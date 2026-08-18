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
import shutil
import queue
import select
import signal
import subprocess
import curses
import locale
import io
import contextlib
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

from odatix.lib.parallel_job_handler.ansi_to_curses import AnsiToCursesConverter
from odatix.lib.parallel_job_handler.job_output_formatter import JobOutputFormatter
from odatix.lib.utils import open_path_in_explorer, find_free_port
from odatix.lib.parallel_job_handler.theme import Theme
from odatix.lib.parallel_job_handler.job import JOB_KIND, ParallelJob
from odatix.lib.parallel_job_handler.utils import get_elapsed_time_str, read_pipe_windows
from odatix.lib.parallel_job_handler import curses_ui
from odatix.lib.parallel_job_handler import diagnostics
import odatix.lib.hard_settings as hard_settings
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


class _JobLogWriter(io.TextIOBase):
    """Write redirected stdout/stderr text directly into a job log stream."""

    def __init__(self, write_fn):
        super().__init__()
        self._write_fn = write_fn

    def write(self, s):
        if not s:
            return 0
        text = str(s)
        self._write_fn(text)
        return len(text)

    def flush(self):
        return

######################################
# ParallelJobHandler
######################################

class ParallelJobHandler:
    def __init__(
        self,
        job_list,
        nb_jobs=4,
        process_group=True,
        auto_exit=False,
        format_yaml=None,
        log_size_limit=200,
        resource_guard=True,
        cpu_limit=98.0,
        mem_limit=98.0,
        resource_check_interval=2.0,
    ):
        self.job_list = list(job_list) if job_list is not None else []
        self.nb_jobs = int(nb_jobs)
        self.process_group = bool(process_group)
        self.auto_exit = bool(auto_exit)
        self.log_size_limit = int(log_size_limit)

        # Resource guard: pause running jobs when the system is too loaded
        # (CPU or memory), resume them once it settles back down. Disabled
        # automatically on platforms/setups where it cannot work (Windows has
        # no SIGSTOP/SIGCONT, psutil may be missing).
        self.resource_guard_enabled = bool(resource_guard) and sys.platform != "win32"
        self.cpu_limit = float(cpu_limit)
        self.mem_limit = float(mem_limit)
        # Hysteresis: only resume once usage has dropped well below the
        # pause threshold, so we don't pause/resume the same job repeatedly
        # when load hovers right around the limit.
        self.cpu_resume_limit = max(0.0, self.cpu_limit - 5.0)
        self.mem_resume_limit = max(0.0, self.mem_limit - 5.0)
        self.resource_check_interval = float(resource_check_interval)
        self._resource_guard_last_check = 0.0
        self._resource_guard_last_cpu = None
        self._resource_guard_last_mem = None
        self._auto_paused_jobs = []
        self._resource_guard_warned = False

        self.version = read_version()

        self.running_job_list = []
        self.retired_job_list = []
        # Membership mirrors of the two lists above. A long exploration retires
        # thousands of jobs into the same session, and `job in list` on every
        # tick made the scheduler quadratic in the number of jobs it had ever
        # run -- with the handler lock held, which is what made a busy daemon
        # stop answering. See _update_jobs_state.
        self._running_jobs = set()
        self._retired_jobs = set()
        self.job_queue = queue.Queue()

        # Work to run once, when nothing is running and nothing is queued
        # anymore. Per-job exports (post_run_export) cannot cover everything a
        # batch produces: a derived metric reads records of other jobs, which
        # may not have finished yet when a job exports its own. See
        # odatix.components.export_derived_metrics.
        self.post_batch_action = None
        self._post_batch_done = False
        self.selected_job_index = 0
        self.previous_log_size = 0
        if len(self.job_list) > 0:
            self.max_title_length = max(len(job.display_name) for job in self.job_list)
        else:
            self.max_title_length = 0

        self.selection_enabled = False

        self.converter = AnsiToCursesConverter()
        self.format_yaml = None
        self.formatter = None
        self._set_formatter(format_yaml)

        # Initial calculation of max displayed jobs.
        # Keep constructor headless-safe: do not initialize curses here.
        term_size = shutil.get_terminal_size((120, 40))
        height = int(getattr(term_size, "lines", 40))
        self.job_count = len(self.job_list)
        displayed_jobs_cmd = max(1, height // 2 - 2)  # Half-screen default.
        max_progress_height = max(1, height - 5)  # Keep at least one log line.
        preferred_jobs_height = max(displayed_jobs_cmd, self.job_count)
        max_displayed_jobs = min(max_progress_height, preferred_jobs_height)
        
        # Job list
        self.job_index_start = 0
        self.job_index_end = max_displayed_jobs if self.job_count > 0 else 0

        try:
            self.theme = Theme('Color_Boxes')
        except Exception:
            self.theme = Theme('ASCII_Highlight')

        # Headless / API control state (thread-safe)
        self._lock = threading.RLock()
        self._command_queue = queue.Queue()
        self._stop_event = threading.Event()
        # Exports run on their own thread, one at a time. They rewrite a shared
        # results file, so they must stay serialized -- but not on the scheduler
        # thread, which holds the handler lock and would keep the whole session
        # (API included) silent for as long as an export takes. See
        # _submit_post_success_export.
        self._export_queue = queue.Queue()
        self._export_thread = None
        self._exports_pending = 0
        self._headless_thread = None
        self._headless_running = False
        self._headless_initialized = False
        self._headless_logs_height = 40
        self.showing_help = False
        self._request_curses_exit = False

        # What the diagnostics file reports about the scheduler (see _heartbeat).
        self._tick_count = 0
        self._tick_time_total = 0.0
        self._tick_time_max = 0.0
        self._tick_failures = 0
        self._last_heartbeat = time.time()

        # API server (optional)
        self._api_thread = None
        self._api_server = None

    def _set_formatter(self, format_yaml):
        """Configure log formatter from a YAML file path.

        Passing None keeps caller-defined behavior (used by configure_runtime), while
        passing an empty value disables formatting.
        """
        if format_yaml in ("", False):
            self.format_yaml = None
            self.formatter = None
            return

        if format_yaml is None:
            return

        path = str(format_yaml)
        try:
            resolved = os.path.realpath(os.path.expandvars(os.path.expanduser(path)))
            if os.path.isfile(resolved):
                path = resolved
        except Exception:
            pass

        self.format_yaml = path
        self.formatter = JobOutputFormatter(path)

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
                        "kind": getattr(job, "kind", JOB_KIND),
                        "status": job.status,
                        "progress": getattr(job, "progress", 0),
                        "directory": job.directory,
                        "tmp_dir": job.tmp_dir,
                        "target": job.target,
                        "arch": job.arch,
                        "elapsed_time": get_elapsed_time_str(job.start_time, job.stop_time),
                    }
                )

            if self.job_count > 0:
                selected_id = int(self.selected_job_index)
            else:
                selected_id = -1
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
                    "format_yaml": self.format_yaml,
                    "selected_job_index": selected_id,
                    "job_count": int(self.job_count),
                    "running": len(self.running_job_list),
                    "queued": int(self.job_queue.qsize()),
                    "retired": len(self.retired_job_list),
                    "theme": getattr(self.theme, "theme", None),
                    "resource_guard": {
                        "enabled": bool(self.resource_guard_enabled),
                        "cpu_limit": float(self.cpu_limit),
                        "mem_limit": float(self.mem_limit),
                        "cpu": self._resource_guard_last_cpu,
                        "mem": self._resource_guard_last_mem,
                        "auto_paused": len(self._auto_paused_jobs),
                    },
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

    def configure_runtime(
        self,
        nb_jobs=None,
        process_group=None,
        auto_exit=None,
        log_size_limit=None,
        format_yaml=None,
        resource_guard=None,
        cpu_limit=None,
        mem_limit=None,
    ):
        """Update runtime scheduling options (daemon mode).

        Any argument set to None keeps the current value.
        """
        with self._lock:
            if nb_jobs is not None:
                self.nb_jobs = max(1, int(nb_jobs))
            if process_group is not None:
                self.process_group = bool(process_group)
            if auto_exit is not None:
                self.auto_exit = bool(auto_exit)
            if log_size_limit is not None:
                self.log_size_limit = int(log_size_limit)
            if format_yaml is not None:
                self._set_formatter(format_yaml)
            if resource_guard is not None:
                self.resource_guard_enabled = bool(resource_guard) and sys.platform != "win32"
            if cpu_limit is not None:
                self.cpu_limit = float(cpu_limit)
                self.cpu_resume_limit = max(0.0, self.cpu_limit - 15.0)
            if mem_limit is not None:
                self.mem_limit = float(mem_limit)
                self.mem_resume_limit = max(0.0, self.mem_limit - 15.0)

            self._fill_running_slots_from_queue_unlocked()

    def set_nb_jobs(self, nb_jobs):
        """Change the max number of jobs allowed to run in parallel, at runtime.

        Overridden by the daemon monitor handler to forward the change to the
        remote daemon instead of applying it locally.
        """
        self.configure_runtime(nb_jobs=max(1, int(nb_jobs)))

    ######################################
    # What is running, and what counts as running
    ######################################

    @property
    def used_slots(self):
        """
        How many of the parallel slots are taken.

        Not every running job takes one: a driver runs the run itself and spends
        its time waiting for the jobs it enqueues (see
        odatix.lib.parallel_job_handler.job), so counting it would mean running
        one job less than the user asked for, forever.
        """
        return sum(1 for job in self.running_job_list if job.takes_a_slot)

    @property
    def working_job_list(self):
        """The running jobs that are work, rather than what asked for it."""
        return [job for job in self.running_job_list if job.takes_a_slot]

    @property
    def pinned_job_list(self):
        """The jobs the monitor keeps in sight, in the order they were added."""
        return [job for job in self.job_list if job.pinned]

    @property
    def scrollable_job_list(self):
        """The jobs the monitor scrolls through."""
        return [job for job in self.job_list if not job.pinned]

    @property
    def scrollable_count(self):
        return sum(1 for job in self.job_list if not job.pinned)

    def visible_jobs(self, rows=None):
        """
        What the monitor shows, as (index in job_list, job) pairs: the pinned
        jobs first, always, then the scrolled window over the others.

        Args:
            rows (int): how many rows there is room for. The window already
                worked out by job_index_start/job_index_end when not given.
        """
        indexed = list(enumerate(self.job_list))
        pinned = [pair for pair in indexed if pair[1].pinned]
        scrollable = [pair for pair in indexed if not pair[1].pinned]

        if rows is None:
            rows = max(0, int(self.job_index_end) - int(self.job_index_start))
        room = max(0, int(rows) - len(pinned))
        start = max(0, int(self.job_index_start))
        return pinned + scrollable[start:start + room]

    def scroll_position(self, job_index):
        """
        Where a job sits in what the monitor scrolls through, or None when it is
        pinned and therefore always in sight.
        """
        job_index = int(job_index)
        if job_index < 0 or job_index >= len(self.job_list) or self.job_list[job_index].pinned:
            return None
        return sum(1 for job in self.job_list[:job_index] if not job.pinned)

    def _check_resource_guard_unlocked(self):
        """
        Pause/resume running jobs to keep the host system from freezing under
        too much CPU or memory pressure. Runs on every tick but only actually
        samples the system every `resource_check_interval` seconds, since
        psutil.cpu_percent() needs to be spaced out to mean anything.
        """
        if not self.resource_guard_enabled:
            return

        try:
            import psutil
        except ImportError:
            # Not installed: disable rather than fail repeatedly.
            self.resource_guard_enabled = False
            if not self._resource_guard_warned:
                self._resource_guard_warned = True
                printc.warning(
                    "psutil is not installed: resource guard (auto-pause on high CPU/memory) is disabled",
                    script_name,
                )
            return

        now = time.time()
        if now - self._resource_guard_last_check < self.resource_check_interval:
            return
        self._resource_guard_last_check = now

        try:
            cpu = float(psutil.cpu_percent(interval=None))
            mem = float(psutil.virtual_memory().percent)
        except Exception:
            return

        self._resource_guard_last_cpu = cpu
        self._resource_guard_last_mem = mem

        # Drop jobs that are no longer paused (killed, or resumed by hand) from
        # our own bookkeeping so we don't try to resume them later.
        self._auto_paused_jobs = [job for job in self._auto_paused_jobs if job.status == "paused"]

        overloaded_cpu = cpu >= self.cpu_limit
        overloaded_mem = mem >= self.mem_limit

        if overloaded_cpu or overloaded_mem:
            candidates = [job for job in self.running_job_list if job.status == "running" and job.takes_a_slot]
            if candidates:
                # Pause the most recently started job first: it has the least
                # work invested in it, and pausing it disrupts the batch least.
                job = candidates[-1]
                job.pause()
                if job.status == "paused":
                    self._auto_paused_jobs.append(job)
                    reason = "CPU" if overloaded_cpu else "memory"
                    job.log_history.append(
                        printc.colors.YELLOW
                        + f"Job auto-paused: system {reason} usage too high "
                        + f"({cpu:.0f}% CPU, {mem:.0f}% mem)"
                        + printc.colors.ENDC
                    )
            return

        if cpu < self.cpu_resume_limit and mem < self.mem_resume_limit and self._auto_paused_jobs:
            job = self._auto_paused_jobs.pop(0)
            if job.status == "paused":
                job.resume()
                job.log_history.append(
                    printc.colors.GREEN + "Job auto-resumed: system load back to normal" + printc.colors.ENDC
                )

    def _fill_running_slots_from_queue_unlocked(self):
        while self.used_slots < self.nb_jobs and not self.job_queue.empty():
            self.start_job(self.job_queue.get())

    def _schedule_new_job_unlocked(self, job):
        if not job.takes_a_slot or self.used_slots < self.nb_jobs:
            self.start_job(job)
        else:
            self.queue_job(job)

    def add_job(self, job):
        """Add a new job to this handler and schedule it if already running headless."""
        with self._lock:
            self.job_list.append(job)
            self.job_count = len(self.job_list)
            # A new job means a new batch to close: derive again once it drains.
            self._post_batch_done = False
            self.max_title_length = max(self.max_title_length, len(job.display_name))

            if self.job_count == 1:
                self.selected_job_index = 0
                self.job_index_start = 0
                self.job_index_end = 1
            else:
                if self.job_index_end <= self.job_index_start:
                    self.job_index_end = self.job_index_start + 1
                self.job_index_end = min(self.job_count, self.job_index_end)

            if self._headless_initialized:
                self._schedule_new_job_unlocked(job)

    def add_jobs(self, jobs):
        for job in jobs:
            self.add_job(job)

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
            self._schedule_new_job_unlocked(job)

        self._headless_initialized = True

    def _append_job_log(self, job, line, stream_key="default"):
        if not line:
            return

        if isinstance(line, bytes):
            try:
                text = line.decode(ENCODING, errors="replace")
            except Exception:
                text = line.decode("utf-8", errors="replace")
        else:
            text = str(line)

        text = text.replace("\r\n", "\n")

        stream_states = getattr(job, "_log_stream_states", None)
        if stream_states is None:
            stream_states = {}
            job._log_stream_states = stream_states

        state = stream_states.get(stream_key)
        if state is None:
            state = {"pending": "", "overwrite": False, "line_index": None}
            stream_states[stream_key] = state

        pending = state.get("pending", "")
        overwrite = bool(state.get("overwrite", False))
        line_index = state.get("line_index", None)

        def _store_log(stored_line, do_overwrite=False):
            nonlocal line_index
            if stored_line is None:
                return
            stored_line = str(stored_line).replace("\x00", "")
            if stored_line == "":
                return
            if do_overwrite and line_index is not None and 0 <= line_index < len(job.log_history):
                job.log_history[line_index] = stored_line
            else:
                job.log_history.append(stored_line)
                line_index = len(job.log_history) - 1

        for ch in text:
            if ch == "\r":
                _store_log(pending, overwrite)
                pending = ""
                overwrite = True
            elif ch == "\n":
                _store_log(pending, overwrite)
                pending = ""
                overwrite = False
                line_index = None
            else:
                pending += ch

        # Keep the current carriage-return line live-updated in place.
        if overwrite and pending != "":
            _store_log(pending, do_overwrite=True)

        state["pending"] = pending
        state["overwrite"] = overwrite
        state["line_index"] = line_index

        limit = getattr(job, "log_size_limit", self.log_size_limit)
        if limit != -1 and len(job.log_history) > limit:
            dropped = len(job.log_history) - limit
            job.log_history = job.log_history[-limit:]
            for st in stream_states.values():
                idx = st.get("line_index", None)
                if idx is None:
                    continue
                idx -= dropped
                st["line_index"] = idx if idx >= 0 else None
        job.log_changed = True

    def _flush_job_log_buffer(self, job):
        stream_states = getattr(job, "_log_stream_states", None)
        if not stream_states:
            return

        changed = False
        for st in stream_states.values():
            pending = st.get("pending", "")
            overwrite = bool(st.get("overwrite", False))
            line_index = st.get("line_index", None)

            if pending:
                if overwrite and line_index is not None and 0 <= line_index < len(job.log_history):
                    job.log_history[line_index] = pending
                else:
                    job.log_history.append(pending)
                changed = True

            st["pending"] = ""
            st["overwrite"] = False
            st["line_index"] = None

        if changed:
            limit = getattr(job, "log_size_limit", self.log_size_limit)
            if limit != -1 and len(job.log_history) > limit:
                job.log_history = job.log_history[-limit:]
            job.log_changed = True

    def _drain_process_pipes(self, job):
        if job.process is None or sys.platform == "win32":
            return

        self._read_available_pipe_data(job, job.process.stdout, stream_key="stdout")
        self._read_available_pipe_data(job, job.process.stderr, stream_key="stderr")

    def _read_available_pipe_data(self, job, pipe, stream_key="default"):
        if pipe is None:
            return

        try:
            fd = pipe.fileno()
        except Exception:
            return

        while True:
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                break
            except OSError:
                break

            if not chunk:
                break

            self._append_job_log(job, chunk, stream_key=stream_key)

    #: An export slower than this is worth a line: the session cannot answer
    #: anyone while it runs.
    SLOW_EXPORT_S = 0.5

    def _submit_post_success_export(self, job):
        """
        Hand a finished job's export to the export thread, and come straight back.

        The caller is the scheduler, holding the handler lock: running the export
        here means the session answers nobody -- not the monitor, not the GUI,
        not an exploration waiting on its own batch -- for as long as it takes,
        which grows with the results file being rewritten. Sessions were being
        declared dead over exactly that.

        The job stays in status "exporting" until the export is over, so nothing
        that waits for a job to finish sees it as finished too early.
        """
        export_config = getattr(job, "post_run_export", None)
        if not isinstance(export_config, dict):
            return False

        if str(export_config.get("kind", "")).strip().lower() == "":
            return False

        job.status = "exporting"
        self._exports_pending += 1
        self._ensure_export_thread()
        self._export_queue.put(job)
        return True

    def _ensure_export_thread(self):
        """Start the export thread on first use, and restart it if it ever died."""
        if self._export_thread is not None and self._export_thread.is_alive():
            return
        self._export_thread = threading.Thread(target=self._export_loop, daemon=True)
        self._export_thread.start()

    def _export_loop(self):
        """Run queued exports one at a time, without the handler lock."""
        while True:
            try:
                job = self._export_queue.get(timeout=0.5)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                continue

            try:
                success = self._run_post_success_export(job)
            except Exception as e:
                success = False
                diagnostics.log("export thread error", job=job.display_name, error=str(e))

            with self._lock:
                job.status = "success" if success else "failed"
                self._exports_pending = max(0, self._exports_pending - 1)
                self._run_post_batch_action_if_drained()

    def _run_post_success_export(self, job):
        """Run one job's export. Called on the export thread, lock-free."""
        export_config = getattr(job, "post_run_export", None)
        export_kind = str(export_config.get("kind", "")).strip().lower()

        self._append_job_log(
            job,
            printc.colors.CYAN + "Export job results..." + printc.colors.ENDC + "\n",
            stream_key="export",
        )

        try:
            if export_kind == "synthesis":
                from odatix.components.export_results import export_single_job_result
                export_fn = export_single_job_result
            elif export_kind == "workflow":
                from odatix.components.export_workflow_results import export_single_workflow_job
                export_fn = export_single_workflow_job
            elif export_kind == "simulation":
                from odatix.components.export_simulation_results import export_single_simulation_job
                export_fn = export_single_simulation_job
            elif export_kind == "analysis":
                from odatix.components.export_analysis import export_single_analysis_job
                export_fn = export_single_analysis_job
            else:
                self._append_job_log(
                    job,
                    printc.colors.YELLOW
                    + "warning: unsupported export kind '"
                    + export_kind
                    + "'"
                    + printc.colors.ENDC
                    + "\n",
                    stream_key="export",
                )
                self._flush_job_log_buffer(job)
                return False

            writer = _JobLogWriter(lambda data: self._append_job_log(job, data, stream_key="export"))
            # Timed even off the scheduler thread: an export slower than the
            # jobs it follows is what makes a batch look stalled at the end.
            export_started = time.time()
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                success = bool(export_fn(job=job, export_config=export_config))
            export_duration = time.time() - export_started
            if export_duration >= self.SLOW_EXPORT_S:
                diagnostics.log(
                    "slow export",
                    seconds=export_duration,
                    kind=export_kind,
                    job=job.display_name,
                )
        except Exception as e:
            self._append_job_log(
                job,
                printc.colors.RED + "error: export failed: " + str(e) + printc.colors.ENDC + "\n",
                stream_key="export",
            )
            self._flush_job_log_buffer(job)
            return False

        if success:
            self._append_job_log(
                job,
                printc.colors.GREEN + "Export finished" + printc.colors.ENDC + "\n",
                stream_key="export",
            )
            self._flush_job_log_buffer(job)
            return True

        self._append_job_log(
            job,
            printc.colors.RED + "error: export step reported failure" + printc.colors.ENDC + "\n",
            stream_key="export",
        )
        self._flush_job_log_buffer(job)
        return False

    def _run_post_batch_action(self):
        """
        Run the batch-wide action once the last job of the batch has retired.

        Failures are reported but never fail a job: the jobs themselves are
        done, and their own results are already exported.
        """
        action = self.post_batch_action
        if not isinstance(action, dict):
            return

        kind = str(action.get("kind", "")).strip().lower()
        if kind == "":
            return

        try:
            if kind == "derived_metrics":
                from odatix.components.export_derived_metrics import apply_derived_metrics

                derived_metrics_file = action.get("derived_metrics_file")
                if derived_metrics_file and os.path.isfile(derived_metrics_file):
                    apply_derived_metrics(action.get("result_path"), derived_metrics_file)
            else:
                printc.warning("Unsupported post-batch action '" + kind + "'", script_name)
        except Exception as e:
            printc.error("Post-batch action '" + kind + "' failed: " + str(e), script_name)

    def _run_post_batch_action_if_drained(self):
        """
        Run the batch-wide action when no job is running or waiting anymore.

        A driver is not work: an exploration running its own search would keep
        the session from ever looking drained, and the results of every batch it
        already ran would wait for the whole exploration to be over.
        """
        if self._post_batch_done or not isinstance(self.post_batch_action, dict):
            return
        if len(self.working_job_list) > 0 or not self.job_queue.empty():
            return
        # An export still running is a record not written yet, and a derived
        # metric reads the records of the jobs it derives from.
        if self._exports_pending > 0:
            return
        self._post_batch_done = True
        self._run_post_batch_action()

    def _update_jobs_state(self, selected_job=None, on_selected_retired=None):
        for job in self.job_list:
            if job in self._retired_jobs:
                job.progress = getattr(job, "progress", 0)
            elif job not in self._running_jobs or job.process is None:
                job.progress = 0
            else:
                job.progress = job.get_progress()
                if job.process.poll() is not None:
                    # Drain remaining buffered output before state transition/retire.
                    self._drain_process_pipes(job)
                    self._flush_job_log_buffer(job)

                    if job.process.returncode == 0:
                        if job.status == "starting":
                            job.log_history.append("")
                            self.run_job(job)
                            continue
                        elif hasattr(job, "_task_pipeline"):
                            self._record_completed_step(job)
                            if self._start_next_task(job):
                                continue
                            self._clear_task_pipeline(job)
                            job.status = "success"
                        else:
                            job.status = "success"

                        if job.status == "success":
                            # Retires right away either way: the export runs on
                            # its own thread and settles the final status there.
                            self._submit_post_success_export(job)
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
                    self._run_post_batch_action_if_drained()

                    if selected_job is not None and job == selected_job:
                        selected_job.log_changed = True
                        if callable(on_selected_retired):
                            on_selected_retired()

    #: A tick that takes longer than this is worth knowing about: the handler
    #: lock is held throughout, so nothing answers while it runs.
    SLOW_TICK_S = 1.0

    #: How often the scheduler says it is still alive, in seconds.
    HEARTBEAT_S = 60.0

    def _tick(self):
        """One scheduling + IO tick (headless, no curses)."""
        started = time.time()
        self._tick_once()
        duration = time.time() - started

        self._tick_count += 1
        self._tick_time_total += duration
        if duration > self._tick_time_max:
            self._tick_time_max = duration
        if duration >= self.SLOW_TICK_S:
            diagnostics.log(
                "slow tick",
                seconds=duration,
                jobs=len(self.job_list),
                running=len(self.running_job_list),
                queued=self.job_queue.qsize(),
                retired=len(self.retired_job_list),
            )
        self._heartbeat(started)

    def _heartbeat(self, now):
        """
        Say, once in a while, what the session is carrying.

        A frozen daemon leaves no other trace: the heartbeat stopping, and the
        tick times just before it stopped, are what says whether it was killed
        or ground to a halt.
        """
        if now - self._last_heartbeat < self.HEARTBEAT_S:
            return
        self._last_heartbeat = now
        ticks = max(1, self._tick_count)
        diagnostics.log(
            "heartbeat",
            jobs=len(self.job_list),
            running=len(self.running_job_list),
            queued=self.job_queue.qsize(),
            retired=len(self.retired_job_list),
            log_lines=sum(len(job.log_history) for job in self.job_list),
            ticks=self._tick_count,
            tick_avg=self._tick_time_total / ticks,
            tick_max=self._tick_time_max,
            threads=threading.active_count(),
            failures=self._tick_failures,
        )
        self._tick_count = 0
        self._tick_time_total = 0.0
        self._tick_time_max = 0.0

    def _tick_once(self):
        with self._lock:
            self._update_jobs_state()
            self._check_resource_guard_unlocked()

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
                    diagnostics.log_exception("API command failed", e)
                    with self._lock:
                        if 0 <= self.selected_job_index < len(self.job_list):
                            self.job_list[self.selected_job_index].log_history.append(
                                printc.colors.RED + f"API command error: {e}" + printc.colors.ENDC
                            )

                try:
                    self._tick()
                except Exception as error:
                    # An exception here used to end the scheduler thread while
                    # the API kept answering: the session stayed reachable,
                    # reported its jobs, and never advanced a single one of
                    # them again. Keep going, and leave a trace of why.
                    diagnostics.log_exception("tick failed", error)
                    self._tick_failures += 1
                time.sleep(float(tick_interval))
        except BaseException as error:
            diagnostics.log_exception("scheduler thread stopped", error)
            raise
        finally:
            with self._lock:
                self._headless_running = False
            diagnostics.log("scheduler stopped", jobs=len(self.job_list), failures=self._tick_failures)

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
        # Exports outlive the scheduler on purpose: a job that ran for an hour
        # and whose record is still being written must not lose it because the
        # session was asked to stop.
        e = self._export_thread
        if e is not None:
            e.join(timeout=float(timeout))
        if terminate_jobs:
            with self._lock:
                self.terminate_all_jobs()

    def run_api(
        self,
        host: str = hard_settings.daemon_default_host,
        port: int = hard_settings.daemon_default_port,
        log_level: str = "info",
        auth=None,
        allow_remote_bind: bool = False,
    ):
        """Run a FastAPI+Uvicorn server exposing REST + WebSocket controls.

        Imports are lazy so this file does not require FastAPI unless you call run_api().

        The API is authenticated: when no ``auth`` is given, tokens are
        generated and printed once on stdout, since a caller with no way to
        learn them could not use the server it just started. It binds loopback
        only unless ``allow_remote_bind`` says otherwise.
        """
        from odatix.lib.parallel_job_handler.api import run_parallel_job_api
        from odatix.lib.parallel_job_handler.auth import ApiAuth

        if auth is None:
            auth = ApiAuth.generate(bound_host=host)
            printc.note("Session control token: " + auth.control_token, script_name)
            printc.note("Session read-only token: " + auth.read_token, script_name)

        return run_parallel_job_api(
            self,
            auth=auth,
            host=host,
            port=int(port),
            log_level=str(log_level),
            allow_remote_bind=bool(allow_remote_bind),
        )

    def start_api_background(
        self,
        host: str = hard_settings.daemon_default_host,
        port: int = hard_settings.daemon_default_port,
        log_level: str = "info",
        start_headless_on_startup: bool = False,
        quiet: bool = True,
        auth=None,
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
                auth=auth,
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

    def start_job(self, job):
        # Run generate command
        if not job.generate_rtl:
            self.run_job(job)
            self.running_job_list.append(job)
            self._running_jobs.add(job)
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
                bufsize=0,
            )

            self.set_nonblocking(process.stdout)
            self.set_nonblocking(process.stderr)

            job.process = process
            job.status = "starting"
            job.start_time = time.time()
            self.running_job_list.append(job)
            self._running_jobs.add(job)
        except subprocess.CalledProcessError:
            job.status = "failed"
            self.retire_job(job, progress=0)
            job.log_history.append(printc.colors.RED + "error: rtl generation failed" + printc.colors.ENDC)
            job.log_history.append(printc.colors.CYAN + "note: look for earlier error to solve this issue" + printc.colors.ENDC)
            return

    @staticmethod
    def _stage_sort_key(stage):
        if isinstance(stage, int):
            return (0, stage)
        stage_str = str(stage)
        if stage_str.lstrip("-").isdigit():
            return (0, int(stage_str))
        return (1, stage_str)

    @staticmethod
    def _task_name(task):
        if isinstance(task, dict):
            taskname = task.get("name", None)
        else:
            taskname = getattr(task, "name", None)
        if taskname is None and hasattr(task, "getName"):
            taskname = task.getName()
        if taskname is None:
            taskname = str(task)
        return str(taskname)

    @staticmethod
    def _task_full_command(task):
        if isinstance(task, dict):
            task_command = task.get("command", None)
        else:
            task_command = getattr(task, "command", None)
        if task_command is None and hasattr(task, "getCommand"):
            task_command = task.getCommand()
        if task_command is None:
            task_command = ""

        if isinstance(task_command, list):
            task_command = "\n".join(map(str, task_command))

        cmdlines = task_command.split("\n")
        cmdlines = [ln.lstrip().rstrip() for ln in cmdlines]
        return " && ".join([c[1:] if c.startswith("@") else c for c in cmdlines if c])

    @staticmethod
    def _task_steps(task):
        """
        The steps a task covers. A task running a whole session of the tool
        covers several of them; any other one stands for itself.
        """
        steps = task.get("steps") if isinstance(task, dict) else getattr(task, "steps", None)
        if isinstance(steps, list) and steps:
            return [str(name) for name in steps]
        return [ParallelJobHandler._task_name(task)]

    def _build_task_pipeline(self, job):
        pipeline = []
        for _, tasks in sorted(job.command.items(), key=lambda x: self._stage_sort_key(x[0])):
            for task in tasks:
                taskname = self._task_name(task)
                full_command = self._task_full_command(task)
                if full_command:
                    pipeline.append((taskname, full_command, self._task_steps(task)))
        return pipeline

    @staticmethod
    def _record_completed_step(job):
        """
        Record the steps a stepped job just completed, so a later run can resume
        after them instead of redoing them. A task running a whole session of the
        tool completes several steps at once; the tool's own scripts may have
        recorded them one by one already, which is what makes a session that dies
        halfway resumable, and recording them again here is harmless. Jobs that
        did not opt in (workflows, and flows that are not split into steps) are
        left alone.
        """
        tracking = getattr(job, "step_tracking", None)
        step_names = getattr(job, "_current_task_steps", None)
        if not isinstance(tracking, dict) or not step_names:
            return
        tmp_dir = tracking.get("tmp_dir")
        if not tmp_dir:
            return
        for step_name in step_names:
            try:
                import odatix.lib.job_steps as job_steps

                job_steps.record_completed_step(tmp_dir, step_name, flow=tracking.get("flow"))
            except Exception as e:
                job.log_history.append(
                    printc.colors.YELLOW + "warning: could not record step '" + str(step_name) + "': " + str(e) + printc.colors.ENDC
                )

    @staticmethod
    def _clear_task_pipeline(job):
        for attr in ("_task_pipeline", "_task_index", "_current_task_name", "_current_task_steps",
                     "current_step_index", "current_step_started_at", "_task_steps_recorded_before"):
            if hasattr(job, attr):
                delattr(job, attr)

    @staticmethod
    def _recorded_step_count(job):
        """How many steps the job directory has recorded so far, or None."""
        tracking = getattr(job, "step_tracking", None)
        tmp_dir = tracking.get("tmp_dir") if isinstance(tracking, dict) else None
        if not tmp_dir:
            return None
        try:
            import odatix.lib.job_steps as job_steps

            return len(job_steps.completed_step_names(tmp_dir))
        except Exception:
            return None

    @staticmethod
    def _step_position_of(job, step_names, fallback):
        """Where the steps a task covers start within the run's step list."""
        all_steps = getattr(job, "step_names", None) or []
        if step_names and step_names[0] in all_steps:
            return all_steps.index(step_names[0])
        return fallback

    def _start_next_task(self, job):
        pipeline = getattr(job, "_task_pipeline", None)
        if pipeline is None:
            return False

        task_index = int(getattr(job, "_task_index", 0))
        if task_index >= len(pipeline):
            return False

        taskname, full_command, step_names = pipeline[task_index]
        job._task_index = task_index + 1
        job._current_task_name = taskname
        job._current_task_steps = step_names
        # Which step the progress read from the status files belongs to, and
        # since when they speak for it (see ParallelJob._read_status_file). A
        # task can cover several steps, so its position is that of the first one
        # it runs rather than its own rank in the pipeline.
        job.current_step_index = self._step_position_of(job, step_names, task_index)
        job.current_step_started_at = time.time()
        # A task running several steps at once reports its progress once per
        # step: how many steps were already recorded when it started is what
        # lets the progress tell them apart (see ParallelJob._task_step_offset).
        job._task_steps_recorded_before = self._recorded_step_count(job) if len(step_names or []) > 1 else None

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
            bufsize=0,
            preexec_fn=preexec_fn,
        )

        if job.start_time is None:
            job.start_time = time.time()
        job.process = process
        job.status = "running"

        if sys.platform == "win32":
            threading.Thread(
                target=read_pipe_windows,
                args=(process.stdout, job, lambda j, d: self._append_job_log(j, d, stream_key="stdout")),
                daemon=True,
            ).start()
            threading.Thread(
                target=read_pipe_windows,
                args=(process.stderr, job, lambda j, d: self._append_job_log(j, d, stream_key="stderr")),
                daemon=True,
            ).start()
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
                bufsize=0,
                preexec_fn=preexec_fn,
            )

            if job.start_time is None:
                job.start_time = time.time()
            job.process = process
            job.status = "running"

            if sys.platform == "win32":
                threading.Thread(
                    target=read_pipe_windows,
                    args=(process.stdout, job, lambda j, d: self._append_job_log(j, d, stream_key="stdout")),
                    daemon=True,
                ).start()
                threading.Thread(
                    target=read_pipe_windows,
                    args=(process.stderr, job, lambda j, d: self._append_job_log(j, d, stream_key="stderr")),
                    daemon=True,
                ).start()
            else:
                self.set_nonblocking(process.stdout)
                self.set_nonblocking(process.stderr)
        elif isinstance(job.command, dict):
            if not hasattr(job, "_task_pipeline"):
                # The pipeline is what is left to do: the steps already completed
                # in the job directory were dropped when it was built (see
                # odatix.components.synthesis_common.build_job_command).
                job._task_pipeline = self._build_task_pipeline(job)
                job._task_index = 0
                resume_index = int(getattr(job, "resume_step_index", 0) or 0)
                if resume_index > 0:
                    skipped = ", ".join((getattr(job, "step_names", None) or [])[:resume_index])
                    job.log_history.append(
                        printc.colors.CYAN + "Resuming: already done -> " + skipped + printc.colors.ENDC
                    )

            if not self._start_next_task(job):
                self._clear_task_pipeline(job)
                job.status = "success"

    def queue_job(self, job):
        job.status = "queued"
        self.job_queue.put(job)

    def retire_job(self, job, progress=100):
        job.stop_time = time.time()
        # A job can be retired before it ever started running -- rtl generation
        # that failed outright never made it into the running list -- and
        # list.remove() would raise there, killing the scheduler thread.
        try:
            self.running_job_list.remove(job)
        except ValueError:
            pass
        self._running_jobs.discard(job)
        job.progress = progress
        self.retired_job_list.append(job)
        self._retired_jobs.add(job)

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
                    if pipe is job.process.stdout:
                        stream_key = "stdout"
                    elif pipe is job.process.stderr:
                        stream_key = "stderr"
                    else:
                        stream_key = "default"
                    self._read_available_pipe_data(job, pipe, stream_key=stream_key)
                    break

    def curses_main(self, stdscr):
        return curses_ui.curses_main(self, stdscr)

    def run(self):
        return curses_ui.run(self)
