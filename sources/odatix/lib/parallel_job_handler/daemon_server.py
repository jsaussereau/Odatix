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
import json
import os
import time

from odatix.lib.parallel_job_handler.api import create_uvicorn_server
from odatix.lib.parallel_job_handler.handler_core import ParallelJobHandler
from odatix.lib.utils import find_free_port


def _write_state_file(state_file, host, port):
    state = {
        "pid": os.getpid(),
        "host": str(host),
        "port": int(port),
        "started_at": int(time.time()),
    }
    tmp_file = state_file + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_file, state_file)


def _delete_state_file(state_file):
    try:
        if os.path.isfile(state_file):
            os.remove(state_file)
    except Exception:
        pass


def add_arguments(parser):
    parser.add_argument("--state-file", required=True, help="Path to daemon state JSON file")
    parser.add_argument("--host", default="127.0.0.1", help="Daemon API host")
    parser.add_argument("--port", type=int, default=8000, help="Preferred daemon API port")
    parser.add_argument("--jobs", type=int, default=4, help="Default maximum number of parallel jobs")
    parser.add_argument("--logsize", type=int, default=200, help="Default log history limit per job")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run Odatix parallel-job daemon")
    add_arguments(parser)
    return parser.parse_args()


def run_daemon(state_file, host="127.0.0.1", port=8000, jobs=4, logsize=200):
    state_file = os.path.realpath(os.path.expanduser(str(state_file)))
    state_dir = os.path.dirname(state_file)
    if state_dir:
        os.makedirs(state_dir, exist_ok=True)

    host = str(host)
    port = find_free_port(host, int(port))
    jobs = max(1, int(jobs))
    logsize = int(logsize)

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
        host=host,
        port=port,
        log_level="critical",
        start_headless_on_startup=True,
        quiet=True,
        shutdown_callback=_request_server_shutdown,
    )
    server_ref["server"] = server

    _write_state_file(state_file=state_file, host=host, port=port)

    try:
        server.run()
    finally:
        try:
            handler.stop_headless(terminate_jobs=True, timeout=2.0)
        except Exception:
            pass
        _delete_state_file(state_file)


def main(args=None):
    if args is None:
        args = parse_arguments()
    run_daemon(
        state_file=args.state_file,
        host=args.host,
        port=args.port,
        jobs=args.jobs,
        logsize=args.logsize,
    )


if __name__ == "__main__":
    main()
