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

"""odatix init --detect: odatix.lib.project_detect and odatix.components.init_detect."""

import argparse
import json
import os
import shutil

import pytest

import odatix.lib.project_detect as pd
import odatix.components.init_detect as init_detect


PKG = "package cfg_pkg;\n  parameter int W = 8;\nendpackage\n"
LEAF = "module leaf import cfg_pkg::*; (input logic clk, input logic [W-1:0] d, output logic [W-1:0] q);\n  always_ff @(posedge clk) q <= d;\nendmodule\n"
TOP = (
    "`include \"defs.svh\"\n"
    "module top #(parameter int DEPTH = 4) (input logic clk_i, input logic rst_ni, input logic [7:0] d, output logic [7:0] q);\n"
    "  logic [7:0] r;\n"
    "  always_ff @(posedge clk_i or negedge rst_ni) if (!rst_ni) r <= '0; else r <= d;\n"
    "  leaf u_leaf (.clk(clk_i), .d(r), .q(q));\n"
    "`ifdef USE_EXTRA\n  extra u_extra ();\n`endif\n"
    "endmodule\n"
)
TB = "module tb_top;\n  logic clk;\n  top dut (.clk_i(clk));\n  initial $finish;\nendmodule\n"


def _write(root, files):
    for name, text in files.items():
        path = os.path.join(str(root), name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    _write(root, {
        "rtl/top.sv": TOP,
        "rtl/leaf.sv": LEAF,
        "rtl/pkg/cfg_pkg.sv": PKG,
        "rtl/include/defs.svh": "`define WIDTH 8\n",
        "rtl/unused.sv": "module unused (input a, output b); assign b = a; endmodule\n",
        "tb/tb_top.sv": TB,
    })
    return str(root)


def _rel(detection, paths):
    return [os.path.relpath(p, detection.root).replace(os.sep, "/") for p in paths]


class TestInference:
    def test_hierarchy_order_includes_and_signals(self, project):
        d = pd.detect_project(project, check=False)
        assert d.origin == "inferred from the RTL"
        assert d.top.value == "top"
        files = _rel(d, d.files)
        # only what the top needs, package first, no testbench, nothing unused
        assert files[0] == "rtl/pkg/cfg_pkg.sv"
        assert set(files) == {"rtl/pkg/cfg_pkg.sv", "rtl/leaf.sv", "rtl/top.sv"}
        assert _rel(d, d.include_dirs) == ["rtl/include"]
        assert d.clock.value == "clk_i" and d.reset.value == "rst_ni"
        assert [p.name for p in d.parameters] == ["DEPTH"]
        assert d.optional_macros == ["USE_EXTRA"]

    def test_unknown_module_is_a_black_box(self, project):
        _write(project, {"rtl/top.sv": TOP.replace("leaf u_leaf", "missing_ip u_ip")})
        d = pd.detect_project(project, check=False)
        assert "missing_ip" in d.black_boxes

    def test_vendor_primitives_are_not_black_boxes(self, project):
        _write(project, {"rtl/top.sv": TOP.replace("leaf u_leaf (", "BUFG u_buf (.I(clk_i), .O()); leaf u_leaf (")})
        d = pd.detect_project(project, check=False)
        assert "BUFG" not in d.black_boxes

    def test_given_top(self, project):
        d = pd.detect_project(project, top="leaf", check=False)
        assert d.top.value == "leaf" and d.top.confidence == "given"
        assert _rel(d, d.files) == ["rtl/pkg/cfg_pkg.sv", "rtl/leaf.sv"]

    def test_generic_definition_preferred_over_vendor_one(self, project):
        _write(project, {"rtl/fpga/leaf.sv": LEAF.replace("always_ff", "// fpga\n  always_ff")})
        d = pd.detect_project(project, check=False)
        assert "rtl/leaf.sv" in _rel(d, d.files) and "rtl/fpga/leaf.sv" not in _rel(d, d.files)
        assert "leaf" in d.duplicates


class TestDeclarations:
    def test_filelist_with_unknown_variable(self, project):
        _write(project, {"scripts/top.f": "+incdir+${PROJ_DIR}/rtl/include\n${PROJ_DIR}/rtl/pkg/cfg_pkg.sv\n"
                                           "${PROJ_DIR}/rtl/leaf.sv\n${PROJ_DIR}/rtl/top.sv\n"})
        d = pd.detect_project(project, check=False)
        assert d.origin == "file list (top.f)"
        assert _rel(d, d.files) == ["rtl/pkg/cfg_pkg.sv", "rtl/leaf.sv", "rtl/top.sv"]
        assert _rel(d, d.include_dirs) == ["rtl/include"]
        assert any("PROJ_DIR" in n for n in d.notes)

    def test_bender_targets(self, project):
        _write(project, {"Bender.yml": (
            "package: {name: p}\n"
            "export_include_dirs: [rtl/include]\n"
            "sources:\n"
            "  - rtl/pkg/cfg_pkg.sv\n"
            "  - target: all(fpga, xilinx)\n    files: [rtl/fpga_only.sv]\n"
            "  - target: not(synthesis)\n    files: [tb/tb_top.sv]\n"
            "  - target: not(all(fpga, xilinx))\n    defines: {ASIC: ~}\n    files: [rtl/leaf.sv, rtl/top.sv]\n"
        )})
        d = pd.read_bender(os.path.join(project, "Bender.yml"), project) if not shutil.which("bender") else None
        if d is not None:
            assert _rel(pd.ProjectDetection(project), d.files) == ["rtl/pkg/cfg_pkg.sv", "rtl/leaf.sv", "rtl/top.sv"]
            assert d.defines == ["ASIC"]

    @pytest.mark.parametrize("expression, active", [
        ("all(fpga, xilinx)", False), ("not(all(fpga, xilinx))", True), ("not(synthesis)", False),
        ("any(test, simulation)", False), ("cv64a6_imafdc_sv39", True), ("*", True), ("", True),
    ])
    def test_bender_target_expressions(self, expression, active):
        assert pd.bender_target_active(expression) is active

    def test_fusesoc(self, project):
        _write(project, {"p.core": (
            "CAPI=2:\nname: x:y:p:1\n"
            "filesets:\n"
            "  rtl:\n    files: [rtl/pkg/cfg_pkg.sv, rtl/leaf.sv, rtl/top.sv, rtl/include/defs.svh: {is_include_file: true}]\n"
            "    file_type: systemVerilogSource\n"
            "  tb:\n    files: [tb/tb_top.sv]\n"
            "targets:\n  default:\n    filesets: [rtl, tb]\n    toplevel: tb_top\n"
            "  synth:\n    filesets: [rtl]\n    toplevel: top\n"
        )})
        d = pd.read_fusesoc(os.path.join(project, "p.core"), project)
        assert [os.path.basename(f) for f in d.files] == ["cfg_pkg.sv", "leaf.sv", "top.sv"]
        assert d.top == "top" and [os.path.basename(i) for i in d.include_dirs] == ["include"]

    def test_librelane(self, project):
        _write(project, {"config.json": json.dumps({
            "DESIGN_NAME": "top", "CLOCK_PORT": "clk_i",
            "VERILOG_FILES": ["dir::rtl/pkg/cfg_pkg.sv", "dir::rtl/leaf.sv", "dir::rtl/top.sv"],
            "VERILOG_INCLUDE_DIRS": ["dir::rtl/include"], "VERILOG_DEFINES": ["FAST"],
        })})
        d = pd.detect_project(project, check=False)
        assert d.origin == "LibreLane (config.json)"
        assert d.top.value == "top" and d.top.confidence == "declared" and d.clock.value == "clk_i"
        assert d.defines == ["FAST"]

    def test_quartus(self, project):
        _write(project, {"p.qsf": (
            "set_global_assignment -name TOP_LEVEL_ENTITY top\n"
            "set_global_assignment -name SYSTEMVERILOG_FILE rtl/pkg/cfg_pkg.sv\n"
            "set_global_assignment -name SYSTEMVERILOG_FILE rtl/leaf.sv\n"
            "set_global_assignment -name SYSTEMVERILOG_FILE rtl/top.sv\n"
            "set_global_assignment -name SEARCH_PATH rtl/include\n"
            "set_global_assignment -name VERILOG_MACRO \"FAST=1\"\n"
        )})
        d = pd.read_tcl_script(os.path.join(project, "p.qsf"), project)
        assert d.origin == "Quartus project" and d.top == "top" and d.defines == ["FAST=1"]
        assert len(d.files) == 3

    def test_vivado_script_with_glob(self, project):
        _write(project, {"scripts/build.tcl": (
            "read_verilog -sv [glob ../rtl/pkg/*.sv]\n"
            "read_verilog -sv {../rtl/leaf.sv ../rtl/top.sv}\n"
            "synth_design -top top -part xc7a35t -include_dirs ../rtl/include -verilog_define FAST\n"
        )})
        d = pd.read_tcl_script(os.path.join(project, "scripts", "build.tcl"), project)
        assert d.origin == "Vivado script" and d.top == "top" and d.defines == ["FAST"]
        assert [os.path.basename(f) for f in d.files] == ["cfg_pkg.sv", "leaf.sv", "top.sv"]

    def test_vivado_project(self, project):
        _write(project, {"vivado/p.xpr": (
            '<Project><FileSets><FileSet Name="sources_1" Type="DesignSrcs">'
            '<File Path="$PPRDIR/../rtl/top.sv"/><File Path="$PPRDIR/../rtl/leaf.sv"/>'
            '<Config><Option Name="TopModule" Val="top"/><Option Name="VerilogDefine" Val="FAST"/></Config>'
            '</FileSet></FileSets></Project>'
        )})
        d = pd.read_vivado_project(os.path.join(project, "vivado", "p.xpr"), project)
        assert d.top == "top" and d.defines == ["FAST"] and len(d.files) == 2

    def test_cocotb_makefile(self, project):
        _write(project, {"tb/Makefile": (
            "SIM ?= icarus\nTOPLEVEL_LANG = verilog\n"
            "VERILOG_SOURCES += $(PWD)/../rtl/pkg/cfg_pkg.sv\n"
            "VERILOG_SOURCES += $(PWD)/../rtl/leaf.sv $(PWD)/../rtl/top.sv\n"
            "COMPILE_ARGS += +incdir+../rtl/include\nTOPLEVEL = top\n"
        )})
        d = pd.read_makefile(os.path.join(project, "tb", "Makefile"), project)
        assert d.top == "top" and len(d.files) == 3 and [os.path.basename(i) for i in d.include_dirs] == ["include"]

    def test_declared_list_is_completed_and_variants_kept_apart(self, project):
        _write(project, {
            "rtl/pkg/cfg_big_pkg.sv": PKG.replace("8", "64"),
            "top.f": "rtl/pkg/cfg_pkg.sv\nrtl/pkg/cfg_big_pkg.sv\nrtl/top.sv\n",
        })
        d = pd.detect_project(project, check=False)
        files = _rel(d, d.files)
        assert "rtl/leaf.sv" in files  # instantiated by a listed file
        assert "rtl/pkg/cfg_big_pkg.sv" not in files and "cfg_pkg" in d.variants


@pytest.mark.skipif(not shutil.which("slang") and not shutil.which("verilator"), reason="no elaborating tool")
class TestValidation:
    def test_elaborates(self, project):
        d = pd.detect_project(project)
        assert d.validation.ok is True, d.validation.errors

    def test_missing_include_dir_is_fixed(self, project):
        _write(project, {"top.f": "rtl/pkg/cfg_pkg.sv\nrtl/leaf.sv\nrtl/top.sv\n"})
        d = pd.detect_project(project)
        assert d.validation.ok is True, d.validation.errors
        assert "rtl/include" in _rel(d, d.include_dirs)


def _args(path, **kwargs):
    values = dict(detect=path, top=None, name=None, parameters=False, dry_run=False, no_check=True, json=False, noask=True, generate=None, no_generate=False)
    values.update(kwargs)
    return argparse.Namespace(**values)


class TestCommand:
    def test_layout_next_to_the_project(self, project, tmp_path):
        d = pd.detect_project(project, check=False)
        rtl_dir, project_dir = init_detect.rtl_layout(d, str(tmp_path / "ws"))
        assert rtl_dir == os.path.join(project, "rtl") and project_dir is None

    def test_layout_with_the_workspace_inside_the_project(self, project):
        d = pd.detect_project(project, check=False)
        d.files.append(os.path.join(project, "other", "x.sv"))
        rtl_dir, project_dir = init_detect.rtl_layout(d, project)
        assert rtl_dir == os.path.join(project, "rtl") and project_dir == project
        text = init_detect.filelist_text(d, rtl_dir, project_dir)
        assert "${ODATIX_PROJECT_DIR}/other/x.sv" in text and "\ntop.sv\n" in text

    def test_layout_refused_when_the_rtl_holds_the_workspace(self, project):
        d = pd.detect_project(project, check=False)
        with pytest.raises(ValueError):
            init_detect.rtl_layout(d, os.path.join(project, "rtl"))

    def test_dry_run_writes_nothing(self, project, tmp_path, monkeypatch):
        monkeypatch.chdir(str(tmp_path))
        assert init_detect.run(_args(project, dry_run=True))
        assert not os.path.exists(os.path.join(project, "rtl", init_detect.FILELIST_NAME))
        assert not os.path.exists(str(tmp_path / "odatix.yml"))

    def test_writes_the_architecture(self, project, tmp_path, monkeypatch):
        workspace = tmp_path / "ws"
        workspace.mkdir()
        monkeypatch.chdir(str(workspace))
        assert init_detect.run(_args(project, name="mine", parameters=True))
        import odatix.workspace as api
        ws = api.open_workspace(str(workspace), required=True)
        settings = ws.architectures["mine"].settings
        assert settings.top_level_module == "top" and settings.clock_signal == "clk_i"
        assert settings.filelist == init_detect.FILELIST_NAME
        assert os.path.normpath(os.path.join(str(workspace), settings.rtl_path)) == os.path.join(project, "rtl")
        with open(os.path.join(project, "rtl", init_detect.FILELIST_NAME)) as f:
            lines = [l for l in f.read().splitlines() if not l.startswith("#")]
        assert lines == ["+incdir+include", "pkg/cfg_pkg.sv", "leaf.sv", "top.sv"]
        assert "DEPTH" in ws.architectures["mine"].domains.sub_names()
        # a second run does not overwrite the architecture
        assert not init_detect.run(_args(project, name="mine"))

    def test_foreign_filelist_is_never_overwritten(self, project, tmp_path, monkeypatch):
        _write(project, {"rtl/" + init_detect.FILELIST_NAME: "mine\n"})
        monkeypatch.chdir(str(tmp_path))
        assert not init_detect.run(_args(project))


class TestRealProjectQuirks:
    """Cases met on known open-source repositories (serv, cv32e40p, neorv32, picorv32...)."""

    def test_bender_sources_as_a_single_mapping(self, project):
        _write(project, {"Bender.yml": "package: {name: p}\nsources:\n  include_dirs: [rtl/include]\n"
                                       "  files: [rtl/pkg/cfg_pkg.sv, rtl/leaf.sv, rtl/top.sv]\n"})
        d = pd.read_bender(os.path.join(project, "Bender.yml"), project) if not shutil.which("bender") else None
        if d is not None:
            assert len(d.files) == 3 and len(d.include_dirs) == 1

    def test_fusesoc_conditional_toplevel(self, project):
        _write(project, {"p.core": "CAPI=2:\nfilesets:\n  rtl:\n    files: [rtl/top.sv]\n"
                                   "targets:\n  default:\n    filesets: [rtl]\n    toplevel: [\"is_toplevel? (top)\"]\n"})
        assert pd.read_fusesoc(os.path.join(project, "p.core"), project).top == "top"

    def test_filelist_variable_without_braces(self, project):
        _write(project, {"rtl/list.f": "$PROJ_HOME/rtl/pkg/cfg_pkg.sv\n$PROJ_HOME/rtl/leaf.sv\n$PROJ_HOME/rtl/top.sv\n"})
        d = pd.read_filelist(os.path.join(project, "rtl", "list.f"), project)
        assert all(os.path.isfile(f) for f in d.files) and len(d.files) == 3

    def test_generated_filelist_is_not_a_declaration(self, project):
        _write(project, {"rtl/" + init_detect.FILELIST_NAME: pd.GENERATED_FILELIST_MARK + "\nleaf.sv\n"})
        assert pd.detect_project(project, check=False).origin == "inferred from the RTL"

    def test_declaration_named_after_the_project_wins(self, tmp_path):
        root = tmp_path / "core"
        _write(root, {
            "core.v": "module core(input clk, output q); assign q = clk; endmodule\n",
            "core.core": "CAPI=2:\nfilesets:\n  rtl:\n    files: [core.v]\ntargets:\n  default:\n    filesets: [rtl]\n",
            "soc/soc.v": "module soc(input clk, output q); core u (.clk(clk), .q(q)); endmodule\n",
            "soc/a.v": "module a; endmodule\n", "soc/b.v": "module b; endmodule\n",
            "soc/soc.core": "CAPI=2:\nfilesets:\n  rtl:\n    files: [soc.v, a.v, b.v, ../core.v]\n"
                            "targets:\n  default:\n    filesets: [rtl]\n",
        })
        assert pd.detect_project(str(root), check=False).origin == "FuseSoC (core.core)"

    def test_vhdl_named_library(self, tmp_path):
        _write(tmp_path, {"a.vhd": "library ieee;\nlibrary neorv32;\nuse neorv32.pkg.all;\n"})
        assert pd.vhdl_library([str(tmp_path / "a.vhd")]) == "neorv32"
        _write(tmp_path, {"b.vhd": "library ieee; library unisim;\n"})
        assert pd.vhdl_library([str(tmp_path / "b.vhd")]) == "work"


import odatix.lib.rtl_generation as rtl_generation

FAKE_GENERATOR = (
    "mkdir -p gen && printf 'module gen_top(input clock, input reset, output q);\\n"
    "  reg r; always @(posedge clock) r <= reset ? 1'\"'\"'b0 : ~r; assign q = r;\\nendmodule\\n' > gen/gen_top.v"
)


class TestGeneratedRtl:
    def _chisel(self, root, body):
        _write(root, {
            "build.sbt": 'val chiselVersion = "5.1.0"\nlibraryDependencies += "org.chipsalliance" %% "chisel" % chiselVersion\n',
            "project/build.properties": "sbt.version=1.9.7\n",
            "src/main/scala/Top.scala": "package my.core\n" + body,
            "src/test/scala/TopSpec.scala": "object TopSpec extends App { }\n",
        })

    def test_sbt_entry_points(self, tmp_path):
        self._chisel(tmp_path, "object Helper extends App { println(1) }\n"
                               "object TopGen extends App { ChiselStage.emitSystemVerilog(new Top) }\n")
        g = rtl_generation.detect(str(tmp_path))
        assert g.name == "Chisel" and g.whitelist == ["build.sbt", "project", "src"]
        assert g.command == "sbt 'runMain my.core.TopGen'"
        assert all("TopSpec" not in c for c in [g.command] + g.entries)

    def test_readme_command_first(self, tmp_path):
        self._chisel(tmp_path, "object TopGen extends App { ChiselStage.emitSystemVerilog(new Top) }\n"
                               "object Small extends App { ChiselStage.emitSystemVerilog(new Top) }\n")
        _write(tmp_path, {"README.md": 'Run `sbt "runMain my.core.Small"` to get the Verilog.\n'})
        assert rtl_generation.detect(str(tmp_path)).command == "sbt 'runMain my.core.Small'"

    @pytest.mark.parametrize("body, suffix", [
        ("ChiselStage.emitSystemVerilog(new Top, firtoolOpts = Array(\"--split-verilog\") ++ args)", " -o=generated_rtl"),
        ("ChiselStage.emitSystemVerilog(new Top, args)", " --target-dir generated_rtl"),
        ("ChiselStage.emitSystemVerilog(new Top)", ""),
    ])
    def test_output_argument_when_the_main_forwards_its_arguments(self, tmp_path, body, suffix):
        self._chisel(tmp_path, "object TopGen extends App {\n  " + body + "\n}\n")
        assert rtl_generation.detect(str(tmp_path)).command == "sbt 'runMain my.core.TopGen" + suffix + "'"

    def test_amaranth(self, tmp_path):
        _write(tmp_path, {"gen.py": "from amaranth import *\nif __name__ == '__main__':\n    main()\n"})
        g = rtl_generation.detect(str(tmp_path))
        assert g.name == "Amaranth" and g.command == "python3 gen.py"

    def test_hand_written_rtl_has_no_generator(self, project):
        assert rtl_generation.detect(project) is None

    def test_copy_follows_the_lists(self, tmp_path):
        _write(tmp_path / "p", {"src/a.scala": "x", "target/big": "x", "doc/x.md": "x", "build.sbt": "x"})
        rtl_generation.copy_design(str(tmp_path / "p"), str(tmp_path / "c"), ["build.sbt", "src"], ["target"])
        assert sorted(os.listdir(str(tmp_path / "c"))) == ["build.sbt", "src"]

    def _generated(self, tmp_path, command=FAKE_GENERATOR):
        root = tmp_path / "proj"
        _write(root, {"gen.py": "from amaranth import *\n"})
        d = pd.detect_project(str(root))
        assert d.needs_generation
        assert pd.detect_generated(d, command=command) or d.generator.error
        return d

    def test_generation_runs_in_a_copy(self, tmp_path):
        d = self._generated(tmp_path)
        try:
            assert d.generated_dir and d.generator.output == "gen" and d.generator.generated == ["gen/gen_top.v"]
            assert d.top.value == "gen_top" and d.clock.value == "clock" and d.reset.value == "reset"
            assert not os.path.exists(str(tmp_path / "proj" / "gen"))  # the project is left as it was
            assert d.origin == "generated by Amaranth" and not d.needs_generation
        finally:
            rtl_generation.cleanup(d.generator)
        assert not os.path.exists(d.generator.copy or "/nonexistent")

    def test_generation_failure_is_reported(self, tmp_path):
        d = self._generated(tmp_path, command="echo boom >&2; exit 3")
        assert not d.generated_dir and "exit code 3" in d.generator.error and "boom" in d.generator.error

    def test_generation_that_writes_nothing(self, tmp_path):
        d = self._generated(tmp_path, command="true")
        assert "wrote no" in d.generator.error

    def test_generated_architecture(self, tmp_path):
        d = self._generated(tmp_path)
        workspace = tmp_path / "ws"
        workspace.mkdir()
        try:
            settings = init_detect.generated_settings(d, str(workspace))
        finally:
            rtl_generation.cleanup(d.generator)
        assert settings["generate_rtl"] is True and settings["design_path"] == "../proj"
        assert settings["generate_command"] == FAKE_GENERATOR and settings["generate_output"] == "gen"
        assert settings["top_level_file"] == "gen_top.v" and settings["top_level_module"] == "gen_top"

    def test_workspace_inside_the_project_is_not_copied(self, tmp_path):
        d = self._generated(tmp_path)
        try:
            settings = init_detect.generated_settings(d, str(tmp_path / "proj" / "ws"))
        finally:
            rtl_generation.cleanup(d.generator)
        assert "ws" in settings["design_path_blacklist"] and settings["design_path"] == ".."


import odatix.workspace.detect as workspace_detect

GROUPED = (
    "module top #(\n"
    "  parameter WIDTH = 8,   // data width\n"
    "  parameter DEPTH = 16,  // fifo depth\n"
    "  parameter LATENCY = 2, // pipeline\n"
    "  parameter MODE = 0\n"
    ") (input clk, input rst, output [WIDTH-1:0] q);\n"
    "  assign q = '0;\n"
    "endmodule\n"
)


class TestParameterGroups:
    def test_section_delimiters_never_cut_a_word(self):
        text = "aaa\nparameter X = 1,\nparameter Y = 2\nbbb\n"
        start, end = text.index("parameter X"), text.index(",\nparameter Y")
        begin, stop = workspace_detect.section_delimiters(text, start, end)
        assert text.find(begin) + len(begin) == start and text.find(stop, start) == end
        assert not (begin[0].isalnum() and text[text.find(begin) - 1].isalnum())

    def test_group_settings_replace_only_their_lines(self, tmp_path):
        path = tmp_path / "top.sv"
        path.write_text(GROUPED)
        settings = workspace_detect.parameter_group_settings(str(path), ["DEPTH", "WIDTH"])
        template = settings["configurations"]["template"]
        assert template == ("  parameter WIDTH = ${WIDTH},   // data width\n"
                            "  parameter DEPTH = ${DEPTH},  // fifo depth")
        assert settings["configurations"]["name"] == "${WIDTH}_${DEPTH}"
        assert settings["variables"]["DEPTH"]["settings"]["list"] == [16]

    def test_group_keeps_the_values_of_parameters_in_between(self, tmp_path):
        path = tmp_path / "top.sv"
        path.write_text(GROUPED)
        template = workspace_detect.parameter_group_settings(str(path), ["WIDTH", "LATENCY"])["configurations"]["template"]
        assert "DEPTH = 16" in template and "${LATENCY}" in template

    def test_spec_from_names_groups_and_strings(self, project):
        _write(project, {"rtl/top.sv": GROUPED})
        d = pd.detect_project(project, check=False)
        groups, unknown = init_detect.selected_parameters(d, "fifo=WIDTH+DEPTH,MODE,NOPE")
        assert [(g, [p.name for p in ps]) for g, ps in groups] == [("fifo", ["WIDTH", "DEPTH"]), ("MODE", ["MODE"])]
        assert unknown == ["NOPE"]
        groups, _ = init_detect.selected_parameters(d, [{"group": "g", "names": ["LATENCY"]}, "WIDTH"])
        assert [g for g, _ in groups] == ["g", "WIDTH"]
        assert len(init_detect.selected_parameters(d, True)[0]) == 4

    def test_grouped_domain_is_written(self, project, tmp_path, monkeypatch):
        _write(project, {"rtl/top.sv": GROUPED})
        workspace = tmp_path / "ws"
        workspace.mkdir()
        monkeypatch.chdir(str(workspace))
        assert init_detect.run(_args(project, name="g", parameters="fifo=WIDTH+DEPTH,MODE"))
        import odatix.workspace as api
        arch = api.open_workspace(str(workspace), required=True).architectures["g"]
        assert sorted(arch.domains.sub_names()) == ["MODE", "fifo"]


class TestImportDomains:
    def test_spec_and_summary(self):
        import odatix.gui.project_import as gui
        state = {"domains": [
            {"name": "a", "names": ["a"], "auto": True},
            {"name": "cache", "names": ["b", "c"], "auto": False},
            {"name": "renamed", "names": ["d"], "auto": False},
            {"name": "empty", "names": []},
        ]}
        assert gui.domains_spec(state) == ["a", {"group": "cache", "names": ["b", "c"]}, {"group": "renamed", "names": ["d"]}]
        assert gui.domains_summary(state) == "3 parameter domains, 4 parameters explored"
        assert gui.domains_summary({"domains": []}).startswith("No parameter explored")

    def test_initial_domains(self, project):
        import odatix.gui.project_import as gui
        d = pd.detect_project(project, check=False)
        assert gui.initial_domains(d) == {"domains": [{"name": "DEPTH", "names": ["DEPTH"], "auto": True}]}
        d.parameters = d.parameters * 9
        assert gui.initial_domains(d) == {"domains": []}


class TestValues:
    @pytest.mark.parametrize("text, variable", [
        ("", {"type": "list", "settings": {"list": [16]}}),
        ("8, 16;32 64", {"type": "list", "settings": {"list": [8, 16, 32, 64]}}),
        ("8..32", {"type": "range", "settings": {"from": 8, "to": 32, "step": 1}}),
        ("8 .. 32 step 8", {"type": "range", "settings": {"from": 8, "to": 32, "step": 8}}),
        ("8..64 pow2", {"type": "power_of_two", "settings": {"from": 8, "to": 64}}),
        ([1, "a"], {"type": "list", "settings": {"list": [1, "a"]}}),
    ])
    def test_values_variable(self, text, variable):
        assert workspace_detect.values_variable(text, "16") == variable

    @pytest.mark.parametrize("text", ["32..8", "8..32 step 0", "0..8 pow2", "8...32"])
    def test_values_that_are_not(self, text):
        with pytest.raises(ValueError):
            workspace_detect.values_variable(text)

    def test_spec_carries_values_and_errors(self):
        import odatix.gui.project_import as gui
        state = {"domains": [{"name": "a", "names": ["a"], "auto": True}, {"name": "b", "names": ["b"]}],
                 "values": {"a": "1, 2", "b": " ", "z": "3"}}
        spec = gui.domains_spec(state)
        assert spec == [{"group": "a", "names": ["a"], "values": {"a": "1, 2"}}, "b"]
        assert gui.values_errors(spec) == []
        assert gui.values_errors([{"group": "a", "names": ["a"], "values": {"a": "9..1"}}])[0].startswith("a: ")

    def test_values_are_written(self, project, tmp_path, monkeypatch):
        _write(project, {"rtl/top.sv": GROUPED})
        workspace = tmp_path / "ws"
        workspace.mkdir()
        monkeypatch.chdir(str(workspace))
        assert init_detect.run(_args(project, name="seed"))
        import odatix.workspace as api
        ws = api.open_workspace(str(workspace), required=True)
        d = pd.detect_project(str(project), check=False)
        result = init_detect.describe(d, ws, "v", parameters=[
            {"group": "MODE", "names": ["MODE"], "values": {"MODE": "0..3"}},
            {"group": "fifo", "names": ["WIDTH", "DEPTH"], "values": {"WIDTH": "8..32 pow2"}}])
        assert not result["skipped"]
        arch = ws.architectures["v"]
        assert arch.domains["MODE"].settings.get("variables")["MODE"]["type"] == "range"
        variables = arch.domains["fifo"].settings.get("variables")
        assert variables["WIDTH"]["type"] == "power_of_two" and variables["DEPTH"]["type"] == "list"


class TestChoices:
    def test_every_module_is_a_choice_suggested_first(self, project):
        d = pd.detect_project(project, check=False)
        suggested, others = pd.module_choices(d)
        assert suggested[0] == "top"
        assert set(suggested + others) >= {"top", "leaf", "unused"} and "tb_top" not in suggested + others

    def test_every_one_bit_input_is_a_clock_or_reset_choice(self, project):
        d = pd.detect_project(project, check=False)
        inputs, clocks, resets = pd.signal_choices(d, "top")
        assert inputs == ["clk_i", "rst_ni"]  # d[7:0] is not one bit
        assert clocks == ["clk_i"] and resets == ["rst_ni"]
        assert pd.signal_choices(d, "leaf")[0] == ["clk"]

    def test_gui_options(self, project):
        import odatix.gui.project_import as gui
        d = pd.detect_project(project, check=False)
        clock_options, clock, reset_options, reset = gui.signal_options(d, "top")
        assert clock == "clk_i" and reset == "rst_ni"
        assert [o["value"] for o in clock_options] == ["clk_i", "rst_ni"]
        assert [o["value"] for o in gui.top_options(d)][0] == "top"
