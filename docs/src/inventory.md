---
title: Inventory
subtitle: Container and GUI API
---

# Inventory

An `Inventory` represents a chest-like container that can be opened as a GUI for players. Use it for custom menus, storage views, or item manipulation.

---

## Constructor

```python
Inventory(size=9, title="", contents=None)
```

Create a new inventory.

- **Parameters:**
  - `size` (`int`) — Number of slots. Must be a multiple of 9 (9, 18, 27, 36, 45, 54). Default 9.
  - `title` (`str`) — Display title shown when opened. Supports `§` color codes. Default `""`.
  - `contents` (`list[`[`Item`](item.md)`] | None`) — Initial items. Default `None` (empty).

```python
gui = Inventory(27, "§6Rewards Chest")
```

---

## Attributes

### size

- **Type:** `int`

Total number of slots.

### contents

- **Type:** `list[`[`Item`](item.md)`]`

List of items in the inventory. Empty slots are `None`.

### holder

- **Type:** `Any`

The holder of this inventory (player, chest block, etc.), or `None` for virtual inventories.

### title

- **Type:** `str`

Display title of the inventory.

### first_empty

- **Type:** `int`

Index of the first empty slot, or `-1` if the inventory is full.

---

## Methods

### open

```python
await inventory.open(player)
```

Open this inventory as a GUI for a player.

- **Parameters:**
  - `player` ([`Player`](player.md)) — The player who will see the GUI.
- **Returns:** `Awaitable[Any]`

```python
gui = Inventory(27, "§bShop")
gui_contents = [Item("DIAMOND", name="§bBuy Diamond")]
await gui.open(player)
```

### close

```python
await inventory.close(player=None)
```

Close this inventory for a player.

- **Parameters:**
  - `player` ([`Player`](player.md) `| None`) — The player to close for, or `None` to close for all viewers.
- **Returns:** `Awaitable[Any]`

### add_item

```python
await inventory.add_item(item)
```

Add an item to the first available slot.

- **Parameters:**
  - `item` ([`Item`](item.md)) — The item to add.
- **Returns:** `Awaitable[Any]` — Any items that didn't fit.

```python
await inventory.add_item(Item("DIAMOND", 64))
```

### remove_item

```python
await inventory.remove_item(item)
```

Remove an item from the inventory.

- **Parameters:**
  - `item` ([`Item`](item.md)) — The item to remove.
- **Returns:** `Awaitable[Any]` — Any items that couldn't be removed.

### get_item

```python
item = await inventory.get_item(slot)
```

Get the item in a specific slot.

- **Parameters:**
  - `slot` (`int`) — Slot index (0-based).
- **Returns:** `Awaitable[`[`Item`](item.md)`]` — The item, or `None` if empty.

### set_item

```python
await inventory.set_item(slot, item)
```

Set the item in a specific slot.

- **Parameters:**
  - `slot` (`int`) — Slot index (0-based).
  - `item` ([`Item`](item.md)) — The item to place.
- **Returns:** `Awaitable[None]`

```python
await inventory.set_item(13, Item("NETHER_STAR", name="§eSpecial"))
```

### contains

```python
result = await inventory.contains(material, amount=1)
```

Check if the inventory contains at least `amount` of the given material.

- **Parameters:**
  - `material` ([`Material`](enums.md)) — Material to check for.
  - `amount` (`int`) — Minimum amount. Default 1.
- **Returns:** `Awaitable[bool]`

### clear

```python
await inventory.clear()
```

Remove all items from the inventory.

- **Returns:** `Awaitable[None]`

---

## Example: Custom GUI

```python
from bridge import *

@command("Open a shop GUI")
async def shop(player: Player, args: list[str]):
    gui = Inventory(27, "§6§lItem Shop")

    # Set border
    for i in range(27):
        if i < 9 or i >= 18 or i % 9 == 0 or i % 9 == 8:
            await gui.set_item(i, Item("GRAY_STAINED_GLASS_PANE", name=" "))

    # Set shop items
    await gui.set_item(11, Item("DIAMOND_SWORD", name="§bSword §7- §a$100"))
    await gui.set_item(13, Item("DIAMOND_CHESTPLATE", name="§bArmor §7- §a$500"))
    await gui.set_item(15, Item("GOLDEN_APPLE", name="§6Apple §7- §a$50"))

    await gui.open(player)
```

> **Tip:** For a higher-level GUI system with click handlers, see the [`Menu`](menu.md) class.
