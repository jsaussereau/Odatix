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

"""Utilities to control the background ParallelJob daemon."""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

from odatix.lib.parallel_job_handler.auth import (
    SCOPE_CONTROL,
    SCOPE_READ,
    TOKEN_ENV_VAR,
    secure_makedirs,
)
from odatix.lib.parallel_job_handler import diagnostics
from odatix.lib.parallel_job_handler.serialization import job_to_payload
from odatix.lib.parallel_job_handler.transport import (
    TRANSPORT_TCP,
    TRANSPORT_UNIX,
    AuthError,
    Endpoint,
)
from odatix.lib.parallel_job_handler.utils import get_elapsed_time_str
import odatix.lib.hard_settings as hard_settings
import odatix.lib.printc as printc

DEFAULT_HOST = hard_settings.daemon_default_host
DEFAULT_PORT = hard_settings.daemon_default_port

DAEMON_STATE_DIR = hard_settings.daemon_state_dirname
DAEMON_STATE_FILE = hard_settings.daemon_state_file
DAEMON_LOG_FILE = hard_settings.daemon_log_file
DAEMON_STATE_PREFIX = hard_settings.daemon_state_prefix
DAEMON_STATE_SUFFIX = hard_settings.daemon_state_suffix
DAEMON_LOG_PREFIX = hard_settings.daemon_log_prefix
DAEMON_LOG_SUFFIX = hard_settings.daemon_log_suffix

#: How long a session is given to answer a job listing. Short by default: the
#: monitor and the GUI ask often and would rather show a session as busy than
#: freeze on it. Something that acts on the answer -- an exploration deciding
#: whether its jobs are done -- passes a longer one, because a session carrying
#: a long batch answers between two scheduling ticks and reading the silence as
#: "the jobs are gone" is worse than waiting (see daemon_jobs_report).
JOBS_QUERY_TIMEOUT = 1.0

#: What a caller that acts on the answer should wait, in seconds.
JOBS_QUERY_TIMEOUT_BLOCKING = 30.0


class DaemonControlError(RuntimeError):
    pass

class MultipleDaemonsError(DaemonControlError):
    def __init__(self, daemons=None, message=None):
        normalized = []
        if isinstance(daemons, list):
            normalized = daemons
        elif isinstance(daemons, dict):
            normalized = [daemons]

        if message is None:
            message = "Multiple daemon sessions found, use -S to select one"
            if normalized:
                hints = ", ".join(_format_session_hint(d) for d in normalized)
                message = message + ": " + hints

        super().__init__(message)
        self.daemons = normalized

def detect_workspace_root(start_path=None):
    current = os.path.realpath(start_path or os.getcwd())
    if os.path.isfile(current):
        current = os.path.dirname(current)

    while True:
        if os.path.isfile(os.path.join(current, "odatix.yml")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return os.path.realpath(start_path or os.getcwd())
        current = parent


def _normalize_session_name(session_name, default_name=DEFAULT_HOST):
    if session_name is None:
        return str(default_name)
    session_name = str(session_name).strip()
    if session_name == "":
        return str(default_name)
    return session_name


def _generate_default_session_name(host=DEFAULT_HOST):
    host = str(host or DEFAULT_HOST).strip() or DEFAULT_HOST

    # Try to determine a controlling TTY (stdin/out/err), fallback to env or 'no_tty'.
    tty_slug = None
    for fd in (0, 1, 2):
        try:
            tty_path = os.ttyname(fd)
            if tty_path:
                # Strip leading /dev/ to get a compact tty representation (e.g. pts/2)
                if tty_path.startswith("/dev/"):
                    tty_path = tty_path[len("/dev/"):]
                tty_slug = _session_slug(tty_path)
                if tty_slug:
                    break
        except Exception:
            continue

    if not tty_slug:
        env_tty = os.environ.get("SSH_TTY") or os.environ.get("TTY") or None
        if env_tty:
            if env_tty.startswith("/dev/"):
                env_tty = env_tty[len("/dev/"):]
            tty_slug = _session_slug(env_tty)

    if not tty_slug:
        tty_slug = "no_tty"

    if host == "127.0.0.1" or host == "localhost":
        try:
            host = os.uname().nodename
        except Exception:
            pass

    host_slug = _session_slug(host) or DEFAULT_HOST
    return "{}.{}".format(tty_slug, host_slug)


def _unique_default_session_name(host=DEFAULT_HOST, active_daemons=None):
    """
    Default session name for a new session, made unique against the sessions
    already running.

    The default name is derived from the controlling tty, which distinguishes
    concurrent CLI runs. Callers without a tty (the GUI server, a service, a
    cron job) all get the same "no_tty" name, so without this every session they
    launch would reuse the same state file and replace the previous one.
    """
    base_name = _generate_default_session_name(host=host)
    taken = {_session_name_from_state(state) for state in (active_daemons or [])}
    if base_name not in taken:
        return base_name
    suffix = 2
    while "{}.{}".format(base_name, suffix) in taken:
        suffix += 1
    return "{}.{}".format(base_name, suffix)


def _session_slug(session_name):
    session_name = str(session_name or "").strip()
    if session_name == "":
        return None
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_name).strip("._")
    return slug or None


def _state_filename_for_session(session_name):
    slug = _session_slug(session_name)
    if slug is None:
        return DAEMON_STATE_FILE
    return DAEMON_STATE_PREFIX + slug + DAEMON_STATE_SUFFIX


def _log_filename_for_session(session_name):
    slug = _session_slug(session_name)
    if slug is None:
        return DAEMON_LOG_FILE
    return DAEMON_LOG_PREFIX + slug + DAEMON_LOG_SUFFIX


def get_daemon_paths(workspace_root=None, session_name=None):
    root = detect_workspace_root(workspace_root)
    state_dir = os.path.join(root, DAEMON_STATE_DIR)
    return {
        "workspace_root": root,
        "state_dir": state_dir,
        "state_file": os.path.join(state_dir, _state_filename_for_session(session_name)),
        "log_file": os.path.join(state_dir, _log_filename_for_session(session_name)),
    }


def _read_json_file(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def load_daemon_state(workspace_root=None, session_name=None):
    paths = get_daemon_paths(workspace_root, session_name=session_name)
    return _read_json_file(paths["state_file"])


def _session_name_from_state(state):
    if not isinstance(state, dict):
        return ""

    session_name = state.get("session_name")
    if isinstance(session_name, str) and session_name.strip() != "":
        return session_name.strip()

    session_id = state.get("session_id")
    if isinstance(session_id, str) and "." in session_id:
        return session_id.split(".", 1)[1]

    return str(state.get("host", DEFAULT_HOST))


def _session_id_from_state(state):
    if not isinstance(state, dict):
        return ""

    session_id = state.get("session_id")
    if isinstance(session_id, str) and session_id.strip() != "":
        return session_id.strip()

    pid = state.get("pid")
    session_name = _session_name_from_state(state)
    if pid is not None:
        try:
            return "{}.{}".format(int(pid), session_name)
        except Exception:
            return "{}.{}".format(str(pid), session_name)
    return session_name


def _decorate_session_fields(state):
    if not isinstance(state, dict):
        return state
    state["session_name"] = _session_name_from_state(state)
    state["session_id"] = _session_id_from_state(state)
    state["address"] = _state_address(state)
    return state


def endpoint_for_state(state, scope=SCOPE_CONTROL):
    """The endpoint to talk to a session described by ``state``.

    The session token lives in the state file, which only its owner can read:
    being able to build this endpoint is exactly the right to use the session.
    """
    return Endpoint.from_state(state, scope=scope)


def _api_request(state, method, path, payload=None, timeout=1.0, scope=SCOPE_CONTROL):
    return endpoint_for_state(state, scope=scope).request(
        method, path, payload=payload, timeout=timeout
    )


def _state_address(state):
    """Human-readable address of a session, whatever its transport."""
    if not isinstance(state, dict):
        return ""
    socket_path = state.get("socket_path") or state.get("socket")
    if socket_path and state.get("transport", TRANSPORT_UNIX) == TRANSPORT_UNIX:
        return "unix:{}".format(socket_path)
    host = state.get("host")
    port = state.get("port")
    if host is None and port is None:
        return ""
    return "{}:{}".format(host or DEFAULT_HOST, int(port or DEFAULT_PORT))


def daemon_is_alive(state, timeout=0.6):
    if not isinstance(state, dict):
        return False
    try:
        _api_request(state, "GET", "/status?logs_job_id=-1", timeout=float(timeout), scope=SCOPE_READ)
        return True
    except AuthError:
        # It answered, so it is alive; we simply hold no valid token for it.
        # Reporting it dead here would have callers start a second daemon on
        # top of a perfectly running one.
        return True
    except Exception:
        return False


def _delete_state_file(state_file):
    try:
        if os.path.isfile(state_file):
            os.remove(state_file)
    except Exception:
        pass


def _delete_log_file(log_file):
    try:
        if os.path.isfile(log_file):
            os.remove(log_file)
    except Exception:
        pass


def _iter_state_files(paths):
    state_dir = paths.get("state_dir")
    if not state_dir or not os.path.isdir(state_dir):
        return []

    all_paths = []
    for name in os.listdir(state_dir):
        if not name.endswith(DAEMON_STATE_SUFFIX):
            continue
        if name != DAEMON_STATE_FILE and not name.startswith(DAEMON_STATE_PREFIX):
            continue
        all_paths.append(os.path.join(state_dir, name))
    all_paths.sort()
    return all_paths


def _state_key(state):
    if not isinstance(state, dict):
        return ("", "", "")
    try:
        pid = int(state.get("pid", 0))
    except Exception:
        pid = 0
    return (pid, _state_address(state))


def _format_session_hint(daemon):
    session_id = str(daemon.get("session_id", "?"))
    address = _state_address(daemon)
    if address == "":
        return session_id
    return "{} ({})".format(session_id, address)


def _selector_tokens(daemon):
    tokens = []

    session_id = str(daemon.get("session_id", "")).strip()
    if session_id:
        tokens.append(session_id)
        if "." in session_id:
            tokens.append(session_id.split(".", 1)[1])

    session_name = str(daemon.get("session_name", "")).strip()
    if session_name:
        tokens.append(session_name)

    pid = daemon.get("pid")
    if pid is not None:
        tokens.append(str(pid))

    dedup = []
    seen = set()
    for token in tokens:
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        dedup.append(key)
    return dedup


def _filter_by_workspace(daemons, workspace_root=None):
    root = os.path.realpath(detect_workspace_root(workspace_root))
    filtered = []
    for daemon in daemons:
        daemon_root = os.path.realpath(str(daemon.get("workspace_root", root)))
        if daemon_root == root:
            filtered.append(daemon)
    return filtered, root


def _resolve_session_selector(daemons, selector, allow_missing=False):
    selector = str(selector or "").strip().lower()
    if selector == "":
        if allow_missing:
            return None
        if len(daemons) == 1:
            return daemons[0]
        if len(daemons) == 0:
            raise DaemonControlError("No session found")
        raise MultipleDaemonsError(daemons)

    exact = [d for d in daemons if selector in _selector_tokens(d)]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise MultipleDaemonsError(exact)

    prefix = [d for d in daemons if any(tok.startswith(selector) for tok in _selector_tokens(d))]
    if len(prefix) == 1:
        return prefix[0]
    if len(prefix) > 1:
        raise MultipleDaemonsError(prefix)

    if allow_missing:
        return None

    raise DaemonControlError("No session matches '{}'".format(selector))


def _daemon_is_alive_with_retries(state, attempts=3, timeout=0.6, backoff=0.3):
    """
    Like :func:`daemon_is_alive`, but does not take one slow reply as proof of
    death.

    A daemon that has been running a while can be briefly slow to answer --
    host under load, an event loop hiccup -- and a single 0.6s timeout is not
    enough to tell that from a daemon that is actually gone. Treating it as
    gone anyway spawns a second daemon under the very session name the first
    one is still using (see :func:`ensure_daemon_running`), which orphans the
    first one along with whatever it is running.
    """
    for attempt in range(int(attempts)):
        if daemon_is_alive(state, timeout=timeout):
            return True
        if attempt < attempts - 1:
            time.sleep(backoff)
    return False


def _daemon_is_alive_patiently(state, total_timeout=60.0, timeout=0.6, max_timeout=5.0, backoff=1.0):
    """
    The long version of :func:`_daemon_is_alive_with_retries`, for when giving
    up has real consequences.

    A daemon busy with a large wave of jobs (a synthesis batch finishing, logs
    being flushed) can stay unresponsive for tens of seconds without being in
    any trouble. When the alternative to waiting is refusing to enqueue -- or
    worse, replacing a live session -- it is always cheaper to keep asking, so
    this keeps polling for `total_timeout` seconds with a request timeout that
    grows up to `max_timeout`.
    """
    deadline = time.time() + float(total_timeout)
    current = float(timeout)
    while True:
        if daemon_is_alive(state, timeout=current):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(float(backoff))
        current = min(float(max_timeout), current * 1.5)


def _daemon_is_alive_for_listing(state):
    """Is this session alive, judged patiently enough to survive an export?

    A job completing makes the handler export its results with the scheduler
    lock held, which keeps `/status` silent for seconds. Discovery must outlast
    that: a session dropped from the listing reads as "no session found", and
    the DSE driver waiting on its own batch then has nothing left to ask.
    """
    return _daemon_is_alive_with_retries(state, attempts=4, timeout=1.5, backoff=0.4)


def _pid_is_running(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # No cheap liveness check without extra dependencies here; callers on
        # Windows fall back to trusting the HTTP alive-check alone.
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists, just not ours to signal.
        return True
    except Exception:
        return False
    return True


def _pid_claiming_session(paths, session_name):
    """
    The pid of a still-running process that owns this session's state file, if
    any -- regardless of whether it currently answers HTTP.

    Used before replacing a session whose daemon failed its alive-check: a
    process match here means the daemon is (at worst) stuck, not dead, and
    starting a second one under the same name would silently orphan it.
    """
    target_state_file = os.path.realpath(os.path.expanduser(str(paths.get("state_file") or "")))
    target_slug = _session_slug(session_name)

    for candidate in _iter_system_daemon_candidates() or []:
        candidate_state_file = candidate.get("state_file")
        candidate_state_file = (
            os.path.realpath(os.path.expanduser(str(candidate_state_file)))
            if candidate_state_file else ""
        )
        candidate_slug = _session_slug(candidate.get("session_name"))

        same_state_file = target_state_file != "" and candidate_state_file == target_state_file
        same_session_name = target_slug is not None and candidate_slug == target_slug
        if not (same_state_file or same_session_name):
            continue

        pid = candidate.get("pid")
        if _pid_is_running(pid):
            return pid

    return None


def _spawn_daemon(
    paths,
    host,
    port,
    jobs,
    logsize,
    session_name=None,
    daemon_log_enabled=None,
    transport=None,
    expose=False,
):
    # 0700: the state file inside holds the session token, which is the right
    # to run commands as this user.
    secure_makedirs(paths["state_dir"], 0o700)
    session_name = _normalize_session_name(session_name, default_name=host)
    daemon_log_enabled = (
        hard_settings.daemon_log_enabled_default
        if daemon_log_enabled is None
        else bool(daemon_log_enabled)
    )

    transport = str(transport or "auto")

    command = [
        sys.executable,
        "-m",
        "odatix.lib.parallel_job_handler.daemon_server",
        "--state-file",
        paths["state_file"],
        "--transport",
        transport,
        "--host",
        str(host),
        "--port",
        str(int(port)),
        "--session-name",
        str(session_name),
        "--jobs",
        str(max(1, int(jobs))),
        "--logsize",
        str(int(logsize)),
    ]

    if expose:
        command.append("--expose")

    env = os.environ.copy()
    sources_dir = os.path.join(paths["workspace_root"], "sources")
    if os.path.isdir(os.path.join(sources_dir, "odatix")):
        previous = env.get("PYTHONPATH", "")
        if previous:
            env["PYTHONPATH"] = sources_dir + os.pathsep + previous
        else:
            env["PYTHONPATH"] = sources_dir

    popen_kwargs = {
        "stdin": subprocess.DEVNULL,
        "cwd": paths["workspace_root"],
        "close_fds": True,
        "env": env,
    }

    if sys.platform == "win32":
        detached = getattr(subprocess, "DETACHED_PROCESS", 0)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        popen_kwargs["creationflags"] = detached | new_group
    else:
        popen_kwargs["start_new_session"] = True

    if daemon_log_enabled:
        with open(paths["log_file"], "ab") as log_file:
            popen_kwargs["stdout"] = log_file
            popen_kwargs["stderr"] = log_file
            subprocess.Popen(command, **popen_kwargs)
        return

    _delete_log_file(paths["log_file"])
    popen_kwargs["stdout"] = subprocess.DEVNULL
    popen_kwargs["stderr"] = subprocess.DEVNULL
    subprocess.Popen(command, **popen_kwargs)


def ensure_daemon_running(
    workspace_root=None,
    host=DEFAULT_HOST,
    port=DEFAULT_PORT,
    jobs=4,
    logsize=200,
    session=None,
    daemon_log_enabled=None,
    startup_timeout=15.0,
    create=True,
    stuck_timeout=60.0,
    transport=None,
    expose=False,
):
    """
    The daemon for `session`, started if there is none.

    Args:
        create (bool): whether a missing session may be started. Callers that
            are themselves running *inside* the session they enqueue into (an
            exploration adding batches to its own, see odatix.dse) must pass
            False: for them a missing session is an error to report, never a
            reason to start a second one somewhere else.
        stuck_timeout (float): how long to keep asking a session that owns a
            live process but is not answering, before giving up on it.
        transport (str): "unix", "tcp" or None for the platform default (see
            daemon_server.resolve_transport).
        expose (bool): let the session bind a non-loopback TCP address. Off by
            default: a session in reach of the network is a decision, not a
            side effect.
    """
    workspace_root = detect_workspace_root(workspace_root)
    session_selector = str(session).strip() if session is not None else None

    active_daemons = list_daemons(workspace_root=workspace_root)
    active_daemons, _workspace_root = _filter_by_workspace(active_daemons, workspace_root=workspace_root)

    if session_selector:
        matched = _resolve_session_selector(active_daemons, session_selector, allow_missing=True)
        if matched is not None:
            if _daemon_is_alive_with_retries(matched):
                return matched

            session_name = _normalize_session_name(session_selector, default_name=host)
            paths = get_daemon_paths(workspace_root, session_name=session_name)

            # The alive-check failed, but do not take that as proof the daemon
            # is gone: a process still claiming this exact session at the OS
            # level means it is (at worst) stuck, not dead. Spawning a
            # replacement here would give it a second daemon under its own
            # name, silently orphaning the first one and whatever it is
            # running (see the "dse-<pid>" duplicate-session incident).
            stuck_pid = _pid_claiming_session(paths, session_name)
            if stuck_pid is not None:
                # Still owned by a live process: it is busy or stuck, not gone.
                # Keep asking -- a daemon in the middle of a heavy wave of jobs
                # can go quiet for a while and come back perfectly fine.
                if _daemon_is_alive_patiently(matched, total_timeout=stuck_timeout):
                    return matched
                raise DaemonControlError(
                    "Daemon session '{0}' is not responding after {2:.0f}s, but its process "
                    "(pid {1}) is still running. Stop it explicitly (kill -9 {1}) before "
                    "starting a new one.".format(session_name, stuck_pid, float(stuck_timeout))
                )
            if not create:
                raise DaemonControlError(
                    "Daemon session '{}' is gone. Not starting a new one: this run is part "
                    "of that session.".format(session_name)
                )
        else:
            session_name = _normalize_session_name(session_selector, default_name=host)
            paths = get_daemon_paths(workspace_root, session_name=session_name)

            # list_daemons() scans /proc and can transiently miss an existing
            # daemon under load, coming back with no match even though the
            # session is very much alive. Trusting that absence here would
            # spawn a second daemon under the exact same session name -- the
            # "dse-<pid>" duplicate-session incident again, just reached from
            # the listing side instead of the alive-check side. Read this
            # session's own state file directly before assuming there is
            # nothing to find.
            state = _read_json_file(paths["state_file"])
            if state and _daemon_is_alive_with_retries(state):
                state = dict(state)
                state["workspace_root"] = workspace_root
                state["state_file"] = paths["state_file"]
                _decorate_session_fields(state)
                return state

            stuck_pid = _pid_claiming_session(paths, session_name)
            if stuck_pid is not None:
                if state and _daemon_is_alive_patiently(state, total_timeout=stuck_timeout):
                    state = dict(state)
                    state["workspace_root"] = workspace_root
                    state["state_file"] = paths["state_file"]
                    _decorate_session_fields(state)
                    return state
                raise DaemonControlError(
                    "Daemon session '{0}' is not responding after {2:.0f}s, but its process "
                    "(pid {1}) is still running. Stop it explicitly (kill -9 {1}) before "
                    "starting a new one.".format(session_name, stuck_pid, float(stuck_timeout))
                )
            if not create:
                raise DaemonControlError(
                    "Daemon session '{}' is gone. Not starting a new one: this run is part "
                    "of that session.".format(session_name)
                )
    else:
        # By default, launching jobs creates a fresh daemon session.
        # Existing sessions are reused only when an explicit selector is given.
        session_name = _unique_default_session_name(host=host, active_daemons=active_daemons)
        paths = get_daemon_paths(workspace_root, session_name=session_name)

    _delete_state_file(paths["state_file"])
    _spawn_daemon(
        paths,
        host=host,
        port=port,
        jobs=jobs,
        logsize=logsize,
        session_name=session_name,
        daemon_log_enabled=daemon_log_enabled,
        transport=transport,
        expose=expose,
    )

    deadline = time.time() + float(startup_timeout)
    while time.time() < deadline:
        state = _read_json_file(paths["state_file"])
        if state is not None and daemon_is_alive(state):
            state = dict(state)
            state["workspace_root"] = workspace_root
            state["state_file"] = paths["state_file"]
            _decorate_session_fields(state)
            return state
        time.sleep(0.15)

    daemon_log_enabled = (
        hard_settings.daemon_log_enabled_default
        if daemon_log_enabled is None
        else bool(daemon_log_enabled)
    )
    if daemon_log_enabled:
        raise DaemonControlError(
            "Could not start Odatix daemon (see log: {})".format(paths["log_file"])
        )
    raise DaemonControlError("Could not start Odatix daemon")


def enqueue_parallel_jobs(parallel_jobs, workspace_root=None, session=None, configure=True, create=None):
    """
    Hand jobs to a daemon session, starting one when there is none.

    Args:
        parallel_jobs (ParallelJobHandler): the jobs to enqueue, and how the run
            that built them wants the daemon configured.
        workspace_root (str): the workspace they belong to.
        session (str): the session to enqueue into. A new one is started when
            none is named.
        configure (bool): also apply how this run wants the daemon to behave --
            how many jobs at once, whether the monitor closes by itself. Adding
            jobs to a session and telling it how to run them are two different
            things: something enqueueing *into* a session it is already part of
            (an exploration adding a batch to its own, see odatix.dse) must not
            reconfigure it under everything else that is running there.
        create (bool): whether a missing session may be started. Defaults to
            `configure`, since a run that is part of the session it enqueues
            into is exactly the run that must never start a second one: if its
            own session is gone, that is an error, not a reason to spawn.
    """
    if create is None:
        create = bool(configure)
    job_list = list(getattr(parallel_jobs, "job_list", []) or [])

    format_yaml = getattr(parallel_jobs, "format_yaml", None)
    if format_yaml in (None, ""):
        formatter = getattr(parallel_jobs, "formatter", None)
        format_yaml = getattr(formatter, "filename", None) if formatter is not None else None

    state = ensure_daemon_running(
        workspace_root=workspace_root,
        jobs=getattr(parallel_jobs, "nb_jobs", 4),
        logsize=getattr(parallel_jobs, "log_size_limit", 200),
        session=session,
        daemon_log_enabled=getattr(parallel_jobs, "daemon_log_enabled", None),
        create=create,
    )

    payload = {"jobs": [job_to_payload(job) for job in job_list]}
    if configure:
        payload["options"] = {
            "nb_jobs": int(getattr(parallel_jobs, "nb_jobs", 4)),
            "process_group": bool(getattr(parallel_jobs, "process_group", True)),
            "auto_exit": bool(getattr(parallel_jobs, "auto_exit", False)),
            "log_size_limit": int(getattr(parallel_jobs, "log_size_limit", 200)),
            # Empty string means "disable formatter" (None means "leave unchanged").
            "format_yaml": str(format_yaml) if format_yaml not in (None, "") else "",
        }

    response = _api_request(
        state,
        "POST",
        "/jobs/enqueue",
        payload=payload,
        # Generous on purpose: a daemon busy with a wave of jobs can take a
        # while to get to this, and dropping the batch on a slow reply loses
        # real work.
        timeout=15.0,
    )
    return state, response


def explicit_endpoint_state(host=None, port=None, token=None):
    """A state dict for an endpoint given by hand (--host/--port).

    No state file is involved, so the token has to come from the caller or
    from the environment: without one the session will refuse every call.
    """
    return {
        "transport": TRANSPORT_TCP,
        "host": str(host or DEFAULT_HOST),
        "port": int(port or DEFAULT_PORT),
        "token": str(token or os.environ.get(TOKEN_ENV_VAR, "")),
    }


def _resolve_state_for_attach_or_stop(workspace_root=None, host=None, port=None, session=None, token=None):
    if host is not None or port is not None:
        state = explicit_endpoint_state(host=host, port=port, token=token)
        _decorate_session_fields(state)
        return state

    all_daemons = list_daemons(workspace_root=workspace_root)
    workspace_daemons, workspace_root = _filter_by_workspace(all_daemons, workspace_root=workspace_root)

    selector = str(session).strip() if session is not None else ""
    if selector != "":
        return _resolve_session_selector(all_daemons, selector, allow_missing=False)

    paths = get_daemon_paths(workspace_root)
    state = _read_json_file(paths["state_file"])
    if state is not None and daemon_is_alive(state):
        state = dict(state)
        state["workspace_root"] = workspace_root
        state["state_file"] = paths["state_file"]
        _decorate_session_fields(state)
        return state

    if len(workspace_daemons) == 1:
        return workspace_daemons[0]

    if len(workspace_daemons) > 1:
        raise MultipleDaemonsError(all_daemons)

    if len(all_daemons) == 1:
        return all_daemons[0]

    if len(all_daemons) > 1:
        raise MultipleDaemonsError(all_daemons)

    raise DaemonControlError("No session found")


def attach_monitor(
    workspace_root=None, host=None, port=None, session=None, auto_exit=False, token=None, remote=None
):
    from odatix.lib.parallel_job_handler.daemon_monitor import run_monitor

    if remote is not None:
        from odatix.lib.parallel_job_handler.remote import open_remote_endpoint

        tunnel, endpoint, _state = open_remote_endpoint(remote, session=session)
        try:
            return run_monitor(endpoint=endpoint, auto_exit=bool(auto_exit))
        finally:
            tunnel.close()

    state = _resolve_state_for_attach_or_stop(
        workspace_root=workspace_root, host=host, port=port, session=session, token=token
    )
    if not daemon_is_alive(state):
        raise DaemonControlError("Daemon is not running")

    return run_monitor(endpoint=endpoint_for_state(state), auto_exit=bool(auto_exit))


def _terminate_pid(pid):
    pid = int(pid)
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def _delete_state_files_for_daemon(paths, target_state):
    target_state_file = target_state.get("state_file") if isinstance(target_state, dict) else None
    if isinstance(target_state_file, str) and target_state_file.strip() != "":
        _delete_state_file(target_state_file)

    if isinstance(target_state, dict):
        session_name = _session_name_from_state(target_state)
        if session_name != "":
            _delete_log_file(os.path.join(paths["state_dir"], _log_filename_for_session(session_name)))

    target_key = _state_key(target_state)
    # Compared as a full address rather than host/port: unix sessions carry no
    # port at all, and defaulting them all to the same host:port would make
    # every session in the directory look like the one being stopped.
    target_address = _state_address(target_state) if isinstance(target_state, dict) else ""

    for state_file in _iter_state_files(paths):
        loaded = _read_json_file(state_file)
        loaded_key = _state_key(loaded)
        loaded_address = _state_address(loaded) if isinstance(loaded, dict) else ""
        same_endpoint = target_address != "" and loaded_address == target_address
        if loaded_key == target_key or same_endpoint:
            session_name = _session_name_from_state(loaded)
            if session_name != "":
                _delete_log_file(os.path.join(paths["state_dir"], _log_filename_for_session(session_name)))
            _delete_state_file(state_file)


def _cleanup_workspace_daemon_dir_if_empty(workspace_root):
    workspace_root = detect_workspace_root(workspace_root)
    workspace_daemons, _ = _filter_by_workspace(
        list_daemons(workspace_root=workspace_root),
        workspace_root=workspace_root,
    )
    if len(workspace_daemons) > 0:
        return

    paths = get_daemon_paths(workspace_root)
    state_dir = paths.get("state_dir")
    if not state_dir or not os.path.isdir(state_dir):
        return

    try:
        shutil.rmtree(state_dir)
    except Exception:
        pass


def _stop_daemon_from_state(state, workspace_root):
    cleanup_workspace_root = state.get("workspace_root", workspace_root) if isinstance(state, dict) else workspace_root
    paths = get_daemon_paths(cleanup_workspace_root)

    try:
        _api_request(state, "POST", "/shutdown", payload={}, timeout=1.0)
    except Exception:
        pass

    deadline = time.time() + 3.0
    while time.time() < deadline:
        if not daemon_is_alive(state, timeout=0.3):
            _delete_state_files_for_daemon(paths, state)
            _cleanup_workspace_daemon_dir_if_empty(cleanup_workspace_root)
            return True
        time.sleep(0.1)

    pid = state.get("pid")
    if pid is not None:
        try:
            _terminate_pid(pid)
        except Exception:
            pass

    deadline = time.time() + 2.0
    while time.time() < deadline:
        if not daemon_is_alive(state, timeout=0.3):
            break
        time.sleep(0.1)

    _delete_state_files_for_daemon(paths, state)
    stopped = not daemon_is_alive(state, timeout=0.3)
    _cleanup_workspace_daemon_dir_if_empty(cleanup_workspace_root)
    return stopped


def stop_daemon(workspace_root=None, host=None, port=None, session=None, token=None, remote=None):
    if remote is not None:
        return stop_remote_daemon(remote, session=session)

    workspace_root = detect_workspace_root(workspace_root)
    state = _resolve_state_for_attach_or_stop(
        workspace_root=workspace_root,
        host=host,
        port=port,
        session=session,
        token=token,
    )
    return _stop_daemon_from_state(state, workspace_root)


def stop_remote_daemon(remote, session=None):
    """Stop a session on another machine, through an SSH tunnel.

    The shutdown goes through the same authenticated API as a local stop: the
    tunnel only decides how the request travels, never what it is allowed to
    do.
    """
    from odatix.lib.parallel_job_handler.remote import open_remote_endpoint

    tunnel, endpoint, _state = open_remote_endpoint(remote, session=session)
    try:
        endpoint.post("/shutdown", payload={}, timeout=5.0)
        return True
    finally:
        tunnel.close()


def stop_all_daemons(workspace_root=None, host=None, port=None, token=None):
    workspace_root = detect_workspace_root(workspace_root)
    daemons = list_daemons(workspace_root=workspace_root, host=host, port=port, token=token)

    if len(daemons) == 0:
        _cleanup_workspace_daemon_dir_if_empty(workspace_root)
        return {"total": 0, "stopped": 0, "failed": []}

    stopped = 0
    failed = []
    for daemon in daemons:
        try:
            if _stop_daemon_from_state(daemon, workspace_root):
                stopped += 1
            else:
                failed.append(daemon)
        except Exception:
            failed.append(daemon)

    _cleanup_workspace_daemon_dir_if_empty(workspace_root)

    return {
        "total": len(daemons),
        "stopped": stopped,
        "failed": failed,
    }


def daemon_endpoint(workspace_root=None, session_name=None):
    state = load_daemon_state(workspace_root, session_name=session_name)
    if state is None:
        return None
    return _state_address(state)


SECRET_STATE_FIELDS = ("token", "read_token")


def public_state(state):
    """A session descriptor with its secrets removed.

    Anything leaving this process without a private channel -- a browser store,
    a log line, a printed table -- must go through here.
    """
    if not isinstance(state, dict):
        return state
    return dict((k, v) for k, v in state.items() if k not in SECRET_STATE_FIELDS)


def daemons_to_json(daemons, include_secrets=False, indent=2):
    """Serialize a session list.

    ``include_secrets`` keeps the tokens in, which only makes sense for a
    consumer reached through a private channel (``odatix ls --json`` read over
    SSH by a remote client).
    """
    sessions = [d if include_secrets else public_state(d) for d in (daemons or [])]
    return json.dumps({"sessions": sessions}, indent=indent, default=str)


def _extract_cli_option(tokens, option):
    prefix = option + "="
    for index, token in enumerate(tokens):
        if token == option and index + 1 < len(tokens):
            return tokens[index + 1]
        if token.startswith(prefix):
            return token[len(prefix):]
    return None


def _is_daemon_server_process(tokens):
    for index, token in enumerate(tokens):
        if token == "-m" and index + 1 < len(tokens):
            if tokens[index + 1] == "odatix.lib.parallel_job_handler.daemon_server":
                return True
        if token.endswith("/daemon_server.py") or token.endswith("\\daemon_server.py"):
            return True
    return False


def _workspace_root_from_state_file(state_file):
    if not state_file:
        return None

    state_file = os.path.realpath(os.path.expanduser(str(state_file)))
    state_dir = os.path.dirname(state_file)
    if os.path.basename(state_dir) == DAEMON_STATE_DIR:
        return os.path.dirname(state_dir)

    return None


def _iter_system_daemon_candidates():
    proc_dir = "/proc"
    if not os.path.isdir(proc_dir):
        return

    for entry in os.listdir(proc_dir):
        if not entry.isdigit():
            continue

        pid = int(entry)
        cmdline_path = os.path.join(proc_dir, entry, "cmdline")

        try:
            with open(cmdline_path, "rb") as f:
                raw = f.read()
        except Exception:
            continue

        if not raw:
            continue

        tokens = [part.decode("utf-8", errors="ignore") for part in raw.split(b"\0") if part]
        if not _is_daemon_server_process(tokens):
            continue

        state_file = _extract_cli_option(tokens, "--state-file")
        host = _extract_cli_option(tokens, "--host")
        port = _extract_cli_option(tokens, "--port")
        session_name = _extract_cli_option(tokens, "--session-name")
        transport = _extract_cli_option(tokens, "--transport")

        try:
            port = int(port) if port is not None else None
        except Exception:
            port = None

        # A session on a unix socket has no address of its own here: --host
        # and --port were only the *requested* fallback, and passing them on
        # would have callers dial a TCP endpoint nothing listens on.
        if transport == TRANSPORT_UNIX:
            host = None
            port = None

        workspace_root = _workspace_root_from_state_file(state_file)
        if workspace_root is None:
            try:
                workspace_root = os.path.realpath(os.path.join(proc_dir, entry, "cwd"))
            except Exception:
                workspace_root = None

        yield {
            "pid": pid,
            "host": host,
            "port": port,
            "session_name": session_name,
            "state_file": state_file,
            "workspace_root": workspace_root,
        }


def _daemon_sort_key(daemon):
    session_id = str(daemon.get("session_id", ""))
    workspace_root = str(daemon.get("workspace_root", ""))
    return (workspace_root, session_id, _state_address(daemon))


def _daemon_uptime_str(state):
    started_at = state.get("started_at") if isinstance(state, dict) else None
    try:
        start_time = float(started_at)
    except Exception:
        return ""
    if start_time <= 0:
        return ""
    return get_elapsed_time_str(start_time, None)


def _filter_daemons_by_session_selector(daemons, session_selector):
    selector = str(session_selector or "").strip().lower()
    if selector == "":
        return list(daemons)

    exact = [d for d in daemons if selector in _selector_tokens(d)]
    if exact:
        return exact

    prefix = [d for d in daemons if any(tok.startswith(selector) for tok in _selector_tokens(d))]
    if prefix:
        return prefix

    return []


def list_daemons(workspace_root=None, host=None, port=None, session=None, token=None, remote=None):
    """Return a list of active daemon descriptors.

    By default, this inspects running daemon processes on the system.
    If host and/or port are provided, it checks that explicit endpoint instead.
    If ``remote`` is given, the sessions of that machine are listed over SSH.
    """
    daemons = []

    if remote is not None:
        from odatix.lib.parallel_job_handler.remote import RemoteHost

        host_obj = remote if hasattr(remote, "list_sessions") else RemoteHost(remote)
        return host_obj.list_sessions(session=session)

    if host is not None or port is not None:
        state = explicit_endpoint_state(host=host, port=port, token=token)
        state["workspace_root"] = os.path.realpath(workspace_root or os.getcwd())
        state["uptime_s"] = _daemon_uptime_str(state)
        _decorate_session_fields(state)
        if _daemon_is_alive_with_retries(state):
            daemons.append(state)
        return _filter_daemons_by_session_selector(daemons, session)

    seen = set()

    for candidate in _iter_system_daemon_candidates() or []:
        state = {}
        state_file = candidate.get("state_file")
        if state_file:
            loaded_state = _read_json_file(state_file)
            if isinstance(loaded_state, dict):
                state.update(loaded_state)

        # Keep runtime values from state file when available: cmdline can keep
        # the requested startup port while the daemon may actually bind another
        # free port (find_free_port). A unix session has neither.
        if state.get("transport") == TRANSPORT_UNIX:
            state.pop("host", None)
            state.pop("port", None)
        elif state.get("host") in (None, "") and candidate.get("host") is not None:
            state["host"] = candidate["host"]
        if (
            state.get("transport") != TRANSPORT_UNIX
            and state.get("port") is None
            and candidate.get("port") is not None
        ):
            state["port"] = candidate["port"]
        if state.get("session_name") in (None, "") and candidate.get("session_name") is not None:
            state["session_name"] = str(candidate["session_name"])

        # Keep daemon pid from state file when available.
        # Some process scans can surface intermediary python processes that
        # share daemon cmdline args; overriding pid would create duplicates.
        if state.get("pid") is None:
            state["pid"] = int(candidate["pid"])
        state["state_file"] = candidate.get("state_file")

        if candidate.get("workspace_root") is not None:
            state["workspace_root"] = os.path.realpath(candidate["workspace_root"])
        else:
            state["workspace_root"] = os.path.realpath(workspace_root or os.getcwd())

        state["uptime_s"] = _daemon_uptime_str(state)
        _decorate_session_fields(state)

        # Retries, not a single 0.6s probe: a session under load holds its
        # handler lock for seconds at a time, and dropping it from the listing
        # there makes callers -- the DSE driver above all -- conclude that no
        # session exists at all.
        if not _daemon_is_alive_for_listing(state):
            continue

        # Deduplicate by logical daemon identity rather than candidate pid.
        # Prefer state_file/session_id when available, then endpoint fallback.
        state_file_key = str(state.get("state_file") or "")
        session_id_key = str(state.get("session_id") or "")
        workspace_key = str(state.get("workspace_root") or "")
        key = (
            workspace_key,
            state_file_key,
            session_id_key,
            str(state.get("host", DEFAULT_HOST)),
            int(state.get("port", DEFAULT_PORT)),
        )
        if key in seen:
            continue
        seen.add(key)
        daemons.append(state)

    if len(daemons) > 0:
        daemons = sorted(daemons, key=_daemon_sort_key)
        return _filter_daemons_by_session_selector(daemons, session)

    # Fallback for environments where system process scanning is unavailable.
    paths = get_daemon_paths(workspace_root)
    for state_file in _iter_state_files(paths):
        state = _read_json_file(state_file)
        if not isinstance(state, dict):
            continue

        # Cheapest question first: a state file whose process is gone needs no
        # probing, and probing patiently for one would cost seconds per listing.
        if not _pid_is_running(state.get("pid")):
            diagnostics.log_to(
                diagnostics.diagnostics_path(state_file),
                "state file deleted",
                reason="process gone",
                pid=state.get("pid"),
            )
            _delete_state_file(state_file)
            continue

        # The process is there, so the state file stays whatever the probe says.
        # Deleting it under a busy daemon is unrecoverable: the session keeps
        # running its jobs with nothing able to find it again.
        if _daemon_is_alive_for_listing(state):
            state = dict(state)
            state["workspace_root"] = paths["workspace_root"]
            state["state_file"] = state_file
            state["uptime_s"] = _daemon_uptime_str(state)
            _decorate_session_fields(state)
            daemons.append(state)

    daemons = sorted(daemons, key=_daemon_sort_key)
    return _filter_daemons_by_session_selector(daemons, session)


def list_daemon_jobs(workspace_root=None, session=None):
    """Return jobs currently known by active daemon sessions.

    Each returned job dictionary includes daemon metadata fields:
    ``session_id``, ``session_name``, ``host`` and ``port``.

    Sessions that do not answer are simply left out. Anything that needs to
    tell that apart from a session with no such job wants
    :func:`daemon_jobs_report` instead.
    """
    return daemon_jobs_report(workspace_root=workspace_root, session=session)["jobs"]


def daemon_jobs_report(workspace_root=None, session=None, timeout=JOBS_QUERY_TIMEOUT):
    """The jobs of the active sessions, and which sessions did not answer.

    :func:`list_daemon_jobs` cannot tell "this session has no such job" from
    "this session did not answer in time", because it drops both. That
    difference matters to anything waiting on a job: a caller that reads a
    missed reply as "the job is gone" concludes the job finished, when all
    that happened is that the daemon was busy.

    Returns:
        dict: ``jobs`` (as :func:`list_daemon_jobs` returns them), ``queried``
        (how many sessions were asked) and ``unreachable`` (the addresses of
        those that did not answer).
    """
    jobs = []
    unreachable = []
    daemons = list_daemons(workspace_root=workspace_root, session=session)

    for daemon in daemons:
        try:
            snapshot = _api_request(
                daemon,
                "GET",
                "/status?logs_job_id=-1",
                timeout=float(timeout),
            )
        except Exception as error:
            unreachable.append("{0} ({1})".format(_state_address(daemon), error.__class__.__name__))
            continue

        daemon_jobs = snapshot.get("jobs", [])
        if not isinstance(daemon_jobs, list):
            unreachable.append("{0} (malformed status)".format(_state_address(daemon)))
            continue

        session_id = str(daemon.get("session_id", _session_id_from_state(daemon)))
        session_name = str(daemon.get("session_name", _session_name_from_state(daemon)))
        address = _state_address(daemon)

        for job in daemon_jobs:
            if not isinstance(job, dict):
                continue
            entry = dict(job)
            entry["session_id"] = session_id
            entry["session_name"] = session_name
            entry["address"] = address
            entry["host"] = daemon.get("host")
            entry["port"] = daemon.get("port")
            jobs.append(entry)

    return {"jobs": jobs, "queried": len(daemons), "unreachable": unreachable}


def format_daemons_table(daemons, zombies=False):
    """Format the daemon list into a table with aligned columns.

    With ``zombies=True``, a ``status`` column is added to tell unresponsive
    daemons apart from leftover state files.
    """
    columns = [
        ("workspace", "workspace_root"),
        ("session", "session_id"),
        ("address", "address"),
        ("pid", "pid"),
        ("uptime", "uptime_s"),
    ]
    if zombies:
        columns.append(("status", "status"))

    # Build printable rows once, then compute per-column widths from headers + values.
    rows = []
    for daemon in daemons:
        rows.append([str(daemon.get(key, "")) for _, key in columns])

    column_widths = []
    for index, (header, _) in enumerate(columns):
        max_value_width = max((len(row[index]) for row in rows), default=0)
        column_widths.append(max(len(header), max_value_width))

    row_format = "  ".join(f"{{:<{width}}}" for width in column_widths)
    table = [printc.colors.BOLD + row_format.format(*[header for header, _ in columns]) + printc.colors.BOLD_END]
    table.extend(row_format.format(*row) for row in rows)
    return "\n".join(table)


def _kill_pid(pid):
    """SIGKILL (or forced taskkill) a pid, ignoring processes already gone."""
    pid = int(pid)
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            pass


def _zombie_key(zombie):
    state_file = str(zombie.get("state_file") or "")
    if state_file != "":
        return ("state_file", os.path.realpath(os.path.expanduser(state_file)))
    pid = zombie.get("pid")
    if pid is not None:
        return ("pid", str(pid))
    return ("endpoint", _state_address(zombie))


def exclude_zombies(daemons, zombies):
    """Remove from ``daemons`` the sessions also reported as zombies.

    :func:`list_daemons` and :func:`list_zombie_daemons` are two independent
    snapshots, and they do not probe the same way: the former accepts a single
    reply as proof of life, the latter retries before giving up. A daemon that
    answers intermittently can therefore land in both lists, and be advertised
    as usable while it is in fact a leftover. The zombie verdict is the more
    thorough one, so it wins.
    """
    zombie_keys = set(_zombie_key(zombie) for zombie in zombies)
    return [daemon for daemon in daemons if _zombie_key(daemon) not in zombie_keys]


def list_zombie_daemons(workspace_root=None, session=None):
    """Return daemon sessions that are neither usable nor properly cleaned up.

    Two kinds of leftovers are reported:

    - ``unresponsive``: a daemon process is still running but does not answer
      its HTTP API anymore, so no client can attach to it or enqueue into it.
    - ``stale``: a state file is still there while its daemon is gone, which
      keeps advertising a session that no longer exists.

    These are deliberately excluded from :func:`list_daemons`, which only
    reports sessions that actually answer.
    """
    zombies = []
    seen = set()

    def _add(zombie):
        key = _zombie_key(zombie)
        if key in seen:
            return
        seen.add(key)
        zombies.append(zombie)

    # Running daemon processes that stopped answering.
    for candidate in _iter_system_daemon_candidates() or []:
        state = {}
        state_file = candidate.get("state_file")
        if state_file:
            loaded_state = _read_json_file(state_file)
            if isinstance(loaded_state, dict):
                state.update(loaded_state)

        if state.get("transport") == TRANSPORT_UNIX:
            state.pop("host", None)
            state.pop("port", None)
        else:
            if state.get("host") in (None, "") and candidate.get("host") is not None:
                state["host"] = candidate["host"]
            if state.get("port") is None and candidate.get("port") is not None:
                state["port"] = candidate["port"]
        if state.get("session_name") in (None, "") and candidate.get("session_name") is not None:
            state["session_name"] = str(candidate["session_name"])
        if state.get("pid") is None:
            state["pid"] = int(candidate["pid"])
        state["state_file"] = state_file

        if candidate.get("workspace_root") is not None:
            state["workspace_root"] = os.path.realpath(candidate["workspace_root"])
        else:
            state["workspace_root"] = os.path.realpath(workspace_root or os.getcwd())

        if _daemon_is_alive_with_retries(state):
            continue

        state["uptime_s"] = _daemon_uptime_str(state)
        state["status"] = "unresponsive"
        state["process_pid"] = int(candidate["pid"])
        _decorate_session_fields(state)
        _add(state)

    # State files left behind by daemons that are gone.
    paths = get_daemon_paths(workspace_root)
    for state_file in _iter_state_files(paths):
        state = _read_json_file(state_file)
        if not isinstance(state, dict):
            state = {}
        state = dict(state)
        state["state_file"] = state_file
        state.setdefault("workspace_root", paths["workspace_root"])

        if _pid_is_running(state.get("pid")):
            continue
        if daemon_is_alive(state, timeout=0.6):
            continue

        state["uptime_s"] = _daemon_uptime_str(state)
        state["status"] = "stale"
        _decorate_session_fields(state)
        _add(state)

    zombies = sorted(zombies, key=_daemon_sort_key)
    return _filter_daemons_by_session_selector(zombies, session)


def kill_zombie_daemons(workspace_root=None, session=None):
    """Kill unresponsive daemon processes and remove leftover state files.

    Returns a dict with ``total``, ``killed`` and ``failed`` (the zombie
    descriptors that survived).
    """
    workspace_root = detect_workspace_root(workspace_root)
    zombies = list_zombie_daemons(workspace_root=workspace_root, session=session)

    killed = 0
    failed = []

    for zombie in zombies:
        pid = zombie.get("process_pid", zombie.get("pid"))

        if _pid_is_running(pid):
            try:
                _terminate_pid(pid)
            except Exception:
                pass

            deadline = time.time() + 2.0
            while time.time() < deadline and _pid_is_running(pid):
                time.sleep(0.1)

            if _pid_is_running(pid):
                _kill_pid(pid)
                deadline = time.time() + 2.0
                while time.time() < deadline and _pid_is_running(pid):
                    time.sleep(0.1)

        if _pid_is_running(pid):
            failed.append(zombie)
            continue

        cleanup_root = zombie.get("workspace_root", workspace_root)
        try:
            _delete_state_files_for_daemon(get_daemon_paths(cleanup_root), zombie)
        except Exception:
            pass
        killed += 1

    _cleanup_workspace_daemon_dir_if_empty(workspace_root)

    return {"total": len(zombies), "killed": killed, "failed": failed}
