---
title: Team
subtitle: Scoreboard team API
---

# Team

A `Team` groups players on a [`Scoreboard`](scoreboard.md) for shared prefixes, suffixes, colors, and friendly-fire settings.

---

## Class Methods

### create

```python
team = Team.create(name, scoreboard=None)
```

Create a new team. This is synchronous.

- **Parameters:**
  - `name` (`str`) — Internal team name.
  - `scoreboard` ([`Scoreboard`](scoreboard.md) `| None`) — Scoreboard to register on. If `None`, uses the main scoreboard.
- **Returns:** [`Team`](#)

```python
red = Team.create("red")
await red.set_prefix("§c[RED] ")
await red.set_color("RED")
```

---

## Attributes

### color

- **Type:** `Any`

The team's color used for name tag coloring.

### entries

- **Type:** `set[str]`

Player names currently on this team.

---

## Methods

### add_entry

```python
await team.add_entry(entry)
```

Add a player to this team.

- **Parameters:**
  - `entry` (`str`) — Player name.
- **Returns:** `Awaitable[None]`

```python
await red_team.add_entry(player.name)
```

### remove_entry

```python
await team.remove_entry(entry)
```

Remove a player from this team.

- **Parameters:**
  - `entry` (`str`) — Player name.
- **Returns:** `Awaitable[None]`

### set_prefix

```python
await team.set_prefix(prefix)
```

Set the name tag prefix for all team members.

- **Parameters:**
  - `prefix` (`str`) — Prefix text. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

```python
await team.set_prefix("§a[VIP] ")
```

### set_suffix

```python
await team.set_suffix(suffix)
```

Set the name tag suffix for all team members.

- **Parameters:**
  - `suffix` (`str`) — Suffix text.
- **Returns:** `Awaitable[None]`

### set_color

```python
await team.set_color(color)
```

Set the team color (affects name tag color and tab list).

- **Parameters:**
  - `color` (`Any`) — Color name (e.g. `"RED"`, `"BLUE"`, `"GREEN"`).
- **Returns:** `Awaitable[None]`

---

## Example: PvP teams

```python
from bridge import *

board = Scoreboard.create()
red_team = board.register_team("red")
blue_team = board.register_team("blue")

@command("Join a team")
async def team_join(player: Player, args: list[str]):
    if not args:
        await player.send_message("§cUsage: /team <red|blue>")
        return

    name = args[0].lower()
    if name == "red":
        await red_team.add_entry(player.name)
        await red_team.set_prefix("§c[RED] ")
        await red_team.set_color("RED")
        await player.send_message("§cYou joined the Red team!")
    elif name == "blue":
        await blue_team.add_entry(player.name)
        await blue_team.set_prefix("§9[BLUE] ")
        await blue_team.set_color("BLUE")
        await player.send_message("§9You joined the Blue team!")
    
    await player.set_scoreboard(board)
```
