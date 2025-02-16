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

  # Mapping of ANSI color codes to curses color pairs
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
    """
    Initialize color pairs in curses.
    """
    if not self.initialized:
      curses.start_color()
      curses.use_default_colors()
      for code, color in AnsiToCursesConverter.ANSI_COLORS.items():
        if color != -1:
          curses.init_pair(int(code), color, -1)
      self.current_color = curses.color_pair(0)
      self.initialized = True

  def reset_format(self):
    """
    Reset the current formatting attributes.

    This method resets both the color and intensity attributes to their default values,
    ensuring that subsequent text is displayed without inherited styles.

    Effects:
        - Sets `self.current_color` to the default color pair (curses.color_pair(0)).
        - Sets `self.current_intensity` to `A_NORMAL`.

    Use this method when:
        - Resetting styles after processing ANSI escape sequences.
        - Ensuring consistent formatting when switching contexts.
    """
    self.current_color = curses.color_pair(0)
    self.current_intensity = A_NORMAL

  def add_ansi_str(self, win, text, debug_win=None, width=-1, dim=False):
    """
    Add a string with ANSI escape sequences to a curses window.

    Args:
        win (curses.window): The window where text is displayed.
        text (str): The text containing ANSI escape sequences.
        debug_win (curses.window, optional): Window for debugging output.
        width (int, optional): Maximum width of the displayed text.
        dim (bool, optional): Apply dim effect.
    """
    self.initialize_colors()

    # Regex to match ANSI escape sequences
    ansi_escape = re.compile(r"\x1b\[([0-9;]*)m")

    # Split text by ANSI codes
    segments = ansi_escape.split(text)

    current_width = 0
    truncated = False
    dim = dim and curses.A_DIM

    # Clear line before writing new text to prevent color bleeding
    win.clrtoeol()

    for i, segment in enumerate(segments):
      if i % 2 == 0:
        # Normal text
        if width > 0:
          remaining_width = width - current_width
          if remaining_width > 0:
            if len(segment) > remaining_width:
              segment = segment[:remaining_width-3]
              truncated = True
            current_width += len(segment)
            win.addstr(segment, self.current_color | self.current_intensity | dim)
          if truncated:
            win.addstr("...", curses.color_pair(90) | dim)
        else:
          win.addstr(segment, self.current_color | self.current_intensity | dim)
      else:
        # ANSI code processing
        codes = segment.split(";")
        for code in codes:
          if code in AnsiToCursesConverter.ANSI_COLORS:
            color_pair = curses.color_pair(int(code))
            self.current_color = color_pair
          elif code == "0":  # Reset all attributes
            self.current_color = curses.color_pair(0)
            self.current_intensity = A_NORMAL
          elif code == "1":  # Bold
            self.current_intensity = curses.A_BOLD
          elif code == "22":  # Normal intensity
            self.current_intensity = A_NORMAL
          else:
            if debug_win is not None:
              debug_win.addstr(f"Unsupported ANSI code: {code}", curses.color_pair(31) | dim)

    # Refresh the window after updates
    win.refresh()
    if debug_win is not None:
      debug_win.refresh()

  def test(self, stdscr):
    """
    Test function to display formatted text with ANSI escape sequences.

    Args:
        stdscr (curses.window): The standard screen window.
    """
    stdscr.clear()
    text = " default_text\n \x1b[1m\x1b[31mbold_red_text\x1b[0m\n \x1b[34mblue_and_\x1b[32mgreen_text\n \x1b[31mred_text\n \x1b[0mdefault_text\n \x1b[52merror_text"
    height, width = stdscr.getmaxyx()

    # Ensure the text fits within the window width
    self.add_ansi_str(stdscr, text, width=width)

    # Wait for user input
    stdscr.getch()


if __name__ == "__main__":
  conv = AnsiToCursesConverter()
  curses.wrapper(conv.test)
