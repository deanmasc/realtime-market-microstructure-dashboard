from utils.constants import *
from processing.metrics import Metric, BidAskSpreadMetric, OrderBookImbalanceMetric, VPINMetric
from collections import defaultdict

class MetricsManager:
    def __init__(self):
        self.stream_metric_dict = defaultdict(list)
        self.metric_dict = defaultdict(Metric)

        spread_metric = BidAskSpreadMetric()
        obi_metric = OrderBookImbalanceMetric()
        vpin_metric = VPINMetric()

        self.stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME].append(spread_metric)
        self.stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME].append(obi_metric)
        self.stream_metric_dict[AGGREGATE_TRADES_STREAM_NAME].append(vpin_metric)
        self.metric_dict[SPREAD_KEY] = spread_metric
        self.metric_dict[OBI_KEY] = obi_metric
        self.metric_dict[VPIN_KEY] = vpin_metric

    def process_metric_updates(self, msg) -> None:
        msg_stream = msg['stream']

        if not msg_stream or msg_stream not in self.stream_metric_dict:
            return

        for metric in self.stream_metric_dict[msg_stream]:
            metric.update(msg)

    def get_metric(self, metric_key: str):
        if metric_key not in self.metric_dict:
            return None

        return self.metric_dict[self.metric_key]
        

