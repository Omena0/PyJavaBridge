---
title: ItemBuilder
subtitle: Fluent item construction
---

# ItemBuilder

A fluent builder for constructing `Item` objects. Every setter method returns `self`, allowing chained calls.

---

## Constructor

```python
ItemBuilder(material)
```

Start building an item with the given material.

- **Parameters:**
  - `material` (`Material` `| str`) — Item material.

```python
sword = (
    ItemBuilder("DIAMOND_SWORD")
    .name("§6Excalibur")
    .lore("§7Legendary blade", "§7of kings")
    .enchant("SHARPNESS", 5)
    .unbreakable()
    .glow()
    .build()
)
```

---

## Class Methods

### from_item

```python
builder = ItemBuilder.from_item(item)
```

Create a builder pre-filled with settings from an existing item.

- **Parameters:**
  - `item` (`Item`) — Existing item to copy.
- **Returns:** `ItemBuilder`

```python
builder = ItemBuilder.from_item(existing_item)
upgraded = builder.enchant("SHARPNESS", 10).build()
```

---

## Chain Methods

All chain methods return the builder, so you can chain them:

```python
item = (
    ItemBuilder("IRON_CHESTPLATE")
    .name("§bFrost Armor")
    .lore("§7Chills attackers")
    .enchant("PROTECTION", 4)
    .enchant("THORNS", 3)
    .unbreakable()
    .custom_model_data(1001)
    .add_attribute("GENERIC_ARMOR", 12, "ADD_NUMBER")
    .flag("HIDE_ENCHANTS", "HIDE_ATTRIBUTES")
    .build()
)
```

### amount

```python
builder.amount(n)
```

Set the stack size.

- **Parameters:**
  - `n` (`int`) — Stack amount.

### name

```python
builder.name(n)
```

Set the display name.

- **Parameters:**
  - `n` (`str`) — Display name. Supports `§` color codes.

### lore

```python
builder.lore(*lines)
```

Set lore lines (replaces any existing lore).

- **Parameters:**
  - `*lines` (`str`) — One or more lore lines.

### add_lore

```python
builder.add_lore(line)
```

Append a single lore line.

- **Parameters:**
  - `line` (`str`) — Lore line to add.

### enchant

```python
builder.enchant(enchantment, level=1)
```

Add an enchantment.

- **Parameters:**
  - `enchantment` (`str`) — Enchantment name (e.g. `"SHARPNESS"`, `"PROTECTION"`).
  - `level` (`int`) — Enchantment level. Default 1.

### unbreakable

```python
builder.unbreakable(value=True)
```

Set the unbreakable flag.

- **Parameters:**
  - `value` (`bool`) — Whether the item is unbreakable. Default `True`.

### glow

```python
builder.glow(value=True)
```

Add a glow effect (enchantment glint without visible enchantments).

- **Parameters:**
  - `value` (`bool`) — Whether to add glow. Default `True`.

### custom_model_data

```python
builder.custom_model_data(value)
```

Set custom model data for resource packs.

- **Parameters:**
  - `value` (`int`) — Model data value.

### model

```python
builder.model("myns:item/custom_sword")
```

Set the 1.21.11 `item_model` property which points to a model definition resource.

- **Parameters:**
  - `model` (`str`) — Resource location string (e.g. `"myns:item/custom_sword"`).

### attributes

```python
builder.attributes(attrs)
```

Set attribute modifiers (replaces any existing).

- **Parameters:**
  - `attrs` (`list[dict[str, Any]]`) — Attribute modifier list.

### add_attribute

```python
builder.add_attribute(attribute, amount, operation="ADD_NUMBER")
```

Add a single attribute modifier.

- **Parameters:**
  - `attribute` (`str`) — Attribute name (e.g. `"GENERIC_ARMOR"`, `"GENERIC_ATTACK_DAMAGE"`).
  - `amount` (`float`) — Modifier amount.
  - `operation` (`str`) — Operation type. Default `"ADD_NUMBER"`. Options: `"ADD_NUMBER"`, `"ADD_SCALAR"`, `"MULTIPLY_SCALAR_1"`.

### nbt

```python
builder.nbt(data)
```

Set raw NBT data.

- **Parameters:**
  - `data` (`dict[str, Any]`) — NBT data dictionary.

### flag

```python
builder.flag(*flags)
```

Add item flags to hide information from the tooltip.

- **Parameters:**
  - `*flags` (`str`) — Flag names: `"HIDE_ENCHANTS"`, `"HIDE_ATTRIBUTES"`, `"HIDE_UNBREAKABLE"`, `"HIDE_DESTROYS"`, `"HIDE_PLACED_ON"`, `"HIDE_DYE"`.

---

## build

```python
item = builder.build()
```

Construct the final `Item` from the builder state.

- **Returns:** `Item`

> **Note:** `build()` is synchronous. The resulting `Item` can be used immediately in inventory operations, give, drop, etc.
