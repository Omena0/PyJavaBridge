---
title: CustomItem [ext]
subtitle: Custom item registry
---

# CustomItem [ext]

`CustomItem` extends [`ItemBuilder`](itembuilder.html) with a global registry.
All fluent builder methods (`name()`, `lore()`, `enchant()`, `glow()`, etc.) are inherited.

```python
from bridge.extensions import CustomItem
```

---

## Constructor

```python
CustomItem(item_id, material="DIAMOND")
```

- **Parameters:**
  - `item_id` (`str`) — Unique ID (e.g. `"magic_sword"`).
  - `material` (`str`) — Material name.

Automatically registered in the global registry.

---

## Methods

All [`ItemBuilder`](itembuilder.html) methods are available, plus:

### give(player, amount=1)

Build and give copies to a player.

---

## Class Methods

### CustomItem.get(item_id) → CustomItem | None

Look up a registered custom item.

### CustomItem.all() → dict[str, CustomItem]

Get all registered items.

---

## Example

```python
from bridge.extensions import CustomItem

sword = (CustomItem("fire_sword", "DIAMOND_SWORD")
         .name("§cFire Sword")
         .lore("§7Burns on hit", "§7+5 Fire Damage")
         .enchant("fire_aspect", 2)
         .glow())

@command("Give fire sword")
async def give_sword(event):
    sword.give(event.player)
```
