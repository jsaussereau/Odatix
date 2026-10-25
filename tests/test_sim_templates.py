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
from sim_fixtures import fake_program, fake_simulators  # noqa: F401 (fixture)

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
    with open(path, "w", encoding="utf-8") as f:
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
        "testbench": {
            "top": "tb", "files": ["tb/tb.sv"], "languages": ["sv"], "parameters": {"W": "8"}, "include_dirs": ["tb"],
        },
    }
    (tmp_path / "odatix_sim.yml").write_text(yaml.dump(info), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def report(directory):
    with open(os.path.join(str(directory), "sim_report.yml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestRunner:
    def test_what_to_run(self, sim_dir):
        sim = SimRunner("x")
        assert sim.tb_top == "tb"
        assert sim.files("sv") == ["rtl/a.sv", "rtl/b.sv", "tb/tb.sv"]
        assert sim.files("sv", testbench=False) == ["rtl/a.sv", "rtl/b.sv"]
        assert sim.files("sv", design=False) == ["tb/tb.sv"]
        assert sim.files("vhdl") == []
        assert sim.include_dirs == ["rtl/inc", "tb"]
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
        assert (sim_dir / "log" / "progress.log").read_text(encoding="utf-8").strip() == "progress: 100%"

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
                open(name + ".done", "w", encoding="utf-8").close()
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

def template_simulation(workspace, name, template, testbench):
    """A simulation starting from `template`, naming a copy of the Cordic testbench as its own."""
    sims = workspace / "odatix_userconfig" / "simulations"
    (sims / name / "tb").mkdir(parents=True)
    shutil.copy(str(workspace / "examples" / "cordic_tb" / testbench), str(sims / name / "tb" / testbench))
    settings = {
        "template": template,
        "testbench": {
            "files": ["tb/" + testbench],
            "parameters": {"WIDTH": "${width}", "ITERATIONS": "${iterations}"},
        },
    }
    (sims / name / "_settings.yml").write_text(yaml.dump(settings), encoding="utf-8")


def plan_names(plan, category):
    return [entry["name"] for entry in plan.entries if entry["category"] == category]


def prepared_info(workspace, simulation, architecture):
    """Prepare one job, and read the information file of its work directory."""
    Run(Workspace.open(), "simulation", simulations=[simulation], architectures=[architecture], noask=True).prepare()
    work = next(
        root for root, _dirs, files in os.walk(str(workspace / "work" / "simulations" / simulation))
        if "odatix_sim.yml" in files
    )
    with open(os.path.join(work, "odatix_sim.yml"), encoding="utf-8") as f:
        return work, yaml.safe_load(f)


def set_architecture_testbench(workspace, architecture, testbench):
    path = workspace / "odatix_userconfig" / "architectures" / architecture / "_settings.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["testbench"] = testbench
    path.write_text(yaml.dump(data), encoding="utf-8")


CORDIC = "Example_Cordic_{} + iterations/12 + width/8"


class TestRuns:
    def test_a_template_is_named_in_a_run(self, example_workspace, fake_simulators):
        plan = Run(Workspace.open(), "simulation", simulations=["ghdl"], architectures=[CORDIC.format("vhdl")]).check()
        assert [entry["name"] for entry in plan.entries] == ["ghdl: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]"]
        assert plan_names(plan, "error") == []

    def test_a_language_the_simulator_does_not_compile_is_refused_at_check(self, example_workspace, fake_simulators):
        run = Run(Workspace.open(), "simulation", simulations=["verilator", "ghdl"], architectures=[CORDIC.format("vhdl")])
        plan = run.check()
        assert plan_names(plan, "error") == ["verilator: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]"]
        assert any('"verilator" cannot compile vhdl' in str(message) for message in run.reporter.messages)

    def test_so_is_the_language_of_the_testbench(self, example_workspace, fake_simulators):
        set_architecture_testbench(example_workspace, "Example_Cordic_sv", {"files": ["examples/cordic_tb/tb_cordic.vhdl"]})
        with pytest.raises(RunError) as error:
            Run(Workspace.open(), "simulation", simulations=["verilator"], architectures=[CORDIC.format("sv")]).check()
        assert "cannot compile vhdl, the language of the testbench" in str(error.value)

    def test_a_simulator_that_is_not_installed_is_refused_at_check(self, example_workspace, fake_simulators):
        fake_program(fake_simulators, "vsim").unlink()
        os.environ["PATH"] = str(fake_simulators)
        run = Run(Workspace.open(), "simulation", simulations=["questa", "ghdl"], architectures=[CORDIC.format("vhdl")])
        plan = run.check()
        assert plan_names(plan, "error") == ["questa: Example_Cordic_vhdl/Example_Cordic_vhdl [iterations:12, width:8]"]
        assert any('"questa" runs "vsim", which is not in the PATH' in str(message) for message in run.reporter.messages)

    def test_an_unknown_simulation(self, example_workspace, fake_simulators):
        with pytest.raises(RunError) as error:
            Run(Workspace.open(), "simulation", simulations=["nosuch"], architectures=["Example_Counter_sv/08bits"]).check()
        assert "no template of that name" in str(error.value)

    def test_the_work_directory_gets_the_template_then_the_simulation(self, example_workspace, fake_simulators):
        template_simulation(example_workspace, "TB_mine", "questa", "tb_cordic.sv")
        sims = example_workspace / "odatix_userconfig" / "simulations"
        (sims / "TB_mine" / "run.py").write_text("# mine\n", encoding="utf-8")
        (sims / "TB_mine" / "_metrics.yml").write_text("metrics: {}\n", encoding="utf-8")

        work, info = prepared_info(example_workspace, "TB_mine", CORDIC.format("sv"))
        assert open(os.path.join(work, "run.py"), encoding="utf-8").read() == "# mine\n"
        assert info["testbench"]["parameters"] == {"WIDTH": "8", "ITERATIONS": "12"}
        with open(os.path.join(work, "sim_meta.yml"), encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        assert [os.path.basename(os.path.dirname(path)) for path in meta["metrics_files"]] == ["questa", "TB_mine"]


class TestTestbench:
    """Which testbench a job runs: the simulation's files, the architecture's, the "tb" directory."""

    def test_the_architecture_s_testbench(self, example_workspace, fake_simulators):
        work, info = prepared_info(example_workspace, "questa", CORDIC.format("vhdl"))
        assert info["testbench"] == {
            "top": "tb_cordic",
            "files": ["testbench/tb_cordic.vhdl"],
            "languages": ["vhdl"],
            "parameters": {"WIDTH": "8", "ITERATIONS": "12"},
            "include_dirs": [],
        }
        assert os.path.isfile(os.path.join(work, "testbench", "tb_cordic.vhdl"))

    def test_the_files_a_simulation_names_come_first(self, example_workspace, fake_simulators):
        template_simulation(example_workspace, "TB_mine", "questa", "tb_cordic.sv")
        _work, info = prepared_info(example_workspace, "TB_mine", CORDIC.format("vhdl"))
        assert info["testbench"]["files"] == ["tb/tb_cordic.sv"]

    def test_the_tb_directory_comes_last(self, example_workspace, fake_simulators):
        sims = example_workspace / "odatix_userconfig" / "simulations"
        (sims / "TB_dir" / "tb").mkdir(parents=True)
        (sims / "TB_dir" / "tb" / "tb_other.sv").write_text("module tb_other; endmodule\n", encoding="utf-8")
        (sims / "TB_dir" / "_settings.yml").write_text("template: questa\n", encoding="utf-8")

        _work, info = prepared_info(example_workspace, "TB_dir", CORDIC.format("vhdl"))
        assert info["testbench"]["files"] == ["testbench/tb_cordic.vhdl"]

        set_architecture_testbench(example_workspace, "Example_Cordic_vhdl", {})
        shutil.rmtree(str(example_workspace / "work"))
        _work, info = prepared_info(example_workspace, "TB_dir", CORDIC.format("vhdl"))
        assert info["testbench"]["files"] == ["tb/tb_other.sv"]
        assert info["testbench"]["top"] == "tb_other"

    def test_the_layout_of_the_files_is_kept(self, example_workspace, fake_simulators):
        bench = example_workspace / "bench"
        (bench / "inc").mkdir(parents=True)
        (bench / "tb_cordic.sv").write_text('`include "defs.svh"\nmodule tb_cordic; endmodule\n', encoding="utf-8")
        (bench / "inc" / "defs.svh").write_text("`define X 1\n", encoding="utf-8")
        (bench / "inc" / "helper.sv").write_text("module helper; endmodule\n", encoding="utf-8")
        set_architecture_testbench(example_workspace, "Example_Cordic_sv", {"files": ["bench/*.sv", "bench/inc/*"]})

        work, info = prepared_info(example_workspace, "questa", CORDIC.format("sv"))
        assert info["testbench"]["files"] == ["testbench/tb_cordic.sv", "testbench/inc/helper.sv"]
        assert os.path.isfile(os.path.join(work, "testbench", "inc", "defs.svh"))
        assert info["testbench"]["include_dirs"] == ["testbench", "testbench/inc"]

    def test_files_that_match_nothing_are_refused_at_check(self, example_workspace, fake_simulators):
        set_architecture_testbench(example_workspace, "Example_Cordic_sv", {"files": ["nowhere/*.sv"]})
        with pytest.raises(RunError) as error:
            Run(Workspace.open(), "simulation", simulations=["questa"], architectures=[CORDIC.format("sv")]).check()
        assert "match no file" in str(error.value)

    def test_the_setting_is_validated(self, example_workspace, fake_simulators):
        set_architecture_testbench(example_workspace, "Example_Cordic_sv", {"file": "tb.sv"})
        with pytest.raises(RunError) as error:
            Run(Workspace.open(), "simulation", simulations=["questa"], architectures=[CORDIC.format("sv")]).check()
        assert 'unknown keys: "file"' in str(error.value)


class TestExamples:
    """The Cordic examples: a testbench per language, run by any simulator."""

    CASES = [
        ("TB_Example_Cordic_GHDL", "vhdl"),
        ("TB_Example_Cordic_Verilator", "sv"),
        ("TB_Example_Cordic_QuestaSim", "vhdl"),
        ("TB_Example_Cordic_QuestaSim", "sv"),
        ("TB_Example_Cordic_Vivado", "vhdl"),
        ("TB_Example_Cordic_Icarus", "sv"),
        ("icarus", "sv"),
    ]
    TEMPLATES = {
        "TB_Example_Cordic_GHDL": "ghdl",
        "TB_Example_Cordic_Verilator": "verilator",
        "TB_Example_Cordic_QuestaSim": "questa",
        "TB_Example_Cordic_Vivado": "xsim",
        "TB_Example_Cordic_Icarus": "icarus",
        "icarus": "icarus",
    }

    def test_the_example_simulations_hold_no_script(self):
        from conftest import EXAMPLES_DIR

        for simulation in self.TEMPLATES:
            if simulation == "icarus":
                continue
            directory = os.path.join(EXAMPLES_DIR, "odatix_userconfig", "simulations", simulation)
            assert sorted(os.listdir(directory)) == ["_metrics.yml", "_settings.yml"], simulation

    @pytest.mark.integration
    @pytest.mark.parametrize("simulation, language", CASES)
    def test_cordic_runs_with_every_simulator(self, example_workspace, simulation, language):
        executable = SIMULATORS[self.TEMPLATES[simulation]]
        if shutil.which(executable) is None:
            pytest.skip("needs " + executable)
        import odatix.components.export_simulation_results as exp_sim_res

        jobs = Run(
            Workspace.open(), "simulation", simulations=[simulation], architectures=[CORDIC.format(language)], noask=True,
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
        # The template's metrics...
        assert metrics["sim_status"] == "passed"
        assert metrics["sim_errors"] == 0
        assert metrics["simulated_cycles"] > 0 and metrics["cycles_per_second"] > 0
        # ...and the testbench's, for the configuration run
        if simulation != "icarus":
            assert metrics["check_status"] == "OK"
            # The configuration is a dimension of the result, not a metric
            assert "width" not in metrics


class TestTutorial:
    """The design of the "Simulate your own RTL" tutorial: configurations built from a variable."""

    COUNTER = """
        module counter #(
          parameter BITS = 8
        )(
          input  wire            clock,
          input  wire            reset,
          input  wire            i_init,
          input  wire            i_inc_dec,
          output wire [BITS-1:0] o_value
        );
          reg [BITS-1:0] value;
          always @(posedge clock) begin
            if (reset)       value <= 0;
            else if (i_init) value <= 0;
            else             value <= i_inc_dec ? value + 1 : value - 1;
          end
          assign o_value = value;
        endmodule
        """
    TESTBENCH = """
        module tb_counter #(parameter BITS = 8);
          logic clock = 0, reset = 1;
          logic [BITS-1:0] o_value, expected = 0;
          counter #(.BITS(BITS)) dut (.clock(clock), .reset(reset), .i_init(1'b0), .i_inc_dec(1'b1), .o_value(o_value));
          always #5 clock = ~clock;
          initial begin
            repeat (2) @(negedge clock);
            reset = 0;
            repeat (100) begin
              @(posedge clock);
              #1;
              expected = expected + 1;
              if (o_value !== expected) $error("got %0d, expected %0d", o_value, expected);
            end
            $display("odatix_cycles: %0d", 100);
            $finish;
          end
        endmodule
        """
    SETTINGS = """
        rtl_path: "rtl"
        top_level_file: "counter.v"
        top_level_module: "counter"
        clock_signal: "clock"
        reset_signal: "reset"
        use_parameters: Yes
        start_delimiter: "#("
        stop_delimiter: ")("
        configurations:
          name: "${width}bits"
          template: "  parameter BITS = ${width}"
        variables:
          width:
            type: power_of_two
            settings:
              from: 8
              to: 32
        testbench:
          top: tb_counter
          files: [tb/tb_counter.sv]
          parameters:
            BITS: ${width}
        """

    @pytest.fixture
    def workspace(self, example_workspace):
        write(example_workspace, "rtl/counter.v", self.COUNTER)
        write(example_workspace, "tb/tb_counter.sv", self.TESTBENCH)
        write(example_workspace, "odatix_userconfig/architectures/MyCounter/_settings.yml", self.SETTINGS)
        return example_workspace

    def test_the_testbench_gets_the_variables_of_the_configuration(self, workspace, fake_simulators):
        for bits in ("8", "16", "32"):
            _work, info = prepared_info(workspace, "icarus", "MyCounter/" + bits + "bits")
            assert info["testbench"]["parameters"] == {"BITS": bits}
            shutil.rmtree(str(workspace / "work"))

    @pytest.mark.integration
    def test_it_runs(self, workspace):
        if shutil.which("iverilog") is None:
            pytest.skip("needs iverilog")
        jobs = Run(Workspace.open(), "simulation", simulations=["icarus"], architectures=["MyCounter/*"], noask=True).prepare().job_list
        assert len(jobs) == 3
        for job in jobs:
            completed = subprocess.run(job.command, shell=True, cwd=job.directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            assert completed.returncode == 0, completed.stdout[-2000:]
            assert report(job.directory)["cycles"] == 100
