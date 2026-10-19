"""
RTL analysis: how the reports of each tool are read (odatix.lib.analysis), the
records they become, the terminal report, and the run of an analysis.

The log excerpts below are real: they come from analyses of deliberately broken
designs (a missing module, an undeclared signal, a latch...) by each tool.
"""

import os
import sys
import time

import pytest
import yaml

import odatix.lib.analysis as analysis
import odatix.lib.eda_tools as eda_tools
import odatix.lib.hard_settings as hard_settings
import odatix.lib.results_schema as results_schema
from odatix.lib.settings import OdatixSettings


@pytest.fixture
def user_tools_dir(tmp_path, monkeypatch):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    monkeypatch.setattr(OdatixSettings, "user_tools_path", str(tools_dir))
    return tools_dir


def make_job(root, name, log="", top="top", complete=True, sources=("top.sv",), log_name="analysis.log",
             configuration=None):
    """A job directory as an analysis leaves it."""
    job = root / name
    (job / "log").mkdir(parents=True)
    (job / "rtl").mkdir()
    for source in sources:
        (job / "rtl" / source).write_text("", encoding="utf-8")
    (job / hard_settings.arch_filename).write_text(name + "/" + (configuration or name) + "\n", encoding="utf-8")
    (job / hard_settings.yaml_config_filename).write_text(yaml.safe_dump({"top_level_module": top}), encoding="utf-8")
    if log is not None:
        (job / "log" / log_name).write_text(log, encoding="utf-8")
    if complete:
        (job / "log" / hard_settings.synth_status_filename).write_text(hard_settings.valid_status + "\n", encoding="utf-8")
    return str(job)


def result_of(tool, job, **kwargs):
    return analysis.analyze_job(job, tool, architecture=os.path.basename(job), configuration=os.path.basename(job), **kwargs)


######################################
# What each tool says
######################################

VERILATOR_LOG = """\
%Error-MODMISSING: rtl/top.sv:2:3: Cannot find file containing module: 'sub_missing'
    2 |   sub_missing u_sub (.clk(clk), .d(d), .q(q));
      |   ^~~~~~~~~~~
                   ... For error description see https://verilator.org/warn/MODMISSING?v=5.046
%Warning-LATCH: rtl/top.sv:2:3: Latch inferred for signal 'q' (not all control paths of combinational always assign a value)
%Warning-PINMISSING: rtl/top.sv:5:7: Instance has missing pin: 'd'
%Warning-DECLFILENAME: rtl/top.sv:1:8: Filename 'top' does not match MODULE name: 'sub'
%Error: Exiting due to 1 error(s)
"""

VIVADO_LOG = """\
<grey>[analyze_script.tcl]<end> <cyan>Verilog/SystemVerilog files:<end>
WARNING: [Synth 8-7080] Parallel synthesis criteria is not met
WARNING: [Synth 8-7129] Port undriven_out[7] in module top is either unconnected or has no load
WARNING: [Synth 8-7129] Port undriven_out[6] in module top is either unconnected or has no load
WARNING: [Synth 8-7129] Port undriven_out[5] in module top is either unconnected or has no load
ERROR: [Synth 8-439] module 'sub_missing' not found [{job}/rtl/top.sv:2]
ERROR: [Synth 8-6156] failed synthesizing module 'top' [{job}/rtl/top.sv:1]
<grey>[elaborate_script.tcl]<end> <bold><red>error: Vivado RTL analysis terminated with errors<end>
"""

QUARTUS_LOG = """\
Critical Warning (20759): Use the Reset Release IP in Agilex 7 designs to ensure a successful configuration.
Warning (19651): Verilog HDL warning at top.sv(4): latch inferred for net q[7] File: {job}/rtl/top.sv Line: 4
Warning (21620): Design Assistant Results: 1 of 1 High severity rules issued violations in snapshot 'partitioned'.
"""


class TestVerilator:
    def test_findings(self, tmp_path):
        result = result_of("verilator", make_job(tmp_path, "D", VERILATOR_LOG))
        assert result.status == analysis.STATUS_FAILED
        main = result.main_finding
        assert (main.severity, main.category, main.subject, main.location, main.code) == (
            "error", "missing_module", "sub_missing", "rtl/top.sv:2", "MODMISSING",
        )
        # The indented lines below a message are its excerpt.
        assert main.detail[0].strip().startswith("2 |")
        categories = {finding.category: finding for finding in result.findings}
        assert categories["latch"].severity == "warning"
        # A pin warning stays a warning, whatever the rule it matched says.
        assert categories["port_mismatch"].severity == "warning"
        assert "Exiting due to" not in " ".join(finding.message for finding in result.findings)

    def test_style_remarks_are_expected(self, tmp_path):
        result = result_of("verilator", make_job(tmp_path, "D", VERILATOR_LOG))
        style = [finding for finding in result.findings if finding.category == "style"]
        assert style and all(finding.expected and finding.reason for finding in style)
        assert result.count("expected") == 1

    def test_a_vhdl_design_is_not_supported(self, tmp_path):
        log = "%Error: rtl/top.vhd:1:9: syntax error, unexpected ';', expecting STRING\n"
        result = result_of("verilator", make_job(tmp_path, "D", log, sources=("top.vhd",)))
        assert result.status == analysis.STATUS_UNSUPPORTED
        assert result.findings == [] and result.count("error") == 0
        assert "VHDL" in result.summary


ICARUS_LOG = """\
rtl/top.v:7: error: port ``b'' is not a port of u_sub.
rtl/top.v:8: error: Unable to bind wire/reg/memory `undeclared_thing' in `top'
rtl/top.v:8: error: Unable to elaborate r-value: undeclared_thing
rtl/top.v:16: error: Unknown module type: sub_missing
rtl/top.v:6: warning: Port 1 (a) of sub expects 4 bits, got 8.
rtl/top.v:6:        : Pruning 4 high bits of the expression.
warning: Some design elements have no explicit time unit and/or
       : time precision. This may cause confusing timing results.
4 error(s) during elaboration.
*** These modules were missing:
        sub_missing referenced 1 times.
***
"""


class TestIcarus:
    def test_findings(self, tmp_path):
        result = result_of("icarus", make_job(tmp_path, "D", ICARUS_LOG))
        assert result.status == analysis.STATUS_FAILED
        main = result.main_finding
        assert (main.severity, main.category, main.subject, main.location) == (
            "error", "missing_module", "sub_missing", "rtl/top.v:16",
        )
        categories = {finding.category: finding for finding in result.findings}
        assert categories["undeclared"].subject == "undeclared_thing"
        assert categories["port_mismatch"].subject == "b"
        # A line repeating where it is before the colon continues the message.
        assert categories["width_mismatch"].detail[0].endswith("Pruning 4 high bits of the expression.")
        assert categories["style"].expected
        # Neither the error count, the list of missing modules, nor what only
        # follows from the unbound name is a finding.
        assert "elaborat" not in " ".join(finding.message for finding in result.findings)
        assert sum(finding.category == "missing_module" for finding in result.findings) == 1

    def test_syntax_errors(self, tmp_path):
        log = "rtl/top.v:8: syntax error\nrtl/top.v:1: error: Syntax error in variable list.\nI give up.\n"
        result = result_of("icarus", make_job(tmp_path, "D", log))
        assert [(finding.category, finding.location) for finding in result.findings] == [("syntax", "rtl/top.v:8")]

    def test_a_missing_top_level_and_source_file(self, tmp_path):
        log = (
            "rtl/top.v: No such file or directory\n"
            'error: Unable to find the root module "top" in the Verilog source.\n'
            "     : Perhaps ``-s top'' is incorrect?\n"
            "1 error(s) during elaboration.\n"
        )
        result = result_of("icarus", make_job(tmp_path, "D", log))
        assert sorted(finding.category for finding in result.findings) == ["missing_file", "missing_top"]

    def test_a_vhdl_design_is_not_supported(self, tmp_path):
        log = "rtl/top.vhd:1: error: No architectures to choose from for entity e.\n"
        result = result_of("icarus", make_job(tmp_path, "D", log, sources=("top.vhd",)))
        assert result.status == analysis.STATUS_UNSUPPORTED


# Raw: Yosys writes the names of the design with a leading backslash
YOSYS_LOG = r"""rtl/top.sv:4: Warning: Identifier `\implicit_net' is implicitly declared.
rtl/top.sv:5: Warning: Range [4:0] select out of bounds on signal `\r': Setting 1 MSB bits to undef.
Warning: Resizing cell port top.u.x from 4 bits to 2 bits.
Warning: Wire top.\undriven is used but has no driver.
Warning: multiple conflicting drivers for top.\b:
    module input b[0]
    module input a[0]
Warning: found logic loop in module top:
    cell $rtl/top.sv:3$xor$1 ($xor) source: rtl/top.sv:3.14-3.20
      A[0] --> Y[0]
Warning: Latch inferred for signal `\top.\q' from process `\top.$rtl/top.sv:2$proc$1': $auto$proc_dlatch.cc:559:proc_dlatch$15
ERROR: Module `\sub_missing' referenced in module `\top' in cell `\m' is not part of the design.
"""


class TestYosys:
    def test_findings(self, tmp_path):
        result = result_of("yosys", make_job(tmp_path, "D", YOSYS_LOG))
        assert result.status == analysis.STATUS_FAILED
        main = result.main_finding
        assert (main.severity, main.category, main.subject) == ("error", "missing_module", "sub_missing")
        found = {finding.category: finding for finding in result.findings}
        assert (found["undeclared"].subject, found["undeclared"].location) == ("implicit_net", "rtl/top.sv:4")
        assert found["undriven"].subject == "undriven"
        assert found["multiple_drivers"].subject == "b"
        assert [line.strip() for line in found["multiple_drivers"].detail] == ["module input b[0]", "module input a[0]"]
        assert found["combinational_loop"].subject == "top"
        assert found["latch"].subject == "q"
        assert sorted(finding.category for finding in result.findings if finding.category == "width_mismatch") == [
            "width_mismatch", "width_mismatch",
        ]

    @pytest.mark.parametrize("log, category, subject", [
        ("rtl/top.sv:2: ERROR: syntax error, unexpected ';'\n", "syntax", None),
        ("ERROR: Module `nosuch' not found!\n", "missing_top", "nosuch"),
        ("ERROR: File `rtl/none.sv' not found or is a directory\n", "missing_file", "rtl/none.sv"),
        ("ERROR: Can't open include file `nohdr.svh'!\n", "missing_file", "nohdr.svh"),
        ("ERROR: Module `sub' referenced in module `top' in cell `u' does not have a port named 'nope'.\n",
         "port_mismatch", "nope"),
    ])
    def test_errors(self, tmp_path, log, category, subject):
        result = result_of("yosys", make_job(tmp_path, "D", log))
        assert [(finding.category, finding.subject) for finding in result.findings] == [(category, subject)]

    def test_a_vhdl_design_is_not_supported(self, tmp_path):
        log = "ERROR: File `rtl/top.vhd' not found or is a directory\n"
        result = result_of("yosys", make_job(tmp_path, "D", log, sources=("top.vhd",)))
        assert result.status == analysis.STATUS_UNSUPPORTED


class TestVivado:
    def test_findings(self, tmp_path):
        job = str(tmp_path / "D")
        make_job(tmp_path, "D", VIVADO_LOG.format(job=job))
        result = result_of("vivado", job)
        assert result.status == analysis.STATUS_FAILED
        assert result.main_finding.category == "missing_module"
        assert result.main_finding.location == "rtl/top.sv:2"

    def test_what_follows_from_other_errors_is_left_out(self, tmp_path):
        job = str(tmp_path / "D")
        make_job(tmp_path, "D", VIVADO_LOG.format(job=job))
        messages = [finding.message for finding in result_of("vivado", job).findings]
        assert not any("failed synthesizing" in message for message in messages)
        assert not any("terminated with errors" in message for message in messages)

    def test_the_bits_of_a_bus_are_one_finding(self, tmp_path):
        job = str(tmp_path / "D")
        make_job(tmp_path, "D", VIVADO_LOG.format(job=job))
        unused = [finding for finding in result_of("vivado", job).findings if finding.category == "unused"]
        assert len(unused) == 1
        assert (unused[0].subject, unused[0].count) == ("undriven_out", 3)

    def test_a_top_level_the_sources_lack_is_told_apart(self, tmp_path):
        result = result_of("vivado", make_job(tmp_path, "D", "ERROR: [Synth 8-439] module 'top' not found\n"))
        assert result.main_finding.category == "missing_top"


class TestQuartus:
    def test_the_advice_given_to_every_design_is_expected(self, tmp_path):
        job = str(tmp_path / "D")
        make_job(tmp_path, "D", QUARTUS_LOG.format(job=job))
        result = result_of("quartus", job)
        assert result.status == analysis.STATUS_WARNING
        assert result.main_finding.category == "latch"
        # The prefix repeating the location is not part of the message.
        assert result.main_finding.message == "latch inferred for net q[7]"
        assert result.main_finding.subject == "q"
        assert sorted(finding.code for finding in result.expected) == ["20759", "21620"]

    def test_a_design_with_expected_findings_only_passes(self, tmp_path):
        log = "\n".join(line for line in QUARTUS_LOG.splitlines() if "19651" not in line)
        assert result_of("quartus", make_job(tmp_path, "D", log)).status == analysis.STATUS_PASSED


DC_LATCH_LOG = """\
Inferred memory devices in process in routine 'top' in file
	 './rtl/top.sv'.
==============================================================================
|    Register Name    | Type  | Width | Bus | MB |  Set  | Reset | ST | Line |
==============================================================================
|        q_reg        | Latch |   8   |  Y  | N  | None  | None  | -  |  2   |
==============================================================================
Information: Module top report end. (ELAB-965)
Warning: In design 'top', port 'clk' is not connected to any nets. (LINT-28)
"""

DC_BAD_PORT_LOG = """\
Error: Can't find inout port 'data' on reference to 'sub' in 'top'. (LINK-1)
Warning: Unable to resolve reference 'sub' in 'top'. (LINK-5)
Warning: In design 'top', input port 'd[0]' drives wired logic; the port direction may have been specified incorrectly. (LINT-6)
"""

DC_MULTI_DRIVER_LOG = """\
Warning:  rtl/top.sv:3: Net q[1] or a directly connected net may be driven by more than one process or block. (ELAB-405)
Warning:  rtl/top.sv:3: Net q[0] or a directly connected net may be driven by more than one process or block. (ELAB-405)
Error:  :0: Net 'q[1]' or a directly connected net is driven by more than one source, and not all drivers are three-state. (ELAB-366)
Error:  :0: Net 'q[0]' or a directly connected net is driven by more than one source, and not all drivers are three-state. (ELAB-366)
"""

DC_VHDL_LOG = """\
-------------------
     4:   u_sub : entity work.sub_missing port map (clk => clk, d => d, q => q);
                              ^^^^^^^^^^^
[Error] SUB_MISSING is not a primary unit of library WORK
[Failure] End of compilation: error(s) in design unit RTL
*** Presto compilation was unsuccessful. ***
"""


class TestDesignCompiler:
    def test_a_latch_is_read_from_the_table_of_inferred_registers(self, tmp_path):
        result = result_of("design_compiler", make_job(tmp_path, "D", DC_LATCH_LOG))
        assert result.status == analysis.STATUS_WARNING
        assert (result.main_finding.category, result.main_finding.subject) == ("latch", "q_reg")
        assert result.main_finding.message == "Latch inferred for 'q_reg'"
        unused = next(finding for finding in result.findings if finding.category == "unused")
        # The port, not the design the message names first.
        assert unused.subject == "clk"

    def test_a_port_a_module_lacks_is_not_a_missing_module(self, tmp_path):
        result = result_of("design_compiler", make_job(tmp_path, "D", DC_BAD_PORT_LOG))
        assert result.status == analysis.STATUS_FAILED
        assert [(finding.category, finding.subject) for finding in result.findings] == [("port_mismatch", "data")]

    def test_a_missing_module_is_an_error(self, tmp_path):
        # Design Compiler only warns, and elaborates a black box.
        log = """\
Warning: Cannot find the design 'sub_missing' in the library 'WORK'. (LBR-1)
Warning: Design 'top' has '1' unresolved references. For more detailed information, use the "link" command. (UID-341)
Warning: Unable to resolve reference 'sub_missing' in 'top'. (LINK-5)
"""
        result = result_of("design_compiler", make_job(tmp_path, "D", log))
        assert result.status == analysis.STATUS_FAILED
        assert [(finding.category, finding.subject) for finding in result.findings] == [("missing_module", "sub_missing")]

    def test_several_drivers(self, tmp_path):
        result = result_of("design_compiler", make_job(tmp_path, "D", DC_MULTI_DRIVER_LOG))
        assert [(finding.severity, finding.category, finding.count) for finding in result.findings] == [
            ("error", "multiple_drivers", 2),
        ]
        # No line of the sources (" :0:"): no file, and the bits it was said of.
        assert result.main_finding.file is None
        assert result.main_finding.message.startswith("Net 'q[1:0]'")

    def test_vhdl(self, tmp_path):
        result = result_of("design_compiler", make_job(tmp_path, "D", DC_VHDL_LOG, sources=("top.vhd",)))
        assert result.status == analysis.STATUS_FAILED
        assert [(finding.category, finding.subject) for finding in result.findings] == [("missing_module", "SUB_MISSING")]


GENUS_LOG = """\
Warning : Cannot open file. [VLOGPT-650]
        : File 'missing_defs.svh' in file 'rtl/top.sv' on line 1, column 27.
        : The specified file could not be opened.  Check the value of the init_hdl_search_path attribute.
Warning : In legacy_ui mode, Genus creates a blackbox as description for a module is not found. [CDFG-428]
        : A blackbox was created for instance 'u_sub' in file 'rtl/top.sv' on line 2.
Warning : Black-boxes are represented as unresolved references in the design. [TUI-273]
        : Cannot resolve reference to 'sub_missing'.
Info    : To insure proper verification, preserved netlist point(s) because they are involved in combinational loop(s). To disable this, set the 'cb_preserve_ports_nets' root attribute to 'false'. [ELABUTL-133]
"""

GENUS_CHECKOUT = """\
  Unresolved References & Empty Modules
  -------------------------------------
design 'top' has the following unresolved references
hinst:top/u_sub
Total number of unresolved references in design 'top' : 1
 Unloaded Pin(s), Port(s)
 -------------------------
design 'top' has the following unloaded port(s)
port:top/unused_in[1]
port:top/unused_in[0]
Total number of unloaded ports in design 'top' : 2
design 'top' has the following undriven port(s)
port:top/undriven_out[3]
"""


class TestGenus:
    def job(self, tmp_path, log=GENUS_LOG, checkout=GENUS_CHECKOUT, latches="inst:top/q_reg[0]\ninst:top/q_reg[1]\n"):
        job = make_job(tmp_path, "D", log)
        os.makedirs(os.path.join(job, "report"))
        with open(os.path.join(job, "report", "checkout.rep"), "w", encoding="utf-8") as f:
            f.write(checkout)
        with open(os.path.join(job, "report", "latches.rep"), "w", encoding="utf-8") as f:
            f.write(latches)
        return job

    def test_what_a_message_is_about_is_read_below_it(self, tmp_path):
        findings = {finding.code: finding for finding in result_of("genus", self.job(tmp_path)).findings if finding.code}
        missing = findings["VLOGPT-650"]
        assert (missing.category, missing.severity, missing.subject, missing.location) == (
            "missing_file", "error", "missing_defs.svh", "rtl/top.sv:1",
        )
        assert missing.message == "Cannot open 'missing_defs.svh'"
        assert findings["TUI-273"].message == "Module 'sub_missing' is defined nowhere: it is a black box"
        # The black box of the instance says nothing more than the module.
        assert "CDFG-428" not in findings
        assert findings["ELABUTL-133"].category == "combinational_loop"

    def test_the_lists_of_check_design(self, tmp_path):
        findings = result_of("genus", self.job(tmp_path)).findings
        found = {(finding.category, finding.subject): finding for finding in findings}
        assert found[("unused", "unused_in")].message == "Input 'unused_in[1:0]' is never read"
        assert ("undriven", "undriven_out") in found
        assert found[("latch", "q_reg")].count == 2
        # The unresolved instance only repeats the black box.
        assert not [finding for finding in findings if finding.message.startswith("Instance")]
        # A row is only one below its heading.
        assert ("unused", "undriven_out") not in found

    def test_a_parsing_error_says_what_was_expected(self, tmp_path):
        log = """\
Error   : Parsing error. [VLOGPT-1] [read_hdl]
        : Expecting token ';', found 'always_ff' in file 'rtl/top.sv' on line 3, column 11.
        : Invalid Verilog syntax is parsed, or unsupported Verilog syntax is encountered.
"""
        result = result_of("genus", self.job(tmp_path, log=log, checkout="", latches=""))
        assert result.status == analysis.STATUS_FAILED
        assert result.main_finding.message == "Parsing error: Expecting token ';', found 'always_ff'"
        assert result.main_finding.location == "rtl/top.sv:3"


class TestRules:
    """What message rules can say, whatever the tool."""

    def definition(self, user_tools_dir, data):
        (user_tools_dir / "mylint").mkdir()
        (user_tools_dir / "mylint" / "tool.yml").write_text("unix:\n  analysis_command: [true]\n", encoding="utf-8")
        (user_tools_dir / "mylint" / "analysis.yml").write_text(yaml.safe_dump(data), encoding="utf-8")
        return analysis.load_definition("mylint")

    def test_a_secondary_message_goes_when_one_as_severe_is_there(self, user_tools_dir, tmp_path):
        definition = self.definition(user_tools_dir, {"messages": {
            "main": {"pattern": "^W: (?P<message>width.*)", "severity": "warning", "category": "width_mismatch"},
            "then": {"pattern": "^W: (?P<message>so.*)", "severity": "warning", "secondary": True},
            "error": {"pattern": "^E: (?P<message>.*)", "severity": "error", "secondary": True},
        }})
        log = "W: width differs\nW: so this\nE: and this error\n"
        findings = result_of("mylint", make_job(tmp_path, "D", log), definition=definition).findings
        # A warning does not explain an error away.
        assert [finding.message for finding in findings] == ["and this error", "width differs"]

    def test_a_secondary_message_alone_is_kept(self, user_tools_dir, tmp_path):
        definition = self.definition(user_tools_dir, {"messages": {
            "then": {"pattern": "^W: (?P<message>.*)", "severity": "warning", "secondary": True},
        }})
        findings = result_of("mylint", make_job(tmp_path, "D", "W: alone\n"), definition=definition).findings
        assert [finding.message for finding in findings] == ["alone"]

    def test_bits_that_do_not_follow_each_other(self, user_tools_dir, tmp_path):
        definition = self.definition(user_tools_dir, {"messages": {
            "unused": {"pattern": "^W: (?P<message>.*)", "severity": "warning", "category": "unused"},
        }})
        log = "W: Port d[5] is unused\nW: Port d[0] is unused\nW: Port d[2] is unused\n"
        findings = result_of("mylint", make_job(tmp_path, "D", log), definition=definition).findings
        assert [(finding.message, finding.count) for finding in findings] == [("Port d[0,2,5] is unused", 3)]


class TestStatus:
    def test_an_unfinished_analysis_is_incomplete(self, tmp_path):
        result = result_of("verilator", make_job(tmp_path, "D", "", complete=False))
        assert result.status == analysis.STATUS_INCOMPLETE

    def test_a_tool_that_could_not_run_is_a_tool_failure(self, tmp_path):
        # No license: Design Compiler writes no log, the job output says why.
        job = make_job(tmp_path, "D", None, complete=False)
        with open(os.path.join(job, "log", hard_settings.console_log_filename), "w", encoding="utf-8") as f:
            f.write("Fatal: Design Compiler is not enabled. (DCSH-1)\n")
        result = result_of("design_compiler", job)
        assert result.status == analysis.STATUS_TOOL_FAILURE
        assert result.main_finding.category == "tool_setup"

    def test_a_clean_design_passes(self, tmp_path):
        assert result_of("verilator", make_job(tmp_path, "D", "")).status == analysis.STATUS_PASSED


######################################
# What is normal for a design
######################################

class TestExpectations:
    def test_run_settings_say_what_is_normal(self, tmp_path):
        job = make_job(tmp_path, "D", VERILATOR_LOG.replace("%Error-MODMISSING", "%Warning-MODMISSING"))
        expected = analysis.read_expectations([
            {"category": "latch", "architectures": ["D"], "reason": "a latch on purpose"},
            {"code": "MODMISSING", "tools": ["vivado"]},
        ])
        result = result_of("verilator", job, expected=expected)
        latch = next(finding for finding in result.findings if finding.category == "latch")
        assert latch.expected and latch.reason == "a latch on purpose"
        # Only for the tools it names.
        assert not next(finding for finding in result.findings if finding.code == "MODMISSING").expected

    def test_conditions(self):
        finding = analysis.Finding("warning", "unused", "Signal is not used: 'dbg_bus'", subject="dbg_bus", file="rtl/debug/x.sv")
        assert analysis.Expectation(subject="dbg_*").matches(finding)
        assert analysis.Expectation(file="rtl/debug/*").matches(finding)
        assert analysis.Expectation(message="not used").matches(finding)
        assert not analysis.Expectation(severity="error").matches(finding)
        assert analysis.Expectation(architectures=["Cpu"]).matches(finding, design="Cpu/fast")
        assert not analysis.Expectation(architectures=["Cpu/slow"]).matches(finding, design="Cpu/fast")

    def test_an_expected_finding_is_not_the_summary(self, tmp_path):
        log = "%Warning-UNUSEDSIGNAL: rtl/top.sv:1:1: Signal is not used: 'a'\n%Warning-LATCH: rtl/top.sv:2:3: Latch inferred for signal 'q'\n"
        result = result_of("verilator", make_job(tmp_path, "D", log),
                           expected=analysis.read_expectations({"latch": {"category": "latch"}}))
        assert result.main_finding.category == "unused"
        assert result.findings[-1].category == "latch"


######################################
# Definitions
######################################

class TestDefinitions:
    @pytest.mark.parametrize("tool", ["verilator", "icarus", "yosys", "vivado", "quartus", "design_compiler", "genus", "dc_nxt", "librelane"])
    def test_every_category_a_definition_names_exists(self, tool):
        definition = analysis.load_definition(tool)
        assert definition.rules
        for code, settings in definition.codes.items():
            assert settings.get("category", "other") in definition.categories, (tool, code)
        for rule in definition.rules:
            assert rule.category in definition.categories, (tool, rule.name)
        for expectation in definition.expected:
            assert expectation.category is None or expectation.category in definition.categories

    def test_dc_nxt_reads_like_design_compiler(self):
        assert analysis.load_definition("dc_nxt").codes == analysis.load_definition("design_compiler").codes

    def test_a_workspace_completes_a_builtin_definition(self, user_tools_dir, tmp_path):
        (user_tools_dir / "verilator").mkdir()
        (user_tools_dir / "verilator" / "analysis.yml").write_text(yaml.safe_dump({
            "codes": {"LATCH": {"category": "latch", "severity": "error"}},
            "messages": {"missing_module": None},
            "expected": {"style": None},
        }))
        definition = analysis.load_definition("verilator")
        assert definition.codes["LATCH"]["severity"] == "error"
        assert "missing_module" not in [rule.name for rule in definition.rules]
        assert definition.expected == []
        result = result_of("verilator", make_job(tmp_path, "D", VERILATOR_LOG), definition=definition)
        assert next(finding for finding in result.findings if finding.category == "latch").severity == "error"

    def test_a_tool_of_the_workspace_has_the_shared_vocabulary(self, user_tools_dir):
        (user_tools_dir / "mylint").mkdir()
        (user_tools_dir / "mylint" / "tool.yml").write_text("unix:\n  analysis_command: [true]\n", encoding="utf-8")
        definition = analysis.load_definition("mylint")
        assert "missing_module" in definition.categories
        assert [rule.name for rule in definition.rules if rule.name.startswith("odatix_")]


######################################
# Records
######################################

class TestRecords:
    def test_a_record_of_the_default_flow_written_without_flow_is_replaced(self, tmp_path):
        from odatix.components.export_analysis import export_analysis_results

        old = analysis.AnalysisResult("verilator", "D", "D", status=analysis.STATUS_FAILED)
        assert export_analysis_results([old], str(tmp_path))
        new = analysis.AnalysisResult("verilator", "D", "D", flow="lint", status=analysis.STATUS_PASSED)
        assert export_analysis_results([new], str(tmp_path))
        records = results_schema.load_results_file(str(tmp_path / "results_analysis_verilator.yml")).records
        assert [record["meta"]["_status"] for record in records] == ["passed"]

    def test_round_trip(self, tmp_path):
        result = result_of("verilator", make_job(tmp_path, "D", VERILATOR_LOG))
        record = result.to_record(results_schema)
        assert record["meta"]["type"] == "analysis"
        assert record["metrics"]["expected_count"] == 1
        again = analysis.AnalysisResult.from_record(record)
        assert again.status == result.status
        assert [finding.to_dict() for finding in again.findings] == [finding.to_dict() for finding in result.findings]
        assert again.counts == result.counts

    def test_a_record_of_an_earlier_version_is_read(self):
        record = {
            "meta": {"type": "analysis", "tool": "vivado", "architecture": "A", "configuration": "c",
                     "_status": "WARNING", "_errors": [], "_critical_warnings": ["blackbox u0"]},
            "metrics": {"error_count": 0, "critical_warning_count": 1, "standard_warning_count": 2},
        }
        result = analysis.AnalysisResult.from_record(record)
        assert result.status == analysis.STATUS_WARNING
        assert result.findings[0].message == "blackbox u0"
        assert (result.count("critical"), result.count("warning")) == (1, 2)

    def test_export(self, tmp_path):
        from odatix.components.export_analysis import export_analysis_results

        result = result_of("verilator", make_job(tmp_path, "D", VERILATOR_LOG))
        assert export_analysis_results([result], str(tmp_path / "results"))
        records = results_schema.load_results_file(str(tmp_path / "results" / "results_analysis_verilator.yml")).records
        assert len(records) == 1 and records[0]["meta"]["_status"] == "failed"


######################################
# The report
######################################

def plain(lines):
    from odatix.components.analysis_report import _ANSI

    return "\n".join(_ANSI.sub("", line) for line in lines)


class TestReport:
    def _results(self, tmp_path):
        return [
            result_of("verilator", make_job(tmp_path / "v", "A", VERILATOR_LOG)),
            result_of("verilator", make_job(tmp_path / "v", "B", "")),
            result_of("quartus", make_job(tmp_path / "q", "A", QUARTUS_LOG.format(job=tmp_path / "q" / "A"))),
            result_of("verilator", make_job(tmp_path / "v", "C", "", sources=("x.vhd",))),
        ]

    def test_sections(self, tmp_path):
        from odatix.components.analysis_report import render

        text = plain(render(self._results(tmp_path), width=120))
        assert "2 tools: quartus, verilator" in text
        assert "Missing module" in text and "Latch inferred" in text
        assert "✗ Failed (1)" in text
        assert "Cannot find file containing module: 'sub_missing'" in text
        assert "○ Expected" in text and "Reset Release IP" in text
        assert "verilator does not read VHDL: C" in text

    def test_one_tool_has_no_matrix(self, tmp_path):
        from odatix.components.analysis_report import render

        text = plain(render([result for result in self._results(tmp_path) if result.tool == "verilator"]))
        assert "Design " not in text

    def test_job_directories(self, tmp_path):
        from odatix.components.analysis_report import collect_results, job_directories

        root = tmp_path / "analysis"
        make_job(root / "verilator" / "analysis", "A", VERILATOR_LOG)
        make_job(root / "verilator@strict" / "analysis", "A", "")
        jobs = job_directories(str(root))
        assert sorted((tool, flow or "") for tool, flow in jobs.values()) == [("verilator", ""), ("verilator", "strict")]
        # The default flow is named, as in every other results file.
        assert sorted(result.flow for result in collect_results(jobs)) == ["lint", "strict"]
        assert job_directories(str(root), tools=["vivado"]) == {}


######################################
# Running an analysis
######################################

@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell commands")
class TestDaemonExport:
    """A failed analysis is a result: the job handler exports it all the same."""

    def test_a_failed_job_is_exported_and_stays_failed(self, tmp_path, monkeypatch):
        import odatix.components.export_analysis as export_analysis
        import odatix.lib.parallel_job_handler.handler_core as handler_core
        from odatix.lib.parallel_job_handler.job import ParallelJob

        exported = []
        monkeypatch.setattr(export_analysis, "export_single_analysis_job",
                            lambda job, export_config: exported.append(job) or True)
        job = ParallelJob(
            process=None, command="echo oops; exit 3", directory=str(tmp_path), generate_rtl=False,
            generate_command="", target="t", arch="a", display_name="job", status_file="",
            progress_file="", tmp_dir=str(tmp_path), log_size_limit=100,
        )
        job.post_run_export = {"kind": "analysis", "on_failure": True}
        job.console_log = str(tmp_path / "log" / "console.log")
        handler = handler_core.ParallelJobHandler([job], nb_jobs=1, format_yaml="")
        handler._headless_initialized = True
        handler.start_job(job)

        deadline = time.time() + 10
        while time.time() < deadline and not exported:
            with handler._lock:
                handler._update_jobs_state()
            time.sleep(0.05)
        deadline = time.time() + 5
        while time.time() < deadline and job.status == "exporting":
            time.sleep(0.05)
        handler.terminate_all_jobs(timeout=1)

        assert exported == [job]
        assert job.status == "failed"
        assert "oops" in open(job.console_log, encoding="utf-8").read()


class TestCommands:
    def test_noexport(self, example_workspace, monkeypatch):
        import odatix.odatix_main as odatix_main
        import odatix.run.cli as run_cli

        seen = {}

        def execute(run):
            seen["run"] = run
            return run

        monkeypatch.setattr(run_cli, "execute", execute)
        sys_argv = sys.argv
        sys.argv = ["odatix", "analyze", "-Q", "-y", "-d", "-e", "-t", "verilator"]
        try:
            with pytest.raises(SystemExit) as stop:
                odatix_main.main(odatix_main.ArgParser.parse_arguments())
        finally:
            sys.argv = sys_argv
        assert stop.value.code == 0
        assert seen["run"].result_path == ""
        assert seen["run"].options.tool == ["verilator"]
        assert seen["run"].options.detach is True

    def test_the_tools_come_from_the_settings_file(self, example_workspace, monkeypatch):
        import odatix.components.run_analysis as run_analysis
        import odatix.run.cli as run_cli
        from argparse import Namespace

        seen = {}
        monkeypatch.setattr(run_cli, "execute", lambda run: seen.setdefault("run", run))
        args = Namespace(config=OdatixSettings.DEFAULT_SETTINGS_FILE, tool=None, flow=None, detach=True, noask=True)
        run_analysis.main(args)
        settings_file = str(example_workspace / "odatix_userconfig" / "analyze_settings.yml")
        assert seen["run"].options.tool == run_analysis.get_analysis_tools_from_settings(settings_file)

    def test_res_analysis(self, example_workspace):
        from conftest import SOURCES_DIR
        import subprocess

        work = example_workspace / "work" / "analysis" / "verilator" / "analysis"
        make_job(work, "Example", VERILATOR_LOG)
        result = subprocess.run(
            [sys.executable, "-m", "odatix.odatix_main", "res_analysis", "-Q"],
            cwd=str(example_workspace), env=dict(os.environ, PYTHONPATH=SOURCES_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Cannot find file containing module" in result.stdout
        assert (example_workspace / "results" / "results_analysis_verilator.yml").is_file()


class TestExtends:
    def test_librelane_reads_like_verilator_plus_yosys(self, tmp_path):
        log = (
            "%Warning-LATCH: rtl/top.sv:2:3: Latch inferred for signal 'q'\n"
            "%Error: yosys: Module `\\sub_missing' referenced in module `top' in cell `u' is not part of the design.\n"
            "%Error: librelane: Yosys.Synthesis failed\n"
        )
        result = result_of("librelane", make_job(tmp_path, "D", log, sources=("top.vhd",)))
        # It reads VHDL, through GHDL: no "not supported" there.
        assert result.status == analysis.STATUS_FAILED
        assert result.main_finding.category == "missing_module"
        assert result.main_finding.subject == "sub_missing"
        assert not any("librelane" in finding.message for finding in result.findings)
