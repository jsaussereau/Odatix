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
Layered metrics of an eda tool (odatix.lib.metrics).

A workspace "metrics.yml" completes or overrides the metrics shipped with a
built-in tool, without copying its whole definition. These tests cover the merge
itself (add / replace / remove), the files it is built from, and the two layers
the GUI metrics editor shows.
"""

import textwrap

import pytest

import odatix.lib.eda_tools as eda_tools
import odatix.lib.metrics as metrics_lib
from odatix.lib.settings import OdatixSettings


@pytest.fixture
def tools_dirs(tmp_path, monkeypatch):
    """
    A built-in tools directory and a workspace one, both empty, standing in for
    the directories Odatix ships and the workspace holds.
    """
    builtin_dir = tmp_path / "builtin"
    user_dir = tmp_path / "tools"
    builtin_dir.mkdir()
    user_dir.mkdir()
    monkeypatch.setattr(OdatixSettings, "odatix_eda_tools_path", str(builtin_dir))
    monkeypatch.setattr(OdatixSettings, "user_tools_path", str(user_dir))
    monkeypatch.setattr(eda_tools, "platform_key", lambda: "unix")
    return builtin_dir, user_dir


def write_builtin_tool(builtin_dir, name="acme"):
    tool_dir = builtin_dir / name
    tool_dir.mkdir(parents=True, exist_ok=True)
    (tool_dir / "tool.yml").write_text(
        textwrap.dedent(
            """\
            default_metrics_file: $tool_path/metrics.yml
            unix:
              tool_test_command: true
              fmax_synthesis_command: run_fmax
            """
        )
    )
    (tool_dir / "metrics.yml").write_text(
        textwrap.dedent(
            """\
            fmax_synthesis_metrics:
              Fmax:
                type: regex
                settings:
                  file: log/fmax.log
                  pattern: "([0-9]+) MHz"
                  group_id: 1
                unit: MHz

            metrics:
              Area:
                type: regex
                settings:
                  file: report/area.rep
                  pattern: "area ([0-9.]+)"
                  group_id: 1
              Power:
                type: regex
                settings:
                  file: report/power.rep
                  pattern: "power ([0-9.]+)"
                  group_id: 1
            """
        )
    )
    return tool_dir


def write_workspace_metrics(user_dir, content, name="acme"):
    tool_dir = user_dir / name
    tool_dir.mkdir(parents=True, exist_ok=True)
    path = tool_dir / "metrics.yml"
    path.write_text(textwrap.dedent(content))
    return path


class TestMergeMetricsData:
    def test_a_new_metric_is_added(self):
        merged = metrics_lib.merge_metrics_data(
            {"metrics": {"Area": {"type": "regex"}}},
            {"metrics": {"Mine": {"type": "operation"}}},
        )
        assert sorted(merged["metrics"]) == ["Area", "Mine"]

    def test_a_metric_of_the_same_name_is_replaced_whole(self):
        merged = metrics_lib.merge_metrics_data(
            {"metrics": {"Area": {"type": "regex", "unit": "um2", "settings": {"file": "a"}}}},
            {"metrics": {"Area": {"type": "operation", "settings": {"op": "1"}}}},
        )
        # Not merged key by key: a half-overridden definition would be a trap.
        assert merged["metrics"]["Area"] == {"type": "operation", "settings": {"op": "1"}}

    def test_an_empty_entry_removes_the_metric(self):
        merged = metrics_lib.merge_metrics_data(
            {"metrics": {"Area": {"type": "regex"}, "Power": {"type": "regex"}}},
            {"metrics": {"Power": None}},
        )
        assert list(merged["metrics"]) == ["Area"]

    def test_removing_a_metric_that_does_not_exist_is_harmless(self):
        merged = metrics_lib.merge_metrics_data({"metrics": {}}, {"metrics": {"Ghost": None}})
        assert merged["metrics"] == {}

    def test_sections_are_independent(self):
        merged = metrics_lib.merge_metrics_data(
            {"metrics": {"Area": {"type": "regex"}}, "fmax_synthesis_metrics": {"Fmax": {"type": "regex"}}},
            {"fmax_synthesis_metrics": {"Fmax": None}},
        )
        assert merged["metrics"] == {"Area": {"type": "regex"}}
        assert merged["fmax_synthesis_metrics"] == {}


class TestMetricsFiles:
    def test_a_lone_workspace_metrics_file_is_used(self, tools_dirs):
        builtin_dir, user_dir = tools_dirs
        write_builtin_tool(builtin_dir)
        # No tool.yml next to it: dropping the single file is enough.
        overlay = write_workspace_metrics(user_dir, "metrics: {}\n")

        files = metrics_lib.metrics_files("acme")
        assert files == [str(builtin_dir / "acme" / "metrics.yml"), str(overlay)]

    def test_the_builtin_file_alone_when_the_workspace_says_nothing(self, tools_dirs):
        builtin_dir, _user_dir = tools_dirs
        write_builtin_tool(builtin_dir)
        assert metrics_lib.metrics_files("acme") == [str(builtin_dir / "acme" / "metrics.yml")]

    def test_an_unknown_tool_has_no_metrics_file(self, tools_dirs):
        assert metrics_lib.metrics_files("nope") == []


class TestLoadMetrics:
    def test_the_workspace_completes_and_overrides_the_builtin_metrics(self, tools_dirs):
        builtin_dir, user_dir = tools_dirs
        write_builtin_tool(builtin_dir)
        write_workspace_metrics(
            user_dir,
            """\
            metrics:
              Power:
              Area:
                type: operation
                settings:
                  op: 42
              Mine:
                type: regex
                settings:
                  file: log/mine.log
                  pattern: "mine ([0-9]+)"
                  group_id: 1
            """,
        )

        data, source = metrics_lib.load_metrics("acme")

        assert sorted(data["metrics"]) == ["Area", "Mine"]          # Power removed
        assert data["metrics"]["Area"]["type"] == "operation"        # overridden
        assert data["metrics"]["Mine"]["type"] == "regex"            # added
        assert "Fmax" in data["fmax_synthesis_metrics"]              # untouched section
        assert str(user_dir) in source

    def test_an_explicit_metrics_file_replaces_everything(self, tools_dirs, tmp_path):
        builtin_dir, user_dir = tools_dirs
        write_builtin_tool(builtin_dir)
        write_workspace_metrics(user_dir, "metrics:\n  Mine:\n    type: operation\n")
        custom = tmp_path / "custom.yml"
        custom.write_text("metrics:\n  Only:\n    type: operation\n    settings:\n      op: 1\n")

        data, source = metrics_lib.load_metrics("acme", custom_metrics_file=str(custom))

        assert list(data["metrics"]) == ["Only"]
        assert "fmax_synthesis_metrics" not in data
        assert source == str(custom)

    def test_a_missing_explicit_metrics_file_is_an_error(self, tools_dirs, tmp_path):
        builtin_dir, _user_dir = tools_dirs
        write_builtin_tool(builtin_dir)
        assert metrics_lib.load_metrics("acme", custom_metrics_file=str(tmp_path / "nope.yml")) == (None, None)


class TestLoadMetricsLayers:
    def test_the_two_layers_are_kept_apart(self, tools_dirs):
        builtin_dir, user_dir = tools_dirs
        write_builtin_tool(builtin_dir)
        write_workspace_metrics(
            user_dir,
            """\
            metrics:
              Power:
              Mine:
                type: operation
                settings:
                  op: 1
            """,
        )

        builtin, workspace = metrics_lib.load_metrics_layers("acme")

        # The built-in layer is what Odatix ships, untouched by the workspace.
        assert sorted(builtin["metrics"]) == ["Area", "Power"]
        # The workspace layer keeps the removal as an empty entry, so the editor
        # can show it as a removed metric rather than losing it.
        assert workspace["metrics"] == {"Power": None, "Mine": {"type": "operation", "settings": {"op": 1}}}
        assert workspace["fmax_synthesis_metrics"] == {}

    def test_every_section_is_present_even_when_empty(self, tools_dirs):
        builtin_dir, _user_dir = tools_dirs
        write_builtin_tool(builtin_dir)
        builtin, workspace = metrics_lib.load_metrics_layers("acme")
        for key in metrics_lib.METRIC_SECTION_KEYS:
            assert key in builtin and key in workspace
