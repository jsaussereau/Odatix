"""Regressions of the second new-user pass, architectures and configurations (AR-xx)."""

import pytest

import odatix.components.replace_params as rp
import odatix.gui.exclusion_editor as editor
from odatix.lib.config_generator import ConfigGenerator


class TestDelimiters(object):
    """AR-01: a delimiter holding a line break survives the one-line field."""

    @pytest.mark.parametrize("saved", ["  // <mul>\n", "  // <mul>\\n", "a\tb", "x\\y", ""])
    def test_round_trip(self, saved):
        typed = rp.escape_delimiter(saved)
        assert "\n" not in typed
        assert rp.delimiter_to_write(typed, saved) == saved

    def test_line_break_is_shown_escaped(self):
        assert rp.escape_delimiter("  // <mul>\n") == "  // <mul>\\n"

    def test_edit_keeps_line_break(self):
        typed = rp.escape_delimiter("  // <mul>\n") .replace("mul", "mux")
        assert rp.delimiter_to_write(typed, "  // <mul>\n") == "  // <mux>\n"
        assert rp.same_delimiter("a\\n", "a\n")


class TestUnionVariables(object):
    """AR-03: a rule set's variables list adds to what it uses."""

    DATA = {
        "configurations": [
            {"name": "M${width}", "template": "W=$width"},
            {"name": "P${width}_${depth}", "template": "W=$width", "variables": ["depth"]},
        ],
        "variables": {
            "width": {"type": "list", "settings": {"list": [8, 16]}},
            "depth": {"type": "range", "settings": {"from": 1, "to": 2}},
        },
    }

    def test_names_resolved(self):
        names = list(ConfigGenerator(data=self.DATA, silent=True).generate()[0])
        assert names == ["M8", "M16", "P8_1", "P8_2", "P16_1", "P16_2"]
        assert not any("$" in name for name in names)

    def test_unresolved_name_is_an_error(self):
        from odatix.workspace.errors import WorkspaceError
        data = {"configurations": {"name": "P${widht}", "template": "x"},
                "variables": {"width": {"type": "list", "settings": {"list": [1]}}}}
        with pytest.raises(WorkspaceError) as error:
            ConfigGenerator(data=data, silent=True).generate()
        assert "${width}" in str(error.value)


class TestExclusionEditor(object):
    """AR-07 / AR-08 / AR-18."""

    def test_default_kind_not_added(self):
        assert editor.normalize_block([{"when": "$a"}]) == [{"when": "$a"}]
        assert editor.normalize_block([{"when": "$a", "kind": "illegal"}]) == [{"when": "$a", "kind": "illegal"}]

    def test_card_title(self):
        assert editor.card_title("x", "$a") == "Leave out: x"
        assert editor.card_title("", "$a == 1") == "Leave out: $a == 1"
        assert editor.card_title("", "") == "Leave out"

    def test_unknown_names(self):
        assert editor.unknown_names(["$Mull == 'x'"], {"Mul", "config"}) == [("Mull", "Mul")]
        assert editor.unknown_names(["$Mul == 'x'"], {"Mul"}) == []

    def test_save_notice(self):
        notice = editor.save_notice([{"id": "s", "when": "$a === 1"}, {"id": "e", "when": ""}])
        assert "s cannot be read" in notice and "e has neither" in notice
        assert editor.save_notice([{"when": "$a == 1"}]) is None

    def test_placeholders_name_the_architecture(self):
        when, require = editor.placeholders([("$Mul", "'Fast'"), ("$Pipe", "'0'")])
        assert when == "$Mul == 'Fast' and $Pipe == '0'" and "$Pipe" in require

    def test_sampling_does_not_list_a_large_space(self):
        class Arch(object):
            name = "A"
            def parameter_domains(self):
                import odatix.lib.hard_settings as hs
                return {hs.main_parameter_domain: [str(i) for i in range(2000)], "D": [str(i) for i in range(2000)]}
            def variable_combinations(self):
                return []
        total, found = editor.sample_combinations(Arch(), 100)
        assert total == 4000000 and len(found) == 100
        assert found[0][0].startswith("A/") and found[0][1].startswith("D/")
