---
title: BlockDisplay
subtitle: Block display entity
---

# BlockDisplay

A `BlockDisplay` renders a block as a display entity in the world (1.19.4+). Unlike placed blocks, display entities don't have collision and can be positioned at any coordinates.

---

## Constructor

```python
BlockDisplay(location, block_type, billboard="FIXED")
```

Create and spawn a block display entity.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Spawn position.
  - `block_type` (`str`) — Block material name (e.g. `"DIAMOND_BLOCK"`, `"STONE"`).
  - `billboard` (`str`) — Billboard mode. Default `"FIXED"`.

| Billboard | Description |
|-----------|-------------|
| `"FIXED"` | No rotation (default for blocks) |
| `"CENTER"` | Always faces the player |
| `"HORIZONTAL"` | Only rotates horizontally |
| `"VERTICAL"` | Only rotates vertically |

```python
display = BlockDisplay(
    Location(100, 70, 200, "world"),
    "DIAMOND_BLOCK",
    billboard="FIXED"
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

## Example: Floating block marker

```python
from bridge import *

@command("Place a marker")
async def marker(player: Player, args: list[str]):
    loc = player.location.add(0, 3, 0)
    block = BlockDisplay(loc, "BEACON", billboard="FIXED")
    await player.send_message("§aMarker placed above you!")
```
