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
Server side of the file browser of path fields (see `ui.path_input`).

The browser of the user may run on another machine than the GUI: the paths a
field holds are paths of the server, which a native file picker cannot give.
The modal (assets/file_browser.js) therefore asks this endpoint for the content
of one directory at a time, and never sees anything outside the workspace.

Every request is checked here, against the real path of the workspace: the
client is never trusted, and a symbolic link leading out of it is refused.
"""

import os

from odatix.workspace import Workspace

#: Where the modal asks for a directory listing.
LIST_URL = "/_odatix/fs/list"

#: Entries hidden with the dot files unless "show hidden" is ticked.
NOISE = {"__pycache__", "node_modules"}

#: A directory with more entries than this is cut: the filter narrows it down.
MAX_ENTRIES = 2000


class BrowseError(Exception):
    pass


def _real(path):
    return os.path.normcase(os.path.realpath(path))


def _inside(path, root):
    path, root = _real(path), _real(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _rel(path, root):
    """`path` as written in the workspace: relative to its root, "" for the root."""
    rel = os.path.relpath(path, root)
    return "" if rel == "." else rel.replace(os.sep, "/")


def resolve(root, rel):
    """
    The absolute path of `rel`, a path relative to the workspace (or absolute,
    as a field may hold one), refused when it leads out of the workspace.
    """
    rel = (rel or "").strip()
    path = os.path.normpath(rel if os.path.isabs(rel) else os.path.join(root, rel))
    if not _inside(path, root):
        raise BrowseError("Outside of the workspace")
    return path


def start_directory(root, base, value):
    """
    Where the modal opens: the directory of the field's current value (and the
    entry to select in it), else the base the field is relative to, else the
    workspace root. A value that does not exist falls back to its closest
    existing parent.
    """
    try:
        base_path = resolve(root, base)
    except BrowseError:
        base_path = root
    if not os.path.isdir(base_path):
        base_path = root
    selected = ""
    path = base_path
    value = (value or "").strip()
    if value:
        try:
            candidate = os.path.normpath(os.path.join(base_path, value))
            if not _inside(candidate, root):
                raise BrowseError()
            if os.path.exists(candidate) and not os.path.isdir(candidate):
                selected = os.path.basename(candidate)
                candidate = os.path.dirname(candidate)
            while not os.path.isdir(candidate) and _inside(candidate, root) and candidate != root:
                candidate = os.path.dirname(candidate)
            if os.path.isdir(candidate) and _inside(candidate, root):
                path = candidate
        except BrowseError:
            pass
    return _rel(base_path, root), _rel(path, root), selected


def list_directory(root, rel, show_hidden=False):
    """
    The entries of directory `rel` of the workspace: directories first, then
    files, each sorted by name.
    """
    path = resolve(root, rel)
    if not os.path.isdir(path):
        raise BrowseError("Not a directory")
    entries = []
    hidden = 0
    try:
        scan = list(os.scandir(path))
    except OSError as e:
        raise BrowseError(e.strerror or "Cannot read the directory")
    for entry in scan:
        name = entry.name
        if not show_hidden and (name.startswith(".") or name in NOISE):
            hidden += 1
            continue
        try:
            is_dir = entry.is_dir()
            # A link out of the workspace is not followed.
            if entry.is_symlink() and not _inside(entry.path, root):
                continue
            stat = entry.stat()
        except OSError:
            continue
        entries.append({
            "name": name,
            "dir": is_dir,
            "size": None if is_dir else stat.st_size,
            "mtime": int(stat.st_mtime),
        })
    entries.sort(key=lambda e: (not e["dir"], e["name"].lower()))
    truncated = max(0, len(entries) - MAX_ENTRIES)
    return {
        "path": _rel(path, root),
        "entries": entries[:MAX_ENTRIES],
        "hidden": hidden,
        "truncated": truncated,
    }


def workspace_root():
    return os.path.realpath(Workspace.open().root)


def register(app):
    """Serve `LIST_URL` on a Dash app."""
    from flask import jsonify, request

    def listing():
        root = workspace_root()
        args = request.args
        show_hidden = args.get("hidden") == "1"
        try:
            if args.get("open") == "1":
                base, path, selected = start_directory(root, args.get("base", ""), args.get("value", ""))
            else:
                base, path, selected = args.get("base", ""), args.get("path", ""), ""
            result = list_directory(root, path, show_hidden)
        except BrowseError as e:
            return jsonify({"error": str(e)}), 400
        result.update({
            "root": root,
            "root_name": os.path.basename(root) or root,
            "base": base,
            "selected": selected,
        })
        return jsonify(result)

    app.server.add_url_rule(LIST_URL, "odatix_file_browser_list", listing)
