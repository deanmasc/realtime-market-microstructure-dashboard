# realtime-market-microstructure-dashboard
Market microstructure describes the mechanics of how prices form and trades execute. This project consumes a live exchange feed, computes three core microstructure metrics in real time as each update arrives, and displays them on a live-updating dashboard. 

## FAQS
**• Why does VPIN use volume buckets rather than time buckets?**

VPIN uses volume buckets as opposed to time buckets and volume is a more consistent method to calculate each sub VPIN on due to the fact that there may be some time periods where more volume is traded than others, which can lead to some VPINs being overrepresented and others being underrepresented. Volume buckets fixes this because it keeps volume constant, therefore each sub VPIN is equally as influential.

**• What happens to the event loop if the message queue blocks instead of drops?**

Imagine the case where the producer attempts to append a message to the message queue, however it is full, therefore it can't immediately do so, at this point the producer task will stop executing and in the asyncio scheduler it will change status to 'not ready' or similar. The consumer task is already ready in the asyncio schedular, therefore this task will start executing and the consumer will start processing the messages and updating the metrics and dashboard in 'real time'. It will continue doing so until the queue is completely empty because it will never hand back until there is nothing to pop from the message queue. At the point it is empty and the consumer task tries to pop it will go back to 'not ready' status, and now the producer task can continue where it left off and append the message which is previously was not able to. As the producer just drianed the entire message queue it is likely in that time market data has been collected in the sockets buffer so the producer task will process this and add this into the message queue until it is full again or there is no more market data to put in the message queue.

**• What do your VPIN readings show during a period of high volatility versus a quiet period?**

When there is high volatility the price is jumping up and/or down at more varied rates, therefore a dominated side being the aggressor is more likely, and for VPIN when one side is the primary aggressor the metric approaches 1. During a quirt period you would assume the price variation is more stable, therefore the side aggressor domination is more even, when the side volume aggression is more even the VPIN is typically closer to 0.