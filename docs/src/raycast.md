---
title: Raycast
subtitle: Ray tracing function
---

# raycast

The `raycast` function traces a ray through the world, detecting entities and blocks along the path. Useful for line-of-sight checks, targeting systems, and custom projectiles.

---

## Function Signature

```python
result = await raycast(
    world,
    start,
    direction,
    max_distance=64.0,
    ray_size=0.2,
    include_entities=True,
    include_blocks=True,
    ignore_passable=True
)
```

- **Parameters:**
  - `world` ([`World`](world.md) `| str`) — The world to raycast in.
  - `start` ([`Vector`](vector.md) `| tuple[float,float,float]`) — Ray origin (x, y, z).
  - `direction` (`tuple[float, float]`) — Direction as `(yaw, pitch)` in degrees.
  - `max_distance` (`float`) — Maximum ray distance in blocks. Default 64.0.
  - `ray_size` (`float`) — Ray thickness for entity detection. Default 0.2.
  - `include_entities` (`bool`) — Whether to detect entities. Default `True`.
  - `include_blocks` (`bool`) — Whether to detect blocks. Default `True`.
  - `ignore_passable` (`bool`) — Whether to ignore passable blocks (grass, flowers, etc.). Default `True`.
- **Returns:** `Awaitable[`[`RaycastResult`](#raycastresult)` | None]` — Hit result, or `None` if nothing was hit.

```python
from bridge import *

# Raycast from a player's eye position in their look direction
result = await raycast(
    player.world,
    (player.location.x, player.location.y + 1.62, player.location.z),
    (player.location.yaw, player.location.pitch),
    max_distance=50.0
)

if result:
    if result.entity:
        await player.send_message(f"§aLooking at: {result.entity.type.name}")
    elif result.block:
        await player.send_message(f"§aLooking at block: {result.block.type.name}")
```

---

# RaycastResult

Returned by `raycast()` when a hit occurs.

## Attributes

### x

- **Type:** `float`

X coordinate of the hit point.

### y

- **Type:** `float`

Y coordinate of the hit point.

### z

- **Type:** `float`

Z coordinate of the hit point.

### entity

- **Type:** [`Entity`](entity.md) `| None`

The entity that was hit, or `None` if a block was hit.

### block

- **Type:** [`Block`](block.md) `| None`

The block that was hit, or `None` if an entity was hit.

### start_x

- **Type:** `float`

X coordinate of the ray origin.

### start_y

- **Type:** `float`

Y coordinate of the ray origin.

### start_z

- **Type:** `float`

Z coordinate of the ray origin.

### yaw

- **Type:** `float`

Yaw direction of the ray.

### pitch

- **Type:** `float`

Pitch direction of the ray.

### distance

- **Type:** `float`

Distance from the ray origin to the hit point.

### hit_face

- **Type:** `str | None`

The face of the block that was hit (e.g. `"NORTH"`, `"UP"`), or `None` for entity hits.

---

## Example: Target selector

```python
from bridge import *

@command("Smite what you're looking at")
async def smite(player: Player, args: list[str]):
    loc = player.location
    result = await raycast(
        player.world,
        (loc.x, loc.y + 1.62, loc.z),
        (loc.yaw, loc.pitch),
        max_distance=100.0,
        include_entities=True,
        include_blocks=False
    )

    if result and result.entity:
        hit_loc = Location(result.x, result.y, result.z, player.world.name)
        await player.world.strike_lightning(hit_loc)
        await player.send_message(f"§e⚡ Smited {result.entity.type.name}!")
    else:
        await player.send_message("§cNo entity in sight!")
```

## Example: Build tool

```python
from bridge import *

@command("Place a block where you look")
async def place(player: Player, args: list[str]):
    material = args[0] if args else "STONE"
    loc = player.location
    result = await raycast(
        player.world,
        (loc.x, loc.y + 1.62, loc.z),
        (loc.yaw, loc.pitch),
        max_distance=50.0,
        include_entities=False,
        include_blocks=True
    )

    if result and result.block:
        # Place block on the hit face
        bx, by, bz = int(result.x), int(result.y), int(result.z)
        if result.hit_face == "UP": by += 1
        elif result.hit_face == "DOWN": by -= 1
        elif result.hit_face == "NORTH": bz -= 1
        elif result.hit_face == "SOUTH": bz += 1
        elif result.hit_face == "EAST": bx += 1
        elif result.hit_face == "WEST": bx -= 1

        await player.world.set_block(bx, by, bz, material)
        await player.send_message(f"§aPlaced {material}!")
    else:
        await player.send_message("§cNo block in range!")
```

## Example: Line of sight check

```python
from bridge import *

async def can_see(player, target_location):
    """Check if a player has line of sight to a location."""
    loc = player.location
    # Calculate direction (simplified — yaw/pitch calculation)
    result = await raycast(
        player.world,
        (loc.x, loc.y + 1.62, loc.z),
        (loc.yaw, loc.pitch),
        max_distance=64.0,
        include_entities=False,
        include_blocks=True,
        ignore_passable=True
    )

    if result is None:
        return True  # Nothing blocking
    return result.distance > loc.distance(target_location)
```
