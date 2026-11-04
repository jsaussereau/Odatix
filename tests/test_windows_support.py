"""
What lets the open source tools of the OSS CAD Suite run from Odatix on Windows
as they do on Linux: the programs Windows finds under another name, the
programs of Windows WSL sees, Verilator built without Perl and make, and the
commands the shell of Windows reads.
"""

import os
import shlex
import subprocess
from types import SimpleNamespace

import pytest

import odatix.lib.programs as programs
import odatix.lib.wsl as wsl
import odatix.sim.verilator as verilator


######################################
# Programs found under another name
######################################

class TestPrograms:
    def found(self, monkeypatch, system, paths):
        monkeypatch.setattr(programs.os, "name", system)
        monkeypatch.setattr(programs.shutil, "which", lambda name: paths.get(name))

    def test_windows_runs_the_binary_of_verilator(self, monkeypatch):
        # OSS CAD Suite: "verilator" is a Perl script, without an extension
        self.found(monkeypatch, "nt", {
            "verilator": "C:\\oss\\bin\\verilator", "verilator_bin": "C:\\oss\\bin\\verilator_bin.EXE",
        })
        assert programs.which("verilator") == "C:\\oss\\bin\\verilator_bin.EXE"

    def test_a_program_windows_can_start_is_kept(self, monkeypatch):
        # MSYS2: verilator.exe
        self.found(monkeypatch, "nt", {
            "verilator": "C:\\msys64\\ucrt64\\bin\\verilator.EXE", "verilator_bin": "C:\\oss\\bin\\verilator_bin.EXE",
        })
        assert programs.which("verilator") == "C:\\msys64\\ucrt64\\bin\\verilator.EXE"

    def test_nothing_changes_anywhere_else(self, monkeypatch):
        self.found(monkeypatch, "posix", {"verilator": "/opt/oss/bin/verilator", "verilator_bin": "/opt/oss/bin/verilator_bin"})
        assert programs.which("verilator") == "/opt/oss/bin/verilator"
        self.found(monkeypatch, "posix", {"verilator_bin": "/opt/oss/bin/verilator_bin"})
        assert programs.which("verilator") is None

    def test_a_program_without_an_alternative(self, monkeypatch):
        self.found(monkeypatch, "nt", {"iverilog": "C:\\oss\\bin\\iverilog.EXE"})
        assert programs.which("iverilog") == "C:\\oss\\bin\\iverilog.EXE"
        assert programs.which("ghdl") is None


######################################
# Programs of Windows, as WSL sees them
######################################

class TestWslPrograms:
    @pytest.fixture
    def asked(self, monkeypatch):
        monkeypatch.setattr(wsl, "_programs", {})
        monkeypatch.setattr(wsl, "mount_root", lambda: "/mnt/")

        def answer(output):
            monkeypatch.setattr(wsl, "_ask", lambda command, timeout=60: output)
        return answer

    def test_a_program_of_windows_is_not_installed_in_wsl(self, asked):
        # The PATH of Windows is appended to that of WSL
        asked("/mnt/c/tools/oss-cad-suite/bin/verilator")
        assert wsl.which("verilator") is None

    def test_the_program_of_wsl_is_found_after_it(self, asked):
        asked("/mnt/c/tools/oss-cad-suite/bin/verilator\n/usr/bin/verilator")
        assert wsl.which("verilator") == "/usr/bin/verilator"

    def test_a_program_of_wsl(self, asked):
        asked("/usr/bin/g++")
        assert wsl.which("g++") == "/usr/bin/g++"

    def test_nothing_found(self, asked):
        asked(None)
        assert wsl.which("ghdl") is None

    @pytest.mark.parametrize("path, expected", [
        ("/mnt/c/tools/x", True),
        ("/mnt/d", True),
        ("/mnt/wsl/x", False),
        ("/usr/bin/x", False),
        ("/home/me/mnt/c/x", False),
    ])
    def test_the_drives_of_windows(self, monkeypatch, path, expected):
        monkeypatch.setattr(wsl, "mount_root", lambda: "/mnt/")
        assert wsl.on_windows_drive(path) is expected


######################################
# Verilator without Perl and make
######################################

CLASSES_MK = """\
# Verilated -*- Makefile -*-
VM_C11 = 1
VM_TIMING = 1
VM_COVERAGE = 0
VM_TRACE = 1
VM_TRACE_FST = 0
VM_TRACE_VCD = 1
VM_CLASSES_FAST += \\
  Vtb \\
  Vtb___024root__0 \\
  Vtb__main \\

VM_CLASSES_SLOW += \\
  Vtb___024root__Slow \\

VM_SUPPORT_FAST += \\
  Vtb__Trace__0 \\

VM_SUPPORT_SLOW += \\
  Vtb__Syms__Slow \\

VM_GLOBAL_FAST += \\
  verilated \\
  verilated_vcd_c \\
  verilated_timing \\

VM_GLOBAL_SLOW += \\

"""

PREFIX_MK = """\
default: odatix_sim
PERL = perl
VERILATOR_ROOT = C:\\\\oss\\\\share\\\\verilator
VM_SC = 0
VM_PREFIX = Vtb
VM_USER_CFLAGS = \\
  -DVL_TIME_CONTEXT \\

VM_USER_LDLIBS = \\

VM_USER_CLASSES = \\

include Vtb_classes.mk
"""


class TestVerilatorBuild:
    @pytest.fixture
    def obj_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "obj_dir").mkdir()
        (tmp_path / "obj_dir" / "Vtb_classes.mk").write_text(CLASSES_MK)
        (tmp_path / "obj_dir" / "Vtb.mk").write_text(PREFIX_MK)
        return tmp_path / "obj_dir"

    def test_the_makefile_is_read_as_lists(self, obj_dir):
        variables = verilator.read_makefile(str(obj_dir / "Vtb_classes.mk"))
        assert variables["VM_CLASSES_FAST"] == ["Vtb", "Vtb___024root__0", "Vtb__main"]
        assert variables["VM_GLOBAL_SLOW"] == []
        assert variables["VM_TRACE"] == ["1"]

    def test_the_build_compiles_every_file_the_makefiles_list(self, obj_dir):
        command = verilator.build_command("g++", "Vtb", "/oss/share/verilator", "odatix_sim")
        include = os.path.join("/oss/share/verilator", "include")
        sources = [part for part in command if part.endswith(".cpp")]
        assert sources == [os.path.join("obj_dir", name + ".cpp") for name in (
            "Vtb", "Vtb___024root__0", "Vtb__main", "Vtb___024root__Slow", "Vtb__Trace__0", "Vtb__Syms__Slow",
        )] + [os.path.join(include, name + ".cpp") for name in ("verilated", "verilated_vcd_c", "verilated_timing")]
        assert command[command.index("-o") + 1] == os.path.join("obj_dir", "odatix_sim")

    def test_the_flags_are_those_of_the_makefiles(self, obj_dir):
        command = verilator.build_command("g++", "Vtb", "/oss/share/verilator", "odatix_sim")
        assert "-DVM_TIMING=1" in command and "-DVM_TRACE=1" in command and "-DVM_TRACE_VCD=1" in command
        assert "-DVM_SC=0" in command and "-DVM_TRACE_SAIF=0" in command
        assert "-DVM_PREFIX_INCLUDE=<Vtb.h>" in command
        assert "-DVL_TIME_CONTEXT" in command
        # Timing needs coroutines, and the runtime of the OSS CAD Suite on the
        # PATH must not be loaded by the simulator
        assert "-fcoroutines" in command and "-static" in command

    def test_clang_needs_no_coroutine_flag(self, obj_dir):
        command = verilator.build_command("C:\\llvm\\bin\\clang++.exe", "Vtb", "/oss/share/verilator", "odatix_sim")
        assert "-fcoroutines" not in command and "-std=gnu++20" in command

    def test_verilator_root_is_found_next_to_the_binary(self, tmp_path, monkeypatch):
        monkeypatch.delenv("VERILATOR_ROOT", raising=False)
        (tmp_path / "share" / "verilator" / "include").mkdir(parents=True)
        (tmp_path / "bin").mkdir()
        binary = str(tmp_path / "bin" / "verilator_bin.exe")
        assert verilator.environment(binary) == {"VERILATOR_ROOT": str(tmp_path / "share" / "verilator")}

    def test_a_verilator_root_already_set_is_kept(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VERILATOR_ROOT", "/somewhere")
        assert verilator.environment(str(tmp_path / "bin" / "verilator_bin.exe")) == {}

    def test_the_compiler_cxx_names_comes_first(self, monkeypatch):
        monkeypatch.setenv("CXX", "my-g++")
        monkeypatch.setattr(verilator.shutil, "which", lambda name: "/opt/" + name if name == "my-g++" else None)
        assert verilator.compiler() == "/opt/my-g++"

    def test_no_compiler_fails_and_says_what_to_install(self, monkeypatch):
        monkeypatch.delenv("CXX", raising=False)
        monkeypatch.setattr(verilator.shutil, "which", lambda name: None)

        class Failed(Exception):
            pass

        def fail(message):
            raise Failed(message)
        sim = SimpleNamespace(fail=fail)
        with pytest.raises(Failed) as failure:
            verilator.build(sim, [])
        assert "C++ compiler" in str(failure.value) and "icarus" in str(failure.value)


######################################
# Commands read by the shell of Windows
######################################

class TestDriverCommand:
    def test_cmd_reads_back_a_path_with_spaces(self, monkeypatch):
        import odatix.dse.driver as driver

        monkeypatch.setattr(driver.os, "name", "nt")
        quoted = driver._quote("C:\\Users\\Jo Doe\\venv\\Scripts\\python.exe")
        # Double quotes, the only ones cmd.exe knows
        assert quoted == '"C:\\Users\\Jo Doe\\venv\\Scripts\\python.exe"'
        assert driver._quote("C:\\venv\\python.exe") == "C:\\venv\\python.exe"

    def test_a_posix_shell_gets_single_quotes(self, monkeypatch):
        import odatix.dse.driver as driver

        monkeypatch.setattr(driver.os, "name", "posix")
        assert driver._quote("/home/jo doe/python") == shlex.quote("/home/jo doe/python")

    @pytest.mark.skipif(os.name != "nt", reason="the shell of Windows")
    def test_the_python_of_odatix_runs_through_cmd(self):
        import sys
        import odatix.dse.driver as driver

        completed = subprocess.run(
            driver._quote(sys.executable) + ' -c "print(42)"', shell=True, stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        assert completed.returncode == 0 and completed.stdout.strip() == "42"


class TestAFailedDriverSaysWhy:
    """
    The exploration that could not start on Windows ended with "0/1 job
    succeeded" and nothing else: the end of its log is what tells why.
    """

    def test_the_end_of_the_log_is_printed_when_there_is_no_summary(self, monkeypatch, capsys):
        import odatix.components.run_common as run_common

        log = ["Run job command", " > 'C:\\python.exe' -m odatix.odatix_main dse --worker",
               "The filename, directory name, or volume label syntax is incorrect."]
        monkeypatch.setattr(run_common, "_job_log_lines", lambda state, job_id, job: log)
        job = SimpleNamespace(summary_marker="What the exploration found", display_name="exploration: x")
        run_common.replay_summaries(SimpleNamespace(job_list=[job]), None, [0])
        out = capsys.readouterr().out
        assert "stopped before its summary" in out and "volume label syntax is incorrect" in out

    def test_a_summary_is_printed_as_before(self, monkeypatch, capsys):
        import odatix.components.run_common as run_common

        log = ["batch 1", "What the exploration found:", "3 designs on the front"]
        monkeypatch.setattr(run_common, "_job_log_lines", lambda state, job_id, job: log)
        job = SimpleNamespace(summary_marker="What the exploration found", display_name="exploration: x")
        run_common.replay_summaries(SimpleNamespace(job_list=[job]), None, [0])
        out = capsys.readouterr().out
        assert "3 designs on the front" in out and "batch 1" not in out and "stopped" not in out


class TestWorkflowPython:
    def test_a_workflow_command_can_name_the_python_of_odatix(self, tmp_path):
        import sys
        from odatix.components.run_workflow import _build_workflow_command_substitutions

        workflow = SimpleNamespace(
            workflow_name="w", workflow_config="w", workflow_full="w", tmp_dir=str(tmp_path),
            workflow_definition_dir="", source_path="", extra_command_substitutions=None,
            command_param_file=None, param_file=None, param_domains=[],
        )
        assert _build_workflow_command_substitutions(workflow)["python"] == sys.executable
