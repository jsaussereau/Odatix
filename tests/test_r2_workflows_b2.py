"""Non-regression tests of lot B2 (workflows, metric editor, editors layout)."""

import os

import pytest

from odatix.lib import run_report
from odatix.lib.run_report import Category
import odatix.workspace.selection as selection

pytest.importorskip("dash")


def _make_entries(root, names):
    for name in names:
        os.makedirs(os.path.join(str(root), name, "default"))


class TestMissingEntry:
    """WF-06 / GS-17: a mistyped entry is named after its kind, with suggestions."""

    def test_workflow_wording_and_suggestion(self, tmp_path):
        root = tmp_path / "workflows"
        _make_entries(root, ["basic", "cli_profile"])
        messages = []
        assert selection.expand(["basci/*"], str(root), messages=messages) == []
        assert [message.level for message in messages] == ["error"]
        assert 'The workflow directory' in messages[0].text
        assert 'Did you mean "basic"?' in messages[0].hints
        assert "Available workflows: basic, cli_profile" in messages[0].hints

    def test_architecture_wording(self, tmp_path):
        root = tmp_path / "architectures"
        _make_entries(root, ["Counter"])
        messages = []
        selection.expand(["Countr/*"], str(root), messages=messages)
        assert "The architecture directory" in messages[0].text
        assert 'Did you mean "Counter"?' in messages[0].hints


class TestResumeWording:
    """WF-15: a workflow does not resume at a step, it runs again."""

    def test_workflows_say_they_run_again(self):
        text = run_report.category_description(Category.RESUME, "workflows")
        assert "run again" in text and "step" not in text

    def test_architectures_keep_the_step_wording(self):
        assert "first missing step" in run_report.category_description(Category.RESUME, "architectures")


class TestMetricEditor:
    @pytest.fixture
    def editor(self):
        import dash
        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")
        from odatix.gui.pages import metric_editor
        return metric_editor

    def test_duplicate_and_empty_names_are_shown_on_the_card(self, editor):
        # WF-18
        assert editor.name_errors(["a", "b", "a", " "], "metric") == [
            "", "", "Duplicate metric name: 'a'", "The metric name cannot be empty",
        ]

    def test_noun(self, editor):
        assert editor.item_noun(editor.META_PREFIX, "workflow") == "metadata dimension"
        assert editor.item_noun(editor.META_PREFIX, "tool") == "metric"
        assert editor.item_noun(editor.METRIC_PREFIX, "workflow") == "metric"

    def test_tool_cards_hide_multiple_values(self, editor):
        # TF-13: the switch stays (callbacks stay aligned), hidden.
        card = str(editor.metric_card(editor.METRIC_PREFIX, "m", with_multiple=False))
        assert "Multiple values" in card
        assert "'display': 'none'" in card
        shown = str(editor.metric_card(editor.METRIC_PREFIX, "m"))
        assert "'display': 'inline'" in shown

    def test_template_metrics_are_inherited(self, editor, tmp_path):
        # SIM-109: a simulation starting from the ghdl template shows its metrics.
        sim = tmp_path / "sims" / "tb"
        sim.mkdir(parents=True)
        (sim / "_settings.yml").write_text("template: ghdl\n")
        inherited = editor._template_metrics("tb", str(tmp_path / "sims"))
        assert "sim_status" in inherited["metrics"]

    def test_no_template_inherits_nothing(self, editor, tmp_path):
        inherited = editor._template_metrics("nope", str(tmp_path))
        assert inherited == {"metrics": {}, "metadata": {}}


def test_editors_use_flex_columns():
    # .tiles-container.config is multicol: the workflow and tool editor forms
    # are flex columns instead.
    here = os.path.dirname(os.path.abspath(__file__))
    pages = os.path.join(here, "..", "sources", "odatix", "gui", "pages")
    for name in ("workflow_editor.py", "tool_editor.py"):
        with open(os.path.join(pages, name)) as f:
            text = f.read()
        assert 'className="tiles-container config",\n        style=' not in text, name
        assert "flex-form-column" in text
    with open(os.path.join(pages, "..", "assets", "style.css")) as f:
        assert ".tiles-container.config.flex-form" in f.read()
