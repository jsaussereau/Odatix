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

import sys
import tty
import termios

def set_raw_mode():
  """
  Sets the terminal to raw mode, which allows reading input byte by byte without requiring Enter.
  This function saves the current terminal settings so they can be restored later.
  
  Returns:
    old_settings (list): The original terminal settings before switching to raw mode.
  """
  fd = sys.stdin.fileno()
  global old_settings
  old_settings = termios.tcgetattr(fd)
  tty.setraw(fd)
  return old_settings

def restore_mode(old_settings):
  """
  Restores the terminal to a previously saved state.

  Args:
    old_settings (list): The terminal settings to restore.
  """
  fd = sys.stdin.fileno()
  termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

class RawModeOutputWrapper:
  """
  A wrapper for sys.stdout that ensures compatibility with raw terminal mode.
  
  In raw mode, a newline character (`\n`) only moves the cursor to the next line
  but does not return it to the beginning of the line. This class intercepts all 
  output to sys.stdout and replaces every `\n` with the combination `\r\n`, 
  which moves the cursor both to the next line and back to the beginning.
  """
  def __init__(self, wrapped):
    self.wrapped = wrapped # The original sys.stdout or any file-like object to wrap/

  def write(self, text):
    """ 
    Replaces `\n` with `\r\n` and writes the modified text to the wrapped output
    """
    text = text.replace("\n", "\r\n")
    self.wrapped.write(text)

  def flush(self):
    """
    Flushes the wrapped output stream
    """
    self.wrapped.flush()
