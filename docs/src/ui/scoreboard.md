---
title: Scoreboard
subtitle: Scoreboard management
---

# Scoreboard

A `Scoreboard` manages objectives and teams. Each player can see one scoreboard at a time — assign a custom scoreboard to show custom sidebar content, name tags, or tab list formatting.

---

## Class Methods

### create

```python
board = Scoreboard.create()
```

Create a new empty scoreboard. This is synchronous.

- **Returns:** [`Scoreboard`](#)

```python
board = Scoreboard.create()
await player.set_scoreboard(board)
```

---

## Attributes

### objectives

- **Type:** `list[`[`Objective`](objective.md)`]`

All objectives registered on this scoreboard.

### teams

- **Type:** `list[`[`Team`](team.md)`]`

All teams registered on this scoreboard.

---

## Methods

### register_objective

```python
objective = board.register_objective(name, criteria, display_name="")
```

Register a new objective. This is synchronous.

- **Parameters:**
  - `name` (`str`) — Internal name (unique per scoreboard).
  - `criteria` (`str`) — Criteria type (e.g. `"dummy"`, `"health"`, `"playerKillCount"`).
  - `display_name` (`str`) — Display name shown in the sidebar/tab. Default `""`.
- **Returns:** [`Objective`](objective.md)

```python
obj = board.register_objective("kills", "dummy", "§c§lKill Count")
```

### get_objective

```python
objective = board.get_objective(name)
```

Get an existing objective by name.

- **Parameters:**
  - `name` (`str`) — Internal objective name.
- **Returns:** [`Objective`](objective.md)

### register_team

```python
team = board.register_team(name)
```

Register a new team. This is synchronous.

- **Parameters:**
  - `name` (`str`) — Internal name (unique per scoreboard).
- **Returns:** [`Team`](team.md)

```python
red_team = board.register_team("red")
await red_team.set_prefix("§c[RED] ")
await red_team.set_color("RED")
```

### get_team

```python
team = board.get_team(name)
```

Get an existing team by name.

- **Parameters:**
  - `name` (`str`) — Internal team name.
- **Returns:** [`Team`](team.md)

### clear_slot

```python
await board.clear_slot(slot)
```

Clear the display in a specific slot.

- **Parameters:**
  - `slot` (`Any`) — Display slot to clear.
- **Returns:** `Awaitable[None]`

---

## Example: Kill counter sidebar

```python
from bridge import *

board = Scoreboard.create()
obj = board.register_objective("kills", "dummy", "§6§lKill Count")
await obj.set_display_slot("SIDEBAR")

@event
async def player_join(e: Event):
    await e.player.set_scoreboard(board)

@event
async def entity_death(e: Event):
    killer = e.damager
    if killer and hasattr(killer, 'name'):
        score = obj.get_score(killer.name)
        # Score tracking happens automatically via the scoreboard API
```

> **See also:** [`Sidebar`](sidebar.md) for a simpler high-level sidebar helper.
