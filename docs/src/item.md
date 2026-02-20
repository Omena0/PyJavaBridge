---
title: Item
subtitle: ItemStack API
---

# Item

An `Item` represents a Minecraft item stack with material, amount, name, lore, and NBT data.

---

## Constructor

```python
Item(material=None, amount=1, name=None, lore=None, custom_model_data=None, attributes=None, nbt=None)
```

Create an item.

- **Parameters:**
  - `material` ([`Material`](enums.md) `| str | None`) — Item material.
  - `amount` (`int`) — Stack size. Default 1.
  - `name` (`str | None`) — Display name. Supports `§` color codes.
  - `lore` (`list[str] | None`) — Lore lines.
  - `custom_model_data` (`int | None`) — Custom model data for resource packs.
  - `attributes` (`list[dict] | None`) — Attribute modifiers.
  - `nbt` (`dict | None`) — Raw NBT data.

```python
sword = Item("DIAMOND_SWORD", name="§bFrostbrand", lore=["§7A blade of ice"])
blocks = Item(Material.STONE, amount=64)
```

---

## Class Methods

### drop

```python
entity = await Item.drop(material, location, amount=1, **kwargs)
```

Drop an item entity at a location.

- **Parameters:**
  - `material` ([`Material`](enums.md) `| str`) — Item material.
  - `location` ([`Location`](location.md)) — Where to drop.
  - `amount` (`int`) — Stack size. Default 1.
  - `**kwargs` — Additional item properties.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]` — The dropped item entity.

```python
await Item.drop("DIAMOND", player.location, amount=5)
```

### give

```python
await Item.give(player, material, amount=1, **kwargs)
```

Give an item directly to a player's inventory.

- **Parameters:**
  - `player` ([`Player`](player.md)) — The recipient.
  - `material` ([`Material`](enums.md) `| str`) — Item material.
  - `amount` (`int`) — Stack size. Default 1.
  - `**kwargs` — Additional item properties.
- **Returns:** `Awaitable[None]`

```python
await Item.give(player, "GOLDEN_APPLE", 3)
```

---

## Attributes

### type

- **Type:** [`Material`](enums.md)

The item's material type.

### amount

- **Type:** `int`

Current stack size.

### name

- **Type:** `str | None`

Display name, or `None` for the default name.

### lore

- **Type:** `list[str]`

Lore lines displayed below the item name.

### custom_model_data

- **Type:** `int | None`

Custom model data value for resource packs.

### attributes

- **Type:** `list[dict]`

Attribute modifiers (attack damage, armor, etc.).

### nbt

- **Type:** `dict`

The item's NBT data as a dictionary.

### max_stack_size

- **Type:** `int`

Maximum stack size for this item type (e.g. 64 for blocks, 16 for ender pearls, 1 for tools).

---

## Methods

### set_amount

```python
await item.set_amount(value)
```

Set the stack size.

- **Parameters:**
  - `value` (`int`) — New amount.
- **Returns:** `Awaitable[None]`

### set_name

```python
await item.set_name(name)
```

Set the display name.

- **Parameters:**
  - `name` (`str`) — Name text. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

### set_lore

```python
await item.set_lore(lore)
```

Set the lore lines.

- **Parameters:**
  - `lore` (`list[str]`) — List of lore lines.
- **Returns:** `Awaitable[None]`

### set_custom_model_data

```python
await item.set_custom_model_data(value)
```

Set custom model data.

- **Parameters:**
  - `value` (`int`) — Model data value.
- **Returns:** `Awaitable[None]`

### set_attributes

```python
await item.set_attributes(attributes)
```

Set attribute modifiers.

- **Parameters:**
  - `attributes` (`list[dict]`) — Attribute modifier list.
- **Returns:** `Awaitable[None]`

### set_nbt

```python
await item.set_nbt(nbt)
```

Set raw NBT data.

- **Parameters:**
  - `nbt` (`dict`) — NBT data dictionary.
- **Returns:** `Awaitable[None]`

### clone

```python
copy = await item.clone()
```

Create a deep copy of this item.

- **Returns:** `Awaitable[`[`Item`](#)`]`

### is_similar

```python
result = await item.is_similar(other)
```

Check if two items are similar (same type, name, lore — ignoring amount).

- **Parameters:**
  - `other` ([`Item`](#)) — The item to compare.
- **Returns:** `Awaitable[bool]`
