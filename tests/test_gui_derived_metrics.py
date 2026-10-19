"""GUI derived metrics page: a save keeps what the cards do not edit (C-03)."""

import pytest

dash = pytest.importorskip("dash")

from odatix.workspace import Workspace


@pytest.fixture(scope="module")
def page():
    # dash.register_page (called at page-module import) requires an app
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.derived_metrics as derived_metrics_page
    return derived_metrics_page


def _round_trip(page, definition):
    fields = page.card_fields_of(definition)
    return page.build_metric_definition(
        kind=fields["kind_value"], from_value=fields["from_value"], metric_value=fields["metric_value"],
        op_value=fields["op_value"], for_value=fields["for_value"], apply_to_value=fields["apply_to_value"],
        unit_value=fields["unit_value"], pin_value=fields["pin_value"], ignore_value=fields["ignore_value"],
        map_value=fields["map_value"], on_value=fields["on_value"], on_multiple_value=fields["on_multiple_value"],
        where_value=fields["where_value"], source_where_value=fields["source_where_value"],
        optional_value=fields["optional_value"], overwrite_value=fields["overwrite_value"],
        step_value=fields["step_value"], extra_value=fields["extra_value"],
    )


def test_step_survives_a_save(page):
    definition = {"type": "import", "metric": "LUT_count", "from": "synthesis", "step": "synthesis", "unit": "LUTs"}
    assert _round_trip(page, definition)["step"] == "synthesis"


def test_a_step_list_survives_a_save(page):
    definition = {"type": "import", "from": "synthesis", "step": ["synthesis", "pnr"], "on_multiple": "max"}
    assert _round_trip(page, definition)["step"] == ["synthesis", "pnr"]


def test_keys_no_card_edits_survive_a_save(page):
    definition = {"type": "import", "from": "simulation", "future_key": 3, "match": {"keys": ["architecture"], "strict": True}}
    rebuilt = _round_trip(page, definition)
    assert rebuilt["future_key"] == 3
    assert rebuilt["match"] == {"keys": ["architecture"], "strict": True}


def test_a_definition_round_trips_unchanged(page):
    # Otherwise the page would claim unsaved changes as soon as it opens
    definition = {"type": "import", "from": "pnr", "step": "any", "on_multiple": "mean"}
    assert page.normalize_metrics({"m": definition})["m"] == _round_trip(page, definition)


def test_place_and_route_and_written_aliases_are_offered(page):
    values = [option["value"] for option in page.result_type_options(["fmax", "custom_freq"])]
    assert "pnr" in values and "fmax" in values and "custom_freq" in values


def test_saving_keeps_the_comments_of_unchanged_metrics(tmp_path):
    path = tmp_path / "odatix_userconfig" / "derived_metrics.yml"
    path.parent.mkdir()
    path.write_text(
        "derived_metrics:\n"
        "  LUT_count_after_synthesis:\n"
        "    metric: LUT_count\n"
        "    from: synthesis\n"
        "    step: synthesis   # what P&R did to the estimate\n"
    )
    derived = Workspace.open(str(tmp_path)).derived_metrics
    derived.set("Ratio", {"type": "operation", "op": "LUT_count / meta.frequency"})
    derived.save()
    text = path.read_text(encoding="utf-8")
    assert "# what P&R did to the estimate" in text and "Ratio" in text
