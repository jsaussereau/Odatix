"""
D-14: the Architecture editor edits the "exclusions" block of an architecture,
and tells what each rule leaves out before it is saved.
"""

import pytest
import yaml

from odatix.workspace.architectures import ArchitectureCollection

pytestmark = pytest.mark.gui
dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")


@pytest.fixture
def editor():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.exclusion_editor as exclusion_editor
    return exclusion_editor


def make(tmp_path, exclusions=None):
    """Three widths crossed with a two-configuration domain: six combinations."""
    root = tmp_path / "architectures"
    arch = root / "adder"
    (arch / "Regs").mkdir(parents=True)
    settings = {
        "rtl_path": "rtl",
        "use_parameters": True,
        "start_delimiter": "// <w>",
        "stop_delimiter": "// </w>",
        "configurations": {"name": "${width}bits", "template": "\n  localparam WIDTH = ${width};\n"},
        "variables": {"width": {"type": "list", "settings": {"list": [8, 16, 32]}}},
    }
    if exclusions:
        settings["exclusions"] = exclusions
    (arch / "_settings.yml").write_text(yaml.safe_dump(settings), encoding="utf-8")
    (arch / "Regs" / "_settings.yml").write_text(yaml.safe_dump({
        "use_parameters": True, "start_delimiter": "// <r>", "stop_delimiter": "// </r>",
    }))
    (arch / "Regs" / "On.txt").write_text("\n  localparam R = 1;\n", encoding="utf-8")
    (arch / "Regs" / "Off.txt").write_text("\n  localparam R = 0;\n", encoding="utf-8")
    return ArchitectureCollection(None, str(root))["adder"]


def cards_of(editor, declared):
    rules, _extra = editor.block_rules(declared)
    return [editor.card_fields(rule) for rule in rules]


class TestRoundTrip:
    def test_a_rule_is_written_back_as_it_was_read(self, editor):
        rule = {"id": "no-32", "when": "$width == 32", "require": "$Regs == 'On'", "kind": "duplicate",
                "message": "why"}
        assert editor.build_block(cards_of(editor, [rule])) == [rule]

    def test_a_bare_expression_stays_one_until_it_is_edited(self, editor):
        cards = cards_of(editor, ["$width < 32"])
        assert cards[0]["when"] == "not ($width < 32)"
        assert editor.build_block(cards) == ["$width < 32"]

        cards[0]["message"] = "too wide"
        assert editor.build_block(cards) == [
            {"when": "not ($width < 32)", "message": "too wide"}
        ]

    def test_what_the_card_does_not_show_is_kept(self, editor):
        block = editor.normalize_block([{"expr": "$b == 1", "custom": 3}])
        assert block == [{"when": "$b == 1", "custom": 3}]

    def test_a_mapping_keeps_what_it_says_besides_its_rules(self, editor):
        declared = {"apply": ["illegal", "dominated"], "ignore": ["x"], "rules": [{"when": "$a"}]}
        assert editor.normalize_block(declared) == {
            "apply": ["illegal", "dominated"], "ignore": ["x"], "rules": [{"when": "$a"}],
        }

    def test_a_card_saying_nothing_is_not_written(self, editor):
        assert editor.build_block([{"kind": "illegal", "id": "draft"}]) == []

    def test_the_values_of_the_page_make_the_cards(self, editor):
        cards = editor.cards_from_values(["a", ""], ["illegal", "duplicate"], ["$x", "$y"], ["", "$z"],
                                         ["", ""], [{}, {}])
        assert editor.build_block(cards) == [
            {"id": "a", "when": "$x"},
            {"when": "$y", "require": "$z", "kind": "duplicate"},
        ]


class TestCheck:
    def test_each_rule_says_what_it_leaves_out(self, editor, tmp_path):
        arch = make(tmp_path)
        cards = cards_of(editor, [
            {"id": "no-regs-32", "when": "$Regs == 'Off' and $width == 32"},
            {"when": "$width < 16", "kind": "dominated"},
        ])
        result = editor.check_rules(arch, cards)
        assert result["total"] == result["checked"] == 6
        legal, dominated = result["slots"]
        assert (legal.count, legal.example, legal.applied) == (1, "adder/32bits+Regs/Off", True)
        # Found, but a dominated rule is not applied unless a campaign asks.
        assert (dominated.count, dominated.applied) == (2, False)
        assert result["left_out"] == 1

    def test_a_rule_reading_an_unknown_name_leaves_nothing_out(self, editor, tmp_path):
        result = editor.check_rules(make(tmp_path), cards_of(editor, [{"when": "$Regz == 'Off'"}]))
        assert result["slots"][0].count == 0
        assert "(did you mean" in str(editor.slot_status(result["slots"][0], result["checked"]))

    def test_a_rule_that_cannot_be_read_is_said_so(self, editor, tmp_path):
        result = editor.check_rules(make(tmp_path), cards_of(editor, [{"when": "$width >"}]))
        assert "SyntaxError" in result["slots"][0].error

    def test_the_rules_of_the_page_are_checked_not_the_saved_ones(self, editor, tmp_path):
        arch = make(tmp_path, exclusions=[{"when": "$width == 8"}])
        result = editor.check_rules(arch, cards_of(editor, [{"when": "$width == 16"}]))
        assert result["slots"][0].example.startswith("adder/16bits")

    def test_a_large_space_is_checked_on_a_spread(self, editor, tmp_path):
        arch = make(tmp_path)
        result = editor.check_rules(arch, cards_of(editor, [{"when": "$width == 32"}]), limit=3)
        assert result["total"] == 6 and result["checked"] == 3


class TestEditor:
    def test_the_form_shows_the_rules_and_saves_them(self, example_workspace):
        dash.Dash(__name__, use_pages=True, pages_folder="")
        import odatix.gui.pages.architecture_editor as page
        from odatix.gui.utils import get_workspace

        architectures = get_workspace({}).architectures
        arch = architectures.get("Example_Counter_sv")
        arch.settings["exclusions"] = ["$x > 0"]
        arch.save()

        _title, form, settings, _name = page.init_form("?arch=Example_Counter_sv", page.page_path, {})
        assert settings["exclusions"] == ["$x > 0"]
        assert "arch-add-exclusion-card" in str(form)

        page.apply_form_settings(arch, {"exclusions": [{"when": "$y", "kind": "duplicate"}]})
        reread = get_workspace({}).architectures.get("Example_Counter_sv")
        assert reread.settings.to_dict()["exclusions"] == [{"when": "$y", "kind": "duplicate"}]

        # Emptied, the block leaves the file.
        page.apply_form_settings(reread, {"exclusions": []})
        with open(reread.settings_path, encoding="utf-8") as handle:
            assert "exclusions" not in handle.read()


def test_the_check_lists_what_a_rule_can_read(editor, tmp_path):
    result = editor.check_rules(make(tmp_path), [])
    names = dict(result["names"].lines())
    # Written the way an expression compares them: a configuration name is a
    # string, a variable a number.
    assert names["$Regs"] == "'Off', 'On'"
    assert names["$width"] == "8, 16, 32"
    assert "$config" in names and "$main" not in names
