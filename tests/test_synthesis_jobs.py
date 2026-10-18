"""
Synthesis jobs as a first run meets them: where the tool runs, how the plan
names the jobs, which frequencies a fixed-frequency synthesis accepts, and what
a missing tool says.
"""

import argparse
import os
import re
import types

import pytest

import odatix.components.run_fixed_freq_synthesis as run_fixed_freq_synthesis
import odatix.components.synthesis_common as synthesis_common
import odatix.lib.check_tool as check_tool
from odatix.lib.run_report import Category

from test_handlers import TARGET, make_arch_handler


######################################
# Working directory of a job
######################################

def _arch_instance(tmp_dir):
    return types.SimpleNamespace(
        tmp_dir=tmp_dir,
        generate_rtl=False,
        generate_command="",
        target="xc7a100t-csg324-1",
        arch_name="Counter/08bits",
        arch_display_name="Counter/08bits",
    )


def test_a_synthesis_job_runs_from_its_own_directory():
    # Run from the workspace root, parallel Vivado jobs shared .Xil and their
    # journals there, and an "odatix clean" during a run broke them.
    tmp_dir = os.path.join("work", "fmax_synthesis", "vivado", "xc7a100t-csg324-1", "Counter", "08bits")
    job = synthesis_common.build_parallel_job(
        _arch_instance(tmp_dir), command="vivado -mode tcl", steps=None, resume_index=0,
        flow=None, log_size_limit=300, progress_mode="fmax",
    )
    assert job.directory == tmp_dir
    assert job.directory != "."


######################################
# The plan of a fixed-frequency synthesis
######################################

@pytest.mark.integration
class TestFixedFrequencyPlan:
    def _plan(self, state, overwrite=False):
        handler = make_arch_handler(work_path="work/custom_freq_synthesis", overwrite=overwrite)
        handler.classify_job = lambda tmp_dir, subject, job_noun="synthesis": (state, None)
        handler.get_architectures(["Example_Counter_verilog/04bits"], [TARGET], run_mode="custom_freq", timestamp="ts")
        return handler

    @pytest.mark.parametrize("state, category", [
        ("resume", Category.RESUME),
        ("overwrite", Category.OVERWRITE),
        ("new", Category.NEW),
    ])
    def test_every_job_names_its_frequency_once(self, example_workspace, state, category):
        names = self._plan(state).plan.names(category)
        # The example architecture runs at 50 and 100 MHz on this target.
        assert len(names) == 2
        for name, freq in zip(names, (50, 100)):
            assert name.count("MHz") == 1
            assert "@ {} MHz".format(freq) in name

    def test_the_plan_lists_jobs(self, example_workspace, capsys):
        self._plan("new").print_summary()
        out = capsys.readouterr().out
        assert "New jobs:" in out
        assert "New architectures" not in out


######################################
# Frequencies of a fixed-frequency synthesis
######################################

def _cli_args(**kwargs):
    values = dict(at_freq=None, from_freq=None, to_freq=None, step_freq=None, config=None)
    values.update(kwargs)
    return argparse.Namespace(**values)


@pytest.fixture
def no_run(monkeypatch):
    """Stop main() right before it would run, keeping what it was asked to run."""
    asked = {}

    def fake_execute(command):
        asked["command"] = command
        raise SystemExit(0)

    monkeypatch.setattr(run_fixed_freq_synthesis.run_cli, "execute", fake_execute)
    monkeypatch.setattr(run_fixed_freq_synthesis.run_cli, "command_run", lambda *a, **k: k["options"])
    monkeypatch.setattr(run_fixed_freq_synthesis.run_cli, "command_workspace", lambda *a, **k: None)
    monkeypatch.setattr(run_fixed_freq_synthesis.RunOptions, "from_namespace", staticmethod(lambda args, frequencies: frequencies))
    return asked


class TestFrequencyOptions:
    @pytest.mark.parametrize("kwargs", [
        dict(from_freq=100, to_freq=300, step_freq=0),
        dict(from_freq=100, to_freq=300, step_freq=-50),
        dict(from_freq=0, to_freq=300, step_freq=50),
        dict(at_freq=[-5]),
        dict(at_freq=[100, 0]),
    ])
    def test_a_frequency_that_cannot_run_is_refused(self, no_run, capsys, kwargs):
        with pytest.raises(SystemExit) as exit_info:
            run_fixed_freq_synthesis.main(_cli_args(**kwargs))
        assert exit_info.value.code not in (0, None)
        assert "command" not in no_run
        assert "positive" in capsys.readouterr().out

    def test_a_partial_range_names_what_is_missing(self, no_run, capsys):
        with pytest.raises(SystemExit):
            run_fixed_freq_synthesis.main(_cli_args(from_freq=100, to_freq=300))
        out = capsys.readouterr().out
        assert "--step is missing" in out
        assert "--to cannot be used" not in out

    def test_a_valid_range_runs(self, no_run):
        with pytest.raises(SystemExit) as exit_info:
            run_fixed_freq_synthesis.main(_cli_args(at_freq=[50], from_freq=100, to_freq=200, step_freq=50))
        assert exit_info.value.code == 0
        assert no_run["command"] == [50, 100, 150, 200]

    @pytest.mark.parametrize("frequencies", [
        "  list: [50, -5]\n",
        "  range:\n    from: 100\n    to: 300\n    step: 0\n",
    ])
    def test_the_settings_file_is_checked_the_same_way(self, tmp_path, frequencies):
        settings = tmp_path / "synth_settings.yml"
        settings.write_text("frequencies:\n" + frequencies)
        with pytest.raises(SystemExit):
            run_fixed_freq_synthesis._load_settings_custom_frequencies(str(settings))


######################################
# A tool that cannot be launched
######################################

class TestToolCheckFailure:
    def _failure(self, capsys, tool, message):
        with pytest.raises(SystemExit):
            check_tool._print_check_failure(tool, [tool], message, debug=False)
        return re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)

    def test_the_message_of_the_tool_ends_its_line(self, capsys):
        out = self._failure(capsys, "quartus", "error: quartus_sh not found")
        assert "quartus_sh not found\n" in out

    def test_a_tool_explaining_itself_gets_no_generic_hint(self, capsys):
        out = self._failure(capsys, "quartus", "error: quartus_sh not found\nnote: set tool_install_path")
        assert "PATH=$PATH" not in out
        assert "Vivado" not in out

    def test_the_generic_hint_names_the_tool(self, capsys):
        out = self._failure(capsys, "genus", "genus: command not found")
        assert "Vivado" not in out
        assert "installation directory of genus" in out


def test_a_target_not_enabled_says_how_to_enable_it(capsys):
    with pytest.raises(SystemExit):
        synthesis_common.restrict_targets(["xc7a100t-csg324-1"], ["xc7s25-csga225-1"], "vivado", "target_vivado.yml")
    out = capsys.readouterr().out
    assert "xc7a100t-csg324-1" in out
    assert "uncomment" in out
