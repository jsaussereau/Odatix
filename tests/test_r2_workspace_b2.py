"""Non-regression tests of the 2nd "new user" pass, lot B2 (workspace, results)."""

import io
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "docs", "tools"))


def _write(path, text):
    directory = os.path.dirname(str(path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(str(path), "w", encoding="utf-8") as handle:
        handle.write(text)


######################################
# AR-24: the generated API reference
######################################


class TestApiReference:
    def test_slots_are_not_shown_as_their_repr(self):
        import gen_api_reference as gen
        from odatix.workspace.exclusions import Exclusion

        attributes, _methods = gen.class_members(Exclusion)
        cells = dict((name, doc) for name, _kind, doc in attributes)
        assert "when" in cells and "<member" not in cells["when"]
        assert cells["when"]

    def test_a_wrapped_word_colon_is_not_a_new_item(self):
        import gen_api_reference as gen

        text = (
            "Returns:\n"
            "    Excluded: why the point is out. A rule is reported once, and rejects\n"
            "    nothing: a typo must not empty a space."
        )
        rendered = gen.render_docstring(text)
        assert "rejects nothing: a typo" in rendered
        assert "`nothing`" not in rendered

    def test_args_items_stay_separate(self):
        import gen_api_reference as gen

        rendered = gen.render_docstring("Args:\n    a (int): first.\n    b (str): second.")
        assert "- `a` *(int)* — first." in rendered and "- `b` *(str)* — second." in rendered

    def test_former_keys_are_not_listed_as_settings(self):
        import gen_api_reference as gen
        from odatix.workspace.architectures import ArchitectureSettings

        assert "generate_configurations" not in gen.render_settings_table(ArchitectureSettings)


######################################
# SE-23: odatix.run for scripts
######################################


class TestRunApi:
    def test_job_planner_is_not_public(self):
        import odatix.run

        assert "JobPlanner" not in odatix.run.__all__

    def test_quiet_collects_without_printing(self, tmp_path):
        from odatix.run import CollectingReporter, Reporter, Run
        from odatix.workspace import Workspace

        workspace = Workspace.open(str(tmp_path))
        assert isinstance(Run(workspace, "fmax_synthesis", quiet=True).reporter, CollectingReporter)
        assert type(Run(workspace, "fmax_synthesis").reporter) is Reporter
        given = Reporter()
        assert Run(workspace, "fmax_synthesis", quiet=True, reporter=given).reporter is given

    def test_reporter_methods_are_documented(self):
        from odatix.lib.run_report import JobPlan
        from odatix.run import Reporter, Run

        for member in (Reporter.of_level, Reporter.errors, Reporter.warnings, Reporter.last_error,
                       Reporter.clear, Run.settings_file, Run.work_path, JobPlan.counts):
            assert member.__doc__


######################################
# SE-12: what a run says of a bad workspace
######################################


class TestRunErrors:
    def test_run_outside_a_workspace_says_so(self, tmp_path):
        from odatix.run import Run, RunError
        from odatix.workspace import Workspace

        with pytest.raises(RunError) as error:
            Run(Workspace.open(str(tmp_path)), "fmax_synthesis", quiet=True).check()
        assert "not an Odatix workspace" in str(error.value)

    def test_an_empty_required_key_is_called_empty(self):
        from odatix.workspace.architectures import validate

        data = {"top_level_file": "a.v", "top_level_module": "a", "clock_signal": "clk",
                "reset_signal": "", "rtl_path": "rtl"}
        errors = [message.text for message in validate(data, "s.yml")]
        assert errors == ['Key "reset_signal" is empty in "s.yml": a value is required.']
        del data["reset_signal"]
        errors = [message.text for message in validate(data, "s.yml")]
        assert errors == ['Cannot find key "reset_signal" in "s.yml".']


######################################
# DS-09: a campaign written from the template
######################################


class TestCampaignTemplate:
    def test_new_campaign_keeps_the_template_layout(self, tmp_path):
        from odatix.dse.settings import CampaignSettings
        from odatix.lib.settings import OdatixSettings
        from odatix.workspace.settings import save_settings

        template = os.path.join(
            OdatixSettings.odatix_init_path, "odatix_userconfig", "dse_campaigns", "campaign_template.yml"
        )
        settings = CampaignSettings()
        settings.architectures = ["MyCPU"]
        settings.search.population = 40
        path = str(tmp_path / "c.yml")
        save_settings(settings, path, template=template)
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        assert "exclusions: {}" not in text
        # The section comment of "architectures" stays right above it
        assert "them (\"Design\") searches all of them.\narchitectures:\n  - MyCPU" in text
        # Every key of the template is written in place, none appended
        search = text[text.index("search:"):text.index("# architectures to explore")]
        assert "population:" in search and "constraint_models:" in search
        assert "''" not in search


######################################
# Results
######################################


class TestResults:
    def test_derived_metrics_groups(self, tmp_path):
        from odatix.workspace.derived import DerivedMetricsFile

        new = str(tmp_path / "new.yml")
        derived = DerivedMetricsFile(new)
        derived.metrics
        derived.save()
        with io.open(new, encoding="utf-8") as handle:
            assert "groups: {}" in handle.read()

        old = str(tmp_path / "old.yml")
        _write(old, "groups:\n\nderived_metrics:\n  A:\n    op: x+1\n")
        derived = DerivedMetricsFile(old)
        derived.groups = {}
        derived.save()
        with io.open(old, encoding="utf-8") as handle:
            text = handle.read()
        assert text.startswith("groups:\n") and "groups: {}" not in text

    def test_workflow_export_messages_name_the_metric(self, tmp_path, capsys):
        import odatix.components.export_workflow_results as ewr

        run_dir = str(tmp_path / "run")
        _write(os.path.join(run_dir, "results.csv"), "A\n1\n")
        metrics = {
            "Missing_one": {"type": "csv", "settings": {"file": "results.csv", "key": "NOPE"}},
            "Bad_op": {"type": "operation", "settings": {"op": "Missing_one +"}},
        }
        ewr._extract_run_records(run_dir, metrics, {}, error_prefix="wf => ")
        out = capsys.readouterr().out
        assert 'metric "Missing_one"' in out
        assert 'metric "Bad_op"' in out


class TestNestedBlockFromADict:
    """A nested block assigned as a plain mapping is saved, not ignored."""

    @pytest.mark.parametrize("how", ["attribute", "update"])
    def test_the_new_values_reach_the_file(self, tmp_path, how):
        from odatix.workspace.jobs import FmaxSynthesisJobSettings
        from odatix.workspace.settings import load_settings, save_settings
        path = str(tmp_path / "fmax_synthesis_settings.yml")
        _write(path, "fmax_synthesis:\n  override: No   # keep\n  lower_bound: 50\n  upper_bound: 500\n")
        settings = load_settings(FmaxSynthesisJobSettings, path)
        block = {"override": True, "lower_bound": 100, "upper_bound": 900}
        if how == "attribute":
            settings.fmax_synthesis = block
        else:
            settings.update({"fmax_synthesis": block})
        save_settings(settings, path)
        saved = load_settings(FmaxSynthesisJobSettings, path).fmax_synthesis
        assert (saved.override, saved.lower_bound, saved.upper_bound) == (True, 100, 900)
        assert "# keep" in open(path, encoding="utf-8").read()
