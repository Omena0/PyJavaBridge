---
title: Region [ext]
subtitle: Cuboid region with enter/exit events
---

# Region [ext]

`Region` defines a cuboid area in a world and fires callbacks when players enter or exit.

```python
from bridge.extensions import Region
```

---

## Constructor

```python
Region(name, world, x1, y1, z1, x2, y2, z2)
```

- **Parameters:**
  - `name` (`str`) — Identifier.
  - `world` (`World | str`) — World object or name.
  - `x1, y1, z1` (`float`) — First corner.
  - `x2, y2, z2` (`float`) — Second corner.

Coordinates are automatically sorted so min/max are correct.

```python
spawn = Region("spawn", "world", -50, 0, -50, 50, 256, 50)
```

---

## Properties

### world

- **Type:** `str`

World name.

---

## Methods

### contains(location) → bool

Check if a location is inside this region.

### is_inside(player) → bool

Whether the player is currently tracked as inside.

### remove()

Remove this region from the global tracker.

---

## Decorators

### @region.on_enter

```python
@spawn.on_enter
def entered(player, region):
    player.send_message("Welcome to spawn!")
```

### @region.on_exit

```python
@spawn.on_exit
def left(player, region):
    player.send_message("Leaving spawn area")
```
