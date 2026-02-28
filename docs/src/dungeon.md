---
title: Dungeon [ext]
subtitle: Jigsaw-style instanced dungeon system with world generation
---

# Dungeon [ext]

The dungeon system generates real in-world dungeons from `.droom` room
files.  Rooms connect via **jigsaw-style exits** — each exit has an
exact position, facing direction, and size.  Exits match when they
share the same **tag** and **size** with opposite facing directions.

```python
from bridge.extensions import Dungeon, DungeonInstance, PlacedRoom, RoomTemplate, Exit, loot_pool
```

---

## .droom File Format

Room blueprints are `.droom` text files with a metadata header and
block data separated by `---`:

```
type: combat
weight: 10
width: 9
height: 5
depth: 9
loot: chest1=common

exit: 0,2,4 -x 3x3
exit: 8,2,4 +x 3x3
exit: 4,4,0 -z 2x2 upper

S: stone_bricks
C: chest[facing=north,name=[loot:chest1]]

---
S9~7S~~7S~S3~S~S3~~7SS9~7S~~7S~SCS~S3~~7SS9~7S~~7S~S3~S~S3~~7SS9
```

### Metadata keys

| Key | Description |
| --- | ----------- |
| `type` | Free-form room type tag (`combat`, `hallway`, `boss`, …) |
| `weight` | Spawn weight (default `10`, higher = more likely) |
| `width` | Room X size |
| `height` | Room Y size (layers) |
| `depth` | Room Z size |
| `loot` | Space-separated `tag=pool` pairs for container filling |

### Exit definitions

Each exit is a connection point (like a Minecraft jigsaw block):

```
exit: <x>,<y>,<z> <facing> <width>x<height> [tag]
```

| Field | Description |
| ----- | ----------- |
| `x,y,z` | Position of the exit anchor inside the room (local coords) |
| `facing` | Outward-facing direction: `+x`, `-x`, `+y`, `-y`, `+z`, `-z` |
| `width x height` | Opening size |
| `tag` | Optional matching tag (default: `WxH`). Exits only connect to exits with the same tag, same size, and opposite facing |

A room can have **multiple exits of different sizes** on any face or
Y level.  The generator matches exits by tag+size and positions rooms
so the openings align block-by-block.

### Block keys

Single-character definitions map to block data (without `minecraft:` prefix):

```
S: stone_bricks
C: chest[facing=north,name=[loot:chest1]]
```

`~` is hardcoded as air.  Block states and NBT go in the key definition.

### Block data

After the `---` separator, a **single line** of RLE-encoded block keys.
Blocks are stored in **Y → Z → X** order.  `S3` = `SSS`, `~5` = `~~~~~`.

### Capturing with /bridge schem

Stand in-game and run:

```
/bridge schem <x> <y> <z> <width> <height> <depth>
```

This saves a `.droom` file to `plugins/PyJavaBridge/schematics/` with
auto-generated single-char keys and RLE compression.  Chests named
`[loot:tag]` are detected automatically.  Edit the file to add exit
definitions, set the room type, and configure loot pools.

---

## Exit

An exit/connection point (jigsaw block) within a room template.

### Constructor

```python
Exit(x, y, z, facing, width, height, tag=None)
```

- `facing` — Outward direction as a tuple: `(1,0,0)` for `+x`, `(-1,0,0)` for `-x`, etc.
- `tag` — Matching tag.  Defaults to `"{width}x{height}"`.

### Methods

#### can_connect(other) → bool

True if this exit can connect to `other` (same tag, same size, opposite facing).

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `x`, `y`, `z` | `int` | Position in room local coordinates |
| `facing` | `tuple[int,int,int]` | Outward-facing unit vector |
| `width` | `int` | Opening width |
| `height` | `int` | Opening height |
| `tag` | `str` | Matching tag |

---

## RoomTemplate

Parsed from a `.droom` file via `RoomTemplate.load(path)`.

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `name` | `str` | Filename stem |
| `type` | `str` | Room type tag |
| `exits` | `list[Exit]` | Exit definitions |
| `weight` | `int` | Spawn weight |
| `loot` | `dict[str, str]` | `{tag: pool}` loot mapping |
| `width` / `height` / `depth` | `int` | Room dimensions |
| `blocks` | `list` | 3D block data `[y][z][x]` |

### Methods

#### to_droom() → str

Serialize back to `.droom` format.

---

## Dungeon

### Constructor

```python
Dungeon(name, rooms_dir, room_count=12, branch_factor=0.5,
        min_candidates=5, description="", difficulty=1, start_room=None)
```

- `rooms_dir` — Path to directory containing `.droom` files.
- `branch_factor` — `0.0` = depth-first, `1.0` = breadth-first, `0.5` = balanced.
- `min_candidates` — Prefer exits with at least this many viable templates
  before expanding an exit.  Falls back to fewer when no exit meets the
  threshold.
- `start_room` — Name of the starting room template (without `.droom`).

### Configuration

```python
dungeon.type_limits["boss"] = 1   # Max 1 boss room per instance
```

### Methods

#### await create_instance(players, origin, world="world", room_count=None, branch_factor=None) → DungeonInstance

Generate, paste, and start tracking a dungeon.

- `origin` — `(x, y, z)` tuple for entrance room placement.
- Returns the new `DungeonInstance`.

#### reload_templates()

Re-scan the rooms directory for `.droom` files.

#### add_template(template)

Manually add a `RoomTemplate`.

### Decorators

```python
crypt = Dungeon("Crypt", rooms_dir="path/to/rooms")

@crypt.on_enter
async def entered(instance, player):
    player.send_message("You enter the Crypt...")

@crypt.on_complete
async def cleared(instance):
    for p in instance.players:
        p.send_message("§aDungeon cleared!")

@crypt.on_room_enter
async def room_enter(player, room):
    player.send_message(f"Entering {room.template.name}")

@crypt.on_room_clear
async def room_clear(room):
    print(f"Room {room.template.name} at {room.origin} cleared")
```

---

## DungeonInstance

Created by `await Dungeon.create_instance()`.

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `rooms` | `list[PlacedRoom]` | Placed rooms in the world |
| `players` | `list[Player]` | Participating players |
| `progress` | `float` | 0.0 – 1.0 fraction of rooms cleared |
| `is_complete` | `bool` | Whether all rooms are cleared |
| `world_name` | `str` | World the dungeon is in |

### Methods

#### await complete()

Fire completion handlers.

#### await destroy()

Restore all original blocks and remove the instance.

#### start_tracking()

Start polling player positions for room enter events.
Called automatically by `create_instance()`.

---

## PlacedRoom

A room that has been pasted into the world.

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `template` | `RoomTemplate` | The room blueprint |
| `origin` | `tuple[int, int, int]` | World position of `(0,0,0)` corner |
| `aabb` | `tuple` | `(min_corner, max_corner)` bounding box |
| `connected_exits` | `dict[int, PlacedRoom \| None]` | Exit connections by index |
| `cleared` | `bool` | Whether cleared |
| `center` | `tuple[int, int, int]` | Center of the room |

### Methods

#### mark_cleared()

Mark room as cleared and fire `on_clear` handlers.

### Decorators

```python
room.on_enter(handler)   # (player, room)
room.on_clear(handler)   # (room)
```

---

## Loot System

Register loot generators with `@loot_pool`:

```python
from bridge.extensions import loot_pool

@loot_pool("common")
def fill_common(inventory, room):
    inventory.add_item(ItemBuilder("BREAD").amount(8).build())

@loot_pool("rare")
def fill_rare(inventory, room):
    inventory.add_item(ItemBuilder("DIAMOND").amount(3).build())
```

In `.droom` files, use `loot: tag=pool` metadata.
In-game, name chests `[loot:tag]` — they'll be filled on generation.

---

## Generation Algorithm

The generator uses a jigsaw-style algorithm inspired by Minecraft's
structure generation:

1. Place the starting room at the given origin.
2. Collect all open (unconnected) exits across placed rooms.
3. For each open exit, find template+exit pairs that match by
   **tag**, **size**, and **opposite facing**, then check AABB
   overlap against all placed rooms.
4. **Lowest entropy first** — prioritise the exit with the fewest
   valid candidates.  Exits with fewer than `min_candidates`
   (default 5) are deprioritised.
5. Pick a candidate weighted by `weight` and position the new room
   so the exit openings align block-by-block.
6. `branch_factor` controls depth vs breadth when entropies tie.
7. Repeat until `room_count` is reached or no valid exits remain.

Rooms of any size can connect at any position/Y-level, supporting
hundreds of rooms across multiple levels with different-sized passages.
