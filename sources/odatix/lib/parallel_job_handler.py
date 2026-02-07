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
import time
import queue
import select
import signal
import subprocess
import curses
import locale
import io
import threading

if sys.platform == "win32":
  import msvcrt
  import time
  import ctypes
  import threading
  STD_BUF = ""
else:
  import fcntl
  STD_BUF = ""

from odatix.components.motd import read_version

from odatix.lib.curses_helper import enable_selection, disable_selection
from odatix.lib.ansi_to_curses import AnsiToCursesConverter
from odatix.lib.job_output_formatter import JobOutputFormatter
from odatix.lib.utils import open_path_in_explorer
import odatix.lib.printc as printc

ENCODING = locale.getpreferredencoding()

# Handle BUTTON5_PRESSED missing in some curses versions
if not hasattr(curses, "BUTTON5_PRESSED"):
  curses.BUTTON5_PRESSED = 2097152

if sys.platform == "win32":
  ENCODING = "utf-8"
  old_stdout = sys.stdout
  old_stderr = sys.stderr
  sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=ENCODING, errors="replace")
  sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding=ENCODING, errors="replace")

######################################
# Settings
######################################

script_name = os.path.basename(__file__)
error = None

NORMAL = 1
RED = 2
YELLOW = 3
GREEN = 4
BLUE = 5
CYAN = 6
BLACK = 7
WHITE = 8
GREY = 9

REVERSE = 10
REVERSE_RED = 12
REVERSE_YELLOW = 13
REVERSE_GREEN = 14
REVERSE_BLUE = 15
REVERSE_CYAN = 16
REVERSE_BLACK = 17
REVERSE_WHITE = 18
REVERSE_GREY = 19

class Theme:
  theme = {
    'Color_Boxes': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊ ',
      'progress_empty'    : '▅',
      'progress_full'     : '▅',
      'ballot_check'      : '➜ ',
      'ballot_empty'      : '  ',
      'spacer'            : ' ∙ ',
      'ellipsis'          : '…',
      'selected_bold'     : True,
      'selected_reverse'  : False,
      'colored_bar'       : True,
      'dim_empty_bar'     : True,
      'reserved_space'    : 32,
    },
    'ASCII_Highlight': {
      'bar'               : '-',
      'border_left'       : ' [',
      'border_right'      : '] ',
      'progress_empty'    : ' ',
      'progress_full'     : '#',
      'ballot_check'      : ' ',
      'ballot_empty'      : ' ',
      'spacer'            : '  ',
      'ellipsis'          : '...',
      'selected_bold'     : True,
      'selected_reverse'  : True,
      'colored_bar'       : False,
      'dim_empty_bar'     : False,
      'reserved_space'    : 29,
    },
    'ASCII_Highlight_Color': {
      'bar'               : '-',
      'border_left'       : ' [',
      'border_right'      : '] ',
      'progress_empty'    : ' ',
      'progress_full'     : '#',
      'ballot_check'      : ' ',
      'ballot_empty'      : ' ',
      'spacer'            : '  ',
      'ellipsis'          : '...',
      'selected_bold'     : True,
      'selected_reverse'  : True,
      'colored_bar'       : True,
      'dim_empty_bar'     : False,
      'reserved_space'    : 29,
    },
    'Color_Lines': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊ ',
      'progress_empty'    : '━',
      'progress_full'     : '━',
      'ballot_check'      : ' ➜ ',
      'ballot_empty'      : '   ',
      'spacer'            : '  ',
      'ellipsis'          : '…',
      'selected_bold'     : True,
      'selected_reverse'  : False,
      'colored_bar'       : True,
      'dim_empty_bar'     : True,
      'reserved_space'    : 31,
    },
    'Legacy': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊ ',
      'progress_empty'    : '🮏',
      'progress_full'     : '▅',
      'ballot_check'      : ' ✔ ',
      'ballot_empty'      : ' ❏ ',
      'spacer'            : '  ',
      'ellipsis'          : '…',
      'selected_bold'     : True,
      'selected_reverse'  : False,
      'colored_bar'       : False,
      'dim_empty_bar'     : False,
      'reserved_space'    : 31,
    },
    'Rectangles': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊ ',
      'progress_empty'    : ' ',
      'progress_full'     : '▮',
      'ballot_check'      : ' ➜ ',
      'ballot_empty'      : '   ',
      'spacer'            : '  ',
      'ellipsis'          : '…',
      'selected_bold'     : True,
      'selected_reverse'  : False,
      'colored_bar'       : False,
      'dim_empty_bar'     : False,
      'reserved_space'    : 31,
    },
    'Rectangles_Color': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊ ',
      'progress_empty'    : '▮',
      'progress_full'     : '▮',
      'ballot_check'      : ' ➜ ',
      'ballot_empty'      : '   ',
      'spacer'            : '  ',
      'ellipsis'          : '…',
      'selected_bold'     : True,
      'selected_reverse'  : False,
      'colored_bar'       : True,
      'dim_empty_bar'     : True,
      'reserved_space'    : 31,
    },
    'Simple': {
      'bar'               : '─',
      'border_left'       : ' ┊',
      'border_right'      : '┊ ',
      'progress_empty'    : '▭',
      'progress_full'     : '■',
      'ballot_check'      : ' ✔ ',
      'ballot_empty'      : ' ❏ ',
      'spacer'            : '  ',
      'ellipsis'          : '…',
      'selected_bold'     : True,
      'selected_reverse'  : False,
      'colored_bar'       : False,
      'dim_empty_bar'     : False,
      'reserved_space'    : 31,
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
# OS specific functions
######################################

def read_pipe_windows(pipe, job):
  while True:
    try:
      data = pipe.readline()
      if not data:
        break
      job.log_history.append(data)
      if job.log_size_limit != -1 and len(job.log_history) > job.log_size_limit:
        job.log_history = job.log_history[-job.log_size_limit:]
      job.log_changed = True
    except OSError:
      break

######################################
# ParallelJob
######################################

def get_elapsed_time_str(job_start_time, job_stop_time):
  if job_start_time is not None:
    if job_stop_time is not None:
      stop_time = job_stop_time
    else:
      stop_time = time.time()
    elapsed_seconds = int(stop_time - job_start_time)
    days = elapsed_seconds // 86400
    hours = (elapsed_seconds % 86400) // 3600
    minutes = (elapsed_seconds % 3600) // 60
    seconds = elapsed_seconds % 60
    if days > 0:
      elapsed_time = f"{days}d+{hours:02}:{minutes:02}" # Format Days+HH:MM
    else:
      elapsed_time = f"{hours:02}:{minutes:02}:{seconds:02}" # Format HH:MM:SS
  else:
    elapsed_time = "00:00:00"
  return elapsed_time

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
    log_size_limit,
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
    self.log_size_limit = log_size_limit
    self.progress_mode = progress_mode
    self.status = status

    self.log_history = []
    self.log_position = 0
    self.log_changed = False
    self.autoscroll = True

    self.start_time = None
    self.stop_time = None

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

  def pause(self):
    """Suspend the job execution."""
    if self.process and self.status == "running":
      os.killpg(os.getpgid(self.process.pid), signal.SIGSTOP) # Suspend process
      self.status = "paused"
      self.stop_time = time.time()
      self.log_history.append(printc.colors.BLUE + "Job paused by user" + printc.colors.ENDC)

  def resume(self):
    """Resume the job execution."""
    if self.process and self.status == "paused":
      os.killpg(os.getpgid(self.process.pid), signal.SIGCONT) # Resume execution
      self.status = "running"
      self.start_time += time.time() - self.stop_time # Adjust the start time to reflect the paused duration
      self.stop_time = None
      self.log_history.append(printc.colors.GREEN + "Job resumed by user" + printc.colors.ENDC)

######################################
# ParallelJobHandler
######################################

class ParallelJobHandler:
  def __init__(self, job_list, nb_jobs=4, process_group=True, auto_exit=False, format_yaml=None, log_size_limit=200):
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

    self.selection_enabled = False

    self.converter = AnsiToCursesConverter()
    if format_yaml is not None:
      self.formatter = JobOutputFormatter(format_yaml)
    else:
      self.formatter = None

    # Initial calculation of max displayed jobs
    height, _ = curses.initscr().getmaxyx()
    self.job_count = len(self.job_list)
    displayed_jobs_cmd = height // 2 - 2 # Default to half the remaining screen height
    max_displayed_jobs = min(self.job_count, displayed_jobs_cmd)
    
    # Job list
    self.job_index_start = 0
    self.job_index_end = max_displayed_jobs

    try:
      print(" ")
      self.theme = Theme('Color_Boxes')
    except:
      self.theme = Theme('ASCII_Highlight')

    # Headless / API control state (thread-safe)
    self._lock = threading.RLock()
    self._command_queue = queue.Queue()
    self._stop_event = threading.Event()
    self._headless_thread = None
    self._headless_running = False
    self._headless_initialized = False
    self._headless_logs_height = 40
    self.showing_help = False

    # API server (optional)
    self._api_thread = None
    self._api_server = None

  ######################################
  # Headless control / snapshot API
  ######################################

  def snapshot(self, logs_job_id=None, logs_offset=None, logs_limit=None):
    """Return a JSON-serializable snapshot of handler + job state.

    If logs_job_id is None, returns logs for the selected job.
    """
    with self._lock:
      jobs = []
      for idx, job in enumerate(self.job_list):
        jobs.append(
          {
            "id": idx,
            "display_name": job.display_name,
            "status": job.status,
            "progress": getattr(job, "progress", 0),
            "directory": job.directory,
            "tmp_dir": job.tmp_dir,
            "target": job.target,
            "arch": job.arch,
            "elapsed_time": get_elapsed_time_str(job.start_time, job.stop_time),
          }
        )

      selected_id = int(self.selected_job_index)
      if logs_job_id is None:
        logs_job_id = selected_id

      logs = None
      if 0 <= int(logs_job_id) < len(self.job_list):
        job = self.job_list[int(logs_job_id)]
        history = list(job.log_history)
        total = len(history)

        if logs_offset is None:
          logs_offset = job.log_position
        if logs_limit is None:
          logs_limit = self._headless_logs_height

        logs_offset = max(0, int(logs_offset))
        logs_limit = int(logs_limit)

        if logs_limit < 0:
          # Special case: full log from offset
          lines = history[logs_offset:]
        else:
          logs_limit = max(0, logs_limit)
          lines = history[logs_offset : logs_offset + logs_limit]

        logs = {
          "job_id": int(logs_job_id),
          "total_lines": total,
          "offset": logs_offset,
          "limit": logs_limit,
          "log_position": job.log_position,
          "autoscroll": job.autoscroll,
          "lines": lines,
        }

      return {
        "handler": {
          "version": str(self.version),
          "nb_jobs": int(self.nb_jobs),
          "process_group": bool(self.process_group),
          "auto_exit": bool(self.auto_exit),
          "selected_job_index": selected_id,
          "job_count": int(self.job_count),
          "running": len(self.running_job_list),
          "queued": int(self.job_queue.qsize()),
          "retired": len(self.retired_job_list),
          "theme": getattr(self.theme, "theme", None),
        },
        "jobs": jobs,
        "logs": logs,
      }

  def select_job(self, job_id: int):
    with self._lock:
      job_id = int(job_id)
      if job_id < 0 or job_id >= len(self.job_list):
        raise IndexError("job_id out of range")
      self.selected_job_index = job_id
      job = self.job_list[self.selected_job_index]
      job.log_position = max(0, len(job.log_history) - self._headless_logs_height)
      job.autoscroll = True

  def scroll_logs(self, job_id: int, delta: int):
    with self._lock:
      job = self.job_list[int(job_id)]
      if delta == 0:
        return
      job.log_position = max(0, job.log_position + int(delta))
      max_start = max(0, len(job.log_history) - self._headless_logs_height)
      job.log_position = min(job.log_position, max_start)
      job.autoscroll = False

  def logs_home(self, job_id: int):
    with self._lock:
      job = self.job_list[int(job_id)]
      job.log_position = 0
      job.autoscroll = False

  def logs_end(self, job_id: int):
    with self._lock:
      job = self.job_list[int(job_id)]
      job.log_position = max(0, len(job.log_history) - self._headless_logs_height)
      job.autoscroll = True

  def set_logs_height(self, height: int):
    with self._lock:
      self._headless_logs_height = max(1, int(height))

  def pause_job(self, job_id: int):
    with self._lock:
      job = self.job_list[int(job_id)]
      if job.status == "running":
        job.pause()

  def start_or_resume_job(self, job_id: int):
    with self._lock:
      job = self.job_list[int(job_id)]
      if job.status == "queued":
        try:
          self.job_queue.queue.remove(job)
        except ValueError:
          pass
      if job.status in ("queued", "canceled"):
        self.start_job(job)
      elif job.status == "paused":
        job.resume()

  def kill_or_cancel_job(self, job_id: int):
    with self._lock:
      job = self.job_list[int(job_id)]
      if job.status == "running" and job.process is not None:
        try:
          if sys.platform == "win32":
            job.process.send_signal(signal.CTRL_BREAK_EVENT)
          else:
            os.killpg(os.getpgid(job.process.pid), signal.SIGTERM)
          job.status = "killed"
          self.retire_job(job, getattr(job, "progress", 0))
          job.log_history.append(printc.colors.RED + "Job killed by user" + printc.colors.ENDC)
        except ProcessLookupError:
          job.log_history.append(printc.colors.RED + "Failed to kill the job" + printc.colors.ENDC)
      elif job.status == "queued":
        try:
          self.job_queue.queue.remove(job)
          job.status = "canceled"
          job.log_history.append(printc.colors.RED + "Job canceled by user" + printc.colors.ENDC)
        except ValueError:
          pass

  def open_job_path(self, job_id: int):
    with self._lock:
      job = self.job_list[int(job_id)]
      try:
        open_path_in_explorer(job.tmp_dir)
      except NotImplementedError:
        pass

  def next_theme(self):
    with self._lock:
      self.theme.next_theme()

  def request_shutdown(self):
    self._stop_event.set()

  def enqueue_command(self, name: str, **kwargs):
    """Enqueue a control command to be executed by the headless loop."""
    self._command_queue.put({"name": str(name), "kwargs": dict(kwargs)})

  def process_pending_commands(self, max_commands: int = 100):
    """Apply enqueued commands (used by headless loop and optionally curses loop)."""
    processed = 0
    while processed < int(max_commands):
      try:
        cmd = self._command_queue.get_nowait()
      except queue.Empty:
        break
      self._apply_command(cmd)
      processed += 1

  def _apply_command(self, cmd):
    name = cmd.get("name")
    kwargs = cmd.get("kwargs") or {}

    if name == "select":
      self.select_job(kwargs["job_id"])
    elif name == "pause":
      self.pause_job(kwargs["job_id"])
    elif name == "start":
      self.start_or_resume_job(kwargs["job_id"])
    elif name == "kill":
      self.kill_or_cancel_job(kwargs["job_id"])
    elif name == "open":
      self.open_job_path(kwargs["job_id"])
    elif name == "theme_next":
      self.next_theme()
    elif name == "logs_scroll":
      self.scroll_logs(kwargs["job_id"], kwargs.get("delta", 0))
    elif name == "logs_home":
      self.logs_home(kwargs["job_id"])
    elif name == "logs_end":
      self.logs_end(kwargs["job_id"])
    elif name == "set_logs_height":
      self.set_logs_height(kwargs["height"])
    elif name == "shutdown":
      self.request_shutdown()
    else:
      raise ValueError(f"Unknown command '{name}'")

  def _initialize_headless(self):
    if self._headless_initialized:
      return

    # Start initial jobs / queue remaining jobs (same as curses mode)
    for job in self.job_list:
      if len(self.running_job_list) < self.nb_jobs:
        self.start_job(job)
      else:
        self.queue_job(job)

    self._headless_initialized = True

  def _tick(self):
    """One scheduling + IO tick (headless, no curses)."""
    with self._lock:
      # Update job status and progress (logic mirrored from curses loop)
      for job in self.job_list:
        if job in self.retired_job_list:
          job.progress = getattr(job, "progress", 0)
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

      # Collect stdout and stderr pipes
      self.read_process_output()

      # Autoscroll selected job (keep behavior similar to curses)
      if 0 <= self.selected_job_index < len(self.job_list):
        selected_job = self.job_list[self.selected_job_index]
        if selected_job.autoscroll and selected_job.log_changed:
          selected_job.log_position = max(0, len(selected_job.log_history) - self._headless_logs_height)

  def _headless_loop(self, tick_interval: float):
    with self._lock:
      self._initialize_headless()
      self._headless_running = True

    try:
      while not self._stop_event.is_set():
        # Apply queued commands
        try:
          with self._lock:
            self.process_pending_commands(max_commands=200)
        except Exception as e:
          # Keep running; record error in selected job log (best-effort)
          with self._lock:
            if 0 <= self.selected_job_index < len(self.job_list):
              self.job_list[self.selected_job_index].log_history.append(
                printc.colors.RED + f"API command error: {e}" + printc.colors.ENDC
              )

        self._tick()
        time.sleep(float(tick_interval))
    finally:
      with self._lock:
        self._headless_running = False

  def start_headless(self, tick_interval: float = 0.1):
    """Start a background thread that runs the job scheduler without curses."""
    with self._lock:
      if self._headless_thread is not None and self._headless_thread.is_alive():
        return
      self._stop_event.clear()
      self._headless_thread = threading.Thread(
        target=self._headless_loop, args=(tick_interval,), daemon=True
      )
      self._headless_thread.start()

  def stop_headless(self, terminate_jobs: bool = True, timeout: float = 5.0):
    """Stop the headless scheduler thread and optionally terminate running jobs."""
    self.request_shutdown()
    t = self._headless_thread
    if t is not None:
      t.join(timeout=float(timeout))
    if terminate_jobs:
      with self._lock:
        self.terminate_all_jobs()

  def run_api(self, host: str = "0.0.0.0", port: int = 8000, log_level: str = "info"):
    """Run a FastAPI+Uvicorn server exposing REST + WebSocket controls.

    Imports are lazy so this file does not require FastAPI unless you call run_api().
    """
    from odatix.lib.parallel_job_api import run_parallel_job_api

    return run_parallel_job_api(self, host=host, port=int(port), log_level=str(log_level))

  def start_api_background(
    self,
    host: str = "127.0.0.1",
    port: int = 8000,
    log_level: str = "info",
    start_headless_on_startup: bool = False,
    quiet: bool = True,
  ):
    """Start the FastAPI/Uvicorn server in a background thread.

    - If you plan to run the curses monitor (`run()`), set start_headless_on_startup=False
      so you don't run two schedulers at once.
    - If you want the API to run standalone (no curses), set start_headless_on_startup=True.
    """
    from odatix.lib.parallel_job_api import create_uvicorn_server

    with self._lock:
      if self._api_thread is not None and self._api_thread.is_alive():
        return self._api_server

      self._api_server = create_uvicorn_server(
        self,
        host=host,
        port=int(port),
        log_level=str(log_level),
        start_headless_on_startup=bool(start_headless_on_startup),
        quiet=bool(quiet),
      )

      server = self._api_server

      def _run():
        server.run()

      self._api_thread = threading.Thread(target=_run, daemon=True)
      self._api_thread.start()
      return self._api_server

  def stop_api_background(self, timeout: float = 2.0):
    with self._lock:
      server = self._api_server
      t = self._api_thread
    if server is not None:
      server.should_exit = True
    if t is not None:
      t.join(timeout=float(timeout))

  @staticmethod
  def set_nonblocking(fd):
    if sys.platform != "win32":
      try:
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
      except TypeError:
        pass

  def progress_bar(self, window, id, progress, time, title, title_size, width, status="", selected=False):
    reserved_space = self.theme.get('reserved_space')
    spacer = self.theme.get('spacer')
    ellipsis = self.theme.get('ellipsis')

    if width > 100:
      display_time = True
    else:
      display_time = False
      reserved_space = reserved_space - (len(time) + len(spacer))

    bar_width = width - title_size - reserved_space
    if bar_width < 4:
      bar_width = 4
      title_size = width - bar_width - reserved_space
      if title_size < 0:
        title_size = 0

      if len(title) > title_size:
        title = title[: title_size - len(ellipsis)] + ellipsis
      else:
        title = title.ljust(title_size)
    else:
      title = title.ljust(title_size)

    bar_length = int(bar_width * progress / 100.0)

    real_id = self.job_index_start  + id

    try:
      # Style
      if real_id == self.selected_job_index and self.theme.get('selected_reverse') and self.job_count > 1:
        window.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
        attr = curses.A_REVERSE | curses.A_BOLD
        offset = REVERSE
      else:
        attr = 0
        offset = 0

      # Dim if popup menu opened
      attr = attr | curses.A_DIM if self.showing_help else attr

      # Ballot
      ballot = self.theme.get('ballot_check') if selected else self.theme.get('ballot_empty')
      window.addstr(id, 0, f"{ballot}")
      pos = len(ballot)
      
      # Title
      if real_id == self.selected_job_index and self.theme.get('selected_bold') and self.job_count > 1:
        window.attron(curses.color_pair(NORMAL) | curses.A_BOLD)
        attr = attr | curses.A_BOLD
      window.addstr(id, pos, f"{title}")
      window.attroff(curses.A_BOLD)
      pos = pos + len(title)

      # Border (left)
      border_left = self.theme.get('border_left')
      window.addstr(id, pos, f"{border_left}")
      pos = pos + len(border_left)

      # Progress bar (full)
      if self.theme.get('colored_bar'):
        if status == "failed" or status == "killed" or status == "canceled":
          color = curses.color_pair(RED + offset)
        elif status == "running":
          color = curses.color_pair(WHITE + offset)
        elif status == "success":
          color = curses.color_pair(GREEN + offset)
        elif status == "queued" or "paused":
          color = curses.color_pair(BLUE + offset)
        elif status == "starting":
          color = curses.color_pair(CYAN + offset)
        else:
          color = curses.color_pair(NORMAL + offset)
      else:
        color = 0
      window.addstr(id, pos, self.theme.get('progress_full') * bar_length, attr | color)
      
      # Progress bar (empty)
      if self.theme.get('dim_empty_bar'):
        dim = curses.color_pair(GREY + offset)
      else:
        dim = 0
      window.addstr(id, pos + bar_length, self.theme.get('progress_empty') * (bar_width - bar_length), attr | dim)
      pos = pos + bar_width

      # Border
      border_right = self.theme.get('border_right')
      window.addstr(id, pos, border_right + " ", attr)
      pos = pos + len(border_right)
      
      # Percentage
      percentage = f"{progress:3.0f}%"
      window.addstr(id, pos, percentage + spacer, attr)
      pos = pos + len(percentage) + len(spacer)
      
      # Elapsed time
      if display_time:
        window.addstr(id, pos, time + spacer, attr | curses.color_pair(GREY + offset))
        pos = pos + len(time) + len(spacer)

      # Status
      if status == "failed" or status == "killed" or status == "canceled":
        window.addstr(id, pos, status, curses.color_pair(RED + offset) | attr)
      elif status == "running":
        window.addstr(id, pos, status, curses.color_pair(YELLOW + offset) | attr)
      elif status == "success":
        window.addstr(id, pos, status, curses.color_pair(GREEN + offset) | attr)
      elif status == "queued" or "paused":
        window.addstr(id, pos, status, curses.color_pair(BLUE + offset) | attr)
      elif status == "starting":
        window.addstr(id, pos, status, curses.color_pair(CYAN + offset) | attr)
      else:
        window.addstr(id, pos, status, curses.color_pair(NORMAL + offset) | attr)
      pos = pos + len(status)

      # Padding
      remainder = width-pos
      if remainder > 0:
        window.addstr(id, pos, " "*(remainder), attr)
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
    if self.showing_help:
      progress_win.attron(curses.A_DIM)
    
    # Clear the window
    progress_win.erase()

    # Display the jobs within the visible range
    for id, job in enumerate(self.job_list[self.job_index_start:self.job_index_end]):
      selected = (self.selected_job_index == self.job_index_start + id)
      elapsed_time = get_elapsed_time_str(job.start_time, job.stop_time)
      try:
        self.progress_bar(
          id=id,
          window=progress_win,
          progress=job.progress,
          time=elapsed_time,
          title=job.display_name,
          title_size=self.max_title_length,
          width=width,
          status=job.status,
          selected=selected,
        )
      except curses.error:
        pass
    progress_win.refresh()
    progress_win.attroff(curses.A_DIM)

  def update_separator(self, separator_win, val, ref, width):
    dim = self.showing_help and curses.A_DIM
    separator_win.erase()
    if val == ref:
      separator_text = self.theme.get("bar") * (width - 1)
    else:
      message = f"{val - ref} more" 
      padding = 4
      separator_text = self.theme.get("bar") * padding + message + self.theme.get("bar") * (width - len(message) - padding - 1)
    try:
      separator_win.addstr(0, 0, separator_text, dim)
    except curses.error as e:
      pass
    separator_win.refresh()

  @staticmethod
  def update_help(bottom_bar):
    bottom_bar.erase()

    # Define the text with attributes
    help_text = [
      ("q", "Quit"),
      ("h", "Help Menu"),
      ("c", "Cursor Mode"),
    ]

    bottom_bar.attron(curses.color_pair(NORMAL) | curses.A_REVERSE)
    try:
      bottom_bar.addstr(" ")
    except curses.error:
      pass

    for i, (key, description) in enumerate(help_text):
      try:
        if i > 0:
          bottom_bar.addstr(" | ")
        bottom_bar.attron(curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
        bottom_bar.addstr(key)
        bottom_bar.attroff(curses.A_BOLD)  # Remove attributes
        bottom_bar.addstr(": ")
        bottom_bar.addstr(description)
      except curses.error:
        pass

    try:
      bottom_bar.addstr(" ")
    except curses.error:
      pass
    bottom_bar.attroff(curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
    bottom_bar.refresh()

  @staticmethod
  def show_exit_confirmation(bottom_bar):
    try:
      bottom_bar.erase()
      bottom_bar.addstr(" Kill all jobs and exit: Yes (", curses.color_pair(NORMAL) | curses.A_REVERSE)
      bottom_bar.addstr("y", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
      bottom_bar.addstr(") / No (", curses.color_pair(NORMAL) | curses.A_REVERSE)
      bottom_bar.addstr("n", curses.color_pair(NORMAL) | curses.A_REVERSE | curses.A_BOLD)
      bottom_bar.addstr(")? ", curses.color_pair(NORMAL) | curses.A_REVERSE)
      bottom_bar.refresh()
    except curses.error:
      pass

    key = bottom_bar.getch()
    curses.flushinp()
    if key == ord("y") or key == ord("Y"):
      return True, True
    elif key == ord("n") or key == ord("N"):
      return True, False
    else:
      return False, False

  @staticmethod
  def update_exit(bottom_bar):
    try:
      bottom_bar.erase()
      bottom_bar.addstr(" Exiting... ", curses.color_pair(NORMAL) | curses.A_REVERSE)
      bottom_bar.refresh()
    except curses.error:
      pass

  def update_logs(self, logs_win, selected_job, logs_height, width):
    history = selected_job.log_history
    log_length = len(history)

    # Erase extra lines from previous selected job
    if log_length < self.previous_log_size:
      for i in range(log_length, self.previous_log_size):
        try:
          logs_win.move(i, 0)
          logs_win.clrtoeol()
        except curses.error:
          pass

    self.converter.reset_format()

    # Logs from selected job
    for i, line in enumerate(history[selected_job.log_position : selected_job.log_position + logs_height]):
      try:
        logs_win.move(i, 0)
        if self.formatter is not None:
          line = self.formatter.replace_in_line(line)
        self.converter.add_ansi_str(logs_win, line, width=width, dim=self.showing_help)
      except curses.error:
        pass

    logs_win.refresh()
    self.previous_log_size = log_length

  def update_help_popup(self, popup_win, width, height, popup_width, popup_height):
    """Display a non-blocking help popup in the center of the screen while updating the other windows."""

    help_text = [
      ("q"          , "Quit"),
      ("PageUp    n", "Select next job"),
      ("PageDown  p", "Select previous job"),
      ("Up        u", "Scroll log"),
      ("Down      d", "Scroll log"),
      ("Home/End"   , "Scroll to top/bottom"),
      ("+/-"        , "Change progress window zize"),
      ("Space"      , "Pause selected job"),
      ("k"          , "Kill selected job"),
      ("s"          , "Start/resume selected job"),
      ("o"          , "Open current job work path"),
      ("t"          , "Switch theme"),
      ("h         ?", "Show help"),
    ]
    
    if popup_height <= 7:
      popup_win.erase()
    popup_win.box()
    
    try:
      close_x = popup_width - 5
      popup_win.addstr(1, close_x, " X ", curses.A_BOLD | curses.color_pair(REVERSE_RED))
    except curses.error:
      pass

    if popup_height > 2:
      try:
        text = " Help Menu "
        popup_win.addstr(1, (popup_width - len(text)) // 2, text, curses.A_BOLD | curses.A_REVERSE)
      except curses.error:
        pass
      if popup_height > 5:
        try:
          popup_win.addstr(3, 3, "Key      Alt", curses.A_BOLD )
          popup_win.addstr(3, 17, "Description", curses.A_BOLD )
          for i, (key, desc) in enumerate(help_text, start=4):
            if i < popup_height - 2:
              popup_win.addstr(i, 3, f"{key}", curses.color_pair(CYAN))
              popup_win.addstr(i, 17, f"{desc}")
        except curses.error:
          pass
    try:
      text = "Press 'q' or 'h' to close"
      popup_win.addstr(max(popup_height - 2, 1), (popup_width - len(text)) // 2, text, curses.A_DIM)
    except curses.error:
      pass
    popup_win.refresh()

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
        stderr=subprocess.PIPE if sys.platform != "win32" else subprocess.STDOUT,
        cwd=job.tmp_dir,
        shell=True,
        universal_newlines=True,
        bufsize=1,
        encoding="utf-8",
        errors='replace',
      )

      self.set_nonblocking(process.stdout)
      self.set_nonblocking(process.stderr)

      job.process = process
      job.status = "starting"
      job.start_time = time.time()
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
        return job_index
    return -1

  def run_job(self, job):
    job.log_history.append(printc.colors.CYAN + "Run job command" + printc.colors.ENDC)
    job.log_history.append(printc.colors.BOLD + " > " + job.command + printc.colors.ENDC)

    preexec_fn = None
    if sys.platform != "win32" and self.process_group:
      preexec_fn = os.setpgrp

    process = subprocess.Popen(
      STD_BUF + job.command,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      cwd=job.directory,
      shell=True,
      universal_newlines=True,
      bufsize=1,
      preexec_fn=preexec_fn, 
      encoding="utf-8",
      errors='replace',
    )

    if job.start_time is None:
      job.start_time = time.time()
    job.process = process
    job.status = "running"
    
    if sys.platform == "win32":
      threading.Thread(target=read_pipe_windows, args=(process.stdout, job), daemon=True).start()
      threading.Thread(target=read_pipe_windows, args=(process.stderr, job), daemon=True).start()
    else:
      self.set_nonblocking(process.stdout)
      self.set_nonblocking(process.stderr)

  def queue_job(self, job):
    job.status = "queued"
    self.job_queue.put(job)

  def retire_job(self, job, progress=100):
    job.stop_time = time.time()
    self.running_job_list.remove(job)
    job.progress = progress
    self.retired_job_list.append(job)

  def terminate_all_jobs(self):
    for job in self.running_job_list:
      if job.process:
        try:  # Try to terminate the process group
          if sys.platform == "win32":
            job.process.send_signal(signal.CTRL_BREAK_EVENT)
          else:
            os.killpg(os.getpgid(job.process.pid), signal.SIGTERM)
        except ProcessLookupError:
          pass  # Process already terminated

    # Wait for all processes to finish
    for job in self.running_job_list:
      if job.process:
        job.process.wait()

  def read_process_output(self):
    if sys.platform == "win32":
      return
    
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
              if self.log_size_limit != -1 and len(job.log_history) > self.log_size_limit:
                job.log_history = job.log_history[-self.log_size_limit:]
              job.log_changed = True
            else:
              break

  def curses_main(self, stdscr):
    curses.curs_set(0)  # Hide cursor

    # Enable mouse actions (disable selection)
    disable_selection()

    curses.start_color()
    curses.use_default_colors()

    # Define color pairs
    curses.init_pair(NORMAL, -1, -1)
    curses.init_pair(RED, curses.COLOR_RED, -1)
    curses.init_pair(YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(BLUE, curses.COLOR_BLUE, -1)
    curses.init_pair(CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(BLACK, curses.COLOR_BLACK, -1)
    curses.init_pair(WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(GREY, curses.COLOR_BLACK + AnsiToCursesConverter.LIGHT_OFFSET, -1)

    curses.init_pair(REVERSE, curses.COLOR_BLACK, curses.COLOR_WHITE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_RED, -1, curses.COLOR_RED + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_YELLOW, -1, curses.COLOR_YELLOW + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_GREEN, -1, curses.COLOR_GREEN + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_BLUE, -1, curses.COLOR_BLUE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_CYAN, -1, curses.COLOR_CYAN + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_BLACK, -1, curses.COLOR_BLACK + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_WHITE, -1, curses.COLOR_WHITE + AnsiToCursesConverter.LIGHT_OFFSET)
    curses.init_pair(REVERSE_GREY, -1, curses.COLOR_BLACK)

    height, width = stdscr.getmaxyx()
    old_width = width
    old_height = height

    # Adjust window positions
    progress_height = self.job_index_end - self.job_index_start
    header_height = 1
    separator_height = 1
    help_height = 1
    logs_height = height - progress_height - 2*separator_height - help_height - header_height
    popup_width = min(50, width - 4)
    popup_height = min(19, height - 4)
    popup_height = max(popup_height, 3)
    start_x = (width - popup_width) // 2
    start_y = (height - popup_height) // 2

    try:
      header_win = curses.newwin(header_height, width, 0, 0)
      separator_top_win = curses.newwin(separator_height, width, header_height, 0)
      progress_win = curses.newwin(progress_height, width, header_height + separator_height, 0)
      separator_middle_win = curses.newwin(separator_height, width, header_height + separator_height + progress_height, 0)
      logs_win = curses.newwin(logs_height, width, header_height + separator_height + progress_height + separator_height, 0)
      bottom_bar = curses.newwin(help_height, width, height - help_height, 0)
      popup_win = curses.newwin(popup_height, popup_width, start_y, start_x)
      popup_win.box()
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

    self.showing_help = False

    while True:
      # Apply any API commands (when running with background REST/WS control)
      try:
        with self._lock:
          self.process_pending_commands(max_commands=200)
      except Exception as e:
        try:
          # Best-effort: show an error in selected job logs
          if 0 <= self.selected_job_index < len(self.job_list):
            self.job_list[self.selected_job_index].log_history.append(
              printc.colors.RED + f"API command error: {e}" + printc.colors.ENDC
            )
        except Exception:
          pass

      height, width = stdscr.getmaxyx()
      # If window size changes, adjust the layout
      if height != old_height or width != old_width or resize:
        popup_width = min(50, width - 4)
        popup_height = min(20, height - 4)
        popup_height = max(popup_height, 3)
        start_x = (width - popup_width) // 2
        start_y = (height - popup_height) // 2
        try:
          progress_height = self.job_index_end - self.job_index_start
          logs_height = height - progress_height - 2*separator_height - help_height - header_height
          
          separator_top_win = curses.newwin(separator_height, width, header_height, 0)
          progress_win = curses.newwin(progress_height, width, header_height + separator_height, 0)
          separator_middle_win = curses.newwin(separator_height, width, header_height + separator_height + progress_height, 0)
          logs_win = curses.newwin(logs_height, width, header_height + separator_height + progress_height + separator_height, 0)
          bottom_bar = curses.newwin(help_height, width, height - help_height, 0)
          popup_win = curses.newwin(popup_height, popup_width, start_y, start_x)
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
      queued_jobs_count = self.job_queue.qsize()
      if active_jobs_count == 0 and queued_jobs_count == 0:
        finished = True

      retired_jobs_count = len(self.retired_job_list)

      # Add a header
      self.update_header(header_win, active_jobs_count, retired_jobs_count, total_jobs_count, width)

      # Add a separator
      self.update_separator(separator_top_win, self.job_index_start, 0, width)

      # Update job status and progress (protected for API concurrency)
      with self._lock:
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

      # Help window
      if self.showing_help:
        self.update_help_popup(popup_win, width, height, popup_width, popup_height)

      # Collect all stdout and stderr pipes
      with self._lock:
        self.read_process_output()

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

      if not self.showing_help:

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
          if button & curses.BUTTON1_CLICKED or button & curses.BUTTON1_DOUBLE_CLICKED:
            # Check if user left clicked on a job
            job_index = self.click_on_job(progress_win, y, x)
            # If user clicked on a job, update the selected job
            if job_index >= 0:
              self.selected_job_index = job_index
              selected_job = update_selected_job()
              self.update_logs(logs_win, selected_job, logs_height, width)
          
              # Check if it was a double click
              if button & curses.BUTTON1_DOUBLE_CLICKED:
                try:
                  open_path_in_explorer(self.job_list[job_index].tmp_dir)
                except NotImplementedError:
                  pass

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
        elif key == curses.KEY_UP or key == ord("u") or key == ord("U"):
          scroll_up_logs(selected_job)

        # Scroll Down
        elif key == curses.KEY_DOWN or key == ord("d") or key == ord("D"):
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

        # Enable/disable mouse actions/selection
        elif key == ord("c") or key == ord("C"):
          if self.selection_enabled:
            disable_selection()
            self.selection_enabled = False
          else:
            enable_selection()
            self.selection_enabled = True

        # Kill the selected job
        elif key == ord('k') or key == ord('K'):
          if selected_job.status == "running":  # Kill the running job
            try:
              if sys.platform == "win32":
                job.process.send_signal(signal.CTRL_BREAK_EVENT)
              else:
                os.killpg(os.getpgid(selected_job.process.pid), signal.SIGTERM)
              selected_job.status = "killed"
              self.retire_job(selected_job, selected_job.progress)
              selected_job.log_history.append(printc.colors.RED + "Job killed by user" + printc.colors.ENDC)
            except ProcessLookupError:
              selected_job.log_history.append(printc.colors.RED + "Failed to kill the job" + printc.colors.ENDC)
          elif selected_job.status == "queued":  # Remove job from queue
            try:
              self.job_queue.queue.remove(selected_job)
              selected_job.status = "canceled"
              selected_job.log_history.append(printc.colors.RED + "Job canceled by user" + printc.colors.ENDC)
            except ValueError:
              pass

        # Pause the selected job
        elif key == ord(' '):
          if selected_job.status == "running":
            selected_job.pause()

        # Start the selected job
        elif key == ord('s') or key == ord('S'): 
          if selected_job.status == "queued":
            self.job_queue.queue.remove(selected_job)
          if selected_job.status == "queued" or selected_job.status == "canceled":  # Start a queued job immediately
            self.start_job(selected_job)
          if selected_job.status == "paused":
            selected_job.resume()

        # Open job work directory in system file explorer
        elif key == ord('o') or key == ord('O'): 
          try:
            open_path_in_explorer(selected_job.tmp_dir)
          except NotImplementedError:
            pass

        # Change theme
        elif key == ord("t") or key == ord("T"):
          self.theme.next_theme()

        # Open help menu
        elif key in [ord("h"), ord("H"), ord("?")]:
          self.showing_help = True
          self.update_logs(logs_win, selected_job, logs_height, width) # Update to dim log window

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
      
      else: # help window
        if key == curses.KEY_MOUSE:
          _, mouse_x, mouse_y, _, button = curses.getmouse()
          close_x = start_x + popup_width - 5
          close_y = start_y + 1

          if button & curses.BUTTON1_CLICKED and mouse_y == close_y and close_x <= mouse_x <= close_x + 2:
            self.showing_help = False
            logs_win.erase()
            self.update_logs(logs_win, selected_job, logs_height, width)

        elif key in [ord('h'), ord('H'), ord('?'), ord('q'), ord('Q')]:
          self.showing_help = False
          logs_win.erase() # Erase remains of help menu
          self.update_logs(logs_win, selected_job, logs_height, width)

      # Handle exit
      if ask_exit:
        user_answered, user_confirmed = self.show_exit_confirmation(bottom_bar)
        if user_answered:
          if user_confirmed:
            self.update_exit(bottom_bar)
            self.terminate_all_jobs()
            return False
          else:
            ask_exit = False
      else:
        self.update_help(bottom_bar)

  def run(self):
    curses.wrapper(self.curses_main)
