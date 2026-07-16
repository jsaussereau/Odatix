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
Shared definition of the Odatix results file format.

This module is the single source of truth for reading and writing result
files, used by both the result exporters (producers) and Odatix Explorer
(consumer).

Format v2 (current):
  schema: 2
  units:            # metric name -> unit string
    Fmax: MHz
  results:          # flat list of records
    - meta:
        type: fmax_synthesis          # fmax_synthesis | custom_freq_synthesis | workflow | ...
        target: xc7a100t-csg324-1
        architecture: Example_Counter_verilog
        configuration: 04bits         # full configuration name (incl. "+domain/value" segments)
        frequency: 100                # custom_freq_synthesis only
        timestamp: 2025-08-27_07-50-09
        main: 04bits                  # parameter domains are flattened into meta
        _run_dir: /abs/path           # "_" prefix = informational, not a dimension
      metrics:
        Fmax: 450
        LUT_count: 3

Legacy formats (read-only, auto-converted to v2 records):
  - v1 synthesis: top-level fmax_synthesis / fmax_results / custom_freq_synthesis
    nested as target -> architecture -> configuration [-> "<N>MHz"] -> metrics,
    with an optional Param_Domains dict inside each metrics block.
  - v1 workflow: top-level workflows nested as
    workflow -> config_key -> {run_dir, workflow_full, ..., metrics}.
"""

import os
import re
import yaml

import odatix.lib.hard_settings as hard_settings

SCHEMA_VERSION = 2

# Meta keys with fixed semantics. Any other (non "_"-prefixed) meta key is a
# free dimension (typically a parameter domain).
META_TYPE = "type"
META_TARGET = "target"
META_ARCHITECTURE = "architecture"
META_CONFIGURATION = "configuration"
META_FREQUENCY = "frequency"
META_WORKFLOW = "workflow"
META_TIMESTAMP = "timestamp"

RESERVED_META_KEYS = (
  META_TYPE,
  META_TARGET,
  META_ARCHITECTURE,
  META_CONFIGURATION,
  META_FREQUENCY,
  META_WORKFLOW,
  META_TIMESTAMP,
)

TYPE_FMAX = "fmax_synthesis"
TYPE_CUSTOM_FREQ = "custom_freq_synthesis"
TYPE_WORKFLOW = "workflow"

FORMAT_V2 = "v2"
FORMAT_V1_SYNTH = "v1_synth"
FORMAT_V1_WORKFLOW = "v1_workflow"
FORMAT_UNKNOWN = "unknown"

PARAM_DOMAINS_KEY = "Param_Domains"
MAIN_DOMAIN_KEY = hard_settings.main_parameter_domain  # "__main__"
TIMESTAMP_DOMAIN_KEY = "__timestamp__"
MAIN_DOMAIN_META_KEY = "main"

_frequency_label_pattern = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)")


class ResultsFile:
  """Contents of a results file, normalized to v2 records."""

  def __init__(self, path=None, units=None, records=None, schema_detected=FORMAT_UNKNOWN):
    self.path = path
    self.units = units if units is not None else {}
    self.records = records if records is not None else []
    self.schema_detected = schema_detected


######################################
# Format detection
######################################


def detect_format(payload):
  """
  Detect the format of a loaded results payload.

  Returns:
      str: FORMAT_V2, FORMAT_V1_SYNTH, FORMAT_V1_WORKFLOW or FORMAT_UNKNOWN.
  """
  if not isinstance(payload, dict):
    return FORMAT_UNKNOWN
  if isinstance(payload.get("results"), list):
    return FORMAT_V2
  if any(key in payload for key in (TYPE_FMAX, "fmax_results", TYPE_CUSTOM_FREQ)):
    return FORMAT_V1_SYNTH
  if isinstance(payload.get("workflows"), dict):
    return FORMAT_V1_WORKFLOW
  return FORMAT_UNKNOWN


######################################
# Record helpers
######################################


def make_record(meta, metrics):
  """Build a v2 record from a meta dict and a metrics dict."""
  return {"meta": meta, "metrics": metrics}


def record_identity(meta):
  """
  Identity of a record, used to deduplicate/replace records on incremental
  exports. The timestamp and informational ("_"-prefixed) keys are excluded:
  re-running the same job replaces its previous record.
  """
  if not isinstance(meta, dict):
    return tuple()
  return tuple(
    sorted((str(key), str(value)) for key, value in meta.items() if str(key) != META_TIMESTAMP and not str(key).startswith("_"))
  )


def upsert_records(existing, new):
  """
  Merge new records into an existing record list: a new record replaces any
  existing record with the same identity (in place), otherwise it is appended.

  Returns:
      list: The merged record list.
  """
  merged = list(existing) if existing else []
  index_by_identity = {record_identity(record.get("meta", {})): i for i, record in enumerate(merged) if isinstance(record, dict)}
  for record in new:
    if not isinstance(record, dict):
      continue
    identity = record_identity(record.get("meta", {}))
    if identity in index_by_identity:
      merged[index_by_identity[identity]] = record
    else:
      index_by_identity[identity] = len(merged)
      merged.append(record)
  return merged


def flatten_param_domains(param_domains, meta):
  """
  Flatten a v1 Param_Domains dict into a v2 meta dict:
  __main__ -> main, __timestamp__ -> timestamp, other domains kept as-is.
  Reserved keys already present in meta are never overwritten.
  """
  if not isinstance(param_domains, dict):
    return
  for key, value in param_domains.items():
    key = str(key)
    if key == MAIN_DOMAIN_KEY:
      meta.setdefault(MAIN_DOMAIN_META_KEY, value)
    elif key == TIMESTAMP_DOMAIN_KEY:
      meta.setdefault(META_TIMESTAMP, value)
    else:
      meta.setdefault(key, value)


def parse_frequency_label(label):
  """
  Parse a v1 frequency directory label such as "50MHz" into a number.

  Returns:
      int | float | None: The frequency value, or None if not parseable.
  """
  match = _frequency_label_pattern.match(str(label))
  if match is None:
    return None
  value = match.group(1)
  return float(value) if "." in value else int(value)


def parse_domain_segments(name):
  """
  Parse the "+domain/value" segments of a configuration or workflow_full name,
  e.g. "base+voltage/1v2+corner/tt" -> {"voltage": "1v2", "corner": "tt"}.
  The first segment (base name) and segments without "/" are ignored.
  """
  domains = {}
  if not isinstance(name, str):
    return domains
  for segment in name.split("+")[1:]:
    if "/" in segment:
      domain, value = segment.split("/", 1)
      if domain != "":
        domains[domain] = value
  return domains


######################################
# v1 -> v2 conversion
######################################


def records_from_v1_synth(payload):
  """
  Convert a v1 synthesis payload (fmax_synthesis / fmax_results /
  custom_freq_synthesis nested dicts) into v2 records.

  Returns:
      tuple: (units dict, list of records)
  """
  units = payload.get("units") if isinstance(payload.get("units"), dict) else {}
  records = []

  fmax_data = {}
  for key in (TYPE_FMAX, "fmax_results"):
    value = payload.get(key)
    if isinstance(value, dict):
      for target, architectures in value.items():
        fmax_data.setdefault(target, {}).update(architectures if isinstance(architectures, dict) else {})

  for target, architectures in fmax_data.items():
    if not isinstance(architectures, dict):
      continue
    for architecture, configurations in architectures.items():
      if not isinstance(configurations, dict):
        continue
      for configuration, metrics in configurations.items():
        if not isinstance(metrics, dict):
          continue
        records.append(_v1_synth_record(TYPE_FMAX, target, architecture, configuration, None, metrics))

  custom_freq_data = payload.get(TYPE_CUSTOM_FREQ)
  if isinstance(custom_freq_data, dict):
    for target, architectures in custom_freq_data.items():
      if not isinstance(architectures, dict):
        continue
      for architecture, configurations in architectures.items():
        if not isinstance(configurations, dict):
          continue
        for configuration, frequencies in configurations.items():
          if not isinstance(frequencies, dict):
            continue
          for frequency_label, metrics in frequencies.items():
            if not isinstance(metrics, dict):
              continue
            frequency = parse_frequency_label(frequency_label)
            records.append(_v1_synth_record(TYPE_CUSTOM_FREQ, target, architecture, configuration, frequency, metrics))

  return units, records


def _v1_synth_record(result_type, target, architecture, configuration, frequency, metrics):
  meta = {
    META_TYPE: result_type,
    META_TARGET: str(target),
    META_ARCHITECTURE: str(architecture),
    META_CONFIGURATION: str(configuration),
  }
  if frequency is not None:
    meta[META_FREQUENCY] = frequency
  metrics = dict(metrics)
  param_domains = metrics.pop(PARAM_DOMAINS_KEY, None)
  flatten_param_domains(param_domains, meta)
  for domain, value in parse_domain_segments(str(configuration)).items():
    meta.setdefault(domain, value)
  return make_record(meta, metrics)


def records_from_v1_workflow(payload):
  """
  Convert a v1 workflow payload (workflows nested dicts) into v2 records.

  Returns:
      tuple: (units dict, list of records)
  """
  units = payload.get("units") if isinstance(payload.get("units"), dict) else {}
  records = []

  workflows = payload.get("workflows")
  if not isinstance(workflows, dict):
    return units, records

  for workflow, entries in workflows.items():
    if not isinstance(entries, dict):
      continue
    for config_key, entry in entries.items():
      if not isinstance(entry, dict):
        continue
      metrics = entry.get("metrics") if isinstance(entry.get("metrics"), dict) else {}
      workflow_full = entry.get("workflow_full", "")
      records.append(
        make_workflow_record(
          workflow=entry.get("workflow_param_dir", workflow),
          workflow_full=workflow_full if isinstance(workflow_full, str) else "",
          fallback_configuration=str(config_key),
          run_dir=entry.get("run_dir"),
          workflow_definition_dir=entry.get("workflow_definition_dir"),
          metrics=metrics,
        )
      )

  return units, records


def make_workflow_record(workflow, workflow_full, fallback_configuration, run_dir, workflow_definition_dir, metrics, timestamp=None):
  """
  Build a v2 workflow record from workflow run information.

  The workflow_full name follows the convention
  "<workflow>[/<config>][+domain/value]...". The configuration meta value is
  rebuilt as "<config>+domain/value+..." (without the workflow name).
  """
  segments = workflow_full.split("+") if isinstance(workflow_full, str) and workflow_full != "" else []
  base = segments[0] if segments else ""
  configuration = base.split("/", 1)[1] if "/" in base else ""
  domain_segments = [segment for segment in segments[1:] if "/" in segment]

  configuration_parts = ([configuration] if configuration != "" else []) + domain_segments
  full_configuration = "+".join(configuration_parts) if configuration_parts else fallback_configuration

  meta = {
    META_TYPE: TYPE_WORKFLOW,
    META_WORKFLOW: str(workflow),
    META_CONFIGURATION: str(full_configuration),
  }
  if timestamp is not None:
    meta[META_TIMESTAMP] = timestamp
  for domain, value in parse_domain_segments(workflow_full).items():
    meta.setdefault(domain, value)
  if run_dir is not None:
    meta["_run_dir"] = str(run_dir)
  if workflow_definition_dir is not None:
    meta["_workflow_definition_dir"] = str(workflow_definition_dir)
  if isinstance(workflow_full, str) and workflow_full != "":
    meta["_workflow_full"] = workflow_full
  return make_record(meta, metrics)


######################################
# Load / dump
######################################


def normalize_v2_records(raw_records):
  """
  Normalize a raw v2 record list: keep only dict items holding a meta dict and
  a metrics dict; ignore any other key (tolerates drafts with numbered items).
  """
  records = []
  for item in raw_records:
    if not isinstance(item, dict):
      continue
    meta = item.get("meta")
    metrics = item.get("metrics")
    if not isinstance(meta, dict):
      continue
    meta = dict(meta)
    flatten_param_domains(meta.pop(PARAM_DOMAINS_KEY, None), meta)
    records.append(make_record(meta, dict(metrics) if isinstance(metrics, dict) else {}))
  return records


def load_results_payload(payload, path=None):
  """
  Normalize an already-loaded results payload (any supported format) into a
  ResultsFile of v2 records.
  """
  detected = detect_format(payload)
  if detected == FORMAT_V2:
    units = payload.get("units") if isinstance(payload.get("units"), dict) else {}
    records = normalize_v2_records(payload.get("results", []))
  elif detected == FORMAT_V1_SYNTH:
    units, records = records_from_v1_synth(payload)
  elif detected == FORMAT_V1_WORKFLOW:
    units, records = records_from_v1_workflow(payload)
  else:
    units, records = {}, []
  return ResultsFile(path=path, units=units, records=records, schema_detected=detected)


def load_results_file(path):
  """
  Load a results file of any supported format.

  Returns:
      ResultsFile: units + records normalized to v2.

  Raises:
      OSError: If the file cannot be read.
      yaml.YAMLError: If the file is not valid YAML.
  """
  with open(path, "r") as file:
    payload = yaml.safe_load(file)
  return load_results_payload(payload, path=path)


def dump_results_file(path, units, records):
  """
  Write a v2 results file.

  Raises:
      OSError: If the file cannot be written.
  """
  directory = os.path.dirname(path)
  if directory != "":
    os.makedirs(directory, exist_ok=True)
  with open(path, "w") as file:
    yaml.dump(
      {"schema": SCHEMA_VERSION, "units": units if units else {}, "results": records if records else []},
      file,
      default_style=None,
      default_flow_style=False,
      sort_keys=False,
    )
