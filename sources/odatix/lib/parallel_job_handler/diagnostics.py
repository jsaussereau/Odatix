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
What the daemon was doing when it stopped answering.

A session that dies takes its terminal with it: its stdout goes nowhere by
default, its scheduler thread runs unattended, and the only thing left to look
at afterwards is that the monitor no longer connects. This is the one place
that survives -- a small append-only file next to the session state, holding
the few things that turn "it froze" into a cause: how long a tick took, how
many jobs the session is carrying, what an unhandled exception was.

It is deliberately not the ``logging`` module: the daemon runs uvicorn, which
reconfigures logging for its own purposes, and a diagnostics file that a
library can silence is worth nothing.
"""

import os
import threading
import time
import traceback

__all__ = ["configure", "log", "log_exception", "is_enabled", "diagnostics_path"]

#: How large the file is allowed to grow before it is rotated once, in bytes.
#: A frozen session writes slowly -- a heartbeat a minute -- so this is days.
MAX_SIZE = 4 * 1024 * 1024

_state = {"path": None}
_lock = threading.Lock()


def diagnostics_path(state_file):
    """Where the diagnostics of the session whose state is ``state_file`` go."""
    state_file = os.path.realpath(os.path.expanduser(str(state_file)))
    directory = os.path.dirname(state_file)
    name = os.path.basename(state_file)
    for suffix in (".json", ".yml"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return os.path.join(directory, "{0}.diag.log".format(name or "daemon"))


def configure(path):
    """Start writing diagnostics to ``path``. Called once, by the daemon."""
    with _lock:
        _state["path"] = str(path) if path else None
    if path:
        log("diagnostics opened", pid=os.getpid())


def is_enabled():
    return _state["path"] is not None


def log(message, **fields):
    """
    One line: when, from which thread, what, and whatever numbers explain it.

    Never raises: a diagnostics file that can break the daemon it observes
    would be worse than no diagnostics at all.
    """
    path = _state["path"]
    if not path:
        return
    try:
        extra = " ".join("{0}={1}".format(key, _render(value)) for key, value in sorted(fields.items()))
        line = "{0} [{1}] {2}{3}\n".format(
            time.strftime("%Y-%m-%d %H:%M:%S"),
            threading.current_thread().name,
            message,
            (" " + extra) if extra else "",
        )
        with _lock:
            _rotate_if_needed(path)
            with open(path, "a") as handle:
                handle.write(line)
    except Exception:
        pass


def log_to(path, message, **fields):
    """Write one line into a given session's file, from outside that session.

    Clients act on sessions they do not run -- deleting a state file above all,
    which is irreversible and leaves the daemon unreachable. The trace belongs
    in the file of the session it happened to, not in the client's own.
    """
    if not path:
        return
    previous = _state["path"]
    try:
        _state["path"] = path
        log(message, **fields)
    finally:
        _state["path"] = previous


def log_exception(message, error=None, **fields):
    """Same as :func:`log`, followed by the traceback that is being handled."""
    log(message, error=repr(error) if error is not None else "", **fields)
    path = _state["path"]
    if not path:
        return
    try:
        text = traceback.format_exc()
        if not text or text.startswith("NoneType"):
            return
        with _lock:
            with open(path, "a") as handle:
                handle.write(text if text.endswith("\n") else text + "\n")
    except Exception:
        pass


def _render(value):
    if isinstance(value, float):
        return "{0:.3f}".format(value)
    text = str(value)
    return text if " " not in text else '"{0}"'.format(text)


def _rotate_if_needed(path):
    try:
        if os.path.getsize(path) < MAX_SIZE:
            return
    except OSError:
        return
    try:
        os.replace(path, path + ".1")
    except OSError:
        pass
