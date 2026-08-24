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
Apply the derived metrics of a workspace to its result files.

Every other exporter turns *one* run directory into records. This one reads no
run directory at all: it loads every result file of the result directory at
once, because a derived metric is precisely a value a record borrows from
another one, which lives in another file (a synthesis result reading a
simulation result, typically).

That is also why this runs after the exporters rather than inside them. When a
job finishes, the record it needs may simply not exist yet: a synthesis can
complete long before the simulation it borrows a cycle count from. Deriving is
therefore a whole-workspace pass, run once everything else is exported, and
recomputed from scratch every time (see odatix.lib.derived_metrics), so running
it again is a no-op rather than a duplication.
"""

import os
import sys
import argparse

import odatix.lib.printc as printc
import odatix.lib.results_schema as results_schema
import odatix.lib.results_cache as results_cache
import odatix.lib.derived_metrics as derived_metrics_lib
from odatix.lib.settings import OdatixSettings

script_name = os.path.basename(__file__)

RESULTS_FILE_EXTENSIONS = (".yml", ".yaml")


def add_arguments(parser):
  parser.add_argument("-r", "--respath", help="result path")
  parser.add_argument("-d", "--derived", help="derived metrics definition file")
  parser.add_argument(
    "-c",
    "--config",
    default=OdatixSettings.DEFAULT_SETTINGS_FILE,
    help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
  )


def parse_arguments():
  parser = argparse.ArgumentParser(description="Apply derived metrics to the result files")
  add_arguments(parser)
  return parser.parse_args()


def discover_results_files(result_path):
  """Every results file of a result directory, whatever format version it is in."""
  files = []
  if not os.path.isdir(result_path):
    return files

  for filename in sorted(os.listdir(result_path)):
    if not filename.lower().endswith(RESULTS_FILE_EXTENSIONS):
      continue
    path = os.path.join(result_path, filename)
    if os.path.isfile(path):
      files.append(path)
  return files


def load_pool(result_path):
  """
  Load every results file into one pool of records.

  Returns:
      tuple: (files, records, origins) where `files` maps a path to its
      ResultsFile, `records` is the flat pool every derived metric is computed
      over, and `origins` gives the file each pooled record came from, at the
      same index.
  """
  files = {}
  records = []
  origins = []

  for path in discover_results_files(result_path):
    try:
      results_file = results_schema.load_results_file(path)
    except Exception:
      # Not every YAML file of the result directory is a results file.
      continue
    if results_file.schema_detected == results_schema.FORMAT_UNKNOWN:
      continue

    files[path] = results_file
    for record in results_file.records:
      records.append(record)
      origins.append(path)

  return files, records, origins


def apply_derived_metrics(result_path, derived_metrics_file):
  """
  Compute the derived metrics of a workspace and write back the files that
  changed.

  Returns:
      bool: False when the definitions could not be applied at all.
  """
  config = derived_metrics_lib.load_derived_metrics(derived_metrics_file)

  files, records, origins = load_pool(result_path)
  if len(files) == 0:
    printc.note('No results file found in "' + result_path + '"', script_name)
    return True

  units_by_file = {path: results_file.units for path, results_file in files.items()}

  # Every metric this module owns, in this run or a previous one. A metric whose
  # definition was removed is still ours to clean up, units included, which is
  # why the names a previous run recorded count too.
  managed_names = set(config.names)
  for record in records:
    meta = record.get("meta")
    if isinstance(meta, dict):
      managed_names.update(str(name) for name in meta.get(derived_metrics_lib.DERIVED_META_KEY, []) or [])

  # Units are collected per file, so that a derived metric only declares its
  # unit in the files that actually got it.
  pooled_units = {}
  changed_indices = derived_metrics_lib.apply_derived_metrics(config, records, pooled_units)

  if len(changed_indices) == 0:
    if config:
      printc.note("No derived metric to update", script_name)
    return True

  changed_files = set(origins[index] for index in changed_indices)
  derived_names = managed_names

  for path in sorted(changed_files):
    results_file = files[path]
    units = units_by_file[path]

    # A derived metric's unit belongs to a file only if one of its records has
    # that metric, so that a file nothing was derived into stays untouched.
    present = set()
    for record in results_file.records:
      metrics = record.get("metrics")
      if isinstance(metrics, dict):
        present.update(name for name in derived_names if name in metrics)
    for name in present:
      if name in pooled_units:
        units[name] = pooled_units[name]
    for name in derived_names - present:
      units.pop(name, None)

    try:
      results_cache.store(path, units, results_file.records)
    except OSError as e:
      printc.error('Could not write results file "' + path + '": ' + str(e), script_name)
      return False

  printc.say(
    "Derived metrics updated in " + str(len(changed_files)) + " results file"
    + ("s" if len(changed_files) > 1 else ""),
    script_name,
  )
  return True


def configure_post_batch_derivation(parallel_jobs, result_path, derived_metrics_file=None, settings=None):
  """
  Ask a job handler to derive metrics once its whole batch is done.

  Per-job exports run as each job finishes, which is too early to derive: the
  record a metric borrows from may belong to a job still running. The handler
  therefore runs this once nothing is left to run.

  Returns:
      bool: Whether the derivation was armed.
  """
  if parallel_jobs is None or result_path is None:
    return False

  if derived_metrics_file is None:
    derived_metrics_file = derived_metrics_lib.default_derived_metrics_file(settings)
  if not os.path.isfile(derived_metrics_file):
    return False

  parallel_jobs.post_batch_action = {
    "kind": "derived_metrics",
    "result_path": os.path.realpath(str(result_path)),
    "derived_metrics_file": os.path.realpath(str(derived_metrics_file)),
  }
  return True


def run(settings=None, result_path=None, derived_metrics_file=None, config_file=None):
  """
  Entry point for the callers that already know the workspace (the run commands
  and "odatix results"), so that deriving is one call with no argparse detour.
  """
  if settings is None:
    settings = OdatixSettings(config_file or OdatixSettings.DEFAULT_SETTINGS_FILE, silent=True)

  if result_path is None:
    result_path = settings.result_path
  if derived_metrics_file is None:
    derived_metrics_file = derived_metrics_lib.default_derived_metrics_file(settings)

  # A workspace that derives nothing must not pay for loading its results.
  if not os.path.isfile(derived_metrics_file):
    return True

  return apply_derived_metrics(result_path, derived_metrics_file)


def main(args, settings=None):
  if settings is None:
    settings = OdatixSettings(args.config)
    if not settings.valid and args.respath is None:
      printc.error(
        'Could not load settings from file "' + args.config + '" and the -r option is not used',
        script_name=script_name,
      )
      sys.exit(-1)

  result_path = args.respath if args.respath is not None else settings.result_path
  derived_metrics_file = args.derived
  if derived_metrics_file is None:
    derived_metrics_file = derived_metrics_lib.default_derived_metrics_file(settings)

  if not os.path.isfile(derived_metrics_file):
    printc.note(
      'No derived metrics file "' + derived_metrics_file + '", nothing to derive',
      script_name,
    )
    return

  if not apply_derived_metrics(result_path, derived_metrics_file):
    sys.exit(-1)


if __name__ == "__main__":
  main(parse_arguments())
