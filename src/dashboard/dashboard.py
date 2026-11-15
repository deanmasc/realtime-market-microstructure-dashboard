import dash
import threading
from dash import dcc, html, Input, Output
from processing.metrics_manager import MetricsManager
from utils.constants import *
from datetime import datetime, timezone, timedelta

BG = "#16161d"
FG = "#e8e8ea"
ACCENT = "#2dd4bf"
PANEL = {"backgroundColor": "#1e1e28", "borderRadius": "6px",
         "padding": "12px 16px", "marginBottom": "16px"}
VALUE = {"fontFamily": "monospace", "fontSize": "22px", "color": ACCENT}
LABEL = {"fontSize": "12px", "letterSpacing": "1px", "color": "#8a8a99"}

GRAPH_LAYOUT = {
    "paper_bgcolor": "#1e1e28",
    "plot_bgcolor": "#1e1e28",
    "font": {"color": FG, "size": 11},
    "margin": {"l": 50, "r": 20, "t": 50, "b": 40},
    "height": 260,
    "xaxis": {"gridcolor": "#2e2e3a"},
    "yaxis": {"gridcolor": "#2e2e3a"},
}

def panel(tick_id, interval, chart_id, value_id, label):
    return html.Div([
        dcc.Interval(id=tick_id, interval=interval),
        html.Div(label, style=LABEL),
        html.Div(id=value_id, style=VALUE),
        dcc.Graph(id=chart_id, config={"displayModeBar": False}),
    ], style=PANEL)


class Dashboard:
    def __init__(self, metrics_manager: MetricsManager):
        self.app = dash.Dash(__name__)
        self.metrics_manager = metrics_manager

    def _series(self, metric, title, interval_ms, yaxis_range=None):
        curr = metric.get_value()
        metric.append_time_series_value(curr)
        now = datetime.now(timezone.utc)
        window = list(metric.time_series_window)
        n = len(window)
        # oldest sample is at index 0, so it gets the oldest timestamp
        x = [now - timedelta(milliseconds=250) * (n - 1 - i) for i in range(n)]

        layout = dict(GRAPH_LAYOUT)
        layout["title"] = {"text": title, "x": 0, "font": {"size": 14}}
        if yaxis_range:
            layout["yaxis"] = {**GRAPH_LAYOUT["yaxis"], "range": yaxis_range}

        figure = {"data": [{"x": x, "y": window, "type": "scatter",
                            "mode": "lines", "line": {"color": ACCENT, "width": 1.5}}],
                  "layout": layout}
        return curr, figure

    def setup(self):
        self.app.layout = html.Div([
            html.Div([
                dcc.Interval(id='header-tick', interval=250),
                html.Div(id='header', style={"fontSize": "20px", "fontWeight": "600",
                                             "marginBottom": "20px"}),
            ]),
            panel('spread-tick', 500, 'spread-chart', 'spread', 'BID-ASK SPREAD'),
            panel('obi-tick', 500, 'obi-chart', 'obi', 'ORDER BOOK IMBALANCE'),
            panel('vpin-tick', 1000, 'vpin-chart', 'vpin', 'VPIN'),
        ], style={"backgroundColor": BG, "color": FG, "minHeight": "100vh",
                  "padding": "24px", "maxWidth": "900px", "margin": "0 auto",
                  "fontFamily": "system-ui, sans-serif"})

        @self.app.callback(Output('header', 'children'), 
                           Input('header-tick', 'n_intervals'))
        def update_header(n):
            return "BTCUSDT Microstructure"

        @self.app.callback(Output('spread', 'children'), 
                           Output('spread-chart', 'figure'),
                           Input('spread-tick', 'n_intervals'))
        def update_spread(n):
            curr, fig = self._series(self.metrics_manager.get_metric(SPREAD_KEY), "Spread (bps)", 500)
            return f"{curr:.5f} bps", fig

        @self.app.callback(Output('obi', 'children'), 
                            Output('obi-chart', 'figure'),
                           Input('obi-tick', 'n_intervals'))
        def update_obi(n):
            curr, fig = self._series(self.metrics_manager.get_metric(OBI_KEY), "Order Book Imbalance", 500, yaxis_range=[-1, 1])
            return f"{curr:+.4f}", fig

        @self.app.callback(Output('vpin', 'children'), 
                           Output('vpin-chart', 'figure'),
                           Input('vpin-tick', 'n_intervals'))
        def update_vpin(n):
            curr, fig = self._series(self.metrics_manager.get_metric(VPIN_KEY), "VPIN", 500, yaxis_range=[0, 1])
            return f"{curr:.4f}", fig

        threading.Thread(target=self.app.run, kwargs={"port": 8050}, daemon=True).start()