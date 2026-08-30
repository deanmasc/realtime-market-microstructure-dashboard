import asyncio
from market_data.stream_handler import BinanceSockethandler

class Producer:
    def __init__(self, connection_handler: BinanceSockethandler):
        self.connection_handler = connection_handler

    async def produce(self):
        await self.connection_handler.recv_data() # loops on recieveing data
