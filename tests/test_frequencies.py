"""
Tests for the frequency resolution of an architecture
(odatix.workspace.architectures.resolve_frequencies).

An architecture settings file can say its frequencies for every job it produces,
and again in each rule of its "overrides" section that selects only some of
them. Which one has the last word is what these tests pin down.
"""

import odatix.lib.hard_settings as hard_settings
from odatix.workspace.architectures import ArchitectureSettings, check_bounds, resolve_frequencies

TARGET = "fpga1"
CONFIG = "08bits"


def settings(global_block=None, target_block=None, configuration_block=None, key="fmax_synthesis"):
    """
    An architecture settings file saying its frequencies at up to three levels:
    for every job, for the jobs of one target, and for the jobs running one
    configuration on that target.
    """
    data = {"top_level_module": "counter"}
    if global_block is not None:
        data[key] = global_block
    rules = []
    if target_block is not None:
        rules.append({"targets": TARGET, key: target_block})
    if configuration_block is not None:
        rules.append({"targets": TARGET, "configurations": CONFIG, key: configuration_block})
    if rules:
        data["overrides"] = rules
    return data


def fmax(**kwargs):
    return resolve_frequencies(settings(**kwargs), target=TARGET, configuration=CONFIG, mode="fmax")


def custom(fallback=None, **kwargs):
    kwargs["key"] = "custom_freq_synthesis"
    return resolve_frequencies(
        settings(**kwargs), target=TARGET, configuration=CONFIG, mode="custom_freq", fallback=fallback
    )


######################################
# Fmax bounds
######################################

class TestFmaxBounds:
    def test_defaults_when_the_file_says_nothing(self):
        resolved = fmax()
        assert resolved.lower_bound == hard_settings.default_fmax_lower_bound
        assert resolved.upper_bound == hard_settings.default_fmax_upper_bound
        assert not resolved.deprecated_bounds

    def test_global_bounds(self):
        resolved = fmax(global_block={"lower_bound": 100, "upper_bound": 900})
        assert (resolved.lower_bound, resolved.upper_bound) == (100, 900)

    def test_target_overrides_global(self):
        resolved = fmax(
            global_block={"lower_bound": 100, "upper_bound": 900},
            target_block={"lower_bound": 250, "upper_bound": 800},
        )
        assert (resolved.lower_bound, resolved.upper_bound) == (250, 800)

    def test_a_later_rule_overrides_an_earlier_one(self):
        resolved = fmax(
            global_block={"lower_bound": 100, "upper_bound": 900},
            target_block={"lower_bound": 250, "upper_bound": 800},
            configuration_block={"lower_bound": 280, "upper_bound": 950},
        )
        assert (resolved.lower_bound, resolved.upper_bound) == (280, 950)

    def test_a_level_only_overrides_what_it_says(self):
        resolved = fmax(
            global_block={"lower_bound": 100, "upper_bound": 900},
            configuration_block={"lower_bound": 280},
        )
        assert (resolved.lower_bound, resolved.upper_bound) == (280, 900)

    def test_legacy_keys_are_still_read_and_reported(self):
        data = settings()
        data["overrides"] = [{"targets": TARGET, "fmax_lower_bound": 42, "fmax_upper_bound": 424}]
        resolved = resolve_frequencies(data, target=TARGET, configuration=CONFIG, mode="fmax")
        assert (resolved.lower_bound, resolved.upper_bound) == (42, 424)
        assert resolved.deprecated_bounds

    def test_the_modern_block_wins_over_the_legacy_keys(self):
        data = settings(global_block={"lower_bound": 100, "upper_bound": 900})
        data["overrides"] = [{"targets": TARGET, "fmax_lower_bound": 42, "fmax_upper_bound": 424}]
        resolved = resolve_frequencies(data, target=TARGET, configuration=CONFIG, mode="fmax")
        assert (resolved.lower_bound, resolved.upper_bound) == (100, 900)
        assert resolved.deprecated_bounds


######################################
# Custom frequencies
######################################

class TestCustomFrequencies:
    def test_fallback_when_the_file_says_nothing(self):
        assert custom().frequencies == list(hard_settings.default_custom_freq_list)

    def test_given_fallback_wins_over_the_odatix_default(self):
        assert custom(fallback=[11, 22]).frequencies == [11, 22]

    def test_list(self):
        assert custom(global_block={"list": [50, 100]}).frequencies == [50, 100]

    def test_range(self):
        resolved = custom(global_block={"lower_bound": 100, "upper_bound": 300, "step": 100})
        assert resolved.frequencies == [100, 200, 300]

    def test_range_and_list_are_both_run(self):
        resolved = custom(global_block={"lower_bound": 100, "upper_bound": 300, "step": 100, "list": [25]})
        assert resolved.frequencies == [25, 100, 200, 300]

    def test_a_step_of_no_switches_the_range_off(self):
        resolved = custom(global_block={"lower_bound": 100, "upper_bound": 300, "step": False, "list": [25]})
        assert resolved.frequencies == [25]

    def test_an_invalid_range_is_reported(self):
        resolved = custom(global_block={"lower_bound": 300, "upper_bound": 100, "step": 50})
        assert [message.level for message in resolved.messages] == ["error"]

    def test_the_most_specific_list_is_the_whole_set(self):
        resolved = custom(global_block={"list": [50, 100]}, configuration_block={"list": [25]})
        assert resolved.frequencies == [25]

    def test_list_append_adds_to_the_level_above(self):
        resolved = custom(
            global_block={"list": [50, 100]},
            configuration_block={"list": [25], "list_append": True},
        )
        assert resolved.frequencies == [25, 50, 100]

    def test_list_append_walks_up_every_rule(self):
        resolved = custom(
            global_block={"list": [200]},
            target_block={"list": [100], "list_append": True},
            configuration_block={"list": [25], "list_append": True},
        )
        assert resolved.frequencies == [25, 100, 200]

    def test_append_stops_where_it_is_not_asked_for(self):
        resolved = custom(
            global_block={"list": [200]},
            target_block={"list": [100]},
            configuration_block={"list": [25], "list_append": True},
        )
        assert resolved.frequencies == [25, 100]


######################################
# Which jobs a rule applies to
######################################

class TestSelectors:
    def test_a_rule_naming_no_selector_applies_to_every_job(self):
        data = {"overrides": [{"fmax_synthesis": {"lower_bound": 111, "upper_bound": 222}}]}
        resolved = resolve_frequencies(data, target="whatever", configuration="whatever", mode="fmax")
        assert (resolved.lower_bound, resolved.upper_bound) == (111, 222)

    def test_a_rule_of_another_target_is_not_read(self):
        data = {"overrides": [{"targets": "other", "fmax_synthesis": {"lower_bound": 111}}]}
        resolved = resolve_frequencies(data, target=TARGET, configuration=CONFIG, mode="fmax")
        assert resolved.lower_bound == hard_settings.default_fmax_lower_bound

    def test_a_pattern_selects_the_targets_it_matches(self):
        data = {"overrides": [{"targets": "fpga*", "fmax_synthesis": {"lower_bound": 111}}]}
        assert resolve_frequencies(data, target="fpga1", mode="fmax").lower_bound == 111
        assert resolve_frequencies(data, target="asic1", mode="fmax").lower_bound != 111

    def test_a_tool_covers_all_of_its_flows(self):
        data = {"overrides": [{"tools": "vivado", "fmax_synthesis": {"lower_bound": 111}}]}
        assert resolve_frequencies(data, tool="vivado", flow="power_opt", mode="fmax").lower_bound == 111
        assert resolve_frequencies(data, tool="genus", flow="power_opt", mode="fmax").lower_bound != 111

    def test_a_flow_is_named_after_its_tool(self):
        data = {"overrides": [{"tools": "vivado@power_opt", "fmax_synthesis": {"lower_bound": 111}}]}
        assert resolve_frequencies(data, tool="vivado", flow="power_opt", mode="fmax").lower_bound == 111
        assert resolve_frequencies(data, tool="vivado", flow="standard", mode="fmax").lower_bound != 111

    def test_every_selector_of_a_rule_has_to_match(self):
        data = {"overrides": [{
            "tools": ["vivado", "genus"],
            "targets": "fpga*",
            "configurations": "*bits",
            "fmax_synthesis": {"lower_bound": 111},
        }]}
        matching = dict(tool="genus", target="fpga1", configuration="08bits", mode="fmax")
        assert resolve_frequencies(data, **matching).lower_bound == 111
        assert resolve_frequencies(data, **dict(matching, configuration="fast")).lower_bound != 111

    def test_a_star_restricts_nothing(self):
        data = {"overrides": [{"tools": "*", "targets": "*", "fmax_synthesis": {"lower_bound": 111}}]}
        assert resolve_frequencies(data, target="anything", mode="fmax").lower_bound == 111

    def test_an_invalid_section_is_reported_rather_than_raised(self):
        resolved = resolve_frequencies({"overrides": "not a list"}, target=TARGET, mode="fmax")
        assert [message.level for message in resolved.messages] == ["error"]
        assert resolved.lower_bound == hard_settings.default_fmax_lower_bound


######################################
# Through the API
######################################

class TestThroughSettings:
    def test_an_architecture_settings_object_answers_the_same(self):
        architecture_settings = ArchitectureSettings.from_dict(
            settings(global_block={"lower_bound": 100, "upper_bound": 900})
        )
        resolved = architecture_settings.frequencies(target=TARGET, configuration=CONFIG)
        assert (resolved.lower_bound, resolved.upper_bound) == (100, 900)

    def test_legacy_bounds_survive_the_settings_object(self):
        # to_dict() writes an empty fmax_synthesis block, which must not hide them
        architecture_settings = ArchitectureSettings.from_dict({"fmax_lower_bound": 100, "fmax_upper_bound": 900})
        resolved = architecture_settings.frequencies()
        assert (resolved.lower_bound, resolved.upper_bound) == (100, 900)
        assert resolved.messages == []

    def test_a_settings_object_and_a_run_agree_on_legacy_bounds(self):
        data = {"top_level_module": "counter", "fmax_lower_bound": 100, "fmax_upper_bound": 900}
        through_settings = ArchitectureSettings.from_dict(data).frequencies(target=TARGET, configuration=CONFIG)
        raw = resolve_frequencies(data, target=TARGET, configuration=CONFIG)
        assert (through_settings.lower_bound, through_settings.upper_bound) == (raw.lower_bound, raw.upper_bound)

    def test_legacy_global_bounds_and_a_modern_block_for_a_target(self):
        data = {
            "top_level_module": "counter", "fmax_lower_bound": 100, "fmax_upper_bound": 900,
            "overrides": [{"targets": TARGET, "fmax_synthesis": {"lower_bound": 250}}],
        }
        resolved = ArchitectureSettings.from_dict(data).frequencies(target=TARGET, configuration=CONFIG)
        assert (resolved.lower_bound, resolved.upper_bound) == (250, 900)
        other_target = ArchitectureSettings.from_dict(data).frequencies(target="other", configuration=CONFIG)
        assert (other_target.lower_bound, other_target.upper_bound) == (100, 900)

    def test_a_custom_frequency_block_is_read_as_a_whole(self):
        architecture_settings = ArchitectureSettings.from_dict(
            settings(global_block={"lower_bound": 100, "upper_bound": 300, "step": 100}, key="custom_freq_synthesis")
        )
        assert architecture_settings.fixed_freq_synthesis.step == 100
        resolved = architecture_settings.frequencies(target=TARGET, configuration=CONFIG, mode="custom_freq")
        assert resolved.frequencies == [100, 200, 300]


class TestCheckBounds:
    def test_a_valid_range_says_nothing(self):
        assert check_bounds(100, 900, 50) == []

    def test_bounds_must_be_integers(self):
        assert len(check_bounds("100", 900, 50)) == 1

    def test_the_upper_bound_must_be_the_highest(self):
        assert len(check_bounds(900, 100, 50)) == 1


class TestFormerFixedFrequencyKey:
    """"fixed_freq_synthesis" used to be called "custom_freq_synthesis": both are read."""

    def test_the_former_key_is_read_at_the_root_and_in_a_rule(self):
        data = {
            "top_level_module": "counter",
            "custom_freq_synthesis": {"list": [50]},
            "overrides": [{"targets": TARGET, "custom_freq_synthesis": {"list": [70], "list_append": True}}],
        }
        resolved = resolve_frequencies(data, target=TARGET, configuration=CONFIG, mode="custom_freq")
        assert sorted(resolved.frequencies) == [50, 70]

    def test_a_settings_object_moves_it_to_the_current_key(self):
        settings = ArchitectureSettings.from_dict({"custom_freq_synthesis": {"list": [50, 100]}})
        assert settings.to_dict()["fixed_freq_synthesis"]["list"] == [50, 100]
        assert "custom_freq_synthesis" not in settings.to_dict()

    def test_the_current_key_wins_over_the_former(self):
        data = {"custom_freq_synthesis": {"list": [1]}, "fixed_freq_synthesis": {"list": [2]}}
        assert resolve_frequencies(data, mode="custom_freq").frequencies == [2]
