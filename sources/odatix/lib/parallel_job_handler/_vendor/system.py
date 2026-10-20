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
Small system helpers the job handler needs: finding a free port, opening a
directory in the file explorer. Odatix re-exports them from odatix.lib.utils.
"""

import os
import socket
import subprocess
import sys

from . import printc

def port_is_free(host, port):
    """
    Whether a server can listen on `host`:`port` right now.

    The probe sets SO_REUSEADDR, as the servers Odatix starts do (waitress,
    uvicorn): a port only held by connections in TIME_WAIT, which a server
    stopped a few seconds ago leaves behind, counts as free. Without it a
    restarted GUI would move to the next port for a minute or so.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name != "nt":
            # On Windows SO_REUSEADDR lets two sockets share a port: never set it there
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def find_free_port(host, start_port, max_find_port_attempts=100, strict=False, script_name=""):
    """
    Find a free port by incrementing from the start_port.

    With `strict`, `start_port` was asked for explicitly: if it is taken, say so
    and exit instead of moving to another port (a tunnel or a bookmark to that
    port would otherwise reach whatever listens there, or nothing).
    """
    if strict:
        if port_is_free(host, start_port):
            return start_port
        printc.error("port " + str(start_port) + " is already in use on " + str(host)
                     + ": choose another port with -p, or leave -p out to take the next free one", script_name)
        sys.exit(1)
    for port in range(start_port, start_port + max_find_port_attempts):
        if port_is_free(host, port):
            return port
    printc.error("Could not find any available port in range [" + str(start_port) + ":" + str(start_port + max_find_port_attempts - 1) + "]", script_name)
    sys.exit(-1)


def can_open_path_in_explorer():
    """Returns True if a file explorer can actually be opened on this system.

    On Linux, xdg-open needs a graphical session: without DISPLAY nor
    WAYLAND_DISPLAY (headless servers), opening a path would just fail.
    """
    if sys.platform.startswith("win") or sys.platform.startswith("darwin"):
        return True
    if sys.platform.startswith("linux"):
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return False

def open_path_in_explorer(path):
    """Opens the given path in the system file explorer."""
    if not can_open_path_in_explorer():
        raise NotImplementedError("No file explorer available on this system")

    if sys.platform.startswith("win"): # Windows
        os.startfile(path)
    elif sys.platform.startswith("linux"): # Linux
        subprocess.run(["xdg-open", path])
    elif sys.platform.startswith("darwin"): # macOS
        subprocess.run(["open", path])
    else:
        raise NotImplementedError("Unsupported platform: " + sys.platform)
