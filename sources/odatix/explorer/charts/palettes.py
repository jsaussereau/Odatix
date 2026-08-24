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

import plotly.colors as plotly_colors

# Selectable trace color palettes
PALETTES = {
  "Plotly": plotly_colors.qualitative.Plotly,
  "D3": plotly_colors.qualitative.D3,
  "G10": plotly_colors.qualitative.G10,
  "T10": plotly_colors.qualitative.T10,
  "Bold": plotly_colors.qualitative.Bold,
  "Vivid": plotly_colors.qualitative.Vivid,
  "Safe": plotly_colors.qualitative.Safe,
  "Pastel": plotly_colors.qualitative.Pastel,
  "Prism": plotly_colors.qualitative.Prism,
  "Dark24": plotly_colors.qualitative.Dark24,
  "Light24": plotly_colors.qualitative.Light24,
  "Alphabet": plotly_colors.qualitative.Alphabet,
}

DEFAULT_PALETTE = "Plotly"

MARKER_SYMBOLS = ["circle", "square", "diamond", "cross", "x", "triangle-up", "triangle-down", "pentagon", "star"]
MARKER_SYMBOLS_3D = ["circle", "square", "diamond", "cross", "x", "circle-open", "diamond-open", "square-open"]
BAR_PATTERNS = ["", "/", "x", "-", "|", "+", ".", "\\"]

GREYED_COLOR = "#aaa"
HIGHLIGHT_COLOR = "#FFD43B"


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
