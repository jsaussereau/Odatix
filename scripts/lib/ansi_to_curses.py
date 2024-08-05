# ********************************************************************** #
#                               Asterism                                 #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

import curses
import re

LIGHT_OFFSET = 8

# Define ANSI codes for colors and attributes
ANSI_COLORS = {
  "0": -1,  # Reset
  "30": curses.COLOR_BLACK,
  "31": curses.COLOR_RED,
  "32": curses.COLOR_GREEN,
  "33": curses.COLOR_YELLOW,
  "34": curses.COLOR_BLUE,
  "35": curses.COLOR_MAGENTA,
  "36": curses.COLOR_CYAN,
  "37": curses.COLOR_WHITE,
  "90": curses.COLOR_BLACK + LIGHT_OFFSET,  # Light black (grey)
  "91": curses.COLOR_RED + LIGHT_OFFSET,  # Light red
  "92": curses.COLOR_GREEN + LIGHT_OFFSET,  # Light green
  "93": curses.COLOR_YELLOW + LIGHT_OFFSET,  # Light yellow
  "94": curses.COLOR_BLUE + LIGHT_OFFSET,  # Light blue
  "95": curses.COLOR_MAGENTA + LIGHT_OFFSET,  # Light magenta
  "96": curses.COLOR_CYAN + LIGHT_OFFSET,  # Light cyan
  "97": curses.COLOR_WHITE + LIGHT_OFFSET,  # Light white
}


def add_ansi_str(win, text):
  # Initialize colors in curses mode
  curses.start_color()
  curses.use_default_colors()
  curses.init_pair(1, -1, -1)
  for code, color in ANSI_COLORS.items():
    curses.init_pair(int(code), color, -1)

  # Attributes for text
  A_NORMAL = 0
  A_BOLD = curses.A_BOLD

  # Regular expression to find ANSI codes
  ansi_escape = re.compile(r"\x1b\[([0-9;]*)m")
  pos = 0
  color = 1  # Default color: white on black
  attr = A_NORMAL  # Default attribute

  while True:
    match = ansi_escape.search(text, pos)
    if match is None:
      win.addstr(text[pos:], attr | curses.color_pair(color))
      win.refresh()
      break

    # Display text before the next color code
    win.addstr(text[pos : match.start()], attr | curses.color_pair(color))
    pos = match.end()

    # Parse color code
    codes = match.group(1).split(";")
    for code in codes:
      if code == "1":
        attr |= A_BOLD
      elif code == "22":
        attr &= ~A_BOLD
      elif code == "0":
        attr = A_NORMAL
        color = 1
      elif code in ANSI_COLORS:
        color = int(code)

    # Display text with the specified color
    win.addstr("", attr | curses.color_pair(color))
