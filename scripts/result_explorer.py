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
import numpy as np
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd
import yaml
import json
import webbrowser
from threading import Timer
from itertools import product

# Add local libs to path
current_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(current_dir, 'lib')
sys.path.append(lib_path)

import printc

script_name = os.path.basename(__file__)

class ResultExplorer:
    def __init__(self, result_path='results', yaml_prefix='results_'):
        self.result_path = result_path
        self.yaml_prefix = yaml_prefix

        # Check paths 
        if not os.path.exists(result_path):
            printc.error("Could not find result path \"" + result_path + "\"")
            sys.exit(-1)

        # Initialize additional instance variables here
        self.plot_colors = px.colors.qualitative.Plotly
        self.yaml_files = [file for file in os.listdir(self.result_path) if file.endswith('.yml') and file.startswith(yaml_prefix)]
        self.valid_yaml_files = []
        self.all_data = {}
        self.dfs = {}
        
        # Load and validate YAML files
        self.load_yaml_files()
        
        if not self.valid_yaml_files:
            printc.error("Could not find any valid YAML file in \"" + self.result_path + "\", exiting.", script_name=script_name)
            sys.exit(-1)
        
        self.all_architectures = sorted(set(architecture for df in self.dfs.values() for architecture in df['Architecture'].unique()))
        self.all_configurations = sorted(set(config for df in self.dfs.values() for config in df['Configuration'].unique()))
        self.legend_items = [self.create_legend_item(architecture, '2px dashed', self.plot_colors[i % len(self.plot_colors)]) 
                             for i, architecture in enumerate(self.all_architectures)]
        
        self.app = dash.Dash(__name__)
        self.app.title = 'Asterism'
        self.setup_layout()
        self.setup_callbacks()

    def load_yaml_files(self):
        """
        Load and validate YAML files from the specified path.
        """
        for yaml_file in self.yaml_files:
            file_path = os.path.join(self.result_path, yaml_file)
            try:
                data = self.get_yaml_data(file_path)
                df = self.update_dataframe(data)
                if df is None:
                    printc.warning("YAML file  \"" + yaml_file + "\" is empty or corrupted, skipping...", script_name=script_name)
                    printc.note("Run fmax synthesis with the correct settings to generate  \"" + yaml_file + "\"", script_name=script_name)
                else:
                    self.all_data[yaml_file] = data
                    self.valid_yaml_files.append(yaml_file)
                    self.dfs[yaml_file] = df
            except:
                printc.warning("YAML file  \"" + yaml_file + "\" is not a valid result file, skipping...", script_name=script_name)

    def get_yaml_data(self, file_path):
        """
        Load YAML data from a file.
        """
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
        
    def update_dataframe(self, yaml_data):
        """
        Update the dataframe with YAML data.
        """
        data = []
        for target, architectures in yaml_data.items():
            for architecture, configurations in architectures.items():
                for config, metrics in configurations.items():
                    row = metrics.copy()
                    row['Target'] = target
                    row['Architecture'] = architecture
                    row['Configuration'] = config
                    data.append(row)
        df = pd.DataFrame(data)

        # Check if the dataframe contains the required columns and they are not empty
        required_columns = ['Target', 'Architecture', 'Configuration']
        if not all(column in df.columns and not df[column].empty for column in required_columns):
            return None
        return df

    def update_metrics(self, yaml_data):
        """
        Update metrics based on YAML data.
        """
        metrics_from_yaml = set()
        for target_data in yaml_data.values():
            for architecture_data in target_data.values():
                for configuration_data in architecture_data.values():
                    metrics_from_yaml.update(configuration_data.keys())
        return metrics_from_yaml

    def create_legend_item(self, architecture, line_style, color):
        """
        Create a legend item for the architecture.
        """
        return html.Div([
            dcc.Checklist(
                id=f'checklist-{architecture}',
                options=[{'label': '', 'value': architecture}],
                value=[architecture],
                inline=True,
                style={'display': 'inline-block', 'margin-right': '10px'}
            ),
            html.Div(style={
                'display': 'inline-block',
                'width': '30px',
                'height': '2px',
                'border-top': f'{line_style} {color}',
                'position': 'relative'
            }, children=html.Div(style={
                'position': 'absolute',
                'top': '-6px',
                'left': '50%',
                'transform': 'translateX(-50%)',
                'width': '10px',
                'height': '10px',
                'background-color': color,
                'border-radius': '50%'
            })),
            html.Div(f'{architecture}', style={'display': 'inline-block', 'margin-left': '5px'})
        ], id=f'legend-item-{architecture}', style={'display': 'block', 'margin-bottom': '5px'})

    def setup_layout(self):
        """
        Setup the layout of the Dash application.
        """
        self.app.layout = html.Div([
            html.H1("Asterism - Implementation Result Explorer"),
            dcc.Dropdown(
                id='yaml-dropdown',
                options=[{'label': yaml_file, 'value': yaml_file} for yaml_file in self.valid_yaml_files],
                value=self.valid_yaml_files[0]
            ),
            html.Div([
                dcc.Dropdown(
                    id='metric-dropdown',
                    value='Fmax_MHz'
                ),
                dcc.Dropdown(
                    id='target-dropdown',
                    value=self.dfs[self.valid_yaml_files[0]]['Target'].iloc[0]
                ),
            ], id='dropdowns'),
            html.Div([
                html.Div([
                    dcc.Graph(id="graph"),
                ], style={'display': 'inline-block', 'vertical-align': 'top'}),
                html.Div([
                    html.Div([
                        html.Button("Show All", id="show-all", n_clicks=0, style={'margin-top': '100px'}),
                        html.Button("Hide All", id="hide-all", n_clicks=0),
                    ]),
                    html.Div(self.legend_items, id='custom-legend', style={'margin-top': '5px'}),
                ], style={'display': 'inline-block', 'margin-left': '20px', 'margin-bottom': '-50px'}),
            ]),
            html.Div(id='checklist-states', style={'display': 'none'})
        ])
    
    def setup_callbacks(self):
        """
        Setup Dash callbacks for interactivity.
        """
        @self.app.callback(
            [Output('metric-dropdown', 'options'),
             Output('target-dropdown', 'options')],
            Input('yaml-dropdown', 'value')
        )
        def update_dropdowns(selected_yaml):
            df = self.dfs[selected_yaml]
            metrics_from_yaml = self.update_metrics(self.all_data[selected_yaml])
            available_metrics = [{'label': metric, 'value': metric} for metric in metrics_from_yaml]
            available_targets = [{'label': target, 'value': target} for target in df['Target'].unique()]
            return available_metrics, available_targets

        @self.app.callback(
            Output('dropdowns', 'children'),
            Input('yaml-dropdown', 'value')
        )
        def update_yaml(selected_yaml):
            df = self.dfs[selected_yaml]
            return [
                dcc.Dropdown(
                    id='metric-dropdown',
                    value='Fmax_MHz'
                ),
                dcc.Dropdown(
                    id='target-dropdown',
                    value=df['Target'].iloc[0]
                ),
            ]

        @self.app.callback(
            Output('graph', 'figure'),
            [Input('yaml-dropdown', 'value'),
             Input('metric-dropdown', 'value'),
             Input('target-dropdown', 'value'),
             Input('show-all', 'n_clicks'),
             Input('hide-all', 'n_clicks')] + 
            [Input(f'checklist-{architecture}', 'value') for architecture in self.all_architectures],
        )
        def update_graph(selected_yaml, selected_metric, selected_target, show_all, hide_all, *checklist_values):
            ctx = dash.callback_context
            triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

            if triggered_id in ['show-all', 'hide-all']:
                visible_architectures = set(self.all_architectures if triggered_id == 'show-all' else [])
            else:
                visible_architectures = set(architecture for i, architecture in enumerate(self.all_architectures) if checklist_values[i])

            filtered_df = self.dfs[selected_yaml][(self.dfs[selected_yaml]['Target'] == selected_target) &
                                                  (self.dfs[selected_yaml]['Architecture'].isin(visible_architectures))]

            unique_configurations = sorted(filtered_df['Configuration'].unique())
            
            fig = go.Figure()
            for i, architecture in enumerate(self.all_architectures):
                if architecture in visible_architectures:
                    df_architecture = filtered_df[filtered_df['Architecture'] == architecture]
                    y_values = [df_architecture[df_architecture['Configuration'] == config][selected_metric].values[0] 
                                if config in df_architecture['Configuration'].values else None 
                                for config in unique_configurations]

                    fig.add_trace(
                        go.Scatter(
                            x=unique_configurations, 
                            y=y_values, 
                            mode='lines+markers',
                            line=dict(dash='dot'),
                            marker=dict(size=10, color=self.plot_colors[i % len(self.plot_colors)]),
                            name=architecture,
                            showlegend=False,
                            connectgaps=True
                        )
                    )

            fig.update_layout(
                yaxis=dict(range=[0, None]),
                width=1450,
                height=720
            )    
            return fig

        @self.app.callback(
            [Output(f'legend-item-{architecture}', 'style') for architecture in self.all_architectures],
            [Input('target-dropdown', 'value'),
             Input('yaml-dropdown', 'value')]
        )
        def update_legend_visibility(selected_target, selected_yaml):
            architectures_for_target = self.dfs[selected_yaml][self.dfs[selected_yaml]['Target'] == selected_target]['Architecture'].unique()
            return [{'display': 'block' if architecture in architectures_for_target else 'none'}
                    for architecture in self.all_architectures]

        @self.app.callback(
            [Output(f'checklist-{architecture}', 'value') for architecture in self.all_architectures],
            [Input('show-all', 'n_clicks'),
             Input('hide-all', 'n_clicks')],
            [State(f'checklist-{architecture}', 'value') for architecture in self.all_architectures]
        )
        def update_checklist_states(show_all_clicks, hide_all_clicks, *current_values):
            ctx = dash.callback_context
            if not ctx.triggered:
                return dash.no_update

            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if button_id == 'show-all':
                return [[architecture] for architecture in self.all_architectures]
            elif button_id == 'hide-all':
                return [[] for _ in self.all_architectures]

            return current_values

    def run_server(self, debug=False, host='127.0.0.1', port=5000):
        """
        Run the Dash server.
        """
        self.app.run_server(debug=debug, host=host, port=port)

if __name__ == "__main__":
    result_explorer = ResultExplorer()
    result_explorer.run_server(debug=True)
