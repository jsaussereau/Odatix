"""
Simulation templates: the simulations Odatix provides for each simulator
(odatix_sim_templates/, odatix.sim.templates), and the script helper they are
written with (odatix.sim.runner).
"""

import os
import shutil
import subprocess
import sys
import textwrap

import pytest
import yaml

import odatix.sim.templates as sim_templates
from odatix.sim.runner import SimRunner
from odatix.run import Run, RunError
from odatix.workspace import Workspace

SIMULATORS = {
    "ghdl": "ghdl",
    "verilator": "verilator",
    "questa": "vsim",
    "xsim": "xelab",
    "icarus": "iverilog",
}


def write(root, relpath, text):
    path = os.path.join(str(root), relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(textwrap.dedent(text))
    return path


######################################
# Finding a simulation
######################################

class TestResolve:
    def test_odatix_provides_a_template_per_simulator(self):
        templates = sim_templates.list_templates()
        assert set(SIMULATORS) <= set(templates)
        for name, directory in templates.items():
            settings = sim_templates.read_settings(directory)
            assert sim_templates.accepted_languages(settings), name
            assert settings.get(sim_templates.TEST_COMMAND_KEY), name
            assert os.path.isfile(os.path.join(directory, "run.py")), name
            assert os.path.isfile(os.path.join(directory, "_metrics.yml")), name

    def test_a_template_is_found_without_a_directory_of_its_own(self, tmp_path):
        directories, settings = sim_templates.resolve("ghdl", str(tmp_path))
        assert directories == [os.path.join(sim_templates.builtin_path(), "ghdl")]
        assert settings["languages"] == ["vhdl"]

    def test_a_simulation_starts_from_a_template(self, tmp_path):
        write(tmp_path, "TB/_settings.yml", """
            template: questa
            testbench:
              top: tb
            progress:
              regex: "x: ([0-9]+)%"
            """)
        directories, settings = sim_templates.resolve("TB", str(tmp_path))
        assert directories == [os.path.join(sim_templates.builtin_path(), "questa"), str(tmp_path / "TB")]
        assert settings["testbench"] == {"top": "tb"}
        # Mappings are merged key by key, the rest replaced.
        assert settings["progress"] == {"file": "log/progress.log", "regex": "x: ([0-9]+)%"}
        assert settings["tasks"][0]["name"] == "main"
        assert "template" not in settings

    def test_the_workspace_overrides_a_template(self, tmp_path):
        write(tmp_path, "ghdl/_settings.yml", "languages: [vhdl, sv]\n")
        directories, settings = sim_templates.resolve("ghdl", str(tmp_path))
        assert directories == [str(tmp_path / "ghdl")]
        assert settings == {"languages": ["vhdl", "sv"]}

    def test_a_simulation_named_after_its_template_starts_from_odatix_s(self, tmp_path):
        write(tmp_path, "ghdl/_settings.yml", "template: ghdl\ndescription: mine\n")
        directories, settings = sim_templates.resolve("ghdl", str(tmp_path))
        assert directories == [os.path.join(sim_templates.builtin_path(), "ghdl"), str(tmp_path / "ghdl")]
        assert settings["description"] == "mine"
        assert settings["languages"] == ["vhdl"]

    def test_a_chain_of_workspace_templates(self, tmp_path):
        write(tmp_path, "base/_settings.yml", "template: xsim\ndescription: base\n")
        write(tmp_path, "TB/_settings.yml", "template: base\n")
        directories, settings = sim_templates.resolve("TB", str(tmp_path))
        assert [os.path.basename(d) for d in directories] == ["xsim", "base", "TB"]
        assert settings["description"] == "base"

    def test_errors(self, tmp_path):
        with pytest.raises(sim_templates.SimulationNotFound) as error:
            sim_templates.resolve("nowhere", str(tmp_path))
        assert "ghdl" in str(error.value)
        write(tmp_path, "TB/_settings.yml", "template: nosuch\n")
        with pytest.raises(sim_templates.TemplateError) as error:
            sim_templates.resolve("TB", str(tmp_path))
        assert 'Unknown template "nosuch"' in str(error.value)
        write(tmp_path, "A/_settings.yml", "template: B\n")
        write(tmp_path, "B/_settings.yml", "template: A\n")
        with pytest.raises(sim_templates.TemplateError):
            sim_templates.resolve("A", str(tmp_path))


######################################
# The script helper
######################################

def python_command(code):
    return [sys.executable, "-c", textwrap.dedent(code)]


@pytest.fixture
def sim_dir(tmp_path, monkeypatch):
    """A work directory holding the information file a template reads."""
    info = {
        "dut": {"top": "dut", "languages": ["sv"]},
        "sources": {"vhdl": [], "verilog": [], "sv": ["rtl/a.sv", "rtl/b.sv"], "include_dirs": ["rtl/inc"]},
        "testbench": {"top": "tb", "files": ["tb/tb.sv"], "languages": ["sv"], "parameters": {"W": "8"}},
    }
    (tmp_path / "odatix_sim.yml").write_text(yaml.dump(info))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def report(directory):
    with open(os.path.join(str(directory), "sim_report.yml")) as f:
        return yaml.safe_load(f)


class TestRunner:
    def test_what_to_run(self, sim_dir):
        sim = SimRunner("x")
        assert sim.tb_top == "tb"
        assert sim.files("sv") == ["rtl/a.sv", "rtl/b.sv", "tb/tb.sv"]
        assert sim.files("sv", testbench=False) == ["rtl/a.sv", "rtl/b.sv"]
        assert sim.files("sv", design=False) == ["tb/tb.sv"]
        assert sim.files("vhdl") == []
        assert sim.include_dirs == ["rtl/inc"]
        assert sim.tb_parameters == {"W": "8"}

    def test_a_language_it_does_not_compile_is_refused(self, sim_dir):
        with pytest.raises(SystemExit):
            SimRunner("ghdl", languages=["vhdl"])
        assert report(sim_dir)["status"] == "failed"
        assert "ghdl cannot compile sv" in report(sim_dir)["message"]

    def test_a_passing_simulation(self, sim_dir):
        sim = SimRunner("x")
        sim.run("compile", python_command('print("Warning: careful")'), log="build")
        sim.run(
            "simulate",
            python_command("""
                import time
                print("elaborated", flush=True)
                time.sleep(0.2)
                print("odatix_cycles: 1000")
            """),
            elaborated_mark="elaborated",
        )
        with pytest.raises(SystemExit) as end:
            sim.finish()
        assert end.value.code == 0
        result = report(sim_dir)
        assert result["status"] == "passed"
        assert result["warnings"] == 1 and result["errors"] == 0
        assert result["cycles"] == 1000
        assert result["simulation_time"] >= 0.2 > result["elaboration_time"]
        assert result["cycles_per_second"] > 0
        assert os.path.isfile(str(sim_dir / "log" / "build.log"))
        assert (sim_dir / "log" / "progress.log").read_text().strip() == "progress: 100%"

    def test_an_error_message_fails_it(self, sim_dir):
        sim = SimRunner("x")
        sim.run("simulate", python_command('print("# ** Error: assertion failed")'))
        with pytest.raises(SystemExit) as end:
            sim.finish()
        assert end.value.code == 1
        assert report(sim_dir)["status"] == "failed"

    def test_a_failing_command_stops_it(self, sim_dir):
        sim = SimRunner("x")
        with pytest.raises(SystemExit):
            sim.run("compile", python_command("import sys; sys.exit(3)"))
        assert "exited with code 3" in report(sim_dir)["message"]

    def test_compiling_until_everything_compiles(self, sim_dir):
        """A file compiles once the files it needs did: the order is found by retrying."""
        compiler = python_command("""
            import os, sys
            needs = {"a": "b", "b": "c"}
            for name in sys.argv[1:]:
                if name in needs and not os.path.exists(needs[name] + ".done"):
                    print("Error: " + name + " needs " + needs[name])
                    sys.exit(1)
                open(name + ".done", "w").close()
        """)
        sim = SimRunner("x")
        sim.compile(["a", "b", "c"], lambda files: compiler + files)
        assert all(os.path.exists(str(sim_dir / (name + ".done"))) for name in "abc")
        # The errors of the attempts in the wrong order are not the design's.
        assert sim.report["errors"] == 0

    def test_a_file_that_never_compiles(self, sim_dir):
        compiler = python_command("""
            import sys
            if "bad" in sys.argv[1:]:
                print("Error: bad")
                sys.exit(1)
        """)
        sim = SimRunner("x")
        with pytest.raises(SystemExit):
            sim.compile(["good", "bad"], lambda files: compiler + files)
        assert "compile failed for bad" in report(sim_dir)["message"]


######################################
# Runs
######################################

def template_simulation(workspace, name, template, testbench, parameters=True):
    """A simulation starting from `template`, holding only the Cordic testbench."""
    sims = workspace / "odatix_userconfig" / "simulations"
    source = sims / ("TB_Example_Cordic_GHDL/tb/tb_cordic.vhdl" if testbench.endswith(".vhdl") else "TB_Example_Cordic_QuestaSim/tb/tb_cordic.sv")
    (sims / name / "tb").mkdir(parents=True)
    shutil.copy(str(source), str(sims / name / "tb" / testbench))
    settings = {"template": template}
    if parameters:
        settings["testbench"] = {"parameters": {"WIDTH": "${width}", "ITERATIONS": "${iterations}"}}
    (sims / name / "_settings.yml").write_text(yaml.dump(settings))


def plan_names(plan, category):
    return [entry["name"] for entry in plan.entries if entry["category"] == category]


class TestRuns:
    def test_a_template_is_named_in_a_run(self, example_workspace):
        plan = Run(
            Workspace.open(), "simulation", simulations=["ghdl"],
            architectures=["Example_Cordic_vhdl + iterations/12 + width/8"],
        ).check()
        assert [entry["name"] for entry in plan.entries] == ["ghdl: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]"]
        assert plan_names(plan, "error") == []

    def test_a_language_the_simulator_does_not_compile_is_refused_at_check(self, example_workspace):
        run = Run(
            Workspace.open(), "simulation", simulations=["verilator", "ghdl"],
            architectures=["Example_Cordic_vhdl + iterations/12 + width/8"],
        )
        plan = run.check()
        assert plan_names(plan, "error") == ["verilator: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]"]
        assert any('"verilator" cannot compile vhdl' in str(message) for message in run.reporter.messages)

    def test_an_unknown_simulation(self, example_workspace):
        with pytest.raises(RunError) as error:
            Run(Workspace.open(), "simulation", simulations=["nosuch"], architectures=["Example_Counter_sv/08bits"]).check()
        assert "no template of that name" in str(error.value)

    def test_the_work_directory_gets_the_template_then_the_simulation(self, example_workspace):
        template_simulation(example_workspace, "TB_mine", "questa", "tb_cordic.sv")
        sims = example_workspace / "odatix_userconfig" / "simulations"
        (sims / "TB_mine" / "run.py").write_text("# mine\n")
        (sims / "TB_mine" / "_metrics.yml").write_text("metrics: {}\n")

        Run(
            Workspace.open(), "simulation", simulations=["TB_mine"],
            architectures=["Example_Cordic_sv + iterations/12 + width/8"], noask=True,
        ).prepare()
        work = next(
            root for root, _dirs, files in os.walk(str(example_workspace / "work" / "simulations" / "TB_mine"))
            if "odatix_sim.yml" in files
        )
        assert open(os.path.join(work, "run.py")).read() == "# mine\n"
        with open(os.path.join(work, "odatix_sim.yml")) as f:
            info = yaml.safe_load(f)
        assert info["testbench"]["parameters"] == {"WIDTH": "8", "ITERATIONS": "12"}
        with open(os.path.join(work, "sim_meta.yml")) as f:
            meta = yaml.safe_load(f)
        assert [os.path.basename(os.path.dirname(path)) for path in meta["metrics_files"]] == ["questa", "TB_mine"]

    CASES = [
        ("ghdl", "tb_cordic.vhdl", "Example_Cordic_vhdl"),
        ("verilator", "tb_cordic.sv", "Example_Cordic_sv"),
        ("questa", "tb_cordic.sv", "Example_Cordic_vhdl"),
        ("questa", "tb_cordic.sv", "Example_Cordic_sv"),
        ("xsim", "tb_cordic.sv", "Example_Cordic_vhdl"),
        ("icarus", "tb_cordic.sv", "Example_Cordic_sv"),
    ]

    @pytest.mark.integration
    @pytest.mark.parametrize("template, testbench, architecture", CASES)
    def test_cordic_runs_with_every_simulator(self, example_workspace, template, testbench, architecture):
        if shutil.which(SIMULATORS[template]) is None:
            pytest.skip("needs " + SIMULATORS[template])
        import odatix.components.export_simulation_results as exp_sim_res

        template_simulation(example_workspace, "TB_" + template, template, testbench)
        jobs = Run(
            Workspace.open(), "simulation", simulations=["TB_" + template],
            architectures=[architecture + " + iterations/12 + width/8"], noask=True,
        ).prepare().job_list
        assert len(jobs) == 1
        job = jobs[0]
        completed = subprocess.run(
            job.command, shell=True, cwd=job.directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        assert completed.returncode == 0, completed.stdout[-3000:]

        work_root = str(example_workspace / "work" / "simulations")
        sim_path = str(example_workspace / "odatix_userconfig" / "simulations")
        records, _units = exp_sim_res._extract_records_for_run(job.directory, work_root, sim_path)
        metrics = records[0]["metrics"]
        assert metrics["sim_status"] == "passed"
        assert metrics["sim_errors"] == 0
        assert metrics["simulation_time"] > 0
        # The testbench's own result file was written, with the configuration's width.
        with open(os.path.join(job.directory, "results.yml")) as f:
            assert yaml.safe_load(f)["width"] == 8
