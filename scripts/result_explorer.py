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

class bcolors:
  WARNING = '\033[93m'
  FAIL = '\033[91m'
  OKCYAN = '\033[96m'
  ENDC = '\033[0m'
  BOLD = '\033[1m'

# Prepare data for the dataframe
def update_dataframe(yaml_data):
    data = []
    for target, architectures in yaml_data.items():
        for architecture, configurations in architectures.items():
            for config, metrics in configurations.items():
                row = metrics.copy()
                row['Target'] = target
                row['Architecture'] = architecture
                row['Configuration'] = config
                data.append(row)

    # Create the dataframe
    df = pd.DataFrame(data)

    # Check if the dataframe contains the required columns and they are not empty
    required_columns = ['Target', 'Architecture', 'Configuration']
    if not all(column in df.columns and not df[column].empty for column in required_columns):
        return None

    return df

def get_yaml_data(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

# List of metrics and available targets
# Retrieve metrics from the YAML file
def update_metrics(yaml_data):
    metrics_from_yaml = set()
    for target_data in yaml_data.values():
        for architecture_data in target_data.values():
            for configuration_data in architecture_data.values():
                metrics_from_yaml.update(configuration_data.keys())
    return metrics_from_yaml

def get_complete_df(df):
    complete_df = pd.DataFrame(product(all_architectures, all_configurations), columns=['Architecture', 'Configuration'])
    for metric in available_metrics:
        complete_df[metric] = None
    return complete_df

####################################################################################

# Color of the lines
plot_colors = px.colors.qualitative.Plotly

# Get the list of YAML files in the results folder
yaml_files = [file for file in os.listdir('results') if file.endswith('.yml')]
valid_yaml_files = []

# Load data from all YAML files
all_data = {}
for yaml_file in yaml_files:
    file_path = os.path.join('results', yaml_file)
    data = get_yaml_data(file_path)
    df = update_dataframe(data)   
    if df is None:
        print(bcolors.WARNING + f"warning: yaml file \"{yaml_file}\" is empty or corrupted, skipping..." + bcolors.ENDC)
    else:
        all_data[yaml_file] = data
        valid_yaml_files.append(yaml_file)

# Prepare data for the dataframe
dfs = {yaml_file: update_dataframe(data) for yaml_file, data in all_data.items()}

# Get all architectures from all YAML files
all_architectures = sorted(set(architecture for df in dfs.values() for architecture in df['Architecture'].unique()))

# All configurations
all_configurations = sorted(set(config for df in dfs.values() for config in df['Configuration'].unique()))

# List of buttons for each architecture
def create_legend_item(architecture, line_style, color):
    return html.Div([
        dcc.Checklist(
            id=f'checklist-{architecture}',
            options=[{'label': '', 'value': architecture}],
            value=[architecture],  # Selected by default
            inline=True,
            style={'display': 'inline-block', 'margin-right': '10px'}
        ),
        html.Div(style={
            'display': 'inline-block',
            'width': '30px',
            'height': '2px',
            'border-top': f'{line_style} {color}',
            'position': 'relative'
        },
        children=html.Div(style={
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
    ], id=f'legend-item-{architecture}', style={'display': 'block', 'margin-bottom': '5px'})  # Change here to 'display': 'block' and add bottom margin

# Create custom legend
legend_items = [create_legend_item(architecture, '2px dashed', plot_colors[i % len(plot_colors)]) 
                for i, architecture in enumerate(all_architectures)]

# Create Dash application
app = dash.Dash(__name__)
app.title = 'Asterism'

# Set up the application layout
app.layout = html.Div([
    html.H1("Asterism - Implementation Result Explorer"),
    dcc.Dropdown(
        id='yaml-dropdown',
        options=[{'label': yaml_file, 'value': yaml_file} for yaml_file in yaml_files],
        value=yaml_files[0]  # Select the first file by default
    ),
    html.Div([
        dcc.Dropdown(
            id='metric-dropdown',
            value='Fmax_MHz'
        ),
        dcc.Dropdown(
            id='target-dropdown',
            value=dfs[valid_yaml_files[0]]['Target'].iloc[0]
        ),
    ], id='dropdowns'),  # Put dropdowns in a div container to update them together

    html.Div([
        html.Div([
            dcc.Graph(id="graph"),
        ], style={'display': 'inline-block', 'vertical-align': 'top'}),
        
        html.Div([
            html.Div([
                html.Button("Show All", id="show-all", n_clicks=0, style={'margin-top': '100px'}),
                html.Button("Hide All", id="hide-all", n_clicks=0),
            ]),
            
            html.Div(legend_items, id='custom-legend', style={'margin-top': '5px'}),
        ], style={'display': 'inline-block', 'margin-left': '20px', 'margin-bottom': '-50px'}),
    ]),
    html.Div(id='checklist-states', style={'display': 'none'})
])

####################################################################################

# Callback to update the dropdowns
@app.callback(
    [Output('metric-dropdown', 'options'),
     Output('target-dropdown', 'options')],
    Input('yaml-dropdown', 'value')
)
def update_dropdowns(selected_yaml):
    df = dfs[selected_yaml]
    metrics_from_yaml = update_metrics(all_data[selected_yaml])
    available_metrics = [{'label': metric, 'value': metric} for metric in metrics_from_yaml]
    available_targets = [{'label': target, 'value': target} for target in df['Target'].unique()]
    return available_metrics, available_targets

# Callback for YAML file change
@app.callback(
    Output('dropdowns', 'children'),
    Input('yaml-dropdown', 'value')
)
def update_yaml(selected_yaml):
    df = dfs[selected_yaml]
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

# Callback to update the graph
@app.callback(
    Output('graph', 'figure'),
    [Input('yaml-dropdown', 'value'),
     Input('metric-dropdown', 'value'),
     Input('target-dropdown', 'value'),
     Input('show-all', 'n_clicks'),
     Input('hide-all', 'n_clicks')] + 
    [Input(f'checklist-{architecture}', 'value') for architecture in all_architectures],
)
def update_graph(selected_yaml, selected_metric, selected_target, show_all, hide_all, *checklist_values):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # Update visible architectures based on the triggering button
    if triggered_id in ['show-all', 'hide-all']:
        visible_architectures = set(all_architectures if triggered_id == 'show-all' else [])
    else:
        # Extract visible architectures from checklists
        visible_architectures = set(architecture for i, architecture in enumerate(all_architectures) if checklist_values[i])

    # Filter dataframe for selected architectures
    filtered_df = dfs[selected_yaml][(dfs[selected_yaml]['Target'] == selected_target) &
                                      (dfs[selected_yaml]['Architecture'].isin(visible_architectures))]

    unique_configurations = sorted(filtered_df['Configuration'].unique())
    
    # Build the graph
    fig = go.Figure()
    for i, architecture in enumerate(all_architectures):
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
                    marker=dict(size=10, color=plot_colors[i % len(plot_colors)]),
                    name=architecture,
                    showlegend=False,
                    connectgaps=True
                )
            )

    fig.update_layout(
        yaxis=dict(range=[0, None]), # ymin at 0 and automatic ymax
        width=1450,
        height=720
    )    
    return fig

# Callback to change the visibility of dropdowns
@app.callback(
    [Output(f'legend-item-{architecture}', 'style') for architecture in all_architectures],
    [Input('target-dropdown', 'value'),
     Input('yaml-dropdown', 'value')]
)
def update_legend_visibility(selected_target, selected_yaml):
    architectures_for_target = dfs[selected_yaml][dfs[selected_yaml]['Target'] == selected_target]['Architecture'].unique()
    return [{'display': 'block' if architecture in architectures_for_target else 'none'}
            for architecture in all_architectures]

# Callback to synchronize "Show All" and "Hide All" buttons with individual checklists
@app.callback(
    [Output(f'checklist-{architecture}', 'value') for architecture in all_architectures],
    [Input('show-all', 'n_clicks'),
     Input('hide-all', 'n_clicks')],
    [State(f'checklist-{architecture}', 'value') for architecture in all_architectures]
)
def update_checklist_states(show_all_clicks, hide_all_clicks, *current_values):
    ctx = dash.callback_context
    if not ctx.triggered:
        # No change if no button is clicked
        return dash.no_update

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == 'show-all':
        # Select all architectures
        return [[architecture] for architecture in all_architectures]
    elif button_id == 'hide-all':
        # Deselect all architectures
        return [[] for _ in all_architectures]

    return current_values

if __name__ == "__main__":
    app.run_server(debug=True)
    