"""Tests for odatix.lib.results_schema (results file format v2 + legacy conversion)."""

import pytest

import odatix.lib.results_schema as schema


######################################
# Format detection
######################################

class TestDetectFormat:
    def test_v2(self):
        assert schema.detect_format({"schema": 2, "results": []}) == schema.FORMAT_V2

    def test_v1_synth(self):
        assert schema.detect_format({"fmax_synthesis": {}}) == schema.FORMAT_V1_SYNTH
        assert schema.detect_format({"fmax_results": {}}) == schema.FORMAT_V1_SYNTH
        assert schema.detect_format({"custom_freq_synthesis": {}}) == schema.FORMAT_V1_SYNTH

    def test_v1_workflow(self):
        assert schema.detect_format({"workflows": {}}) == schema.FORMAT_V1_WORKFLOW

    def test_unknown(self):
        assert schema.detect_format({"foo": "bar"}) == schema.FORMAT_UNKNOWN
        assert schema.detect_format(None) == schema.FORMAT_UNKNOWN
        assert schema.detect_format([1, 2]) == schema.FORMAT_UNKNOWN


######################################
# Record identity and merging
######################################

class TestRecordIdentity:
    def test_timestamp_is_excluded(self):
        meta1 = {"type": "fmax_synthesis", "target": "t", "timestamp": "2026-01-01"}
        meta2 = {"type": "fmax_synthesis", "target": "t", "timestamp": "2026-02-02"}
        assert schema.record_identity(meta1) == schema.record_identity(meta2)

    def test_informational_keys_are_excluded(self):
        meta1 = {"type": "workflow", "_run_dir": "/a"}
        meta2 = {"type": "workflow", "_run_dir": "/b"}
        assert schema.record_identity(meta1) == schema.record_identity(meta2)

    def test_different_dimensions_differ(self):
        assert schema.record_identity({"target": "a"}) != schema.record_identity({"target": "b"})

    def test_non_dict_meta(self):
        assert schema.record_identity(None) == tuple()


class TestUpsertRecords:
    def test_appends_new_record(self):
        existing = [schema.make_record({"target": "a"}, {"Fmax": 1})]
        new = [schema.make_record({"target": "b"}, {"Fmax": 2})]
        merged = schema.upsert_records(existing, new)
        assert len(merged) == 2

    def test_replaces_same_identity(self):
        existing = [schema.make_record({"target": "a", "timestamp": "old"}, {"Fmax": 1})]
        new = [schema.make_record({"target": "a", "timestamp": "new"}, {"Fmax": 99})]
        merged = schema.upsert_records(existing, new)
        assert len(merged) == 1
        assert merged[0]["metrics"]["Fmax"] == 99

    def test_empty_existing(self):
        new = [schema.make_record({"target": "a"}, {})]
        assert len(schema.upsert_records([], new)) == 1

    def test_non_dict_records_ignored(self):
        merged = schema.upsert_records([], ["garbage", 42])
        assert merged == []


######################################
# Parsing helpers
######################################

class TestParsers:
    def test_parse_frequency_label_int(self):
        assert schema.parse_frequency_label("50MHz") == 50
        assert isinstance(schema.parse_frequency_label("50MHz"), int)

    def test_parse_frequency_label_float(self):
        assert schema.parse_frequency_label("62.5MHz") == 62.5

    def test_parse_frequency_label_invalid(self):
        assert schema.parse_frequency_label("fast") is None

    def test_parse_domain_segments(self):
        domains = schema.parse_domain_segments("base+voltage/1v2+corner/tt")
        assert domains == {"voltage": "1v2", "corner": "tt"}

    def test_parse_domain_segments_ignores_base_and_bad_segments(self):
        assert schema.parse_domain_segments("base+nodomain") == {}
        assert schema.parse_domain_segments("base") == {}
        assert schema.parse_domain_segments(None) == {}

    def test_flatten_param_domains(self):
        meta = {}
        schema.flatten_param_domains(
            {"__main__": "cfg", "__timestamp__": "2026", "voltage": "1v2"}, meta
        )
        assert meta == {"main": "cfg", "timestamp": "2026", "voltage": "1v2"}

    def test_flatten_does_not_overwrite(self):
        meta = {"main": "keep"}
        schema.flatten_param_domains({"__main__": "new"}, meta)
        assert meta["main"] == "keep"


######################################
# v1 -> v2 conversion
######################################

class TestV1SynthConversion:
    def test_fmax_records(self):
        payload = {
            "units": {"Fmax": "MHz"},
            "fmax_synthesis": {
                "target1": {
                    "arch1": {
                        "cfg1": {"Fmax": 450, "Param_Domains": {"__main__": "cfg1"}},
                    }
                }
            },
        }
        units, records = schema.records_from_v1_synth(payload)
        assert units == {"Fmax": "MHz"}
        assert len(records) == 1
        meta = records[0]["meta"]
        assert meta["type"] == schema.TYPE_FMAX
        assert meta["target"] == "target1"
        assert meta["architecture"] == "arch1"
        assert meta["configuration"] == "cfg1"
        assert meta["main"] == "cfg1"
        assert records[0]["metrics"] == {"Fmax": 450}

    def test_custom_freq_records(self):
        payload = {
            "custom_freq_synthesis": {
                "t": {"a": {"c": {"50MHz": {"LUT": 12}}}},
            }
        }
        _, records = schema.records_from_v1_synth(payload)
        assert len(records) == 1
        assert records[0]["meta"]["frequency"] == 50
        assert records[0]["meta"]["type"] == schema.TYPE_CUSTOM_FREQ

    def test_domain_segments_from_configuration_name(self):
        payload = {"fmax_synthesis": {"t": {"a": {"base+corner/tt": {"Fmax": 1}}}}}
        _, records = schema.records_from_v1_synth(payload)
        assert records[0]["meta"]["corner"] == "tt"


class TestV1WorkflowConversion:
    def test_workflow_records(self):
        payload = {
            "workflows": {
                "wf": {
                    "cfgkey": {
                        "run_dir": "/runs/1",
                        "workflow_full": "wf/cfg+corner/tt",
                        "metrics": {"Total_time": 12},
                    }
                }
            }
        }
        _, records = schema.records_from_v1_workflow(payload)
        assert len(records) == 1
        meta = records[0]["meta"]
        assert meta["type"] == schema.TYPE_WORKFLOW
        assert meta["workflow"] == "wf"
        assert meta["configuration"] == "cfg+corner/tt"
        assert meta["corner"] == "tt"
        assert meta["_run_dir"] == "/runs/1"


class TestMakeWorkflowRecord:
    def test_configuration_rebuilt_without_workflow_name(self):
        record = schema.make_workflow_record(
            workflow="wf",
            workflow_full="wf/cfg+voltage/1v2",
            fallback_configuration="fallback",
            run_dir=None,
            workflow_definition_dir=None,
            metrics={},
        )
        assert record["meta"]["configuration"] == "cfg+voltage/1v2"

    def test_fallback_configuration(self):
        record = schema.make_workflow_record(
            workflow="wf",
            workflow_full="",
            fallback_configuration="fb",
            run_dir=None,
            workflow_definition_dir=None,
            metrics={},
        )
        assert record["meta"]["configuration"] == "fb"

    def test_timestamp(self):
        record = schema.make_workflow_record(
            workflow="wf", workflow_full="wf/c", fallback_configuration="c",
            run_dir=None, workflow_definition_dir=None, metrics={}, timestamp="2026",
        )
        assert record["meta"]["timestamp"] == "2026"


######################################
# Load / dump roundtrip
######################################

class TestLoadDump:
    def make_records(self):
        return [
            schema.make_record(
                {"type": "fmax_synthesis", "target": "t", "architecture": "a", "configuration": "c"},
                {"Fmax": 450, "LUT": 3},
            )
        ]

    def test_roundtrip(self, tmp_path):
        path = str(tmp_path / "results.yml")
        schema.dump_results_file(path, {"Fmax": "MHz"}, self.make_records())
        loaded = schema.load_results_file(path)
        assert loaded.schema_detected == schema.FORMAT_V2
        assert loaded.units == {"Fmax": "MHz"}
        assert loaded.records == self.make_records()

    def test_dump_creates_directories(self, tmp_path):
        path = str(tmp_path / "sub" / "dir" / "results.yml")
        schema.dump_results_file(path, {}, [])
        loaded = schema.load_results_file(path)
        assert loaded.records == []

    def test_normalize_ignores_garbage_records(self):
        records = schema.normalize_v2_records(
            ["junk", {"no_meta": 1}, {"meta": {"type": "x"}, "metrics": {"m": 1}}]
        )
        assert len(records) == 1

    def test_normalize_flattens_param_domains(self):
        records = schema.normalize_v2_records(
            [{"meta": {"type": "x", "Param_Domains": {"__main__": "cfg"}}, "metrics": {}}]
        )
        assert records[0]["meta"]["main"] == "cfg"

    def test_load_payload_unknown(self):
        result = schema.load_results_payload({"whatever": 1})
        assert result.schema_detected == schema.FORMAT_UNKNOWN
        assert result.records == []
