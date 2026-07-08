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

App themes are CSS classes defined in odatix/gui/assets/themes.css (shared
with Odatix GUI); Plotly figures cannot read CSS variables, so this module
maps each app theme name to the small set of colors ("chrome") needed to
render figures that blend into the page: text color, grid color and a
dark/light flag. Figure backgrounds stay transparent so the page background
shows through, whatever the theme.
"""

# Chrome values mirror --theme-text-color / --theme-background-color of each
# theme in gui/assets/themes.css. Themes absent from this map fall back to
# LIGHT_CHROME / DARK_CHROME depending on DARK_THEMES.

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

APP_THEME_CHROME = {
  "odatix": LIGHT_CHROME,
  "odatix_dark": DARK_CHROME,
  "odatix_darker": DARK_CHROME,
  "catpuccin": {**DARK_CHROME, "text_color": "#cdd6f4"},
  "dracula": {**DARK_CHROME, "text_color": "#f8f8f2"},
  "code_dark": DARK_CHROME,
  "rainbow": LIGHT_CHROME,
  "galaxy": {**DARK_CHROME, "text_color": "#f8f3ff"},
  "midnight": {**DARK_CHROME, "text_color": "#e0e0ff"},
  "win95": {**LIGHT_CHROME, "text_color": "#000000"},
  "hangover": LIGHT_CHROME,
  "legacy": LIGHT_CHROME,
}

DARK_THEMES = {name for name, chrome in APP_THEME_CHROME.items() if chrome["dark"]}


def get_chrome(app_theme):
  """Plot chrome (text/grid colors, dark flag) for an app theme name."""
  return APP_THEME_CHROME.get(str(app_theme), LIGHT_CHROME)


def is_dark(app_theme):
  return get_chrome(app_theme)["dark"]
