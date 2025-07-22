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
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go

import odatix.explorer.legend as legend
import odatix.explorer.content_lib as content_lib
import odatix.explorer.figures as figures
import odatix.explorer.themes as themes

def setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs):

  @explorer.app.callback(
    Output("graph-scatter3d", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input("metric-x-dropdown", "value"),
      Input("metric-y-dropdown", "value"),
      Input("metric-z-dropdown", "value"),
      Input("results-dropdown", "value"),
      Input("show-all-architectures", "n_clicks"),
      Input("hide-all-architectures", "n_clicks"),
      Input("toggle-legend", "value"),
      Input("toggle-legendgroup", "value"),
      Input("toggle-title", "value"),
      Input("toggle-lines-scatter", "value"),
      Input("toggle-labels", "value"),
      Input("toggle-zero-axis", "value"),
      Input("color-mode-dropdown", "value"),
      Input("symbol-mode-dropdown", "value"),
      Input("dl-format-dropdown", "value"),
      Input("background-dropdown", "value"),
      Input("theme-dropdown", "value"),
      Input("toggle-unique-architectures", "value"),
      Input("toggle-unique-targets", "value"),
      Input("dissociate-domain-dropdown", "value"),
    ]
    + all_checklist_inputs  
  )
  def update_graph_3d(
    selected_yaml,
    selected_metric_x,
    selected_metric_y,
    selected_metric_z,
    selected_results,
    show_all,
    hide_all,
    toggle_legend,
    toggle_legendgroup,
    toggle_title,
    toggle_lines,
    toggle_labels,
    toggle_zero_axis,
    color_mode,
    symbol_mode,
    dl_format,
    background,
    theme,
    toggle_unique_architectures,
    toggle_unique_targets,
    dissociate_domain,
    *checklist_values,
  ):
    try:
      arch_checklist_values = checklist_values[:len(all_architecture_inputs)]
      target_checklist_values = checklist_values[len(all_architecture_inputs):len(all_architecture_inputs) + len(all_target_inputs)]
      domain_checklist_values = checklist_values[len(all_architecture_inputs) + len(all_target_inputs):]

      if not selected_yaml or selected_yaml not in explorer.dfs:
        return html.Div(className="error", children=[html.Div("Please select a YAML file.")])

      selected_metric_x_display = selected_metric_x.replace("_", " ") if selected_metric_x is not None else ""
      selected_metric_y_display = selected_metric_y.replace("_", " ") if selected_metric_y is not None else ""
      selected_metric_z_display = selected_metric_z.replace("_", " ") if selected_metric_z is not None else ""

      unit_x = legend.unit_to_html(explorer.units[selected_yaml].get(selected_metric_x, ""))
      unit_y = legend.unit_to_html(explorer.units[selected_yaml].get(selected_metric_y, ""))
      unit_z = legend.unit_to_html(explorer.units[selected_yaml].get(selected_metric_z, ""))

      selected_metric_x_display_unit = (
        selected_metric_x_display + " (" + unit_x + ")" if unit_x else selected_metric_x_display
      )
      selected_metric_y_display_unit = (
        selected_metric_y_display + " (" + unit_y + ")" if unit_y else selected_metric_y_display
      )
      selected_metric_z_display_unit = (
        selected_metric_z_display + " (" + unit_z + ")" if unit_z else selected_metric_z_display
      )

      ctx = dash.callback_context
      triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

      if triggered_id in ["show-all-architectures", "hide-all-architectures"]:
        visible_architectures = set(
          explorer.dfs[selected_yaml]["Architecture"].unique() if triggered_id == "show-all-architectures" else []
        )
      else:
        visible_architectures = set(
          architecture for i, architecture in enumerate(explorer.all_architectures) if arch_checklist_values[i] and architecture in explorer.dfs[selected_yaml]["Architecture"].unique()
        )

      if triggered_id in ["show-all-targets", "hide-all-targets"]:
        visible_targets = set(
          explorer.dfs[selected_yaml]["Target"].unique() if triggered_id == "show-all-targets" else []
        )
      else:
        visible_targets = set(
          target for i, target in enumerate(explorer.all_targets) if target_checklist_values[i] and target in explorer.dfs[selected_yaml]["Target"].unique()
        )
      
      i_current_value = 0
      domains = {}
      for domain in explorer.all_param_domains.keys():
        domains[domain] = {}
        for config in explorer.all_param_domains[domain]:
          visible = True if domain_checklist_values[i_current_value] else False
          domains[domain].update({f'{config}': visible})
          i_current_value += 1

      filtered_df = explorer.dfs[selected_yaml][
        explorer.dfs[selected_yaml]["Architecture"].isin(visible_architectures)
      ]

      for domain, configs in domains.items():
        if domain in filtered_df.columns:
          filtered_df.loc[:, domain] = filtered_df[domain].fillna("None")
          excluded_values = [config for config, is_visible in configs.items() if not is_visible]

          # Apply exclusion only if there are forbidden values in the column
          if any(filtered_df[domain].isin(excluded_values)):
            filtered_df = filtered_df[~filtered_df[domain].isin(excluded_values)]

      fig = go.Figure()

      i_target = -1
      for i_unique_target, target in enumerate(explorer.all_targets):
        if target in explorer.dfs[selected_yaml]["Target"].unique():
          i_target = i_target + 1
        if target not in visible_targets:
          continue

        i_architecture = -1
        for i_unique_architecture, architecture in enumerate(explorer.all_architectures):
          if architecture in explorer.dfs[selected_yaml]["Architecture"].unique():
            i_architecture = i_architecture + 1
          if architecture in visible_architectures:
            df_architecture_target = filtered_df[
              (filtered_df["Architecture"] == architecture) & 
              (filtered_df["Target"] == target)
            ]
            if df_architecture_target.empty:
              continue

            mode = "lines+markers" if toggle_lines else "markers"

            if dissociate_domain != "None" and dissociate_domain in df_architecture_target.columns:
              dissociation_values = df_architecture_target[dissociate_domain].dropna().unique()
              # cleaned_configurations = [legend.clean_configuration_name(cfg, dissociate_domain) for cfg in unique_configurations]
            else:
              dissociation_values = [None]
              # cleaned_configurations = unique_configurations

            i_dissociate_domain = -1
            for dissociation_value in dissociation_values:
              df_filtered = df_architecture_target.copy()
              if dissociation_value is not None and dissociation_value != "None":
                df_filtered = df_filtered[df_filtered[dissociate_domain] == dissociation_value]
                architecture_diplay = architecture + f" [{dissociate_domain.replace('__main__', 'main')}:{dissociation_value}]" 
              else:
                architecture_diplay = architecture
              i_dissociate_domain += 1

              df_fmax = df_filtered[df_filtered["Type"] == "Fmax"]
              if selected_results in ["All", "Fmax"] and not df_fmax.empty:
                if selected_metric_x is None or selected_metric_x not in df_fmax.columns:
                  return html.Div(className="error", children=[html.Div("Please select a valid x metric.")])
                if selected_metric_y is None or selected_metric_y not in df_fmax.columns:
                  return html.Div(className="error", children=[html.Div("Please select a valid y metric.")])
                if selected_metric_z is None or selected_metric_z not in df_fmax.columns:
                  return html.Div(className="error", children=[html.Div("Please select a valid z metric.")])

                x_values = df_fmax[selected_metric_x].tolist()
                y_values = df_fmax[selected_metric_y].tolist()
                z_values = df_fmax[selected_metric_z].tolist()
                config_names = df_fmax["Configuration"].tolist()
                cleaned_config_names = [legend.clean_configuration_name(cfg, dissociate_domain) for cfg in config_names]
                targets = [target] * len(x_values)
                frequencies = ["fmax"] * len(x_values)

                if color_mode == "architecture":
                  color_id = i_unique_architecture if toggle_unique_architectures else i_architecture
                elif color_mode == "target":
                  color_id = i_unique_target if toggle_unique_targets else i_target
                elif color_mode == "domain_value":
                  color_id = i_dissociate_domain if dissociation_value != "None" else -1
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

                if toggle_labels:
                  mode += "+text"

                figures.add_trace_to_scatter3d_fig(
                  fig, x_values, y_values, z_values, mode, architecture_diplay, frequencies, "fmax", cleaned_config_names,
                  targets, target, selected_metric_x_display, selected_metric_y_display, selected_metric_z_display,
                  unit_x, unit_y, unit_z, color_id, symbol_id, toggle_lines, toggle_legendgroup
                )

              df_range = df_filtered[df_filtered["Type"] == "Custom Freq"]
              if selected_results in ["All", "Custom Freq"] and not df_range.empty:
                for i_freq, frequency in enumerate(explorer.all_frequencies):
                  df_frequency = df_range[df_range["Frequency"] == frequency]
                  if df_frequency.empty:
                    continue

                  if selected_metric_x is None or selected_metric_x not in df_frequency.columns:
                    return html.Div(className="error", children=[html.Div("Please select a valid x metric.")])
                  if selected_metric_y is None or selected_metric_y not in df_frequency.columns:
                    return html.Div(className="error", children=[html.Div("Please select a valid y metric.")])

                  x_values = df_frequency[selected_metric_x].tolist()
                  y_values = df_frequency[selected_metric_y].tolist()
                  z_values = df_frequency[selected_metric_z].tolist()
                  config_names = df_frequency["Configuration"].tolist()
                  cleaned_config_names = [legend.clean_configuration_name(cfg, dissociate_domain) for cfg in config_names]
                  targets = [target] * len(x_values)
                  frequencies = [f"{frequency} MHz"] * len(x_values)

                  if color_mode == "architecture":
                    color_id = i_architecture
                  elif color_mode == "target":
                    color_id = i_target
                  elif color_mode == "domain_value":
                    color_id = i_dissociate_domain if dissociation_value != "None" else -1
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

                  if toggle_labels:
                    mode += "+text"

                  figures.add_trace_to_scatter3d_fig(
                    fig, x_values, y_values, z_values, mode, architecture_diplay, frequencies, f"{frequency} MHz", cleaned_config_names,
                    targets, target, selected_metric_x_display, selected_metric_y_display, selected_metric_z_display,
                    unit_x, unit_y, unit_z, color_id, symbol_id, toggle_lines, toggle_legendgroup
                  )
      axes = {
        "backgroundcolor": themes.get_plot_bgcolor(theme, default=None),
        "range": [0, None] if toggle_zero_axis else [None, None],
      }

      fig.update_layout(
        paper_bgcolor=background,
        showlegend=True if toggle_legend else False,
        legend_groupclick="toggleitem",
        scene=dict(
          xaxis_title=selected_metric_x_display_unit,
          yaxis_title=selected_metric_y_display_unit,
          zaxis_title=selected_metric_z_display_unit,
          xaxis=axes,
          yaxis=axes,
          zaxis=axes,
          camera_eye=dict(x=1, y=2.5, z=1.25)
        ),
        title=selected_metric_z_display + " vs " + selected_metric_y_display + " vs " + selected_metric_x_display if toggle_title else None,
        title_x=0.5,
        autosize=True,
        template=theme,
        modebar={
          "bgcolor": themes.get_page_bgcolor(theme, default=None),
          "color": themes.get_button_color(theme, default=None),
          "activecolor": themes.get_button_active_color(theme, default=None),
        }
      )

      fig.update_traces(marker_size=3)

      filename = "Odatix-{}-{}-vs-{}-vs-{}".format(
        os.path.splitext(selected_yaml)[0], selected_metric_z, selected_metric_y, selected_metric_x
      )

      return html.Div(
        [
          dcc.Graph(
            figure=fig,
            style={"width": "100%", "height": "100%"},
            config={
              "displayModeBar": True,
              "displaylogo": False,
              "modeBarButtonsToRemove": ["lasso", "select"],
              "toImageButtonOptions": {
                "format": dl_format,
                "scale": 3,
                "filename": filename,
              },
            },
          )
        ],
        style={"width": "100%", "height": "100%", "display": "inline-block", "vertical-align": "top"},
      )
    except Exception as e:
      return content_lib.generate_error_div(e)
