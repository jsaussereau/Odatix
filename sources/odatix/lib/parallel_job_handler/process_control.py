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
Starting, signaling and stopping the processes of the jobs.

Everything that sends a signal to a job goes through here, so that there is one
answer to "what does this signal reach":

* A job started with its own process group (the tool's ``process_group: true``,
  the default) is signaled as a whole: the shell, the tool, and whatever the
  tool started.
* A job started without one shares the group of the handler. Signaling that
  group would signal the handler itself -- the daemon used to kill itself that
  way. Only the job's own process is signaled then; what the tool started on
  its own is the tool's to manage, which is what ``process_group: false`` asks
  for.

Stopping is done in two halves so that the scheduler never waits for a process
while it holds its lock: :func:`request_stop` sends the signals and returns,
:func:`reap` (called on every tick) collects what has exited and finishes off
what did not within :data:`TERMINATE_TIMEOUT_S`. :func:`terminate` chains both
for the paths that can afford to wait, the end of a session.
"""

import os
import signal
import subprocess
import sys
import threading
import time

from .utils import read_pipe_windows

if sys.platform != "win32":
    import fcntl

#: How long a job asked to stop gets to do so before it is killed.
TERMINATE_TIMEOUT_S = 5.0

WINDOWS = sys.platform == "win32"


######################################
# Starting
######################################

def spawn(command, cwd, own_group):
    """
    Start `command` through the shell, its output piped.

    Args:
        own_group (bool): put the process in a new process group, so that it
            can later be signaled together with everything it starts.
    """
    kwargs = {}
    if own_group:
        if WINDOWS:
            # CTRL_BREAK_EVENT only reaches a process that heads its own group:
            # without this flag it goes to the console group of the handler.
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["preexec_fn"] = os.setpgrp
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
        shell=True,
        bufsize=0,
        **kwargs
    )


def start_job_process(job, command, cwd, own_group, on_output):
    """
    Start `command` as the process of `job`, and wire its output.

    Under POSIX the scheduler polls the pipes, which are made non-blocking.
    Windows cannot select() on pipes: a thread per pipe reads them instead and
    hands what it reads to `on_output(job, data, stream_key)`.
    """
    process = spawn(command, cwd, own_group)
    job.process = process
    job.own_group = bool(own_group)
    job._stop_deadline = None
    if WINDOWS:
        for pipe, stream_key in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            threading.Thread(
                target=read_pipe_windows,
                args=(pipe, job, lambda j, d, key=stream_key: on_output(j, d, key)),
                daemon=True,
            ).start()
    else:
        set_nonblocking(process.stdout)
        set_nonblocking(process.stderr)
    return process


def set_nonblocking(pipe):
    """Make reading `pipe` return what is there instead of waiting for more."""
    if WINDOWS or pipe is None:
        return
    try:
        fd = pipe.fileno() if hasattr(pipe, "fileno") else pipe
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    except (TypeError, ValueError, OSError):
        pass


######################################
# Signaling
######################################

def is_alive(job):
    """Whether the process of `job` has not exited yet (reaping it if it has)."""
    process = getattr(job, "process", None)
    return process is not None and process.poll() is None


def _group_of(job):
    """
    The process group to signal for `job`, or None to signal its process alone.

    Only a job started in its own group is signaled as a group. The check that
    the group is not the handler's is a second line of defense: a job is never
    supposed to share it while claiming its own.
    """
    if not getattr(job, "own_group", False):
        return None
    try:
        group = os.getpgid(job.process.pid)
    except (ProcessLookupError, OSError):
        return None
    if group == os.getpgid(0):
        return None
    return group


def send(job, sig):
    """
    Send `sig` to `job`: to its whole group when it has one, to its process
    otherwise (see the module documentation).

    Returns:
        bool: whether there was still a process to receive it.
    """
    process = getattr(job, "process", None)
    if process is None or process.poll() is not None:
        return False
    try:
        group = _group_of(job)
        if group is not None:
            os.killpg(group, sig)
        else:
            os.kill(process.pid, sig)
    except ProcessLookupError:
        return False
    return True


def pause(job):
    """Suspend `job`. POSIX only: Windows has no equivalent of SIGSTOP."""
    if WINDOWS:
        return False
    return send(job, signal.SIGSTOP)


def resume(job):
    """Resume a job suspended by :func:`pause`. POSIX only."""
    if WINDOWS:
        return False
    return send(job, signal.SIGCONT)


######################################
# Stopping
######################################

def request_stop(job, timeout=TERMINATE_TIMEOUT_S):
    """
    Ask `job` to stop, without waiting for it to.

    Under POSIX this is SIGTERM *then* SIGCONT, in that order: a paused process
    does not act on SIGTERM until it runs again, and resuming it first would
    let it run a slice of work before the TERM arrives. With the TERM already
    pending, it dies as soon as it wakes up.

    The job is given `timeout` seconds; :func:`reap` kills it after that.

    Returns:
        bool: whether there was still a process to stop.
    """
    process = getattr(job, "process", None)
    if process is None or process.poll() is not None:
        return False
    if WINDOWS:
        try:
            if getattr(job, "own_group", False):
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
        except OSError:
            return False
    else:
        if not send(job, signal.SIGTERM):
            return False
        send(job, signal.SIGCONT)
    job._stop_deadline = time.time() + float(timeout)
    return True


def kill(job):
    """Kill `job` outright: SIGKILL, or a forced end of its tree under Windows."""
    process = getattr(job, "process", None)
    if process is None or process.poll() is not None:
        return False
    if WINDOWS:
        if getattr(job, "own_group", False):
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            try:
                process.kill()
            except OSError:
                return False
        return True
    return send(job, signal.SIGKILL)


def reap(jobs, now=None):
    """
    Collect the jobs of `jobs` that were asked to stop and have exited, and kill
    those that outlived their deadline.

    Called by the scheduler on every tick, holding its lock: it never waits.
    poll() is what collects an exited process -- without it a stopped job stays
    a zombie for as long as the session lives.

    Returns:
        list: the jobs still on their way out, to pass again on the next tick.
    """
    now = time.time() if now is None else now
    pending = []
    for job in jobs:
        process = getattr(job, "process", None)
        if process is None or process.poll() is not None:
            continue
        deadline = getattr(job, "_stop_deadline", None)
        if deadline is not None and now >= deadline:
            kill(job)
            # Not checked again before the next tick: SIGKILL is not instant.
            job._stop_deadline = None
        pending.append(job)
    return pending


def terminate(jobs, timeout=TERMINATE_TIMEOUT_S):
    """
    Stop `jobs` and wait for them: ask each to stop, give them `timeout` seconds
    in all, then kill those still there and wait for them too.

    It blocks for up to `timeout` seconds and more: the caller must not hold
    the scheduler's lock (see the module documentation).
    """
    jobs = [job for job in jobs if getattr(job, "process", None) is not None]
    for job in jobs:
        request_stop(job, timeout=timeout)
    deadline = time.time() + float(timeout)
    for job in jobs:
        try:
            job.process.wait(timeout=max(0.0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            pass
    for job in jobs:
        if kill(job):
            try:
                job.process.wait(timeout=float(timeout))
            except subprocess.TimeoutExpired:
                pass
