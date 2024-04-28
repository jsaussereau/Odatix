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

# Préparation des données pour le DataFrame
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

    # Création du DataFrame
    return pd.DataFrame(data)

def get_yaml_data(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

# Liste des métriques et des cibles disponibles
# Récupérer les métriques à partir du fichier YAML
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

# Couleur des courbes
plot_colors = px.colors.qualitative.Plotly

# Obtenir la liste des fichiers YAML dans le dossier results
yaml_files = [file for file in os.listdir('results') if file.endswith('.yml')]

# Charger les données depuis tous les fichiers YAML
all_data = {}
for yaml_file in yaml_files:
    file_path = os.path.join('results', yaml_file)
    all_data[yaml_file] = get_yaml_data(file_path)

# Préparation des données pour la DataFrame
dfs = {yaml_file: update_dataframe(data) for yaml_file, data in all_data.items()}

# Obtenez toutes les architectures de tous les fichiers YAML
all_architectures = sorted(set(architecture for df in dfs.values() for architecture in df['Architecture'].unique()))

# Toutes les configurations
all_configurations = sorted(set(config for df in dfs.values() for config in df['Configuration'].unique()))

# Liste des boutons pour chaque architecture
def create_legend_item(architecture, line_style, color):
    return html.Div([
        dcc.Checklist(
            id=f'checklist-{architecture}',
            options=[{'label': '', 'value': architecture}],
            value=[architecture],  # Sélectionnée par défaut
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
    ], id=f'legend-item-{architecture}', style={'display': 'block', 'margin-bottom': '5px'})  # Modifiez ici pour 'display': 'block' et ajoutez une marge en bas

# Création de la légende personnalisée
legend_items = [create_legend_item(architecture, '2px dashed', plot_colors[i % len(plot_colors)]) 
                for i, architecture in enumerate(all_architectures)]

# Création de l'application Dash
app = dash.Dash(__name__)
app.title = 'Asterism'

# Mise en place du layout de l'application
app.layout = html.Div([
    html.H1("Asterism - Implementation Result Explorer"),
    dcc.Dropdown(
        id='yaml-dropdown',
        options=[{'label': yaml_file, 'value': yaml_file} for yaml_file in yaml_files],
        value=yaml_files[0]  # Sélectionnez le premier fichier par défaut
    ),
    html.Div([
        dcc.Dropdown(
            id='metric-dropdown',
            value='Fmax_MHz'
        ),
        dcc.Dropdown(
            id='target-dropdown',
            value=dfs[yaml_files[0]]['Target'].iloc[0]
        ),
    ], id='dropdowns'),  # Mettez les dropdowns dans un conteneur div pour les mettre à jour ensemble

    html.Div([
        html.Div([
            dcc.Graph(id="graph"),
        ], style={'display': 'inline-block', 'vertical-align': 'top'}),
        
        html.Div([
            html.Div([
                html.Button("Afficher Tout", id="show-all", n_clicks=0, style={'margin-top': '100px'}),
                html.Button("Masquer Tout", id="hide-all", n_clicks=0),
            ]),
            
            html.Div(legend_items, id='custom-legend', style={'margin-top': '5px'}),
        ], style={'display': 'inline-block', 'margin-left': '20px', 'margin-bottom': '-50px'}),
    ]),
    html.Div(id='checklist-states', style={'display': 'none'})
])

####################################################################################

# Callback pour la mise à jour des dropdowns
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

# Callback pour le changement de fichier YAML
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

# Callback pour la mise à jour du graphique
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

    # Mise à jour des architectures visibles en fonction du bouton déclencheur
    if triggered_id in ['show-all', 'hide-all']:
        visible_architectures = set(all_architectures if triggered_id == 'show-all' else [])
    else:
        # Extraire les architectures visibles des checklists
        visible_architectures = set(architecture for i, architecture in enumerate(all_architectures) if checklist_values[i])

     # Filtrer le DataFrame pour les architectures sélectionnées
    filtered_df = dfs[selected_yaml][(dfs[selected_yaml]['Target'] == selected_target) &
                                      (dfs[selected_yaml]['Architecture'].isin(visible_architectures))]

    unique_configurations = sorted(filtered_df['Configuration'].unique())
    
    # Construction du graphique
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
        yaxis=dict(range=[0, None]), # ymin à 0 et ymax automatique
        width=1450,
        height=720
    )    
    return fig

# Callback pour changer la visibilité des dropdowns
@app.callback(
    [Output(f'legend-item-{architecture}', 'style') for architecture in all_architectures],
    [Input('target-dropdown', 'value'),
     Input('yaml-dropdown', 'value')]
)
def update_legend_visibility(selected_target, selected_yaml):
    architectures_for_target = dfs[selected_yaml][dfs[selected_yaml]['Target'] == selected_target]['Architecture'].unique()
    return [{'display': 'block' if architecture in architectures_for_target else 'none'}
            for architecture in all_architectures]

# Callback pour synchroniser les boutons "Afficher Tout" et "Masquer Tout" avec les checklists individuelles
@app.callback(
    [Output(f'checklist-{architecture}', 'value') for architecture in all_architectures],
    [Input('show-all', 'n_clicks'),
     Input('hide-all', 'n_clicks')],
    [State(f'checklist-{architecture}', 'value') for architecture in all_architectures]
)
def update_checklist_states(show_all_clicks, hide_all_clicks, *current_values):
    ctx = dash.callback_context
    if not ctx.triggered:
        # Pas de changement si aucun bouton n'est cliqué
        return dash.no_update

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if button_id == 'show-all':
        # Sélectionner toutes les architectures
        return [[architecture] for architecture in all_architectures]
    elif button_id == 'hide-all':
        # Désélectionner toutes les architectures
        return [[] for _ in all_architectures]

    return current_values

if __name__ == "__main__":
    app.run_server(debug=True)
