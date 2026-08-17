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

import curses
import sys

CTRL_D = 4

# XTerm mouse tracking modes. As long as any of them is set, the terminal sends
# mouse events to the application instead of handling text selection itself, so
# a click-drag gets interrupted. ncurses does not reliably emit the "reset"
# sequences when the mouse mask is cleared, so we write them out explicitly.
_MOUSE_TRACKING_MODES = ("1000", "1002", "1003", "1006", "1015")

def _write_terminal_sequence(sequence):
    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
    except (IOError, ValueError):
        pass

def _set_mouse_tracking(enabled):
    action = "h" if enabled else "l"
    _write_terminal_sequence("".join("\033[?" + mode + action for mode in _MOUSE_TRACKING_MODES))

def enable_selection():
    """Gives the mouse back to the terminal so the user can select text."""
    try:
        curses.mousemask(0)
    except curses.error:
        pass
    _set_mouse_tracking(False)

def disable_selection():
    """Grabs mouse events for the application (clicks, drags, wheel)."""
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    _set_mouse_tracking(True)
