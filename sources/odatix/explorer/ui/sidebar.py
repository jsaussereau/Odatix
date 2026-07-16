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
The Odatix Explorer control sidebar.

Every control exists on every chart page (the single figure callback needs a
fixed set of inputs); controls irrelevant to the page's chart kind are
statically hidden. Options that depend on the data (axes, dimensions,
filters) are populated by callbacks.
"""

from dash import dcc, html

import odatix.explorer.charts.palettes as palettes
import odatix.explorer.charts.plot_themes as plot_themes
from odatix.explorer.charts.spec import CAPABILITIES, TOGGLE_LABELS, DEFAULT_TOGGLES, OVERVIEW_LAYOUTS
import odatix.explorer.ui.components as components

_PERSIST = dict(persistence=True, persistence_type="session")


def _dropdown(id, options=None, value=None, clearable=False, persist=True, **kwargs):
  extra = dict(_PERSIST) if persist else {}
  extra.update(kwargs)
  return dcc.Dropdown(id=id, options=options or [], value=value, clearable=clearable, className="xp-dropdown", style={"width": "100%"}, **extra)


def build_sidebar(kind):
  capabilities = CAPABILITIES[kind]
  axes = capabilities["axes"]
  is_scatter = kind in ("scatter", "scatter3d")
  is_overview = kind == "overview"

  toggles = [toggle for toggle in capabilities["toggles"]] + ["stable_index"]
  toggle_options = [{"label": TOGGLE_LABELS.get(toggle, toggle), "value": toggle} for toggle in toggles]
  toggle_defaults = [toggle for toggle in toggles if toggle in DEFAULT_TOGGLES or toggle == "stable_index"]

  return html.Div(
    [
      # --- Data ---
      components.section("Data", [
        html.Div(
          [
            html.Div(id="xp-status", className="xp-status"),
            html.Button("⟳", id="xp-refresh", n_clicks=0, className="xp-mini-button xp-refresh", title="Reload result files now"),
          ],
          className="xp-status-row",
        ),
        dcc.Checklist(id="xp-source-select", options=[], value=None, className="xp-filter-checklist", **_PERSIST),
      ]),

      # --- Axes ---
      components.section("Axes", [
        components.control_row("Chart type", _dropdown(
          "xp-overview-chart-type",
          options=[{"label": label, "value": value} for value, label in (("lines", "Lines"), ("columns", "Columns"), ("radar", "Radar"))],
          value="lines",
        ), hidden=not is_overview),
        components.control_row("X axis" if not is_scatter else "X metric", _dropdown("xp-axis-x"), hidden="x" not in axes and not is_overview),
        components.control_row("Y metric", _dropdown("xp-axis-y"), hidden="y" not in axes),
        components.control_row("Z metric", _dropdown("xp-axis-z"), hidden="z" not in axes),
        components.control_row("Layout", _dropdown(
          "xp-overview-layout",
          options=[{"label": name, "value": name} for name in OVERVIEW_LAYOUTS],
          value="default",
        ), hidden=not is_overview),
      ]),

      # --- Style ---
      components.section("Style", [
        components.control_row("Color by", _dropdown("xp-color-by")),
        components.control_row("Pattern by" if kind == "columns" else "Symbol by", _dropdown("xp-symbol-by")),
        components.control_row("Group legend by", _dropdown("xp-legend-group-by")),
        components.control_row("Dissociate", _dropdown("xp-dissociate-by"), tooltip="Split one dimension into separate traces"),
        components.control_row("Palette", _dropdown(
          "xp-palette",
          options=[{"label": name, "value": name} for name in palettes.PALETTES],
          value=palettes.DEFAULT_PALETTE,
        )),
        components.control_row("Plot theme", _dropdown(
          "xp-plot-theme",
          options=[{"label": name, "value": name} for name in plot_themes.plot_theme_names()],
          value=plot_themes.DEFAULT_PLOT_THEME,
        ), tooltip="Look of the figures, independent from the app theme"),
      ]),

      # --- Filters ---
      components.section("Filters", [html.Div(id="xp-filter-panel")]),

      # --- Display ---
      components.section("Display", [
        dcc.Checklist(
          id="xp-toggles",
          options=toggle_options,
          value=toggle_defaults,
          className="xp-toggle-checklist",
          **_PERSIST,
        ),
      ], open=False),

      # --- Export ---
      components.section("Export", [
        components.control_row("Image format", _dropdown(
          "xp-dl-format",
          options=[{"label": fmt.upper(), "value": fmt} for fmt in ("svg", "png", "jpeg", "webp")],
          value="svg",
        )),
        components.control_row("Image background", _dropdown(
          "xp-dl-background",
          options=[{"label": "Transparent", "value": "transparent"}, {"label": "White", "value": "white"}, {"label": "Theme", "value": "theme"}],
          value="transparent",
        )),
        html.Button("Download CSV", id="xp-download-csv", n_clicks=0, className="xp-button", title="Export the currently displayed data as CSV"),
      ], open=False),
    ],
    className="xp-sidebar-content",
  )
