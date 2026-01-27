from bridge import *

@event
async def load(event: Event):
    server.broadcast("server start")

@event
async def block_break(event: Event):
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.player.send_message("You cannot break blocks there!")
        await event.cancel()

@event
async def block_place(event: Event):
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.player.send_message("You cannot place blocks there!")
        await event.cancel()

@event
async def block_explode(event: Event):
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.cancel()

