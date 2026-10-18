"""
D-21: the variables of the main domain, without a configuration template, are
virtual parameter domains -- the configuration editor no longer counts them as
configurations, and shows the values of a list in the order it declares them.
"""

import pytest

pytestmark = pytest.mark.gui
pytest.importorskip("dash")

import odatix.gui.config_rules as config_rules
import odatix.lib.hard_settings as hard_settings

VARIABLES = {
    "taps": {"type": "list", "settings": {"list": [8, 16, 32]}},
    "partition": {"type": "list", "settings": {"list": ["none", "cyclic", "complete"]}},
}


def test_the_main_domain_alone_describes_no_configuration():
    settings = {"variables": VARIABLES}
    main = config_rules.implicit_for(hard_settings.main_parameter_domain)
    assert not config_rules.rules_space(settings, implicit=main).generates
    # A named domain of the same variables does describe its configurations.
    assert config_rules.rules_space(settings, implicit=config_rules.implicit_for("Regs")).generates


def test_a_list_keeps_its_declared_order():
    values = config_rules.rules_space({"variables": VARIABLES}, implicit=True).values()
    ordered = config_rules.declared_order(VARIABLES["partition"], values["partition"])
    assert ordered == ["none", "cyclic", "complete"]


def test_other_types_keep_the_generated_order():
    assert config_rules.declared_order({"type": "range"}, [3, 1, 2]) == [3, 1, 2]


def test_the_summary_says_virtual():
    summary = config_rules.virtual_summary(2, 9)
    assert "9 combinations" in repr(summary)
    assert "virtual parameter domains" in repr(summary)


def test_declared_variables_of_the_main_domain_stay_virtual_on_save():
    # Saving the rules of Example_FIR_hls from the GUI wrote "enabled: true",
    # which turned its virtual parameter domains into configurations.
    stored = config_rules.stored_rules_settings(
        {"variables": VARIABLES}, [(1, "", "", [])], VARIABLES, hard_settings.main_parameter_domain,
    )
    assert not (stored.get("configurations") or {}).get("enabled")
    current = config_rules.form_rules_settings(
        [(1, "", "", [])], VARIABLES, hard_settings.main_parameter_domain, stored,
        match=config_rules.configuration_match(stored),
    )
    assert current == stored


def test_a_variable_added_to_a_bare_main_domain_describes_configurations():
    saved = config_rules.rules_settings("", "", {})
    current = config_rules.form_rules_settings(
        [(1, "", "", [])], {"width": VARIABLES["taps"]}, hard_settings.main_parameter_domain, saved,
    )
    assert current["configurations"]["enabled"] is True
