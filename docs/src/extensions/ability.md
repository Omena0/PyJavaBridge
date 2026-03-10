---
title: Ability [ext]
subtitle: Player abilities with cooldowns and mana
---

# Ability [ext]

`Ability` represents a player ability with cooldown, optional mana cost, and BossBar display.

```python
from bridge.extensions import Ability
```

---

## Constructor

```python
Ability(name, description="", cooldown=0, use_cost=0,
        cooldown_msg="§cAbility on cooldown!", display_bossbar=False)
```

- **Parameters:**
  - `name` (`str`) — Ability name.
  - `description` (`str`) — Flavour text.
  - `cooldown` (`float`) — Cooldown in seconds.
  - `use_cost` (`float`) — Mana cost (requires `set_mana_store()`).
  - `cooldown_msg` (`str`) — Message shown when on cooldown.
  - `display_bossbar` (`bool`) — Show cooldown bar.

---

## Methods

### use(player)

Try to use the ability. Checks `can_use`, then fires `on_use`.

### set_mana_store(mana_store)

Link a `ManaStore` for mana cost checking.

---

## Decorators

### @ability.on_use

```python
fireball = Ability("Fireball", cooldown=5, use_cost=20)

@fireball.on_use
async def cast(player):
    player.send_message("§c🔥 Fireball!")
```

### @ability.can_use

```python
@fireball.can_use
def check(player):
    return player.health > 5  # must have >5 HP
```
