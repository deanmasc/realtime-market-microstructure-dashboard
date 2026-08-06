# Technical Design Document
This document explains how key parts in this project are to be implemented. This includes discussions of alternatives and justifications of solutions. 

### Assumptions
- This project will be implemented with Python, therefore we are not considering multi-threading/paralellism

## 1. Market Data Handling
- Binance provides two WebSockets streams which this project will use to compute the three key metrics (spread, imbalance, VPIN), one of the streams gives the partial book depth and the other gives aggregate trades
- 2 sockets will be created to connect to both, as the partial book depth stream is used to calculate the spread and imbalance, and the aggregate trades stream is used to calculate the VPIN
- The naive solution would be to have a singlular loop which recieves from the socket, parses the data, and then directly processing the data by updating metrics and updating the dashboard accordingly, however there are a few downsides to this. The first being that we have no internal management of messages from the binance market data, therefore we cannot manage capacity, identify dropped messages etc. In addition to this we have no real separation of concerns per task, rather we have a single task that does everything which is technically okay in Python but poor practice.
- Therefore, I will implement multi-tasking via asyncio & a message queue to create an interface between a producer task which recieves from the socket and pushes to the message queue, and a consumer task which reads from the message queue and then does the processing of the market data from there. Therefore, we can manage the capacity of the amount of messages we have in our queue and we can track dropped messages as well when we reach capacity. we also separate responsibilities for different tasks, and if there is ever an extension where we have multiple consumers this will be much easier to implement.
- As this project is implemented in Python these tasks wont be running in paralell and only one will be running at once, the producer task will `await` when there is no data being recieved from the socket, and the consumer task will `await` when there is no messages/market data in the queue. 
- You may be asking - will the queue ever be full? and is there even a point in having tasks and a queue? because the consumer task will keep running as long as there is messages in the queue therefore the queue can never be full and there be a messages dropped/memory bandwidth problem? This is usually the case however in the tail case where the processing task wil take a long time or in the case where a significant market event occurs and the socket is recieveing a lot of market data, when the producer path is executing it may have a batch of messages to update the queue, and this batch may exceed the queue's capacity, therefore out internal handling will be helpful here in managing this.

## 2. Producer/Consumer Concurrency (non-parallel)

## 3. Performant Metrics Updates & State Management

## 4. Dashboard Real-Time Updates