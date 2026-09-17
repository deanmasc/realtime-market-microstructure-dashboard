from abc import ABC, abstractmethod
from collections import deque
import math

class Metric(ABC):
    WINDOW_LENGTH = 10_000 # 10,000 * 4bytes = 40,000 bytes = ~40KB for each metric, all fit in L1/2 cache

    def __init__(self):
        self.time_series_window = deque(maxlen=self.WINDOW_LENGTH)

    @abstractmethod
    def update(self, msg: dict): ...

    @abstractmethod
    def get_value(self): ...

    # @abstractmethod
    # def get_name(self): ...


class BidAskSpreadMetric(Metric):
    BIP = 10000
    ALPHA = 0.001

    def __init__(self):
        super().__init__()
        self.spread_bps = None
        self.best_bid = None
        self.best_ask = None
        self.mid = None
        self.rolling_spread_bps_mean = None
        self.rolling_spread_bps_std = None

    def update(self, msg: dict):
        self.best_bid = float(msg['data']['bids'][0][0])
        self.best_ask = float(msg['data']['asks'][0][0])
        print(f'BEST BID = {self.best_bid}, BEST ASK = {self.best_ask}')
        self.mid = (self.best_bid + self.best_ask) / 2
        self.spread_bps = ((self.best_ask - self.best_bid) / self.mid) * self.BIP
        self.time_series_window.append(self.spread_bps)
        print(f'UPDATED SPREAD BPS = {self.spread_bps}')

        if self.rolling_spread_bps_mean is None and self.rolling_spread_bps_std is None:
            self.rolling_spread_bps_mean = self.spread_bps
            self.rolling_spread_bps_std = 0.0
        else:
            diff = self.spread_bps - self.rolling_spread_bps_mean
            self.rolling_spread_bps_mean = self.rolling_spread_bps_mean + self.ALPHA * diff
            self.rolling_spread_bps_std = math.sqrt((1 - self.ALPHA) * (self.rolling_spread_bps_std**2 + self.ALPHA * diff**2))

            print(f'UPDATED SPREAD BPS ROLLING MEAN = {self.rolling_spread_bps_mean}')
            print(f'UPDATED SPREAD BPS ROLLING STD = {self.rolling_spread_bps_std}')

    
    def get_value(self) -> float:
        return self.spread_bps if self.spread_bps is not None else 0.0
    

class OrderBookImbalanceMetric(Metric):
    N_LEVELS = 5

    def __init__(self):
        super().__init__()
        self.obi = None

    def update(self, msg: dict):
        bid_volume = ask_volume = 0
        bids = msg['data']['bids']
        asks = msg['data']['asks']

        for i in range(self.N_LEVELS):
            bid_volume += float(bids[i][1])
            ask_volume += float(asks[i][1])

        if bid_volume + ask_volume == 0:
            self.obi = 0
        else:
            self.obi = (bid_volume - ask_volume)/(bid_volume + ask_volume)

        self.time_series_window.append(self.obi)
        print(f'UPDATED OBI VALUE = {self.obi}')

    def get_value(self) -> float:
        return self.obi if self.obi is not None else 0.0



class VPINMetric(Metric):
    pass