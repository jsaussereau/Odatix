"""Tests for Explorer result loading, filtering and dimension discovery."""

import yaml

from odatix.explorer.callbacks.filters import build_filters_dict
import odatix.explorer.core.query as query
import odatix.explorer.core.schema as schema
from odatix.explorer.core.store import ResultStore


def _write_results(path, records):
    path.write_text(yaml.safe_dump({"schema": 2, "units": {"area": "um2"}, "results": records}))


def test_store_loads_results_and_query_filters_missing_values(tmp_path):
    _write_results(
        tmp_path / "results_demo.yml",
        [
            {"meta": {"type": "custom_freq_synthesis", "architecture": "counter", "configuration": "fast", "frequency": 100, "corner": "tt"}, "metrics": {"area": 10}},
            {"meta": {"type": "custom_freq_synthesis", "architecture": "counter", "configuration": "slow", "frequency": 200}, "metrics": {"area": 20}},
        ],
    )
    store = ResultStore()
    assert store.configure(tmp_path) is True

    selected = query.select_dataframe(store, sources=["demo"], filters={"corner": ["None"]})
    dimensions, metrics = query.discover(store.dataframe(), store)

    assert store.source_names() == ["demo"]
    assert selected[schema.COL_CONFIGURATION].tolist() == ["slow"]
    assert dimensions["corner"] == ["None", "tt"]
    assert metrics == ["area"]
    assert store.units() == {"area": "um2"}


def test_cascaded_dimensions_keep_a_dimension_reenableable(tmp_path):
    _write_results(
        tmp_path / "results_demo.yml",
        [
            {"meta": {"type": "workflow", "configuration": "fast", "device": "a"}, "metrics": {"score": 1}},
            {"meta": {"type": "workflow", "configuration": "slow", "device": "b"}, "metrics": {"score": 2}},
        ],
    )
    store = ResultStore()
    store.configure(tmp_path)

    dimensions = query.cascaded_dimensions(store, ["demo"], {"device": {"a": True, "b": False}})

    assert dimensions["device"] == ["a", "b"]
    assert dimensions[schema.COL_CONFIGURATION] == ["fast"]


def test_filter_callback_helper_rebuilds_the_selection_state():
    filters = build_filters_dict(
        [["counter"], [], ["fast", "slow"]],
        [{"dim": "architecture"}, {"dim": "target"}, {"dim": "configuration"}],
    )

    assert filters == {
        "architecture": ["counter"],
        "target": [],
        "configuration": ["fast", "slow"],
    }