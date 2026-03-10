---
title: Block
subtitle: Block in the world
---

# Block

A `Block` represents a single block in the world. You get block references from [`World.block_at()`](world.md#block_at) or event properties.

---

## Constructor

```python
Block(world=None, x=None, y=None, z=None, material=None)
```

Create a block reference.

- **Parameters:**
  - `world` ([`World`](world.md) `| str | None`) — World reference.
  - `x` (`int | None`) — X coordinate.
  - `y` (`int | None`) — Y coordinate.
  - `z` (`int | None`) — Z coordinate.
  - `material` ([`Material`](enums.md) `| str | None`) — Block material.

---

## Class Methods

### create

```python
block = await Block.create(location, material)
```

Create (place) a block at a location.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Where to place the block.
  - `material` ([`Material`](enums.md) `| str`) — Block material.
- **Returns:** `Awaitable[`[`Block`](#)`]`

```python
block = await Block.create(player.location.add(0, -1, 0), Material.DIAMOND_BLOCK)
```

---

## Attributes

### x

- **Type:** `int`

Block X coordinate.

### y

- **Type:** `int`

Block Y coordinate.

### z

- **Type:** `int`

Block Z coordinate.

### type

- **Type:** [`Material`](enums.md)

The block's material type.

### location

- **Type:** [`Location`](location.md)

The block's location.

### world

- **Type:** [`World`](world.md)

The world this block is in.

### is_solid

- **Type:** `bool`

Whether the block is solid (not air, water, etc.).

### data

- **Type:** `any`
- **Settable:** `block.data = value`

The block's data state (e.g., slab halves, stair direction). Varies by block type.

### light_level

- **Type:** `int`

Light level at this block (0–15).

### biome

- **Type:** [`Biome`](enums.md)
- **Settable:** `block.biome = Biome.DESERT`

The biome at this block's location.

### hardness

- **Type:** `float`

The block's hardness (mining resistance). Read-only.

### blast_resistance

- **Type:** `float`

The block's explosion resistance. Read-only.

### is_passable

- **Type:** `bool`

Whether entities can pass through this block.

### is_liquid

- **Type:** `bool`

Whether this block is a liquid (water/lava).

### drops

- **Type:** `list`

The block's natural drops list.

---

## Methods

### break_naturally

```python
await block.break_naturally()
```

Break the block as if a player mined it (drops items).

- **Returns:** `Awaitable[None]`

### set_type

```python
await block.set_type(material)
```

Change the block's material.

- **Parameters:**
  - `material` ([`Material`](enums.md)) — The new material.
- **Returns:** `Awaitable[None]`

```python
await block.set_type(Material.AIR)  # Delete the block
```

### set_data

```python
await block.set_data(data)
```

Set the block's data state. You can also use property syntax: `block.data = value`.

- **Parameters:**
  - `data` (`any`) — Block data value.
- **Returns:** `Awaitable[None]`

### get_drops

```python
drops = await block.get_drops(tool=None)
```

Get the block's drops with an optional tool.

- **Parameters:**
  - `tool` ([`Item`](item.md) `| None`) — The tool used to mine. `None` for bare hand.
- **Returns:** `Awaitable[list]`

---

## Container Properties

These work on blocks that hold inventories (chests, hoppers, dispensers, droppers, barrels, etc.).

### inventory

- **Type:** [`Inventory`](inventory.md) `| None`

The block's inventory, or `None` if the block isn't a container.

```python
chest = world.block_at(10, 64, 20)
inv = chest.inventory
if inv:
    items = inv.contents
```

### is_container

- **Type:** `bool`

Whether this block has an inventory.

### state_type

- **Type:** `str`

The tile entity type name (e.g. `"Sign"`, `"Chest"`, `"Furnace"`, `"Hopper"`).

---

## Sign Methods

These work on sign blocks (oak sign, birch sign, etc.). Properties return `None` if the block isn't a sign.

### sign_lines

- **Type:** `list[str] | None`
- **Settable:** `block.sign_lines = ["Line 1", "Line 2", "", ""]`

Front side text as a list of 4 strings.

```python
sign = world.block_at(10, 64, 20)
lines = sign.sign_lines  # ["Hello", "World", "", ""]
```

### sign_back_lines

- **Type:** `list[str] | None`
- **Settable:** `block.sign_back_lines = ["Back", "Text", "", ""]`

Back side text as a list of 4 strings.

### is_sign_glowing

- **Type:** `bool | None`
- **Settable:** `block.is_sign_glowing = True`

Whether the front sign text is glowing. `None` if not a sign.

### set_sign_line

```python
await block.set_sign_line(index, text)
```

Set a single front sign line.

- **Parameters:**
  - `index` (`int`) — Line index (0–3).
  - `text` (`str`) — Line text.
- **Returns:** `Awaitable[None]`

### set_sign_lines

```python
await block.set_sign_lines(lines)
```

Set all front sign lines at once. You can also use property syntax: `block.sign_lines = [...]`.

- **Parameters:**
  - `lines` (`list[str]`) — Up to 4 lines.
- **Returns:** `Awaitable[None]`

```python
await sign.set_sign_lines(["Welcome", "to the", "shop!", ""])
```

### set_sign_back_line / set_sign_back_lines

Same as front-side methods, but for the back of the sign. Property syntax: `block.sign_back_lines = [...]`.

### set_sign_glowing

```python
await block.set_sign_glowing(glowing)
```

Set whether the front sign text glows. You can also use property syntax: `block.is_sign_glowing = True`.

- **Parameters:**
  - `glowing` (`bool`) — Whether text should glow.
- **Returns:** `Awaitable[None]`

---

## Furnace Methods

These work on furnace blocks (furnace, blast furnace, smoker). Properties return `None` if the block isn't a furnace.

### furnace_burn_time

- **Type:** `int | None`
- **Settable:** `block.furnace_burn_time = 200`

Remaining fuel burn time in ticks.

### furnace_cook_time

- **Type:** `int | None`
- **Settable:** `block.furnace_cook_time = 100`

Current cooking progress in ticks.

### furnace_cook_time_total

- **Type:** `int | None`

Total cook time needed for the current item.

### set_furnace_burn_time

```python
await block.set_furnace_burn_time(ticks)
```

Set remaining fuel burn time. Property syntax: `block.furnace_burn_time = ticks`.

- **Parameters:**
  - `ticks` (`int`) — Burn time in ticks.
- **Returns:** `Awaitable[None]`

### set_furnace_cook_time

```python
await block.set_furnace_cook_time(ticks)
```

Set cooking progress. Property syntax: `block.furnace_cook_time = ticks`.

- **Parameters:**
  - `ticks` (`int`) — Cook time in ticks.
- **Returns:** `Awaitable[None]`

```python
furnace = world.block_at(10, 64, 20)
if furnace.state_type == "Furnace":
    print(f"Cook progress: {furnace.furnace_cook_time}/{furnace.furnace_cook_time_total}")
    inv = furnace.inventory
```

### set_biome

```python
await block.set_biome(biome)
```

Change the biome at this block's position. Property syntax: `block.biome = Biome.DESERT`.

- **Parameters:**
  - `biome` ([`Biome`](enums.md)) — The new biome.
- **Returns:** `Awaitable[None]`

---

## Persistent Data Container (PDC)

Store custom data on blocks that persists across restarts.

### get_persistent_data

```python
data = await block.get_persistent_data()
```

Get all persistent data as a dictionary.

- **Returns:** `Awaitable[dict]`

### set_persistent_data

```python
await block.set_persistent_data(key, value)
```

Set a persistent data key.

- **Parameters:**
  - `key` (`str`) — The data key.
  - `value` (`str`) — The data value.
- **Returns:** `Awaitable[None]`

### remove_persistent_data

```python
await block.remove_persistent_data(key)
```

Remove a persistent data key.

- **Parameters:**
  - `key` (`str`) — The key to remove.
- **Returns:** `Awaitable[None]`

```python
await block.set_persistent_data("owner", player.name)
data = await block.get_persistent_data()
print(data["owner"])  # "Steve"
```
