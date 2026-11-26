"""
Design Compiler releases up to 2013 embed Tcl 8.4, and a design may have no reset:
the shared settings.tcl has to work in both cases.
"""

import os
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from odatix.lib.prepare_work import edit_config_file

SETTINGS_TCL = os.path.join(
    os.path.dirname(__file__), os.pardir, "sources", "odatix_eda_tools", "_common", "settings.tcl"
)

TCLSH = shutil.which("tclsh")
needs_tclsh = pytest.mark.skipif(TCLSH is None, reason="tclsh is not installed")


def _tcl(script, tmp_path):
    path = tmp_path / "script.tcl"
    path.write_text(script, encoding="utf-8")
    result = subprocess.run([TCLSH, str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def _arch(tmp_path, reset_signal):
    job_dir = tmp_path / "job"
    (job_dir / "scripts").mkdir(parents=True)
    return SimpleNamespace(
        tmp_dir=str(job_dir), constraint_files=[], constraint_filename="constraints.sdc",
        top_level_module="top", top_level_filename="top.vhd", clock_signal="clk", reset_signal=reset_signal,
        local_rtl_path="rtl", rtl_path="rtl", arch_path="architectures", lib_name="LIB",
        target_frequency=100, fmax_lower_bound=50, fmax_upper_bound=500,
        continue_on_error=False, force_single_thread=False,
    )


class TestDesignWithoutReset:
    @pytest.mark.parametrize("reset_signal,expected", [("", ""), (None, ""), ("rst_n", "rst_n")])
    def test_the_reset_is_always_written_as_a_value(self, tmp_path, reset_signal, expected):
        arch = _arch(tmp_path, reset_signal)
        config = tmp_path / "job" / "scripts" / "settings.tcl"
        config.write_text("set reset_signal       i_rst\n", encoding="utf-8")
        edit_config_file(arch, str(config))
        written = config.read_text(encoding="utf-8")

        # "set reset_signal" without a value would read the variable instead
        assert written.strip() != "set reset_signal"
        if TCLSH:
            assert _tcl(written + 'puts "<$reset_signal>"\n', tmp_path).strip() == "<" + expected + ">"


@needs_tclsh
class TestTcl84Compatibility:
    """The dict and lassign subset of settings.tcl, against the native commands."""

    SCRIPT = """
        if {[lindex $argv 0] eq "emulated"} {
            rename dict ""
            rename lassign ""
        }
        source {%s}
        set d [dict create a 1 b 2 a 3]
        dict set d c 4
        dict lappend d l x
        dict lappend d l y z
        puts "$d|[dict get $d a]|[dict exists $d b]|[dict exists $d zz]|[dict keys $d]|[dict size $d]"
        set nested [dict create x [dict create y 5]]
        puts "[dict get $nested x y]|[dict exists $nested x y]|[dict exists $nested x z]"
        set seen {}
        dict for {k v} $d {
            if {$k eq "b"} continue
            lappend seen $k=$v
            if {$k eq "c"} break
        }
        puts $seen
        set rest [lassign {1 2 3 4} p q]
        puts "$p $q $rest"
        puts [catch {dict get $d missing} message]|$message
        set ::odatix_flow_parameters [dict create compile compile_ultra compile_options {-retime -x}]
        puts "[odatix_flow_param compile]|[odatix_flow_param compile_options]|[odatix_flow_param missing none]"
    """

    def _run(self, tmp_path, mode):
        path = tmp_path / ("script_" + mode + ".tcl")
        path.write_text(self.SCRIPT % os.path.abspath(SETTINGS_TCL), encoding="utf-8")
        result = subprocess.run([TCLSH, str(path), mode], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    def test_the_emulation_behaves_as_the_native_commands(self, tmp_path):
        native = self._run(tmp_path, "native")
        assert self._run(tmp_path, "emulated") == native
        assert "compile_ultra|-retime -x|none" in native

    def test_the_emulation_is_not_installed_over_native_commands(self, tmp_path):
        path = tmp_path / "script.tcl"
        path.write_text(
            'source {%s}\nputs "[llength [info procs dict]] [llength [info procs lassign]]"\n'
            % os.path.abspath(SETTINGS_TCL),
            encoding="utf-8",
        )
        result = subprocess.run([TCLSH, str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
        assert result.stdout.strip() == "0 0"

    def test_design_compiler_scripts_avoid_tcl_85_syntax(self):
        """{*} and the max()/min() functions of expr cannot be emulated."""
        root = os.path.join(os.path.dirname(SETTINGS_TCL), os.pardir, "design_compiler", "tcl")
        for name in sorted(os.listdir(root)) + ["../../_common/settings.tcl"]:
            if not name.endswith(".tcl"):
                continue
            with open(os.path.join(root, name), encoding="utf-8") as f:
                code = "\n".join(line for line in f if not line.lstrip().startswith("#"))
            for construct in ("{*}", "max(", "min("):
                assert construct not in code, construct + " in " + name
