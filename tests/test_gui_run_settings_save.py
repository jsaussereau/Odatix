"""
"Save all" on a run page of the GUI: the run settings file is updated the way
its author would edit it, never regenerated. Its comments, and the catalogue of
commented-out examples the tutorials ask to uncomment, survive a save.
"""

import os
import shutil

import pytest

from odatix.gui.jobs_config import prepare_state
from odatix.gui.jobs_config.settings_io import (
    _edit_selection_text,
    _write_temp_run_settings,
    write_run_settings,
)
from odatix.workspace.yaml_io import read_yaml

from conftest import EXAMPLES_DIR


SETTINGS = """\
# overwrite existing results
overwrite:        No   # overridden by -o / --overwrite
ask_continue:     Yes
nb_jobs:          8

# targeted architectures
architectures:

#--------------------------------------------#
# Add your own architectures!
#--------------------------------------------#

  #- Your_Design/Your_1st_Configuration

  - Counter/04bits # fails with openlane
  - Counter/08bits

  # - ALU/04bits
  # - ALU/08bits # slow
"""


class TestSelectionText:
    def test_an_entry_no_longer_selected_is_commented_out_in_place(self):
        text = _edit_selection_text(SETTINGS, "architectures", ["Counter/08bits"])
        assert "  # - Counter/04bits # fails with openlane\n" in text
        assert "  - Counter/08bits\n" in text

    def test_a_commented_out_entry_selected_again_is_uncommented_in_place(self):
        text = _edit_selection_text(SETTINGS, "architectures", ["Counter/04bits", "ALU/08bits"])
        assert "  - ALU/08bits # slow\n" in text
        assert "  # - ALU/04bits\n" in text
        assert text.index("ALU/08bits") > text.index("ALU/04bits")

    def test_an_entry_the_file_never_mentioned_goes_after_the_last_selected_one(self):
        text = _edit_selection_text(SETTINGS, "architectures", ["Counter/08bits", "Mult/*"])
        assert "  - Counter/08bits\n  - Mult/*\n" in text

    def test_a_new_entry_goes_next_to_the_entries_of_its_architecture(self):
        # What the GUI writes when every configuration of a design is selected.
        text = _edit_selection_text(SETTINGS, "architectures", ["Counter/08bits", "ALU/*"])
        assert "  - ALU/*\n  # - ALU/04bits\n" in text

    def test_new_entries_keep_their_order(self):
        text = _edit_selection_text(SETTINGS, "architectures", ["Counter/08bits", "Mult/a", "Mult/b"])
        assert "  - Counter/08bits\n  - Mult/a\n  - Mult/b\n" in text

    def test_the_comments_stay(self):
        text = _edit_selection_text(SETTINGS, "architectures", [])
        for line in ("# Add your own architectures!", "  #- Your_Design/Your_1st_Configuration", "# targeted architectures"):
            assert line in text

    def test_an_inline_list_is_left_to_the_writer(self):
        assert _edit_selection_text("architectures: [a/b]\n", "architectures", ["c/d"]) is None


@pytest.mark.parametrize("filename, mode", [
    ("fmax_settings.yml", "fmax_synthesis"),
    ("synth_settings.yml", "custom_freq_synthesis"),
    ("analyze_settings.yml", "analyze"),
])
def test_save_all_keeps_the_comments_of_a_run_settings_file(tmp_path, filename, mode):
    path = str(tmp_path / filename)
    shutil.copy(os.path.join(EXAMPLES_DIR, "odatix_userconfig", filename), path)
    with open(path) as f:
        before = f.read()
    payload = dict(read_yaml(path, default={}))
    payload.update({"architectures": ["Example_Counter_verilog/08bits"], "nb_jobs": 3})

    write_run_settings(path, payload, mode)

    with open(path) as f:
        after = f.read()
    saved = read_yaml(path, default={})
    assert saved["architectures"] == ["Example_Counter_verilog/08bits"]
    assert saved["nb_jobs"] == 3
    body = before[before.index("\n---\n") + 5:]
    comments = [line.strip() for line in body.splitlines() if line.strip().startswith("#") and "Example_" not in line]
    for comment in comments:
        assert comment in after
    # The catalogue of examples stays, commented out.
    assert "# - Example_ALU_sv/" in after


def test_save_all_keeps_the_header_of_a_run_settings_file(tmp_path):
    path = str(tmp_path / "fmax_settings.yml")
    shutil.copy(os.path.join(EXAMPLES_DIR, "odatix_userconfig", "fmax_settings.yml"), path)
    payload = dict(read_yaml(path, default={}))
    payload["nb_jobs"] = 3
    write_run_settings(path, payload, "fmax_synthesis")
    with open(path) as f:
        assert "# Odatix settings for Fmax synthesis\n" in f.read()


def test_the_temporary_file_of_a_run_is_removed_once_used(tmp_path):
    settings_path = str(tmp_path / "fmax_settings.yml")
    shutil.copy(os.path.join(EXAMPLES_DIR, "odatix_userconfig", "fmax_settings.yml"), settings_path)
    temp_path = _write_temp_run_settings(
        settings_path, {"architectures": ["Example_Counter_verilog/08bits"]}, "fmax_synthesis", False, False,
    )
    try:
        assert read_yaml(temp_path, default={})["architectures"] == ["Example_Counter_verilog/08bits"]
        prepare_state._prepare_temp_settings_file = temp_path
        prepare_state._remove_temp_settings_file()
        assert not os.path.exists(temp_path)
        assert prepare_state._prepare_temp_settings_file is None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
