"""Non-regression tests of the 2nd new-user campaign, Explorer domain."""

import pandas as pd

import odatix.explorer.charts.builder as builder
import odatix.explorer.charts.palettes as palettes
from odatix.explorer.charts.spec import FigureSpec, resolve_defaults


def _df():
    return pd.DataFrame({
        "Architecture": ["A"] * 4,
        "Configuration": ["c1", "c2", "c1", "c2"],
        "Frequency": ["50", "50", "100", "100"],
        "LUT": [1, 2, 3, 4],
    })


def _dims(df):
    return {c: sorted(df[c].astype(str).unique()) for c in ("Architecture", "Configuration", "Frequency")}


def test_default_color_by_varies():
    """XR-04: one architecture -> color by the frequency, not the architecture."""
    df = _df()
    spec = resolve_defaults(FigureSpec(kind="lines"), _dims(df), ["LUT"])
    assert spec.color_by == ("Frequency",)


def test_distinct_series_never_share_a_style():
    """XR-04: traces differing only by a dimension outside color/symbol differ by symbol."""
    df = _df()
    spec = resolve_defaults(FigureSpec(kind="lines", color_by=("Architecture",), symbol_by=()), _dims(df), ["LUT"])
    fig = builder.build_figure(df, spec, _dims(df), ["LUT"], {}, {}, as_dict=True)
    styles = {(t["marker"]["color"], t["marker"]["symbol"]) for t in fig["data"]}
    assert len(fig["data"]) == 2 and len(styles) == 2


def test_figure_is_plain_and_marked():
    """UX-01/UX-05: unvalidated dict figure, titles as dicts, meta mark for the guard."""
    df = _df()
    spec = resolve_defaults(FigureSpec(kind="lines"), _dims(df), ["LUT"])
    fig = builder.build_figure(df, spec, _dims(df), ["LUT"], {}, {"dark": True}, as_dict=True)
    assert fig["layout"]["meta"] == {"odatix": True}
    assert isinstance(fig["layout"]["xaxis"]["title"], dict)
    assert isinstance(fig["layout"]["template"], dict)


def test_empty_selection_says_so():
    """UX-13: no "None" title on an empty chart."""
    spec = resolve_defaults(FigureSpec(kind="lines"), {}, [])
    fig = builder.build_figure(pd.DataFrame(), spec, {}, [], {}, {}, as_dict=True, empty_text="No results yet.")
    assert "title" not in fig["layout"]
    assert fig["layout"]["annotations"][0]["text"] == "No results yet."


def test_scene_grid_is_opaque():
    """UX-11: WebGL ignores the alpha of a grid color."""
    assert builder.opaque_grid_color("rgba(240, 240, 240, 0.15)", True).startswith("#")


def test_radar_labels_shortened():
    """XR-14: long angular labels are shortened in the middle."""
    label = builder.short_label("Example_FIR_hls+taps_8taps+ii_1+partition_complete")
    assert len(label) == builder.RADAR_LABEL_LENGTH and "…" in label


def test_csv_drops_internal_columns():
    """XR-16: no _* columns, lists joined, units in headers."""
    from odatix.explorer.callbacks.figure import csv_frame
    df = pd.DataFrame({"LUT": [1], "_last_step": [True], "_derived": [["a", "b"]], "tags": [["x", "y"]]})
    out = csv_frame(df, {"LUT": "cells"})
    assert list(out.columns) == ["LUT (cells)", "tags"] and out["tags"][0] == "x; y"


def test_gallery_is_cached(monkeypatch):
    """UX-01/XR-01: the gallery is computed once per data version."""
    import odatix.explorer.ui.insights as insights
    calls = []
    monkeypatch.setattr(insights.recommend, "recommend_gallery", lambda *a, **k: calls.append(1) or ["r"])
    monkeypatch.setattr(insights, "default_filters", lambda *a: {})

    class Store(object):
        result_path = "/x"
        version = 7
    insights._gallery_cache.clear()
    assert insights.cached_gallery(Store(), ["s"]) == ["r"]
    assert insights.cached_gallery(Store(), ["s"]) == ["r"]
    assert len(calls) == 1


def test_heartbeat_ignores_timeouts():
    """UX-01: only a refused connection declares the server lost."""
    import os
    import odatix.gui
    path = os.path.join(os.path.dirname(odatix.gui.__file__), "assets", "server_heartbeat.js")
    text = open(path).read()
    assert "if (timedOut) return;" in text and "if (pending) return;" in text
