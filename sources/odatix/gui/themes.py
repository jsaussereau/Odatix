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

import plotly.graph_objects as go
import plotly.io as pio
import copy

default_theme = "plotly"
templates = pio.templates

themes = {
  "code_dark": {
    "base_template": "plotly_dark",
    "nav_bgcolor": "#1e1e1e",
    "page_bgcolor": "#252526",
    "plot_bgcolor": "#252526",
    "button_color":" #aaaaaa",
    "button_active_color": "#ffffff",
  },
  "odatix_darker": { 
    "base_template": "plotly_dark",
    "nav_bgcolor":"#0b0b0b",
    "page_bgcolor": "#24292e",
    "plot_bgcolor": "#181b20",
    "button_color":" #aaaaaa",
    "button_active_color": "#ffffff",
  },
  "odatix_dark": { 
    "nav_bgcolor":"#181b20",
    "base_template": "plotly_dark",
    "page_bgcolor": "#24292e",
    "plot_bgcolor": "#24292e",
    "button_color":" #aaaaaa",
    "button_active_color": "#ffffff",
  },
  "plotly_dark": {
    "base_template": None,
    "nav_bgcolor":"#0b0b0b",
    "page_bgcolor": "#111111",
    "plot_bgcolor": "#111111",
    "button_color":" #aaaaaa",
    "button_active_color": "#ffffff",
  },
  "default": {
    "base_template": None,
    "nav_bgcolor":"#24292e",
    "page_bgcolor": "#ffffff",
    "plot_bgcolor": "#ffffff",
    "button_color":" #aaaaaa",
    "button_active_color": "#ffffff",
  },
}

def get_page_bgcolor(theme, default=themes["default"]["page_bgcolor"]):
  if theme in themes:
    return themes[theme]["page_bgcolor"]
  else:
    return default

def get_nav_bgcolor(theme, default=themes["default"]["nav_bgcolor"]):
  if theme in themes:
    return themes[theme]["nav_bgcolor"]
  else:
    return default

def get_plot_bgcolor(theme, default=themes["default"]["plot_bgcolor"]):
  if theme in themes:
    return themes[theme]["plot_bgcolor"]
  else:
    return default

def get_button_color(theme, default=themes["default"]["button_color"]):
  if theme in themes:
    return themes[theme]["button_color"]
  else:
    return default

def get_button_active_color(theme, default=themes["default"]["button_active_color"]):
  if theme in themes:
    return themes[theme]["button_active_color"]
  else:
    return default


templates["code_dark"] = go.layout.Template(
  layout = copy.deepcopy(templates["plotly_dark"].layout).update(
    paper_bgcolor=get_page_bgcolor("code_dark"),
    plot_bgcolor=get_plot_bgcolor("code_dark"),
    polar_bgcolor=get_plot_bgcolor("code_dark"),
  )
)

templates["odatix_darker"] = go.layout.Template(
  layout = copy.deepcopy(templates["plotly_dark"].layout).update(
    paper_bgcolor=get_page_bgcolor("odatix_darker"),
    plot_bgcolor=get_plot_bgcolor("odatix_darker"),
    polar_bgcolor=get_plot_bgcolor("odatix_darker"),
  )
)

templates["odatix_dark"] = go.layout.Template(
  layout = copy.deepcopy(templates["plotly_dark"].layout).update(
    paper_bgcolor=get_page_bgcolor("odatix_dark"),
    plot_bgcolor=get_plot_bgcolor("odatix_dark"),
    polar_bgcolor=get_plot_bgcolor("odatix_dark"),
  )
)

#2b2929
#565c64