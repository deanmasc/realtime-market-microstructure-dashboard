from abc import ABC, abstractmethod

class Metric(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def update(self): ...

    @abstractmethod
    def get_value(self): ...

    @abstractmethod
    def get_name(self): ...


class BidAskSpreadMetric(Metric):
    pass

class OrderBookImbalanceMetric(Metric):
    pass

class VPINMetric(Metric):
    pass