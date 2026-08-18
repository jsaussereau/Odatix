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

"""How a client reaches a daemon session.

Two transports:

- ``unix``: a Unix domain socket, the default wherever the platform has them.
  There is no port to reach from anywhere else, and the socket's file
  permissions keep other users out before a single byte is parsed.
- ``tcp``: a loopback TCP port. The fallback on Windows, which has no usable
  Unix socket support in the ASGI server, and on POSIX when the socket path
  would not fit in the address structure. Also what an SSH tunnel presents on
  the local side.

Both carry the same HTTP API and both require a session token (see auth.py);
the transport decides who can *reach* the session, the token decides who may
*use* it.
"""

import errno
import hashlib
import http.client
import json
import os
import socket
import sys
import tempfile

from odatix.lib.parallel_job_handler.auth import (
    AUTH_SCHEME,
    SCOPE_CONTROL,
    secure_makedirs,
)
import odatix.lib.hard_settings as hard_settings

TRANSPORT_UNIX = "unix"
TRANSPORT_TCP = "tcp"

# sockaddr_un.sun_path is 108 bytes on Linux and 104 on macOS, including the
# terminating NUL. Staying well under the smaller one keeps the same socket
# path valid everywhere.
MAX_UNIX_SOCKET_PATH = 100


class ApiError(RuntimeError):
    """An API call that reached the session but was refused by it."""

    def __init__(self, status, message):
        super().__init__("HTTP {}: {}".format(int(status), str(message)))
        self.status = int(status)
        self.message = str(message)


class AuthError(ApiError):
    """The session refused the token (or the absence of one)."""


def unix_sockets_supported():
    """Whether this platform can serve the API on a Unix domain socket.

    Windows 10 has AF_UNIX, but asyncio there cannot create a Unix server, so
    uvicorn cannot bind one -- the answer is no regardless of the socket
    module.
    """
    if sys.platform == "win32":
        return False
    return hasattr(socket, "AF_UNIX")


def socket_dir():
    """Directory holding session sockets, created private to its owner.

    Deliberately *not* the workspace: socket paths are limited to ~100 bytes,
    and a workspace living a few directories deep already blows that budget.
    """
    base = os.environ.get("XDG_RUNTIME_DIR", "")
    if base and os.path.isdir(base):
        path = os.path.join(base, "odatix")
    else:
        uid = getattr(os, "geteuid", lambda: 0)()
        path = os.path.join(tempfile.gettempdir(), "odatix-{}".format(uid))
    secure_makedirs(path, 0o700)
    return path


def socket_path_for_session(workspace_root, session_name):
    """The socket path for a session, or None when it would not fit.

    Callers must treat None as "use TCP instead": a truncated socket path is
    not something to work around silently.
    """
    if not unix_sockets_supported():
        return None

    raw = "{}\x00{}".format(str(workspace_root or ""), str(session_name or ""))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    path = os.path.join(socket_dir(), "{}.sock".format(digest))

    if len(path.encode("utf-8")) >= MAX_UNIX_SOCKET_PATH:
        return None
    return path


def harden_socket(path, timeout=10.0):
    """Make a listening socket readable only by its owner.

    uvicorn chmods the socket it creates to 0666. The socket lives in a 0700
    directory, so that alone keeps other users out, but a socket nobody else
    can open is one less thing depending on the directory staying private.
    """
    import time

    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        if os.path.exists(path):
            try:
                os.chmod(path, 0o600)
                return True
            except OSError:
                return False
        time.sleep(0.05)
    return False


def remove_socket(path):
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


class _UnixHTTPConnection(http.client.HTTPConnection):
    """http.client speaking to a Unix domain socket."""

    def __init__(self, socket_path, timeout=None):
        http.client.HTTPConnection.__init__(self, "localhost", timeout=timeout)
        self.socket_path = str(socket_path)

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if self.timeout is not None:
            sock.settimeout(self.timeout)
        try:
            sock.connect(self.socket_path)
        except Exception:
            sock.close()
            raise
        self.sock = sock


class Endpoint:
    """Where a session is, and what this client is allowed to ask of it."""

    def __init__(
        self,
        transport=TRANSPORT_TCP,
        host=None,
        port=None,
        socket_path=None,
        token=None,
        scope=SCOPE_CONTROL,
        label=None,
    ):
        self.transport = str(transport or TRANSPORT_TCP)
        self.host = str(host or hard_settings.daemon_default_host)
        self.port = int(port or hard_settings.daemon_default_port)
        self.socket_path = str(socket_path) if socket_path else None
        self.token = str(token) if token else ""
        self.scope = str(scope or SCOPE_CONTROL)
        self._label = label

        if self.transport == TRANSPORT_UNIX and not self.socket_path:
            raise ValueError("a unix endpoint needs a socket path")

    # -- construction ----------------------------------------------------

    @classmethod
    def from_state(cls, state, scope=SCOPE_CONTROL):
        """Build an endpoint from a daemon state file's contents."""
        if not isinstance(state, dict):
            raise ValueError("state must be a dictionary")

        socket_path = state.get("socket_path") or state.get("socket")
        transport = state.get("transport")
        if not transport:
            transport = TRANSPORT_UNIX if socket_path else TRANSPORT_TCP

        token = state.get("token")
        if scope != SCOPE_CONTROL:
            token = state.get("read_token") or token
        if not token:
            token = os.environ.get("ODATIX_DAEMON_TOKEN", "")

        return cls(
            transport=transport,
            host=state.get("host"),
            port=state.get("port"),
            socket_path=socket_path,
            token=token,
            scope=scope,
            label=state.get("session_name"),
        )

    @classmethod
    def tcp(cls, host, port, token=None, scope=SCOPE_CONTROL):
        return cls(transport=TRANSPORT_TCP, host=host, port=port, token=token, scope=scope)

    # -- description -----------------------------------------------------

    @property
    def address(self):
        if self.transport == TRANSPORT_UNIX:
            return "unix:{}".format(self.socket_path)
        return "{}:{}".format(self.host, self.port)

    def __repr__(self):
        return "<Endpoint {}>".format(self.address)

    def to_state_fields(self):
        """The fields describing this endpoint inside a state file."""
        fields = {"transport": self.transport}
        if self.transport == TRANSPORT_UNIX:
            fields["socket_path"] = self.socket_path
        else:
            fields["host"] = self.host
            fields["port"] = int(self.port)
        return fields

    # -- requests --------------------------------------------------------

    def _connection(self, timeout):
        if self.transport == TRANSPORT_UNIX:
            return _UnixHTTPConnection(self.socket_path, timeout=float(timeout))
        return http.client.HTTPConnection(self.host, int(self.port), timeout=float(timeout))

    def request(self, method, path, payload=None, timeout=1.0):
        """Call the session API. Returns the decoded JSON body."""
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = "{} {}".format(AUTH_SCHEME, self.token)

        # Unix connections have no meaningful authority; "localhost" is what
        # the session's own host allow-list expects.
        headers["Host"] = "localhost" if self.transport == TRANSPORT_UNIX else self.host

        conn = self._connection(timeout)
        try:
            conn.request(str(method).upper(), str(path), body=body, headers=headers)
            resp = conn.getresponse()
            status = int(resp.status)
            raw = resp.read()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if status >= 400:
            message = _error_message(raw, status)
            if status in (401, 403):
                raise AuthError(status, message)
            raise ApiError(status, message)

        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def get(self, path, timeout=1.0):
        return self.request("GET", path, timeout=timeout)

    def post(self, path, payload=None, timeout=1.0):
        return self.request("POST", path, payload=payload, timeout=timeout)


def _error_message(raw, status):
    if not raw:
        return "request refused"
    try:
        decoded = json.loads(raw.decode("utf-8"))
        if isinstance(decoded, dict):
            for key in ("error", "detail", "message"):
                if decoded.get(key):
                    return str(decoded[key])
    except Exception:
        pass
    try:
        return raw.decode("utf-8", "replace").strip()[:200]
    except Exception:
        return "HTTP {}".format(status)


def wait_until_reachable(endpoint, timeout=10.0, interval=0.1):
    """Block until the endpoint answers, or the timeout expires."""
    import time

    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        try:
            endpoint.get("/status?logs_job_id=-1", timeout=1.0)
            return True
        except AuthError:
            # Reachable, and telling us the token is wrong: waiting longer
            # will not change that.
            raise
        except Exception:
            time.sleep(float(interval))
    return False


def tcp_port_is_free(host, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((str(host), int(port)))
        return True
    except OSError as e:
        if e.errno in (errno.EADDRINUSE, errno.EACCES):
            return False
        return False
    finally:
        sock.close()
