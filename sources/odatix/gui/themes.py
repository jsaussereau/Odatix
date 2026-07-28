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

import os
import re

import flask

default_theme = "odatix"
cookie_name = "odatix_theme"
_regex_theme = r"\.theme\.(\S+)\s*{"

# Fetch themes from the CSS file
_current_dir = os.path.dirname(os.path.abspath(__file__))
_css_file = os.path.join(_current_dir, "assets", "themes.css")

with open(_css_file, "r") as f:
    _content = f.read()
    _available_theme = re.findall(_regex_theme, _content)

_available_theme = list(_available_theme)
list = _available_theme


def theme_from_cookie(default=None):
    """
    Resolve the theme to use for the current request: the value stored in the
    odatix_theme cookie by the browser, falling back to `default` (or
    default_theme) if there is no request context, no cookie, or the cookie
    holds an unknown theme.
    """
    if default is None or default not in _available_theme:
        default = default_theme
    try:
        theme = flask.request.cookies.get(cookie_name)
    except RuntimeError:
        theme = None
    if theme not in _available_theme:
        theme = default
    return theme
