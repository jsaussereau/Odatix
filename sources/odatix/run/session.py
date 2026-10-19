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
The sessions that run the jobs, seen from a script.

A started run hands its jobs over to a session: a background process of its own,
which keeps running them once the script is gone. This is what ``odatix ps``,
``odatix monitor`` and ``odatix stop`` do from a terminal, as objects.
"""

import os
import time

from odatix.lib.parallel_job_handler import daemon_control
from odatix.lib.parallel_job_handler.job_status import (
    DONE_STATUSES,
    FAILED_STATUSES,
    QUEUED_STATUSES,
    RUNNING_STATUSES,
)

__all__ = ["Session", "sessions", "SessionError"]


class SessionError(RuntimeError):
    """A session cannot be found, reached or told something."""


#: Statuses of a job its session is done with.
FINISHED_STATUSES = tuple(DONE_STATUSES) + tuple(FAILED_STATUSES)


def _workspace_root(workspace):
    """The directory of a workspace, given as a Workspace, a path or None."""
    root = getattr(workspace, "root", workspace)
    root = os.getcwd() if root in (None, "", ".") else str(root)
    return daemon_control.detect_workspace_root(root)


def _normalized_dir(path, base=None):
    if not path:
        return ""
    path = str(path)
    if base and not os.path.isabs(path):
        path = os.path.join(str(base), path)
    return os.path.realpath(os.path.expanduser(path))


def _bucket(status):
    status = str(status or "").strip().lower()
    for name, statuses in (
        ("running", RUNNING_STATUSES),
        ("queued", QUEUED_STATUSES),
        ("done", DONE_STATUSES),
        ("failed", FAILED_STATUSES),
    ):
        if status in statuses:
            return name
    return "queued"


def count_jobs(jobs):
    """
    How many of `jobs` (as :meth:`Session.jobs` gives them) are in each state.

    Returns:
        dict: ``total``, ``running``, ``queued`` (paused jobs included),
        ``done`` and ``failed`` (killed and canceled jobs included).
    """
    counts = {"total": 0, "running": 0, "queued": 0, "done": 0, "failed": 0}
    for job in jobs:
        counts["total"] += 1
        counts[_bucket(job.get("status"))] += 1
    return counts


class Session(object):
    """
    One session: the background process running the jobs a run handed over.

    Get one from :func:`sessions`, from :meth:`Session.find`, or from
    :attr:`odatix.run.Run.session` once a run is started::

        from odatix.run import sessions

        for session in sessions():
            print(session.id, session.counts())

    Args:
        state (dict): how to reach the session, as the session listing gives
            it. Not meant to be built by hand.
    """

    def __init__(self, state):
        if not isinstance(state, dict):
            raise SessionError("A session is described by a dict, not {0!r}".format(state))
        self._state = dict(state)

    ######################################
    # Finding one
    ######################################

    @classmethod
    def find(cls, selector=None, workspace=None, any_workspace=False):
        """
        The session `selector` names, as ``odatix monitor -S`` finds it.

        Args:
            selector (str): its name, its id (``"12345.nightly"``), its pid,
                or the start of one of them. Without one, the only session of the
                workspace.
            workspace (Workspace or str): the workspace to look in. The one of
                the current directory when not given.
            any_workspace (bool): look in every workspace, not only this one.

        Raises:
            SessionError: no session, or several, match.
        """
        try:
            state = daemon_control._resolve_state_for_attach_or_stop(
                workspace_root=_workspace_root(workspace), session=selector, any_workspace=any_workspace,
            )
        except daemon_control.MultipleDaemonsError as error:
            raise SessionError(
                "Several sessions match: " + ", ".join(str(d.get("session_id", "?")) for d in error.daemons)
            )
        except daemon_control.DaemonControlError as error:
            raise SessionError(str(error))
        return cls(state)

    ######################################
    # What it is
    ######################################

    @property
    def id(self):
        """The session id, its pid and its name (``"12345.nightly"``), as ``odatix ps`` shows it."""
        return str(self._state.get("session_id") or daemon_control._session_id_from_state(self._state))

    @property
    def name(self):
        """The session name, what ``-S`` is given."""
        return str(self._state.get("session_name") or daemon_control._session_name_from_state(self._state))

    @property
    def pid(self):
        """The process id of the session."""
        try:
            return int(self._state.get("pid"))
        except (TypeError, ValueError):
            return None

    @property
    def workspace_root(self):
        """The workspace the session belongs to."""
        return self._state.get("workspace_root")

    @property
    def address(self):
        """Where the session listens (a unix socket or host:port)."""
        return daemon_control._state_address(self._state)

    def is_alive(self):
        """Whether the session answers."""
        return daemon_control.daemon_is_alive(self._state, timeout=2.0)

    ######################################
    # What it is doing
    ######################################

    def _request(self, method, path, timeout=10.0):
        try:
            return daemon_control._api_request(self._state, method, path, timeout=float(timeout))
        except Exception as error:
            raise SessionError("Session {0} did not answer: {1}".format(self.id, error))

    def status(self, timeout=10.0):
        """
        What the session says of itself: how many jobs it runs at once, its
        resource guard, and its jobs.

        Returns:
            dict: ``nb_jobs``, ``resource_guard`` (``enabled``, ``cpu_limit``,
            ``mem_limit``...), ``counts`` (see :meth:`counts`) and ``jobs``
            (see :meth:`jobs`).

        Raises:
            SessionError: the session did not answer.
        """
        snapshot = self._request("GET", "/status?logs_job_id=-1", timeout=timeout)
        handler = snapshot.get("handler", {}) if isinstance(snapshot, dict) else {}
        jobs = self._jobs_of(snapshot)
        return {
            "nb_jobs": handler.get("nb_jobs"),
            "resource_guard": dict(handler.get("resource_guard") or {}),
            "counts": count_jobs(jobs),
            "jobs": jobs,
        }

    def _jobs_of(self, snapshot):
        jobs = snapshot.get("jobs", []) if isinstance(snapshot, dict) else []
        root = self.workspace_root
        return [
            {
                "id": int(job.get("id", index)),
                "name": str(job.get("display_name", "")),
                "status": str(job.get("status", "")),
                "progress": job.get("progress", 0),
                "elapsed": str(job.get("elapsed_time", "")),
                "tmp_dir": _normalized_dir(job.get("tmp_dir"), base=root),
            }
            for index, job in enumerate(jobs) if isinstance(job, dict)
        ]

    def jobs(self, timeout=10.0):
        """
        The jobs of the session, in the order it received them.

        Returns:
            list: one dict per job: ``id`` (what :meth:`pause`, :meth:`resume`
            and :meth:`kill` take), ``name``, ``status`` ("queued", "running",
            "paused", "success", "failed", "killed", "canceled"...),
            ``progress`` (percent), ``elapsed`` ("HH:MM:SS") and ``tmp_dir``
            (the job's work directory, absolute).
        """
        return self.status(timeout=timeout)["jobs"]

    def counts(self, timeout=10.0):
        """
        How many jobs are in each state.

        Returns:
            dict: ``total``, ``running``, ``queued`` (paused jobs included),
            ``done`` and ``failed`` (killed and canceled jobs included).
        """
        return self.status(timeout=timeout)["counts"]

    def is_finished(self, timeout=10.0):
        """Whether every job of the session is over, however it ended."""
        counts = self.counts(timeout=timeout)
        return counts["running"] == 0 and counts["queued"] == 0

    def wait(self, timeout=None, poll_interval=2.0, job_ids=None):
        """
        Wait until the jobs are over, however they end.

        Args:
            timeout (float): give up after that many seconds. Forever when None.
            poll_interval (float): how often to ask the session, in seconds.
            job_ids (list): only wait for these jobs (ids from :meth:`jobs`).

        Returns:
            list: the jobs waited for, as :meth:`jobs` gives them.

        Raises:
            SessionError: the session is gone before the jobs are over.
            TimeoutError: they were not over in time.
        """
        wanted = None if job_ids is None else set(int(job_id) for job_id in job_ids)
        return self._wait_for(lambda job: wanted is None or job["id"] in wanted, timeout, poll_interval)

    def _wait_for(self, selected, timeout, poll_interval):
        deadline = None if timeout is None else time.time() + float(timeout)
        while True:
            jobs = [job for job in self.jobs() if selected(job)]
            if all(job["status"] in FINISHED_STATUSES for job in jobs):
                return jobs
            if deadline is not None and time.time() >= deadline:
                raise TimeoutError("Session {0}: jobs still running after {1}s".format(self.id, timeout))
            time.sleep(max(0.05, float(poll_interval)))

    ######################################
    # Telling it what to do
    ######################################

    def pause(self, job_id):
        """Pause a running job (an id from :meth:`jobs`)."""
        self._request("POST", "/jobs/{0}/pause".format(int(job_id)))

    def resume(self, job_id):
        """Resume a paused job, or start a queued or canceled one."""
        self._request("POST", "/jobs/{0}/start".format(int(job_id)))

    def kill(self, job_id):
        """Kill a running or paused job, or cancel a queued one."""
        self._request("POST", "/jobs/{0}/kill".format(int(job_id)))

    def set_jobs(self, nb_jobs):
        """Change how many jobs run at once."""
        self._request("POST", "/config?nb_jobs={0}".format(max(1, int(nb_jobs))))

    def set_resource_guard(self, enabled):
        """Turn the resource guard (auto-pause on overload) on or off."""
        self._request("POST", "/config?resource_guard={0}".format("true" if enabled else "false"))

    def stop(self):
        """
        Stop the session, and the jobs still running in it, as ``odatix stop``
        does.

        Returns:
            bool: whether the session is confirmed gone.
        """
        return bool(daemon_control._stop_daemon_from_state(self._state, self.workspace_root))

    def __eq__(self, other):
        return isinstance(other, Session) and (self.id, self.address) == (other.id, other.address)

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash((self.id, self.address))

    def __repr__(self):
        return "<Session {0!r} of {1!r}>".format(self.id, self.workspace_root)


def sessions(workspace=None, any_workspace=False):
    """
    The sessions running jobs, as ``odatix ps`` lists them.

    Args:
        workspace (Workspace or str): the workspace whose sessions to list. The
            one of the current directory when not given.
        any_workspace (bool): list the sessions of every workspace.

    Returns:
        list: :class:`Session` objects.
    """
    root = _workspace_root(workspace)
    daemons = daemon_control.list_daemons(workspace_root=root)
    in_scope, _root, _scoped = daemon_control.scope_daemons(daemons, root, any_workspace=any_workspace)
    return [Session(state) for state in in_scope]
