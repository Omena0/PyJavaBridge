---
title: ManaStore [ext]
subtitle: Per-player mana tracking
---

# ManaStore [ext]

`ManaStore` tracks mana per player with auto-regen and BossBar display. It automatically cleans up boss bars when players disconnect.

```python
from bridge.extensions import ManaStore
```

---

## Constructor

```python
ManaStore(default_mana=100, default_max_mana=100,
          default_regen_rate=1, display_bossbar=False)
```

- **Parameters:**
  - `default_mana` (`float`) — Starting mana for new players. Default 100.
  - `default_max_mana` (`float`) — Maximum mana for new players. Default 100.
  - `default_regen_rate` (`float`) — Mana restored per regen tick. Default 1.
  - `display_bossbar` (`bool`) — Whether to show a BossBar above the player's screen. Default `False`.

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

Try to consume mana. Returns `False` if the player doesn't have enough.

```python
if mana.consume(player, 30):
    # Ability cast succeeds
    ...
else:
    await player.send_message("§cNot enough mana!")
```

### restore(player, amount)

Restore mana to the player (capped at max).

### start_regen()

Begin the auto-regen loop (restores `regen_rate` mana per second).

---

## Per-Player Overrides

```python
mana.set_max(player, 200)
mana.set_regen(player, 5)
```

---

## Player Integration

Set `Player._default_mana_store = mana` to enable `player.mana`:

```python
Player._default_mana_store = mana

# Now you can use:
current = player.mana
player.mana = 50
```

---

## Lifecycle

- **Player disconnect:** Boss bars are automatically removed when a player quits. The regen loop skips disconnected players gracefully.
- **Script reload:** Boss bars are cleaned up on reload to prevent duplicates.
