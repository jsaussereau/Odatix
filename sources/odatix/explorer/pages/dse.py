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
import odatix.explorer.core.dse_factors as dse_factors
from odatix.explorer.core.dse import CAMPAIGNS
from odatix.explorer.core.store import STORE

POLL_INTERVAL_MS = 3000

FRONT_COLOR_INDEX = 0
OTHER_COLOR_INDEX = 1

#: One color per kind of factor, so that the bar chart says at a glance whether
#: what moved the metric was a whole domain being swapped or one number in one.
#: The chips that pick the kinds are painted from the same table, so that the
#: chip and the bars it turns on are read as the same thing.
KIND_COLOR_INDEX = {
  dse_factors.DOMAIN: 0,
  dse_factors.PARAMETER: 2,
  dse_factors.RUN: 4,
}

#: The kinds of factor, in the order the chips offer them.
KIND_ORDER = (dse_factors.DOMAIN, dse_factors.PARAMETER, dse_factors.RUN)
DEFAULT_KINDS = (dse_factors.DOMAIN, dse_factors.RUN)

KIND_CHIP_LABEL = {
  dse_factors.DOMAIN: "parameter domains",
  dse_factors.PARAMETER: "individual parameters",
  dse_factors.RUN: "run settings",
}

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
                  # What the color of a point means. The front against the rest
                  # is what the chart is read for, but "which designs up there
                  # all share the same cache" is the next question, and it is
                  # answered by coloring the same cloud by that choice instead.
                  html.Div(
                    [
                      html.Label("color by", className="xp-dse-axis-label", htmlFor="xp-dse-color"),
                      dcc.Dropdown(id="xp-dse-color", options=[], value="front", clearable=False,
                                   className="xp-dse-axis-dropdown"),
                    ],
                    className="xp-dse-axis xp-dse-color",
                  ),
                  html.Div(
                    [
                      dcc.Checklist(
                        id="xp-dse-filters",
                        options=[
                          {"label": "only the front", "value": "front"},
                          {"label": "hide designs that break a constraint", "value": "feasible"},
                        ],
                        value=["feasible"],
                        className="xp-dse-filters",
                      ),
                      # How the axes are drawn. Two readings of the same cloud:
                      # a log axis to tell apart designs a handful of huge ones
                      # would otherwise squash together, an axis from zero to
                      # see how large a difference actually is rather than only
                      # that there is one.
                      dcc.Checklist(
                        id="xp-dse-scales",
                        options=[
                          {"label": "log x", "value": "x"},
                          {"label": "log y", "value": "y"},
                          {"label": "x from 0", "value": "x0"},
                          {"label": "y from 0", "value": "y0"},
                        ],
                        value=[],
                        className="xp-dse-filters",
                      ),
                    ],
                    className="xp-dse-options",
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
          html.Div(
            [
              html.Div(
                [
                  html.Div("Objectives, side by side", className="xp-dse-card-title"),
                  html.Div(
                    "every design across every objective at once -- top is always better",
                    id="xp-dse-parcoords-subtitle",
                    className="xp-dse-card-subtitle",
                  ),
                ],
                className="xp-dse-card-head",
              ),
              # Each axis spans what the designs reached, which reads a
              # one-percent spread the same as a tenfold one. From zero, the
              # width of the band is the size of the difference.
              dcc.Checklist(
                id="xp-dse-parcoords-scales",
                options=[
                  {"label": "axes from 0", "value": "zero"},
                  # An axis being minimized is drawn upside down so that "high"
                  # reads as "good" everywhere; this puts every axis back the
                  # way a number line runs, for a reader comparing the values
                  # themselves rather than how good they are.
                  {"label": "low values at the bottom", "value": "natural"},
                ],
                value=[],
                className="xp-dse-filters xp-dse-card-options",
              ),
              html.Div(id="xp-dse-parcoords-slot", className="xp-dse-slot"),
            ],
            className="xp-dse-card",
          ),
          # The answer of the campaign, before the analysis of the space it came
          # out of; what never built at all closes the page.
          html.Div(id="xp-dse-front-table-slot"),
          _impact_section(),
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


def _kind_chip(kind, selected):
  """One kind of factor, as a chip that turns its bars on and off."""
  color = palettes.get_color(KIND_COLOR_INDEX.get(kind, 1), palettes.DEFAULT_PALETTE)
  className = "xp-dse-chip xp-dse-chip-toggle"
  if not selected:
    className += " xp-dse-chip-off"
  return html.Button(
    KIND_CHIP_LABEL.get(kind, kind),
    id="xp-dse-kind-" + kind,
    n_clicks=0,
    className=className,
    style={"--xp-dse-chip-color": color},
  )


def _impact_section():
  """
  What the designs are made of, and what each part of them did to the numbers.

  The rest of the page is about the answer; this is about the space it came out
  of. Two charts, and they answer two different questions: which choices moved
  the metric at all, and what one of them in particular did to it.
  """
  return html.Div(
    [
      _section("What drove the results"),
      html.Div(
        "Every design the search measured, broken down by what it was made of. "
        "A search does not sample its space evenly, so these are what the designs "
        "that were tried have in common -- not a controlled experiment.",
        className="xp-dse-section-note",
      ),
      html.Div(
        [
          html.Div(
            [
              html.Label("metric", className="xp-dse-axis-label", htmlFor="xp-dse-impact-metric"),
              dcc.Dropdown(id="xp-dse-impact-metric", options=[], value=None, clearable=False,
                           className="xp-dse-axis-dropdown"),
            ],
            className="xp-dse-axis",
          ),
          # A chip per kind rather than a checkbox: it carries the color its
          # bars are drawn in, so what a kind is is read off the ranking
          # itself instead of having to be remembered.
          dcc.Store(id="xp-dse-impact-kinds", data=list(DEFAULT_KINDS)),
          html.Div(
            [_kind_chip(kind, kind in DEFAULT_KINDS) for kind in KIND_ORDER],
            className="xp-dse-chips xp-dse-kind-chips",
          ),
          dcc.Checklist(
            id="xp-dse-impact-scope",
            options=[{"label": "only designs that meet the constraints", "value": "feasible"}],
            value=["feasible"],
            className="xp-dse-filters",
          ),
        ],
        className="xp-dse-impact-controls",
      ),
      html.Div(
        [
          _card(
            "What moved this metric",
            html.Div(id="xp-dse-impact-slot", className="xp-dse-slot"),
            "how much of the spread each choice accounts for -- click a bar to look into it",
          ),
          html.Div(
            [
              html.Div(
                [
                  html.Div("One choice, in detail", className="xp-dse-card-title"),
                  html.Div(id="xp-dse-factor-caption", className="xp-dse-card-subtitle"),
                ],
                className="xp-dse-card-head",
              ),
              dcc.Dropdown(id="xp-dse-factor", options=[], value=None, clearable=False,
                           className="xp-dse-axis-dropdown xp-dse-factor-picker"),
              html.Div(id="xp-dse-factor-slot", className="xp-dse-slot"),
            ],
            className="xp-dse-card",
          ),
        ],
        id="xp-dse-impact-charts",
        className="xp-dse-charts",
      ),
      html.Div(id="xp-dse-levels"),
    ],
    id="xp-dse-impact",
    className="xp-dse-section",
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


def _translucent(color, alpha):
  """
  The same color, at a given opacity -- so a fill and its outline can be the
  one color without the fill shouting as loudly as the line.
  """
  color = str(color).strip()
  if color.startswith("#"):
    digits = color[1:]
    if len(digits) == 3:
      digits = "".join(digit * 2 for digit in digits)
    if len(digits) >= 6:
      channels = [int(digits[index:index + 2], 16) for index in (0, 2, 4)]
      return "rgba({0},{1},{2},{3})".format(channels[0], channels[1], channels[2], alpha)
  if color.startswith("rgb(") and color.endswith(")"):
    return "rgba(" + color[4:-1] + ",{0})".format(alpha)
  if color.startswith("rgba("):
    parts = color[5:-1].split(",")
    if len(parts) == 4:
      return "rgba(" + ",".join(part.strip() for part in parts[:3]) + ",{0})".format(alpha)
  return color


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


######################################
# Coloring the cloud by something else
######################################

def _factor_id(factor):
  return "factor|{0}|{1}".format(factor.source, factor.key)


def _factor_by_id(campaign, value):
  """The factor an id names, or None -- a campaign may not have it any more."""
  if not value:
    return None
  for factor in dse_factors.factors(campaign):
    if _factor_id(factor) == value:
      return factor
  return None


def _color_options(campaign):
  """
  Everything a point can be colored by: what the search found, what the design
  was made of, and what it measured.
  """
  options = [
    {"label": "on the front", "value": "front"},
    {"label": "batch it was found in", "value": "batch"},
  ]
  if campaign.constraints:
    options.append({"label": "meets the constraints", "value": "feasible"})
  for factor in dse_factors.factors(campaign):
    options.append({"label": "{0} ({1})".format(factor.label, factor.kind_label),
                    "value": _factor_id(factor)})
  for metric in dse_factors.metrics(campaign):
    options.append({"label": "{0} (metric)".format(metric), "value": "metric|" + metric})
  return options


def _color_spec(campaign, color_by):
  """
  How to color a point, or None for the front-against-the-rest split the chart
  draws by default -- which is a different figure, not a different color.
  """
  if not color_by or color_by == "front":
    return None
  if color_by == "batch":
    return {"label": "batch", "numeric": True, "getter": lambda record: record.get("batch")}
  if color_by == "feasible":
    return {
      "label": "meets the constraints", "numeric": False,
      "getter": lambda record: None if record.get("feasible") is None else (
        "yes" if record.get("feasible") else "no"),
    }
  if color_by.startswith("metric|"):
    metric = color_by.split("|", 1)[1]
    return {"label": metric, "numeric": True,
            "getter": lambda record: dse_factors.metric_of(record, metric)}
  factor = _factor_by_id(campaign, color_by)
  if factor is None:
    return None
  return {
    "label": factor.label,
    # A numeric factor with a handful of values reads better as one trace per
    # value than as a color bar nobody can tell two shades of apart.
    "numeric": factor.numeric and len(factor.levels) > 6,
    "getter": lambda record: dse_factors.value_of(record, factor),
  }


def _colored_traces(figure, points, front_keys, spec, palette, drawn, coordinates, hover,
                     hovertemplate, is_3d, highlight_key):
  """
  The cloud colored by something other than the front, with the front drawn
  over it.

  The front stays visible whatever the color means: it is the answer, and a
  reader who colored the chart by cache size is asking which of the answers
  have a big cache -- a question that needs both drawn at once.
  """
  scatter = go.Scatter3d if is_3d else go.Scatter
  size = 4 if is_3d else 9

  labelled = []
  for values, record in points:
    color_value = spec["getter"](record)
    if color_value is not None:
      labelled.append((values, record, color_value))

  if not labelled:
    return False

  colorbar_title = spec["label"]
  if spec["numeric"]:
    keys = [_key_str(_key_of(item[1])) for item in labelled]
    marker = {
      "size": size,
      "color": [item[2] for item in labelled],
      "colorscale": "Viridis",
      "showscale": True,
      "colorbar": {"title": {"text": colorbar_title}, "thickness": 12, "len": 0.8},
      "opacity": 0.85,
    }
    figure.add_trace(scatter(
      mode="markers",
      name=colorbar_title,
      showlegend=False,
      marker=_with_highlight(marker, keys, highlight_key, is_3d=is_3d),
      text=["{0}<br>{1}: {2}".format(hover(item[1]), colorbar_title, _number(item[2]))
            for item in labelled],
      customdata=keys,
      hovertemplate=hovertemplate,
      **coordinates([(item[0], item[1]) for item in labelled])
    ))
  else:
    groups = {}
    for values, record, color_value in labelled:
      groups.setdefault(color_value, []).append((values, record))
    for index, level in enumerate(sorted(groups, key=lambda value: (isinstance(value, str),
                                                                   value))):
      group = groups[level]
      keys = [_key_str(_key_of(point[1])) for point in group]
      marker = {"size": size, "color": palettes.get_color(index, palette), "opacity": 0.85}
      figure.add_trace(scatter(
        mode="markers",
        name="{0}: {1}".format(colorbar_title, _number(level)),
        marker=_with_highlight(marker, keys, highlight_key, is_3d=is_3d),
        text=["{0}<br>{1}: {2}".format(hover(point[1]), colorbar_title, _number(level))
              for point in group],
        customdata=keys,
        hovertemplate=hovertemplate,
        **coordinates(group)
      ))

  front = [(values, record) for values, record in points if _key_of(record) in front_keys]
  if front:
    keys = [_key_str(_key_of(point[1])) for point in front]
    marker = {
      "size": size + (2 if is_3d else 6),
      # Hollow, so the color underneath -- which is what the reader chose to
      # look at -- is not the one thing the front hides.
      "symbol": "diamond" if is_3d else "diamond-open",
      "color": palettes.get_color(FRONT_COLOR_INDEX, palette),
      "opacity": 0.55 if is_3d else 1.0,
      "line": {"width": 2, "color": palettes.get_color(FRONT_COLOR_INDEX, palette)},
    }
    figure.add_trace(scatter(
      mode="markers",
      name="on the front",
      marker=_with_highlight(marker, keys, highlight_key, is_3d=is_3d),
      text=[hover(point[1]) for point in front],
      customdata=keys,
      hovertemplate=hovertemplate,
      **coordinates(front)
    ))
  return True


def _front_figure(campaign, chrome, palette, x_metric=None, y_metric=None, z_metric=None,
                   highlight_key=None, filters=(), color_by=None, log_axes=(), zero_axes=()):
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

  spec = _color_spec(campaign, color_by)
  if spec is not None:
    drawn_any = _colored_traces(
      figure, points[True] + points[False], front_keys, spec, palette, drawn, coordinates,
      hover, hovertemplate, bool(z_metric), highlight_key,
    )
    if not drawn_any:
      return _empty_figure(chrome, "No design says what its " + spec["label"] + " was.")
    points = {True: [], False: []}

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
    for axis in log_axes:
      if axis in ("x", "y"):
        layout["scene"][axis + "axis"]["type"] = "log"
    for axis in zero_axes:
      if axis in ("x", "y") and axis not in log_axes:
        # A scene axis has no rangemode, so the range is spelled out: whatever
        # the designs reached, down to zero.
        reach = _reach_of(figure, axis)
        if reach is not None:
          layout["scene"][axis + "axis"]["range"] = [min(0.0, reach[0]), max(0.0, reach[1])]
    layout["margin"] = {"l": 0, "r": 0, "t": 10, "b": 10}
  else:
    layout["xaxis"].update({"title": {"text": _axis_label(campaign, x_metric)}})
    layout["yaxis"].update({"title": {"text": _axis_label(campaign, y_metric)}})
    # A design space spans orders of magnitude more often than not -- a handful
    # of huge designs otherwise flatten everything else against one edge.
    for axis in log_axes:
      if axis in ("x", "y"):
        layout[axis + "axis"]["type"] = "log"
    for axis in zero_axes:
      # Meaningless on a log axis, where zero is infinitely far away.
      if axis in ("x", "y") and axis not in log_axes:
        layout[axis + "axis"]["rangemode"] = "tozero"
  figure.update_layout(**layout)
  return figure


def _reach_of(figure, axis):
  """How far the drawn points go along one axis, across every trace."""
  values = []
  for trace in figure.data:
    for value in (getattr(trace, axis, None) or ()):
      if isinstance(value, (int, float)) and not isinstance(value, bool) and value == value:
        values.append(float(value))
  return (min(values), max(values)) if values else None


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


def _parcoords_figure(campaign, chrome, palette, highlight_key=None, filters=(),
                      from_zero=False, natural=False):
  """
  Every design across every objective at once, as a parallel coordinates plot.

  Each axis is one objective, oriented so that up is always better -- an axis
  being minimized is drawn upside down, unless ``natural`` puts every axis back
  the way a number line runs -- so a front design reads as a line
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
    if from_zero:
      # Every axis measured from zero, so that the width of a band is how big
      # the difference is and not only that there is one.
      value_range = [min(0.0, value_range[0]), max(0.0, value_range[1])]
    if not natural and goal is not None and goal.startswith("min"):
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


######################################
# What drove the results
######################################

MAX_IMPACT_BARS = 18


def _impact_records(campaign, scope):
  """The designs the breakdown is computed over."""
  records = campaign.evaluations
  if "feasible" in (scope or []):
    records = [record for record in records if record.get("feasible") is not False]
  return records


def _impact_figure(campaign, chrome, palette, metric, kinds, records):
  """
  Which choices moved a metric, ranked.

  A bar is the share of the metric's spread that knowing this one choice would
  account for -- corrected for how many values the choice has, so a parameter
  that takes thirty of them does not come top simply for being able to name
  every design (see :func:`~odatix.explorer.core.dse_factors._omega_squared`).

  A bar at zero is not noise: it is the campaign saying this choice did not
  matter for this metric, which is as useful an answer as the top of the list.
  """
  ranked = dse_factors.impacts(campaign, metric, records, kinds=tuple(kinds or ()))
  if not ranked:
    return None
  ranked = ranked[:MAX_IMPACT_BARS]
  # Plotly draws a horizontal bar chart bottom-up, and the biggest belongs on
  # top: the list is read downwards.
  ranked.reverse()

  def direction(result):
    if result["direction"] is None:
      return ""
    if result["direction"] > 0.2:
      return " (more of it, more {0})".format(result["metric"])
    if result["direction"] < -0.2:
      return " (more of it, less {0})".format(result["metric"])
    return " (no simple direction)"

  figure = go.Figure(go.Bar(
    orientation="h",
    x=[result["impact"] for result in ranked],
    y=[result["factor"].label for result in ranked],
    marker={
      "color": [palettes.get_color(KIND_COLOR_INDEX.get(result["factor"].kind, 1), palette)
                for result in ranked],
    },
    text=["{0:.0%}".format(result["impact"]) for result in ranked],
    textposition="outside",
    cliponaxis=False,
    customdata=[
      [_factor_id(result["factor"]), result["factor"].kind_label, result["levels"],
       _number(result["spread"]), str(_number(result["best"])), direction(result)]
      for result in ranked
    ],
    hovertemplate=(
      "%{y} (%{customdata[1]}, %{customdata[2]} values)"
      "<br>accounts for %{x:.0%} of the spread%{customdata[5]}"
      "<br>best on average: %{customdata[4]}"
      "<br>between its best and worst value: %{customdata[3]}"
      "<extra></extra>"
    ),
  ))

  layout = _base_layout(chrome)
  layout["xaxis"].update({"title": {"text": "share of the spread of " + metric},
                          "tickformat": ".0%", "range": [0, 1.08]})
  layout["yaxis"].update({"automargin": True, "title": None})
  layout["margin"] = {"l": 10, "r": 40, "t": 10, "b": 46}
  layout.pop("legend")
  figure.update_layout(**layout)
  return figure


def _factor_figure(campaign, chrome, palette, factor, metric, records, front_keys):
  """
  What one choice did to a metric, value by value.

  A choice with a few values gets one box per value: the spread of a value
  matters as much as its average, since a parameter whose good designs are
  buried among bad ones is not the same finding as one that is good every time.
  A choice with many is drawn as a cloud with the average through it, because
  forty boxes side by side are counted rather than read.

  The designs on the front are drawn over both, so "the search kept picking
  this value" and "this value is good on average" stay two separate readings.
  """
  points = []
  for record in records:
    if record.get("failed"):
      continue
    value = dse_factors.value_of(record, factor)
    measured = dse_factors.metric_of(record, metric)
    if value is None or measured is None:
      continue
    points.append((value, measured, _key_of(record) in front_keys, record))

  if not points:
    return _empty_figure(chrome, "No design says what its " + factor.label + " was.")

  figure = go.Figure()
  as_cloud = factor.numeric and factor.many_levels

  if as_cloud:
    others = [point for point in points if not point[2]]
    if others:
      figure.add_trace(go.Scatter(
        x=[point[0] for point in others], y=[point[1] for point in others],
        mode="markers", name="evaluated",
        marker={"size": 7, "color": palettes.get_color(OTHER_COLOR_INDEX, palette),
                "opacity": 0.45},
        hovertemplate=factor.label + ": %{x}<br>" + metric + ": %{y}<extra></extra>",
      ))
    means = {}
    for value, measured, _on_front, _record in points:
      means.setdefault(value, []).append(measured)
    ordered = sorted(means)
    figure.add_trace(go.Scatter(
      x=ordered, y=[sum(means[value]) / float(len(means[value])) for value in ordered],
      mode="lines+markers", name="average",
      line={"color": chrome["text_color"], "width": 2, "dash": "dot"},
      hovertemplate=factor.label + ": %{x}<br>average " + metric + ": %{y:.4g}<extra></extra>",
    ))
  else:
    box_color = palettes.get_color(OTHER_COLOR_INDEX, palette)
    box_x = []
    box_y = []
    for level in factor.levels:
      label = str(_number(level))
      for point in points:
        if point[0] == level:
          box_x.append(label)
          box_y.append(point[1])
    if box_y:
      figure.add_trace(go.Box(
        x=box_x, y=box_y, name="evaluated",
        boxpoints="outliers", whiskerwidth=0.4,
        marker={"color": _translucent(box_color, 0.45), "size": 4,
                "outliercolor": _translucent(box_color, 0.45),
                "line": {"width": 0}},
        line={"color": _translucent(box_color, 0.75), "width": 1.2},
        fillcolor=_translucent(box_color, 0.12),
        showlegend=False,
        hovertemplate=metric + ": %{y}<extra>%{x}</extra>",
      ))

  front = [point for point in points if point[2]]
  if front:
    figure.add_trace(go.Scatter(
      x=[point[0] if as_cloud else str(_number(point[0])) for point in front],
      y=[point[1] for point in front],
      mode="markers", name="on the front",
      marker={"size": 10, "symbol": "diamond",
              "color": palettes.get_color(FRONT_COLOR_INDEX, palette),
              "line": {"width": 1, "color": chrome["text_color"]}},
      text=[str(point[3].get("configuration", "")) for point in front],
      customdata=[_key_str(_key_of(point[3])) for point in front],
      hovertemplate="%{text}<br>" + factor.label + ": %{x}<br>" + metric +
                    ": %{y}<extra></extra>",
    ))

  layout = _base_layout(chrome)
  layout["xaxis"].update({"title": {"text": factor.label}, "automargin": True})
  layout["yaxis"].update({"title": {"text": metric}})
  if not as_cloud:
    # Categorical, and a numeric factor with few values is categorical here too:
    # its values are the ones that were tried, not a scale between them.
    layout["xaxis"]["type"] = "category"
    layout["xaxis"]["categoryorder"] = "array"
    layout["xaxis"]["categoryarray"] = [str(_number(level)) for level in factor.levels]
    layout["xaxis"]["showgrid"] = False
    # Long value names crowd each other end to end; slanting them keeps the
    # axis readable without stretching the card.
    layout["xaxis"]["tickangle"] = -35 if len(factor.levels) > 6 else 0
    layout["boxgap"] = 0.45
    layout["boxgroupgap"] = 0.2
  figure.update_layout(**layout)
  return figure


def _levels_table(campaign, factor, metric, records, front_keys):
  """
  Every value of a choice, as a table -- including what it cost.

  What a chart of the metric cannot show is how many designs never got a metric
  at all: a value every design of which failed to synthesize is not a value
  with no impact, it is a value that was never really tried, and the two look
  identical on a box plot.
  """
  rows = dse_factors.levels_of(campaign, factor, metric, records=records,
                               front_keys=front_keys, key_of=_key_of)
  if not rows:
    return None

  goal = _goal_of(campaign, metric)
  best_of = max if (goal and goal.startswith("max")) else min
  means = [row["mean"] for row in rows if row["mean"] is not None]
  best_mean = best_of(means) if means else None

  header = ["value", "designs", "failed", "on the front", "share of the front",
            "best " + metric, "average " + metric, "worst " + metric]
  body = []
  for row in rows:
    enrichment = row["enrichment"]
    if enrichment is None:
      share = "--"
    else:
      # Read as "this value is 2.4x as common among the answers as among the
      # designs that were tried", which is what makes it a preference.
      share = "{0:.1f}x".format(enrichment)
    cells = [
      html.Td(str(_number(row["level"])), className="xp-dse-level-name"),
      html.Td(_number(row["designs"])),
      html.Td(_number(row["failed"]) if row["failed"] else "--",
              className="xp-dse-level-failed" if row["failed"] else None),
      html.Td(_number(row["front"]) if row["front"] else "--"),
      html.Td(share, className="xp-dse-level-share" if (enrichment or 0) > 1.2 else None),
      html.Td(_number(row["best"])),
      html.Td(_number(row["mean"]),
              className="xp-dse-level-best" if (row["mean"] is not None
                                                and row["mean"] == best_mean) else None),
      html.Td(_number(row["worst"])),
    ]
    body.append(html.Tr(cells))

  return html.Div(
    html.Table(
      [html.Thead(html.Tr([html.Th(name) for name in header])), html.Tbody(body)],
      className="xp-dse-levels-table",
    ),
    className="xp-dse-table",
  )


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
  Output("xp-dse-color", "options"),
  Output("xp-dse-color", "value"),
  Input("xp-dse-campaign", "value"),
  Input("xp-dse-poll", "n_intervals"),
  Input("odatix-settings", "data"),
  State("xp-dse-color", "value"),
)
def update_color_options(name, _intervals, settings, color_by):
  """
  What the cloud can be colored by.

  Rebuilt as the campaign runs, because what it can be colored by grows with
  it: a parameter that has only ever taken one value is not a color, and
  becomes one the moment a batch tries a second.
  """
  campaign = CAMPAIGNS.get(_result_path(settings), name) if name else None
  if campaign is None:
    return [{"label": "on the front", "value": "front"}], "front"
  options = _color_options(campaign)
  values = [option["value"] for option in options]
  return options, color_by if color_by in values else "front"


@dash.callback(
  Output("xp-dse-impact-metric", "options"),
  Output("xp-dse-impact-metric", "value"),
  Output("xp-dse-factor", "options"),
  Output("xp-dse-factor", "value"),
  Output("xp-dse-impact", "style"),
  Input("xp-dse-campaign", "value"),
  Input("xp-dse-poll", "n_intervals"),
  Input("odatix-settings", "data"),
  State("xp-dse-impact-metric", "value"),
  State("xp-dse-factor", "value"),
)
def update_impact_controls(name, _intervals, settings, metric, factor_id):
  """
  Which metric is being broken down, and by which choice.

  The whole section is hidden when the designs of the campaign differ by
  nothing that was written down -- an archive from before parameters were kept
  with the evaluations. There is no breakdown to show, and an empty chart with
  two dropdowns over it says less than nothing.
  """
  campaign = CAMPAIGNS.get(_result_path(settings), name) if name else None
  if campaign is None:
    return [], None, [], None, {"display": "none"}

  available = dse_factors.factors(campaign)
  if not available:
    return [], None, [], None, {"display": "none"}

  metrics = dse_factors.metrics(campaign)
  metric = metric if metric in metrics else (metrics[0] if metrics else None)

  options = [
    {"label": "{0} ({1})".format(factor.label, factor.kind_label), "value": _factor_id(factor)}
    for factor in available
  ]
  ids = [option["value"] for option in options]
  if factor_id not in ids:
    # Whatever moved the metric most, so the card opens on the answer rather
    # than on whichever parameter happens to sort first.
    ranked = dse_factors.impacts(campaign, metric) if metric else []
    factor_id = _factor_id(ranked[0]["factor"]) if ranked else ids[0]
  return [{"label": name, "value": name} for name in metrics], metric, options, factor_id, None


@dash.callback(
  Output("xp-dse-impact-kinds", "data"),
  *[Output("xp-dse-kind-" + kind, "className") for kind in KIND_ORDER],
  *[Input("xp-dse-kind-" + kind, "n_clicks") for kind in KIND_ORDER],
  State("xp-dse-impact-kinds", "data"),
)
def toggle_kind(*args):
  """
  Turning a kind of factor on and off from its chip.

  The last one cannot be turned off: an empty selection ranks nothing, and a
  reader who clicked their way there would be looking at an empty card with no
  hint of why.
  """
  selected = list(args[-1] or KIND_ORDER)
  clicked = getattr(dash.callback_context, "triggered_id", None)
  for kind in KIND_ORDER:
    if clicked == "xp-dse-kind-" + kind:
      if kind in selected:
        if len(selected) > 1:
          selected.remove(kind)
      else:
        selected.append(kind)
      break
  selected = [kind for kind in KIND_ORDER if kind in selected]
  return [selected] + [
    _kind_chip(kind, kind in selected).className for kind in KIND_ORDER
  ]


@dash.callback(
  Output("xp-dse-factor", "value", allow_duplicate=True),
  Input("xp-dse-impact-graph", "clickData"),
  prevent_initial_call=True,
)
def select_factor_from_bar(click):
  """Clicking a bar of the ranking opens that choice in the card beside it."""
  points = (click or {}).get("points") or []
  if not points:
    return dash.no_update
  data = points[0].get("customdata")
  return data[0] if isinstance(data, list) and data else dash.no_update


@dash.callback(
  Output("xp-dse-impact-slot", "children"),
  Output("xp-dse-factor-slot", "children"),
  Output("xp-dse-factor-caption", "children"),
  Output("xp-dse-levels", "children"),
  Input("xp-dse-campaign", "value"),
  Input("xp-dse-impact-metric", "value"),
  Input("xp-dse-impact-kinds", "data"),
  Input("xp-dse-impact-scope", "value"),
  Input("xp-dse-factor", "value"),
  Input("xp-dse-poll", "n_intervals"),
  Input("theme-dropdown", "value"),
  Input("odatix-settings", "data"),
)
def update_impact(name, metric, kinds, scope, factor_id, _intervals, app_theme, settings):
  campaign = CAMPAIGNS.get(_result_path(settings), name) if name else None
  if campaign is None or not metric:
    return None, None, None, None

  chrome = app_theme_bridge.get_chrome(app_theme)
  palette = palettes.DEFAULT_PALETTE
  config = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "responsive": True}
  records = _impact_records(campaign, scope)
  front_keys = set(_key_of(record) for record in campaign.front)

  impact_figure = _impact_figure(campaign, chrome, palette, metric, kinds, records)
  if impact_figure is None:
    impact = _placeholder(
      "Nothing to rank: either no kind of choice is selected, or none of the designs "
      "that are left measured " + metric + "."
    )
  else:
    impact = _graph(impact_figure, config, id="xp-dse-impact-graph")

  factor = _factor_by_id(campaign, factor_id)
  if factor is None:
    return impact, _placeholder("Pick a choice to look into."), None, None

  detail = _graph(_factor_figure(campaign, chrome, palette, factor, metric, records, front_keys),
                  config, id="xp-dse-factor-graph")
  result = dse_factors.impact_of(campaign, factor, metric, records)
  if result is None:
    caption = "{0}, one box per value".format(factor.label)
  else:
    caption = "{0} accounts for {1:.0%} of the spread of {2}, over {3} designs".format(
      factor.label, result["impact"], metric, result["designs"])

  levels = _levels_table(campaign, factor, metric, records, front_keys)
  if levels is not None:
    levels = html.Div([_section("{0}, value by value".format(factor.label)), levels],
                      className="xp-dse-section")
  return impact, detail, caption, levels


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
  Output("xp-dse-parcoords-subtitle", "children"),
  Output("xp-dse-front-table-slot", "children"),
  Output("xp-dse-body", "children"),
  Input("xp-dse-campaign", "value"),
  Input("xp-dse-axis-x", "value"),
  Input("xp-dse-axis-y", "value"),
  Input("xp-dse-axis-z", "value"),
  Input("xp-dse-filters", "value"),
  Input("xp-dse-color", "value"),
  Input("xp-dse-scales", "value"),
  Input("xp-dse-parcoords-scales", "value"),
  Input("xp-dse-poll", "n_intervals"),
  Input("theme-dropdown", "value"),
  Input("odatix-settings", "data"),
  Input("xp-dse-highlight", "data"),
)
def update_body(name, x_metric, y_metric, z_metric, filters, color_by, scales, parcoords_scales,
                 _intervals, app_theme, settings, highlight_key):
  result_path = _result_path(settings)
  campaign = CAMPAIGNS.get(result_path, name) if name else None
  if campaign is None:
    return (_empty_state(result_path), {"display": "none"},
            None, None, None, None, None, None, None)

  scales = scales or []
  log_axes = [axis for axis in ("x", "y") if axis in scales]
  zero_axes = [axis for axis in ("x", "y") if axis + "0" in scales]

  chrome = app_theme_bridge.get_chrome(app_theme)
  palette = palettes.DEFAULT_PALETTE
  # responsive: the two charts share a grid that reflows with the window, and a
  # figure sized once at mount would keep the width the cell had then.
  config = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "responsive": True}

  filters = filters or []

  front_figure = _front_figure(campaign, chrome, palette, x_metric, y_metric, z_metric,
                                highlight_key=highlight_key, filters=filters,
                                color_by=color_by, log_axes=log_axes, zero_axes=zero_axes)
  front = _graph(front_figure, config, id="xp-dse-front-graph")
  progress = _progress_figure(campaign, chrome, palette)
  progress = _graph(progress, config) if progress is not None else _placeholder(
    "This archive holds no per-batch history: it was written by a version of Odatix "
    "that did not record one. The next run of the campaign will."
  )

  natural_axes = "natural" in (parcoords_scales or [])
  parcoords_figure = _parcoords_figure(campaign, chrome, palette, highlight_key=highlight_key,
                                        filters=filters,
                                        from_zero="zero" in (parcoords_scales or []),
                                        natural=natural_axes)
  parcoords = _graph(parcoords_figure, config, id="xp-dse-parcoords-graph")
  parcoords_subtitle = (
    "every design across every objective at once -- low values at the bottom of every axis"
    if natural_axes else
    "every design across every objective at once -- top is always better"
  )

  front_table = html.Div([_section("The front", len(campaign.front)),
                          _front_table(campaign, highlight_key, filters=filters)],
                         className="xp-dse-section")
  return (_summary(campaign), None, front,
          _front_caption(campaign, x_metric, y_metric, z_metric), progress, parcoords,
          parcoords_subtitle, front_table, _failures(campaign))
