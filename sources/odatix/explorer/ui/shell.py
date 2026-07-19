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
Page shell of the explorer chart pages: control sidebar + chart area +
page-local stores and the hot-reload interval. The whole explorer UI lives
inside the page layout, so it embeds into any host app (Odatix GUI or the
standalone shell) without touching the host layout.
"""

from dash import dcc, html

import odatix.explorer.ui.sidebar as sidebar

POLL_INTERVAL_MS = 2000


def explorer_state_stores():
  """
  Session stores that must survive navigation between chart pages (lines,
  columns, scatter, ...). They live in the host root layout, outside
  dash.page_container, so switching chart kind — which swaps the page but not
  the root layout — does not remount and reset them. Per-page stores would be
  clobbered by their own rebuild callbacks on every navigation.

  Every host embedding the explorer (Odatix GUI and the standalone shell) must
  include these in its root layout.
  """
  return [
    dcc.Store(id="xp-filter-state", data={}, storage_type="session"),
    dcc.Store(id="xp-control-state", data={}, storage_type="session"),
    # Sources, palette, toggles, export options... — everything not covered by
    # the two stores above. Unlike Dash persistence (which only records user
    # edits), this store can be written by the saved-view restore callbacks.
    dcc.Store(id="xp-ui-state", data={}, storage_type="session"),
    # Bumped by a saved-view restore to force update_control_options to re-derive
    # the axis/style dropdowns from the freshly written xp-control-state, even
    # when the restored view keeps the same sources (so no other input changes).
    dcc.Store(id="xp-restore-trigger", data=0, storage_type="session"),
  ]


def explorer_shell(kind):
  if kind == "overview":
    graph_area = html.Div(id="xp-overview-area", className="xp-overview-area")
  else:
    graph_area = dcc.Graph(
      id="xp-graph",
      className="xp-graph",
      figure={},
      config={"displaylogo": False},
      style={"height": "100%"},
    )

  return html.Div(
    [
      dcc.Store(id="xp-chart-kind", data=kind),
      dcc.Store(id="xp-data-version", data=-1),
      dcc.Interval(id="xp-poll", interval=POLL_INTERVAL_MS),
      dcc.Download(id="xp-download"),
      # Navigation target of the saved-view restore (view of another chart kind).
      # refresh=True forces a full reload: the target page then rehydrates the
      # session stores (xp-control-state, ...) from sessionStorage and mounts
      # already restored — a plain SPA route swap can mount the new page before
      # the freshly written stores propagate, showing stale controls.
      dcc.Location(id="xp-url", refresh=True),
      html.Div(sidebar.build_sidebar(kind), id="xp-sidebar", className="xp-sidebar"),
      html.Div(
        [
          html.Div(id="xp-error"),
          html.Div(graph_area, id="xp-graph-area", className="xp-graph-area"),
        ],
        className="xp-content",
      ),
    ],
    className="xp-page",
  )
