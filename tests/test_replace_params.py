"""Tests for odatix.components.replace_params (delimiter-based parameter replacement)."""

import pytest

from odatix.components.replace_params import (
    replace_content,
    replace_params,
    replace_param_domain,
    replace_param_domains,
    get_first_appearance,
)
from odatix.lib.param_domain import ParamDomain


VERILOG = """module counter #(
  parameter WIDTH = 4
)(
  input clock,
  output [WIDTH-1:0] count
);
endmodule
"""


class TestReplaceContent:
    def test_replaces_between_delimiters(self):
        new_text, found = replace_content(VERILOG, "\n  parameter WIDTH = 16\n", "counter #(", ")(", False)
        assert found
        assert "parameter WIDTH = 16" in new_text
        assert "parameter WIDTH = 4" not in new_text
        # delimiters themselves are preserved
        assert "counter #(" in new_text
        assert ")(" in new_text

    def test_no_match(self):
        new_text, found = replace_content("hello", "X", "<<", ">>", False)
        assert not found
        assert new_text == "hello"

    def test_empty_delimiters_do_nothing(self):
        new_text, found = replace_content(VERILOG, "X", "", ")(", False)
        assert not found
        assert new_text == VERILOG

    def test_first_occurrence_only(self):
        base = "S a E middle S b E"
        new_text, found = replace_content(base, "X", "S", "E", False)
        assert found
        assert new_text == "SXE middle S b E"

    def test_all_occurrences(self):
        base = "S a E middle S b E"
        new_text, _ = replace_content(base, "X", "S", "E", True)
        assert new_text == "SXE middle SXE"

    def test_multiline_replacement(self):
        new_text, found = replace_content(
            "start(\nold1\nold2\n)end", "\nnew\n", "start(", ")end", False, keep_lines=False,
        )
        assert found
        assert new_text == "start(\nnew\n)end"

    def test_a_shorter_replacement_keeps_the_line_numbers(self):
        # E16: what an EDA tool reports at line N of the work copy is line N of
        # the source, after the block too.
        base = "a\n// <p>\nold1\nold2\n// </p>\nlast\n"
        new_text, found = replace_content(base, "\nnew\n", "// <p>", "// </p>", False)
        assert found
        assert new_text == "a\n// <p>\nnew\n\n// </p>\nlast\n"
        assert new_text.splitlines().index("last") == base.splitlines().index("last")

    def test_a_longer_replacement_is_not_cut(self):
        new_text, _ = replace_content("S\nE", "\n1\n2\n", "S", "E", False)
        assert new_text == "S\n1\n2\nE"

    def test_a_single_line_block_stays_on_one_line(self):
        new_text, _ = replace_content("W = /*<w>*/8/*</w>*/;", "16", "/*<w>*/", "/*</w>*/", False)
        assert new_text == "W = /*<w>*/16/*</w>*/;"


class TestCommentedOutConfiguration:
    """D-02: a configuration written into a line comment is commented out."""

    BASE = "module a;\n  // <regs>\n  localparam X = 1;\n  // </regs>\nendmodule\n"

    def test_a_configuration_landing_in_a_comment_is_reported(self):
        from odatix.components.replace_params import commented_out_warning

        message = commented_out_warning(self.BASE, "  localparam X = 0;\n", "  // <regs>", "  // </regs>", "a.v")
        assert message and "localparam X = 0;" in message

    def test_a_configuration_starting_with_a_line_break_is_fine(self):
        from odatix.components.replace_params import commented_out_warning

        assert commented_out_warning(self.BASE, "\n  localparam X = 0;\n", "  // <regs>", "  // </regs>", "a.v") is None

    def test_a_start_delimiter_ending_with_a_line_break_is_fine(self):
        from odatix.components.replace_params import commented_out_warning

        assert commented_out_warning(self.BASE, "  localparam X = 0;\n", "  // <regs>\\n", "  // </regs>", "a.v") is None

    def test_code_delimiters_are_not_comments(self):
        from odatix.components.replace_params import commented_out_warning

        assert commented_out_warning(VERILOG, "parameter WIDTH = 8", "counter #(", ")(", "counter.v") is None

    def test_the_comment_of_the_language_is_used(self):
        from odatix.components.replace_params import commented_out_warning

        vhdl = "entity a is\n  -- <g>\n  generic (W : integer := 4);\n  -- </g>\n"
        assert commented_out_warning(vhdl, "  generic (W : integer := 8);", "  -- <g>", "  -- </g>", "a.vhd")
        # In Verilog, "#" opens a parameter list, not a comment.
        assert commented_out_warning(VERILOG, "parameter WIDTH = 8", "counter #(", ")(", "counter.sv") is None

    def test_the_replace_command_warns(self, tmp_path, capsys):
        base = tmp_path / "a.v"
        base.write_text(self.BASE)
        config = tmp_path / "c.txt"
        config.write_text("  localparam X = 0;\n")
        assert replace_params(str(base), str(config), str(tmp_path / "o.v"), "  // <regs>", "  // </regs>")
        assert "ends up commented out" in capsys.readouterr().out


class TestGetFirstAppearance:
    def test_found(self):
        line, char = get_first_appearance("abc\ndef target", "target")
        assert (line, char) == (2, 4)

    def test_not_found(self):
        assert get_first_appearance("abc", "zzz") == (-1, -1)


class TestReplaceParamsFiles:
    def test_end_to_end(self, tmp_path):
        base = tmp_path / "top.v"
        base.write_text(VERILOG)
        replacement = tmp_path / "params.txt"
        replacement.write_text("\n  parameter WIDTH = 32\n")
        output = tmp_path / "out.v"

        found = replace_params(str(base), str(replacement), str(output), "counter #(", ")(", silent=True)
        assert found
        assert "parameter WIDTH = 32" in output.read_text()

    def test_in_place(self, tmp_path):
        base = tmp_path / "top.v"
        base.write_text(VERILOG)
        replacement = tmp_path / "params.txt"
        replacement.write_text("\n  parameter WIDTH = 64\n")

        found = replace_params(str(base), str(replacement), str(base), "counter #(", ")(", silent=True)
        assert found
        assert "parameter WIDTH = 64" in base.read_text()

    def test_pattern_not_found(self, tmp_path):
        base = tmp_path / "top.v"
        base.write_text("no delimiters here")
        replacement = tmp_path / "params.txt"
        replacement.write_text("X")
        output = tmp_path / "out.v"

        found = replace_params(str(base), str(replacement), str(output), "counter #(", ")(", silent=True)
        assert not found
        assert output.read_text() == "no delimiters here"


class TestReplaceParamDomains:
    def make_domain(self, tmp_path, value="16", use_parameters=True):
        param_file = tmp_path / f"{value}.txt"
        param_file.write_text(f"\n  parameter WIDTH = {value}\n")
        return ParamDomain(
            domain="main",
            domain_value=value,
            use_parameters=use_parameters,
            start_delimiter="counter #(",
            stop_delimiter=")(",
            param_target_file="top.v",
            param_file=str(param_file),
        )

    def test_replace_param_domain(self, tmp_path):
        (tmp_path / "top.v").write_text(VERILOG)
        domain = self.make_domain(tmp_path)
        assert replace_param_domain(domain, str(tmp_path), silent=True)
        assert "parameter WIDTH = 16" in (tmp_path / "top.v").read_text()

    def test_use_parameters_false_is_noop(self, tmp_path):
        (tmp_path / "top.v").write_text(VERILOG)
        domain = self.make_domain(tmp_path, use_parameters=False)
        assert not replace_param_domain(domain, str(tmp_path), silent=True)
        assert "parameter WIDTH = 4" in (tmp_path / "top.v").read_text()

    def test_replace_param_domains_returns_domain_dict(self, tmp_path):
        (tmp_path / "top.v").write_text(VERILOG)
        domain = self.make_domain(tmp_path)
        result = replace_param_domains([domain], str(tmp_path), timestamp="2026-01-01", silent=True)
        assert result["main"] == "16"
        assert result["__timestamp__"] == "2026-01-01"


class TestRunCheckWarnsAboutCommentedConfigurations:
    """D-02: the check of a run says it too, once per file and configuration."""

    def test_the_check_warns_once(self, tmp_path, capsys):
        from types import SimpleNamespace

        from odatix.lib.architecture_handler import ArchitectureHandler

        (tmp_path / "rtl").mkdir()
        (tmp_path / "rtl" / "adder.v").write_text(TestCommentedOutConfiguration.BASE)
        config = tmp_path / "Off.txt"
        config.write_text("  localparam X = 0;\n")
        handler = SimpleNamespace()
        substitution = (True, "adder.v", "  // <regs>", "  // </regs>", str(config))
        for _ in range(2):
            ArchitectureHandler.warn_commented_configurations(
                handler, "MyAdder/08bits", str(tmp_path / "rtl"), [substitution],
            )
        out = capsys.readouterr().out
        assert out.count("ends up commented out") == 1
        assert "MyAdder/08bits" in out
