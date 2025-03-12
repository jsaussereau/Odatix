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

def create_column_graph(
  explorer,
  selected_yaml,
  selected_metric,
  selected_results,
  show_all,
  hide_all,
  show_all_targets,
  hide_all_targets,
  toggle_legend,
  toggle_legendgroup,
  toggle_title,
  toggle_lines,
  toggle_labels,
  color_mode,
  symbol_mode,
  dl_format,
  background,
  theme,
  toggle_unique_architectures,
  toggle_unique_targets,
  dissociate_domain,
  arch_checklist_values,
  target_checklist_values,
  domain_checklist_values,
):

  fig = go.Figure()

  if not selected_yaml or selected_yaml not in explorer.dfs:
    return html.Div(className="error", children=[html.Div("Please select a YAML file.")])

  selected_metric_display = selected_metric.replace("_", " ") if selected_metric is not None else ""

  unit = legend.unit_to_html(explorer.units[selected_yaml].get(selected_metric, ""))
  selected_metric_display_unit = selected_metric_display + " (" + unit + ")" if unit else selected_metric_display

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
    (explorer.dfs[selected_yaml]["Architecture"].isin(visible_architectures))
  ]

  for domain, configs in domains.items():
    if domain in filtered_df.columns:
      filtered_df[domain] = filtered_df[domain].fillna("None")
      excluded_values = [config for config, is_visible in configs.items() if not is_visible]

      # Apply exclusion only if there are forbidden values in the column
      if any(filtered_df[domain].isin(excluded_values)):
        filtered_df = filtered_df[~filtered_df[domain].isin(excluded_values)]

  unique_configurations = sorted(filtered_df["Configuration"].unique())


  i_target = -1
  for i_unique_target, target in enumerate(explorer.all_targets):
    if target in explorer.dfs[selected_yaml]["Target"].unique():
      i_target = i_target + 1
    if target not in visible_targets:
      continue

    targets = [target] * len(unique_configurations)
    i_architecture = -1
    for i_unique_architecture, architecture in enumerate(explorer.all_architectures):
      if architecture in explorer.dfs[selected_yaml]["Architecture"].unique():
        i_architecture = i_architecture + 1
      if architecture not in visible_architectures:
        continue
      
      df_architecture_target = filtered_df[
        (filtered_df["Architecture"] == architecture) & 
        (filtered_df["Target"] == target)
      ]
      if df_architecture_target.empty:
        continue

      if dissociate_domain != "None" and dissociate_domain in df_architecture_target.columns:
        dissociation_values = df_architecture_target[dissociate_domain].dropna().unique()
        cleaned_configurations = [legend.clean_configuration_name(cfg, dissociate_domain) for cfg in unique_configurations]
      else:
        dissociation_values = [None]
        cleaned_configurations = unique_configurations

      i_dissociate_domain = -1
      for dissociation_value in dissociation_values:
        df_filtered = df_architecture_target.copy()
        if dissociation_value is not None and dissociation_value != "None":
          df_filtered = df_filtered[df_filtered[dissociate_domain] == dissociation_value]
          architecture_diplay = architecture + f" [{dissociate_domain.replace("__main__", "main")}:{dissociation_value}]" 
        else:
          architecture_diplay = architecture
        i_dissociate_domain += 1

        df_fmax = df_filtered[df_filtered["Type"] == "Fmax"]
        if selected_results in ["All", "Fmax"] and not df_fmax.empty:
          if selected_metric is None or selected_metric not in df_architecture_target.columns:
            return html.Div(className="error", children=[html.Div("Please select a valid metric.")])
          
          y_values = [
            df_fmax[df_fmax["Configuration"] == config][selected_metric].values[0]
            if config in df_fmax["Configuration"].values
            else None
            for config in unique_configurations
          ]

          if color_mode == "architecture":
            color_id = i_unique_architecture if toggle_unique_architectures else i_architecture
          elif color_mode == "target":
            color_id = i_unique_target if toggle_unique_targets else i_target
          elif color_mode == "domain_value":
            color_id = i_dissociate_domain if dissociation_value != "None" else -1
          else:
            color_id = 0

          if symbol_mode == "none":
            pattern_id = 0
          elif symbol_mode == "architecture":
            pattern_id = i_unique_architecture if toggle_unique_architectures else i_architecture
          elif symbol_mode == "target":
            pattern_id = i_unique_target if toggle_unique_targets else i_target
          elif symbol_mode == "domain_value":
            pattern_id = i_dissociate_domain
          else:
            pattern_id = 0

          figures.add_trace_to_columns_fig(
            fig, cleaned_configurations, y_values, None, architecture_diplay, "fmax",
            targets, target, selected_metric_display, unit, color_id, pattern_id, toggle_legendgroup
          )

        df_range = df_filtered[df_filtered["Type"] == "Custom Freq"] 
        if selected_results in ["All", "Custom Freq"] and not df_range.empty:
          for i_freq, frequency in enumerate(explorer.all_frequencies):
            df_frequency = df_range[df_range["Frequency"] == frequency]
            if df_frequency.empty:
              continue

            if selected_metric is None or selected_metric not in df_frequency.columns:
              return html.Div(className="error", children=[html.Div("Please select a valid metric.")])

            if color_mode == "architecture":
              color_id = i_architecture
            elif color_mode == "target":
              color_id = i_target
            elif color_mode == "domain_value":
              color_id = i_dissociate_domain if dissociation_value != "None" else -1
            else:
              color_id = i_freq + 1

            if symbol_mode == "none":
              pattern_id = 0
            elif symbol_mode == "architecture":
              pattern_id = i_unique_architecture if toggle_unique_architectures else i_architecture
            elif symbol_mode == "target":
              pattern_id = i_unique_target if toggle_unique_targets else i_target
            else:
              pattern_id = i_freq + 1

            y_values = [
              df_frequency[df_frequency["Configuration"] == config][selected_metric].values[0]
              if config in df_frequency["Configuration"].values
              else None
              for config in unique_configurations
            ]

            figures.add_trace_to_columns_fig(
              fig, cleaned_configurations, y_values, None, architecture_diplay, f"{frequency} MHz",
              targets, target, selected_metric_display, unit, color_id, pattern_id, toggle_legendgroup
            )
  return fig, selected_metric_display, selected_metric_display_unit

def setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs):

  @explorer.app.callback(
    Output("graph-columns", "children"),
    [
      Input("yaml-dropdown", "value"),
      Input("metric-dropdown", "value"),
      Input("results-dropdown", "value"),
      Input("show-all-architectures", "n_clicks"),
      Input("hide-all-architectures", "n_clicks"),
      Input("show-all-targets", "n_clicks"),
      Input("hide-all-targets", "n_clicks"),
      Input("toggle-legend", "value"),
      Input("toggle-legendgroup", "value"),
      Input("toggle-title", "value"),
      Input("toggle-lines", "value"),
      Input("toggle-labels", "value"),
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
  def update_column_graph(
    selected_yaml,
    selected_metric,
    selected_results,
    show_all,
    hide_all,
    show_all_targets,
    hide_all_targets,
    toggle_legend,
    toggle_legendgroup,
    toggle_title,
    toggle_lines,
    toggle_labels,
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
    if explorer is None:
      return html.Div(className="error", children=[html.Div("Loading...")])

    try:
    
      arch_checklist_values = checklist_values[:len(all_architecture_inputs)]
      target_checklist_values = checklist_values[len(all_architecture_inputs):len(all_architecture_inputs) + len(all_target_inputs)]
      domain_checklist_values = checklist_values[len(all_architecture_inputs) + len(all_target_inputs):]
      
      fig, selected_metric_display, selected_metric_display_unit = create_column_graph(
        explorer,
        selected_yaml,
        selected_metric,
        selected_results,
        show_all,
        hide_all,
        show_all_targets,
        hide_all_targets,
        toggle_legend,
        toggle_legendgroup,
        toggle_title,
        toggle_lines,
        toggle_labels,
        color_mode,
        symbol_mode,
        dl_format,
        background,
        theme,
        toggle_unique_architectures,
        toggle_unique_targets,
        dissociate_domain,
        arch_checklist_values,
        target_checklist_values,
        domain_checklist_values,
      )

      fig.update_layout(
        paper_bgcolor=background,
        showlegend=True if toggle_legend else False,
        legend_groupclick="toggleitem",
        xaxis_title="Configuration",
        yaxis_title=selected_metric_display_unit,
        yaxis=dict(range=[0, None]),
        title=selected_metric_display if toggle_title else None,
        title_x=0.5,
        autosize=True,
        template=theme,
        modebar={
          "bgcolor": themes.get_page_bgcolor(theme, default=None),
          "color": themes.get_button_color(theme, default=None),
          "activecolor": themes.get_button_active_color(theme, default=None),
        }
      )

      fig.update_xaxes(
        showticklabels=True if toggle_labels else False
      )
      
      filename = "Odatix-{}-{}-{}".format(
        os.path.splitext(selected_yaml)[0], __name__, selected_metric
      )

      return html.Div(
        [
          dcc.Graph(
            figure=fig,
            style={"width": "100%", "height": "100%"},
            config={
              "displayModeBar": True,
              "displaylogo": False,
              "scrollZoom": True,
              "modeBarButtonsToRemove": ["lasso", "select"],
              "toImageButtonOptions": {
                "format": dl_format,
                "scale": 3,
                "filename": filename
              },
            },
          )
        ],
        style={"width": "100%", "height": "100%", "display": "inline-block", "vertical-align": "top"},
      )
    except Exception as e:
      return content_lib.generate_error_div(e)
