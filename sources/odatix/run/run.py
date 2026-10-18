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

import difflib
import os

import odatix.lib.printc as printc
from odatix.run.errors import NOTHING_TO_RUN, NothingToRun, RunCancelled, RunError
from odatix.run.flows import flow_for
from odatix.run.options import RunOptions
from odatix.run.reporter import CollectingReporter, Reporter

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

    Once started, the jobs run in a session of their own, which outlives the
    script: :attr:`session`, :meth:`status` and :meth:`wait` follow them::

        run.start()
        jobs = run.wait()       # every job of the run over, however it ended
        failed = [job["name"] for job in jobs if job["status"] != "success"]

    Args:
        workspace (Workspace): the workspace the run belongs to.
        mode (str): what to run, one of :data:`odatix.workspace.JOB_MODES`.
        options (RunOptions): what this run does differently from what its
            settings file says. Built from the keyword arguments when not given.
        reporter (Reporter): where what the run says is collected.
        quiet (bool): print nothing (the control list, the progress bars):
            what the run says is only collected, in a
            :class:`CollectingReporter`. Ignored when ``reporter`` is given.
        cancel_event (threading.Event): asking the run to stop. Checking and
            preparing look at it between jobs, and raise :class:`RunCancelled`.
        **overrides: any :class:`RunOptions` setting, e.g. ``overwrite=True``.

    Raises:
        TypeError: an option is not a :class:`RunOptions` setting. A misspelled
            option would otherwise be ignored, and the run would do what its
            settings file says instead.
    """

    def __init__(self, workspace, mode, options=None, reporter=None, cancel_event=None, quiet=False, **overrides):
        from odatix.workspace.jobs import resolve_mode

        self.workspace = workspace
        self.mode = resolve_mode(mode)
        self.flow = flow_for(self.mode)
        if not isinstance(options, RunOptions):
            Run._check_option_names(options or {})
        Run._check_option_names(overrides)
        self.options = options if isinstance(options, RunOptions) else RunOptions(**(options or {}))
        self.options.update(overrides)
        if reporter is None:
            reporter = CollectingReporter() if quiet else Reporter()
        self.reporter = reporter
        self.cancel_event = cancel_event

        #: Eda tool checks handed over instead of being waited for. Left None so
        #: that the flows wait for them, which is what a run without a screen
        #: showing their progress wants.
        self.tool_check_sink = None

        self._checked = None
        self._parallel_jobs = None
        self._started = False
        self._session = None
        self._job_dirs = []

    @staticmethod
    def _check_option_names(values):
        """Refuse what is not a run option, naming the closest ones."""
        known = [spec.key for spec in RunOptions.specs()]
        for name in values:
            if RunOptions.spec(name) is not None or name in known:
                continue
            close = difflib.get_close_matches(str(name), known, n=3)
            hint = " (did you mean {0}?)".format(" or ".join(repr(c) for c in close)) if close else ""
            raise TypeError(
                "Unknown run option {0!r}{1}. The options are those of odatix.run.RunOptions: {2}".format(
                    name, hint, ", ".join(known)
                )
            )

    ######################################
    # Where it works
    ######################################

    @property
    def config(self):
        """The run settings file of this run, as the workspace API sees it."""
        return self.workspace.jobs[self.mode]

    @property
    def settings_file(self):
        """The run settings file this run reads (``options.settings_file``, or the workspace's)."""
        return self.options.settings_file or self.flow.settings_file(self.workspace)

    @property
    def work_path(self):
        """The directory the jobs of this run work in."""
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
        settings_file = os.path.join(self.workspace.root, self.settings_file)
        if not self.workspace.exists and not os.path.isfile(settings_file):
            # Said here, since what the flow would say ("Settings file ... does
            # not exist") hides that the whole directory is not a workspace
            raise RunError(
                "'{0}' is not an Odatix workspace: it holds no '{1}'. Open the workspace the run belongs to "
                "(Workspace.open(path, required=True)), or create one with Workspace.init().".format(
                    self.workspace.root, self.workspace.SETTINGS_FILENAME
                )
            )
        self._checked = self._step("check", self._check)
        return self._checked.plan

    def _check(self):
        self.resolve_tool()
        return self.flow.check(self)

    #: The runs that need an eda tool, and take the default one when not told which.
    TOOL_MODES = ("fmax_synthesis", "custom_freq_synthesis", "analysis")

    def resolve_tool(self):
        """
        Settle which eda tool the run uses: the one it was told, else the
        default tool of the workspace (see :attr:`Workspace.default_tool`), and
        refuse a tool Odatix does not know, saying which ones it does.
        """
        if self.mode not in self.TOOL_MODES and self.mode != "pnr":
            return
        if not self.options.tool and self.mode in self.TOOL_MODES:
            tool = self.workspace.default_tool
            if tool is None:
                configured = self.workspace.configured_tools()
                printc.error('No eda tool to run: -t/--tool names none, and odatix.yml has no "default_tool"', "run")
                printc.note("Tools with a target file in this workspace: " + (", ".join(configured) or "none"), "run")
                printc.tip('Set "default_tool" in odatix.yml, or name the tool with -t/--tool', "run")
                raise SystemExit(-1)
            self.options.tool = [tool] if self.mode == "analysis" else tool
        tools = self.options.tool if isinstance(self.options.tool, (list, tuple)) else [self.options.tool]
        known = self.workspace.tools.all_names()
        unknown = [str(tool) for tool in tools if tool and str(tool) not in known]
        if unknown:
            printc.error('Unknown eda tool "{0}"'.format('", "'.join(unknown)), "run")
            printc.note("Available tools: " + ", ".join(known), "run")
            raise SystemExit(-1)

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
        self._parallel_jobs = self._step(
            "prepare", lambda: self._with_workspace_guard(self.flow.prepare(self, checked))
        )
        return self._parallel_jobs

    def _with_workspace_guard(self, parallel_jobs):
        """
        Give the jobs the resource guard of the workspace ("resource_guard",
        "cpu_limit" and "mem_limit" in odatix.yml), read now: a value changed
        since the last run applies to this one.
        """
        from odatix.lib.settings import OdatixSettings

        settings = self.workspace.settings
        settings_file = getattr(self.workspace, "settings_file", OdatixSettings.DEFAULT_SETTINGS_FILE)
        enabled, cpu_limit, mem_limit = OdatixSettings.read_resource_guard(settings, settings_file)
        configure = getattr(parallel_jobs, "configure_runtime", None)
        if callable(configure):
            configure(resource_guard=enabled, cpu_limit=cpu_limit, mem_limit=mem_limit)
        return parallel_jobs

    def start(self, detach=None, session=None):
        """
        Hand the prepared jobs over to a session, preparing them first when
        that has not been done. :attr:`session` is then the session that took
        them.

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
        # Where the jobs are, as the session will report them: what tells this
        # run's jobs apart from the others of a shared session.
        self._job_dirs = [
            os.path.realpath(str(job.tmp_dir)) for job in getattr(parallel_jobs, "job_list", []) or []
            if getattr(job, "tmp_dir", None)
        ]
        self._step("start", lambda: self.flow.start(self, parallel_jobs))
        self._started = True
        state = getattr(parallel_jobs, "session_state", None)
        if isinstance(state, dict):
            from odatix.run.session import Session

            self._session = Session(state)
        return parallel_jobs

    ######################################
    # Following it
    ######################################

    @property
    def session(self):
        """
        The :class:`~odatix.run.session.Session` running the jobs, once
        :meth:`start` handed them over. None before.
        """
        return self._session

    @property
    def followed(self):
        """
        Whether :meth:`start` followed the jobs until they were over: in the
        job monitor until it closed, or, when the terminal could not show it,
        by waiting for them ("exit_when_done"). False when the run was
        detached, or could not show the monitor and was not told to wait: the
        jobs may then still be running.
        """
        return bool(getattr(self._parallel_jobs, "followed_in_monitor", False))

    def _started_session(self):
        if self._session is None:
            raise RunError("The {0} run has not been started: it has no session to follow.".format(self.mode))
        return self._session

    def _own_jobs(self, jobs):
        """The jobs of this run among those of its session: the last one per work directory."""
        wanted = set(self._job_dirs)
        latest = {}
        for job in jobs:
            if job["tmp_dir"] in wanted:
                latest[job["tmp_dir"]] = job
        return [latest[path] for path in self._job_dirs if path in latest]

    def status(self):
        """
        Where the jobs of this run are, as its session reports them.

        Returns:
            list: one dict per job, as :meth:`Session.jobs` gives them
            (``name``, ``status``, ``progress``...).

        Raises:
            RunError: the run has not been started.
            SessionError: its session did not answer.
        """
        return self._own_jobs(self._started_session().jobs())

    def wait(self, timeout=None, poll_interval=2.0):
        """
        Wait until every job of this run is over, however it ends.

        Args:
            timeout (float): give up after that many seconds. Forever when None.
            poll_interval (float): how often to ask the session, in seconds.

        Returns:
            list: the jobs of the run, as :meth:`status` gives them.

        Raises:
            RunError: the run has not been started.
            SessionError: its session did not answer.
            TimeoutError: the jobs were not over in time.
        """
        session = self._started_session()
        wanted = set(self._job_dirs)
        session._wait_for(lambda job: job["tmp_dir"] in wanted, timeout, poll_interval)
        return self.status()

    def analysis_results(self):
        """
        What the analyses of this run found, once its jobs are over (see :meth:`wait`).

        Returns:
            list: AnalysisResult objects, one per job the run launched.
            ``odatix.lib.analysis.count_by_status`` counts them by verdict.
        """
        from odatix.components import analysis_report
        return analysis_report.run_results(self)

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
            with self.reporter.listening(), _working_directory(self.workspace.root), _plain_unless_terminal():
                return action()
        except cancelled:
            raise RunCancelled("The {0} run was cancelled while it was {1}ing.".format(self.mode, name))
        except RunError:
            raise
        except SystemExit as stop:
            code = stop.code if isinstance(stop.code, int) else -1
            if code == NOTHING_TO_RUN:
                raise NothingToRun(
                    "Nothing to run: every job of the {0} run is already done, or already "
                    "running in a session (see odatix.run.sessions).".format(self.mode),
                    messages=self.reporter.messages[before:],
                )
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


class _working_directory(object):
    """
    Run a step from the root of its workspace. The run flows read the paths of
    the settings files (rtl_path, work_path...) relative to the current
    directory, as the command line, started from the workspace, does: a script
    opening a workspace from elsewhere would find none of them.
    """

    def __init__(self, path):
        self.path = path
        self.previous = None

    def __enter__(self):
        if self.path and os.path.isdir(self.path):
            current = os.getcwd()
            if os.path.realpath(current) != os.path.realpath(self.path):
                self.previous = current
                os.chdir(self.path)
        return self

    def __exit__(self, *exc_info):
        if self.previous is not None:
            os.chdir(self.previous)
        return False


class _plain_unless_terminal(object):
    """
    Drop the color codes a step prints when the script's output is not a
    terminal, as the command line does (printc.plain_unless_terminal), and give
    the script its own stream back afterwards.
    """

    def __init__(self):
        self.replaced = []

    def __enter__(self):
        import sys

        for name in ("stdout", "stderr"):
            stream = getattr(sys, name, None)
            if stream is None or isinstance(stream, printc._PlainStream) or printc.wants_color(stream):
                continue
            plain = printc._PlainStream(stream)
            setattr(sys, name, plain)
            self.replaced.append((name, stream, plain))
        return self

    def __exit__(self, *exc_info):
        import sys

        for name, stream, plain in self.replaced:
            # Another thread may have put its own stream there since.
            if getattr(sys, name, None) is plain:
                setattr(sys, name, stream)
        return False
