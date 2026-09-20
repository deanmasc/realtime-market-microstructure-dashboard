"""Tests for design.md sections 1 (Market Data Handling) and 2 (Producer/Consumer Concurrency)."""

import asyncio
import json

import pytest

from market_data.producer import Producer
from market_data.stream_handler import BinanceSockethandler
from processing.consumer import Consumer
from processing.metrics import BidAskSpreadMetric, OrderBookImbalanceMetric, VPINMetric
from processing.metrics_manager import MetricsManager
from utils.constants import AGGREGATE_TRADES_STREAM_NAME, PARTIAL_DEPTH_STREAM_NAME


# ---------------------------------------------------------------------------
# Raw socket payloads (what Binance puts on the wire: JSON strings)
# ---------------------------------------------------------------------------

def raw_depth(bid=100.0, ask=101.0, qty=1.0, levels=5):
    return json.dumps({
        "stream": PARTIAL_DEPTH_STREAM_NAME,
        "data": {
            "lastUpdateId": 1,
            "bids": [[f"{bid - i:.8f}", f"{qty:.8f}"] for i in range(levels)],
            "asks": [[f"{ask + i:.8f}", f"{qty:.8f}"] for i in range(levels)],
        },
    })


def raw_trade(qty=1.0, is_buy=True, price=100_000.0, agg_id=1):
    return json.dumps({
        "stream": AGGREGATE_TRADES_STREAM_NAME,
        "data": {
            "e": "aggTrade", "E": 1, "s": "BTCUSDT", "a": agg_id,
            "p": f"{price:.8f}", "q": f"{qty:.8f}",
            "f": 1, "l": 1, "T": 1, "m": not is_buy, "M": True,
        },
    })


def raw_unknown(stream="btcusdt@kline_1m"):
    return json.dumps({"stream": stream, "data": {"foo": "bar"}})


# The producer may push raw dicts or custom message objects; read either shape.
def stream_of(item):
    if isinstance(item, dict):
        return item.get("stream")
    return getattr(item, "stream", None)


def data_of(item):
    if isinstance(item, dict):
        return item.get("data")
    return getattr(item, "data", None)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeWebSocket:
    """Replays a fixed list of raw JSON strings, then idles like a quiet socket.

    yield_between=False models a burst: the messages are already sitting in the
    kernel buffer, so recv() hands them back without ever awaiting.
    """

    def __init__(self, messages, yield_between=True, on_recv=None):
        self.messages = list(messages)
        self.yield_between = yield_between
        self.on_recv = on_recv
        self.recv_count = 0
        self.closed = False

    async def recv(self):
        if self.on_recv is not None:
            self.on_recv(self.recv_count)
        if self.recv_count < len(self.messages):
            msg = self.messages[self.recv_count]
            self.recv_count += 1
            if self.yield_between:
                await asyncio.sleep(0)
            return msg
        await asyncio.Event().wait()  # idle socket: never returns

    async def close(self):
        self.closed = True


class RecordingQueue(asyncio.Queue):
    """An asyncio.Queue that remembers the deepest it ever got."""

    max_seen = 0

    def put_nowait(self, item):
        super().put_nowait(item)
        self.max_seen = max(self.max_seen, self.qsize())


class RecordingMetricsManager:
    """Stands in for MetricsManager so we can see exactly what the consumer forwarded."""

    def __init__(self, on_process=None):
        self.processed = []
        self.on_process = on_process

    def process_metric_updates(self, msg):
        self.processed.append(msg)
        if self.on_process is not None:
            self.on_process(msg)


class SpyMetric:
    def __init__(self):
        self.updates = []

    def update(self, msg):
        self.updates.append(msg)

    def get_value(self):
        return 0.0


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def build_pipeline(messages, maxsize=1000, yield_between=True, on_recv=None, on_process=None):
    queue = RecordingQueue(maxsize=maxsize)
    ws = FakeWebSocket(messages, yield_between=yield_between, on_recv=on_recv)
    handler = BinanceSockethandler(queue)
    handler.ws = ws
    producer = Producer(handler)
    consumer = Consumer(queue)
    recorder = RecordingMetricsManager(on_process=on_process)
    consumer.metrics_manager = recorder
    return queue, ws, handler, producer, consumer, recorder


async def wait_until(predicate, timeout=2.0):
    async def waiter():
        while not predicate():
            await asyncio.sleep(0.001)
    await asyncio.wait_for(waiter(), timeout)


async def cancel(*tasks):
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 1. Market data handling: socket -> parse -> queue
# ---------------------------------------------------------------------------

class TestStreamIngestion:
    def test_raw_json_is_parsed_before_being_queued(self):
        async def scenario():
            queue, ws, handler, producer, _, _ = build_pipeline([raw_depth()])
            task = asyncio.create_task(producer.produce())
            await wait_until(lambda: queue.qsize() == 1)
            await cancel(task)
            return queue.get_nowait()

        item = run(scenario())
        assert not isinstance(item, (str, bytes)), "message should be deserialised, not left as JSON text"
        assert stream_of(item) == PARTIAL_DEPTH_STREAM_NAME
        assert data_of(item)["bids"][0] == ["100.00000000", "1.00000000"]

    def test_messages_are_queued_in_arrival_order(self):
        async def scenario():
            messages = [raw_trade(agg_id=i) for i in range(5)]
            queue, ws, handler, producer, _, _ = build_pipeline(messages)
            task = asyncio.create_task(producer.produce())
            await wait_until(lambda: queue.qsize() == 5)
            await cancel(task)
            return [data_of(queue.get_nowait())["a"] for _ in range(5)]

        assert run(scenario()) == [0, 1, 2, 3, 4]

    def test_both_streams_are_queued(self):
        async def scenario():
            queue, ws, handler, producer, _, _ = build_pipeline([raw_depth(), raw_trade(), raw_depth()])
            task = asyncio.create_task(producer.produce())
            await wait_until(lambda: queue.qsize() == 3)
            await cancel(task)
            return [stream_of(queue.get_nowait()) for _ in range(3)]

        assert run(scenario()) == [
            PARTIAL_DEPTH_STREAM_NAME,
            AGGREGATE_TRADES_STREAM_NAME,
            PARTIAL_DEPTH_STREAM_NAME,
        ]

    def test_unrecognised_stream_is_still_queued_without_error(self):
        async def scenario():
            queue, ws, handler, producer, _, _ = build_pipeline([raw_unknown(), raw_trade()])
            task = asyncio.create_task(producer.produce())
            await wait_until(lambda: ws.recv_count == 2)
            await cancel(task)
            return queue.qsize()

        assert run(scenario()) >= 1

    def test_producer_drives_the_connection_handler(self):
        async def scenario():
            queue, ws, handler, producer, _, _ = build_pipeline([raw_trade()])
            task = asyncio.create_task(producer.produce())
            await wait_until(lambda: ws.recv_count >= 1)
            await cancel(task)
            return ws.recv_count

        assert run(scenario()) >= 1

    def test_recv_data_mode_false_stops_the_loop(self):
        async def scenario():
            state = {}

            def stop_after_three(index):
                if index == 2:
                    state["handler"].set_recv_data_mode(False)

            messages = [raw_trade(agg_id=i) for i in range(10)]
            queue, ws, handler, producer, _, _ = build_pipeline(messages, on_recv=stop_after_three)
            state["handler"] = handler
            await asyncio.wait_for(producer.produce(), timeout=2.0)
            return queue.qsize(), ws.recv_count

        queued, received = run(scenario())
        assert received == 3
        assert queued == 3

    def test_connection_is_closed_when_the_loop_stops(self):
        async def scenario():
            state = {}

            def stop_immediately(index):
                state["handler"].set_recv_data_mode(False)

            queue, ws, handler, producer, _, _ = build_pipeline([raw_trade()], on_recv=stop_immediately)
            state["handler"] = handler
            await asyncio.wait_for(producer.produce(), timeout=2.0)
            return ws.closed

        assert run(scenario()) is True

    def test_connection_is_closed_when_the_task_is_cancelled(self):
        async def scenario():
            queue, ws, handler, producer, _, _ = build_pipeline([raw_trade()])
            task = asyncio.create_task(producer.produce())
            await wait_until(lambda: queue.qsize() == 1)
            await cancel(task)
            return ws.closed

        assert run(scenario()) is True


# ---------------------------------------------------------------------------
# 2. Producer/consumer concurrency, capacity and bursts
# ---------------------------------------------------------------------------

class TestConcurrencyAndBursts:
    def test_consumer_waits_without_spinning_on_an_empty_queue(self):
        async def scenario():
            queue, ws, handler, producer, consumer, recorder = build_pipeline([])
            task = asyncio.create_task(consumer.consume())
            await asyncio.sleep(0.05)
            alive = not task.done()
            await cancel(task)
            return alive, recorder.processed, queue.qsize()

        alive, processed, qsize = run(scenario())
        assert alive, "consumer task should stay alive awaiting the queue"
        assert processed == []
        assert qsize == 0

    def test_messages_flow_from_socket_through_queue_to_consumer(self):
        async def scenario():
            messages = [raw_trade(agg_id=i) for i in range(20)]
            queue, ws, handler, producer, consumer, recorder = build_pipeline(messages)
            tasks = [asyncio.create_task(producer.produce()), asyncio.create_task(consumer.consume())]
            await wait_until(lambda: len(recorder.processed) == 20)
            await cancel(*tasks)
            return [data_of(m)["a"] for m in recorder.processed], queue.qsize()

        ids, remaining = run(scenario())
        assert ids == list(range(20))
        assert remaining == 0

    def test_queue_never_exceeds_its_capacity_during_a_burst(self):
        async def scenario():
            messages = [raw_trade(agg_id=i) for i in range(200)]
            queue, ws, handler, producer, consumer, recorder = build_pipeline(
                messages, maxsize=10, yield_between=False
            )
            tasks = [asyncio.create_task(producer.produce()), asyncio.create_task(consumer.consume())]
            await wait_until(lambda: len(recorder.processed) == 200, timeout=5.0)
            await cancel(*tasks)
            return queue.max_seen

        assert run(scenario()) <= 10

    def test_no_messages_are_lost_during_a_burst(self):
        async def scenario():
            messages = [raw_trade(agg_id=i) for i in range(200)]
            queue, ws, handler, producer, consumer, recorder = build_pipeline(
                messages, maxsize=10, yield_between=False
            )
            tasks = [asyncio.create_task(producer.produce()), asyncio.create_task(consumer.consume())]
            await wait_until(lambda: len(recorder.processed) == 200, timeout=5.0)
            await cancel(*tasks)
            return [data_of(m)["a"] for m in recorder.processed]

        assert run(scenario()) == list(range(200))

    def test_producer_hands_control_back_when_the_queue_is_full(self):
        """The consumer must get to run mid-burst rather than after the whole burst."""

        async def scenario():
            messages = [raw_trade(agg_id=i) for i in range(100)]
            observations = []
            state = {}

            def note(_msg):
                observations.append(state["ws"].recv_count)

            queue, ws, handler, producer, consumer, recorder = build_pipeline(
                messages, maxsize=5, yield_between=False, on_process=note
            )
            state["ws"] = ws
            tasks = [asyncio.create_task(producer.produce()), asyncio.create_task(consumer.consume())]
            await wait_until(lambda: len(recorder.processed) == 100, timeout=5.0)
            await cancel(*tasks)
            return observations

        observations = run(scenario())
        assert observations, "consumer never ran"
        assert min(observations) < 100, "consumer only ran after the producer drained the whole burst"

    def test_burst_larger_than_capacity_does_not_deadlock(self):
        async def scenario():
            messages = [raw_depth() for _ in range(500)]
            queue, ws, handler, producer, consumer, recorder = build_pipeline(
                messages, maxsize=8, yield_between=False
            )
            tasks = [asyncio.create_task(producer.produce()), asyncio.create_task(consumer.consume())]
            await wait_until(lambda: len(recorder.processed) == 500, timeout=5.0)
            await cancel(*tasks)
            return len(recorder.processed)

        assert run(scenario()) == 500

    def test_slow_consumer_does_not_stall_the_socket_reader(self):
        """While the consumer works through the queue the producer keeps draining the socket."""

        async def scenario():
            messages = [raw_trade(agg_id=i) for i in range(50)]
            queue, ws, handler, producer, consumer, recorder = build_pipeline(messages, maxsize=5)
            tasks = [asyncio.create_task(producer.produce()), asyncio.create_task(consumer.consume())]
            await wait_until(lambda: len(recorder.processed) >= 1)
            received_early = ws.recv_count
            await wait_until(lambda: len(recorder.processed) == 50)
            await cancel(*tasks)
            return received_early

        assert run(scenario()) >= 1


# ---------------------------------------------------------------------------
# Consumer -> MetricsManager routing
# ---------------------------------------------------------------------------

class TestConsumerRouting:
    def test_consumer_forwards_every_message_to_the_metrics_manager(self):
        async def scenario():
            queue = asyncio.Queue(maxsize=10)
            consumer = Consumer(queue)
            recorder = RecordingMetricsManager()
            consumer.metrics_manager = recorder
            task = asyncio.create_task(consumer.consume())
            for i in range(3):
                await queue.put({"stream": AGGREGATE_TRADES_STREAM_NAME, "data": {"a": i}})
            await wait_until(lambda: len(recorder.processed) == 3)
            await cancel(task)
            return [m["data"]["a"] for m in recorder.processed]

        assert run(scenario()) == [0, 1, 2]

    def test_consumer_owns_a_metrics_manager_by_default(self):
        assert isinstance(Consumer(asyncio.Queue()).metrics_manager, MetricsManager)


class TestMetricsManagerRouting:
    def _manager_with_spies(self):
        manager = MetricsManager()
        depth_spies = [SpyMetric(), SpyMetric()]
        trade_spies = [SpyMetric()]
        manager.stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME] = depth_spies
        manager.stream_metric_dict[AGGREGATE_TRADES_STREAM_NAME] = trade_spies
        return manager, depth_spies, trade_spies

    def test_depth_stream_is_wired_to_spread_and_imbalance(self):
        registered = MetricsManager().stream_metric_dict[PARTIAL_DEPTH_STREAM_NAME]
        types = {type(m) for m in registered}
        assert BidAskSpreadMetric in types
        assert OrderBookImbalanceMetric in types

    def test_agg_trade_stream_is_wired_to_vpin(self):
        registered = MetricsManager().stream_metric_dict[AGGREGATE_TRADES_STREAM_NAME]
        assert {type(m) for m in registered} == {VPINMetric}

    def test_depth_message_only_reaches_depth_metrics(self):
        manager, depth_spies, trade_spies = self._manager_with_spies()
        msg = json.loads(raw_depth())
        manager.process_metric_updates(msg)
        assert all(spy.updates == [msg] for spy in depth_spies)
        assert all(spy.updates == [] for spy in trade_spies)

    def test_trade_message_only_reaches_the_trade_metric(self):
        manager, depth_spies, trade_spies = self._manager_with_spies()
        msg = json.loads(raw_trade())
        manager.process_metric_updates(msg)
        assert all(spy.updates == [msg] for spy in trade_spies)
        assert all(spy.updates == [] for spy in depth_spies)

    def test_unknown_stream_updates_nothing(self):
        manager, depth_spies, trade_spies = self._manager_with_spies()
        manager.process_metric_updates(json.loads(raw_unknown()))
        assert all(spy.updates == [] for spy in depth_spies + trade_spies)

    def test_message_without_a_stream_is_ignored(self):
        manager, depth_spies, trade_spies = self._manager_with_spies()
        manager.process_metric_updates({"stream": None, "data": {}})
        assert all(spy.updates == [] for spy in depth_spies + trade_spies)


# ---------------------------------------------------------------------------
# End to end: raw socket frames move the real metric values
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_real_metrics_update_from_raw_socket_frames(self):
        async def scenario():
            messages = [raw_depth(bid=100.0, ask=101.0, qty=1.0)] * 3
            messages += [raw_trade(qty=VPINMetric.BUCKET_VOLUME, is_buy=True)]
            queue = RecordingQueue(maxsize=100)
            ws = FakeWebSocket(messages)
            handler = BinanceSockethandler(queue)
            handler.ws = ws
            producer, consumer = Producer(handler), Consumer(queue)
            tasks = [asyncio.create_task(producer.produce()), asyncio.create_task(consumer.consume())]
            await wait_until(lambda: ws.recv_count == len(messages) and queue.qsize() == 0)
            await asyncio.sleep(0.01)
            await cancel(*tasks)
            return consumer.metrics_manager

        manager = run(scenario())
        by_type = {
            type(metric): metric
            for metrics in manager.stream_metric_dict.values()
            for metric in metrics
        }
        assert by_type[BidAskSpreadMetric].get_value() == pytest.approx(99.50248756, rel=1e-6)
        assert by_type[OrderBookImbalanceMetric].get_value() == pytest.approx(0.0)
        assert by_type[VPINMetric].get_value() == pytest.approx(1.0)
