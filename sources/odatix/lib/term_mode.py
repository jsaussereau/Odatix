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
import time

if sys.platform != "win32":
  import select
  import tty
  import termios
else:
  import msvcrt

def has_terminal():
  """
  Whether stdin is a terminal, i.e. whether there is a keyboard to read 'q'
  from. A server started in the background, under nohup or by a service
  manager reads from /dev/null, a file or a pipe instead.
  """
  if sys.platform == "win32":
    return True
  try:
    return sys.stdin is not None and sys.stdin.isatty()
  except (AttributeError, ValueError):
    return False

def set_raw_mode():
  """
  Sets the terminal to raw mode, which allows reading input byte by byte without requiring Enter.
  This function saves the current terminal settings so they can be restored later.

  Without a terminal there is no mode to change: nothing is done, and nothing
  will have to be restored.

  Returns:
    old_settings (list): The original terminal settings before switching to raw
      mode, or None when stdin is not a terminal.
  """
  if sys.platform != "win32":
    if not has_terminal():
      return None
    fd = sys.stdin.fileno()
    global old_settings
    try:
      old_settings = termios.tcgetattr(fd)
    except termios.error:
      return None
    tty.setraw(fd)
    return old_settings

def quit_hint(normal_term_mode):
  """How to stop a server, said once it is running."""
  if not has_terminal():
    return "not started from a terminal: end the process (Ctrl+C, kill) to stop the server"
  if normal_term_mode:
    return "press 'q', then enter to quit"
  return "press 'q' to quit"

def restore_mode(old_settings):
  """
  Restores the terminal to a previously saved state.

  Args:
    old_settings (list): The terminal settings to restore.
  """
  if sys.platform != "win32":
    fd = sys.stdin.fileno()
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def wait_for_quit_key(on_quit, server_thread):
  """
  Call `on_quit` when 'q' is pressed in the terminal, while the server runs.

  A server started without a terminal (in the background, stdin on /dev/null)
  sees end-of-file on stdin: it then has no key to wait for, and just waits for
  the server. Polling a stdin at end-of-file would spin a core forever.

  Args:
    on_quit (callable): what to do when 'q' is pressed.
    server_thread (Thread): the thread serving the app.
  """
  while True:
    if sys.platform == "win32":
      if msvcrt.kbhit():
        if msvcrt.getch().decode("utf-8", "replace").lower() == 'q':
          on_quit()
      else:
        time.sleep(0.5)
      continue
    try:
      ready = sys.stdin in select.select([sys.stdin], [], [], 0.5)[0]
      key = sys.stdin.read(1) if ready else None
    except (OSError, ValueError):
      key = ""
    if key == "":
      server_thread.join()
      return
    if key is not None and key.lower() == 'q':
      on_quit()

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

  def isatty(self):
    """Preserve TTY detection for callers relying on interactive output."""
    isatty = getattr(self.wrapped, "isatty", None)
    return bool(isatty()) if callable(isatty) else False

  def __getattr__(self, name):
    """Delegate unknown attributes/methods to the wrapped stream."""
    return getattr(self.wrapped, name)
