#**********************************************************************#
#                               Asterism                               #
#**********************************************************************#
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Asterism.
# Asterism is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Asterism is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Asterism. If not, see <https://www.gnu.org/licenses/>.
#

import os
import sys
import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import pandas as pd
import yaml
import legend
import navigation

page_name = 'vs'

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, '..', 'lib')
sys.path.append(lib_path)

import printc

def layout(explorer):
    legend_items = legend.create_legend_items(explorer, page_name)

    return html.Div([
        navigation.top_bar(page_name),
        navigation.side_bar(
            content=html.Div(
                id=f'sidebar-content-{page_name}',
                children=[
                    html.H2('Architectures'),
                    html.Div([
                        html.Div([
                            html.Button("Show All", id="show-all", n_clicks=0),
                            html.Button("Hide All", id="hide-all", n_clicks=0),
                        ]),
                        html.Div(legend_items, id='custom-legend', style={'margin-top': '15px', 'margin-bottom': '15px'}),
                    ], style={'display': 'inline-block', 'margin-left': '20px', 'margin-bottom': '-50px'}),
                ]
            ),
            page_name=page_name
        ),
        html.Div(
            id=f'content-{page_name}',
            children=[
                html.Div(
                    className='title-dropdown',
                    children=[
                        html.Div(
                            className='dropdown-label',
                            children=[html.Label("YAML File")]
                        ),
                        dcc.Dropdown(
                            id='yaml-dropdown',
                            options=[{'label': yaml_file, 'value': yaml_file} for yaml_file in explorer.valid_yaml_files],
                            value=explorer.valid_yaml_files[0] if explorer.valid_yaml_files else None
                        ),
                    ]
                ),
                html.Div(
                    className='title-dropdown',
                    children=[
                        html.Div(
                            className='dropdown-label',
                            children=[html.Label("Target")]
                        ),
                        dcc.Dropdown(
                            id=f'target-dropdown-{page_name}',
                            value=explorer.dfs[explorer.valid_yaml_files[0]]['Target'].iloc[0] if explorer.valid_yaml_files else None
                        ),
                    ]
                ),
                html.Div(
                    className='title-dropdown',
                    children=[
                        html.Div(
                            className='dropdown-label',
                            children=[html.Label("Metric X")]
                        ),
                        dcc.Dropdown(
                            id='metric-x-dropdown',
                            value='Fmax_MHz'
                        ),
                    ]
                ),
                html.Div(
                    className='title-dropdown',
                    children=[
                        html.Div(
                            className='dropdown-label',
                            children=[html.Label("Metric Y")]
                        ),
                        dcc.Dropdown(
                            id='metric-y-dropdown',
                            value='Fmax_MHz'
                        ),
                    ]
                ),
                html.Div([
                    html.Div(id=f'graph-{page_name}'),
                ]),
                html.Div(id='checklist-states', style={'display': 'none'})
            ],
            className='content',
            style={'marginLeft': '0'}
        )
    ])

def setup_callbacks(explorer):
    @explorer.app.callback(
        [Output('metric-x-dropdown', 'options'),
         Output('metric-y-dropdown', 'options'),
         Output(f'target-dropdown-{page_name}', 'options')],
        Input('yaml-dropdown', 'value')
    )
    def update_dropdowns(selected_yaml):
        if not selected_yaml or selected_yaml not in explorer.dfs:
            return [], [], []

        df = explorer.dfs[selected_yaml]
        metrics_from_yaml = explorer.update_metrics(explorer.all_data[selected_yaml])
        available_metrics = [{'label': metric, 'value': metric} for metric in metrics_from_yaml]
        available_targets = [{'label': target, 'value': target} for target in df['Target'].unique()]

        return available_metrics, available_metrics, available_targets

    @explorer.app.callback(
        Output(f'graph-{page_name}', 'children'),
        [Input('yaml-dropdown', 'value'),
         Input('metric-x-dropdown', 'value'),
         Input('metric-y-dropdown', 'value'),
         Input(f'target-dropdown-{page_name}', 'value'),
         Input('show-all', 'n_clicks'),
         Input('hide-all', 'n_clicks')] + 
        [Input(f'checklist-{architecture}-{page_name}', 'value') for architecture in explorer.all_architectures],
    )
    def update_graph(selected_yaml, selected_metric_x, selected_metric_y, selected_target, show_all, hide_all, *checklist_values):
        if not selected_yaml or selected_yaml not in explorer.dfs:
            return html.Div(
                className='error',
                children=[html.Div('Please select a YAML file.')]
            )

        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if triggered_id in ['show-all', 'hide-all']:
            visible_architectures = set(explorer.all_architectures if triggered_id == 'show-all' else [])
        else:
            visible_architectures = set(architecture for i, architecture in enumerate(explorer.all_architectures) if checklist_values[i])

        filtered_df = explorer.dfs[selected_yaml][(explorer.dfs[selected_yaml]['Target'] == selected_target) &
                                                  (explorer.dfs[selected_yaml]['Architecture'].isin(visible_architectures))]

        fig = go.Figure()
        for i, architecture in enumerate(explorer.all_architectures):
            if architecture in visible_architectures:
                df_architecture = filtered_df[filtered_df['Architecture'] == architecture]

                x_values = df_architecture[selected_metric_x].tolist()
                y_values = df_architecture[selected_metric_y].tolist()

                fig.add_trace(
                    go.Scatter(
                        x=x_values,
                        y=y_values,
                        mode='lines+markers',
                        line=dict(dash='dot'),
                        marker=dict(size=10, color=legend.get_color(i)),
                        name=architecture,
                        showlegend=False,
                        connectgaps=True
                    )
                )

        fig.update_layout(
            xaxis_title=selected_metric_x.replace('_', ' ') if selected_metric_x is not None else "",
            yaxis_title=selected_metric_y.replace('_', ' ') if selected_metric_y is not None else "",
            title=f"{selected_metric_y.replace('_', ' ')} vs {selected_metric_x.replace('_', ' ')}",
            title_x=0.5,
            width=1450,
            height=720
        )
        return html.Div([
            dcc.Graph(
                figure=fig,
                style={'width': '100%'},
                config={
                    'displaylogo': False,
                    'modeBarButtonsToRemove': ['lasso', 'select'],
                    'toImageButtonOptions': {
                        'format': 'svg',  # one of png, svg, jpeg, webp
                        'filename': f'Asterism-{os.path.splitext(selected_yaml)[0]}-{selected_target}-{selected_metric_x}-vs-{selected_metric_y}'
                    }
                }
            )], style={'display': 'inline-block', 'vertical-align': 'top'}
        )

    legend.setup_callbacks(explorer, page_name)
    navigation.setup_sidebar_callbacks(explorer, page_name)
