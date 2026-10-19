"""An "operation" synthesis metric computes on the extracted values, not on their "format" (W-15)."""

import odatix.components.export_results as export_results
from odatix.components.export_common import exact_value


def _extract(tmp_path, metrics):
    (tmp_path / "report.txt").write_text("power 0.0004\nluts 12\nregs 30\n", encoding="utf-8")
    export_results._reset_banned_lists()
    results, _units, _measured = export_results.extract_metrics(
        {"metrics": metrics}, str(tmp_path / "metrics.yml"), str(tmp_path), "arch", str(tmp_path),
    )
    return results


def _regex(pattern, **extra):
    metric = {"type": "regex", "settings": {"file": "report.txt", "pattern": pattern, "group_id": 1}}
    metric.update(extra)
    return metric


def test_operation_reads_the_value_before_its_format(tmp_path):
    results = _extract(tmp_path, {
        "Power": _regex(r"power (\S+)", format="%.2f"),          # written as 0.0
        "Power_uW": {"type": "operation", "settings": {"op": "Power * 1e6"}},
    })
    assert results["Power"] == 0.0
    assert abs(results["Power_uW"] - 400.0) < 1e-9


def test_operation_on_unformatted_values_is_numeric(tmp_path):
    # Without a "format", a regex group is text: "12" + "30" must not read "1230"
    results = _extract(tmp_path, {
        "LUT": _regex(r"luts (\d+)"),
        "Reg": _regex(r"regs (\d+)"),
        "Cells": {"type": "operation", "settings": {"op": "LUT + Reg"}},
    })
    assert results["Cells"] == 42


def test_the_operation_itself_is_still_formatted(tmp_path):
    results = _extract(tmp_path, {
        "LUT": _regex(r"luts (\d+)"),
        "Reg": _regex(r"regs (\d+)"),
        "Ratio": {"type": "operation", "format": "%.1f", "settings": {"op": "LUT / Reg"}},
    })
    assert results["Ratio"] == 0.4


def test_exact_value():
    assert exact_value("12") == 12 and exact_value("1e-05") == 1e-05 and exact_value("abc") == "abc"
    assert exact_value(None) is None
