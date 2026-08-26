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
# We only ever *enable* one motion mode at a time plus the SGR encoding 1006:
#   - 1002 reports motion only while a button is held (drags),
#   - 1003 reports every motion, which is what hover effects need.
# 1003 makes ncurses see far more events, so it is only turned on when the UI
# actually wants hover feedback. 1015 (urxvt encoding) is never enabled: it
# conflicts with 1006, the terminal picks one encoding while ncurses decodes the
# other, which surfaces as random button states.
_MOUSE_DRAG_MODE = "1002"
_MOUSE_HOVER_MODE = "1003"

# On reset we clear every mode we might have left behind, including ones set by
# a previous version or by the shell.
_MOUSE_DISABLE_MODES = ("1000", "1002", "1003", "1006", "1015")

def _write_terminal_sequence(sequence):
    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
    except (IOError, ValueError):
        pass

def _set_mouse_tracking(enabled, track_motion=False):
    if not enabled:
        _write_terminal_sequence("".join("\033[?" + mode + "l" for mode in _MOUSE_DISABLE_MODES))
        return
    # Switching between the two motion modes means turning the other one off
    # explicitly: leaving both set makes the terminal keep the more verbose one.
    if track_motion:
        on, off = _MOUSE_HOVER_MODE, _MOUSE_DRAG_MODE
    else:
        on, off = _MOUSE_DRAG_MODE, _MOUSE_HOVER_MODE
    _write_terminal_sequence("\033[?" + off + "l\033[?" + on + "h\033[?1006h")


def enable_selection():
    """Gives the mouse back to the terminal so the user can select text."""
    try:
        curses.mousemask(0)
    except curses.error:
        pass
    _set_mouse_tracking(False)

def disable_selection(track_motion=False):
    """Grabs mouse events for the application (clicks, drags, wheel).

    With `track_motion`, the terminal also reports pointer motion when no button
    is held, which is what hover feedback needs.
    """
    # REPORT_MOUSE_POSITION is needed in the mask so ncurses hands us the motion
    # reports of modes 1002 and 1003 at all.
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    try:
        # No click resolution at all: with a non-zero interval ncurses holds
        # press events back to guess at clicks and double-clicks, and drops
        # some of them when motion reports arrive meanwhile, which shows up as
        # clicks that do nothing. We get raw press/release events instead and
        # do our own click and double-click detection.
        curses.mouseinterval(0)
    except curses.error:
        pass
    _set_mouse_tracking(True, track_motion=track_motion)
