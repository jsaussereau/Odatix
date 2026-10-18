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
from odatix.lib.parallel_job_handler.daemon_control import (
    enqueue_parallel_jobs,
    attach_monitor,
    MonitorUnavailableError,
    SessionGoneError,
)


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


def run_overview(valid_count, tool=None, targets=None, flow=None, nb_jobs=None, session=None):
    """
    The line that sums up a run before it starts, e.g.
    "Total: 2 jobs | tool: vivado | target: xc7a100t | flow: default | 2 in parallel".
    The items left empty are left out.
    """
    count = int(valid_count)
    items = ["Total: {0} job{1}".format(count, "" if count == 1 else "s")]
    if tool:
        items.append("tool: " + str(tool))
    if targets:
        targets = [str(target) for target in (targets if isinstance(targets, (list, tuple)) else [targets])]
        items.append(("target: " if len(targets) == 1 else "targets: ") + ", ".join(targets))
    if flow:
        items.append("flow: " + str(flow))
    try:
        parallel = min(int(nb_jobs), count) if nb_jobs else None
    except (TypeError, ValueError):
        parallel = None
    if parallel:
        items.append("{0} in parallel".format(parallel))
    if session:
        items.append("session: " + str(session))
    return " | ".join(items)


def confirm_valid_jobs(valid_count, ask_continue, ask_to_continue_callback, script_name=None, plan=None, overview=None):
    """
    Ask before a run starts, after its plan is printed.

    Args:
        overview (dict): what :func:`run_overview` adds to the "Total" line
            (tool, targets, flow, nb_jobs, session).
    """
    if valid_count > 0:
        if ask_continue:
            from odatix.lib import printc

            printc.bold("\n" + run_overview(valid_count, **(overview or {})))
            ask_to_continue_callback()
        return

    if plan is not None:
        from odatix.lib.run_report import Category
        from odatix.run.errors import NOTHING_TO_RUN

        counts = plan.counts()
        cached = counts.get(Category.CACHED, 0)
        in_session = counts.get(Category.DAEMON, 0)
        if (cached or in_session) and not counts.get(Category.ERROR, 0):
            # Not a failure: the jobs are done, or a session is doing them.
            from odatix.lib import printc

            # "In a session" is not "running": a session keeps its jobs once
            # they are over, until it is closed.
            if in_session and cached:
                reason = "every selected job is already done, or already in a session (running or over)"
            elif in_session:
                reason = "every selected job is already in a session (running or over)"
            else:
                reason = "every selected job is already done (-o/--overwrite runs them again)"
            printc.note("Nothing to run: " + reason, script_name or "")
            if in_session:
                printc.note('"odatix ls" lists the sessions, "odatix monitor -S <session>" follows one', script_name or "")
            raise SystemExit(NOTHING_TO_RUN)
    raise SystemExit(-1)


def settle_tool_checks(tool_checks, tool_check_sink=None, needed=True):
    """
    Close the background eda tool checks started while the settings were read.

    Without a sink (terminal flows), every check is waited for: a failed one
    reports itself and exits. With a sink (the GUI), the still-running handles
    are handed over instead, so the caller can show the run plan right away and
    report the outcome its own way.

    A run with nothing to run (needed=False) does not need the tool at all: its
    checks are stopped rather than waited for, so "Nothing to run" comes right
    away instead of after the tool has started up (several seconds for Vivado).
    """
    for tool_check in tool_checks:
        if tool_check is not None and not needed:
            tool_check.cancel()
            continue
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


def resolve_param_target_file(tmp_dir, target_filename, generate_rtl):
    """
    Where a "param_target_file" is read from, inside a work directory.

    The path is written against the sources, which is what the architecture
    editor previews it against. When the RTL is generated, "design_path" is
    copied whole at the root of the work directory, so the path is used as is.
    Otherwise "rtl_path" is copied into the "rtl" subfolder, which is then the
    directory the path is relative to.
    """
    if generate_rtl:
        return os.path.join(tmp_dir, target_filename)
    return os.path.join(tmp_dir, hard_settings.work_rtl_path, target_filename)


def resolve_workflow_param_target_file(tmp_dir, target_filename):
    """
    Same, for a workflow: it has no RTL, and its "sources" are copied whole at
    the root of the work directory, so the path is used as is.
    """
    return os.path.join(tmp_dir, target_filename)


def resolve_sim_param_target_file(tmp_dir, target_filename):
    """
    Same, for a simulation: its target file can be one of the simulation's own
    sources, copied at the root of the work directory, as well as one of the
    architecture's RTL files. Whichever is there is the one used.
    """
    at_root = os.path.join(tmp_dir, target_filename)
    if os.path.isfile(at_root):
        return at_root
    in_rtl = os.path.join(tmp_dir, hard_settings.work_rtl_path, target_filename)
    if os.path.isfile(in_rtl):
        return in_rtl
    return at_root


def replace_and_write_param_domains(
    tmp_dir,
    arch_name,
    param_domains,
    default_target_filename,
    target_filename_getter,
    debug,
    generate_rtl=False,
    target_resolver=None,
    timestamp=None,
    virtual_domains=None,
    arch_path=None,
    main_param_file=None,
):
    domain_dict = {}
    arch_config = re.sub('.*/', '', str(arch_name).split("+")[0])
    domain_dict["__main__"] = arch_config
    if timestamp is not None:
        domain_dict["__timestamp__"] = timestamp

    for param_domain in param_domains:
        if param_domain.use_parameters:
            target_filename = target_filename_getter(param_domain) or default_target_filename
            if target_resolver is not None:
                param_target_file = target_resolver(tmp_dir, target_filename)
            else:
                param_target_file = resolve_param_target_file(tmp_dir, target_filename, generate_rtl)
            success = replace_params(
                base_text_file=param_target_file,
                replacement_text_file=param_domain.param_file,
                output_file=param_target_file,
                start_delimiter=param_domain.start_delimiter,
                stop_delimiter=param_domain.stop_delimiter,
                replace_all_occurrences=False,
                silent=False if debug else True,
            )
            # A domain with no value is one a job declared for itself rather than a dimension
            # of the sweep, so it names nothing in the result record.
            if success and param_domain.domain_value != "":
                domain_dict[param_domain.domain] = param_domain.domain_value
        elif param_domain.domain_value != "":
            domain_dict[param_domain.domain] = param_domain.domain_value

    # Virtual domains (variables) have no parameter file to substitute, but they are
    # still a dimension of the sweep: without them here, they never reach the results.
    for domain, domain_value in (virtual_domains or {}).items():
        if domain_value != "":
            domain_dict[domain] = domain_value

    # Where the job sits in the design space of its architecture, so that a
    # search run later can start from what this run measured instead of
    # measuring it again (see :mod:`odatix.workspace.design_point`). Imported
    # here: preparing a job is the only thing that needs the workspace api, and
    # the daemon imports this module for everything else it does.
    from odatix.workspace import design_point

    point = design_point.coordinates(
        arch_path=arch_path,
        arch_name=arch_name,
        param_domains=param_domains,
        virtual_domains=virtual_domains,
        main_param_file=main_param_file,
    )
    if point:
        domain_dict[design_point.POINT_KEY] = point

    with open(os.path.join(tmp_dir, hard_settings.param_domains_filename), "w") as param_domains_file:
        yaml.dump(domain_dict, param_domains_file, default_flow_style=False, sort_keys=False)


def start_parallel_jobs(
    parallel_jobs: ParallelJobHandler,
    use_api=True,
    start_headless_on_startup=False,
    detach=False,
    session=None,
    configure=True,
):
    """Enqueue jobs into the background daemon, then optionally attach monitor.

    `configure` also applies how this run wants the daemon to behave; a run that
    is itself running inside the session it enqueues into leaves it alone (see
    enqueue_parallel_jobs).

    Once the monitor is closed, the terminal keeps a line of what happened (see
    say_monitor_exit), and the summary of the driver job of the run, if it has
    one (see replay_summaries).

    The `use_api` and `start_headless_on_startup` arguments are kept for
    backward compatibility with older call sites.
    """
    _state, _response = enqueue_parallel_jobs(parallel_jobs, session=session, configure=configure)
    from odatix.lib import printc

    # The jobs of this run in the session: a session named with "-S" may also
    # run the jobs of other runs, which "-E" does not wait for.
    job_ids = getattr(parallel_jobs, "session_job_ids", None)
    if not isinstance(job_ids, list):
        from odatix.lib.parallel_job_handler.daemon_control import session_job_ids

        job_ids = session_job_ids(_response, len(getattr(parallel_jobs, "job_list", []) or []))

    if detach:
        # A run that reconfigures nothing is part of a session already (an
        # exploration batch): its driver says what it does, not each batch.
        if configure:
            name = str(_state.get("session_name") or session or "")
            printc.note(
                "{} job(s) handed to session {}: follow them with \"odatix monitor -S {}\", "
                "stop it with \"odatix stop -S {}\"".format(
                    len(getattr(parallel_jobs, "job_list", []) or []), _state.get("session_id") or name, name, name
                ),
                "run",
            )
        return

    # Attach to the session the jobs actually went to, by its id: a session
    # listening on a unix socket has no host/port to be found by, and
    # falling back to the default endpoint would attach to nothing.
    session_ref = str(_state.get("session_id") or _state.get("session_name") or session or "") or None
    auto_exit = bool(getattr(parallel_jobs, "auto_exit", False))
    try:
        monitor_exit = attach_monitor(session=session_ref, auto_exit=auto_exit, job_ids=job_ids if auto_exit else None)
    except MonitorUnavailableError as e:
        # The jobs are already in the session: they run whatever the terminal.
        from odatix.lib.parallel_job_handler.daemon_control import follow_hint

        printc.warning(getattr(e, "reason", str(e)), "run")
        if not auto_exit:
            printc.note(
                "The jobs keep running in session {}: {}".format(session_ref, follow_hint(session_ref)), "run",
            )
            return
        # "-E" asks for the run to be over when the command returns, monitor or
        # not: without one, the jobs are waited for here instead.
        if wait_for_session(_state, job_ids=job_ids):
            parallel_jobs.followed_in_monitor = True
            replay_summaries(parallel_jobs, _state, job_ids)
            close_finished_session(_state, job_ids=job_ids, analyses=_only_analyses(parallel_jobs))
        return
    except SessionGoneError as e:
        printc.warning(str(e), "run")
        return
    parallel_jobs.followed_in_monitor = True
    replay_summaries(parallel_jobs, _state, job_ids)
    if auto_exit and getattr(monitor_exit, "reason", "auto") in ("auto", None):
        close_finished_session(_state, job_ids=job_ids, analyses=_only_analyses(parallel_jobs))
    else:
        say_monitor_exit(monitor_exit)


def _only_analyses(parallel_jobs):
    """Whether every job of the run is an RTL analysis (see close_finished_session)."""
    jobs = list(getattr(parallel_jobs, "job_list", []) or [])
    kinds = set()
    for job in jobs:
        export = getattr(job, "post_run_export", None)
        kinds.add(str(export.get("kind", "")).strip().lower() if isinstance(export, dict) else "")
    return bool(jobs) and kinds == {"analysis"}


def say_monitor_exit(monitor_exit, script_name="run"):
    """
    Leave a line in the terminal once the monitor is closed: the screen goes
    back to what it was before the monitor, and nothing would tell which
    session goes on, how to get back to it, or what became of the jobs.
    """
    from odatix.lib import printc
    from odatix.lib.parallel_job_handler.daemon_monitor import exit_messages

    for level, text in exit_messages(monitor_exit):
        (printc.warning if level == "warning" else printc.note)(text, script_name)


def replay_summaries(parallel_jobs, state, job_ids, script_name="run"):
    """
    Print again, once the monitor is closed, the summary a job of the run
    wrote to its log: what was only on the monitor's screen is gone with it.

    A job asks for it with a `summary_marker` attribute: its log is printed
    from the last line containing that text to its end. It is read from the
    session while it is alive, else from the job's console log, if it has one.
    Nothing is printed for a job without a marker.
    """
    from odatix.lib import printc

    jobs = list(getattr(parallel_jobs, "job_list", []) or [])
    for index, job in enumerate(jobs):
        marker = getattr(job, "summary_marker", None)
        if not marker:
            continue
        job_id = job_ids[index] if isinstance(job_ids, list) and index < len(job_ids) else None
        lines = _job_log_lines(state, job_id, job)
        start = None
        for position, line in enumerate(lines):
            if marker in printc.strip_colors(line):
                start = position
        if start is None:
            continue
        print()
        for line in lines[start:]:
            print(line + printc.colors.ENDC)
        sys.stdout.flush()


def _job_log_lines(state, job_id, job):
    """The log of a job of a session, from the session, else from its console log."""
    if job_id is not None:
        from odatix.lib.parallel_job_handler.daemon_control import _api_request

        try:
            snapshot = _api_request(
                state, "GET",
                "/status?logs_job_id={}&include_jobs=0&logs_offset=0&logs_limit=-1".format(int(job_id)),
                timeout=5.0,
            )
            logs = snapshot.get("logs") if isinstance(snapshot, dict) else None
            if isinstance(logs, dict) and isinstance(logs.get("lines"), list):
                return [str(line) for line in logs["lines"]]
        except Exception:
            pass
    path = getattr(job, "console_log", None)
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read().splitlines()
        except OSError:
            pass
    return []


def _run_counts(session, job_ids):
    """How the jobs of the run are doing (every job of the session when the ids are unknown)."""
    from odatix.run.session import count_jobs

    if job_ids is None:
        return session.counts()
    wanted = set(int(job_id) for job_id in job_ids)
    return count_jobs([job for job in session.jobs() if job["id"] in wanted])


def wait_for_session(state, script_name="run", poll_interval=5.0, job_ids=None):
    """
    What "-E" does when the terminal cannot show the job monitor (a run started
    by a script, under nohup, in a CI job): wait for the jobs of the run to be
    over, saying how they are going as it changes, so that the session can then
    be closed as it is once the monitor closes by itself.

    Ctrl+C stops the waiting, not the jobs.

    Args:
        job_ids (list): the jobs of the run in the session. Every job of the
            session when None.

    Returns:
        bool: whether every job is over. False when the waiting was stopped or
        the session went away.
    """
    from odatix.lib import printc
    from odatix.run.session import Session, SessionError

    session = Session(state)
    printc.note(
        "Waiting for the jobs of this run in session {} to be over (-E). "
        "Ctrl+C stops waiting; the jobs keep running".format(session.id),
        script_name,
    )
    said = None
    guard_said = False
    try:
        while True:
            counts = _run_counts(session, job_ids)
            if not guard_said:
                guard_said = _say_auto_paused(session, script_name)
            line = "{}/{} job(s) over: {} succeeded, {} failed, {} running, {} queued".format(
                counts["done"] + counts["failed"], counts["total"],
                counts["done"], counts["failed"], counts["running"], counts["queued"],
            )
            if line != said:
                printc.say(line, script_name)
                sys.stdout.flush()
                said = line
            if counts["running"] == 0 and counts["queued"] == 0:
                return True
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        printc.note(
            "Stopped waiting: the jobs keep running in session {}. Follow them with "
            "\"odatix monitor -S {}\", stop it with \"odatix stop -S {}\"".format(session.id, session.name, session.name),
            script_name,
        )
    except SessionError as error:
        printc.warning(str(error), script_name)
    return False


def _say_auto_paused(session, script_name):
    """
    Say it when auto-pause holds jobs: nothing else on a terminal without the
    monitor tells why a run takes longer than it should.

    Returns:
        bool: whether it was said.
    """
    from odatix.lib import printc

    try:
        paused = int((session.status().get("resource_guard") or {}).get("auto_paused") or 0)
    except Exception:
        return False
    if paused <= 0:
        return False
    printc.note(
        "{} job(s) paused by auto-pause: the machine is overloaded. They resume once the load goes down; "
        "\"odatix monitor -S {}\" then \"a\" turns auto-pause off (or \"resource_guard: No\" in odatix.yml)".format(
            paused, session.name,
        ),
        script_name,
    )
    return True


#: How long (s) "-E" waits for the last exports of its jobs to be written, once
#: the monitor has closed, before it says they are still going.
EXPORT_SETTLE_TIMEOUT = 30.0


def close_finished_session(state, script_name="run", job_ids=None, settle_timeout=EXPORT_SETTLE_TIMEOUT, analyses=False):
    """
    What "-E" does once the monitor closed by itself: the jobs of the run are
    over, so the session is closed too -- what the popup of the monitor does by
    default -- and what became of them is printed, since the monitor is gone.

    A session that also runs the jobs of other runs ("-S") is left open, and
    the command says how to follow it.

    Args:
        job_ids (list): the jobs of the run in the session. Every job of the
            session when None.
        analyses (bool): the jobs are RTL analyses. What they found is in
            the report the command prints next, and a job that "failed" may
            only have found an error in the design: no success count here,
            it would say something else than the report.

    Returns:
        dict: how many jobs of the run ended how (see
        odatix.run.session.count_jobs), or None when the session could not
        be asked.
    """
    from odatix.lib import printc
    from odatix.run.session import Session, SessionError

    session = Session(state)
    if not session.is_alive():
        return None  # closed from the monitor already ("q", or killing every job)
    try:
        counts = _run_counts(session, job_ids)
        # A job still writing its results is not over: give it the time to.
        deadline = time.time() + float(settle_timeout)
        while (counts["running"] or counts["queued"]) and time.time() < deadline:
            time.sleep(0.5)
            counts = _run_counts(session, job_ids)
        everything = counts if job_ids is None else session.counts()
    except SessionError as error:
        printc.warning(str(error), script_name)
        return None

    total = counts["total"]
    summary = "{}/{} job(s) succeeded".format(counts["done"], total)
    if counts["failed"]:
        summary += ", {} failed".format(counts["failed"])
    if analyses:
        summary = "{}/{} analysis job(s) over".format(counts["done"] + counts["failed"], total)
    if counts["running"] or counts["queued"]:
        printc.note(
            summary + "; {} still running or queued in session {}: follow them with "
            "\"odatix monitor -S {}\"".format(counts["running"] + counts["queued"], session.id, session.name),
            script_name,
        )
        return counts

    if counts["failed"] and not analyses:
        printc.warning(summary, script_name)
    else:
        printc.note(summary + (": the report below says what they found" if analyses else ""), script_name)

    others = everything["running"] + everything["queued"]
    if others:
        # Other runs share the session: it stays for them.
        printc.note(
            "Session {} kept open: {} job(s) of other runs are still running or queued in it; "
            "follow them with \"odatix monitor -S {}\"".format(session.id, others, session.name),
            script_name,
        )
        return counts

    closed = session.stop()
    if closed:
        printc.note("Session {} closed".format(session.id), script_name)
    else:
        printc.warning(
            "Could not confirm that session {} is closed: \"odatix stop -S {}\" stops it".format(session.id, session.name),
            script_name,
        )
    return counts
