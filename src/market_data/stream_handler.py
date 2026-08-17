import asyncio, websockets, json
from utils.constants import STREAM_URL, PARTIAL_DEPTH_STREAM_NAME, AGGREGATE_TRADES_STREAM_NAME

class BinanceSockethandler:
    def __init__(self):
        self.ws = None
        self.recv_data_mode = True

    async def setup_connection(self) -> None:
        print("Setting up WebSocket connection.")
        self.ws = await websockets.connect(STREAM_URL)
        print("WebSocket connection established.")

    async def recv_data(self) -> None:
        print("Commencing stream data retrieval")
        while (self.recv_data_mode):
            if self.ws is not None:
                try:
                    msg = await self.ws.recv()
                    print(f"Message recieved: {msg}")
                finally:
                    self.close_connection()
        print("Stopped recieveing data")

    async def close_connection(self) -> None:
        await self.ws.close()

    def set_recv_data_mode(self, status: bool) -> None:
        self.recv_data_mode = status