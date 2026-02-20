---
title: Examples
subtitle: Complete script examples
---

# Examples

Full working scripts that demonstrate PyJavaBridge features.

---

## Commands & GUI

A script demonstrating commands, raycast teleportation, inventory GUIs, and inventory click events.

```python
from bridge import *

# Simple hello world command
@command("Hello world command")
async def helloworld(event: Event):
    event.player.send_message("Hello, World!")

# Command with arguments
@command("Greet command")
async def greet(event: Event, name: str = None):
    event.player.send_message(f"Hello, {name or event.player.name}!")

# Raycast to find ground level, then teleport
@command("Teleport to spawn")
async def spawn(event: Event):
    ray = await raycast('world', (0.5, 320, 0.5), (0, 90), 384, 0.5, False)
    event.player.teleport((0.5, ray.y + 0.5, 0.5))

# Custom inventory GUI
@command("open test gui")
async def gui(event: Event):
    inv = Inventory(
        3 * 9,
        title="Test GUI",
        contents=[
            Item('light_gray_stained_glass_pane').set_name(" ")
            for _ in range(3 * 9)
        ]
    )
    inv.set_item(9 + 4, Item('totem_of_undying').set_name("Bing chilling"))
    inv.open(event.player)

# Handle clicks in the GUI
@event
async def inventory_click(event: Event):
    if event.inventory.title != 'Test GUI':
        return

    event.cancel()

    if event.slot == 9 + 4:
        event.player.play_sound('item_totem_use')
        event.player.send_message('Bing chilling')
        event.inventory.close()

# Prevent dragging in the GUI
@event
async def inventory_drag(event: Event):
    if event.inventory.title == 'Test GUI':
        event.cancel()

# View another player's inventory
@command("Open someones inv")
async def invsee(event: Event, p: str):
    if p == event.player.name:
        event.player.send_message("You cannot open your own inventory!")
        event.player.play_sound('block_note_block_bass')
        return

    Player(p).inventory.open(event.player)
```

**Concepts demonstrated:**
- [`@command`](decorators.md) with and without arguments
- [`raycast()`](raycast.md) for finding ground level
- [`Inventory`](inventory.md) with custom contents
- [`@event`](decorators.md) for `inventory_click` and `inventory_drag`
- [`Event.cancel()`](event.md#cancel) to prevent default behavior
- [`Player`](player.md) messaging, sounds, and teleportation

---

## Spawn Protection

A script that prevents building near spawn using block events.

```python
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
```

**Concepts demonstrated:**
- [`@event`](decorators.md) for `block_break`, `block_place`, `block_explode`, and `load`
- [`Event.cancel()`](event.md#cancel) to prevent block modification
- [`Event.block`](event.md#block) to access block coordinates
- [`server.broadcast()`](server.md#broadcast) for server-wide messages
- Diamond (taxicab) distance check for a protection zone

---

## Temporary Ban System

A full ban system with configurable durations and persistence.

```python
"""Ban users for customizable amounts of time."""
from humanfriendly import format_timespan
from time import time as time_now
from bridge import *
import re

bans = {}

def parse_time(time: str) -> int:
    """Parse a time string like '1h30m' into seconds."""
    if not time:
        raise ValueError('Time string is required')

    units = {
        's': 1, 'm': 60, 'h': 3600,
        'd': 86400, 'w': 604800,
        'mo': 2592000, 'y': 31536000,
    }

    pattern = re.compile(r'(\d+)(mo|[smhdwy])', re.IGNORECASE)
    total = 0
    time_str = time.strip().lower()
    idx = 0

    for match in pattern.finditer(time_str):
        if match.start() != idx:
            raise ValueError(f"Invalid time format: {time}")
        value = int(match.group(1))
        unit = match.group(2)
        if unit not in units:
            raise ValueError(f"Unknown time unit: {unit}")
        total += value * units[unit]
        idx = match.end()

    if idx != len(time_str):
        raise ValueError(f"Invalid time format: {time}")
    return total

@command('Ban someone for a specified time or permanently')
async def ban(event: Event, user: str, t: str = None, r: str = None):
    global bans

    if not event.player.is_op():
        event.player.send_message('No permission!')
        event.player.play_sound('block_note_block_bass')
        return

    target = Player(user)
    duration = parse_time(t) if t else None
    reason = r or "Ban hammer has spoken!"

    reason_text = (
        f"You have been {'permanently ' if not duration else ''}banned"
        f"{f' for {format_timespan(duration)}' if duration else ''}"
        f"\nReason: {reason}"
    )

    await target.kick(reason_text)
    bans[target.uuid] = (time_now() + duration if duration else None, reason)

    event.player.send_message(
        f"{user} has been {'permanently ' if not duration else ''}banned"
        f"{f' for {format_timespan(duration)}' if duration else ''}"
    )

@command('Unban someone')
async def unban(event: Event, user: str):
    global bans

    if not event.player.is_op():
        event.player.send_message('No permission!')
        event.player.play_sound('block_note_block_bass')
        return

    target = Player(user)
    if target.uuid not in bans:
        event.player.send_message("That user is not banned")
        event.player.play_sound('block_note_block_bass')
        return

    bans.pop(target.uuid)
    event.player.send_message(f"{user} has been unbanned.")

@event
async def player_join(event: Event):
    global bans
    uuid = event.player.uuid

    if uuid not in bans:
        return

    time, reason = bans[uuid]
    if time:
        time -= time_now()

    if time and time <= 0:
        bans.pop(uuid)
        return

    event.player.kick(
        f"You have been {'permanently ' if not time else ''}banned"
        f"{f' for {format_timespan(time)}' if time else ''}"
        f"\nReason: {reason}"
    )
```

**Concepts demonstrated:**
- [`@command`](decorators.md) with multiple optional arguments
- [`Player`](player.md) creation by name for offline lookups
- [`Player.kick()`](player.md#kick) with a formatted reason
- [`Player.is_op`](player.md#is_op) for permission checking
- [`@event`](decorators.md) for `player_join` to enforce bans on login
- Python standard library usage (`re`, `time`)
- Third-party library usage (`humanfriendly`)
- State management with a global dictionary

---

## Tips for Writing Scripts

1. **Always import from bridge:** `from bridge import *`
2. **Use async/await:** Most bridge methods return awaitables
3. **Name your event handlers after the event:** `async def block_break(event)` handles `block_break` events
4. **Commands auto-register:** The function name becomes the command name
5. **Cancel events to prevent default behavior:** `await event.cancel()`
6. **Use the [`Config`](config.md) class for persistence** instead of global dictionaries
