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

import os
import sys
import re
import queue
import fcntl
import curses
import select
import signal
import subprocess

from odatix.components.motd import read_version

from odatix.lib.ansi_to_curses import AnsiToCursesConverter
import odatix.lib.printc as printc

######################################
# Settings
######################################

STD_BUF = "stdbuf -oL "
script_name = os.path.basename(__file__)
error = None

NORMAL = 1
RED = 2
YELLOW = 3
GREEN = 4
BLUE = 5
CYAN = 6

REVERSE = 10
REVERSE_RED = 12
REVERSE_YELLOW = 13
REVERSE_GREEN = 14
REVERSE_BLUE = 15
REVERSE_CYAN = 16

class Theme:
  theme = {
    'ASCII_HIGHLIGHT': {
      'bar'               : '-',
      'border_left'       : ' [',
      'border_right'      : ']',
      'progress_empty'    : ' ',
      'progress_full'     : '#',
      'ballot_check'      : ' ',
      'ballot_empty'      : ' ',
      'selected_bold'     : True,
      'selected_reverse'  : True,
    },
    'ASCII': {
      'bar'               : '-',
      'border_left'       : ' [',
      'border_right'      : ']',
      'progress_empty'    : ' ',
      'progress_full'     : '#',
      'ballot_check'      : '[x] ',
      'ballot_empty'      : '[ ] ',
      'selected_bold'     : False,
      'selected_reverse'  : False,
    },
    'Legacy': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊',
      'progress_empty'    : '🮏',
      'progress_full'     : '▅',
      'ballot_check'      : ' ✔ ',
      'ballot_empty'      : ' ❏ ',
      'selected_bold'     : True,
      'selected_reverse'  : False,
    },
    'Arrow': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊',
      'progress_empty'    : ' ',
      'progress_full'     : '▮',
      'ballot_check'      : ' ➜ ',
      'ballot_empty'      : '   ',
      'selected_bold'     : True,
      'selected_reverse'  : False,
    },
    'Lines': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊',
      'progress_empty'    : ' ',
      'progress_full'     : '━',
      'ballot_check'      : ' ➜ ',
      'ballot_empty'      : '   ',
      'selected_bold'     : True,
      'selected_reverse'  : False,
    },
    'Slanted': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊',
      'progress_empty'    : '▱',
      'progress_full'     : '▰',
      'ballot_check'      : ' ▶ ',
      'ballot_empty'      : '   ',
      'selected_bold'     : True,
      'selected_reverse'  : False,
    },
    'Circle': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊',
      'progress_empty'    : '○',
      'progress_full'     : '●',
      'ballot_check'      : ' ● ',
      'ballot_empty'      : '   ',
      'selected_bold'     : True,
      'selected_reverse'  : False,
    },
    'Simple': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊',
      'progress_empty'    : '▭',
      'progress_full'     : '■',
      'ballot_check'      : ' ✔ ',
      'ballot_empty'      : ' ❏ ',
      'selected_bold'     : True,
      'selected_reverse'  : False,
    },
  }
  
  themes = list(theme.keys())

  def __init__(self, theme):
    if theme in Theme.themes:
      self.theme = theme
    else:
      raise ValueError(f"Unknown theme '{theme}'")

  def get(self, key):
    if self.theme not in Theme.themes:
      return '?'
    if key not in Theme.theme[self.theme]:
      return '?'
    return Theme.theme[self.theme][key]

  def next_theme(self):
    current_index = Theme.themes.index(self.theme)
    next_index = (current_index + 1) % len(Theme.themes)
    self.theme = Theme.themes[next_index]

######################################
# ParallelJob
######################################

class ParallelJob:
  status_file_pattern = re.compile(r"(.*)")
  progress_file_pattern = re.compile(r"(.*)")

  def __init__(
    self,
    process,
    command,
    directory,
    generate_rtl,
    generate_command,
    target,
    arch,
    display_name,
    status_file,
    progress_file,
    tmp_dir,
    progress_mode="default",
    status="not started",
  ):
    self.process = process
    self.command = command
    self.directory = directory
    self.generate_rtl = generate_rtl
    self.generate_command = generate_command
    self.target = target
    self.arch = arch
    self.display_name = display_name
    self.status_file = status_file
    self.progress_file = progress_file
    self.tmp_dir = tmp_dir
    self.progress_mode = progress_mode
    self.status = status

    self.log_history = []
    self.log_position = 0
    self.log_changed = False
    self.autoscroll = True

  @staticmethod
  def set_patterns(progress_file_pattern, status_file_pattern=None):
    ParallelJob.status_file_pattern = status_file_pattern
    ParallelJob.progress_file_pattern = progress_file_pattern

  def get_progress(self):
    if self.progress_mode == "fmax":
      return self.get_progress_fmax()
    else:
      progress = 0
      if os.path.isfile(self.progress_file):
        with open(self.progress_file, "r") as f:
          content = f.read()
        for match in re.finditer(ParallelJob.progress_file_pattern, content):
          parts = ParallelJob.progress_file_pattern.search(match.group())
          if len(parts.groups()) >= 2:
            progress = int(parts.group(2))
      if progress > 100:
        progress = 100
      return progress

  def get_progress_fmax(self):
    # Get progress from status file
    fmax_progress = 0
    fmax_step = 1
    fmax_totalstep = 1
    if os.path.isfile(self.status_file):
      with open(self.status_file, "r") as f:
        content = f.read()
      for match in re.finditer(ParallelJob.status_file_pattern, content):
        parts = ParallelJob.status_file_pattern.search(match.group())
        if len(parts.groups()) >= 4:
          fmax_progress = int(parts.group(2))
          fmax_step = int(parts.group(3))
          fmax_totalstep = int(parts.group(4))

    # Get progress from synth status file
    synth_progress = 0
    if os.path.isfile(self.progress_file):
      with open(self.progress_file, "r") as f:
        content = f.read()
      for match in re.finditer(ParallelJob.progress_file_pattern, content):
        parts = ParallelJob.progress_file_pattern.search(match.group())
        if len(parts.groups()) >= 2:
          synth_progress = int(parts.group(2))

    # Compute total progress
    if fmax_totalstep != 0:
      progress = fmax_progress + synth_progress / fmax_totalstep
    else:
      progress = synth_progress

    if progress > 100:
      progress = 100
    return progress


######################################
# ParallelJobHandler
######################################

class ParallelJobHandler:
  def __init__(self, job_list, nb_jobs=4, process_group=True, auto_exit=False, log_size_limit=200):
    self.job_list = job_list
    self.nb_jobs = nb_jobs
    self.process_group = process_group
    self.auto_exit = auto_exit
    self.log_size_limit = log_size_limit

    self.version = read_version()

    self.running_job_list = []
    self.retired_job_list = []
    self.job_queue = queue.Queue()
    self.selected_job_index = 0
    self.previous_log_size = 0
    self.max_title_length = max(len(job.display_name) for job in job_list)

    self.converter = AnsiToCursesConverter()

    # Initial calculation of max displayed jobs
    height, _ = curses.initscr().getmaxyx()
    self.job_count = len(self.job_list)
    displayed_jobs_cmd = height // 2 - 2 # Default to half the remaining screen height
    max_displayed_jobs = min(self.job_count, displayed_jobs_cmd)
    
    # Job list
    self.job_index_start = 0
    self.job_index_end = max_displayed_jobs

    self.theme = Theme('ASCII_HIGHLIGHT')

  @staticmethod
  def set_nonblocking(fd):
    try:
      fl = fcntl.fcntl(fd, fcntl.F_GETFL)
      fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    except TypeError:
      pass

  def progress_bar(self, window, id, progress, bar_width, title, title_size, width, status="", selected=False):
    bar_width = bar_width - title_size
    if bar_width < 4:
      bar_width = 4
      title_size = width - bar_width - 25
      if title_size < 0:
        title_size = 0

      if len(title) > title_size:
        title = title[: title_size - 3] + "..."
      else:
        title = title.ljust(title_size)
    else:
      title = title.ljust(title_size)

    bar_length = int(bar_width * progress / 100.0)
    percentage = f"{progress:.0f}%"
    comment = f"({status})"

    real_id = self.job_index_start  + id

    try:
      if real_id == self.selected_job_index and self.theme.get('selected_reverse'):
        window.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
        attr = curses.A_REVERSE | curses.A_BOLD
        offset = REVERSE
      else:
        attr = 0
        offset = 0

      button = self.theme.get('ballot_check') if selected else self.theme.get('ballot_empty')
      border_left = self.theme.get('border_left')
      border_right = self.theme.get('border_right')

      window.addstr(id, 0, f"{button}")
      if real_id == self.selected_job_index and self.theme.get('selected_bold'):
        window.attron(curses.color_pair(NORMAL) | curses.A_BOLD)
      window.addstr(id, len(button), f"{title}")
      window.attroff(curses.A_BOLD)
      window.addstr(id, len(button) + len(title), f"{border_left}")
      window.addstr(id, len(button) + len(title) + len(border_left), self.theme.get('progress_full') * bar_length)
      window.addstr(id, len(button) + len(title) + len(border_left) + bar_length, self.theme.get('progress_empty') * (bar_width - bar_length))

      pos = len(button) + len(title) + len(border_left) + bar_width + len(border_right)
      window.addstr(id, pos, " "*(width-pos-1))
      window.addstr(id, len(button) + len(title) + len(border_left) + bar_width, f"{border_right} {percentage}")

      comment_position = len(button) + len(title) + 3 + bar_width + 8
      if status == "failed":
        window.addstr(id, comment_position, comment, curses.color_pair(RED + offset) | attr)
      elif status == "running":
        window.addstr(id, comment_position, comment, curses.color_pair(YELLOW + offset) | attr)
      elif status == "success":
        window.addstr(id, comment_position, comment, curses.color_pair(GREEN + offset) | attr)
      elif status == "queued":
        window.addstr(id, comment_position, comment, curses.color_pair(BLUE + offset) | attr)
      elif status == "starting":
        window.addstr(id, comment_position, comment, curses.color_pair(CYAN + offset) | attr)
      else:
        window.addstr(id, comment_position, comment, curses.color_pair(NORMAL + offset) | attr)

    except curses.error as e:
      pass
    
    window.attroff(curses.A_REVERSE)
    window.attroff(curses.A_BOLD)

  def update_header(self, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width):
    try:
      header_win.hline(0, 0, " ", width, curses.color_pair(NORMAL) | curses.A_REVERSE)
      header_win.addstr(0, 1, "v" + str(self.version), curses.color_pair(NORMAL) | curses.A_REVERSE)
    except curses.error:
      pass
    if total_jobs_count == 1:
      if retired_jobs_count == total_jobs_count:
        text = "{}/{} job done!".format(retired_jobs_count, total_jobs_count)
      else:
        text = "{}/{} job done - {} running".format(retired_jobs_count, total_jobs_count, active_jobs_count)
    else:
      if retired_jobs_count == total_jobs_count:
        text = "{}/{} jobs done!".format(retired_jobs_count, total_jobs_count)
      else:
        text = "{}/{} jobs done - {} running".format(retired_jobs_count, total_jobs_count, active_jobs_count)
    try:
      header_win.addstr(0, width - len(text) - 1, text, curses.color_pair(NORMAL) | curses.A_REVERSE)
    except curses.error:
      pass

    try:
      header_win.addstr(
        0, (width - len(" Odatix ")) // 2, " Odatix ", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD
      )
    except curses.error:
      pass

    header_win.refresh()

  def update_progress_window(self, progress_win, selected_job):
    height, width = progress_win.getmaxyx()
    
    # Clear the window
    progress_win.erase()

    # Display the jobs within the visible range
    for id, job in enumerate(self.job_list[self.job_index_start:self.job_index_end]):
      selected = (self.selected_job_index == self.job_index_start + id)
      try:
        self.progress_bar(
          id=id,
          window=progress_win,
          progress=job.progress,
          bar_width=(width - 25),
          title=job.display_name,
          title_size=self.max_title_length,
          width=width,
          status=job.status,
          selected=selected,
        )
      except curses.error:
        pass
    progress_win.refresh()


  def update_separator(self, separator_win, val, ref, width):
      separator_win.erase()
      if val == ref:
        separator_text = self.theme.get("bar") * (width - 1)
      else:
        message = f"{val - ref} more" 
        padding = 4
        separator_text = self.theme.get("bar") * padding + message + self.theme.get("bar") * (width - len(message) - padding - 1)
      try:
        separator_win.addstr(0, 0, separator_text)
      except curses.error as e:
        pass
      separator_win.refresh()

  @staticmethod
  def update_help(help_win):
    help_win.erase()

    # Define the text with attributes
    help_text = [
      ("q", "Quit"),
      ("PageUp/PageDown", "Switch Job"),
      ("Up/Down", "Scroll Log"),
      ("Home/End", "Scroll to Top/Bottom"),
      ("+/-", "Adjust Progress Window"),
    ]

    help_win.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
    try:
      help_win.addstr(" ")
    except curses.error:
      pass

    for i, (key, description) in enumerate(help_text):
      try:
        if i > 0:
          help_win.addstr(" | ")
        help_win.attron(curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
        help_win.addstr(key)
        help_win.attroff(curses.A_BOLD)  # Remove attributes
        help_win.addstr(": ")
        help_win.addstr(description)
      except curses.error:
        pass

    try:
      help_win.addstr(" ")
    except curses.error:
      pass
    help_win.attroff(curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
    help_win.refresh()

  @staticmethod
  def show_exit_confirmation(help_win):
    try:
      help_win.erase()
      help_win.addstr(" Kill all jobs and exit: Yes (", curses.color_pair(NORMAL) | curses.A_REVERSE)
      help_win.addstr("y", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
      help_win.addstr(") / No (", curses.color_pair(NORMAL) | curses.A_REVERSE)
      help_win.addstr("n", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
      help_win.addstr(")? ", curses.color_pair(NORMAL) | curses.A_REVERSE)
      help_win.refresh()
    except curses.error:
      pass

    key = help_win.getch()
    curses.flushinp()
    if key == ord("y") or key == ord("Y"):
      return True, True
    elif key == ord("n") or key == ord("N"):
      return True, False
    else:
      return False, False

  @staticmethod
  def update_exit(help_win):
    try:
      help_win.erase()
      help_win.addstr(" Exiting... ", curses.color_pair(NORMAL) | curses.A_REVERSE)
      help_win.refresh()
    except curses.error:
      pass

  def update_logs(self, logs_win, selected_job, logs_height, width):
    history = selected_job.log_history
    log_length = len(history)

    # Erase lines extra lines from previous selected job
    if log_length < self.previous_log_size:
      for i in range(log_length, self.previous_log_size):
        try:
          logs_win.move(i, 0)
          logs_win.clrtoeol()
        except curses.error:
          pass

    # Logs from selected job
    for i, line in enumerate(history[selected_job.log_position : selected_job.log_position + logs_height]):
      try:
        logs_win.move(i, 0)
        logs_win.clrtoeol()
        self.converter.add_ansi_str(logs_win, line, width=width)
      except curses.error:
        pass

    logs_win.refresh()
    self.previous_log_size = log_length

  def start_job(self, job):
    # Run generate command
    if not job.generate_rtl:
      self.run_job(job)
      self.running_job_list.append(job)
      return

    try:
      job.log_history.append(printc.colors.CYAN + "Run generate command for " + job.display_name + printc.colors.ENDC)
      job.log_history.append(printc.colors.BOLD + " > " + job.generate_command + printc.colors.ENDC)

      process = subprocess.Popen(
        job.generate_command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=job.tmp_dir,
        shell=True,
        universal_newlines=True
      )

      self.set_nonblocking(process.stdout)
      self.set_nonblocking(process.stderr)

      job.process = process
      job.status = "starting"
      self.running_job_list.append(job)
    except subprocess.CalledProcessError:
      job.status = "failed"
      self.retire_job(job, progress=0)
      job.log_history.append(printc.colors.RED + "error: rtl generation failed" + printc.colors.ENDC)
      job.log_history.append(printc.colors.CYAN + "note: look for earlier error to solve this issue" + printc.colors.ENDC)
      return

  def click_on_job(self, progress_win, y, x):
    # Check if the click occured in progress_win
    if progress_win.enclose(y, x):
      # Get job index based on Y position
      relative_y = y - progress_win.getbegyx()[0]
      job_index = self.job_index_start + relative_y

      # Check if index is valid
      if 0 <= job_index < len(self.job_list):
        self.selected_job_index = job_index
        return True
    return False

  def run_job(self, job):
    job.log_history.append(printc.colors.CYAN + "Run job command" + printc.colors.ENDC)
    job.log_history.append(printc.colors.BOLD + " > " + job.command + printc.colors.ENDC)

    process = subprocess.Popen(
      STD_BUF + job.command,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      cwd=job.directory,
      shell=True,
      universal_newlines=True,
      bufsize=1,
      preexec_fn=os.setpgrp if self.process_group else None, 
    )

    self.set_nonblocking(process.stdout)
    self.set_nonblocking(process.stderr)

    job.process = process
    job.status = "running"

  def queue_job(self, job):
    job.status = "queued"
    self.job_queue.put(job)

  def retire_job(self, job, progress=100):
    self.running_job_list.remove(job)
    job.progress = progress
    self.retired_job_list.append(job)

  def terminate_all_jobs(self):
    for job in self.running_job_list:
      if job.process:
        try:  # Try to terminate the process group
          os.killpg(os.getpgid(job.process.pid), signal.SIGTERM)
        except ProcessLookupError:
          pass  # Process already terminated

    # Wait for all processes to finish
    for job in self.running_job_list:
      if job.process:
        job.process.wait()

  def curses_main(self, stdscr):
    curses.curs_set(0)  # Hide cursor

    # Enable mouse
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

    curses.start_color()
    curses.use_default_colors()

    # Define color pairs
    curses.init_pair(NORMAL, -1, -1)
    curses.init_pair(RED, curses.COLOR_RED, -1)
    curses.init_pair(YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(CYAN, curses.COLOR_CYAN, -1)

    curses.init_pair(REVERSE, curses.COLOR_BLACK, curses.COLOR_WHITE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_RED, -1, curses.COLOR_RED + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_YELLOW, -1, curses.COLOR_YELLOW + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_GREEN, -1, curses.COLOR_GREEN + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_BLUE, -1, curses.COLOR_BLUE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_CYAN, -1, curses.COLOR_CYAN + AnsiToCursesConverter.LIGHT_OFFSET)

    height, width = stdscr.getmaxyx()
    old_width = width
    old_height = height

    # Adjust window positions
    progress_height = self.job_index_end - self.job_index_start
    header_height = 1
    separator_height = 1
    help_height = 1
    logs_height = height - progress_height - 2*separator_height - help_height - header_height

    try:
      header_win = curses.newwin(header_height, width, 0, 0)
      separator_top_win = curses.newwin(separator_height, width, header_height, 0)
      progress_win = curses.newwin(progress_height, width, header_height + separator_height, 0)
      separator_middle_win = curses.newwin(separator_height, width, header_height + separator_height + progress_height, 0)
      logs_win = curses.newwin(logs_height, width, header_height + separator_height + progress_height + separator_height, 0)
      help_win = curses.newwin(help_height, width, height - help_height, 0)
    except curses.error:
      stdscr.clear()
      try:
        stdscr.addstr(0, 0, "Could not start: window is too small. Press any key to exit", curses.color_pair(RED))
        stdscr.refresh()
      except curses.error:
        pass
      stdscr.getch()
      sys.exit(-1)

    finished = False
    ask_exit = False

    selected_job = self.job_list[self.selected_job_index]

    for job in self.job_list:
      if len(self.running_job_list) < self.nb_jobs:
        self.start_job(job)
      else:
        self.queue_job(job)

    total_jobs_count = len(self.job_list)

    stdscr.nodelay(True)

    resize = False
    resize_hold = False

    while True:
      height, width = stdscr.getmaxyx()
      # If window size changes, adjust the layout
      if height != old_height or width != old_width or resize:
        try:
          progress_height = self.job_index_end - self.job_index_start
          logs_height = height - progress_height - 2*separator_height - help_height - header_height
          
          separator_top_win = curses.newwin(separator_height, width, header_height, 0)
          progress_win = curses.newwin(progress_height, width, header_height + separator_height, 0)
          separator_middle_win = curses.newwin(separator_height, width, header_height + separator_height + progress_height, 0)
          logs_win = curses.newwin(logs_height, width, header_height + separator_height + progress_height + separator_height, 0)
          help_win = curses.newwin(help_height, width, height - help_height, 0)

          self.update_logs(logs_win, selected_job, logs_height, width)
        except curses.error:
          try:
            stdscr.clear()
            stdscr.addstr(0, 0, "Window is too small!", curses.color_pair(RED))
            stdscr.refresh()
          except curses.error:
            pass

        old_width = width
        old_height = height
        resize = False

      # Check if all jobs have finished
      active_jobs_count = len(self.running_job_list)
      if active_jobs_count == 0:
        finished = True

      retired_jobs_count = len(self.retired_job_list)

      # Add a header
      self.update_header(header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width)

      # Add a separator
      self.update_separator(separator_top_win, self.job_index_start, 0, width)

      # Update job status and progress
      for job in self.job_list:
        if job in self.retired_job_list:
          job.progress = job.progress
        elif job not in self.running_job_list or job.process is None:
          job.progress = 0
        else: 
          job.progress = job.get_progress()
          if job.process.poll() is not None:
            if job.process.returncode == 0:
              if job.status == "starting":
                job.log_history.append("")
                self.run_job(job)
                continue
              else:
                job.status = "success"
            else:
              job.status = "failed"
              if job.progress is None:
                job.progress = 0

            self.retire_job(job, job.progress)
            if not self.job_queue.empty():
              self.start_job(self.job_queue.get())
              
            if job == selected_job:
              selected_job.log_changed = True
              self.update_logs(logs_win, selected_job, logs_height, width)

      # Update progress window
      self.update_progress_window(progress_win, selected_job)

      # Add a separator
      self.update_separator(separator_middle_win, self.job_count, self.job_index_end, width)

      # Collect all stdout and stderr pipes
      pipes = [job.process.stdout for job in self.running_job_list] + [
        job.process.stderr for job in self.running_job_list
      ]

      try:
        read_ready, _, _ = select.select(pipes, [], [], 0.1)
      except:
        read_ready = []

      for pipe in read_ready:
        for job in self.running_job_list:
          job.log_changed = False
          if pipe in (job.process.stdout, job.process.stderr):
            while True:
              line = pipe.readline()
              if line:
                job.log_history.append(line)
                # Apply log size limit
                if self.log_size_limit != -1 and len(job.log_history) > self.log_size_limit:
                  job.log_history = job.log_history[-self.log_size_limit :]
                job.log_changed = True
              else:
                break

      # Automatically scroll if at the bottom
      if selected_job.autoscroll and selected_job.log_changed:
        selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
        self.update_logs(logs_win, selected_job, logs_height, width)

      # Handle resize
      if width != old_width:
          self.update_logs(logs_win, selected_job, logs_height, width)
      old_width = width

      # Get inputs
      key = stdscr.getch()
      curses.flushinp()    

      def update_selected_job():
        job = self.job_list[self.selected_job_index]
        job.log_position = max(0, len(job.log_history) - logs_height)
        job.autoscroll = True
        return job

      def scroll_up_logs(selected_job):
        if selected_job.log_position > 0:
          selected_job.log_position = max(0, selected_job.log_position - 3)
          selected_job.autoscroll = False
          self.update_logs(logs_win, selected_job, logs_height, width)

      def scroll_down_logs(selected_job):
        if selected_job.log_position + logs_height < len(selected_job.log_history):
          selected_job.log_position = min(len(selected_job.log_history) - logs_height, selected_job.log_position + 3)
          selected_job.autoscroll = False
          self.update_logs(logs_win, selected_job, logs_height, width)

      def scroll_up_progress():
        self.job_index_start -= 1
        self.job_index_end -= 1

      def scroll_down_progress():
        self.job_index_start += 1
        self.job_index_end += 1

      if key == curses.KEY_MOUSE:
        _, x, y, _, button = curses.getmouse()

        if resize_hold:
          # Ensure the y-coordinate does not exceed the bounds of the terminal height
          y = min(y, height - 2)

          relative_y = y - (header_height + separator_height)
          new_job_index_end = self.job_index_start + relative_y

          # Minimum size
          if new_job_index_end <= self.job_index_start:
            self.job_index_end = self.job_index_start + 1
            resize = True
          # Exceeding job count
          elif new_job_index_end >= self.job_count:
            remainder = new_job_index_end - self.job_count
            self.job_index_end = self.job_count
            self.job_index_start = max(0, self.job_index_start - remainder)
            resize = True
          # General case
          else:
            self.job_index_end = new_job_index_end
            resize = True

        # Left click
        if button & curses.BUTTON1_CLICKED:
          # Check if user left clicked on a job
          if self.click_on_job(progress_win, y, x):
            selected_job = update_selected_job()
            self.update_logs(logs_win, selected_job, logs_height, width)

        # Hold separator
        elif button & curses.BUTTON1_PRESSED:
          if separator_middle_win.enclose(y, x):
            resize_hold = True

        # Release
        elif button & curses.BUTTON1_RELEASED:
          resize_hold = False

        # Scroll up
        elif button & curses.BUTTON4_PRESSED:
          if progress_win.enclose(y, x):
            if self.job_index_start > 0:
              scroll_up_progress()
          elif logs_win.enclose(y, x):
            scroll_up_logs(selected_job)

        # Scroll down
        elif button & curses.BUTTON5_PRESSED:
          if progress_win.enclose(y, x):
            if self.job_index_end <= len(self.job_list) - 1:
              scroll_down_progress()
          elif logs_win.enclose(y, x):
            scroll_down_logs(selected_job)
      
      # Page Up
      elif key == curses.KEY_PPAGE or key == ord("p") or key == ord("P"):  
        if self.selected_job_index > 0:
          self.selected_job_index -= 1
        if self.selected_job_index < self.job_index_start:
          scroll_up_progress()
        selected_job = update_selected_job()
        self.update_logs(logs_win, selected_job, logs_height, width)

      # Page Down
      elif key == curses.KEY_NPAGE or key == ord("n") or key == ord("N"):
        if self.selected_job_index < len(self.job_list) - 1:
          self.selected_job_index += 1
        if self.selected_job_index >= self.job_index_end:
          scroll_down_progress()
        selected_job = update_selected_job()
        self.update_logs(logs_win, selected_job, logs_height, width)

      # Scroll Up Logs
      elif key == curses.KEY_UP:
        scroll_up_logs(selected_job)

      # Scroll Down
      elif key == curses.KEY_DOWN:
        scroll_down_logs(selected_job)

      # Logs Home
      elif key == curses.KEY_HOME:
        selected_job.log_position = 0
        selected_job.autoscroll = False
        self.update_logs(logs_win, selected_job, logs_height, width)

      # Logs End
      elif key == curses.KEY_END:
        selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
        selected_job.autoscroll = True
        self.update_logs(logs_win, selected_job, logs_height, width)

      # Expand progress window
      elif key == ord("+") or key == ord("="): 
        if logs_height > 0:
          if self.job_index_end < self.job_count:
            self.job_index_end += 1
            resize = True
          elif self.job_index_start > 0:
            self.job_index_start -= 1
            resize = True

      # Shrink progress window
      elif key == ord("-") or key == ord("_"):
        if self.selected_job_index < self.job_index_end - 1:
          self.job_index_end -= 1
          resize = True
        elif self.job_index_start < self.job_index_end - 1:
          self.job_index_start += 1
          resize = True

      # Change theme
      elif key == ord("t") or key == ord("T"):
        self.theme.next_theme()

      # Exit
      else:
        if self.auto_exit and finished:
          return True
        else:
          if key == ord("q") or key == ord("Q"):
            if finished:
              return True
            else:
              ask_exit = True

      # Handle exit
      if ask_exit:
        user_answered, user_confirmed = self.show_exit_confirmation(help_win)
        if user_answered:
          if user_confirmed:
            self.update_exit(help_win)
            self.terminate_all_jobs()
            return False
          else:
            ask_exit = False
      else:
        self.update_help(help_win)

  def run(self):
    curses.wrapper(self.curses_main)
