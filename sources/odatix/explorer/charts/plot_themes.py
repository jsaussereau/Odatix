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
PLOT themes: the look of the figures themselves, independent from the app
theme.

The default plot theme, "auto", renders figures with transparent backgrounds
and text/grid colors taken from the current app theme (see app_theme_bridge),
so plots always blend into the page. The other plot themes force a specific
Plotly template (with its own backgrounds), which is useful to preview or
export figures with a fixed look regardless of the app theme.
"""

import copy

import plotly.graph_objects as go
import plotly.io as pio

AUTO = "auto"
DEFAULT_PLOT_THEME = AUTO

# name -> plotly template name (registered below when custom)
_PLOT_THEMES = {
  AUTO: None,
  "plotly": "plotly",
  "plotly_white": "plotly_white",
  "plotly_dark": "plotly_dark",
  "seaborn": "seaborn",
  "ggplot2": "ggplot2",
  "simple_white": "simple_white",
  "odatix_light": "odatix_light",
  "odatix_dark": "odatix_dark",
  "odatix_darker": "odatix_darker",
  "code_dark": "code_dark",
  "candy": "candy",
  "gradient": "gradient",
}


def _register_template(name, base, paper_bgcolor, plot_bgcolor, **extra):
  pio.templates[name] = go.layout.Template(
    layout=copy.deepcopy(pio.templates[base].layout).update(
      paper_bgcolor=paper_bgcolor,
      plot_bgcolor=plot_bgcolor,
      polar_bgcolor=plot_bgcolor,
      **extra,
    )
  )


_register_template("odatix_light", "plotly_white", "#ffffff", "#ffffff")
_register_template("odatix_dark", "plotly_dark", "#24292e", "#24292e")
_register_template("odatix_darker", "plotly_dark", "#24292e", "#181b20")
_register_template("code_dark", "plotly_dark", "#252526", "#252526")
_register_template("candy", "plotly", "#954DC5", "#6D13A8", barcornerradius=10000)
_register_template("gradient", "plotly_white", "#ffffff", "#ffffff")


def plot_theme_names():
  return list(_PLOT_THEMES)


def get_template(plot_theme):
  """Plotly template name for a plot theme, or None for "auto"."""
  if plot_theme not in _PLOT_THEMES:
    return None
  return _PLOT_THEMES[plot_theme]
