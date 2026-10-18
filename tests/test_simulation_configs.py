"""
Editing the configurations of a simulation.

A simulation substitutes parameters of its own from "param_dir" directories,
which hold configuration files and rules like the parameter domains of an
architecture do. These cover both what the workspace makes of those directories
and how the configuration editor is told to show them.
"""

import os
import textwrap

import pytest

from odatix.workspace import Workspace


######################################
# Fixtures
######################################

def write(path, content):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as f:
        f.write(textwrap.dedent(content))
    return path


@pytest.fixture
def workspace_with_simulation(tmp_path):
    """A workspace holding one simulation with two parameter directories."""
    root = str(tmp_path)
    write(os.path.join(root, "odatix.yml"), """\
        arch_path: architectures
        sim_path: simulations
        work_path: work
        """)
    write(os.path.join(root, "simulations", "tb_cordic", "_settings.yml"), """\
        architectures:
          - Cordic:
              param_domains:
                width:
                  combine: both
                  param_target_file: "tb/tb_cordic.sv"
                  param_dir: "tb_params/width"
                iterations:
                  param_dir: "tb_params/iterations"
          - Other:
              param_domains:
                width:
                  param_dir: "tb_params/width"
                stimuli:
                  param_file: "stimuli.txt"
        """)
    write(os.path.join(root, "simulations", "tb_cordic", "tb_params", "width", "8.txt"),
          "localparam WIDTH = 8;\n")
    write(os.path.join(root, "simulations", "tb_cordic", "tb_params", "iterations", "_settings.yml"), """\
        variables:
          iterations:
            type: list
            settings:
              list: [4, 8]
        """)
    return Workspace(root)


######################################
# What a simulation holds
######################################

class TestParameterDirectories:

    def test_the_directories_are_listed_in_order_without_repetition(self, workspace_with_simulation):
        simulation = workspace_with_simulation.simulations["tb_cordic"]
        assert simulation.param_dirs == [
            os.path.join("tb_params", "width"),
            os.path.join("tb_params", "iterations"),
        ]

    def test_a_domain_substituted_from_a_file_is_not_a_directory(self, workspace_with_simulation):
        simulation = workspace_with_simulation.simulations["tb_cordic"]
        assert "stimuli.txt" not in simulation.param_dirs

    def test_a_simulation_without_directories_has_no_domain(self, tmp_path):
        write(os.path.join(str(tmp_path), "odatix.yml"), "sim_path: simulations\n")
        write(os.path.join(str(tmp_path), "simulations", "tb", "_settings.yml"),
              "architectures:\n  - Cordic\n")
        simulation = Workspace(str(tmp_path)).simulations["tb"]
        assert simulation.param_dirs == []
        assert list(simulation.domains) == []


class TestDirectoriesAsDomains:

    def test_a_directory_is_a_domain_of_the_simulation(self, workspace_with_simulation):
        simulation = workspace_with_simulation.simulations["tb_cordic"]
        domains = list(simulation.domains)
        assert [domain.name for domain in domains] == simulation.param_dirs
        assert domains[0].path == os.path.join(simulation.path, "tb_params", "width")

    def test_a_simulation_has_no_main_domain(self, workspace_with_simulation):
        simulation = workspace_with_simulation.simulations["tb_cordic"]
        assert simulation.domains.main is None

    def test_configuration_files_are_read(self, workspace_with_simulation):
        simulation = workspace_with_simulation.simulations["tb_cordic"]
        domain = simulation.domains[os.path.join("tb_params", "width")]
        assert domain.configs.names() == ["8"]
        assert domain.configs["8"].read() == "localparam WIDTH = 8;\n"

    def test_rules_are_resolved_like_an_architectures(self, workspace_with_simulation):
        simulation = workspace_with_simulation.simulations["tb_cordic"]
        domain = simulation.domains[os.path.join("tb_params", "iterations")]
        assert domain.configuration_names() == ["4", "8"]

    def test_a_configuration_can_be_written(self, workspace_with_simulation):
        simulation = workspace_with_simulation.simulations["tb_cordic"]
        domain = simulation.domains[os.path.join("tb_params", "width")]
        domain.configs.write("16.txt", "localparam WIDTH = 16;\n")
        with open(os.path.join(domain.path, "16.txt")) as f:
            assert f.read() == "localparam WIDTH = 16;\n"


######################################
# What the configuration editor shows
######################################

pytest.importorskip("dash")
pytest.importorskip("dash_svg")


@pytest.fixture(scope="module")
def config_editor():
    import dash

    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.config_editor as config_editor

    return config_editor


class TestEditorMode:

    def test_a_simulation_url_selects_the_simulations(self):
        from odatix.gui.utils import get_instance_mode

        assert get_instance_mode("?simulation=tb_cordic") == ("simulation", "tb_cordic")
        assert get_instance_mode("?sim=tb_cordic") == ("simulation", "tb_cordic")
        assert get_instance_mode("?arch=Cordic") == ("arch", "Cordic")

    def test_the_simulations_are_the_collection_of_that_mode(self, workspace_with_simulation):
        from odatix.gui.utils import get_instance_collection

        collection = get_instance_collection(workspace_with_simulation, "simulation")
        assert "tb_cordic" in collection

    def test_the_title_goes_back_to_the_simulation_settings(self, config_editor):
        title = str(config_editor.instance_title("simulation", "tb_cordic"))
        assert "/sim_editor?sim=tb_cordic" in title
        assert "Simulation settings" in title

    def test_nothing_is_previewed_for_a_simulation(self, config_editor):
        # Nothing is shown: what the pane holds is the hidden span every domain
        # carries so the replacement callback keeps one output per domain.
        pane = config_editor.preview_pane("uuid", "simulation", {}, {}, "text")
        assert pane.style == {"display": "none"}
        assert not pane.children

    def test_the_parameters_form_is_hidden_for_a_simulation(self, config_editor):
        section = config_editor.domain_section("tb_params/width", mode="simulation", instance_name="tb_cordic")
        hidden = [
            child for child in section.children
            if getattr(child, "style", None) == {"display": "none"}
        ]
        assert hidden, "the form and the preview of a simulation domain must be hidden"

    def test_the_directory_of_a_simulation_is_not_renamed_here(self, config_editor):
        title = config_editor.parameter_domain_title(
            domain_name="tb_params/width", domain_uuid="uuid", mode="simulation",
            instance_name="tb_cordic",
        )
        assert "Parameter directory:" in str(title)
        assert "disabled=True" in str(title)


######################################
# What a simulation substitutes for one architecture
######################################

class TestOneArchitecture:
    """
    "?sim=&arch=" shows what a simulation substitutes for one architecture: one
    section per parameter domain it overrides, holding what points at the
    configurations as well as the configurations themselves.
    """

    def _in_workspace(self, workspace, function, *args, **kwargs):
        cwd = os.getcwd()
        os.chdir(workspace.root)
        try:
            return function(*args, **kwargs)
        finally:
            os.chdir(cwd)

    def test_the_url_names_the_architecture(self, config_editor):
        assert config_editor.sim_arch_name("?sim=tb_cordic&arch=Cordic") == "Cordic"
        # The whole simulation, not one of its architectures.
        assert config_editor.sim_arch_name("?sim=tb_cordic") is None
        assert config_editor.sim_arch_name("?arch=Cordic") is None

    def test_the_entry_of_the_url_is_the_one_shown(self, workspace_with_simulation):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Other")
        assert position == 1
        assert [name for name, _ in sim_domains.param_domains_of(entries[position])] == [
            "width", "stimuli",
        ]

    def test_a_section_is_built_per_domain(self, workspace_with_simulation, config_editor):
        sections, initialized, _ = self._in_workspace(
            workspace_with_simulation,
            config_editor.sim_arch_sections,
            "?sim=tb_cordic&arch=Cordic", {}, None, [], None,
        )
        assert initialized is True
        metadata = _stores(sections, "domain-metadata")
        # The configurations of a section are held in the directory it points at.
        assert [(data["entry_domain"], data["domain_name"]) for data in metadata] == [
            ("width", "tb_params/width"),
            ("iterations", "tb_params/iterations"),
        ]

    def test_a_section_holds_what_it_points_at(self, workspace_with_simulation, config_editor):
        sections, _, _ = self._in_workspace(
            workspace_with_simulation,
            config_editor.sim_arch_sections,
            "?sim=tb_cordic&arch=Other", {}, None, [], None,
        )
        entries = _stores(sections, "simarch-entry-store")
        assert [entry["name"] for entry in entries] == ["width", "stimuli"]
        # A domain substituting one file whichever configuration runs points at
        # no directory: it has no configurations to show. A section states what
        # it does with the architecture's own substitution, whether or not the
        # file said it: on its own, it no longer knows its place in the list.
        assert entries[1]["overrides"] == {"param_file": "stimuli.txt", "combine": "replace"}
        assert _stores(sections, "domain-metadata")[1]["domain_name"] == ""

    def test_a_domain_replaced_twice_is_shown_twice(self, workspace_with_simulation, config_editor):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Other")
        sim_domains.save_param_domains(simulation, position, [
            ("width", {"param_dir": "tb_params/width", "combine": "replace"}),
            ("width", {"param_file": "stimuli.txt", "combine": "both"}),
        ])
        sections, _, _ = self._in_workspace(
            workspace_with_simulation,
            config_editor.sim_arch_sections,
            "?sim=tb_cordic&arch=Other", {}, None, [], None,
        )
        assert [entry["name"] for entry in _stores(sections, "simarch-entry-store")] == [
            "width", "width",
        ]

    def test_deleting_one_section_keeps_the_other_of_the_same_domain(self, workspace_with_simulation, config_editor):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Other")
        sim_domains.save_param_domains(simulation, position, [
            ("width", {"param_dir": "tb_params/width", "combine": "replace"}),
            ("width", {"param_file": "stimuli.txt", "combine": "both"}),
        ])
        metadata = [
            {"domain_uuid": "first", "entry_domain": "width", "entry_position": 0},
            {"domain_uuid": "second", "entry_domain": "width", "entry_position": 1},
        ]
        self._in_workspace(
            workspace_with_simulation,
            config_editor.sim_arch_sections,
            "?sim=tb_cordic&arch=Other", {},
            {"action": "delete-domain", "domain_uuid": "second"},
            metadata, None,
        )

        written = Workspace(workspace_with_simulation.root).simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(written, "Other")
        # The one section is deleted, not every replacement of that domain.
        assert entries[position].param_domains["width"] == {"param_dir": "tb_params/width"}

    def test_an_unlisted_architecture_says_so(self, workspace_with_simulation, config_editor):
        sections, _, _ = self._in_workspace(
            workspace_with_simulation,
            config_editor.sim_arch_sections,
            "?sim=tb_cordic&arch=Nothing", {}, None, [], None,
        )
        assert "does not list" in str(sections)

    def test_the_title_names_both(self, config_editor):
        title = str(config_editor.instance_title("simulation", "tb_cordic", arch="Cordic"))
        assert "tb_cordic" in title and "Cordic" in title
        # Opened from the card of that architecture, it goes back to it.
        assert "/sim_editor?sim=tb_cordic" in title

    def test_the_file_of_the_simulation_is_previewed(self, config_editor, tmp_path):
        # A simulation writes into its own sources, which is where the file a
        # section previews is looked up.
        write(os.path.join(str(tmp_path), "tb", "tb_cordic.sv"), "START\nold\nSTOP\n")
        pane = config_editor.preview_pane(
            "uuid", "simulation", {},
            {
                "use_parameters": True,
                "param_target_file": "tb/tb_cordic.sv",
                "start_delimiter": "START\\n",
                "stop_delimiter": "\\nSTOP",
            },
            "localparam WIDTH = 8;",
            base_path=str(tmp_path),
        )
        assert "localparam WIDTH = 8;" in str(pane)

    def test_the_rtl_of_the_architecture_is_previewed_too(self, config_editor, tmp_path):
        # The RTL of the architecture under test is copied next to the
        # simulation before it runs, so a target file naming one of its files is
        # found there as well.
        sim_dir = os.path.join(str(tmp_path), "simulations", "tb_cordic")
        rtl_dir = os.path.join(str(tmp_path), "examples", "cordic_sv")
        write(os.path.join(rtl_dir, "rtl", "cordic.sv"), "START\nold\nSTOP\n")
        pane = config_editor.preview_pane(
            "uuid", "simulation", {},
            {
                "use_parameters": True,
                "param_target_file": "rtl/cordic.sv",
                "start_delimiter": "START\\n",
                "stop_delimiter": "\\nSTOP",
            },
            "localparam WIDTH = 8;",
            base_path=[sim_dir, rtl_dir],
        )
        assert "localparam WIDTH = 8;" in str(pane)

    def test_the_simulation_wins_when_both_hold_the_file(self, config_editor, tmp_path):
        sim_dir = os.path.join(str(tmp_path), "simulations", "tb_cordic")
        rtl_dir = os.path.join(str(tmp_path), "examples", "cordic_sv")
        write(os.path.join(sim_dir, "top.sv"), "of the simulation\n")
        write(os.path.join(rtl_dir, "top.sv"), "of the architecture\n")
        assert config_editor.resolve_preview_file([sim_dir, rtl_dir], "top.sv") == os.path.join(sim_dir, "top.sv")
        # Held by neither, the message names where it was expected first.
        assert config_editor.resolve_preview_file([sim_dir, rtl_dir], "none.sv") == os.path.join(sim_dir, "none.sv")

    def test_the_target_file_can_name_the_copied_rtl_directory(self, config_editor, tmp_path):
        # The RTL is copied under "rtl/" in the work directory, so a target file
        # written against that directory names the architecture sources this way.
        sim_dir = os.path.join(str(tmp_path), "simulations", "tb_cordic")
        rtl_dir = os.path.join(str(tmp_path), "examples", "cordic_sv")
        write(os.path.join(sim_dir, "tb.sv"), "of the simulation\n")
        write(os.path.join(rtl_dir, "soc", "top.sv"), "of the architecture\n")
        bases = [sim_dir, (rtl_dir, "rtl"), rtl_dir]
        assert config_editor.resolve_preview_file(bases, "rtl/soc/top.sv") == os.path.join(rtl_dir, "soc", "top.sv")
        assert config_editor.resolve_preview_file(bases, "soc/top.sv") == os.path.join(rtl_dir, "soc", "top.sv")
        assert config_editor.resolve_preview_file(bases, "tb.sv") == os.path.join(sim_dir, "tb.sv")

    def test_the_default_parameter_file_is_what_a_domain_without_configurations_writes(
        self, config_editor, tmp_path
    ):
        # A domain given only a "param_file" has nothing to select: what the
        # preview writes is what that file holds.
        sim_dir = os.path.join(str(tmp_path), "simulations", "tb_cordic")
        write(os.path.join(sim_dir, "sim_params.txt"), "parameter WIDTH = 8;\n")
        assert config_editor.default_param_text(sim_dir, "sim_params.txt") == "parameter WIDTH = 8;\n"
        # Named nothing, or a file that is not there: nothing to fall back to.
        assert config_editor.default_param_text(sim_dir, "") is None
        assert config_editor.default_param_text(sim_dir, "  ") is None
        assert config_editor.default_param_text(sim_dir, "none.txt") is None

    def test_where_the_sources_of_an_architecture_are(self, workspace_with_simulation, config_editor):
        import odatix.gui.sim_domains as sim_domains

        workspace = workspace_with_simulation
        write(os.path.join(workspace.root, "architectures", "Cordic", "_settings.yml"), """\
            rtl_path: examples/cordic_sv
            top_level_file: rtl/cordic.sv
            top_level_module: cordic
            clock_signal: clock
            reset_signal: reset
            """)
        write(os.path.join(workspace.root, "architectures", "Generated", "_settings.yml"), """\
            generate_rtl: true
            design_path: examples/generator
            generate_command: make rtl
            top_level_file: rtl/top.sv
            top_level_module: top
            clock_signal: clock
            reset_signal: reset
            """)
        assert sim_domains.architecture_source_paths(workspace.architectures, "Cordic") == ["examples/cordic_sv"]
        # A generated RTL has no file to read yet, so the design it is generated
        # from is what is previewed.
        assert sim_domains.architecture_source_paths(workspace.architectures, "Generated") == ["examples/generator"]
        # An entry naming several architectures at once reads all of them.
        both = sim_domains.architecture_source_paths(workspace.architectures, "*")
        assert "examples/cordic_sv" in both and "examples/generator" in both
        assert sim_domains.architecture_source_paths(workspace.architectures, "Nothing") == []


class TestWhatIsWrittenWhere:
    """
    A section pointing at a directory says how its parameters are written in
    that directory's own settings, and the entry keeps only what points at it.
    """

    def test_a_directory_takes_the_substitution(self):
        import odatix.gui.sim_domains as sim_domains

        overrides = sim_domains.entry_overrides(
            {
                "param_dir": "tb_params/width",
                "param_file": "",
                "combine": "both",
                "param_target_file": "tb/tb_cordic.sv",
                "start_delimiter": "START",
                "stop_delimiter": "STOP",
                "use_parameters": True,
            },
            {"param_dir": "tb_params/width", "param_target_file": "old.sv"},
        )
        assert overrides == {"param_dir": "tb_params/width", "combine": "both"}

    def test_without_a_directory_the_entry_keeps_saying_it(self):
        import odatix.gui.sim_domains as sim_domains

        overrides = sim_domains.entry_overrides(
            {
                "param_file": "stimuli.txt",
                "param_dir": "",
                "combine": "replace",
                "param_target_file": "tb/tb.sv",
                "use_parameters": False,
                "start_delimiter": "",
                "stop_delimiter": "",
            },
            {},
        )
        assert overrides == {
            "param_file": "stimuli.txt",
            "param_target_file": "tb/tb.sv",
            "use_parameters": False,
            "combine": "replace",
        }

    def test_what_the_entry_carries_besides_is_kept(self):
        import odatix.gui.sim_domains as sim_domains

        overrides = sim_domains.entry_overrides(
            {"param_dir": "tb_params", "param_file": "", "combine": "replace"},
            {"param_dir": "tb_params", "domain_value": "8", "something_else": 1},
        )
        assert overrides["domain_value"] == "8"
        assert overrides["something_else"] == 1

    def test_the_directory_is_written_and_the_entry_points_at_it(self, workspace_with_simulation):
        import odatix.gui.sim_domains as sim_domains
        import odatix.workspace.sim_architectures as sim_architectures

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Cordic")
        sim_domains.save_param_domains(simulation, position, [
            ("width", sim_domains.entry_overrides(
                {"param_dir": "tb_params/width", "param_file": "", "combine": "both"},
                dict(entries[position].param_domains["width"]),
            )),
        ])
        sim_domains.domain_directory(simulation, "tb_params/width").update({
            "param_target_file": "tb/tb_cordic.sv",
        })

        written = Workspace(workspace_with_simulation.root).simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(written, "Cordic")
        overrides = entries[position].param_domains["width"]
        assert overrides == {"param_dir": "tb_params/width", "combine": "both"}
        # ...and a run reads the two of them as one.
        assert sim_architectures.domain_settings(overrides, written.path)["param_target_file"] == (
            "tb/tb_cordic.sv"
        )


class TestSeveralReplacementsOfOneDomain:
    """
    A parameter domain whose value has consequences in more than one file is
    replaced more than once, and is one section per replacement.
    """

    def test_a_domain_replaced_twice_is_two_sections(self, workspace_with_simulation):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Cordic")
        entries[position].settings["param_domains"]["width"] = [
            {"param_target_file": "tb/tb_cordic.sv"},
            {"param_target_file": "Makefile"},
        ]
        assert [name for name, _ in sim_domains.param_domains_of(entries[position])] == [
            "width", "width", "iterations",
        ]

    def test_a_section_says_what_it_does_with_the_architectures_replacement(self, workspace_with_simulation):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Cordic")
        entries[position].settings["param_domains"]["width"] = [
            {"param_target_file": "tb/tb_cordic.sv"},
            {"param_target_file": "Makefile"},
        ]
        # The order says it, where the file does not: the first takes the
        # architecture's place, the one after it is added.
        assert [
            overrides["combine"] for name, overrides in sim_domains.param_domains_of(entries[position])
            if name == "width"
        ] == ["replace", "both"]

    def test_the_sections_of_one_domain_are_written_as_its_list(self, workspace_with_simulation):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Other")
        sim_domains.save_param_domains(simulation, position, [
            ("width", {"param_dir": "tb_params/width", "combine": "replace"}),
            ("width", {"param_file": "stimuli.txt", "combine": "both"}),
            ("stimuli", {"param_file": "stimuli.txt", "combine": "replace"}),
        ])

        written = Workspace(workspace_with_simulation.root).simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(written, "Other")
        domains = entries[position].param_domains
        # What the order already says is not written; a domain replaced once
        # stays the mapping it was.
        assert domains["width"] == [
            {"param_dir": "tb_params/width"},
            {"param_file": "stimuli.txt"},
        ]
        assert domains["stimuli"] == {"param_file": "stimuli.txt"}

    def test_a_replacement_departing_from_the_order_says_so(self, workspace_with_simulation):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Other")
        sim_domains.save_param_domains(simulation, position, [
            ("width", {"param_dir": "tb_params/width", "combine": "both"}),
            ("width", {"param_file": "stimuli.txt", "combine": "replace"}),
        ])

        written = Workspace(workspace_with_simulation.root).simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(written, "Other")
        assert entries[position].param_domains["width"] == [
            {"param_dir": "tb_params/width", "combine": "both"},
            {"param_file": "stimuli.txt", "combine": "replace"},
        ]

    def test_the_sections_of_a_domain_survive_a_round_trip(self, workspace_with_simulation):
        import odatix.gui.sim_domains as sim_domains

        simulation = workspace_with_simulation.simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(simulation, "Other")
        domains = [
            ("width", {"param_dir": "tb_params/width", "combine": "replace"}),
            ("width", {"param_file": "stimuli.txt", "combine": "both"}),
        ]
        sim_domains.save_param_domains(simulation, position, domains)

        written = Workspace(workspace_with_simulation.root).simulations["tb_cordic"]
        entries, position = sim_domains.find_entry(written, "Other")
        assert sim_domains.param_domains_of(entries[position]) == domains


def _stores(sections, store_type):
    """The data of every store of a kind, in the order the sections hold them."""
    found = []

    def walk(component):
        identifier = getattr(component, "id", None)
        if isinstance(identifier, dict) and identifier.get("type") == store_type:
            found.append(getattr(component, "data", None))
        children = getattr(component, "children", None)
        if isinstance(children, (list, tuple)):
            for child in children:
                walk(child)
        elif children is not None:
            walk(children)

    for section in sections:
        walk(section)
    return found
