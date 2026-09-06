from abc import ABC, abstractmethod
import math

class Metric(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update(self, msg: dict): ...

    @abstractmethod
    def get_value(self): ...

    # @abstractmethod
    # def get_name(self): ...


class BidAskSpreadMetric(Metric):
    BIP = 10000
    ALPHA = 0.1
    def __init__(self):
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
        return self.value if self.value is not None else 0.0
    

class OrderBookImbalanceMetric(Metric):
    pass

class VPINMetric(Metric):
    pass