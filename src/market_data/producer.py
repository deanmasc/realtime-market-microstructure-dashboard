import asyncio
from market_data.stream_handler import BinanceSockethandler

async def producer(connection_handler: BinanceSockethandler):
    await connection_handler.recv_data() # loops on recieveing data
