---
title: ManaStore [ext]
subtitle: Per-player mana tracking
---

# ManaStore [ext]

`ManaStore` tracks mana per player with auto-regen and BossBar display.

```python
from bridge.extensions import ManaStore
```

---

## Constructor

```python
ManaStore(default_mana=100, default_max_mana=100,
          default_regen_rate=1, display_bossbar=False)
```

---

## Usage

```python
mana = ManaStore(default_mana=100, display_bossbar=True)

# Index notation
current = mana[player]
mana[player] = 50
```

---

## Methods

### consume(player, amount) → bool

Returns `False` if insufficient.

### restore(player, amount)

### start_regen()

Begin the auto-regen loop (1 tick per second by default).

---

## Per-Player Overrides

```python
mana.set_max(player, 200)
mana.set_regen(player, 5)
```

---

## Player Integration

Set `Player._default_mana_store = mana` to enable `player.mana`.
