"""
What a new user of "odatix dse" ran into, kept from happening again.

- a job run as a flow of several steps is measured by its last step (B0);
- odatix.dse.explore() runs from a script (B1);
- every exploration the app starts has a session of its own (B2);
- an unknown strategy is a settings file to fix, not an internal error (B3);
- a campaign whose question changed reads its designs again (B4);
- a metric nothing measures is said before anything runs (U2);
- "until" stops every evaluation at a step its flows declare (W1);
- "odatix dse" takes -E/--exit and --logsize (D4);
- the archive says what was searched, and counts what was reused apart (D6, U6);
- a resumed campaign says what is left, not what the budget was (U1).
"""

import os

import pytest
import yaml

from odatix.dse.archive import Archive
from odatix.dse.campaign import Campaign, CampaignError
from odatix.dse.evaluation import Evaluation, Evaluator, is_final_record
from odatix.dse.objectives import Objectives
from odatix.dse.space import ArchitectureSpace

from test_dse import (  # noqa: F401 -- architecture and workflow are fixtures
    FakeEvaluator,
    architecture,
    campaign_settings,
    workflow,
)


def write_results(workspace, tool, records):
    """A results file of the workspace, as a run exports it."""
    path = os.path.join(workspace.paths.result_path, "results_{0}.yml".format(tool))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"schema": 2, "units": {}, "results": records}, f)
    return path


def step_records(configuration, steps):
    """The records of one job of a flow with steps: one per step it reached."""
    records = []
    for index, (step, metrics) in enumerate(steps):
        records.append({
            "meta": {
                "type": "custom_freq_synthesis", "tool": "vivado", "flow": "standard",
                "target": "xc7a100t", "architecture": "Design", "configuration": configuration,
                "main": configuration, "frequency": 100, "step": step, "_step_index": index,
                "_last_step": index == len(steps) - 1, "timestamp": "2026-10-18_00-00-00",
            },
            "metrics": metrics,
        })
    return records


######################################
# B0: the last step measures the design
######################################

class TestFinalStep:
    def test_a_record_of_an_earlier_step_is_not_final(self):
        assert not is_final_record({"_last_step": False})
        assert is_final_record({"_last_step": True})
        # A job without steps writes no flag, and its record is final.
        assert is_final_record({"architecture": "Design"})

    def evaluator(self, architecture, objectives, constraints=None):
        from odatix.workspace import Workspace

        settings = campaign_settings(
            run="custom_freq_synthesis", objectives=objectives, constraints=constraints or [],
        )
        workspace = Workspace(os.path.dirname(os.path.dirname(os.path.dirname(architecture.path))))
        return workspace, Evaluator(workspace, settings, settings.objective_list())

    def test_a_design_is_worth_its_last_step_whatever_the_objective(self, architecture):
        # The synthesis step has more slack than the place and route one: an
        # exploration maximizing the slack used to keep the synthesis record.
        workspace, evaluator = self.evaluator(
            architecture,
            [{"metric": "Worst_Slack", "goal": "max"}, {"metric": "LUT_count", "goal": "min"}],
        )
        design = ArchitectureSpace(architecture).design((0, 0))
        write_results(workspace, "vivado", step_records(design.configuration, [
            ("elaboration", {"LUT_count": None, "Worst_Slack": None}),
            ("synthesis", {"LUT_count": 9, "Worst_Slack": 7.781}),
            ("pnr", {"LUT_count": 9, "Worst_Slack": 7.53}),
        ]))

        evaluation = evaluator.measure(design, evaluator._records(), {})
        assert evaluation.measured
        assert evaluation.metrics["Worst_Slack"] == 7.53
        assert evaluation.source["step"] == "pnr"

    def test_a_design_already_measured_is_reused_with_its_last_step(self, architecture):
        workspace, evaluator = self.evaluator(
            architecture,
            [{"metric": "Worst_Slack", "goal": "max"}, {"metric": "LUT_count", "goal": "min"}],
        )
        space = ArchitectureSpace(architecture)
        design = space.design((0, 0))
        records = step_records(design.configuration, [
            ("synthesis", {"LUT_count": 9, "Worst_Slack": 7.781}),
            ("pnr", {"LUT_count": 9, "Worst_Slack": 7.53}),
        ])
        write_results(workspace, "vivado", records)

        records = evaluator._records()
        assert sum(len(found) for found in records.values()) == 1
        assert list(records.values())[0][0]["meta"]["step"] == "pnr"

    def test_unmeasured_names_only_what_no_record_measured(self, architecture):
        # The first record of a job (elaboration) measures nothing: the note
        # used to name every metric of the campaign, measured or not.
        workspace, evaluator = self.evaluator(
            architecture,
            [{"metric": "LUT_count", "goal": "min"}, {"metric": "Total_Power", "goal": "min"}],
            constraints=[{"metric": "Slack", "min": 0}],
        )
        design = ArchitectureSpace(architecture).design((0, 0))
        records = [
            {"meta": {"step": "elaboration"}, "metrics": {"LUT_count": None, "Total_Power": None}},
            {"meta": {"step": "synthesis"}, "metrics": {"LUT_count": 9, "Total_Power": 0.1}},
        ]
        evaluation = evaluator.evaluation_of(design, records)
        assert not evaluation.measured
        assert evaluation.note == "nothing was measured for: Slack"


######################################
# U2: metric names checked before anything runs
######################################

class TestMetricNames:
    def campaign(self, architecture, **overrides):
        from odatix.workspace import Workspace

        settings = campaign_settings(**overrides)
        workspace = Workspace(os.path.dirname(os.path.dirname(os.path.dirname(architecture.path))))
        return Campaign(workspace, architecture, settings)

    def test_a_metric_the_tool_does_not_measure_stops_the_check(self, architecture):
        campaign = self.campaign(
            architecture, run="custom_freq_synthesis",
            objectives=[{"metric": "LUT_count", "goal": "min"}],
            constraints=[{"metric": "Slack", "min": 0}],
        )
        with pytest.raises(CampaignError) as error:
            campaign.check()
        message = str(error.value)
        assert '"Slack" (did you mean "Worst_Slack"?)' in message
        assert "Worst_Slack" in message.split("can name are:")[1]

    def test_an_fmax_synthesis_measures_fmax_not_a_frequency(self, architecture):
        # An fmax record has no "frequency": its answer is the "Fmax" metric.
        campaign = self.campaign(
            architecture, run="fmax_synthesis",
            objectives=[{"metric": "frequency", "goal": "max"}, {"metric": "LUT_count", "goal": "min"}],
        )
        with pytest.raises(CampaignError) as error:
            campaign.check()
        assert '"frequency" (did you mean "Fmax"?)' in str(error.value)

        campaign = self.campaign(
            architecture, run="fmax_synthesis",
            objectives=[{"metric": "Fmax", "goal": "max"}, {"metric": "LUT_count", "goal": "min"}],
        )
        campaign.check()

    def test_a_custom_frequency_synthesis_may_name_its_frequency(self, architecture):
        campaign = self.campaign(
            architecture, run="custom_freq_synthesis",
            objectives=[{"metric": "frequency", "goal": "max"}, {"metric": "Worst_Slack", "goal": "max"}],
        )
        campaign.check()

    def test_a_workflow_is_checked_against_its_metrics_file(self, workflow, tmp_path):
        from odatix.dse.campaigns import RunSettings
        from odatix.dse.settings import CampaignSettings, DseSettings
        from odatix.workspace import Workspace

        with open(os.path.join(workflow.path, "_metrics.yml"), "w", encoding="utf-8") as f:
            f.write("metrics:\n  bitrate_bpp: {type: json}\n  psnr_db: {type: json}\n")
        campaign_file = CampaignSettings.from_dict({
            "run": "workflow", "tool": "",
            "objectives": [{"metric": "bitrate_bpp", "goal": "min"}, {"metric": "psnr", "goal": "max"}],
            "search": {"strategy": "random", "budget": 2, "batch": 2},
            "architectures": ["Codec"],
        })
        settings = RunSettings(campaign_file, DseSettings.from_dict({"campaigns": ["c"]}))
        campaign = Campaign(Workspace(str(tmp_path)), workflow, settings)
        with pytest.raises(CampaignError) as error:
            campaign.check()
        assert '"psnr" (did you mean "psnr_db"?)' in str(error.value)

    def test_a_campaign_measured_another_way_is_not_checked(self, architecture, tmp_path):
        # An evaluator that does not read results files (a test, a model)
        # measures whatever it measures.
        from odatix.workspace import Workspace

        settings = campaign_settings()
        evaluator = FakeEvaluator(settings.objective_list(), lambda design: {"speed": 1, "area": 1})
        Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator).check()


######################################
# W1: until, the step every evaluation stops at
######################################

class TestUntil:
    def campaign(self, architecture, **overrides):
        from odatix.workspace import Workspace

        settings = campaign_settings(
            run="custom_freq_synthesis",
            objectives=[{"metric": "frequency", "goal": "max"}, {"metric": "LUT_count", "goal": "min"}],
            **overrides
        )
        workspace = Workspace(os.path.dirname(os.path.dirname(os.path.dirname(architecture.path))))
        return Campaign(workspace, architecture, settings)

    def test_a_step_of_the_flow_is_accepted(self, architecture):
        campaign = self.campaign(architecture, until="synthesis")
        campaign.check()
        assert campaign.settings.until == "synthesis"

    def test_a_step_the_flow_does_not_have_stops_the_check(self, architecture):
        campaign = self.campaign(architecture, until="routing")
        with pytest.raises(CampaignError) as error:
            campaign.check()
        message = str(error.value)
        assert '"until: routing" is not a step of vivado' in message
        assert "synthesis" in message

    def test_every_batch_is_run_until_that_step(self, architecture, monkeypatch):
        import odatix.run

        seen = {}

        class StopRun(Exception):
            pass

        def fake_run(*args, **kwargs):
            seen.update(kwargs)
            raise StopRun()

        monkeypatch.setattr(odatix.run, "Run", fake_run)
        campaign = self.campaign(architecture, until="synthesis")
        design = campaign.space.design(next(iter(campaign.space.genomes())))
        with pytest.raises(StopRun):
            campaign.evaluator.start_batch([design], None, None)
        assert seen["until"] == "synthesis"


######################################
# B3: an unknown strategy
######################################

class TestStrategyName:
    def test_an_unknown_strategy_is_a_settings_file_to_fix(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(search={"strategy": "genetik", "budget": 4, "batch": 2})
        with pytest.raises(CampaignError) as error:
            Campaign(Workspace(str(tmp_path)), architecture, settings,
                     evaluator=FakeEvaluator(settings.objective_list(), lambda design: {}))
        message = str(error.value)
        assert 'Unknown search strategy "genetik"' in message
        assert "bayesian, exhaustive, genetic, random" in message
        assert "nsga2" in message

    def test_the_command_line_says_it_as_an_error(self, architecture, tmp_path, monkeypatch, capsys):
        from odatix.components import run_dse

        monkeypatch.chdir(str(tmp_path))
        _write_dse_workspace(tmp_path, objectives=[{"metric": "Fmax", "goal": "max"}])
        args = _parse(["dse", "-Q", "-C", "-s", "foo"])
        with pytest.raises(SystemExit):
            run_dse.main(args)
        out = capsys.readouterr().out
        assert "Unknown search strategy" in out
        assert "internal error" not in out


######################################
# B4 + U1: picking a campaign up
######################################

class _RemeasuringEvaluator(FakeEvaluator):
    """Reads the designs again from a formula, the way Evaluator reads them from the results."""

    def __init__(self, objectives, cost):
        super(_RemeasuringEvaluator, self).__init__(objectives, cost)
        self.remeasured = []

    def _records(self):
        return {}

    def remeasure(self, evaluation, records=None):
        self.remeasured.append(evaluation.entry)
        metrics = self.cost(evaluation.design)
        return Evaluation(
            evaluation.design, metrics=metrics, costs=self.objectives.costs(metrics),
            batch=evaluation.batch, reused=evaluation.reused,
        )


class TestResumeAnotherQuestion:
    def cost(self, design):
        return {"speed": design.values["width"] * 10, "area": design.values["width"]}

    def _campaign(self, architecture, tmp_path, evaluator_class, objectives, budget=4):
        from odatix.workspace import Workspace

        search = {"strategy": "exhaustive", "budget": budget, "batch": 2, "seed": 1}
        settings = campaign_settings(objectives=objectives, search=search)
        evaluator = evaluator_class(settings.objective_list(), self.cost)
        campaign = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator)
        return campaign, evaluator

    def test_a_fixed_objective_reads_the_designs_again(self, architecture, tmp_path):
        typo = [{"metric": "speed", "goal": "max"}, {"metric": "aera", "goal": "min"}]
        first, _ = self._campaign(architecture, tmp_path, FakeEvaluator, typo)
        archive = first.run()
        assert len(archive) == 4 and not archive.measured

        fixed = [{"metric": "speed", "goal": "max"}, {"metric": "area", "goal": "min"}]
        second, evaluator = self._campaign(architecture, tmp_path, _RemeasuringEvaluator, fixed)
        archive = second.run()
        # Nothing is run again: the budget was spent, the designs are read.
        assert evaluator.evaluated == []
        assert len(evaluator.remeasured) == 4
        assert len(archive.measured) == 4
        assert archive.front()

        written = yaml.safe_load(open(archive.path, encoding="utf-8").read())
        assert not any(record.get("failed") for record in written["evaluations"])

    def test_the_same_question_reads_again_only_what_was_unmeasured(self, architecture, tmp_path):
        objectives = [{"metric": "speed", "goal": "max"}, {"metric": "area", "goal": "min"}]
        first, _ = self._campaign(architecture, tmp_path, FakeEvaluator, objectives)
        first.run()
        second, evaluator = self._campaign(architecture, tmp_path, _RemeasuringEvaluator, objectives, budget=6)
        second.run()
        assert evaluator.remeasured == []
        assert len(evaluator.evaluated) == 2

    def test_a_spent_budget_says_so_and_asks_nothing(self, architecture, tmp_path, monkeypatch):
        from odatix.dse.campaign import Exploration
        from odatix.dse.settings import DseSettings

        objectives = [{"metric": "speed", "goal": "max"}, {"metric": "area", "goal": "min"}]
        first, _ = self._campaign(architecture, tmp_path, FakeEvaluator, objectives)
        first.run()

        second, _ = self._campaign(architecture, tmp_path, FakeEvaluator, objectives)
        assert second.already_evaluated == 4
        assert second.remaining == 0
        assert "the budget is spent" in second.describe()

        more, _ = self._campaign(architecture, tmp_path, FakeEvaluator, objectives, budget=6)
        assert more.remaining == 2
        assert "2 left to run" in more.describe()

        def ask():
            raise AssertionError("asked to continue with nothing left to run")

        monkeypatch.setattr("odatix.lib.utils.ask_to_continue", ask)
        exploration = Exploration(second.workspace, DseSettings.from_dict({"ask_continue": True}))
        exploration.confirm([second])


######################################
# D6 + U6: what the archive says
######################################

class TestArchiveContent:
    def test_the_archive_names_the_campaign_and_what_it_searched(self, architecture, tmp_path):
        from odatix.workspace import Workspace

        settings = campaign_settings(name="my_campaign")
        evaluator = FakeEvaluator(settings.objective_list(), lambda d: {"speed": 1, "area": d.values["width"]})
        archive = Campaign(Workspace(str(tmp_path)), architecture, settings, evaluator=evaluator).run()
        written = yaml.safe_load(open(archive.path, encoding="utf-8").read())
        assert written["campaign"] == "my_campaign"
        assert written["architecture"] == "Design"

    def test_reused_designs_are_counted_apart(self, architecture, tmp_path):
        space = ArchitectureSpace(architecture)
        objectives = Objectives.from_list(["area"])
        archive = Archive(str(tmp_path / "a.yml"), "c", objectives, design="Design")
        archive.add([
            Evaluation(space.design((0, 0)), metrics={"area": 1}, costs=objectives.costs({"area": 1})),
            Evaluation(space.design((1, 0)), metrics={"area": 2}, costs=objectives.costs({"area": 2}),
                       reused=True),
        ])
        written = archive.to_dict()
        assert written["evaluated"] == 1
        assert written["reused"] == 1

    def test_an_archive_written_before_the_campaign_key_is_still_read(self, architecture, tmp_path):
        space = ArchitectureSpace(architecture)
        objectives = Objectives.from_list(["area"])
        path = str(tmp_path / "old.yml")
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "architecture": "c", "objectives": objectives.to_list(),
                "evaluations": [{"genome": [0, 0], "metrics": {"area": 1}, "batch": 1}],
            }, f)
        archive = Archive(path, "c", objectives, design="Design")
        assert archive.peek() == 1
        assert len(archive.restore(space)) == 1


######################################
# B2: a session per exploration
######################################

class TestSessions:
    def test_every_new_session_has_a_name_of_its_own(self, architecture, tmp_path):
        from odatix.dse.driver import driver_paths, new_session
        from odatix.workspace import Workspace

        workspace = Workspace(str(tmp_path))
        first = new_session(workspace)
        driver_paths(workspace, first)
        second = new_session(workspace)
        assert first != second
        assert first.startswith("dse-{0}-".format(os.getpid()))

    def test_the_app_starts_each_exploration_in_a_new_session(self, architecture, tmp_path, monkeypatch):
        from odatix.dse.settings import DseSettings
        from odatix.gui.dse_config import exploration
        from odatix.lib.parallel_job_handler import daemon_control
        from odatix.workspace import Workspace

        sessions = []

        def enqueue(handler, session=None, **_):
            sessions.append(session)
            return {"session_name": session}, None

        monkeypatch.setattr(daemon_control, "enqueue_parallel_jobs", enqueue)
        workspace = Workspace(str(tmp_path))
        for _ in range(2):
            exploration._start(workspace, DseSettings.from_dict({"campaigns": []}), [], session=None)
        assert len(sessions) == 2 and sessions[0] != sessions[1]


######################################
# B1: explore() from a script
######################################

def _write_dse_workspace(root, objectives, campaign="camp"):
    from test_dse import PARAMETERIZED, write_architecture

    (root / "odatix.yml").write_text("arch_path: odatix_userconfig/architectures\n", encoding="utf-8")
    arch_root = root / "odatix_userconfig" / "architectures"
    if not (arch_root / "Design").exists():
        arch_root.mkdir(parents=True, exist_ok=True)
        write_architecture(arch_root, "Design", PARAMETERIZED)
    campaigns = root / "odatix_userconfig" / "dse_campaigns"
    campaigns.mkdir(parents=True, exist_ok=True)
    (campaigns / "{0}.yml".format(campaign)).write_text(yaml.safe_dump({
        "run": "custom_freq_synthesis", "tool": "vivado",
        "frequencies": {"explore": False, "list": [100]},
        "objectives": objectives + [{"metric": "LUT_count", "goal": "min"}],
        "search": {"strategy": "random", "budget": 50, "batch": 8},
        "architectures": ["Design"],
    }))
    (root / "odatix_userconfig" / "dse_settings.yml").write_text(
        "ask_continue: Yes\nnb_jobs: 2\ncampaigns:\n  - {0}\n".format(campaign)
    )


def _parse(argv):
    from odatix.odatix_main import ArgParser

    return ArgParser.parse_arguments(argv)


class TestExplore:
    def test_overrides_go_where_they_belong(self):
        from odatix.dse import _split_overrides

        run, search, campaign = _split_overrides(
            {"nb_jobs": 2, "budget": 4, "batch": 2, "strategy": "random", "tool": "vivado"}
        )
        assert run == {"nb_jobs": 2}
        assert search == {"budget": 4, "batch": 2, "strategy": "random"}
        assert campaign == {"tool": "vivado"}

    def test_an_unknown_override_is_refused(self):
        from odatix.dse import _split_overrides

        with pytest.raises(TypeError) as error:
            _split_overrides({"budgte": 4})
        assert "budgte" in str(error.value) and "budget" in str(error.value)

    def test_explore_runs_in_a_session_it_closes_and_asks_nothing(self, tmp_path, monkeypatch):
        import odatix.dse as dse
        from odatix.dse import driver
        from odatix.dse.campaign import Exploration
        from odatix.workspace import Workspace

        _write_dse_workspace(tmp_path, [{"metric": "Worst_Slack", "goal": "max"}])
        seen = {}

        monkeypatch.setattr(driver, "open_session", lambda ws, settings, session=None: ("s1", True))
        monkeypatch.setattr(driver, "close_session",
                            lambda ws, session, started: seen.setdefault("closed", (session, started)))

        def run(self, confirm=True):
            seen["confirm"] = confirm
            seen["session"] = self.session
            seen["search"] = [dict(c.search.to_dict()) for c in self.campaign_settings()]
            return ["archive"]

        monkeypatch.setattr(Exploration, "run", run)
        result = dse.explore(Workspace(str(tmp_path)), budget=4, batch=2)
        assert result == ["archive"]
        assert seen["confirm"] is False
        assert seen["session"] == "s1"
        assert seen["closed"] == ("s1", True)
        assert seen["search"][0]["budget"] == 4 and seen["search"][0]["batch"] == 2

    def test_explore_refuses_a_campaign_that_cannot_run_before_starting_a_session(self, tmp_path, monkeypatch):
        import odatix.dse as dse
        from odatix.dse import driver
        from odatix.workspace import Workspace

        _write_dse_workspace(tmp_path, [{"metric": "Slack", "goal": "max"}])

        def no_session(*_args, **_kwargs):
            raise AssertionError("a session was started for an exploration that cannot run")

        monkeypatch.setattr(driver, "open_session", no_session)
        with pytest.raises(CampaignError):
            dse.explore(Workspace(str(tmp_path)))


######################################
# D4: -E/--exit and --logsize
######################################

class TestCommandLine:
    def test_exit_and_logsize_are_options_of_dse(self):
        from odatix.components.run_dse import apply_arguments
        from odatix.dse.settings import DseSettings

        args = _parse(["dse", "-C", "-E", "--logsize", "42"])
        settings = apply_arguments(DseSettings.from_dict({}), args)
        assert settings.exit_when_done is True
        assert settings.log_size_limit == 42
