---
title: CombatSystem [ext]
subtitle: Combat tagging and log detection
---

# CombatSystem [ext]

`CombatSystem` tracks when players are in combat and detects combat logging.

```python
from bridge.extensions import CombatSystem
```

---

## Constructor

```python
CombatSystem(combat_timeout=10, display_bossbar=False)
```

- `combat_timeout` (`float`) — Seconds after last hit before out of combat.
- `display_bossbar` (`bool`) — Show remaining combat time on a BossBar.

---

## Methods

### start()

Register damage and quit listeners.

### in_combat(player) → bool

### remaining(player) → float

Seconds remaining in combat.

---

## Decorators

### @combat.on_combat_log

```python
combat = CombatSystem(combat_timeout=15, display_bossbar=True)
combat.start()

@combat.on_combat_log
def logged(player, combat_system):
    server.broadcast(f"§c{player.name} combat logged!")
```
