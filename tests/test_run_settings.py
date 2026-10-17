"""Tests for odatix.lib.run_settings (job settings files) and odatix.lib.settings."""

import os
import textwrap

import pytest

from odatix.lib.run_settings import (
    get_synth_settings,
    get_sim_settings,
    get_workflow_settings,
    DEFAULT_EXIT_WHEN_DONE,
    DEFAULT_LOG_SIZE_LIMIT,
)
from odatix.lib.settings import OdatixSettings


######################################
# run_settings
######################################

SYNTH_YAML = """\
overwrite: false
ask_continue: true
nb_jobs: 4
architectures:
  - arch1/cfg1
  - arch2/cfg2
"""


class TestGetSynthSettings:
    def test_full_file(self, tmp_path):
        f = tmp_path / "s.yml"
        f.write_text(SYNTH_YAML + "exit_when_done: true\nlog_size_limit: 50\n")
        overwrite, ask, exit_done, log_limit, jobs, archs = get_synth_settings(str(f))
        assert overwrite is False
        assert ask is True
        assert exit_done is True
        assert log_limit == 50
        assert jobs == 4
        assert archs == ["arch1/cfg1", "arch2/cfg2"]

    def test_optional_keys_default(self, tmp_path):
        f = tmp_path / "s.yml"
        f.write_text(SYNTH_YAML)
        _, _, exit_done, log_limit, _, _ = get_synth_settings(str(f))
        assert exit_done == DEFAULT_EXIT_WHEN_DONE
        assert log_limit == DEFAULT_LOG_SIZE_LIMIT

    def test_missing_mandatory_key_exits(self, tmp_path):
        f = tmp_path / "s.yml"
        f.write_text("overwrite: false\n")
        with pytest.raises(SystemExit):
            get_synth_settings(str(f))

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            get_synth_settings(str(tmp_path / "missing.yml"))

    def test_none_filename_exits(self):
        with pytest.raises(SystemExit):
            get_synth_settings(None)

    def test_bad_type_exits(self, tmp_path):
        f = tmp_path / "s.yml"
        f.write_text("overwrite: 12\nask_continue: true\nnb_jobs: 1\narchitectures: []\n")
        with pytest.raises(SystemExit):
            get_synth_settings(str(f))


class TestGetSimAndWorkflowSettings:
    def test_sim_settings(self, tmp_path):
        f = tmp_path / "s.yml"
        f.write_text("overwrite: true\nask_continue: false\nnb_jobs: 2\nsimulations: [sim1]\n")
        overwrite, ask, _, _, jobs, sims = get_sim_settings(str(f))
        assert overwrite is True
        assert jobs == 2
        assert sims == ["sim1"]

    def test_workflow_settings(self, tmp_path):
        f = tmp_path / "s.yml"
        f.write_text("overwrite: false\nask_continue: false\nnb_jobs: 8\nworkflows: [wf1, wf2]\n")
        _, _, _, _, jobs, workflows = get_workflow_settings(str(f))
        assert jobs == 8
        assert workflows == ["wf1", "wf2"]


######################################
# OdatixSettings
######################################

class TestOdatixSettings:
    def test_missing_settings_file_is_invalid(self, in_tmp_dir):
        settings = OdatixSettings(silent=True)
        assert not settings.valid
        assert not settings.settings_file_exists

    def test_example_workspace_is_valid(self, example_workspace):
        settings = OdatixSettings(silent=True)
        assert settings.settings_file_exists
        assert settings.valid
        assert settings.arch_path == "odatix_userconfig/architectures"

    def test_get_settings_file_dict_missing(self, in_tmp_dir):
        assert OdatixSettings.get_settings_file_dict("missing.yml") == {}

    def test_get_settings_file_dict_empty_file(self, tmp_path):
        f = tmp_path / "odatix.yml"
        f.write_text("")
        assert OdatixSettings.get_settings_file_dict(str(f)) == {}

    def test_get_settings_file_dict_not_a_mapping(self, tmp_path):
        f = tmp_path / "odatix.yml"
        f.write_text("- a\n- b\n")
        assert OdatixSettings.get_settings_file_dict(str(f)) is None

    def test_to_dict_holds_every_path_setting(self, example_workspace):
        from odatix.workspace.core import PATH_SETTINGS

        settings = OdatixSettings(silent=True).to_dict()
        assert set(settings) == set(name for name, _default in PATH_SETTINGS)
        assert settings["gui_theme_path"] == OdatixSettings.DEFAULT_GUI_THEME_PATH

    def test_resource_guard_defaults_when_left_out(self):
        assert OdatixSettings.read_resource_guard({}) == (
            OdatixSettings.DEFAULT_RESOURCE_GUARD,
            OdatixSettings.DEFAULT_CPU_LIMIT,
            OdatixSettings.DEFAULT_MEM_LIMIT,
        )

    def test_resource_guard_reads_the_file(self):
        data = {"resource_guard": False, "cpu_limit": 80, "mem_limit": "90.5"}
        assert OdatixSettings.read_resource_guard(data) == (False, 80.0, 90.5)

    @pytest.mark.parametrize("data", [
        {"resource_guard": "maybe"},
        {"cpu_limit": 0},
        {"cpu_limit": 150},
        {"cpu_limit": "high"},
        {"mem_limit": True},
    ])
    def test_resource_guard_invalid_values_fall_back_on_defaults(self, data):
        assert OdatixSettings.read_resource_guard(data) == (
            OdatixSettings.DEFAULT_RESOURCE_GUARD,
            OdatixSettings.DEFAULT_CPU_LIMIT,
            OdatixSettings.DEFAULT_MEM_LIMIT,
        )


######################################
# Saving the workspace settings file
######################################

# Every path setting, an unknown key, comments and a quoted value: nothing
# here may move when the file is saved without being changed.
FULL_SETTINGS_FILE = """\
# My workspace, laid out my way
workspace: odatix

arch_path: archs  # where my designs are
sim_path: sims
workflow_path: flows
tools_path: my_tools
target_path: my_targets
gui_theme_path: 'themes'

# Settings files
clean_settings_file: cfg/clean.yml
simulation_settings_file: cfg/sim.yml
fmax_synthesis_settings_file: cfg/fmax.yml
custom_freq_synthesis_settings_file: cfg/freq.yml
pnr_settings_file: cfg/pnr.yml
analysis_settings_file: cfg/analysis.yml
workflow_settings_file: cfg/workflow.yml
dse_settings_file: cfg/dse.yml
dse_campaign_path: campaigns
derived_metrics_file: cfg/derived.yml

work_path: w
simulation_work_path: s
fmax_synthesis_work_path: f
custom_freq_synthesis_work_path: c
pnr_work_path: p
analysis_work_path: a
workflow_work_path: wf
result_path: res
use_benchmark: false
benchmark_file: res/bench.yml

my_own_key: [1, 2]  # a key Odatix does not know
"""


class TestSaveWorkspaceSettings:
    def write(self, tmp_path, text=FULL_SETTINGS_FILE):
        path = tmp_path / "odatix.yml"
        path.write_text(text)
        return str(path)

    def test_a_save_that_changes_nothing_leaves_the_file_identical(self, tmp_path):
        path = self.write(tmp_path)
        OdatixSettings.save_dict_to_file({}, path)
        assert open(path).read() == FULL_SETTINGS_FILE

    def test_saving_what_the_gui_holds_leaves_the_file_identical(self, tmp_path, monkeypatch):
        # The GUI saves every field of its form, resolved values included.
        path = self.write(tmp_path)
        monkeypatch.chdir(str(tmp_path))
        OdatixSettings.save_dict_to_file(OdatixSettings(silent=True).to_dict(), path)
        assert open(path).read() == FULL_SETTINGS_FILE

    def test_only_the_changed_key_moves(self, tmp_path):
        path = self.write(tmp_path)
        OdatixSettings.save_dict_to_file({"sim_path": "other_sims"}, path)
        assert open(path).read() == FULL_SETTINGS_FILE.replace("sim_path: sims", "sim_path: other_sims")

    def test_an_empty_setting_is_removed_so_that_the_default_applies(self, tmp_path):
        path = self.write(tmp_path)
        OdatixSettings.save_dict_to_file({"tools_path": "", "work_path": None}, path)
        text = open(path).read()
        assert "tools_path" not in text
        assert "work_path: w\n" not in text
        assert "my_own_key: [1, 2]  # a key Odatix does not know" in text
        assert OdatixSettings(path, silent=True).tools_path == OdatixSettings.DEFAULT_TOOLS_PATH

    def test_a_new_file_is_generated_with_its_sections(self, tmp_path):
        path = str(tmp_path / "odatix.yml")
        OdatixSettings.save_dict_to_file({"arch_path": "archs", "work_path": "", "result_path": "res"}, path)
        text = open(path).read()
        assert "# Odatix Workspace Settings" in text
        assert "workspace: odatix" in text
        assert "# Main paths\narch_path: archs" in text
        assert "# Results\nresult_path: res" in text
        assert "work_path" not in text

    def test_workspace_save_settings_uses_the_same_writer(self, tmp_path):
        from odatix.workspace import Workspace

        self.write(tmp_path)
        workspace = Workspace.open(str(tmp_path))
        workspace.save_settings(arch_path="new_archs")
        # The end-of-line comment follows its (longer) value by one column.
        assert open(str(tmp_path / "odatix.yml")).read() == FULL_SETTINGS_FILE.replace(
            "arch_path: archs  #", "arch_path: new_archs #"
        )
        assert workspace.paths.arch_path == os.path.join(str(tmp_path), "new_archs")
