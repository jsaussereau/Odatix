"""Tests for odatix.components.export_common (shared result-export helpers)."""

import json

import pytest

import odatix.components.export_common as ec


######################################
# parse_regex / parse_regex_all
######################################

class TestParseRegex:
    def test_first_match(self, tmp_path):
        f = tmp_path / "out.txt"
        f.write_text("LUTs: 1234\nLUTs: 5\n", encoding="utf-8")
        assert ec.parse_regex(str(f), r"LUTs: (\d+)", 1) == "1234"

    def test_all_matches(self, tmp_path):
        f = tmp_path / "out.txt"
        f.write_text("v 1\nv 2\nv 3\n", encoding="utf-8")
        assert ec.parse_regex_all(str(f), r"v (\d+)", 1) == ["1", "2", "3"]

    def test_anchors_match_at_line_boundaries(self, tmp_path):
        f = tmp_path / "area.rep"
        f.write_text("  Hinst  Count  Area\n-----\ntop    84    7043.400\n sub   24    1838.200\n", encoding="utf-8")
        assert ec.parse_regex(str(f), r"^\S+\s+([0-9]+)\s+([0-9.]+)\s*$", 2) == "7043.400"
        assert ec.parse_regex_all(str(f), r"^\s*\S+\s+([0-9]+)\s", 1) == ["84", "24"]

    def test_no_match_returns_none(self, tmp_path):
        f = tmp_path / "out.txt"
        f.write_text("nothing here\n", encoding="utf-8")
        assert ec.parse_regex(str(f), r"X (\d+)", 1) is None

    def test_missing_file_error_suppressed(self, tmp_path, capsys):
        # error_if_missing=False must not print anything for a missing file
        assert ec.parse_regex(str(tmp_path / "nope.txt"), r"(.*)", 1, error_if_missing=False) is None
        assert capsys.readouterr().out == ""

    def test_no_match_error_respects_flag(self, tmp_path, capsys):
        f = tmp_path / "out.txt"
        f.write_text("nothing\n", encoding="utf-8")
        ec.parse_regex(str(f), r"X (\d+)", 1, error_if_missing=False)
        assert capsys.readouterr().out == ""
        ec.parse_regex(str(f), r"X (\d+)", 1, error_if_missing=True)
        assert "No match" in capsys.readouterr().out


######################################
# parse_csv / parse_csv_all
######################################

class TestParseCsv:
    def test_first_row_value(self, tmp_path):
        f = tmp_path / "r.csv"
        f.write_text("a, b\n1, 2\n3, 4\n", encoding="utf-8")
        assert ec.parse_csv(str(f), "b") == "2"

    def test_all_rows(self, tmp_path):
        f = tmp_path / "r.csv"
        f.write_text("a, b\n1, 2\n3, 4\n", encoding="utf-8")
        assert ec.parse_csv_all(str(f), "a") == ["1", "3"]

    def test_missing_key_returns_none(self, tmp_path):
        f = tmp_path / "r.csv"
        f.write_text("a, b\n1, 2\n", encoding="utf-8")
        assert ec.parse_csv(str(f), "z", error_if_missing=False) is None
        assert ec.parse_csv_all(str(f), "z", error_if_missing=False) == []


######################################
# parse_yaml / parse_json
######################################

class TestParseYamlJson:
    def test_yaml_whole_and_key(self, tmp_path):
        f = tmp_path / "d.yml"
        f.write_text("depth: 42\nname: foo\n", encoding="utf-8")
        assert ec.parse_yaml(str(f)) == {"depth": 42, "name": "foo"}
        assert ec.parse_yaml(str(f), "depth") == 42

    def test_yaml_missing_key_respects_flag(self, tmp_path, capsys):
        f = tmp_path / "d.yml"
        f.write_text("depth: 42\n", encoding="utf-8")
        assert ec.parse_yaml(str(f), "nope", error_if_missing=False) is None
        assert capsys.readouterr().out == ""
        ec.parse_yaml(str(f), "nope", error_if_missing=True)
        assert "Could not find key" in capsys.readouterr().out

    def test_yaml_non_mapping_returns_none_for_key(self, tmp_path):
        f = tmp_path / "d.yml"
        f.write_text("- a\n- b\n", encoding="utf-8")  # a list, not a mapping
        assert ec.parse_yaml(str(f), "x", error_if_missing=False) is None

    def test_json_whole_and_key(self, tmp_path):
        f = tmp_path / "d.json"
        f.write_text(json.dumps({"width": 8}), encoding="utf-8")
        assert ec.parse_json(str(f)) == {"width": 8}
        assert ec.parse_json(str(f), "width") == 8

    def test_json_missing_key(self, tmp_path):
        f = tmp_path / "d.json"
        f.write_text(json.dumps({"width": 8}), encoding="utf-8")
        assert ec.parse_json(str(f), "height", error_if_missing=False) is None


######################################
# convert_to_numeric / calculate_operation
######################################

class TestTransforms:
    def test_convert_int_float_and_passthrough(self):
        assert ec.convert_to_numeric("1234") == 1234
        assert isinstance(ec.convert_to_numeric("1234"), int)
        assert ec.convert_to_numeric("12.5") == 12.5
        assert ec.convert_to_numeric(7) == 7          # already numeric
        assert ec.convert_to_numeric("abc") == "abc"  # not numeric-looking

    def test_operation(self):
        assert ec.calculate_operation("a + b", {"a": 3, "b": 4}) == 7
        # a None operand is dropped -> NameError -> None (error suppressed)
        assert ec.calculate_operation("a + b", {"a": 3, "b": None}, error_if_missing=False) is None

    def test_operation_zero_division(self):
        assert ec.calculate_operation("a / b", {"a": 1, "b": 0}, error_if_missing=False) is None


######################################
# load_existing_results_file
######################################

class TestLoadExisting:
    def test_missing_file_is_empty(self, tmp_path):
        assert ec.load_existing_results_file(str(tmp_path / "nope.yml")) == ({}, [])

    def test_unparsable_file_starts_over(self, tmp_path, capsys):
        f = tmp_path / "results.yml"
        f.write_text(": : not : valid : yaml :\n", encoding="utf-8")
        units, records = ec.load_existing_results_file(str(f))
        assert units == {} and records == []


class TestMissingFileReportedOnce:
    """A failed job's missing report: one error, not one per metric (C-17)."""

    def test_one_error_per_missing_file(self, tmp_path, capsys):
        import odatix.components.export_common as export_common
        missing = str(tmp_path / "results.yml")
        for key in ("a", "b", "c"):
            assert export_common.parse_yaml(missing, key, True, "job => ") is None
        assert export_common.parse_regex(missing, "x", 0, True, "job => ") is None
        assert capsys.readouterr().out.count("does not exist") == 1

    def test_said_again_after_a_while(self, tmp_path, capsys, monkeypatch):
        import odatix.components.export_common as export_common
        missing = str(tmp_path / "output.txt")
        export_common.parse_regex(missing, "x", 0, True)
        monkeypatch.setattr(export_common, "MISSING_FILE_REPEAT_S", 0.0)
        export_common.parse_regex(missing, "x", 0, True)
        assert capsys.readouterr().out.count("does not exist") == 2

    def test_other_files_are_still_reported(self, tmp_path, capsys):
        import odatix.components.export_common as export_common
        export_common.parse_regex(str(tmp_path / "one.txt"), "x", 0, True)
        export_common.parse_regex(str(tmp_path / "two.txt"), "x", 0, True)
        assert capsys.readouterr().out.count("does not exist") == 2
