"""
The "architectures" block of a simulation settings file: what a simulation runs
on, and what it changes for each of those architectures.
"""

import os

import pytest

import odatix.workspace.sim_architectures as sim_architectures


######################################
# Reading
######################################

class TestParse:
    def test_a_list_of_names(self):
        entries = sim_architectures.parse(["Example_Cordic_sv", "Example_Cordic_vhdl"])
        assert sim_architectures.names(entries) == ["Example_Cordic_sv", "Example_Cordic_vhdl"]
        assert all(entry.settings == {} for entry in entries)

    def test_a_name_holding_its_settings(self):
        entries = sim_architectures.parse([
            {"Example_Cordic_sv": {"param_domains": {"width": {"param_target_file": "tb.sv"}}}}
        ])
        assert entries[0].name == "Example_Cordic_sv"
        assert entries[0].param_domains == {"width": {"param_target_file": "tb.sv"}}

    def test_settings_written_next_to_the_name(self):
        # What YAML makes of settings indented like the name itself. One space
        # apart from the form above, and meaning the same thing.
        entries = sim_architectures.parse([
            {"Example_Cordic_sv": None, "metrics_file": "_metrics_sv.yml"}
        ])
        assert entries[0].name == "Example_Cordic_sv"
        assert entries[0].metrics_file == "_metrics_sv.yml"

    def test_a_mapping_of_names(self):
        entries = sim_architectures.parse({"A": {"metrics_file": "a.yml"}, "B": None})
        assert sim_architectures.names(entries) == ["A", "B"]
        assert entries[0].metrics_file == "a.yml"

    def test_nothing_at_all(self):
        assert sim_architectures.parse(None) == []
        assert sim_architectures.parse([]) == []

    def test_an_entry_naming_nothing_is_reported(self):
        messages = []
        entries = sim_architectures.parse([{"param_domains": {"width": {}}}], messages=messages)
        assert entries == []
        assert [message.level for message in messages] == ["error"]

    def test_an_ambiguous_entry_is_reported(self):
        messages = []
        entries = sim_architectures.parse(
            [{"A": None, "B": None, "metrics_file": "a.yml"}], messages=messages
        )
        assert entries == []
        assert [message.level for message in messages] == ["error"]


######################################
# Applying
######################################

class TestSettingsFor:
    def test_only_the_matching_entries_apply(self):
        entries = sim_architectures.parse([
            {"Example_Cordic_vhdl": {"param_domains": {"width": {"param_target_file": "tb.vhdl"}}}},
            {"Example_Cordic_sv": {"param_domains": {"width": {"param_target_file": "tb.sv"}}}},
        ])
        settings = sim_architectures.settings_for(entries, "Example_Cordic_sv")
        assert settings["param_domains"]["width"]["param_target_file"] == "tb.sv"

    def test_an_architecture_that_matches_nothing_gets_nothing(self):
        entries = sim_architectures.parse([{"A": {"metrics_file": "a.yml"}}])
        assert sim_architectures.settings_for(entries, "B") == {}
        assert not sim_architectures.matches(entries, "B")

    def test_a_wildcard_covers_every_architecture(self):
        entries = sim_architectures.parse([{"*": {"param_domains": {"width": {"use_parameters": False}}}}])
        assert sim_architectures.matches(entries, "Anything")
        assert sim_architectures.settings_for(entries, "Anything")["param_domains"]["width"] == {
            "use_parameters": False
        }

    def test_a_named_entry_refines_a_wildcard_written_before_it(self):
        entries = sim_architectures.parse([
            {"*": {"param_domains": {"width": {"param_target_file": "tb.sv", "use_parameters": True}}}},
            {"Example_Cordic_vhdl": {"param_domains": {"width": {"param_target_file": "tb.vhdl"}}}},
        ])
        width = sim_architectures.settings_for(entries, "Example_Cordic_vhdl")["param_domains"]["width"]
        # The named entry replaces what it says, and inherits the rest.
        assert width == {"param_target_file": "tb.vhdl", "use_parameters": True}
        assert sim_architectures.settings_for(entries, "Other")["param_domains"]["width"][
            "param_target_file"
        ] == "tb.sv"


######################################
# Writing
######################################

class TestToYaml:
    def test_an_architecture_without_settings_stays_a_bare_name(self):
        entries = sim_architectures.parse(["A", {"B": {"metrics_file": "b.yml"}}])
        assert sim_architectures.to_yaml(entries) == ["A", {"B": {"metrics_file": "b.yml"}}]

    def test_round_trip(self):
        written = [
            {"A": {"param_domains": {"width": {"use_parameters": False}}}},
            "B",
        ]
        assert sim_architectures.to_yaml(sim_architectures.parse(written)) == written


######################################
# What a run does with it
######################################

@pytest.mark.integration
class TestSimulationHandlerReadsIt:
    def _handler(self):
        import odatix.lib.hard_settings as hard_settings
        from odatix.lib.simulation_handler import SimulationHandler

        return SimulationHandler(
            work_path="work/simulations",
            arch_path="odatix_userconfig/architectures",
            sim_path="odatix_userconfig/simulations",
            work_rtl_path=hard_settings.work_rtl_path,
            work_script_path=hard_settings.work_script_path,
            work_log_path=hard_settings.work_log_path,
            log_path=hard_settings.work_log_path,
            param_settings_filename=hard_settings.param_settings_filename,
            sim_settings_filename=hard_settings.sim_settings_filename,
            sim_makefile_filename="Makefile",
            overwrite=False,
        )

    def _write(self, sim, settings):
        os.makedirs("odatix_userconfig/simulations/" + sim, exist_ok=True)
        with open("odatix_userconfig/simulations/" + sim + "/_settings.yml", "w", encoding="utf-8") as f:
            f.write(settings)

    TASKS = "tasks:\n  - name: main\n    commands:\n      - 'echo hello'\n"

    def test_an_unlisted_architecture_still_runs(self, example_workspace, capsys):
        self._write("TB_Listed", "architectures:\n  - Some_Other_Design\n" + self.TASKS)
        handler = self._handler()
        simulations = handler.get_simulations(
            [{"TB_Listed": ["Example_Counter_verilog/04bits"]}]
        )
        assert len(simulations) == 1
        assert "not one of the architectures" in capsys.readouterr().out

    def test_a_listed_architecture_says_nothing(self, example_workspace, capsys):
        self._write("TB_Listed", "architectures:\n  - Example_Counter_verilog\n" + self.TASKS)
        handler = self._handler()
        assert len(handler.get_simulations([{"TB_Listed": ["Example_Counter_verilog/04bits"]}])) == 1
        assert "not one of the architectures" not in capsys.readouterr().out

    def test_param_domains_of_another_architecture_are_ignored(self, example_workspace):
        # A target file that does not exist would be reported if it applied.
        self._write(
            "TB_Listed",
            "architectures:\n"
            "  - Example_Counter_vhdl:\n"
            "      param_domains:\n"
            "        MEM:\n"
            "          param_file: no_such_file.txt\n"
            "  - Example_Counter_verilog\n" + self.TASKS,
        )
        handler = self._handler()
        assert len(handler.get_simulations([{"TB_Listed": ["Example_Counter_verilog/04bits"]}])) == 1

    def test_the_previous_top_level_keys_are_rejected(self, example_workspace, capsys):
        self._write(
            "TB_Listed",
            "param_domains:\n  MEM:\n    use_parameters: No\n" + self.TASKS,
        )
        handler = self._handler()
        assert handler.get_simulations([{"TB_Listed": ["Example_Counter_verilog/04bits"]}]) == []
        assert "is not read anymore" in capsys.readouterr().out


######################################
# What a simulation substitutes
######################################

class TestCombineMode:
    def test_replacing_is_the_default(self):
        assert sim_architectures.combine_mode({}) == sim_architectures.COMBINE_REPLACE

    def test_doing_both_is_asked_for(self):
        assert sim_architectures.combine_mode({"combine": "Both"}) == sim_architectures.COMBINE_BOTH

    def test_the_former_name_still_asks_for_both(self):
        assert sim_architectures.combine_mode({"combine": "append"}) == sim_architectures.COMBINE_BOTH

    def test_an_unknown_mode_replaces(self):
        assert sim_architectures.combine_mode({"combine": "sideways"}) == sim_architectures.COMBINE_REPLACE

    def test_the_substitutions_after_the_first_are_added(self):
        # Listing several of them asks for several substitutions, not for the
        # last one only.
        assert sim_architectures.combine_mode({}, 1) == sim_architectures.COMBINE_BOTH
        assert sim_architectures.combine_mode({}, 2) == sim_architectures.COMBINE_BOTH

    def test_what_is_written_wins_over_the_order(self):
        assert sim_architectures.combine_mode({"combine": "replace"}, 1) == sim_architectures.COMBINE_REPLACE
        assert sim_architectures.combine_mode({"combine": "both"}, 0) == sim_architectures.COMBINE_BOTH


class TestSubstitutions:
    def test_a_single_mapping_is_a_list_of_one(self):
        assert sim_architectures.substitutions({"param_target_file": "tb.sv"}) == [
            {"param_target_file": "tb.sv"}
        ]

    def test_a_list_is_read_in_order(self):
        written = [{"param_target_file": "tb.sv"}, {"param_target_file": "Makefile"}]
        assert sim_architectures.substitutions(written) == written

    def test_what_describes_no_substitution_is_empty(self):
        assert sim_architectures.substitutions(None) == []
        assert sim_architectures.substitutions("tb.sv") == []
        assert sim_architectures.substitutions([None, "tb.sv"]) == []


class TestResolveParamFile:
    def _sim(self, tmp_path):
        (tmp_path / "fixed.txt").write_text("parameter SEED = 1;", encoding="utf-8")
        (tmp_path / "stimuli").mkdir()
        (tmp_path / "stimuli" / "8bits.txt").write_text("localparam TB_WIDTH = 8;", encoding="utf-8")
        return str(tmp_path)

    def test_nothing_named_resolves_to_nothing(self, tmp_path):
        assert sim_architectures.resolve_param_file({}, self._sim(tmp_path)) is None

    def test_one_file_for_every_configuration(self, tmp_path):
        sim = self._sim(tmp_path)
        assert sim_architectures.resolve_param_file(
            {"param_file": "fixed.txt"}, sim, "8bits"
        ) == os.path.join(sim, "fixed.txt")

    def test_one_file_per_configuration(self, tmp_path):
        sim = self._sim(tmp_path)
        assert sim_architectures.resolve_param_file(
            {"param_dir": "stimuli"}, sim, "8bits"
        ) == os.path.join(sim, "stimuli", "8bits.txt")

    def test_a_configuration_described_by_a_rule_is_resolved(self, tmp_path):
        sim = self._sim(tmp_path)
        with open(os.path.join(sim, "stimuli", "_settings.yml"), "w", encoding="utf-8") as f:
            f.write(
                "configurations:\n"
                "  name: \"${width}bits\"\n"
                "  template: \"localparam TB_WIDTH = ${width};\"\n"
                "variables:\n"
                "  width:\n"
                "    type: range\n"
                "    settings: {from: 8, to: 16, step: 8}\n"
            )
        resolved = sim_architectures.resolve_param_file({"param_dir": "stimuli"}, sim, "16bits")
        assert resolved is not None
        with open(resolved, encoding="utf-8") as f:
            assert f.read().strip() == "localparam TB_WIDTH = 16;"

    def test_a_configuration_the_directory_does_not_hold_is_reported(self, tmp_path):
        messages = []
        assert sim_architectures.resolve_param_file(
            {"param_dir": "stimuli"}, self._sim(tmp_path), "32bits", messages=messages
        ) is None
        assert any(message.level == "error" for message in messages)

    def test_a_missing_file_is_reported(self, tmp_path):
        messages = []
        assert sim_architectures.resolve_param_file(
            {"param_file": "no_such_file.txt"}, self._sim(tmp_path), messages=messages
        ) is None
        assert any(message.level == "error" for message in messages)

    def test_the_directory_wins_over_the_default_file(self, tmp_path):
        sim = self._sim(tmp_path)
        messages = []
        assert sim_architectures.resolve_param_file(
            {"param_file": "fixed.txt", "param_dir": "stimuli"},
            sim, "8bits", messages=messages,
        ) == os.path.join(sim, "stimuli", "8bits.txt")
        assert not messages

    def test_a_configuration_the_directory_does_not_hold_falls_back_to_the_file(self, tmp_path):
        sim = self._sim(tmp_path)
        messages = []
        assert sim_architectures.resolve_param_file(
            {"param_file": "fixed.txt", "param_dir": "stimuli"},
            sim, "32bits", messages=messages,
        ) == os.path.join(sim, "fixed.txt")
        assert not messages

    def test_a_missing_default_file_is_reported_even_with_a_directory(self, tmp_path):
        messages = []
        assert sim_architectures.resolve_param_file(
            {"param_file": "no_such_file.txt", "param_dir": "stimuli"},
            self._sim(tmp_path), "8bits", messages=messages,
        ) is None
        assert any(message.level == "error" for message in messages)

    def test_a_domain_without_a_configuration_falls_back_to_the_file(self, tmp_path):
        sim = self._sim(tmp_path)
        messages = []
        assert sim_architectures.resolve_param_file(
            {"param_file": "fixed.txt", "param_dir": "stimuli"},
            sim, "", messages=messages,
        ) == os.path.join(sim, "fixed.txt")
        assert not messages

    def test_a_directory_needs_a_configuration_to_look_up(self, tmp_path):
        messages = []
        assert sim_architectures.resolve_param_file(
            {"param_dir": "stimuli"}, self._sim(tmp_path), "", messages=messages
        ) is None
        assert any(message.level == "error" for message in messages)


@pytest.mark.integration
class TestWhatARunSubstitutes(TestSimulationHandlerReadsIt):
    """
    The parameter domains a run ends up with, for a simulation that substitutes
    parameters of its own on top of an architecture's.
    """

    ARCH = "Example_Cordic_sv"
    SELECTION = ARCH + " + width/8 + iterations/12"

    def _sim_with(self, overrides):
        self._write(
            "TB_Combining",
            "architectures:\n"
            "  - " + self.ARCH + ":\n"
            "      param_domains:\n"
            "        width:\n" + overrides + self.TASKS,
        )
        os.makedirs("odatix_userconfig/simulations/TB_Combining/tb_params", exist_ok=True)
        with open("odatix_userconfig/simulations/TB_Combining/tb_params/8.txt", "w", encoding="utf-8") as f:
            f.write("localparam TB_WIDTH = 8;")
        with open("odatix_userconfig/simulations/TB_Combining/fixed.txt", "w", encoding="utf-8") as f:
            f.write("localparam TB_SEED = 1;")

        simulations = self._handler().get_simulations([{"TB_Combining": [self.SELECTION]}])
        assert len(simulations) == 1
        return [pd for pd in simulations[0].architecture.param_domains if pd.domain == "width"]

    def test_a_parameter_file_replaces_the_configuration(self, example_workspace):
        domains = self._sim_with('          param_file: "fixed.txt"\n')
        assert len(domains) == 1
        assert domains[0].param_file.endswith("fixed.txt")

    def test_a_parameter_directory_is_read_by_configuration(self, example_workspace):
        domains = self._sim_with('          param_dir: "tb_params"\n')
        assert len(domains) == 1
        assert domains[0].param_file.endswith(os.path.join("tb_params", "8.txt"))

    def test_doing_both_keeps_the_architectures_substitution(self, example_workspace):
        domains = self._sim_with(
            '          combine: both\n'
            '          param_target_file: "tb/tb.sv"\n'
            '          param_dir: "tb_params"\n'
        )
        assert len(domains) == 2
        architectures, simulations = domains
        # The architecture's substitution is untouched...
        assert architectures.param_file.endswith(os.path.join("width", "8.txt"))
        assert not architectures.param_target_file.endswith("tb/tb.sv")
        # ...and the simulation's is done as well, inheriting the delimiters.
        assert simulations.param_file.endswith(os.path.join("tb_params", "8.txt"))
        assert simulations.param_target_file == "tb/tb.sv"
        assert simulations.domain_value == architectures.domain_value
        assert simulations.start_delimiter == architectures.start_delimiter

    def test_a_domain_is_substituted_in_as_many_places_as_it_lists(self, example_workspace):
        # A value of "width" the testbench reads, and that the Makefile building
        # it passes on: two files, two substitutions, one domain.
        domains = self._sim_with(
            '          - param_target_file: "tb/tb.sv"\n'
            '            param_dir: "tb_params"\n'
            '          - param_target_file: "Makefile"\n'
            '            start_delimiter: "# start"\n'
            '            stop_delimiter: "# stop"\n'
            '            param_file: "fixed.txt"\n'
        )
        assert len(domains) == 2
        testbench, makefile = domains
        # The first takes the architecture's substitution place...
        assert testbench.param_target_file == "tb/tb.sv"
        assert testbench.param_file.endswith(os.path.join("tb_params", "8.txt"))
        # ...and the ones after it are done as well, each with its own file and
        # delimiters, inheriting the rest from the architecture's domain.
        assert makefile.param_target_file == "Makefile"
        assert makefile.param_file.endswith("fixed.txt")
        assert makefile.start_delimiter == "# start"
        assert makefile.domain_value == testbench.domain_value

    def test_every_substitution_inherits_the_architectures_domain(self, example_workspace):
        # Not what the substitution before it wrote: they describe two places,
        # not one refining the other.
        domains = self._sim_with(
            '          - param_target_file: "tb/tb.sv"\n'
            '          - param_target_file: "Makefile"\n'
        )
        assert len(domains) == 2
        assert domains[1].start_delimiter == domains[0].start_delimiter
        assert domains[1].param_file == domains[0].param_file

    def test_the_architectures_substitution_is_kept_alongside_a_list(self, example_workspace):
        domains = self._sim_with(
            '          - combine: both\n'
            '            param_target_file: "tb/tb.sv"\n'
            '          - param_target_file: "Makefile"\n'
        )
        assert len(domains) == 3
        assert [domain.param_target_file for domain in domains[1:]] == ["tb/tb.sv", "Makefile"]
        assert not domains[0].param_target_file.endswith("tb/tb.sv")

    def test_a_domain_describing_no_substitution_stops_the_run(self, example_workspace, capsys):
        assert self._handler() is not None
        self._write(
            "TB_Empty",
            "architectures:\n"
            "  - " + self.ARCH + ":\n"
            "      param_domains:\n"
            "        width: tb/tb.sv\n" + self.TASKS,
        )
        assert self._handler().get_simulations([{"TB_Empty": [self.SELECTION]}]) == []
        assert "must be a mapping, or a list of mappings" in capsys.readouterr().out

    def test_a_configuration_the_directory_does_not_hold_stops_the_run(self, example_workspace):
        self._write(
            "TB_Missing",
            "architectures:\n"
            "  - " + self.ARCH + ":\n"
            "      param_domains:\n"
            "        width:\n"
            '          param_dir: "tb_params"\n' + self.TASKS,
        )
        os.makedirs("odatix_userconfig/simulations/TB_Missing/tb_params", exist_ok=True)
        assert self._handler().get_simulations([{"TB_Missing": [self.SELECTION]}]) == []


class TestTheDirectorySaysHowItIsWritten(TestSimulationHandlerReadsIt):
    """
    A "param_dir" holds configurations like a parameter domain of an
    architecture does, and says how they are written the same way: in its own
    "_settings.yml", the entry keeping only what points at it.
    """

    ARCH = "Example_Cordic_sv"
    SELECTION = ARCH + " + width/8 + iterations/12"

    def _sim_with(self, directory_settings):
        self._write(
            "TB_Directory",
            "architectures:\n"
            "  - " + self.ARCH + ":\n"
            "      param_domains:\n"
            "        width:\n"
            '          param_dir: "tb_params"\n' + self.TASKS,
        )
        os.makedirs("odatix_userconfig/simulations/TB_Directory/tb_params", exist_ok=True)
        with open("odatix_userconfig/simulations/TB_Directory/tb_params/8.txt", "w", encoding="utf-8") as f:
            f.write("localparam TB_WIDTH = 8;")
        if directory_settings is not None:
            with open("odatix_userconfig/simulations/TB_Directory/tb_params/_settings.yml", "w", encoding="utf-8") as f:
                f.write(directory_settings)
        simulations = self._handler().get_simulations([{"TB_Directory": [self.SELECTION]}])
        assert len(simulations) == 1
        return [pd for pd in simulations[0].architecture.param_domains if pd.domain == "width"]

    def test_the_directory_settings_are_read(self, example_workspace):
        domains = self._sim_with(
            "param_target_file: tb/tb_cordic.sv\n"
            "start_delimiter: START\n"
            "stop_delimiter: STOP\n"
        )
        assert len(domains) == 1
        assert domains[0].param_target_file == "tb/tb_cordic.sv"
        assert domains[0].start_delimiter == "START"
        assert domains[0].stop_delimiter == "STOP"
        assert domains[0].param_file.endswith(os.path.join("tb_params", "8.txt"))

    def test_a_directory_saying_nothing_leaves_the_architecture_alone(self, example_workspace):
        domains = self._sim_with(None)
        assert len(domains) == 1
        assert domains[0].param_file.endswith(os.path.join("tb_params", "8.txt"))

    def test_the_entry_still_wins_over_the_directory(self, example_workspace):
        # What was written before the directory said it keeps meaning what it
        # meant.
        self._write(
            "TB_Legacy",
            "architectures:\n"
            "  - " + self.ARCH + ":\n"
            "      param_domains:\n"
            "        width:\n"
            '          param_dir: "tb_params"\n'
            '          param_target_file: "tb/from_entry.sv"\n' + self.TASKS,
        )
        os.makedirs("odatix_userconfig/simulations/TB_Legacy/tb_params", exist_ok=True)
        with open("odatix_userconfig/simulations/TB_Legacy/tb_params/8.txt", "w", encoding="utf-8") as f:
            f.write("localparam TB_WIDTH = 8;")
        with open("odatix_userconfig/simulations/TB_Legacy/tb_params/_settings.yml", "w", encoding="utf-8") as f:
            f.write("param_target_file: tb/from_directory.sv\n")
        simulations = self._handler().get_simulations([{"TB_Legacy": [self.SELECTION]}])
        assert len(simulations) == 1
        domains = [pd for pd in simulations[0].architecture.param_domains if pd.domain == "width"]
        assert domains[0].param_target_file == "tb/from_entry.sv"


class TestDomainSettings:
    def test_an_entry_without_a_directory_is_itself(self):
        overrides = {"param_file": "p.txt", "param_target_file": "tb.sv"}
        assert sim_architectures.domain_settings(overrides, "/nowhere") == overrides

    def test_what_is_not_a_mapping_says_nothing(self):
        assert sim_architectures.domain_settings("width", "/nowhere") == {}
