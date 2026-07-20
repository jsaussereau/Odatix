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


# Sidebar tabs. Every control lives on every page in a fixed DOM (the single
# figure callback needs a fixed set of inputs), so tabs must never remove their
# panels from the DOM. Tab switching is done client-side by toggling a class on
# the sidebar content (see callbacks/controls.py), which drives panel visibility
# through CSS. The tab bar is sticky so tabs stay reachable when scrolled down.
_TABS = (("data", "Plot"), ("filters", "Filters"), ("export", "Save"))
DEFAULT_TAB = "data"


def _tab_bar():
  buttons = [
    html.Button(
      label,
      id="xp-tab-btn-" + key,
      n_clicks=0,
      className="xp-tab-label" + (" xp-tab-active" if key == DEFAULT_TAB else ""),
    )
    for key, label in _TABS
  ]
  return [
    dcc.Store(id="xp-active-tab", data=DEFAULT_TAB, storage_type="session"),
    html.Div(buttons, className="xp-tabs"),
  ]


def _data_section():
  """Shared "Data" section: live status, reload button and source selector."""
  return components.section("Data", [
    html.Div(
      [
        html.Div(id="xp-status", className="xp-status"),
        html.Button("⟳", id="xp-refresh", n_clicks=0, className="xp-mini-button xp-refresh", title="Reload result files now"),
      ],
      className="xp-status-row",
    ),
    # Remembered via xp-ui-state (not Dash persistence) so that saved-view
    # restores can overwrite it — likewise for palette, plot theme, toggles,
    # overview and export options below.
    dcc.Checklist(id="xp-source-select", options=[], value=None, className="xp-filter-checklist"),
  ])


def build_sidebar(kind):
  capabilities = CAPABILITIES[kind]
  axes = capabilities["axes"]
  is_scatter = kind in ("scatter", "scatter3d")
  is_overview = kind == "overview"
  is_table = kind == "table"

  toggles = [toggle for toggle in capabilities["toggles"]] + ["stable_index"]
  toggle_options = [{"label": TOGGLE_LABELS.get(toggle, toggle), "value": toggle} for toggle in toggles]
  toggle_defaults = [toggle for toggle in toggles if toggle in DEFAULT_TOGGLES or toggle == "stable_index"]

  axes_section = (
      # --- Axes ---
      components.section("Axes", [
        components.control_row("Chart type", _dropdown(
          "xp-overview-chart-type",
          options=[{"label": label, "value": value} for value, label in (("lines", "Lines"), ("columns", "Columns"), ("radar", "Radar"))],
          value="lines",
          persist=False,
        ), hidden=not is_overview),
        components.control_row("X axis" if not is_scatter else "X metric", _dropdown("xp-axis-x"), hidden="x" not in axes and not is_overview),
        components.control_row("Y metric", _dropdown("xp-axis-y"), hidden="y" not in axes),
        components.control_row("Z metric", _dropdown("xp-axis-z"), hidden="z" not in axes),
        components.control_row("Layout", _dropdown(
          "xp-overview-layout",
          options=[{"label": name, "value": name} for name in OVERVIEW_LAYOUTS],
          value="default",
          persist=False,
        ), hidden=not is_overview),
      ])
  )

  style_section = (
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
          persist=False,
        )),
        components.control_row("Plot theme", _dropdown(
          "xp-plot-theme",
          options=[{"label": name, "value": name} for name in plot_themes.plot_theme_names()],
          value=plot_themes.DEFAULT_PLOT_THEME,
          persist=False,
        ), tooltip="Look of the figures, independent from the app theme"),
      ])
  )

  display_section = (
      # --- Display ---
      components.section("Display", [
        dcc.Checklist(
          id="xp-toggles",
          options=toggle_options,
          value=toggle_defaults,
          className="xp-toggle-checklist",
        ),
      ], open=True)
  )

  if is_table:
    # The table has its own "Columns" section. The chart controls (axes, style,
    # toggles) are irrelevant here, but must stay mounted: the shared filter,
    # figure and control callbacks list them as inputs and would not fire on a
    # page where they are absent (the app suppresses callback exceptions). So we
    # keep them in the DOM, hidden.
    data_children = [
      _data_section(),
      components.section("Columns", [
        components.control_row("Show columns", _dropdown(
          "xp-table-columns",
          multi=True,
          clearable=True,
          placeholder="All columns",
        ), tooltip="Pick which columns to display (empty = all), in the order shown."),
        html.Div(
          "Click a header to sort. Type in a header's filter box to filter that column "
          "(e.g. \"> 100\" on a numeric column). Use the Filters tab to filter by dimension.",
          className="xp-hint",
        ),
      ]),
      html.Div([axes_section, style_section, display_section], style={"display": "none"}),
    ]
  else:
    data_children = [_data_section(), axes_section, style_section, display_section]

  data_panel = html.Div(data_children, className="xp-tab-panel xp-tab-panel-data")

  filters_panel = html.Div(
    [
      # --- Filters ---
      html.Div(id="xp-filter-panel"),
    ],
    className="xp-tab-panel xp-tab-panel-filters",
  )

  export_panel = html.Div(
    [
      # --- Export ---
      components.section("Export", [
        components.control_row("Image format", _dropdown(
          "xp-dl-format",
          options=[{"label": fmt.upper(), "value": fmt} for fmt in ("svg", "png", "jpeg", "webp")],
          value="svg",
          persist=False,
        ), hidden=is_table),
        components.control_row("Image background", _dropdown(
          "xp-dl-background",
          options=[{"label": "Transparent", "value": "transparent"}, {"label": "White", "value": "white"}, {"label": "Theme", "value": "theme"}],
          value="transparent",
          persist=False,
        ), hidden=is_table),
        html.Button("Download CSV", id="xp-download-csv", n_clicks=0, className="xp-button", title="Export the currently displayed data as CSV"),
      ]),

      # --- Saved views ---
      components.section("Saved views", [
        components.control_row("Name", dcc.Input(
          id="xp-view-name",
          type="text",
          value="",
          debounce=True,
          className="xp-text-input",
        ), tooltip="Name of the view to save (a default is proposed)"),
        components.control_row("Description", dcc.Textarea(
          id="xp-view-description",
          value="",
          placeholder="Optional description...",
          className="xp-text-input xp-textarea",
        ), tooltip="Optional description shown on the home-page view card"),
        html.Button("Save current view", id="xp-view-save", n_clicks=0, className="xp-button",
                    title="Save the whole display state (sources, axes, style, filters, ...) as a shareable file"),
        components.control_row("Restore a view", _dropdown(
          "xp-view-select",
          persist=False,
          placeholder="Select a saved view...",
          clearable=True,
        ), tooltip="Selecting a view restores the exact display state it was saved with"),
        html.Div(id="xp-view-status", className="xp-view-status"),
      ]),
    ],
    className="xp-tab-panel xp-tab-panel-export",
  )

  return html.Div(
    _tab_bar() + [data_panel, filters_panel, export_panel],
    id="xp-sidebar-content",
    className="xp-sidebar-content xp-tab-active-" + DEFAULT_TAB,
  )
