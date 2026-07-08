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
Data callbacks: hot reload polling and source selection.
"""

import dash
from dash import Input, Output, State

from odatix.explorer.core.store import STORE
import odatix.explorer.ui.components as components


def register_callbacks():
  @dash.callback(
    Output("xp-data-version", "data"),
    Output("xp-status", "children"),
    Input("xp-poll", "n_intervals"),
    Input("xp-refresh", "n_clicks"),
    Input("odatix-settings", "data"),
    State("xp-data-version", "data"),
  )
  def poll(_intervals, _clicks, settings, current_version):
    """Re-point / rescan the store; bump the page data version on change."""
    if isinstance(settings, dict):
      result_path = settings.get("result_path")
      if result_path:
        STORE.configure(result_path)

    triggered = dash.callback_context.triggered_id
    STORE.poll(force=triggered in ("xp-refresh", "odatix-settings"))

    status = components.status_text(STORE)
    if current_version == STORE.version:
      return dash.no_update, status
    return STORE.version, status

  @dash.callback(
    Output("xp-source-select", "options"),
    Output("xp-source-select", "value"),
    Input("xp-data-version", "data"),
    State("xp-source-select", "value"),
    State("xp-source-select", "options"),
  )
  def update_sources(_version, selected, previous_options):
    """
    Refresh the source list, keeping the user's selection. The first source is
    selected by default; a source appearing while nothing is selected (e.g. a
    first job finishing) is selected automatically.
    """
    names = STORE.source_names()
    errors = {source.name: source.error for source in STORE.sources()}
    options = [{"label": name + (" ⚠" if errors.get(name) else ""), "value": name} for name in names]

    kept = [name for name in selected if name in names] if selected else []
    value = kept if kept else names[:1]

    return options, value
