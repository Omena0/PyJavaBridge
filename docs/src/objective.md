---
title: Objective
subtitle: Scoreboard objective API
---

# Objective

An `Objective` tracks a score for each player on a [`Scoreboard`](scoreboard.md). Objectives can be displayed in the sidebar, below name tags, or in the tab list.

---

## Class Methods

### create

```python
obj = Objective.create(name, criteria, display_name="", scoreboard=None)
```

Create a new objective. This is synchronous.

- **Parameters:**
  - `name` (`str`) — Internal objective name (unique per scoreboard).
  - `criteria` (`str`) — Score criteria. See [Criteria table](#criteria-types) below.
  - `display_name` (`str`) — Name displayed to players. Default `""`.
  - `scoreboard` ([`Scoreboard`](scoreboard.md) `| None`) — Scoreboard to register on. If `None`, uses the main scoreboard.
- **Returns:** [`Objective`](#)

```python
obj = Objective.create("kills", "dummy", "§6Kill Count")
```

---

## Attributes

### name

- **Type:** `str`

Internal name of the objective.

### criteria

- **Type:** `str`

The criteria type (e.g. `"dummy"`, `"health"`).

### display_slot

- **Type:** `Any`

Current display slot, or `None` if not displayed.

---

## Methods

### set_display_name

```python
await obj.set_display_name(name)
```

Change the display name.

- **Parameters:**
  - `name` (`str`) — New display name. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

### set_display_slot

```python
await obj.set_display_slot(slot)
```

Set where this objective is displayed.

- **Parameters:**
  - `slot` (`Any`) — Display slot. Common values: `"SIDEBAR"`, `"BELOW_NAME"`, `"PLAYER_LIST"`.
- **Returns:** `Awaitable[None]`

```python
await obj.set_display_slot("SIDEBAR")     # Right side of screen
await obj.set_display_slot("BELOW_NAME")  # Under name tags
await obj.set_display_slot("PLAYER_LIST") # In tab list
```

### get_score

```python
score = obj.get_score(entry)
```

Get the score tracker for a player. This is synchronous and returns a score object.

- **Parameters:**
  - `entry` (`str`) — Player name.
- **Returns:** Score object

```python
score = obj.get_score(player.name)
```

---

## Criteria Types

| Criteria | Description |
|----------|-------------|
| `dummy` | Manual scores only — set by commands/plugins |
| `health` | Player health (auto-updated) |
| `playerKillCount` | Player kills (auto-updated) |
| `totalKillCount` | Total kills (auto-updated) |
| `deathCount` | Deaths (auto-updated) |
| `food` | Food level (auto-updated) |
| `air` | Air remaining (auto-updated) |
| `armor` | Armor points (auto-updated) |
| `xp` | XP level (auto-updated) |

---

## Example: Custom sidebar

```python
from bridge import *

board = Scoreboard.create()
sidebar = board.register_objective("display", "dummy", "§6§lMy Server")
await sidebar.set_display_slot("SIDEBAR")

# Set lines (higher score = higher position)
sidebar.get_score("§7───────────").score = 10
sidebar.get_score("§fKills: §a0").score = 9
sidebar.get_score("§fDeaths: §c0").score = 8
sidebar.get_score("§fCoins: §e0").score = 7
sidebar.get_score("§7───────────").score = 6

@event
async def player_join(e: Event):
    await e.player.set_scoreboard(board)
```

> **Tip:** For a simpler sidebar API that handles line management automatically, see [`Sidebar`](sidebar.md).
