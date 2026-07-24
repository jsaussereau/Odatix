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
Color palettes, marker symbols and bar patterns used by the chart engine.
"""

import plotly.express as px

# Selectable trace color palettes
PALETTES = {
  "Plotly": px.colors.qualitative.Plotly,
  "D3": px.colors.qualitative.D3,
  "G10": px.colors.qualitative.G10,
  "T10": px.colors.qualitative.T10,
  "Bold": px.colors.qualitative.Bold,
  "Vivid": px.colors.qualitative.Vivid,
  "Safe": px.colors.qualitative.Safe,
  "Pastel": px.colors.qualitative.Pastel,
  "Prism": px.colors.qualitative.Prism,
  "Dark24": px.colors.qualitative.Dark24,
  "Light24": px.colors.qualitative.Light24,
  "Alphabet": px.colors.qualitative.Alphabet,
}

DEFAULT_PALETTE = "Plotly"

MARKER_SYMBOLS = ["circle", "square", "diamond", "cross", "x", "triangle-up", "triangle-down", "pentagon", "star"]
MARKER_SYMBOLS_3D = ["circle", "square", "diamond", "cross", "x", "circle-open", "diamond-open", "square-open"]
BAR_PATTERNS = ["", "/", "x", "-", "|", "+", ".", "\\"]

GREYED_COLOR = "#aaa"


def palette_colors(palette):
  return PALETTES.get(palette, PALETTES[DEFAULT_PALETTE])


def get_color(i, palette=DEFAULT_PALETTE):
  """Color of index i in a palette; -1 means greyed out."""
  if i is None or i < 0:
    return GREYED_COLOR
  colors = palette_colors(palette)
  return colors[i % len(colors)]


def get_marker_symbol(i):
  if i is None or i < 0:
    return MARKER_SYMBOLS[0]
  return MARKER_SYMBOLS[i % len(MARKER_SYMBOLS)]


def get_marker_symbol_3d(i):
  if i is None or i < 0:
    return MARKER_SYMBOLS_3D[0]
  return MARKER_SYMBOLS_3D[i % len(MARKER_SYMBOLS_3D)]


def get_bar_pattern(i):
  if i is None or i < 0:
    return BAR_PATTERNS[0]
  return BAR_PATTERNS[i % len(BAR_PATTERNS)]
