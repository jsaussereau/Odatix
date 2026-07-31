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
        new_text, found = replace_content("start(\nold1\nold2\n)end", "\nnew\n", "start(", ")end", False)
        assert found
        assert new_text == "start(\nnew\n)end"


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
