---
title: World
subtitle: World API with region utilities, particle shapes, and spawn helpers
---

# World

The `World` class provides access to world properties, blocks, entities, weather, time, and advanced utilities for working with regions, particles, and entity spawning.

---

## Constructor

```python
World(name: str | None = None)
```

Resolve a world by name. You can also get worlds from `server.worlds` or `server.world("name")`.

- **Parameters:**
  - `name` (`str | None`) — The world name (e.g. `"world"`, `"world_nether"`, `"world_the_end"`).

---

## Attributes

### name

- **Type:** `str`

The world name.

### uuid

- **Type:** `str`

The world's unique identifier.

### environment

- **Type:** `any`

The world environment (NORMAL, NETHER, THE_END).

### entities

- **Type:** `list[`[`Entity`](entity.md)`]`

All entities currently in the world, including players, mobs, dropped items, etc.

### players

- **Type:** `list[`[`Player`](player.md)`]`

All players currently in this world.

### time

- **Type:** `int`

Current world time (0–24000). 0 = dawn, 6000 = noon, 12000 = dusk, 18000 = midnight.

### world_time

- **Type:** [`WorldTime`](#worldtime-class)

Current world time as a `WorldTime` object with helper properties.

### full_time

- **Type:** `int`

Absolute world time that is not reset by sleeping.

### difficulty

- **Type:** [`Difficulty`](enums.md)

World difficulty level.

### spawn_location

- **Type:** [`Location`](location.md)

The world's spawn location.

### has_storm

- **Type:** `bool`

Whether it is currently raining/snowing.

### is_thundering

- **Type:** `bool`

Whether there is a thunderstorm.

### weather_duration

- **Type:** `int`

Remaining weather duration in ticks.

### thunder_duration

- **Type:** `int`

Remaining thunder duration in ticks.

---

## Methods

### block_at

```python
block = await world.block_at(x, y, z)
```

Get the block at specific coordinates.

- **Parameters:**
  - `x` (`int`) — X coordinate.
  - `y` (`int`) — Y coordinate.
  - `z` (`int`) — Z coordinate.
- **Returns:** `Awaitable[`[`Block`](block.md)`]`

```python
block = await world.block_at(0, 64, 0)
print(block.type)  # Material.GRASS_BLOCK
```

### chunk_at

```python
chunk = await world.chunk_at(x, z)
```

Get the chunk at chunk coordinates.

- **Parameters:**
  - `x` (`int`) — Chunk X (block X ÷ 16).
  - `z` (`int`) — Chunk Z (block Z ÷ 16).
- **Returns:** `Awaitable[`[`Chunk`](chunk.md)`]`

### spawn

```python
entity = await world.spawn(location, entity_cls, **kwargs)
```

Spawn an entity at a location.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Spawn position.
  - `entity_cls` (`type | EntityType | str`) — Entity type to spawn.
  - `**kwargs` — Additional spawn options.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]`

```python
zombie = await world.spawn(Location(0, 64, 0), EntityType.ZOMBIE)
```

### spawn_entity

```python
entity = await world.spawn_entity(location, entity_type, **kwargs)
```

Spawn an entity by type name.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Spawn position.
  - `entity_type` ([`EntityType`](enums.md) `| str`) — Entity type.
  - `**kwargs` — Additional options.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]`

### spawn_particle

```python
await world.spawn_particle(particle, location, count=1, offset_x=0, offset_y=0, offset_z=0, extra=0)
```

Spawn particles visible to all players in the world.

- **Parameters:**
  - `particle` ([`Particle`](enums.md)) — Particle type.
  - `location` ([`Location`](location.md)) — Center position.
  - `count` (`int`) — Number of particles.
  - `offset_x/y/z` (`float`) — Random offset range on each axis.
  - `extra` (`float`) — Extra data (usually speed).
- **Returns:** `Awaitable[None]`

```python
await world.spawn_particle(Particle.FLAME, player.location, count=50, offset_x=0.5, offset_y=1, offset_z=0.5)
```

### play_sound

```python
await world.play_sound(location, sound, volume=1.0, pitch=1.0)
```

Play a sound at a location, audible to nearby players.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Sound source position.
  - `sound` ([`Sound`](enums.md)) — Sound to play.
  - `volume` (`float`) — Volume. Default 1.0.
  - `pitch` (`float`) — Pitch. Default 1.0.
- **Returns:** `Awaitable[None]`

### strike_lightning

```python
entity = await world.strike_lightning(location)
```

Strike lightning at a location. This deals damage and starts fires.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Strike position.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]` — The lightning entity.

### strike_lightning_effect

```python
await world.strike_lightning_effect(location)
```

Strike visual-only lightning (no damage, no fire).

- **Parameters:**
  - `location` ([`Location`](location.md)) — Strike position.
- **Returns:** `Awaitable[None]`

---

## Time & Weather Setters

### set_time

```python
await world.set_time(time)
```

Set the world time.

- **Parameters:**
  - `time` (`int`) — Time value (0–24000).
- **Returns:** `Awaitable[None]`

### at_time

```python
@world.at_time(time)
async def handler(world):
    ...
```

Register a handler that runs every time this world crosses the specified time of day. Useful for day/night cycle events.

- **Parameters:**
  - `time` (`WorldTime | int`) — Target time (0–24000 ticks, or a `WorldTime` constant).

```python
world = World(name="world")

@world.at_time(WorldTime.NOON)
async def high_noon(w):
    await server.broadcast("It's high noon!")

@world.at_time(WorldTime.DUSK)
async def sunset(w):
    await server.broadcast("Night is falling...")

@world.at_time(0)
async def dawn(w):
    await server.broadcast("A new day begins!")
```

### set_full_time

```python
await world.set_full_time(time)
```

Set the absolute (non-resetting) time.

- **Parameters:**
  - `time` (`int`) — Absolute time value.
- **Returns:** `Awaitable[None]`

### set_difficulty

```python
await world.set_difficulty(difficulty)
```

Set the world difficulty.

- **Parameters:**
  - `difficulty` ([`Difficulty`](enums.md)) — Difficulty level.
- **Returns:** `Awaitable[None]`

### set_spawn_location

```python
await world.set_spawn_location(location)
```

Set the world spawn point.

- **Parameters:**
  - `location` ([`Location`](location.md)) — New spawn location.
- **Returns:** `Awaitable[None]`

### set_storm

```python
await world.set_storm(value)
```

Start or stop rain/snow.

- **Parameters:**
  - `value` (`bool`) — `True` = start storm, `False` = clear.
- **Returns:** `Awaitable[None]`

### set_thundering

```python
await world.set_thundering(value)
```

Start or stop thunderstorm.

- **Parameters:**
  - `value` (`bool`)
- **Returns:** `Awaitable[None]`

### set_weather_duration

```python
await world.set_weather_duration(ticks)
```

Set how long the current weather lasts.

- **Parameters:**
  - `ticks` (`int`) — Duration in ticks.
- **Returns:** `Awaitable[None]`

### set_thunder_duration

```python
await world.set_thunder_duration(ticks)
```

Set how long the current thunder lasts.

- **Parameters:**
  - `ticks` (`int`) — Duration in ticks.
- **Returns:** `Awaitable[None]`

---

## Region Utilities

These methods operate on regions of blocks in the world. Position arguments accept [`Location`](location.md), `tuple[int,int,int]`, or [`Vector`](vector.md).

### set_block

```python
count = await world.set_block(x, y, z, material, apply_physics=False)
```

Set a single block.

- **Parameters:**
  - `x, y, z` (`int`) — Block coordinates.
  - `material` ([`Material`](enums.md) `| str`) — Block material.
  - `apply_physics` (`bool`) — Whether to trigger physics updates. Default `False`.
- **Returns:** `Awaitable[int]` — Number of blocks changed (0 or 1).

### fill

```python
count = await world.fill(pos1, pos2, material, apply_physics=False)
```

Fill a cuboid region with a material.

- **Parameters:**
  - `pos1` — First corner.
  - `pos2` — Opposite corner.
  - `material` ([`Material`](enums.md) `| str`) — Block material.
  - `apply_physics` (`bool`) — Default `False`.
- **Returns:** `Awaitable[int]` — Number of blocks changed.

```python
await world.fill((0, 60, 0), (10, 70, 10), Material.STONE)
```

### replace

```python
count = await world.replace(pos1, pos2, from_material, to_material)
```

Replace all blocks of one material with another in a region.

- **Parameters:**
  - `pos1` — First corner.
  - `pos2` — Opposite corner.
  - `from_material` ([`Material`](enums.md) `| str`) — Material to replace.
  - `to_material` ([`Material`](enums.md) `| str`) — Replacement material.
- **Returns:** `Awaitable[int]` — Number of blocks replaced.

```python
await world.replace((0, 60, 0), (10, 70, 10), "DIRT", "GRASS_BLOCK")
```

### fill_sphere

```python
count = await world.fill_sphere(center, radius, material, hollow=False)
```

Fill a sphere with a material.

- **Parameters:**
  - `center` — Center position.
  - `radius` (`float`) — Sphere radius in blocks.
  - `material` ([`Material`](enums.md) `| str`) — Block material.
  - `hollow` (`bool`) — If `True`, only the shell is filled.
- **Returns:** `Awaitable[int]` — Number of blocks changed.

```python
await world.fill_sphere(player.location, 5, Material.GLASS, hollow=True)
```

### fill_cylinder

```python
count = await world.fill_cylinder(center, radius, height, material, hollow=False)
```

Fill a vertical cylinder.

- **Parameters:**
  - `center` — Center of the base.
  - `radius` (`float`) — Cylinder radius.
  - `height` (`int`) — Height in blocks.
  - `material` ([`Material`](enums.md) `| str`) — Block material.
  - `hollow` (`bool`) — If `True`, only the walls are filled.
- **Returns:** `Awaitable[int]`

### fill_line

```python
count = await world.fill_line(start, end, material)
```

Place blocks along a line between two points.

- **Parameters:**
  - `start` — Start position.
  - `end` — End position.
  - `material` ([`Material`](enums.md) `| str`) — Block material.
- **Returns:** `Awaitable[int]`

---

## Particle Shape Utilities

All particle shape methods accept optional `offset_x`, `offset_y`, `offset_z`, `extra` parameters for per-particle randomization.

### particle_line

```python
count = await world.particle_line(start, end, particle, density=4.0)
```

Draw a line of particles between two points.

- **Parameters:**
  - `start` — Start position.
  - `end` — End position.
  - `particle` ([`Particle`](enums.md) `| str`) — Particle type.
  - `density` (`float`) — Particles per block. Default 4.0.
- **Returns:** `Awaitable[int]` — Number of particles spawned.

### particle_sphere

```python
count = await world.particle_sphere(center, radius, particle, density=4.0, hollow=True)
```

Draw a sphere of particles.

- **Parameters:**
  - `center` — Center position.
  - `radius` (`float`) — Sphere radius.
  - `particle` ([`Particle`](enums.md) `| str`) — Particle type.
  - `density` (`float`) — Particles per block. Default 4.0.
  - `hollow` (`bool`) — If `True`, only surface particles. Default `True`.
- **Returns:** `Awaitable[int]`

### particle_cube

```python
count = await world.particle_cube(pos1, pos2, particle, density=4.0, hollow=True)
```

Draw a cuboid of particles.

- **Parameters:**
  - `pos1` — First corner.
  - `pos2` — Opposite corner.
  - `particle` ([`Particle`](enums.md) `| str`) — Particle type.
  - `density` (`float`) — Default 4.0.
  - `hollow` (`bool`) — Default `True`.
- **Returns:** `Awaitable[int]`

### particle_ring

```python
count = await world.particle_ring(center, radius, particle, density=4.0)
```

Draw a horizontal ring of particles.

- **Parameters:**
  - `center` — Center position.
  - `radius` (`float`) — Ring radius.
  - `particle` ([`Particle`](enums.md) `| str`) — Particle type.
  - `density` (`float`) — Default 4.0.
- **Returns:** `Awaitable[int]`

---

## Entity Spawn Helpers

### spawn_at_player

```python
entity = await world.spawn_at_player(player, entity_type, offset=None, **kwargs)
```

Spawn an entity at a player's current position with an optional offset.

- **Parameters:**
  - `player` ([`Player`](player.md)) — The player.
  - `entity_type` ([`EntityType`](enums.md) `| str`) — Entity type to spawn.
  - `offset` ([`Vector`](vector.md) `| tuple | None`) — Offset from player position.
  - `**kwargs` — Additional spawn options.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]`

```python
zombie = await world.spawn_at_player(player, "ZOMBIE", offset=(2, 0, 0))
```

### spawn_projectile

```python
entity = await world.spawn_projectile(shooter, entity_type, velocity=None, **kwargs)
```

Spawn a projectile from an entity with an optional initial velocity.

- **Parameters:**
  - `shooter` ([`Entity`](entity.md)) — The entity shooting the projectile.
  - `entity_type` ([`EntityType`](enums.md) `| str`) — Projectile type (e.g. `"ARROW"`, `"FIREBALL"`).
  - `velocity` ([`Vector`](vector.md) `| tuple | None`) — Initial velocity.
  - `**kwargs` — Additional options.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]`

### spawn_with_nbt

```python
entity = await world.spawn_with_nbt(location, entity_type, nbt, **kwargs)
```

Spawn an entity with custom SNBT (Stringified NBT) data.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Spawn position.
  - `entity_type` ([`EntityType`](enums.md) `| str`) — Entity type.
  - `nbt` (`str`) — SNBT string.
  - `**kwargs` — Additional options.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]`

```python
await world.spawn_with_nbt(loc, "ZOMBIE", '{IsBaby:1b,CustomName:\'{"text":"Baby Zombie"}\'}')
```

---

## World Utilities

### create_explosion

```python
await world.create_explosion(location, power=4.0, fire=False)
```

Create an explosion at the given location.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Center of the explosion.
  - `power` (`float`) — Explosion power. Default 4.0 (TNT-strength).
  - `fire` (`bool`) — Whether the explosion sets fire. Default `False`.
- **Returns:** `Awaitable[None]`

```python
await world.create_explosion(player.location, power=2.0, fire=True)
```

### entities_near

```python
entities = await world.entities_near(location, radius)
```

Get all entities within a radius of the location.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Center position.
  - `radius` (`float`) — Search radius in blocks.
- **Returns:** `Awaitable[list[`[`Entity`](entity.md)`]]`

```python
nearby = await world.entities_near(player.location, 10)
for e in nearby:
    await e.set_fire_ticks(100)
```

### blocks_near

```python
blocks = world.blocks_near(location, radius)
```

Get all blocks within a cubic radius of the location. **Synchronous** — returns a pre-built list of [`Block`](block.md) proxies.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Center position.
  - `radius` (`int`) — Cubic radius in blocks.
- **Returns:** `list[`[`Block`](block.md)`]`

```python
for block in world.blocks_near(player.location, 3):
    if block.type.name == "DIAMOND_ORE":
        await player.send_message("Diamond nearby!")
```

---

## Dimension

The `Dimension` type represents a world's dimension. It's available as a property on `World` objects.

### Properties

#### name

- **Type:** `str`

The dimension name (e.g. `"OVERWORLD"`, `"THE_NETHER"`, `"THE_END"`).

```python
world = player.world
dim = world.dimension
print(dim.name)  # "OVERWORLD"
```

---

## WorldTime Class

The `WorldTime` class represents a Minecraft time of day (0–24000 ticks) with utilities for conversion and comparison.

### Constructor

```python
WorldTime(ticks: int)
```

Create a `WorldTime` from a tick value. Automatically wraps to 0–24000.

### Class Methods

#### from_hours

```python
WorldTime.from_hours(hours: float) -> WorldTime
```

Create from a 24-hour clock value. `6.0` = dawn (tick 0), `12.0` = noon (tick 6000).

```python
noon = WorldTime.from_hours(12.0)   # WorldTime(ticks=6000)
midnight = WorldTime.from_hours(0)  # WorldTime(ticks=18000)
```

### Constants

| Constant | Ticks | Real-world equivalent |
| -------- | ----- | -------------------- |
| `WorldTime.DAWN` | 0 | 6:00 AM |
| `WorldTime.NOON` | 6000 | 12:00 PM |
| `WorldTime.DUSK` | 12000 | 6:00 PM |
| `WorldTime.MIDNIGHT` | 18000 | 12:00 AM |

### Properties

#### ticks

- **Type:** `int`

The raw tick value (0–24000).

#### hours

- **Type:** `float`

The time as a 24-hour clock value (0.0–24.0).

#### is_day

- **Type:** `bool`

`True` when ticks are in the 0–12000 range (daytime).

#### is_night

- **Type:** `bool`

`True` when ticks are 12000+ (nighttime).

### Example

```python
from bridge import WorldTime, World, server

world = World(name="world")

# Check time of day
t = world.world_time
if t.is_night:
    await server.broadcast("It's dark outside!")

# Schedule events at specific times
@world.at_time(WorldTime.NOON)
async def noon_event(w):
    await server.broadcast("The sun is at its peak!")

@world.at_time(WorldTime.MIDNIGHT)
async def midnight_event(w):
    await server.broadcast("Beware the creatures of the night!")
```
