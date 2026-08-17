# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
Where "param_target_file" is read from.

The path is written by the user against the sources, which is also what the
architecture editor previews it against:

  - generating the RTL: relative to "design_path", copied whole at the root of
    the work directory;
  - otherwise: relative to "rtl_path", copied into the "rtl" subfolder of the
    work directory.

So the job has to add that "rtl" subfolder itself, and only in the second case.
Getting this wrong makes a preview of a configuration that the job then fails
to start on, or the other way around.
"""

import os

import pytest
import yaml

import odatix.lib.architecture_handler as architecture_handler
import odatix.lib.hard_settings as hard_settings
from odatix.components.run_common import resolve_param_target_file

TOP_LEVEL = "top_level.sv"
TOP_LEVEL_SOURCE = "module top_level(input clock, input reset);\nendmodule\n"


def write_architecture(root, settings, config="config"):
    """A minimal architecture on disk, and the handler reading it."""
    arch_path = os.path.join(root, "architectures")
    arch_dir = os.path.join(arch_path, "counter")
    os.makedirs(arch_dir)
    with open(os.path.join(arch_dir, "_settings.yml"), "w") as settings_file:
        yaml.dump(settings, settings_file)
    with open(os.path.join(arch_dir, config + ".txt"), "w") as param_file:
        param_file.write("parameter WIDTH = 8;\n")

    handler = architecture_handler.ArchitectureHandler(
        work_path=os.path.join(root, "work"),
        arch_path=arch_path,
        script_path=os.path.join(root, "scripts"),
        log_path="log",
        work_rtl_path=hard_settings.work_rtl_path,
        work_script_path="script",
        work_log_path="log",
        work_report_path="report",
        process_group=True,
        command="",
        eda_target_filename="target.yml",
        fmax_status_filename="fmax_status.log",
        frequency_search_filename="frequency_search.log",
        param_settings_filename="_settings.yml",
        valid_status="Done",
        valid_frequency_search="Done",
        forced_fmax_lower_bound=None,
        forced_fmax_upper_bound=None,
        forced_custom_freq_list=None,
        overwrite=True,
    )
    return handler.get_architecture("counter/" + config)


@pytest.fixture
def rtl_dir(tmp_path):
    rtl_path = tmp_path / "rtl"
    rtl_path.mkdir()
    (rtl_path / TOP_LEVEL).write_text(TOP_LEVEL_SOURCE)
    return rtl_path


class TestDefaultTargetFile:
    def test_it_is_relative_to_the_rtl_path(self, tmp_path, rtl_dir):
        """
        Left unset, the target file is the top level, named the way the user
        would have named it: relative to "rtl_path", without the work
        subfolder the job copies it into.
        """
        arch = write_architecture(
            str(tmp_path),
            {
                "rtl_path": str(rtl_dir),
                "top_level_file": TOP_LEVEL,
                "top_level_module": "top_level",
                "clock_signal": "clock",
                "reset_signal": "reset",
                "use_parameters": True,
                "start_delimiter": "/* start */",
                "stop_delimiter": "/* stop */",
            },
        )
        assert arch is not None
        assert arch.param_target_filename == TOP_LEVEL

    def test_generating_the_rtl_it_is_relative_to_the_work_directory(self, tmp_path):
        """
        A generated top level is not in the sources at all: it is wherever the
        generation command writes it, under the root of the work directory.
        """
        arch = write_architecture(
            str(tmp_path),
            {
                "generate_rtl": True,
                "generate_command": "true",
                "generate_output": "generated",
                "top_level_file": TOP_LEVEL,
                "top_level_module": "top_level",
                "clock_signal": "clock",
                "reset_signal": "reset",
                "use_parameters": True,
                "start_delimiter": "/* start */",
                "stop_delimiter": "/* stop */",
            },
        )
        assert arch is not None
        assert arch.param_target_filename == os.path.join("generated", TOP_LEVEL)


class TestJobResolution:
    def test_it_reads_the_file_copied_into_the_rtl_subfolder(self, tmp_path, rtl_dir):
        """
        The bug: a target file written against "rtl_path" (what the preview
        shows) was looked up at the root of the work directory, where the RTL
        never is.
        """
        work_dir = tmp_path / "work"
        (work_dir / hard_settings.work_rtl_path).mkdir(parents=True)
        (work_dir / hard_settings.work_rtl_path / TOP_LEVEL).write_text(TOP_LEVEL_SOURCE)

        resolved = resolve_param_target_file(str(work_dir), TOP_LEVEL, generate_rtl=False)

        assert os.path.isfile(resolved)
        assert resolved == os.path.join(str(work_dir), hard_settings.work_rtl_path, TOP_LEVEL)

    def test_generating_the_rtl_it_reads_from_the_work_directory_root(self, tmp_path):
        """
        The design path is copied whole at the root, so nothing is added.
        """
        work_dir = tmp_path / "work"
        (work_dir / "generated").mkdir(parents=True)
        (work_dir / "generated" / TOP_LEVEL).write_text(TOP_LEVEL_SOURCE)

        resolved = resolve_param_target_file(
            str(work_dir), os.path.join("generated", TOP_LEVEL), generate_rtl=True
        )

        assert os.path.isfile(resolved)
        assert resolved == os.path.join(str(work_dir), "generated", TOP_LEVEL)

    def test_the_preview_and_the_job_read_the_same_file(self, tmp_path, rtl_dir):
        """
        The invariant the two sides have to agree on: a target file relative to
        "rtl_path" in the sources is the same file, once copied, as the one the
        job replaces the parameters in.
        """
        target = os.path.join("core", "counter.sv")
        (rtl_dir / "core").mkdir()
        (rtl_dir / "core" / "counter.sv").write_text("module counter;\nendmodule\n")

        preview_file = os.path.join(str(rtl_dir), target)

        work_dir = tmp_path / "work"
        os.makedirs(str(work_dir / hard_settings.work_rtl_path / "core"))
        (work_dir / hard_settings.work_rtl_path / "core" / "counter.sv").write_text("module counter;\nendmodule\n")
        job_file = resolve_param_target_file(str(work_dir), target, generate_rtl=False)

        assert os.path.isfile(preview_file)
        assert os.path.isfile(job_file)
        assert os.path.relpath(job_file, os.path.join(str(work_dir), hard_settings.work_rtl_path)) == os.path.relpath(
            preview_file, str(rtl_dir)
        )
