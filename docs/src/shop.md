---
title: Shop [ext]
subtitle: Chest-GUI shop with pagination
---

# Shop [ext]

`Shop` opens a paginated chest GUI where players can buy items using a `Bank`.

```python
from bridge.extensions import Shop
```

---

## Constructor

```python
Shop(name, bank)
```

- **Parameters:**
  - `name` (`str`) — Shop title.
  - `bank` (`Bank`) — Bank instance for transactions.

---

## Methods

### add_item(item, price)

Add an item to the shop.

- `item` (`Item | str`) — Item or material name.
- `price` (`int`) — Cost.

### open(player, page=0)

Open the shop GUI for a player.

### close(player)

Close the GUI.

---

## Decorators

### @shop.on_purchase

```python
@shop.on_purchase
def purchased(player, item, price, shop):
    player.send_message(f"Bought {item.name} for {price}!")
```
