---
title: LevelSystem [ext]
subtitle: XP and levelling
---

# LevelSystem [ext]

`LevelSystem` provides configurable XP/levelling with persistence.

```python
from bridge.extensions import LevelSystem
```

---

## Constructor

```python
LevelSystem(multiplier=100, exponent=1.5, persist=True)
```

- `multiplier` (`float`) — Base XP for level 1.
- `exponent` (`float`) — XP curve exponent. XP for level N = `multiplier * N^exponent`.
- `persist` (`bool`) — Save XP to `plugins/PyJavaBridge/levels.json`.

---

## Usage

```python
levels = LevelSystem(multiplier=100, exponent=1.5)

# Index notation
levels[player]  # current level (int)
```

---

## Methods

### xp(player) → float

### level(player) → int

### add_xp(player, amount)

### set_xp(player, amount)

### set_level(player, level)

### xp_to_next(player) → float

XP needed for next level.

### progress(player) → float

0.0 – 1.0 progress through current level.

---

## Decorators

### @levels.on_level_up

```python
@levels.on_level_up
def leveled(player, old_level, new_level, system):
    player.send_message(f"§aLevel up! {old_level} → {new_level}")
```

---

## Player Integration

Set `Player._default_level_system = levels` to enable `player.xp` and `player.player_level`.
