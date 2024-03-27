'''
Copyright(C) 2023 by Jonathan Saussereau. All rights reserved.

All source codes and documentation contain proprietary confidential
information and are distributed under license. It may be used, copied
and/or disclosed only pursuant to the terms of a valid license agreement
with Jonathan Saussereau. This copyright must be retained at all times.

result_explorer.py

use example: python3 result_explorer.py
''' 

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

plot_colors = px.colors.qualitative.Plotly

# Charger les données depuis le fichier YML
file_path = 'results/results_fpga.yml'
with open(file_path, 'r') as file:
    yml_data = yaml.safe_load(file)

# Préparation des données pour le DataFrame
data = []
for target, architectures in yml_data.items():
    for architecture, configurations in architectures.items():
        for config, metrics in configurations.items():
            row = metrics.copy()
            row['Target'] = target
            row['Architecture'] = architecture
            row['Configuration'] = config
            data.append(row)

# Création du DataFrame
df = pd.DataFrame(data)

# Liste des métriques et des cibles disponibles
available_metrics = ['Fmax_MHz', 'LUT_count', 'Reg_count', 'Total_LUT_reg', 'BRAM_count', 'DSP_count', 'Dynamic_Power', 'Static_Power', 'Total_Power', 'DMIPS_per_MHz', 'DMIPS']
available_targets = df['Target'].unique()

# Toutes les configurations et architectures
all_configurations = sorted(df['Configuration'].unique())
all_architectures = sorted(df['Architecture'].unique())

# Fusion avec les données existantes pour compléter les métriques manquantes
complete_df = pd.merge(
    pd.DataFrame(product(all_architectures, all_configurations), columns=['Architecture', 'Configuration']),
    df, 
    on=['Architecture', 'Configuration'], 
    how='left'
)

for metric in available_metrics:
    if metric not in complete_df.columns:
        complete_df[metric] = None

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

# Créez une fonction pour générer les entrées Input pour les architectures du target actuel
def generate_architecture_inputs(selected_target):
    architectures_for_target = df[df['Target'] == selected_target]['Architecture'].unique()
    return [Input(f'checklist-{architecture}', 'value') for architecture in architectures_for_target]

def get_architectures_for_target(selected_target):
    return df[df['Target'] == selected_target]['Architecture'].unique()
    
# Obtenir les architectures pour le target sélectionné par défaut
default_target = available_targets[0]
default_architectures = get_architectures_for_target(default_target)

# Création de la légende personnalisée pour le target par défaut
legend_items = [create_legend_item(architecture, '2px dashed', plot_colors[i % len(plot_colors)]) 
                for i, architecture in enumerate(all_architectures)]

# Création de l'application Dash
app = dash.Dash(__name__)

# Mise en place du layout de l'application
app.layout = html.Div([
    html.H1("Implementation Result Explorer"),
    dcc.Dropdown(
        id='metric-dropdown',
        options=[{'label': metric, 'value': metric} for metric in available_metrics],
        value='Fmax_MHz'
    ),
    dcc.Dropdown(
        id='target-dropdown',
        options=[{'label': target, 'value': target} for target in available_targets],
        value=available_targets[0]
    ),
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

# Callback pour la mise à jour du graphique
@app.callback(
    Output('graph', 'figure'),
    [Input('metric-dropdown', 'value'),
     Input('target-dropdown', 'value'),
     Input('show-all', 'n_clicks'),
     Input('hide-all', 'n_clicks')] + [Input(f'checklist-{architecture}', 'value') for architecture in all_architectures],
)
def update_graph(selected_metric, selected_target, show_all, hide_all, *checklist_values):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # Mise à jour des architectures visibles en fonction du bouton déclencheur
    if triggered_id in ['show-all', 'hide-all']:
        visible_architectures = set(all_architectures if triggered_id == 'show-all' else [])
    else:
        # Extraire les architectures visibles des checklists
        visible_architectures = set(architecture for i, architecture in enumerate(all_architectures) if checklist_values[i])

     # Filtrer le DataFrame pour les architectures sélectionnées
    filtered_df = complete_df[(complete_df['Target'] == selected_target) &
                              (complete_df['Architecture'].isin(visible_architectures))]

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
    [Input('target-dropdown', 'value')]
)
def update_legend_visibility(selected_target):
    architectures_for_target = get_architectures_for_target(selected_target)
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
