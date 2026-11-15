import dash
import threading
from dash import dcc, html, Input, Output
from processing.metrics_manager import MetricsManager
from utils.constants import *
from datetime import datetime, timezone, timedelta

class Dashboard:
    def __init__(self, metrics_manager: MetricsManager):
        self.app = dash.Dash(__name__)
        self.metrics_manager = metrics_manager

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
                html.Div(id='spread'),
            ]),
            html.Div([
                dcc.Interval(id='obi-tick', interval=500),
                dcc.Graph(id='obi-chart'),
                html.Div(id='obi'),
            ]),
            html.Div([
                dcc.Interval(id='vpin-tick', interval=1000),
                dcc.Graph(id='vpin-chart'),
                html.Div(id='vpin'),
            ]),
        ])

        @self.app.callback(Output('header', 'children'), Input('header-tick', 'n_intervals'))
        def update_header(n):
            return f"..."

        @self.app.callback(Output('spread', 'children'),
                           Output('spread-chart', 'children'), 
                           Input('spread-tick', 'n_intervals'))
        def update_spread(n):
            spread_metric = self.metrics_manager.get_metric(SPREAD_KEY)
            curr_spread = spread_metric.get_value()
            spread_metric.append_time_series_value(curr_spread)
            curr_time = datetime.now(timezone.utc)

            figure = {"data": [{"x": [curr_time - timedelta(milliseconds=250)*i for i in range(spread_metric.time_series_window)], "y": spread_metric.time_series_window, "type": "scatter", "mode": "lines"}],
                      "layout": {"title": "Spread (bps)",
                          "yaxis": {"title": "Value"},
                          "margin": {"l": 40, "r": 20, "t": 40, "b": 30}}}
            return curr_spread, figure

        @self.app.callback(Output('obi', 'children'),
                           Output('obi-chart', 'children'), 
                           Input('obi-tick', 'n_intervals'))
        def update_obi(n):
            obi_metric = self.metrics_manager.get_metric(OBI_KEY)
            curr_spread = obi_metric.get_value()
            obi_metric.append_time_series_value(curr_spread)
            curr_time = datetime.now(timezone.utc)
                        
            figure = {"data": [{"x": [curr_time - timedelta(milliseconds=250)*i for i in range(obi_metric.time_series_window)], "y": obi_metric.time_series_window, "type": "scatter", "mode": "lines"}],
                        "layout": {"title": "Order Book Imbalance",
                            "yaxis": {"title": "Value"},
                            "margin": {"l": 40, "r": 20, "t": 40, "b": 30}}}
            return curr_spread, figure

        @self.app.callback(Output('vpin', 'children'),
                           Output('vpin-chart', 'children'), 
                           Input('vpin-tick', 'n_intervals'))
        def update_vpin(n):
            vpin_metric = self.metrics_manager.get_metric(VPIN_KEY)
            curr_spread = vpin_metric.get_value()
            vpin_metric.append_time_series_value(curr_spread)
            curr_time = datetime.now(timezone.utc)
                        
            figure = {"data": [{"x": [curr_time - timedelta(milliseconds=250)*i for i in range(vpin_metric.time_series_window)], "y": vpin_metric.time_series_window, "type": "scatter", "mode": "lines"}],
                        "layout": {"title": "Volume-Synchronized Probability of Informed Trading",
                            "yaxis": {"title": "Value"},
                            "margin": {"l": 40, "r": 20, "t": 40, "b": 30}}}
            return curr_spread, figure

        threading.Thread(target=self.app.run, kwargs={"port": 8050}, daemon=True).start()