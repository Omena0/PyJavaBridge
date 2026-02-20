---
title: Cooldown
subtitle: Rate limiting helper
---

# Cooldown

`Cooldown` is a helper that tracks per-player cooldowns. Use it to prevent ability spam, command abuse, or add skill cooldown timers.

---

## Constructor

```python
Cooldown(seconds=1.0, on_expire=None)
```

Create a cooldown tracker.

- **Parameters:**
  - `seconds` (`float`) — Cooldown duration in seconds. Default 1.0.
  - `on_expire` (`Callable[[`[`Player`](player.md)`], Any] | None`) — Callback invoked when a player's cooldown expires. Default `None`.

```python
ability_cd = Cooldown(seconds=5.0)

fireball_cd = Cooldown(
    seconds=10.0,
    on_expire=lambda p: p.send_message("§aFireball ready!")
)
```

---

## Attributes

### seconds

- **Type:** `float`

The cooldown duration in seconds.

### on_expire

- **Type:** `Callable[[`[`Player`](player.md)`], Any] | None`

Callback invoked when the cooldown expires for a player.

---

## Methods

### check

```python
is_ready = cooldown.check(player)
```

Check if the player's cooldown has expired. If ready, **automatically starts a new cooldown**.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Player to check.
- **Returns:** `bool` — `True` if the cooldown was ready (and has now been reset), `False` if still on cooldown.

```python
cd = Cooldown(seconds=5.0)

@command("Use special ability")
async def ability(player: Player, args: list[str]):
    if not cd.check(player):
        remaining = cd.remaining(player)
        await player.send_message(f"§cOn cooldown! {remaining:.1f}s remaining")
        return
    await player.send_message("§aAbility activated!")
```

### remaining

```python
time_left = cooldown.remaining(player)
```

Get the remaining cooldown time for a player.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Player to check.
- **Returns:** `float` — Remaining seconds, or 0.0 if ready.

### reset

```python
cooldown.reset(player)
```

Manually reset (clear) a player's cooldown, making the ability immediately available.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Player to reset.

---

## Example: Ability with boss bar indicator

```python
from bridge import *

fireball_cd = Cooldown(seconds=8.0)

@command("Shoot a fireball")
async def fireball(player: Player, args: list[str]):
    if not fireball_cd.check(player):
        r = fireball_cd.remaining(player)
        await player.send_message(f"§c{r:.1f}s cooldown remaining!")
        return

    loc = player.location
    await world.spawn_projectile(player, "FIREBALL")
    await player.send_message("§6🔥 Fireball launched!")
```

## Example: On-expire callback

```python
from bridge import *

dash_cd = Cooldown(
    seconds=3.0,
    on_expire=lambda p: p.send_action_bar("§aDash ready!")
)

@command("Dash forward")
async def dash(player: Player, args: list[str]):
    if not dash_cd.check(player):
        await player.send_action_bar(f"§c{dash_cd.remaining(player):.1f}s")
        return

    await player.set_velocity(Vector(0, 0.5, 1.5))
    await player.send_action_bar("§6Dash!")
```

> **See also:** [`BossBarDisplay.link_cooldown()`](bossbardisplay.md#link_cooldown) to visually display cooldown progress.
