"""Tests for the "outside the rules" action of the Explorer metric rules."""

import pandas as pd

import odatix.explorer.charts.builder as builder
import odatix.explorer.core.rules as rules
import odatix.explorer.core.schema as schema
from odatix.explorer.callbacks.figure import MATCHES_RULES_COLUMN, csv_frame
from odatix.explorer.charts.spec import FigureSpec


def _df():
    return pd.DataFrame(
        {
            schema.COL_CONFIGURATION: ["a", "b", "c"],
            "LUT": [10, 20, 30],
            "worst_slack": [0.5, -0.2, 0.1],
        }
    )


def _state(outside=None):
    state = rules.empty_state()
    rule = rules.new_rule(state, metric="worst_slack")
    rule.update(op=">=", value=0)
    rules.add_child(state, rules.ROOT_ID, rule)
    if outside is not None:
        rules.set_field(state, rules.ROOT_ID, "outside", outside)
    return state


def test_hide_is_the_default_and_drops_the_rows():
    state = _state()
    assert rules.normalize(state)["outside"] == rules.OUTSIDE_HIDE
    kept = rules.apply_rules(_df(), state)
    assert kept[schema.COL_CONFIGURATION].tolist() == ["a", "c"]
    assert rules.MISS_COLUMN not in kept.columns


def test_highlight_keeps_the_rows_and_marks_the_rejected_ones():
    kept = rules.apply_rules(_df(), _state(rules.OUTSIDE_HIGHLIGHT))
    assert len(kept) == 3
    assert kept[rules.MISS_COLUMN].tolist() == [False, True, False]
    marks = [rules.parse_mark(mark)[0] for mark in kept[rules.MARK_COLUMN]]
    assert marks == ["", rules.MARK_HIGHLIGHT, ""]
    assert len(rules.matching(_df(), _state(rules.OUTSIDE_HIGHLIGHT))) == 2


def _inverted(outside=None):
    return rules.toggle_invert(_state(outside))


def test_invert_turns_the_rules_around():
    kept = rules.apply_rules(_df(), _inverted())
    assert kept[schema.COL_CONFIGURATION].tolist() == ["b"]
    assert len(rules.matching(_df(), _inverted())) == 1
    assert rules.describe(_inverted()) == "not (worst_slack ≥ 0)"
    assert rules.normalize({"invert": "yes"})["invert"] is False


def test_inverted_highlight_marks_the_rows_meeting_the_rules():
    kept = rules.apply_rules(_df(), _inverted(rules.OUTSIDE_HIGHLIGHT))
    marks = [rules.parse_mark(mark)[0] for mark in kept[rules.MARK_COLUMN]]
    assert marks == [rules.MARK_HIGHLIGHT, "", rules.MARK_HIGHLIGHT]


def test_highlight_style_is_carried_by_the_mark():
    state = _state(rules.OUTSIDE_HIGHLIGHT)
    rules.set_field(state, rules.ROOT_ID, "highlight_color", "#0090ff")
    rules.set_field(state, rules.ROOT_ID, "highlight_effect", rules.EFFECT_RING)
    rules.set_field(state, rules.ROOT_ID, "highlight_color", "not a color")
    mark = rules.apply_rules(_df(), state)[rules.MARK_COLUMN].iloc[1]
    assert rules.parse_mark(mark) == (rules.MARK_HIGHLIGHT, "#0090ff", rules.EFFECT_RING)


def test_views_saved_without_the_fields_still_hide():
    state = _state()
    for field in ("outside", "highlight_color", "highlight_effect"):
        del state[field]
    state = rules.normalize(state)
    assert state["outside"] == rules.OUTSIDE_HIDE
    assert state["highlight_color"] == rules.DEFAULT_HIGHLIGHT_COLOR
    assert rules.outside_action({"outside": "bogus"}) == rules.OUTSIDE_HIDE


def _figure(state, kind="scatter", toggles=()):
    df = rules.apply_rules(_df(), state)
    spec = FigureSpec(kind=kind, x="LUT", y="worst_slack", toggles=tuple(toggles))
    return builder.build_figure(df, spec, {schema.COL_CONFIGURATION: ["a", "b", "c"]}, ["LUT", "worst_slack"], {}, {}, as_dict=True)


def _markers(state, key="color"):
    values = []
    for trace in _figure(state)["data"]:
        value = trace["marker"].get(key)
        values.extend(value if isinstance(value, list) else [value] * len(trace["x"]))
    return values


def test_highlighted_points_take_the_color_and_grow():
    assert _markers(_state(rules.OUTSIDE_HIGHLIGHT)).count(rules.DEFAULT_HIGHLIGHT_COLOR) == 1
    sizes = _markers(_state(rules.OUTSIDE_HIGHLIGHT), "size")
    assert builder.MARKER_SIZE * builder.LARGE_SCALE in sizes


def test_ring_effect_keeps_the_fill_and_adds_an_outline():
    state = _inverted(rules.OUTSIDE_HIGHLIGHT)
    rules.set_field(state, rules.ROOT_ID, "highlight_effect", rules.EFFECT_RING)
    assert rules.DEFAULT_HIGHLIGHT_COLOR not in _markers(state)
    rings = [trace["marker"].get("line") for trace in _figure(state)["data"]]
    assert any(ring and rules.DEFAULT_HIGHLIGHT_COLOR in ring["color"] for ring in rings)


def test_dimmed_points_are_faded():
    colors = _markers(_state(rules.OUTSIDE_DIM))
    assert sum(1 for color in colors if str(color).endswith("," + str(builder.DIM_ALPHA) + ")")) == 1


def test_dim_fades_the_line_and_redraws_the_kept_segments():
    df = rules.apply_rules(_df().assign(**{schema.COL_CONFIGURATION: "a"}), _state(rules.OUTSIDE_DIM))
    spec = FigureSpec(kind="scatter", x="LUT", y="worst_slack", toggles=("scatter_lines",))
    data = builder.build_figure(df, spec, {schema.COL_CONFIGURATION: ["a"]}, ["LUT", "worst_slack"], {}, {}, as_dict=True)["data"]
    assert len(data) == 2
    line, overlay = data
    assert line["line"]["color"].endswith("," + str(builder.DIM_ALPHA) + ")")
    assert overlay["y"] == [0.5, None, 0.1]
    assert overlay["showlegend"] is False and overlay["legendgroup"] == line["legendgroup"]


def test_highlight_recolors_the_segments_touching_a_highlighted_point():
    df = rules.apply_rules(_df().assign(**{schema.COL_CONFIGURATION: "a"}), _state(rules.OUTSIDE_HIGHLIGHT))
    spec = FigureSpec(kind="scatter", x="LUT", y="worst_slack", toggles=("scatter_lines",))
    data = builder.build_figure(df, spec, {schema.COL_CONFIGURATION: ["a"]}, ["LUT", "worst_slack"], {}, {}, as_dict=True)["data"]
    assert len(data) == 2
    overlay = data[1]
    assert overlay["line"]["color"] == rules.DEFAULT_HIGHLIGHT_COLOR
    assert overlay["x"] == [10, 20, 30, None] and overlay["y"] == [0.5, -0.2, 0.1, None]


def test_csv_says_which_records_match():
    frame = csv_frame(rules.apply_rules(_df(), _inverted(rules.OUTSIDE_HIGHLIGHT)))
    assert frame[MATCHES_RULES_COLUMN].tolist() == [False, True, False]
    assert rules.MISS_COLUMN not in frame.columns and rules.MARK_COLUMN not in frame.columns
