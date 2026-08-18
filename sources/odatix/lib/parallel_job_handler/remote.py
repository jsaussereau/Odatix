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

"""Reaching a session running on another machine, over SSH.

Odatix never opens a port to the network for this. The remote session keeps
listening on its private socket, and SSH carries the API to it:

    ssh -N -L 127.0.0.1:<local port>:<remote socket> user@host

Authentication, encryption and host verification are SSH's, which the site
administrator already controls; the session token then travels inside the
tunnel and authorises the calls. Nothing about the remote session has to be
made reachable for this to work, which is also what makes it usable on
clusters where opening ports is not an option.

The same primitive is what distributed execution would build on: a worker is
just a session someone else's machine hosts and that we reach through a tunnel.
"""

import json
import os
import shlex
import shutil
import socket
import subprocess
import time

from odatix.lib.parallel_job_handler.auth import SCOPE_CONTROL
from odatix.lib.parallel_job_handler.transport import TRANSPORT_UNIX, Endpoint

DEFAULT_SSH_COMMAND = "ssh"
DEFAULT_ODATIX_COMMAND = "odatix"


class RemoteError(RuntimeError):
    pass


def _ssh_binary(ssh_command=None):
    ssh_command = str(ssh_command or os.environ.get("ODATIX_SSH", DEFAULT_SSH_COMMAND))
    if shutil.which(ssh_command.split()[0]) is None:
        raise RemoteError("'{}' not found: remote sessions need an SSH client".format(ssh_command))
    return ssh_command.split()


def _free_local_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


class RemoteHost:
    """A machine hosting Odatix sessions, reached over SSH."""

    def __init__(self, spec, workspace=None, ssh_command=None, odatix_command=None, ssh_options=None):
        spec = str(spec or "").strip()
        if spec == "":
            raise RemoteError("Empty remote specification")

        # "user@host:/path/to/workspace" also sets the workspace.
        if workspace is None and ":" in spec:
            host_part, _, path_part = spec.rpartition(":")
            if host_part and path_part.startswith(("/", "~", ".")):
                spec = host_part
                workspace = path_part

        self.spec = spec
        self.workspace = str(workspace) if workspace else None
        self.ssh = _ssh_binary(ssh_command)
        # Split so that ODATIX_REMOTE_COMMAND can name an interpreter and a
        # script, not just a single executable.
        self.odatix_command = shlex.split(
            str(odatix_command or os.environ.get("ODATIX_REMOTE_COMMAND", DEFAULT_ODATIX_COMMAND))
        )
        self.ssh_options = list(ssh_options or [])

    def __str__(self):
        if self.workspace:
            return "{}:{}".format(self.spec, self.workspace)
        return self.spec

    # -- running commands on the other side -------------------------------

    def _remote_shell_command(self, argv):
        """A single shell command line to run on the remote host."""
        quote = shlex.quote
        parts = [quote(str(a)) for a in argv]
        command = " ".join(parts)
        if self.workspace:
            command = "cd {} && {}".format(quote(self.workspace), command)
        return command

    def run(self, argv, timeout=30.0, check=True):
        """Run an odatix command on the remote host, returning its stdout."""
        command = self.ssh + list(self.ssh_options) + [self.spec, self._remote_shell_command(argv)]
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=float(timeout),
            )
        except subprocess.TimeoutExpired:
            raise RemoteError("Timed out running '{}' on {}".format(" ".join(argv), self.spec))

        if check and proc.returncode != 0:
            message = proc.stderr.decode("utf-8", "replace").strip()
            raise RemoteError(
                "Remote command failed on {} ({}): {}".format(self.spec, proc.returncode, message or "no output")
            )
        return proc.stdout.decode("utf-8", "replace")

    def list_sessions(self, session=None, timeout=30.0):
        """The sessions running on the remote host.

        Uses ``odatix ls --json`` on the other side, which reports each
        session's endpoint and token -- the token never leaves the SSH
        connection.
        """
        argv = list(self.odatix_command) + ["ls", "--json"]
        if session:
            argv += ["-S", str(session)]

        output = self.run(argv, timeout=timeout)
        try:
            data = json.loads(output)
        except ValueError:
            raise RemoteError(
                "Could not read the session list from {}. Is odatix installed there"
                " (tried '{}')?".format(self.spec, " ".join(self.odatix_command))
            )

        sessions = data.get("sessions") if isinstance(data, dict) else data
        if not isinstance(sessions, list):
            raise RemoteError("Unexpected session list from {}".format(self.spec))

        for state in sessions:
            if isinstance(state, dict):
                state["remote"] = str(self)
        return sessions

    def resolve_session(self, session=None, timeout=30.0):
        sessions = self.list_sessions(session=session, timeout=timeout)
        if len(sessions) == 0:
            raise RemoteError("No active session found on {}".format(self))
        if len(sessions) > 1:
            hints = ", ".join(str(s.get("session_id", "?")) for s in sessions)
            raise RemoteError(
                "Multiple sessions on {}, use -S to select one: {}".format(self, hints)
            )
        return sessions[0]

    def tunnel(self, state, local_port=None):
        """An SSH tunnel to one remote session."""
        return SshTunnel(self, state, local_port=local_port)


class SshTunnel:
    """A forwarded local port that lands on a remote session's socket.

    Use as a context manager; the endpoint it yields is a normal local
    endpoint carrying the remote session's token.
    """

    def __init__(self, remote_host, state, local_port=None):
        self.remote_host = remote_host
        self.state = dict(state or {})
        self.local_port = int(local_port) if local_port else None
        self.process = None

    def _forward_spec(self):
        """The -L argument: local loopback port -> remote socket or port."""
        transport = self.state.get("transport")
        socket_path = self.state.get("socket_path") or self.state.get("socket")

        if transport == TRANSPORT_UNIX or (socket_path and not transport):
            if not socket_path:
                raise RemoteError("Remote session reports no socket path")
            # OpenSSH >= 6.7 forwards a local port to a remote unix socket.
            return "127.0.0.1:{}:{}".format(self.local_port, socket_path)

        host = str(self.state.get("host") or "127.0.0.1")
        port = int(self.state.get("port") or 0)
        if port <= 0:
            raise RemoteError("Remote session reports no port to forward")
        return "127.0.0.1:{}:{}:{}".format(self.local_port, host, port)

    def open(self, timeout=15.0):
        if self.local_port is None:
            self.local_port = _free_local_port()

        command = (
            self.remote_host.ssh
            + list(self.remote_host.ssh_options)
            + [
                "-N",
                "-o", "ExitOnForwardFailure=yes",
                "-L", self._forward_spec(),
                self.remote_host.spec,
            ]
        )

        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        endpoint = Endpoint.tcp(
            "127.0.0.1",
            self.local_port,
            token=self.state.get("token"),
            scope=SCOPE_CONTROL,
        )

        deadline = time.time() + float(timeout)
        while time.time() < deadline:
            if self.process.poll() is not None:
                message = ""
                try:
                    message = self.process.stderr.read().decode("utf-8", "replace").strip()
                except Exception:
                    pass
                raise RemoteError(
                    "Could not open the SSH tunnel to {}: {}".format(
                        self.remote_host, message or "ssh exited"
                    )
                )
            try:
                endpoint.get("/status?logs_job_id=-1", timeout=1.0)
                return endpoint
            except Exception:
                time.sleep(0.2)

        self.close()
        raise RemoteError("Timed out waiting for the SSH tunnel to {}".format(self.remote_host))

    def close(self):
        if self.process is None:
            return
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=3.0)
            except Exception:
                self.process.kill()
        except Exception:
            pass
        self.process = None

    def __enter__(self):
        return self.open()

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def open_remote_endpoint(remote, session=None, workspace=None, ssh_options=None):
    """Resolve a remote session and open a tunnel to it.

    Returns ``(tunnel, endpoint, state)``. The caller owns the tunnel and must
    close it (or use it as a context manager).
    """
    host = remote if isinstance(remote, RemoteHost) else RemoteHost(remote, workspace=workspace, ssh_options=ssh_options)
    state = host.resolve_session(session=session)
    tunnel = host.tunnel(state)
    endpoint = tunnel.open()
    return tunnel, endpoint, state
