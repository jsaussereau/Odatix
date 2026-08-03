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

Everything the API writes goes through :func:`write_document`, so a workspace
file never ends up half-written by one helper and half by another.
"""

import copy
import os

import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

__all__ = [
    "read_yaml",
    "read_mapping",
    "read_document",
    "write_document",
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
            data = yaml.safe_load(f)
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
            data = yaml.safe_load(f)
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
    reader = YAML()
    # Keep the quoting the user chose: a value nobody edits must come out of a
    # save byte for byte as it went in.
    reader.preserve_quotes = True
    try:
        with open(path, "r") as f:
            data = reader.load(f)
    except Exception:
        return CommentedMap()
    if data is None:
        return CommentedMap()
    return data


######################################
# Writing
######################################

def write_document(path, data, yaml_obj=None):
    """
    Write a mapping to `path`, creating the parent directories if needed.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    writer = yaml_obj if yaml_obj is not None else YAML()
    with open(path, "w") as f:
        writer.dump(data, f)


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
