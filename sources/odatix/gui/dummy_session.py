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

"""
A simulated monitor session, for `/monitor?dummy=true`.

No daemon, no jobs, no subprocesses: this module fakes exactly the part of the
daemon API the monitor page speaks (`GET /status`, `POST /jobs/<id>/<action>`,
`POST /config`), so the web monitor can be demoed, screenshotted and styled
without a synthesis run -- showing roughly what the curses monitor shows on a
real fmax session.

The simulation advances lazily: nothing runs in the background, each `/status`
call moves the session forward by however much wall time has passed since the
previous one. It also honours the delta protocol (`since`/`epoch`) and the log
windowing (`logs_offset`/`logs_limit`) the real handler implements, so the page
exercises the same code paths it does against a real session.
"""

import random
import threading
import time
import uuid

from odatix.lib.parallel_job_handler.job_status import (
    STATUS_BUCKETS,
    STATUS_SORT_PRIORITY,
    RUNNING_STATUSES,
    QUEUED_STATUSES,
    DONE_STATUSES,
    FAILED_STATUSES,
)

# What a dummy session calls itself, in the URL and in the session dropdown.
DUMMY_SESSION_ID = "dummy"
DUMMY_SESSION_LABEL = "dummy (simulated)"
DUMMY_ADDRESS = "simulated://dummy"

_ARCHITECTURES = [
    "AsteRISC/M0000 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0001 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0008 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0016 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0024 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0025 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0036 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0037 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0039 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0044 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0052 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0060 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0061 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0100 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
    "AsteRISC/M0108 [MEM:1024I_1024D, Baseline:I, Mul:Off]",
]

_TARGETS = ("xc7a100t-csg324-1", "xcku3p-ffva676-3-e")

# Jobs that fail, as (target index, architecture index), so a dummy session
# always shows the failed KPI and a red row without waiting on chance.
_FAILING = {(0, 6), (1, 0), (1, 11)}

# Vivado-flavoured log lines, cycled through as a job progresses. They only
# have to look like a synthesis log: nothing reads them back.
_LOG_TEMPLATES = [
    "Command: synth_design -top {arch} -part {target}",
    "Starting synth_design",
    "INFO: [Synth 8-7079] Multithreading enabled for synth_design using a maximum of 2 processes.",
    "INFO: [Synth 8-6157] synthesizing module '{module}'",
    "INFO: [Synth 8-3491] module '{module}' declared at line {line}",
    "WARNING: [Synth 8-7080] Parallel synthesis criteria is not met",
    "Starting Logic Optimization Task",
    "Time (s): cpu = 00:00:{cpu:02d} ; elapsed = 00:00:{cpu:02d} . Memory (MB): peak = 3341.125 ; gain = 7.996",
    "Ending Logic Optimization Task | Checksum: 270cf5b08",
    "Starting Netlist Obfuscation Task",
    "Netlist sorting complete. Time (s): cpu = 00:00:00 ; elapsed = 00:00:00 .",
    "INFO: [Common 17-83] Releasing license: Implementation",
    "{infos} Infos, {warnings} Warnings, 2 Critical Warnings and 0 Errors encountered.",
    "opt_design completed successfully",
    "Command: place_design -directive Explore",
    "Attempting to get a license for feature 'Implementation' and/or device '{short_target}'",
    "Phase 1 Placer Initialization",
    "Phase 2 Global Placement",
    "Phase 3 Detail Placement",
    "INFO: [Timing 38-35] Done setting XDC timing constraints.",
    "Running route_design with fmax target {fmax} MHz",
]

_MODULES = ("riscv_core", "alu", "regfile", "csr_unit", "decoder", "lsu", "fetch_stage")


class _Job(object):
    """One simulated job."""

    def __init__(self, job_id, display_name, target, arch, duration, fails):
        self.id = job_id
        self.display_name = display_name
        self.target = target
        self.arch = arch
        self.status = "queued"
        self.progress = 0.0
        self.elapsed = 0.0
        self.duration = float(duration)
        self.fails = bool(fails)
        self.log_history = []
        self.log_position = 0
        self.autoscroll = True
        self.directory = "work/{}/{}".format(target, arch)
        self.tmp_dir = "work/{}/{}/tmp".format(target, arch)
        # How far along the log has been written, so lines are appended in step
        # with the progress rather than all at once.
        self._logged_lines = 0
        self._seed = random.Random(job_id * 7919)


class DummySession(object):
    """A fake daemon session, answering the subset of the API the monitor uses."""

    def __init__(self, nb_jobs=8, speed=1.0):
        self._lock = threading.RLock()
        self.nb_jobs = int(nb_jobs)
        self.speed = float(speed)
        self.selected_job_index = 0

        self._epoch = uuid.uuid4().hex
        self._revision = 0
        self._job_revisions = {}
        self._last_tick = time.time()

        self.job_list = []
        job_id = 0
        for target_index, target in enumerate(_TARGETS):
            for arch_index, arch in enumerate(_ARCHITECTURES):
                rng = random.Random(job_id * 104729)
                self.job_list.append(
                    _Job(
                        job_id=job_id,
                        display_name="{} ({})".format(arch, target),
                        target=target,
                        arch=arch.split(" ")[0],
                        duration=rng.uniform(45.0, 130.0),
                        fails=(target_index, arch_index) in _FAILING,
                    )
                )
                job_id += 1

        for job in self.job_list:
            self._job_revisions[job.id] = 0

        # Start the session part-way through, so the first frame already looks
        # like a run in flight rather than 30 queued rows. Stepping (rather than
        # jumping) matters: a single long step would progress nothing, since a
        # job only starts at the end of the step that frees its slot.
        start = self._last_tick
        for step in range(1, 13):
            self._advance(now=start + step * 12.0)
        self._last_tick = time.time()

        # One paused job, so the status is represented on the first frame the
        # same way a real session shows a job the user held.
        for job in self.job_list:
            if job.status in RUNNING_STATUSES and job.progress > 20:
                job.status = "paused"
                self._touch(job)
                break

    # -- simulation ------------------------------------------------------

    def _touch(self, job):
        self._revision += 1
        self._job_revisions[job.id] = self._revision

    def _log(self, job, text):
        job.log_history.append(text)

    def _emit_logs(self, job):
        """Append log lines so the log length tracks the job's progress."""
        wanted = int(job.progress * 1.4) + 4
        rng = job._seed
        while job._logged_lines < wanted:
            template = _LOG_TEMPLATES[job._logged_lines % len(_LOG_TEMPLATES)]
            self._log(
                job,
                template.format(
                    arch=job.arch,
                    target=job.target,
                    short_target=job.target.split("-")[0],
                    module=_MODULES[job._logged_lines % len(_MODULES)],
                    line=rng.randint(10, 900),
                    cpu=rng.randint(0, 59),
                    infos=rng.randint(200, 999),
                    warnings=rng.randint(10, 1999),
                    fmax=rng.randint(50, 250),
                ),
            )
            job._logged_lines += 1

    def _running_count(self):
        return sum(1 for job in self.job_list if job.status in RUNNING_STATUSES)

    def _advance(self, now=None):
        """Move the session forward by the wall time since the last call."""
        now = time.time() if now is None else now
        delta = (now - self._last_tick) * self.speed
        self._last_tick = now
        if delta <= 0:
            return

        for job in self.job_list:
            if job.status not in RUNNING_STATUSES:
                continue
            job.elapsed += delta
            job.progress = min(100.0, 100.0 * job.elapsed / job.duration)
            self._emit_logs(job)
            if job.progress >= 100.0:
                if job.fails:
                    job.status = "failed"
                    self._log(job, "ERROR: [Common 17-69] Command failed: synthesis failed")
                else:
                    job.status = "success"
                    self._log(job, "synth_design completed successfully")
                job.progress = 100.0
            self._touch(job)

        # Fill the free parallel slots, in order, the way the handler does.
        free = self.nb_jobs - self._running_count()
        for job in self.job_list:
            if free <= 0:
                break
            if job.status == "queued":
                job.status = "running"
                self._log(job, "Starting job for {} on {}".format(job.arch, job.target))
                self._emit_logs(job)
                self._touch(job)
                free -= 1

    # -- snapshot --------------------------------------------------------

    def _entry(self, job):
        return {
            "id": job.id,
            "display_name": job.display_name,
            "kind": "job",
            "status": job.status,
            "progress": int(round(job.progress)),
            "directory": job.directory,
            "tmp_dir": job.tmp_dir,
            "target": job.target,
            "arch": job.arch,
            "elapsed_time": _format_hms(job.elapsed),
        }

    def snapshot(self, logs_job_id=None, logs_offset=None, logs_limit=None,
                 since=None, epoch=None, include_jobs=True):
        with self._lock:
            self._advance()

            entries = [self._entry(job) for job in self.job_list]
            counts = {"total": 0, "running": 0, "queued": 0, "done": 0, "failed": 0}
            progress_sum = 0
            longest_elapsed = 0
            for entry, job in zip(entries, self.job_list):
                status = str(entry["status"]).lower().strip()
                counts["total"] += 1
                if status in RUNNING_STATUSES:
                    counts["running"] += 1
                elif status in QUEUED_STATUSES:
                    counts["queued"] += 1
                elif status in DONE_STATUSES:
                    counts["done"] += 1
                elif status in FAILED_STATUSES:
                    counts["failed"] += 1
                progress_sum += max(0, min(100, int(entry["progress"])))
                longest_elapsed = max(longest_elapsed, int(job.elapsed))

            full = True
            if not include_jobs:
                entries = []
                full = False
            elif since is not None and str(epoch or "") == self._epoch:
                try:
                    since_i = int(since)
                except Exception:
                    since_i = None
                if since_i is not None and 0 <= since_i <= self._revision:
                    entries = [
                        entry for entry in entries
                        if self._job_revisions.get(entry["id"], 0) > since_i
                    ]
                    full = False

            overall = int(round(progress_sum / counts["total"])) if counts["total"] else 0

            selected_id = int(self.selected_job_index) if self.job_list else -1
            if logs_job_id is None:
                logs_job_id = selected_id

            logs = None
            logs_job_id = int(logs_job_id)
            if 0 <= logs_job_id < len(self.job_list):
                job = self.job_list[logs_job_id]
                history = list(job.log_history)
                offset = max(0, int(job.log_position if logs_offset is None else logs_offset))
                limit = int(50 if logs_limit is None else logs_limit)
                lines = history[offset:] if limit < 0 else history[offset:offset + max(0, limit)]
                logs = {
                    "job_id": logs_job_id,
                    "total_lines": len(history),
                    "offset": offset,
                    "limit": limit,
                    "log_position": job.log_position,
                    "autoscroll": job.autoscroll,
                    "lines": lines,
                }

            return {
                "handler": {
                    "version": "dummy",
                    "nb_jobs": int(self.nb_jobs),
                    "process_group": False,
                    "auto_exit": False,
                    # No tool.yml: the log formatter is skipped for a dummy session.
                    "format_yaml": "",
                    "selected_job_index": selected_id,
                    "job_count": len(self.job_list),
                    "running": counts["running"],
                    "queued": counts["queued"],
                    "retired": counts["done"] + counts["failed"],
                    "theme": None,
                    "resource_guard": {
                        "enabled": False,
                        "cpu_limit": 100.0,
                        "mem_limit": 100.0,
                        "cpu": None,
                        "mem": None,
                        "auto_paused": 0,
                    },
                    "counts": counts,
                    "overall_progress": overall,
                    "longest_elapsed": longest_elapsed,
                    "first_job_id": self.job_list[0].id if self.job_list else None,
                    "status_buckets": STATUS_BUCKETS,
                    "status_sort_priority": STATUS_SORT_PRIORITY,
                },
                "jobs": entries,
                "full": full,
                "revision": int(self._revision),
                "epoch": self._epoch,
                "logs": logs,
            }

    # -- actions ---------------------------------------------------------

    def act(self, job_id, action):
        with self._lock:
            self._advance()
            if not (0 <= int(job_id) < len(self.job_list)):
                raise ValueError("job_id out of range")
            job = self.job_list[int(job_id)]
            if action == "pause":
                if job.status in RUNNING_STATUSES:
                    job.status = "paused"
                elif job.status == "queued":
                    job.status = "paused"
            elif action == "start":
                if job.status in ("paused", "queued"):
                    job.status = "running"
            elif action == "kill":
                if job.status not in DONE_STATUSES and job.status not in FAILED_STATUSES:
                    job.status = "killed"
                    self._log(job, "Job killed by user")
            elif action == "open":
                # Nothing to open: a dummy job has no directory on disk.
                pass
            elif action == "select":
                self.selected_job_index = int(job_id)
            else:
                raise ValueError("unknown action: {}".format(action))
            self._touch(job)
            return {"ok": True}

    def set_nb_jobs(self, nb_jobs):
        with self._lock:
            self._advance()
            self.nb_jobs = max(1, int(nb_jobs))
            return {"ok": True}


def _format_hms(seconds):
    seconds = max(0, int(seconds))
    return "{:d}:{:02d}:{:02d}".format(seconds // 3600, (seconds % 3600) // 60, seconds % 60)


######################################
# Registry + API façade
######################################

_SESSIONS = {}
_SESSIONS_LOCK = threading.Lock()


def get_session(key=DUMMY_SESSION_ID):
    """The dummy session named `key`, created on first use."""
    key = str(key or DUMMY_SESSION_ID)
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(key)
        if session is None:
            session = DummySession()
            _SESSIONS[key] = session
        return session


def reset_session(key=DUMMY_SESSION_ID):
    """Forget the dummy session, so the next request starts a fresh run."""
    with _SESSIONS_LOCK:
        _SESSIONS.pop(str(key or DUMMY_SESSION_ID), None)


def _split_path(path):
    path = str(path or "")
    if "?" not in path:
        return path, {}
    route, _, query = path.partition("?")
    params = {}
    for chunk in query.split("&"):
        if not chunk:
            continue
        name, _, value = chunk.partition("=")
        params[name] = value
    return route, params


def _int_param(params, name, default=None):
    value = params.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except Exception:
        return default


def api_get(path, key=DUMMY_SESSION_ID):
    """Answer a monitor `GET`, the way `Endpoint.get` would."""
    route, params = _split_path(path)
    session = get_session(key)
    if route != "/status":
        raise ValueError("unsupported dummy endpoint: {}".format(route))
    return session.snapshot(
        logs_job_id=_int_param(params, "logs_job_id"),
        logs_offset=_int_param(params, "logs_offset"),
        logs_limit=_int_param(params, "logs_limit"),
        since=_int_param(params, "since"),
        epoch=params.get("epoch"),
        include_jobs=_int_param(params, "include_jobs", 1) != 0,
    )


def api_post(path, key=DUMMY_SESSION_ID):
    """Answer a monitor `POST`, the way `Endpoint.post` would."""
    route, params = _split_path(path)
    session = get_session(key)

    if route == "/config":
        nb_jobs = _int_param(params, "nb_jobs")
        if nb_jobs is not None:
            return session.set_nb_jobs(nb_jobs)
        return {"ok": True}

    parts = [part for part in route.split("/") if part]
    if len(parts) == 3 and parts[0] == "jobs":
        return session.act(parts[1], parts[2])

    raise ValueError("unsupported dummy endpoint: {}".format(route))
