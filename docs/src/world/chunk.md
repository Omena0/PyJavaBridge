---
title: Chunk
subtitle: World chunk API
---

# Chunk

A `Chunk` represents a 16×256×16 (or 16×384×16 in 1.18+) column of blocks in a world. Use it to force-load or release terrain.

---

## Constructor

```python
Chunk(world=None, x=None, z=None)
```

Reference a chunk by world and chunk coordinates.

- **Parameters:**
  - `world` ([`World`](world.md) `| str | None`) — The world.
  - `x` (`int | None`) — Chunk X coordinate (block X ÷ 16).
  - `z` (`int | None`) — Chunk Z coordinate (block Z ÷ 16).

> **Note:** Chunk coordinates are block coordinates divided by 16. A block at X=100 is in chunk X=6.

```python
chunk = Chunk("world", 5, 10)
```

You can also get a chunk from a world:

```python
chunk = await world.chunk_at(5, 10)
```

---

## Attributes

### x

- **Type:** `int`

Chunk X coordinate.

### z

- **Type:** `int`

Chunk Z coordinate.

### world

- **Type:** [`World`](world.md)

The world this chunk is in.

### is_loaded

- **Type:** `bool`

Whether this chunk is currently loaded in memory.

---

## Methods

### load

```python
result = await chunk.load()
```

Force-load this chunk into memory. If the chunk is already loaded, this is a no-op.

- **Returns:** `Awaitable[bool]` — `True` if the chunk was loaded successfully.

```python
chunk = await world.chunk_at(0, 0)
await chunk.load()
```

### unload

```python
result = await chunk.unload()
```

Allow this chunk to be unloaded from memory. The server will unload it when no players are nearby.

- **Returns:** `Awaitable[bool]` — `True` if the chunk was unloaded successfully.

> **Warning:** Unloading a chunk with players in it may cause issues. Only unload chunks you know are safe to release.
