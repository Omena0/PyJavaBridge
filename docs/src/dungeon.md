---
title: Dungeon [ext]
subtitle: Instanced dungeon system with procedural generation
---

# Dungeon [ext]

The dungeon system provides `Dungeon`, `DungeonInstance`, and `DungeonRoom` for creating instanced, procedurally generated dungeons.

```python
from bridge.extensions import Dungeon, DungeonInstance, DungeonRoom, RoomType
```

---

## RoomType

Enum with values: `HALLWAY`, `COMBAT`, `PUZZLE`, `TREASURE`, `TRAP`, `BOSS`.

Each type has generation constraints:

| Type | Min Depth | Notes |
| ---- | --------- | ----- |
| `HALLWAY` | 0 | Default filler |
| `COMBAT` | 0 | Common room |
| `TRAP` | 1 | Minimum 1 room from entrance |
| `PUZZLE` | 2 | Must be near treasure or boss |
| `TREASURE` | 3 | Must be near puzzle, boss, or hallway |
| `BOSS` | 8 | Max 1 per dungeon, far from entrance |

---

## Dungeon

### Constructor

```python
Dungeon(name, description="", difficulty=1, recommended_level=1,
        room_count=12, grid_size=8)
```

### Methods

#### create_instance(players, room_count=None, grid_size=None) → DungeonInstance

Generate and return a new dungeon instance.

### Decorators

```python
my_dungeon = Dungeon("Crypt", difficulty=3)

@my_dungeon.on_enter
def entered(instance, player):
    player.send_message("You enter the Crypt...")

@my_dungeon.on_complete
def cleared(instance):
    for p in instance.players:
        p.send_message("§aDungeon cleared!")

@my_dungeon.reward
def give_reward(instance):
    for p in instance.players:
        p.give_exp(500)

@my_dungeon.on_room_enter
def room_enter(player, room):
    player.send_message(f"Entering {room.room_type.value} room")

@my_dungeon.on_room_clear
def room_clear(room):
    print(f"Room {room.grid_x},{room.grid_z} cleared")
```

---

## DungeonInstance

Created by `Dungeon.create_instance()`.

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `rooms` | `list[DungeonRoom]` | Generated rooms |
| `players` | `list[Player]` | Players in this instance |
| `progress` | `float` | 0.0 – 1.0 fraction of rooms cleared |
| `is_complete` | `bool` | Whether all rooms are cleared |

### Methods

#### complete() → Awaitable

Fire completion handlers.

#### destroy()

Clean up the instance.

---

## DungeonRoom

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `room_type` | `RoomType` | Type of room |
| `mobs` | `list` | Mob descriptors |
| `cleared` | `bool` | Whether cleared |
| `grid_x` / `grid_z` | `int` | Grid position |

### Methods

#### mark_cleared()

Mark room as cleared and fire `on_clear` handlers.

### Decorators

```python
room.on_enter(handler)
room.on_clear(handler)
```

---

## Generation Algorithm

Room layouts use a wave-function-collapse (WFC) inspired algorithm:

1. A random walk from the entrance selects which grid cells become rooms.
2. Each cell starts with all possible room types based on depth constraints.
3. The cell with the fewest options (lowest entropy) is collapsed first.
4. Constraints propagate to neighbours, eliminating impossible types.
5. Repeat until all cells are assigned.
