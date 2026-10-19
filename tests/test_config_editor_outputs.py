"""
The callbacks of the configuration editor answer one value per component a
pattern Output matched -- not one per domain of the page.

A domain added a moment ago has a section, but not yet the preview built into it
by a later callback; a row of cards or a pane rebuilt on its own comes back in
another order. A callback sizing its answer on the domains then had Dash reject
it, and the GUI stopped (D-01: "Add new parameter domain" killed the server).
"""

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.gui

dash = pytest.importorskip("dash")
pytest.importorskip("dash_svg")

import odatix.lib.hard_settings as hard_settings

MAIN = hard_settings.main_parameter_domain


@pytest.fixture
def editor():
    dash.Dash(__name__, use_pages=True, pages_folder="")
    import odatix.gui.pages.config_editor as config_editor

    return config_editor


def outputs(*groups):
    """An `outputs_list`: one list of matched ids per Output."""
    lists = [[{"id": {"type": "x", "domain_uuid": uuid}, "property": "p"} for uuid in group] for group in groups]
    return lists[0] if len(lists) == 1 else lists


def inputs_of(type_name, uuids):
    return [{"id": {"type": type_name, "domain_uuid": uuid}, "property": "p", "value": None} for uuid in uuids]


def metadata(*uuids):
    return [{"domain_uuid": uuid, "domain_name": uuid if uuid != MAIN else MAIN} for uuid in uuids]


def use_ctx(editor, monkeypatch, **values):
    values.setdefault("triggered_id", None)
    values.setdefault("triggered_prop_ids", {})
    values.setdefault("inputs_list", [])
    values.setdefault("states_list", [])
    monkeypatch.setattr(editor, "ctx", SimpleNamespace(**values))


class TestPerDomain:
    def test_values_follow_the_matched_components(self, editor, monkeypatch):
        use_ctx(editor, monkeypatch, outputs_list=outputs(["b", MAIN]))
        assert editor.per_domain(["main", "b", "new"], [MAIN, "b", "new"]) == ["b", "main"]

    def test_a_component_without_a_domain_gets_the_default(self, editor, monkeypatch):
        use_ctx(editor, monkeypatch, outputs_list=outputs([MAIN, "c"]))
        assert editor.per_domain(["main"], [MAIN], default="-") == ["main", "-"]

    def test_outside_a_callback_the_order_given_is_kept(self, editor):
        assert editor.per_domain([1, 2], ["a", "b"]) == [1, 2]


class TestPreviewOfANewDomain:
    def test_the_replaced_section_is_only_sent_to_the_panes_that_exist(self, editor, monkeypatch):
        # Two domains on the page, but only the main one has its pane built.
        monkeypatch.setattr(
            editor, "preview_replacements",
            lambda *args: ("arch", "arch", {"arch": object()}, None, ["main text", "new text"]),
        )
        use_ctx(editor, monkeypatch, outputs_list=outputs([MAIN], [MAIN]))
        rest = [[] for _ in editor.config_rules.FIELD_PATTERNS] + [[], metadata(MAIN, "new"), {}, [], []]
        sections, notices = editor.update_preview_replacement("?arch=arch", None, [], [], [], [], [], [], *rest)
        assert sections == ["main text"]
        assert notices == [""]

    def test_the_section_says_when_it_lands_in_a_comment(self, editor, monkeypatch):
        # D-02: the pane read the file once; typing is checked against what it read.
        monkeypatch.setattr(
            editor, "preview_replacements",
            lambda *args: ("arch", "arch", {"arch": object()}, None, ["  localparam X = 0;"]),
        )
        use_ctx(
            editor, monkeypatch, outputs_list=outputs([MAIN], [MAIN]),
            states_list=[[{"id": {"type": "preview-context", "domain_uuid": MAIN}, "property": "data"}]],
        )
        context = {"lines": 2, "comment": "//", "start_delimiter": "  // <regs>", "file": "adder.v"}
        rest = [[] for _ in editor.config_rules.FIELD_PATTERNS] + [[], metadata(MAIN), {}, [], [context]]
        sections, notices = editor.update_preview_replacement("?arch=arch", None, [], [], [], [], [], [], *rest)
        # Padded to the two lines of the block, as a run writes it.
        assert sections == ["  localparam X = 0;\n\n"]
        assert "commented out" in repr(notices[0])

    def test_the_pane_carries_what_the_section_needs(self, editor, tmp_path):
        (tmp_path / "adder.v").write_text("module a;\n  // <regs>\n  localparam X = 1;\n  // </regs>\nendmodule\n", encoding="utf-8")
        pane = editor.preview_pane(
            MAIN, "arch", {"rtl_path": str(tmp_path), "top_level_file": "adder.v"},
            {"use_parameters": True, "param_target_file": "adder.v",
             "start_delimiter": "  // <regs>", "stop_delimiter": "  // </regs>"},
            "  localparam X = 0;",
        )
        pre, store = pane
        assert store.data["comment"] == "//" and store.data["lines"] == 2
        assert "commented out" in repr(pre.children[0])

    def test_no_instance_answers_every_pane(self, editor, monkeypatch):
        monkeypatch.setattr(
            editor, "preview_replacements", lambda *args: ("arch", "", {}, None, ["a", "b"]),
        )
        use_ctx(editor, monkeypatch, outputs_list=outputs([MAIN], []))
        rest = [[] for _ in editor.config_rules.FIELD_PATTERNS] + [[], metadata(MAIN, "new"), {}, [], []]
        sections, notices = editor.update_preview_replacement("?arch=", None, [], [], [], [], [], [], *rest)
        assert sections == [dash.no_update]
        assert notices == []


class TestCardsWithoutAnInstance:
    def test_the_message_goes_to_the_rows_there_are(self, editor, monkeypatch):
        # The page opened on no architecture holds no row at all: a list of one
        # message was rejected, and stopped the GUI.
        monkeypatch.setattr(editor, "get_instance_collection_context", lambda search, settings: ("arch", "", {}))
        use_ctx(editor, monkeypatch, outputs_list=[[], {"id": "config-editor-feedback", "property": "children"}])
        rows, feedback = editor.update_config_cards(
            "", False, "normal", [], [], [], [], [], "", [], [], [], [], [], {},
        )
        assert rows == []
        assert feedback is dash.no_update


class TestCounters:
    def test_counts_are_matched_to_their_domain(self, editor, monkeypatch):
        # The row of cards of "b" was rebuilt, and Dash now lists it first.
        use_ctx(
            editor, monkeypatch,
            outputs_list=outputs(["b", MAIN]),
            inputs_list=[
                {"id": "page-anchor-config_editor", "property": "data", "value": None},
                [],
                inputs_of("config-hidden", ["b", MAIN]),
                inputs_of("config-filter-state", [MAIN, "b"]),
            ],
        )
        config_metadata = [{"domain_uuid": MAIN, "origin": "manual"}]
        counters = editor.update_config_counters(config_metadata, [7, 0], [[], []], metadata(MAIN, "b"))
        assert len(counters) == 2
        b_counter, main_counter = counters
        # "b" has no card but 7 configurations without one; main has one card.
        text = repr(b_counter)
        assert "7" in text
        assert "not shown" in text
        assert "not shown" not in repr(main_counter)


class TestDomainTitles:
    def test_the_main_domain_and_a_new_one_get_their_own_answer(self, editor, monkeypatch, tmp_path):
        instances = SimpleNamespace(entry=lambda name: SimpleNamespace(domains=[]))
        monkeypatch.setattr(editor, "get_instance_collection_context", lambda search, settings: ("arch", "arch", instances))
        # Outputs: save-domain-title (no main), its tooltip, every domain-metadata.
        use_ctx(
            editor, monkeypatch,
            outputs_list=outputs(["new", "b"], ["new", "b"], [MAIN, "b", "new"]),
            inputs_list=[
                {"id": "page-anchor-config_editor", "property": "data", "value": None},
                inputs_of("save-domain-title", ["new", "b"]),
                inputs_of("domain-title-input", ["new", "b"]),
            ],
        )
        classes, tooltips, new_metadata = editor.update_params_title_save_button(
            [0, 0], ["new", "renamed"], metadata(MAIN, "b", "new"), "?arch=arch", {},
        )
        assert len(classes) == len(tooltips) == 2
        assert len(new_metadata) == 3
        assert tooltips == ["Nothing to save", "Save new parameter domain name"]


class TestSaveParameters:
    def test_only_the_saved_domain_is_answered(self, editor, monkeypatch, tmp_path):
        saved = {}
        domain = SimpleNamespace(update=lambda settings: saved.update(settings))
        monkeypatch.setattr(editor, "get_instance_collection_context", lambda search, settings: ("arch", "arch", {}))
        monkeypatch.setattr(editor, "instance_domain", lambda instances, name, domain_name: domain)
        use_ctx(
            editor, monkeypatch,
            triggered_id={"type": "save-params-btn", "domain_uuid": "b"},
            outputs_list=[outputs(["b", MAIN]), [], {"id": "sim-arch-reload", "property": "data"}],
        )
        stores, entries, reload_count = editor.save_config_parameters(
            [0, 1], [[True], [True]], ["top.v", "top.v"], ["// <a>", "// <b>"], ["// </a>", "// </b>"],
            metadata(MAIN, "b"), [{}, {}], [], [], [], [], [], 0, "?arch=arch", {},
        )
        assert stores[1] is dash.no_update
        assert stores[0]["start_delimiter"] == "// <b>"
        assert saved["start_delimiter"] == "// <b>"


class TestNewDomain:
    def test_a_new_domain_starts_without_configurations(self, editor, monkeypatch, tmp_path):
        """D-11: an example variable gave a new domain four configurations."""
        import yaml

        from odatix.workspace.architectures import ArchitectureCollection

        root = tmp_path / "architectures"
        (root / "arch").mkdir(parents=True)
        (root / "arch" / "_settings.yml").write_text(yaml.safe_dump({"rtl_path": "rtl"}), encoding="utf-8")
        instances = ArchitectureCollection(None, str(root))
        monkeypatch.setattr(
            editor, "get_instance_collection_context", lambda search, settings: ("arch", "arch", instances),
        )
        use_ctx(editor, monkeypatch, triggered_id={"action": "add-domain", "type": "button"})
        sections, _initialized, new_uuid = editor.update_param_domains(
            None, "?arch=arch", editor.page_path, [1], [], [], 0, {}, ["main", "add"], metadata(MAIN), "",
        )
        assert new_uuid
        domain = instances["arch"].domains["new_domain1"]
        assert domain.configuration_names() == []
        assert instances["arch"].count_combinations() == 0
