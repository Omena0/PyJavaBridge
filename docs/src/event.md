---
title: Event
subtitle: Event proxy and event type mapping
---

# Event

The `Event` class is the proxy object passed to your `@event` handlers. It exposes fields relevant to the specific Bukkit event that fired. Fields that don't apply to the current event type are `None`.

---

## Attributes

### player

- **Type:** [`Player`](player.md) | `None`

The player involved in the event. Available for all player-related events (`player_join`, `player_chat`, `player_interact`, etc.).

```python
@event
async def player_join(e):
    await e.player.send_message(f"Welcome, {e.player.name}!")
```

### entity

- **Type:** [`Entity`](entity.md) | `None`

The entity involved in the event. Available for entity events (`entity_damage`, `entity_death`, etc.).

### block

- **Type:** [`Block`](block.md) | `None`

The block involved in the event. Available for block events (`block_break`, `block_place`, etc.).

### world

- **Type:** [`World`](world.md) | `None`

The world where the event occurred. If the event doesn't directly provide a world, it is automatically derived from the event's `location`, `entity`, or `player` — so `event.world` works reliably for most events.

### location

- **Type:** [`Location`](location.md) | `None`

The location relevant to the event. If the event doesn't directly provide a location, it is derived from the event's `entity` or `player`.

### item

- **Type:** [`Item`](item.md) | `None`

The item involved in the event. Available for interact events, inventory events, etc.

### inventory

- **Type:** [`Inventory`](inventory.md) | `None`

The inventory involved in the event. Available for `inventory_click`, `inventory_close`, etc.

### chunk

- **Type:** [`Chunk`](chunk.md) | `None`

The chunk involved in the event.

### slot

- **Type:** `int`

The inventory slot index for `inventory_click` events.

### damager

- **Type:** [`Entity`](entity.md) | [`Block`](block.md) | `None`

The source of damage for `entity_damage` events. Can be an entity (attacker, projectile) or a block (cactus, lava).

### damage

- **Type:** `float`

The raw damage amount for `entity_damage` events (before armor/enchantment modifiers).

### final_damage

- **Type:** `float`

The final damage after all modifiers for `entity_damage` events.

### damage_cause

- **Type:** `str | None`

The [DamageCause](https://hub.spigotmc.org/javadocs/spigot/org/bukkit/event/entity/EntityDamageEvent.DamageCause.html) for damage events (e.g. `"ENTITY_ATTACK"`, `"FALL"`, `"FIRE"`).

### action

- **Type:** `str | None`

The action for interact events (e.g. `"RIGHT_CLICK_BLOCK"`, `"LEFT_CLICK_AIR"`). Available on `player_interact`.

### hand

- **Type:** `str | None`

Which hand was used (`"HAND"` or `"OFF_HAND"`). Available on `player_interact` and similar events.

### cause

- **Type:** `str | None`

A general cause string for events that have one (e.g. death cause, ignite cause).

### reason

- **Type:** `str | None`

The reason string for events like `player_kick`.

### message

- **Type:** `str | None`

The chat message for `player_chat`, join/quit message for `player_join`/`player_quit`, or death message for `entity_death`.

### velocity

- **Type:** [`Vector`](vector.md) | `None`

The velocity involved in the event (e.g. for projectile launch events).

### from_location / to_location

- **Type:** [`Location`](location.md) | `None`

For movement events (`player_move`, `player_teleport`): the start (`from`) and end (`to`) locations.

### new_slot

- **Type:** `int | None`

The new hotbar slot for `player_item_held` events (0–8).

### previous_slot

- **Type:** `int | None`

The previous hotbar slot for `player_item_held` events (0–8).

### amount

- **Type:** `int | None`

The amount for events that involve a quantity (e.g. experience gain).

---

## Methods

### cancel

```python
await event.cancel()
```

Cancel the event, preventing its default action. Only works on cancellable events.

- **Returns:** `Awaitable[None]`

```python
@event
async def block_break(e):
    if e.block.type.name == "BEDROCK":
        await e.cancel()
        await e.player.send_message("You can't break bedrock!")
```

---

## Damage Override

For `entity_damage` events, returning a number from the handler overrides the final damage:

```python
@event
async def entity_damage(e):
    if e.damage_cause == "FALL":
        return 0  # Cancel all fall damage
    if e.player:
        return e.damage * 0.5  # Half damage for players
```

---

## Chat Override

For `player_chat` events, returning a string cancels the original message and broadcasts your string instead:

```python
@event
async def player_chat(e):
    return f"[VIP] {e.player.name}: {e.message}"
```

Returning `None` (or not returning) leaves the chat message unchanged.

---

## Respawn Location Override

For `player_respawn` events, returning a `Location` overrides where the player respawns:

```python
@event
async def player_respawn(e):
    return Location(0, 100, 0, e.player.world)  # Custom spawn point
```

---

## Event Type Mapping

Events are resolved from handler function names: `snake_case` → `PascalCase` + `Event`.

> **Tip:** Event fields are accessed in `snake_case`. The bridge automatically converts to the matching Java getter (`getNewSlot`, `getPreviousSlot`, `isFlying`, etc.), so you can use natural Python naming: `event.new_slot`, `event.previous_slot`, `event.action`.

| Function name | Bukkit event |
| ------------- | ------------ |
| `player_join` | `PlayerJoinEvent` |
| `player_quit` | `PlayerQuitEvent` |
| `player_chat` | `AsyncPlayerChatEvent` |
| `player_move` | `PlayerMoveEvent` |
| `player_interact` | `PlayerInteractEvent` |
| `block_break` | `BlockBreakEvent` |
| `block_place` | `BlockPlaceEvent` |
| `entity_damage` | `EntityDamageEvent` / `EntityDamageByEntityEvent` |
| `entity_death` | `EntityDeathEvent` |
| `inventory_click` | `InventoryClickEvent` |
| `inventory_close` | `InventoryCloseEvent` |
| `world_load` | `WorldLoadEvent` |
| `weather_change` | `WeatherChangeEvent` |

### Special cases

- **`server_boot`** maps to `ServerLoadEvent`
- **`block_explode`** is dispatched for both `BlockExplodeEvent` and `EntityExplodeEvent`

### Supported packages

The bridge discovers events from all standard Bukkit/Paper event packages:

- `org.bukkit.event.player.*`
- `org.bukkit.event.block.*`
- `org.bukkit.event.entity.*`
- `org.bukkit.event.inventory.*`
- `org.bukkit.event.server.*`
- `org.bukkit.event.world.*`
- `org.bukkit.event.weather.*`
- `org.bukkit.event.vehicle.*`
- `org.bukkit.event.hanging.*`
- `org.bukkit.event.enchantment.*`
- `org.bukkit.event.*`
- `io.papermc.paper.event.player.*`
- `io.papermc.paper.event.block.*`
- `io.papermc.paper.event.entity.*`
- `io.papermc.paper.event.world.*`
- `io.papermc.paper.event.*`
