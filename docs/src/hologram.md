---
title: Hologram
subtitle: Floating text displays
---

# Hologram

A `Hologram` is a floating text display entity. It supports multiple lines, configurable billboard mode, and can be moved or removed.

Uses display entities (1.19.4+) internally for crisp rendering.

---

## Constructor

```python
Hologram(location, *lines, billboard="CENTER")
```

Create and spawn a hologram.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Where to spawn the hologram.
  - `*lines` (`str`) — Text lines to display. Supports `§` color codes.
  - `billboard` (`str`) — Billboard mode. Default `"CENTER"`.

| Billboard | Description |
|-----------|-------------|
| `"CENTER"` | Always faces the player (default) |
| `"FIXED"` | Fixed orientation |
| `"HORIZONTAL"` | Only rotates horizontally |
| `"VERTICAL"` | Only rotates vertically |

```python
holo = Hologram(
    Location(100, 70, 200, "world"),
    "§6§lWelcome!",
    "§7to our server",
    billboard="CENTER"
)
```

---

## Attributes

### billboard

- **Type:** `str`

Current billboard mode.

### see_through

- **Type:** `bool`

Whether the text can be seen through blocks. Default `False`.

### shadowed

- **Type:** `bool`

Whether the text has a shadow. Default `True` for most setups.

### alignment

- **Type:** `str`

Text alignment: `"CENTER"`, `"LEFT"`, or `"RIGHT"`.

### line_width

- **Type:** `int`

Maximum line width in pixels before wrapping.

### background

- **Type:** `int | None`

Background color as an ARGB integer, or `None` for default.

---

## Line Access

Hologram supports index-based access for lines using `[]` notation.

### Set a line

```python
holo[index] = text
```

### Get a line

```python
text = holo[index]
```

### Delete a line

```python
del holo[index]
```

### Get line count

```python
count = len(holo)
```

### Append a line

```python
holo.append(text)
```

Add a new line to the bottom.

- **Parameters:**
  - `text` (`str`) — Line text.

---

## Methods

### teleport

```python
holo.teleport(location)
```

Move the hologram to a new location. This is synchronous.

- **Parameters:**
  - `location` ([`Location`](location.md)) — New position.

```python
holo.teleport(Location(100, 75, 200, "world"))
```

### remove

```python
holo.remove()
```

Despawn and destroy the hologram. This is synchronous.

---

## Example: Welcome hologram

```python
from bridge import *

spawn = Location(0, 65, 0, "world")
welcome = Hologram(
    spawn,
    "§6§l✦ My Server ✦",
    "",
    "§fType §a/help §fto get started",
    "§7play.example.com"
)
```

## Example: Dynamic leaderboard

```python
from bridge import *

lb_loc = Location(50, 70, 50, "world")
leaderboard = Hologram(lb_loc, "§e§lTop Kills", "§7Loading...")

kills = {}

@event
async def entity_death(e: Event):
    d = e.damager
    if d and hasattr(d, 'name'):
        kills[d.name] = kills.get(d.name, 0) + 1
        # Update hologram
        sorted_kills = sorted(kills.items(), key=lambda x: -x[1])[:5]
        leaderboard[0] = "§e§l⚔ Top Kills ⚔"
        for i, (name, count) in enumerate(sorted_kills):
            leaderboard[i + 1] = f"§f#{i+1} §a{name} §7- §e{count}"
```

## Example: Per-player welcome

```python
from bridge import *

holograms = {}

@event
async def player_join(e: Event):
    p = e.player
    loc = p.location.add(0, 2.5, 0)
    holograms[p.name] = Hologram(loc, f"§aWelcome, {p.name}!")

@event
async def player_quit(e: Event):
    h = holograms.pop(e.player.name, None)
    if h:
        h.remove()
```
