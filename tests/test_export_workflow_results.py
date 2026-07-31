"""Tests for odatix.components.export_workflow_results (workflow metric export)."""

import os

import pytest

import odatix.components.export_workflow_results as ewr


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


######################################
# Parsers
######################################

class TestParsers:
    def test_parse_csv_skips_leading_space_in_header_and_values(self, tmp_path):
        # header "EBNO, FER" has a space after the comma
        csv = tmp_path / "results.csv"
        csv.write_text("EBNO, FER\n1, 0.5\n2, 0.25\n")
        assert ewr.parse_csv(str(csv), "FER") == "0.5"

    def test_parse_csv_all_returns_every_row(self, tmp_path):
        csv = tmp_path / "results.csv"
        csv.write_text("EBNO, FER\n1, 0.5\n2, 0.25\n3, 0.1\n")
        assert ewr.parse_csv_all(str(csv), "FER") == ["0.5", "0.25", "0.1"]
        assert ewr.parse_csv_all(str(csv), "EBNO") == ["1", "2", "3"]

    def test_parse_csv_all_missing_key(self, tmp_path):
        csv = tmp_path / "results.csv"
        csv.write_text("EBNO, FER\n1, 0.5\n")
        assert ewr.parse_csv_all(str(csv), "NOPE", error_if_missing=False) == []

    def test_parse_regex_all_returns_every_match(self, tmp_path):
        txt = tmp_path / "out.txt"
        txt.write_text("val: 1\nval: 2\nval: 3\n")
        assert ewr.parse_regex_all(str(txt), r"val: (\d+)", 1) == ["1", "2", "3"]


######################################
# Metrics file loading (metrics + metadata)
######################################

class TestLoadMetrics:
    def test_metrics_and_metadata(self, tmp_path):
        f = tmp_path / "_metrics.yml"
        f.write_text(
            "metrics:\n"
            "  FER:\n    type: csv\n    settings: {file: results.csv, key: FER}\n"
            "metadata:\n"
            "  EBNO:\n    type: csv\n    settings: {file: results.csv, key: EBNO}\n"
        )
        metrics, metadata = ewr._load_metrics(str(f))
        assert "FER" in metrics
        assert "EBNO" in metadata

    def test_top_level_metrics_have_no_metadata(self, tmp_path):
        # metrics defined at top level (legacy style) -> metadata is empty
        f = tmp_path / "_metrics.yml"
        f.write_text("word:\n  type: regex\n  settings: {file: out.txt, pattern: 'x (.*)', group_id: 1}\n")
        metrics, metadata = ewr._load_metrics(str(f))
        assert "word" in metrics
        assert metadata == {}

    def test_missing_file(self, tmp_path):
        assert ewr._load_metrics(str(tmp_path / "nope.yml")) == (None, None)


######################################
# Run extraction / record expansion
######################################

class TestRunExpansion:
    @pytest.fixture
    def run_dir(self, tmp_path):
        d = tmp_path / "run"
        _write(str(d / "results.csv"), "EBNO, FER, BER\n1, 0.11, 0.05\n1.5, 0.03, 0.017\n2, 0.007, 0.003\n")
        return str(d)

    def test_single_record_without_multiple(self, run_dir):
        metrics = {"FER": {"type": "csv", "settings": {"file": "results.csv", "key": "FER"}}}
        records, _ = ewr._extract_run_records(run_dir, metrics, {})
        assert len(records) == 1
        meta_extra, run_metrics = records[0]
        assert meta_extra == {}
        # scalar metrics keep their raw extracted value (unchanged behavior)
        assert run_metrics["FER"] == "0.11"

    def test_multiple_expands_into_one_record_per_row(self, run_dir):
        metrics = {
            "FER": {"type": "csv", "settings": {"file": "results.csv", "key": "FER"}, "multiple": True},
            "BER": {"type": "csv", "settings": {"file": "results.csv", "key": "BER"}, "multiple": True},
        }
        metadata = {"EBNO": {"type": "csv", "settings": {"file": "results.csv", "key": "EBNO"}, "multiple": True}}
        records, _ = ewr._extract_run_records(run_dir, metrics, metadata)
        assert len(records) == 3
        # each row: EBNO in meta, FER/BER in metrics, all numeric
        assert records[0][0] == {"EBNO": 1}
        assert records[0][1] == {"FER": 0.11, "BER": 0.05}
        assert records[1][0] == {"EBNO": 1.5}
        assert records[2][1]["FER"] == 0.007

    def test_operation_evaluated_per_row(self, run_dir):
        metrics = {
            "FER": {"type": "csv", "settings": {"file": "results.csv", "key": "FER"}, "multiple": True},
            "BER": {"type": "csv", "settings": {"file": "results.csv", "key": "BER"}, "multiple": True},
            "ratio": {"type": "operation", "settings": {"op": "FER / BER"}},
        }
        metadata = {"EBNO": {"type": "csv", "settings": {"file": "results.csv", "key": "EBNO"}, "multiple": True}}
        records, _ = ewr._extract_run_records(run_dir, metrics, metadata)
        assert records[0][1]["ratio"] == pytest.approx(0.11 / 0.05)
        assert records[1][1]["ratio"] == pytest.approx(0.03 / 0.017)

    def test_scalar_field_is_broadcast_to_every_row(self, run_dir):
        _write(os.path.join(run_dir, "info.txt"), "label: sweepA\n")
        metrics = {
            "FER": {"type": "csv", "settings": {"file": "results.csv", "key": "FER"}, "multiple": True},
            "label": {"type": "regex", "settings": {"file": "info.txt", "pattern": "label: (.*)", "group_id": 1}},
        }
        metadata = {"EBNO": {"type": "csv", "settings": {"file": "results.csv", "key": "EBNO"}, "multiple": True}}
        records, _ = ewr._extract_run_records(run_dir, metrics, metadata)
        assert len(records) == 3
        assert all(run_metrics["label"] == "sweepA" for _, run_metrics in records)


######################################
# End-to-end export
######################################

class TestExportEndToEnd:
    def _build_workspace(self, tmp_path):
        work = tmp_path / "work"
        defs = tmp_path / "defs"
        results = tmp_path / "results"
        _write(str(work / "my_workflow" / "config1" / "results.csv"),
               "EBNO, FER, BER\n1, 0.11, 0.05\n1.5, 0.03, 0.017\n")
        _write(str(defs / "my_workflow" / "_metrics.yml"),
               "metrics:\n"
               "  FER:\n    type: csv\n    settings: {file: results.csv, key: FER}\n    multiple: true\n"
               "  BER:\n    type: csv\n    settings: {file: results.csv, key: BER}\n    multiple: true\n"
               "metadata:\n"
               "  EBNO:\n    type: csv\n    settings: {file: results.csv, key: EBNO}\n    multiple: true\n")
        return str(work), str(defs), str(results)

    def test_export_produces_one_record_per_ebno(self, tmp_path):
        import odatix.lib.results_schema as results_schema

        work, defs, results = self._build_workspace(tmp_path)
        ewr.export_workflow_results(work_root=work, workflow_path=defs, output_dir=results)

        out = os.path.join(results, ewr.DEFAULT_OUTPUT_FILENAME)
        rf = results_schema.load_results_file(out)
        assert len(rf.records) == 2
        ebnos = sorted(r["meta"]["EBNO"] for r in rf.records)
        assert ebnos == [1, 1.5]
        by_ebno = {r["meta"]["EBNO"]: r["metrics"] for r in rf.records}
        assert by_ebno[1] == {"FER": 0.11, "BER": 0.05}

    def test_re_export_upserts_by_metadata_identity(self, tmp_path):
        import odatix.lib.results_schema as results_schema

        work, defs, results = self._build_workspace(tmp_path)
        # export twice: the per-EBNO records must be replaced in place, not duplicated
        ewr.export_workflow_results(work_root=work, workflow_path=defs, output_dir=results)

        out = os.path.join(results, ewr.DEFAULT_OUTPUT_FILENAME)
        units, records = ewr._load_existing_workflow_output(out)
        # simulate an incremental re-run of config1 that adds a third EBNO row
        _write(os.path.join(work, "my_workflow", "config1", "results.csv"),
               "EBNO, FER, BER\n1, 0.09, 0.05\n1.5, 0.03, 0.017\n2, 0.007, 0.003\n")
        ewr.export_workflow_results(work_root=work, workflow_path=defs, output_dir=results)

        rf = results_schema.load_results_file(out)
        by_ebno = {r["meta"]["EBNO"]: r["metrics"] for r in rf.records}
        assert set(by_ebno) == {1, 1.5, 2}
        # EBNO=1 was replaced (0.11 -> 0.09), not duplicated
        assert by_ebno[1]["FER"] == 0.09
