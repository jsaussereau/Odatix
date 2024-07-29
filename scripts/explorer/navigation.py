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

def top_bar(page_name=""):
    return html.Div(
        [
            html.Div(
                id=f'navbar-title-{page_name}',
                children=[
                    dcc.Link('Asterism Explorer', href='/', className='title'),
                ],
                style={'marginLeft': '0', 'transition': 'margin-left 0.25s'}
            ),
            html.Div(),
            html.Div([
                dcc.Link('XY', href='/xy', className='nav-link'),
                dcc.Link('VS', href='/vs', className='nav-link'),
                dcc.Link('Radar', href='/radar', className='nav-link'),
                # dcc.Link('Help', href='/help', className='nav-link')
            ], className='nav-links')
        ], 
        className='navbar'
    )


def side_bar(content, page_name=""):
    return html.Div([
        html.Div(
            id=f'sidebar-back-{page_name}',
            className='sidebar-back',
            style={'display': 'none'}
        ),
        html.Img(
            id=f'toggle-button-{page_name}', 
            src='/assets/icons/sidebar-panel-expand-icon.svg', 
            n_clicks=0,
            style={'cursor': 'pointer', 'position': 'absolute', 'top': '10px', 'left': '20px', 'width': '30px'}
        ),
        html.Div(
            id=f'sidebar-{page_name}',
            children = [
                html.Img(
                    id=f'close-button-{page_name}', 
                    src='/assets/icons/sidebar-panel-collapse-icon.svg', 
                    n_clicks=0,
                    style={'cursor': 'pointer', 'position': 'absolute', 'top': '10px', 'left': '20px', 'width': '30px'}
                ),
                html.Div(
                    children=[
                        
                        html.Div(
                            children=[
                                html.H1('')
                            ],
                            style={'margin-bottom': '30px'}
                        ),
                        content
                    ], 
                    className='sidebar-content',
                )
            ],
            className='sidebar',
            style={'left': '-450px', 'width': '450px'}
        ),
    ])


def setup_sidebar_callbacks(explorer, page_name=""):
    @explorer.app.callback(
        [Output(f'sidebar-{page_name}', 'style'),
        Output(f'content-{page_name}', 'style'),
        Output(f'navbar-title-{page_name}', 'style'),
        Output(f'sidebar-back-{page_name}', 'style'),
        Output(f'toggle-button-{page_name}', 'style')],
        [Input(f'toggle-button-{page_name}', 'n_clicks'),
        Input(f'close-button-{page_name}', 'n_clicks')],
        [State(f'sidebar-{page_name}', 'style'),
        State(f'content-{page_name}', 'style'),
        State(f'navbar-title-{page_name}', 'style'),
        State(f'sidebar-back-{page_name}', 'style'),
        State(f'toggle-button-{page_name}', 'style')]
    )
    def toggle_sidebar(toggle_n_clicks, close_n_clicks, sidebar_style, content_style, navbar_style, sidebar_back, toggle_style):
        ctx = dash.callback_context
        if not ctx.triggered:
            return sidebar_style, content_style, navbar_style, toggle_style
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]

        if button_id == f'toggle-button-{page_name}':
            if sidebar_style['left'] == '-450px':
                sidebar_style['left'] = '0'
                content_style['marginLeft'] = '450px'
                navbar_style['marginLeft'] = '30px'
                navbar_style['position'] = 'fixed'
                sidebar_back['display'] = 'block'
                toggle_style['display'] = 'none'
            else:
                sidebar_style['left'] = '-450px'
                content_style['marginLeft'] = '0'
                navbar_style['marginLeft'] = '0'
                navbar_style['position'] = 'relative'
                sidebar_back['display'] = 'none'
                toggle_style['display'] = 'block'
        elif button_id == f'close-button-{page_name}':
            sidebar_style['left'] = '-450px'
            content_style['marginLeft'] = '0'
            navbar_style['marginLeft'] = '0'
            navbar_style['position'] = 'relative'
            sidebar_back['display'] = 'none'
            toggle_style['display'] = 'block'

        return sidebar_style, content_style, navbar_style, sidebar_back, toggle_style
