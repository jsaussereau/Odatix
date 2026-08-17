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
Exploration page: what a design space exploration searched, and what it found.

The designs a campaign evaluated are also exported as a results source, so
every other page of the explorer already charts them like any other result --
including "color the points by whether they are on the front", since the
export marks them (see :mod:`odatix.dse.export`). What that cannot show is the
search: this page does.

Three questions, in the order they get asked:

- did it find anything -- the trade-off curve, drawn in the space of the
  objectives, with the designs it beat behind it;
- was it done -- how the front grew batch after batch, which is what says
  whether the next run needs a bigger budget or a smaller one;
- what exactly are the answers -- the front, design by design.

The page polls, because an exploration is read while it runs.
"""

import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.graph_objects as go

import odatix.explorer.charts.app_theme_bridge as app_theme_bridge
import odatix.explorer.charts.palettes as palettes
from odatix.explorer.core.dse import CAMPAIGNS
from odatix.explorer.core.store import STORE

POLL_INTERVAL_MS = 3000

FRONT_COLOR_INDEX = 0
OTHER_COLOR_INDEX = 1

#: Charts are given their height here rather than in the stylesheet: a figure
#: whose container has no height of its own collapses to whatever plotly
#: guessed at mount, and an inline height cannot be lost to a later rule.
GRAPH_HEIGHT = "400px"

HIGHLIGHT_COLOR = palettes.HIGHLIGHT_COLOR


def _key_of(record):
  """
  The identity of a design, for matching the same point across the trade-off
  curve, the parallel-coordinates plot and the front table.

  An archive writes the front as its own list of records, so the same design
  can appear more than once and cannot be told apart by identity: this is what
  names it instead.
  """
  return (str(record.get("configuration")), record.get("frequency"), record.get("batch"))


def _key_str(key):
  return "|".join(str(part) for part in key)


######################################
# Layout
######################################

def layout(**kwargs):
  return html.Div(
    [
      dcc.Interval(id="xp-dse-poll", interval=POLL_INTERVAL_MS),
      # The design under the pointer, shared across the trade-off curve, the
      # parallel-coordinates plot and the front table: hovering or clicking any
      # one of them sets this, and the other two redraw to point it out.
      dcc.Store(id="xp-dse-highlight", data=None),
      html.Div(
        [
          html.Div(
            [
              html.H1("Design space exploration", className="xp-dse-title"),
              html.Div(
                "What the search evaluated, and which designs are the answer.",
                className="xp-dse-subtitle",
              ),
            ],
            className="xp-dse-heading",
          ),
          html.Div(
            dcc.Dropdown(id="xp-dse-campaign", options=[], value=None, clearable=False,
                         placeholder="Campaign"),
            className="xp-dse-picker",
          ),
        ],
        className="xp-dse-header",
      ),
      html.Div(
        [
          html.Div(id="xp-dse-summary"),
          html.Div(
            [
              html.Div(
                [
                  html.Div(
                    [
                      html.Div("Trade-off curve", className="xp-dse-card-title"),
                      html.Div(id="xp-dse-front-caption", className="xp-dse-card-subtitle"),
                    ],
                    className="xp-dse-card-head",
                  ),
                  # The axes are chosen here rather than fixed to the two first
                  # objectives: a campaign can pull in more directions than a
                  # chart has axes, and which trade-off is worth looking at is a
                  # question only the reader can answer.
                  html.Div(
                    [
                      _axis_picker("xp-dse-axis-x", "x"),
                      _axis_picker("xp-dse-axis-y", "y"),
                      _axis_picker("xp-dse-axis-z", "z", clearable=True, placeholder="none (2D)"),
                    ],
                    id="xp-dse-axes",
                    className="xp-dse-axes",
                  ),
                  dcc.Checklist(
                    id="xp-dse-filters",
                    options=[
                      {"label": "only the front", "value": "front"},
                      {"label": "hide designs that break a constraint", "value": "feasible"},
                    ],
                    value=[],
                    className="xp-dse-filters",
                  ),
                  html.Div(id="xp-dse-front-slot", className="xp-dse-slot"),
                ],
                className="xp-dse-card",
              ),
              _card(
                "How the search progressed",
                html.Div(id="xp-dse-progress-slot", className="xp-dse-slot"),
                "how much the front covers, batch after batch",
              ),
            ],
            id="xp-dse-charts",
            className="xp-dse-charts",
          ),
          _card(
            "Objectives, side by side",
            html.Div(id="xp-dse-parcoords-slot", className="xp-dse-slot"),
            "every design across every objective at once -- top is always better",
          ),
          html.Div(id="xp-dse-body"),
        ],
        className="xp-dse-body",
      ),
    ],
    className="xp-dse",
  )


dash.register_page(
  __name__, path="/explorer/dse", name="Exploration",
  title="Odatix Explorer - Exploration", order=29, layout=layout,
)


######################################
# Pieces of the page
######################################

def _result_path(settings):
  if isinstance(settings, dict) and settings.get("result_path"):
    STORE.configure(settings.get("result_path"))
  return STORE.result_path


def _number(value):
  """A number as a person reads it, and "--" for what was never measured."""
  if value is None:
    return "--"
  if isinstance(value, bool):
    return "yes" if value else "no"
  if isinstance(value, float):
    if value != value:  # NaN
      return "--"
    if value == int(value) and abs(value) < 1e15:
      return "{0:,}".format(int(value)).replace(",", " ")
    return "{0:.4g}".format(value)
  if isinstance(value, int):
    return "{0:,}".format(value).replace(",", " ")
  return str(value)


def _stat(label, value, detail=None):
  children = [
    html.Div(_number(value), className="xp-dse-stat-value"),
    html.Div(label, className="xp-dse-stat-label"),
  ]
  if detail:
    children.append(html.Div(detail, className="xp-dse-stat-detail"))
  return html.Div(children, className="xp-dse-stat")


def _goal_label(objective):
  return objective["metric"] + (" (maximize)" if objective["goal"].startswith("max") else " (minimize)")


def _axis_picker(picker_id, label, clearable=False, placeholder=None):
  return html.Div(
    [
      html.Label(label, className="xp-dse-axis-label", htmlFor=picker_id),
      dcc.Dropdown(id=picker_id, options=[], value=None, clearable=clearable,
                   placeholder=placeholder or label, className="xp-dse-axis-dropdown"),
    ],
    className="xp-dse-axis",
  )


def _axis_metrics(campaign):
  """
  Every metric a point of this campaign can be plotted against.

  The objectives first, in the order the campaign declares them, then whatever
  the constraints name: a constraint is a number that was measured for every
  design too, and "how much slack did the answer cost" is a trade-off worth
  looking at even though nothing was optimizing for it.
  """
  metrics = []
  for objective in campaign.objectives:
    if objective["metric"] not in metrics:
      metrics.append(objective["metric"])
  for constraint in campaign.constraints:
    metric = str(constraint.get("metric", ""))
    if metric and metric not in metrics:
      metrics.append(metric)
  return metrics


def _goal_of(campaign, metric):
  for objective in campaign.objectives:
    if objective["metric"] == metric:
      return objective["goal"]
  return None


def _axis_label(campaign, metric):
  goal = _goal_of(campaign, metric)
  if goal is None:
    return metric
  return _goal_label({"metric": metric, "goal": goal})


def _summary(campaign):
  counts = campaign.counts()
  objectives = campaign.objectives

  stats = [
    _stat("on the front", counts["front"], "the answer"),
    _stat("evaluated", counts["evaluated"],
          "of {0} in the space".format(_number(counts["space"])) if counts["space"] else None),
    _stat("measured", counts["measured"],
          "{0} failed".format(_number(counts["failed"])) if counts["failed"] else None),
    # An archive written before batches were recorded knows none, which is not
    # the same thing as a campaign that ran none: say so rather than print a
    # zero the numbers above contradict.
    _stat("batches", counts["batches"] or None, campaign.strategy or None),
  ]

  chips = [
    html.Span(_goal_label(objective), className="xp-dse-chip") for objective in objectives
  ] or [html.Span("no objective", className="xp-dse-chip")]
  for constraint in campaign.constraints:
    parts = []
    if constraint.get("min") is not None:
      parts.append("{0} >= {1}".format(constraint.get("metric"), _number(constraint.get("min"))))
    if constraint.get("max") is not None:
      parts.append("{0} <= {1}".format(constraint.get("metric"), _number(constraint.get("max"))))
    chips.append(html.Span(" and ".join(parts) or str(constraint.get("metric")),
                           className="xp-dse-chip xp-dse-chip-constraint"))

  children = [
    html.Div(stats, className="xp-dse-stats"),
    html.Div(chips, className="xp-dse-chips"),
  ]
  if campaign.feasible is False:
    children.append(html.Div(
      "No design on the front meets the constraints: the search did not reach the feasible "
      "part of the space. What it reports below is the closest it got, not the answer.",
      className="xp-dse-warning",
    ))
  if campaign.error:
    children.append(html.Div(
      "This archive could not be read: {0}".format(campaign.error), className="xp-dse-warning"))
  return html.Div(children, className="xp-dse-summary")


def _metric_of(record, metric):
  """
  What a record says a metric is worth.

  An archive keeps the metrics of a design where the results file put them,
  and the dimensions that are numbers themselves -- the frequency of a custom
  frequency synthesis -- count as metrics too, exactly as they do for the
  objectives of the campaign.
  """
  metrics = record.get("metrics") or {}
  if metric in metrics:
    value = metrics.get(metric)
  elif metric == "frequency" and record.get("frequency") is not None:
    value = record.get("frequency")
  else:
    return None
  if isinstance(value, bool) or not isinstance(value, (int, float)):
    return None
  return value


def _base_layout(chrome, title=None):
  return {
    "template": "plotly_dark" if chrome["dark"] else "plotly_white",
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": chrome["text_color"]},
    "title": {"text": title} if title else None,
    "margin": {"l": 60, "r": 20, "t": 40 if title else 20, "b": 50},
    "hovermode": "closest",
    # A hover or a table click rebuilds this figure to redraw the highlight, and
    # without a fixed uirevision that redraw would also throw away whatever zoom
    # or pan the reader had set -- exactly while they are pointing at something.
    "uirevision": "xp-dse-figure",
    "legend": {"orientation": "h", "y": -0.18, "x": 0},
    "xaxis": {"gridcolor": chrome["grid_color"], "zerolinecolor": chrome["zeroline_color"]},
    "yaxis": {"gridcolor": chrome["grid_color"], "zerolinecolor": chrome["zeroline_color"]},
  }


def _empty_figure(chrome, message):
  figure = go.Figure()
  figure.update_layout(**_base_layout(chrome))
  figure.add_annotation(text=message, showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
                        font={"color": chrome["text_color"], "size": 14})
  figure.update_xaxes(visible=False)
  figure.update_yaxes(visible=False)
  return figure


def _curve_split(campaign, y_metric, ordered):
  """
  Split the front into the designs the curve is drawn through and the rest.

  A front can hold several designs at the same x -- same frequency, different
  area -- and only one of them is the best the search reached there. Joining
  all of them would send the curve backwards through designs another point of
  the front already beats on this pair of axes, so the curve keeps the best one
  per x and the others stay as markers.

  Returns (None, ordered) when the y axis is not an objective: without a goal
  there is no best to keep, so no curve is drawn at all.
  """
  goal = _goal_of(campaign, y_metric)
  if goal is None:
    return None, ordered
  better = max if goal.startswith("max") else min
  best = {}
  for point in ordered:
    x = point[0][0]
    if x not in best or better(point[0][1], best[x][0][1]) == point[0][1]:
      best[x] = point
  on_curve = [point for point in ordered if best.get(point[0][0]) is point]
  off_curve = [point for point in ordered if best.get(point[0][0]) is not point]
  return on_curve, off_curve


def _with_highlight(marker, keys, highlight_key, is_3d=False):
  """
  A marker dict, with the highlighted point (if it is in this trace) enlarged
  and outlined -- so a hover or a click elsewhere on the page can point back
  at exactly one design without redrawing anything else about the chart.

  scatter3d.marker.line.width/color are scalars, unlike scatter's -- so in 3D
  the whole trace's outline is switched on instead of per-point.
  """
  if not highlight_key or highlight_key not in keys:
    return marker
  marker = dict(marker)
  base_size = marker.get("size", 8)
  marker["size"] = [base_size * 1.8 if key == highlight_key else base_size for key in keys]
  line = marker.get("line") or {}
  base_color = line.get("color", "rgba(0,0,0,0)")
  base_width = line.get("width", 0)
  if is_3d:
    marker["line"] = {"color": HIGHLIGHT_COLOR, "width": 4}
  else:
    marker["line"] = {
      "color": [HIGHLIGHT_COLOR if key == highlight_key else base_color for key in keys],
      "width": [4 if key == highlight_key else base_width for key in keys],
    }
  return marker


def _passes_filters(record, front_keys, filters):
  """Whether a record survives the filters chosen above the trade-off curve."""
  if "front" in filters and _key_of(record) not in front_keys:
    return False
  if "feasible" in filters and record.get("feasible") is False:
    return False
  return True


def _front_figure(campaign, chrome, palette, x_metric=None, y_metric=None, z_metric=None,
                   highlight_key=None, filters=()):
  """
  The trade-off curve, in the space of the chosen metrics.

  Everything the campaign measured is drawn, not only the front: a front alone
  says what the answer is, and a front over the cloud it came out of says how
  much of the space had to be given up for it -- which is the question a
  trade-off curve is read to answer.

  With a third metric chosen the same thing is drawn in three dimensions, as
  markers only: a front in a volume is a surface, and joining its designs with
  a line would draw one particular path through it as if it meant something.
  """
  metrics = _axis_metrics(campaign)
  if len(metrics) < 2:
    return _empty_figure(chrome, "A trade-off curve needs two metrics.")

  x_metric = x_metric if x_metric in metrics else metrics[0]
  y_metric = y_metric if y_metric in metrics else metrics[1]
  z_metric = z_metric if z_metric in metrics else None
  # The archive writes the front as its own list of records, so the same design
  # appears twice and cannot be told apart by identity: match on what names it.
  front_keys = set(_key_of(record) for record in campaign.front)

  drawn = [x_metric, y_metric] + ([z_metric] if z_metric else [])
  points = {True: [], False: []}
  for record in campaign.evaluations:
    if record.get("failed"):
      continue
    if not _passes_filters(record, front_keys, filters):
      continue
    values = [_metric_of(record, metric) for metric in drawn]
    if None in values:
      continue
    points[_key_of(record) in front_keys].append((values, record))

  if not points[True] and not points[False]:
    return _empty_figure(chrome, "Nothing left to show for " + " and ".join(drawn) +
                         " with these filters.")

  figure = go.Figure()

  def hover(record):
    batch = record.get("batch")
    label = str(record.get("configuration", ""))
    if record.get("frequency") is not None:
      label += " @ {0} MHz".format(_number(record.get("frequency")))
    if batch:
      label += "<br>batch {0}".format(batch)
    return label

  axis_of = ["x", "y", "z"]
  hovertemplate = "%{text}" + "".join(
    "<br>" + metric + ": %{" + axis_of[index] + "}" for index, metric in enumerate(drawn)
  ) + "<extra></extra>"

  def coordinates(group):
    return dict(
      (axis_of[index], [point[0][index] for point in group]) for index in range(len(drawn))
    )

  scatter = go.Scatter3d if z_metric else go.Scatter

  if points[False]:
    keys = [_key_str(_key_of(point[1])) for point in points[False]]
    marker = {"size": 4 if z_metric else 8,
              "color": palettes.get_color(OTHER_COLOR_INDEX, palette), "opacity": 0.45}
    figure.add_trace(scatter(
      mode="markers",
      name="evaluated",
      marker=_with_highlight(marker, keys, highlight_key, is_3d=bool(z_metric)),
      text=[hover(point[1]) for point in points[False]],
      customdata=keys,
      hovertemplate=hovertemplate,
      **coordinates(points[False])
    ))

  if points[True]:
    # Sorted along the x axis so the line reads as a curve and not as the order
    # the designs happened to be evaluated in.
    ordered = sorted(points[True], key=lambda point: point[0][0])
    # In three dimensions a front is a surface, and joining its designs with a
    # line would draw one particular path through it as if it meant something.
    on_curve, off_curve = (None, ordered) if z_metric else _curve_split(campaign, y_metric, ordered)

    marker = {"size": 5 if z_metric else 11,
              "color": palettes.get_color(FRONT_COLOR_INDEX, palette),
              "symbol": "diamond"}

    if on_curve:
      keys = [_key_str(_key_of(point[1])) for point in on_curve]
      trace = {
        "mode": "lines+markers",
        "name": "Pareto front",
        "marker": _with_highlight(marker, keys, highlight_key, is_3d=bool(z_metric)),
        "line": {"color": palettes.get_color(FRONT_COLOR_INDEX, palette), "width": 2},
        "text": [hover(point[1]) for point in on_curve],
        "customdata": keys,
        "hovertemplate": hovertemplate,
      }
      trace.update(coordinates(on_curve))
      figure.add_trace(scatter(**trace))

    if off_curve:
      # Hollow and off the line: these are on the front, but another design of
      # the front beats them on this pair of axes, so the curve passes them by.
      # In three dimensions no curve is drawn at all and nothing is set apart.
      other = dict(marker)
      if on_curve is not None:
        other["symbol"] = "triangle-up"
        other["line"] = {"color": palettes.get_color(FRONT_COLOR_INDEX, palette), "width": 2}
      keys = [_key_str(_key_of(point[1])) for point in off_curve]
      trace = {
        "mode": "markers",
        "name": "Pareto front" if on_curve is None else "front on other axes",
        "marker": _with_highlight(other, keys, highlight_key, is_3d=bool(z_metric)),
        "text": [hover(point[1]) for point in off_curve],
        "customdata": keys,
        "hovertemplate": hovertemplate,
      }

      trace.update(coordinates(off_curve))
      figure.add_trace(scatter(**trace))

  layout = _base_layout(chrome)
  if z_metric:
    # A 3D figure hangs its axes off the scene, and the flat xaxis/yaxis of a
    # 2D layout would be ignored where they are not rejected outright.
    layout.pop("xaxis")
    layout.pop("yaxis")
    layout["scene"] = dict(
      # showbackground: a scene paints its own walls from the template, and the
      # card behind it is already the background of everything else here.
      (axis_of[index] + "axis", {"title": {"text": _axis_label(campaign, metric)},
                                 "gridcolor": chrome["grid_color"],
                                 "zerolinecolor": chrome["zeroline_color"],
                                 "showbackground": False})
      for index, metric in enumerate(drawn)
    )
    layout["margin"] = {"l": 0, "r": 0, "t": 10, "b": 10}
  else:
    layout["xaxis"].update({"title": {"text": _axis_label(campaign, x_metric)}})
    layout["yaxis"].update({"title": {"text": _axis_label(campaign, y_metric)}})
  figure.update_layout(**layout)
  return figure


def _front_caption(campaign, x_metric=None, y_metric=None, z_metric=None):
  """
  What the trade-off curve is showing, said in the card rather than in the
  chart: a campaign can pull in more directions than a chart has axes, and a
  reader has to know which of them are drawn.
  """
  metrics = _axis_metrics(campaign)
  if len(metrics) < 2:
    return None
  drawn = [metric for metric in (x_metric, y_metric, z_metric) if metric in metrics]
  caption = "the front, over everything it beat"
  objectives = len(campaign.objectives)
  if drawn and objectives > len(drawn):
    caption += " ({0}, {1} of {2} objectives)".format(
      " / ".join(drawn), len(drawn), objectives)
  return caption


def _progress_figure(campaign, chrome, palette):
  """
  How the front grew, batch after batch.

  The volume it covers is what a campaign is trying to grow, and a curve that
  went flat ten batches ago is the exploration saying the budget of the next
  run can be smaller. The size of the front is drawn with it, on its own axis:
  a front that keeps gaining designs while the volume does not is a search
  refining a curve it has already found.

  Returns None when the archive has no history to draw: a sentence about why
  there is no curve belongs in a paragraph, not squeezed into the middle of an
  empty pair of axes.
  """
  history = campaign.history
  if not history:
    return None

  batches = [entry.get("batch") for entry in history]
  figure = go.Figure()
  figure.add_trace(go.Scatter(
    x=batches,
    y=[entry.get("hypervolume") for entry in history],
    mode="lines+markers",
    name="hypervolume of the front",
    line={"color": palettes.get_color(FRONT_COLOR_INDEX, palette), "width": 2},
    customdata=[[entry.get("evaluated"), entry.get("measured")] for entry in history],
    hovertemplate=("batch %{x}<br>hypervolume: %{y:.4g}"
                   "<br>%{customdata[1]} measured of %{customdata[0]} evaluated<extra></extra>"),
  ))
  figure.add_trace(go.Scatter(
    x=batches,
    y=[entry.get("front") for entry in history],
    mode="lines+markers",
    name="designs on the front",
    yaxis="y2",
    line={"color": palettes.get_color(OTHER_COLOR_INDEX, palette), "width": 2, "dash": "dot"},
    hovertemplate="batch %{x}<br>%{y} designs on the front<extra></extra>",
  ))

  layout = _base_layout(chrome)
  layout["xaxis"].update({"title": {"text": "batch"}, "dtick": 1 if len(batches) < 20 else None})
  layout["yaxis"].update({"title": {"text": "hypervolume"}, "rangemode": "tozero"})
  layout["yaxis2"] = {
    "title": {"text": "front size"},
    "overlaying": "y",
    "side": "right",
    "showgrid": False,
    "rangemode": "tozero",
    "color": palettes.get_color(OTHER_COLOR_INDEX, palette),
  }
  figure.update_layout(**layout)
  return figure


def _parcoords_figure(campaign, chrome, palette, highlight_key=None, filters=()):
  """
  Every design across every objective at once, as a parallel coordinates plot.

  Each axis is one objective, oriented so that up is always better -- an axis
  being minimized is drawn upside down -- so a front design reads as a line
  that stays high across the whole chart, and a design that only wins on one
  objective shows exactly where it gives the rest up. Lines are colored by
  whether the design is on the front, which is the same split every other
  chart on this page draws.
  """
  objectives = campaign.objectives
  metrics = []
  for objective in objectives:
    if objective["metric"] not in metrics:
      metrics.append(objective["metric"])
  if len(metrics) < 2:
    return _empty_figure(chrome, "A parallel coordinates plot needs two objectives.")

  front_keys = set(_key_of(record) for record in campaign.front)

  rows = []
  keys = []
  for record in campaign.evaluations:
    if record.get("failed"):
      continue
    if not _passes_filters(record, front_keys, filters):
      continue
    values = [_metric_of(record, metric) for metric in metrics]
    if None in values:
      continue
    rows.append((values, _key_of(record) in front_keys))
    keys.append(_key_str(_key_of(record)))

  if not rows:
    return _empty_figure(chrome, "Nothing left to show for " + " and ".join(metrics) +
                         " with these filters.")

  dimensions = []
  for index, metric in enumerate(metrics):
    values = [row[0][index] for row in rows]
    goal = _goal_of(campaign, metric)
    value_range = [min(values), max(values)]
    if goal is not None and goal.startswith("min"):
      # Flipped so that, on every axis, up reads as "better" no matter what the
      # objective is optimizing towards.
      value_range = [value_range[1], value_range[0]]
    dimensions.append({
      "label": _axis_label(campaign, metric),
      "values": values,
      "range": value_range,
    })

  colors = [1 if row[1] else 0 for row in rows]
  # A third color value, out of the 0/1 range every other line is colored with,
  # singles the highlighted line out without having to touch the color of
  # anything else -- which is what lets a hover elsewhere on the page point at
  # one line here without redrawing the whole plot.
  color_range = [0, 1]
  colorscale = [
    [0, palettes.get_color(OTHER_COLOR_INDEX, palette)],
    [1, palettes.get_color(FRONT_COLOR_INDEX, palette)],
  ]
  if highlight_key and highlight_key in keys:
    colors[keys.index(highlight_key)] = 2
    color_range = [0, 2]
    colorscale = [
      [0, palettes.get_color(OTHER_COLOR_INDEX, palette)],
      [0.5, palettes.get_color(FRONT_COLOR_INDEX, palette)],
      [1, HIGHLIGHT_COLOR],
    ]

  figure = go.Figure(go.Parcoords(
    line={
      "color": colors,
      "cmin": color_range[0],
      "cmax": color_range[1],
      "colorscale": colorscale,
      "showscale": False,
    },
    customdata=keys,
    dimensions=dimensions,
  ))

  layout = _base_layout(chrome)
  layout.pop("xaxis")
  layout.pop("yaxis")
  layout.pop("hovermode")
  layout.pop("legend")
  layout["margin"] = {"l": 60, "r": 60, "t": 60, "b": 20}
  figure.update_layout(**layout)
  return figure


def _row_filter_query(row):
  """
  A filter_query matching exactly this row, by the fields that name a design.

  Used instead of a row_index so the highlighted row keeps up with the table
  once the reader sorts it: a query matches on cell values, not on the order
  rows happened to be built in.
  """
  parts = []
  if row.get("configuration") is not None:
    parts.append('{{configuration}} = "{0}"'.format(str(row["configuration"]).replace('"', '\\"')))
  if row.get("batch") is not None:
    parts.append("{{batch}} = {0}".format(row["batch"]))
  if row.get("frequency") is not None:
    parts.append("{{frequency}} = {0}".format(row["frequency"]))
  return " && ".join(parts)


def _front_table(campaign, highlight_key=None, filters=()):
  """The answer, design by design."""
  metrics = [objective["metric"] for objective in campaign.objectives]
  for constraint in campaign.constraints:
    metric = str(constraint.get("metric", ""))
    if metric and metric not in metrics:
      metrics.append(metric)

  rows = []
  for record in campaign.front:
    if "feasible" in filters and record.get("feasible") is False:
      continue
    row = {"configuration": record.get("configuration", ""), "batch": record.get("batch")}
    if record.get("frequency") is not None:
      row["frequency"] = record.get("frequency")
    for metric in metrics:
      row[metric] = _metric_of(record, metric)
    if record.get("feasible") is not None:
      row["meets constraints"] = "yes" if record.get("feasible") else "no"
      if record.get("unmet"):
        row["meets constraints"] = "no: " + ", ".join(str(name) for name in record["unmet"])
    row["_key"] = _key_str(_key_of(record))
    rows.append(row)

  if not rows:
    message = ("No design on the front meets the constraints." if filters
               else "The campaign has not measured any design yet.")
    return html.Div(message, className="xp-dse-empty")

  columns = []
  for key in rows[0].keys():
    if key == "_key":
      continue
    # An older archive knows no batch, and an empty column titled "batch" reads
    # as a campaign that lost its batches rather than as one that never wrote
    # any: drop what nothing filled in.
    if all(row.get(key) is None for row in rows):
      continue
    spec = {"name": key, "id": key}
    if key in metrics or key in ("batch", "frequency"):
      spec["type"] = "numeric"
    columns.append(spec)

  style_data_conditional = [
    {"if": {"row_index": "odd"}, "backgroundColor": "var(--theme-element-background-color)"},
  ]
  highlighted = next((row for row in rows if row["_key"] == highlight_key), None) \
    if highlight_key else None
  if highlighted is not None:
    style_data_conditional.append({
      "if": {"filter_query": _row_filter_query(highlighted)},
      "backgroundColor": "var(--theme-primary-color)",
      "color": "var(--theme-contrast-text-color)",
    })

  return html.Div(
    dash_table.DataTable(
      id="xp-dse-front-table",
      columns=columns,
      data=rows,
      sort_action="native",
      page_action="none",
      # The page polls every few seconds and rebuilds this table from scratch;
      # without persistence a sort the reader chose would be thrown away at the
      # next tick, which is exactly while a campaign is running.
      # Keyed by campaign: a sort belongs to the columns it was chosen on, and
      # another campaign may not have them.
      persistence=getattr(campaign, "name", True),
      persistence_type="session",
      persisted_props=["sort_by", "filter_query", "hidden_columns"],
      style_table={"overflowX": "auto"},
      style_header={
        "backgroundColor": "var(--theme-contrast-background-color)",
        "color": "var(--theme-contrast-text-color)",
        "fontWeight": "600",
        "border": "1px solid var(--theme-border-color)",
      },
      style_cell={
        "backgroundColor": "var(--theme-background-color)",
        "color": "var(--theme-text-color)",
        "border": "1px solid var(--theme-border-color)",
        "textAlign": "left",
        "padding": "4px 10px",
        "fontFamily": "var(--theme-font-family)",
        "fontSize": "var(--theme-small-font-size)",
        "maxWidth": "320px",
        "overflow": "hidden",
        "textOverflow": "ellipsis",
      },
      style_data_conditional=style_data_conditional,
    ),
    className="xp-dse-table",
  )


def _failures(campaign):
  """
  The designs that produced no answer, and what became of them.

  Worth a place on the page rather than only in the archive: a campaign where
  half the designs failed to build has not searched the space it thinks it
  searched, and nothing else here would say so.
  """
  failed = campaign.failed
  if not failed:
    return None
  rows = [
    html.Li([
      html.Span(str(record.get("configuration", "")), className="xp-dse-failure-name"),
      html.Span(str(record.get("reason", "") or "no result"), className="xp-dse-failure-reason"),
    ])
    for record in failed[:20]
  ]
  if len(failed) > 20:
    rows.append(html.Li("and {0} more".format(len(failed) - 20), className="xp-dse-failure-more"))
  return html.Div(
    [
      _section("Designs that produced nothing", len(failed)),
      html.Ul(rows, className="xp-dse-failures"),
    ],
    className="xp-dse-section",
  )


def _section(title, count=None):
  children = [html.H2(title, className="xp-section-heading")]
  if count is not None:
    children.append(html.Span(str(count), className="xp-section-count"))
  return html.Div(children, className="xp-section-head")


def _card(title, body, subtitle=None):
  """
  A titled panel, so that a chart and the sentence that replaces it when there
  is nothing to chart occupy the same box and line up with each other.
  """
  head = [html.Div(title, className="xp-dse-card-title")]
  if subtitle:
    head.append(html.Div(subtitle, className="xp-dse-card-subtitle"))
  return html.Div([html.Div(head, className="xp-dse-card-head"), body], className="xp-dse-card")


def _placeholder(message):
  return html.Div(html.Div(message, className="xp-dse-placeholder-text"),
                  className="xp-dse-placeholder")


def _graph(figure, config, id=None):
  kwargs = {"id": id} if id else {}
  return dcc.Graph(figure=figure, config=config, className="xp-dse-graph",
                   style={"height": GRAPH_HEIGHT, "width": "100%"}, **kwargs)


def _empty_state(result_path):
  return html.Div(
    [
      html.Div("No exploration found yet", className="xp-source-empty-title"),
      html.Div(
        'Looked for exploration archives in "{0}". '
        "Run \"odatix dse\" — campaigns appear here as soon as their first batch is done, "
        "and the page follows them while they run.".format(CAMPAIGNS.directory(result_path)),
        className="xp-source-empty-subtitle",
      ),
    ],
    className="xp-source-empty",
  )


######################################
# Callbacks
######################################

@dash.callback(
  Output("xp-dse-highlight", "data"),
  Input("xp-dse-front-graph", "hoverData"),
  Input("xp-dse-parcoords-graph", "hoverData"),
  Input("xp-dse-front-table", "active_cell"),
  Input("xp-dse-campaign", "value"),
  Input("xp-dse-axis-x", "value"),
  Input("xp-dse-axis-y", "value"),
  Input("xp-dse-axis-z", "value"),
  Input("xp-dse-filters", "value"),
  State("xp-dse-front-table", "derived_virtual_data"),
  prevent_initial_call=True,
)
def update_highlight(front_hover, parcoords_hover, active_cell, _name, _x, _y, _z, _filters,
                     table_rows):
  """
  Which design is pointed at, from whichever of the three views the reader
  used -- a hover on either chart, or a click on a row of the table.

  Switching campaign or axes clears it: a key from one campaign's designs, or
  from a trace no longer drawn, would point at nothing, or worse, at whatever
  unrelated design happens to share it.
  """
  trigger = dash.callback_context.triggered_id
  if trigger in ("xp-dse-campaign", "xp-dse-axis-x", "xp-dse-axis-y", "xp-dse-axis-z",
                 "xp-dse-filters"):
    return None
  if trigger == "xp-dse-front-graph":
    points = (front_hover or {}).get("points") or []
    return points[0].get("customdata") if points else dash.no_update
  if trigger == "xp-dse-parcoords-graph":
    points = (parcoords_hover or {}).get("points") or []
    return points[0].get("customdata") if points else dash.no_update
  if trigger == "xp-dse-front-table":
    if not active_cell or not table_rows:
      return dash.no_update
    row = table_rows[active_cell["row"]]
    return row.get("_key")
  return dash.no_update


@dash.callback(
  Output("xp-dse-campaign", "options"),
  Output("xp-dse-campaign", "value"),
  Input("xp-dse-poll", "n_intervals"),
  Input("odatix-settings", "data"),
  State("xp-dse-campaign", "value"),
)
def update_campaigns(_intervals, settings, selected):
  campaigns = CAMPAIGNS.campaigns(_result_path(settings))
  options = [{"label": campaign.name, "value": campaign.name} for campaign in campaigns]
  names = [campaign.name for campaign in campaigns]
  # A campaign that is still there stays selected: the page polls, and a
  # selection that reset every three seconds would be unusable while a search
  # is running -- which is exactly when this page is open.
  value = selected if selected in names else (names[0] if names else None)
  return options, value


@dash.callback(
  Output("xp-dse-axis-x", "options"),
  Output("xp-dse-axis-x", "value"),
  Output("xp-dse-axis-y", "options"),
  Output("xp-dse-axis-y", "value"),
  Output("xp-dse-axis-z", "options"),
  Output("xp-dse-axis-z", "value"),
  Output("xp-dse-axes", "style"),
  Input("xp-dse-campaign", "value"),
  Input("odatix-settings", "data"),
  State("xp-dse-axis-x", "value"),
  State("xp-dse-axis-y", "value"),
  State("xp-dse-axis-z", "value"),
)
def update_axes(name, settings, x_metric, y_metric, z_metric):
  """
  What the axes of the trade-off curve can be, and what they are.

  Only offered when there is a choice to make: with two metrics the chart can
  only be one thing, and a pair of dropdowns that cannot be changed is noise.
  A choice already made survives -- both the poll and, when the metrics are
  still there, a switch to another campaign of the same shape.
  """
  campaign = CAMPAIGNS.get(_result_path(settings), name) if name else None
  metrics = _axis_metrics(campaign) if campaign is not None else []
  if len(metrics) < 3:
    return [], None, [], None, [], None, {"display": "none"}

  options = [{"label": metric, "value": metric} for metric in metrics]
  x_metric = x_metric if x_metric in metrics else metrics[0]
  y_metric = y_metric if y_metric in metrics else metrics[1]
  if y_metric == x_metric:
    y_metric = next(metric for metric in metrics if metric != x_metric)
  z_metric = z_metric if z_metric in metrics and z_metric not in (x_metric, y_metric) else None

  # An axis cannot be the metric another axis already has: the same number
  # against itself is a diagonal, and it costs a reader a moment to work out
  # that the chart is not broken.
  def offered(taken):
    return [option for option in options if option["value"] not in taken]

  return (offered([y_metric, z_metric]), x_metric,
          offered([x_metric, z_metric]), y_metric,
          offered([x_metric, y_metric]), z_metric,
          None)


@dash.callback(
  Output("xp-dse-summary", "children"),
  Output("xp-dse-charts", "style"),
  Output("xp-dse-front-slot", "children"),
  Output("xp-dse-front-caption", "children"),
  Output("xp-dse-progress-slot", "children"),
  Output("xp-dse-parcoords-slot", "children"),
  Output("xp-dse-body", "children"),
  Input("xp-dse-campaign", "value"),
  Input("xp-dse-axis-x", "value"),
  Input("xp-dse-axis-y", "value"),
  Input("xp-dse-axis-z", "value"),
  Input("xp-dse-filters", "value"),
  Input("xp-dse-poll", "n_intervals"),
  Input("theme-dropdown", "value"),
  Input("odatix-settings", "data"),
  Input("xp-dse-highlight", "data"),
)
def update_body(name, x_metric, y_metric, z_metric, filters, _intervals, app_theme, settings,
                 highlight_key):
  result_path = _result_path(settings)
  campaign = CAMPAIGNS.get(result_path, name) if name else None
  if campaign is None:
    return _empty_state(result_path), {"display": "none"}, None, None, None, None, None

  chrome = app_theme_bridge.get_chrome(app_theme)
  palette = palettes.DEFAULT_PALETTE
  # responsive: the two charts share a grid that reflows with the window, and a
  # figure sized once at mount would keep the width the cell had then.
  config = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "responsive": True}

  filters = filters or []

  front_figure = _front_figure(campaign, chrome, palette, x_metric, y_metric, z_metric,
                                highlight_key=highlight_key, filters=filters)
  front = _graph(front_figure, config, id="xp-dse-front-graph")
  progress = _progress_figure(campaign, chrome, palette)
  progress = _graph(progress, config) if progress is not None else _placeholder(
    "This archive holds no per-batch history: it was written by a version of Odatix "
    "that did not record one. The next run of the campaign will."
  )

  parcoords_figure = _parcoords_figure(campaign, chrome, palette, highlight_key=highlight_key,
                                        filters=filters)
  parcoords = _graph(parcoords_figure, config, id="xp-dse-parcoords-graph")

  body = [
    html.Div([_section("The front", len(campaign.front)),
              _front_table(campaign, highlight_key, filters=filters)],
             className="xp-dse-section"),
  ]
  failures = _failures(campaign)
  if failures is not None:
    body.append(failures)
  return (_summary(campaign), None, front,
          _front_caption(campaign, x_metric, y_metric, z_metric), progress, parcoords, body)
