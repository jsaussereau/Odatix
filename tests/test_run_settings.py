"""Tests for odatix.lib.run_settings (job settings files) and odatix.lib.settings."""

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

    def test_get_settings_template_dict_defaults(self):
        template = OdatixSettings.get_settings_template_dict(settings={})
        assert "arch_path" in template
        assert "work_path" in template
