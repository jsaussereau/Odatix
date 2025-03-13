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

import os
import re
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd

import odatix.explorer.legend as legend

from odatix.lib.utils import safe_df_append

def add_trace_to_lines_fig(fig, x_values, y_values, mode, architecture, frequency, targets, target, selected_metric_display, unit, color_id, symbol_id, toggle_legendgroup, toggle_connect_gaps):
  fig.add_trace(
    go.Scatter(
      x=x_values,
      y=y_values,
      mode=mode,
      line=dict(dash="dot") if mode == "lines+markers" else None,
      marker=dict(
        size=10,
        color=legend.get_color(color_id),
        symbol=legend.get_marker_symbol(symbol_id),
      ),
      name=f"{architecture} @ {frequency}" if frequency else architecture,
      customdata=targets,
      legendgroup=target,
      legendgrouptitle_text=str(target) if toggle_legendgroup else None,
      connectgaps=True if toggle_connect_gaps else False,
      hovertemplate="<br>".join(
        [
          "Architecture: %{fullData.name}",
          "Configuration: %{x}",
          "Target: %{customdata}",
          selected_metric_display + ": %{y} " + unit,
          "<extra></extra>",
        ]
      ),
    )
  )

def add_trace_to_columns_fig(fig, x_values, y_values, mode, architecture, frequency, targets, target, selected_metric_display, unit, color_id, pattern_id, toggle_legendgroup):
  fig.add_trace(
    go.Bar(
      x=x_values,
      y=y_values,
      marker=dict(
        color=legend.get_color(color_id),
        pattern=dict(
          shape=legend.get_pattern(pattern_id)
        )
      ),
      name=f"{architecture} @ {frequency}" if frequency else architecture,
      customdata=targets,
      legendgroup=target,
      legendgrouptitle_text=str(target) if toggle_legendgroup else None,
      hovertemplate="<br>".join(
        [
          "Architecture: %{fullData.name}",
          "Configuration: %{x}",
          "Target: %{customdata}",
          selected_metric_display + ": %{y} " + unit,
          "<extra></extra>",
        ]
      ),
    )
  )

def add_trace_to_scatter_fig(fig, x_values, y_values, mode, architecture, frequencies, frequency, config_names, targets, target, selected_metric_x_display, selected_metric_y_display, unit_x, unit_y, color_id, symbol_id, toggle_lines, toggle_legendgroup):
  fig.add_trace(
    go.Scatter(
      x=x_values,
      y=y_values,
      mode=mode,
      line=dict(dash="dot") if toggle_lines else None,
      marker=dict(
        size=10,
        color=legend.get_color(color_id ),
        symbol=legend.get_marker_symbol(symbol_id),
      ),
      name=f"{architecture} @ {frequency}" if frequency else architecture,
      customdata=[list(a) for a in zip(targets, frequencies)],
      legendgroup=target,
      legendgrouptitle_text=str(target) if toggle_legendgroup else None,
      connectgaps=True,
      text=config_names,
      textposition="top center",
      hovertemplate="<br>".join(
        [
          "Architecture: %{fullData.name}",
          "Configuration: %{text}",
          "Target: %{customdata[0]}",
          "Frequency: %{customdata[1]}",
          selected_metric_x_display + ": %{x} " + unit_x,
          selected_metric_y_display + ": %{y} " + unit_y,
          "<extra></extra>",
        ]
      ),
    )
  )

def add_trace_to_scatter3d_fig(fig, x_values, y_values, z_values, mode, architecture, frequencies, frequency, config_names, targets, target, selected_metric_x_display, selected_metric_y_display, selected_metric_z_display, unit_x, unit_y, unit_z, color_id, symbol_id, toggle_lines, toggle_legendgroup):
  fig.add_trace(
    go.Scatter3d(
      x=x_values,
      y=y_values,
      z=z_values,
      mode=mode,
      line=dict(dash="dot") if toggle_lines else None,
      marker=dict(
        size=5,
        color=legend.get_color(color_id ),
        symbol=legend.get_marker_symbol(symbol_id),
      ),
      name=f"{architecture} @ {frequency}" if frequency else architecture,
      customdata=[list(a) for a in zip(targets, frequencies)],
      legendgroup=target,
      legendgrouptitle_text=str(target) if toggle_legendgroup else None,
      connectgaps=True,
      text=config_names,
      textposition="top center",
      hovertemplate="<br>".join(
        [
          "Architecture: %{fullData.name}",
          "Configuration: %{text}",
          "Target: %{customdata[0]}",
          "Frequency: %{customdata[1]}",
          selected_metric_x_display + ": %{x} " + unit_x,
          selected_metric_y_display + ": %{y} " + unit_y,
          selected_metric_z_display + ": %{z} " + unit_z,
          "<extra></extra>",
        ]
      ),
    )
  )

def add_trace_to_radar_fig(fig, theta_values, r_values, mode, architecture, frequency, targets, target, selected_metric_display, unit, color_id, symbol_id, toggle_legendgroup, toggle_connect_gaps):
  fig.add_trace(
  go.Scatterpolar(
    theta=theta_values,
    r=r_values,
    mode=mode,
    name=f"{architecture} @ {frequency}" if frequency else architecture,
    customdata=targets,
    legendgroup=target,
    legendgrouptitle_text=str(target) if toggle_legendgroup else None,
    connectgaps=True if toggle_connect_gaps else False,
    marker_size=10,
    marker_color=legend.get_color(color_id),
    marker_symbol=legend.get_marker_symbol(symbol_id),
    hovertemplate="<br>".join(
      [
        "Architecture: %{fullData.name}",
        "Configuration: %{theta}",
        "Target: %{customdata}",
        selected_metric_display + ": %{y} " + unit,
        "<extra></extra>",
      ]
    ),
  )
)

# Overview 

def make_figure_div(fig, filename, dl_format, page_wide=False, remove_zoom=False):
  page_wide_style = {"width": "100%", "height": "100%", "display": "inline-block", "vertical-align": "top"}
  normal_style = {"flex": "0 0 auto", "margin": "0px"}

  if fig is not None:
    to_remove = ["lasso", "select"]
    if remove_zoom:
      to_remove.append("zoom")
    return html.Div(
      [
        dcc.Graph(
          figure=fig,
          style={"width": "100%"},
          config={
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": to_remove,
            "toImageButtonOptions": {
              "format": dl_format,
              "scale": 3,
              "filename": filename
            },
          },
        )
      ],
      style=page_wide_style if page_wide else normal_style,
    )
  else:
    return html.Div([html.Div([], style={"width": "475px"})], style={"flex": "0 0 auto", "margin": "0px"})
