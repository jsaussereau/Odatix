# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
Enumeration of the jobs of a place & route run.

Every other job type builds its job list from the architecture configuration
files: a job is "this design, in this configuration, on this target". A place &
route job is instead "this synthesis job, placed & routed by that tool", so its
job list is built from what is already in the work tree (see
odatix.lib.pnr_source) rather than from the architecture directory.

What a job *is*, though, does not change: the rest of Odatix (the checklist, the
monitor, the per-job export, the tcl settings of the work directory) reads the
same Architecture object whatever produced it. So PnrJobHandler subclasses
ArchitectureHandler and overrides only the enumeration: each job's Architecture
is read back from the settings.yml its synthesis job left behind — which is
exactly what makes a cross-tool run possible, since the clock signal, the top
level module and the parameter domains are the synthesis' answer, not something
the place & route run has to be told again.

The work directory of a place & route job is::

    <work>/pnr/<pnr_tool[@pnr_flow]>/<synth_tool[@synth_flow]>/<target>/<architecture>/<configuration>/<frequency>

with the last segment being "<N>MHz" for a custom frequency source and the
literal "fmax" for an fmax search, so both kinds sit side by side instead of one
nesting inside the other.
"""

import copy
import os

import odatix.lib.hard_settings as hard_settings
import odatix.lib.pnr_source as pnr_source
import odatix.lib.printc as printc
from odatix.lib.architecture_handler import Architecture, ArchitectureHandler
from odatix.lib.run_report import Category

script_name = os.path.basename(__file__)


class PnrJobHandler(ArchitectureHandler):
  """
  Builds the job list of a place & route run from the completed synthesis jobs it
  starts from.

  Everything the callers of a handler use — plan, valid_archs, print_summary,
  get_valid_arch_count, classify_job, overwrite, command, process_group — is
  inherited unchanged, so a place & route run goes through the same checklist,
  the same daemon deduplication and the same preparation loop as any other.
  """

  def __init__(
    self,
    work_path,
    source_work_root,
    script_path,
    work_rtl_path,
    work_script_path,
    work_log_path,
    work_report_path,
    process_group,
    command,
    eda_target_filename,
    overwrite,
    source_result_types=None,
    log_path=None,
    fmax_status_filename=None,
    valid_status=None,
    continue_on_error=False,
    force_single_thread=False,
    requested_steps=None,
    rerun_step_index=None,
  ):
    super().__init__(
      work_path=work_path,
      # A place & route job never reads the architecture configuration files: it
      # inherits what was synthesized from the source job's settings.yml.
      arch_path=None,
      script_path=script_path,
      log_path=log_path if log_path is not None else hard_settings.work_log_path,
      work_rtl_path=work_rtl_path,
      work_script_path=work_script_path,
      work_log_path=work_log_path,
      work_report_path=work_report_path,
      process_group=process_group,
      command=command,
      eda_target_filename=eda_target_filename,
      fmax_status_filename=fmax_status_filename if fmax_status_filename is not None else hard_settings.synth_status_filename,
      frequency_search_filename=hard_settings.frequency_search_filename,
      param_settings_filename=hard_settings.param_settings_filename,
      valid_status=valid_status if valid_status is not None else hard_settings.valid_status,
      valid_frequency_search=hard_settings.valid_frequency_search,
      forced_fmax_lower_bound=None,
      forced_fmax_upper_bound=None,
      forced_custom_freq_list=None,
      overwrite=overwrite,
      continue_on_error=continue_on_error,
      force_single_thread=force_single_thread,
      requested_steps=requested_steps,
      rerun_step_index=rerun_step_index,
    )

    self.source_work_root = source_work_root
    self.source_result_types = source_result_types
    self.architecture_instances = []
    # Every source found in the work tree, whether or not this run selected it.
    # The GUI lists them, the CLI reports how many were considered.
    self.available_sources = []

  ######################################
  # Job directory
  ######################################

  def job_dir(self, source):
    """Where the place & route job of a source runs."""
    return os.path.join(
      self.work_path,
      source.work_dirname,
      source.target,
      source.architecture,
      source.configuration,
      source.frequency_segment,
    )

  ######################################
  # Enumeration
  ######################################

  def get_pnr_jobs(self, selectors, targets=None, install_path="", constraint_filename=""):
    """
    Build the job list of a place & route run.

    Args:
        selectors (list): the "sources" entries of the run settings file.
        targets (list, optional): the targets the place & route tool declares. A
            source synthesized for a target this tool does not know is rejected:
            keeping the synthesis' target is what lets a place & route result
            join its synthesis result in Odatix Explorer.
        install_path (str): installation path of the place & route tool.
        constraint_filename (str): constraint file name of the place & route
            tool, for the jobs that do not take the source's sdc.

    Returns:
        list: the Architecture instances to prepare, in selection order.
    """
    self.available_sources = pnr_source.discover_sources(
      work_root=self.source_work_root,
      result_types=self.source_result_types,
    )

    if not self.available_sources:
      printc.error("No completed synthesis to place & route", script_name)
      printc.note(
        "Run a synthesis first, and make sure its flow writes the handoff files ("
        + ", ".join(
          [hard_settings.pnr_netlist_filename, hard_settings.pnr_sdc_filename, hard_settings.pnr_sdf_filename]
        )
        + ") in its result directory.",
        script_name,
      )
      return self.architecture_instances

    for source in pnr_source.match_sources(self.available_sources, selectors):
      instance = self._build_instance(source, targets, install_path, constraint_filename)
      if instance is not None:
        self.architecture_instances.append(instance)

    return self.architecture_instances

  def _build_instance(self, source, targets, install_path, constraint_filename):
    """
    Turn one source into the job that places & routes it, or None when it cannot
    be run (the reason is reported and the job is recorded as an error).
    """
    display_name = source.display_name

    if targets and source.target not in targets:
      printc.error(
        'The place & route tool does not support target "' + source.target
        + '", which "' + source.architecture + "/" + source.configuration + '" was synthesized for',
        script_name,
      )
      printc.note(
        'Add "' + source.target + '" to "' + str(self.eda_target_filename)
        + '", or select sources synthesized for a target it supports.',
        script_name,
      )
      self.plan.add(display_name, Category.ERROR)
      return None

    arch = Architecture.read_yaml(source.settings_file)
    if arch is None:
      printc.error('Could not read the settings of the synthesis "' + source.selector + '"', script_name)
      self.plan.add(display_name, Category.ERROR)
      return None

    arch = copy.copy(arch)
    arch.arch_display_name = display_name
    arch.install_path = install_path if install_path else arch.install_path
    arch.constraint_filename = constraint_filename if constraint_filename else arch.constraint_filename
    arch.continue_on_error = self.continue_on_error
    arch.force_single_thread = self.force_single_thread
    # Parameters were replaced in the RTL the synthesis ran on; a place & route
    # job starts from its netlist and has nothing left to replace.
    arch.param_domains = []
    arch.use_parameters = False
    arch.generate_rtl = False
    arch.generate_command = ""
    arch.design_path = None
    arch.file_copy_enable = False
    arch.script_copy_enable = False

    arch.tmp_dir = self.job_dir(source)
    arch.tmp_script_path = os.path.join(arch.tmp_dir, self.work_script_path)
    arch.tmp_report_path = os.path.join(arch.tmp_dir, self.work_report_path)
    arch.tmp_log_path = os.path.join(arch.tmp_dir, self.work_log_path)

    # The synthesis this job continues. Carried on the instance rather than in
    # the Architecture constructor: it is what a place & route job adds, and
    # nothing else has a use for it.
    arch.pnr_source = source

    state, daemon_entry = self.classify_job(arch.tmp_dir, '"' + display_name + '"', job_noun="place & route")

    if state == "cached":
      self.plan.add(display_name, Category.CACHED)
      return None
    if state == "daemon":
      self.plan.add(display_name + ArchitectureHandler._format_daemon_entry(daemon_entry), Category.DAEMON)
      return None

    if state == "overwrite":
      self.plan.add(display_name, Category.OVERWRITE)
    elif state == "incomplete":
      self.plan.add(display_name, Category.INCOMPLETE)
    elif state == "resume":
      self.plan.add(display_name, Category.RESUME)
    else:
      self.plan.add(display_name, Category.NEW)

    self.valid_archs.append(display_name)
    return arch

  def print_summary(self):
    self.plan.print_summary(noun="place & route jobs")
