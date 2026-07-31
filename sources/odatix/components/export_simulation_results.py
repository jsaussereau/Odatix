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
Export the results of simulation runs, exactly like workflow results are
exported (see odatix.components.export_workflow_results).

Each simulation directory holds an optional "_metrics.yml" describing what to
extract from a run directory, with the same "metrics" / "metadata" layout and
the same extraction types (regex, csv, yaml, json, xml, operation) as workflows.
The only difference is what a record is about: a simulation run is identified by
the simulation *and* by the architecture configuration it ran on, so its records
carry both dimensions.
"""

import os
import sys
import argparse

import odatix.lib.printc as printc
import odatix.lib.results_schema as results_schema
import odatix.lib.param_domain as param_domain
import odatix.lib.hard_settings as hard_settings
from odatix.lib.settings import OdatixSettings
from odatix.components.export_common import parse_yaml, load_existing_results_file
from odatix.components.export_workflow_results import _load_metrics, _extract_run_records

script_name = os.path.basename(__file__)

SIMULATION_META_FILENAME = "sim_meta.yml"
SIMULATION_SETTINGS_FILENAME = hard_settings.sim_settings_filename
SIMULATION_METRICS_FILENAME = "_metrics.yml"
DEFAULT_OUTPUT_FILENAME = "results_simulation.yml"


def add_arguments(parser):
    parser.add_argument("-w", "--work", help="simulation work directory")
    parser.add_argument("-s", "--simpath", help="simulation directory")
    parser.add_argument("-r", "--respath", help="result path")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_FILENAME, help="output yaml filename (default: " + DEFAULT_OUTPUT_FILENAME + ")")
    parser.add_argument(
        "-c",
        "--config",
        default=OdatixSettings.DEFAULT_SETTINGS_FILE,
        help="global settings file for Odatix (default: " + OdatixSettings.DEFAULT_SETTINGS_FILE + ")",
    )


def parse_arguments():
    parser = argparse.ArgumentParser(description="Export simulation results")
    add_arguments(parser)
    return parser.parse_args()


def _run_identity(run_dir, work_root, sim_path):
    """
    Resolve which simulation and which architecture configuration produced a run
    directory. The metadata file written by run_simulations is authoritative;
    its fallback is the "<work_root>/<simulation>/<architecture>/<config>"
    directory layout.

    Returns:
        dict: simulation, architecture, configuration, arch_full,
        simulation_definition_dir and invariant_domains.
    """
    fallback = {"simulation": "", "architecture": "", "configuration": os.path.basename(run_dir)}
    try:
        rel = os.path.relpath(run_dir, work_root)
        parts = [part for part in rel.split(os.sep) if part not in ("", ".")]
        if len(parts) >= 3:
            fallback["simulation"], fallback["architecture"], fallback["configuration"] = parts[0], parts[1], parts[2]
    except Exception:
        pass

    meta = parse_yaml(os.path.join(run_dir, SIMULATION_META_FILENAME), error_if_missing=False)
    if not isinstance(meta, dict):
        meta = {}

    simulation = str(meta.get("simulation", fallback["simulation"]))
    architecture = str(meta.get("architecture", fallback["architecture"]))
    configuration = str(meta.get("configuration", fallback["configuration"]))

    arch_full = meta.get("arch_full")
    if not isinstance(arch_full, str) or arch_full == "":
        arch_full = architecture + "/" + configuration if architecture else configuration

    simulation_definition_dir = meta.get("simulation_definition_dir")
    if not isinstance(simulation_definition_dir, str) or simulation_definition_dir == "":
        simulation_definition_dir = os.path.join(sim_path, simulation) if simulation else sim_path

    if "invariant_domains" in meta:
        invariant_domains = param_domain.parse_invariant_domains(meta.get("invariant_domains"))
    else:
        # Work directories produced before invariant domains existed have no such
        # key: read the declaration back from the simulation definition, so that
        # re-exporting an old run gives the same record as running it again.
        invariant_domains = _declared_invariant_domains(simulation_definition_dir)

    return {
        "simulation": simulation,
        "architecture": architecture,
        "configuration": configuration,
        "arch_full": arch_full,
        "simulation_definition_dir": simulation_definition_dir,
        "invariant_domains": sorted(invariant_domains),
    }


def _declared_invariant_domains(simulation_definition_dir):
    """The invariant domains a simulation declares in its settings file."""
    settings_file = os.path.join(str(simulation_definition_dir), SIMULATION_SETTINGS_FILENAME)
    settings_data = parse_yaml(settings_file, error_if_missing=False)
    if not isinstance(settings_data, dict):
        return {}
    return param_domain.parse_invariant_domains(
        settings_data.get(param_domain.INVARIANT_DOMAINS_KEY), settings_file
    )


def _build_simulation_records(run_records, identity, run_dir):
    """Turn (meta_extra, metrics) tuples into v2 simulation records."""
    built = []
    for meta_extra, metrics in run_records:
        record = results_schema.make_simulation_record(
            simulation=identity["simulation"],
            architecture=identity["architecture"],
            configuration=identity["configuration"],
            arch_full=identity["arch_full"],
            run_dir=run_dir,
            simulation_definition_dir=identity["simulation_definition_dir"],
            metrics=metrics,
            invariant_domains=identity["invariant_domains"],
        )
        for key, value in meta_extra.items():
            # setdefault protects the reserved simulation meta keys
            record["meta"].setdefault(str(key), value)
        built.append(record)
    return built


def _extract_records_for_run(run_dir, work_root, sim_path):
    """
    Extract every record a single run directory yields.

    Returns:
        tuple: (records, units), both empty when the simulation defines nothing
        to extract, or (None, None) when its metrics file cannot be read.
    """
    identity = _run_identity(run_dir, work_root, sim_path)

    metrics_file = os.path.join(identity["simulation_definition_dir"], SIMULATION_METRICS_FILENAME)
    if not os.path.isfile(metrics_file):
        # A simulation without a metrics file has nothing to export, which is a
        # normal setup (e.g. a testbench that checks itself through assertions
        # and only has to succeed). That is not an export failure.
        return [], {}

    metrics_def, metadata_def = _load_metrics(metrics_file)
    if metrics_def is None:
        return None, None
    if len(metrics_def) == 0 and len(metadata_def) == 0:
        return [], {}

    error_prefix = identity["simulation"] + " => " + identity["arch_full"] + " => "
    run_records, units = _extract_run_records(run_dir, metrics_def, metadata_def, error_prefix=error_prefix)
    return _build_simulation_records(run_records, identity, run_dir), units


def _discover_runs(work_root):
    """Every "<work_root>/<simulation>/<architecture>/<config>" run directory."""
    runs = []
    if not os.path.isdir(work_root):
        return runs

    for simulation in sorted(os.listdir(work_root)):
        simulation_dir = os.path.join(work_root, simulation)
        if not os.path.isdir(simulation_dir):
            continue
        for architecture in sorted(os.listdir(simulation_dir)):
            architecture_dir = os.path.join(simulation_dir, architecture)
            if not os.path.isdir(architecture_dir):
                continue
            for configuration in sorted(os.listdir(architecture_dir)):
                run_dir = os.path.join(architecture_dir, configuration)
                if os.path.isdir(run_dir):
                    runs.append(run_dir)
    return runs


def configure_simulation_job_exports(
    parallel_jobs,
    *,
    work_root,
    sim_path,
    output_dir,
    output_filename=DEFAULT_OUTPUT_FILENAME,
):
    """
    Tag every job of a run so the job handler exports its result as soon as it
    finishes (au fil de l'eau), instead of waiting for the whole batch.

    Returns:
        int: How many jobs were tagged.
    """
    if work_root is None or sim_path is None or output_dir is None:
        return 0

    work_root = os.path.realpath(str(work_root))
    sim_path = os.path.realpath(str(sim_path))
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
            "kind": "simulation",
            "run_dir": run_dir,
            "work_root": work_root,
            "sim_path": sim_path,
            "output_dir": output_dir,
            "output_filename": output_filename,
        }
        configured += 1

    return configured


def export_single_simulation_job(job, export_config=None):
    config = export_config if isinstance(export_config, dict) else getattr(job, "post_run_export", None)
    if not isinstance(config, dict):
        printc.error("Missing per-job simulation export configuration", script_name=script_name)
        return False

    run_dir = os.path.realpath(str(config.get("run_dir", getattr(job, "tmp_dir", ""))))
    work_root = os.path.realpath(str(config.get("work_root", "")))
    sim_path = os.path.realpath(str(config.get("sim_path", "")))
    output_dir = os.path.realpath(str(config.get("output_dir", "")))
    output_filename = str(config.get("output_filename", DEFAULT_OUTPUT_FILENAME))

    if run_dir == "" or sim_path == "" or output_dir == "":
        printc.error("Per-job simulation export configuration is incomplete", script_name=script_name)
        return False

    if not os.path.isdir(run_dir):
        printc.error('Simulation run directory "' + run_dir + '" does not exist', script_name=script_name)
        return False

    new_records, run_units = _extract_records_for_run(run_dir, work_root, sim_path)
    if new_records is None:
        return False

    if len(new_records) == 0:
        printc.note("This simulation defines no metrics to export", script_name=script_name)
        return True

    output_file = os.path.join(output_dir, output_filename)
    units, records = load_existing_results_file(output_file)
    units.update(run_units)
    records = results_schema.upsert_records(records, new_records)

    results_schema.dump_results_file(output_file, units, records)

    printc.say('Simulation results updated in "' + output_file + '"', script_name=script_name)
    return True


def export_simulation_results(work_root, sim_path, output_dir, output_filename=DEFAULT_OUTPUT_FILENAME):
    all_units = {}
    records = []

    runs = _discover_runs(work_root)
    if len(runs) == 0:
        printc.warning('No simulation run found in "' + work_root + '"', script_name)

    for run_dir in runs:
        run_records, run_units = _extract_records_for_run(run_dir, work_root, sim_path)
        if run_records is None:
            continue
        all_units.update(run_units)
        records.extend(run_records)

    output_file = os.path.join(output_dir, output_filename)
    results_schema.dump_results_file(output_file, all_units, records)

    printc.say('Simulation results written to "' + output_file + '"', script_name=script_name)


def main(args, settings=None):
    if settings is None:
        settings = OdatixSettings(args.config)
        if not settings.valid and (args.work is None or args.respath is None):
            printc.error(
                'Could not load settings from file "' + args.config + '" and -w and/or -r options are not used',
                script_name=script_name,
            )
            sys.exit(-1)

    if args.work is not None:
        work_root = args.work
    else:
        work_root = os.path.join(str(settings.work_path), str(settings.simulation_work_path))

    if args.respath is not None:
        output_dir = args.respath
    else:
        output_dir = settings.result_path

    if args.simpath is not None:
        sim_path = args.simpath
    elif settings.valid:
        sim_path = settings.sim_path
    else:
        sim_path = OdatixSettings.DEFAULT_SIM_PATH

    export_simulation_results(
        work_root=work_root,
        sim_path=sim_path,
        output_dir=output_dir,
        output_filename=args.output,
    )


if __name__ == "__main__":
    args = parse_arguments()
    main(args)
