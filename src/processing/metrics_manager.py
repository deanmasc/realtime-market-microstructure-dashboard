from utils.constants import PARTIAL_DEPTH_STREAM_NAME, AGGREGATE_TRADES_STREAM_NAME
from processing.metrics import Metric, BidAskSpreadMetric, OrderBookImbalanceMetric, VPINMetric
from collections import defaultdict

class MetricsManager:
    def __init__(self):
        # create some storage which stores all metrics objects 
        # Need to find some way to be able t know which metrics to update
        # based on the message/stream type, naive way is to check for each,
        # but would be nice to know the list for a certain stream using a map
        self.stream_metric_dict = defaultdict(list(Metric))

        self.stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME].append(BidAskSpreadMetric())
        self.stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME].append(OrderBookImbalanceMetric())
        self.stream_metric_dict[AGGREGATE_TRADES_STREAM_NAME].append(VPINMetric())

    def process_metric_updates(self, msg):
        msg_stream = msg['stream']

        if not msg_stream or msg_stream not in self.stream_metric_dict:
            return

        for metric in self.stream_metric_dict[msg_stream]:
            metric.update(msg)
        

