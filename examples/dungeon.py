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
from bridge.extensions import Dungeon, loot_pool

# ── Register loot generators ────────────────────────────────────────
# These fill chests tagged with [loot:<pool>] in the room template.

@loot_pool("common")
def fill_common(inventory, room):
    """Fill a common loot chest."""
    inventory.add_item(ItemBuilder("BREAD").amount(8).build())
    inventory.add_item(ItemBuilder("IRON_INGOT").amount(3).build())
    inventory.add_item(ItemBuilder("ARROW").amount(16).build())

@loot_pool("rare")
def fill_rare(inventory, room):
    """Fill a rare loot chest."""
    inventory.add_item(
        ItemBuilder("DIAMOND_SWORD")
        .name("§bFrostbite")
        .enchant("sharpness", 3)
        .lore("§7A blade of ancient ice")
        .glow()
        .build()
    )
    inventory.add_item(ItemBuilder("GOLDEN_APPLE").amount(2).build())

@loot_pool("boss")
def fill_boss(inventory, room):
    """Fill the boss room reward chest."""
    inventory.add_item(
        ItemBuilder("NETHERITE_CHESTPLATE")
        .name("§5Crypt Lord's Plate")
        .enchant("protection", 5)
        .enchant("blast_protection", 5)
        .enchant("projectile_protection", 5)
        .enchant("fire_protection", 5)
        .unbreakable()
        .glow()
        .lore("§7Taken from the crypt lord's corpse")
        .build()
    )
    inventory.add_item(ItemBuilder("DIAMOND").amount(16).build())

# ── Define the dungeon ──────────────────────────────────────────────
# Point rooms_dir at a folder full of .droom files.
# The start_room is the first room placed (must exist as a .droom file).

crypt = Dungeon(
    name="Ancient Crypt",
    rooms_dir="plugins/PyJavaBridge/scripts/crypt_rooms",
    room_count=10,
    branch_factor=0.5,  # 0=depth-first, 1=breadth-first, 0.5=balanced
    description="A crumbling crypt filled with undead horrors.",
    difficulty=3,
    start_room="entrance",  # entrance.droom
)

# Optional: limit how many rooms of a given type can appear
crypt.type_limits["boss"] = 1
crypt.type_limits["treasure"] = 2

# ── Dungeon event handlers ──────────────────────────────────────────

@crypt.on_enter
async def on_enter(instance, player):
    player.send_message("§5You descend into the Ancient Crypt...")
    player.send_message(f"§7Rooms: {len(instance.rooms)} | Difficulty: {instance.dungeon.difficulty}")
    player.play_sound("ambient_cave")

@crypt.on_complete
async def on_complete(instance):
    for p in instance.players:
        p.send_message("§a§lDungeon Complete! §7The Ancient Crypt trembles...")
        p.play_sound("ui_toast_challenge_complete")
    # Auto-cleanup after 30 seconds
    await server.after(600)
    await instance.destroy()

@crypt.on_room_enter
async def on_room_enter(player, room):
    player.send_message(f"§8Entering: §f{room.template.name} §7({room.template.type})")

@crypt.on_room_clear
async def on_room_clear(room):
    print(f"Room {room.template.name} at {room.origin} cleared!")

# ── Commands ─────────────────────────────────────────────────────────

@command("Start a dungeon run")
async def dungeon(event: Event):
    player = event.player
    loc = player.location

    # Place dungeon at player's location
    origin = (int(loc.x), int(loc.y), int(loc.z))

    try:
        instance = await crypt.create_instance(
            players=[player],
            origin=origin,
            world=player.world,
        )
        player.send_message(f"§dGenerated {len(instance.rooms)} rooms:")
        for room in instance.rooms:
            player.send_message(
                f"  §8{room.origin} §f{room.template.name} §7({room.template.type})"
            )
    except RuntimeError as e:
        player.send_message(f"§c{e}")

@command("Destroy active dungeon")
async def dungeon_destroy(event: Event):
    if not crypt.instances:
        event.player.send_message("§7No active dungeon instances.")
        return

    instance = crypt.instances[-1]
    await instance.destroy()
    event.player.send_message("§eDungeon destroyed and blocks restored.")

@command("List dungeon instances")
async def dungeon_list(event: Event):
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

