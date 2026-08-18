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
Insights gallery: charts the explorer proposes on its own.

core.recommend measures the data and returns ranked view payloads, in the very
same shape as a hand-saved view file. Nothing here is stored: a card is opened
by writing the session stores and navigating to its chart page (exactly what
the home-page saved-view cards do), and only an explicit "Save" turns one into
a real view file.

The source chips narrow what gets measured, not what gets displayed: a mixed
workspace recommends the loudest source's metrics, and picking one source is
how the user asks the engine to look somewhere else. Within that selection the
engine carves its own scopes (one per source, plus one comparing the tools that
ran the same designs), so a card always describes a slice that holds together
rather than an average of unrelated result files.
"""

import dash
from dash import dcc, html, Input, Output, State, ALL

from odatix.components import home_shared
from odatix.explorer.core.store import STORE
import odatix.explorer.core.query as query
import odatix.explorer.core.recommend as recommend
import odatix.explorer.core.schema as schema
import odatix.explorer.core.views as views
import odatix.explorer.callbacks.views as views_callbacks
from odatix.explorer.ui.thumbnails import view_thumbnail

# The gallery recomputes only when the data or the source selection changed, so
# this can poll often.
POLL_INTERVAL = 3000

# Source names listed on a card before they collapse into a "+n" tag.
MAX_SOURCE_TAGS = 3


def default_filters(store, sources):
  """
  The selection the chart pages start from: everything except the values
  unchecked by default (the intermediate steps of a multi-step flow), which
  would otherwise double every curve.
  """
  df = query.select_dataframe(store, sources=sources)
  dimensions, _metrics = query.discover(df, store, sources)
  filters = {}
  for dimension, values in dimensions.items():
    kept = [value for value in values if schema.default_selected(dimension, value)]
    if len(kept) != len(values):
      filters[dimension] = kept
  return filters


def selected_sources(selection, available):
  """The sources to measure: the chip selection, minus whatever vanished.

  An empty or stale selection means "everything", which is also the state the
  page starts in.
  """
  chosen = [name for name in (selection or []) if name in available]
  return chosen or list(available)


######################################
# Source filter chips
######################################


def _source_chip(value, label, active):
  return html.Button(
    label,
    id={"type": "xp-insights-source", "name": value},
    n_clicks=0,
    type="button",
    className="xp-chip" + (" xp-chip-active" if active else ""),
  )


def _source_chips(available, selection):
  """"All sources" plus one toggle per source. Hidden when there is only one."""
  if len(available) < 2:
    return []
  chosen = [name for name in (selection or []) if name in available]
  chips = [_source_chip("all", "All sources", not chosen)]
  for name in available:
    chips.append(_source_chip(name, name, name in chosen))
  return chips


######################################
# Cards
######################################


def _source_tags(sources, scope=""):
  """What the chart was measured on: the engine's scope name, or the sources.

  Spelling out ten source names on every card says nothing about the chart and
  is what made the cards unreadable; the full list stays in the tooltip.
  """
  sources = list(sources or [])
  if scope:
    return [html.Span(scope, className="xp-reco-tag xp-reco-tag-scope", title=", ".join(sources) or scope)]
  if len(sources) > MAX_SOURCE_TAGS:
    return [html.Span(str(len(sources)) + " sources", className="xp-reco-tag xp-reco-tag-more", title=", ".join(sources))]
  return [html.Span(name, className="xp-reco-tag", title=name) for name in sources]


def _card(index, reco):
  """One proposal: sketch, chart kind, title, the reason it is worth a look.

  The whole card is clickable through a stretched hit area rather than a button
  wrapping everything, so the Save button can sit inside it (a button inside a
  button is invalid markup and swallows the inner click).
  """
  view = reco.view
  return html.Div(
    [
      html.Button(
        "",
        id={"type": "xp-reco-open", "index": index},
        n_clicks=0,
        type="button",
        className="xp-reco-hit",
        title="Open this chart",
        **{"aria-label": "Open " + str(reco.title)}
      ),
      html.Div(
        [
          html.Div(view_thumbnail(view), className="xp-reco-thumb"),
          html.Span(views.kind_label(view.get("kind")), className="xp-reco-kind"),
        ],
        className="xp-reco-thumb-box",
      ),
      html.Div(
        [
          html.Div(reco.title, className="xp-reco-title", title=reco.title),
          html.Div(reco.why, className="xp-reco-why", title=reco.why),
        ],
        className="xp-reco-body",
      ),
      html.Div(
        [
          html.Div(_source_tags(view.get("sources"), getattr(reco, "scope", "")), className="xp-reco-tags"),
          html.Button(
            "Save",
            id={"type": "xp-reco-save", "index": index},
            n_clicks=0,
            type="button",
            className="xp-reco-save",
            title="Keep this chart as a saved view",
          ),
        ],
        className="xp-reco-foot",
      ),
    ],
    className="xp-reco-card",
  )


def _empty_state(has_sources):
  if has_sources:
    title = "Nothing to recommend for this selection"
    detail = ("The gallery proposes charts once the selected sources hold a metric that actually varies. "
              "Try another source, or widen the selection.")
  else:
    title = "Nothing to recommend yet"
    detail = ("The gallery proposes charts as soon as there are results with at least one metric that varies. "
              "Run a synthesis or a workflow and they appear here.")
  return html.Div(
    [
      html.Div(title, className="xp-source-empty-title"),
      html.Div(detail, className="xp-source-empty-subtitle"),
    ],
    className="xp-source-empty",
  )


######################################
# Page
######################################


def layout(**kwargs):
  return html.Div(
    [
      dcc.Interval(id="xp-insights-poll", interval=POLL_INTERVAL),
      # refresh=True: full reload so the target chart page rehydrates the
      # session stores written by open_recommendation (see pages/home.py).
      dcc.Location(id="xp-insights-url", refresh=True),
      dcc.Store(id="xp-insights-views", data={}),
      dcc.Store(id="xp-insights-sources", data=[], storage_type="session"),
      home_shared.home_header("Insights", "Charts Odatix suggests from what your results actually contain."),
      html.Div(
        [
          html.Div("Sources", className="xp-insights-bar-label"),
          html.Div(id="xp-insights-chips", className="xp-chips"),
        ],
        id="xp-insights-bar",
        className="xp-insights-bar",
      ),
      html.Div(id="xp-insights-status", className="xp-insights-status"),
      html.Div(id="xp-insights-grid", className="xp-home-section"),
    ],
    className="xp-home xp-insights",
  )


dash.register_page(__name__, path="/explorer/insights", name="Insights", title="Odatix Explorer - Insights", order=19, layout=layout)


@dash.callback(
  Output("xp-insights-chips", "children"),
  Input("xp-insights-poll", "n_intervals"),
  Input("odatix-settings", "data"),
  Input("xp-insights-sources", "data"),
  State("xp-insights-chips", "children"),
)
def update_source_chips(_intervals, settings, selection, previous):
  if isinstance(settings, dict) and settings.get("result_path"):
    STORE.configure(settings.get("result_path"))
  STORE.poll()

  chips = _source_chips(STORE.source_names(), selection)
  if chips == (previous or []):
    return dash.no_update
  return chips


@dash.callback(
  Output("xp-insights-sources", "data"),
  Input({"type": "xp-insights-source", "name": ALL}, "n_clicks"),
  State("xp-insights-sources", "data"),
  prevent_initial_call=True,
)
def toggle_source(clicks, selection):
  """Chips are a multi-select: each one adds or removes a source, "All" clears.

  Rebuilt chips come back with n_clicks=0, so an all-zero call is a rebuild
  rather than a click.
  """
  triggered = dash.callback_context.triggered_id
  if not isinstance(triggered, dict) or not any(clicks or []):
    raise dash.exceptions.PreventUpdate

  name = triggered.get("name")
  if name == "all":
    return []
  chosen = list(selection or [])
  if name in chosen:
    chosen.remove(name)
  else:
    chosen.append(name)
  return chosen


@dash.callback(
  Output("xp-insights-grid", "children"),
  Output("xp-insights-views", "data"),
  Input("xp-insights-poll", "n_intervals"),
  Input("odatix-settings", "data"),
  Input("xp-insights-sources", "data"),
  State("xp-insights-views", "data"),
)
def update_insights(_intervals, settings, selection, previous):
  if isinstance(settings, dict) and settings.get("result_path"):
    STORE.configure(settings.get("result_path"))
  STORE.poll()

  available = STORE.source_names()
  sources = selected_sources(selection, available)
  # The store bumps its version whenever a result file actually changed, so the
  # gallery can poll often without re-measuring the data every time.
  signature = [STORE.version, sources]
  if signature == (previous or {}).get("signature"):
    return dash.no_update, dash.no_update

  if not sources:
    return _empty_state(False), {"signature": signature, "views": []}

  recommendations = recommend.recommend_gallery(STORE, sources=sources, filters=default_filters(STORE, sources))
  if not recommendations:
    return _empty_state(bool(available)), {"signature": signature, "views": []}

  cards = [_card(index, reco) for index, reco in enumerate(recommendations)]
  return html.Div(cards, className="xp-reco-grid"), {"signature": signature, "views": [reco.view for reco in recommendations]}


######################################
# Card actions
######################################


def _clicked_view(clicks, store):
  """The view of the card that fired, or None when nothing really happened."""
  triggered = dash.callback_context.triggered_id
  if not isinstance(triggered, dict) or not any(clicks or []):
    return None
  saved = (store or {}).get("views") or []
  index = triggered.get("index")
  if not isinstance(index, int) or index >= len(saved):
    return None
  return saved[index]


@dash.callback(
  Output("xp-control-state", "data", allow_duplicate=True),
  Output("xp-filter-state", "data", allow_duplicate=True),
  Output("xp-rule-state", "data", allow_duplicate=True),
  Output("xp-ui-state", "data", allow_duplicate=True),
  Output("xp-insights-url", "pathname"),
  Input({"type": "xp-reco-open", "index": ALL}, "n_clicks"),
  State("xp-insights-views", "data"),
  State("xp-ui-state", "data"),
  prevent_initial_call=True,
)
def open_recommendation(clicks, store, ui_state):
  """Restore a generated view, then navigate to its chart page."""
  view = _clicked_view(clicks, store)
  if view is None:
    raise dash.exceptions.PreventUpdate
  try:
    payload, ui_patch, _warnings = views_callbacks.restore_generated(view)
  except ValueError:
    raise dash.exceptions.PreventUpdate

  ui_state = dict(ui_state or {})
  ui_state.update(ui_patch)
  return payload["controls"], payload["filter_state"], payload["rule_state"], ui_state, "/explorer/" + payload["kind"]


@dash.callback(
  Output("xp-insights-status", "children"),
  Input({"type": "xp-reco-save", "index": ALL}, "n_clicks"),
  State("xp-insights-views", "data"),
  prevent_initial_call=True,
)
def save_recommendation(clicks, store):
  """Turn a proposal into a real view file, so it survives the next data change."""
  view = _clicked_view(clicks, store)
  if view is None:
    raise dash.exceptions.PreventUpdate
  try:
    slug = views.save_view(STORE.result_path, view.get("name"), view)
  except (OSError, ValueError) as e:
    return html.Div("⚠ Could not save the view: " + str(e), className="xp-view-warning")
  return html.Div('Saved as "' + slug + '.json" — it now shows up on the Explorer home page', className="xp-view-ok")
