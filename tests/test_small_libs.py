"""Tests for small lib modules: re_helper, variables, wosit."""

import re

import pytest

from odatix.lib.re_helper import get_re_group_from_file, BAD_VALUE
from odatix.lib.variables import Variables, replace_variables
import odatix.lib.wosit as wosit


######################################
# re_helper
######################################

class TestGetReGroupFromFile:
    def test_match(self, tmp_path):
        report = tmp_path / "report.txt"
        report.write_text("some line\nFrequency: 450.5 MHz\nother\n")
        pattern = re.compile(r"Frequency: ([0-9.]+) MHz")
        assert get_re_group_from_file(str(report), pattern, 1) == "450.5"

    def test_first_match_wins(self, tmp_path):
        report = tmp_path / "report.txt"
        report.write_text("LUT: 10\nLUT: 20\n")
        pattern = re.compile(r"LUT: ([0-9]+)")
        assert get_re_group_from_file(str(report), pattern, 1) == "10"

    def test_no_match_returns_bad_value(self, tmp_path):
        report = tmp_path / "report.txt"
        report.write_text("nothing here\n")
        pattern = re.compile(r"Frequency: ([0-9.]+)")
        assert get_re_group_from_file(str(report), pattern, 1) == BAD_VALUE

    def test_missing_file_returns_bad_value(self, tmp_path):
        pattern = re.compile(r"(x)")
        assert get_re_group_from_file(str(tmp_path / "nope.txt"), pattern, 1) == BAD_VALUE

    def test_custom_bad_value(self, tmp_path):
        pattern = re.compile(r"(x)")
        assert get_re_group_from_file(str(tmp_path / "nope.txt"), pattern, 1, bad_value="N/A") == "N/A"


######################################
# variables
######################################

class TestReplaceVariables:
    def test_replaces_known_variables(self):
        variables = Variables(work_path="/work", top_level_module="top")
        out = replace_variables("cd $work_path && synth $top_level_module", variables)
        assert out == "cd /work && synth top"

    def test_none_values_left_untouched(self):
        variables = Variables(work_path="/work")
        out = replace_variables("$work_path $clock_signal", variables)
        assert out == "/work $clock_signal"

    def test_none_variables_object(self):
        assert replace_variables("cmd $work_path", None) == "cmd $work_path"

    def test_all_variables(self):
        variables = Variables(
            odatix_path="/o",
            odatix_eda_tools_path="/e",
            work_path="/w",
            tool_install_path="/t",
            script_path="/s",
            log_path="/l",
            clock_signal="clk",
            top_level_module="top",
            lib_name="lib",
        )
        command = "$odatix_path $eda_tools_path $work_path $tool_install_path $script_path $log_path $clock_signal $top_level_module $lib_name"
        assert replace_variables(command, variables) == "/o /e /w /t /s /l clk top lib"


######################################
# wosit task graphs
######################################

class TestCreateTaskGraph:
    def test_requires_list(self):
        with pytest.raises(TypeError):
            wosit.createTaskGraph("not a list")

    def test_requires_name(self):
        with pytest.raises(ValueError):
            wosit.createTaskGraph([{"commands": ["echo hi"]}])

    def test_builds_maker(self):
        tasks = [
            {"name": "a", "commands": ["echo a"]},
            {"name": "b", "commands": ["echo b1", "echo b2"], "dependencies": ["a"]},
        ]
        maker = wosit.createTaskGraph(tasks, path="/tmp")
        assert maker is not None

    def test_empty_task_list(self):
        maker = wosit.createTaskGraph([])
        assert maker is not None
