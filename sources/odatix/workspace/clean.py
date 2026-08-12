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
Clean settings: what "odatix clean" removes from a workspace.

A workspace declares them in one file, holding a single list of paths -- glob
patterns, resolved against the workspace directory. The tools Odatix runs each
leave their own litter behind, so the list is what tells Odatix which of it is
safe to throw away.

Cleaning nothing is a normal state of a workspace, so a missing file is not an
error: it simply removes nothing.

Removing files is the one thing this API does that cannot be undone, so it never
does it silently: :meth:`CleanSettingsFile.run` reports every path it removed,
every pattern that matched nothing, and every path it refused to touch, and it
refuses outright the patterns that would take the whole workspace with them
unless it is explicitly forced.
"""

import glob
import os
import shutil

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedSeq

from odatix.workspace.yaml_io import block_seq, file_header, new_document, read_document, read_yaml, write_document

__all__ = ["CleanSettingsFile", "CleanResult", "PathRemoval", "DANGEROUS_PATHS", "remove_path"]


#: The patterns that would wipe out the workspace, the home directory or the
#: whole filesystem. They are only removed when a clean is explicitly forced.
DANGEROUS_PATHS = ("/", "./", "./*", "*", "~", ".", "..")


######################################
# Results
######################################

class PathRemoval(object):
    """
    What became of one path a clean tried to remove.

    Attributes:
        path (str): the path itself.
        kind (str): "file", "directory" or "" when nothing was removed.
        status (str): one of "removed", "skipped" (refused as dangerous) or
            "error".
        message (str): why, for the statuses that are not "removed".
    """

    def __init__(self, path, kind="", status="removed", message=""):
        self.path = path
        self.kind = kind
        self.status = status
        self.message = message

    @property
    def removed(self):
        return self.status == "removed"

    def __repr__(self):
        return "<PathRemoval {0!r} {1}>".format(self.path, self.status)


class CleanResult(object):
    """
    What a clean did.

    Attributes:
        removed (list): the :class:`PathRemoval` of every path actually removed.
        skipped (list): the ones refused because the pattern was dangerous.
        errors (list): the ones that could not be removed.
        unmatched (list): the resolved paths of the patterns that matched
            nothing at all.
    """

    def __init__(self):
        self.removed = []
        self.skipped = []
        self.errors = []
        self.unmatched = []

    @property
    def ok(self):
        """Whether the clean went through without a single failure."""
        return not self.errors

    def add(self, removal):
        if removal.status == "removed":
            self.removed.append(removal)
        elif removal.status == "skipped":
            self.skipped.append(removal)
        else:
            self.errors.append(removal)
        return removal

    def extend(self, other):
        self.removed.extend(other.removed)
        self.skipped.extend(other.skipped)
        self.errors.extend(other.errors)
        self.unmatched.extend(other.unmatched)
        return self

    def summary(self):
        """A one line account of the clean, as the interfaces report it."""
        parts = ["{0} path(s) removed".format(len(self.removed))]
        if self.skipped:
            parts.append("{0} refused".format(len(self.skipped)))
        if self.errors:
            parts.append("{0} failed".format(len(self.errors)))
        if self.unmatched:
            parts.append("{0} pattern(s) matched nothing".format(len(self.unmatched)))
        return ", ".join(parts)

    def __repr__(self):
        return "<CleanResult {0}>".format(self.summary())


######################################
# Removing
######################################

def remove_path(pattern, force=False, root=None):
    """
    Remove everything one pattern of a clean list matches.

    Args:
        pattern (str): a path or glob pattern, resolved against `root`.
        force (bool): remove even the patterns of :data:`DANGEROUS_PATHS`.
        root (str): the directory the pattern is relative to. The current one by
            default, which is where the Odatix commands run.

    Returns:
        CleanResult: what was removed, refused or failed. A pattern matching
        nothing lands in :attr:`~CleanResult.unmatched`, which is not an error:
        a workspace that was never run has nothing to clean.
    """
    result = CleanResult()

    pattern = str(pattern or "").strip()
    if pattern == "":
        return result

    full_path = os.path.realpath(os.path.join(root if root else os.getcwd(), pattern))

    if pattern in DANGEROUS_PATHS or full_path in DANGEROUS_PATHS:
        if not force:
            result.add(PathRemoval(
                full_path, status="skipped",
                message='Removing "{0}" seems dangerous. Force the clean to remove it anyway '
                        "(at your own risks).".format(full_path),
            ))
            return result

    matches = glob.glob(full_path)
    if not matches:
        result.unmatched.append(full_path)
        return result

    for path in matches:
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
                result.add(PathRemoval(path, kind="file"))
            elif os.path.isdir(path):
                shutil.rmtree(path)
                result.add(PathRemoval(path, kind="directory"))
            else:
                result.unmatched.append(path)
        except Exception as error:
            result.add(PathRemoval(path, status="error", message=str(error)))

    return result


######################################
# The file
######################################

class CleanSettingsFile(object):
    """
    The clean settings file of a workspace.
    """

    def __init__(self, path, root=None):
        self.path = path
        #: The directory the patterns are relative to.
        self.root = root if root else "."
        self._remove_list = None

    @property
    def exists(self):
        return os.path.isfile(self.path)

    ######################################
    # Content
    ######################################

    def _load(self):
        if self._remove_list is not None:
            return
        data = read_yaml(self.path, default={})
        if not isinstance(data, dict):
            data = {}
        remove_list = data.get("remove_list")
        self._remove_list = [str(item) for item in remove_list if item is not None] if isinstance(remove_list, list) else []

    @property
    def remove_list(self):
        """The paths and glob patterns a clean removes, in file order."""
        self._load()
        return self._remove_list

    @remove_list.setter
    def remove_list(self, value):
        self._remove_list = _as_pattern_list(value)

    def reload(self):
        self._remove_list = None
        return self

    ######################################
    # Editing
    ######################################

    def add(self, pattern):
        """Add one pattern, unless the list already holds it."""
        pattern = str(pattern).strip()
        if pattern != "" and pattern not in self.remove_list:
            self._remove_list.append(pattern)
        return self

    def remove(self, pattern):
        """Drop one pattern from the list."""
        self._load()
        self._remove_list = [item for item in self._remove_list if item != pattern]
        return self

    def to_dict(self):
        return {"remove_list": list(self.remove_list)}

    ######################################
    # Writing
    ######################################

    def save(self):
        """
        Write the file back, keeping its comments and any top-level key the API
        does not own. A file that does not exist yet is generated with the
        header Odatix puts on the files it writes.

        The list of a hand-written clean file is usually grouped by the tool
        that leaves each file behind, with a comment introducing every group, so
        the comments of the patterns that survive an edit are kept with them
        (see :func:`_rebuild_remove_list`).
        """
        self._load()
        if self.exists:
            document = read_document(self.path)
        else:
            document = new_document(file_header("Odatix Clean Settings"))
        document["remove_list"] = _rebuild_remove_list(document.get("remove_list"), self._remove_list)
        write_document(self.path, document, yaml_obj=_writer())
        return self

    ######################################
    # Running
    ######################################

    def run(self, force=False, root=None):
        """
        Remove everything the list matches.

        Args:
            force (bool): remove even the patterns of :data:`DANGEROUS_PATHS`.
            root (str): the directory the patterns are relative to. The
                workspace directory by default.

        Returns:
            CleanResult: what was removed, refused or failed.
        """
        root = root if root else self.root
        result = CleanResult()
        for pattern in self.remove_list:
            result.extend(remove_path(pattern, force=force, root=root))
        return result

    def __repr__(self):
        return "<CleanSettingsFile {0!r}>".format(self.path)


def _writer():
    """
    The YAML writer this file is written with: its list is indented under its
    key, which is how a clean file reads when it is written by hand.
    """
    writer = YAML()
    writer.preserve_quotes = True
    writer.indent(mapping=2, sequence=4, offset=2)
    return writer


def _rebuild_remove_list(previous, patterns):
    """
    The new list, carrying over the comment each kept pattern had.

    A pattern the file already held keeps whatever was written next to it, and
    the quoting it was written with, at its new position; one that is gone takes
    its comment with it, and a new one simply has none. A file nobody edited
    thus comes out of a save exactly as it went in.
    """
    if not isinstance(previous, CommentedSeq):
        return block_seq(list(patterns))

    comments = {}
    written = {}
    for index, value in enumerate(previous):
        written.setdefault(str(value), value)
        comment = previous.ca.items.get(index)
        if comment is not None:
            comments[str(value)] = comment

    seq = block_seq([written.get(str(pattern), pattern) for pattern in patterns])
    for index, pattern in enumerate(patterns):
        comment = comments.get(str(pattern))
        if comment is not None:
            seq.ca.items[index] = comment
    return seq


def _as_pattern_list(value):
    """
    The patterns as the file holds them, from a list or from the free text an
    editor holds (one pattern per line).
    """
    if value is None:
        return []
    if isinstance(value, str):
        items = value.splitlines()
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        return []
    patterns = []
    for item in items:
        if item is None:
            continue
        text = str(item).strip()
        if text != "":
            patterns.append(text)
    return patterns
