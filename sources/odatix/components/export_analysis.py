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
Export of RTL analysis results to a v2 results file.

RTL analysis (odatix analyze) produces, per architecture/configuration, a
status (PASSED/WARNING/FAILED/INCOMPLETE) together with the list of detected
errors and (critical) warnings. This module compiles those detailed results
into the shared Odatix results file format (see odatix.lib.results_schema), so
that they are discoverable by Odatix Explorer exactly like synthesis/workflow
results, and rendered by its dedicated analysis dashboard.

Analysis records use ``type: analysis``. The status, error messages and the
error/warning lists are stored as informational ("_"-prefixed) meta keys so
they are not treated as chart dimensions and do not take part in the record
identity (re-running the same architecture replaces its previous record even
when its status changed). The error/warning counts are stored as numeric
metrics.
"""

import os

import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
import odatix.lib.results_schema as results_schema
from odatix.components.export_common import load_existing_results_file

script_name = os.path.basename(__file__)

# Result type of analysis records in the v2 results file.
TYPE_ANALYSIS = "analysis"

# Output file name (per eda tool), placed in the workspace result directory.
def analysis_results_filename(tool):
  return "results_analysis_" + str(tool) + ".yml"


def _split_architecture(architecture):
  """
  Split the analysis "architecture" label ("<arch>/<config>") into an
  (architecture, configuration) pair. A label without "/" is kept whole as the
  architecture, with an empty configuration.
  """
  architecture = str(architecture)
  if "/" in architecture:
    arch, _, config = architecture.rpartition("/")
    return arch, config
  return architecture, ""


def _record_from_result(result, tool):
  """Build a v2 analysis record from one generate_analysis_summary() result."""
  architecture, configuration = _split_architecture(result.get("architecture", ""))

  meta = {
    results_schema.META_TYPE: TYPE_ANALYSIS,
    "tool": str(tool),
    results_schema.META_ARCHITECTURE: architecture,
    results_schema.META_CONFIGURATION: configuration,
    # Informational fields (not dimensions, excluded from record identity).
    "_status": str(result.get("status", "")),
  }

  error_message = result.get("error", "")
  if error_message:
    meta["_error_message"] = str(error_message)

  errors = [str(e) for e in (result.get("errors") or [])]
  if errors:
    meta["_errors"] = errors

  blackbox_warnings = [str(w) for w in (result.get("blackbox_warnings") or [])]
  if blackbox_warnings:
    meta["_critical_warnings"] = blackbox_warnings

  log_file = result.get("log_file")
  if log_file:
    meta["_log_file"] = str(log_file)

  metrics = {
    "error_count": int(result.get("error_count", 0)),
    "warning_count": int(result.get("warning_count", 0)),
    "critical_warning_count": len(blackbox_warnings),
    "standard_warning_count": int(result.get("standard_warning_count", 0)),
  }

  return results_schema.make_record(meta, metrics)


def export_analysis_results(summary, output_dir, tool):
  """
  Compile an analysis summary (as returned by
  odatix.components.analyze_results.generate_analysis_summary) into a v2 results
  file "results_analysis_<tool>.yml" in ``output_dir``.

  Existing records for the same architectures/configurations are replaced
  (incremental export), so re-running the analysis keeps the file up to date.

  Returns:
      str | None: the path of the written file, or None if nothing was written.
  """
  if not summary or not summary.get("results"):
    return None

  output_file = os.path.join(output_dir, analysis_results_filename(tool))

  units, records = load_existing_results_file(output_file)

  new_records = [_record_from_result(result, tool) for result in summary["results"]]
  records = results_schema.upsert_records(records, new_records)

  try:
    results_schema.dump_results_file(output_file, units, records)
  except Exception as e:
    printc.error('Could not write analysis results "' + output_file + '"', script_name=script_name)
    printc.cyan("error details: ", script_name=script_name, end="")
    print(str(e))
    return None

  printc.say('Analysis results written to "' + output_file + '"', script_name=script_name)
  printc.note("Run 'odatix-explorer' and open the Analysis dashboard to explore them", script_name=script_name)
  return output_file


######################################
# Per-job export (au fil de l'eau)
######################################

def configure_analysis_job_exports(parallel_jobs, *, analysis_work_root, output_dir):
  """
  Attach a per-job export descriptor to every analysis job, so the job handler
  exports its result as soon as the job finishes (au fil de l'eau — see
  export_single_analysis_job and the "analysis" branch of
  ParallelJobHandler._run_post_success_export), instead of exporting everything
  at the end of the session.

  ``analysis_work_root`` is the analysis work directory that holds the per-tool
  sub-directories (``<tool>/<target>/<architecture>/<configuration>``). The eda
  tool and the architecture name are derived from each job's temporary
  directory, so a single call tags every tool's jobs in a shared job list.

  Returns:
      int: the number of jobs configured.
  """
  if analysis_work_root is None or output_dir is None:
    return 0

  analysis_work_root = os.path.realpath(str(analysis_work_root))
  output_dir = os.path.realpath(str(output_dir))

  configured = 0
  for job in list(getattr(parallel_jobs, "job_list", []) or []):
    tmp_dir = os.path.realpath(str(getattr(job, "tmp_dir", "")))
    if not tmp_dir:
      continue

    try:
      rel_path = os.path.relpath(tmp_dir, analysis_work_root)
    except Exception:
      continue
    if rel_path.startswith(".."):
      continue

    parts = [part for part in rel_path.split(os.sep) if part not in ("", ".")]
    if len(parts) < 4:  # tool / target / architecture / configuration
      continue

    tool = parts[0]
    architecture = parts[2] + "/" + parts[3]

    job.post_run_export = {
      "kind": "analysis",
      "tool": str(tool),
      "output_dir": output_dir,
      "tmp_dir": tmp_dir,
      "architecture": architecture,
    }
    configured += 1

  return configured


def export_single_analysis_job(job, export_config=None):
  """
  Export the result of a single finished analysis job into
  "results_analysis_<tool>.yml" (incremental upsert). Called by the job handler
  right after the job succeeds. Returns True on success.
  """
  from odatix.components.analyze_results import analyze_log_dir

  config = export_config if isinstance(export_config, dict) else getattr(job, "post_run_export", None)
  if not isinstance(config, dict):
    printc.error("Missing per-job analysis export configuration", script_name=script_name)
    return False

  tool = str(config.get("tool", ""))
  output_dir = str(config.get("output_dir", ""))
  tmp_dir = str(config.get("tmp_dir", ""))
  architecture = str(config.get("architecture", ""))

  if tool == "" or output_dir == "" or tmp_dir == "":
    printc.error("Per-job analysis export configuration is incomplete", script_name=script_name)
    return False

  log_dir = os.path.join(tmp_dir, hard_settings.work_log_path)
  result = analyze_log_dir(log_dir, tool, architecture)
  if result is None:
    printc.warning('No analysis log found in "' + log_dir + '"', script_name=script_name)
    return False

  output_file = os.path.join(output_dir, analysis_results_filename(tool))
  units, records = load_existing_results_file(output_file)
  records = results_schema.upsert_records(records, [_record_from_result(result, tool)])

  try:
    results_schema.dump_results_file(output_file, units, records)
  except Exception as e:
    printc.error('Could not write analysis results "' + output_file + '"', script_name=script_name)
    printc.cyan("error details: ", script_name=script_name, end="")
    print(str(e))
    return False

  printc.say('Analysis result updated in "' + output_file + '"', script_name=script_name)
  return True
