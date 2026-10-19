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

"""Curses monitor attached to a running daemon, using the legacy curses UI."""

import argparse
import errno
import os
import shutil
import time

import odatix.lib.printc as printc
import odatix.lib.hard_settings as hard_settings
from odatix.lib.parallel_job_handler import curses_ui
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler
from odatix.lib.parallel_job_handler.auth import TOKEN_ENV_VAR
from odatix.lib.parallel_job_handler.job import JOB_KIND, ParallelJob
from odatix.lib.parallel_job_handler.transport import Endpoint
from odatix.lib.utils import open_path_in_explorer


def _api_get(endpoint, path, timeout=1.0):
    return endpoint.request("GET", path, timeout=timeout)


def _api_post(endpoint, path, payload=None, timeout=1.0):
    return endpoint.request("POST", path, payload=payload, timeout=timeout)


def _extract_jobs(snapshot):
    jobs = snapshot.get("jobs") if isinstance(snapshot, dict) else None
    if not isinstance(jobs, list):
        return []
    return [job for job in jobs if isinstance(job, dict)]


def _extract_handler(snapshot):
    handler = snapshot.get("handler") if isinstance(snapshot, dict) else None
    if not isinstance(handler, dict):
        return {}
    return handler


def _parse_elapsed_seconds(elapsed):
    if not isinstance(elapsed, str):
        return 0
    parts = elapsed.split(":")
    if len(parts) != 3:
        return 0
    try:
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2])
    except Exception:
        return 0
    return max(0, (h * 3600) + (m * 60) + s)


def _is_active_log_status(status):
    return str(status) in ("running", "starting", "paused", "queued", "exporting")


def _is_terminal_log_status(status):
    return str(status) in ("success", "failed", "killed", "canceled")


#: How long (s) a session has to stay unreachable -- its socket gone, or its
#: port refusing connections -- before the monitor takes it as stopped. A busy
#: session answers late (a timeout) but never refuses: that is not counted.
SESSION_GONE_GRACE = 2.0


def _session_gone_error(error):
    """Whether `error` says nothing listens there any more (rather than "busy")."""
    if isinstance(error, (FileNotFoundError, ConnectionRefusedError)):
        return True
    return getattr(error, "errno", None) in (errno.ENOENT, errno.ECONNREFUSED)


#: Statuses whose elapsed time does not move.
_FROZEN_CLOCK_STATUSES = ("success", "failed", "killed", "canceled", "paused")


class _QueueCounter:
    def __init__(self):
        self._count = 0

    def qsize(self):
        return max(0, int(self._count))

    def set(self, count):
        self._count = max(0, int(count))


class DaemonMonitorHandler(ParallelJobHandler):
    """API-backed handler that mimics ParallelJobHandler for curses_ui."""

    def __init__(
        self,
        endpoint=None,
        host=hard_settings.daemon_default_host,
        port=hard_settings.daemon_default_port,
        poll_interval=0.25,
        auto_exit=False,
        token=None,
    ):
        super().__init__(job_list=[], nb_jobs=1, process_group=True, auto_exit=bool(auto_exit), log_size_limit=200)

        if endpoint is None:
            endpoint = Endpoint.tcp(host, port, token=token or os.environ.get(TOKEN_ENV_VAR, ""))
        self._endpoint = endpoint
        self._poll_interval = max(0.05, float(poll_interval))
        self._last_poll = 0.0
        self._last_logs_poll = 0.0
        self._selected_remote_id = -1
        self._logs_poll_interval_active = max(0.10, self._poll_interval)
        self._logs_poll_interval_idle = max(0.75, self._poll_interval * 2.0)
        self._jobs_by_remote_id = {}
        # Snapshot delta cursor: with a revision and its matching epoch the
        # daemon returns only the jobs whose state moved since then (see
        # ParallelJobHandler.snapshot). Both stay None until the first reply,
        # which is therefore a full snapshot.
        self._snapshot_revision = None
        self._snapshot_epoch = None
        self._queue_counter = _QueueCounter()
        self.job_queue = self._queue_counter

        self._remote_running = 0
        self._remote_paused = 0
        self._remote_queued = 0
        self._remote_retired = 0
        # The jobs a "-E" run waits for (see watch_jobs): None watches the
        # whole session.
        self.watched_job_ids = None
        # Mirror of the daemon's resource guard (see _sync_snapshot). The guard
        # never runs here: pausing jobs is the daemon's business.
        self.resource_guard_enabled = False
        self._remote_auto_paused = 0
        self._remote_guard_unavailable = None
        self._remote_total_jobs = 0
        self._remote_format_yaml = None
        # Set once the session stops answering for good (see _sync_snapshot).
        self.session_gone = False
        # Set once this monitor told the session to stop ("q", the end popup).
        self.session_closed = False
        self._unreachable_since = None

        self._placeholder = self._new_local_job(
            remote_id=-1,
            display_name="Waiting for jobs...",
            directory=".",
            tmp_dir=".",
        )
        self._placeholder.status = "idle"
        self._placeholder.progress = 0

        self.job_list = [self._placeholder]
        self.job_count = 1
        self.selected_job_index = 0
        self.job_index_start = 0
        self.job_index_end = 1
        self.max_title_length = len(self._placeholder.display_name)
        self.running_job_list = []
        self.retired_job_list = []

        self._sync_snapshot(force=True)

    def _new_local_job(self, remote_id, display_name, directory, tmp_dir):
        job = ParallelJob(
            process=None,
            command="",
            directory=str(directory or "."),
            generate_rtl=False,
            generate_command="",
            target="",
            arch="",
            display_name=str(display_name or "job"),
            status_file="",
            progress_file="",
            tmp_dir=str(tmp_dir or directory or "."),
            log_size_limit=int(self.log_size_limit),
            status="idle",
        )
        job.progress = 0
        job._remote_id = int(remote_id)
        job._remote_log_total = None
        return job

    def _append_error(self, message):
        if not message:
            return
        if not self.job_list:
            return
        index = min(max(0, int(self.selected_job_index)), len(self.job_list) - 1)
        job = self.job_list[index]
        text = printc.colors.RED + "daemon monitor error: " + str(message) + printc.colors.ENDC
        if not job.log_history or job.log_history[-1] != text:
            job.log_history.append(text)
            job.log_changed = True

    def _sync_job_from_remote(self, job, remote_job, now):
        job.display_name = str(remote_job.get("display_name", job.display_name))
        job.kind = str(remote_job.get("kind", getattr(job, "kind", JOB_KIND)) or JOB_KIND)
        job.status = str(remote_job.get("status", job.status))
        job.progress = int(round(float(remote_job.get("progress", getattr(job, "progress", 0)))))
        job.progress = max(0, min(100, job.progress))
        job.directory = str(remote_job.get("directory", job.directory or "."))
        job.tmp_dir = str(remote_job.get("tmp_dir", job.tmp_dir or job.directory or "."))
        job.target = str(remote_job.get("target", ""))
        job.arch = str(remote_job.get("arch", ""))

        elapsed_seconds = _parse_elapsed_seconds(remote_job.get("elapsed_time"))
        if elapsed_seconds > 0:
            job.start_time = now - float(elapsed_seconds)
            # A paused job's time stands still, like a finished one's: a delta
            # snapshot does not send it again while it stays paused, and a
            # clock left running here would keep counting until it resumes.
            if job.status in _FROZEN_CLOCK_STATUSES:
                job.stop_time = now
            else:
                job.stop_time = None
        else:
            if job.status == "paused":
                if job.start_time is None:
                    job.start_time = now
                job.stop_time = job.start_time
            elif job.status in ("running", "starting", "exporting"):
                if job.start_time is None:
                    job.start_time = now
                job.stop_time = None
            elif job.status in ("success", "failed", "killed", "canceled"):
                if job.start_time is None:
                    job.start_time = now
                if job.stop_time is None:
                    job.stop_time = now
            else:
                job.start_time = None
                job.stop_time = None

    def _status_path(self):
        """`/status` for the next poll, asking for a delta when we can."""
        path = "/status?logs_job_id=-1"
        if self._snapshot_epoch is not None and self._snapshot_revision is not None:
            path += "&since={}&epoch={}".format(int(self._snapshot_revision), self._snapshot_epoch)
        return path

    def _apply_job_updates(self, remote_jobs, full, now):
        """Merge a snapshot's job entries into the local mirror.

        A delta carries only the jobs that changed, so the mirror -- not the
        response -- is what holds the job list. Only a full snapshot may drop
        jobs: the daemon rerolls its epoch when its list shrinks, which forces
        one, so a delta never means "the missing ids are gone".
        """
        if full:
            live_ids = {int(remote_job.get("id", -1)) for remote_job in remote_jobs}
            for stale_id in [job_id for job_id in self._jobs_by_remote_id if job_id not in live_ids]:
                self._jobs_by_remote_id.pop(stale_id, None)

        for remote_job in remote_jobs:
            remote_id = int(remote_job.get("id", -1))
            job = self._jobs_by_remote_id.get(remote_id)
            if job is None:
                job = self._new_local_job(
                    remote_id=remote_id,
                    display_name=remote_job.get("display_name", "job"),
                    directory=remote_job.get("directory", "."),
                    tmp_dir=remote_job.get("tmp_dir", "."),
                )
                self._jobs_by_remote_id[remote_id] = job
            self._sync_job_from_remote(job, remote_job, now)

    def _sync_snapshot(self, force=False):
        now = time.time()
        if not force and (now - self._last_poll) < self._poll_interval:
            return

        try:
            snapshot = _api_get(self._endpoint, self._status_path(), timeout=0.8)
        except Exception as e:
            self._last_poll = now
            if _session_gone_error(e):
                # Stopped from elsewhere ("odatix stop", the GUI): there is
                # nothing left to show, and the monitor says so and leaves
                # (see curses_ui and run_monitor) rather than freeze on it.
                if self._unreachable_since is None:
                    self._unreachable_since = now
                if now - self._unreachable_since >= SESSION_GONE_GRACE:
                    self.session_gone = True
                return
            self._unreachable_since = None
            self._append_error(e)
            return

        self._last_poll = now
        self._unreachable_since = None

        handler_data = _extract_handler(snapshot)
        remote_jobs = _extract_jobs(snapshot)

        # The aggregates always cover every job, delta or not.
        self._remote_running = int(handler_data.get("running", 0))
        self._remote_queued = int(handler_data.get("queued", 0))
        self._remote_retired = int(handler_data.get("retired", 0))
        self._remote_total_jobs = int(handler_data.get("job_count", len(remote_jobs)))
        # A session from before "paused" was told apart counts its paused
        # jobs as running: the mirror below says how many there are.
        self._remote_paused = handler_data.get("paused")

        # Keep the local nb_jobs mirror in sync with the daemon so the curses UI
        # displays the daemon's actual parallelism cap.
        try:
            self.nb_jobs = max(1, int(handler_data.get("nb_jobs", self.nb_jobs)))
        except Exception:
            pass

        # Same for the resource guard: the daemon runs it, the monitor shows it.
        guard = handler_data.get("resource_guard")
        if isinstance(guard, dict):
            self.resource_guard_enabled = bool(guard.get("enabled", self.resource_guard_enabled))
            self._remote_guard_unavailable = guard.get("unavailable")
            try:
                self._remote_auto_paused = int(guard.get("auto_paused") or 0)
            except Exception:
                pass

        remote_format_yaml = handler_data.get("format_yaml")
        if remote_format_yaml != self._remote_format_yaml:
            self._remote_format_yaml = remote_format_yaml
            # Keep local monitor formatting aligned with daemon runtime config.
            self._set_formatter(remote_format_yaml if remote_format_yaml is not None else "")

        self._queue_counter.set(self._remote_queued)

        # A reply that says nothing about its revision cannot be followed up on;
        # dropping the cursor asks for a full snapshot next time rather than
        # replaying a stale `since`.
        epoch = snapshot.get("epoch") if isinstance(snapshot, dict) else None
        revision = snapshot.get("revision") if isinstance(snapshot, dict) else None
        full = bool(snapshot.get("full", True)) if isinstance(snapshot, dict) else True
        if epoch != self._snapshot_epoch:
            full = True
        if isinstance(epoch, str) and isinstance(revision, int):
            self._snapshot_epoch = epoch
            self._snapshot_revision = revision
        else:
            self._snapshot_epoch = None
            self._snapshot_revision = None

        self._apply_job_updates(remote_jobs, full, now)

        if self._jobs_by_remote_id:
            self.job_list = [self._jobs_by_remote_id[job_id] for job_id in sorted(self._jobs_by_remote_id)]
            self.job_count = len(self.job_list)
            self.max_title_length = max(len(job.display_name) for job in self.job_list)
            self.selected_job_index = max(0, min(int(self.selected_job_index), self.job_count - 1))
            self.job_index_start = max(0, min(self.job_index_start, self.job_count - 1))

            # Default progress window height on attach:
            # whichever is larger between half-screen and total jobs,
            # while preserving at least one log line.
            term_size = shutil.get_terminal_size((120, 40))
            height = int(getattr(term_size, "lines", 40))
            half_screen = max(1, height // 2 - 2)
            max_progress_height = max(1, height - 5)
            preferred_height = max(half_screen, self.job_count)
            default_end = self.job_index_start + min(preferred_height, max_progress_height)

            min_end = self.job_index_start + 1
            if self.job_index_end <= min_end:
                self.job_index_end = max(min_end, default_end)
            else:
                self.job_index_end = max(min_end, self.job_index_end)

            self.running_job_list = [
                job for job in self.job_list if job.status in ("running", "starting", "paused", "exporting")
            ]
            self.retired_job_list = [
                job for job in self.job_list if job.status in ("success", "failed", "killed", "canceled")
            ]
            if self._remote_paused is None:
                paused = sum(1 for job in self.job_list if job.status == "paused")
                self._remote_running = max(0, self._remote_running - paused)
                self._remote_paused = paused
        else:
            self.job_list = [self._placeholder]
            self.job_count = 1
            self.selected_job_index = 0
            self.job_index_start = 0
            self.job_index_end = 1
            self.max_title_length = len(self._placeholder.display_name)
            self.running_job_list = []
            self.retired_job_list = []
        if self._remote_paused is None:
            self._remote_paused = 0

    def runtime_counts(self):
        """What the session says about all of its jobs (see ParallelJobHandler.runtime_counts)."""
        return {
            "running": int(self._remote_running),
            "paused": int(self._remote_paused or 0),
            "queued": int(self._remote_queued),
            "retired": int(self._remote_retired),
            "total": int(self._remote_total_jobs),
        }

    def watch_jobs(self, job_ids):
        """
        Close the monitor once these jobs are over ("-E"), rather than once the
        whole session is: the session may also run the jobs of other runs.
        """
        self.watched_job_ids = None if job_ids is None else set(int(job_id) for job_id in job_ids)

    def watched_jobs_over(self):
        if not self.watched_job_ids:
            return None
        seen = 0
        for remote_id in self.watched_job_ids:
            job = self._jobs_by_remote_id.get(remote_id)
            if job is None:
                continue
            seen += 1
            if job.status not in ("success", "failed", "killed", "canceled"):
                return False
        # Not one of them listed yet: the first snapshot is still to come.
        return seen > 0

    def _sync_selected_logs(self):
        if not self.job_list:
            return

        self._sync_snapshot(force=False)

        selected_idx = min(max(0, int(self.selected_job_index)), len(self.job_list) - 1)
        job = self.job_list[selected_idx]
        remote_id = int(getattr(job, "_remote_id", -1))
        if remote_id < 0:
            return

        full_refresh = getattr(job, "_remote_log_total", None) is None
        selected_changed = remote_id != self._selected_remote_id
        if selected_changed:
            self._selected_remote_id = remote_id
            full_refresh = True

        terminal_status = _is_terminal_log_status(job.status)
        if terminal_status:
            if not bool(getattr(job, "_remote_terminal_sync_done", False)):
                # Ensure we capture trailing lines emitted right before completion.
                full_refresh = True
        else:
            job._remote_terminal_sync_done = False

        if not full_refresh:
            now = time.time()
            if _is_active_log_status(job.status):
                poll_interval = self._logs_poll_interval_active
            else:
                poll_interval = self._logs_poll_interval_idle
            if (now - self._last_logs_poll) < poll_interval:
                return
            self._last_logs_poll = now
        else:
            self._last_logs_poll = time.time()

        try:
            if full_refresh:
                limit = int(getattr(job, "log_size_limit", self.log_size_limit))
                if limit == -1:
                    snap = _api_get(
                        self._endpoint,
                        "/status?logs_job_id={}&include_jobs=0&logs_offset=0&logs_limit=-1".format(remote_id),
                        timeout=2.0,
                    )
                    logs = snap.get("logs") if isinstance(snap, dict) else {}
                    lines = logs.get("lines") if isinstance(logs, dict) else []
                    total = logs.get("total_lines", len(lines)) if isinstance(logs, dict) else len(lines)
                    if not isinstance(lines, list):
                        lines = []
                    job.log_history = [str(x) for x in lines]
                    job._remote_log_total = int(total)
                    job.log_changed = True
                else:
                    meta = _api_get(
                        self._endpoint,
                        "/status?logs_job_id={}&include_jobs=0&logs_offset=0&logs_limit=0".format(remote_id),
                        timeout=1.2,
                    )
                    meta_logs = meta.get("logs") if isinstance(meta, dict) else {}
                    total = meta_logs.get("total_lines", 0) if isinstance(meta_logs, dict) else 0
                    total = max(0, int(total))
                    fetch_offset = max(0, total - max(0, int(limit)))
                    snap = _api_get(
                        self._endpoint,
                        "/status?logs_job_id={}&include_jobs=0&logs_offset={}&logs_limit={}".format(remote_id, fetch_offset, max(0, int(limit))),
                        timeout=1.8,
                    )
                    logs = snap.get("logs") if isinstance(snap, dict) else {}
                    lines = logs.get("lines") if isinstance(logs, dict) else []
                    if not isinstance(lines, list):
                        lines = []
                    job.log_history = [str(x) for x in lines]
                    job._remote_log_total = total
                    job.log_changed = True
            else:
                offset = int(getattr(job, "_remote_log_total", 0))
                limit = int(getattr(job, "log_size_limit", self.log_size_limit))
                snap = _api_get(
                    self._endpoint,
                    "/status?logs_job_id={}&include_jobs=0&logs_offset={}&logs_limit=500".format(remote_id, offset),
                    timeout=1.0,
                )
                logs = snap.get("logs") if isinstance(snap, dict) else {}
                lines = logs.get("lines") if isinstance(logs, dict) else []
                total = logs.get("total_lines", offset) if isinstance(logs, dict) else offset
                if not isinstance(lines, list):
                    lines = []

                if int(total) < offset:
                    limit = int(getattr(job, "log_size_limit", self.log_size_limit))
                    if limit == -1:
                        full = _api_get(
                            self._endpoint,
                            "/status?logs_job_id={}&include_jobs=0&logs_offset=0&logs_limit=-1".format(remote_id),
                            timeout=2.0,
                        )
                        full_logs = full.get("logs") if isinstance(full, dict) else {}
                        full_lines = full_logs.get("lines") if isinstance(full_logs, dict) else []
                        full_total = full_logs.get("total_lines", len(full_lines)) if isinstance(full_logs, dict) else len(full_lines)
                        if not isinstance(full_lines, list):
                            full_lines = []
                        job.log_history = [str(x) for x in full_lines]
                        job._remote_log_total = int(full_total)
                        job.log_changed = True
                    else:
                        meta = _api_get(
                            self._endpoint,
                            "/status?logs_job_id={}&include_jobs=0&logs_offset=0&logs_limit=0".format(remote_id),
                            timeout=1.2,
                        )
                        meta_logs = meta.get("logs") if isinstance(meta, dict) else {}
                        full_total = meta_logs.get("total_lines", 0) if isinstance(meta_logs, dict) else 0
                        full_total = max(0, int(full_total))
                        fetch_offset = max(0, full_total - max(0, int(limit)))
                        full = _api_get(
                            self._endpoint,
                            "/status?logs_job_id={}&include_jobs=0&logs_offset={}&logs_limit={}".format(remote_id, fetch_offset, max(0, int(limit))),
                            timeout=1.8,
                        )
                        full_logs = full.get("logs") if isinstance(full, dict) else {}
                        full_lines = full_logs.get("lines") if isinstance(full_logs, dict) else []
                        if not isinstance(full_lines, list):
                            full_lines = []
                        job.log_history = [str(x) for x in full_lines]
                        job._remote_log_total = int(full_total)
                        job.log_changed = True
                else:
                    if lines:
                        job.log_history.extend([str(x) for x in lines])
                        job.log_changed = True
                    elif (
                        limit != -1
                        and _is_active_log_status(job.status)
                        and int(total) == offset
                        and int(total) >= max(1, int(limit))
                    ):
                        # Daemon history may be a rolling fixed-size buffer.
                        # In that case total_lines can stay constant while newer lines
                        # replace older ones, so offset-only incremental fetch stalls.
                        fetch_limit = max(0, int(limit))
                        fetch_offset = max(0, int(total) - fetch_limit)
                        tail_snap = _api_get(
                            self._endpoint,
                            "/status?logs_job_id={}&include_jobs=0&logs_offset={}&logs_limit={}".format(
                                remote_id,
                                fetch_offset,
                                fetch_limit,
                            ),
                            timeout=1.2,
                        )
                        tail_logs = tail_snap.get("logs") if isinstance(tail_snap, dict) else {}
                        tail_lines = tail_logs.get("lines") if isinstance(tail_logs, dict) else []
                        if not isinstance(tail_lines, list):
                            tail_lines = []

                        new_history = [str(x) for x in tail_lines]
                        if job.log_history != new_history:
                            job.log_history = new_history
                            max_log_position = max(0, len(job.log_history) - 1)
                            job.log_position = max(0, min(int(job.log_position), max_log_position))
                            job.log_changed = True
                    elif _is_active_log_status(job.status) and int(total) == offset and int(total) > 0:
                        # Some tools frequently refresh progress in-place with '\r'.
                        # In that case total_lines does not grow, so probe the tail line explicitly.
                        tail_offset = max(0, int(total) - 1)
                        tail_snap = _api_get(
                            self._endpoint,
                            "/status?logs_job_id={}&include_jobs=0&logs_offset={}&logs_limit=1".format(remote_id, tail_offset),
                            timeout=1.0,
                        )
                        tail_logs = tail_snap.get("logs") if isinstance(tail_snap, dict) else {}
                        tail_lines = tail_logs.get("lines") if isinstance(tail_logs, dict) else []
                        if isinstance(tail_lines, list) and len(tail_lines) > 0:
                            tail_line = str(tail_lines[-1])
                            if job.log_history:
                                if job.log_history[-1] != tail_line:
                                    job.log_history[-1] = tail_line
                                    job.log_changed = True
                            else:
                                job.log_history.append(tail_line)
                                job.log_changed = True
                    job._remote_log_total = int(total)

            limit = int(getattr(job, "log_size_limit", self.log_size_limit))
            if limit != -1 and len(job.log_history) > limit:
                dropped = len(job.log_history) - limit
                job.log_history = job.log_history[-limit:]
                if int(job.log_position) >= dropped:
                    job.log_position = max(0, int(job.log_position) - dropped)
                else:
                    job.log_position = 0

            if terminal_status:
                job._remote_terminal_sync_done = True
        except Exception as e:
            self._append_error(e)

    def _remote_id_from_index(self, job_id):
        idx = int(job_id)
        if idx < 0 or idx >= len(self.job_list):
            return None
        remote_id = int(getattr(self.job_list[idx], "_remote_id", -1))
        if remote_id < 0:
            return None
        return remote_id

    def _post_job_action(self, action, remote_id):
        if action == "start":
            _api_post(self._endpoint, "/jobs/{}/start".format(int(remote_id)), timeout=1.0)
        elif action == "pause":
            _api_post(self._endpoint, "/jobs/{}/pause".format(int(remote_id)), timeout=1.0)
        elif action == "kill":
            _api_post(self._endpoint, "/jobs/{}/kill".format(int(remote_id)), timeout=1.0)
        elif action == "open":
            _api_post(self._endpoint, "/jobs/{}/open".format(int(remote_id)), timeout=1.0)

    def _update_jobs_state(self, selected_job=None, on_selected_retired=None):
        self._sync_snapshot(force=False)

    def read_process_output(self):
        self._sync_selected_logs()

    def start_job(self, job):
        # Curses bootstrap phase is ignored in daemon-attach mode.
        return

    def queue_job(self, job):
        # Curses bootstrap phase is ignored in daemon-attach mode.
        return

    def pause_job(self, job_id: int):
        remote_id = self._remote_id_from_index(job_id)
        if remote_id is None:
            return
        try:
            self._post_job_action("pause", remote_id)
        except Exception as e:
            self._append_error(e)

    def start_or_resume_job(self, job_id: int):
        remote_id = self._remote_id_from_index(job_id)
        if remote_id is None:
            return
        try:
            self._post_job_action("start", remote_id)
        except Exception as e:
            self._append_error(e)

    def kill_or_cancel_job(self, job_id: int):
        remote_id = self._remote_id_from_index(job_id)
        if remote_id is None:
            return
        try:
            self._post_job_action("kill", remote_id)
        except Exception as e:
            self._append_error(e)

    def restart_job(self, job_id: int):
        remote_id = self._remote_id_from_index(job_id)
        if remote_id is None:
            return
        try:
            self._post_job_action("restart", remote_id)
        except Exception as e:
            self._append_error(e)

    def open_job_path(self, job_id: int):
        idx = int(job_id)
        if idx < 0 or idx >= len(self.job_list):
            return
        job = self.job_list[idx]
        try:
            open_path_in_explorer(job.tmp_dir)
        except NotImplementedError:
            pass
        except Exception as e:
            self._append_error(e)

    def _check_resource_guard_unlocked(self):
        # The jobs listed here are mirrors of the daemon's: the daemon runs the
        # guard on the real ones.
        return

    def resource_guard_paused_count(self):
        return self._remote_auto_paused

    def resource_guard_unavailable(self):
        return self._remote_guard_unavailable

    def set_resource_guard(self, enabled):
        # Forwarded like set_nb_jobs; reflected back on the next snapshot poll.
        enabled = bool(enabled)
        try:
            _api_post(
                self._endpoint,
                "/config?resource_guard={}".format("true" if enabled else "false"),
                timeout=1.0,
            )
            self.resource_guard_enabled = enabled  # optimistic; reconciled by _sync_snapshot
            if not enabled:
                self._remote_auto_paused = 0
        except Exception as e:
            self._append_error(e)

    def set_nb_jobs(self, nb_jobs):
        # Forward the parallelism change to the daemon instead of applying it
        # locally; the new value is reflected back on the next snapshot poll.
        new_value = max(1, int(nb_jobs))
        try:
            _api_post(self._endpoint, "/config?nb_jobs={}".format(new_value), timeout=1.0)
            self.nb_jobs = new_value  # optimistic; reconciled by _sync_snapshot
        except Exception as e:
            self._append_error(e)

    def terminate_all_jobs(self):
        self._sync_snapshot(force=True)
        # Queued jobs first: a killed job frees its slot, and the daemon would
        # otherwise start the next queued one only to be told to kill it too.
        # The daemon's kill handles every live status (paused and starting
        # included), and signals each job the way it was started.
        jobs = list(enumerate(self.job_list))
        for statuses in (("queued",), ("running", "starting", "paused")):
            for idx, job in jobs:
                if getattr(job, "_remote_id", -1) < 0 or job.status not in statuses:
                    continue
                try:
                    self.kill_or_cancel_job(idx)
                except Exception as e:
                    self._append_error(e)
        try:
            _api_post(self._endpoint, "/shutdown", payload={}, timeout=1.0)
            self.session_closed = True
        except Exception as e:
            self._append_error(e)

    def on_quit_after_finished(self):
        # On explicit quit ('q'), stop daemon only when all jobs are done.
        self._sync_snapshot(force=True)
        if self._remote_total_jobs <= 0:
            return

        all_done = (
            self._remote_running == 0
            and not self._remote_paused
            and self._remote_queued == 0
            and self._remote_retired >= self._remote_total_jobs
        )
        if not all_done:
            return

        try:
            _api_post(self._endpoint, "/shutdown", payload={}, timeout=1.0)
            self.session_closed = True
        except Exception as e:
            self._append_error(e)


class MonitorExit(object):
    """
    How a monitor was left, and what it last saw: what the command that opened
    it says once the screen is back to the shell (see exit_messages).

    Attributes:
        reason (str): "detach" ("d", or the end popup keeping the session),
            "close" (the end popup, or "q" once every job is over), "kill"
            ("q", then killing every job), "auto" ("-E"), "shutdown", or None.
        counts (dict): the job counts it last saw (see runtime_counts).
        session_label (str): the ID of the session.
        session_closed (bool): whether it told the session to stop.
    """

    def __init__(self, reason, counts, session_label, session_closed=False):
        self.reason = reason
        self.counts = dict(counts or {})
        self.session_label = session_label
        self.session_closed = bool(session_closed)

    def __bool__(self):
        # What run_monitor returned before: whether the jobs were left alive.
        return self.reason != "kill"

    __nonzero__ = __bool__


def exit_messages(monitor_exit):
    """
    What to say once the monitor is closed, so that the terminal keeps a line
    of what happened: which session goes on and how to get back to it, or
    what became of the jobs.

    "-E" ("auto") says it its own way, from the jobs of its run (see
    odatix.components.run_common.close_finished_session).

    Returns:
        list: (level, text) pairs, level being "note" or "warning".
    """
    if not isinstance(monitor_exit, MonitorExit) or not monitor_exit.session_label:
        return []
    session = monitor_exit.session_label
    counts = monitor_exit.counts
    total = int(counts.get("total", 0))
    retired = int(counts.get("retired", 0))
    left = total - retired
    reason = monitor_exit.reason
    reattach = 're-attach with "odatix monitor -S {0}" or simply "odatix monitor" if it is the only one running in this workspace'.format(session)

    if reason == "detach":
        if left > 0:
            return [("note", "Detached: {0} job(s) keep running in session {1}\n{2}".format(left, session, reattach))]
        return [("note", 'Detached: session {0} stays open with its {1} finished job(s)\n{2}\n '
                         'close it with "odatix stop -S {0}"'.format(session, total, reattach))]
    if reason == "kill":
        return [("warning", "{0} job(s) killed, session {1} closed".format(left, session))]
    if reason == "close":
        if not monitor_exit.session_closed:
            return [("note", "Session {0} still has jobs running\n{1}".format(session, reattach))]
        failed = int(counts.get("failed", 0))
        summary = "{0}/{1} job(s) succeeded".format(retired - failed, total)
        if failed:
            return [("warning", "{0}, {1} failed; session {2} closed".format(summary, failed, session))]
        return [("note", "{0}; session {1} closed".format(summary, session))]
    return []


def run_monitor(
    endpoint=None,
    host=hard_settings.daemon_default_host,
    port=hard_settings.daemon_default_port,
    poll_interval=0.25,
    auto_exit=False,
    token=None,
    session_label=None,
    job_ids=None,
):
    """
    Show the curses monitor of a session until it is left.

    Args:
        job_ids (list): with `auto_exit`, the jobs whose end closes the monitor
            (those of the run that opened it). Every job of the session when None.

    Returns:
        MonitorExit: how it was left.
    """
    handler = DaemonMonitorHandler(
        endpoint=endpoint,
        host=str(host),
        port=int(port),
        poll_interval=float(poll_interval),
        auto_exit=bool(auto_exit),
        token=token,
    )
    # Which session this is, for the header: with several sessions running,
    # nothing else on the screen tells them apart.
    handler.session_label = session_label
    if job_ids is not None:
        handler.watch_jobs(job_ids)
    handler.monitor_exit = None
    curses_ui.run(handler)
    if handler.session_gone:
        from odatix.lib.parallel_job_handler.daemon_control import SessionGoneError

        name = "Session {}".format(session_label) if session_label else "The session"
        raise SessionGoneError(name + " was stopped while the monitor was attached to it")
    counts = dict(getattr(handler, "monitor_exit_counts", None) or handler.runtime_counts())
    counts["failed"] = sum(
        1 for job in handler.job_list
        if getattr(job, "_remote_id", -1) >= 0 and job.status in ("failed", "killed", "canceled")
    )
    return MonitorExit(handler.monitor_exit, counts, session_label, session_closed=handler.session_closed)


def add_arguments(parser):
    parser.add_argument("--host", default=hard_settings.daemon_default_host, help="Daemon API host")
    parser.add_argument("--port", type=int, default=hard_settings.daemon_default_port, help="Daemon API port")
    parser.add_argument(
        "--token",
        default=None,
        help="Session token (default: ${})".format(TOKEN_ENV_VAR),
    )
    parser.add_argument("--poll", type=float, default=0.25, help="Polling interval in seconds")
    parser.add_argument("--auto-exit", action="store_true", help="Exit monitor when all jobs are completed")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Attach curses monitor to Odatix daemon")
    add_arguments(parser)
    return parser.parse_args()


def main(args=None):
    if args is None:
        args = parse_arguments()
    run_monitor(
        host=args.host,
        port=args.port,
        poll_interval=args.poll,
        auto_exit=args.auto_exit,
        token=args.token,
    )


if __name__ == "__main__":
    main()
