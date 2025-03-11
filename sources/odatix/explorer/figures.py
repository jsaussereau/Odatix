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
  theme,
  toggle_unique_architectures,
  toggle_unique_targets,
  dissociate_domain,
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

        if dissociate_domain != "None" and dissociate_domain in df_architecture.columns:
          dissociation_values = df_architecture[dissociate_domain].dropna().unique()
          cleaned_configurations = [legend.clean_configuration_name(cfg, dissociate_domain) for cfg in unique_configurations]
        else:
          dissociation_values = [None]
          cleaned_configurations = unique_configurations

        i_dissociate_domain = -1
        for dissociation_value in dissociation_values:
          df_filtered = df_architecture.copy()
          if dissociation_value is not None:
            df_filtered = df_filtered[df_filtered[dissociate_domain] == dissociation_value]
            architecture_diplay = architecture + f" [{dissociate_domain}:{dissociation_value}]" 
          else:
            architecture_diplay = architecture
          i_dissociate_domain += 1

          df_fmax = df_filtered[df_filtered["Type"] == "Fmax"]
          if selected_results in ["All", "Fmax"] and not df_fmax.empty:

            if color_mode == "architecture":
              color_id = i_unique_architecture if toggle_unique_architectures else i_architecture
            elif color_mode == "target":
              color_id = i_unique_target if toggle_unique_targets else i_target
            elif color_mode == "domain_value":
              color_id = i_dissociate_domain
            else:
              color_id = 0

            if symbol_mode == "none":
              symbol_id = 0
            elif symbol_mode == "architecture":
              symbol_id = i_unique_architecture if toggle_unique_architectures else i_architecture
            elif symbol_mode == "target":
              symbol_id = i_unique_target if toggle_unique_targets else i_target
            elif symbol_mode == "domain_value":
              symbol_id = i_dissociate_domain
            else:
              symbol_id = 0
              
            fig.add_trace(
              go.Scatterpolar(
                r=[None],
                theta=df_fmax["Configuration"],
                mode=mode,
                name=f"{architecture_diplay} @ fmax",
                legendgroup=target,
                legendgrouptitle_text=str(target) if toggle_legendgroup else None,
                marker_size=10,
                marker_color=legend.get_color(color_id),
                marker_symbol=legend.get_marker_symbol(symbol_id),
              )
            )

          df_range = df_filtered[df_filtered["Type"] == "Custom Freq"]
          if selected_results in ["All", "Custom Freq"] and not df_range.empty:
            for i_freq, frequency in enumerate(explorer.all_frequencies):
              df_frequency = df_range[df_range["Frequency"] == frequency]
              if not df_frequency.empty:

                if color_mode == "architecture":
                  color_id = i_unique_architecture if toggle_unique_architectures else i_architecture
                elif color_mode == "target":
                  color_id = i_unique_target if toggle_unique_targets else i_target
                elif color_mode == "domain_value":
                  color_id = i_dissociate_domain
                else:
                  color_id = i_freq + 1
                  
                if symbol_mode == "none":
                  symbol_id = 0
                elif symbol_mode == "architecture":
                  symbol_id = i_unique_architecture if toggle_unique_architectures else i_architecture
                elif symbol_mode == "target":
                  symbol_id = i_unique_target if toggle_unique_targets else i_target
                elif symbol_mode == "domain_value":
                  symbol_id = i_dissociate_domain
                else:
                  symbol_id = i_freq + 1
            
                fig.add_trace(
                  go.Scatterpolar(
                    r=[None],
                    theta=df_range["Configuration"],
                    mode=mode,
                    name=f"{architecture_diplay} @ {frequency} MHz",
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
    template=theme,
  )

  return fig

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

