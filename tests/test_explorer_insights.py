"""Tests for the insights section of the Explorer home page (generated view cards)."""

import dash
import yaml

# The page module registers itself at import time, which Dash only allows once
# an app exists.
dash.Dash(__name__, use_pages=True, pages_folder="")

import odatix.explorer.core.recommend as recommend
import odatix.explorer.core.views as views
import odatix.explorer.ui.insights as insights
from odatix.explorer.core.store import ResultStore


def _store(tmp_path, records, units=None):
    (tmp_path / "results_demo.yml").write_text(
        yaml.safe_dump({"schema": 2, "units": units or {}, "results": records})
    )
    store = ResultStore()
    store.configure(tmp_path)
    return store


def _synthesis(configuration, width, area, fmax):
    return {
        "meta": {
            "type": "fmax_synthesis", "architecture": "alu", "configuration": configuration,
            "target": "fpga", "width": width,
        },
        "metrics": {"cell_area": area, "Fmax": fmax},
    }


def _design_space(tmp_path):
    return _store(
        tmp_path,
        [_synthesis("w4", 4, 100, 400), _synthesis("w8", 8, 190, 320),
         _synthesis("w16", 16, 400, 250), _synthesis("w32", 32, 810, 180)],
        units={"cell_area": "um2", "Fmax": "MHz"},
    )


def _stepped(tmp_path):
    """A job exported step by step, as a multi-step flow writes it."""
    records = []
    for index, (configuration, area) in enumerate([("small", 100), ("big", 400)]):
        records.append({
            "meta": {"type": "fmax_synthesis", "architecture": "alu", "configuration": configuration,
                     "step": "synthesis", "_step_index": 0, "_last_step": False},
            "metrics": {"cell_area": area, "Fmax": 400 - index * 100},
        })
        records.append({
            "meta": {"type": "fmax_synthesis", "architecture": "alu", "configuration": configuration,
                     "step": "pnr", "_step_index": 1, "_last_step": True},
            "metrics": {"cell_area": area * 1.2, "Fmax": 350 - index * 100},
        })
    return _store(tmp_path, records)


def test_the_gallery_starts_from_the_same_selection_as_a_chart_page(tmp_path):
    store = _stepped(tmp_path)

    filters = insights.default_filters(store, store.source_names())

    # The intermediate steps a job went past are excluded, exactly as they are
    # on a freshly opened chart page: recommendations must describe what the
    # user would actually see.
    assert filters["Step scope"] == ["last"]


def test_a_selection_without_anything_to_hide_needs_no_filter(tmp_path):
    store = _design_space(tmp_path)

    assert insights.default_filters(store, store.source_names()) == {}


def test_the_gallery_only_recomputes_when_the_data_changed(tmp_path):
    """The page keys its cache on the store version, which is the store's own
    "something really changed" signal."""
    store = _design_space(tmp_path)
    before = store.version

    assert store.poll(force=True) is False
    assert store.version == before

    (tmp_path / "results_more.yml").write_text(
        yaml.safe_dump({"schema": 2, "results": [_synthesis("w64", 64, 1600, 140)]})
    )
    assert store.poll(force=True) is True
    assert store.version != before


def test_every_card_carries_a_thumbnail_a_title_and_a_reason(tmp_path):
    store = _design_space(tmp_path)
    context = recommend.build_context(store, sources=store.source_names())
    recommendations = recommend.recommend(context)
    assert recommendations

    card = insights._card(0, recommendations[0])
    hit, thumb_box, body, foot = card.children

    # The whole card opens the chart, and Save sits on top of that hit area
    # rather than nesting a button inside a button.
    assert hit.id == {"type": "xp-reco-open", "index": 0}
    assert foot.children[1].id == {"type": "xp-reco-save", "index": 0}
    assert thumb_box.children[0].children is not None
    title, why = body.children
    assert title.children == recommendations[0].title
    assert why.children == recommendations[0].why


def test_a_card_summarizes_its_sources_instead_of_listing_them_all(tmp_path):
    many = ["source_" + str(index) for index in range(7)]

    tags = insights._source_tags(many)

    # A dozen source names on one line is what made the cards unreadable.
    assert [tag.children for tag in tags] == ["7 sources"]
    assert tags[0].title == ", ".join(many)
    # Few enough to be worth naming: they are named.
    assert [tag.children for tag in insights._source_tags(["a", "b"])] == ["a", "b"]


def test_the_source_chips_are_a_multi_select_with_an_all_reset():
    available = ["alpha", "beta"]

    chips = insights._source_chips(available, ["beta"])

    assert [chip.children for chip in chips] == ["All sources", "alpha", "beta"]
    # "All" is the selected state precisely when no source is singled out.
    assert "xp-chip-active" not in chips[0].className
    assert "xp-chip-active" in chips[2].className
    assert insights._source_chips(["only"], []) == []


def test_a_stale_source_selection_falls_back_to_everything():
    available = ["alpha", "beta"]

    # A source disappeared since the chip was clicked: measuring nothing at all
    # would leave the user staring at an empty gallery.
    assert insights.selected_sources(["gone"], available) == available
    assert insights.selected_sources([], available) == available
    assert insights.selected_sources(["beta"], available) == ["beta"]


def test_an_empty_workspace_says_so_instead_of_showing_nothing(tmp_path):
    assert "Nothing to recommend yet" in insights._empty_state(False).children[0].children
    # With data loaded, the same emptiness means the selection is too narrow.
    assert "this selection" in insights._empty_state(True).children[0].children


def test_a_saved_recommendation_becomes_a_normal_view_file(tmp_path):
    store = _design_space(tmp_path)
    context = recommend.build_context(store, sources=store.source_names())
    recommendation = recommend.recommend(context)[0]

    slug = views.save_view(tmp_path, recommendation.view.get("name"), recommendation.view)

    # It must come back exactly like a hand-saved view: listed on the home page,
    # loadable, and honored by the live data without a single repair.
    listed = views.list_views(tmp_path)
    assert [view["name"] for view in listed] == [slug]
    _payload, warnings = views.sanitize_view(views.load_view(tmp_path, slug), store)
    assert warnings == []


def test_a_card_announces_the_scope_it_was_measured_on():
    tags = insights._source_tags(["vivado", "vivado_hls"], "vivado vs vivado_hls")

    # The scope is the identifying fact: "2 sources" says nothing about which.
    assert [tag.children for tag in tags] == ["vivado vs vivado_hls"]
    assert "xp-reco-tag-scope" in tags[0].className
