---
title: "Commands Example"
subtitle: "Commands, raycast teleport, inventory GUIs, and click events"
---

# Commands Example

This script demonstrates several core PyJavaBridge features:
registering chat commands, using raycast for teleportation,
creating inventory-based GUIs, and handling inventory click/drag events.

Drop this file into `plugins/PyJavaBridge/scripts/` and reload the server.

```python
from bridge import *
from typing import Optional

# ─── Simple Command ─────────────────────────────────────────────────
# The @command decorator registers a chat command whose name matches
# the function name.  The string argument becomes the command's
# description (shown in /help).
#
# Every command handler receives an Event object.  event.player is the
# Player who ran the command.

@command("Hello world command")
async def helloworld(event: Event):
    """Send a Hello World message to the player."""
    # send_message() delivers a chat message only to this player.
    event.player.send_message("Hello, World!")


# ─── Command with Arguments ────────────────────────────────────────
# Extra function parameters after `event` become command arguments.
# Optional parameters (with a default) are not required in-game.
# PJB auto-generates the usage string from the function signature.

@command("Greet command")
async def greet(event: Event, name: Optional[str] = None):
    """Greet a player by name."""
    # If the player doesn't supply a name, fall back to their own name.
    event.player.send_message(f"Hello, {name or event.player.name}!")


# ─── Raycast & Teleport ────────────────────────────────────────────
# raycast() fires an invisible ray through the world and returns the
# first block it hits (or None if it reaches max distance).
#
# Arguments: world name, origin (x,y,z), direction (yaw, pitch),
#            max distance, step size, ignore fluids.
#
# This example casts straight down from y=320 at (0.5, 0.5) to find
# the highest block, then teleports the player on top of it.

@command("Teleport to spawn")
async def spawn(event: Event):
    """Teleport the player to spawn using raycast."""
    # Cast a ray straight down (pitch 90°) from build limit.
    ray = await raycast('world', (0.5, 320, 0.5), (0, 90), 384, 0.5, False)

    if ray is not None:
        # ray.y is the top of the block we hit; add 0.5 so the player
        # stands on top rather than inside the block.
        event.player.teleport(Location(0.5, ray.y + 0.5, 0.5, world='world'))


# ─── Inventory GUI ──────────────────────────────────────────────────
# Inventories can be used as custom GUIs.  Create an Inventory with a
# size (must be a multiple of 9) and a title, then open it for a
# player.  Items placed inside act as clickable buttons.

@command("open test gui")
async def gui(event: Event):
    """Open a test inventory GUI."""
    # Create a filler pane with a blank name so it looks decorative.
    pane = Item('light_gray_stained_glass_pane')
    await pane.set_name(" ")

    # Fill all 27 slots (3 rows × 9 columns) with the filler pane.
    inv = Inventory(3 * 9, title="Test GUI", contents=[pane for _ in range(3 * 9)])

    # Place a special item in the center slot (row 1, column 4 → slot 13).
    totem = Item('totem_of_undying')
    await totem.set_name("Bing chilling")
    inv.set_item(9 + 4, totem)

    # Open the inventory for the player who ran the command.
    inv.open(event.player)


# ─── Handling Inventory Clicks ──────────────────────────────────────
# To make a GUI interactive, listen for the inventory_click event.
# Check event.inventory.title to make sure the click happened in YOUR
# GUI (other plugins may have inventories open too).
#
# Always call event.cancel() to prevent the player from taking items
# out of the GUI.

@event
async def inventory_click(event: Event):
    """Handle clicks in the test GUI."""
    # Ignore clicks in inventories that aren't ours.
    if event.inventory.title != 'Test GUI':
        return

    # Cancel the click so items can't be moved out of the GUI.
    event.cancel()

    # Slot 13 (9 + 4) is where we placed the totem.
    if event.slot == 9 + 4:
        # Play the totem revival sound and send a chat message.
        event.player.play_sound(Sound.from_name('ITEM_TOTEM_USE'))
        event.player.send_message('Bing chilling')
        # Close the GUI after the player clicks the button.
        event.inventory.close()


# ─── Preventing Drags ──────────────────────────────────────────────
# Players can also drag items across slots.  Cancel that too so the
# GUI stays intact.

@event
async def inventory_drag(event: Event):
    """Cancel drags in the test GUI."""
    if event.inventory.title == 'Test GUI':
        event.cancel()


# ─── Viewing Another Player's Inventory ────────────────────────────
# Player(name=...) looks up an online player by name.  Accessing
# .inventory returns their real inventory, and .open() shows it to
# another player.

@command("Open someones inv")
async def invsee(event: Event, p: str):
    """Open another player's inventory."""
    # Don't let players open their own inventory through this command –
    # it would cause a confusing double-open.
    if p == event.player.name:
        event.player.send_message("You cannot open your own inventory!")
        event.player.play_sound(Sound.from_name('BLOCK_NOTE_BLOCK_BASS'))
        return

    # Look up the target by name and open their inventory for the caller.
    Player(name=p).inventory.open(event.player)
```
