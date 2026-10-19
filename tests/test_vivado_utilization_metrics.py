"""
D-27: the utilization percentages of Vivado are read from the last column of
the report, "<0.01" included -- not from whatever number comes first.
"""

import os

import yaml

from odatix.components.export_common import parse_regex
from conftest import SOURCES_DIR

REPORT = """\
+-------------------------+------+-------+------------+-----------+-------+
|        Site Type        | Used | Fixed | Prohibited | Available | Util% |
+-------------------------+------+-------+------------+-----------+-------+
| Slice LUTs              |    8 |     0 |          0 |     63400 |  0.01 |
|   LUT as Logic          |    8 |     0 |          0 |     63400 |  0.01 |
| Slice Registers         |    9 |     0 |          0 |    126800 | <0.01 |
|   Register as Flip Flop |    9 |     0 |          0 |    126800 | <0.01 |
+-------------------------+------+-------+------------+-----------+-------+
+----------------+------+-------+------------+-----------+-------+
| Block RAM Tile |    0 |     0 |          0 |       135 |  0.00 |
+----------------+------+-------+------------+-----------+-------+
| DSPs      |   12 |     0 |          0 |       240 |  5.00 |
"""

# An older Vivado, without the "Prohibited" column, and a synthesis report.
OLD_REPORT = """\
| Slice LUTs*             |  120 |     0 |     63400 |  0.19 |
| Slice Registers         |   49 |     0 |    126800 |  0.04 |
"""


def metrics():
    path = os.path.join(SOURCES_DIR, "odatix_eda_tools", "vivado", "metrics.yml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["metrics"]


def read(tmp_path, text, name):
    report = tmp_path / "utilization.rep"
    report.write_text(text, encoding="utf-8")
    settings = metrics()[name]["settings"]
    return parse_regex(str(report), settings["pattern"], settings["group_id"])


def test_a_percentage_below_what_vivado_prints(tmp_path):
    assert read(tmp_path, REPORT, "Reg_percent") == "0.01"


def test_every_percentage_comes_from_the_last_column(tmp_path):
    assert read(tmp_path, REPORT, "LUT_percent") == "0.01"
    assert read(tmp_path, REPORT, "BRAM_percent") == "0.00"
    assert read(tmp_path, REPORT, "DSP_percent") == "5.00"


def test_a_report_without_the_prohibited_column(tmp_path):
    assert read(tmp_path, OLD_REPORT, "LUT_percent") == "0.19"
    assert read(tmp_path, OLD_REPORT, "Reg_percent") == "0.04"


def test_the_counts_are_unchanged(tmp_path):
    assert read(tmp_path, REPORT, "Reg_count") == "9"
    assert read(tmp_path, REPORT, "LUT_count") == "8"
