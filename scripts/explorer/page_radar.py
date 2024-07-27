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

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
import plotly.graph_objs as go
import legend

page_name = 'radar'

def make_radar_chart(df, metric, all_configurations, all_architectures, visible_architectures, close=False):
    df[metric] = pd.to_numeric(df[metric], errors='coerce')
    df = df.dropna(subset=[metric])

    if df.empty:
        fig = go.Figure(data=go.Scatterpolar())
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=False
                ),
                angularaxis=dict(
                    showticklabels=False
                )
            ),
            showlegend=False,
            title=metric.replace('_', ' ') if metric is not None else "",
            title_x=0.5
        )
        return fig

    fig = go.Figure(data=go.Scatterpolar(
        r=[0 for c in all_configurations],
        theta=all_configurations,
        marker_color='rgba(0, 0, 0, 0)',
    ))

    for i, architecture in enumerate(all_architectures):
        if architecture in visible_architectures:
            df_architecture = df[df['Architecture'] == architecture]
            if close:
                first_row = df_architecture.iloc[0:1]
                df_architecture = df_architecture._append(first_row, ignore_index=True)
            fig.add_trace(go.Scatterpolar(
                r=df_architecture[metric],
                theta=df_architecture['Configuration'],
                mode='lines+markers',
                name=architecture,
                marker_color=legend.get_color(i),
                showlegend=False
            ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, df[metric].max() if not df[metric].empty else 1]
            )
        ),
        showlegend=False,
        title=metric.replace('_', ' '), 
        title_x=0.5
    )
    
    return fig

def make_all_radar_charts(df, metrics, all_configurations, all_architectures, visible_architectures):
    radar_charts = []
    
    for metric in metrics:
        fig = make_radar_chart(df, metric, all_configurations, all_architectures, visible_architectures)
        radar_charts.append(
            html.Div([
                dcc.Graph(
                    figure=fig,
                    style={'width': '100%'},
                    config = {
                        'displaylogo': False,
                        'modeBarButtonsToRemove': ['lasso', 'select'],
                        'toImageButtonOptions': {
                            'format': 'svg',
                            'filename': 'Asterism-' + str(page_name) + "-" + str(metric)
                        },
                    }
                )
            ], style={'flex': '1 0 21%', 'margin': '5px'})
        )
    
    return radar_charts

def layout(explorer):
    legend_items = legend.create_legend_items(explorer, page_name)

    return html.Div([
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
        html.Div(id='radar-graphs'),
        html.Div([
                html.Div([
                    html.Button("Show All", id="show-all", n_clicks=0, style={'margin-top': '10px'}),
                    html.Button("Hide All", id="hide-all", n_clicks=0),
                ]),
                html.Div(legend_items, id='custom-legend', style={'margin-top': '15px', 'margin-bottom': '15px'}),
            ], style={'display': 'inline-block', 'margin-left': '20px', 'margin-bottom': '-50px'}
        ),
    ])

def setup_callbacks(explorer):
    @explorer.app.callback(
        Output('radar-graphs', 'children'),
        [Input('yaml-dropdown', 'value'),
         Input(f'target-dropdown-{page_name}', 'value'), 
         Input('show-all', 'n_clicks'),
         Input('hide-all', 'n_clicks')] + 
        [Input(f'checklist-{architecture}-{page_name}', 'value') for architecture in explorer.all_architectures],
    )
    def update_radar_charts(selected_yaml, selected_target, show_all, hide_all, *checklist_values):
        if not selected_yaml or selected_yaml not in explorer.dfs:
            return html.Div(
                className='error',
                children=[ html.Div('Please select a YAML file.') ]
            )

        if not selected_target:
            return html.Div('Please select a target.')
            
        ctx = dash.callback_context
        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if triggered_id in ['show-all', 'hide-all']:
            visible_architectures = set(explorer.all_architectures if triggered_id == 'show-all' else [])
        else:
            visible_architectures = set(architecture for i, architecture in enumerate(explorer.all_architectures) if checklist_values[i])
        
        filtered_df = explorer.dfs[selected_yaml][(explorer.dfs[selected_yaml]['Target'] == selected_target) &
                                            (explorer.dfs[selected_yaml]['Architecture'].isin(visible_architectures))]

        unique_configurations = sorted(filtered_df['Configuration'].unique())

        metrics = [col for col in filtered_df.columns if col not in ['Target', 'Architecture', 'Configuration']]
        all_configurations = explorer.all_configurations
        all_architectures = explorer.all_architectures
        radar_charts = make_all_radar_charts(filtered_df, metrics, unique_configurations, all_architectures, visible_architectures)
        
        return html.Div(radar_charts, style={'display': 'flex', 'flex-wrap': 'wrap', 'justify-content': 'space-between'})

    @explorer.app.callback(
        Output(f'target-dropdown-{page_name}', 'options'),
        Input('yaml-dropdown', 'value')
    )
    def update_dropdowns_radar(selected_yaml):
        if not selected_yaml or selected_yaml not in explorer.dfs:
            return [], []

        df = explorer.dfs[selected_yaml]
        available_targets = [{'label': target, 'value': target} for target in df['Target'].unique()]

        return available_targets

    legend.setup_callbacks(explorer, page_name)
