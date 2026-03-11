---
title: "Spawn Protection"
subtitle: "Prevent building near spawn with block events"
---

# Spawn Protection

A compact script that prevents players from breaking, placing, or
exploding blocks within 15 blocks of spawn.  It shows how to listen
for block-related events and cancel them conditionally.

Drop this file into `plugins/PyJavaBridge/scripts/` and reload the server.

```python
from bridge import *

# ─── Server Load Event ──────────────────────────────────────────────
# The "load" event fires once when the script is first loaded by the
# plugin.  It's a good place for initialization or broadcast messages.

@event
async def load(event: Event):
    """Broadcast a start message on server load."""
    # server.broadcast() sends a message to every online player.
    server.broadcast("server start")


# ─── Block Break Protection ────────────────────────────────────────
# The function name "block_break" matches the Bukkit BlockBreakEvent.
# PJB automatically routes it to this handler.
#
# event.block gives you the Block being broken, which has .x, .y, .z
# coordinates.  We use the Manhattan distance on the X/Z plane to
# define a diamond-shaped protected zone around (0, 0).

@event
async def block_break(event: Event):
    """Cancel block breaking near spawn."""
    # Manhattan distance from spawn on the horizontal plane.
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        # Tell the player why their action was denied.
        event.player.send_message("You cannot break blocks there!")
        # event.cancel() prevents the block from actually being broken.
        await event.cancel()


# ─── Block Place Protection ────────────────────────────────────────
# Same logic as block_break, but for BlockPlaceEvent.  Both events
# expose event.block and event.player.

@event
async def block_place(event: Event):
    """Cancel block placing near spawn."""
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.player.send_message("You cannot place blocks there!")
        await event.cancel()


# ─── Explosion Protection ──────────────────────────────────────────
# block_explode covers TNT, creepers, and other explosions.  Note that
# there is no event.player here (explosions aren't always caused by a
# player), so we just silently cancel without a message.

@event
async def block_explode(event: Event):
    """Cancel explosions near spawn."""
    if (abs(event.block.x) + abs(event.block.z)) < 15:
        event.cancel()
```
