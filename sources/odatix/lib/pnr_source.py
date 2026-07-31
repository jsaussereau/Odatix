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
The synthesis jobs a place & route run can start from.

Unlike every other job type, "odatix pnr" does not start from the RTL and the
architecture configuration files: it starts from a synthesis job that has already
run and succeeded, possibly with a different eda tool. Synthesizing with Design
Compiler and placing & routing with Innovus is one job of each type, chained
through the files the first one left in its work directory.

This module owns that link:

  * finding the synthesis jobs that can be used as an input (discover_sources),
  * naming one of them in a settings file (PnrSource.selector, parse_selector),
  * matching what a run asks for against what is on disk (match_sources).

A source is usable when its job directory reports a completed run *and* holds the
three handoff files a synthesis flow writes for the next tool (netlist, sdc,
sdf — see hard_settings.pnr_netlist_filename and its siblings). A synthesis that
never wrote them cannot feed a place & route job, whatever its status says.

Selector grammar, one source per entry, "*" accepted at every level::

    <source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]

    fmax_synthesis/design_compiler/gf22/Counter/8bits
    custom_freq_synthesis/genus@fast/gf22/Counter/*@100MHz
    custom_freq_synthesis/*/*/*/*
"""

import os

import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
import odatix.lib.printc as printc

script_name = os.path.basename(__file__)

# Job types a place & route job can start from, and the settings key holding the
# work sub-directory of each.
SOURCE_JOB_TYPES = ("fmax_synthesis", "custom_freq_synthesis")

# Separator between a configuration and the frequency it was synthesized at, in a
# selector. "/" is already the level separator and "@" already tells a flow from
# its tool, so a third one is needed.
FREQUENCY_SEPARATOR = "@"

WILDCARD = "*"


class PnrSource:
  """
  One completed synthesis job a place & route job can start from.

  Attributes:
      job_type (str): "fmax_synthesis" or "custom_freq_synthesis".
      tool (str): the eda tool that ran the synthesis.
      flow (str | None): the flow of that tool, None for its default flow.
      work_dirname (str): how tool and flow are spelled in the work tree
          ("design_compiler", "genus@fast").
      target (str), architecture (str), configuration (str): what was synthesized.
      frequency (int | None): the frequency it was synthesized at, None for an
          fmax search (there the frequency is a result, not an input).
      job_dir (str): the synthesis job directory.
  """

  def __init__(self, job_type, tool, flow, work_dirname, target, architecture, configuration, frequency, job_dir):
    self.job_type = job_type
    self.tool = tool
    self.flow = flow
    self.work_dirname = work_dirname
    self.target = target
    self.architecture = architecture
    self.configuration = configuration
    self.frequency = frequency
    self.job_dir = job_dir

  ######################################
  # Handoff files
  ######################################

  def _result_file(self, filename):
    return os.path.join(self.job_dir, hard_settings.work_result_path, filename)

  @property
  def netlist(self):
    return self._result_file(hard_settings.pnr_netlist_filename)

  @property
  def sdc(self):
    return self._result_file(hard_settings.pnr_sdc_filename)

  @property
  def sdf(self):
    return self._result_file(hard_settings.pnr_sdf_filename)

  @property
  def handoff_files(self):
    return (self.netlist, self.sdc, self.sdf)

  def missing_handoff_files(self):
    """The handoff files this synthesis job did not write, in order."""
    return [path for path in self.handoff_files if not os.path.isfile(path)]

  @property
  def settings_file(self):
    """The settings.yml describing what was synthesized here."""
    return os.path.join(self.job_dir, hard_settings.yaml_config_filename)

  ######################################
  # Naming
  ######################################

  @property
  def frequency_segment(self):
    """
    Last path segment of the place & route job started from this source, and the
    frequency part of its selector: "<N>MHz" for a custom frequency synthesis,
    the literal "fmax" for an fmax search. Always present, so every pnr job
    directory has the same depth and the two kinds never nest into each other.
    """
    if self.frequency is None:
      return hard_settings.pnr_fmax_dirname
    return str(self.frequency) + "MHz"

  @property
  def selector(self):
    """How to name this source in a settings file (see the module docstring)."""
    selector = "/".join([self.job_type, self.work_dirname, self.target, self.architecture, self.configuration])
    if self.frequency is not None:
      selector += FREQUENCY_SEPARATOR + self.frequency_segment
    return selector

  @property
  def display_name(self):
    """How to name this source in the checklist and in the monitor."""
    name = self.architecture + "/" + self.configuration + " (" + self.target + ")"
    if self.frequency is not None:
      name += " @ " + str(self.frequency) + " MHz"
    return name + " from " + self.work_dirname

  def __repr__(self):
    return "PnrSource(" + self.selector + ")"


######################################
# Discovery
######################################


def _is_completed(job_dir):
  """
  Whether a synthesis job directory reports a completed run. Both status files
  are accepted: an fmax search writes "status.log", a custom frequency synthesis
  "synth_status.log".
  """
  for filename in (hard_settings.fmax_status_filename, hard_settings.synth_status_filename):
    status_file = os.path.join(job_dir, hard_settings.work_log_path, filename)
    if not os.path.isfile(status_file):
      continue
    try:
      with open(status_file, "r") as f:
        if hard_settings.valid_status in f.read():
          return True
    except OSError:
      continue
  return False


def _subdirectories(path):
  try:
    return sorted(entry for entry in os.listdir(path) if os.path.isdir(os.path.join(path, entry)))
  except OSError:
    return []


def _parse_frequency_dirname(dirname):
  """The frequency a "<N>MHz" work directory holds, or None when it is not one."""
  name = str(dirname)
  if not name.endswith("MHz"):
    return None
  try:
    return int(name[: -len("MHz")])
  except ValueError:
    return None


def discover_sources(work_root, result_types=None, job_types=None, require_handoff=True):
  """
  Find every completed synthesis job of a workspace that a place & route job can
  start from.

  Args:
      work_root (str): the workspace work directory.
      result_types (dict, optional): the {job_type: {"path": ...}} mapping of
          OdatixSettings.result_types, to honour a workspace that renamed its
          work sub-directories. Defaults to the job type names.
      job_types (list, optional): restrict the search to these source job types.
      require_handoff (bool): drop the jobs that did not write the handoff files.
          Pass False to list them anyway (the GUI shows them as unusable rather
          than hiding them).

  Returns:
      list: the sources found, ordered by selector.
  """
  sources = []

  for job_type in (job_types or SOURCE_JOB_TYPES):
    if job_type not in SOURCE_JOB_TYPES:
      continue
    work_subpath = job_type
    if isinstance(result_types, dict) and job_type in result_types:
      work_subpath = result_types[job_type].get("path", job_type)

    type_root = os.path.join(str(work_root), str(work_subpath))
    if not os.path.isdir(type_root):
      continue

    for work_dirname in _subdirectories(type_root):
      tool, flow = eda_tools.split_tool_work_dirname(work_dirname)
      tool_root = os.path.join(type_root, work_dirname)

      for target in _subdirectories(tool_root):
        for architecture in _subdirectories(os.path.join(tool_root, target)):
          for configuration in _subdirectories(os.path.join(tool_root, target, architecture)):
            config_dir = os.path.join(tool_root, target, architecture, configuration)

            if job_type == "custom_freq_synthesis":
              candidates = [
                (_parse_frequency_dirname(entry), os.path.join(config_dir, entry))
                for entry in _subdirectories(config_dir)
              ]
              candidates = [(frequency, path) for frequency, path in candidates if frequency is not None]
            else:
              candidates = [(None, config_dir)]

            for frequency, job_dir in candidates:
              if not _is_completed(job_dir):
                continue
              source = PnrSource(
                job_type=job_type,
                tool=tool,
                flow=flow,
                work_dirname=work_dirname,
                target=target,
                architecture=architecture,
                configuration=configuration,
                frequency=frequency,
                job_dir=job_dir,
              )
              if require_handoff and source.missing_handoff_files():
                continue
              sources.append(source)

  return sorted(sources, key=lambda source: source.selector)


######################################
# Selectors
######################################


def parse_selector(selector):
  """
  Split a selector into the levels it constrains.

  Returns:
      dict | None: {"job_type", "work_dirname", "target", "architecture",
      "configuration", "frequency_segment"}, each either a value or "*", or None
      when the selector is malformed.
  """
  if not isinstance(selector, str):
    return None
  selector = selector.strip()
  if selector == "":
    return None

  frequency_segment = WILDCARD
  if FREQUENCY_SEPARATOR in selector:
    selector, _, frequency_segment = selector.rpartition(FREQUENCY_SEPARATOR)
    frequency_segment = frequency_segment.strip() or WILDCARD

  parts = [part.strip() for part in selector.split("/")]
  if len(parts) != 5 or any(part == "" for part in parts):
    return None

  return {
    "job_type": parts[0],
    "work_dirname": parts[1],
    "target": parts[2],
    "architecture": parts[3],
    "configuration": parts[4],
    "frequency_segment": frequency_segment,
  }


def _matches(pattern, value):
  return pattern == WILDCARD or pattern == str(value)


def source_matches(source, parsed_selector):
  """Whether a source satisfies every level a parsed selector constrains."""
  return (
    _matches(parsed_selector["job_type"], source.job_type)
    and _matches(parsed_selector["work_dirname"], source.work_dirname)
    and _matches(parsed_selector["target"], source.target)
    and _matches(parsed_selector["architecture"], source.architecture)
    and _matches(parsed_selector["configuration"], source.configuration)
    and _matches(parsed_selector["frequency_segment"], source.frequency_segment)
  )


def match_sources(sources, selectors, report_unmatched=True):
  """
  The sources a run asks for, in discovery order and without duplicates.

  Args:
      sources (list): what discover_sources found.
      selectors (list): the entries of the settings file's "sources" key.
      report_unmatched (bool): warn about a selector nothing matches, which is
          almost always a typo or a synthesis that has not run yet.

  Returns:
      list: the matched sources.
  """
  matched = []
  seen = set()

  for selector in selectors or []:
    parsed = parse_selector(selector)
    if parsed is None:
      printc.error('Invalid place & route source "' + str(selector) + '"', script_name)
      printc.note(
        "A source is written "
        '"<source_type>/<source_tool>[@<source_flow>]/<target>/<architecture>/<configuration>[@<frequency>MHz]"',
        script_name,
      )
      continue

    found = False
    for source in sources:
      if not source_matches(source, parsed):
        continue
      found = True
      if source.selector in seen:
        continue
      seen.add(source.selector)
      matched.append(source)

    if not found and report_unmatched:
      printc.warning('No completed synthesis matches "' + str(selector) + '"', script_name)

  return matched
