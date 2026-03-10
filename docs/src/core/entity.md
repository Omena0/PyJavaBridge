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

### inventory

- **Type:** [`Inventory`](inventory.md)

The entity's inventory / equipment. For mobs, this is their equipment slots.

### held_item

- **Type:** [`Item`](item.md)

The item in the entity's main hand equipment slot.

### yaw

- **Type:** `float`

The entity's horizontal rotation in degrees (from its location).

### pitch

- **Type:** `float`

The entity's vertical rotation in degrees (from its location).

### look_direction

- **Type:** [`Vector`](vector.md)

Normalized direction vector computed from the entity's yaw and pitch. Useful for spawning projectiles or offsetting positions in front of the entity.

```python
# Spawn a fireball 2 blocks ahead of the player
direction = player.look_direction * 2
fireball = await Entity.spawn("FIREBALL", player.location + direction)
await fireball.set_velocity(direction)
```

### velocity

- **Type:** [`Vector`](vector.md)
- **Settable:** `entity.velocity = Vector(0, 1, 0)`

The entity's current velocity vector.

### equipment

- **Type:** `Inventory | None`

The entity's equipment (armor slots and held items). For mobs this is their equipment; for players use `inventory` instead.

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
- **Settable:** `entity.fire_ticks = 100`

Remaining fire ticks. 0 means not on fire. Each tick at 20 TPS, so 100 = 5 seconds of fire.

### passengers

- **Type:** `list[`[`Entity`](#)`]`

Entities riding on top of this entity.

### custom_name

- **Type:** `str | None`
- **Settable:** `entity.custom_name = "§cBoss"`
- **Deletable:** `del entity.custom_name` (clears name)

The entity's custom name, or `None` if not set.

### custom_name_visible

- **Type:** `bool`
- **Settable:** `entity.custom_name_visible = True`

Whether the custom name tag is visible through walls and at distance.

### is_projectile

- **Type:** `bool`

Whether this entity is a projectile (arrow, snowball, trident, etc.).

### shooter

- **Type:** [`Entity`](#) | [`Player`](player.md) | [`Block`](block.md) | `None`

For projectiles, the entity or block that launched it. `None` for non-projectiles.

### is_tamed

- **Type:** `bool`

Whether this entity is a tameable animal that has been tamed (wolf, cat, horse, etc.).

### owner

- **Type:** [`Player`](player.md) | `None`

The player who caused/owns this entity. Works for:

- **Tamed animals** — the player who tamed them
- **Projectiles** — the player who shot them (same as `shooter` when shooter is a player)
- **TNT** — the player who ignited it
- **Any entity** with a traceable cause

Returns `None` if the owner is offline or unknown.

### owner_uuid

- **Type:** `str | None`

UUID of the owning player, even if they're offline.

### owner_name

- **Type:** `str | None`

Name of the owning player, if known.

### source

- **Type:** [`Entity`](#) | [`Player`](player.md) | `None`

The entity that created this entity. For example, the player who lit a TNT block, or the witch that threw a potion.

```python
@event
async def entity_damage_by_entity(e):
    # Track who's responsible for projectile kills
    damager = e.damager
    if damager.is_projectile and damager.owner:
        owner = damager.owner
        await owner.send_message(f"You hit {e.entity.type}!")

    # Check if a tamed wolf attacked something
    if damager.is_tamed:
        await damager.owner.send_message(f"Your {damager.type} attacked {e.entity.type}")
```

### gravity

- **Type:** `bool`
- **Settable:** `entity.gravity = False`

Whether the entity is affected by gravity.

### glowing

- **Type:** `bool`
- **Settable:** `entity.glowing = True`

Whether the entity has the glowing outline effect.

### invisible

- **Type:** `bool`
- **Settable:** `entity.invisible = True`

Whether the entity is invisible.

### invulnerable

- **Type:** `bool`
- **Settable:** `entity.invulnerable = True`

Whether the entity is invulnerable to damage.

### silent

- **Type:** `bool`
- **Settable:** `entity.silent = True`

Whether the entity makes sounds.

### persistent

- **Type:** `bool`
- **Settable:** `entity.persistent = True`

Whether the entity persists through chunk unloads. Prevents despawning.

### collidable

- **Type:** `bool`
- **Settable:** `entity.collidable = False`

Whether other entities can collide with this entity.

### portal_cooldown

- **Type:** `int`
- **Settable:** `entity.portal_cooldown = 100`

The entity's portal cooldown in ticks.

### max_fire_ticks

- **Type:** `int`

The maximum fire ticks the entity can have (read-only).

### freeze_ticks

- **Type:** `int`
- **Settable:** `entity.freeze_ticks = 140`

The entity's powdered-snow freeze ticks.

### height

- **Type:** `float`

The entity's bounding box height.

### width

- **Type:** `float`

The entity's bounding box width.

### bounding_box

- **Type:** `dict`

The entity's axis-aligned bounding box as a dictionary.

### metadata

- **Type:** `dict`

Transient Python-side key/value storage attached to this entity. Persists across event handlers within the same session but is not saved to disk.

```python
entity.metadata["spawned_by"] = player.name
```

### `__bool__`

Entity implements `__bool__` returning `is_valid`, so you can use:

```python
if entity:  # equivalent to entity.is_valid
    await entity.remove()
```

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

Set the entity's custom name tag. You can also use property syntax: `entity.custom_name = "§cBoss Zombie"`.

- **Parameters:**
  - `name` (`str`) — The name to display. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

```python
await zombie.set_custom_name("§cBoss Zombie")
# or
zombie.custom_name = "§cBoss Zombie"
del zombie.custom_name  # clears name
```

### set_custom_name_visible

```python
await entity.set_custom_name_visible(value)
```

Show or hide the custom name tag. When `True`, the name is visible through walls and at a distance. You can also use property syntax: `entity.custom_name_visible = True`.

- **Parameters:**
  - `value` (`bool`) — Whether the name should be visible.
- **Returns:** `Awaitable[None]`

### damage

```python
await entity.damage(amount)
```

Deal damage to the entity.

- **Parameters:**
  - `amount` (`float`) — Damage amount in half-hearts (1.0 = half a heart).
- **Returns:** `Awaitable[None]`

```python
await zombie.damage(10.0)  # 5 hearts of damage
```

---

## Mob AI

These methods only work on Mob entities (zombies, skeletons, etc). They will fail silently on non-mob entities like dropped items or projectiles.

### target

```python
target = entity.target
```

Get the mob's current attack target.

- **Type:** [`Entity`](#) `| None`
- **Settable:** `entity.target = player`
- **Deletable:** `del entity.target` (clears target)

### set_target

```python
await entity.set_target(target)
```

Set the mob's attack target. Pass `None` to clear. You can also use property syntax.

- **Parameters:**
  - `target` ([`Entity`](#) `| None`) — The entity to target.
- **Returns:** `Awaitable[None]`

```python
await zombie.set_target(player)
# or
zombie.target = player
del zombie.target  # clear target
```

### is_aware

```python
aware = entity.is_aware
```

Check if the mob has AI awareness (responds to environment, pathfinds, etc).

- **Type:** `bool`
- **Settable:** `entity.is_aware = False`

### set_aware

```python
await entity.set_aware(aware)
```

Enable or disable AI awareness. When disabled, the mob won't move or react. You can also use property syntax: `entity.is_aware = False`.

- **Parameters:**
  - `aware` (`bool`) — Whether AI should be active.
- **Returns:** `Awaitable[None]`

```python
await zombie.set_aware(False)  # freeze the mob
```

### pathfind_to

```python
result = entity.pathfind_to(location, speed=1.0)
```

Make the mob pathfind to a location using Paper's Pathfinder API.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Destination.
  - `speed` (`float`) — Movement speed multiplier. Default `1.0`.
- **Returns:** `bool` — `True` if a path was found.

```python
found = zombie.pathfind_to(player.location, speed=1.5)
```

### stop_pathfinding

```python
await entity.stop_pathfinding()
```

Stop the mob's current pathfinding. The mob will stand still.

- **Returns:** `Awaitable[None]`

### has_line_of_sight

```python
can_see = entity.has_line_of_sight(other)
```

Check if this mob has line of sight to another entity.

- **Parameters:**
  - `other` ([`Entity`](#)) — The entity to check visibility for.
- **Returns:** `bool`

```python
if zombie.has_line_of_sight(player):
    await zombie.set_target(player)
```

### look_at

```python
await entity.look_at(location)
```

Make the mob face a location.

- **Parameters:**
  - `location` ([`Location`](location.md)) — The location to look at.
- **Returns:** `Awaitable[None]`

```python
await zombie.look_at(player.location)
```

---

## AI Goals

These methods interact with Paper's MobGoals API to inspect and modify mob AI goals.

### goal_types

```python
goals = entity.goal_types
```

Get a list of all active AI goal type keys on the mob.

- **Type:** `list`

### remove_goal

```python
removed = entity.remove_goal(goal_key)
```

Remove a specific AI goal by its key. **Synchronous.**

- **Parameters:**
  - `goal_key` (`str`) — The goal type key to remove.
- **Returns:** `bool`

### remove_all_goals

```python
await entity.remove_all_goals()
```

Remove all AI goals from the mob.

- **Returns:** `Awaitable[None]`

```python
# Create a "dummy" mob that won't do anything
await zombie.remove_all_goals()
await zombie.set_aware(False)
```

---

## Tags

Entities support Python-side tags — string labels shared across all instances that reference the same entity UUID. Tags are stored in memory (not persisted to disk) and are useful for marking entities across different event handlers.

### add_tag

```python
entity.add_tag(tag)
```

Add a tag to this entity. **Synchronous.**

- **Parameters:**
  - `tag` (`str`) — The tag string.

```python
zombie.add_tag("boss")
```

### remove_tag

```python
entity.remove_tag(tag)
```

Remove a tag. **Synchronous.**

- **Parameters:**
  - `tag` (`str`) — The tag to remove.

### tags

```python
all_tags = entity.tags
```

Get all tags on this entity.

- **Type:** `set[str]`

### is_tagged

```python
result = entity.is_tagged(tag)
```

Check if the entity has a specific tag. **Synchronous.**

- **Parameters:**
  - `tag` (`str`) — The tag to check.
- **Returns:** `bool`

```python
@event
async def entity_damage(e):
    if e.entity.is_tagged("boss"):
        await e.entity.set_custom_name(f"§c Boss HP: {e.entity.health}")
```

---

## Entity Subtypes

See [Entity subtypes](#entity-subtypes)
