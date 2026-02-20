---
title: Menu
subtitle: GUI menu system
---

# Menu

`Menu` is a high-level inventory GUI system with click handlers. It wraps [`Inventory`](inventory.md) with per-slot click callbacks using [`MenuItem`](#menuitem).

---

## Constructor

```python
Menu(title="", rows=3)
```

Create a menu.

- **Parameters:**
  - `title` (`str`) — Title displayed at the top. Supports `§` color codes.
  - `rows` (`int`) — Number of rows (1–6). Each row has 9 slots. Default 3.

```python
shop = Menu("§6§lItem Shop", rows=3)
```

---

## Attributes

### title

- **Type:** `str`

Menu title.

### rows

- **Type:** `int`

Number of rows.

---

## Slot Access

Menu supports index-based access using `[]` notation.

### Set a slot

```python
menu[slot] = menu_item
```

- **Parameters:**
  - `slot` (`int`) — Slot index (0-based, left-to-right, top-to-bottom).
  - `menu_item` ([`MenuItem`](#menuitem)) — Item with click handler.

### Get a slot

```python
item = menu[slot]
```

- **Returns:** [`MenuItem`](#menuitem) `| None`

### Delete a slot

```python
del menu[slot]
```

---

## Methods

### fill_border

```python
menu.fill_border(item)
```

Fill the border slots with a decorative item. This is synchronous.

- **Parameters:**
  - `item` ([`Item`](item.md)) — Item to use for the border.

```python
shop = Menu("§6§lShop", rows=3)
shop.fill_border(Item("GRAY_STAINED_GLASS_PANE", name=" "))
```

### open

```python
menu.open(player)
```

Open this menu for a player. This is synchronous.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Player to show the menu to.

---

# MenuItem

A `MenuItem` wraps an [`Item`](item.md) with an optional click callback.

## Constructor

```python
MenuItem(item, on_click=None)
```

- **Parameters:**
  - `item` ([`Item`](item.md) `| str`) — The display item. If a string, creates an `Item` with that material.
  - `on_click` (`Callable[[`[`Player`](player.md)`, `[`Event`](event.md)`], Any] | None`) — Click callback. Receives the clicking player and the click event. Default `None`.

```python
# Simple display item
MenuItem(Item("DIAMOND", name="§bShiny"))

# With click handler
MenuItem(
    Item("GOLDEN_APPLE", name="§6Buy Apple §7- §a$50"),
    on_click=lambda player, event: player.send_message("§aPurchased!")
)
```

## Attributes

### item

- **Type:** [`Item`](item.md)

The display item.

### on_click

- **Type:** `Callable[[`[`Player`](player.md)`, `[`Event`](event.md)`], Any] | None`

Click callback.

---

## Example: Shop menu

```python
from bridge import *

async def buy_sword(player, event):
    await Item.give(player, "DIAMOND_SWORD")
    await player.send_message("§aYou bought a Diamond Sword!")

async def buy_armor(player, event):
    await Item.give(player, "DIAMOND_CHESTPLATE")
    await player.send_message("§aYou bought Diamond Armor!")

@command("Open the shop")
async def shop(player: Player, args: list[str]):
    menu = Menu("§6§lItem Shop", rows=3)
    menu.fill_border(Item("BLACK_STAINED_GLASS_PANE", name=" "))

    menu[10] = MenuItem(
        Item("DIAMOND_SWORD", name="§bDiamond Sword", lore=["§7Price: §a$100"]),
        on_click=buy_sword
    )
    menu[12] = MenuItem(
        Item("DIAMOND_CHESTPLATE", name="§bDiamond Armor", lore=["§7Price: §a$500"]),
        on_click=buy_armor
    )
    menu[14] = MenuItem(
        Item("GOLDEN_APPLE", name="§6Golden Apple", lore=["§7Price: §a$50"]),
        on_click=lambda p, e: Item.give(p, "GOLDEN_APPLE")
    )
    menu[16] = MenuItem(
        Item("BARRIER", name="§cClose"),
        on_click=lambda p, e: p.inventory.close()
    )

    menu.open(player)
```

## Example: Confirmation dialog

```python
from bridge import *

def confirm_menu(title, on_confirm, on_cancel):
    menu = Menu(title, rows=3)
    menu.fill_border(Item("GRAY_STAINED_GLASS_PANE", name=" "))

    menu[11] = MenuItem(
        Item("LIME_WOOL", name="§a§lConfirm"),
        on_click=on_confirm
    )
    menu[15] = MenuItem(
        Item("RED_WOOL", name="§c§lCancel"),
        on_click=on_cancel
    )
    return menu

@command("Delete your home")
async def delhome(player: Player, args: list[str]):
    async def confirm(p, e):
        await p.send_message("§aHome deleted!")
        await p.inventory.close()

    async def cancel(p, e):
        await p.send_message("§cCancelled.")
        await p.inventory.close()

    menu = confirm_menu("§c§lDelete Home?", confirm, cancel)
    menu.open(player)
```

> **Tip:** For lower-level inventory control without click handlers, see [`Inventory`](inventory.md).
