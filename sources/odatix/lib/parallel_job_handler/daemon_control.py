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
import urllib.error
import urllib.request

from odatix.lib.parallel_job_handler.serialization import job_to_payload
from odatix.lib.parallel_job_handler.job import ParallelJob
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
    pid = int(os.getpid())

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
    return "{}.{}.{}".format(pid, tty_slug, host_slug)


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
    return state


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


def _state_base_url(state):
    host = str(state.get("host", DEFAULT_HOST))
    port = int(state.get("port", DEFAULT_PORT))
    return "http://{}:{}".format(host, port)


def daemon_is_alive(state, timeout=0.6):
    if not isinstance(state, dict):
        return False
    try:
        _api_request(_state_base_url(state), "GET", "/status?logs_job_id=-1", timeout=float(timeout))
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
    host = str(state.get("host", DEFAULT_HOST))
    try:
        port = int(state.get("port", DEFAULT_PORT))
    except Exception:
        port = DEFAULT_PORT
    return (pid, host, port)


def _format_session_hint(daemon):
    session_id = str(daemon.get("session_id", "?"))
    host = str(daemon.get("host", DEFAULT_HOST))
    port = str(daemon.get("port", DEFAULT_PORT))
    return "{} ({})".format(session_id, host + ":" + port)


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


def _spawn_daemon(paths, host, port, jobs, logsize, session_name=None, daemon_log_enabled=None):
    os.makedirs(paths["state_dir"], exist_ok=True)
    session_name = _normalize_session_name(session_name, default_name=host)
    daemon_log_enabled = (
        hard_settings.daemon_log_enabled_default
        if daemon_log_enabled is None
        else bool(daemon_log_enabled)
    )

    command = [
        sys.executable,
        "-m",
        "odatix.lib.parallel_job_handler.daemon_server",
        "--state-file",
        paths["state_file"],
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
):
    workspace_root = detect_workspace_root(workspace_root)
    session_selector = str(session).strip() if session is not None else None

    active_daemons = list_daemons(workspace_root=workspace_root)
    active_daemons, _workspace_root = _filter_by_workspace(active_daemons, workspace_root=workspace_root)

    if session_selector:
        matched = _resolve_session_selector(active_daemons, session_selector, allow_missing=True)
        if matched is not None and daemon_is_alive(matched):
            return matched

        session_name = _normalize_session_name(session_selector, default_name=host)
        paths = get_daemon_paths(workspace_root, session_name=session_name)
    else:
        # By default, launching jobs creates a fresh daemon session.
        # Existing sessions are reused only when an explicit selector is given.
        session_name = _generate_default_session_name(host=host)
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


def enqueue_parallel_jobs(parallel_jobs, workspace_root=None, session=None):
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
    )

    payload = {
        "jobs": [job_to_payload(job) for job in job_list],
        "options": {
            "nb_jobs": int(getattr(parallel_jobs, "nb_jobs", 4)),
            "process_group": bool(getattr(parallel_jobs, "process_group", True)),
            "auto_exit": bool(getattr(parallel_jobs, "auto_exit", False)),
            "log_size_limit": int(getattr(parallel_jobs, "log_size_limit", 200)),
            "progress_pattern": getattr(getattr(ParallelJob, "progress_file_pattern", None), "pattern", None),
            "status_pattern": getattr(getattr(ParallelJob, "status_file_pattern", None), "pattern", None),
            # Empty string means "disable formatter" (None means "leave unchanged").
            "format_yaml": str(format_yaml) if format_yaml not in (None, "") else "",
        },
    }

    response = _api_request(
        _state_base_url(state),
        "POST",
        "/jobs/enqueue",
        payload=payload,
        timeout=3.0,
    )
    return state, response


def _resolve_state_for_attach_or_stop(workspace_root=None, host=None, port=None, session=None):
    if host is not None or port is not None:
        state = {
            "host": str(host or DEFAULT_HOST),
            "port": int(port or DEFAULT_PORT),
        }
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


def attach_monitor(workspace_root=None, host=None, port=None, session=None, auto_exit=False):
    state = _resolve_state_for_attach_or_stop(workspace_root=workspace_root, host=host, port=port, session=session)
    if not daemon_is_alive(state):
        raise DaemonControlError("Daemon is not running")

    from odatix.lib.parallel_job_handler.daemon_monitor import run_monitor

    run_monitor(
        host=state.get("host", DEFAULT_HOST),
        port=int(state.get("port", DEFAULT_PORT)),
        auto_exit=bool(auto_exit),
    )


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
    target_host = str((target_state or {}).get("host", DEFAULT_HOST)) if isinstance(target_state, dict) else DEFAULT_HOST
    try:
        target_port = int((target_state or {}).get("port", DEFAULT_PORT)) if isinstance(target_state, dict) else DEFAULT_PORT
    except Exception:
        target_port = DEFAULT_PORT

    for state_file in _iter_state_files(paths):
        loaded = _read_json_file(state_file)
        loaded_key = _state_key(loaded)
        try:
            loaded_port = int((loaded or {}).get("port", DEFAULT_PORT)) if isinstance(loaded, dict) else DEFAULT_PORT
        except Exception:
            loaded_port = DEFAULT_PORT
        same_endpoint = (
            str((loaded or {}).get("host", DEFAULT_HOST)) == target_host
            and loaded_port == target_port
        ) if isinstance(loaded, dict) else False
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
        _api_request(_state_base_url(state), "POST", "/shutdown", payload={}, timeout=1.0)
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


def stop_daemon(workspace_root=None, host=None, port=None, session=None):
    workspace_root = detect_workspace_root(workspace_root)
    state = _resolve_state_for_attach_or_stop(
        workspace_root=workspace_root,
        host=host,
        port=port,
        session=session,
    )
    return _stop_daemon_from_state(state, workspace_root)


def stop_all_daemons(workspace_root=None, host=None, port=None):
    workspace_root = detect_workspace_root(workspace_root)
    daemons = list_daemons(workspace_root=workspace_root, host=host, port=port)

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
    return "{}:{}".format(state.get("host", DEFAULT_HOST), int(state.get("port", DEFAULT_PORT)))


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

        try:
            port = int(port) if port is not None else None
        except Exception:
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
    host = str(daemon.get("host", DEFAULT_HOST))
    workspace_root = str(daemon.get("workspace_root", ""))
    try:
        port = int(daemon.get("port", DEFAULT_PORT))
    except Exception:
        port = DEFAULT_PORT
    return (workspace_root, session_id, host, port)


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


def list_daemons(workspace_root=None, host=None, port=None, session=None):
    """Return a list of active daemon descriptors.

    By default, this inspects running daemon processes on the system.
    If host and/or port are provided, it checks that explicit endpoint instead.
    """
    daemons = []

    if host is not None or port is not None:
        state = {
            "host": str(host or DEFAULT_HOST),
            "port": int(port or DEFAULT_PORT),
            "workspace_root": os.path.realpath(workspace_root or os.getcwd()),
        }
        state["uptime_s"] = _daemon_uptime_str(state)
        _decorate_session_fields(state)
        if daemon_is_alive(state):
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
        # free port (find_free_port).
        if state.get("host") in (None, "") and candidate.get("host") is not None:
            state["host"] = candidate["host"]
        if state.get("port") is None and candidate.get("port") is not None:
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

        if not daemon_is_alive(state):
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

        if daemon_is_alive(state):
            state = dict(state)
            state["workspace_root"] = paths["workspace_root"]
            state["state_file"] = state_file
            state["uptime_s"] = _daemon_uptime_str(state)
            _decorate_session_fields(state)
            daemons.append(state)
        else:
            _delete_state_file(state_file)

    daemons = sorted(daemons, key=_daemon_sort_key)
    return _filter_daemons_by_session_selector(daemons, session)


def list_daemon_jobs(workspace_root=None, session=None):
    """Return jobs currently known by active daemon sessions.

    Each returned job dictionary includes daemon metadata fields:
    ``session_id``, ``session_name``, ``host`` and ``port``.
    """
    jobs = []
    daemons = list_daemons(workspace_root=workspace_root, session=session)

    for daemon in daemons:
        try:
            snapshot = _api_request(
                _state_base_url(daemon),
                "GET",
                "/status?logs_job_id=-1",
                timeout=1.0,
            )
        except Exception:
            continue

        daemon_jobs = snapshot.get("jobs", [])
        if not isinstance(daemon_jobs, list):
            continue

        session_id = str(daemon.get("session_id", _session_id_from_state(daemon)))
        session_name = str(daemon.get("session_name", _session_name_from_state(daemon)))
        host = str(daemon.get("host", DEFAULT_HOST))
        try:
            port = int(daemon.get("port", DEFAULT_PORT))
        except Exception:
            port = DEFAULT_PORT

        for job in daemon_jobs:
            if not isinstance(job, dict):
                continue

            entry = dict(job)
            entry["session_id"] = session_id
            entry["session_name"] = session_name
            entry["host"] = host
            entry["port"] = port
            jobs.append(entry)

    return jobs


def format_daemons_table(daemons):
    """Format the daemon list into a table with aligned columns."""
    columns = [
        ("workspace", "workspace_root"),
        ("session", "session_id"),
        ("host", "host"),
        ("port", "port"),
        ("pid", "pid"),
        ("uptime", "uptime_s"),
    ]

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
