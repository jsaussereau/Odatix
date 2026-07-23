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
import re
import sys
import threading
import time
import yaml

from odatix.components.replace_params import replace_params
import odatix.lib.hard_settings as hard_settings
from odatix.lib.utils import resolve_nb_jobs
from odatix.lib.parallel_job_handler import ParallelJobHandler
from odatix.lib.parallel_job_handler.daemon_control import enqueue_parallel_jobs, attach_monitor


######################################
# Job-preparation progress bar
######################################

# State shared with the GUI (jobs_config polls get_prepare_progress() while the
# preparation thread runs): {label, total, done, ok, failed, active}.
_prepare_progress_lock = threading.Lock()
_prepare_progress_state = None


class _ProgressOutputProxy:
    """Temporarily keeps job output from colliding with a live progress bar."""

    def __init__(self, stream, progress):
        self._stream = stream
        self._progress = progress

    def write(self, text):
        return self._progress._write_job_output(self._stream, text)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


class PrepareProgress:
    """
    Progress of the job-preparation phase (copies into the work directory,
    parameter replacements, ...), shared by every run flow.

    On a terminal (CLI), renders an in-place colored bar: the green section is
    the jobs prepared successfully, the red section the jobs whose preparation
    failed (e.g. a missing design_path), with ok/failed counts. Error messages
    printed while a job is being prepared stay on their own lines.

    The state is also published through get_prepare_progress() so the GUI can
    render its own progress bar while the preparation thread runs (its stdout
    is redirected to a log buffer, not a terminal).
    """

    BAR_WIDTH = 30

    GREEN = "\033[92m"
    RED = "\033[91m"
    GREY = "\033[90m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    REDRAW_INTERVAL = 0.25
    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self, total, label="Preparing jobs", stream=None):
        self.total = max(int(total), 0)
        self.label = label
        self.done = 0
        self.ok = 0
        self.failed = 0
        self.stream = stream if stream is not None else sys.stdout
        isatty = getattr(self.stream, "isatty", None)
        self.isatty = bool(isatty()) if callable(isatty) else False
        self._draw_lock = threading.Lock()
        # Keep every displayed value at a fixed width. This lets _draw()
        # overwrite the previous frame with "\r" only, without the terminal
        # line-clear escape sequence that causes visible flickering.
        self._num_width = len(str(self.total)) if self.total > 0 else 1
        self._spinner_index = 0
        self._line_visible = False
        self._job_output_open = False
        self._redraw_not_before = 0.0
        self._stop_event = threading.Event()
        self._redraw_thread = None
        self._stdout_before_job = None
        self._stderr_before_job = None
        self._publish(active=True)
        if self.isatty and self.total > 0:
            self._draw()
            self._redraw_thread = threading.Thread(target=self._redraw_loop, daemon=True)
            self._redraw_thread.start()

    def _redraw_loop(self):
        while not self._stop_event.wait(self.REDRAW_INTERVAL):
            self._draw()

    def job_starting(self):
        """Capture stdout/stderr so job logs can safely hide the live bar."""
        if self.isatty and self.total > 0:
            if self.stream is sys.stdout:
                self._stdout_before_job = sys.stdout
                self._stderr_before_job = sys.stderr
                sys.stdout = _ProgressOutputProxy(self._stdout_before_job, self)
                sys.stderr = _ProgressOutputProxy(self._stderr_before_job, self)

    def job_finished(self):
        """Restore the streams captured for the current job."""
        if self._stdout_before_job is not None:
            sys.stdout = self._stdout_before_job
            sys.stderr = self._stderr_before_job
            self._stdout_before_job = None
            self._stderr_before_job = None

    def update(self, ok):
        self.done += 1
        if ok:
            self.ok += 1
        else:
            self.failed += 1
        self._publish(active=True)
        if self.isatty and self.total > 0:
            self._draw()

    def finish(self):
        self.job_finished()
        if self._redraw_thread is not None:
            self._stop_event.set()
            self._redraw_thread.join(timeout=1)
        self._publish(active=False)
        if self.total <= 0:
            return
        if self.isatty:
            self._draw()
            self.stream.write("\n")
            self.stream.flush()
        else:
            # Not a terminal (e.g. the GUI log buffer): single summary line.
            summary = "{}: {}/{} prepared".format(self.label, self.ok, self.total)
            if self.failed > 0:
                summary += " ({} failed)".format(self.failed)
            self.stream.write(summary + "\n")

    def _publish(self, active):
        global _prepare_progress_state
        with _prepare_progress_lock:
            _prepare_progress_state = {
                "label": self.label,
                "total": self.total,
                "done": self.done,
                "ok": self.ok,
                "failed": self.failed,
                "active": bool(active),
            }

    def _write_job_output(self, stream, text):
        """Write job output after hiding the bar only if it is currently shown."""
        if not text:
            return 0
        with self._draw_lock:
            if self._line_visible:
                self.stream.write("\r\033[K")
                self.stream.flush()
                self._line_visible = False
            written = stream.write(text)
            self._job_output_open = not (text.endswith("\n") or text.endswith("\r"))
            if "\n" in text or "\r" in text:
                stream.flush()
                # Do not redraw the bar between consecutive log lines. This
                # avoids an erase/redraw flash when several errors are emitted
                # in quick succession, while the spinner resumes for long jobs.
                self._redraw_not_before = time.monotonic() + self.REDRAW_INTERVAL
            return written

    def _draw(self):
        # Snapshot the counters outside the lock (plain int reads/writes are
        # atomic under the GIL); only the actual terminal write is guarded, so
        # the redraw thread never blocks update()/job_starting() for long.
        total, done, ok, failed = self.total, self.done, self.ok, self.failed
        width = self.BAR_WIDTH
        ok_width = int(round(width * ok / total)) if total else 0
        failed_width = int(round(width * failed / total)) if total else 0
        if ok_width + failed_width > width:
            failed_width = width - ok_width
        empty_width = width - ok_width - failed_width
        bar = (
            self.GREEN + "█" * ok_width
            + self.RED + "█" * failed_width
            + self.GREY + "░" * empty_width
            + self.RESET
        )
        w = self._num_width
        counts = (
            " " + self.GREEN + "✔ {:>{w}d}".format(ok, w=w) + self.RESET
            + "  " + self.RED + "✘ {:>{w}d}".format(failed, w=w) + self.RESET
        )
        line = "\r{}{}{} {} [{}] {:>{w}d}/{:>{w}d} {}".format(
            self.BOLD, self.label, self.RESET, self.SPINNER[self._spinner_index], bar, done, total, counts, w=w
        )
        with self._draw_lock:
            if self._job_output_open or time.monotonic() < self._redraw_not_before:
                return
            self.stream.write(line)
            self.stream.flush()
            self._line_visible = True
            self._spinner_index = (self._spinner_index + 1) % len(self.SPINNER)


def get_prepare_progress():
    """Snapshot of the current job-preparation progress (None outside a run)."""
    with _prepare_progress_lock:
        return dict(_prepare_progress_state) if _prepare_progress_state else None


def reset_prepare_progress():
    global _prepare_progress_state
    with _prepare_progress_lock:
        _prepare_progress_state = None


def run_prepare_loop(instances, build_job, job_list, check_cancel=None, label="Preparing jobs"):
    """
    Run build_job over every instance with a PrepareProgress bar. A job whose
    preparation fails is skipped without being appended to job_list (see the
    prepare_job implementations): success is detected by job_list growing.
    """
    progress = PrepareProgress(total=len(instances), label=label)
    try:
        for instance in instances:
            progress.job_starting()
            jobs_before = len(job_list)
            job_completed = False
            try:
                if check_cancel is not None:
                    check_cancel()
                build_job(instance)
                job_completed = True
            finally:
                progress.job_finished()
            if job_completed:
                progress.update(ok=len(job_list) > jobs_before)
    finally:
        progress.finish()


def normalize_run_settings(overwrite, noask, exit_when_done, log_size_limit, nb_jobs, defaults):
    _overwrite, ask_continue, _exit_when_done, _log_size_limit, _nb_jobs = defaults

    overwrite = True if overwrite else _overwrite
    exit_when_done = True if exit_when_done else _exit_when_done
    log_size_limit = int(log_size_limit) if log_size_limit is not None else _log_size_limit
    nb_jobs = resolve_nb_jobs(nb_jobs if nb_jobs is not None else _nb_jobs)

    if noask:
        ask_continue = False

    return overwrite, ask_continue, exit_when_done, log_size_limit, nb_jobs


def confirm_valid_jobs(valid_count, ask_continue, ask_to_continue_callback, script_name=None):
    if valid_count > 0:
        if ask_continue:
            from odatix.lib import printc

            printc.bold("\nTotal: " + str(valid_count))
            ask_to_continue_callback()
    else:
        raise SystemExit(-1)


def settle_tool_checks(tool_checks, tool_check_sink=None):
    """
    Close the background eda tool checks started while the settings were read.

    Without a sink (terminal flows), every check is waited for: a failed one
    reports itself and exits. With a sink (the GUI), the still-running handles
    are handed over instead, so the caller can show the run plan right away and
    report the outcome its own way.
    """
    for tool_check in tool_checks:
        if tool_check is None:
            continue
        if tool_check_sink is not None:
            tool_check_sink(tool_check)
        else:
            tool_check.wait()


def abort_if_empty_job_list(job_list, script_name=None):
    """
    Some architectures/simulations pass the initial checklist (confirm_valid_jobs)
    but still fail while their job is actually being built (e.g. a missing
    design_path): they are skipped rather than appended to job_list. If every
    job failed this way, job_list ends up empty here; without this check, the
    monitor/daemon session would still launch with zero jobs to run.
    """
    if not job_list:
        from odatix.lib import printc

        printc.error("None of the selected jobs could be prepared. See errors above for details.", script_name)
        raise SystemExit(-1)


def replace_and_write_param_domains(
    tmp_dir,
    arch_name,
    param_domains,
    default_target_filename,
    target_filename_getter,
    debug,
    timestamp=None,
):
    domain_dict = {}
    arch_config = re.sub('.*/', '', arch_name)
    domain_dict["__main__"] = arch_config
    if timestamp is not None:
        domain_dict["__timestamp__"] = timestamp

    for param_domain in param_domains:
        if param_domain.use_parameters:
            target_filename = target_filename_getter(param_domain) or default_target_filename
            param_target_file = os.path.join(tmp_dir, target_filename)
            success = replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_domain.param_file,
                output_file=param_target_file,
                start_delimiter=param_domain.start_delimiter,
                stop_delimiter=param_domain.stop_delimiter,
                replace_all_occurrences=False,
                silent=False if debug else True,
            )
            if success:
                domain_dict[param_domain.domain] = param_domain.domain_value

    with open(os.path.join(tmp_dir, hard_settings.param_domains_filename), "w") as param_domains_file:
        yaml.dump(domain_dict, param_domains_file, default_flow_style=False, sort_keys=False)


def start_parallel_jobs(
    parallel_jobs: ParallelJobHandler,
    use_api=True,
    start_headless_on_startup=False,
    detach=False,
    session=None,
):
    """Enqueue jobs into the background daemon, then optionally attach monitor.

    The `use_api` and `start_headless_on_startup` arguments are kept for
    backward compatibility with older call sites.
    """
    _state, _response = enqueue_parallel_jobs(parallel_jobs, session=session)
    if not detach:
        attach_monitor(
            host=_state.get("host", hard_settings.daemon_default_host),
            port=int(_state.get("port", hard_settings.daemon_default_port)),
            session=session,
            auto_exit=bool(getattr(parallel_jobs, "auto_exit", False)),
        )
