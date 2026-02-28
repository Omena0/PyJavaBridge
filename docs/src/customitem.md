---
title: CustomItem [ext]
subtitle: Custom item registry
---

# CustomItem [ext]

`CustomItem` defines reusable item templates stored in a global registry.

```python
from bridge.extensions import CustomItem
```

---

## Constructor

```python
CustomItem(item_id, material, name=None, lore=None, custom_model_data=None)
```

- **Parameters:**
  - `item_id` (`str`) — Unique ID (e.g. `"magic_sword"`).
  - `material` (`str`) — Material name.
  - `name` (`str | None`) — Display name.
  - `lore` (`list[str] | None`) — Lore lines.
  - `custom_model_data` (`int | None`) — Custom model data.

Automatically registered in the global registry.

---

## Methods

### build() → Item

Create a new `Item` from this template.

### give(player, amount=1)

Give copies to a player.

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

sword = CustomItem("fire_sword", "DIAMOND_SWORD",
                   name="§cFire Sword",
                   lore=["§7Burns on hit"])

@command("Give fire sword")
async def give_sword(event):
    sword.give(event.player)
```
