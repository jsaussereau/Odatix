"""
Non-regression tests of the 2nd "new user" campaign, simulations domain:
simulation editor (save, layout, template choice, architectures offered),
runner times and build parallelism, example metrics.
"""

import os

import pytest
import yaml

dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")

import odatix.sim.design_info as design_info
from odatix.sim.runner import SimRunner
from odatix.workspace import Workspace

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "sources", "odatix_examples", "odatix_userconfig", "simulations")


@pytest.fixture
def editor():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.sim_editor as sim_editor
    return sim_editor


def _walk(component, found):
    if isinstance(component, (list, tuple)):
        for child in component:
            _walk(child, found)
        return
    found.append(component)
    _walk(getattr(component, "children", None) or [], found)


class TestSimulationEditor:
    def test_saving_twice_writes_the_new_testbench_and_progress(self, editor, example_workspace):
        """SIM-102 follow-up: a block already in the file was never rewritten."""
        simulations = Workspace.open().simulations
        simulation = simulations.create("TB_r2", template="ghdl")
        for top, log in (("tb_a", "a.log"), ("tb_b", "b.log")):
            settings = editor.normalize_simulation_settings({
                "template": "ghdl", "testbench": {"top": top}, "progress": {"file": log, "regex": "r"},
            })
            editor.save_simulation(simulation, settings)
        written = yaml.safe_load(open(simulation.settings_path, encoding="utf-8").read())
        assert written["testbench"] == {"top": "tb_b"}
        assert written["progress"]["file"] == "b.log"

    def test_the_url_is_rewritten_without_reloading(self, editor):
        """SIM-102: a reload dropped "Saved." and aborted callbacks."""
        found = []
        _walk(editor.layout, found)
        locations = [c for c in found if type(c).__name__ == "Location"]
        assert locations and all(c.refresh is False for c in locations)

    def test_the_form_is_two_flex_columns(self, editor):
        """UG-06: a menu in a CSS column opened in the next column."""
        form = editor.sim_form(editor.normalize_simulation_settings({}), {}, "")
        assert "sim-form" in form.className
        assert [child.className for child in form.children] == ["sim-form-column"] * 2

    def test_a_new_simulation_starts_from_an_installed_template(self, editor, monkeypatch):
        monkeypatch.setattr(editor, "template_installed", lambda name: name == "ghdl")
        assert editor.default_template() == "ghdl"
        monkeypatch.setattr(editor, "template_installed", lambda name: False)
        assert editor.default_template() == ""
        labels = {o["value"]: o["label"] for o in editor.template_options()}
        assert labels["ghdl"].endswith("not installed")

    def test_nothing_to_run_is_said(self, editor, tmp_path):
        assert "Nothing to run" in editor.run_warning("", [], str(tmp_path))
        assert editor.run_warning("ghdl", [], str(tmp_path)) == ""
        assert editor.run_warning("", ["main"], str(tmp_path)) == ""
        (tmp_path / "Makefile").write_text("sim:\n", encoding="utf-8")
        assert editor.run_warning("", [], str(tmp_path)) == ""

    def test_architectures_the_template_cannot_compile_are_greyed(self, editor, example_workspace):
        options = editor.architecture_options(None, accepted=["verilog", "sv"])
        by_value = {o["value"]: o for o in options}
        assert by_value["Example_Cordic_vhdl"].get("disabled") is True
        assert not by_value["Example_Cordic_sv"].get("disabled")
        assert "Example_Cordic_vhdl" not in editor.compatible_architecture_names(None, ["verilog", "sv"])


class TestRunner:
    def _sim_dir(self, tmp_path, monkeypatch, parallel_jobs):
        monkeypatch.chdir(tmp_path)
        info = {"dut": {"top": "x", "languages": ["sv"]}, "testbench": {"top": "tb", "files": ["tb.sv"]}}
        if parallel_jobs:
            info["parallel_jobs"] = parallel_jobs
        design_info.write_info(str(tmp_path), info)

    def test_unmeasured_stages_have_no_time(self, tmp_path, monkeypatch):
        """SIM-112: elaboration_time was exported as 0.0 for Verilator."""
        self._sim_dir(tmp_path, monkeypatch, 2)
        sim = SimRunner("x")
        with pytest.raises(SystemExit):
            sim.finish()
        report = yaml.safe_load((tmp_path / "sim_report.yml").read_text(encoding="utf-8"))
        assert report["elaboration_time"] is None and report["compile_time"] is None

    def test_the_cores_are_shared_among_the_jobs(self, tmp_path, monkeypatch):
        self._sim_dir(tmp_path, monkeypatch, 10 ** 6)
        assert SimRunner("x").build_jobs == 1

    def test_verilator_does_not_take_every_core(self):
        run_py = os.path.join(os.path.dirname(__file__), "..", "sources", "odatix_sim_templates", "verilator", "run.py")
        text = open(run_py, encoding="utf-8").read()
        assert '"-j", "0"' not in text and "sim.build_jobs" in text
        metrics = yaml.safe_load(open(os.path.join(os.path.dirname(run_py), "_metrics.yml"), encoding="utf-8"))["metrics"]
        assert "elaboration_time" not in metrics


def test_cordic_examples_do_not_repeat_status_or_dimensions():
    """SIM-116."""
    for name in ("Verilator", "GHDL", "QuestaSim", "Vivado"):
        metrics = yaml.safe_load(open(os.path.join(EXAMPLES, "TB_Example_Cordic_" + name, "_metrics.yml"), encoding="utf-8"))["metrics"]
        assert "status" not in metrics and "check_status" in metrics
        assert not {"width", "iterations", "cycles"} & set(metrics)
