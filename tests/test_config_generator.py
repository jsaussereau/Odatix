"""Tests for odatix.lib.config_generator (parameter configuration generation)."""

import pytest

from odatix.lib.config_generator import ConfigGenerator, _safe_sorted

from conftest import make_generation_settings


def generate(variables, template="$X", name="$X", **kwargs):
    data = {
        "generate_configurations": True,
        "generate_configurations_settings": {
            "template": template,
            "name": name,
            "variables": variables,
        },
    }
    gen = ConfigGenerator(data=data, silent=True, **kwargs)
    return gen.generate()


######################################
# Validation / enabling
######################################

class TestValidation:
    def test_valid_settings(self):
        gen = ConfigGenerator(data=make_generation_settings(), silent=True)
        assert gen.valid
        assert gen.enabled

    def test_generation_disabled(self):
        data = make_generation_settings(generate_configurations=False)
        gen = ConfigGenerator(data=data, silent=True)
        assert not gen.enabled
        assert gen.generate() == ({}, {})

    def test_missing_settings_key(self):
        gen = ConfigGenerator(data={"generate_configurations": True}, silent=True)
        assert not gen.valid
        assert gen.generate() == ({}, {})

    def test_template_as_list_is_joined(self):
        data = make_generation_settings()
        data["generate_configurations_settings"]["template"] = ["line1 $WIDTH", "line2"]
        gen = ConfigGenerator(data=data, silent=True)
        assert gen.template == "line1 $WIDTH\nline2"

    def test_invalid_variable_type_returns_empty_tuple(self):
        result = generate({"X": {"type": "bogus"}})
        assert result == ({}, {})


######################################
# Dimension types
######################################

class TestDimensions:
    def test_bool(self):
        configs, values = generate({"X": {"type": "bool"}})
        assert values["X"] == [0, 1]
        assert set(configs) == {"0", "1"}

    def test_range(self):
        _, values = generate({"X": {"type": "range", "settings": {"from": 1, "to": 5}}})
        assert values["X"] == [1, 2, 3, 4, 5]

    def test_range_with_step(self):
        _, values = generate({"X": {"type": "range", "settings": {"from": 0, "to": 10, "step": 5}}})
        assert values["X"] == [0, 5, 10]

    def test_range_step_zero_does_not_crash(self):
        configs, values = generate({"X": {"type": "range", "settings": {"from": 1, "to": 5, "step": 0}}})
        assert configs == {}
        assert values["X"] == []

    def test_range_missing_bound(self):
        configs, _ = generate({"X": {"type": "range", "settings": {"from": 1}}})
        assert configs == {}

    def test_list(self):
        _, values = generate({"X": {"type": "list", "settings": {"list": [3, 1, 2]}}})
        assert sorted(values["X"]) == [1, 2, 3]

    def test_list_of_strings(self):
        configs, _ = generate({"X": {"type": "list", "settings": {"list": ["a", "b"]}}})
        assert set(configs) == {"a", "b"}

    def test_multiples(self):
        _, values = generate({"X": {"type": "multiples", "settings": {"from": 5, "to": 20, "base": 4}}})
        assert values["X"] == [8, 12, 16, 20]

    def test_power_of_two_exponent_bounds(self):
        _, values = generate({"X": {"type": "power_of_two", "settings": {"from_2^": 2, "to_2^": 5}}})
        assert values["X"] == [4, 8, 16, 32]

    def test_power_of_two_value_bounds(self):
        _, values = generate({"X": {"type": "power_of_two", "settings": {"from": 8, "to": 64}}})
        assert values["X"] == [8, 16, 32, 64]

    def test_power_of_two_lower_bound_respected(self):
        # from=5: the first power of two >= 5 is 8, never 4
        _, values = generate({"X": {"type": "power_of_two", "settings": {"from": 5, "to": 16}}})
        assert values["X"] == [8, 16]

    def test_power_of_two_invalid_bounds(self):
        configs, values = generate({"X": {"type": "power_of_two", "settings": {"from": 0, "to": 16}}})
        assert configs == {}

    def test_whitelist(self):
        _, values = generate({"X": {"type": "range", "settings": {"from": 1, "to": 10, "whitelist": [2, 4, 99]}}})
        assert values["X"] == [2, 4]

    def test_blacklist(self):
        _, values = generate({"X": {"type": "range", "settings": {"from": 1, "to": 5, "blacklist": [2, 4]}}})
        assert values["X"] == [1, 3, 5]


######################################
# Set operations
######################################

class TestSetOperations:
    def two_lists(self, op):
        return {
            "A": {"type": "list", "settings": {"list": [1, 2, 3]}},
            "B": {"type": "list", "settings": {"list": [3, 4]}},
            "OP": {"type": op, "settings": {"sources": ["$A", "$B"]}},
        }

    def test_union(self):
        _, values = generate(self.two_lists("union"), template="$OP", name="$OP")
        assert values["OP"] == [1, 2, 3, 4]

    def test_intersection(self):
        _, values = generate(self.two_lists("intersection"), template="$OP", name="$OP")
        assert values["OP"] == [3]

    def test_disjunctive_union(self):
        _, values = generate(self.two_lists("disjunctive_union"), template="$OP", name="$OP")
        assert values["OP"] == [1, 2, 4]

    def test_difference(self):
        _, values = generate(self.two_lists("difference"), template="$OP", name="$OP")
        assert values["OP"] == [1, 2]

    def test_difference_requires_two_sources(self):
        variables = {
            "A": {"type": "list", "settings": {"list": [1]}},
            "OP": {"type": "difference", "settings": {"sources": ["$A"]}},
        }
        _, values = generate(variables, template="$OP", name="$OP")
        assert values["OP"] == []

    def test_sources_are_not_dimensions(self):
        # A and B are consumed by OP: they must not multiply the combos
        configs, _ = generate(self.two_lists("union"), template="$OP", name="$OP")
        assert len(configs) == 4

    def test_missing_sources_key_returns_empty_tuple(self):
        variables = {
            "A": {"type": "list", "settings": {"list": [1]}},
            "OP": {"type": "union", "settings": {}},
        }
        assert generate(variables, template="$OP", name="$OP") == ({}, {})

    def test_sources_still_shown_in_preview_values(self):
        # Regression: sources consumed by a set operation must not disappear
        # from the values preview, even though they are excluded from the
        # combination cross product (see test_sources_are_not_dimensions).
        _, values = generate(self.two_lists("union"), template="$OP", name="$OP")
        assert values["A"] == [1, 2, 3]
        assert values["B"] == [3, 4]
        assert values["OP"] == [1, 2, 3, 4]


######################################
# Computed variables (function / format / conversion)
######################################

class TestComputedVariables:
    def test_function(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [2, 3]}},
            "Y": {"type": "function", "settings": {"op": "$X * 10 + 1"}},
        }
        configs, values = generate(variables, template="$Y", name="x$X")
        assert configs == {"x2": "21", "x3": "31"}
        assert values["Y"] == [21, 31]

    def test_function_with_math(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [8]}},
            "Y": {"type": "function", "settings": {"op": "math.ceil(math.log2($X))"}},
        }
        configs, _ = generate(variables, template="$Y", name="n")
        assert configs == {"n": "3"}

    def test_function_caret_is_exponent(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [3]}},
            "Y": {"type": "function", "settings": {"op": "2 ^ $X"}},
        }
        configs, _ = generate(variables, template="$Y", name="n")
        assert configs == {"n": "8"}

    def test_function_error_does_not_pollute_values(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [1]}},
            "Y": {"type": "function", "settings": {"op": "unknown_var + 1"}},
        }
        _, values = generate(variables, template="$X", name="$X")
        assert values.get("Y", []) == []

    def test_conversion_dec_to_bin(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [5]}},
            "B": {"type": "conversion", "settings": {"from": "dec", "to": "bin", "source": "$X"}},
        }
        configs, _ = generate(variables, template="$B", name="n")
        assert configs == {"n": "101"}

    def test_conversion_dec_to_hex(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [255]}},
            "H": {"type": "conversion", "settings": {"from": "dec", "to": "hex", "source": "$X"}},
        }
        configs, _ = generate(variables, template="$H", name="n")
        assert configs == {"n": "ff"}

    def test_conversion_of_integer_value_does_not_crash(self):
        # bin -> dec on an int dimension value: invalid but must not raise
        variables = {
            "X": {"type": "list", "settings": {"list": [5]}},
            "D": {"type": "conversion", "settings": {"from": "bin", "to": "dec", "source": "$X"}},
        }
        configs, _ = generate(variables, template="$D", name="n")
        assert "n" in configs

    def test_format(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [5]}, "format": "%03d"},
            "L": {"type": "format", "settings": {"source": "value_$X"}},
        }
        configs, _ = generate(variables, template="$L", name="n")
        assert configs == {"n": "value_005"}

    def test_computed_values_are_isolated_per_variable(self):
        variables = {
            "X": {"type": "list", "settings": {"list": [1, 2]}},
            "F": {"type": "function", "settings": {"op": "$X + 100"}},
            "G": {"type": "function", "settings": {"op": "$X + 200"}},
        }
        _, values = generate(variables, template="$X", name="$X")
        assert values["F"] == [101, 102]
        assert values["G"] == [201, 202]


######################################
# Name / template substitution
######################################

class TestSubstitution:
    def test_dollar_and_braced_forms(self):
        variables = {"X": {"type": "list", "settings": {"list": [7]}}}
        configs, _ = generate(variables, template="a=$X b=${X}", name="n${X}")
        assert configs == {"n7": "a=7 b=7"}

    def test_prefix_variable_names_do_not_collide(self):
        variables = {
            "WIDTH": {"type": "list", "settings": {"list": [8]}},
            "WIDTH_OUT": {"type": "list", "settings": {"list": [16]}},
        }
        configs, _ = generate(variables, template="in=$WIDTH out=$WIDTH_OUT", name="w$WIDTH")
        assert configs == {"w8": "in=8 out=16"}

    def test_format_applied_in_name_and_template(self):
        variables = {"X": {"type": "list", "settings": {"list": [5]}, "format": "%02d"}}
        configs, _ = generate(variables, template="v=$X", name="n$X")
        assert configs == {"n05": "v=05"}

    def test_combination_count(self):
        variables = {
            "A": {"type": "list", "settings": {"list": [1, 2]}},
            "B": {"type": "list", "settings": {"list": [1, 2, 3]}},
        }
        configs, _ = generate(variables, template="$A-$B", name="a$A-b$B")
        assert len(configs) == 6


######################################
# Helpers
######################################

class TestHelpers:
    def test_safe_sorted_homogeneous(self):
        assert _safe_sorted({3, 1, 2}) == [1, 2, 3]

    def test_safe_sorted_mixed_types(self):
        result = _safe_sorted({1, "a", 2})
        assert len(result) == 3  # must not raise

    def test_evaluate_expression(self):
        gen = ConfigGenerator(data=make_generation_settings(), silent=True)
        assert gen.evaluate_expression("${A} + $B", {"A": 1, "B": 2}) == 3

    def test_evaluate_expression_failure_returns_none(self):
        gen = ConfigGenerator(data=make_generation_settings(), silent=True)
        assert gen.evaluate_expression("nope +", {}) is None

    def test_format_value_none_format(self):
        gen = ConfigGenerator(data=make_generation_settings(), silent=True)
        assert gen.format_value(3, None) == "3"

    def test_format_value_bad_format_falls_back(self):
        gen = ConfigGenerator(data=make_generation_settings(), silent=True)
        assert gen.format_value("abc", "%d") == "abc"

    def test_apply_conversion_unsupported(self):
        gen = ConfigGenerator(data=make_generation_settings(), silent=True)
        assert gen.apply_conversion("5", "dec", "oct") == "5"

    def test_apply_conversion_none_value(self):
        gen = ConfigGenerator(data=make_generation_settings(), silent=True)
        assert gen.apply_conversion(None, "dec", "bin") is None
