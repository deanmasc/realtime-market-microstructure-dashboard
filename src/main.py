from market_data.stream_handler import BinanceSockethandler

def main():
    """
    Main entry function, we need to:
    - Establish connections with Binance Streams
    - Commence loop to run the loop of updating the dashboard in real time
    """
    connection_handler = BinanceSockethandler()
    connection_handler.setup_connection() # creates websocket
    connection_handler.recv_data() # loops on recieveing data

if __name__ == "__main__":
    main()