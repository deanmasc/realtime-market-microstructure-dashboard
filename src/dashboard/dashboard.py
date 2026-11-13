import dash
from dash import dcc, html, Input, Output
import threading

class Dashboard:
    def __init__(self):
        self.app = dash.Dash(__name__)

    def setup(self):
        # this is template code for now

        self.app.layout = html.Div([
            html.Div([
                dcc.Interval(id='header-tick', interval=250),
                html.Div(id='header'),
            ]),
            html.Div([
                dcc.Interval(id='spread-tick', interval=500),
                dcc.Graph(id='spread-chart'),
            ]),
            html.Div([
                dcc.Interval(id='obi-tick', interval=500),
                dcc.Graph(id='obi-chart'),
            ]),
        ])

        @self.app.callback(Output('header', 'children'),
              Input('header-tick', 'n_intervals'))
        def update_header(n):
            return f"..."

        threading.Thread(target=self.app.run, kwargs={"port": 8050}, daemon=True).start()