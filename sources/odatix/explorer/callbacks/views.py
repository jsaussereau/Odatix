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
Saved-view callbacks: save the whole display state to a shareable JSON file,
and restore one from the sidebar dropdown (see also pages/home.py for the
home-page view cards).

Restoring writes the three session stores (xp-control-state, xp-filter-state,
xp-ui-state) — the same mechanism that re-applies the state at every page
mount — plus the live component values for an instant same-page restore. When
the view belongs to another chart kind, xp-url navigates there and the page
mount does the rest.
"""

import datetime
import time

import dash
from dash import Input, Output, State, ALL, html

from odatix.explorer.core.store import STORE
import odatix.explorer.core.query as query
import odatix.explorer.core.views as views
from odatix.explorer.callbacks.filters import build_filters_dict

# UI-state keys of a sanitized view payload, in remember_ui_state order
_UI_KEYS = ("sources", "palette", "plot_theme", "toggles", "overview_chart_type", "overview_layout", "dl_format", "dl_background")


def view_options():
  return [{"label": view["name"], "value": view["name"]} for view in views.list_views(STORE.result_path)]


def restore_payload(name):
  """Load + sanitize a view; returns (payload, ui_state patch, warnings)."""
  view = views.load_view(STORE.result_path, name)
  payload, warnings = views.sanitize_view(view, STORE)
  ui_patch = {key: payload[key] for key in _UI_KEYS}
  ui_patch["view_notice"] = notice_data(payload["name"], warnings)
  return payload, ui_patch, warnings


def notice_data(name, warnings):
  return {"name": name, "warnings": warnings, "time": datetime.datetime.now().strftime("%H:%M:%S")}


def notice_children(notice):
  """Render the last restore notice (name + sanitization warnings)."""
  if not notice or not notice.get("name"):
    return None
  children = [html.Div('Restored view "' + str(notice["name"]) + '" at ' + str(notice.get("time", "")), className="xp-view-ok")]
  for warning in notice.get("warnings") or []:
    children.append(html.Div("⚠ " + str(warning), className="xp-view-warning"))
  return children


def register_callbacks():
  @dash.callback(
    Output("xp-view-select", "options"),
    Input("xp-poll", "n_intervals"),
    Input("xp-data-version", "data"),
    State("xp-view-select", "options"),
  )
  def refresh_view_options(_intervals, _version, previous):
    options = view_options()
    if options == (previous or []):
      return dash.no_update
    return options

  @dash.callback(
    Output("xp-view-name", "placeholder"),
    Input("xp-axis-y", "value"),
    Input("xp-source-select", "value"),
    State("xp-chart-kind", "data"),
  )
  def suggest_view_name(y, sources, kind):
    """Propose a coherent default name: kind, main metric, date."""
    parts = [str(kind or "view")]
    if kind != "overview" and y:
      parts.append(str(y))
    elif sources:
      parts.append("-".join(sources[:2]))
    parts.append(datetime.date.today().isoformat())
    return views.slugify("_".join(parts))

  @dash.callback(
    Output("xp-view-status", "children"),
    Input("xp-data-version", "data"),
    State("xp-ui-state", "data"),
  )
  def show_view_notice(_version, ui_state):
    """Re-show the last restore outcome at page mount (e.g. after navigation)."""
    return notice_children((ui_state or {}).get("view_notice"))

  @dash.callback(
    Output("xp-view-status", "children", allow_duplicate=True),
    Output("xp-view-select", "options", allow_duplicate=True),
    Input("xp-view-save", "n_clicks"),
    State("xp-view-name", "value"),
    State("xp-view-name", "placeholder"),
    State("xp-chart-kind", "data"),
    State("xp-source-select", "value"),
    State("xp-axis-x", "value"),
    State("xp-axis-y", "value"),
    State("xp-axis-z", "value"),
    State("xp-color-by", "value"),
    State("xp-symbol-by", "value"),
    State("xp-legend-group-by", "value"),
    State("xp-dissociate-by", "value"),
    State("xp-palette", "value"),
    State("xp-plot-theme", "value"),
    State("xp-toggles", "value"),
    State("xp-overview-chart-type", "value"),
    State("xp-overview-layout", "value"),
    State("xp-dl-format", "value"),
    State("xp-dl-background", "value"),
    State("xp-filter-state", "data"),
    State({"type": "xp-filter", "dim": ALL}, "value"),
    State({"type": "xp-filter", "dim": ALL}, "id"),
    prevent_initial_call=True,
  )
  def save_current_view(n_clicks, name, suggested, kind, sources, x, y, z, color_by, symbol_by,
                        legend_group_by, dissociate, palette, plot_theme, toggles,
                        overview_chart_type, overview_layout, dl_format, dl_background,
                        filter_state, filter_values, filter_ids):
    if not n_clicks:
      raise dash.exceptions.PreventUpdate

    name = (name or "").strip() or (suggested or "")
    try:
      # Hidden filter values must be listed against the unfiltered selection
      base_df = query.select_dataframe(STORE, sources=sources)
      base_dimensions, _ = query.discover(base_df, STORE, sources)

      filters = build_filters_dict(filter_values, filter_ids)
      df = query.select_dataframe(STORE, sources=sources, filters=filters)
      dimensions, _ = query.discover(df, STORE, sources)

      thumb_kind = overview_chart_type if kind == "overview" else kind
      view = {
        "name": name,
        "kind": kind,
        "sources": sources or [],
        "controls": {
          "x": x, "y": y, "z": z,
          "color_by": color_by, "symbol_by": symbol_by,
          "legend_group_by": legend_group_by, "dissociate": dissociate,
        },
        "filters": views.filters_to_hidden(filter_state, base_dimensions),
        "palette": palette,
        "plot_theme": plot_theme,
        "toggles": toggles or [],
        "overview": {"chart_type": overview_chart_type, "layout": overview_layout},
        "export": {"format": dl_format, "background": dl_background},
        "thumb": views.make_thumbnail(df, thumb_kind, x, y, color_by, dimensions),
      }
      slug = views.save_view(STORE.result_path, name, view)
    except (OSError, ValueError) as e:
      return [html.Div("⚠ Could not save the view: " + str(e), className="xp-view-warning")], dash.no_update

    status = [html.Div('Saved as "' + slug + '.json" — copy this file to share the view', className="xp-view-ok")]
    return status, view_options()

  @dash.callback(
    Output("xp-control-state", "data", allow_duplicate=True),
    Output("xp-filter-state", "data", allow_duplicate=True),
    Output("xp-ui-state", "data", allow_duplicate=True),
    Output("xp-source-select", "value", allow_duplicate=True),
    Output("xp-palette", "value", allow_duplicate=True),
    Output("xp-plot-theme", "value", allow_duplicate=True),
    Output("xp-toggles", "value", allow_duplicate=True),
    Output("xp-overview-chart-type", "value", allow_duplicate=True),
    Output("xp-overview-layout", "value", allow_duplicate=True),
    Output("xp-dl-format", "value", allow_duplicate=True),
    Output("xp-dl-background", "value", allow_duplicate=True),
    Output("xp-view-status", "children", allow_duplicate=True),
    Output("xp-restore-trigger", "data", allow_duplicate=True),
    Output("xp-url", "pathname"),
    Input("xp-view-select", "value"),
    State("xp-chart-kind", "data"),
    State("xp-ui-state", "data"),
    prevent_initial_call=True,
  )
  def restore_view(name, kind, ui_state):
    if not name:
      raise dash.exceptions.PreventUpdate
    try:
      payload, ui_patch, warnings = restore_payload(name)
    except ValueError as e:
      status = [html.Div("⚠ Could not restore the view: " + str(e), className="xp-view-warning")]
      return (dash.no_update,) * 11 + (status, dash.no_update, dash.no_update)

    ui_state = dict(ui_state or {})
    ui_state.update(ui_patch)
    same_kind = payload["kind"] == kind
    # Same page: nudge update_control_options to re-derive the axis dropdowns
    # from the freshly written xp-control-state. Different page: the target page
    # remounts and re-derives on its own, so no nudge (and no navigation clash).
    pathname = dash.no_update if same_kind else "/explorer/" + payload["kind"]
    trigger = time.time() if same_kind else dash.no_update

    return (
      payload["controls"],
      payload["filter_state"],
      ui_state,
      payload["sources"],
      payload["palette"],
      payload["plot_theme"],
      payload["toggles"],
      payload["overview_chart_type"],
      payload["overview_layout"],
      payload["dl_format"],
      payload["dl_background"],
      notice_children(ui_patch["view_notice"]),
      trigger,
      pathname,
    )
