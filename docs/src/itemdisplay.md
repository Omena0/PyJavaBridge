---
title: ItemDisplay
subtitle: Item display entity
---

# ItemDisplay

An `ItemDisplay` renders an item as a display entity in the world (1.19.4+). Unlike dropped items, display entities don't have physics, don't despawn, and can use billboard modes.

---

## Constructor

```python
ItemDisplay(location, item, billboard="FIXED")
```

Create and spawn an item display entity.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Spawn position.
  - `item` ([`Item`](item.md) `| str`) — The item to display. If a string, interprets as a material name.
  - `billboard` (`str`) — Billboard mode. Default `"FIXED"`.

| Billboard | Description |
|-----------|-------------|
| `"FIXED"` | No rotation (default) |
| `"CENTER"` | Always faces the player |
| `"HORIZONTAL"` | Only rotates horizontally |
| `"VERTICAL"` | Only rotates vertically |

```python
display = ItemDisplay(
    Location(100, 70, 200, "world"),
    Item("DIAMOND_SWORD", name="§bExcalibur"),
    billboard="CENTER"
)
```

---

## Attributes

### billboard

- **Type:** `str`

Current billboard mode.

---

## Methods

### teleport

```python
display.teleport(location)
```

Move the display entity. This is synchronous.

- **Parameters:**
  - `location` ([`Location`](location.md)) — New position.

### remove

```python
display.remove()
```

Despawn and destroy the display entity. This is synchronous.

---

## Example: Floating reward indicator

```python
from bridge import *

@command("Show reward")
async def reward(player: Player, args: list[str]):
    loc = player.location.add(0, 2, 0)
    display = ItemDisplay(loc, "NETHER_STAR", billboard="CENTER")
    await player.send_message("§e⭐ Reward available above you!")
```
