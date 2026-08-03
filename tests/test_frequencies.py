"""
Tests for the frequency resolution of an architecture
(odatix.workspace.architectures.resolve_frequencies).

An architecture settings file can say its frequencies three times: for every
target, for one target, and for one configuration of one target. Which one has
the last word is what these tests pin down.
"""

import odatix.lib.hard_settings as hard_settings
from odatix.workspace.architectures import ArchitectureSettings, check_bounds, resolve_frequencies

TARGET = "fpga1"
CONFIG = "08bits"


def settings(global_block=None, target_block=None, configuration_block=None, key="fmax_synthesis"):
    """An architecture settings file saying its frequencies at up to three levels."""
    data = {"top_level_module": "counter"}
    if global_block is not None:
        data[key] = global_block
    target_data = {}
    if target_block is not None:
        target_data[key] = target_block
    if configuration_block is not None:
        target_data[CONFIG] = {key: configuration_block}
    if target_data:
        data[TARGET] = target_data
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

    def test_configuration_overrides_target(self):
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
        data[TARGET] = {"fmax_lower_bound": 42, "fmax_upper_bound": 424}
        resolved = resolve_frequencies(data, target=TARGET, configuration=CONFIG, mode="fmax")
        assert (resolved.lower_bound, resolved.upper_bound) == (42, 424)
        assert resolved.deprecated_bounds

    def test_the_modern_block_wins_over_the_legacy_keys(self):
        data = settings(global_block={"lower_bound": 100, "upper_bound": 900})
        data[TARGET] = {"fmax_lower_bound": 42, "fmax_upper_bound": 424}
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

    def test_list_append_walks_up_every_level(self):
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
# Through the API
######################################

class TestThroughSettings:
    def test_an_architecture_settings_object_answers_the_same(self):
        architecture_settings = ArchitectureSettings.from_dict(
            settings(global_block={"lower_bound": 100, "upper_bound": 900})
        )
        resolved = architecture_settings.frequencies(target=TARGET, configuration=CONFIG)
        assert (resolved.lower_bound, resolved.upper_bound) == (100, 900)

    def test_a_custom_frequency_block_is_read_as_a_whole(self):
        architecture_settings = ArchitectureSettings.from_dict(
            settings(global_block={"lower_bound": 100, "upper_bound": 300, "step": 100}, key="custom_freq_synthesis")
        )
        assert architecture_settings.custom_freq_synthesis.step == 100
        resolved = architecture_settings.frequencies(target=TARGET, configuration=CONFIG, mode="custom_freq")
        assert resolved.frequencies == [100, 200, 300]


class TestCheckBounds:
    def test_a_valid_range_says_nothing(self):
        assert check_bounds(100, 900, 50) == []

    def test_bounds_must_be_integers(self):
        assert len(check_bounds("100", 900, 50)) == 1

    def test_the_upper_bound_must_be_the_highest(self):
        assert len(check_bounds(900, 100, 50)) == 1
