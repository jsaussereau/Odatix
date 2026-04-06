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
import re
import csv
import sys
import yaml
import argparse

import odatix.lib.printc as printc
from odatix.lib.settings import OdatixSettings

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


def parse_regex(file, pattern, group_id, error_if_missing=True, error_prefix=""):
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, "r") as f:
        try:
            content = f.read()
            match = re.search(pattern, content)
            if match:
                return match.group(group_id)
        except Exception as e:
            printc.error(error_prefix + 'Could not get value from regex "' + pattern + '" in file "' + file + '": ' + str(e), script_name=script_name)
            return None

    if error_if_missing:
        printc.error(error_prefix + 'No match for regex "' + pattern + '" in file "' + file + '"', script_name=script_name)
    return None


def parse_csv(file, key, error_if_missing=True, error_prefix=""):
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, mode="r") as csv_file:
        try:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if key in row:
                    return row[key]
            if error_if_missing:
                printc.error(error_prefix + 'Could not find key "' + key + '" in csv "' + file + '"', script_name=script_name)
        except csv.Error as e:
            printc.error(error_prefix + 'An error occurred while reading csv file "' + file + '": ' + str(e), script_name=script_name)
            return None

    return None


def parse_yaml(file, key=None, error_if_missing=True, error_prefix=""):
    if not os.path.isfile(file):
        if error_if_missing:
            printc.error(error_prefix + 'File "' + file + '" does not exist', script_name)
        return None

    with open(file, "r") as yaml_file:
        try:
            data = yaml.safe_load(yaml_file)
            if key is None:
                return data
            if data is None:
                return None
            if isinstance(data, dict):
                return data.get(key, None)
            return None
        except yaml.YAMLError as e:
            printc.error(f'{error_prefix}Could not parse yaml file "{file}": {str(e)}', script_name=script_name)
            return None


def convert_to_numeric(data):
    if isinstance(data, (int, float)):
        return data
    try:
        if "." in str(data):
            return float(data)
        return int(data)
    except Exception:
        return data


def calculate_operation(op_str, results, error_if_missing=True, error_prefix=""):
    try:
        local_vars = {k: v for k, v in results.items() if v is not None}
        return eval(op_str, {}, local_vars)
    except (NameError, SyntaxError, TypeError, ZeroDivisionError) as e:
        if error_if_missing:
            printc.error(error_prefix + 'Failed to evaluate operation "' + op_str + '": ' + str(e), script_name)
        return None


def _load_metrics(metrics_file):
    if not os.path.isfile(metrics_file):
        return None
    with open(metrics_file, "r") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            printc.error('Could not parse metrics file "' + metrics_file + '": ' + str(e), script_name)
            return None
    if data is None:
        return {}
    if not isinstance(data, dict):
        printc.error('Metrics file "' + metrics_file + '" must contain a YAML mapping at top level', script_name)
        return None

    # Workflow metrics can be defined directly at top level or under a
    # dedicated "metrics" key (same style as synthesis metrics files).
    metrics = data.get("metrics", data)
    if metrics is None:
        return {}
    if not isinstance(metrics, dict):
        printc.error('Key "metrics" in "' + metrics_file + '" must be a YAML mapping', script_name)
        return None
    return metrics


def _extract_run_metrics(run_dir, metrics_def, error_prefix=""):
    results = {}
    units = {}

    for metric, content in metrics_def.items():
        if not isinstance(content, dict):
            continue

        metric_type = content.get("type")
        settings = content.get("settings", {})
        error_if_missing = bool(content.get("error_if_missing", True))

        value = None
        if metric_type == "regex":
            file = settings.get("file")
            pattern = settings.get("pattern")
            group_id = settings.get("group_id")
            if file is not None and pattern is not None and group_id is not None:
                value = parse_regex(os.path.join(run_dir, file), pattern, int(group_id), error_if_missing, error_prefix)
        elif metric_type == "csv":
            file = settings.get("file")
            key = settings.get("key")
            if file is not None and key is not None:
                value = parse_csv(os.path.join(run_dir, file), key, error_if_missing, error_prefix)
        elif metric_type == "yaml":
            file = settings.get("file")
            key = settings.get("key", None)
            if file is not None:
                value = parse_yaml(os.path.join(run_dir, file), key, error_if_missing, error_prefix)
        elif metric_type == "operation":
            op = settings.get("op")
            if op is not None:
                value = calculate_operation(op, results, error_if_missing, error_prefix)
        else:
            printc.warning('Unsupported workflow metric type "' + str(metric_type) + '" for metric "' + metric + '"', script_name)

        if value is not None and "format" in content:
            try:
                value = convert_to_numeric(content["format"] % float(value))
            except Exception:
                pass

        results[metric] = value
        if "unit" in content:
            units[metric] = content["unit"]

    return results, units


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


def export_workflow_results(work_root, workflow_path, output_dir, output_filename=DEFAULT_OUTPUT_FILENAME):
    all_units = {}
    out = {"units": all_units, "workflows": {}}

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
        workflow_config = meta.get("workflow_config", run_name)

        workflow_definition_dir = meta.get("workflow_definition_dir")
        if workflow_definition_dir is None:
            workflow_definition_dir = os.path.join(workflow_path, workflow_param_dir)

        metrics_file = os.path.join(workflow_definition_dir, WORKFLOW_METRICS_FILENAME)
        metrics_def = _load_metrics(metrics_file)
        if metrics_def is None:
            continue

        error_prefix = workflow_full + " => "
        run_metrics, run_units = _extract_run_metrics(run_dir, metrics_def, error_prefix=error_prefix)
        all_units.update(run_units)

        if workflow_param_dir not in out["workflows"]:
            out["workflows"][workflow_param_dir] = {}

        out["workflows"][workflow_param_dir][workflow_config] = {
            "run_dir": run_dir,
            "workflow_param_dir": workflow_param_dir,
            "workflow_definition_dir": workflow_definition_dir,
            "metrics": run_metrics,
        }

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_filename)
    with open(output_file, "w") as f:
        yaml.dump(out, f, default_flow_style=False, sort_keys=False)

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
