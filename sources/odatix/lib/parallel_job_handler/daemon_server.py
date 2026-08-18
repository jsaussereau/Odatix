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

"""Background daemon process for shared ParallelJobHandler execution."""

import argparse
import os
import threading
import time

from odatix.lib.parallel_job_handler import diagnostics
from odatix.lib.parallel_job_handler.api import create_uvicorn_server
from odatix.lib.parallel_job_handler.auth import ApiAuth, secure_makedirs, write_secret_json
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler
from odatix.lib.parallel_job_handler.transport import (
    TRANSPORT_TCP,
    TRANSPORT_UNIX,
    harden_socket,
    remove_socket,
    socket_path_for_session,
    unix_sockets_supported,
)
from odatix.lib.utils import find_free_port
import odatix.lib.hard_settings as hard_settings


def _write_state_file(state_file, endpoint_fields, auth, session_name, host):
    """Record where this session listens and how to authenticate to it.

    The file holds the session tokens, so it is written with owner-only
    permissions -- anyone who can read it can run commands as this user.
    """
    session_name = str(session_name or host).strip() or str(host)
    state = {
        "pid": os.getpid(),
        "session_name": session_name,
        "session_id": "{}.{}".format(os.getpid(), session_name),
        "started_at": int(time.time()),
    }
    state.update(endpoint_fields)
    state.update(auth.tokens_dict())
    write_secret_json(state_file, state)


def _delete_state_file(state_file):
    try:
        if os.path.isfile(state_file):
            os.remove(state_file)
    except Exception:
        pass


def _cleanup_state_dir_if_empty(state_file):
    try:
        state_dir = os.path.dirname(os.path.realpath(os.path.expanduser(str(state_file))))
        if not state_dir or not os.path.isdir(state_dir):
            return
        if len(os.listdir(state_dir)) == 0:
            os.rmdir(state_dir)
    except Exception:
        pass


def add_arguments(parser):
    parser.add_argument("--state-file", required=True, help="Path to daemon state JSON file")
    parser.add_argument(
        "--transport",
        choices=[TRANSPORT_UNIX, TRANSPORT_TCP, "auto"],
        default="auto",
        help="Listen on a unix socket (default where supported) or a TCP port",
    )
    parser.add_argument("--socket", default=None, help="Unix socket path (transport 'unix')")
    parser.add_argument(
        "--expose",
        action="store_true",
        help="Allow binding a non-loopback TCP address (exposes the session to the network)",
    )
    parser.add_argument("--host", default=hard_settings.daemon_default_host, help="Daemon API host")
    parser.add_argument("--port", type=int, default=hard_settings.daemon_default_port, help="Preferred daemon API port")
    parser.add_argument("--session-name", default=None, help="Optional daemon session name")
    parser.add_argument("--jobs", type=int, default=4, help="Default maximum number of parallel jobs")
    parser.add_argument("--logsize", type=int, default=200, help="Default log history limit per job")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run Odatix parallel-job daemon")
    add_arguments(parser)
    return parser.parse_args()


def resolve_transport(transport, socket_path, workspace_root, session_name, host):
    """Pick the transport actually used, and where it listens.

    "auto" means a unix socket whenever the platform can serve one and the
    path fits in a sockaddr_un; otherwise loopback TCP. Windows always lands
    on TCP -- asyncio there cannot create a unix server -- which is safe
    because the session token is required either way.
    """
    transport = str(transport or "auto")

    if transport == TRANSPORT_UNIX:
        if not unix_sockets_supported():
            raise RuntimeError("Unix sockets are not supported on this platform")
        socket_path = socket_path or socket_path_for_session(workspace_root, session_name)
        if not socket_path:
            raise RuntimeError("No usable unix socket path for this session")
        return TRANSPORT_UNIX, str(socket_path)

    if transport == "auto" and unix_sockets_supported():
        socket_path = socket_path or socket_path_for_session(workspace_root, session_name)
        if socket_path:
            return TRANSPORT_UNIX, str(socket_path)

    return TRANSPORT_TCP, None


def run_daemon(
    state_file,
    host=hard_settings.daemon_default_host,
    port=hard_settings.daemon_default_port,
    jobs=4,
    logsize=200,
    session_name=None,
    transport="auto",
    socket_path=None,
    expose=False,
):
    state_file = os.path.realpath(os.path.expanduser(str(state_file)))
    state_dir = os.path.dirname(state_file)
    if state_dir:
        secure_makedirs(state_dir, 0o700)

    # Opened before anything else can fail: the whole point of the file is to
    # hold what a session that dies would otherwise take with it, and its
    # stdout goes to /dev/null unless the daemon log was asked for.
    diagnostics.configure(diagnostics.diagnostics_path(state_file))
    diagnostics.log("daemon starting", session=str(session_name or ""), jobs=int(jobs))

    host = str(host)
    jobs = max(1, int(jobs))
    logsize = int(logsize)

    workspace_root = os.path.dirname(state_dir) if state_dir else os.getcwd()
    transport, socket_path = resolve_transport(
        transport, socket_path, workspace_root, session_name, host
    )

    if transport == TRANSPORT_UNIX:
        # A leftover socket from a crashed daemon would make the bind fail.
        remove_socket(socket_path)
        port = 0
    else:
        port = find_free_port(host, int(port))

    auth = ApiAuth.generate(bound_host=host)

    handler = ParallelJobHandler(
        job_list=[],
        nb_jobs=jobs,
        process_group=True,
        auto_exit=False,
        log_size_limit=logsize,
    )

    server_ref = {"server": None}

    def _request_server_shutdown():
        server = server_ref.get("server")
        if server is not None:
            server.should_exit = True

    server = create_uvicorn_server(
        handler,
        auth=auth,
        transport=transport,
        host=host,
        port=port,
        socket_path=socket_path,
        allow_remote_bind=bool(expose),
        log_level="critical",
        start_headless_on_startup=True,
        quiet=True,
        shutdown_callback=_request_server_shutdown,
    )
    server_ref["server"] = server

    endpoint_fields = {"transport": transport}
    if transport == TRANSPORT_UNIX:
        endpoint_fields["socket_path"] = socket_path
        # The socket only exists once uvicorn has bound it, and uvicorn leaves
        # it world-writable. Tighten it as soon as it appears.
        threading.Thread(target=harden_socket, args=(socket_path,), daemon=True).start()
    else:
        endpoint_fields["host"] = host
        endpoint_fields["port"] = int(port)

    _write_state_file(
        state_file=state_file,
        endpoint_fields=endpoint_fields,
        auth=auth,
        session_name=session_name,
        host=host,
    )

    try:
        server.run()
    except BaseException as error:
        # Without this the traceback of a daemon that dies is written to a
        # closed stdout and lost, and all that is left is a session that no
        # longer answers.
        diagnostics.log_exception("daemon stopped on error", error)
        raise
    finally:
        diagnostics.log(
            "daemon exiting",
            jobs=len(getattr(handler, "job_list", ())),
            running=len(getattr(handler, "running_job_list", ())),
        )
        try:
            handler.stop_headless(terminate_jobs=True, timeout=2.0)
        except Exception:
            pass
        if transport == TRANSPORT_UNIX:
            remove_socket(socket_path)
        _delete_state_file(state_file)
        _cleanup_state_dir_if_empty(state_file)


def main(args=None):
    if args is None:
        args = parse_arguments()
    run_daemon(
        state_file=args.state_file,
        host=args.host,
        port=args.port,
        session_name=args.session_name,
        jobs=args.jobs,
        logsize=args.logsize,
        transport=args.transport,
        socket_path=args.socket,
        expose=args.expose,
    )


if __name__ == "__main__":
    main()
