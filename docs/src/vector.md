---
title: Vector
subtitle: 3D direction and velocity
---

# Vector

A `Vector` is a simple 3D coordinate used for velocities, offsets, and directional calculations. Unlike [`Location`](location.md), a Vector has no world, yaw, or pitch.

---

## Constructor

```python
Vector(x=0.0, y=0.0, z=0.0)
```

Create a vector.

- **Parameters:**
  - `x` (`float`) — X component. Default 0.
  - `y` (`float`) — Y component. Default 0.
  - `z` (`float`) — Z component. Default 0.

```python
velocity = Vector(0, 1.5, 0)       # Straight up
direction = Vector(0.5, 0.2, -0.3) # Angled
```

---

## Attributes

### x

- **Type:** `float`

X component.

### y

- **Type:** `float`

Y component.

### z

- **Type:** `float`

Z component.

---

## Common Uses

### Setting entity velocity

```python
# Launch a player upward
await player.set_velocity(Vector(0, 2.0, 0))
```

### Spawning projectiles with velocity

```python
arrow = await world.spawn_projectile(
    player,
    "ARROW",
    velocity=Vector(0, 1, 0)
)
```

---

## Arithmetic Operators

Vector supports `+`, `-`, and `*` operators for easy vector math.

### Addition (`+`)

```python
result = Vector(1, 2, 3) + Vector(4, 5, 6)   # Vector(5, 7, 9)
result = Vector(1, 2, 3) + [4, 5, 6]          # Vector(5, 7, 9)
result = Vector(1, 2, 3) + (4, 5, 6)          # Vector(5, 7, 9)
```

Supports `Vector`, `list[3]`, and `tuple[3]` as the right operand.

### Subtraction (`-`)

```python
result = Vector(5, 7, 9) - Vector(1, 2, 3)    # Vector(4, 5, 6)
result = Vector(5, 7, 9) - [1, 2, 3]          # Vector(4, 5, 6)
```

### Multiplication (`*`)

```python
# Scalar multiplication
result = Vector(1, 2, 3) * 2      # Vector(2, 4, 6)
result = 2 * Vector(1, 2, 3)      # Vector(2, 4, 6)

# Component-wise multiplication
result = Vector(1, 2, 3) * Vector(4, 5, 6)  # Vector(4, 10, 18)
result = Vector(1, 2, 3) * [4, 5, 6]        # Vector(4, 10, 18)
```

Supports `int`, `float`, `Vector`, `list[3]`, and `tuple[3]`. Scalar multiplication works in both directions (`scalar * vec` and `vec * scalar`).

---

## Common Uses

### Setting entity velocity

```python
# Launch a player upward
await player.set_velocity(Vector(0, 2.0, 0))
```

### Spawning projectiles with velocity

```python
# Shoot a fireball in the player's look direction
direction = player.look_direction * 2
arrow = await world.spawn_projectile(player, "ARROW", velocity=direction)
```

### As position tuples

Many methods accept `Vector | tuple[int,int,int]` interchangeably:

```python
# Both are equivalent
await world.fill(Vector(0, 60, 0), Vector(10, 65, 10), "STONE")
await world.fill((0, 60, 0), (10, 65, 10), "STONE")
```

### Player spawn offset

```python
await world.spawn_at_player(player, "ZOMBIE", offset=Vector(3, 0, 0))
```
