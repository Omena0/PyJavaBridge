---
title: BossBarDisplay
subtitle: Per-player boss bar manager
---

# BossBarDisplay

`BossBarDisplay` is a high-level wrapper around `BossBar` that manages per-player visibility and integrates with `Cooldown` for automatic progress animation.

---

## Constructor

```python
BossBarDisplay(title="", color="PINK", style="SOLID")
```

Create a boss bar display.

- **Parameters:**
  - `title` (`str`) — Bar title. Supports `§` color codes. Default `""`.
  - `color` (`str`) — Bar color name. Default `"PINK"`. Options: `"PINK"`, `"BLUE"`, `"RED"`, `"GREEN"`, `"YELLOW"`, `"PURPLE"`, `"WHITE"`.
  - `style` (`str`) — Bar style name. Default `"SOLID"`. Options: `"SOLID"`, `"SEGMENTED_6"`, `"SEGMENTED_10"`, `"SEGMENTED_12"`, `"SEGMENTED_20"`.

```python
ability_bar = BossBarDisplay("§6Fireball", color="RED", style="SOLID")
```

---

## Attributes

### text

- **Type:** `str`

Current title text.

### color

- **Type:** `str`

Current color name.

### style

- **Type:** `str`

Current style name.

### value

- **Type:** `float`

Current value.

### max

- **Type:** `float`

Maximum value.

### progress

- **Type:** `float`

Progress from 0.0 to 1.0 (calculated as `value / max`).

### visible

- **Type:** `bool`

Whether the bar is currently visible.

---

## Methods

### show

```python
display.show(player)
```

Show the boss bar to a player. This is synchronous.

- **Parameters:**
  - `player` (`Player`) — Player to show the bar to.

### hide

```python
display.hide(player)
```

Hide the boss bar from a player. This is synchronous.

- **Parameters:**
  - `player` (`Player`) — Player to hide from.

### link_to

```python
display.link_to(cooldown, player)
```

Link this bar to a `Cooldown` — the bar progress will automatically animate to reflect the remaining cooldown time.

- **Parameters:**
  - `cooldown` (`Cooldown`) — The cooldown to track.
  - `player` (`Player`) — The player to display the cooldown bar to.

```python
cd = Cooldown(seconds=10.0)
bar = BossBarDisplay("§6Fireball Cooldown", color="RED")

@command("Fireball")
async def fireball(player: Player, args: list[str]):
    if not cd.check(player):
        return

    bar.link_to(cd, player)
    await player.send_message("§6🔥 Fireball!")
```

---

## Example: Ability cooldown bar

```python
from bridge import *

fireball_cd = Cooldown(seconds=8.0)
fireball_bar = BossBarDisplay("§6§lFireball", color="RED", style="SOLID")

@command("Shoot a fireball")
async def fireball(player: Player, args: list[str]):
    if not fireball_cd.check(player):
        r = fireball_cd.remaining(player)
        await player.send_message(f"§c{r:.1f}s cooldown!")
        return

    fireball_bar.link_to(fireball_cd, player)
    await world.spawn_projectile(player, "FIREBALL")
    await player.send_message("§6🔥 Fireball launched!")
```

## Example: Multiple ability bars

```python
from bridge import *

abilities = {
    "fireball": {
        "cd": Cooldown(seconds=8.0),
        "bar": BossBarDisplay("§6Fireball", color="RED"),
    },
    "heal": {
        "cd": Cooldown(seconds=15.0),
        "bar": BossBarDisplay("§aHeal", color="GREEN"),
    },
    "dash": {
        "cd": Cooldown(seconds=3.0),
        "bar": BossBarDisplay("§bDash", color="BLUE"),
    },
}

@command("Use an ability")
async def ability(player: Player, args: list[str]):
    if not args or args[0] not in abilities:
        await player.send_message("§cUsage: /ability <fireball|heal|dash>")
        return

    ab = abilities[args[0]]
    if not ab["cd"].check(player):
        return

    ab["bar"].link_to(ab["cd"], player)
    await player.send_message(f"§aUsed {args[0]}!")
```

> **See also:** `BossBar` for the lower-level boss bar API, `Cooldown` for standalone cooldown tracking.
