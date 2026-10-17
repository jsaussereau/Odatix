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


def _stepped_results(tmp_path):
    """A job exported step by step: synthesis, then place & route."""
    _write_results(
        tmp_path / "results_demo.yml",
        [
            {
                "meta": {
                    "type": "fmax_synthesis", "architecture": "counter", "configuration": "fast",
                    "step": "synthesis", "_step_index": 0, "_last_step": False,
                },
                "metrics": {"area": 10},
            },
            {
                "meta": {
                    "type": "fmax_synthesis", "architecture": "counter", "configuration": "fast",
                    "step": "pnr", "_step_index": 1, "_last_step": True,
                },
                "metrics": {"area": 12},
            },
        ],
    )
    store = ResultStore()
    store.configure(tmp_path)
    return store


def test_steps_are_a_dimension_ordered_by_the_flow(tmp_path):
    store = _stepped_results(tmp_path)
    dimensions, _metrics = query.discover(store.dataframe(), store)

    # Flow order, not alphabetical order ("pnr" would come first).
    assert dimensions[schema.COL_STEP] == ["synthesis", "pnr"]


def test_only_the_last_step_is_selected_by_default(tmp_path):
    store = _stepped_results(tmp_path)
    dimensions = query.cascaded_dimensions(store, ["demo"], {})

    # Both scopes are offered...
    assert dimensions[schema.COL_STEP_SCOPE] == [schema.STEP_SCOPE_INTERMEDIATE, schema.STEP_SCOPE_LAST]
    # ...but only the finished result starts out checked, so the steps a job
    # went past do not double every curve.
    assert schema.default_selected(schema.COL_STEP_SCOPE, schema.STEP_SCOPE_LAST) is True
    assert schema.default_selected(schema.COL_STEP_SCOPE, schema.STEP_SCOPE_INTERMEDIATE) is False
    # Which prunes the cross-filtered step list down to the last step alone.
    assert dimensions[schema.COL_STEP] == ["pnr"]


def test_a_record_without_steps_counts_as_a_finished_result(tmp_path):
    _write_results(
        tmp_path / "results_demo.yml",
        [{"meta": {"type": "workflow", "configuration": "fast"}, "metrics": {"score": 1}}],
    )
    store = ResultStore()
    store.configure(tmp_path)
    dimensions, _metrics = query.discover(store.dataframe(), store)

    # A job with no steps at all has no step scope to filter on: nothing to hide.
    assert schema.COL_STEP_SCOPE not in dimensions


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

######################################
# Audit lot 4: what the explorer shows is what the data says
######################################


import importlib
import types

import dash

import odatix.explorer.core.recommend as recommend
import odatix.explorer.core.views as views
from odatix.explorer.core.store import MIXED_UNITS, METRIC_COLLISION_SUFFIX


def _files(tmp_path, files):
    for name, (units, records) in files.items():
        (tmp_path / ("results_" + name + ".yml")).write_text(
            yaml.safe_dump({"schema": 2, "units": units, "results": records})
        )
    store = ResultStore()
    store.configure(tmp_path)
    return store


def _record(configuration, metrics, **meta):
    meta.update({"type": "workflow", "configuration": configuration})
    return {"meta": meta, "metrics": metrics}


def test_a_unit_is_kept_only_when_every_source_agrees(tmp_path):
    store = _files(tmp_path, {
        "a": ({"delay": "ns", "area": "um2"}, [_record("x", {"delay": 1, "area": 2})]),
        "b": ({"delay": "MHz", "area": "um2"}, [_record("y", {"delay": 3, "area": 4})]),
    })
    assert store.units() == {"delay": MIXED_UNITS, "area": "um2"}
    # Each source on its own still has its unit...
    assert store.units(["a"])["delay"] == "ns"
    # ... and a conflict can no longer flip the direction guessed from the unit.
    assert recommend.metric_direction("delay", store.units()) == recommend.MINIMIZE
    warned = dict((source.name, source.warnings) for source in store.sources())
    assert any("MHz" in warning for warning in warned["a"])
    assert any("ns" in warning for warning in warned["b"])


def test_a_metric_repeating_its_dimension_stays_one_column(tmp_path):
    store = _files(tmp_path, {
        "a": ({}, [_record("x", {"width": 8, "score": 1}, width="8"),
                   _record("y", {"width": 16, "score": 2})]),
    })
    assert "width" + METRIC_COLLISION_SUFFIX not in store.dataframe().columns
    assert store.sources()[0].warnings == []


def test_a_metric_named_like_a_dimension_does_not_overwrite_it(tmp_path):
    store = _files(tmp_path, {
        "a": ({"width": "bit"}, [_record("x", {"width": 8, "score": 1}, width="w8")]),
    })
    df = store.dataframe()
    assert df["width"].tolist() == ["w8"]
    assert df["width" + METRIC_COLLISION_SUFFIX].tolist() == [8]
    assert "width" + METRIC_COLLISION_SUFFIX in store.metric_columns()
    assert store.units() == {"width" + METRIC_COLLISION_SUFFIX: "bit"}
    assert store.sources()[0].warnings


def _stepped_store(tmp_path):
    return _files(tmp_path, {"demo": ({}, [
        _record("fast", {"area": 10}, step="synthesis", _step_index=0, _last_step=False),
        _record("fast", {"area": 12}, step="pnr", _step_index=1, _last_step=True),
    ])})


def test_a_value_shown_against_its_default_survives_a_saved_view(tmp_path):
    store = _stepped_store(tmp_path)
    base = query.cascaded_dimensions(store, ["demo"], {schema.COL_STEP_SCOPE: {schema.STEP_SCOPE_INTERMEDIATE: True}})
    state = {schema.COL_STEP_SCOPE: {schema.STEP_SCOPE_INTERMEDIATE: True}}

    view = {
        views.VIEW_SCHEMA_KEY: views.VIEW_SCHEMA_VERSION, "kind": "lines", "sources": ["demo"],
        "filters": views.filters_to_hidden(state, base),
        "shown": views.filters_to_shown(state, base),
    }
    assert view["filters"] == {}
    assert view["shown"] == {schema.COL_STEP_SCOPE: [schema.STEP_SCOPE_INTERMEDIATE]}

    payload, warnings = views.sanitize_view(view, store)
    assert warnings == []
    assert payload["filter_state"] == state


def test_a_value_hidden_by_default_is_not_saved_as_hidden(tmp_path):
    store = _stepped_store(tmp_path)
    base = query.cascaded_dimensions(store, ["demo"], {schema.COL_STEP_SCOPE: {schema.STEP_SCOPE_INTERMEDIATE: True}})
    assert views.filters_to_hidden({}, base) == {}
    assert views.filters_to_shown({}, base) == {}


def test_an_old_view_without_shown_still_loads(tmp_path):
    store = _stepped_store(tmp_path)
    view = {
        views.VIEW_SCHEMA_KEY: views.VIEW_SCHEMA_VERSION, "kind": "lines", "sources": ["demo"],
        "filters": {schema.COL_STEP_SCOPE: [schema.STEP_SCOPE_LAST]},
    }
    payload, warnings = views.sanitize_view(view, store)
    assert warnings == []
    assert payload["filter_state"] == {schema.COL_STEP_SCOPE: {schema.STEP_SCOPE_LAST: False}}


def test_malformed_rule_nodes_are_dropped_not_raised():
    warnings = []
    node = {"kind": "group", "children": [
        "not a rule",
        {"kind": "group", "children": []},  # no id, empty
        {"kind": "rule", "metric": "area", "op": ">", "value": 1},
    ]}
    pruned = views._sanitize_rules(node, ["area"], warnings)
    assert [child.get("metric") for child in pruned["children"]] == ["area"]
    assert views._sanitize_rules("junk", ["area"], warnings) is None


def _dse_page():
    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    return importlib.import_module("odatix.explorer.pages.dse")


def test_a_nan_measurement_is_no_value():
    dse_page = _dse_page()
    assert dse_page._metric_of({"metrics": {"area": float("nan")}}, "area") is None
    assert dse_page._metric_of({"metrics": {"area": 3.0}}, "area") == 3.0


def test_the_front_table_shows_columns_only_later_rows_have():
    dse_page = _dse_page()
    campaign = types.SimpleNamespace(
        name="c", objectives=[{"metric": "area"}], constraints=[],
        front=[
            {"configuration": "a", "metrics": {"area": 1.0}},
            {"configuration": "b", "frequency": 100, "metrics": {"area": 2.0}},
        ],
    )
    table = dse_page._front_table(campaign).children
    assert "frequency" in [column["id"] for column in table.columns]


def test_the_highlight_query_escapes_quotes_and_backslashes():
    dse_page = _dse_page()
    query_text = dse_page._row_filter_query({"configuration": 'a\\"b'})
    assert query_text == '{configuration} = "a\\\\\\"b"'
