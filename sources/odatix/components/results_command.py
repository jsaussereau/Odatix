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
What "odatix results <type>" runs, for the command line, the graphical
interface and the Python API alike (odatix.run.export_results).

Each type is the exporter of one kind of result (odatix.components.export_*).
This module adds what the types share:

  * an export that rewrites a results file (synth, sim, workflow) applies the
    derived metrics again right after: the file it wrote has none, and the
    metrics a user defined must not vanish because one kind was re-exported;
  * an export succeeds only if it reported no error: a metric that cannot be
    read, a definition that cannot be parsed, a file that cannot be written all
    say "error", and a script chaining exports must be able to tell.
"""

import argparse
import os

import odatix.lib.printc as printc
from odatix.lib.settings import OdatixSettings
from odatix.components import export_results as exp_res
from odatix.components import export_simulation_results as exp_sim_res
from odatix.components import export_workflow_results as exp_workflow_res
from odatix.components import export_derived_metrics as exp_derived
from odatix.components import export_analysis as exp_analysis

script_name = os.path.basename(__file__)

#: The types of "odatix results", "all" doing every other one in turn.
KINDS = ("all", "synth", "sim", "workflow", "analysis", "derived")

#: The types whose export writes a results file from scratch, losing the
#: derived metrics it held: they are applied again after it.
REDERIVED_KINDS = ("synth", "sim", "workflow")


def command_status(result):
  """
  Whether an exporter succeeded, from what its main() returned: nothing or True
  for a success, False or a non-zero exit code for a failure.
  """
  if result is None or result is True:
    return True
  if result is False:
    return False
  if isinstance(result, int):
    return result == 0
  return bool(result)


def _run(main_function, args, on_exception=None):
  """
  Run an exporter and say whether it succeeded, however it says so: by what it
  returns, or by stopping with an exit code. An unexpected exception goes to
  `on_exception` (the command line logs it), or up to the caller.
  """
  try:
    return command_status(main_function(args))
  except SystemExit as e:
    return e.code in (None, 0)
  except Exception as e:
    if on_exception is None:
      raise
    on_exception(e)
    return False


def add_arguments(kind, parser):
  """The options of one type, as "odatix results <type>" takes them."""
  if kind in ("all", "synth"):
    exp_res.add_arguments(parser)
  elif kind == "sim":
    exp_sim_res.add_arguments(parser)
  elif kind == "workflow":
    exp_workflow_res.add_arguments(parser)
  elif kind == "analysis":
    exp_analysis.add_arguments(parser)
  elif kind == "derived":
    exp_derived.add_arguments(parser)
  else:
    raise ValueError('Unknown result type "' + str(kind) + '": expected one of ' + ", ".join(KINDS))


def default_arguments(kind):
  """The options of one type, all left at their default."""
  parser = argparse.ArgumentParser(add_help=False)
  add_arguments(kind, parser)
  return parser.parse_args([])


######################################
# The types
######################################

def _derive(args, on_exception=None):
  """Apply the derived metrics to the result files the export wrote into."""
  def derive(_args):
    return exp_derived.run(
      result_path=getattr(args, "result_path", None), config_file=args.config, announce_unchanged=False,
      # The API names the file of the workspace it was given
      derived_metrics_file=getattr(args, "derived_metrics_file", None),
    )
  return _run(derive, args, on_exception)


def _export_workflow(args, on_exception=None):
  """
  "odatix results workflow": like "odatix results sim", a missing work
  directory is an error, and one with no run has nothing to export. Nothing is
  written then: an empty results file would only show up as an empty source in
  Odatix Explorer, and replace the results of runs since cleaned up.
  """
  work_root = args.work_path
  if work_root is None:
    settings = OdatixSettings(args.config, silent=True)
    work_root = os.path.join(str(settings.work_path), str(settings.workflow_work_path))
  if not os.path.isdir(str(work_root)):
    printc.error('No workflow work directory "' + str(work_root) + '": nothing written', script_name)
    printc.tip('Run workflows with "odatix workflow" first', script_name)
    return False
  if not exp_workflow_res._discover_runs(work_root):
    printc.note('No workflow run found in "' + str(work_root) + '": nothing to export', script_name)
    return True
  return _run(exp_workflow_res.main, args, on_exception)


def export_all(args, on_exception=None):
  """
  "odatix results": every kind of result there is, then the derived metrics,
  which read what the others wrote. A kind with no work directory has simply
  not been run, and is skipped.
  """
  settings = OdatixSettings(args.config)
  work_root = args.work_path if args.work_path is not None else settings.work_path
  success = True

  if os.path.isdir(work_root):
    success = _run(exp_res.main, argparse.Namespace(
      tool=args.tool, work_path=work_root, result_path=args.result_path, metrics=args.metrics, config=args.config,
    ), on_exception) and success
  else:
    printc.note('No work directory "' + str(work_root) + '": no synthesis results to export', script_name)

  for module, work_key in (
    (exp_sim_res, "simulation_work_path"),
    (exp_workflow_res, "workflow_work_path"),
  ):
    kind_root = os.path.join(str(work_root), str(getattr(settings, work_key)))
    if not os.path.isdir(kind_root):
      continue
    options = argparse.Namespace(
      work_path=kind_root, result_path=args.result_path, output=module.DEFAULT_OUTPUT_FILENAME, config=args.config, sim_path=None,
    )
    success = _run(module.main, options, on_exception) and success

  # Derived metrics come last: they read the records the exports above just
  # wrote, plus the simulation and workflow ones already on disk.
  return _derive(args, on_exception) and success


_EXPORTERS = {
  "all": export_all,
  "synth": lambda args, on_exception=None: _run(exp_res.main, args, on_exception),
  "sim": lambda args, on_exception=None: _run(exp_sim_res.main, args, on_exception),
  "workflow": _export_workflow,
  "analysis": lambda args, on_exception=None: _run(exp_analysis.main, args, on_exception),
  "derived": lambda args, on_exception=None: _run(exp_derived.main, args, on_exception),
}


def export(kind, args, on_exception=None):
  """
  Run one type of "odatix results".

  Args:
      kind (str): one of KINDS.
      args (argparse.Namespace): its options (see add_arguments).
      on_exception (callable): what to do with an unexpected exception, which
          otherwise goes up to the caller.

  Returns:
      tuple: (success, errors). ``errors`` lists every error the export
      reported; ``success`` is False as soon as there is one, or when the export
      itself failed.
  """
  if kind not in _EXPORTERS:
    raise ValueError('Unknown result type "' + str(kind) + '": expected one of ' + ", ".join(KINDS))

  errors = []

  def count_errors(level, message, _script_name):
    if level == "error":
      errors.append(message)

  with printc.collect(count_errors):
    success = _EXPORTERS[kind](args, on_exception)
    if kind in REDERIVED_KINDS and success:
      # The results file it wrote has lost its derived metrics. An export that
      # failed wrote nothing to apply them to (a missing work directory, a file
      # that could not be written).
      success = _derive(args, on_exception)

  return success and not errors, errors
