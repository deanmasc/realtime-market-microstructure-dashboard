from utils.constants import PARTIAL_DEPTH_STREAM_NAME, AGGREGATE_TRADES_STREAM_NAME
from processing.metrics import Metric, BidAskSpreadMetric, OrderBookImbalanceMetric, VPINMetric
from collections import defaultdict

class MetricsManager:
    def __init__(self):
        self.stream_metric_dict = defaultdict(list)
        # self.stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME].append(BidAskSpreadMetric())
        # self.stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME].append(OrderBookImbalanceMetric())
        self.stream_metric_dict[AGGREGATE_TRADES_STREAM_NAME].append(VPINMetric())

    def process_metric_updates(self, msg) -> None:
        msg_stream = msg['stream']

        if not msg_stream or msg_stream not in self.stream_metric_dict:
            return

        for metric in self.stream_metric_dict[msg_stream]:
            metric.update(msg)
        

