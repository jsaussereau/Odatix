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
from odatix.lib.parallel_job_handler.ansi_to_curses import AnsiToCursesConverter
from odatix.lib.parallel_job_handler.job_output_formatter import JobOutputFormatter
from odatix.lib.utils import open_path_in_explorer, find_free_port
from odatix.lib.parallel_job_handler.theme import Theme
from odatix.lib.parallel_job_handler.job import ParallelJob
from odatix.lib.parallel_job_handler.utils import get_elapsed_time_str, read_pipe_windows
from odatix.lib.parallel_job_handler import curses_ui
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
        self._request_curses_exit = False

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
        self._request_curses_exit = True

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

    def _append_job_log(self, job, line):
        if not line:
            return
        job.log_history.append(line)
        limit = getattr(job, "log_size_limit", self.log_size_limit)
        if limit != -1 and len(job.log_history) > limit:
            job.log_history = job.log_history[-limit:]
        job.log_changed = True

    def _drain_process_pipes(self, job):
        if job.process is None or sys.platform == "win32":
            return

        for pipe in (job.process.stdout, job.process.stderr):
            if pipe is None:
                continue
            while True:
                try:
                    line = pipe.readline()
                except Exception:
                    break
                if not line:
                    break
                self._append_job_log(job, line)

    def _update_jobs_state(self, selected_job=None, on_selected_retired=None):
        for job in self.job_list:
            if job in self.retired_job_list:
                job.progress = getattr(job, "progress", 0)
            elif job not in self.running_job_list or job.process is None:
                job.progress = 0
            else:
                job.progress = job.get_progress()
                if job.process.poll() is not None:
                    # Drain remaining buffered output before state transition/retire.
                    self._drain_process_pipes(job)

                    if job.process.returncode == 0:
                        if job.status == "starting":
                            job.log_history.append("")
                            self.run_job(job)
                            continue
                        elif hasattr(job, "_task_pipeline"):
                            if self._start_next_task(job):
                                continue
                            self._clear_task_pipeline(job)
                            job.status = "success"
                        else:
                            job.status = "success"
                    else:
                        job.status = "failed"
                        if hasattr(job, "_current_task_name"):
                            job.log_history.append(
                                printc.colors.RED + "error: task '" + str(job._current_task_name) + "' failed" + printc.colors.ENDC
                            )
                            job.log_history.append(
                                printc.colors.CYAN + "note: look for earlier error to solve this issue" + printc.colors.ENDC
                            )
                        self._clear_task_pipeline(job)
                        if job.progress is None:
                            job.progress = 0

                    self.retire_job(job, job.progress)
                    if not self.job_queue.empty():
                        self.start_job(self.job_queue.get())

                    if selected_job is not None and job == selected_job:
                        selected_job.log_changed = True
                        if callable(on_selected_retired):
                            on_selected_retired()

    def _tick(self):
        """One scheduling + IO tick (headless, no curses)."""
        with self._lock:
            self._update_jobs_state()

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
        from odatix.lib.parallel_job_handler.api import run_parallel_job_api

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
        from odatix.lib.parallel_job_handler.api import create_uvicorn_server

        with self._lock:
            if self._api_thread is not None and self._api_thread.is_alive():
                return self._api_server

            port = find_free_port(host, int(port))

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
            return self._api_server, port

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

    @staticmethod
    def _task_name(task):
        taskname = getattr(task, "name", None)
        if taskname is None and hasattr(task, "getName"):
            taskname = task.getName()
        if taskname is None:
            taskname = str(task)
        return str(taskname)

    @staticmethod
    def _task_full_command(task):
        task_command = getattr(task, "command", None)
        if task_command is None and hasattr(task, "getCommand"):
            task_command = task.getCommand()
        if task_command is None:
            task_command = ""

        cmdlines = task_command.split("\n")
        cmdlines = [ln.lstrip().rstrip() for ln in cmdlines]
        return " && ".join([c[1:] if c.startswith("@") else c for c in cmdlines if c])

    def _build_task_pipeline(self, job):
        pipeline = []
        for _, tasks in sorted(job.command.items(), key=lambda x: x[0]):
            for task in tasks:
                taskname = self._task_name(task)
                full_command = self._task_full_command(task)
                if full_command:
                    pipeline.append((taskname, full_command))
        return pipeline

    @staticmethod
    def _clear_task_pipeline(job):
        for attr in ("_task_pipeline", "_task_index", "_current_task_name"):
            if hasattr(job, attr):
                delattr(job, attr)

    def _start_next_task(self, job):
        pipeline = getattr(job, "_task_pipeline", None)
        if pipeline is None:
            return False

        task_index = int(getattr(job, "_task_index", 0))
        if task_index >= len(pipeline):
            return False

        taskname, full_command = pipeline[task_index]
        job._task_index = task_index + 1
        job._current_task_name = taskname

        job.log_history.append(printc.colors.CYAN + "Run job task '" + taskname + "'" + printc.colors.ENDC)
        job.log_history.append(printc.colors.BOLD + " > " + full_command + printc.colors.ENDC)

        preexec_fn = None
        if sys.platform != "win32" and self.process_group:
            preexec_fn = os.setpgrp

        process = subprocess.Popen(
            STD_BUF + full_command,
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

        return True

    def run_job(self, job):
        if isinstance(job.command, str):
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
        elif isinstance(job.command, dict):
            if not hasattr(job, "_task_pipeline"):
                job._task_pipeline = self._build_task_pipeline(job)
                job._task_index = 0

            if not self._start_next_task(job):
                self._clear_task_pipeline(job)
                job.status = "success"

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

        for job in self.running_job_list:
            job.log_changed = False

        pipes = []
        for job in self.running_job_list:
            if job.process is None:
                continue
            if job.process.stdout is not None:
                pipes.append(job.process.stdout)
            if job.process.stderr is not None:
                pipes.append(job.process.stderr)

        if not pipes:
            return
        
        try:
            read_ready, _, _ = select.select(pipes, [], [], 0.1)
        except:
            read_ready = []
        
        for pipe in read_ready:
            for job in self.running_job_list:
                if job.process is not None and pipe in (job.process.stdout, job.process.stderr):
                    while True:
                        line = pipe.readline()
                        if line:
                            self._append_job_log(job, line)
                        else:
                            break

    def curses_main(self, stdscr):
        return curses_ui.curses_main(self, stdscr)

    def run(self):
        return curses_ui.run(self)
