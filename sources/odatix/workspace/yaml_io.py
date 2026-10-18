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
Reading and writing of the YAML files of a workspace.

Two ways of reading are needed, and they are not interchangeable:

* :func:`read_yaml` parses a file into plain Python values (comments and
  formatting are lost). This is what the API hands to callers.
* :func:`read_document` parses it into ruamel round-trip objects, keeping
  comments, key order and formatting. This is what a save starts from, so that
  writing one setting back does not throw away the rest of the user's file.

Everything the API writes goes through :func:`write_document` (or
:func:`write_text` for what is not YAML), so a workspace file never ends up
half-written by one helper and half by another -- nor half-written at all: a
file is replaced in one go, never truncated then filled.

Saving a file somebody wrote by hand must change what was changed and nothing
else. Three layers see to it, and every writer of the API goes through them:

* :func:`merge` changes a document read by :func:`read_document` value by
  value: what did not change keeps its node -- its quoting, its ``Yes``, its
  ``|`` block, its comments --, a changed value is written in the style of the
  one it replaces, and a new key goes next to the key it follows rather than at
  the end of the file.
* :func:`edit_list_text` edits a list of names in the text itself, commenting
  out what is taken out of it: this is how a run settings file keeps the
  catalogue of commented-out entries the tutorials ask to uncomment, and how a
  target file says a target is disabled.
* :func:`dump_document` lays the text out like the file it replaces, and only
  the lines that actually changed take the layout ruamel gives them: a file
  loaded and saved without a change comes out byte for byte as it went in.
"""

import copy
import difflib
import io
import os
import re
import tempfile

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import CommentMark
from ruamel.yaml.scalarstring import (
    DoubleQuotedScalarString,
    FoldedScalarString,
    LiteralScalarString,
    SingleQuotedScalarString,
)
from ruamel.yaml.tokens import CommentToken

import odatix.lib.yaml_loader as yaml_loader

__all__ = [
    "read_yaml",
    "read_mapping",
    "read_document",
    "load_document",
    "write_document",
    "write_text",
    "dump_document",
    "merge",
    "set_key",
    "same_value",
    "insert_key",
    "remove_key",
    "edit_list_text",
    "new_document",
    "flow_seq",
    "block_seq",
    "parse_bool",
    "parse_int",
    "parse_int_list",
    "yes_no",
    "file_header",
]


######################################
# Reading
######################################

def read_yaml(path, default=None):
    """
    Read a YAML file into plain Python values.

    A missing, empty or unreadable file yields a copy of `default` (an empty
    dict when not given): a workspace file that does not exist yet is a normal
    state, not an error.
    """
    if default is None:
        default = {}
    if not path or not os.path.isfile(path):
        return copy.deepcopy(default)
    try:
        with open(path, "r") as f:
            data = yaml_loader.safe_load(f)
    except Exception:
        return copy.deepcopy(default)
    if data is None:
        return copy.deepcopy(default)
    return data


def read_mapping(path):
    """
    Read a YAML file that has to hold a mapping, reporting what is wrong with it
    instead of falling back on a default.

    This is how a file is read when something is about to be done with it (a run
    reading what it must run, for instance): a file that is missing or that
    holds something else than the expected settings is an error there, while
    :func:`read_yaml` treats it as "nothing configured yet".

    Raises:
        InvalidSettingsError: the file does not exist, is not valid YAML, or
            does not hold a mapping of settings.
    """
    from odatix.workspace.errors import InvalidSettingsError

    if not path:
        raise InvalidSettingsError("No settings file specified.")
    if not os.path.isfile(path):
        raise InvalidSettingsError('Settings file "{0}" does not exist.'.format(path), path=path)
    try:
        with open(path, "r") as f:
            data = yaml_loader.safe_load(f)
    except Exception as error:
        raise InvalidSettingsError(
            'Settings file "{0}" is not a valid YAML file.'.format(path),
            path=path,
            hints=["error details: " + str(error)],
        )
    if data is None:
        raise InvalidSettingsError('Settings file "{0}" is empty.'.format(path), path=path)
    if not isinstance(data, dict):
        raise InvalidSettingsError(
            'Settings file "{0}" does not hold a list of settings.'.format(path), path=path
        )
    return data


def read_document(path):
    """
    Read a YAML file into a ruamel round-trip mapping, keeping its comments and
    formatting. A missing or empty file yields an empty mapping.
    """
    if not path or not os.path.isfile(path):
        return CommentedMap()
    return load_document(read_text(path))


def _reader():
    reader = YAML()
    # Keep the quoting the user chose: a value nobody edits must come out of a
    # save byte for byte as it went in.
    reader.preserve_quotes = True
    return reader


def load_document(text):
    """
    The round-trip mapping a YAML text holds (see :func:`read_document`). A
    text that is empty or that cannot be read yields an empty one.
    """
    try:
        data = _reader().load(text or "")
    except Exception:
        return CommentedMap()
    if data is None:
        return CommentedMap()
    return data


######################################
# Writing
######################################

def write_text(path, text):
    """
    Write `text` to `path`, creating the parent directories if needed.

    The file is written next to its destination and then renamed over it: a
    run interrupted halfway, or a disk that fills up, leaves the previous
    version of the file in place rather than an empty or truncated one. A
    symbolic link is followed, so that a workspace keeping a file elsewhere
    still finds it there after a save.
    """
    target = os.path.realpath(path)
    directory = os.path.dirname(target)
    if directory:
        os.makedirs(directory, exist_ok=True)
    handle, temporary = tempfile.mkstemp(
        dir=directory or ".", prefix="." + os.path.basename(target) + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w") as f:
            f.write(text)
        if os.path.exists(target):
            # Keep the permissions of the file being replaced, not those of a
            # fresh temporary file (which mkstemp makes private).
            os.chmod(temporary, os.stat(target).st_mode & 0o7777)
        else:
            os.chmod(temporary, 0o666 & ~_umask())
        os.replace(temporary, target)
    except BaseException:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise


def _umask():
    """The process umask (only readable by setting it, so it is set back)."""
    mask = os.umask(0)
    os.umask(mask)
    return mask


_KEY_LINE = re.compile(r"^( *)[^\s#-][^:]*:\s*(#.*)?$")
_ITEM_LINE = re.compile(r"^( *)- ")


def sequence_offset(text):
    """
    How far the items of a list are indented under their key in a YAML text
    ("key:" then "  - item" is 2), 0 when they are not or when it holds no
    block list.
    """
    key_indent = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        item = _ITEM_LINE.match(line)
        if key_indent is not None and item:
            return max(0, len(item.group(1)) - key_indent)
        key = _KEY_LINE.match(line)
        key_indent = len(key.group(1)) if key else None
    return 0


def write_document(path, data, yaml_obj=None):
    """
    Write a mapping to `path`, creating the parent directories if needed,
    keeping the layout of the file it replaces (see :func:`dump_document`).
    """
    write_text(path, dump_document(data, read_text(path), yaml_obj=yaml_obj))


def read_text(path):
    """The text of a file, empty when there is none to read."""
    if not path or not os.path.isfile(path):
        return ""
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError:
        return ""


def dump_document(data, previous="", yaml_obj=None):
    """
    The text of a mapping, laid out like `previous`, the text it replaces.

    ruamel keeps comments and key order, but not two things a file written by
    hand has: the indentation of its lists (ruamel knows one style per dump,
    and would move every list of the file when a single setting changes) and
    the blank lines it starts with. A writer given by the caller keeps its own
    indentation.

    Long values stay on one line: ruamel folds plain scalars at 80 columns by
    default, which would cut a long command in three on every save.

    Beyond that, ruamel lays a whole file out its own way (the alignment of the
    values, the "..." that ends a document, the spaces of a flow mapping...).
    So the text is not taken as ruamel writes it: what ruamel writes for
    `previous` as it is, and what it writes for `data`, are compared, and only
    the lines that differ are carried over into `previous`. A document saved
    without a change comes out exactly as it was; a changed value changes its
    own lines and nothing else.
    """
    writer = _writer(yaml_obj, previous)
    text = _finish(_dump(writer, data), previous)
    if not previous.strip() or text == previous:
        return text
    try:
        baseline = _finish(_dump(_writer(yaml_obj, previous), _reader().load(previous)), previous)
    except Exception:
        return text
    return _carry_changes(previous, baseline, text)


def _writer(yaml_obj, previous):
    if yaml_obj is not None:
        return yaml_obj
    writer = YAML()
    writer.width = 4096
    offset = sequence_offset(previous)
    if offset:
        writer.indent(mapping=2, sequence=offset + 2, offset=offset)
    return writer


def _dump(writer, data):
    buffer = io.StringIO()
    writer.dump(data, buffer)
    return buffer.getvalue()


def _finish(text, previous):
    """What ruamel loses of a file whatever the document says: its first lines."""
    leading = len(previous) - len(previous.lstrip("\n"))
    if leading and not text.startswith("\n"):
        text = "\n" * leading + text
    preamble = _preamble(previous)
    if preamble and not text.lstrip("\n").startswith("---"):
        text = preamble + (text if text.startswith("\n") else text.lstrip("\n"))
    return text


_VALUE_LINE = re.compile(r"^(\s*(?:- )?[^\s#'\"][^:#]*:|\s*-)([ \t]+)(.*?)([ \t]+#.*)?(\r?\n)?$")


def _realign(original, line):
    """
    `line`, the new text of the line `original` was, laid out like it: the
    value where the file puts its values, the comment where it puts it.
    """
    old = _VALUE_LINE.match(original)
    new = _VALUE_LINE.match(line)
    if not old or not new or old.group(1) != new.group(1) or not new.group(3):
        return line
    text = old.group(1) + old.group(2) + new.group(3)
    comment = new.group(4)
    if comment:
        comment = comment.lstrip(" \t")
        if old.group(4) and old.group(4).lstrip(" \t") == comment:
            column = len(old.group(1) + old.group(2) + old.group(3)) + len(old.group(4)) - len(comment)
            text += " " * max(1, column - len(text)) + comment
        else:
            text += " " + comment
    return text + (new.group(5) or "")


def _carry_changes(previous, baseline, changed):
    """
    `previous`, with the changes that turn `baseline` into `changed`.

    `baseline` is `previous` as ruamel writes it: it is the same file, line for
    line, apart from what ruamel lays out its own way. The lines `changed`
    differs from it by are the ones a save is about, and they replace the lines
    of `previous` they stand for. Should the result not read as `changed`
    does -- two hunks too close to tell apart, a file ruamel rewrites too much
    --, `changed` is taken as it is: a layout is worth less than a value.
    """
    if baseline == changed:
        return previous
    base_lines = baseline.splitlines(True)
    previous_lines = previous.splitlines(True)
    changed_lines = changed.splitlines(True)
    if base_lines and not base_lines[-1].endswith("\n"):
        base_lines[-1] += "\n"
    if changed_lines and not changed_lines[-1].endswith("\n"):
        changed_lines[-1] += "\n"
    if previous_lines and not previous_lines[-1].endswith("\n"):
        previous_lines[-1] += "\n"

    # How the lines of the baseline map onto the lines of the file: blocks of
    # the same size map line for line; anything else maps as a whole.
    layout = difflib.SequenceMatcher(None, base_lines, previous_lines, autojunk=False).get_opcodes()

    def block_of(index):
        for block in layout:
            if block[1] <= index < block[2]:
                return block
        return layout[-1]

    def end_of_document():
        # What the file holds after the last line ruamel writes (the "..." that
        # ends a document) stays after it.
        for block in layout:
            if block[0] == "insert" and block[1] == len(base_lines):
                return block[3]
        return len(previous_lines)

    def line_for_line(block):
        return block[0] == "equal" or (block[0] == "replace" and block[2] - block[1] == block[4] - block[3])

    edits = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, base_lines, changed_lines, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        replacement = changed_lines[j1:j2]
        start = block_of(i1) if i1 < len(base_lines) else None
        if (tag == "replace" and i2 - i1 == j2 - j1 and start is not None and line_for_line(start)
                and block_of(i2 - 1) is start):
            # A value changed on lines that are still there: they keep the way
            # the file aligns its values and its comments.
            o1 = start[3] + (i1 - start[1])
            edits.append((o1, o1 + (i2 - i1), [
                _realign(previous_lines[o1 + offset], line) for offset, line in enumerate(replacement)
            ]))
            continue
        if start is None:
            o1 = end_of_document()
        elif line_for_line(start):
            o1 = start[3] + (i1 - start[1])
        else:
            # The change starts inside lines ruamel laid out differently: the
            # whole of them goes, as the baseline writes them.
            replacement = base_lines[start[1]:i1] + replacement
            o1 = start[3]
        if i2 == i1:
            o2 = o1
        else:
            end = block_of(i2 - 1)
            if line_for_line(end):
                o2 = end[3] + (i2 - 1 - end[1]) + 1
            else:
                replacement = replacement + base_lines[i2:end[2]]
                o2 = end[4]
        edits.append((o1, o2, replacement))

    lines = list(previous_lines)
    last = None
    for o1, o2, replacement in reversed(edits):
        if last is not None and o2 > last:
            return changed  # overlapping hunks: no telling which line goes where
        lines[o1:o2] = replacement
        last = o1
    text = "".join(lines)
    if not previous.endswith("\n") and text.endswith("\n") and not changed.endswith("\n"):
        text = text[:-1]
    try:
        if yaml.safe_load(text) != yaml.safe_load(changed):
            return changed
    except Exception:
        return changed
    return text


_DOCUMENT_START = re.compile(r"^---[ \t]*$", re.M)


def _preamble(text):
    """
    The comments a file holds before its '---' marker, which ruamel drops: the
    "Odatix settings for ..." header of every run settings file.
    """
    match = _DOCUMENT_START.search(text)
    if not match:
        return ""
    head = text[:match.end()]
    if any(line.strip() and not line.lstrip().startswith("#") for line in head.splitlines()[:-1]):
        return ""
    return head + "\n"


def new_document(header=None):
    """
    Build an empty round-trip mapping, optionally starting with a header comment
    (see :func:`file_header`).
    """
    data = CommentedMap()
    if header:
        data.yaml_set_start_comment(header)
    return data


def file_header(title, generator="Odatix"):
    """
    The banner Odatix puts at the top of the files it generates.
    """
    from datetime import datetime

    import odatix.components.motd as motd

    return (
        "##############################################\n"
        "# {title}\n"
        "##############################################\n"
        "\n"
        "# This file was generated by {generator} {version} on {date}.\n"
        "# You can still modify manually this file as needed.\n"
    ).format(
        title=title,
        generator=generator,
        version=motd.read_version(),
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def flow_seq(values):
    """A sequence rendered inline, as "[a, b, c]"."""
    seq = CommentedSeq(values if values is not None else [])
    seq.fa.set_flow_style()
    return seq


def block_seq(values):
    """A sequence rendered one item per line."""
    return CommentedSeq(values if values is not None else [])


######################################
# Merging
######################################

#: Tells "not given" from None, which is a value a file holds.
ABSENT = object()

_BOOLEAN_WORDS = {
    "yes": True, "no": False, "true": True, "false": False,
    "on": True, "off": False, "y": True, "n": False,
}
_BOOLEAN_PAIRS = {
    "yes": ("yes", "no"), "no": ("yes", "no"), "true": ("true", "false"), "false": ("true", "false"),
    "on": ("on", "off"), "off": ("on", "off"), "y": ("y", "n"), "n": ("y", "n"),
}


def _as_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _BOOLEAN_WORDS.get(value.strip().lower())
    return None


def _is_empty(value):
    return value is None or (isinstance(value, (str, dict, list, tuple)) and len(value) == 0)


def same_value(a, b):
    """
    Whether two values say the same thing in a settings file.

    This is looser than ``==`` in the ways a file can say the same thing twice:
    ``Yes`` is ``True``, ``8`` is ``"8"``, and an empty key, an empty string,
    an empty list and an empty mapping all say nothing. It is what decides that
    a value was not changed, and is left in the file as it was written.
    """
    if _is_empty(a) and _is_empty(b):
        return True
    if isinstance(a, dict) and isinstance(b, dict):
        if len(a) != len(b):
            return False
        for key in a:
            if key not in b or not same_value(a[key], b[key]):
                return False
        return True
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same_value(x, y) for x, y in zip(a, b))
    if isinstance(a, (dict, list, tuple)) or isinstance(b, (dict, list, tuple)):
        return False
    if isinstance(a, bool) or isinstance(b, bool):
        x, y = _as_boolean(a), _as_boolean(b)
        return x is not None and x == y
    if a == b:
        return True
    if isinstance(a, (int, float)) and isinstance(b, str):
        return str(a) == b.strip()
    if isinstance(b, (int, float)) and isinstance(a, str):
        return str(b) == a.strip()
    return False


def _restyle(old, new):
    """
    `new`, written the way `old` -- the value it replaces -- was: a boolean as
    ``Yes``/``No`` when the file says ``Yes``, a text quoted or as a ``|`` block
    when the file quoted it or wrote it as one.
    """
    if isinstance(new, bool) and isinstance(old, str) and not isinstance(old, bool):
        word = old.strip()
        pair = _BOOLEAN_PAIRS.get(word.lower())
        if pair:
            text = pair[0] if new else pair[1]
            if word.isupper() and len(word) > 1:
                return text.upper()
            if word[:1].isupper():
                return text.capitalize()
            return text
        return new
    if isinstance(old, bool) and isinstance(new, str) and new in ("Yes", "No"):
        # What Settings write a "yesno" setting as, in a file that says true.
        return new == "Yes"
    if isinstance(new, str) and not isinstance(new, bool) and isinstance(old, str) and not isinstance(old, bool):
        text = str(new)
        if isinstance(old, (LiteralScalarString, FoldedScalarString)):
            return type(old)(text) if "\n" in text else text
        if isinstance(old, (DoubleQuotedScalarString, SingleQuotedScalarString)):
            return type(old)(text)
        if isinstance(new, (DoubleQuotedScalarString, SingleQuotedScalarString)) and "\n" not in text:
            # Written plain in the file: it stays plain (ruamel quotes a text
            # that could not be read back otherwise).
            return text
        return new
    return new


def _node(value):
    """A value as a node comments can be attached to."""
    if isinstance(value, (CommentedMap, CommentedSeq)):
        return value
    if isinstance(value, dict):
        node = CommentedMap()
        for key, item in value.items():
            node[key] = _node(item)
        return node
    if isinstance(value, (list, tuple)):
        return CommentedSeq([_node(item) for item in value])
    return value


def merge(node, new, base=ABSENT):
    """
    `node` changed so that it holds `new`, changing as little of it as possible.

    `node` is what :func:`read_document` read (a mapping, a list or a value,
    comments attached), or plain data. Mappings and lists are changed in
    place, entry by entry: an entry left as it was keeps its node -- its
    comments, its quoting, its ``Yes``, its flow or block style --, a changed
    value is written in the style of the value it replaces, an entry taken out
    leaves the comments that follow it to what comes before, and a new key is
    written after the key it follows in `new` rather than at the end.

    Args:
        node: what the file holds.
        new: what it should hold.
        base: what the caller read `node` as, in the shape `new` comes in
            (defaults to `node` itself). Only what differs between `base` and
            `new` is changed: a key `base` and `new` agree on is left as the
            file has it, even when the file says it otherwise -- or does not
            say it at all, because it was a default.

    Returns:
        The node to put in place of `node`: `node` itself when it could be
        changed in place.
    """
    if base is ABSENT:
        base = node
    if same_value(base, new):
        return node
    if isinstance(node, dict) and isinstance(new, dict):
        _merge_mapping(node, new, base if isinstance(base, dict) else node)
        return node
    if isinstance(node, list) and isinstance(new, (list, tuple)):
        _merge_sequence(node, list(new), base if isinstance(base, (list, tuple)) else node)
        return node
    if isinstance(new, (dict, list, tuple)):
        return _node(copy.deepcopy(new))
    return _restyle(node, new)


def set_key(mapping, key, value, base=ABSENT, after=ABSENT):
    """
    ``mapping[key] = value``, the way :func:`merge` writes it: only what differs
    from what the key holds is changed, and a key the mapping does not hold
    yet goes after `after` (see :func:`insert_key`), at the end by default.
    """
    if key in mapping:
        merged = merge(mapping[key], value, base)
        if merged is not mapping[key]:
            mapping[key] = merged
    else:
        insert_key(mapping, key, _node(copy.deepcopy(value)), after=after)
    return mapping


def _merge_mapping(node, new, base):
    for key in [key for key in base if key not in new]:
        if key in node:
            remove_key(node, key)
    previous = None
    for key, value in new.items():
        old = base.get(key, ABSENT)
        if not (old is not ABSENT and same_value(old, value)):
            if key in node:
                merged = merge(node[key], value, old if old is not ABSENT else node[key])
                if merged is not node[key]:
                    node[key] = merged
            else:
                insert_key(node, key, _node(value) if isinstance(node, CommentedMap) else copy.deepcopy(value),
                           after=_last_present(node, new, key))
        if key in node:
            previous = key
    return previous


def _last_present(node, new, key):
    """The key of `new` before `key` that `node` holds, None when there is none."""
    found = None
    for other in new:
        if other == key:
            break
        if other in node:
            found = other
    return found


def _identity(value):
    """
    What an entry of a list is compared by, to tell which entries stayed. An
    entry that names itself (a task, a rule with an "id") is the same entry
    whatever else changed in it.
    """
    if isinstance(value, dict):
        for key in ("name", "id"):
            if isinstance(value.get(key), str) and value.get(key):
                return key + ":" + value.get(key)
        return _content(value)
    return _content(value)


def _content(value):
    if isinstance(value, dict):
        return "{" + ",".join(sorted(str(key) + ":" + _content(item) for key, item in value.items())) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_content(item) for item in value) + "]"
    boolean = _as_boolean(value) if isinstance(value, (bool, str)) else None
    if boolean is not None:
        return "b:" + str(boolean)
    if value is None:
        return ""
    return "s:" + str(value)


def _merge_sequence(node, new, base):
    if len(base) != len(node):
        base = node
    matcher = difflib.SequenceMatcher(
        None, [_identity(item) for item in base], [_identity(item) for item in new], autojunk=False
    )
    for tag, i1, i2, j1, j2 in reversed(matcher.get_opcodes()):
        paired = min(i2 - i1, j2 - j1) if tag in ("replace", "equal") else 0
        for offset in range(paired):
            merged = merge(node[i1 + offset], new[j1 + offset], base[i1 + offset])
            if merged is not node[i1 + offset]:
                node[i1 + offset] = merged
        for index in reversed(range(i1 + paired, i2)):
            remove_item(node, index)
        for offset, value in enumerate(new[j1 + paired:j2]):
            insert_item(node, i1 + paired + offset, value)


######################################
# Comments around what is added or removed
######################################

def _tail(container, key):
    """
    Where ruamel keeps what follows the value of ``container[key]``: the end of
    its line and the comment lines after it, which belong to the deepest last
    entry of a nested value. Returns ``(slots, index)``, or None.
    """
    if not isinstance(container, (CommentedMap, CommentedSeq)):
        return None
    value = container[key]
    while isinstance(value, (CommentedMap, CommentedSeq)) and len(value):
        container = value
        key = list(value.keys())[-1] if isinstance(value, CommentedMap) else len(value) - 1
        value = container[key]
    slots = container.ca.items.setdefault(key, [None, None, None, None])
    return slots, (2 if isinstance(container, CommentedMap) else 0)


def _take_following_lines(container, key):
    """
    Take away the comment lines that follow ``container[key]`` (not the comment
    at the end of its own line), and return them.
    """
    where = _tail(container, key)
    if where is None:
        return ""
    slots, index = where
    token = slots[index]
    if token is None or not isinstance(getattr(token, "value", None), str):
        return ""
    text = token.value
    cut = text.find("\n")
    if cut < 0 or cut == len(text) - 1:
        return ""
    token.value = text[:cut + 1]
    return text[cut + 1:]


def _give_following_lines(container, key, lines):
    """Put comment lines right after ``container[key]``, before what already follows it."""
    if not lines:
        return
    where = _tail(container, key)
    if where is None:
        return
    slots, index = where
    token = slots[index]
    if token is not None and isinstance(getattr(token, "value", None), str):
        text = token.value
        cut = text.find("\n")
        if cut < 0:
            token.value = text + "\n" + lines
        else:
            token.value = text[:cut + 1] + lines + text[cut + 1:]
    else:
        slots[index] = CommentToken("\n" + lines, CommentMark(0), None)


def _give_leading_lines(container, lines):
    """Put comment lines before the first entry of `container`, after those already there."""
    token = CommentToken(lines, CommentMark(0), None)
    comment = container.ca.comment
    if comment is None:
        container.ca.comment = [None, [token]]
    elif comment[1] is None:
        comment[1] = [token]
    else:
        # The very list the mapping holding `container` reads them from.
        comment[1].append(token)


def insert_key(mapping, key, value, after=ABSENT, before=None):
    """
    Add `key` to `mapping` next to the key it belongs with: after `after`
    (first when None), else before `before`, else at the end. The comment lines
    that followed the key it is written after -- which introduce what comes
    next -- stay above what comes next, not above the new key.
    """
    keys = list(mapping.keys())
    if after is not ABSENT and (after is None or after in mapping):
        position = 0 if after is None else keys.index(after) + 1
    elif before is not None and before in mapping:
        position = keys.index(before)
    else:
        position = len(keys)
    following = ""
    if position > 0 and isinstance(mapping, CommentedMap):
        following = _take_following_lines(mapping, keys[position - 1])
    if isinstance(mapping, CommentedMap):
        mapping.insert(position, key, value)
    else:
        items = list(mapping.items())
        items.insert(position, (key, value))
        mapping.clear()
        mapping.update(items)
    if following:
        _give_following_lines(mapping, key, following)
    return mapping


def remove_key(mapping, key):
    """
    Remove `key` from `mapping`, leaving the comment lines that followed its
    value (which introduce what comes next) where they were.
    """
    if key not in mapping:
        return mapping
    keys = list(mapping.keys())
    position = keys.index(key)
    following = _take_following_lines(mapping, key) if isinstance(mapping, CommentedMap) else ""
    mapping.pop(key)
    if isinstance(mapping, CommentedMap):
        mapping.ca.items.pop(key, None)
        if following and position > 0:
            _give_following_lines(mapping, keys[position - 1], following)
        elif following and len(mapping):
            _give_leading_lines(mapping, following)
    return mapping


def insert_item(sequence, index, value):
    """Insert an entry in a list, after the comment lines of the entry before it."""
    following = ""
    if index > 0 and isinstance(sequence, CommentedSeq):
        following = _take_following_lines(sequence, index - 1)
    sequence.insert(index, _node(value) if isinstance(sequence, CommentedSeq) else copy.deepcopy(value))
    if following:
        _give_following_lines(sequence, index, following)
    return sequence


def remove_item(sequence, index):
    """Remove an entry from a list, keeping the comment lines that follow it."""
    following = _take_following_lines(sequence, index) if isinstance(sequence, CommentedSeq) else ""
    del sequence[index]
    if following and index > 0:
        _give_following_lines(sequence, index - 1, following)
    elif following and len(sequence):
        _give_leading_lines(sequence, following)
    return sequence


######################################
# Lists edited in the text
######################################

_LIST_KEY_END = re.compile(r"^[^\s#-][^:]*:")
_DOCUMENT_MARKER = re.compile(r"^(---|\.\.\.)\s*$")
_ACTIVE_ENTRY = re.compile(r"^(\s*)-\s+(.*?)(\s+#.*)?$")
_COMMENTED_ENTRY = re.compile(r"^(\s*)#\s*-\s*(\S.*?)(\s+#.*)?$")


def _entry_value(text):
    """The entry a list line names, without the quotes it may be written with."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    return text


def _entry_group(value):
    """What an entry is listed with: "Counter/*" goes with "Counter/04bits"."""
    return value.split("/")[0].split("+")[0].strip()


def edit_list_text(text, key, values, keep=None, renames=None):
    """
    The text of a file whose top-level `key` lists `values`, edited the way its
    author would edit it.

    An entry taken out of the list is commented out where it is, a
    commented-out entry put back is uncommented where it is, and only an entry
    the file never mentioned is added -- next to the entries of the same
    architecture, else after the last one. The comments and the commented-out
    entries of the file stay exactly as they were.

    Args:
        text (str): the text of the file.
        key (str): a top-level key holding a list of names.
        values (list): the names the list should hold.
        keep (list): when given, the names to keep as commented-out entries;
            any other entry, commented out or not, is removed. When not given,
            nothing is removed: a commented-out entry is a catalogue entry.
        renames (dict): ``{old name: new name}``, renamed where they are.

    Returns:
        str: the edited text, or None when `key` is not a block list this can
        edit ("key: []", an inline list, a list of mappings...), for the caller
        to write the list another way.
    """
    lines = text.splitlines(True)
    start = None
    for index, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if re.match(r"^" + re.escape(key) + r":\s*(#.*)?$", stripped):
            start = index
            break
        empty = re.match(r"^" + re.escape(key) + r":\s*\[\s*\]([ \t]*#.*)?$", stripped)
        if empty:
            if not values and not keep:
                return text  # still empty
            # An empty inline list is an empty block list to fill.
            lines[index] = key + ":" + (empty.group(1) or "") + line[len(stripped):]
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index].rstrip("\n")
        if _LIST_KEY_END.match(line) or _DOCUMENT_MARKER.match(line):
            end = index
            break
    for index in range(start + 1, end):
        line = lines[index].rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ACTIVE_ENTRY.match(line)
        if not match or match.group(2).startswith(("{", "[")) or re.match(r"^[^'\"]*:\s", match.group(2) + " "):
            return None  # not a list of names

    wanted = [str(value) for value in values]
    kept_commented = None if keep is None else set(str(value) for value in keep)
    renames = dict((str(old), str(new)) for old, new in (renames or {}).items())
    kept = set()
    last_item = None
    indent = None
    removed = []
    for index in range(start + 1, end):
        line = lines[index].rstrip("\n")
        newline = lines[index][len(line):]
        for pattern, commented in ((_ACTIVE_ENTRY, False), (_COMMENTED_ENTRY, True)):
            match = pattern.match(line)
            if not match:
                continue
            value = _entry_value(match.group(2))
            if value in renames:
                match_text = match.group(2)
                renamed = match_text.replace(value, renames[value], 1)
                line = line[:match.start(2)] + renamed + line[match.end(2):]
                lines[index] = line + newline
                match = pattern.match(line)
                value = _entry_value(match.group(2))
            if not commented or indent is None:
                indent = match.group(1)
            if not commented:
                if value in wanted and value not in kept:
                    kept.add(value)
                    last_item = index
                elif kept_commented is not None and value not in kept_commented:
                    removed.append(index)
                else:
                    lines[index] = match.group(1) + "# - " + line[len(match.group(1)):].lstrip()[1:].lstrip() + newline
            elif kept_commented is not None and value not in kept_commented and value not in wanted:
                removed.append(index)
            break
    for index in range(start + 1, end):
        line = lines[index].rstrip("\n")
        match = _COMMENTED_ENTRY.match(line)
        if not match:
            continue
        value = _entry_value(match.group(2))
        if value in wanted and value not in kept:
            kept.add(value)
            newline = lines[index][len(line):]
            lines[index] = match.group(1) + "- " + match.group(2) + (match.group(3) or "") + newline
            last_item = index if last_item is None else max(last_item, index)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    if indent is None:
        indent = "  "

    # Entries to add, active ones and (with `keep`) commented-out ones, in the
    # order they are asked for.
    present = set(kept)
    for index in range(start + 1, end):
        match = _COMMENTED_ENTRY.match(lines[index].rstrip("\n"))
        if match:
            present.add(_entry_value(match.group(2)))
    missing = [(value, True) for value in wanted if value not in kept]
    if kept_commented is not None:
        missing += [(value, False) for value in keep if str(value) not in present and str(value) not in wanted]
    for value, active in reversed(missing):
        group = _entry_group(value)
        position = None
        for index in range(start + 1, end):
            line = lines[index].rstrip("\n")
            match = _ACTIVE_ENTRY.match(line) or _COMMENTED_ENTRY.match(line)
            if match and index not in removed and _entry_group(_entry_value(match.group(2))) == group:
                position = index
                break
        if position is None:
            position = (last_item if last_item is not None else start) + 1
        lines.insert(position, indent + ("- " if active else "# - ") + value + "\n")
        end += 1
        removed = [index + 1 if index >= position else index for index in removed]
        if last_item is not None and position <= last_item:
            last_item += 1
    for index in sorted(removed, reverse=True):
        del lines[index]
    return "".join(lines)


######################################
# Value parsing
######################################

def parse_bool(value, default=False):
    """
    Read a boolean the way the workspace files write them: YAML booleans, but
    also the "Yes"/"No" spelling Odatix generates.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("yes", "true", "y", "on", "1"):
            return True
        if text in ("no", "false", "n", "off", "0"):
            return False
    return default


def parse_int(value, default=None):
    """Read an integer, returning `default` for anything that is not one."""
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_int_list(value):
    """
    Read a list of integers, accepting either a real list or the free text a
    form field holds ("50, 100; 200"). Anything that is not a number is dropped.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = str(value).replace(";", ",").split(",")
    numbers = []
    for item in items:
        number = parse_int(item)
        if number is not None:
            numbers.append(number)
    return numbers


def yes_no(value):
    """Render a boolean the way the generated files spell it."""
    return "Yes" if value else "No"
