import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State

app = dash.Dash(__name__)

app.layout = html.Div([
    html.Img(
        id='toggle-button', 
        src='/assets/icons/sidebar-panel-expand-icon.svg', 
        n_clicks=0,
        style={'cursor': 'pointer', 'position': 'absolute', 'top': '20px', 'left': '20px', 'width': '30px'}
    ),
    html.Div(
        id='sidebar',
        children=[
            html.Img(
                id='close-button', 
                src='/assets/icons/sidebar-panel-collapse-icon.svg', 
                n_clicks=0,
                style={'cursor': 'pointer', 'margin-bottom': '20px', 'width': '30px'}
            ),
            html.H2('Menu'),
            html.Ul([
                html.Li('Option 1'),
                html.Li('Option 2'),
                html.Li('Option 3'),
            ]),
        ],
        style={'position': 'fixed', 'top': '0', 'left': '-250px', 'width': '250px', 'height': '100%', 'backgroundColor': '#111', 'padding-top': '10px', 'overflowX': 'hidden', 'transition': 'left 0.25s'}
    ),
    html.Div(
        id='content',
        children=[
            html.H1('Content Area'),
            html.P('This is the main content area.'),
        ],
        style={'marginLeft': '0', 'padding': '10px', 'transition': 'margin-left 0.25s'}
    )
])

@app.callback(
    [Output('sidebar', 'style'),
     Output('content', 'style'),
     Output('toggle-button', 'style')],
    [Input('toggle-button', 'n_clicks'),
     Input('close-button', 'n_clicks')],
    [State('sidebar', 'style'),
     State('content', 'style'),
     State('toggle-button', 'style')]
)
def toggle_sidebar(toggle_n_clicks, close_n_clicks, sidebar_style, content_style, toggle_style):
    ctx = dash.callback_context
    if not ctx.triggered:
        return sidebar_style, content_style, toggle_style
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if button_id == 'toggle-button':
        if sidebar_style['left'] == '-250px':
            sidebar_style['left'] = '0'
            content_style['marginLeft'] = '250px'
            toggle_style['display'] = 'none'
        else:
            sidebar_style['left'] = '-250px'
            content_style['marginLeft'] = '0'
            toggle_style['display'] = 'block'
    elif button_id == 'close-button':
        sidebar_style['left'] = '-250px'
        content_style['marginLeft'] = '0'
        toggle_style['display'] = 'block'

    return sidebar_style, content_style, toggle_style

if __name__ == '__main__':
    app.run_server(debug=True)
