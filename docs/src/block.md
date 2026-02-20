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

The block's data state (e.g., slab halves, stair direction). Varies by block type.

### light_level

- **Type:** `int`

Light level at this block (0–15).

### biome

- **Type:** [`Biome`](enums.md)

The biome at this block's location.

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

Set the block's data state.

- **Parameters:**
  - `data` (`any`) — Block data value.
- **Returns:** `Awaitable[None]`

### set_biome

```python
await block.set_biome(biome)
```

Change the biome at this block's position.

- **Parameters:**
  - `biome` ([`Biome`](enums.md)) — The new biome.
- **Returns:** `Awaitable[None]`
