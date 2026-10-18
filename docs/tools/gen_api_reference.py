#!/usr/bin/env python3
# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""
Generate the Python API reference pages of the documentation.

One page per module, built from the code itself: what a module exports through
its ``__all__``, the signatures of what it exports, its docstrings, the ``#:``
comments documenting attributes, and — for settings classes — the settings they
declare. Nothing is written by hand, so the reference cannot drift away from the
API it documents.

Usage::

    python docs/tools/gen_api_reference.py           # write the pages
    python docs/tools/gen_api_reference.py --check    # fail if they are stale
"""

import argparse
import ast
import inspect
import io
import os
import re
import sys
import textwrap

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.dirname(SCRIPT_DIR)
REPO_DIR = os.path.dirname(DOCS_DIR)
SOURCES_DIR = os.path.join(REPO_DIR, "sources")

PAGES_DIR = os.path.join(DOCS_DIR, "content", "docs", "python_api")

WORKSPACE_PREAMBLE = """
# `odatix.workspace`

> [!IMPORTANT] Requires Odatix 4.0+

Every public name of **`odatix.workspace`**, what it does and what it takes:
opening a workspace, and reading and writing everything it holds. The
[Python API overview](/docs/python_api/) is the place to start; this page is the
one to come back to. What a workspace describes is then run through
[`odatix.run`](/docs/python_api/run/).

The module re-exports everything worth using, so nothing below needs to be
imported from a submodule:

{{< code lang=python filename="imports.py" >}}
from odatix.workspace import Workspace, NotFoundError
{{< /code >}}

> [!NOTE]
> Every path is resolved against the workspace, never against the current
> directory, so an object obtained from a `Workspace` reads and writes the same
> files as the commands run from inside it.
"""

RUN_PREAMBLE = """
# `odatix.run`

> [!IMPORTANT] Requires Odatix 4.0+

Every public name of **`odatix.run`**, what it does and what it takes: checking
what a run needs, preparing it, and starting it. What is run is what a
[`Workspace`](/docs/python_api/workspace/) describes, so that page is the one
that documents the configuration this one executes.

The module re-exports everything worth using, so nothing below needs to be
imported from a submodule:

{{< code lang=python filename="imports.py" >}}
from odatix.run import Run, RunError
{{< /code >}}
"""


def _epilogue(*extra):
    """The "See also" of a page, its own links first."""
    links = list(extra) + [
        "- [Python API overview](/docs/python_api/) — the same API, told as a story.",
        "- [Configuration file reference](/docs/reference/) — every file, every key.",
        "- [Commands reference](/docs/commands/) — every command and its options.",
    ]
    return "\n---\n\n## See also\n\n" + "\n".join(links) + "\n"


#: What each page of the reference documents, and how it introduces itself.
PAGES = (
    {
        "module": "odatix.workspace",
        "file": "workspace.md",
        "title": "odatix.workspace",
        "description": "Every class, method and setting of odatix.workspace: opening a workspace and reading and writing what it holds.",
        "weight": 100,
        "preamble": WORKSPACE_PREAMBLE,
        "epilogue": _epilogue(
            "- [`odatix.run`](/docs/python_api/run/) — running what a workspace describes.",
        ),
    },
    {
        "module": "odatix.run",
        "file": "run.md",
        "title": "odatix.run",
        "description": "Every class, method and setting of odatix.run: checking, preparing and starting a run.",
        "weight": 110,
        "preamble": RUN_PREAMBLE,
        "epilogue": _epilogue(
            "- [`odatix.workspace`](/docs/python_api/workspace/) — the configuration a run executes.",
        ),
    },
)

FRONT_MATTER = """---
title: "{title}"
description: "{description}"
weight: {weight}
---
"""

GENERATED_NOTICE = (
    "<!--\n"
    "  This page is generated from the source code by docs/tools/gen_api_reference.py.\n"
    "  Do not edit it by hand: edit the docstrings of {module}, then run\n"
    "  `make api-docs`.\n"
    "-->\n"
)

#: The mapping methods a class may define, and what they let a user write.
MAPPING_PROTOCOL = (
    ("__len__", "`len(x)`"),
    ("__contains__", '`"name" in x`'),
    ("__getitem__", '`x["name"]`'),
    ("__iter__", "iteration"),
    ("__bool__", "`if x:`"),
)


######################################
# reStructuredText to markdown
######################################


def _role(match):
    """One reST role (:class:`~a.b.C`) as inline code."""
    target = match.group("target").strip()
    if target.startswith("~"):
        target = target[1:].rsplit(".", 1)[-1]
    # ":meth:`Workspace.open`" reads better as a call
    if match.group("role") in ("meth", "func") and not target.endswith(")"):
        target += "()"
    return "`" + target + "`"


def rst_to_markdown(text):
    """A prose docstring as markdown, its reST spellings translated."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n")
    text = re.sub(r":(?P<role>\w+):`(?P<target>[^`]+)`", _role, text)
    text = re.sub(r"``([^`]+)``", r"`\1`", text)
    return text.strip()


def split_blocks(text):
    """
    A docstring as a list of ("text"|"code", content) blocks.

    A paragraph ending with "::" opens an indented literal block, which becomes
    a fenced code block.
    """
    blocks = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() == "":
            index += 1
            continue
        paragraph = []
        while index < len(lines) and lines[index].strip() != "":
            paragraph.append(lines[index])
            index += 1
        text_block = "\n".join(paragraph)
        literal = text_block.endswith("::")
        if literal:
            text_block = text_block[:-2].rstrip()
            if text_block.endswith(":"):
                pass
            elif text_block:
                text_block += ":"
        if text_block:
            blocks.append(("text", text_block))
        if not literal:
            continue
        # Everything indented that follows belongs to the literal block
        code = []
        while index < len(lines):
            line = lines[index]
            if line.strip() == "":
                code.append("")
                index += 1
                continue
            if not line.startswith((" ", "\t")):
                break
            code.append(line)
            index += 1
        code_block = textwrap.dedent("\n".join(code)).strip("\n")
        if code_block:
            blocks.append(("code", code_block))
    return blocks


#: The docstring sections written the Google way, which are rendered as lists
#: rather than as prose.
DOC_SECTIONS = ("Args", "Arguments", "Parameters", "Returns", "Yields", "Raises", "Attributes")

SECTION_RE = re.compile(r"^(?P<title>" + "|".join(DOC_SECTIONS) + r"):\s*$")


def split_sections(text):
    """A docstring as its prose, plus its ("Args", body) sections."""
    body = []
    sections = []
    current = None
    for line in (text or "").split("\n"):
        match = SECTION_RE.match(line.strip()) if not line.startswith((" ", "\t")) else None
        if match:
            current = (match.group("title"), [])
            sections.append(current)
            continue
        if current is None:
            body.append(line)
        elif line.strip() == "" or line.startswith((" ", "\t")):
            current[1].append(line)
        else:
            # Back to prose, at the left margin
            current = None
            body.append(line)
    return "\n".join(body).strip(), [(title, textwrap.dedent("\n".join(lines)).strip()) for title, lines in sections]


def render_section(title, content):
    """One "Args:"-style section as a markdown list."""
    items = []
    for line in content.split("\n"):
        if not line.strip():
            continue
        # A new item names what it documents; anything else continues the
        # previous one, whatever it is indented to
        starts_item = re.match(r"^[\w*]+\s*(\([^)]*\))?\s*:", line.strip())
        if items and (not starts_item or line.startswith((" ", "\t"))):
            items[-1] += " " + line.strip()
        else:
            items.append(line.strip())
    if not items:
        return ""
    lines = ["**{0}:**".format(title), ""]
    for item in items:
        match = re.match(r"^(?P<name>[\w*]+)\s*(?:\((?P<type>[^)]*)\))?\s*:\s*(?P<doc>.*)$", item)
        if match:
            label = "`" + match.group("name") + "`"
            if match.group("type"):
                label += " *({0})*".format(match.group("type"))
            lines.append("- {0} — {1}".format(label, match.group("doc")))
        else:
            lines.append("- {0}".format(item))
    return "\n".join(lines)


def render_docstring(text):
    """A docstring as the markdown of a documentation section."""
    body, sections = split_sections(text)
    out = []
    for kind, content in split_blocks(rst_to_markdown(body)):
        if kind == "code":
            out.append("```python\n" + content + "\n```")
        else:
            out.append(content)
    for title, content in sections:
        rendered = render_section(title, rst_to_markdown(content))
        if rendered:
            out.append(rendered)
    return "\n\n".join(out)


def render_cell(text):
    """A docstring as a single table cell: one line, pipes escaped."""
    if not text:
        return ""
    body, _sections = split_sections(text)
    parts = []
    for kind, content in split_blocks(rst_to_markdown(body)):
        content = " ".join(content.split())
        if kind == "code":
            content = "`" + content + "`"
        parts.append(content)
    for title, content in _sections:
        items = []
        for item in render_section(title, rst_to_markdown(content)).split("\n"):
            if item.startswith("- "):
                items.append(" ".join(item[2:].split()))
        if items:
            parts.append("*{0}:* {1}".format(title, "; ".join(items)))
    return " ".join(parts).replace("|", "\\|")


def summary(text):
    """The first sentence of a docstring, as a table cell."""
    return render_cell(text)


######################################
# Reading the source
######################################


def module_exports(module):
    """
    What a module exports, in `__all__` order, grouped by its own comments.

    The comment lines inside the `__all__` list are what groups the names of the
    page, so the structure of the reference is the one the module itself gives.
    """
    source = inspect.getsource(module)
    tree = ast.parse(source)
    node = None
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    node = statement
    if node is None:
        raise RuntimeError("{0} has no __all__".format(module.__name__))

    lines = source.split("\n")
    groups = []
    current = None
    pending = None
    for line_number in range(node.lineno, node.end_lineno):
        line = lines[line_number].strip()
        if line.startswith("#"):
            pending = line.lstrip("#").strip()
            continue
        match = re.match(r'^["\'](?P<name>\w+)["\'],?$', line)
        if not match:
            continue
        if pending is not None or current is None:
            current = (pending, [])
            groups.append(current)
            pending = None
        current[1].append(match.group("name"))
    return groups


def attribute_docs(obj):
    """
    What the `#:` comments of a class or module document.

    Sphinx spells an attribute's documentation as a comment starting with "#:"
    above it; this reads the same thing, for class bodies and for the attributes
    a constructor sets.
    """
    try:
        source = textwrap.dedent(inspect.getsource(obj))
    except (OSError, TypeError):
        return {}
    docs = {}
    pending = []
    for line in source.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#:"):
            pending.append(stripped[2:].strip())
            continue
        if pending:
            match = re.match(r"^(?:self\.)?(?P<name>[A-Za-z_]\w*)\s*(?::[^=]+)?=", stripped)
            if match and not match.group("name").startswith("_"):
                docs.setdefault(match.group("name"), " ".join(pending))
            pending = []
    return docs


def signature_of(obj, name=None, skip_self=True):
    """The call signature of a callable, as it is written in the reference."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return (name or getattr(obj, "__name__", "?")) + "(...)"
    parameters = list(sig.parameters.values())
    if skip_self and parameters and parameters[0].name in ("self", "cls"):
        parameters = parameters[1:]
    rendered = str(sig.replace(parameters=parameters, return_annotation=inspect.Signature.empty))
    return (name or getattr(obj, "__name__", "?")) + rendered


######################################
# Rendering an object
######################################


def is_settings_class(obj):
    """Whether a class declares settings, i.e. has a `specs()` of `Setting`."""
    return inspect.isclass(obj) and hasattr(obj, "specs") and hasattr(obj, "to_dict")


def member_kind(cls, name):
    """What a member of a class is called in the reference."""
    raw = inspect.getattr_static(cls, name, None)
    if isinstance(raw, classmethod):
        return "classmethod"
    if isinstance(raw, staticmethod):
        return "staticmethod"
    if isinstance(raw, property):
        return "property"
    return ""


def class_members(cls):
    """
    What a class documents: its attributes, its properties and its methods.

    Only what the class itself defines is listed; what it inherits is reached
    through the base class it is said to derive from.
    """
    attributes = []
    methods = []
    docs = attribute_docs(cls)
    init = cls.__dict__.get("__init__")
    if init is not None:
        docs.update(attribute_docs(init))
    for name, value in vars(cls).items():
        if name.startswith("_"):
            continue
        kind = member_kind(cls, name)
        if kind == "property":
            attributes.append((name, kind, inspect.getdoc(value) or docs.get(name, "")))
        elif inspect.isclass(value):
            # A class held as an attribute (the entry class of a collection,
            # the settings class of a job) is what it points at, not a method
            attributes.append((name, "", docs.get(name, "") or "`{0}`".format(value.__name__)))
        elif callable(value) or kind in ("classmethod", "staticmethod"):
            function = value.__func__ if kind in ("classmethod", "staticmethod") else value
            methods.append((name, kind, function))
        else:
            attributes.append((name, "", docs.get(name, "") or _constant_cell(value)))
    # Attributes a constructor sets, documented by a "#:" comment
    documented = set(name for name, _kind, _doc in attributes)
    documented.update(name for name, _kind, _function in methods)
    for name, doc in docs.items():
        if name not in documented:
            attributes.append((name, "", doc))
    return attributes, methods


def _constant_cell(value):
    """A constant's value, when there is nothing else to say about it."""
    text = repr(value)
    if len(text) > 80:
        return ""
    return "`" + text.replace("|", "\\|") + "`"


def render_settings_table(cls):
    """The settings a settings class declares, in file order."""
    try:
        specs = cls.specs()
    except Exception:
        return ""
    if not specs:
        return ""
    lines = ["| Setting | Type | Default | What it is |", "|---|---|---|---|"]
    section = None
    for spec in specs:
        if getattr(spec, "section", None) and spec.section != section:
            section = spec.section
            # A section is also the comment written above its settings in the
            # file (" overwrite existing results"): "** text**" is not bold.
            title = section.strip()
            lines.append("| **{0}** | | | |".format(title[:1].upper() + title[1:]))
        default = spec.make_default() if hasattr(spec, "make_default") else spec.default
        default_cell = "" if default in (None, "", [], {}) else "`{0!r}`".format(default)
        type_name = spec.type.__name__ if inspect.isclass(spec.type) else str(spec.type)
        lines.append(
            "| `{0}` | `{1}` | {2} | {3} |".format(
                spec.name, type_name, default_cell, render_cell(getattr(spec, "doc", "") or "")
            )
        )
    return "\n".join(lines)


def render_class(name, cls, out, level="####"):
    """One class of the reference."""
    out.write("{0} `{1}`\n\n".format(level, name))

    init = cls.__dict__.get("__init__")
    if init is not None:
        out.write("`{0}`\n\n".format(signature_of(init, name)))

    bases = [base.__name__ for base in cls.__bases__ if base is not object]
    if bases:
        out.write("Derives from {0}.\n\n".format(", ".join("`" + base + "`" for base in bases)))

    doc = inspect.getdoc(cls)
    if doc and doc != inspect.getdoc(object):
        rendered = render_docstring(doc)
        if rendered:
            out.write(rendered + "\n\n")

    if issubclass(cls, BaseException):
        return

    protocol = [text for method, text in MAPPING_PROTOCOL if method in vars(cls)]
    if protocol:
        out.write("Supports {0}.\n\n".format(", ".join(protocol)))

    attributes, methods = class_members(cls)
    if attributes:
        out.write("| Attribute | What it is |\n|---|---|\n")
        for attribute_name, kind, attribute_doc in attributes:
            label = "`{0}`".format(attribute_name)
            if kind == "property":
                label += " *(property)*"
            out.write("| {0} | {1} |\n".format(label, render_cell(attribute_doc)))
        out.write("\n")

    if methods:
        out.write("| Method | What it does |\n|---|---|\n")
        for method_name, kind, function in methods:
            label = "`{0}`".format(signature_of(function, method_name))
            if kind in ("classmethod", "staticmethod"):
                label += " *({0})*".format(kind)
            out.write("| {0} | {1} |\n".format(label, summary(inspect.getdoc(function))))
        out.write("\n")

    if is_settings_class(cls):
        table = render_settings_table(cls)
        if table:
            out.write("Declared settings:\n\n" + table + "\n\n")


def render_function(name, function, out, level="####"):
    """One function of the reference."""
    out.write("{0} `{1}`\n\n".format(level, signature_of(function, name, skip_self=False)))
    doc = inspect.getdoc(function)
    if doc:
        out.write(render_docstring(doc) + "\n\n")


def render_constant(name, value, doc, out, level="####"):
    """One constant of the reference."""
    out.write("{0} `{1}`\n\n".format(level, name))
    if doc:
        out.write(render_docstring(doc) + "\n\n")
    text = repr(value)
    if len(text) <= 200:
        out.write("```python\n{0} = {1}\n```\n\n".format(name, text))
    elif isinstance(value, dict):
        out.write("Keys: {0}.\n\n".format(", ".join("`" + str(key) + "`" for key in value)))


def module_constant_docs(module):
    """
    What the `#:` comments of a package document, submodules included.

    A package re-exports the constants its submodules define, and that is where
    their documentation is written, so the submodules it imports from are read
    as well.
    """
    docs = attribute_docs(module)
    tree = ast.parse(inspect.getsource(module))
    for statement in ast.walk(tree):
        if not isinstance(statement, ast.ImportFrom) or not statement.module:
            continue
        submodule = sys.modules.get(statement.module)
        if submodule is None:
            continue
        for name, doc in attribute_docs(submodule).items():
            docs.setdefault(name, doc)
    return docs


def render_module(module_name, out):
    """One module of the reference, group by group."""
    module = __import__(module_name, fromlist=["__all__"])
    doc = inspect.getdoc(module)
    if doc:
        out.write(render_docstring(doc) + "\n\n")

    constants = module_constant_docs(module)
    groups = module_exports(module)
    # A module that groups its exports gets one heading level more than one
    # that does not, so the page never skips a level
    level = "###" if any(group_name for group_name, _names in groups) else "##"
    for group_name, names in groups:
        if group_name:
            out.write("## {0}\n\n".format(group_name))
        for name in names:
            value = getattr(module, name)
            if inspect.isclass(value):
                render_class(name, value, out, level)
            elif inspect.isfunction(value):
                render_function(name, value, out, level)
            else:
                render_constant(name, value, constants.get(name, ""), out, level)


def generate(page):
    """One whole page of the reference, as it should be on disk."""
    out = io.StringIO()
    out.write(FRONT_MATTER.format(**page))
    out.write(GENERATED_NOTICE.format(**page))
    out.write(page["preamble"])
    out.write("\n")
    render_module(page["module"], out)
    out.write(page["epilogue"])
    text = out.getvalue()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip("\n") + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--check", action="store_true", help="fail when a page is not up to date")
    parser.add_argument("--output-dir", default=PAGES_DIR, help="directory of the pages")
    args = parser.parse_args()

    if os.path.isdir(SOURCES_DIR):
        sys.path.insert(0, SOURCES_DIR)

    stale = []
    for page in PAGES:
        path = os.path.join(args.output_dir, page["file"])
        text = generate(page)

        if args.check:
            current = ""
            if os.path.isfile(path):
                with io.open(path, "r", encoding="utf-8") as handle:
                    current = handle.read()
            if current != text:
                stale.append(os.path.relpath(path, REPO_DIR))
            continue

        with io.open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        sys.stderr.write("Wrote {0}\n".format(os.path.relpath(path, REPO_DIR)))

    if stale:
        sys.stderr.write(
            "{0} out of date with the API it documents.\n"
            "Run `make api-docs` and commit the result.\n".format(", ".join(stale))
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
