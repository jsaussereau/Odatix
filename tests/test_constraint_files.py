"""Tests for the constraint files a user hands to a job."""

from types import SimpleNamespace

import pytest

import odatix.lib.constraint_files as constraint_files
from odatix.lib.constraint_files import ConstraintFileError
from odatix.lib.prepare_work import edit_config_file


def _files(tmp_path, *names):
    made = []
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# " + name + "\n", encoding="utf-8")
        made.append(str(path))
    return made


class TestDeclaration:
    def test_a_declaration_is_a_path_a_list_or_a_scoped_mapping(self, tmp_path):
        pinout, exceptions = _files(tmp_path, "pinout.xdc", "exceptions.xdc")

        assert constraint_files.read_constraints({"constraints": pinout}, "f.yml") == [
            {"source": pinout, "scope": "all"}
        ]
        assert constraint_files.read_constraints({"constraints": [pinout, exceptions]}, "f.yml") == [
            {"source": pinout, "scope": "all"},
            {"source": exceptions, "scope": "all"},
        ]
        assert constraint_files.read_constraints(
            {"constraints": [{"files": [pinout], "scope": "pnr"}, {"file": exceptions}]}, "f.yml"
        ) == [
            {"source": pinout, "scope": "pnr"},
            {"source": exceptions, "scope": "all"},
        ]

    def test_a_settings_file_without_constraints_declares_none(self):
        assert constraint_files.read_constraints({}, "f.yml") == []
        assert constraint_files.read_constraints({"constraints": None}, "f.yml") == []

    def test_a_constraint_file_that_does_not_exist_is_an_error(self, tmp_path):
        # Going on would run the job without the constraint it was given, and
        # produce a result that looks valid and is not.
        with pytest.raises(ConstraintFileError):
            constraint_files.read_constraints({"constraints": [str(tmp_path / "nope.xdc")]}, "f.yml")

    def test_an_invalid_declaration_is_an_error(self, tmp_path):
        (pinout,) = _files(tmp_path, "pinout.xdc")

        for declaration in (
            [{"files": [pinout], "scope": "route"}],  # no such stage
            [{"scope": "pnr"}],                       # no file
            42,
        ):
            with pytest.raises(ConstraintFileError):
                constraint_files.read_constraints({"constraints": declaration}, "f.yml")


class TestResolution:
    def test_one_file_declared_twice_is_read_once_with_the_scopes_merged(self, tmp_path):
        # A pinout named by the tool's target file and again by one of its
        # targets: one copy, one read, and it is wanted at both stages.
        resolved = constraint_files.resolve([
            {"source": "/board/pinout.xdc", "scope": "synthesis"},
            {"source": "/board/pinout.xdc", "scope": "pnr"},
        ])

        assert resolved == [{"source": "/board/pinout.xdc", "scope": "all", "dest": "constraints/pinout.xdc"}]
        assert constraint_files.for_scope(resolved, "synthesis") == ["constraints/pinout.xdc"]
        assert constraint_files.for_scope(resolved, "pnr") == ["constraints/pinout.xdc"]

    def test_two_different_files_sharing_a_name_do_not_overwrite_each_other(self):
        resolved = constraint_files.resolve([
            {"source": "/board/io.xdc", "scope": "pnr"},
            {"source": "/design/io.xdc", "scope": "pnr"},
        ])

        assert [entry["dest"] for entry in resolved] == ["constraints/io.xdc", "constraints/io_2.xdc"]

    def test_a_stage_only_reads_what_is_scoped_to_it(self):
        resolved = constraint_files.resolve([
            {"source": "/design/exceptions.sdc", "scope": "synthesis"},
            {"source": "/board/floorplan.tcl", "scope": "pnr"},
        ])

        assert constraint_files.for_scope(resolved, "synthesis") == ["constraints/exceptions.sdc"]
        assert constraint_files.for_scope(resolved, "pnr") == ["constraints/floorplan.tcl"]


class TestWorkDirectory:
    def _arch(self, tmp_path, entries):
        job_dir = tmp_path / "job"
        (job_dir / "scripts").mkdir(parents=True)
        return SimpleNamespace(
            tmp_dir=str(job_dir), constraint_files=entries, constraint_filename="constraints.xdc",
            top_level_module="top", top_level_filename="top.sv", clock_signal="clk", reset_signal="rst",
            local_rtl_path="rtl", rtl_path="rtl", arch_path="architectures", lib_name="LIB",
            target_frequency=100, fmax_lower_bound=50, fmax_upper_bound=500,
            continue_on_error=False, force_single_thread=False,
        )

    def test_the_files_are_copied_into_the_job_and_listed_for_tcl(self, tmp_path, monkeypatch):
        pinout, exceptions = _files(tmp_path, "board/pinout.xdc", "design/exceptions.xdc")
        entries = constraint_files.resolve([
            {"source": pinout, "scope": "all"},
            {"source": exceptions, "scope": "synthesis"},
        ])
        arch = self._arch(tmp_path, entries)

        assert constraint_files.copy_constraint_files(arch)
        copied = tmp_path / "job" / "constraints"
        assert sorted(path.name for path in copied.iterdir()) == ["exceptions.xdc", "pinout.xdc"]

        # The generated settings.tcl carries the two lists the tcl proc reads,
        # through $tmp_path so that a job directory survives being moved.
        config = tmp_path / "job" / "scripts" / "settings.tcl"
        config.write_text(
            "set tmp_path           synth\n"
            "set constraints_file   $tmp_path/constraints.txt\n"
            "set user_constraints_synthesis [list]\n"
            "set user_constraints_pnr       [list]\n"
        )
        edit_config_file(arch, str(config))
        written = config.read_text(encoding="utf-8")

        assert 'set user_constraints_synthesis [list "$tmp_path/constraints/pinout.xdc" "$tmp_path/constraints/exceptions.xdc"]' in written
        assert 'set user_constraints_pnr       [list "$tmp_path/constraints/pinout.xdc"]' in written

    def test_a_job_without_constraints_leaves_the_lists_empty(self, tmp_path):
        arch = self._arch(tmp_path, [])

        assert constraint_files.copy_constraint_files(arch)
        assert not (tmp_path / "job" / "constraints").exists()

        config = tmp_path / "job" / "scripts" / "settings.tcl"
        config.write_text(
            "set tmp_path           synth\n"
            "set constraints_file   $tmp_path/constraints.txt\n"
            "set user_constraints_synthesis [list]\n"
            "set user_constraints_pnr       [list]\n"
        )
        edit_config_file(arch, str(config))

        assert "set user_constraints_synthesis [list]" in config.read_text(encoding="utf-8")
