---
title: BlockSnapshot
subtitle: Capture and restore regions of blocks
---

# BlockSnapshot

`BlockSnapshot` captures a region of blocks and can restore them later, optionally spread across ticks to avoid lag.

```python
from bridge import BlockSnapshot, World

world = World("world")

# Capture a 10x10x10 region
snap = BlockSnapshot.capture(world, 0, 60, 0, 10, 70, 10)

# ... make changes to the area ...

# Restore the original blocks
await snap.restore()
```

## Class Methods

### BlockSnapshot.capture(world, x1, y1, z1, x2, y2, z2)

Capture all blocks within a cuboid region.

- **Parameters:**
  - `world` *(World)* — The world to capture from.
  - `x1, y1, z1` *(int)* — First corner coordinates.
  - `x2, y2, z2` *(int)* — Second corner coordinates.
- **Returns:** `BlockSnapshot`

```python
snap = BlockSnapshot.capture(world, -5, 60, -5, 5, 70, 5)
print(len(snap))  # number of blocks captured
```

## Properties

### .blocks

A copy of the captured block data.

- **Type:** `list[dict]`
- **Read-only**

## Methods

### await .restore(blocks_per_tick=256)

Restore captured blocks, spread across ticks to avoid lag spikes.

- **Parameters:**
  - `blocks_per_tick` *(int)* — Maximum blocks to restore per tick. Default `256`.
- **Returns:** `Awaitable[None]`

```python
# Restore slowly to minimize lag
await snap.restore(blocks_per_tick=64)
```

## Special Methods

### len(snapshot)

Returns the number of captured blocks.

```python
snap = BlockSnapshot.capture(world, 0, 60, 0, 10, 70, 10)
print(f"Captured {len(snap)} blocks")
```
