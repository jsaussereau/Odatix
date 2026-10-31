"""
Running each job on a single thread: "force_single_thread" is a setting of the
run (its settings file, or the API), and every tool hears it, through the
environment of the job and the settings.tcl of its scripts.
"""

import os
import shutil
import subprocess

import pytest

import odatix.lib.printc as printc
from odatix.lib import single_thread
from odatix.run import Run
from odatix.workspace import Workspace

needs_tclsh = pytest.mark.skipif(shutil.which("tclsh") is None, reason="the dummy tool runs tclsh")

SETTINGS_TCL = os.path.join(
    os.path.dirname(__file__), "..", "sources", "odatix_eda_tools", "_common", "settings.tcl"
)


######################################
# The environment of a job
######################################

class TestCommand:
    def test_a_command_line_sets_the_environment_first(self):
        command = single_thread.wrap_command("cd work; make", windows=False)
        assert command.startswith("export ")
        assert "ODATIX_SINGLE_THREAD=1" in command and "OMP_NUM_THREADS=1" in command
        assert command.endswith("; cd work; make")

    def test_cmd_sets_it_and_hands_it_to_wsl(self):
        command = single_thread.wrap_command("dir", windows=True)
        assert 'set "ODATIX_SINGLE_THREAD=1" & ' in command
        assert 'set "WSLENV=%WSLENV%:' in command
        assert command.endswith(" & dir")

    def test_every_task_of_the_stages_is_wrapped(self):
        stages = {0: [{"name": "a", "command": "one", "steps": ["s"]}], 1: [{"name": "b", "command": "two"}]}
        wrapped = single_thread.wrap_command(stages, windows=False)
        assert [task["command"].split("; ")[-1] for level in (0, 1) for task in wrapped[level]] == ["one", "two"]
        assert all(task["command"].startswith("export ") for level in (0, 1) for task in wrapped[level])
        assert wrapped[0][0]["steps"] == ["s"]
        # what the job was built with is left alone
        assert stages[0][0]["command"] == "one"

    def test_a_job_is_wrapped_once(self):
        class Job(object):
            command = "make"

        job = single_thread.apply(single_thread.apply(Job()))
        assert job.command.count("ODATIX_SINGLE_THREAD=1") == 1


class TestRequested:
    def test_read_from_the_run_settings_file(self, tmp_path):
        path = tmp_path / "synth_settings.yml"
        path.write_text("nb_jobs: 8\nforce_single_thread: Yes\n", encoding="utf-8")
        assert single_thread.requested(str(path))
        path.write_text("nb_jobs: 8\nforce_single_thread: No\n", encoding="utf-8")
        assert not single_thread.requested(str(path))
        path.write_text("nb_jobs: 8\n", encoding="utf-8")
        assert not single_thread.requested(str(path))
        assert not single_thread.requested(str(tmp_path / "missing.yml"))


######################################
# What a run prepares
######################################

def _set_in_file(path, key, value):
    """Set a top level key of a YAML file: in place when it has it, else first."""
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith(key + ":"):
            lines[index] = key + ": " + value
            break
    else:
        lines.insert(0, key + ": " + value)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prepared(**options):
    run = Run(Workspace.open(), "custom_freq_synthesis", tool="dummy",
              architectures=["Example_Counter_sv/08bits"], noask=True, overwrite=True, **options)
    return run.prepare().job_list


def _single_thread_of(job):
    with open(os.path.join(job.tmp_dir, "scripts", "settings.tcl"), encoding="utf-8") as f:
        return [line.split()[-1] for line in f if line.startswith("set single_thread")]


@needs_tclsh
class TestRun:
    def test_off_by_default(self, dummy_workspace):
        jobs = _prepared()
        assert jobs
        assert not any("ODATIX_SINGLE_THREAD" in str(job.command) for job in jobs)
        assert all(_single_thread_of(job) == ["0"] for job in jobs)

    def test_asked_by_the_run_settings_file(self, dummy_workspace):
        _set_in_file(dummy_workspace / "odatix_userconfig" / "synth_settings.yml", "force_single_thread", "Yes")
        jobs = _prepared()
        assert jobs
        assert all(single_thread.environment_prefix() in str(job.command) for job in jobs)
        assert all(_single_thread_of(job) == ["1"] for job in jobs)

    def test_asked_by_the_api(self, dummy_workspace):
        jobs = _prepared(force_single_thread=True)
        assert jobs
        assert all("ODATIX_SINGLE_THREAD=1" in str(job.command) for job in jobs)

    def test_a_target_file_that_still_says_it_is_followed(self, dummy_workspace, monkeypatch):
        _set_in_file(dummy_workspace / "odatix_userconfig" / "targets" / "target_dummy.yml", "force_single_thread", "Yes")
        warnings = []
        monkeypatch.setattr(printc, "warning", lambda message, *a, **k: warnings.append(message))
        jobs = _prepared()
        assert jobs
        assert all(_single_thread_of(job) == ["1"] for job in jobs)
        assert all(str(job.command).count("ODATIX_SINGLE_THREAD=1") == 1 for job in jobs)
        assert any("deprecated" in message and "force_single_thread" in message for message in warnings)


######################################
# What the tools hear
######################################

def _tcl(tmp_path, script, env=None):
    path = tmp_path / "test.tcl"
    path.write_text(script, encoding="utf-8")
    environ = dict(os.environ)
    environ.pop("ODATIX_SINGLE_THREAD", None)
    environ.update(env or {})
    return subprocess.run(["tclsh", str(path)], env=environ, stdout=subprocess.PIPE,
                          universal_newlines=True, check=True).stdout


@pytest.mark.skipif(shutil.which("tclsh") is None, reason="tclsh not installed")
class TestSettingsTcl:
    # Commands of the tools, as tclsh does not have them: each says it ran.
    TOOL_COMMANDS = (
        "proc set_host_options {args} {puts \"ran set_host_options $args\"}\n"
        "proc set_db {args} {puts \"ran set_db $args\"}\n"
    )

    def test_off_unless_asked(self, tmp_path):
        out = _tcl(tmp_path, self.TOOL_COMMANDS + "source {" + SETTINGS_TCL + "}\nputs \"single=$single_thread\"\n")
        assert "single=0" in out
        assert "ran " not in out

    def test_the_environment_asks_it_and_the_tool_is_told(self, tmp_path):
        out = _tcl(
            tmp_path,
            self.TOOL_COMMANDS
            + "source {" + SETTINGS_TCL + "}\nsource {" + SETTINGS_TCL + "}\n"
            + "puts \"single=$single_thread omp=$::env(OMP_NUM_THREADS) cores=$::env(ROUTING_CORES)\"\n",
            env={"ODATIX_SINGLE_THREAD": "1"},
        )
        assert "single=1 omp=1 cores=1" in out
        # once, however many times the settings are sourced
        assert out.count("ran set_host_options -max_cores 1") == 1
        assert out.count("ran set_db max_cpus_per_server 1") == 1


class TestSimulationRunner:
    def test_a_build_takes_one_process(self, monkeypatch):
        from odatix.sim.runner import SimRunner

        class Runner(object):
            info = {"parallel_jobs": 1}
            single_thread = SimRunner.single_thread

        monkeypatch.setenv("ODATIX_SINGLE_THREAD", "1")
        assert SimRunner.build_jobs.fget(Runner()) == 1
        monkeypatch.delenv("ODATIX_SINGLE_THREAD")
        assert not Runner().single_thread
