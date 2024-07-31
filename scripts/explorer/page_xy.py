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
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd
import yaml
import legend
import navigation

page_name = 'xy'

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
                className='sidebar-content-holder',
                children=[
                    html.H2('Data'),
                    html.Div(
                        className='title-dropdown',
                        children=[
                            html.Div(
                                className='dropdown-label',
                                children=[ html.Label("YAML File") ]
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
                                children=[ html.Label("Target") ]
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
                                children=[ html.Label("Metric") ]
                            ),
                            dcc.Dropdown(
                                id='metric-dropdown',
                                value='Fmax_MHz'
                            ),
                        ]
                    ),
                    html.H2('Architectures'),
                    html.Div([
                        html.Div([
                            html.Button("Show All", id="show-all", n_clicks=0),
                            html.Button("Hide All", id="hide-all", n_clicks=0),
                        ]),
                        html.Div(legend_items, id='custom-legend', style={'margin-top': '15px', 'margin-bottom': '15px'}),
                    ], style={'display': 'inline-block', 'margin-left': '20px'}),
                    html.H2('Settings'),
                    html.Div(
                        className='title-dropdown',
                        children=[
                            html.Div(
                                className='dropdown-label',
                                children=[ html.Label("Display Mode") ]
                            ),
                            dcc.Dropdown(
                                id='display-mode-dropdown',
                                options=[
                                    {'label': 'Points', 'value': 'points'},
                                    {'label': 'Bars', 'value': 'bars'}
                                ],
                                value='points',
                            )
                        ], style={'margin-bottom': '5px'}
                    ),
                    html.Div(
                        className='toggle-container',
                        children=[
                            dcc.Checklist(
                                id='toggle-legend',
                                options=[{'label': ' Show Legend', 'value': 'show_legend'}],
                                value=[''],
                                className='toggle',
                                labelStyle={'display': 'block', 'font-weight': '515', 'margin-bottom': '5px'},
                            ),
                            dcc.Checklist(
                                id='toggle-lines',
                                options=[{'label': ' Show Lines', 'value': 'show_lines'}],
                                value=['show_lines'],
                                labelStyle={'display': 'block', 'font-weight': '515', 'margin-bottom': '5px'},
                            ),
                        ]
                    ),
                ]
            ),
            page_name=page_name
        ),
        html.Div(
            id=f'content-{page_name}',
            children=[
                html.Div([
                    html.Div(id=f'graph-{page_name}', style={'width': '100%', 'height': '100%'}, className='graph-container')
                ], style={'width': '100%', 'height': '100%'}),
                html.Div(id='checklist-states', style={'display': 'none'})
            ],
            className='content',
            style={'marginLeft': navigation.side_bar_width, 'width': 'calc(100%-'+navigation.side_bar_width+")", 'height': '100%'}
        ),
    ], style={'width': '100%', 'height': '100vh', 'display': 'flex', 'flexDirection': 'column'})

def setup_callbacks(explorer):
    @explorer.app.callback(
        [Output('metric-dropdown', 'options'),
         Output(f'target-dropdown-{page_name}', 'options')],
        Input('yaml-dropdown', 'value')
    )
    def update_dropdowns(selected_yaml):
        if not selected_yaml or selected_yaml not in explorer.dfs:
            return [], []

        df = explorer.dfs[selected_yaml]
        metrics_from_yaml = explorer.update_metrics(explorer.all_data[selected_yaml])
        available_metrics = [{'label': metric, 'value': metric} for metric in metrics_from_yaml]
        available_targets = [{'label': target, 'value': target} for target in df['Target'].unique()]

        return available_metrics, available_targets

    @explorer.app.callback(
        Output(f'graph-{page_name}', 'children'),
        [Input('yaml-dropdown', 'value'),
         Input('metric-dropdown', 'value'),
         Input(f'target-dropdown-{page_name}', 'value'),
         Input('show-all', 'n_clicks'),
         Input('hide-all', 'n_clicks'),
         Input('toggle-legend', 'value'),
         Input('toggle-lines', 'value'),
         Input('display-mode-dropdown', 'value')] + 
        [Input(f'checklist-{architecture}-{page_name}', 'value') for architecture in explorer.all_architectures],
    )
    def update_graph(selected_yaml, selected_metric, selected_target, show_all, hide_all, toggle_legend, toggle_lines, display_mode, *checklist_values):
        if not selected_yaml or selected_yaml not in explorer.dfs:
            return html.Div(
                className='error',
                children=[ html.Div('Please select a YAML file.') ]
            )

        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if triggered_id in ['show-all', 'hide-all']:
            visible_architectures = set(explorer.all_architectures if triggered_id == 'show-all' else [])
        else:
            visible_architectures = set(architecture for i, architecture in enumerate(explorer.all_architectures) if checklist_values[i])

        filtered_df = explorer.dfs[selected_yaml][(explorer.dfs[selected_yaml]['Target'] == selected_target) &
                                                  (explorer.dfs[selected_yaml]['Architecture'].isin(visible_architectures))]

        unique_configurations = sorted(filtered_df['Configuration'].unique())

        fig = go.Figure()

        if display_mode == 'points':
            for i, architecture in enumerate(explorer.all_architectures):
                if architecture in visible_architectures:
                    df_architecture = filtered_df[filtered_df['Architecture'] == architecture]
                    y_values = [df_architecture[df_architecture['Configuration'] == config][selected_metric].values[0] 
                                if config in df_architecture['Configuration'].values else None 
                                for config in unique_configurations]

                    mode = 'lines+markers' if 'show_lines' in toggle_lines else 'markers'

                    fig.add_trace(
                        go.Scatter(
                            x=unique_configurations, 
                            y=y_values, 
                            mode=mode,
                            line=dict(dash='dot') if 'show_lines' in toggle_lines else None,
                            marker=dict(size=10, color=legend.get_color(i)),
                            name=architecture,
                            connectgaps=True
                        )
                    )
        elif display_mode == 'bars':
            for i, architecture in enumerate(explorer.all_architectures):
                if architecture in visible_architectures:
                    df_architecture = filtered_df[filtered_df['Architecture'] == architecture]
                    y_values = [df_architecture[df_architecture['Configuration'] == config][selected_metric].values[0] 
                                if config in df_architecture['Configuration'].values else None 
                                for config in unique_configurations]

                    fig.add_trace(
                        go.Bar(
                            x=unique_configurations, 
                            y=y_values,
                            marker=dict(color=legend.get_color(i)),
                            name=architecture
                        )
                    )

        fig.update_layout(
            showlegend='show_legend' in toggle_legend,
            xaxis_title="Configuration",
            yaxis_title=selected_metric.replace('_', ' ') if selected_metric is not None else "",
            yaxis=dict(range=[0, None]),
            title=selected_metric.replace('_', ' ') if selected_metric is not None else "", 
            title_x=0.5,
            autosize=True,
        )    
        return html.Div([
            dcc.Graph(
                figure=fig,
                style={'width': '100%', 'height': '100%'},
                config = {
                        'displaylogo': False,
                        'modeBarButtonsToRemove': ['lasso', 'select'],
                        'toImageButtonOptions': {
                            'format': 'svg', # one of png, svg, jpeg, webp
                            'filename': 'Asterism-' + str(os.path.splitext(selected_yaml)[0]) + "-" + str(selected_target) + "-" + str(selected_metric) + "-" + str(page_name) 
                        }
                    }
            )], style={'width': '100%', 'height': '100%', 'display': 'inline-block', 'vertical-align': 'top'}
        )

    legend.setup_callbacks(explorer, page_name)
    navigation.setup_sidebar_callbacks(explorer, page_name)
