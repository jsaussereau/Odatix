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

import os
import sys
import yaml
import argparse

import odatix.lib.printc as printc
import odatix.lib.results_schema as results_schema
from odatix.lib.settings import OdatixSettings
from odatix.components.export_common import (
    parse_regex,
    parse_regex_all,
    parse_csv,
    parse_csv_all,
    parse_yaml,
    parse_json,
    convert_to_numeric,
    calculate_operation,
    load_existing_results_file,
)

script_name = os.path.basename(__file__)

WORKFLOW_META_FILENAME = "workflow_meta.yml"
WORKFLOW_METRICS_FILENAME = "_metrics.yml"
DEFAULT_OUTPUT_FILENAME = "results_workflow.yml"


def add_arguments(parser):
    parser.add_argument("-w", "--work", help="workflow work directory")
    parser.add_argument("-r", "--respath", help="result path")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_FILENAME, help="output yaml filename (default: " + DEFAULT_OUTPUT_FILENAME + ")")
    parser.add_argument(
        "-c",
        "--config",
        default=OdatixSettings.DEFAULT_SETTINGS_FILE,
        help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
    )


def parse_arguments():
    parser = argparse.ArgumentParser(description="Export workflow results")
    add_arguments(parser)
    return parser.parse_args()


def _load_metrics(metrics_file):
    """
    Load a workflow metrics definition file.

    Returns:
        tuple: (metrics, metadata), or (None, None) on a hard error.
            - metrics:  metric name -> definition, extracted into record["metrics"]
            - metadata: dimension name -> definition, extracted into record["meta"]

    "metadata" is an optional sibling mapping of "metrics" that describes extra
    meta dimensions (e.g. an EBNO sweep column). Combined with a "multiple: true"
    field, it lets a single run expand into several records that differ only by
    those metadata values -- as if the same configuration had been run several
    times. It is only honored when metrics live under an explicit "metrics" key.
    """
    if not os.path.isfile(metrics_file):
        return None, None
    with open(metrics_file, "r") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            printc.error('Could not parse metrics file "' + metrics_file + '": ' + str(e), script_name)
            return None, None
    if data is None:
        return {}, {}
    if not isinstance(data, dict):
        printc.error('Metrics file "' + metrics_file + '" must contain a YAML mapping at top level', script_name)
        return None, None

    # Workflow metrics can be defined directly at top level or under a
    # dedicated "metrics" key (same style as synthesis metrics files).
    if "metrics" in data:
        metrics = data.get("metrics")
        metadata = data.get("metadata", {})
    else:
        metrics = data
        metadata = {}

    if metrics is None:
        metrics = {}
    if not isinstance(metrics, dict):
        printc.error('Key "metrics" in "' + metrics_file + '" must be a YAML mapping', script_name)
        return None, None

    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        printc.error('Key "metadata" in "' + metrics_file + '" must be a YAML mapping', script_name)
        return None, None

    return metrics, metadata


def _finalize_value(value, content, numeric):
    """
    Apply an optional "format" to an extracted value. When no format is given
    and numeric is True, convert numeric-looking strings to int/float.
    """
    if value is None:
        return None
    if "format" in content:
        try:
            return convert_to_numeric(content["format"] % float(value))
        except Exception:
            return value
    if numeric:
        return convert_to_numeric(value)
    return value


def _extract_direct_value(run_dir, name, content, error_prefix=""):
    """
    Extract a single non-"operation" field from a run directory.

    Returns a scalar, or a list of values when the field is "multiple: true".
    Returns None when the field is not extractable.
    """
    metric_type = content.get("type")
    settings = content.get("settings", {})
    error_if_missing = bool(content.get("error_if_missing", True))
    multiple = bool(content.get("multiple", False))

    if metric_type == "regex":
        file = settings.get("file")
        pattern = settings.get("pattern")
        group_id = settings.get("group_id")
        if file is None or pattern is None or group_id is None:
            return None
        path = os.path.join(run_dir, file)
        if multiple:
            return parse_regex_all(path, pattern, int(group_id), error_if_missing, error_prefix)
        return parse_regex(path, pattern, int(group_id), error_if_missing, error_prefix)

    if metric_type == "csv":
        file = settings.get("file")
        key = settings.get("key")
        if file is None or key is None:
            return None
        path = os.path.join(run_dir, file)
        if multiple:
            return parse_csv_all(path, key, error_if_missing, error_prefix)
        return parse_csv(path, key, error_if_missing, error_prefix)

    if metric_type == "yaml":
        file = settings.get("file")
        key = settings.get("key", None)
        if file is None:
            return None
        return parse_yaml(os.path.join(run_dir, file), key, error_if_missing, error_prefix)

    if metric_type == "json":
        file = settings.get("file")
        key = settings.get("key", None)
        if file is None:
            return None
        return parse_json(os.path.join(run_dir, file), key, error_if_missing, error_prefix)

    return None


def _extract_run_records(run_dir, metrics_def, metadata_def=None, error_prefix=""):
    """
    Extract the metrics (and optional metadata dimensions) for a single run.

    A field marked "multiple: true" is extracted as a list of values; when any
    field is multiple, the run is expanded into one record per row (aligned by
    index). Scalar fields are broadcast to every row, and "operation" metrics
    are evaluated per row from the other fields' row values.

    Returns:
        tuple: (records, units) where records is a list of (meta_extra, metrics)
        tuples -- a single tuple normally, one per expanded row otherwise.
    """
    metadata_def = metadata_def or {}
    units = {}

    # Phase A: extract every direct (non-operation) field exactly once.
    direct = {}   # name -> scalar, or list when the field is "multiple"
    is_list = {}  # name -> whether the field expands the run into rows
    role = {}     # name -> "meta" or "metric"
    op_fields = []  # (name, content, role) evaluated per row in phase C

    def register(name, content, field_role):
        if not isinstance(content, dict):
            return
        if field_role == "metric" and "unit" in content:
            units[name] = content["unit"]

        metric_type = content.get("type")
        if metric_type == "operation":
            op_fields.append((name, content, field_role))
            return
        if metric_type not in ("regex", "csv", "yaml", "json"):
            printc.warning('Unsupported workflow metric type "' + str(metric_type) + '" for metric "' + name + '"', script_name)
            direct[name] = None
            is_list[name] = False
            role[name] = field_role
            return

        multiple = bool(content.get("multiple", False))
        raw = _extract_direct_value(run_dir, name, content, error_prefix)

        if multiple:
            if raw is None:
                values = []
            elif isinstance(raw, list):
                values = raw
            else:
                values = [raw]
            direct[name] = [_finalize_value(v, content, numeric=True) for v in values]
            is_list[name] = True
        else:
            direct[name] = _finalize_value(raw, content, numeric=(field_role == "meta"))
            is_list[name] = False
        role[name] = field_role

    for name, content in metrics_def.items():
        register(name, content, "metric")
    for name, content in metadata_def.items():
        register(name, content, "meta")

    # Phase B: number of expanded rows, taken from the "multiple" fields.
    lengths = [len(direct[name]) for name in direct if is_list[name]]
    if not lengths:
        n_rows = 1
    else:
        n_rows = min(lengths)
        if any(length != n_rows for length in lengths):
            printc.warning(
                error_prefix + "Multiple metrics have mismatched lengths "
                + str(sorted(set(lengths))) + "; aligning on the shortest (" + str(n_rows) + ")",
                script_name,
            )

    # Phase C: build one (meta_extra, metrics) record per row.
    records = []
    for i in range(n_rows):
        meta_extra = {}
        metrics = {}
        row_values = {}
        for name in direct:
            value = direct[name][i] if is_list[name] else direct[name]
            row_values[name] = value
            (meta_extra if role[name] == "meta" else metrics)[name] = value
        for name, content, field_role in op_fields:
            op = content.get("settings", {}).get("op")
            error_if_missing = bool(content.get("error_if_missing", True))
            value = calculate_operation(op, row_values, error_if_missing, error_prefix) if op is not None else None
            value = _finalize_value(value, content, numeric=(field_role == "meta"))
            row_values[name] = value
            (meta_extra if field_role == "meta" else metrics)[name] = value
        records.append((meta_extra, metrics))

    return records, units


def _build_workflow_records(run_records, *, workflow_param_dir, workflow_full, fallback_configuration, run_dir, workflow_definition_dir):
    """Turn (meta_extra, metrics) tuples into v2 workflow records."""
    built = []
    for meta_extra, metrics in run_records:
        record = results_schema.make_workflow_record(
            workflow=workflow_param_dir,
            workflow_full=workflow_full,
            fallback_configuration=fallback_configuration,
            run_dir=run_dir,
            workflow_definition_dir=workflow_definition_dir,
            metrics=metrics,
        )
        for key, value in meta_extra.items():
            # setdefault protects the reserved workflow meta keys (type, workflow, ...)
            record["meta"].setdefault(str(key), value)
        built.append(record)
    return built


def _discover_runs(work_root):
    runs = []
    if not os.path.isdir(work_root):
        return runs

    for workflow_param_dir in sorted(os.listdir(work_root)):
        workflow_dir = os.path.join(work_root, workflow_param_dir)
        if not os.path.isdir(workflow_dir):
            continue
        for run_name in sorted(os.listdir(workflow_dir)):
            run_dir = os.path.join(workflow_dir, run_name)
            if os.path.isdir(run_dir):
                runs.append((workflow_param_dir, run_name, run_dir))
    return runs


# Backward-compatible alias: the shared loader (odatix.components.export_common)
# handles every supported format version.
_load_existing_workflow_output = load_existing_results_file


def configure_workflow_job_exports(
    parallel_jobs,
    *,
    work_root,
    workflow_path,
    output_dir,
    output_filename=DEFAULT_OUTPUT_FILENAME,
):
    if work_root is None or workflow_path is None or output_dir is None:
        return 0

    work_root = os.path.realpath(str(work_root))
    workflow_path = os.path.realpath(str(workflow_path))
    output_dir = os.path.realpath(str(output_dir))
    output_filename = str(output_filename)

    configured = 0
    for job in list(getattr(parallel_jobs, "job_list", []) or []):
        run_dir = os.path.realpath(str(getattr(job, "tmp_dir", "")))
        if not run_dir:
            continue

        try:
            rel_path = os.path.relpath(run_dir, work_root)
        except Exception:
            continue

        if rel_path.startswith(".."):
            continue

        job.post_run_export = {
            "kind": "workflow",
            "run_dir": run_dir,
            "work_root": work_root,
            "workflow_path": workflow_path,
            "output_dir": output_dir,
            "output_filename": output_filename,
        }
        configured += 1

    return configured


def export_single_workflow_job(job, export_config=None):
    config = export_config if isinstance(export_config, dict) else getattr(job, "post_run_export", None)
    if not isinstance(config, dict):
        printc.error("Missing per-job workflow export configuration", script_name=script_name)
        return False

    run_dir = os.path.realpath(str(config.get("run_dir", getattr(job, "tmp_dir", ""))))
    work_root = os.path.realpath(str(config.get("work_root", "")))
    workflow_path = os.path.realpath(str(config.get("workflow_path", "")))
    output_dir = os.path.realpath(str(config.get("output_dir", "")))
    output_filename = str(config.get("output_filename", DEFAULT_OUTPUT_FILENAME))

    if run_dir == "" or workflow_path == "" or output_dir == "":
        printc.error("Per-job workflow export configuration is incomplete", script_name=script_name)
        return False

    if not os.path.isdir(run_dir):
        printc.error('Workflow run directory "' + run_dir + '" does not exist', script_name=script_name)
        return False

    fallback_param_dir = os.path.basename(os.path.dirname(run_dir))
    fallback_run_name = os.path.basename(run_dir)

    if work_root != "":
        try:
            rel = os.path.relpath(run_dir, work_root)
            parts = [part for part in rel.split(os.sep) if part not in ("", ".")]
            if len(parts) >= 2:
                fallback_param_dir = parts[0]
                fallback_run_name = parts[1]
        except Exception:
            pass

    meta_path = os.path.join(run_dir, WORKFLOW_META_FILENAME)
    meta = parse_yaml(meta_path, error_if_missing=False)
    if not isinstance(meta, dict):
        meta = {}

    workflow_param_dir = meta.get("workflow_param_dir", fallback_param_dir)
    workflow_full = meta.get("workflow_full", workflow_param_dir + "/" + fallback_run_name)

    workflow_definition_dir = meta.get("workflow_definition_dir")
    if workflow_definition_dir is None:
        workflow_definition_dir = os.path.join(workflow_path, workflow_param_dir)

    metrics_file = os.path.join(workflow_definition_dir, WORKFLOW_METRICS_FILENAME)
    metrics_def, metadata_def = _load_metrics(metrics_file)
    if metrics_def is None:
        return False

    run_records, run_units = _extract_run_records(run_dir, metrics_def, metadata_def, error_prefix=workflow_full + " => ")

    new_records = _build_workflow_records(
        run_records,
        workflow_param_dir=workflow_param_dir,
        workflow_full=workflow_full,
        fallback_configuration=fallback_run_name,
        run_dir=run_dir,
        workflow_definition_dir=workflow_definition_dir,
    )

    output_file = os.path.join(output_dir, output_filename)
    units, records = _load_existing_workflow_output(output_file)
    units.update(run_units)
    records = results_schema.upsert_records(records, new_records)

    results_schema.dump_results_file(output_file, units, records)

    printc.say('Workflow results updated in "' + output_file + '"', script_name=script_name)
    return True


def export_workflow_results(work_root, workflow_path, output_dir, output_filename=DEFAULT_OUTPUT_FILENAME):
    all_units = {}
    records = []

    runs = _discover_runs(work_root)
    if len(runs) == 0:
        printc.warning('No workflow run found in "' + work_root + '"', script_name)

    for fallback_param_dir, run_name, run_dir in runs:
        meta_path = os.path.join(run_dir, WORKFLOW_META_FILENAME)
        meta = parse_yaml(meta_path, error_if_missing=False)
        if meta is None:
            meta = {}

        workflow_param_dir = meta.get("workflow_param_dir", fallback_param_dir)
        workflow_full = meta.get("workflow_full", fallback_param_dir + "/" + run_name)

        workflow_definition_dir = meta.get("workflow_definition_dir")
        if workflow_definition_dir is None:
            workflow_definition_dir = os.path.join(workflow_path, workflow_param_dir)

        metrics_file = os.path.join(workflow_definition_dir, WORKFLOW_METRICS_FILENAME)
        metrics_def, metadata_def = _load_metrics(metrics_file)
        if metrics_def is None:
            continue

        error_prefix = workflow_full + " => "
        run_records, run_units = _extract_run_records(run_dir, metrics_def, metadata_def, error_prefix=error_prefix)
        all_units.update(run_units)

        records.extend(
            _build_workflow_records(
                run_records,
                workflow_param_dir=workflow_param_dir,
                workflow_full=workflow_full,
                fallback_configuration=run_name,
                run_dir=run_dir,
                workflow_definition_dir=workflow_definition_dir,
            )
        )

    output_file = os.path.join(output_dir, output_filename)
    results_schema.dump_results_file(output_file, all_units, records)

    printc.say('Workflow results written to "' + output_file + '"', script_name=script_name)


def main(args, settings=None):
    if settings is None:
        settings = OdatixSettings(args.config)
        if not settings.valid and (args.work is None or args.respath is None):
            printc.error("Could not load settings from file \"" + args.config + "\" and -w and/or -r options are not used", script_name=script_name)
            sys.exit(-1)

    if args.work is not None:
        work_root = args.work
    else:
        work_root = os.path.join(str(settings.work_path), str(settings.workflow_work_path))

    if args.respath is not None:
        output_dir = args.respath
    else:
        output_dir = settings.result_path

    if settings.valid:
        workflow_path = settings.workflow_path
    else:
        workflow_path = OdatixSettings.DEFAULT_WORKFLOW_PATH

    export_workflow_results(
        work_root=work_root,
        workflow_path=workflow_path,
        output_dir=output_dir,
        output_filename=args.output,
    )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
