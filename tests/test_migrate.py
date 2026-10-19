"""
odatix migrate: the settings files written in a former format are rewritten in
the current one, meaning exactly what they meant and laid out as they were.
"""

import os
import textwrap

import pytest

from odatix.workspace import Workspace
from odatix.workspace import migrate as workspace_migrate
from odatix.workspace.architectures import resolve_frequencies
from odatix.workspace.space import config_set_rules
from odatix.workspace.yaml_io import read_yaml, sequence_offset, write_document, read_document

from test_cli import run_cli


TARGETS = ("xc7s25-csga225-1", "xc7a100t-csg324-1", "other")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
    return path


@pytest.fixture
def workspace_dir(tmp_path, monkeypatch):
    """A workspace holding only what each test writes into it."""
    (tmp_path / "odatix.yml").write_text("workspace: odatix\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def architecture(workspace_dir):
    """An architecture whose bounds are written the former way, at the root and in a rule."""
    return write(workspace_dir / "odatix_userconfig" / "architectures" / "Old" / "_settings.yml", """
        # my old architecture
        rtl_path: "examples/mult"
        top_level_file: "mult.sv"
        top_level_module: "mult"
        clock_signal: "i_clk"
        reset_signal: "i_rst"

        fmax_lower_bound: 100
        fmax_upper_bound: 900

        overrides:
          # slow target
          - targets: xc7s25-csga225-1
            fmax_upper_bound: 400
        """)


@pytest.fixture
def domain(workspace_dir):
    """A parameter domain still switching its generation on the former way."""
    return write(workspace_dir / "odatix_userconfig" / "architectures" / "Old" / "width" / "_settings.yml", """
        # width domain
        generate_configurations: Yes
        generate_configurations_settings:
          name: "w${W}"
          template: "WIDTH = ${W}"
          variables:
            W:
              type: range
              settings: {from: 8, to: 16, step: 8}
        """)


def bounds(path):
    data = read_yaml(str(path))
    return [
        (resolve_frequencies(data, target=target).lower_bound, resolve_frequencies(data, target=target).upper_bound)
        for target in TARGETS
    ]


######################################
# What is found
######################################

class TestFinding:
    def test_a_current_workspace_has_nothing_to_migrate(self, workspace_dir):
        write(workspace_dir / "odatix_userconfig" / "architectures" / "New" / "_settings.yml", """
            top_level_module: "mult"
            fmax_synthesis:
              lower_bound: 100
            """)
        assert workspace_migrate.pending(Workspace.open()) == []
        assert workspace_migrate.plan(Workspace.open()) == []

    def test_former_files_are_found_without_being_touched(self, architecture, domain):
        before = architecture.read_text(encoding="utf-8"), domain.read_text(encoding="utf-8")
        paths = [os.path.realpath(path) for path, _keys in workspace_migrate.pending(Workspace.open())]
        assert os.path.realpath(str(architecture)) in paths
        assert os.path.realpath(str(domain)) in paths

        migrations = workspace_migrate.migrate(Workspace.open(), dry_run=True)
        assert (architecture.read_text(encoding="utf-8"), domain.read_text(encoding="utf-8")) == before
        assert all(migration.changed for migration in migrations)
        assert not any(os.path.exists(str(path) + ".bak") for path in (architecture, domain))


######################################
# What a migration changes
######################################

class TestArchitectureBounds:
    def test_every_job_keeps_its_bounds(self, architecture):
        before = bounds(architecture)
        workspace_migrate.migrate(Workspace.open())
        assert bounds(architecture) == before == [(100, 400), (100, 900), (100, 900)]
        assert not resolve_frequencies(read_yaml(str(architecture)), target="other").deprecated_bounds

    def test_the_file_keeps_its_layout(self, architecture):
        workspace_migrate.migrate(Workspace.open())
        text = architecture.read_text(encoding="utf-8")
        assert "fmax_lower_bound" not in text and "fmax_upper_bound" not in text
        assert text.startswith("# my old architecture\n")
        assert "  # slow target\n  - targets: xc7s25-csga225-1\n    fmax_synthesis:\n      upper_bound: 400\n" in text
        # the block takes the place of the former keys, not the end of the file
        assert text.index("fmax_synthesis:\n  lower_bound: 100\n  upper_bound: 900\n\noverrides:") > 0

    def test_the_former_version_is_kept(self, architecture):
        original = architecture.read_text(encoding="utf-8")
        migration, = [m for m in workspace_migrate.migrate(Workspace.open()) if m.kind == "architecture"]
        assert os.path.realpath(migration.backup) == os.path.realpath(str(architecture) + ".bak")
        assert open(migration.backup, encoding="utf-8").read() == original

    def test_a_backup_already_there_is_not_overwritten(self, architecture):
        (architecture.parent / "_settings.yml.bak").write_text("older\n", encoding="utf-8")
        workspace_migrate.migrate(Workspace.open())
        assert (architecture.parent / "_settings.yml.bak").read_text(encoding="utf-8") == "older\n"
        assert (architecture.parent / "_settings.yml.bak.1").exists()

    def test_former_keys_in_rules_next_to_modern_rules_are_left_to_the_user(self, workspace_dir):
        path = write(workspace_dir / "odatix_userconfig" / "architectures" / "Mixed" / "_settings.yml", """
            top_level_module: "mult"
            overrides:
              - targets: xc7s25-csga225-1
                fmax_lower_bound: 42
              - targets: "*"
                fmax_synthesis:
                  lower_bound: 300
            """)
        before = bounds(path)
        migration, = workspace_migrate.migrate(Workspace.open())
        assert any("fmax_lower_bound" in reason for reason in migration.left)
        assert "fmax_lower_bound: 42" in path.read_text(encoding="utf-8")
        assert bounds(path) == before

    def test_former_keys_a_modern_root_block_hides_are_dropped(self, workspace_dir):
        path = write(workspace_dir / "odatix_userconfig" / "architectures" / "Hidden" / "_settings.yml", """
            top_level_module: "mult"
            fmax_synthesis:
              lower_bound: 300
            overrides:
              - targets: xc7s25-csga225-1
                fmax_lower_bound: 42
            """)
        before = bounds(path)
        migration, = workspace_migrate.migrate(Workspace.open())
        assert migration.left == []
        assert "fmax_lower_bound" not in path.read_text(encoding="utf-8")
        assert bounds(path) == before


class TestDomains:
    def test_the_generation_is_carried_over(self, domain):
        rules = config_set_rules(read_yaml(str(domain)))
        workspace_migrate.migrate(Workspace.open())
        text = domain.read_text(encoding="utf-8")
        assert "generate_configurations" not in text
        assert text.startswith("# width domain\n")
        migrated = config_set_rules(read_yaml(str(domain)))
        assert (migrated.name, migrated.template) == (rules.name, rules.template) == ("w${W}", "WIDTH = ${W}")


class TestTargets:
    def test_disabled_targets_become_commented_entries(self, workspace_dir):
        path = write(workspace_dir / "odatix_userconfig" / "targets" / "target_vivado.yml", """
            # targets of vivado
            targets:
              - xc7a100t-csg324-1
              # - xc7s25-csga225-1

            disabled_targets:
              - xc7z020-clg400-1
            """)
        before = [(target.name, target.enabled) for target in Workspace.open().targets["vivado"].targets]
        migration, = workspace_migrate.migrate(Workspace.open())
        assert migration.kind == "targets"
        text = path.read_text(encoding="utf-8")
        assert "disabled_targets" not in text
        assert "  # - xc7z020-clg400-1" in text
        after = [(target.name, target.enabled) for target in Workspace.open().targets["vivado"].targets]
        assert after == before


class TestMetrics:
    def test_metrics_at_the_top_level_move_under_metrics(self, workspace_dir):
        workflow = workspace_dir / "odatix_userconfig" / "workflows" / "wf"
        write(workflow / "_settings.yml", "tasks: []\n")
        path = write(workflow / "_metrics.yml", """
            area:
              type: regex
              pattern: "Area: ([0-9.]+)"
            """)
        metrics = Workspace.open().workflows["wf"].metrics.metrics
        migration, = workspace_migrate.migrate(Workspace.open())
        assert migration.kind == "metrics"
        assert "metrics" in read_yaml(str(path))
        assert Workspace.open().workflows["wf"].metrics.metrics == metrics


class TestOnce:
    def test_a_migrated_workspace_has_nothing_left(self, architecture, domain):
        workspace_migrate.migrate(Workspace.open())
        assert workspace_migrate.pending(Workspace.open()) == []


######################################
# Layout of a file saved by the API
######################################

class TestLayout:
    def test_the_indentation_of_the_lists_is_read_off_the_file(self):
        assert sequence_offset("a:\n  - x\n") == 2
        assert sequence_offset("a:\n- x\n") == 0
        assert sequence_offset("# a:\n#   - x\nb: 1\n") == 0
        assert sequence_offset("a:\n  # comment\n    - x\n") == 4

    def test_a_save_keeps_the_lists_and_the_leading_blank_line(self, tmp_path):
        path = tmp_path / "f.yml"
        path.write_text("\n# header\nkey: 1\nlist:\n  - a\n  - b\n", encoding="utf-8")
        document = read_document(str(path))
        document["key"] = 2
        write_document(str(path), document)
        assert path.read_text(encoding="utf-8") == "\n# header\nkey: 2\nlist:\n  - a\n  - b\n"


######################################
# Command line
######################################

@pytest.mark.integration
class TestCommand:
    def test_nothing_to_migrate_succeeds(self, workspace_dir):
        result = run_cli("migrate", "-Q", cwd=str(workspace_dir))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_a_dry_run_writes_nothing(self, architecture):
        original = architecture.read_text(encoding="utf-8")
        result = run_cli("migrate", "-Q", "--dry-run", cwd=str(architecture.parents[3]))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "fmax_lower_bound" in result.stdout
        assert architecture.read_text(encoding="utf-8") == original

    def test_a_migration_rewrites_the_files(self, architecture):
        result = run_cli("migrate", "-Q", "--no-backup", cwd=str(architecture.parents[3]))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "fmax_lower_bound" not in architecture.read_text(encoding="utf-8")
        assert not os.path.exists(str(architecture) + ".bak")

    def test_what_is_left_to_the_user_fails_the_command(self, workspace_dir):
        write(workspace_dir / "odatix_userconfig" / "architectures" / "Mixed" / "_settings.yml", """
            top_level_module: "mult"
            overrides:
              - targets: a
                fmax_lower_bound: 42
              - targets: b
                fmax_synthesis:
                  lower_bound: 300
            """)
        assert run_cli("migrate", "-Q", cwd=str(workspace_dir)).returncode != 0


######################################
# Settings files named after their command
######################################

class TestSettingsFileNames:
    def test_a_former_key_of_odatix_yml_is_still_read_and_said(self, workspace_dir, capsys):
        from odatix.lib.settings import OdatixSettings

        (workspace_dir / "odatix.yml").write_text("workspace: odatix\nfmax_synthesis_settings_file: my_fmax.yml\n", encoding="utf-8")
        assert Workspace.open().paths.fmax_settings_file.endswith("my_fmax.yml")
        assert OdatixSettings().fmax_settings_file == "my_fmax.yml"
        assert '"fmax_settings_file"' in capsys.readouterr().out

    def test_a_file_under_its_former_name_is_still_read(self, workspace_dir):
        write(workspace_dir / "odatix_userconfig" / "fmax_synthesis_settings.yml", "architectures: []\n")
        assert Workspace.open().paths.fmax_settings_file.endswith("fmax_synthesis_settings.yml")

    def test_the_current_name_wins_when_both_are_there(self, workspace_dir):
        write(workspace_dir / "odatix_userconfig" / "fmax_synthesis_settings.yml", "architectures: []\n")
        write(workspace_dir / "odatix_userconfig" / "fmax_settings.yml", "architectures: []\n")
        assert Workspace.open().paths.fmax_settings_file.endswith("fmax_settings.yml")

    def test_migrate_renames_the_files_and_the_keys(self, workspace_dir):
        (workspace_dir / "odatix.yml").write_text(
            "workspace: odatix\n# where the simulations are set\nsimulation_settings_file: odatix_userconfig/my_sims.yml\n"
        )
        write(workspace_dir / "odatix_userconfig" / "clean.yml", "remove_list: [work]\n")
        write(workspace_dir / "odatix_userconfig" / "my_sims.yml", "simulations: []\n")
        assert len(workspace_migrate.pending(Workspace.open())) == 2

        workspace_migrate.migrate(Workspace.open())
        assert (workspace_dir / "odatix_userconfig" / "clean_settings.yml").read_text(encoding="utf-8") == "remove_list: [work]\n"
        assert not (workspace_dir / "odatix_userconfig" / "clean.yml").exists()
        settings = (workspace_dir / "odatix.yml").read_text(encoding="utf-8")
        assert "# where the simulations are set\nsim_settings_file: odatix_userconfig/my_sims.yml" in settings
        assert "simulation_settings_file" not in settings
        # named in odatix.yml: left where it is
        assert (workspace_dir / "odatix_userconfig" / "my_sims.yml").exists()
        assert workspace_migrate.pending(Workspace.open()) == []


class TestFixedFrequencyKey:
    def test_migrate_renames_the_block_everywhere(self, workspace_dir):
        path = write(workspace_dir / "odatix_userconfig" / "architectures" / "Freq" / "_settings.yml", """
            top_level_module: "mult"
            # frequencies of every job
            custom_freq_synthesis:
              list: [50, 100]
            overrides:
              - targets: a
                custom_freq_synthesis:
                  list: [70]
            """)
        before = resolve_frequencies(read_yaml(str(path)), target="a", mode="custom_freq").frequencies
        migration, = workspace_migrate.migrate(Workspace.open())
        assert "custom_freq_synthesis" in migration.former_keys
        text = path.read_text(encoding="utf-8")
        assert "custom_freq_synthesis" not in text
        assert "# frequencies of every job\nfixed_freq_synthesis:" in text
        assert resolve_frequencies(read_yaml(str(path)), target="a", mode="custom_freq").frequencies == before == [70]

    def test_a_workspace_spelling_every_path_out_still_renames_the_files(self, workspace_dir):
        # The GUI builds its workspace from settings that name every file,
        # defaults included: only what odatix.yml says keeps a file where it is.
        from odatix.lib.settings import OdatixSettings

        write(workspace_dir / "odatix_userconfig" / "clean.yml", "remove_list: [work]\n")
        workspace = Workspace.from_dict(OdatixSettings().to_dict(), root=str(workspace_dir))
        assert [migration.kind for migration in workspace_migrate.plan(workspace)] == ["file name"]
