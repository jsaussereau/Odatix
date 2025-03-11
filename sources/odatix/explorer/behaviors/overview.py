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

import odatix.explorer.behaviors.lines as bhv_lines
import odatix.explorer.behaviors.columns as bhv_columns
import odatix.explorer.behaviors.radar as bhv_radar

dim = {
  "default": {
    "lines": {
      "width_legend": 840,
      "width": 475,
      "height": 500,
    },
    "columns": {
      "width_legend": 840,
      "width": 475,
      "height": 500,
    },
    "radar": {
      "width_legend": 840,
      "width": 475,
      "height": 475,
    }
  },
  "large": {
    "lines": {
      "width_legend": 1000,
      "width": 635,
      "height": 670,
    },
    "columns": {
      "width_legend": 1000,
      "width": 635,
      "height": 670,
    },
    "radar": {
      "width_legend": 1000,
      "width": 635,
      "height": 635,
    }
  },
  "default_tall": {
    "lines": {
      "width_legend": 840,
      "width": 475,
      "height": 600,
    },
    "columns": {
      "width_legend": 840,
      "width": 475,
      "height": 600,
    },
    "radar": {
      "width_legend": 840,
      "width": 475,
      "height": 550,
    }
  },
  "large_tall": {
    "lines": {
      "width_legend": 1000,
      "width": 635,
      "height": 770,
    },
    "columns": {
      "width_legend": 1000,
      "width": 635,
      "height": 770,
    },
    "radar": {
      "width_legend": 1000,
      "width": 635,
      "height": 735,
    }
  },
}

def setup_callbacks(explorer, all_checklist_inputs, all_architecture_inputs, all_target_inputs, all_domains_inputs):

  @explorer.app.callback(
    Output("radar-graphs", "children"),
    [
      Input("overview-layout-dropdown", "value"),
      Input("yaml-dropdown", "value"),
      Input("results-dropdown", "value"),
      Input("show-all-architectures", "n_clicks"),
      Input("hide-all-architectures", "n_clicks"),
      Input("show-all-targets", "n_clicks"),
      Input("hide-all-targets", "n_clicks"),
      Input("show-all-domains", "n_clicks"),
      Input("hide-all-domains", "n_clicks"),
      Input("toggle-legend", "value"),
      Input("toggle-legendgroup", "value"),
      Input("toggle-title", "value"),
      Input("toggle-lines", "value"),
      Input("toggle-close-line", "value"),
      Input("toggle-connect-gaps", "value"),
      Input("toggle-labels", "value"),
      Input("legend-dropdown", "value"),
      Input("chart-type-dropdown", "value"),
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
  def update_overview_charts(
    layout,
    selected_yaml,
    selected_results,
    show_all,
    hide_all,
    show_all_targets,
    hide_all_targets,
    show_all_domains,
    hide_all_domains,
    toggle_legend,
    toggle_legendgroup,
    toggle_title,
    toggle_lines,
    toggle_close,
    toggle_connect_gaps,
    toggle_labels,
    legend_dropdown,
    chart_type,
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

      metrics = [col for col in filtered_df.columns if col not in ["Target", "Architecture", "Configuration", "Type", "Frequency"]]

      targets_for_yaml = explorer.dfs[selected_yaml]["Target"].unique()

      yaml_name = os.path.splitext(selected_yaml)[0]

      radar_charts = []

      mode = "lines+markers" if toggle_lines else "markers"

      for metric in metrics:

        if chart_type == "lines":
          fig, metric_display, metric_display_unit = bhv_lines.create_line_graph(
            explorer,
            selected_yaml,
            metric,
            selected_results,
            show_all,
            hide_all,
            show_all_targets,
            hide_all_targets,
            show_all_domains,
            hide_all_domains,
            toggle_legend,
            toggle_legendgroup,
            toggle_title,
            toggle_lines,
            toggle_connect_gaps,
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
          fig.update_xaxes(
            showticklabels=True if toggle_labels else False
          )
        elif chart_type == "columns":
          fig, metric_display, metric_display_unit = bhv_columns.create_column_graph(
            explorer,
            selected_yaml,
            metric,
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
        elif chart_type == "radar":
          fig, metric_display, metric_display_unit = bhv_radar.create_radar_graph(
            explorer,
            selected_yaml,
            metric,
            selected_results,
            show_all,
            hide_all,
            show_all_targets,
            hide_all_targets,
            show_all_domains,
            hide_all_domains,
            toggle_legend,
            toggle_legendgroup,
            toggle_title,
            toggle_lines,
            toggle_close,
            toggle_connect_gaps,
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
        else:
          metric_display = ""
          metric_display_unit = ""
          fig = go.Figure()
        
        width_legend = dim[layout][chart_type]["width_legend"]
        width = dim[layout][chart_type]["width"]
        height = dim[layout][chart_type]["height"]

        fig.update_layout(
          paper_bgcolor=background,
          showlegend="show_legend" in legend_dropdown,
          legend_groupclick="toggleitem",
          margin=dict(l=60, r=60, t=60, b=60),
          title=metric_display if toggle_title else None,
          title_x=0.5,
          width=width_legend if "show_legend" in legend_dropdown else width,
          height=height,
          template=theme,
          polar_angularaxis_showticklabels=True if toggle_labels else False,
        )

        filename = "Odatix-{}-{}-{}".format(yaml_name, __name__, metric)
        radar_charts.append(figures.make_figure_div(fig, filename, dl_format))

      # # Add legend chart
      # if "separate_legend" in legend_dropdown:
      #   legend_fig = figures.make_legend_chart(
      #     explorer,
      #     filtered_df,
      #     selected_results,
      #     selected_yaml,
      #     targets_for_yaml,
      #     visible_architectures,
      #     visible_targets,
      #     toggle_legendgroup,
      #     toggle_title,
      #     color_mode,
      #     symbol_mode,
      #     background,
      #     theme,
      #     toggle_unique_architectures,
      #     toggle_unique_targets,
      #     dissociate_domain,
      #     mode
      #   )
      #   radar_charts.append(
      #     figures.make_figure_div(legend_fig, "Odatix-" + str(__name__) + "-legend", dl_format, remove_zoom=True)
      #   )

      page_background = themes.get_page_bgcolor(theme)
      return html.Div(radar_charts, style={"display": "flex", "flex-wrap": "wrap", "justify-content": "space-evenly", "backgroundColor": page_background})
    except Exception as e:
      return content_lib.generate_error_div(e)
      