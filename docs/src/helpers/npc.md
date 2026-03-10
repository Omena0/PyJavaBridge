---
title: NPC
subtitle: Fake players with click handlers, dialog, and movement paths
---

# NPC

`NPC` spawns a mob (default: villager) with AI disabled and provides click handlers, dialog trees, and pathfinding movement.

---

## Spawning

```python
npc = await NPC.spawn(location, entity_type="VILLAGER", name="Guard")
```

- **Parameters:**
  - `location` ([`Location`](location.md)) — Where to spawn the NPC.
  - `entity_type` ([`EntityType`](enums.md) `| str`) — Mob type. Default `"VILLAGER"`.
  - `name` (`str | None`) — Display name shown above the NPC.
  - `**kwargs` — Extra spawn options passed to `Entity.spawn`.
- **Returns:** `Awaitable[NPC]`

```python
guard = await NPC.spawn(Location(100, 64, 200, "world"), name="§6Town Guard")
shopkeeper = await NPC.spawn(player.location, entity_type="VILLAGER", name="§aShop")
```

---

## Properties

### entity

```python
npc.entity  # → Entity
```

The underlying [`Entity`](entity.md) instance.

### uuid

```python
npc.uuid  # → str | None
```

The entity's UUID string.

### location

```python
npc.location  # → Location
```

The NPC's current location.

---

## Click Handlers

### on_click

```python
@npc.on_click
def handler(player, npc):
    ...
```

Register a handler called when a player left-clicks the NPC. Handler receives `(Player, NPC)`.

### on_right_click

```python
@npc.on_right_click
def handler(player, npc):
    ...
```

Register a handler called when a player right-clicks the NPC. Handler receives `(Player, NPC)`.

```python
guard = await NPC.spawn(loc, name="Guard")

@guard.on_right_click
async def greet(player, npc):
    await player.send_message("§eHalt! State your business.")
```

---

## Dialog Trees

### dialog

```python
npc.dialog(messages, loop=False)
```

Set a sequence of messages shown one per right-click. Each click advances to the next message.

- **Parameters:**
  - `messages` (`list[str]`) — Messages to show in order.
  - `loop` (`bool`) — If `True`, restart from the beginning after the last message. Default `False` (stays on last message).

```python
npc.dialog([
    "§eWelcome, traveler!",
    "§eThe dungeon lies to the north.",
    "§eBeware of the dragon!",
    "§7(The guard nods silently.)"
], loop=False)
```

---

## Movement

### move_to

```python
await npc.move_to(location, speed=1.0)
```

Move the NPC to a location using pathfinding. Temporarily enables AI.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Destination.
  - `speed` (`float`) — Speed multiplier. Default `1.0`.

### follow_path

```python
await npc.follow_path(waypoints, loop=False, speed=1.0, delay=0.5)
```

Make the NPC walk through a list of waypoints.

- **Parameters:**
  - `waypoints` (`list[`[`Location`](location.md)`]`) — Locations to visit in order.
  - `loop` (`bool`) — If `True`, repeat the path endlessly.
  - `speed` (`float`) — Speed multiplier.
  - `delay` (`float`) — Seconds between each waypoint. Default `0.5`.

### stop_path

```python
npc.stop_path()
```

Stop the current movement and disable AI.

```python
path = [Location(0, 64, 0, "world"), Location(10, 64, 0, "world"), Location(10, 64, 10, "world")]
await npc.follow_path(path, loop=True, speed=0.8)

# Later...
npc.stop_path()
```

---

## Removing

### remove

```python
await npc.remove()
```

Remove the NPC entity from the world and unregister all handlers.
