import math

import pytest

from processing.metrics import BidAskSpreadMetric, OrderBookImbalanceMetric, VPINMetric
from utils.constants import AGGREGATE_TRADES_STREAM_NAME, PARTIAL_DEPTH_STREAM_NAME


# ---------------------------------------------------------------------------
# Message builders (Binance combined-stream format)
# ---------------------------------------------------------------------------

def depth_msg(bids, asks):
    """bids/asks: list of (price, qty); bids best-first (descending), asks best-first (ascending)."""
    return {
        "stream": PARTIAL_DEPTH_STREAM_NAME,
        "data": {
            "lastUpdateId": 1,
            "bids": [[f"{p:.8f}", f"{q:.8f}"] for p, q in bids],
            "asks": [[f"{p:.8f}", f"{q:.8f}"] for p, q in asks],
        },
    }


def trade_msg(qty, is_buy, price=100_000.0):
    """is_buy=True -> buyer is the aggressor, so the buyer is NOT the maker (m=False)."""
    return {
        "stream": AGGREGATE_TRADES_STREAM_NAME,
        "data": {
            "e": "aggTrade",
            "E": 1,
            "s": "BTCUSDT",
            "a": 1,
            "p": f"{price:.8f}",
            "q": f"{qty:.8f}",
            "f": 1,
            "l": 1,
            "T": 1,
            "m": not is_buy,
            "M": True,
        },
    }


def buy(qty):
    return trade_msg(qty, is_buy=True)


def sell(qty):
    return trade_msg(qty, is_buy=False)


def spread_bps(bid, ask):
    mid = (bid + ask) / 2
    return (ask - bid) / mid * 10_000


# ---------------------------------------------------------------------------
# Bid-Ask Spread
# ---------------------------------------------------------------------------

class TestBidAskSpread:
    def test_value_before_any_update_is_zero(self):
        assert BidAskSpreadMetric().get_value() == 0.0

    def test_spread_in_bps_relative_to_mid(self):
        m = BidAskSpreadMetric()
        m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)]))
        assert m.get_value() == pytest.approx(spread_bps(100.0, 101.0))
        assert m.get_value() == pytest.approx(99.50248756, rel=1e-9)

    def test_realistic_btc_prices(self):
        m = BidAskSpreadMetric()
        m.update(depth_msg(bids=[(65_000.00, 0.5)], asks=[(65_000.01, 0.3)]))
        assert m.get_value() == pytest.approx(spread_bps(65_000.00, 65_000.01))

    def test_zero_spread(self):
        m = BidAskSpreadMetric()
        m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(100.0, 1.0)]))
        assert m.get_value() == pytest.approx(0.0)

    def test_uses_only_top_of_book(self):
        m = BidAskSpreadMetric()
        bids = [(100.0, 1.0), (99.0, 50.0), (98.0, 50.0)]
        asks = [(102.0, 1.0), (103.0, 50.0), (104.0, 50.0)]
        m.update(depth_msg(bids, asks))
        assert m.get_value() == pytest.approx(spread_bps(100.0, 102.0))

    def test_quantities_do_not_affect_spread(self):
        a, b = BidAskSpreadMetric(), BidAskSpreadMetric()
        a.update(depth_msg(bids=[(100.0, 0.001)], asks=[(101.0, 999.0)]))
        b.update(depth_msg(bids=[(100.0, 999.0)], asks=[(101.0, 0.001)]))
        assert a.get_value() == pytest.approx(b.get_value())

    def test_each_update_replaces_previous_spread(self):
        m = BidAskSpreadMetric()
        m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)]))
        m.update(depth_msg(bids=[(200.0, 1.0)], asks=[(200.5, 1.0)]))
        assert m.get_value() == pytest.approx(spread_bps(200.0, 200.5))

    def test_spread_is_non_negative(self):
        m = BidAskSpreadMetric()
        for bid, ask in [(100.0, 100.01), (50.0, 51.0), (65_000.0, 65_010.0)]:
            m.update(depth_msg(bids=[(bid, 1.0)], asks=[(ask, 1.0)]))
            assert m.get_value() >= 0.0

    # --- EWMA rolling mean -------------------------------------------------

    def test_rolling_mean_follows_ewma_recurrence(self):
        """mean_k = a * x_k + (1 - a) * mean_{k-1}, checked between consecutive updates."""
        m = BidAskSpreadMetric()
        a = BidAskSpreadMetric.ALPHA
        quotes = [(100.0, 101.0), (100.0, 100.5), (100.0, 102.0), (100.0, 100.1), (100.0, 103.0)]

        m.update(depth_msg(bids=[(quotes[0][0], 1.0)], asks=[(quotes[0][1], 1.0)]))
        prev_mean = m.rolling_spread_bps_mean
        assert prev_mean is not None

        for bid, ask in quotes[1:]:
            m.update(depth_msg(bids=[(bid, 1.0)], asks=[(ask, 1.0)]))
            x = spread_bps(bid, ask)
            expected = a * x + (1 - a) * prev_mean
            assert m.rolling_spread_bps_mean == pytest.approx(expected, rel=1e-12)
            prev_mean = m.rolling_spread_bps_mean

    def test_rolling_mean_of_constant_spread_equals_that_spread(self):
        m = BidAskSpreadMetric()
        for _ in range(50):
            m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)]))
        assert m.rolling_spread_bps_mean == pytest.approx(spread_bps(100.0, 101.0))

    def test_rolling_mean_stays_between_min_and_max_observed(self):
        m = BidAskSpreadMetric()
        values = []
        for ask in [101.0, 100.2, 105.0, 100.7, 102.3, 100.01]:
            m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(ask, 1.0)]))
            values.append(spread_bps(100.0, ask))
            assert min(values) - 1e-9 <= m.rolling_spread_bps_mean <= max(values) + 1e-9

    # --- EWMA rolling std --------------------------------------------------

    def test_rolling_std_of_constant_spread_is_zero(self):
        m = BidAskSpreadMetric()
        for _ in range(50):
            m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(101.0, 1.0)]))
        assert m.rolling_spread_bps_std == pytest.approx(0.0, abs=1e-9)

    def test_rolling_std_is_non_negative(self):
        m = BidAskSpreadMetric()
        for ask in [101.0, 100.2, 105.0, 100.7, 102.3, 100.01]:
            m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(ask, 1.0)]))
            assert m.rolling_spread_bps_std >= 0.0

    def test_rolling_std_positive_when_spread_varies(self):
        m = BidAskSpreadMetric()
        for ask in [101.0, 102.0] * 10:
            m.update(depth_msg(bids=[(100.0, 1.0)], asks=[(ask, 1.0)]))
        assert m.rolling_spread_bps_std > 0.0


# ---------------------------------------------------------------------------
# Order Book Imbalance
# ---------------------------------------------------------------------------

def levels(start, step, qtys):
    return [(start + i * step, q) for i, q in enumerate(qtys)]


class TestOrderBookImbalance:
    N = OrderBookImbalanceMetric.N_LEVELS

    def obi(self, bid_qtys, ask_qtys):
        m = OrderBookImbalanceMetric()
        m.update(depth_msg(bids=levels(100.0, -1.0, bid_qtys), asks=levels(101.0, 1.0, ask_qtys)))
        return m.get_value()

    def test_value_before_any_update_is_zero(self):
        assert OrderBookImbalanceMetric().get_value() == 0.0

    def test_balanced_book_is_zero(self):
        assert self.obi([1.0] * self.N, [1.0] * self.N) == pytest.approx(0.0)

    def test_balanced_totals_with_different_shapes_is_zero(self):
        bids = [5.0] + [0.0] * (self.N - 1)
        asks = [1.0] * self.N
        assert self.obi(bids, asks) == pytest.approx(0.0)

    def test_known_value(self):
        # bid_vol = 3 * N, ask_vol = 1 * N -> (3 - 1) / (3 + 1) = 0.5
        assert self.obi([3.0] * self.N, [1.0] * self.N) == pytest.approx(0.5)

    def test_known_negative_value(self):
        # bid_vol = 1 * N, ask_vol = 3 * N -> -0.5
        assert self.obi([1.0] * self.N, [3.0] * self.N) == pytest.approx(-0.5)

    def test_uneven_levels_known_value(self):
        bids = [0.5, 1.25, 2.0, 0.25, 1.0][: self.N]
        asks = [1.0, 0.75, 0.5, 3.0, 0.25][: self.N]
        bv, av = sum(bids), sum(asks)
        assert self.obi(bids, asks) == pytest.approx((bv - av) / (bv + av))

    def test_all_bid_volume_is_plus_one(self):
        assert self.obi([1.0] * self.N, [0.0] * self.N) == pytest.approx(1.0)

    def test_all_ask_volume_is_minus_one(self):
        assert self.obi([0.0] * self.N, [1.0] * self.N) == pytest.approx(-1.0)

    def test_only_top_n_levels_are_used(self):
        # Top N balanced, but a huge amount of bid volume sits deeper in the book (depth20).
        bids = [1.0] * self.N + [1_000.0] * (20 - self.N)
        asks = [1.0] * self.N + [0.001] * (20 - self.N)
        assert self.obi(bids, asks) == pytest.approx(0.0)

    def test_deeper_levels_do_not_change_value(self):
        top_bids, top_asks = [2.0] * self.N, [1.0] * self.N
        shallow = self.obi(top_bids, top_asks)
        deep = self.obi(top_bids + [50.0] * 15, top_asks + [7.0] * 15)
        assert deep == pytest.approx(shallow)

    def test_prices_do_not_affect_value(self):
        a, b = OrderBookImbalanceMetric(), OrderBookImbalanceMetric()
        qtys_b, qtys_a = [2.0] * self.N, [1.0] * self.N
        a.update(depth_msg(bids=levels(100.0, -1.0, qtys_b), asks=levels(101.0, 1.0, qtys_a)))
        b.update(depth_msg(bids=levels(65_000.0, -0.01, qtys_b), asks=levels(65_000.01, 0.01, qtys_a)))
        assert a.get_value() == pytest.approx(b.get_value())

    def test_value_always_in_range(self):
        m = OrderBookImbalanceMetric()
        for bq, aq in [(0.001, 900.0), (900.0, 0.001), (1.0, 1.0), (3.3, 7.7)]:
            m.update(depth_msg(bids=levels(100.0, -1.0, [bq] * 20), asks=levels(101.0, 1.0, [aq] * 20)))
            assert -1.0 <= m.get_value() <= 1.0

    def test_each_update_replaces_previous_value(self):
        m = OrderBookImbalanceMetric()
        m.update(depth_msg(bids=levels(100.0, -1.0, [3.0] * self.N), asks=levels(101.0, 1.0, [1.0] * self.N)))
        m.update(depth_msg(bids=levels(100.0, -1.0, [1.0] * self.N), asks=levels(101.0, 1.0, [3.0] * self.N)))
        assert m.get_value() == pytest.approx(-0.5)


# ---------------------------------------------------------------------------
# VPIN
# ---------------------------------------------------------------------------

B = VPINMetric.BUCKET_VOLUME
C = VPINMetric.N_VPINS


def fill_bucket(m, buy_frac):
    """Fill exactly one bucket with buy_frac of it buyer-initiated. Returns expected VPIN_i."""
    buy_vol, sell_vol = buy_frac * B, (1 - buy_frac) * B
    if buy_vol > 0:
        m.update(buy(buy_vol))
    if sell_vol > 0:
        m.update(sell(sell_vol))
    return abs(buy_vol - sell_vol) / B


class TestVPIN:
    def test_value_before_any_update_is_zero(self):
        assert VPINMetric().get_value() == 0.0

    def test_no_change_until_first_bucket_filled(self):
        m = VPINMetric()
        m.update(buy(0.25 * B))
        m.update(buy(0.25 * B))
        m.update(buy(0.25 * B))
        assert m.get_value() == 0.0

    def test_bucket_filled_by_single_trade_all_buys(self):
        m = VPINMetric()
        m.update(buy(B))
        assert m.get_value() == pytest.approx(1.0)

    def test_bucket_filled_by_single_trade_all_sells(self):
        m = VPINMetric()
        m.update(sell(B))
        assert m.get_value() == pytest.approx(1.0)

    def test_buyer_is_maker_flag_counts_as_sell(self):
        # m=True means the buyer was the maker, so the seller was the aggressor.
        m = VPINMetric()
        m.update(trade_msg(0.5 * B, is_buy=False))  # m=True
        m.update(trade_msg(0.5 * B, is_buy=True))   # m=False
        assert m.get_value() == pytest.approx(0.0)

    def test_balanced_bucket_is_zero(self):
        m = VPINMetric()
        m.update(buy(0.5 * B))
        m.update(sell(0.5 * B))
        assert m.get_value() == pytest.approx(0.0)

    def test_bucket_filled_by_many_trades(self):
        m = VPINMetric()
        for _ in range(3):
            m.update(buy(0.25 * B))
        assert m.get_value() == 0.0
        m.update(sell(0.25 * B))
        # |0.75B - 0.25B| / B = 0.5
        assert m.get_value() == pytest.approx(0.5)

    def test_partial_bucket_does_not_change_vpin(self):
        m = VPINMetric()
        m.update(buy(B))
        assert m.get_value() == pytest.approx(1.0)
        m.update(sell(0.5 * B))
        m.update(sell(0.25 * B))
        assert m.get_value() == pytest.approx(1.0)

    def test_vpin_is_average_of_filled_buckets(self):
        m = VPINMetric()
        fill_bucket(m, 1.0)   # VPIN_1 = 1
        fill_bucket(m, 0.5)   # VPIN_2 = 0
        assert m.get_value() == pytest.approx(0.5)
        fill_bucket(m, 0.75)  # VPIN_3 = 0.5
        assert m.get_value() == pytest.approx(0.5)
        fill_bucket(m, 0.0)   # VPIN_4 = 1
        assert m.get_value() == pytest.approx((1 + 0 + 0.5 + 1) / 4)

    def test_average_before_window_full(self):
        """VPIN = (S * VPIN + VPIN_new) / (S + 1) while fewer than C buckets filled."""
        m = VPINMetric()
        vpins = []
        for k in range(C):
            vpins.append(fill_bucket(m, (k % 5) / 4))
            assert m.get_value() == pytest.approx(sum(vpins) / len(vpins))

    def test_window_evicts_oldest_bucket_at_capacity(self):
        m = VPINMetric()
        fill_bucket(m, 1.0)  # VPIN_1 = 1, will be evicted
        for _ in range(C - 1):
            fill_bucket(m, 0.5)  # 0
        assert m.get_value() == pytest.approx(1 / C)
        fill_bucket(m, 0.5)  # evicts VPIN_1
        assert m.get_value() == pytest.approx(0.0)

    def test_rolling_average_matches_mean_of_last_c_buckets(self):
        """VPIN = VPIN + (VPIN_new - VPIN_old) / C once at capacity; must equal mean of last C."""
        m = VPINMetric()
        vpins = []
        for k in range(5 * C + 3):
            vpins.append(fill_bucket(m, ((k * 3) % 5) / 4))
            window = vpins[-C:]
            assert m.get_value() == pytest.approx(sum(window) / len(window), abs=1e-9)

    def test_many_buckets_does_not_drift(self):
        m = VPINMetric()
        for _ in range(1_000):
            fill_bucket(m, 1.0)
        for _ in range(C):
            fill_bucket(m, 0.5)
        assert m.get_value() == pytest.approx(0.0, abs=1e-9)

    def test_many_small_trades_fill_bucket(self):
        m = VPINMetric()
        for _ in range(64):
            m.update(buy(B / 64))
        assert m.get_value() == pytest.approx(1.0)

    # --- Trades that cross bucket boundaries ------------------------------

    def test_overflow_volume_carries_into_next_bucket(self):
        m = VPINMetric()
        m.update(buy(0.25 * B))
        m.update(sell(B))  # 0.75B completes bucket 1, 0.25B sell carries over
        # Bucket 1: |0.25B - 0.75B| / B = 0.5
        assert m.get_value() == pytest.approx(0.5)
        m.update(sell(0.75 * B))  # bucket 2: 0.25B carried + 0.75B = all sell -> 1.0
        assert m.get_value() == pytest.approx((0.5 + 1.0) / 2)

    def test_single_trade_can_fill_multiple_buckets(self):
        m = VPINMetric()
        m.update(buy(2.5 * B))  # two full buy buckets, 0.5B buy carried over
        assert m.get_value() == pytest.approx(1.0)
        m.update(sell(0.5 * B))  # bucket 3: 0.5B buy + 0.5B sell -> 0
        assert m.get_value() == pytest.approx((1.0 + 1.0 + 0.0) / 3)

    def test_single_trade_larger_than_window(self):
        m = VPINMetric()
        fill_bucket(m, 0.5)  # 0, will be evicted
        m.update(buy(C * B))  # C full buy buckets
        assert m.get_value() == pytest.approx(1.0)

    def test_value_always_in_unit_interval(self):
        m = VPINMetric()
        trades = [buy(0.3 * B), sell(1.7 * B), buy(3.1 * B), sell(0.05 * B), buy(0.9 * B), sell(4.4 * B)]
        for t in trades * 5:
            m.update(t)
            assert 0.0 <= m.get_value() <= 1.0 + 1e-12
