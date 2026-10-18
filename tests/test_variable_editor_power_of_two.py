"""
D-04: the "Power of 2" variable of the GUI takes its bounds as values, as the
settings files and the documentation write them: from 8 to 32 is 8, 16, 32.
"""

import pytest

pytestmark = pytest.mark.gui
pytest.importorskip("dash")

import odatix.gui.variable_editor as ve


def build(**fields):
    values = {name: [""] for name in ve._BUILD_ORDER}
    values["type_value"] = ["power_of_two"]
    for name, value in fields.items():
        values[name] = [value]
    return ve.build_variables_dict(["width"], *[values[name] for name in ve._BUILD_ORDER])


def test_the_card_shows_value_bounds():
    visible = ve.FIELD_VISIBILITY["power_of_two"]
    assert {"from", "to"} <= visible
    assert not ({"from_2_pow", "to_2_pow"} & visible)


def test_the_card_writes_value_bounds():
    variables = build(from_value="8", to_value="32")
    assert variables["width"]["settings"] == {"from": 8, "to": 32}


def test_exponents_open_as_the_values_they_stand_for():
    fields = ve.card_field_values({"type": "power_of_two", "settings": {"from_2^": 3, "to_2^": 5}})
    assert (fields["from_value"], fields["to_value"]) == ("8", "32")


def test_what_the_card_writes_gives_8_16_32():
    variables = build(from_value="8", to_value="32")
    from odatix.lib.config_generator import ConfigGenerator

    generator = ConfigGenerator(data={
        "generate_configurations": True,
        "generate_configurations_settings": {"name": "$width", "template": "$width", "variables": variables},
    }, silent=True)
    _configs, values = generator.generate()
    assert [int(value) for value in values["width"]] == [8, 16, 32]
