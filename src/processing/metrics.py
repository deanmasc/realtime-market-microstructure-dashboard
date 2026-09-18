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


class BidAskSpreadMetric(Metric):
    BIP = 10000
    ALPHA = 0.001

    def __init__(self):
        super().__init__()
        self.spread_bps = 0.0
        self.best_bid = 0.0
        self.best_ask = 0.0
        self.mid = 0.0
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
        return self.spread_bps
    

class OrderBookImbalanceMetric(Metric):
    N_LEVELS = 5

    def __init__(self):
        super().__init__()
        self.obi = 0.0

    def update(self, msg: dict):
        bid_volume = ask_volume = 0.0
        bids = msg['data']['bids']
        asks = msg['data']['asks']

        for i in range(self.N_LEVELS):
            bid_volume += float(bids[i][1])
            ask_volume += float(asks[i][1])

        if bid_volume + ask_volume == 0:
            self.obi = 0.0
        else:
            self.obi = (bid_volume - ask_volume)/(bid_volume + ask_volume)

        self.time_series_window.append(self.obi)
        print(f'UPDATED OBI VALUE = {self.obi}')

    def get_value(self) -> float:
        return self.obi



class VPINMetric(Metric):
    BUCKET_VOLUME = 0.5 # refers to 50BTC units
    N_VPINS = 10 # The number of bucket filled VPINs we use to calculate the global VPIN

    def __init__(self):
        super().__init__()
        self.curr_V_buy = 0.0
        self.curr_V_sell = 0.0
        self.curr_bucket_filled = 0.0
        self.vpin_window = deque(maxlen=self.N_VPINS)
        self.vpin = 0.0

    def update(self, msg: dict):
            msg_data = msg['data']
            volume = float(msg_data['q'])
            is_buyer_aggressor = msg_data['m'] # True for buyer aggressor false for seller aggressor
            has_updated_global_vpin = False

            while True:
                if volume == 0:
                    break
                elif (self.curr_bucket_filled + volume) < self.BUCKET_VOLUME:
                    if is_buyer_aggressor:
                        self.curr_V_buy += volume
                    else:
                        self.curr_V_sell += volume
                    self.curr_bucket_filled += volume
                    break
                else:
                    leftover = (self.curr_bucket_filled + volume) - self.BUCKET_VOLUME
                    curr_bucket_volume = volume - leftover

                    if is_buyer_aggressor:
                        self.curr_V_buy += curr_bucket_volume
                    else:
                        self.curr_V_sell += curr_bucket_volume

                    vpin_i = abs(self.curr_V_buy - self.curr_V_sell)/self.BUCKET_VOLUME
                    print(f'BUY AGRESSOR VOLUME = {self.curr_V_buy}, SELL AGGRESSOR VOLUME = {self.curr_V_sell}, bucket size = {self.BUCKET_VOLUME}')
                    print(f'VPIN_i HAS BEEN COMPUTED = {vpin_i}')

                    if len(self.vpin_window) == self.N_VPINS:
                        vpin_old = self.vpin_window.popleft()
                        self.vpin = self.vpin + 1/self.N_VPINS * (vpin_i - vpin_old)
                    elif len(self.vpin_window) < self.N_VPINS:
                        vpin_len = len(self.vpin_window)
                        self.vpin = 1/(vpin_len + 1) * (vpin_len * self.vpin + vpin_i)

                    has_updated_global_vpin = True
                    self.vpin_window.append(vpin_i)
                    self.curr_bucket_filled = 0.0
                    self.curr_V_sell = 0.0
                    self.curr_V_buy = 0.0
                    volume = leftover

            self.time_series_window.append(self.vpin)
            if has_updated_global_vpin: print(f'UPDATED GLOBAL VPIN = {self.vpin}')
    
    def get_value(self) -> float:
        return self.vpin

