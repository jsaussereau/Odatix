"""
One concept, one word: the words the glossary (docs/content/docs/glossary.md)
says Odatix avoids do not appear in what a user reads -- the labels of the GUI,
the help of the command line, and, for some of them, the documentation.

Only precise expressions are looked for, never a bare word: "design" names a
design point and the sources of an architecture alike ("design_path"), and
forbidding it would forbid correct text.
"""

import argparse
import ast
import os
import re

import pytest

import odatix.gui
import odatix.odatix_main as odatix_main

from conftest import REPO_ROOT

GUI_DIR = os.path.dirname(odatix.gui.__file__)
DOCS_DIR = os.path.join(REPO_ROOT, "docs", "content")

#: Keywords of a Dash component or of a ui helper that hold text a user reads.
LABEL_KEYWORDS = {
    "children", "label", "title", "tooltip", "placeholder", "text", "name",
    "description", "subtitle", "caption", "message", "header", "data-tooltip",
}

#: Calls whose positional arguments are text a user reads.
LABEL_CALLS = {
    "Div", "Span", "P", "H1", "H2", "H3", "H4", "H5", "H6", "Label", "Button", "A",
    "Li", "Strong", "Em", "Small", "B", "I", "Summary", "Th", "Td", "Option",
    "caption", "section", "panel", "page_bar", "page_header", "title_tile",
    "subtitle_div", "empty_state", "error", "success", "field_error", "tag",
    "badge", "stat", "form_field", "form_area", "form_dropdown", "switch_row",
    "inline_switch", "add_card",
}

#: Dictionary keys of the card and page tables the pages render.
LABEL_KEYS = {"name", "title", "description", "label", "tooltip", "placeholder", "help"}


def _literal(node):
    """The text of a string literal, None for anything else (ast.Str before Python 3.8)."""
    if isinstance(node, ast.Constant) and isinstance(getattr(node, "value", None), str):
        return node.value
    legacy = getattr(ast, "Str", None)
    if legacy is not None and isinstance(node, legacy) and isinstance(getattr(node, "s", None), str):
        return node.s
    return None


def _strings(node):
    """The literal text of a node: a string, the literal parts of an f-string, or of a concatenation."""
    if _literal(node) is not None:
        yield _literal(node)
    elif isinstance(node, ast.JoinedStr):
        yield "".join(_literal(part) for part in node.values if _literal(part) is not None)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        for side in (node.left, node.right):
            for text in _strings(side):
                yield text
    elif isinstance(node, (ast.List, ast.Tuple)):
        for element in node.elts:
            for text in _strings(element):
                yield text


def _call_name(call):
    function = call.func
    if isinstance(function, ast.Attribute):
        return function.attr
    if isinstance(function, ast.Name):
        return function.id
    return None


def gui_labels():
    """Every (file, line, text) of the GUI that a user reads."""
    found = []
    for directory, _subdirs, files in os.walk(GUI_DIR):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            with open(path) as f:
                tree = ast.parse(f.read(), path)
            relative = os.path.relpath(path, GUI_DIR)
            for node in ast.walk(tree):
                values = []
                if isinstance(node, ast.Call):
                    if _call_name(node) in LABEL_CALLS:
                        values.extend(node.args)
                    values.extend(keyword.value for keyword in node.keywords if keyword.arg in LABEL_KEYWORDS)
                    # **{"data-tooltip": ...}
                    for keyword in node.keywords:
                        if keyword.arg is None and isinstance(keyword.value, ast.Dict):
                            for key, value in zip(keyword.value.keys, keyword.value.values):
                                if _literal(key) in LABEL_KEYWORDS:
                                    values.append(value)
                elif isinstance(node, ast.Dict):
                    for key, value in zip(node.keys, node.values):
                        if _literal(key) in LABEL_KEYS:
                            values.append(value)
                for value in values:
                    for text in _strings(value):
                        if text.strip():
                            found.append((relative, value.lineno, text))
    return found


def gui_strings():
    """
    Every (file, line, text) of the GUI that is a string, docstrings left out:
    labels kept in tables, messages and tooltips built from pieces are read by
    a user as much as the text of a component.
    """
    found = []
    for directory, _subdirs, files in os.walk(GUI_DIR):
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(directory, name)
            with open(path) as f:
                tree = ast.parse(f.read(), path)
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
                    first = node.body[0]
                    if isinstance(first, ast.Expr) and _literal(first.value) is not None:
                        docstrings.add(id(first.value))
            relative = os.path.relpath(path, GUI_DIR)
            for node in ast.walk(tree):
                text = _literal(node)
                if text is not None and id(node) not in docstrings:
                    # Ids and keys ("use-custom-freq-list") are not read by anyone.
                    if " " in text.strip():
                        found.append((relative, node.lineno, text))
    return found


def cli_help():
    """Every (command, option, text) of the help of "odatix"."""
    odatix_main.ArgParser.parse_arguments(["ls"])
    found = []

    def walk(parser, path):
        if parser.description:
            found.append((path, "", parser.description))
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for choice in action._choices_actions:
                    found.append((path, choice.dest, choice.help or ""))
                for name, subparser in action.choices.items():
                    walk(subparser, path + " " + name)
            elif action.help and action.help != argparse.SUPPRESS:
                found.append((path, "/".join(action.option_strings), action.help))

    walk(odatix_main.ArgParser.parser, "odatix")
    return found


def docs_text():
    """Every (file, line, text) of the documentation, code blocks included."""
    found = []
    for directory, _subdirs, files in os.walk(DOCS_DIR):
        for name in files:
            if name.endswith(".md"):
                path = os.path.join(directory, name)
                with open(path) as f:
                    for number, line in enumerate(f, 1):
                        found.append((os.path.relpath(path, DOCS_DIR), number, line))
    return found


#: Expressions to avoid, and where. The glossary says why.
AVOIDED = [
    # "Tool": an EDA tool, never "eda tool" in a label.
    (re.compile(r"\beda tools?\b", re.IGNORECASE), ("gui", "cli")),
    # "Fixed-frequency synthesis", never "custom freq" or "custom synthesis" in a label.
    (re.compile(r"\bcustom[ -](freq|synth)", re.IGNORECASE), ("gui", "cli")),
    # ... nor "custom frequency synthesis" / "custom-frequency synthesis" in the
    # documentation (the key "custom_freq_synthesis" keeps its name: not matched).
    (re.compile(r"\bcustom[ -]frequency\b", re.IGNORECASE), ("docs",)),
    # A search evaluates design points.
    (re.compile(r"\bhow many designs\b", re.IGNORECASE), ("gui", "cli", "docs")),
    # A session, never a "daemon session".
    (re.compile(r"\bdaemon sessions?\b", re.IGNORECASE), ("gui", "cli")),
]


def _sources(where):
    if where == "gui":
        return [("gui/" + path + ":" + str(line), text) for path, line, text in gui_strings()]
    if where == "cli":
        return [(command + " " + option, text) for command, option, text in cli_help()]
    # The glossary names the words it avoids, on purpose.
    return [
        ("docs/" + path + ":" + str(line), text)
        for path, line, text in docs_text()
        if path != os.path.join("docs", "glossary.md")
    ]


@pytest.mark.parametrize("pattern, places", AVOIDED, ids=[pattern.pattern for pattern, _places in AVOIDED])
def test_an_avoided_expression_appears_nowhere_a_user_reads(pattern, places):
    hits = []
    for where in places:
        hits.extend(place + ": " + text.strip() for place, text in _sources(where) if pattern.search(text))
    assert hits == [], "\n".join(hits)


def test_the_labels_are_found():
    # The extraction is what the tests above rely on: if it finds nothing, they
    # pass for nothing.
    labels = [text for _path, _line, text in gui_labels()]
    assert len(labels) > 500
    assert "Default tool" in labels
    assert len(cli_help()) > 200


def test_the_glossary_is_published_and_linked():
    with open(os.path.join(DOCS_DIR, "docs", "glossary.md")) as f:
        glossary = f.read()
    for term in ("Architecture", "Configuration", "Design point", "Target", "Tool", "Job", "Session", "Campaign"):
        assert "**" + term + "**" in glossary
    with open(os.path.join(DOCS_DIR, "docs", "getting-started.md")) as f:
        assert "/docs/glossary/" in f.read()
    assert odatix_main.GLOSSARY_URL.endswith("/docs/glossary/")


######################################
# Sentence case
######################################

#: Words that keep their capital wherever they are: names and acronyms.
PROPER_NOUNS = set(
    "Odatix Fmax RTL EDA Vivado Explorer GUI DSE MHz HLS CSV YAML JSON XML Python "
    "Verilator Quartus Genus Innovus LibreLane OpenLane ICC2 Pareto CPU ID UUID "
    "Dhrystone Chisel VHDL Verilog SystemVerilog TCL Tcl DC NXT Monte Carlo".split()
)

#: Not labels but examples of what a user types (metric names, patterns).
EXAMPLE_VALUES = {"Cycles / Frequency", "Voltage, Corner", "MEM: Cache", "AsteRISC/*, Ibex/*"}


def title_cased_words(text):
    """The words of a label capitalized for no reason: not the first of a sentence, not a name."""
    found = []
    for segment in re.split(r"\. |: |\? | - |! ", text):
        words = [word for word in re.split(r"[\s/]+", segment) if word.strip()]
        for word in words[1:]:
            core = re.sub(r"[^A-Za-z0-9&']", "", word)
            if core and core[0].isupper() and core[1:].islower() and core not in PROPER_NOUNS:
                found.append(core)
    return found


def test_the_labels_of_the_gui_are_in_sentence_case():
    offenders = []
    for path, line, text in gui_labels():
        label = text.strip()
        if len(label) > 60 or "\n" in label or label in EXAMPLE_VALUES or label.startswith("+ "):
            continue
        if title_cased_words(label):
            offenders.append("gui/{0}:{1}: {2}".format(path, line, label))
    assert offenders == [], "\n".join(offenders)
