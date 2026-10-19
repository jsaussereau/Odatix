"""
Glob patterns in a run selection (E14, D-23): "*" stands for "every one of
them" at any level, and "*", "?" and "[...]" select by pattern.
"""

import pytest

from odatix.workspace import selection


@pytest.fixture
def architectures(tmp_path):
    counter = tmp_path / "counter"
    (counter / "corner").mkdir(parents=True)
    for name in ("04bits", "08bits", "16bits"):
        (counter / (name + ".txt")).write_text("WIDTH = 8", encoding="utf-8")
    for name in ("tt", "ff", "ss"):
        (counter / "corner" / (name + ".txt")).write_text("CORNER", encoding="utf-8")
    for arch in ("adder", "Broken_a", "Broken_b"):
        (tmp_path / arch).mkdir()
    (tmp_path / "adder" / "08bits.txt").write_text("WIDTH = 8", encoding="utf-8")
    (tmp_path / "Broken_a" / "1.txt").write_text("", encoding="utf-8")
    (tmp_path / "Broken_b" / "2.txt").write_text("", encoding="utf-8")
    return tmp_path


def expand(selection_list, root):
    messages = []
    return selection.expand(selection_list, str(root), messages=messages), messages


def test_a_configuration_of_every_architecture(architectures):
    expanded, messages = expand(["*/08bits"], architectures)
    # Only where there is one: the other architectures are not errors.
    assert expanded == ["adder/08bits", "counter/08bits"]
    assert not [m for m in messages if m.level == "error"]


def test_every_configuration_of_some_architectures(architectures):
    expanded, _ = expand(["Broken_*/*"], architectures)
    assert expanded == ["Broken_a/1", "Broken_b/2"]


def test_a_pattern_of_configurations(architectures):
    expanded, _ = expand(["counter/0*"], architectures)
    assert expanded == ["counter/04bits", "counter/08bits"]


def test_a_pattern_of_domain_values(architectures):
    expanded, _ = expand(["counter/16bits + corner/[ft]?"], architectures)
    assert expanded == ["counter/16bits+corner/ff", "counter/16bits+corner/tt"]


def test_a_pattern_matching_no_architecture_is_said(architectures):
    expanded, messages = expand(["Nothing_*/*"], architectures)
    assert expanded == []
    assert [m.level for m in messages] == ["warning"]


def test_a_literal_selection_is_unchanged(architectures):
    expanded, _ = expand(["counter/08bits+corner/tt"], architectures)
    assert expanded == ["counter/08bits+corner/tt"]


def test_an_architecture_without_main_configurations_points_at_its_domains(tmp_path):
    cordic = tmp_path / "cordic"
    (cordic / "width").mkdir(parents=True)
    (cordic / "width" / "8.txt").write_text("", encoding="utf-8")
    expanded, messages = expand(["cordic/*"], tmp_path)
    assert expanded == []
    hints = [hint for message in messages for hint in (message.hints or [])]
    assert any('"cordic + width/*"' in hint for hint in hints)
