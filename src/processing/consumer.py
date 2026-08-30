import asyncio

async def consumer(message_queue: asyncio.Queue):
    while (True):
        msg = await message_queue.get()
        print("Consumer is processing msg:\n")
        print(msg)
        # We then process the message