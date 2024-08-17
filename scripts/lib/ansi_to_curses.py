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
import re


A_NORMAL = 0


class AnsiToCursesConverter:
  LIGHT_OFFSET = 8

  # Define ANSI codes for colors and attributes
  ANSI_COLORS = {
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

  def __init__(self):
    self.current_color = None
    self.current_intensity = 0
    self.initialized = False

  def initialize_colors(self):
    if not self.initialized:
      curses.start_color()
      curses.use_default_colors()
      for code, color in AnsiToCursesConverter.ANSI_COLORS.items():
        if color != -1:
          curses.init_pair(int(code), color, -1)
      self.current_color = curses.color_pair(0)
      self.initialized = True

  def add_ansi_str(self, win, text, debug_win=None, width=-1):
    self.initialize_colors()

    # Regular expression to find ANSI escape sequences
    ansi_escape = re.compile(r"\x1b\[([0-9;]*)m")

    # Find all ANSI codes and normal text
    segments = ansi_escape.split(text)

    current_width = 0
    truncated = False

    for i, segment in enumerate(segments):
      if i % 2 == 0:
        # Normal text segment
        if width > 0:
          remaining_width = width - current_width
          if remaining_width > 0:
            if len(segment) > remaining_width:
              segment = segment[:remaining_width-3]
              truncated = True
            current_width += len(segment)
            win.addstr(segment, self.current_color | self.current_intensity)
          if truncated:
            win.addstr("...", curses.color_pair(90))
        else:
          win.addstr(segment, self.current_color | self.current_intensity)
      else:
        # ANSI code segment
        codes = segment.split(";")
        for code in codes:
          if code in AnsiToCursesConverter.ANSI_COLORS:
            color_pair = curses.color_pair(int(code))
            self.current_color = color_pair  # Use the new color
          elif code == "0":  # Reset code
            self.current_color = curses.color_pair(0)  # Reset to default color and attributes
            self.current_intensity = A_NORMAL
          elif code == "1":  # Bold code
            self.current_intensity = curses.A_BOLD
          elif code == "22":  # Normal intensity
            self.current_intensity = A_NORMAL
          else:
            if debug_win is not None:
              debug_win.addstr("{Unsupported ANSI escape code:" + code + "}", curses.color_pair(31))

    win.refresh()
    if debug_win is not None:
      debug_win.refresh()

  def test(self, stdscr):
    stdscr.clear()
    text = " default_text\n \x1b[1m\x1b[31mbold_red_text\x1b[0m\n \x1b[34mblue_and_\x1b[32mgreen_text\n \x1b[31mred_text\n \x1b[0mdefault_text\n \x1b[52merror_text"
    height, width = stdscr.getmaxyx()

    # Ensure the text fits within the window width
    self.add_ansi_str(stdscr, text, width=width)

    # Wait for a key press to exit
    stdscr.getch()


if __name__ == "__main__":
  conv = AnsiToCursesConverter()
  curses.wrapper(conv.test)
