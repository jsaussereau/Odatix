"""Tests for small lib modules: re_helper, variables, wosit."""

import os
import re
import subprocess
import sys

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
        report.write_text("some line\nFrequency: 450.5 MHz\nother\n", encoding="utf-8")
        pattern = re.compile(r"Frequency: ([0-9.]+) MHz")
        assert get_re_group_from_file(str(report), pattern, 1) == "450.5"

    def test_first_match_wins(self, tmp_path):
        report = tmp_path / "report.txt"
        report.write_text("LUT: 10\nLUT: 20\n", encoding="utf-8")
        pattern = re.compile(r"LUT: ([0-9]+)")
        assert get_re_group_from_file(str(report), pattern, 1) == "10"

    def test_no_match_returns_bad_value(self, tmp_path):
        report = tmp_path / "report.txt"
        report.write_text("nothing here\n", encoding="utf-8")
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


class TestOnFailureCommands:
    def test_without_fallback_the_commands_are_kept_as_they_are(self):
        assert wosit.task_command(["echo a", "echo b"]) == "echo a\necho b"

    def test_the_fallback_runs_when_the_commands_fail(self):
        command = wosit.task_command(["@echo a", "false"], ["echo b"])
        assert command == "(echo a && false) || (echo b)"

    def test_an_invalid_fallback_is_refused(self):
        with pytest.raises(ValueError):
            wosit.createTaskGraph([{"name": "main", "commands": ["true"], "on_failure_commands": {"a": 1}}])

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell commands")
    @pytest.mark.parametrize("commands, fallback, code, output", [
        (["echo primary"], ["echo fallback"], 0, "primary\n"),
        (["false", "echo never"], ["echo fallback"], 0, "fallback\n"),
        (["false"], ["false"], 1, ""),
    ])
    def test_as_the_daemon_runs_it(self, tmp_path, commands, fallback, code, output):
        """Through the task graph, and the command line a job's task becomes."""
        from odatix.lib.parallel_job_handler import ParallelJobHandler

        maker = wosit.createTaskGraph([{"name": "main", "commands": commands, "on_failure_commands": fallback}])
        stages = maker.getStages(name="main", max_process=1)
        (task,) = [task for tasks in stages.values() for task in tasks]
        line = ParallelJobHandler._task_full_command(task)

        result = subprocess.run(line, shell=True, cwd=str(tmp_path), stdout=subprocess.PIPE, universal_newlines=True)
        assert (result.returncode, result.stdout) == (code, output)

    def test_workflow_placeholders_are_substituted_in_the_fallback(self):
        import odatix.components.run_workflow as run_workflow

        tasks = run_workflow._resolve_workflow_tasks(
            [{"name": "main", "commands": ["run ${n}"], "on_failure_commands": ["retry ${n}"]}],
            {"n": "4"},
        )
        assert tasks[0]["on_failure_commands"] == ["retry 4"]


@pytest.mark.skipif(sys.platform == "win32", reason="select() on stdin is POSIX-only")
def test_quit_key_wait_returns_on_stdin_at_end_of_file(monkeypatch):
    # A server started in the background has stdin on /dev/null: waiting for
    # 'q' there must hand over to the server thread, not spin a core polling EOF.
    import threading
    from odatix.lib import term_mode

    read_end, write_end = os.pipe()
    os.close(write_end)
    stdin = os.fdopen(read_end, "r")
    monkeypatch.setattr(sys, "stdin", stdin)
    server = threading.Thread(target=lambda: None)
    server.start()
    quits = []

    term_mode.wait_for_quit_key(lambda: quits.append(True), server)

    stdin.close()
    assert quits == []
    assert not server.is_alive()


@pytest.mark.skipif(sys.platform == "win32", reason="terminal modes are POSIX-only")
def test_raw_mode_leaves_a_stdin_that_is_not_a_terminal_alone(monkeypatch):
    # odatix-gui started in the background, without -N, stopped on
    # "termios.error: Inappropriate ioctl for device".
    from odatix.lib import term_mode

    with open(os.devnull, encoding="utf-8") as devnull:
        monkeypatch.setattr(sys, "stdin", devnull)
        assert not term_mode.has_terminal()
        assert term_mode.set_raw_mode() is None
        # And it does not tell to press a key nobody can press.
        assert "press" not in term_mode.quit_hint(False)
        assert "end the process" in term_mode.quit_hint(True)
