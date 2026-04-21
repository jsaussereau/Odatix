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
import json
import shutil
import time
import urllib.request

import odatix.lib.printc as printc
from odatix.lib.parallel_job_handler import curses_ui
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler
from odatix.lib.parallel_job_handler.job import ParallelJob
from odatix.lib.utils import open_path_in_explorer


def _api_request(base_url, method, path, payload=None, timeout=1.0):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url=base_url.rstrip("/") + path,
        data=data,
        headers=headers,
        method=str(method).upper(),
    )

    with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
        raw = resp.read()

    if not raw:
        return {}

    return json.loads(raw.decode("utf-8"))


def _api_get(base_url, path, timeout=1.0):
    return _api_request(base_url, "GET", path, timeout=timeout)


def _api_post(base_url, path, payload=None, timeout=1.0):
    return _api_request(base_url, "POST", path, payload=payload, timeout=timeout)


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


class _QueueCounter:
    def __init__(self):
        self._count = 0

    def qsize(self):
        return max(0, int(self._count))

    def set(self, count):
        self._count = max(0, int(count))


class DaemonMonitorHandler(ParallelJobHandler):
    """API-backed handler that mimics ParallelJobHandler for curses_ui."""

    def __init__(self, host="127.0.0.1", port=8000, poll_interval=0.25, auto_exit=False):
        super().__init__(job_list=[], nb_jobs=1, process_group=True, auto_exit=bool(auto_exit), log_size_limit=200)

        self._base_url = "http://{}:{}".format(str(host), int(port))
        self._poll_interval = max(0.05, float(poll_interval))
        self._last_poll = 0.0
        self._last_logs_poll = 0.0
        self._selected_remote_id = -1
        self._logs_poll_interval_active = max(0.10, self._poll_interval)
        self._logs_poll_interval_idle = max(0.75, self._poll_interval * 2.0)
        self._jobs_by_remote_id = {}
        self._queue_counter = _QueueCounter()
        self.job_queue = self._queue_counter

        self._remote_running = 0
        self._remote_queued = 0
        self._remote_retired = 0
        self._remote_total_jobs = 0
        self._remote_format_yaml = None

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
            if job.status in ("success", "failed", "killed", "canceled"):
                job.stop_time = now
            else:
                job.stop_time = None
        else:
            if job.status in ("running", "starting", "paused"):
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

    def _sync_snapshot(self, force=False):
        now = time.time()
        if not force and (now - self._last_poll) < self._poll_interval:
            return

        try:
            snapshot = _api_get(self._base_url, "/status?logs_job_id=-1", timeout=0.8)
        except Exception as e:
            self._last_poll = now
            self._append_error(e)
            return

        self._last_poll = now

        handler_data = _extract_handler(snapshot)
        remote_jobs = _extract_jobs(snapshot)

        self._remote_running = int(handler_data.get("running", 0))
        self._remote_queued = int(handler_data.get("queued", 0))
        self._remote_retired = int(handler_data.get("retired", 0))
        self._remote_total_jobs = int(handler_data.get("job_count", len(remote_jobs)))

        remote_format_yaml = handler_data.get("format_yaml")
        if remote_format_yaml != self._remote_format_yaml:
            self._remote_format_yaml = remote_format_yaml
            # Keep local monitor formatting aligned with daemon runtime config.
            self._set_formatter(remote_format_yaml if remote_format_yaml is not None else "")

        self._queue_counter.set(self._remote_queued)

        if remote_jobs:
            new_job_list = []
            seen = set()
            for remote_job in remote_jobs:
                remote_id = int(remote_job.get("id", -1))
                seen.add(remote_id)
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
                new_job_list.append(job)

            stale_ids = [job_id for job_id in self._jobs_by_remote_id.keys() if job_id not in seen]
            for stale_id in stale_ids:
                self._jobs_by_remote_id.pop(stale_id, None)

            self.job_list = new_job_list
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
                job for job in self.job_list if job.status in ("running", "starting", "paused")
            ]
            self.retired_job_list = [
                job for job in self.job_list if job.status in ("success", "failed", "killed", "canceled")
            ]
        else:
            self._jobs_by_remote_id.clear()
            self.job_list = [self._placeholder]
            self.job_count = 1
            self.selected_job_index = 0
            self.job_index_start = 0
            self.job_index_end = 1
            self.max_title_length = len(self._placeholder.display_name)
            self.running_job_list = []
            self.retired_job_list = []

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

        if not full_refresh:
            now = time.time()
            if job.status in ("running", "starting", "paused", "queued"):
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
                        self._base_url,
                        "/status?logs_job_id={}&logs_offset=0&logs_limit=-1".format(remote_id),
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
                        self._base_url,
                        "/status?logs_job_id={}&logs_offset=0&logs_limit=0".format(remote_id),
                        timeout=1.2,
                    )
                    meta_logs = meta.get("logs") if isinstance(meta, dict) else {}
                    total = meta_logs.get("total_lines", 0) if isinstance(meta_logs, dict) else 0
                    total = max(0, int(total))
                    fetch_offset = max(0, total - max(0, int(limit)))
                    snap = _api_get(
                        self._base_url,
                        "/status?logs_job_id={}&logs_offset={}&logs_limit={}".format(remote_id, fetch_offset, max(0, int(limit))),
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
                snap = _api_get(
                    self._base_url,
                    "/status?logs_job_id={}&logs_offset={}&logs_limit=500".format(remote_id, offset),
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
                            self._base_url,
                            "/status?logs_job_id={}&logs_offset=0&logs_limit=-1".format(remote_id),
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
                            self._base_url,
                            "/status?logs_job_id={}&logs_offset=0&logs_limit=0".format(remote_id),
                            timeout=1.2,
                        )
                        meta_logs = meta.get("logs") if isinstance(meta, dict) else {}
                        full_total = meta_logs.get("total_lines", 0) if isinstance(meta_logs, dict) else 0
                        full_total = max(0, int(full_total))
                        fetch_offset = max(0, full_total - max(0, int(limit)))
                        full = _api_get(
                            self._base_url,
                            "/status?logs_job_id={}&logs_offset={}&logs_limit={}".format(remote_id, fetch_offset, max(0, int(limit))),
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
                    job._remote_log_total = int(total)

            limit = int(getattr(job, "log_size_limit", self.log_size_limit))
            if limit != -1 and len(job.log_history) > limit:
                dropped = len(job.log_history) - limit
                job.log_history = job.log_history[-limit:]
                if int(job.log_position) >= dropped:
                    job.log_position = max(0, int(job.log_position) - dropped)
                else:
                    job.log_position = 0
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
            _api_post(self._base_url, "/jobs/{}/start".format(int(remote_id)), timeout=1.0)
        elif action == "pause":
            _api_post(self._base_url, "/jobs/{}/pause".format(int(remote_id)), timeout=1.0)
        elif action == "kill":
            _api_post(self._base_url, "/jobs/{}/kill".format(int(remote_id)), timeout=1.0)
        elif action == "open":
            _api_post(self._base_url, "/jobs/{}/open".format(int(remote_id)), timeout=1.0)

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

    def terminate_all_jobs(self):
        self._sync_snapshot(force=True)
        for idx, job in enumerate(list(self.job_list)):
            if getattr(job, "_remote_id", -1) < 0:
                continue
            if job.status in ("running", "starting", "paused", "queued"):
                try:
                    self.kill_or_cancel_job(idx)
                except Exception as e:
                    self._append_error(e)
        try:
            _api_post(self._base_url, "/shutdown", payload={}, timeout=1.0)
        except Exception as e:
            self._append_error(e)

    def on_quit_after_finished(self):
        # On explicit quit ('q'), stop daemon only when all jobs are done.
        self._sync_snapshot(force=True)
        if self._remote_total_jobs <= 0:
            return

        all_done = (
            self._remote_running == 0
            and self._remote_queued == 0
            and self._remote_retired >= self._remote_total_jobs
        )
        if not all_done:
            return

        try:
            _api_post(self._base_url, "/shutdown", payload={}, timeout=1.0)
        except Exception as e:
            self._append_error(e)


def run_monitor(host="127.0.0.1", port=8000, poll_interval=0.25, auto_exit=False):
    handler = DaemonMonitorHandler(
        host=str(host),
        port=int(port),
        poll_interval=float(poll_interval),
        auto_exit=bool(auto_exit),
    )
    return curses_ui.run(handler)


def add_arguments(parser):
    parser.add_argument("--host", default="127.0.0.1", help="Daemon API host")
    parser.add_argument("--port", type=int, default=8000, help="Daemon API port")
    parser.add_argument("--poll", type=float, default=0.25, help="Polling interval in seconds")
    parser.add_argument("--auto-exit", action="store_true", help="Exit monitor when all jobs are completed")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Attach curses monitor to Odatix daemon")
    add_arguments(parser)
    return parser.parse_args()


def main(args=None):
    if args is None:
        args = parse_arguments()
    run_monitor(host=args.host, port=args.port, poll_interval=args.poll, auto_exit=args.auto_exit)


if __name__ == "__main__":
    main()
