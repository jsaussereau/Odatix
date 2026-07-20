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
