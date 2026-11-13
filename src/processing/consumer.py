import asyncio
from processing.metrics_manager import MetricsManager

class Consumer:
    def __init__(self, message_queue: asyncio.Queue, metrics_manager: MetricsManager):
        self.message_queue = message_queue
        self.metrics_manager = metrics_manager

    async def consume(self):
        while (True):
            msg = await self.message_queue.get()
            print("Consumer is processing msg:")
            print(msg)
            # We then process the message
            self.metrics_manager.process_metric_updates(msg)
