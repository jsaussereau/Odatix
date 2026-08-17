"""Regression tests for Explorer chart control persistence."""

from odatix.explorer.callbacks.controls import _merge_control_state


def test_hidden_scatter_axis_does_not_overwrite_saved_z_axis():
    state = {
        "x": "frequency",
        "y": "area",
        "z": "power",
        "color_by": "target",
    }

    updated = _merge_control_state(
        state,
        "scatter",
        "frequency",
        "area",
        None,
        "target",
        "none",
        "none",
        "none",
    )

    assert updated["x"] == "frequency"
    assert updated["y"] == "area"
    assert updated["z"] == "power"


def test_scatter3d_updates_saved_z_axis():
    state = {"x": "frequency", "y": "area", "z": "power"}

    updated = _merge_control_state(
        state,
        "scatter3d",
        "frequency",
        "area",
        "delay",
        "target",
        "none",
        "none",
        "none",
    )

    assert updated["z"] == "delay"
