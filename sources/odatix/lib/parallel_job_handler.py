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

    return progress


######################################
# ParallelJobHandler
######################################

class ParallelJobHandler:
  def __init__(self, job_list, nb_jobs=4, process_group=True, auto_exit=False, log_size_limit=100):
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

  @staticmethod
  def set_nonblocking(fd):
    try:
      fl = fcntl.fcntl(fd, fcntl.F_GETFL)
      fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    except TypeError:
      pass

  @staticmethod
  def progress_bar(window, id, progress, bar_width, title, title_size, width, status="", selected=False):
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

    try:
      button = "[*]" if selected else "[ ]"
      window.addstr(id, 0, f"{button} {title} [")
      window.addstr(id, len(button) + len(title) + 3, "#" * bar_length, curses.color_pair(1))
      window.addstr(id, len(button) + len(title) + 3 + bar_length, " " * (bar_width - bar_length), curses.color_pair(1))
      window.addstr(id, len(button) + len(title) + 3 + bar_width, f"] {percentage}")

      comment_position = len(button) + len(title) + 3 + bar_width + 8
      if status == "failed":
        window.addstr(id, comment_position, comment, curses.color_pair(2))
      elif status == "running":
        window.addstr(id, comment_position, comment, curses.color_pair(3))
      elif status == "success":
        window.addstr(id, comment_position, comment, curses.color_pair(4))
      elif status == "queued":
        window.addstr(id, comment_position, comment, curses.color_pair(5))
      elif status == "starting":
        window.addstr(id, comment_position, comment, curses.color_pair(6))
      else:
        window.addstr(id, comment_position, comment, curses.color_pair(1))
    except curses.error as e:
      print(f"curses.error: {e}")

  def update_header(self, header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width):
    header_win.hline(0, 0, " ", width, curses.color_pair(1) | curses.A_REVERSE)
    try:
      header_win.addstr(0, 1, "v" + str(self.version), curses.color_pair(1) | curses.A_REVERSE)
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
      header_win.addstr(0, width - len(text) - 1, text, curses.color_pair(1) | curses.A_REVERSE)
    except curses.error:
      pass

    try:
      header_win.addstr(
        0, (width - len(" Odatix ")) // 2, " Odatix ", curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD
      )
    except curses.error:
      pass
    header_win.hline(1, 0, "-", width)
    header_win.refresh()

  @staticmethod
  def update_help(help_win):
    help_win.erase()

    # Define the text with attributes
    help_text = [
      ("q", "Quit"),
      ("PageUp/PageDown", "Switch Process"),
      ("Up/Down", "Scroll Log"),
      ("Home/End", "Scroll to Top/Bottom"),
    ]

    help_win.attron(curses.color_pair(1) | curses.A_REVERSE)
    help_win.addstr(" ")

    for i, (key, description) in enumerate(help_text):
      try:
        if i > 0:
          help_win.addstr(" | ")
        help_win.attron(curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD)
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
    help_win.attroff(curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD)
    help_win.refresh()

  @staticmethod
  def show_exit_confirmation(help_win):
    help_win.erase()
    help_win.addstr(" Kill all jobs and exit: Yes (", curses.color_pair(1) | curses.A_REVERSE)
    help_win.addstr("y", curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD)
    help_win.addstr(") / No (", curses.color_pair(1) | curses.A_REVERSE)
    help_win.addstr("n", curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD)
    help_win.addstr(")? ", curses.color_pair(1) | curses.A_REVERSE)
    help_win.refresh()

    key = help_win.getch()
    curses.flushinp()
    if key == ord("y"):
      return True, True
    elif key == ord("n"):
      return True, False
    else:
      return False, False

  @staticmethod
  def update_exit(help_win):
    help_win.erase()
    help_win.addstr(" Exiting... ", curses.color_pair(1) | curses.A_REVERSE)
    help_win.refresh()

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

    curses.start_color()
    curses.use_default_colors()

    # Define color pairs
    curses.init_pair(1, -1, -1)
    curses.init_pair(2, curses.COLOR_RED, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_GREEN, -1)
    curses.init_pair(5, curses.COLOR_BLUE, -1)
    curses.init_pair(6, curses.COLOR_CYAN, -1)
    curses.init_pair(10, curses.COLOR_BLACK, curses.COLOR_WHITE + AnsiToCursesConverter.LIGHT_OFFSET)

    height, width = stdscr.getmaxyx()
    old_width = width
    old_height = height

    header_height = 2

    # Adjust window positions
    progress_height = len(self.job_list)
    separator_height = 1
    help_height = 1
    logs_height = height - progress_height - separator_height - help_height - header_height

    try:
      header_win = curses.newwin(header_height, width, 0, 0)
      progress_win = curses.newwin(progress_height, width, header_height, 0)
      separator_win = curses.newwin(separator_height, width, header_height + progress_height, 0)
      logs_win = curses.newwin(logs_height, width, header_height + progress_height + separator_height, 0)
      help_win = curses.newwin(help_height, width, height - help_height, 0)
    except curses.error:
      stdscr.clear()
      stdscr.addstr(0, 0, "Could not start: window is too small. Press any key to exit", curses.color_pair(2))
      stdscr.refresh()
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

    while True:
      # Check if all jobs have finished
      active_jobs_count = len(self.running_job_list)
      if active_jobs_count == 0:
        finished = True

      retired_jobs_count = len(self.retired_job_list)

      # Add a header
      self.update_header(header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width)

      progress_win.erase()
      height, width = progress_win.getmaxyx()
      for id, job in enumerate(self.job_list):

        if job in self.retired_job_list:
          progress = job.progress
        elif job not in self.running_job_list or job.process is None:
          progress = 0
        else:
          progress = job.get_progress()
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
              if progress is None:
                progress = 0

            self.retire_job(job, progress)
            if not self.job_queue.empty():
              self.start_job(self.job_queue.get())
              
            if job == selected_job:
              selected_job.log_changed = True
              self.update_logs(logs_win, selected_job, logs_height, width)
        try:
          self.progress_bar(
            id=id,
            window=progress_win,
            progress=progress,
            bar_width=(width - 25),
            title=job.display_name,
            title_size=self.max_title_length,
            width=width,
            status=job.status,
            selected=(id == self.selected_job_index),
          )
        except curses.error:
          pass
      progress_win.refresh()

      # Add a separator
      separator_win.erase()
      separator_win.hline(0, 0, "-", width)
      separator_win.refresh()

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

      if key == curses.KEY_PPAGE:  # Page Up
        if self.selected_job_index > 0:
          self.selected_job_index -= 1
          selected_job = self.job_list[self.selected_job_index]
          selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
          selected_job.autoscroll = True
          self.update_logs(logs_win, selected_job, logs_height, width)
      elif key == curses.KEY_NPAGE:  # Page Down
        if self.selected_job_index < len(self.job_list) - 1:
          self.selected_job_index += 1
          selected_job = self.job_list[self.selected_job_index]
          selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
          selected_job.autoscroll = True
          self.update_logs(logs_win, selected_job, logs_height, width)
      elif key == curses.KEY_UP:  # Scroll Up
        if selected_job.log_position > 0:
          selected_job.log_position = max(0, selected_job.log_position - 3)
          selected_job.autoscroll = False
          self.update_logs(logs_win, selected_job, logs_height, width)
      elif key == curses.KEY_DOWN:  # Scroll Down
        if selected_job.log_position + logs_height < len(selected_job.log_history):
          selected_job.log_position = min(len(selected_job.log_history) - logs_height, selected_job.log_position + 3)
          selected_job.autoscroll = False
          self.update_logs(logs_win, selected_job, logs_height, width)
      elif key == curses.KEY_HOME:  # Home
        selected_job.log_position = 0
        selected_job.autoscroll = False
        self.update_logs(logs_win, selected_job, logs_height, width)
      elif key == curses.KEY_END:  # End
        selected_job.log_position = max(0, len(selected_job.log_history) - logs_height)
        selected_job.autoscroll = True
        self.update_logs(logs_win, selected_job, logs_height, width)
      else:
        if self.auto_exit and finished:
          return True
        else:
          if key == ord("q"):
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
