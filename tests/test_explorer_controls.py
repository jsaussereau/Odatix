"""Regression tests for Explorer chart control persistence."""

from odatix.explorer.callbacks.controls import _merge_control_state


def _merge(state, kind, x, y, z, y_metrics=None):
    """Merge with every control that is not an axis left at its default."""
    return _merge_control_state(
        state,
        kind,
        x,
        y,
        z,
        "target",  # color_by
        "none",  # symbol_by
        "none",  # legend_group_by
        "none",  # sort_by
        "none",  # sort_x_by
        "asc",  # sort_x_order
        False,  # dissociate
        y_metrics,
    )


def test_hidden_scatter_axis_does_not_overwrite_saved_z_axis():
    state = {
        "x": "frequency",
        "y": "area",
        "z": "power",
        "color_by": "target",
    }

    updated = _merge(state, "scatter", "frequency", "area", None)

    assert updated["x"] == "frequency"
    assert updated["y"] == "area"
    assert updated["z"] == "power"


def test_scatter3d_updates_saved_z_axis():
    state = {"x": "frequency", "y": "area", "z": "power"}

    updated = _merge(state, "scatter3d", "frequency", "area", "delay")

    assert updated["z"] == "delay"


def test_only_parcoords_saves_its_metric_list():
    state = {"y_metrics": ["area", "power"]}

    assert _merge(state, "scatter", "frequency", "area", None, y_metrics=None)["y_metrics"] == ["area", "power"]
    assert _merge(state, "parcoords", None, None, None, y_metrics=["delay"])["y_metrics"] == ["delay"]
