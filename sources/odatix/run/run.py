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
One run of a workspace, from what it would do to what it did.
"""

import odatix.lib.printc as printc
from odatix.run.errors import RunCancelled, RunError
from odatix.run.flows import flow_for
from odatix.run.options import RunOptions
from odatix.run.reporter import Reporter

__all__ = ["Run", "run_job"]


class Run(object):
    """
    A run of one of the commands of a workspace.

    It goes through three steps, and stopping after any of them is a normal
    thing to do::

        run = Run(Workspace.open(), "fmax_synthesis", tool="vivado")

        plan = run.check()      # what it would do, having touched nothing
        run.prepare()           # every work directory written, nothing started
        run.start()             # handed over to the daemon

    Each step needs the one before it, and does it when it has not been done.

    Args:
        workspace (Workspace): the workspace the run belongs to.
        mode (str): what to run, one of :data:`odatix.workspace.JOB_MODES`.
        options (RunOptions): what this run does differently from what its
            settings file says. Built from the keyword arguments when not given.
        reporter (Reporter): where what the run says is collected.
        cancel_event (threading.Event): asking the run to stop. Checking and
            preparing look at it between jobs, and raise :class:`RunCancelled`.
        **overrides: any :class:`RunOptions` setting, e.g. ``overwrite=True``.
    """

    def __init__(self, workspace, mode, options=None, reporter=None, cancel_event=None, **overrides):
        from odatix.workspace.jobs import resolve_mode

        self.workspace = workspace
        self.mode = resolve_mode(mode)
        self.flow = flow_for(self.mode)
        self.options = options if isinstance(options, RunOptions) else RunOptions(**(options or {}))
        self.options.update(overrides)
        self.reporter = reporter if reporter is not None else Reporter()
        self.cancel_event = cancel_event

        #: Eda tool checks handed over instead of being waited for. Left None so
        #: that the flows wait for them, which is what a run without a screen
        #: showing their progress wants.
        self.tool_check_sink = None

        self._checked = None
        self._parallel_jobs = None
        self._started = False

    ######################################
    # Where it works
    ######################################

    @property
    def config(self):
        """The run settings file of this run, as the workspace API sees it."""
        return self.workspace.jobs[self.mode]

    @property
    def settings_file(self):
        return self.options.settings_file or self.flow.settings_file(self.workspace)

    @property
    def work_path(self):
        return self.options.work_path or self.flow.work_path(self.workspace)

    def path(self, name):
        """
        Where one part of the workspace is, letting this run replace it.

        A run started from a script works on the workspace as it is configured;
        the command line lets a user point one of its parts elsewhere for a
        single run ("--archpath", "--work"), which is what the options hold.
        """
        return getattr(self.options, name, None) or getattr(self.workspace.paths, name)

    @property
    def result_path(self):
        """
        Where the results go. Nothing is exported when there is none, which is
        what a run working outside of a workspace does.
        """
        if self.options.result_path is not None:
            return self.options.result_path
        return self.workspace.paths.result_path

    @property
    def use_benchmark(self):
        if self.options.use_benchmark is not None:
            return bool(self.options.use_benchmark)
        return bool(self.workspace.settings.get("use_benchmark", False))

    @property
    def benchmark_file(self):
        return self.options.benchmark_file or self.workspace.paths.benchmark_file

    ######################################
    # What it would do
    ######################################

    def check(self):
        """
        Read everything the run needs, and work out what it would do with each
        of its jobs, without touching anything.

        Returns:
            JobPlan: what would be run, what is already done, and what cannot be
            run at all.

        Raises:
            RunError: the run cannot be started at all.
            RunCancelled: it was asked to stop.
        """
        self._checked = self._step("check", lambda: self.flow.check(self))
        return self._checked.plan

    @property
    def was_checked(self):
        """Whether checking has already been done, and its plan is in hand."""
        return self._checked is not None

    @property
    def plan(self):
        """What the run would do (see :meth:`check`)."""
        return self.checked().plan

    @property
    def jobs(self):
        """The jobs this run would run, as the objects its flow builds."""
        return self.checked().instances

    def checked(self):
        """What checking produced, checking first when it has not been done."""
        if self._checked is None:
            self.check()
        return self._checked

    ######################################
    # Doing it
    ######################################

    def prepare(self):
        """
        Write the work directory of every job: its sources, its parameters and
        the script that runs it. Nothing is started.

        Returns:
            ParallelJobHandler: the jobs, ready to be run.
        """
        checked = self.checked()
        self._parallel_jobs = self._step("prepare", lambda: self.flow.prepare(self, checked))
        return self._parallel_jobs

    def start(self, detach=None, session=None):
        """
        Hand the prepared jobs over to the daemon, preparing them first when
        that has not been done.

        Args:
            detach (bool): return as soon as the jobs are enqueued, instead of
                attaching the monitor to them. A run started from a script does,
                unless it is told otherwise.
            session (str): the daemon session to enqueue into.
        """
        if detach is not None:
            self.options.detach = detach
        if session is not None:
            self.options.session = session

        parallel_jobs = self._parallel_jobs if self._parallel_jobs is not None else self.prepare()
        self._step("start", lambda: self.flow.start(self, parallel_jobs))
        self._started = True
        return parallel_jobs

    def execute(self):
        """Check, prepare and start, in one call."""
        self.check()
        self.prepare()
        return self.start()

    ######################################
    # Running a step
    ######################################

    def _step(self, name, action):
        """
        Run one step, collecting what it says and turning how it stops into
        something a caller can catch.

        The run flows report through printc and stop the process, which is what
        the command line wants from them. Here the report is kept and the stop
        becomes an exception carrying it.
        """
        cancelled = self.flow.cancelled_exceptions()
        before = len(self.reporter)
        try:
            with self.reporter.listening():
                return action()
        except cancelled:
            raise RunCancelled("The {0} run was cancelled while it was {1}ing.".format(self.mode, name))
        except RunError:
            raise
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else -1
            raise RunError(
                self._failure_message(name, before),
                messages=self.reporter.messages[before:],
                code=code,
            )

    def _failure_message(self, step, first_message):
        """What the run said last about why it stopped."""
        for level, text in reversed(self.reporter.messages[first_message:]):
            if level == "error":
                return text
        return "The {0} run could not be {1}ed.".format(self.mode, step)

    def __repr__(self):
        return "<Run {0!r} of {1!r}>".format(self.mode, self.workspace.root)


def run_job(mode, workspace=None, **overrides):
    """
    Run one of the commands of a workspace, from beginning to end.

    A shortcut for the common case::

        from odatix.run import run_job

        run_job("fmax_synthesis", tool="vivado", overwrite=True)

    Args:
        mode (str): what to run.
        workspace (Workspace): the workspace to run it in. The one of the
            current directory when not given.
        **overrides: any :class:`RunOptions` setting.

    Returns:
        Run: the run, once its jobs have been handed over to the daemon.
    """
    from odatix.workspace import Workspace

    run = Run(workspace if workspace is not None else Workspace.open(), mode, **overrides)
    run.execute()
    return run
