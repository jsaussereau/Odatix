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
What a run should do with a job it already has a directory for.

A job directory is not necessarily something to run again: a previous run may
have finished it, stopped in the middle of it, or done the first steps of its
flow, and another session may be running it right now. Deciding between those
is what this does, and it is the same decision whatever the job is, which is why
it lives on its own rather than inside the handler of one job type.
"""

import os
from os.path import isdir, isfile

import odatix.lib.printc as printc
from odatix.lib.parallel_job_handler.daemon_control import list_daemon_jobs
from odatix.lib.run_report import Category, JobPlan

__all__ = ["JobPlanner"]

script_name = os.path.basename(__file__)


class JobPlanner(object):
    """
    What a run does with each of its job directories, and the plan it builds
    from those decisions.

    Args:
        work_path (str): where the jobs of this run live.
        work_log_path (str): the log directory inside a job directory.
        status_filename (str): the file a finished job writes its status in.
        valid_status (str): what that file holds when the job went through.
        overwrite (bool): run again what is already done.
        requested_steps (list): names of the flow steps this run covers, when
            the flow is split into steps (see odatix.lib.job_steps). Empty for a
            flow that runs in one go.
        rerun_step_index (int): index of the step "--rerun-from" points at.
            Everything from there on is run again, even when already recorded.
    """

    #: A job a session left in one of these states is not being worked on by it
    #: any more: a run may take it over.
    DAEMON_RESTARTABLE_STATUSES = ("failed", "killed", "canceled", "cancelled")

    #: Statuses of a job a session is done with: re-enqueueing over one of them
    #: is allowed when the flow has steps left to run (see daemon_decision).
    DAEMON_FINISHED_STATUSES = ("success", "done", "finished")

    def __init__(self, work_path="", work_log_path="", status_filename="", valid_status="",
                 overwrite=False, requested_steps=None, rerun_step_index=None):
        self.work_path = work_path
        self.work_log_path = work_log_path
        self.status_filename = status_filename
        self.valid_status = valid_status
        self.overwrite = overwrite
        self.requested_steps = list(requested_steps) if requested_steps else []
        self.rerun_step_index = rerun_step_index
        self.reset()

    def reset(self):
        """Forget every decision taken so far."""
        # Single source of truth for the check outcome: the CLI checklist and
        # the GUI run popup both read this plan.
        self.plan = JobPlan()
        self._daemon_jobs_by_tmp_dir = None
        return self

    ######################################
    # Steps
    ######################################

    def steps_decision(self, tmp_dir):
        """
        Cache decision for a flow split into steps, or None when the flow is not
        stepped (the caller then falls back to the status file).

        Returns "cached" when the directory already holds every step this run
        asks for, "resume" when it holds some of them (the run picks up at the
        first missing one), "new" otherwise.

        This has to take precedence over the status file: a directory left by a
        run that stopped at an earlier step holds a perfectly valid status file,
        and must not be mistaken for a complete result.
        """
        if not self.requested_steps:
            return None

        import odatix.lib.job_steps as job_steps

        done = job_steps.resume_index(tmp_dir, self.requested_steps)
        if self.rerun_step_index is not None:
            done = min(done, self.rerun_step_index)
        if done >= len(self.requested_steps):
            return "cached"
        return "resume" if done > 0 else "new"

    ######################################
    # Daemon sessions
    ######################################

    @staticmethod
    def normalize_tmp_dir(tmp_dir):
        if tmp_dir is None:
            return ""
        try:
            return os.path.realpath(os.path.expanduser(str(tmp_dir)))
        except Exception:
            return str(tmp_dir)

    @staticmethod
    def format_daemon_entry(entry):
        """How a job another session owns is named in the plan."""
        status = str(entry.get("status", "unknown"))
        session_id = str(entry.get("session_id", "")).strip()
        if session_id == "":
            return " {0}(session status: {1}){2}".format(printc.colors.GREY, status, printc.colors.ENDC)
        return " {0}({1} in session {2}){3}".format(printc.colors.GREY, status, session_id, printc.colors.ENDC)

    def refresh_daemon_jobs(self):
        """Read what the daemon sessions are working on."""
        self._daemon_jobs_by_tmp_dir = {}
        try:
            daemon_jobs = list_daemon_jobs(workspace_root=self.work_path)
        except Exception:
            daemon_jobs = []

        for job in daemon_jobs:
            if not isinstance(job, dict):
                continue

            normalized_tmp_dir = JobPlanner.normalize_tmp_dir(job.get("tmp_dir", ""))
            if normalized_tmp_dir == "":
                continue

            status = str(job.get("status", "")).strip().lower()
            if status == "":
                status = "unknown"

            self._daemon_jobs_by_tmp_dir.setdefault(normalized_tmp_dir, []).append(
                {
                    "status": status,
                    "session_id": str(job.get("session_id", "")).strip(),
                }
            )
        return self

    def daemon_decision(self, tmp_dir, steps_decision=None):
        """
        Whether a job is already handled by a daemon session ("skip"), can be
        re-enqueued over a failed one ("replace"), or is unknown to every
        session ("none").

        `steps_decision` is the step-level verdict for the same directory (see
        :meth:`steps_decision`): a session that ran an earlier step of the flow
        reports a successful job, which must not stand in the way of running the
        steps left to do.
        """
        if self._daemon_jobs_by_tmp_dir is None:
            self.refresh_daemon_jobs()

        daemon_entries = self._daemon_jobs_by_tmp_dir.get(JobPlanner.normalize_tmp_dir(tmp_dir), [])
        if len(daemon_entries) == 0:
            return "none", None

        # A job still queued or running belongs to its session whatever the
        # steps say; a finished one does not when steps are left to run.
        finished_is_restartable = steps_decision in ("resume", "new")

        for entry in daemon_entries:
            status = entry["status"]
            if status in JobPlanner.DAEMON_RESTARTABLE_STATUSES:
                continue
            if finished_is_restartable and status in JobPlanner.DAEMON_FINISHED_STATUSES:
                continue
            return "skip", entry

        return "replace", daemon_entries[0]

    ######################################
    # The decision itself
    ######################################

    def classify_job(self, tmp_dir, subject, job_noun="synthesis"):
        """
        Decide what a run should do with a job directory, printing the notes and
        warnings the checklist is built from.

        The verdict comes from three sources, in order of precedence: the step
        state of the directory (see :meth:`steps_decision`), its status file,
        then the daemon sessions (a job another session already owns is not run
        again).

        Args:
            tmp_dir (str): the job directory.
            subject (str): how to name the job in the messages, already quoted and
                complete (e.g. '"Counter/8bits" @ 50 MHz with target "gf22"').
            job_noun (str): what the previous run was, for the "not finished"
                warning ("synthesis", "place & route", ...).

        Returns:
            tuple: (state, daemon_entry) where state is one of "cached",
            "daemon", "overwrite", "incomplete", "resume" or "new". Mapping a
            state to a plan category is left to the caller, which knows how it
            names its jobs there.
        """
        state = "new"

        status_file = os.path.join(tmp_dir, self.work_log_path, self.status_filename)
        steps_decision = self.steps_decision(tmp_dir)

        if steps_decision is not None:
            if steps_decision == "cached":
                if self.overwrite:
                    printc.warning("Every requested step is already done for " + subject + ".", script_name)
                    state = "overwrite"
                else:
                    printc.note("Every requested step is already done for " + subject + ". Skipping.", script_name)
                    state = "cached"
            elif steps_decision == "resume" and not self.overwrite:
                state = "resume"
        elif isdir(tmp_dir) and isfile(status_file):
            # Check whether the previous run completed.
            with open(status_file, "r") as sf:
                completed = self.valid_status in sf.read()
            if completed:
                if self.overwrite:
                    printc.warning("Found cached results for " + subject + ".", script_name)
                    state = "overwrite"
                else:
                    printc.note("Found cached results for " + subject + ". Skipping.", script_name)
                    state = "cached"
            else:
                printc.warning(
                    "The previous " + job_noun + " for " + subject
                    + " has not finished or the directory has been corrupted.",
                    script_name,
                )
                state = "incomplete"

        if state == "cached":
            return "cached", None

        decision, daemon_entry = self.daemon_decision(tmp_dir, steps_decision)
        if decision == "skip":
            daemon_status = str(daemon_entry.get("status", "unknown"))
            daemon_session = str(daemon_entry.get("session_id", "")).strip() or "unknown"
            printc.note(
                "Found existing daemon job for " + subject
                + " (session \"" + daemon_session + "\", status \"" + daemon_status + "\"). Skipping.",
                script_name,
            )
            return "daemon", daemon_entry
        if decision == "replace":
            daemon_status = str(daemon_entry.get("status", "unknown"))
            printc.warning(
                "Found previously failed/canceled daemon job for " + subject
                + " (status \"" + daemon_status + "\"). Re-enqueueing.",
                script_name,
            )

        return state, daemon_entry

    ######################################
    # The plan
    ######################################

    def record(self, name, state, daemon_entry=None):
        """
        Add a job to the plan, under the category its state calls for.

        Returns whether the job is one this run will actually work on, which is
        what tells a caller to keep building it.
        """
        if state == "cached":
            self.plan.add(name, Category.CACHED)
            return False
        if state == "daemon":
            self.plan.add(name + JobPlanner.format_daemon_entry(daemon_entry or {}), Category.DAEMON)
            return False
        self.plan.add(name, STATE_CATEGORIES.get(state, Category.NEW))
        return True

    def __repr__(self):
        return "<JobPlanner {0!r}>".format(self.work_path)


#: The plan category each decision lands in.
STATE_CATEGORIES = {
    "overwrite": Category.OVERWRITE,
    "incomplete": Category.INCOMPLETE,
    "resume": Category.RESUME,
    "new": Category.NEW,
}
