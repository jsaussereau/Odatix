"""
odatix.lib.wsl: running the tools and simulators of the Windows Subsystem for
Linux from Odatix on Windows. Which ones run there (as the workspace chooses),
the paths they are given, and the command line that starts them.

Every test but the last one runs anywhere: the system is simulated. The last
one runs a command in WSL for real, on Windows with WSL only.
"""

import base64
import os
import re
import subprocess
import sys

import pytest

import odatix.lib.eda_tools as eda_tools
import odatix.lib.wsl as wsl
from odatix.lib.settings import OdatixSettings
from odatix.lib.variables import Variables, replace_variables

UNIX_ONLY = {"unix": {"tool_test_command": "mytool -v"}}
BOTH = {"unix": {"tool_test_command": "mytool -v"}, "windows": {"tool_test_command": "mytool.exe -v"}}
WINDOWS_ONLY = {"windows": {"tool_test_command": "mytool.exe -v"}}


@pytest.fixture
def windows(monkeypatch):
    """A Windows with WSL installed, its drives mounted under /mnt/."""
    monkeypatch.setattr(wsl, "is_windows", lambda: True)
    monkeypatch.setattr(wsl, "is_installed", lambda: True)
    monkeypatch.setattr(wsl, "mount_root", lambda: "/mnt/")
    monkeypatch.setattr(wsl, "distribution_name", lambda: "Ubuntu")
    monkeypatch.setattr(OdatixSettings, "wsl_settings", wsl.DEFAULTS)
    return monkeypatch


def set_settings(monkeypatch, **data):
    monkeypatch.setattr(OdatixSettings, "wsl_settings", wsl.read_settings(data))


######################################
# Settings
######################################

class TestSettings:
    def test_the_defaults(self):
        assert wsl.read_settings({}) == ("auto", "", [], [])
        assert wsl.read_settings(None) == wsl.DEFAULTS

    def test_the_settings_of_a_workspace(self):
        data = {"wsl": "Never", "wsl_distribution": " Ubuntu ", "wsl_tools": ["genus", "innovus"], "windows_tools": ["ghdl"]}
        assert wsl.read_settings(data) == ("never", "Ubuntu", ["genus", "innovus"], ["ghdl"])

    def test_a_mode_odatix_does_not_know_is_the_default(self):
        assert wsl.read_settings({"wsl": "sometimes"})[0] == "auto"

    def test_tools_may_be_written_as_a_string(self):
        assert wsl.read_settings({"wsl_tools": "genus, innovus"}).tools == ["genus", "innovus"]

    def test_reading_a_workspace_latches_them(self, tmp_path, monkeypatch):
        from odatix.workspace import Workspace

        monkeypatch.setattr(OdatixSettings, "wsl_settings", wsl.DEFAULTS)
        (tmp_path / "odatix.yml").write_text("wsl: never\nwsl_tools: [genus]\nwindows_tools: [ghdl]\n", encoding="utf-8")
        Workspace.open(str(tmp_path)).paths
        assert wsl.settings() == ("never", "", ["genus"], ["ghdl"])


######################################
# Which tools run in WSL
######################################

class TestWhichTools:
    def test_never_anywhere_but_on_windows(self, monkeypatch):
        monkeypatch.setattr(wsl, "is_windows", lambda: False)
        set_settings(monkeypatch, wsl_tools=["mytool"])
        assert not wsl.runs_in_wsl("mytool", UNIX_ONLY)

    def test_a_tool_without_windows_commands(self, windows):
        assert wsl.runs_in_wsl("mytool", UNIX_ONLY)
        assert not wsl.runs_in_wsl("mytool", BOTH)
        assert not wsl.runs_in_wsl("mytool", WINDOWS_ONLY)

    def test_not_without_wsl(self, windows):
        windows.setattr(wsl, "is_installed", lambda: False)
        assert not wsl.runs_in_wsl("mytool", UNIX_ONLY)

    def test_a_tool_named_runs_there_even_with_windows_commands(self, windows):
        set_settings(windows, wsl_tools=["mytool"])
        assert wsl.runs_in_wsl("mytool", BOTH)
        # It still needs Linux commands
        assert not wsl.runs_in_wsl("mytool", WINDOWS_ONLY)

    def test_a_tool_named_runs_on_windows_even_without_windows_commands(self, windows):
        # Then it says it cannot run on Windows, rather than going to WSL
        set_settings(windows, windows_tools=["mytool"])
        assert not wsl.runs_in_wsl("mytool", UNIX_ONLY)
        assert eda_tools.platform_key("mytool", UNIX_ONLY) == "windows"

    def test_never(self, windows):
        set_settings(windows, wsl="never", wsl_tools=["mytool"])
        assert not wsl.runs_in_wsl("mytool", UNIX_ONLY)
        assert not wsl.runs_in_wsl("mytool", BOTH)

    def test_the_section_of_tool_yml_a_tool_runs(self, windows):
        assert eda_tools.platform_key("mytool", UNIX_ONLY) == "unix"
        assert eda_tools.platform_key("mytool", BOTH) == "windows"
        assert eda_tools.platform_key() == "windows"

    def test_the_flows_of_a_tool_run_in_wsl_are_its_linux_ones(self, windows):
        settings = {"unix": {"tool_test_command": "t", "custom_freq_synthesis_command": "run"}}
        flows = eda_tools.list_flows("mytool", job_type="custom_freq_synthesis", settings=settings)
        assert [flow["commands"]["custom_freq_synthesis_command"] for flow in flows.values()] == ["run"]


class TestWhichSimulations:
    """A simulation is named by its own name or by the template it starts from."""

    def test_a_simulator_installed_on_windows_runs_there(self, windows):
        windows.setattr(wsl.shutil, "which", lambda program: "C:\\tools\\" + program + ".exe")
        windows.setattr(wsl, "which", lambda program: "/usr/bin/" + program)
        assert not wsl.simulation_runs_in_wsl(["TB_mine", "verilator"], "verilator")

    def test_one_installed_in_wsl_only_runs_there(self, windows):
        windows.setattr(wsl.shutil, "which", lambda program: None)
        windows.setattr(wsl, "which", lambda program: "/usr/bin/" + program)
        assert wsl.simulation_runs_in_wsl(["TB_mine", "verilator"], "verilator")

    def test_one_installed_nowhere_stays_on_windows(self, windows):
        # Where its check then says it is missing
        windows.setattr(wsl.shutil, "which", lambda program: None)
        windows.setattr(wsl, "which", lambda program: None)
        assert not wsl.simulation_runs_in_wsl(["TB_mine", "verilator"], "verilator")

    def test_the_workspace_chooses_by_simulation_or_by_template(self, windows):
        windows.setattr(wsl.shutil, "which", lambda program: "C:\\tools\\" + program + ".exe")
        set_settings(windows, wsl_tools=["verilator"])
        assert wsl.simulation_runs_in_wsl(["TB_mine", "verilator"], "verilator")
        set_settings(windows, wsl_tools=["verilator"], windows_tools=["TB_mine"])
        assert not wsl.simulation_runs_in_wsl(["TB_mine", "verilator"], "verilator")

    def test_never(self, windows):
        windows.setattr(wsl.shutil, "which", lambda program: None)
        set_settings(windows, wsl="never", wsl_tools=["TB_mine"])
        assert not wsl.simulation_runs_in_wsl(["TB_mine"], "verilator")

    def test_never_anywhere_but_on_windows(self, monkeypatch):
        monkeypatch.setattr(wsl, "is_windows", lambda: False)
        set_settings(monkeypatch, wsl_tools=["TB_mine"])
        assert not wsl.simulation_runs_in_wsl(["TB_mine"], "verilator")


SIMULATION = """\
architectures:
  - Example_Counter_sv
test_command: [python3, --version]
tasks:
  - name: main
    platforms: [linux]
    commands:
      - '"${python}" sim.py ${work_path}'
  - name: main
    platforms: [win32]
    commands:
      - 'sim.exe ${work_path}'
"""


class TestSimulationJobs:
    def run_jobs(self, example_workspace, monkeypatch, capsys, **settings):
        from odatix.run import Run
        from odatix.workspace import Workspace

        directory = example_workspace / "odatix_userconfig" / "simulations" / "TB_mine"
        directory.mkdir()
        (directory / "_settings.yml").write_text(SIMULATION, encoding="utf-8")
        monkeypatch.setattr(wsl, "which", lambda program: "/usr/bin/" + program)
        monkeypatch.setattr(wsl, "python_problem", lambda: None)
        workspace = Workspace.open()
        workspace.paths
        set_settings(monkeypatch, **settings)
        jobs = Run(workspace, "simulation", simulations=["TB_mine"], architectures=["Example_Counter_sv/08bits"], noask=True).prepare().job_list
        return jobs[0], capsys.readouterr().out

    def test_a_simulation_run_in_wsl(self, windows, example_workspace, capsys):
        job, out = self.run_jobs(example_workspace, windows, capsys, wsl_tools=["TB_mine"])
        command = job.command
        # Its Linux task, with the paths of WSL and its Python, run through wsl.exe...
        task = decoded(command)
        assert task == '"python3" sim.py ' + wsl.linux_path(os.path.realpath(job.directory))
        # ...while marking the job done stays on Windows
        assert command.startswith("(wsl.exe ") and ") && echo done>" in command
        # and the check said where it runs
        assert '"TB_mine" runs in WSL (Ubuntu)' in out

    def test_the_same_simulation_run_on_windows(self, windows, example_workspace, capsys):
        job, out = self.run_jobs(example_workspace, windows, capsys, windows_tools=["TB_mine"])
        # The implementation of its task for this system, as is
        expected = "sim.exe " if sys.platform == "win32" else '"' + sys.executable + '" sim.py '
        assert job.command.startswith("(" + expected) and "wsl.exe" not in job.command
        assert '"TB_mine" runs on Windows' in out

    def test_a_simulator_missing_from_wsl_is_said_so(self, windows, example_workspace, capsys):
        from odatix.run import Run
        from odatix.run.errors import RunError
        from odatix.workspace import Workspace

        directory = example_workspace / "odatix_userconfig" / "simulations" / "TB_mine"
        directory.mkdir()
        (directory / "_settings.yml").write_text(SIMULATION, encoding="utf-8")
        windows.setattr(wsl, "which", lambda program: None)
        workspace = Workspace.open()
        workspace.paths
        set_settings(windows, wsl_tools=["TB_mine"])
        run = Run(workspace, "simulation", simulations=["TB_mine"], architectures=["Example_Counter_sv/08bits"], noask=True)
        with pytest.raises(RunError):
            run.prepare()
        messages = " ".join(str(message) for message in run.reporter.messages)
        assert '"TB_mine" runs "python3", which is not in the PATH in WSL (Ubuntu)' in messages


######################################
# Paths
######################################

class TestPaths:
    @pytest.mark.parametrize("path, expected", [
        ("C:\\Users\\me\\work\\job", "/mnt/c/Users/me/work/job"),
        ("d:/data/rtl", "/mnt/d/data/rtl"),
        ("C:\\", "/mnt/c"),
        ("\\\\wsl.localhost\\Ubuntu\\home\\me\\ws", "/home/me/ws"),
        ("\\\\wsl$\\Ubuntu\\opt\\tools", "/opt/tools"),
        ("/opt/cadence/bin", "/opt/cadence/bin"),
        ("rtl/top.sv", "rtl/top.sv"),
        ("", ""),
    ])
    def test_a_path_of_windows_as_wsl_sees_it(self, windows, path, expected):
        assert wsl.linux_path(path) == expected

    def test_the_variables_of_a_command_run_in_wsl(self, windows):
        variables = Variables(
            work_path="C:\\ws\\work\\job", script_path="C:\\ws\\work\\job\\scripts",
            odatix_eda_tools_path="C:\\odatix\\odatix_eda_tools", tool="mytool", wsl=True,
        )
        command = replace_variables(
            'cd $work_path; "$python" $eda_tools_path/x.py $script_path/run.tcl $tool', variables
        )
        assert command == 'cd /mnt/c/ws/work/job; "python3" /mnt/c/odatix/odatix_eda_tools/x.py /mnt/c/ws/work/job/scripts/run.tcl mytool'

    def test_the_variables_of_a_command_run_here_are_left_alone(self):
        command = replace_variables('"$python" $work_path', Variables(work_path="/ws/job"))
        assert command == '"' + sys.executable + '" /ws/job'


######################################
# Commands
######################################

def decoded(command):
    """The shell command a command line of wsl.exe runs."""
    encoded = re.search(r"echo ([A-Za-z0-9+/=]+) \| base64 -d", command).group(1)
    return base64.b64decode(encoded).decode("utf-8")


class TestCommands:
    def test_the_command_is_handed_over_unchanged(self, windows):
        shell_command = "cd \"/mnt/c/a b\" && echo '$HOME' | tr a-z A-Z; exit 3"
        command = wsl.command(shell_command)
        assert command.startswith("wsl.exe -e bash -lc ")
        assert decoded(command) == shell_command
        # Nothing cmd.exe would act on is outside the quotes
        outside = re.sub(r'"[^"]*"', "", command.replace('\\"', '"'))
        assert not re.search(r"[|&<>^]", outside)

    def test_in_the_distribution_of_the_workspace(self, windows):
        set_settings(windows, wsl_distribution="Ubuntu-24.04")
        # wsl.exe does not take a quoted distribution name
        assert wsl.command("true").startswith("wsl.exe -d Ubuntu-24.04 -e bash -lc ")

    def test_a_job_of_a_tool_run_in_wsl(self, windows):
        from odatix.components.synthesis_common import build_job_command

        variables = Variables(work_path="C:\\ws\\job", log_path="C:\\ws\\job\\log", wsl=True)
        command = build_job_command(["cd $work_path;", "make all"], None, variables)
        assert decoded(command) == "cd /mnt/c/ws/job; make all"

        steps = [
            {"name": "synthesis", "command": ["tool -log $log_path/$first_step.log"], "session": None},
            {"name": "pnr", "command": ["tool pnr"], "session": None},
        ]
        pipeline = build_job_command(None, steps, variables)
        assert [decoded(tasks[0]["command"]) for tasks in pipeline.values()] == [
            "tool -log /mnt/c/ws/job/log/synthesis.log", "tool pnr",
        ]

    def test_a_job_of_a_tool_run_here_is_not_wrapped(self):
        from odatix.components.synthesis_common import build_job_command

        assert build_job_command("make -C $work_path", None, Variables(work_path="/ws/job")) == "make -C /ws/job"


@pytest.mark.skipif(not wsl.is_installed(), reason="needs Windows and WSL")
def test_a_command_runs_in_wsl(monkeypatch):
    """For real: what reaches bash, its exit code, and the directory it runs in."""
    monkeypatch.setattr(OdatixSettings, "wsl_settings", wsl.DEFAULTS)
    probe = subprocess.run(wsl.command("true"), shell=True, timeout=120)
    if probe.returncode != 0:
        pytest.skip("no WSL distribution can be started")
    command = wsl.command("echo \"a  b\" '$HOME' $((1 + 2)); pwd; exit 3")
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, cwd=os.path.expanduser("~"), timeout=120)
    lines = result.stdout.decode("utf-8", "replace").splitlines()
    assert result.returncode == 3
    assert lines[0] == "a  b $HOME 3"
    assert lines[1] == wsl.linux_path(os.path.expanduser("~"))
