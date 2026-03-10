---
title: Menu
subtitle: GUI menu system
---

# Menu

`Menu` is a high-level inventory GUI system with click handlers. It wraps [`Inventory`](inventory.md) with per-slot click callbacks using [`MenuItem`](menuitem.md).

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
  - `menu_item` ([`MenuItem`](menuitem.md)) — Item with click handler.

### Get a slot

```python
item = menu[slot]
```

- **Returns:** [`MenuItem`](menuitem.md) `| None`

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

> **Tip:** You can safely open a new menu from inside a click handler. The bridge handles the close/re-open race condition automatically.

```python
# Opening a sub-menu from a click handler
def on_settings_click(player, event):
    settings_menu.open(player)  # Works correctly

main = Menu("§6Main Menu", rows=1)
main[0] = MenuItem(Item("REDSTONE", name="§cSettings"), on_click=on_settings_click)
```

> **Tip:** See [`MenuItem`](menuitem.md) for click handler details and examples.
