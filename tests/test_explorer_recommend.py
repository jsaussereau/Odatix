"""Tests for the Explorer's recommended charts engine."""

import yaml

import odatix.explorer.core.recommend as recommend
import odatix.explorer.core.views as views
from odatix.explorer.core.store import ResultStore


def _store(tmp_path, records, units=None):
    (tmp_path / "results_demo.yml").write_text(
        yaml.safe_dump({"schema": 2, "units": units or {}, "results": records})
    )
    store = ResultStore()
    store.configure(tmp_path)
    return store


def _synthesis(configuration, width, area, fmax, target="fpga"):
    return {
        "meta": {
            "type": "fmax_synthesis", "architecture": "alu", "configuration": configuration,
            "target": target, "width": width,
        },
        "metrics": {"cell_area": area, "Fmax": fmax},
    }


def _design_space(tmp_path):
    """A small space where area and Fmax trade against each other."""
    return _store(
        tmp_path,
        [
            _synthesis("w4", 4, 100, 400),
            _synthesis("w8", 8, 190, 320),
            _synthesis("w16", 16, 400, 250),
            _synthesis("w32", 32, 810, 180),
            _synthesis("w4", 4, 120, 380, target="asic"),
            _synthesis("w8", 8, 210, 300, target="asic"),
            _synthesis("w16", 16, 430, 240, target="asic"),
            _synthesis("w32", 32, 850, 170, target="asic"),
        ],
    )


######################################
# Direction guessing
######################################


def test_metric_direction_reads_the_unit_first():
    assert recommend.metric_direction("Total_Power", {"Total_Power": "W"}) == recommend.MINIMIZE
    assert recommend.metric_direction("clock", {"clock": "MHz"}) == recommend.MAXIMIZE


def test_metric_direction_falls_back_on_name_tokens():
    assert recommend.metric_direction("cell_area") == recommend.MINIMIZE
    assert recommend.metric_direction("Fmax") == recommend.MAXIMIZE
    # The longest matching token wins: a violation is bad even though "slack" is good
    assert recommend.metric_direction("slack_violation") == recommend.MINIMIZE


def test_metric_direction_admits_it_does_not_know():
    assert recommend.metric_direction("wibble") == recommend.UNKNOWN


######################################
# Measuring the selection
######################################


def test_a_flat_metric_is_never_worth_charting(tmp_path):
    store = _store(
        tmp_path,
        [
            {"meta": {"type": "workflow", "configuration": "a"}, "metrics": {"constant": 42, "varying": 1}},
            {"meta": {"type": "workflow", "configuration": "b"}, "metrics": {"constant": 42, "varying": 90}},
        ],
    )
    ctx = recommend.build_context(store)

    assert ctx.metric_stats["constant"].is_flat
    assert ctx.metric_stats["constant"].interest == 0.0
    assert "constant" not in ctx.ranked_metrics()
    assert "varying" in ctx.ranked_metrics()


def test_a_parameter_is_ordinal_even_when_its_values_carry_a_suffix(tmp_path):
    store = _store(
        tmp_path,
        [
            {"meta": {"type": "workflow", "configuration": "a", "taps": "8taps", "board": "xc7a100t"}, "metrics": {"score": 1}},
            {"meta": {"type": "workflow", "configuration": "b", "taps": "16taps", "board": "sky130"}, "metrics": {"score": 2}},
            {"meta": {"type": "workflow", "configuration": "c", "taps": "32taps", "board": "gf22"}, "metrics": {"score": 4}},
        ],
    )
    ctx = recommend.build_context(store)

    assert ctx.dimension_stats["taps"].numeric is True
    assert ctx.dimension_stats["board"].numeric is False


def test_structural_dimensions_rank_below_design_parameters(tmp_path):
    ctx = recommend.build_context(_design_space(tmp_path))

    assert ctx.dimension_stats["Type"].structural is True
    assert ctx.dimension_stats["width"].structural is False
    assert ctx.dimension_stats["width"].interest > ctx.dimension_stats["Type"].interest


def test_metrics_that_never_share_a_row_are_not_paired(tmp_path):
    """Metrics of two unrelated result types coexist without ever meeting."""
    store = _store(
        tmp_path,
        [
            {"meta": {"type": "fmax_synthesis", "configuration": "a"}, "metrics": {"Fmax": 100}},
            {"meta": {"type": "fmax_synthesis", "configuration": "b"}, "metrics": {"Fmax": 250}},
            {"meta": {"type": "simulation", "configuration": "a"}, "metrics": {"cell_area": 10}},
            {"meta": {"type": "simulation", "configuration": "b"}, "metrics": {"cell_area": 90}},
        ],
    )
    ctx = recommend.build_context(store)

    assert ctx.paired_rows("cell_area", "Fmax") == 0
    assert [reco for reco in recommend.recommend(ctx) if reco.id == "pareto"] == []


def test_measured_values_only_lists_values_carrying_the_metric(tmp_path):
    store = _store(
        tmp_path,
        [
            {"meta": {"type": "workflow", "configuration": "a", "mode": "fast"}, "metrics": {"score": 1}},
            {"meta": {"type": "workflow", "configuration": "b", "mode": "slow"}, "metrics": {"score": 9}},
            {"meta": {"type": "workflow", "configuration": "c", "mode": "off"}, "metrics": {"score": None}},
        ],
    )
    ctx = recommend.build_context(store)

    assert ctx.measured_values("mode", "score") == ["fast", "slow"]


######################################
# The recommendations themselves
######################################


def test_a_design_space_gets_a_trade_off_and_a_scaling_chart(tmp_path):
    ctx = recommend.build_context(_design_space(tmp_path))
    by_id = dict((reco.id, reco) for reco in recommend.recommend(ctx))

    pareto = by_id["pareto"]
    assert pareto.view["kind"] == "scatter"
    # The cost goes on x and the gain on y, whichever way round the guess found them
    assert pareto.view["controls"]["x"] == "cell_area"
    assert pareto.view["controls"]["y"] == "Fmax"

    scaling = by_id["scaling"]
    assert scaling.view["kind"] == "lines"
    assert scaling.view["controls"]["x"] == "width"


def test_every_recommendation_survives_sanitization(tmp_path):
    store = _design_space(tmp_path)
    ctx = recommend.build_context(store)

    recos = recommend.recommend(ctx)
    assert recos

    for reco in recos:
        payload, warnings = views.sanitize_view(reco.view, store)
        assert warnings == [], reco.id
        assert payload["kind"] == reco.view["kind"]
        assert reco.title and reco.why


def test_recommendations_never_repeat_the_same_chart(tmp_path):
    ctx = recommend.build_context(_design_space(tmp_path))
    recos = recommend.recommend(ctx)

    signatures = [reco.signature for reco in recos]
    assert len(signatures) == len(set(signatures))


def test_recommendations_are_ranked_best_first(tmp_path):
    ctx = recommend.build_context(_design_space(tmp_path))
    scores = [reco.score for reco in recommend.recommend(ctx)]

    assert scores == sorted(scores, reverse=True)


def test_the_limit_is_honored(tmp_path):
    ctx = recommend.build_context(_design_space(tmp_path))

    assert len(recommend.recommend(ctx, limit=2)) == 2


def test_stated_interest_floats_the_named_metric_up(tmp_path):
    """A metric the user asked about should climb, without emptying the gallery."""
    store = _store(
        tmp_path,
        [
            {"meta": {"type": "workflow", "configuration": "a", "width": 4}, "metrics": {"headline": 1, "aside": 100}},
            {"meta": {"type": "workflow", "configuration": "b", "width": 8}, "metrics": {"headline": 4, "aside": 130}},
            {"meta": {"type": "workflow", "configuration": "c", "width": 16}, "metrics": {"headline": 40, "aside": 90}},
        ],
    )
    ctx = recommend.build_context(store)

    neutral = recommend.recommend(ctx)
    focused = recommend.recommend(ctx, intent={"metrics": ["aside"]})

    def charts_aside(reco):
        controls = reco.view["controls"]
        return controls.get("y") == "aside" or "aside" in (controls.get("y_metrics") or [])

    assert len(focused) == len(neutral)
    assert any(charts_aside(reco) for reco in focused)
    assert focused[0].score > neutral[0].score


def test_the_current_filters_are_carried_into_the_view(tmp_path):
    store = _design_space(tmp_path)
    ctx = recommend.build_context(store, filters={"Target": ["fpga"]})

    recos = recommend.recommend(ctx)
    assert recos
    # The view hides what the selection excluded, rather than silently widening it
    assert recos[0].view["filters"]["Target"] == ["asic"]


def test_empty_data_recommends_nothing(tmp_path):
    store = _store(tmp_path, [{"meta": {"type": "workflow", "configuration": "a"}, "metrics": {}}])
    ctx = recommend.build_context(store)

    assert recommend.recommend(ctx) == []


######################################
# Scopes: what may legitimately be compared
######################################


def _sources(tmp_path, files, units=None):
    """One result file per source, so the store sees several sources."""
    for name, records in files.items():
        (tmp_path / ("results_" + name + ".yml")).write_text(
            yaml.safe_dump({"schema": 2, "units": units or {}, "results": records})
        )
    store = ResultStore()
    store.configure(tmp_path)
    return store


def _implemented(architecture, configuration, area, fmax):
    return {
        "meta": {"type": "fmax_synthesis", "architecture": architecture,
                 "configuration": configuration, "target": "fpga"},
        "metrics": {"cell_area": area, "Fmax": fmax},
    }


def _two_tools(tmp_path):
    """The same two designs implemented by two tools, plus a simulation of them."""
    return _sources(tmp_path, {
        "toolA": [_implemented("alu", "w8", 190, 320), _implemented("alu", "w16", 400, 250),
                  _implemented("alu", "w32", 810, 180)],
        "toolB": [_implemented("alu", "w8", 210, 300), _implemented("alu", "w16", 430, 240),
                  _implemented("alu", "w32", 850, 170)],
        "sim": [{"meta": {"type": "simulation", "architecture": "alu", "configuration": "w8"},
                 "metrics": {"cycles": 40}},
                {"meta": {"type": "simulation", "architecture": "alu", "configuration": "w16"},
                 "metrics": {"cycles": 90}},
                {"meta": {"type": "simulation", "architecture": "alu", "configuration": "w32"},
                 "metrics": {"cycles": 210}}],
    })


def test_two_tools_that_ran_the_same_designs_are_comparable(tmp_path):
    store = _two_tools(tmp_path)
    scopes = recommend.plan_scopes(store, store.source_names())

    cross = [scope for scope in scopes if scope.compare_by == "Source"]
    assert len(cross) == 1
    # The simulation ran the very same configurations, yet shares no metric with
    # a synthesis: putting them on one chart would compare nothing.
    assert cross[0].sources == ["toolA", "toolB"]
    assert cross[0].label == "toolA vs toolB"
    # ... and the comparison is confined to the designs both tools actually ran.
    assert cross[0].filters["Configuration"] == ["w16", "w32", "w8"]
    # Every source still gets measured on its own terms.
    assert set(scope.sources[0] for scope in scopes if scope.compare_by is None) == {"toolA", "toolB", "sim"}


def test_sources_sharing_no_design_are_never_mixed(tmp_path):
    store = _sources(tmp_path, {
        "left": [_implemented("alu", "w8", 190, 320), _implemented("alu", "w16", 400, 250)],
        "right": [_implemented("fir", "t4", 150, 300), _implemented("fir", "t8", 320, 220)],
    })

    assert [scope for scope in recommend.plan_scopes(store, store.source_names()) if scope.compare_by] == []


def test_a_comparison_chart_colors_by_source(tmp_path):
    store = _two_tools(tmp_path)

    recos = recommend.recommend_gallery(store, sources=store.source_names())
    compared = [reco for reco in recos if reco.scope == "toolA vs toolB"]

    assert compared
    # The scope exists to put one trace per tool on the chart.
    assert compared[0].view["controls"]["color_by"] == ["Source"]
    assert "Compared across toolA and toolB" in compared[0].why


def test_the_gallery_spreads_over_the_scopes(tmp_path):
    store = _two_tools(tmp_path)

    recos = recommend.recommend_gallery(store, sources=store.source_names())

    assert len(set(reco.scope for reco in recos)) >= 3
    # No card claims to be about the whole workspace any more.
    for reco in recos:
        assert reco.view["sources"] != store.source_names()


######################################
# Specific charts rather than generic ones
######################################


def test_a_recipe_proposes_every_question_worth_asking(tmp_path):
    """Two parameters and two metrics are four distinct questions, not one."""
    records = []
    for width in (4, 8, 16):
        for taps in (2, 4, 8):
            records.append({
                "meta": {"type": "workflow", "architecture": "fir",
                         "configuration": "w" + str(width) + "t" + str(taps),
                         "width": width, "taps": taps},
                "metrics": {"cell_area": width * taps * 10, "Fmax": 600 - width * taps},
            })
    ctx = recommend.build_context(_store(tmp_path, records))

    scaling = [reco for reco in recommend.recommend(ctx) if reco.id == "scaling"]

    assert len(scaling) > 1
    assert len(set(reco.signature for reco in scaling)) == len(scaling)


def test_a_chart_drops_the_architectures_that_ignore_its_parameter(tmp_path):
    """A parameter domain rarely spans the workspace."""
    records = []
    for width in (4, 8, 16):
        records.append({
            "meta": {"type": "fmax_synthesis", "architecture": "alu",
                     "configuration": "w" + str(width), "width": width},
            "metrics": {"cell_area": width * 25, "Fmax": 500 - width * 5},
        })
    for index, name in enumerate(["a", "b", "c"]):
        records.append({
            "meta": {"type": "fmax_synthesis", "architecture": "rom", "configuration": name},
            "metrics": {"cell_area": 40 + index * 30, "Fmax": 300 + index * 20},
        })
    ctx = recommend.build_context(_store(tmp_path, records))

    scaling = [reco for reco in recommend.recommend(ctx) if reco.id == "scaling"][0]

    assert scaling.view["controls"]["x"] == "width"
    # "rom" has no width at all: leaving it checked means an empty half-chart
    # and a filter panel the user has to clean up by hand.
    assert scaling.view["filters"]["Architecture"] == ["rom"]
    # And the card says what it is about, not just which metrics it draws.
    assert "architecture alu" in scaling.why


######################################
# Audit lot 4: the gallery says true things
######################################


def _pareto_why(tmp_path, pairs):
    store = _store(tmp_path, [
        _synthesis("w" + str(index), index, area + offset, fmax + offset, target=target)
        for target, offset in (("fpga", 0), ("asic", 10))
        for index, (area, fmax) in enumerate(pairs)
    ])
    by_id = dict((reco.id, reco) for reco in recommend.recommend(recommend.build_context(store)))
    return by_id["pareto"].why


def test_a_real_trade_off_is_one_where_paying_more_buys_more(tmp_path):
    # Cost (to minimize) and gain (to maximize) rising together is the compromise.
    why = _pareto_why(tmp_path, [(100, 150), (200, 240), (400, 330), (800, 420)])
    assert "pull against each other" in why


def test_cheaper_and_better_at_once_is_no_trade_off(tmp_path):
    why = _pareto_why(tmp_path, [(100, 400), (190, 320), (400, 250), (810, 180)])
    assert "little to arbitrate" in why
    assert "pull against each other" not in why


def test_comparable_sources_accepts_no_measurement_lookup():
    designs = {"a": {"x", "y"}, "b": {"x", "y"}}
    members, shared = recommend.comparable_sources(designs)
    assert members == ["a", "b"] and shared == {"x", "y"}


def _crossed_tools(tmp_path):
    """Two tools sharing alu/c1 and fir/c2 only: the per-dimension filters of
    that common ground (alu+fir x c1+c2) also admit alu/c2 and fir/c1."""
    return _sources(tmp_path, {
        "toolA": [_implemented("alu", "c1", 100, 300), _implemented("alu", "c2", 200, 260),
                  _implemented("fir", "c1", 150, 280), _implemented("fir", "c2", 300, 200)],
        "toolB": [_implemented("alu", "c1", 110, 290), _implemented("fir", "c2", 320, 190),
                  _implemented("alu", "c3", 400, 150)],
    })


def test_a_cross_scope_is_measured_on_the_exact_shared_designs(tmp_path):
    store = _crossed_tools(tmp_path)
    cross = [scope for scope in recommend.plan_scopes(store, store.source_names()) if scope.compare_by][0]
    assert cross.designs == {"alu :: c1", "fir :: c2"}

    ctx = recommend.build_context(store, sources=cross.sources, filters=cross.filters, designs=cross.designs)
    pairs = set(zip(ctx.df["Architecture"], ctx.df["Configuration"]))
    assert pairs == {("alu", "c1"), ("fir", "c2")}
    assert len(ctx.df) == 4
    assert ctx.widened


def test_a_card_says_when_its_view_reopens_a_wider_selection(tmp_path):
    store = _crossed_tools(tmp_path)
    recos = [reco for reco in recommend.recommend_gallery(store, sources=store.source_names())
             if reco.scope == "toolA vs toolB"]
    assert recos
    for reco in recos:
        assert recommend.WIDENED_VIEW_NOTE in reco.why
        assert reco.view["description"] == reco.why


def test_an_exact_cross_scope_adds_no_note(tmp_path):
    store = _two_tools(tmp_path)
    recos = [reco for reco in recommend.recommend_gallery(store, sources=store.source_names())
             if reco.scope == "toolA vs toolB"]
    assert recos
    assert all(recommend.WIDENED_VIEW_NOTE not in reco.why for reco in recos)
