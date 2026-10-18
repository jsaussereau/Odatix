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
Export of RTL analysis results to the results files.

An analysis concludes, for each design and tool, a status and a list of
findings (see odatix.lib.analysis). Each of those results is a record of
"results_analysis_<tool>.yml" in the workspace result directory, written as
soon as its job ends -- whether the tool succeeded or not: an analysis that
found errors is a result too -- so that Odatix Explorer shows it on its RTL
Analysis page, and "odatix results analysis" can report it again.

Analysis records use ``type: analysis``. What they found is held by
informational ("_"-prefixed) meta keys, so that it is neither a chart dimension
nor part of the record identity: analyzing a design again replaces its record,
whatever it concluded. The record format is described by
:meth:`odatix.lib.analysis.AnalysisResult.to_record`.
"""

import os

import odatix.lib.analysis as analysis
import odatix.lib.printc as printc
import odatix.lib.results_schema as results_schema
import odatix.lib.results_cache as results_cache
from odatix.components.export_common import load_existing_results_file

script_name = os.path.basename(__file__)

#: Result type of analysis records in the results files.
TYPE_ANALYSIS = analysis.TYPE_ANALYSIS


def analysis_results_filename(tool):
  """The results file of the analyses of a tool, in the workspace result directory."""
  return analysis.results_filename(tool)


def export_analysis_results(results, output_dir, quiet=False):
  """
  Write analysis results into the results files of their tools, replacing the
  records of the same designs.

  Args:
      results (list): AnalysisResult objects, of one or several tools.

  Returns:
      bool: whether every file could be written. What failed was reported.
  """
  by_tool = {}
  for result in results:
    by_tool.setdefault(result.tool, []).append(result)

  success = True
  for tool, tool_results in sorted(by_tool.items()):
    output_file = os.path.join(output_dir, analysis_results_filename(tool))
    units, records = load_existing_results_file(output_file)
    records = _without_records_replaced(records, tool, tool_results)
    records = results_schema.upsert_records(records, [result.to_record(results_schema) for result in tool_results])
    try:
      results_cache.store(output_file, units, records)
    except Exception as e:
      printc.error('Could not write analysis results "' + output_file + '"', script_name=script_name)
      printc.cyan("error details: ", script_name=script_name, end="")
      print(str(e))
      success = False
      continue
    if not quiet:
      printc.say('Analysis results written to "' + output_file + '"', script_name=script_name)
  return success


def _without_records_replaced(records, tool, results):
  """
  The records a new result replaces although they do not say the same flow:
  those written before the flow of an analysis was recorded, for the default
  flow of the tool, carried none.
  """
  import odatix.lib.eda_tools as eda_tools

  default_flow = eda_tools.get_default_flow(tool, job_type="analysis")
  replaced = {
    (result.architecture, result.configuration)
    for result in results
    if result.flow in (None, "", default_flow)
  }
  if not replaced:
    return records
  return [
    record for record in records
    if (record.get("meta", {}).get(results_schema.META_FLOW) not in (None, "")
        or (record.get("meta", {}).get(results_schema.META_ARCHITECTURE),
            record.get("meta", {}).get(results_schema.META_CONFIGURATION)) not in replaced)
  ]


######################################
# Per-job export (au fil de l'eau)
######################################

def configure_analysis_job_exports(parallel_jobs, *, analysis_work_root, output_dir, flows=None, expected=None):
  """
  Have the job handler export the result of every analysis job as soon as it
  ends (see export_single_analysis_job), including when the tool fails: for an
  analysis, a failure is a result.

  ``analysis_work_root`` is the analysis work directory, holding one
  sub-directory per tool ("<tool>" or "<tool>@<flow>"), which is how the tool of
  each job is known. ``flows`` ({tool: flow}) names the flow of each tool, and
  ``expected`` is what the run settings say is normal (their "expected"
  section, as written), handed over to the export as it is.

  Returns:
      int: the number of jobs configured.
  """
  import odatix.lib.eda_tools as eda_tools

  if analysis_work_root is None or output_dir is None:
    return 0

  analysis_work_root = os.path.realpath(str(analysis_work_root))
  output_dir = os.path.realpath(str(output_dir))

  configured = 0
  for job in list(getattr(parallel_jobs, "job_list", []) or []):
    tmp_dir = os.path.realpath(str(getattr(job, "tmp_dir", "") or ""))
    if not tmp_dir:
      continue
    try:
      rel_path = os.path.relpath(tmp_dir, analysis_work_root)
    except Exception:
      continue
    parts = [part for part in rel_path.split(os.sep) if part not in ("", ".")]
    if rel_path.startswith("..") or len(parts) < 2:
      continue

    tool, dir_flow = eda_tools.split_tool_work_dirname(parts[0])
    job.post_run_export = {
      "kind": "analysis",
      # An analysis that found errors is a result to export, not a job to drop.
      "on_failure": True,
      "tool": str(tool),
      "flow": str((flows or {}).get(tool) or dir_flow or "") or None,
      "output_dir": output_dir,
      "tmp_dir": tmp_dir,
      "expected": expected,
    }
    configured += 1

  return configured


def settle_job_status(job, result):
  """
  Make the status of an analysis job say whether the tool ran, the same way for
  every tool: a job whose analysis concluded something about the design
  (passed, warnings, errors in the RTL, a language the tool does not read)
  succeeded, whatever the exit code of the tool; one whose tool could not run or
  did not finish failed. Tools do not agree on what an error in the RTL does to
  their exit code (Vivado fails, a linter may not): the verdict is the analysis
  status, not the job status.

  The job handler reads ``_failed_before_export`` once the export returns to
  settle the status of the job.
  """
  if job is None:
    return
  try:
    job._failed_before_export = not analysis.tool_ran(result.status)
  except Exception:
    pass


def export_single_analysis_job(job, export_config=None):
  """
  Export the result of one finished analysis job into the results file of its
  tool. Called by the job handler as soon as the job ends.
  """
  from odatix.components.analysis_report import job_identity

  config = export_config if isinstance(export_config, dict) else getattr(job, "post_run_export", None)
  if not isinstance(config, dict):
    printc.error("Missing per-job analysis export configuration", script_name=script_name)
    return False

  tool = str(config.get("tool", "") or "")
  output_dir = str(config.get("output_dir", "") or "")
  tmp_dir = str(config.get("tmp_dir", "") or "")
  if tool == "" or output_dir == "" or tmp_dir == "":
    printc.error("Per-job analysis export configuration is incomplete", script_name=script_name)
    return False

  architecture, configuration, flow = job_identity(tmp_dir)
  result = analysis.analyze_job(
    tmp_dir, tool,
    architecture=architecture or os.path.basename(tmp_dir),
    configuration=configuration,
    flow=flow or config.get("flow"),
    expected=analysis.read_expectations(config.get("expected")),
  )
  if result is None:
    printc.warning('No analysis job directory "' + tmp_dir + '"', script_name=script_name)
    return False

  settle_job_status(job, result)
  if not export_analysis_results([result], output_dir, quiet=True):
    return False
  printc.say(
    'Analysis of "' + result.name + '": ' + analysis.STATUS_LABELS[result.status].lower()
    + (" (" + result.summary + ")" if result.summary else ""),
    script_name=script_name,
  )
  return True


######################################
# From the work directory ("odatix results analysis")
######################################

def export_analysis_from_work(analysis_root, output_dir, tools=None, expected=None, export=True):
  """
  Read again every analysis job of the analysis work directory and, unless
  ``export`` is False, write their records.

  Returns:
      tuple: (results, whether every file could be written)
  """
  from odatix.components.analysis_report import collect_results, job_directories

  results = collect_results(job_directories(analysis_root, tools=tools), expected=analysis.read_expectations(expected))
  if not export or not results:
    return results, True
  return results, export_analysis_results(results, output_dir)


def add_arguments(parser):
  from odatix.components.cli_options import add_options

  add_options(
    parser, "tool", "settings_file", "work_path", "result_path", "noexport", "config",
    tool={"nargs": "+", "default": None, "help": "only report the analyses of these tools"},
    settings_file={"help": "analysis settings file, whose \"expected\" section says what is normal (default: the workspace's)"},
    work_path={"help": "work directory (default: the workspace's)"},
    noexport={"help": "only print the report, without writing the results files"},
  )


def main(args):
  """Report, and export again, the analyses of the work directory."""
  import odatix.run.cli as run_cli
  from odatix.components.analysis_report import print_report
  from odatix.components.run_analysis import read_run_expectations

  workspace = run_cli.command_workspace(args.config, script_name)
  paths = workspace.paths
  analysis_root = paths.under_work_path("analysis_work_path", args.work_path)
  if not os.path.isdir(analysis_root):
    printc.error('No analysis work directory "' + analysis_root + '"', script_name)
    printc.note("Run an analysis with \"odatix analyze\" first", script_name)
    return False

  settings_file = args.settings_file or paths.analyze_settings_file
  results, success = export_analysis_from_work(
    analysis_root,
    args.result_path or paths.result_path,
    tools=args.tool,
    expected=read_run_expectations(settings_file),
    export=not args.noexport,
  )
  print_report(results)
  return success
