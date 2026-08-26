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

"""Putting text in the system clipboard from a terminal application."""

import base64
import os
import subprocess
import sys

# Command lines tried in order, first one available wins.
_CLIPBOARD_COMMANDS = (
    ("wl-copy",),
    ("xclip", "-selection", "clipboard"),
    ("xsel", "--clipboard", "--input"),
    ("pbcopy",),
    ("clip.exe",),
)

# OSC 52 payloads above this size are dropped by most terminals, so we do not
# even try: the local helper is the only way for very large selections.
OSC52_MAX_BYTES = 100000


def _command_exists(command):
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(directory, command)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return True
    return False


def _copy_with_command(text):
    # A Wayland/X11 helper only makes sense when there is a display to talk to,
    # otherwise it hangs or fails on every call (typically over SSH).
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    for command in _CLIPBOARD_COMMANDS:
        if command[0] in ("wl-copy", "xclip", "xsel") and not has_display:
            continue
        if not _command_exists(command[0]):
            continue
        try:
            process = subprocess.Popen(
                list(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            process.communicate(text.encode("utf-8"), timeout=2)
            if process.returncode == 0:
                return command[0]
        except Exception:
            continue
    return None


def _copy_with_osc52(text):
    """Ask the terminal itself to hold the text, which also works over SSH."""
    payload = text.encode("utf-8")
    if len(payload) > OSC52_MAX_BYTES:
        return False
    encoded = base64.b64encode(payload).decode("ascii")
    sequence = "\033]52;c;" + encoded + "\a"
    if os.environ.get("TMUX"):
        # tmux swallows unknown OSC sequences unless they are wrapped for it.
        sequence = "\033Ptmux;\033" + sequence + "\033\\"
    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
        return True
    except (IOError, ValueError):
        return False


def copy_to_clipboard(text):
    """Copies `text` to the system clipboard.

    Returns a short description of what was used, or None when nothing worked.
    """
    if not text:
        return None
    command = _copy_with_command(text)
    if command is not None:
        return command
    if _copy_with_osc52(text):
        return "terminal"
    return None
