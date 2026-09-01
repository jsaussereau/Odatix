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
Bridge between APP themes and plot rendering.

App themes are CSS files in odatix/gui/assets/themes/ and in the workspace theme
directory (shared with Odatix GUI); Plotly figures cannot read CSS variables, so
this module reads the small set of colors ("chrome") each theme declares in its
`odatix-theme` header — text color, grid color and a dark/light flag — and hands
them to the figure builders, which then blend into the page. Figure backgrounds
stay transparent so the page background shows through, whatever the theme.

A theme that declares no plot colors falls back to LIGHT_CHROME / DARK_CHROME
according to its `dark:` field, so a user theme needs nothing more than that
line to get readable figures.
"""

import odatix.gui.themes as themes

# Re-exported: the defaults a theme's header overrides, and what an unknown
# theme name gets.
LIGHT_CHROME = themes.LIGHT_CHROME
DARK_CHROME = themes.DARK_CHROME


def get_chrome(app_theme):
  """Plot chrome (text/grid colors, dark flag) for an app theme name."""
  theme = themes.get(str(app_theme))
  if theme is None:
    return LIGHT_CHROME
  return theme.chrome


def is_dark(app_theme):
  return get_chrome(app_theme)["dark"]


def dark_themes():
  """The names of every dark theme, builtin or user-defined."""
  return {name for name, theme in themes.discover().items() if theme.dark}
