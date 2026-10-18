"""
The simulation templates in the GUI and the Python API: the simulation editor
(template, testbench), the Simulations section of Run jobs and the simulators
of the /tools page.
"""

import os

import pytest
import yaml

dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")

import odatix.sim.templates as sim_templates
from odatix.run import Run
from odatix.workspace import Workspace
from sim_fixtures import fake_simulators  # noqa: F401 (fixture)


@pytest.fixture
def pages():
    """dash.register_page, called when a page module is imported, needs an app."""
    dash.Dash(__name__, use_pages=True, pages_folder="")


######################################
# Python API
######################################

class TestApi:
    def test_a_new_simulation_holds_no_deprecated_key_and_runs(self, example_workspace, fake_simulators):
        ws = Workspace.open()
        simulation = ws.simulations.create(
            "TB_new", template="questa", testbench={"parameters": {"WIDTH": "${width}"}},
        )
        written = yaml.safe_load(open(simulation.settings_path).read())
        assert written == {"template": "questa", "testbench": {"parameters": {"WIDTH": "${width}"}}}
        plan = Run(ws, "simulation", simulations=["TB_new"], architectures=["Example_Cordic_vhdl + iterations/12 + width/8"]).check()
        assert [entry["category"] for entry in plan.entries] == ["new"]

    def test_metrics_set_on_a_simulation_are_saved(self, example_workspace):
        simulation = Workspace.open().simulations.create("TB_new", tasks=[{"name": "main", "commands": ["true"]}])
        simulation.metrics.set("cycles", {"type": "yaml", "settings": {"file": "r.yml", "key": "c"}})
        simulation.metrics.save()
        assert "cycles" in yaml.safe_load(open(simulation.metrics_path).read())["metrics"]

    def test_the_templates_are_listed_apart_from_the_simulations(self, example_workspace):
        simulations = Workspace.open().simulations
        assert simulations.templates() == list(sim_templates.list_templates())
        assert "ghdl" not in simulations
        simulations.create("ghdl", template="ghdl")
        assert "ghdl" not in simulations.templates()


######################################
# Simulation editor
######################################

class TestSimulationEditor:
    @pytest.fixture
    def editor(self, pages):
        import odatix.gui.pages.sim_editor as sim_editor

        return sim_editor

    def test_the_testbench_keeps_only_what_it_sets(self, editor):
        assert editor.normalize_testbench(None) == {}
        assert editor.normalize_testbench({"top": "", "files": [], "parameters": {}, "cycles": None, "waves": ""}) == {}
        assert editor.normalize_testbench({
            "top": "tb", "files": "tb/a.sv", "parameters": {"W": 8}, "cycles": "50", "stimulus": "zero", "waves": "no",
        }) == {"top": "tb", "files": ["tb/a.sv"], "parameters": {"W": "8"}, "cycles": 50, "stimulus": "zero", "waves": False}

    def test_parameters_are_written_one_per_line(self, editor):
        text = "WIDTH: ${width}\n\n  DEPTH : 4 \nnot a parameter\n"
        parameters = editor.parse_parameters_text(text)
        assert parameters == {"WIDTH": "${width}", "DEPTH": "4"}
        assert editor.parse_parameters_text(editor.format_parameters(parameters)) == parameters

    def test_the_templates_are_offered(self, editor):
        values = [option["value"] for option in editor.template_options()]
        assert values[0] == "" and set(sim_templates.list_templates()) <= set(values)
        assert "mine" in [option["value"] for option in editor.template_options(current_template="mine")]

    def test_what_a_template_brings_is_said(self, editor, example_workspace):
        path = Workspace.open().simulations.path
        inherited = editor.template_settings("ghdl", path)
        assert "compiles vhdl" in editor.template_note("ghdl", inherited)
        assert "Makefile" in editor.template_note("", {})
        assert 'tasks of the template "ghdl"' in editor.default_task_text("ghdl")
        assert "make sim" in editor.default_task_text("")

    def test_the_testbench_shows_what_it_inherits(self, editor, example_workspace):
        ws = Workspace.open()
        ws.simulations.create("TB_base", template="xsim", testbench={"top": "tb_x", "files": ["tb/x.sv"], "cycles": 10})
        top, files, parameters, cycles = editor.testbench_placeholders(editor.template_settings("TB_base", ws.simulations.path))
        assert (top, files, cycles) == ("tb_x", "tb/x.sv", "10")
        top, files, _parameters, cycles = editor.testbench_placeholders({})
        assert "Guessed" in top and "generated" in files and cycles == "1000"

    def test_settings_round_trip(self, editor, example_workspace):
        simulations = Workspace.open().simulations
        simulation = simulations["TB_Example_Cordic_GHDL"]
        settings = editor.normalize_simulation_settings(editor.settings_as_written(simulation.settings))
        assert settings["template"] == "ghdl"
        settings["testbench"] = {"parameters": {"WIDTH": "${width}"}, "cycles": 20}
        simulation.update(dict(settings, architectures=editor.architectures_to_yaml(settings["architectures"])))
        reloaded = editor.normalize_simulation_settings(
            editor.settings_as_written(simulations["TB_Example_Cordic_GHDL"].reload().settings)
        )
        assert reloaded == settings

    def test_the_form_holds_the_template_and_testbench_fields(self, editor):
        form = editor.sim_form(editor.normalize_simulation_settings({"template": "questa"}), {}, "")
        ids = set()

        def walk(component):
            if isinstance(component, (list, tuple)):
                for child in component:
                    walk(child)
                return
            identifier = getattr(component, "id", None)
            if isinstance(identifier, str):
                ids.add(identifier)
            walk(getattr(component, "children", None) or [])

        walk(form)
        assert {
            "sim-template", "sim-template-note", "sim-testbench-top", "sim-testbench-files",
            "sim-testbench-parameters", "sim-testbench-cycles", "sim-testbench-stimulus", "sim-testbench-waves",
        } <= ids


######################################
# Run jobs
######################################

class TestRunJobs:
    @pytest.fixture
    def jobs(self, pages):
        import odatix.gui.pages.jobs_config  # noqa: F401 (registers the page)
        import odatix.gui.jobs_config.context as context
        import odatix.gui.jobs_config.simulation as simulation

        return context, simulation

    def test_the_templates_are_shown_after_the_simulations(self, jobs, example_workspace):
        context, _simulation = jobs
        run = context._run_context("?type=simulation", {})
        names = Workspace.open().simulations.names()
        assert run["instances"] == names + list(sim_templates.list_templates())
        assert run["templates"] == list(sim_templates.list_templates())

    def test_only_compatible_architectures_are_offered(self, jobs, example_workspace):
        _context, simulation = jobs
        ws = Workspace.open()
        names = ws.architectures.names()
        ghdl = simulation.compatible_architectures(ws, "ghdl", names)
        verilator = simulation.compatible_architectures(ws, "verilator", names)
        assert "Example_Cordic_vhdl" in ghdl and "Example_Cordic_sv" not in ghdl
        assert "Example_Cordic_sv" in verilator and "Example_Cordic_vhdl" not in verilator
        # A generated RTL is only known once generated: offered to every simulator.
        assert "Example_Counter_chisel" in ghdl and "Example_Counter_chisel" in verilator
        # A simulation that says nothing of its languages runs on anything
        assert simulation.compatible_architectures(ws, "TB_Example_Counter_GHDL", names) == names

    def test_a_template_card(self, jobs, example_workspace):
        context, simulation = jobs
        run = context._run_context("?type=simulation", {})
        sections, _baseline, listed = simulation._simulation_job_sections(run, {})
        assert listed["questa"] == []
        card = sections[run["instances"].index("questa")]
        text = str(card)
        assert "Odatix template" in text
        assert "/sim_editor?template=questa" in text

    def test_saving_never_writes_a_template_directory(self, jobs, example_workspace):
        _context, simulation = jobs
        ws = Workspace.open()
        simulation._save_listed_architectures(ws, {"ghdl": ["Example_Counter_vhdl"]}, {"ghdl": []})
        assert not os.path.exists(os.path.join(ws.simulations.path, "ghdl"))
        assert sim_templates.resolve("ghdl", ws.simulations.path)[0] == [
            os.path.join(sim_templates.builtin_path(), "ghdl")
        ]


######################################
# /tools
######################################

class TestToolsPage:
    @pytest.fixture
    def tools(self, pages):
        import odatix.gui.pages.tools as tools

        return tools

    def test_a_card_per_simulator(self, tools):
        cards = tools.build_simulator_cards()
        assert len(cards) == len(sim_templates.list_templates())
        assert "checking..." in str(cards[0])

    def test_the_badge_says_whether_it_is_installed(self, tools, fake_simulators):
        assert tools.check_simulator("ghdl") == ("installed", "odx-badge success")
        (fake_simulators / "ghdl").write_text("#!/bin/sh\nexit 1\n")
        assert tools.check_simulator("ghdl") == ("not installed", "odx-badge caution")
        os.environ["PATH"] = str(fake_simulators)
        (fake_simulators / "ghdl").unlink()
        assert tools.check_simulator("ghdl") == ("not installed", "odx-badge caution")
