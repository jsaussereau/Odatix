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
Registry of the GUI themes.

A theme is one CSS file holding a ``.theme.<name>`` rule that overrides the
tokens declared in ``assets/themes/00_base.css``. The file name is the theme
name, and an optional ``odatix-theme`` header comment carries what CSS cannot
express: the label shown in the theme picker, whether the theme is dark, and
the few colors Plotly needs to draw figures that blend into the page (see
odatix.explorer.charts.app_theme_bridge).

    /* odatix-theme
     * name: Solarized Dark
     * dark: true
     * plot-text-color: #93a1a1
     * plot-grid-color: rgba(147, 161, 161, 0.18)
     * plot-zeroline-color: rgba(38, 139, 210, 0.55)
     */

Themes come from two places:

* the builtin ones, shipped in ``odatix/gui/assets/themes/`` and served by Dash
  like any other asset;
* the user ones, in the workspace directory pointed at by the ``gui_theme_path``
  setting (``odatix_userconfig/themes/gui`` by default). Those live outside the
  asset folder, so they are concatenated and served at `USER_STYLESHEET_URL`.

The user directory is re-scanned whenever one of its files changes, so a theme
can be written and refined without restarting the app.
"""

import os
import re
from collections import OrderedDict, namedtuple

import flask

from odatix.lib.settings import OdatixSettings

default_theme = "odatix"
cookie_name = "odatix_theme"

#: Where the user themes are served, on apps that call `serve_user_themes`.
USER_STYLESHEET_URL = "/_odatix/user-themes.css"

_builtin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "themes")

# The file holding the token defaults; it declares no theme of its own.
BASE_FILE = "00_base.css"

_HEADER_RE = re.compile(r"/\*\s*odatix-theme\b(.*?)\*/", re.DOTALL)
_FIELD_RE = re.compile(r"^\s*\*?\s*([a-z0-9-]+)\s*:\s*(.*?)\s*$", re.MULTILINE)
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

LIGHT_CHROME = {
  "dark": False,
  "text_color": "#24292e",
  "grid_color": "rgba(36, 41, 46, 0.15)",
  "zeroline_color": "rgba(36, 41, 46, 0.4)",
}

DARK_CHROME = {
  "dark": True,
  "text_color": "#f0f0f0",
  "grid_color": "rgba(240, 240, 240, 0.15)",
  "zeroline_color": "rgba(240, 240, 240, 0.4)",
}

#: name     the theme's CSS class and the value stored in the cookie
#: label    what the theme picker shows
#: dark     whether the page background is dark (drives the plot defaults)
#: chrome   text/grid/zeroline colors for Plotly figures
#: source   "builtin" or "user"
#: path     the CSS file the theme was read from
Theme = namedtuple("Theme", "name label dark chrome source path")


def user_theme_dir():
  """
  The directory user themes are read from: the ``gui_theme_path`` setting of the
  workspace, or its default relative to the current directory.
  """
  path = OdatixSettings.user_theme_path
  if path is None:
    path = OdatixSettings.DEFAULT_GUI_THEME_PATH
  return path


def _theme_files(directory):
  """Sorted (name, path) of the theme files of a directory, base file aside."""
  try:
    names = sorted(os.listdir(directory))
  except OSError:
    return []
  files = []
  for filename in names:
    if not filename.endswith(".css") or filename == BASE_FILE:
      continue
    name = filename[: -len(".css")]
    # The name ends up in a CSS class and in a cookie: keep it to what can
    # safely be either.
    if not _NAME_RE.match(name):
      continue
    files.append((name, os.path.join(directory, filename)))
  return files


def _parse_theme(name, path, source):
  """Read a theme file's `odatix-theme` header. Missing fields get defaults."""
  fields = {}
  try:
    with open(path, "r") as f:
      # The header sits at the top of the file, after the license banner; no
      # need to read a few hundred lines of declarations to find it.
      head = f.read(4096)
    match = _HEADER_RE.search(head)
    if match:
      fields = dict(_FIELD_RE.findall(match.group(1)))
  except OSError:
    pass

  dark = str(fields.get("dark", "")).strip().lower() in ("true", "yes", "1")
  base = DARK_CHROME if dark else LIGHT_CHROME
  chrome = {
    "dark": dark,
    "text_color": fields.get("plot-text-color") or base["text_color"],
    "grid_color": fields.get("plot-grid-color") or base["grid_color"],
    "zeroline_color": fields.get("plot-zeroline-color") or base["zeroline_color"],
  }
  return Theme(
    name=name,
    label=fields.get("name") or name,
    dark=dark,
    chrome=chrome,
    source=source,
    path=path,
  )


_cache = None
_cache_key = None


def _user_dir_key(directory):
  """A cheap fingerprint of the user theme directory, to know when to re-scan."""
  try:
    entries = sorted(os.listdir(directory))
  except OSError:
    return ()
  key = []
  for filename in entries:
    if not filename.endswith(".css"):
      continue
    try:
      key.append((filename, os.path.getmtime(os.path.join(directory, filename))))
    except OSError:
      pass
  return tuple(key)


def discover(force=False):
  """
  Every available theme, by name, builtin ones first.

  A user theme whose name collides with a builtin one replaces it, which is how
  a workspace can retouch a shipped theme.
  """
  global _cache, _cache_key
  directory = user_theme_dir()
  key = (directory, _user_dir_key(directory))
  if _cache is not None and not force and key == _cache_key:
    return _cache

  builtin = [_parse_theme(name, path, "builtin") for name, path in _theme_files(_builtin_dir)]
  user = [_parse_theme(name, path, "user") for name, path in _theme_files(directory)]

  # The picker shows this order: the default theme first, so it stays findable
  # among the twenty-odd builtin ones, then the rest by label, then whatever the
  # workspace adds.
  builtin.sort(key=lambda theme: (theme.name != default_theme, theme.label.lower()))
  user.sort(key=lambda theme: theme.label.lower())

  themes = OrderedDict()
  for theme in builtin + user:
    themes[theme.name] = theme

  _cache, _cache_key = themes, key
  return themes


def theme_list():
  """The names of every available theme."""
  return list(discover().keys())


def options():
  """Theme picker options, as dcc.Dropdown expects them."""
  return [{"label": theme.label, "value": theme.name} for theme in discover().values()]


def get(name):
  """The named theme, or the default one if it does not exist."""
  themes = discover()
  if name in themes:
    return themes[name]
  return themes.get(default_theme)


def exists(name):
  return name in discover()


def resolve(name, fallback=None):
  """
  The name of the theme to use: `name` if it exists, else `fallback`, else the
  default theme.
  """
  themes = discover()
  if name in themes:
    return name
  if fallback in themes:
    return fallback
  return default_theme if default_theme in themes else next(iter(themes), default_theme)


def theme_from_cookie(default=None):
  """
  Resolve the theme to use for the current request: the value stored in the
  odatix_theme cookie by the browser, falling back to `default` (or
  default_theme) if there is no request context, no cookie, or the cookie
  holds an unknown theme.
  """
  try:
    theme = flask.request.cookies.get(cookie_name)
  except RuntimeError:
    theme = None
  return resolve(theme, default)


def user_stylesheet():
  """
  Every user theme, as one stylesheet. Empty when the workspace defines none.
  """
  parts = []
  for theme in discover().values():
    if theme.source != "user":
      continue
    try:
      with open(theme.path, "r") as f:
        parts.append("/* {0} */\n{1}".format(theme.path, f.read()))
    except OSError:
      pass
  return "\n\n".join(parts)


def serve_user_themes(app):
  """
  Serve `user_stylesheet()` at `USER_STYLESHEET_URL` on a Dash app.

  The app must also ask for it, by listing that URL in its
  ``external_stylesheets``. The response is not cached, so editing a theme file
  and refreshing the page is enough to see the change.
  """
  from flask import Response

  def stylesheet():
    response = Response(user_stylesheet(), mimetype="text/css")
    response.headers["Cache-Control"] = "no-store"
    return response

  app.server.add_url_rule(USER_STYLESHEET_URL, "odatix_user_themes", stylesheet)
