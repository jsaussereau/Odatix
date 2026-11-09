"""
The file list of a design ("filelist" in the settings of its architecture):
what the readers of Odatix take from it -- the Python one (simulations,
yosys_fpga, RTL analyses) and the Tcl one (Design Compiler, Genus, Vivado,
Quartus, LibreLane) -- and how the values of a configuration reach it.
"""

import os
import shutil
import subprocess

import pytest

from odatix.sim import design_info

from conftest import REPO_ROOT

SETTINGS_TCL = os.path.join(REPO_ROOT, "sources", "odatix_eda_tools", "_common", "settings.tcl")

# A core written as many projects are: a file list naming its files from the
# root of the repository through a variable, a nested one for a subsystem, a
# configuration package picked by a variable, and include directories.
TOP_LIST = """\
// The core
+incdir+${REPO_DIR}/include/
-F ${SUB_DIR}/sub.Flist
${REPO_DIR}/include/${TARGET_CFG}_config_pkg.sv  // the configuration
${REPO_DIR}/core/core.sv
+define+FROM_LIST+WIDTH=8
"""
SUB_LIST = """\
+incdir+${SUB_DIR}/inc
${SUB_DIR}/sub.v
"""


@pytest.fixture
def repository(tmp_path):
    """A job directory whose rtl/ holds the repository of the core."""
    rtl = tmp_path / "rtl"
    for path, text in {
        "core/Flist.core": TOP_LIST,
        "core/core.sv": "module core; endmodule\n",
        "include/small_config_pkg.sv": "package config_pkg; endpackage\n",
        "include/big_config_pkg.sv": "package config_pkg; endpackage\n",
        "include/defs.svh": "",
        "vendor/sub/sub.Flist": SUB_LIST,
        "vendor/sub/sub.v": "module sub; endmodule\n",
        "vendor/sub/inc/sub.vh": "",
        # Not in the list: never read
        "core/unused.sv": "module unused; endmodule\n",
    }.items():
        (rtl / path).parent.mkdir(parents=True, exist_ok=True)
        (rtl / path).write_text(text)
    return tmp_path


VARIABLES = {"REPO_DIR": ".", "TARGET_CFG": "small", "SUB_DIR": "${REPO_DIR}/vendor/sub"}


def test_the_file_list_gives_files_includes_and_macros_in_order(repository):
    sources = design_info.collect_sources(
        str(repository), "rtl", filelist="core/Flist.core", variables=VARIABLES, defines={"ASSERT_OFF": None},
    )
    assert sources["order"] == "filelist"
    assert sources["verilog"] == ["rtl/vendor/sub/sub.v"]
    assert sources["sv"] == ["rtl/include/small_config_pkg.sv", "rtl/core/core.sv"]
    assert sources["include_dirs"] == ["rtl/include", "rtl/vendor/sub/inc"]
    assert sources["defines"] == ["ASSERT_OFF", "FROM_LIST", "WIDTH=8"]


def test_a_variable_left_unset_comes_from_the_environment(repository, monkeypatch):
    monkeypatch.setenv("TARGET_CFG", "big")
    variables = dict(VARIABLES)
    del variables["TARGET_CFG"]
    sources = design_info.collect_sources(str(repository), "rtl", filelist="core/Flist.core", variables=variables)
    assert "rtl/include/big_config_pkg.sv" in sources["sv"]


def test_without_a_file_list_the_rtl_directory_is_read(repository):
    sources = design_info.collect_sources(str(repository), "rtl", defines=["A=1"])
    assert sources["order"] == "dependencies"
    assert "rtl/core/unused.sv" in sources["sv"]
    assert sources["defines"] == ["A=1"]


@pytest.mark.parametrize("given, expected", [
    (None, []),
    (["A", "B=2"], ["A", "B=2"]),
    ({"A": None, "B": 2, "C": ""}, ["A", "B=2", "C"]),
    ("A B=2", ["A", "B=2"]),
])
def test_macros_are_written_as_a_list_or_a_mapping(given, expected):
    assert design_info.normalize_defines(given) == expected


def test_the_job_settings_give_the_file_list(repository):
    import yaml

    with open(str(repository / "settings.yml"), "w") as f:
        yaml.safe_dump({"filelist": "core/Flist.core", "filelist_variables": VARIABLES, "defines": ["X"]}, f)
    sources = design_info.job_sources(str(repository))
    assert sources["sv"] == ["rtl/include/small_config_pkg.sv", "rtl/core/core.sv"]
    assert sources["defines"] == ["X", "FROM_LIST", "WIDTH=8"]


def test_the_simulation_file_list_holds_the_macros(repository):
    info = design_info.build_info(
        str(repository), top="core", filelist="core/Flist.core", filelist_variables=VARIABLES, defines=["X"],
    )
    lines = design_info.filelist_lines(info)
    assert "+define+X" in lines and "+define+WIDTH=8" in lines
    assert info["dut"]["filelist"] == "core/Flist.core"
    # A generated RTL is read again with the same list
    design_info.write_info(str(repository), info)
    assert design_info.refresh(str(repository))["sources"]["sv"] == ["rtl/include/small_config_pkg.sv", "rtl/core/core.sv"]


@pytest.mark.skipif(shutil.which("tclsh") is None, reason="tclsh is needed")
def test_the_tcl_reader_reads_the_list_as_the_python_one(repository):
    script = repository / "read.tcl"
    script.write_text(
        "source {" + SETTINGS_TCL + "}\n"
        "set rtl_path rtl\n"
        "set filelist core/Flist.core\n"
        "set filelist_variables [list REPO_DIR . TARGET_CFG small SUB_DIR {${REPO_DIR}/vendor/sub}]\n"
        "set verilog_defines [list ASSERT_OFF]\n"
        "set s [odatix_design_sources]\n"
        "foreach f [dict get $s files] { puts \"file [file tail $f]\" }\n"
        "foreach d [dict get $s incdirs] { puts \"incdir [file tail $d]\" }\n"
        "foreach m [dict get $s defines] { puts \"define $m\" }\n"
    )
    output = subprocess.run(["tclsh", str(script)], cwd=str(repository), stdout=subprocess.PIPE,
                            universal_newlines=True, check=True).stdout.split("\n")
    assert [line for line in output if line] == [
        "file sub.v", "file small_config_pkg.sv", "file core.sv",
        "incdir include", "incdir inc",
        "define FROM_LIST", "define WIDTH=8", "define ASSERT_OFF",
    ]


@pytest.mark.skipif(shutil.which("tclsh") is None, reason="tclsh is needed")
def test_a_file_list_named_but_missing_stops_the_tool(repository):
    script = repository / "read.tcl"
    script.write_text(
        "source {" + SETTINGS_TCL + "}\nset rtl_path rtl\nset filelist missing.f\nodatix_design_sources\n"
    )
    result = subprocess.run(["tclsh", str(script)], cwd=str(repository), stdout=subprocess.PIPE,
                            universal_newlines=True)
    assert result.returncode != 0
    assert "missing.f" in result.stdout


@pytest.mark.skipif(shutil.which("tclsh") is None, reason="tclsh is needed")
def test_a_configuration_value_reaches_the_file_list(dummy_workspace):
    # CVA6 picks its configuration package with TARGET_CFG: a variable of the
    # architecture gives it, one job per value, in the settings of each job.
    import glob

    import yaml

    from odatix.run import Run
    from odatix.workspace import Workspace

    ws = Workspace.open(str(dummy_workspace))
    arch = ws.architectures["Example_Counter_sv"]
    arch.update(filelist_variables={"TARGET_CFG": "${CONFIG}", "ROOT": "."},
                defines=["ASSERT_OFF", "CFG_${CONFIG}"])
    arch.settings.set_variable("CONFIG", "list", {"list": ["small", "big"]})
    arch.save()

    run = Run(Workspace.open(str(dummy_workspace)), "custom_freq_synthesis", tool="dummy",
              architectures=["Example_Counter_sv/08bits + CONFIG/*"], frequencies=[50], quiet=True)
    run.prepare()

    settings = {}
    for path in glob.glob(str(dummy_workspace / "work" / "**" / "settings.yml"), recursive=True):
        with open(path) as f:
            data = yaml.safe_load(f)
        settings[data["filelist_variables"]["TARGET_CFG"]] = (data, os.path.dirname(path))
    assert set(settings) == {"small", "big"}
    data, job_dir = settings["big"]
    assert data["defines"] == ["ASSERT_OFF", "CFG_big"]
    with open(os.path.join(job_dir, "scripts", "settings.tcl")) as f:
        text = f.read()
    assert "set filelist           {}" in text
    assert "set filelist_variables [list {TARGET_CFG} {big} {ROOT} {.}]" in text
    assert "set verilog_defines    [list {ASSERT_OFF} {CFG_big}]" in text
