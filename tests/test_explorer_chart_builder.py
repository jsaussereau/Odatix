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


class TestScatterAxes:
    def _df_with_missing(self):
        # The second configuration has no Fmax at all (failed run): its trace
        # alone must not turn the numeric x axis categorical.
        return pd.DataFrame(
            {
                schema.COL_CONFIGURATION: ["a", "a", "b", "b"],
                "Fmax": [250.0, 100.0, None, None],
                "Area": [10.0, 20.0, 30.0, 40.0],
                "variant": ["v16", None, "v8", "v32"],
            }
        )

    def test_missing_values_never_reach_a_numeric_axis(self):
        df = self._df_with_missing()
        spec = FigureSpec(kind="scatter", x="Fmax", y="Area", color_by=schema.COL_CONFIGURATION)
        fig = builder.build_figure(df, spec, _dimensions(df), metrics=["Fmax", "Area"], units={}, chrome={})
        xs = [value for trace in fig.data for value in trace.x]
        assert sorted(xs) == [100.0, 250.0]
        assert fig.layout.xaxis.type != "category"

    def test_categorical_axis_is_naturally_sorted_without_missing(self):
        df = self._df_with_missing()
        spec = FigureSpec(kind="scatter", x="variant", y="Area")
        fig = builder.build_figure(df, spec, _dimensions(df), metrics=["Area"], units={}, chrome={})
        assert list(fig.layout.xaxis.categoryarray) == ["v8", "v16", "v32"]
        assert schema.MISSING_VALUE not in [value for trace in fig.data for value in trace.x]


class TestScatterLabels:
    def test_labels_follow_their_points_when_lines_reorder_them(self):
        df = pd.DataFrame({
            schema.COL_CONFIGURATION: ["c", "a", "b"],
            "F": [3.0, 1.0, 2.0], "A": [30.0, 10.0, 20.0], "name": ["three", "one", "two"],
        })
        spec = FigureSpec(kind="scatter", x="F", y="A", label_by="name", toggles=("scatter_lines", "labels"))
        fig = builder.build_figure(df, spec, {"name": ["one", "three", "two"]}, metrics=["F", "A"], units={}, chrome={})
        trace = fig.data[0]
        assert list(trace.x) == [1.0, 2.0, 3.0]
        assert list(trace.text) == ["one", "two", "three"]


class TestXOrder:
    def _df(self):
        return pd.DataFrame({"v": ["p", "q", "r"], "A": [1.0, None, 3.0]})

    def test_a_category_without_value_goes_last_ascending(self):
        assert builder._x_categories(self._df(), FigureSpec(kind="bar", x="v", y="A", sort_x_order="y_asc")) == ["p", "r", "q"]

    def test_a_category_without_value_goes_last_descending(self):
        assert builder._x_categories(self._df(), FigureSpec(kind="bar", x="v", y="A", sort_x_order="y_desc")) == ["r", "p", "q"]

    def test_reverse_still_reverses_the_natural_order(self):
        assert builder._x_categories(self._df(), FigureSpec(kind="bar", x="v", y="A", sort_x_order="reverse")) == ["r", "q", "p"]


class TestParcoordsMissingValues:
    def _df(self):
        return pd.DataFrame({
            schema.COL_CONFIGURATION: ["a", "b", "c", "d"],
            "area": [10.0, None, 30.0, 40.0],
            "fmax": [100.0, 200.0, 300.0, 400.0],
            "power": [1.0, 2.0, 3.0, None],
        })

    def _figure(self, df, **spec):
        spec = FigureSpec(kind="parcoords", y_metrics=("area", "fmax"), **spec)
        return builder.build_figure(df, spec, {}, metrics=["area", "fmax", "power"], units={}, chrome={})

    def test_a_design_missing_a_charted_metric_is_left_out_and_counted(self):
        fig = self._figure(self._df())
        values = [list(dimension["values"]) for dimension in fig.data[0].dimensions]
        assert values == [[10.0, 30.0, 40.0], [100.0, 300.0, 400.0]]
        assert [annotation.text for annotation in fig.layout.annotations] == ["1 design without a value excluded"]

    def test_a_missing_numeric_color_is_left_out_too(self):
        fig = self._figure(self._df(), color_by=("power",))
        assert list(fig.data[0].line.color) == [1.0, 3.0]
        assert fig.layout.annotations[0].text == "2 designs without a value excluded"

    def test_nothing_excluded_says_nothing(self):
        fig = self._figure(self._df().dropna())
        assert not fig.layout.annotations


class TestNoRecordHiddenAtTheSameX:
    """Several records of a trace at the same x: every one of them is drawn."""

    def _sweep(self):
        # A ``multiple`` metric: one record per EBNO row, x = configuration
        return pd.DataFrame(
            {
                schema.COL_CONFIGURATION: ["gain-0.5"] * 3 + ["gain-1.0"] * 3,
                "EBNO": ["1.0", "2.0", "3.0"] * 2,
                "FER": [0.31, 0.17, 0.07, 0.11, 0.04, 0.01],
            }
        )

    def _dimensions(self, df):
        return {column: sorted(df[column].astype(str).unique().tolist()) for column in (schema.COL_CONFIGURATION, "EBNO")}

    @pytest.mark.parametrize("kind", ["lines", "columns", "radar"])
    def test_every_record_is_drawn(self, kind):
        df = self._sweep()
        spec = FigureSpec(kind=kind, x=schema.COL_CONFIGURATION, y="FER")
        fig = builder.build_figure(df, spec, self._dimensions(df), ["FER"], {}, {})
        values = []
        for trace in fig.data:
            values += [value for value in (trace.r if kind == "radar" else trace.y) if value is not None]
        assert sorted(set(values)) == sorted(df["FER"].tolist())
        assert len(fig.data) == 3
        assert not fig.layout.annotations

    def test_split_dimension_is_named_in_the_trace_and_colored(self):
        df = self._sweep()
        spec = FigureSpec(kind="lines", x=schema.COL_CONFIGURATION, y="FER")
        fig = builder.build_figure(df, spec, self._dimensions(df), ["FER"], {}, {})
        assert sorted(trace.name for trace in fig.data) == ["EBNO: 1.0", "EBNO: 2.0", "EBNO: 3.0"]
        assert len({trace.line.color for trace in fig.data}) == 3

    def test_user_colors_kept_split_goes_to_symbols(self):
        df = self._sweep()
        spec = FigureSpec(kind="lines", x=schema.COL_CONFIGURATION, y="FER", color_by=(schema.COL_CONFIGURATION,))
        dimensions = self._dimensions(df)
        split, hidden = builder.split_dimensions(df, spec, dimensions)
        assert split == ["EBNO"] and hidden == 0
        assert builder.auto_style_dimensions(spec, dimensions, split) == (None, ("EBNO",))

    def test_step_preferred_to_step_scope(self):
        df = pd.DataFrame(
            {
                schema.COL_CONFIGURATION: ["a", "a", "b", "b"],
                schema.COL_STEP: ["synthesis", "pnr"] * 2,
                schema.COL_STEP_SCOPE: ["intermediate", "last"] * 2,
                "LUT": [10, 12, 20, 22],
            }
        )
        dimensions = {column: sorted(df[column].unique().tolist()) for column in (schema.COL_CONFIGURATION, schema.COL_STEP, schema.COL_STEP_SCOPE)}
        spec = FigureSpec(kind="columns", x=schema.COL_CONFIGURATION, y="LUT")
        assert builder.split_dimensions(df, spec, dimensions) == ([schema.COL_STEP], 0)

    def test_records_nothing_tells_apart_are_counted_on_the_figure(self):
        df = pd.DataFrame({schema.COL_CONFIGURATION: ["a", "a", "b"], "LUT": [1, 2, 3]})
        dimensions = {schema.COL_CONFIGURATION: ["a", "b"]}
        spec = FigureSpec(kind="lines", x=schema.COL_CONFIGURATION, y="LUT")
        fig = builder.build_figure(df, spec, dimensions, ["LUT"], {}, {})
        assert "1 record shares an x value" in fig.layout.annotations[0].text

    def test_scatter_is_left_alone(self):
        df = self._sweep()
        spec = FigureSpec(kind="scatter", x="FER", y="FER")
        assert builder.split_dimensions(df, spec, self._dimensions(df)) == ([], 0)
