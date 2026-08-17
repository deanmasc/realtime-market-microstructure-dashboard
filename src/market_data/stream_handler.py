import asyncio, websockets, json
from utils.constants import STREAM_URL

class BinanceSockethandler:
    def __init__(self):
        self.ws = None

    async def setup_connection(self):
        self.ws = await websockets.connect(STREAM_URL)

    async def recv_data(self):
        while (True):
            if self.ws is not None:
                msg = await self.ws.recv()
                print(msg)

    async def close_connection(self):
        await self.ws.close()