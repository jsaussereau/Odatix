"""Tests for odatix.explorer.charts.builder (trace grouping / coloring)."""

import pandas as pd
import pytest

import odatix.explorer.charts.builder as builder
import odatix.explorer.core.schema as schema
from odatix.explorer.charts.spec import FigureSpec, NONE_VALUE


def _df():
    # Two configurations sharing the same EBNO x-values, like a sweep run
    # twice with a different setup (see workflow_metric_sweep example).
    return pd.DataFrame(
        {
            schema.COL_CONFIGURATION: ["channel_gain-0.5"] * 3 + ["channel_gain-1.0"] * 3,
            "EBNO": [1, 1.5, 2, 1, 1.5, 2],
            "FER": [0.31, 0.24, 0.17, 0.11, 0.07, 0.04],
        }
    )


def _dimensions(df):
    return {schema.COL_CONFIGURATION: sorted(df[schema.COL_CONFIGURATION].unique().tolist())}


class TestAutoLineGrouping:
    def test_line_chart_auto_groups_by_configuration_when_no_explicit_grouping(self):
        df = _df()
        spec = FigureSpec(kind="lines", x="EBNO", y="FER")
        dimensions = _dimensions(df)
        groups = builder.group_traces(df, spec, dimensions)
        assert len(groups) == 2
        names = sorted(info[schema.COL_CONFIGURATION] for info, _ in groups)
        assert names == ["channel_gain-0.5", "channel_gain-1.0"]

    def test_line_chart_traces_get_distinct_colors_automatically(self):
        df = _df()
        spec = FigureSpec(kind="lines", x="EBNO", y="FER")
        dimensions = _dimensions(df)
        colors = set()
        for info, _ in builder.group_traces(df, spec, dimensions):
            color_index, _ = builder.style_indices(
                info, spec, dimensions, dimensions, color_by=builder._auto_line_color_dimension(spec, dimensions)
            )
            colors.add(color_index)
        assert len(colors) == 2

    def test_explicit_color_by_disables_auto_grouping_override(self):
        # Auto-grouping still identity-splits (still 2 traces), but color
        # indexing must follow the user's explicit choice, not be overridden.
        df = _df()
        spec = FigureSpec(kind="lines", x="EBNO", y="FER", color_by=schema.COL_CONFIGURATION)
        dimensions = _dimensions(df)
        assert builder._auto_line_color_dimension(spec, dimensions) is None

    def test_explicit_symbol_by_disables_auto_configuration_grouping(self):
        # If the user already picked a different explicit grouping (symbol),
        # don't also silently group by configuration behind their back.
        df = _df()
        spec = FigureSpec(kind="lines", x="EBNO", y="FER", symbol_by="something_else")
        dimensions = _dimensions(df)
        assert builder._auto_line_color_dimension(spec, dimensions) is None

    def test_no_auto_grouping_for_scatter_charts(self):
        df = _df()
        spec = FigureSpec(kind="scatter", x="EBNO", y="FER")
        dimensions = _dimensions(df)
        assert builder._auto_line_color_dimension(spec, dimensions) is None

    def test_no_auto_grouping_when_configuration_is_the_x_axis(self):
        df = _df()
        spec = FigureSpec(kind="lines", x=schema.COL_CONFIGURATION, y="FER")
        dimensions = _dimensions(df)
        assert builder._auto_line_color_dimension(spec, dimensions) is None

    def test_no_auto_grouping_when_single_configuration(self):
        df = _df()[lambda d: d[schema.COL_CONFIGURATION] == "channel_gain-0.5"]
        spec = FigureSpec(kind="lines", x="EBNO", y="FER")
        dimensions = _dimensions(df)
        assert builder._auto_line_color_dimension(spec, dimensions) is None

    def test_build_figure_produces_two_non_zigzagging_traces(self):
        df = _df()
        spec = FigureSpec(kind="lines", x="EBNO", y="FER", toggles=("lines",))
        dimensions = _dimensions(df)
        fig = builder.build_figure(df, spec, dimensions, metrics=["FER"], units={}, chrome={})
        assert len(fig.data) == 2
        for trace in fig.data:
            # each trace's own x values must already be monotonically sorted
            assert list(trace.x) == sorted(trace.x)
