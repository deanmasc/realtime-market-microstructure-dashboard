import asyncio
from market_data.stream_handler import BinanceSockethandler
from market_data.producer import Producer
from processing.consumer import Consumer

async def main():
    """
    Main entry function, we need to:
    - Establish connections with Binance Streams
    - Commence loop to run the loop of updating the dashboard in real time
    """
    message_queue = asyncio.Queue(maxsize=1000)
    connection_handler = BinanceSockethandler(message_queue)
    await connection_handler.setup_connection() # creates websocket
    
    producer = Producer(connection_handler)
    consumer = Consumer(message_queue)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer.produce())
        tg.create_task(consumer.consume())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exiting")