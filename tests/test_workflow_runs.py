"""
Non-regression tests of what a workflow run does with its settings: the task
graph (path, phony), which jobs it skips, the placeholders it substitutes or
warns about, the workflows it selects, and how their results are exported.
"""

import os
import sys

import pytest

import odatix.components.export_workflow_results as ewr
import odatix.components.run_workflow as run_workflow
import odatix.lib.wosit as wosit
from odatix.lib.run_report import Category, JobPlan


def _write(path, content):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(str(path), "w") as f:
        f.write(content)


def _stage_names(maker, directory):
    """Names of the tasks a job would run, stage by stage."""
    old = os.getcwd()
    os.chdir(str(directory))
    try:
        stages = maker.getStages(name="main", max_process=1) or {}
    finally:
        os.chdir(old)
    return [[task.getName() for task in stages[level]] for level in sorted(stages)]


######################################
# Task graph
######################################

class TestTaskPath:
    def test_the_path_of_a_task_does_not_leak_on_the_next_ones(self, tmp_path):
        # "main" depends on "b", which runs in "sub": both are still found by name.
        tasks = [
            {"name": "b", "path": "sub", "commands": ["pwd"]},
            {"name": "main", "dependencies": ["b"], "commands": ["pwd"]},
        ]
        assert _stage_names(wosit.createTaskGraph(tasks), tmp_path) == [["b"], ["main"]]

    def test_order_does_not_matter(self, tmp_path):
        tasks = [
            {"name": "main", "dependencies": ["b"], "commands": ["pwd"]},
            {"name": "b", "path": "sub", "commands": ["pwd"]},
        ]
        assert _stage_names(wosit.createTaskGraph(tasks), tmp_path) == [["b"], ["main"]]

    def test_a_task_with_a_path_runs_from_it(self, tmp_path):
        maker = wosit.createTaskGraph([{"name": "main", "path": "sub", "commands": ["pwd"]}])
        old = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            stages = maker.getStages(name="main")
        finally:
            os.chdir(old)
        assert stages[0][0].getCommand() == 'cd "sub"\npwd'

    def test_the_fallback_runs_from_the_path_too(self):
        stages = wosit.createTaskGraph([
            {"name": "main", "path": "/abs", "commands": ["false"], "on_failure_commands": ["true"]},
        ]).getStages(name="main")
        assert stages[0][0].getCommand() == '(cd "/abs" && false) || (cd "/abs" && true)'


class TestPhony:
    def test_tasks_are_phony_by_default(self, tmp_path):
        (tmp_path / "built.txt").write_text("")
        tasks = [
            {"name": "built.txt", "commands": ["touch built.txt"]},
            {"name": "main", "dependencies": ["built.txt"], "commands": ["true"]},
        ]
        assert _stage_names(wosit.createTaskGraph(tasks), tmp_path) == [["built.txt"], ["main"]]

    def test_a_task_that_is_not_phony_is_skipped_when_its_file_exists(self, tmp_path):
        tasks = [
            {"name": "built.txt", "phony": False, "commands": ["touch built.txt"]},
            {"name": "main", "dependencies": ["built.txt"], "commands": ["true"]},
        ]
        assert _stage_names(wosit.createTaskGraph(tasks), tmp_path) == [["built.txt"], ["main"]]
        (tmp_path / "built.txt").write_text("")
        assert _stage_names(wosit.createTaskGraph(tasks), tmp_path) == [["main"]]

    def test_its_file_is_read_in_its_own_directory(self, tmp_path):
        tasks = [
            {"name": "built.txt", "path": "sub", "phony": False, "commands": ["touch built.txt"]},
            {"name": "main", "dependencies": ["built.txt"], "commands": ["true"]},
        ]
        (tmp_path / "built.txt").write_text("")
        assert _stage_names(wosit.createTaskGraph(tasks), tmp_path) == [[os.path.join("sub", "built.txt")], ["main"]]
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "built.txt").write_text("")
        assert _stage_names(wosit.createTaskGraph(tasks), tmp_path) == [["main"]]

    def test_phony_must_be_yes_or_no(self):
        with pytest.raises(ValueError):
            wosit.createTaskGraph([{"name": "main", "phony": "maybe", "commands": ["true"]}])


class TestDoneCommand:
    def test_main_runs_it_last(self, tmp_path):
        maker = wosit.createTaskGraph(
            [{"name": "main", "commands": ["false"], "on_failure_commands": ["true"]}],
            done_command="echo done> marker",
        )
        stages = maker.getStages(name="main")
        assert stages[0][0].getCommand() == "(false) || (true)\necho done> marker"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell commands")
    def test_only_once_everything_succeeded(self, tmp_path):
        import subprocess

        marker = tmp_path / run_workflow.WORKFLOW_DONE_FILENAME
        done = run_workflow._done_command(str(tmp_path))
        for commands, written in ((["false"], False), (["true"], True)):
            command = wosit.createTaskGraph(
                [{"name": "main", "commands": commands}], done_command=done,
            ).getStages(name="main")[0][0].getCommand()
            # As the daemon runs it: one line, each command after the previous one.
            subprocess.call(" && ".join(command.split("\n")), shell=True, cwd=str(tmp_path))
            assert marker.is_file() == written


######################################
# What a run does with each job
######################################

class TestJobCategory:
    def test_new(self, tmp_path):
        assert run_workflow.job_category(str(tmp_path / "nope"), overwrite=False) == Category.NEW

    def test_done_is_skipped_unless_overwritten(self, tmp_path):
        (tmp_path / run_workflow.WORKFLOW_DONE_FILENAME).write_text("done")
        assert run_workflow.job_category(str(tmp_path), overwrite=False) == Category.CACHED
        assert run_workflow.job_category(str(tmp_path), overwrite=True) == Category.OVERWRITE

    def test_unfinished_runs_again(self, tmp_path):
        assert run_workflow.job_category(str(tmp_path), overwrite=False) == Category.INCOMPLETE
        assert run_workflow.job_category(str(tmp_path), overwrite=False, resume=True) == Category.RESUME


class TestPlanNames:
    def test_every_name_without_a_category(self):
        plan = JobPlan()
        plan.add("a", Category.NEW)
        plan.add("b", Category.CACHED)
        assert plan.names() == ["a", "b"]
        assert plan.names(Category.CACHED) == ["b"]


######################################
# Placeholders
######################################

def _instance(tmp_path, **kwargs):
    values = dict(
        workflow_name="cli_profile", workflow_display_name="cli_profile/default",
        workflow_full="cli_profile/default", workflow_param_dir="cli_profile",
        workflow_config="default", tmp_dir=str(tmp_path / "work"), source_path=str(tmp_path),
        source_whitelist=None, source_blacklist=None, param_target_file=None,
        start_delimiter=None, stop_delimiter=None, param_file=None, param_domains=[],
        progress_file="progress.txt", tasks=[], workflow_settings_file="", workflow_definition_dir=str(tmp_path),
    )
    values.update(kwargs)
    return run_workflow.WorkflowInstance(**values)


class TestPlaceholders:
    def test_the_configuration_reaches_the_commands_without_use_parameters(self, tmp_path):
        config = tmp_path / "default.txt"
        config.write_text("balanced profile\n")
        instance = _instance(tmp_path, use_parameters=False, command_param_file=str(config))
        substitutions = run_workflow._build_workflow_command_substitutions(instance)
        assert substitutions["cli_profile"] == "balanced profile"

    def test_unresolved_placeholders(self):
        tasks = [{"name": "main", "commands": ["run --a ${a} --b ${b} --home ${HOME_X} $c"]}]
        found = run_workflow.unresolved_placeholders(tasks, {"a": "1"}, environment={"HOME_X": "/"})
        assert found == [("main", "b")]


######################################
# Selecting workflows
######################################

RUN_SETTINGS = """overwrite: No
ask_continue: No
exit_when_done: No
log_size_limit: 300
nb_jobs: 2
workflows:
  - one
"""


@pytest.fixture
def workflows(tmp_path):
    for name in ("one", "two"):
        _write(tmp_path / "sources" / name / "x.txt", "")
        _write(
            tmp_path / "workflows" / name / "_settings.yml",
            "sources:\n  path: " + str(tmp_path / "sources" / name) + "\nuse_parameters: No\n"
            "tasks:\n  - name: main\n    commands:\n      - echo ${missing}\n",
        )
    _write(tmp_path / "workflow_settings.yml", RUN_SETTINGS)
    return tmp_path


def _check(tmp_path, **kwargs):
    return run_workflow.check_settings(
        run_config_settings_filename=str(tmp_path / "workflow_settings.yml"),
        workflow_path=str(tmp_path / "workflows"), work_path=str(tmp_path / "work"),
        overwrite=kwargs.pop("overwrite", False), noask=True, exit_when_done=False,
        log_size_limit=None, nb_jobs=None, **kwargs
    )


class TestSelection:
    def test_the_file_by_default(self, workflows):
        plan = _check(workflows)[-1]
        assert plan.names(colored=False) == ["one"]

    def test_named_workflows_replace_the_list(self, workflows):
        plan = _check(workflows, selected_workflows=["two", "one"])[-1]
        assert sorted(plan.names(colored=False)) == ["one", "two"]

    def test_a_job_done_is_skipped(self, workflows):
        done = workflows / "work" / "one" / "one" / run_workflow.WORKFLOW_DONE_FILENAME
        _write(done, "done")
        instances = _check(workflows, selected_workflows=["one", "two"])[0]
        assert [instance.workflow_display_name for instance in instances] == ["two"]
        plan = _check(workflows, selected_workflows=["one", "two"], overwrite=True)[-1]
        assert plan.counts()[Category.OVERWRITE] == 1

    def test_a_job_a_session_runs_is_left_to_it(self, workflows, monkeypatch):
        from odatix.run.planner import JobPlanner

        running = {"session_id": "other", "status": "running"}
        monkeypatch.setattr(
            JobPlanner, "daemon_decision",
            lambda self, tmp_dir, steps_decision=None: ("skip", running) if tmp_dir.endswith("one") else ("none", None),
        )
        result = _check(workflows, selected_workflows=["one", "two"])
        assert [instance.workflow_display_name for instance in result[0]] == ["two"]
        assert result[-1].counts()[Category.DAEMON] == 1

    def test_an_unresolved_placeholder_is_reported(self, workflows, capsys):
        _check(workflows)
        assert '"${missing}"' in capsys.readouterr().out


######################################
# Export
######################################

class TestExport:
    def test_no_metrics_file_is_not_a_failure(self, tmp_path):
        run_dir = tmp_path / "work" / "wf" / "wf"
        run_dir.mkdir(parents=True)
        (tmp_path / "workflows" / "wf").mkdir(parents=True)
        config = {
            "run_dir": str(run_dir), "work_root": str(tmp_path / "work"),
            "workflow_path": str(tmp_path / "workflows"), "output_dir": str(tmp_path / "results"),
        }
        assert ewr.export_single_workflow_job(object(), config) is True
        assert not (tmp_path / "results").exists()

    def test_an_operation_computes_on_the_values_before_their_format(self, tmp_path):
        (tmp_path / "out.txt").write_text("comparisons: 19900\nseconds: 0.016404\n")
        metrics = {
            "comparisons": {"type": "regex", "settings": {"file": "out.txt", "pattern": "comparisons: (.*)", "group_id": 1}},
            "seconds": {"type": "regex", "settings": {"file": "out.txt", "pattern": "seconds: (.*)", "group_id": 1}, "format": "%.0f"},
            "rate": {"type": "operation", "settings": {"op": "comparisons / seconds"}, "format": "%.1f"},
        }
        records, _units = ewr._extract_run_records(str(tmp_path), metrics)
        _meta, values = records[0]
        assert values["seconds"] == 0
        assert values["rate"] == round(19900 / 0.016404, 1)


######################################
# What the GUI editors keep
######################################

class TestEditorsKeepWhatTheyDoNotShow:
    def test_a_variable_keeps_its_unit(self):
        import odatix.gui.variable_editor as ve

        edited = {"max_speed": {"type": "list", "settings": {"list": [35, 45]}}}
        stored = {"max_speed": {"type": "list", "unit": "kmh", "settings": {"list": [35]}}}
        kept = ve.keep_unmanaged_keys(edited, stored)
        assert kept["max_speed"]["unit"] == "kmh"
        assert kept["max_speed"]["settings"] == {"list": [35, 45]}

    def test_list_entries_stay_numbers(self):
        import odatix.gui.variable_editor as ve

        variables = ve.build_variables_dict(
            ["n"], ["list"], [""], [""], [""], [""], [""], [""], [""], [""], [""],
            ["35, 45"], [""], [""], [""], [""],
        )
        assert variables["n"]["settings"]["list"] == [35, 45]

    @pytest.fixture
    def workflow_editor(self):
        import dash

        # dash.register_page (called at page-module import) requires an app
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.workflow_editor as workflow_editor

        return workflow_editor

    def test_a_task_keeps_phony(self, workflow_editor):

        edited = [{"name": "main", "commands": ["a"]}, {"name": "env", "commands": ["b"]}]
        stored = [{"name": "env", "phony": False, "commands": ["old"]}, {"name": "main", "commands": ["a"]}]
        kept = workflow_editor.keep_unmanaged_task_keys(edited, stored)
        assert kept == [{"name": "main", "commands": ["a"]}, {"name": "env", "commands": ["b"], "phony": False}]


class TestWorkflowCombinations:
    def test_command_domains_variables_and_configurations_count(self, tmp_path):
        from odatix.workspace import Workspace

        _write(tmp_path / "odatix.yml", "")
        base = tmp_path / "odatix_userconfig" / "workflows"
        # Parameter domains substituted into commands ("use_parameters: No").
        _write(base / "cli" / "_settings.yml", "use_parameters: No\ntasks:\n  - name: main\n")
        for domain, values in (("a", ("1", "2")), ("b", ("x", "y", "z"))):
            _write(base / "cli" / domain / "_settings.yml", "use_parameters: No\n")
            for value in values:
                _write(base / "cli" / domain / (value + ".txt"), value)
        # Configurations of the workflow itself, read by ${profile}.
        _write(base / "profile" / "_settings.yml", "use_parameters: No\ntasks:\n  - name: main\n")
        for value in ("fast", "slow"):
            _write(base / "profile" / (value + ".txt"), value)
        # Variables, two of them paired.
        _write(
            base / "vars" / "_settings.yml",
            "use_parameters: No\ntasks:\n  - name: main\nvariables:\n"
            "  p:\n    type: list\n    group: g\n    settings:\n      list: [1, 2]\n"
            "  q:\n    type: list\n    group: g\n    settings:\n      list: [3, 4]\n"
            "  r:\n    type: list\n    settings:\n      list: [5, 6, 7]\n",
        )
        ws = Workspace.open(str(tmp_path))
        assert ws.workflows["cli"].count_combinations() == 6
        assert ws.workflows["profile"].count_combinations() == 2
        assert ws.workflows["vars"].count_combinations() == 6
        assert len(ws.workflows["vars"].combinations()) == 6

class TestWorkflowEditorLayout:
    @pytest.fixture
    def workflow_editor(self):
        import dash

        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.workflow_editor as workflow_editor

        return workflow_editor

    def test_the_fields_the_save_callback_reads_are_there_on_load(self, workflow_editor):
        # They used to be rendered by a callback only: "A nonexistent object was
        # used in an Input" on every load of the page.
        def ids(component):
            found = []
            stack = [component]
            while stack:
                node = stack.pop()
                if isinstance(node, (list, tuple)):
                    stack.extend(node)
                    continue
                found.append(getattr(node, "id", None))
                children = getattr(node, "children", None)
                if children is not None:
                    stack.append(children)
            return found

        present = ids(workflow_editor.layout)
        for field in ("wf-source-path", "wf-use-parameters", "wf-progress-regex"):
            assert field in present


class TestWorkflowMetricsApi:
    def test_metrics_set_on_a_workflow_are_saved(self, tmp_path):
        import yaml
        from odatix.workspace import Workspace

        _write(tmp_path / "odatix.yml", "")
        _write(tmp_path / "odatix_userconfig" / "workflows" / "wf" / "_settings.yml", "tasks:\n  - name: main\n")
        workflow = Workspace.open(str(tmp_path)).workflows["wf"]
        assert workflow.metrics is workflow.metrics
        workflow.metrics.set("seconds", {"type": "json", "settings": {"file": "r.json", "key": "seconds"}})
        workflow.metrics.save()
        with open(workflow.metrics_path) as f:
            assert "seconds" in yaml.safe_load(f)["metrics"]


class TestPlanNamesColors:
    def test_plain_unless_a_terminal(self, monkeypatch):
        import odatix.lib.run_report as run_report

        plan = JobPlan()
        plan.add("\033[90mgrey\033[0m", Category.NEW)
        monkeypatch.setattr(run_report, "_stdout_is_a_terminal", lambda: False)
        assert plan.names() == ["grey"]
        monkeypatch.setattr(run_report, "_stdout_is_a_terminal", lambda: True)
        assert plan.names() == ["\033[90mgrey\033[0m"]
        assert plan.names(colored=False) == ["grey"]
