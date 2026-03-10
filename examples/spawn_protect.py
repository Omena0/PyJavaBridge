from bridge import *

@event
async def load(event: Event):
    """Broadcast a start message on server load."""
    server.broadcast("server start")

@event
async def block_break(event: Event):
    """Cancel block breaking near spawn."""
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.player.send_message("You cannot break blocks there!")
        await event.cancel()

@event
async def block_place(event: Event):
    """Cancel block placing near spawn."""
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.player.send_message("You cannot place blocks there!")
        await event.cancel()

@event
async def block_explode(event: Event):
    """Cancel explosions near spawn."""
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.cancel()

