"""Tests for odatix.components.export_simulation_results (simulation metric export)."""

import os

import pytest
import yaml

import odatix.components.export_simulation_results as esr
import odatix.lib.results_schema as results_schema


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


METRICS = (
    "metrics:\n"
    "  cycles:\n    type: csv\n    settings: {file: results.csv, key: cycles}\n"
    "  errors:\n    type: csv\n    settings: {file: results.csv, key: errors}\n"
)


@pytest.fixture
def workspace(tmp_path):
    """
    A minimal simulation workspace: one simulation definition holding a metrics
    file, and two finished runs of it under the work directory.
    """
    sim_path = tmp_path / "simulations"
    work_root = tmp_path / "work"

    _write(str(sim_path / "TB_Demo" / "_metrics.yml"), METRICS)

    for config, cycles in (("04bits", 12), ("08bits", 34)):
        run_dir = work_root / "TB_Demo" / "Example_Counter" / config
        _write(str(run_dir / "results.csv"), "cycles,errors\n{},0\n".format(cycles))
        _write(
            str(run_dir / esr.SIMULATION_META_FILENAME),
            yaml.dump(
                {
                    "simulation": "TB_Demo",
                    "simulation_definition_dir": str(sim_path / "TB_Demo"),
                    "architecture": "Example_Counter",
                    "configuration": config,
                    "arch_full": "Example_Counter/" + config,
                }
            ),
        )

    return {
        "sim_path": str(sim_path),
        "work_root": str(work_root),
        "results": str(tmp_path / "results"),
        "run_dir": str(work_root / "TB_Demo" / "Example_Counter" / "04bits"),
    }


######################################
# Run identity
######################################

class TestRunIdentity:
    def test_identity_comes_from_the_metadata_file(self, workspace):
        identity = esr._run_identity(workspace["run_dir"], workspace["work_root"], workspace["sim_path"])
        assert identity["simulation"] == "TB_Demo"
        assert identity["architecture"] == "Example_Counter"
        assert identity["configuration"] == "04bits"
        assert identity["arch_full"] == "Example_Counter/04bits"

    def test_identity_falls_back_to_the_directory_layout(self, tmp_path):
        # No sim_meta.yml: "<work>/<simulation>/<architecture>/<config>" is used.
        run_dir = tmp_path / "work" / "TB_Demo" / "Example_Counter" / "08bits"
        os.makedirs(str(run_dir))
        identity = esr._run_identity(str(run_dir), str(tmp_path / "work"), str(tmp_path / "simulations"))
        assert identity["simulation"] == "TB_Demo"
        assert identity["architecture"] == "Example_Counter"
        assert identity["configuration"] == "08bits"
        assert identity["simulation_definition_dir"].endswith(os.path.join("simulations", "TB_Demo"))


######################################
# Batch export
######################################

class TestExportSimulationResults:
    def test_every_run_becomes_a_record(self, workspace):
        esr.export_simulation_results(
            work_root=workspace["work_root"],
            sim_path=workspace["sim_path"],
            output_dir=workspace["results"],
        )
        output = os.path.join(workspace["results"], esr.DEFAULT_OUTPUT_FILENAME)
        loaded = results_schema.load_results_file(output)

        assert len(loaded.records) == 2
        by_config = {r["meta"]["configuration"]: r for r in loaded.records}
        assert set(by_config) == {"04bits", "08bits"}

        record = by_config["04bits"]
        assert record["meta"]["type"] == results_schema.TYPE_SIMULATION
        assert record["meta"]["simulation"] == "TB_Demo"
        assert record["meta"]["architecture"] == "Example_Counter"
        assert record["metrics"]["cycles"] == "12"

    def test_a_simulation_without_metrics_file_exports_nothing(self, tmp_path):
        run_dir = tmp_path / "work" / "TB_Bare" / "Arch" / "cfg"
        os.makedirs(str(run_dir))
        esr.export_simulation_results(
            work_root=str(tmp_path / "work"),
            sim_path=str(tmp_path / "simulations"),
            output_dir=str(tmp_path / "results"),
        )
        loaded = results_schema.load_results_file(
            os.path.join(str(tmp_path / "results"), esr.DEFAULT_OUTPUT_FILENAME)
        )
        assert loaded.records == []


######################################
# Per-job export (au fil de l'eau)
######################################

class TestSingleJobExport:
    def test_export_single_job_appends_then_replaces(self, workspace):
        config = {
            "kind": "simulation",
            "run_dir": workspace["run_dir"],
            "work_root": workspace["work_root"],
            "sim_path": workspace["sim_path"],
            "output_dir": workspace["results"],
            "output_filename": esr.DEFAULT_OUTPUT_FILENAME,
        }
        assert esr.export_single_simulation_job(job=None, export_config=config) is True

        output = os.path.join(workspace["results"], esr.DEFAULT_OUTPUT_FILENAME)
        assert len(results_schema.load_results_file(output).records) == 1

        # Re-running the same job refines its record instead of adding one.
        _write(os.path.join(workspace["run_dir"], "results.csv"), "cycles,errors\n99,1\n")
        assert esr.export_single_simulation_job(job=None, export_config=config) is True
        records = results_schema.load_results_file(output).records
        assert len(records) == 1
        assert records[0]["metrics"]["cycles"] == "99"

    def test_a_simulation_without_metrics_is_not_an_error(self, tmp_path):
        run_dir = tmp_path / "work" / "TB_Bare" / "Arch" / "cfg"
        os.makedirs(str(run_dir))
        config = {
            "kind": "simulation",
            "run_dir": str(run_dir),
            "work_root": str(tmp_path / "work"),
            "sim_path": str(tmp_path / "simulations"),
            "output_dir": str(tmp_path / "results"),
        }
        assert esr.export_single_simulation_job(job=None, export_config=config) is True
        assert not os.path.exists(os.path.join(str(tmp_path / "results"), esr.DEFAULT_OUTPUT_FILENAME))


######################################
# Job tagging
######################################

class _Job:
    def __init__(self, tmp_dir):
        self.tmp_dir = tmp_dir


class _Handler:
    def __init__(self, jobs):
        self.job_list = jobs


class TestConfigureJobExports:
    def test_only_jobs_inside_the_work_root_are_tagged(self, workspace):
        inside = _Job(workspace["run_dir"])
        outside = _Job(os.path.join(workspace["sim_path"], "elsewhere"))
        handler = _Handler([inside, outside])

        configured = esr.configure_simulation_job_exports(
            parallel_jobs=handler,
            work_root=workspace["work_root"],
            sim_path=workspace["sim_path"],
            output_dir=workspace["results"],
        )
        assert configured == 1
        assert inside.post_run_export["kind"] == "simulation"
        assert not hasattr(outside, "post_run_export")
