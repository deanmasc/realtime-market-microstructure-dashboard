import asyncio
from market_data.stream_handler import BinanceSockethandler
from market_data.producer import producer
from processing.consumer import consumer

async def main():
    """
    Main entry function, we need to:
    - Establish connections with Binance Streams
    - Commence loop to run the loop of updating the dashboard in real time
    """
    message_queue = asyncio.Queue(maxsize=1000)
    connection_handler = BinanceSockethandler(message_queue)
    await connection_handler.setup_connection() # creates websocket

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(connection_handler))
        tg.create_task(consumer(message_queue))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting")