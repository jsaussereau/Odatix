"""
The GUI says how an action went.

What is covered: the shared feedback line (ui.feedback/error/success), the names
the DSE campaign editor refuses, the renaming of a configuration from its own
save button, and -- statically, over every page -- that each callback answers
with as many values as it declares outputs, which is what adding a feedback
output to a callback most easily breaks.
"""

import ast
import os
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

pytestmark = pytest.mark.gui

dash = pytest.importorskip("dash")

import odatix.gui.ui_components as ui
import odatix.lib.hard_settings as hard_settings


GUI_DIR = os.path.join(os.path.dirname(ui.__file__))


######################################
# Shared feedback line
######################################

class TestFeedbackComponents:
    def test_the_line_is_empty_until_a_callback_fills_it(self):
        line = ui.feedback("some-feedback")
        assert line.id == "some-feedback"
        assert "odx-feedback" in line.className.split()
        assert not getattr(line, "children", None)

    def test_an_error_and_a_success_tell_themselves_apart(self):
        assert ui.error("broken").className == "odx-message error"
        assert ui.success().className == "odx-message success"
        assert ui.success().children == "Saved."

    def test_a_field_error_can_be_left_for_a_callback_to_fill(self):
        placeholder = ui.field_error(id={"type": "x"})
        assert placeholder.id == {"type": "x"}
        assert placeholder.children == ""
        assert "field" in placeholder.className.split()


######################################
# DSE campaign names
######################################

@pytest.fixture(scope="module")
def common():
    import odatix.gui.dse_config.common as common
    return common


class TestCampaignNames:
    def test_a_valid_name_is_accepted(self, common):
        assert common.campaign_name_error("explore_alu", ["other"]) is None

    def test_an_empty_name_is_refused(self, common):
        assert common.campaign_name_error("", []) is not None

    @pytest.mark.parametrize("character", hard_settings.invalid_filename_characters)
    def test_every_character_a_file_name_cannot_hold_is_refused(self, common, character):
        reason = common.campaign_name_error("a{0}b".format(character), [])
        assert reason is not None
        assert ("space" if character == " " else character) in reason

    @pytest.mark.parametrize("name", [".", "..", ".hidden"])
    def test_a_name_the_campaign_list_would_hide_is_refused(self, common, name):
        assert common.campaign_name_error(name, []) is not None

    def test_a_name_taken_by_another_campaign_is_refused(self, common):
        assert "already exists" in common.campaign_name_error("a", ["a", "b"])

    def test_a_campaign_keeps_its_own_name(self, common):
        assert common.campaign_name_error("a", ["a", "b"], original_name="a") is None

    @pytest.mark.parametrize("name", ["a&b", "a#b", "a+b", "a%b", "été"])
    def test_the_link_carries_the_name_unchanged(self, common, name):
        link = common.campaign_link("/dse_campaign", name)
        assert parse_qs(urlparse(link).query)["campaign"] == [name]


######################################
# Saving one configuration
######################################

DOMAIN = "width"


@pytest.fixture(scope="module")
def config_editor():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.config_editor as config_editor
    return config_editor


@pytest.fixture
def architecture(tmp_path, monkeypatch):
    """An architecture whose "width" domain holds a.txt and b.txt."""
    (tmp_path / "odatix.yml").write_text("arch_path: architectures\n", encoding="utf-8")
    domain = tmp_path / "architectures" / "Arch" / DOMAIN
    domain.mkdir(parents=True)
    (tmp_path / "architectures" / "Arch" / hard_settings.param_settings_filename).write_text(
        "use_parameters: false\n"
    )
    (domain / hard_settings.param_settings_filename).write_text("use_parameters: false\n", encoding="utf-8")
    (domain / "a.txt").write_text("A\n", encoding="utf-8")
    (domain / "b.txt").write_text("B\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return domain


def save_config(config_editor, monkeypatch, title, content="A edited\n"):
    """Press the save button of a.txt, its title field holding `title`."""
    trigger = {"type": "save-config", "domain_uuid": "d", "config_uuid": "ca"}
    monkeypatch.setattr(config_editor, "ctx", SimpleNamespace(triggered_id=trigger, triggered_prop_ids={}))
    metadata = [
        {"domain_uuid": "d", "config_uuid": "ca", "config_name": "a.txt", "config_content": "A\n"},
        {"domain_uuid": "d", "config_uuid": "cb", "config_name": "b.txt", "config_content": "B\n"},
    ]
    rows, feedback = config_editor.update_config_cards(
        "?arch=Arch", None,
        "normal", [0], [1, 0], [0, 0], [0, 0], [], "",
        [["card a", "card b"]],
        [title, "b"],
        [content, "B\n"],
        metadata,
        [{"domain_name": DOMAIN, "domain_uuid": "d"}],
        {},
    )
    return rows, feedback


class TestSaveOneConfiguration:
    def test_a_rename_onto_an_existing_name_writes_nothing_and_says_why(
        self, config_editor, architecture, monkeypatch
    ):
        rows, feedback = save_config(config_editor, monkeypatch, "b")
        assert sorted(os.listdir(str(architecture))) == ["_settings.yml", "a.txt", "b.txt"]
        assert (architecture / "a.txt").read_text(encoding="utf-8") == "A\n"
        assert (architecture / "b.txt").read_text(encoding="utf-8") == "B\n"
        assert feedback.className == "odx-message error"
        assert "already exists" in feedback.children
        assert rows == [dash.no_update]

    def test_the_txt_suffix_typed_in_the_title_does_not_hide_a_duplicate(
        self, config_editor, architecture, monkeypatch
    ):
        _, feedback = save_config(config_editor, monkeypatch, "b.txt")
        assert (architecture / "b.txt").read_text(encoding="utf-8") == "B\n"
        assert "already exists" in feedback.children

    def test_a_name_with_a_slash_is_refused_before_anything_moves(
        self, config_editor, architecture, monkeypatch
    ):
        _, feedback = save_config(config_editor, monkeypatch, "../escaped")
        assert not (architecture.parent / "escaped.txt").exists()
        assert (architecture / "a.txt").read_text(encoding="utf-8") == "A\n"
        assert "Unauthorized character" in feedback.children

    def test_a_valid_rename_moves_the_file_and_says_so(self, config_editor, architecture, monkeypatch):
        _, feedback = save_config(config_editor, monkeypatch, "c")
        assert not (architecture / "a.txt").exists()
        assert (architecture / "c.txt").read_text(encoding="utf-8") == "A edited\n"
        assert feedback.className == "odx-message success"


######################################
# Every callback answers all its outputs
######################################

CALLBACK_DECORATORS = {"callback", "page_callback"}


def _decorator_name(decorator):
    function = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(function, ast.Attribute):
        return function.attr
    if isinstance(function, ast.Name):
        return function.id
    return None


def _output_count(decorator):
    """How many outputs the decorator declares, or None when some are spread."""
    count = 0
    for argument in decorator.args:
        if isinstance(argument, ast.Starred):
            return None
        if isinstance(argument, ast.Call) and _decorator_name(argument) == "Output":
            count += 1
        if isinstance(argument, ast.List):
            return None
    return count


def _own_returns(function):
    """The returns of `function` itself, not of the functions it defines."""
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        if isinstance(node, ast.Return):
            yield node
        pending.extend(ast.iter_child_nodes(node))


def _callbacks():
    for directory, _, files in os.walk(GUI_DIR):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call) and _decorator_name(decorator) in CALLBACK_DECORATORS:
                        yield os.path.relpath(path, GUI_DIR), node, _output_count(decorator)


def test_every_callback_returns_as_many_values_as_it_has_outputs():
    mismatches = []
    checked = 0
    for path, function, outputs in _callbacks():
        if not outputs or outputs < 2:
            continue
        checked += 1
        for node in _own_returns(function):
            if isinstance(node.value, ast.Tuple) and len(node.value.elts) != outputs:
                mismatches.append("{0}:{1} {2}() returns {3} values for {4} outputs".format(
                    path, node.lineno, function.name, len(node.value.elts), outputs,
                ))
    assert checked > 50
    assert mismatches == [], "\n".join(mismatches)
