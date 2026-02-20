---
title: Entity
subtitle: Base entity proxy
---

# Entity

`Entity` is the base class for all entities in the game — mobs, animals, projectiles, dropped items, etc. [`Player`](player.md) extends this class.

---

## Constructor

```python
Entity(uuid: str | None = None)
```

Resolve an existing entity by its UUID.

- **Parameters:**
  - `uuid` (`str | None`) — The entity's UUID string.

```python
entity = Entity("550e8400-e29b-41d4-a716-446655440000")
```

---

## Class Methods

### spawn

```python
entity = await Entity.spawn(entity_type, location, **kwargs)
```

Spawn a new entity at a location.

- **Parameters:**
  - `entity_type` ([`EntityType`](enums.md) `| str`) — The type of entity to spawn.
  - `location` ([`Location`](location.md)) — Where to spawn the entity.
  - `**kwargs` — Additional spawn options.
- **Returns:** `Awaitable[`[`Entity`](#)`]`

```python
zombie = await Entity.spawn(EntityType.ZOMBIE, player.location)
zombie = await Entity.spawn("ZOMBIE", Location(0, 64, 0, "world"))
```

---

## Attributes

### uuid

- **Type:** `str`

The entity's universally unique identifier.

### type

- **Type:** [`EntityType`](enums.md)

The entity type (e.g. `EntityType.ZOMBIE`, `EntityType.ARROW`).

### location

- **Type:** [`Location`](location.md)

The entity's current location. Re-fetched each access.

### world

- **Type:** [`World`](world.md)

The world the entity is in.

### velocity

- **Type:** [`Vector`](vector.md)

The entity's current velocity vector.

### is_dead

- **Type:** `bool`

Whether the entity is dead.

### is_alive

- **Type:** `bool`

Whether the entity is alive.

### is_valid

- **Type:** `bool`

Whether the entity handle is still valid. Becomes `False` when the entity is removed from the server. Always check this before interacting with an entity you've stored across ticks.

### fire_ticks

- **Type:** `int`

Remaining fire ticks. 0 means not on fire. Each tick at 20 TPS, so 100 = 5 seconds of fire.

### passengers

- **Type:** `list[`[`Entity`](#)`]`

Entities riding on top of this entity.

### custom_name

- **Type:** `any`

The entity's custom name, or `None` if not set.

### is_projectile

- **Type:** `bool`

Whether this entity is a projectile (arrow, snowball, trident, etc.).

### shooter

- **Type:** [`Entity`](#) | [`Player`](player.md) | [`Block`](block.md) | `None`

For projectiles, the entity or block that launched it. `None` for non-projectiles.

### is_tamed

- **Type:** `bool`

Whether this entity is a tameable animal that has been tamed.

### owner

- **Type:** [`Player`](player.md) | `None`

The player who owns this tamed entity, if the owner is online.

### owner_uuid

- **Type:** `str | None`

UUID of the taming player, even if they're offline.

### owner_name

- **Type:** `str | None`

Name of the taming player, if known.

### source

- **Type:** [`Entity`](#) | [`Player`](player.md) | `None`

The entity that created this entity. For example, the player who lit a TNT block, or the witch that threw a potion.

---

## Methods

### teleport

```python
await entity.teleport(location)
```

Teleport the entity to a new location.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Destination.
- **Returns:** `Awaitable[None]`

```python
await zombie.teleport(Location(0, 100, 0, "world"))
```

### remove

```python
await entity.remove()
```

Remove the entity from the world permanently.

- **Returns:** `Awaitable[None]`

### set_velocity

```python
await entity.set_velocity(vector)
```

Set the entity's velocity. Useful for launching entities, knockback effects, etc.

- **Parameters:**
  - `vector` ([`Vector`](vector.md)) — The velocity vector. Each component is in blocks/tick.
- **Returns:** `Awaitable[None]`

```python
# Launch entity upward
await entity.set_velocity(Vector(0, 1.5, 0))
```

### set_fire_ticks

```python
await entity.set_fire_ticks(ticks)
```

Set the entity on fire for a duration.

- **Parameters:**
  - `ticks` (`int`) — Duration in ticks (20 ticks = 1 second). Set to 0 to extinguish.
- **Returns:** `Awaitable[None]`

```python
await entity.set_fire_ticks(100)  # 5 seconds of fire
await entity.set_fire_ticks(0)    # Extinguish
```

### add_passenger

```python
success = await entity.add_passenger(entity)
```

Make another entity ride on top of this one.

- **Parameters:**
  - `entity` ([`Entity`](#)) — The entity to add as a passenger.
- **Returns:** `Awaitable[bool]` — `True` if the passenger was added successfully.

### remove_passenger

```python
success = await entity.remove_passenger(entity)
```

Remove a riding entity.

- **Parameters:**
  - `entity` ([`Entity`](#)) — The passenger to remove.
- **Returns:** `Awaitable[bool]`

### set_custom_name

```python
await entity.set_custom_name(name)
```

Set the entity's custom name tag.

- **Parameters:**
  - `name` (`str`) — The name to display. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

```python
await zombie.set_custom_name("§cBoss Zombie")
```

### set_custom_name_visible

```python
await entity.set_custom_name_visible(value)
```

Show or hide the custom name tag. When `True`, the name is visible through walls and at a distance.

- **Parameters:**
  - `value` (`bool`) — Whether the name should be visible.
- **Returns:** `Awaitable[None]`
