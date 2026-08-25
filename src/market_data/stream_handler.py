import asyncio, websockets, json
from utils.constants import STREAM_URL, PARTIAL_DEPTH_STREAM_NAME, AGGREGATE_TRADES_STREAM_NAME

class BinanceSockethandler:
    def __init__(self, message_queue: asyncio.Queue):
        self.ws = None
        self.message_queue = message_queue
        self.recv_data_mode = True

    async def setup_connection(self) -> None:
        print("Setting up WebSocket connection.")
        self.ws = await websockets.connect(STREAM_URL)
        print("WebSocket connection established.")

    async def recv_data(self) -> None:
        print("Commencing stream data retrieval")

        try:
            while (self.recv_data_mode):
                if self.ws is not None:
                    msg = await self.ws.recv()
                    msg = json.loads(msg)
                    if msg['stream'] == PARTIAL_DEPTH_STREAM_NAME:
                        print("This message is from the partial depth stream")
                    elif msg['stream'] == AGGREGATE_TRADES_STREAM_NAME:
                        print("This message is from the aggregate trades stream")

                    print(f"Message recieved: {msg}\n")
        
        finally:
            await self.close_connection()

        print("Stopped recieveing data")

    async def close_connection(self) -> None:
        print("\nClosing socket connection")
        await self.ws.close()

    def set_recv_data_mode(self, status: bool) -> None:
        self.recv_data_mode = status