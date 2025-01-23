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

def add_trace_to_lines_fig(fig, x_values, y_values, mode, architecture, frequency, targets, target, selected_metric_display, unit, color_id, symbol_id, toggle_legendgroup):
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
      connectgaps=True,
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

# Radar 


def make_legend_chart(
  explorer,
  df,
  selected_results,
  selected_yaml,
  targets_for_yaml,
  visible_architectures,
  visible_targets,
  toggle_legendgroup,
  toggle_title,
  color_mode,
  symbol_mode,
  background,
  toggle_unique_architectures,
  toggle_unique_targets,
  mode
):
  fig = go.Figure()

  if not visible_architectures:
    return None

  unique_configurations = sorted(df["Configuration"].unique())

  i_target = -1
  for i_unique_target, target in enumerate(explorer.all_targets): 
    if target in explorer.dfs[selected_yaml]["Target"].unique():
      i_target = i_target + 1
    if target in visible_targets:
      targets = [target] * len(unique_configurations)
      i_architecture = -1
      for i_unique_architecture, architecture in enumerate(explorer.all_architectures):
        if architecture in explorer.dfs[selected_yaml]["Architecture"].unique():
          i_architecture = i_architecture + 1
        if architecture not in visible_architectures:
          continue

        df_architecture = df[df["Architecture"] == architecture]

        df_fmax = df_architecture[df_architecture["Type"] == "Fmax"]
        if selected_results in ["All", "Fmax"] and not df_fmax.empty:

          if color_mode == "architecture":
            color_id = i_unique_architecture if toggle_unique_architectures else i_architecture
          elif color_mode == "target":
            color_id = i_unique_target if toggle_unique_targets else i_target
          else:
            color_id = 0

          if symbol_mode == "none":
            symbol_id = 0
          elif symbol_mode == "architecture":
            symbol_id = i_unique_architecture if toggle_unique_architectures else i_architecture
          elif symbol_mode == "target":
            symbol_id = i_unique_target if toggle_unique_targets else i_target
          else:
            symbol_id = 0
            
          fig.add_trace(
            go.Scatterpolar(
              r=[None],
              theta=df_fmax["Configuration"],
              mode=mode,
              name=f"{architecture} @ fmax",
              legendgroup=target,
              legendgrouptitle_text=str(target) if toggle_legendgroup else None,
              marker_size=10,
              marker_color=legend.get_color(color_id),
              marker_symbol=legend.get_marker_symbol(symbol_id),
            )
          )

        df_range = df_architecture[df_architecture["Type"] == "Custom Freq"]
        if selected_results in ["All", "Custom Freq"] and not df_range.empty:
          for i_freq, frequency in enumerate(explorer.all_frequencies):
            df_frequency = df_architecture[df_architecture["Frequency"] == frequency]
            if not df_frequency.empty:

              if color_mode == "architecture":
                color_id = i_unique_architecture if toggle_unique_architectures else i_architecture
              elif color_mode == "target":
                color_id = i_unique_target if toggle_unique_targets else i_target
              else:
                color_id = i_freq + 1
                
              if symbol_mode == "none":
                symbol_id = 0
              elif symbol_mode == "architecture":
                symbol_id = i_unique_architecture if toggle_unique_architectures else i_architecture
              elif symbol_mode == "target":
                symbol_id = i_unique_target if toggle_unique_targets else i_target
              else:
                symbol_id = i_freq + 1
          
              fig.add_trace(
                go.Scatterpolar(
                  r=[None],
                  theta=df_range["Configuration"],
                  mode=mode,
                  name=f"{architecture} @ {frequency} MHz",
                  legendgroup=target,
                  legendgrouptitle_text=str(target) if toggle_legendgroup else None,
                  marker_size=10,
                  marker_color=legend.get_color(color_id),
                  marker_symbol=legend.get_marker_symbol(symbol_id),
                )
              )

  fig.update_layout(
    polar_bgcolor="rgba(255, 255, 255, 0)",
    paper_bgcolor=background,
    showlegend=True,
    legend_groupclick="toggleitem",
    margin=dict(l=60, r=60, t=60, b=60),
    title="Legend" if toggle_title else "",
    title_x=0.5,
    polar=dict(radialaxis=dict(visible=False), angularaxis=dict(visible=False)),
    autosize=True,
    legend_x=0,
    legend_y=1,
    width=475,
    height=475,
  )

  return fig


def make_radar_chart(
  explorer,
  df,
  units,
  metric,
  selected_results,
  selected_yaml,
  targets_for_yaml,
  visible_architectures,
  visible_targets,
  legend_dropdown,
  toggle_legendgroup,
  toggle_title,
  toggle_close,
  color_mode,
  symbol_mode,
  background,
  toggle_unique_architectures,
  toggle_unique_targets,
  mode,
):
  numeric_df = df.copy()
  numeric_df.loc[:, metric] = pd.to_numeric(numeric_df[metric], errors="coerce")
  numeric_df = numeric_df.dropna(subset=[metric])

  if df.empty:
    fig = go.Figure(data=go.Scatterpolar())
    fig.update_layout(
      polar=dict(radialaxis=dict(visible=False), angularaxis=dict(showticklabels=False)),
      showlegend=False,
      title=metric.replace("_", " ") if metric is not None else "",
      title_x=0.5,
    )
    return fig

  metric_display = metric.replace("_", " ")
  unit = legend.unit_to_html(units.get(metric, ""))

  unique_configurations = sorted(df["Configuration"].unique())
  nb_points = len(unique_configurations) + 1 if toggle_close else len(unique_configurations)

  fig = go.Figure(
    data=go.Scatterpolar(
      r=[None for c in unique_configurations],
      theta=unique_configurations,
      marker_color="rgba(0, 0, 0, 0)",
      showlegend=False,
    )
  )

  i_target = -1
  for i_unique_target, target in enumerate(explorer.all_targets):
    if target in targets_for_yaml:
      i_target = i_target + 1
    if target not in visible_targets:
      continue
      
    targets = [target] * nb_points

    i_architecture = -1
    for i_unique_architecture, architecture in enumerate(explorer.all_architectures):
      if architecture in explorer.dfs[selected_yaml]["Architecture"].unique():
        i_architecture = i_architecture + 1
      if architecture in visible_architectures:
        df_architecture = df[
          (df["Architecture"] == architecture) & 
          (df["Target"] == target)
        ]

        df_architecture_fmax = df_architecture[df_architecture["Type"] == "Fmax"]
        if selected_results in ["All", "Fmax"] and not df_architecture_fmax.empty:

          if toggle_close:
            first_row = df_architecture_fmax.iloc[0:1]
            df_architecture_fmax = safe_df_append(df_architecture_fmax, first_row)

          if color_mode == "architecture":
            color_id = i_unique_architecture if toggle_unique_architectures else i_architecture
          elif color_mode == "target":
            color_id = i_unique_target if toggle_unique_targets else i_target
          else:
            color_id = 0

          if symbol_mode == "none":
            symbol_id = 0
          elif symbol_mode == "architecture":
            symbol_id = i_unique_architecture if toggle_unique_architectures else i_architecture
          elif symbol_mode == "target":
            symbol_id = i_unique_target if toggle_unique_targets else i_target
          else:
            symbol_id = 0

          fig.add_trace(
            go.Scatterpolar(
              r=df_architecture_fmax[metric],
              theta=df_architecture_fmax["Configuration"],
              mode=mode,
              name=f"{architecture} @ fmax",
              customdata=targets,
              legendgroup=target,
              legendgrouptitle_text=str(target) if toggle_legendgroup else None,
              marker_size=10,
              marker_color=legend.get_color(color_id),
              marker_symbol=legend.get_marker_symbol(symbol_id),
              hovertemplate="<br>".join(
                [
                  "Architecture: %{fullData.name}",
                  "Configuration: %{theta}",
                  "Target: %{customdata}",
                  "Frequency: fmax",
                  str(metric_display) + ": %{r} " + unit,
                  "<extra></extra>",
                ]
              ),
            )
          )

        df_architecture_range = df_architecture[df_architecture["Type"] == "Custom Freq"]
        if selected_results in ["All", "Custom Freq"] and not df_architecture_range.empty:
          for i_freq, frequency in enumerate(explorer.all_frequencies):
            df_frequency = df_architecture_range[df_architecture_range["Frequency"] == frequency]
            frequencies = [f"{frequency} MHz"] * nb_points

            if toggle_close:
              first_row = df_frequency.iloc[0:1]
              df_frequency = safe_df_append(df_frequency, first_row)
            
            if color_mode == "architecture":
              color_id = i_architecture
            elif color_mode == "target":
              color_id = i_target
            else:
              color_id = i_freq + 1
              
            if symbol_mode == "none":
              symbol_id = 0
            elif symbol_mode == "architecture":
              symbol_id = i_architecture
            elif symbol_mode == "target":
              symbol_id = i_target
            else:
              symbol_id = i_freq + 1

            fig.add_trace(
              go.Scatterpolar(
                r=df_frequency[metric],
                theta=df_frequency["Configuration"],
                mode=mode,
                name=f"{architecture} @ {frequency} MHz",
                customdata=[list(a) for a in zip(targets, frequencies)],
                legendgroup=target,
                legendgrouptitle_text=str(target) if toggle_legendgroup else None,
                marker_size=10,
                marker_color=legend.get_color(color_id),
                marker_symbol=legend.get_marker_symbol(symbol_id),
                hovertemplate="<br>".join(
                  [
                    "Architecture: %{fullData.name}",
                    "Configuration: %{theta}",
                    "Target: %{customdata[0]}",
                    "Frequency: %{customdata[1]}",
                    str(metric_display) + ": %{r} " + unit,
                    "<extra></extra>",
                  ]
                ),
              )
            )

  fig.update_layout(
    # template='plotly_dark',
    paper_bgcolor=background,
    polar=dict(radialaxis=dict(visible=True, range=[0, numeric_df[metric].max() if not df[metric].empty else 1])),
    showlegend="show_legend" in legend_dropdown,
    legend_groupclick="toggleitem",
    margin=dict(l=60, r=60, t=60, b=60),
    title=metric_display if toggle_title else None,
    title_x=0.5,
    width=840 if "show_legend" in legend_dropdown else 475,
    height=475,
  )

  return fig


def make_figure_div(fig, filename, dl_format, remove_zoom=False):
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
      style={"flex": "0 0 auto", "margin": "0px"},
    )
  else:
    return html.Div([html.Div([], style={"width": "475px"})], style={"flex": "0 0 auto", "margin": "0px"})


def make_all_radar_charts(
  explorer,
  df,
  units,
  metrics,
  selected_results,
  selected_yaml,
  targets_for_yaml,
  visible_architectures,
  visible_targets,
  yaml_name,
  legend_dropdown,
  toggle_legendgroup,
  toggle_title,
  toggle_lines,
  toggle_close,
  color_mode,
  symbol_mode,
  dl_format,
  background,
  toggle_unique_architectures,
  toggle_unique_targets,
):
  radar_charts = []

  mode = "lines+markers" if toggle_lines else "markers"

  for metric in metrics:
    fig = make_radar_chart(
      explorer,
      df,
      units,
      metric,
      selected_results,
      selected_yaml,
      targets_for_yaml,
      visible_architectures,
      visible_targets,
      legend_dropdown,
      toggle_legendgroup,
      toggle_title,
      toggle_close,
      color_mode,
      symbol_mode,
      background,
      toggle_unique_architectures,
      toggle_unique_targets,
      mode,
    )
    filename = "Odatix-{}-{}-{}".format(yaml_name, __name__, metric)
    radar_charts.append(make_figure_div(fig, filename, dl_format))

  # Add legend chart
  if "separate_legend" in legend_dropdown:
    legend_fig = make_legend_chart(
      explorer,
      df,
      selected_results,
      selected_yaml,
      targets_for_yaml,
      visible_architectures,
      visible_targets,
      toggle_legendgroup,
      toggle_title,
      color_mode,
      symbol_mode,
      background,
      toggle_unique_architectures,
      toggle_unique_targets,
      mode
    )
    radar_charts.append(
      make_figure_div(legend_fig, "Odatix-" + str(__name__) + "-legend", dl_format, remove_zoom=True)
    )

  return radar_charts