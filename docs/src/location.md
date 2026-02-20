---
title: Location
subtitle: 3D position with world reference, yaw, and pitch
---

# Location

A `Location` represents a position in a world with rotation angles. It is used for teleportation, block lookups, spawning, and spatial calculations.

---

## Constructor

```python
Location(x=0.0, y=0.0, z=0.0, world=None, yaw=0.0, pitch=0.0)
```

Create a new location.

- **Parameters:**
  - `x` (`float`) — X coordinate. Default 0.
  - `y` (`float`) — Y coordinate. Default 0.
  - `z` (`float`) — Z coordinate. Default 0.
  - `world` ([`World`](world.md) `| str | None`) — World reference or name. Default `None`.
  - `yaw` (`float`) — Horizontal rotation in degrees. Default 0.
  - `pitch` (`float`) — Vertical rotation in degrees. Default 0. Negative = looking up.

```python
loc = Location(100, 64, -200, "world")
loc = Location(0, 64, 0, "world_nether", yaw=90, pitch=-45)
```

---

## Attributes

### x

- **Type:** `float`

X coordinate (East-West).

### y

- **Type:** `float`

Y coordinate (altitude).

### z

- **Type:** `float`

Z coordinate (North-South).

### world

- **Type:** [`World`](world.md)

The world this location is in.

### yaw

- **Type:** `float`

Horizontal rotation in degrees. 0 = South, 90 = West, 180 = North, 270 = East.

### pitch

- **Type:** `float`

Vertical rotation in degrees. 0 = level, -90 = straight up, 90 = straight down.

---

## Methods

### add

```python
new_loc = location.add(x, y, z)
```

Create a new location with the given offsets added. **This is synchronous** — no `await` needed.

- **Parameters:**
  - `x` (`float`) — X offset.
  - `y` (`float`) — Y offset.
  - `z` (`float`) — Z offset.
- **Returns:** [`Location`](#) — A new location (the original is not modified).

```python
above = player.location.add(0, 2, 0)
```

### clone

```python
copy = location.clone()
```

Create an independent copy of this location. **Synchronous.**

- **Returns:** [`Location`](#)

### distance

```python
d = location.distance(other)
```

Calculate the Euclidean distance to another location. **Synchronous.**

- **Parameters:**
  - `other` ([`Location`](#)) — The other location.
- **Returns:** `float`

```python
dist = player.location.distance(spawn_location)
if dist < 10:
    await player.send_message("You're near spawn!")
```

### distance_squared

```python
d2 = location.distance_squared(other)
```

Calculate the squared distance to another location. **Synchronous.** Faster than `distance()` when you only need to compare distances (avoids square root).

- **Parameters:**
  - `other` ([`Location`](#)) — The other location.
- **Returns:** `float`

```python
# More efficient than: if loc.distance(other) < 10
if loc.distance_squared(other) < 100:
    ...
```
