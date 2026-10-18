"""Contract tests for the high-level synthesis, simulation and workflow runners."""

import os
import shutil
from types import SimpleNamespace

import pytest

import odatix.components.run_fmax_synthesis as fmax
import odatix.components.run_simulations as simulations
import odatix.components.run_workflow as workflows

INIT_DIR = os.path.join(os.path.dirname(__file__), "..", "sources", "odatix_init")


@pytest.fixture(autouse=True)
def _in_a_workspace(tmp_path, monkeypatch):
    """The runners open the current directory as a workspace: give them one."""
    shutil.copy(os.path.join(INIT_DIR, "odatix.yml"), str(tmp_path / "odatix.yml"))
    monkeypatch.chdir(tmp_path)


def test_fmax_runner_prepares_then_starts_the_same_job_handler(monkeypatch):
    handler = object()
    captured = {}

    monkeypatch.setattr(
        fmax,
        "check_settings",
        lambda **kwargs: (["arch"], "prepare", [], "tool.yml", "arch-handler", True, 42, 3, "plan"),
    )

    def fake_prepare(**kwargs):
        captured["prepare"] = kwargs
        return handler

    monkeypatch.setattr(fmax, "prepare_synthesis", fake_prepare)
    monkeypatch.setattr(fmax, "start_parallel_jobs", lambda jobs, **kwargs: captured.update(start=(jobs, kwargs)))

    fmax.run_synthesis(
        "run.yml", "architectures", "vivado", "standard", None, None, "work", "targets",
        False, True, False, None, "auto", False, True,
        export_output_dir="results",
        custom_metrics_file="metrics.yml", detach=True, daemon_session="nightly",
    )

    assert captured["prepare"]["architecture_instances"] == ["arch"]
    assert captured["prepare"]["export_output_dir"] == "results"
    assert "use_benchmark" not in captured["prepare"]
    assert captured["start"] == (handler, {"detach": True, "session": "nightly", "configure": True})


def test_simulation_runner_prepares_then_starts_the_same_job_handler(monkeypatch):
    handler = object()
    captured = {}
    monkeypatch.setattr(simulations, "check_settings", lambda **kwargs: (["sim"], "prepare", [], True, 12, 2, "plan"))

    def fake_prepare(**kwargs):
        captured["prepare"] = kwargs
        return handler

    monkeypatch.setattr(simulations, "prepare_simulations", fake_prepare)
    monkeypatch.setattr(simulations, "start_parallel_jobs", lambda jobs, **kwargs: captured.update(start=(jobs, kwargs)))

    simulations.run_simulations(
        "sim.yml", "architectures", "simulations", "work", False, True, False, None, "auto",
        output_dir="results", output_filename="sim.yml", detach=True, daemon_session="nightly",
    )

    assert captured["prepare"]["simulation_instances"] == ["sim"]
    assert captured["prepare"]["export_sim_path"] == "simulations"
    assert captured["start"] == (handler, {"detach": True, "session": "nightly", "configure": True})


def test_workflow_runner_prepares_then_starts_the_same_job_handler(monkeypatch):
    handler = object()
    captured = {}
    monkeypatch.setattr(
        workflows,
        "check_settings",
        lambda **kwargs: (["workflow"], "prepare", [], True, 12, 2, "plan"),
    )

    def fake_prepare(**kwargs):
        captured["prepare"] = kwargs
        return handler

    monkeypatch.setattr(workflows, "prepare_workflows", fake_prepare)
    monkeypatch.setattr(workflows, "start_parallel_jobs", lambda jobs, **kwargs: captured.update(start=(jobs, kwargs)))

    workflows.run_workflows(
        "workflow.yml", "workflows", "work", False, True, False, None, "auto",
        output_dir="results", output_filename="workflow.yml", detach=True, daemon_session="nightly",
    )

    assert captured["prepare"]["workflow_instances"] == ["workflow"]
    assert captured["prepare"]["export_workflow_path"] == "workflows"
    assert captured["start"] == (handler, {"detach": True, "session": "nightly", "configure": True})


def test_prepare_simulations_configures_per_job_and_batch_exports(monkeypatch):
    jobs = []
    captured = {}

    class FakeHandler:
        def __init__(self, **kwargs):
            self.job_list = kwargs["job_list"]
            captured["handler"] = kwargs

    def fake_loop(instances, build_job, job_list):
        build_job(instances[0])

    def prepare(instance, resume=False):
        jobs.append(SimpleNamespace(tmp_dir="work/simulation"))

    monkeypatch.setattr(simulations, "run_prepare_loop", fake_loop)
    monkeypatch.setattr(simulations, "ParallelJobHandler", FakeHandler)
    monkeypatch.setattr(simulations.exp_sim_res, "configure_simulation_job_exports", lambda **kwargs: captured.update(single=kwargs))
    monkeypatch.setattr(simulations.exp_derived, "configure_post_batch_derivation", lambda *args: captured.update(batch=args))

    result = simulations.prepare_simulations(
        ["simulation"], prepare, jobs, True, 100, 4,
        export_output_dir="results", export_work_root="work", export_sim_path="simulations",
    )

    assert result.job_list == jobs
    assert captured["handler"]["auto_exit"] is True
    assert captured["single"]["parallel_jobs"] is result
    assert captured["batch"] == (result, "results")