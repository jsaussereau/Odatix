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

"""Authentication for the daemon API.

Adding a job to a session means running a command line on the machine hosting
it, so reaching a session's API *is* the right to execute code as its owner.
Nothing here is optional decoration: every request must carry a token, and the
token is a per-session secret written to a file only its owner can read.

Two scopes are distinguished:

- ``read``    : snapshots and logs (the monitor, the GUI dashboards).
- ``control`` : everything that acts -- enqueue, kill, config, shutdown.

They exist so that watching a session can be delegated without handing over the
right to run code. The read token is useless for anything but looking.

The ``Host`` header is checked as well. A browser visiting a malicious page can
be made to POST to ``127.0.0.1:<port>``, and DNS rebinding lets that page reach
a loopback-only server under a hostname it controls. The token defeats this on
its own (the page cannot read the token file), but the host check costs nothing
and closes the door before anything else is looked at.
"""

import hashlib
import json
import os
import secrets
import socket
import stat
import subprocess
import sys

AUTH_HEADER = "authorization"
AUTH_SCHEME = "Bearer"
TOKEN_ENV_VAR = "ODATIX_DAEMON_TOKEN"
ALLOWED_HOSTS_ENV_VAR = "ODATIX_DAEMON_ALLOWED_HOSTS"

SCOPE_READ = "read"
SCOPE_CONTROL = "control"

# Scopes, from least to most powerful. A token's scope satisfies a requirement
# when it sits at or above it in this list.
SCOPE_ORDER = [SCOPE_READ, SCOPE_CONTROL]

LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0", "")


def generate_token():
    """A fresh session secret."""
    return secrets.token_urlsafe(32)


def is_loopback_host(host):
    host = str(host or "").strip().lower()
    if host in ("localhost", "::1", "[::1]"):
        return True
    return host.startswith("127.")


def scope_satisfies(token_scope, required_scope):
    try:
        return SCOPE_ORDER.index(str(token_scope)) >= SCOPE_ORDER.index(str(required_scope))
    except ValueError:
        return False


def _split_host_header(value):
    """The host part of a ``Host`` header, without its port."""
    value = str(value or "").strip().lower()
    if value.startswith("["):  # IPv6 literal: [::1]:8000
        end = value.find("]")
        if end != -1:
            return value[: end + 1]
        return value
    if ":" in value:
        return value.rsplit(":", 1)[0]
    return value


def default_allowed_hosts(bound_host=None):
    """Host header values a session accepts by default."""
    hosts = set(LOOPBACK_HOSTS)
    if bound_host:
        hosts.add(str(bound_host).strip().lower())
    try:
        nodename = socket.gethostname()
        if nodename:
            hosts.add(nodename.lower())
            hosts.add(nodename.split(".")[0].lower())
    except Exception:
        pass

    extra = os.environ.get(ALLOWED_HOSTS_ENV_VAR, "")
    for item in str(extra).split(","):
        item = item.strip().lower()
        if item:
            hosts.add(item)

    return hosts


class ApiAuth:
    """Server-side token and host checks for one session."""

    def __init__(self, control_token, read_token=None, allowed_hosts=None, bound_host=None):
        self.control_token = str(control_token or "")
        self.read_token = str(read_token or "")
        if allowed_hosts is None:
            allowed_hosts = default_allowed_hosts(bound_host=bound_host)
        self.allowed_hosts = set(str(h).strip().lower() for h in allowed_hosts)

    @classmethod
    def generate(cls, bound_host=None, allowed_hosts=None):
        return cls(
            control_token=generate_token(),
            read_token=generate_token(),
            allowed_hosts=allowed_hosts,
            bound_host=bound_host,
        )

    def host_allowed(self, host_header):
        if "*" in self.allowed_hosts:
            return True
        return _split_host_header(host_header) in self.allowed_hosts

    def scope_for_token(self, token):
        """The scope a presented token grants, or None when it grants nothing.

        Both comparisons always run: returning early on the first match would
        make the answer's timing depend on which token was presented.
        """
        token = str(token or "")
        if token == "":
            return None
        is_control = self.control_token != "" and secrets.compare_digest(token, self.control_token)
        is_read = self.read_token != "" and secrets.compare_digest(token, self.read_token)
        if is_control:
            return SCOPE_CONTROL
        if is_read:
            return SCOPE_READ
        return None

    def token_from_header(self, header_value):
        header_value = str(header_value or "").strip()
        if header_value == "":
            return ""
        parts = header_value.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == AUTH_SCHEME.lower():
            return parts[1].strip()
        # Accept a bare token too: it makes manual curl testing bearable.
        return header_value

    def authorize(self, headers, required_scope=SCOPE_CONTROL):
        """Check one request.

        Returns ``(status, message)`` where status is 0 when the request may
        proceed, or the HTTP status to answer with.
        """
        if not self.host_allowed(headers.get("host")):
            return 403, "Host header not allowed"

        scope = self.scope_for_token(self.token_from_header(headers.get(AUTH_HEADER)))
        if scope is None:
            return 401, "Missing or invalid session token"
        if not scope_satisfies(scope, required_scope):
            return 403, "This token is read-only"
        return 0, ""

    def tokens_dict(self):
        return {"token": self.control_token, "read_token": self.read_token}


def auth_header(token):
    """The Authorization header a client must send."""
    return {"Authorization": "{} {}".format(AUTH_SCHEME, str(token or ""))}


def _restrict_windows_acl(path):
    """Best effort: strip inherited ACLs so only the current user can read.

    Windows ignores the POSIX mode passed to ``os.open``, so a state file
    holding a session token would otherwise be readable by every account on
    the machine.
    """
    user = os.environ.get("USERNAME") or ""
    if not user:
        return
    try:
        subprocess.call(
            ["icacls", str(path), "/inheritance:r", "/grant:r", "{}:F".format(user)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


#: Who may use a session besides its owner: nobody ("user", the default), the
#: members of the group of its workspace ("group"), or every user of the
#: machine ("other"). Using a session is running commands as its owner, so a
#: wider access is a decision its owner makes, never a default.
ACCESS_USER = "user"
ACCESS_GROUP = "group"
ACCESS_OTHER = "other"
ACCESS_LEVELS = (ACCESS_USER, ACCESS_GROUP, ACCESS_OTHER)
DEFAULT_ACCESS = ACCESS_USER


def normalize_access(access):
    """An access level out of ``access`` (None is the default one)."""
    if access in (None, ""):
        return DEFAULT_ACCESS
    value = str(access).strip().lower()
    if value not in ACCESS_LEVELS:
        raise ValueError(
            "Unknown session access '{}' (expected one of: {})".format(access, ", ".join(ACCESS_LEVELS))
        )
    return value


def access_file_mode(access):
    """The mode of a file only those ``access`` names may read (and write)."""
    access = normalize_access(access)
    if access == ACCESS_OTHER:
        return 0o644
    if access == ACCESS_GROUP:
        return 0o640
    return 0o600


def access_socket_mode(access):
    """The mode of a socket only those ``access`` names may connect to."""
    access = normalize_access(access)
    if access == ACCESS_OTHER:
        return 0o666
    if access == ACCESS_GROUP:
        return 0o660
    return 0o600


def access_traverse_bits(access):
    """The bits that let those ``access`` names reach a known file of a directory, not list it."""
    access = normalize_access(access)
    if access == ACCESS_OTHER:
        return 0o011
    if access == ACCESS_GROUP:
        return 0o010
    return 0


def access_gid(path):
    """
    The group a session shared with a group belongs to: that of its workspace
    (``path``), which is how a team shares a project. None when it cannot be
    told.
    """
    try:
        return os.stat(str(path)).st_gid
    except (OSError, AttributeError):
        return None


def chown_group(path_or_fd, gid):
    """Give a file to ``gid``, if its owner may (the owner must be a member of it)."""
    if gid is None or not hasattr(os, "chown"):
        return False
    try:
        if isinstance(path_or_fd, int):
            os.fchown(path_or_fd, -1, int(gid))
        else:
            os.chown(str(path_or_fd), -1, int(gid))
        return True
    except OSError:
        return False


def owner_name(uid):
    """The login of ``uid``, or the uid itself when it has none."""
    if uid is None:
        return ""
    try:
        import pwd

        return pwd.getpwuid(int(uid)).pw_name
    except Exception:
        return str(uid)


def current_uid():
    """The user this process acts as (root under sudo)."""
    return getattr(os, "geteuid", lambda: None)()


def prepare_state_dir(path, access=DEFAULT_ACCESS):
    """
    Create the directory holding the state files of a workspace's sessions.

    It is private to its owner, except that a shared session lets those it is
    shared with *reach* its state file: they may traverse the directory, never
    list it. A private session started later does not take that back, since a
    shared one may still be running there; its own state file stays private.
    """
    path = str(path)
    if not path:
        return
    created = not os.path.isdir(path)
    if created:
        os.makedirs(path, exist_ok=True)
    try:
        current = 0o700 if created else (os.stat(path).st_mode & 0o777)
        # Never readable nor writable by anyone else, whatever it was.
        mode = 0o700 | (current & 0o011) | access_traverse_bits(access)
        os.chmod(path, mode)
    except OSError:
        pass
    if sys.platform == "win32":
        _restrict_windows_acl(path)


def secure_makedirs(path, mode=0o700):
    """Create a directory only its owner may enter."""
    path = str(path)
    if not path:
        return
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    try:
        os.chmod(path, mode)
    except Exception:
        pass
    if sys.platform == "win32":
        _restrict_windows_acl(path)


def write_secret_json(path, payload, mode=0o600, gid=None):
    """Write JSON to ``path`` so that only its owner can read it.

    The file is created with its restricted mode from the start: creating it
    world-readable and calling chmod afterwards leaves a window in which the
    token can be read.

    Args:
        mode (int): a wider mode for a session shared with others (see
            access_file_mode), set before anything is written.
        gid (int): the group of the file, for a session shared with a group.
    """
    path = str(path)
    tmp_path = path + ".tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        os.unlink(tmp_path)
    except OSError:
        pass

    fd = os.open(tmp_path, flags, stat.S_IRUSR | stat.S_IWUSR)
    if mode != 0o600 and hasattr(os, "fchmod"):
        # Group first, then mode: a group-readable file of the wrong group
        # would be shared with the wrong people, if only for a moment. The
        # umask does not apply to fchmod, which is what makes the mode exact.
        chown_group(fd, gid)
        try:
            os.fchmod(fd, mode)
        except OSError:
            pass
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        raise

    if sys.platform == "win32":
        _restrict_windows_acl(tmp_path)

    os.replace(tmp_path, path)

    if sys.platform == "win32":
        _restrict_windows_acl(path)


def session_key(workspace_root, session_name):
    """A short, stable identifier for a session, safe to use in a file name."""
    raw = "{}\x00{}".format(str(workspace_root or ""), str(session_name or ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
