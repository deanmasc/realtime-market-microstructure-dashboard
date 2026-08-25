import asyncio
from market_data.stream_handler import BinanceSockethandler

async def main():
    """
    Main entry function, we need to:
    - Establish connections with Binance Streams
    - Commence loop to run the loop of updating the dashboard in real time
    """
    connection_handler = BinanceSockethandler()
    await connection_handler.setup_connection() # creates websocket

    try:
        await connection_handler.recv_data() # loops on recieveing data
    except asyncio.CancelledError:
        print("The program is exiting due to a Ctrl-C event")

if __name__ == "__main__":
    asyncio.run(main())