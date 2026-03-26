---
title: Recipe
subtitle: Custom crafting and smelting recipes
---

# Recipe

Register custom crafting and smelting recipes. All methods are static — no need to instantiate.

---

## Methods

### shaped

```python
await Recipe.shaped(key, result, shape, ingredients, amount=1)
```

Register a shaped crafting recipe.

- **Parameters:**
  - `key` (`str`) — Unique recipe identifier.
  - `result` (`Material` `| str`) — Material of the crafted item.
  - `shape` (`list[str]`) — 1–3 strings representing crafting grid rows. Use single characters as placeholders and spaces for empty slots.
  - `ingredients` (`dict[str, Material | str]`) — Maps each character in `shape` to a material.
  - `amount` (`int`) — Number of items produced (default `1`).
- **Returns:** `Awaitable[str]` — The recipe key.

```python
# Diamond sword from sticks and emeralds
await Recipe.shaped("emerald_sword", Material.DIAMOND_SWORD, [
    "E",
    "E",
    "S"
], {
    "E": Material.EMERALD,
    "S": Material.STICK
})
```

```python
# 4 TNT from sand and gunpowder
await Recipe.shaped("easy_tnt", "TNT", [
    "SG",
    "GS"
], {
    "S": "SAND",
    "G": "GUNPOWDER"
}, amount=4)
```

### shapeless

```python
await Recipe.shapeless(key, result, ingredients, amount=1)
```

Register a shapeless crafting recipe (ingredients can go in any slot).

- **Parameters:**
  - `key` (`str`) — Unique recipe identifier.
  - `result` (`Material` `| str`) — Material of the crafted item.
  - `ingredients` (`list[Material | str]`) — List of required materials.
  - `amount` (`int`) — Number of items produced (default `1`).
- **Returns:** `Awaitable[str]` — The recipe key.

```python
# Combine 4 diamonds into an emerald
await Recipe.shapeless("diamond_to_emerald", Material.EMERALD, [
    Material.DIAMOND, Material.DIAMOND,
    Material.DIAMOND, Material.DIAMOND
])
```

### furnace

```python
await Recipe.furnace(key, input, result, experience=0, cook_time=200, amount=1)
```

Register a furnace smelting recipe.

- **Parameters:**
  - `key` (`str`) — Unique recipe identifier.
  - `input` (`Material` `| str`) — Material to smelt.
  - `result` (`Material` `| str`) — Material produced.
  - `experience` (`float`) — XP awarded per smelt (default `0`).
  - `cook_time` (`int`) — Cook time in ticks (default `200` = 10 seconds).
  - `amount` (`int`) — Number of items produced (default `1`).
- **Returns:** `Awaitable[str]` — The recipe key.

```python
# Smelt gravel into flint
await Recipe.furnace("gravel_to_flint", Material.GRAVEL, Material.FLINT, experience=0.1)

# Fast-cook cobblestone into stone (5 seconds)
await Recipe.furnace("fast_stone", "COBBLESTONE", "STONE", cook_time=100)
```

### remove

```python
await Recipe.remove(key)
```

Remove a previously registered custom recipe.

- **Parameters:**
  - `key` (`str`) — The recipe key used during registration.
- **Returns:** `Awaitable[bool]` — Whether the recipe was found and removed.

```python
await Recipe.remove("emerald_sword")
```
