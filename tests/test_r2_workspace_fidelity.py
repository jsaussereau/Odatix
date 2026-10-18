"""2nd pass, workspace_fidelity: saving never damages a hand-written file."""
import difflib
import os
import shutil

import pytest

from odatix.workspace import Workspace
from odatix.workspace.settings import load_settings, save_settings
from odatix.workspace.yaml_io import dump_document, edit_list_text, load_document, merge

HAND = """# head
---
a:     1   # eol a
# Section B
b: Yes

c:
  - x   # eol x
  # - y
  - z
# after c
d: {k: v, m: [1, 2]}
e: |
  line1
f: "quoted"
...
"""


def changed_lines(before, after):
    return [line for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
            if line[:1] in "+-" and not line.startswith(("+++", "---"))]


def test_unchanged_document_is_byte_identical():
    assert dump_document(load_document(HAND), HAND) == HAND


def test_merge_changes_only_values_in_file_style():
    doc = load_document(HAND)
    merge(doc, {"a": 2, "b": False, "c": ["x", "z"], "d": {"k": "w", "m": [1, 2]},
                "e": "line1\n", "f": "q2"})
    out = dump_document(doc, HAND)
    assert changed_lines(HAND, out) == [
        "-a:     1   # eol a", "+a:     2   # eol a", "-b: Yes", "+b: No",
        "-d: {k: v, m: [1, 2]}", "+d: {k: w, m: [1, 2]}", '-f: "quoted"', '+f: "q2"']


def test_removed_item_keeps_following_comments():
    doc = load_document(HAND)
    merge(doc, {"a": 1, "b": True, "c": ["z"], "d": {"k": "v", "m": [1, 2]}, "e": "line1\n", "f": "quoted"})
    assert "# - y" in dump_document(doc, HAND)


def test_list_text_edit_comments_out_and_uncomments():
    out = edit_list_text(HAND, "c", ["x", "y"])
    assert "  - y\n" in out and "  # - z" in out and "# eol x" in out


@pytest.fixture
def ws(tmp_path):
    Workspace.init(str(tmp_path), examples=True)
    return Workspace.open(str(tmp_path))


def _roundtrip(path, action):
    before = open(path).read()
    action()
    return changed_lines(before, open(path).read())


def test_shipped_files_save_identically(ws):
    for mode in ["fmax_synthesis", "custom_freq_synthesis", "pnr", "simulation", "workflow", "analysis"]:
        cfg = ws.jobs[mode]
        assert _roundtrip(cfg.path, lambda: (cfg.settings, cfg.save())) == [], mode
    for kind in ("architectures", "workflows", "simulations"):
        coll = getattr(ws, kind)
        for name in coll.names():
            entry = coll[name]
            assert _roundtrip(entry.settings_path, lambda: (entry.settings, entry.save())) == [], name
    for tool in ("quartus", "librelane", "design_compiler", "vivado"):
        t = ws.targets[tool]
        assert _roundtrip(t.path, lambda: (t.targets, t.save())) == [], tool
    assert _roundtrip(ws.derived_metrics.path, ws.derived_metrics.save) == []


def test_run_file_keeps_catalogue_and_adds_no_default(ws):
    cfg = ws.jobs["custom_freq_synthesis"]
    sel = list(cfg.settings.architectures)
    sel.remove("Example_Counter_verilog/16bits")
    cfg.settings.architectures = sel + ["Example_Counter_sv/08bits"]
    diff = _roundtrip(cfg.path, cfg.save)
    assert diff == ["-  - Example_Counter_verilog/16bits", "+  # - Example_Counter_verilog/16bits",
                    "-  # - Example_Counter_sv/08bits", "+  - Example_Counter_sv/08bits"]


def test_analysis_tools_uncommented_in_place(ws):
    cfg = ws.jobs["analysis"]
    cfg.settings.tools = list(cfg.settings.tools) + ["genus"]
    assert _roundtrip(cfg.path, cfg.save) == ["-  # - genus", "+  - genus"]


def test_target_update_keeps_comments_and_yes(ws):
    diff = _roundtrip(ws.targets["quartus"].path, lambda: ws.targets["quartus"].update(force_single_thread=True))
    assert len(diff) == 2 and diff[1].startswith("+force_single_thread: Yes")


def test_in_place_mutation_is_saved(ws):  # AR-04
    a = ws.architectures["Example_Mult"]
    a.settings.exclusions.append({"when": "$config == 'x'"})
    a.save()
    assert Workspace.open(ws.root).architectures["Example_Mult"].settings.exclusions


def test_nested_block_update_is_saved(ws):  # WF-01
    ws.workflows.entry("cli_profile").update({"progress": {"file": "p2.txt", "regex": "R2"}})
    assert Workspace.open(ws.root).workflows["cli_profile"].settings.progress.file == "p2.txt"


def test_empty_list_key_reads_empty():  # UG-18
    from odatix.dse.settings import DseSettings
    assert DseSettings.from_dict({"campaigns": None}).campaigns == []


def test_tool_editor_save_keeps_hand_written_tool(ws):  # TF-05
    src = os.path.join(os.path.dirname(__file__), "..", "sources", "odatix_eda_tools", "vivado", "tool.yml")
    dest = os.path.join(ws.paths.tools_path, "viv_hand")
    os.makedirs(dest)
    shutil.copy(src, os.path.join(dest, "tool.yml"))
    tool = Workspace.open(ws.root).tools["viv_hand"]
    tool.settings.description = "changed"
    diff = _roundtrip(tool.settings_path, lambda: tool.save(as_overlay=False))
    assert len(diff) == 2 and "changed" in diff[1]
