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
#
# We only ever *enable* 1002 (report motion while a button is held) plus the SGR
# encoding 1006. 1003 (report every motion, button or not) floods ncurses' click
# resolution and makes it synthesize phantom clicks, and 1015 (urxvt encoding)
# conflicts with 1006: the terminal picks one encoding while ncurses decodes the
# other, which surfaces as random button states.
_MOUSE_ENABLE_MODES = ("1002", "1006")

# On reset we clear every mode we might have left behind, including ones set by
# a previous version or by the shell.
_MOUSE_DISABLE_MODES = ("1000", "1002", "1003", "1006", "1015")

def _write_terminal_sequence(sequence):
    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
    except (IOError, ValueError):
        pass

def _set_mouse_tracking(enabled):
    modes = _MOUSE_ENABLE_MODES if enabled else _MOUSE_DISABLE_MODES
    action = "h" if enabled else "l"
    _write_terminal_sequence("".join("\033[?" + mode + action for mode in modes))

def enable_selection():
    """Gives the mouse back to the terminal so the user can select text."""
    try:
        curses.mousemask(0)
    except curses.error:
        pass
    _set_mouse_tracking(False)

def disable_selection():
    """Grabs mouse events for the application (clicks, drags, wheel)."""
    # REPORT_MOUSE_POSITION is still needed in the mask so ncurses hands us the
    # drag events of mode 1002; the terminal only reports motion while a button
    # is held, so this does not flood us.
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    try:
        # Keep click resolution short: the longer the interval, the more press
        # events ncurses holds back to guess at clicks and double-clicks.
        curses.mouseinterval(120)
    except curses.error:
        pass
    _set_mouse_tracking(True)
