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
Access control of the GUI.

Listening on 127.0.0.1 is not enough: every user of a shared machine can reach
a loopback port, an ssh tunnel makes every visitor come from 127.0.0.1, and a
page of any web site the browser visits can reach a loopback server under a
hostname it controls (DNS rebinding). The GUI runs commands as its owner and
browses their files, so every request must prove it comes from them.

- A token is drawn at each start (or taken from ``ODATIX_GUI_TOKEN``) and
  printed in the URL the GUI announces. The first visit with ``?token=`` trades
  it for a cookie (``HttpOnly``, ``SameSite=Strict``) and goes on to the same
  URL without it, so that it does not stay in the address bar. It goes on from
  a page, not with an HTTP redirect: a visit started elsewhere (the launch file
  below, a link) is cross-site all along a redirect, so the browser would not
  send the Strict cookie it was just given.
- Every request must then carry the cookie. A cookie is not scoped by port: its
  name holds the port, so that two GUIs of one machine do not log each other out.
- The ``Host`` header must name this machine (a loopback name, its hostname, the
  address it listens on, or one of ``ODATIX_GUI_ALLOWED_HOSTS``, ``*`` for any).
- ``--unsafe-no-token`` turns the token off: anyone who reaches the port uses
  the GUI as its owner. The Host check and the headers stay.
- Every answer forbids being framed by another site, sniffing its type, and
  sending its address (with a token) to the sites it links to.
- The browser opened at start is given a local file redirecting to the address
  rather than the address itself: on its command line, the token would be read
  by every user of the machine (``ps``).
"""

import hmac
import os
import secrets
import socket
import tempfile
import threading

TOKEN_ENV_VAR = "ODATIX_GUI_TOKEN"
ALLOWED_HOSTS_ENV_VAR = "ODATIX_GUI_ALLOWED_HOSTS"
TOKEN_PARAM = "token"

#: Headers added to every answer.
SECURITY_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": "frame-ancestors 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

#: How long the redirect file of `launch_url` is kept, in seconds.
LAUNCH_FILE_LIFETIME = 120

_REDIRECT_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={url}">
<title>Odatix</title></head>
<body><script>window.location.replace({url_js});</script>
<p><a href="{url}">Open Odatix</a></p></body></html>
"""

_DENIED_PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Odatix</title>
<style>body{font-family:sans-serif;max-width:40em;margin:4em auto;padding:0 1em;line-height:1.5}</style>
</head><body><h1>Access denied</h1><p>{message}</p></body></html>
"""


def _redirect_page(url):
    """A page sending the browser on to `url`."""
    import html
    import json
    url_js = json.dumps(url).replace("<", "\\u003c")
    return _REDIRECT_PAGE.replace("{url_js}", url_js).replace("{url}", html.escape(url, quote=True))


def generate_token():
    return secrets.token_urlsafe(32)


def _split_host(value):
    """The host part of a ``Host`` header, without its port."""
    value = str(value or "").strip().lower()
    if value.startswith("["):
        end = value.find("]")
        return value[: end + 1] if end != -1 else value
    if ":" in value:
        return value.rsplit(":", 1)[0]
    return value


def _is_loopback_ip(host):
    """127.x.y.z written as an address, not a name starting with "127." (127.evil.example)."""
    import ipaddress
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def default_allowed_hosts(extra=()):
    hosts = {"localhost", "127.0.0.1", "[::1]"}
    try:
        name = socket.gethostname().lower()
        if name:
            hosts.add(name)
            hosts.add(name.split(".")[0])
            try:
                hosts.add(socket.getfqdn(name).lower())
            except Exception:
                pass
    except Exception:
        pass
    for host in extra:
        if host:
            hosts.add(str(host).strip().lower())
    for host in os.environ.get(ALLOWED_HOSTS_ENV_VAR, "").split(","):
        host = host.strip().lower()
        if host:
            hosts.add(host)
    return hosts


class AccessGuard:
    """Checks every request of a Flask server against a token and the Host header."""

    def __init__(self, token=None, port=None, allowed_hosts=None, require_token=True):
        self.require_token = bool(require_token)
        self.token = str(token or os.environ.get(TOKEN_ENV_VAR) or generate_token())
        self.cookie_name = "odatix_gui_" + str(port) if port is not None else "odatix_gui"
        self.allowed_hosts = set(allowed_hosts) if allowed_hosts is not None else default_allowed_hosts()

    def url_suffix(self, path="/"):
        """`path` with the token query a first visit needs (`path` alone without a token)."""
        if not self.require_token:
            return path
        separator = "&" if "?" in path else "?"
        return path + separator + TOKEN_PARAM + "=" + self.token

    def host_allowed(self, host_header):
        if "*" in self.allowed_hosts:
            return True
        host = _split_host(host_header)
        return host in self.allowed_hosts or _is_loopback_ip(host)

    def token_valid(self, token):
        return bool(token) and hmac.compare_digest(str(token), self.token)

    def install(self, server):
        """Check every request of `server` (a Flask app) before it is served."""
        from flask import request, make_response

        guard = self

        def denied(status, message):
            response = make_response(_DENIED_PAGE.replace("{message}", message), status)
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            response.headers["Cache-Control"] = "no-store"
            return response

        @server.before_request
        def check_access():
            if not guard.host_allowed(request.headers.get("Host")):
                return denied(403, "This address is not one of this machine's. To reach the GUI under another "
                                   "name, add it to " + ALLOWED_HOSTS_ENV_VAR + ".")
            if not guard.require_token:
                return None
            query_token = request.args.get(TOKEN_PARAM)
            if query_token is not None:
                if not guard.token_valid(query_token):
                    return denied(401, "This link holds an invalid token. Open the URL Odatix printed when the GUI started.")
                # Trade the token for a cookie, and drop it from the address bar.
                args = [(k, v) for k, v in request.args.items(multi=True) if k != TOKEN_PARAM]
                location = request.path
                if args:
                    from urllib.parse import urlencode
                    location += "?" + urlencode(args)
                response = make_response(_redirect_page(location), 200)
                response.headers["Content-Type"] = "text/html; charset=utf-8"
                response.headers["Cache-Control"] = "no-store"
                response.set_cookie(
                    guard.cookie_name, guard.token,
                    httponly=True, samesite="Strict", path="/",
                )
                return response
            if guard.token_valid(request.cookies.get(guard.cookie_name)):
                return None
            return denied(401, "This GUI needs the link Odatix printed when it started "
                               "(\"Server running on http://...?token=...\").")

        @server.after_request
        def add_security_headers(response):
            for name, value in SECURITY_HEADERS.items():
                response.headers.setdefault(name, value)
            return response

        return self


def launch_url(url):
    """
    A file:// URL of a page only the current user can read, redirecting to
    `url`: what the browser is opened on, so that the token stays off the
    command lines of the machine. The file is removed after a while. `url`
    itself when the file cannot be written.
    """
    try:
        fd, path = tempfile.mkstemp(prefix="odatix-gui-", suffix=".html")  # mode 0600
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(_redirect_page(url))
    except OSError:
        return url

    def remove():
        try:
            os.remove(path)
        except OSError:
            pass

    timer = threading.Timer(LAUNCH_FILE_LIFETIME, remove)
    timer.daemon = True
    timer.start()
    from urllib.request import pathname2url
    return "file:" + pathname2url(path)
