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
of one directory at a time.

It opens the workspace, and the folders of the ``gui_browse_roots`` setting
(the whole file system when it is not set). It opens on the workspace, and
goes anywhere from there: reaching the GUI at all takes the token of its start
(see odatix.gui.access), which only its owner was given.
A path inside the workspace travels relative to it, any other one absolute.

Every request is checked here, against the real paths of these folders: the
client is never trusted, and a symbolic link leading out of them is refused.
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


def _allowed(path, root, roots=()):
    """Whether `path` is in the workspace or in one of the other `roots`."""
    return any(_inside(path, r) for r in (root,) + tuple(roots))


def _rel(path, root):
    """
    `path` as the modal handles it: relative to the workspace root ("" for the
    root) when it is inside, absolute otherwise.
    """
    if not _inside(path, root):
        return os.path.normpath(path).replace(os.sep, "/")
    rel = os.path.relpath(path, root)
    return "" if rel == "." else rel.replace(os.sep, "/")


def resolve(root, rel, roots=()):
    """
    The absolute path of `rel`, a path relative to the workspace (or absolute,
    as a field may hold one), refused when it leads out of the workspace and
    of the other `roots`.
    """
    rel = (rel or "").strip()
    if rel.startswith("~"):
        rel = os.path.expanduser(rel)
    path = os.path.normpath(rel if os.path.isabs(rel) else os.path.join(root, rel))
    if not _allowed(path, root, roots):
        raise BrowseError("Outside of the workspace" if not roots else "Outside of the folders the browser may open")
    return path


def start_directory(root, base, value, roots=()):
    """
    Where the modal opens: the directory of the field's current value (and the
    entry to select in it), else the base the field is relative to, else the
    workspace root. A value that does not exist falls back to its closest
    existing parent.
    """
    try:
        base_path = resolve(root, base, roots)
    except BrowseError:
        base_path = root
    if not os.path.isdir(base_path):
        base_path = root
    selected = ""
    path = base_path
    value = (value or "").strip()
    if value.startswith("~"):
        value = os.path.expanduser(value)
    if value:
        try:
            candidate = os.path.normpath(os.path.join(base_path, value))
            # A value relative to the workspace (see path_input's base_inside_only).
            workspace_candidate = os.path.normpath(os.path.join(root, value))
            if not os.path.exists(candidate) and os.path.exists(workspace_candidate):
                candidate = workspace_candidate
            if not _allowed(candidate, root, roots):
                raise BrowseError()
            if os.path.exists(candidate) and not os.path.isdir(candidate):
                selected = os.path.basename(candidate)
                candidate = os.path.dirname(candidate)
            while (not os.path.isdir(candidate) and _allowed(candidate, root, roots)
                   and candidate != os.path.dirname(candidate)):
                candidate = os.path.dirname(candidate)
            if os.path.isdir(candidate) and _allowed(candidate, root, roots):
                path = candidate
        except BrowseError:
            pass
    return _rel(base_path, root), _rel(path, root), selected


def parent_of(path, root, roots=()):
    """The directory above `path` the modal may go to, None at the top of what it may open."""
    parent = os.path.dirname(path)
    if parent == path or not _allowed(parent, root, roots):
        return None
    return _rel(parent, root)


def display_path(path):
    """A folder as a user writes it: its real path, the home directory as "~"."""
    home = os.path.expanduser("~")
    path = os.path.normpath(path)
    if path == home or path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


def crumbs(path, root, roots=()):
    """The breadcrumbs of `path`: its root first, then each directory below it."""
    owners = [r for r in (root,) + tuple(roots) if _inside(path, r)]
    # The deepest root holding the path: the workspace in the home directory
    # shows as the workspace.
    top = max(owners, key=lambda r: len(_real(r))) if owners else root
    result = [{"name": os.path.basename(top.rstrip(os.sep)) or top, "display": display_path(top),
               "path": _rel(top, root), "root": True}]
    rel = os.path.relpath(path, top)
    if rel != ".":
        current = top
        for part in rel.split(os.sep):
            current = os.path.join(current, part)
            result.append({"name": part, "path": _rel(current, root), "root": False})
    return result


def list_directory(root, rel, show_hidden=False, roots=()):
    """
    The entries of directory `rel` (of the workspace, or of one of the other
    `roots`): directories first, then files, each sorted by name.
    """
    path = resolve(root, rel, roots)
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
            # A link out of the folders the browser may open is not followed.
            # A directory is checked as well: a junction of Windows leads
            # elsewhere without being a symbolic link.
            if (entry.is_symlink() or is_dir) and not _allowed(entry.path, root, roots):
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
        "parent": parent_of(path, root, roots),
        "crumbs": crumbs(path, root, roots),
        "entries": entries[:MAX_ENTRIES],
        "hidden": hidden,
        "truncated": truncated,
    }




#: The folders opened besides the workspace when ``gui_browse_roots`` is not set.
DEFAULT_ROOTS = (os.path.abspath(os.sep),)


def workspace_root():
    return os.path.realpath(Workspace.open().root)


def browse_roots(root, configured=None):
    """
    The folders the browser may open besides the workspace `root`: the
    `configured` ones (``gui_browse_roots``, relative to the workspace or with
    ``~``), else the whole file system. Missing folders, and the workspace
    itself, are left out: ``.`` keeps the browser in the workspace.
    """
    if configured is None:
        try:
            configured = Workspace.open(root).settings.get("gui_browse_roots")
        except Exception:
            configured = None
    if not configured:
        configured = DEFAULT_ROOTS
    if isinstance(configured, str):
        configured = [configured]
    result = []
    for entry in configured:
        entry = os.path.expanduser(str(entry).strip())
        if not entry:
            continue
        path = os.path.realpath(entry if os.path.isabs(entry) else os.path.join(root, entry))
        if os.path.isdir(path) and _real(path) != _real(root) and path not in result:
            result.append(path)
    return result


#: The folders of the workspace shown in the side panel: setting, label, icon.
WORKSPACE_PLACES = (
    ("arch_path", "Architectures", "folder"),
    ("sim_path", "Simulations", "folder"),
    ("workflow_path", "Workflows", "folder"),
    ("target_path", "Targets", "folder"),
    ("result_path", "Results", "folder"),
    ("work_path", "Work", "folder"),
)


def _place(name, path, icon, root, roots):
    """One entry of the side panel, greyed (`available` false) when it cannot be opened."""
    available = bool(path) and os.path.isdir(path) and _allowed(path, root, roots)
    return {
        "name": name,
        "icon": icon,
        "path": _rel(path, root) if path else None,
        "title": display_path(path) if path else "",
        "available": available,
    }


def places(root, roots, paths=None):
    """
    The side panel of the modal: the places of the system ("/", the home
    directory, then the other configured roots), and the folders of the
    workspace (`paths`, its settings with their defaults: Workspace.paths). A place the browser may not open stays listed, greyed.
    """
    home = os.path.expanduser("~")
    system_paths = [os.path.abspath(os.sep), home]
    system = [
        _place("Computer", system_paths[0], "computer", root, roots),
        _place("Home", home if os.path.isdir(home) else None, "home", root, roots),
    ]
    seen = {_real(p) for p in system_paths}
    for r in roots:
        if _real(r) not in seen:
            seen.add(_real(r))
            system.append(_place(os.path.basename(r.rstrip(os.sep)) or r, r, "folder", root, roots))

    if paths is None:
        try:
            paths = Workspace.open(root).paths
        except Exception:
            paths = {}
    workspace = [_place(os.path.basename(root) or root, root, "workspace", root, roots)]
    listed = {_real(root)}
    for key, label, icon in WORKSPACE_PLACES:
        try:
            value = paths.get(key) if isinstance(paths, dict) else getattr(paths, key, None)
        except Exception:
            value = None
        if not value:
            continue
        value = os.path.expanduser(str(value))
        path = os.path.normpath(value if os.path.isabs(value) else os.path.join(root, value))
        if _real(path) in listed:
            continue
        listed.add(_real(path))
        workspace.append(_place(label, path, icon, root, roots))
    return {"system": system, "workspace": workspace}


def register(app):
    """Serve `LIST_URL` on a Dash app."""
    from flask import jsonify, request

    def listing():
        root = workspace_root()
        roots = browse_roots(root)
        args = request.args
        show_hidden = args.get("hidden") == "1"
        try:
            if args.get("open") == "1":
                base, path, selected = start_directory(root, args.get("base", ""), args.get("value", ""), roots)
            else:
                base, path, selected = args.get("base", ""), args.get("path", ""), ""
            result = list_directory(root, path, show_hidden, roots)
        except BrowseError as e:
            return jsonify({"error": str(e)}), 400
        result.update({
            "root": root,
            "root_name": os.path.basename(root) or root,
            "base": base,
            "selected": selected,
            "roots": [{"name": display_path(r), "path": _rel(r, root)} for r in roots],
            "places": places(root, roots),
        })
        return jsonify(result)

    app.server.add_url_rule(LIST_URL, "odatix_file_browser_list", listing)
