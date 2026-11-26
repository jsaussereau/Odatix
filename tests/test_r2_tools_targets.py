"""Regression tests of the 2nd new-user pass, tools/targets domain."""
import os
import subprocess
import sys

import dash
import pytest

import odatix.lib.check_tool as check_tool
import odatix.lib.eda_tools as eda_tools


@pytest.fixture(scope="module")
def select_targets():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.select_targets as module
    return module


def test_new_card_marks_dirty_without_writing(select_targets):
    meta = [select_targets.card_metadata({"name": "a"}), select_targets.card_metadata(None, new=True)]
    assert select_targets.targets_changed(["a", "b"], [[True], [True]], [[], []], ["", ""], meta, ["a"])
    clean = [select_targets.card_metadata({"name": "a"})]
    assert not select_targets.targets_changed(["a"], [[True]], [[]], [""], clean, ["a"])
    # a removed card
    assert select_targets.targets_changed([], [], [], [], [], ["a"])


def test_save_refuses_duplicate_or_empty_names(select_targets):
    meta = [select_targets.card_metadata({"name": "a"})] * 2
    with pytest.raises(ValueError):
        select_targets.targets_to_save(["a", "a"], [[True]] * 2, [[]] * 2, ["", ""], meta)
    with pytest.raises(ValueError):
        select_targets.targets_to_save([""], [[True]], [[]], [""], meta[:1])


def test_duplicate_carries_source_settings(select_targets):
    meta = [select_targets.card_metadata(None, new=True, source="xc7")]
    out = select_targets.targets_to_save(["xc7_copy1"], [[True]], [[]], [""], meta)
    assert out[0]["original_name"] == "xc7"


def test_replayed_clicks_are_ignored(select_targets):
    assert select_targets.is_new_click(10, 5)
    assert not select_targets.is_new_click(5, 5)
    assert not select_targets.is_new_click(None, 0)


def test_install_path_hint():
    assert "qinit.sh" in eda_tools.install_path_hint("quartus")


def test_install_path_comes_first_on_the_path(tmp_path):
    from odatix.lib.variables import install_path_dirs, with_install_path

    (tmp_path / "bin").mkdir()
    assert install_path_dirs(str(tmp_path)) == [str(tmp_path / "bin"), str(tmp_path)]
    # Empty or "/": the tool is on the PATH, the command is left as is
    assert with_install_path("tool -v", "") == "tool -v"
    assert with_install_path("tool -v", "/") == "tool -v"
    if os.name == "nt":
        return
    # The installation wins over a tool of the same name on the PATH ("env")
    fake = tmp_path / "bin" / "env"
    fake.write_text("#!/bin/sh\nexit 7\n")
    fake.chmod(0o755)
    assert subprocess.call(with_install_path("env", str(tmp_path)), shell=True) == 7


def test_passed_check_is_cached():
    # Python commands: the same in sh and cmd.exe
    passing = '"{}" -c "pass"'.format(sys.executable)
    failing = '"{}" -c "import sys; print(\'boom\', file=sys.stderr); sys.exit(3)"'.format(sys.executable)
    check_tool.forget_passed_checks()
    assert check_tool.probe(passing) == (True, "")
    assert check_tool.recently_passed(passing)
    ok, reason = check_tool.probe(failing)
    assert ok is False and reason == "boom"
    check_tool.forget_passed_checks()


# What Synopsys tools print on stdout when they start: the banner speaks of
# licenses without anything being wrong.
SYNOPSYS_BANNER = """
  This software and the associated documentation are proprietary to Synopsys,
 of a written license agreement with Synopsys, Inc. All other use, reproduction,
   or distribution of this software is strictly prohibited.  Licensed Products
    Licensed Products in conformity with the applicable License Key for such
"""


@pytest.mark.parametrize("returncode, stderr, stdout, expected", [
    # Design Compiler without license: on stdout, nothing on stderr
    (255, "", SYNOPSYS_BANNER + "Fatal: Design Compiler is not enabled. (DCSH-1)\n",
     (check_tool.NO_LICENSE, "Fatal: Design Compiler is not enabled. (DCSH-1)")),
    # IC Compiler II / Fusion Compiler: not on the last line
    (1, "", SYNOPSYS_BANNER + "Unable to get shell start-up license keys. Cannot invoke shell.\n"
     "Thank you for using IC Compiler II.\n",
     (check_tool.NO_LICENSE, "Unable to get shell start-up license keys. Cannot invoke shell.")),
    (1, "ERROR: [Common 17-345] A valid license was not found for feature 'Synthesis'\n", "",
     (check_tool.NO_LICENSE, "ERROR: [Common 17-345] A valid license was not found for feature 'Synthesis'")),
    (127, "sh: line 1: dc_shell: command not found\n", "",
     (check_tool.NOT_INSTALLED, "sh: line 1: dc_shell: command not found")),
    (1, "'vivado' is not recognized as an internal or external command,\n", "",
     (check_tool.NOT_INSTALLED, "'vivado' is not recognized as an internal or external command,")),
    # The banner alone is no license failure
    (2, "", SYNOPSYS_BANNER + "Error: unknown option '-y'\n",
     (check_tool.FAILED, "Error: unknown option '-y'")),
    (3, "", "", (check_tool.FAILED, "exit code 3")),
])
def test_failed_check_says_why(returncode, stderr, stdout, expected):
    assert check_tool.classify_failure(returncode, stderr, stdout) == expected


def test_probe_and_tool_check_see_a_license_failure_on_stdout():
    command = '"{}" -c "print(\'Fatal: Design Compiler is not enabled. (DCSH-1)\'); raise SystemExit(255)"'.format(sys.executable)
    check_tool.forget_passed_checks()
    assert check_tool.probe_status(command) == (check_tool.NO_LICENSE, "Fatal: Design Compiler is not enabled. (DCSH-1)")
    assert check_tool.probe(command)[0] is False
    check = check_tool.ToolCheck("design_compiler", command, [], "")
    assert check.failure()[0] == check_tool.NO_LICENSE
    assert "no license" in check.failure_message()
    check_tool.forget_passed_checks()
