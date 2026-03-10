---
title: Sidebar
subtitle: Simple sidebar helper
---

# Sidebar

`Sidebar` is a high-level helper that wraps [`Scoreboard`](scoreboard.md) and [`Objective`](objective.md) to make creating sidebar displays simple. It handles score ordering and line management automatically.

---

## Constants

### MAX_LINES

```python
Sidebar.MAX_LINES  # 15
```

Maximum number of lines a sidebar can display (Minecraft limitation).

---

## Constructor

```python
Sidebar(title="")
```

Create a new sidebar.

- **Parameters:**
  - `title` (`str`) — Title displayed at the top. Supports `§` color codes.

```python
sidebar = Sidebar("§6§lMy Server")
```

---

## Attributes

### title

- **Type:** `str`

The sidebar title.

---

## Item Access

Sidebar supports index-based access using `[]` notation. Slot 0 is the bottom line, higher slots are higher lines.

### Set a line

```python
sidebar[slot] = text
```

- **Parameters:**
  - `slot` (`int`) — Line position (0 = bottom, higher = above).
  - `text` (`str`) — Line text. Supports `§` color codes.

### Get a line

```python
text = sidebar[slot]
```

- **Returns:** `str` — Text at the given slot.

### Delete a line

```python
del sidebar[slot]
```

Removes the line at the given slot.

---

## Methods

### show

```python
sidebar.show(player)
```

Display this sidebar to a player. This is synchronous — it assigns a scoreboard to the player.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Player to show the sidebar to.

---

## Example: Server info sidebar

```python
from bridge import *

sidebar = Sidebar("§6§lMy Server")
sidebar[6] = "§7──────────"
sidebar[5] = "§fOnline: §a0"
sidebar[4] = "§fTPS: §a20.0"
sidebar[3] = ""
sidebar[2] = "§fKills: §c0"
sidebar[1] = "§fDeaths: §c0"
sidebar[0] = "§7──────────"

@event
async def player_join(e: Event):
    sidebar[5] = f"§fOnline: §a{len(server.players)}"
    sidebar.show(e.player)

@event
async def player_quit(e: Event):
    sidebar[5] = f"§fOnline: §a{len(server.players) - 1}"
```

## Example: Per-player stats

```python
from bridge import *

kills = {}

@event
async def player_join(e: Event):
    p = e.player
    kills.setdefault(p.name, 0)
    sb = Sidebar("§c§lPvP Stats")
    sb[3] = f"§fPlayer: §a{p.name}"
    sb[2] = f"§fKills: §e{kills[p.name]}"
    sb[1] = f"§fHealth: §c{int(p.health)}❤"
    sb[0] = "§7play.example.com"
    sb.show(p)
```

> **Note:** `Sidebar` creates its own internal scoreboard and objective. If you need multiple objectives or teams, use the lower-level [`Scoreboard`](scoreboard.md) API.
