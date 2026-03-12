---
title: "Dungeon Example"
subtitle: "Procedural dungeon with rooms, loot, mobs, and lifecycle"
---

# Dungeon Example

An advanced example using the **Dungeon** extension to create a
procedurally generated dungeon with loot pools, mob spawning,
lifecycle events, and management commands.

> **Prerequisites:**
> - Build rooms in-game using `/bridge schem` (see the
>   [Dungeon docs](../extensions/dungeon.html) for details).
> - Save them as `.droom` files and place them in a `crypt_rooms/`
>   folder next to this script.

Drop this file into `plugins/PyJavaBridge/scripts/` and reload the server.

```python
# type: ignore
"""Example: Creating and running a dungeon with .droom room files.

Setup:
1. Build rooms in-game.
2. Place chests and name them [loot:common], [loot:rare], etc.
3. Run /bridge schem <x> <y> <z> <width> <height> <depth> to capture them.
4. Edit the saved .droom files to add exit definitions, set type, and loot pools.
   Exits use exact coordinates: exit: x,y,z <facing> <WxH> [tag]

5. Put the .droom files in a rooms/ folder next to this script.
"""

from bridge import *
# Dungeon and loot_pool come from the extensions package — they are
# not part of the core bridge API.
from bridge.extensions import Dungeon, loot_pool
import random
import inspect


# ── Register Loot Generators ───────────────────────────────────────
# A loot pool is a function that fills a chest's inventory when a room
# containing a chest tagged [loot:<pool_name>] is generated.
#
# The @loot_pool decorator registers the function under the given name.
# It receives:
#   - inventory: the chest Inventory to fill
#   - room:      the Room instance the chest belongs to

@loot_pool("common")
def fill_common(inventory, room):
    """Fill a common loot chest with basic supplies."""
    # ItemBuilder creates items with a fluent API.
    # .amount() sets the stack size.  .build() produces the final Item.
    inventory.add_item(ItemBuilder("BREAD").amount(8).build())
    inventory.add_item(ItemBuilder("IRON_INGOT").amount(3).build())
    inventory.add_item(ItemBuilder("ARROW").amount(16).build())


@loot_pool("rare")
def fill_rare(inventory, room):
    """Fill a rare loot chest with enchanted gear."""
    inventory.add_item(
        ItemBuilder("DIAMOND_SWORD")
        .name("§bFrostbite")                  # Custom display name (§b = aqua)
        .enchant("sharpness", 3)              # Apply Sharpness III
        .lore("§7A blade of ancient ice")     # Gray italic lore text
        .glow()                               # Add enchantment glint
        .build()
    )
    inventory.add_item(ItemBuilder("GOLDEN_APPLE").amount(2).build())


@loot_pool("boss")
def fill_boss(inventory, room):
    """Fill the boss room reward chest with top-tier loot."""
    inventory.add_item(
        ItemBuilder("NETHERITE_CHESTPLATE")
        .name("§5Crypt Lord's Plate")         # Dark purple name
        .enchant("protection", 5)             # Stacking all four protection types
        .enchant("blast_protection", 5)       # makes this truly overpowered
        .enchant("projectile_protection", 5)
        .enchant("fire_protection", 5)
        .unbreakable()                        # Never loses durability
        .glow()
        .lore("§7Taken from the crypt lord's corpse")
        .build()
    )
    inventory.add_item(ItemBuilder("DIAMOND").amount(16).build())


# ── Define the Dungeon ─────────────────────────────────────────────
# The Dungeon object describes a dungeon *template*.  It doesn't exist
# in the world yet — call create_instance() to actually build one.
#
# rooms_dir:     folder containing .droom files (relative to this script)
# room_count:    target number of rooms to generate
# branch_factor: 0 = long corridors (depth-first), 1 = wide (breadth-first)
# start_room:    the .droom file to use as the entrance (without extension)

crypt = Dungeon(
    name="Ancient Crypt",
    rooms_dir="crypt_rooms",
    room_count=50,
    branch_factor=0.8,
    description="A crumbling crypt filled with undead horrors.",
    difficulty=3,
    start_room="entrance",  # loads entrance.droom
)


# ── Dungeon Event Handlers ─────────────────────────────────────────
# Dungeon instances emit lifecycle events that you can hook into.
# Decorate handlers with @crypt.<event_name>.

@crypt.on_enter
async def on_enter(instance, player):
    """Greet the player entering the dungeon."""
    # instance is the live DungeonInstance; instance.rooms lists all
    # generated rooms.  instance.dungeon is the Dungeon template.
    player.send_message("§5You descend into the Ancient Crypt...")
    player.send_message(
        f"§7Rooms: {len(instance.rooms)} | Difficulty: {instance.dungeon.difficulty}"
    )
    player.play_sound("ambient_cave")


@crypt.on_complete
async def on_complete(instance):
    """Announce dungeon completion and schedule cleanup."""
    for p in instance.players:
        p.send_message("§a§lDungeon Complete! §7The Ancient Crypt trembles...")
        p.play_sound("ui_toast_challenge_complete")

    # server.after(ticks) is a coroutine that resolves after N ticks.
    # 600 ticks = 30 seconds at 20 TPS.
    await server.after(600)
    # destroy() removes all placed blocks and restores the original terrain.
    await instance.destroy()


@crypt.on_room_enter
async def on_room_enter(player, room):
    """Notify the player which room they entered."""
    # room.template holds the static data from the .droom file.
    player.send_message(
        f"§8Entering: §f{room.template.name} §7({room.template.type})"
    )


@crypt.on_room_clear
async def on_room_clear(room):
    """Log when a room is cleared (all mobs defeated)."""
    print(f"Room {room.template.name} at {room.origin} cleared!")


# ── Mob Spawning on Room Generation ────────────────────────────────
# on_room_generate fires for each room as the dungeon is being built.
# This is where you spawn enemies or set up traps.

@crypt.on_room_generate
async def spawn_room_mobs(room, world):
    """Spawn zombies proportional to room area."""
    # Calculate how many mobs to spawn based on room floor area.
    area = max(1, room.template.width * room.template.depth)
    count = max(1, area // 25)  # roughly 1 zombie per 25 blocks of floor

    # room.center gives the (x, y, z) center of the room.
    cx, cy, cz = room.center

    for _ in range(count):
        # Add a small random offset so mobs don't stack on the same spot.
        loc = (cx + random.uniform(-1, 1), cy, cz + random.uniform(-1, 1))
        try:
            # world.spawn_entity() may be sync or async depending on
            # the entity type — inspect.isawaitable handles both cases.
            r = world.spawn_entity(loc, "zombie")
            if inspect.isawaitable(r):
                await r
        except Exception:
            # Silently skip if spawning fails (e.g. location is inside a wall).
            pass


# ── Commands ────────────────────────────────────────────────────────

@command("Start a dungeon run")
async def dungeon(event: Event):
    """Create and enter a dungeon instance at the player's location."""
    player = event.player
    loc = player.location

    # Use the player's current position as the dungeon origin.
    origin = (int(loc.x), int(loc.y), int(loc.z))

    try:
        # create_instance() generates rooms, fills loot pools, fires
        # on_room_generate, and returns a DungeonInstance.
        instance = await crypt.create_instance(
            players=[player],
            origin=origin,
            world=player.world,
        )

        # List the generated rooms for debugging / fun.
        player.send_message(f"§dGenerated {len(instance.rooms)} rooms:")
        for room in instance.rooms:
            player.send_message(
                f"  §8{room.origin} §f{room.template.name} §7({room.template.type})"
            )
    except RuntimeError as e:
        player.send_message(f"§c{e}")


@command("Destroy active dungeon")
async def dungeon_destroy(event: Event):
    """Destroy the most recent dungeon instance."""
    # crypt.instances holds all live instances of this dungeon template.
    if not crypt.instances:
        event.player.send_message("§7No active dungeon instances.")
        return

    # Grab the latest instance and tear it down.
    instance = crypt.instances[-1]
    await instance.destroy()
    event.player.send_message("§eDungeon destroyed and blocks restored.")


@command("List dungeon instances")
async def dungeon_list(event: Event):
    """List all active dungeon instances."""
    if not crypt.instances:
        event.player.send_message("§7No active dungeon instances.")
        return

    for inst in crypt.instances:
        event.player.send_message(
            f"§dInstance #{inst.instance_id} §7- "
            f"{inst.progress:.0%} complete, "
            f"{len(inst.players)} player(s), "
            f"{len(inst.rooms)} rooms"
        )
```
