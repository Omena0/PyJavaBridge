---
title: BossBar
subtitle: Boss bar display API
---

# BossBar

A `BossBar` is the bar displayed at the top of the screen (like the Ender Dragon or Wither health bar). You can create custom boss bars with custom titles, colors, and progress.

---

## Class Methods

### create

```python
bar = BossBar.create(title, color=None, style=None, players=None)
```

Create a new boss bar. This is synchronous.

- **Parameters:**
  - `title` (`str`) — Bar title text. Supports `§` color codes.
  - `color` ([`BarColor`](enums.md) `| None`) — Bar color. Default `None` (PINK).
  - `style` ([`BarStyle`](enums.md) `| None`) — Bar segmentation style. Default `None` (SOLID).
  - `players` (`list[`[`Player`](player.md)`] | None`) — Players who can see the bar. Default `None`.
- **Returns:** [`BossBar`](#)

```python
bar = BossBar.create(
    "§c§lRaid Boss",
    color=BarColor.RED,
    style=BarStyle.SEGMENTED_10
)
```

---

## Attributes

### title

- **Type:** `str`

Current title text.

### progress

- **Type:** `float`

Progress value from 0.0 (empty) to 1.0 (full).

### color

- **Type:** [`BarColor`](enums.md)

Current bar color.

### style

- **Type:** [`BarStyle`](enums.md)

Current segmentation style.

### visible

- **Type:** `bool`

Whether the bar is currently visible.

---

## Methods

### add_player

```python
await bar.add_player(player)
```

Show this bar to a player.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Player to add.
- **Returns:** `Awaitable[None]`

### remove_player

```python
await bar.remove_player(player)
```

Hide this bar from a player.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Player to remove.
- **Returns:** `Awaitable[None]`

### set_title

```python
await bar.set_title(title)
```

Change the bar title.

- **Parameters:**
  - `title` (`str`) — New title text.
- **Returns:** `Awaitable[None]`

### set_progress

```python
await bar.set_progress(value)
```

Set the bar progress.

- **Parameters:**
  - `value` (`float`) — Progress from 0.0 to 1.0.
- **Returns:** `Awaitable[None]`

```python
await bar.set_progress(0.5)  # Half full
```

### set_color

```python
await bar.set_color(color)
```

Change the bar color.

- **Parameters:**
  - `color` ([`BarColor`](enums.md)) — New color.
- **Returns:** `Awaitable[None]`

### set_style

```python
await bar.set_style(style)
```

Change the bar segmentation style.

- **Parameters:**
  - `style` ([`BarStyle`](enums.md)) — New style.
- **Returns:** `Awaitable[None]`

### set_visible

```python
await bar.set_visible(value)
```

Show or hide the bar without removing players.

- **Parameters:**
  - `value` (`bool`) — Visibility.
- **Returns:** `Awaitable[None]`

---

## BarColor Options

| Name | Description |
|------|-------------|
| `PINK` | Default pink |
| `BLUE` | Blue |
| `RED` | Red |
| `GREEN` | Green |
| `YELLOW` | Yellow |
| `PURPLE` | Purple |
| `WHITE` | White |

## BarStyle Options

| Name | Description |
|------|-------------|
| `SOLID` | No segments |
| `SEGMENTED_6` | 6 segments |
| `SEGMENTED_10` | 10 segments |
| `SEGMENTED_12` | 12 segments |
| `SEGMENTED_20` | 20 segments |

---

## Example: Health bar for a boss fight

```python
from bridge import *

boss_bar = BossBar.create("§c§lDragon §7- §c100%", color=BarColor.RED, style=BarStyle.SEGMENTED_10)

@event
async def entity_damage(e: Event):
    entity = e.entity
    if entity.custom_name == "Dragon":
        hp_pct = entity.health / 100
        await boss_bar.set_progress(hp_pct)
        await boss_bar.set_title(f"§c§lDragon §7- §c{int(hp_pct * 100)}%")
```

> **See also:** [`BossBarDisplay`](bossbardisplay.md) for a higher-level wrapper with cooldown linking.
