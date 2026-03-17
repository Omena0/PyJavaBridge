---
title: LootTable
subtitle: Custom loot tables with weights, conditions, and rolls
---

# LootTable [ext]

`LootTable` defines custom loot generation with weighted pools, per-entry conditions, and luck-based bonus rolls.

```python
from bridge.extensions import LootTable

loot = LootTable("dungeon_chest")

common = loot.add_pool("common", rolls=3)
common.add("IRON_INGOT", weight=10, min_amount=1, max_amount=5)
common.add("GOLD_INGOT", weight=5, min_amount=1, max_amount=3)
common.add("DIAMOND", weight=1)

items = loot.generate()
# -> [{"material": "IRON_INGOT", "amount": 3}, ...]
```

## Import

```python
from bridge.extensions import LootTable, LootPool, LootEntry
```

## LootTable

### Constructor

```python
loot = LootTable(name="loot_table")
```

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `pools` | `list[LootPool]` | All pools in this table (read-only) |

### Methods

#### .add_pool(name="pool", rolls=1, bonus_rolls=0)

Add a loot pool.

- **Parameters:**
  - `name` *(str)* — Pool identifier.
  - `rolls` *(int)* — Number of items to pick per generation. Default `1`.
  - `bonus_rolls` *(int)* — Extra rolls scaled by luck. Default `0`.
- **Returns:** `LootPool`

#### .get_pool(name)

- **Returns:** `LootPool | None`

#### .remove_pool(name)

Remove a pool by name.

#### .generate(context=None, luck=0.0)

Generate loot from all pools.

- **Parameters:**
  - `context` — Arbitrary data passed to condition functions.
  - `luck` *(float)* — Luck factor for bonus rolls.
- **Returns:** `list[dict]` — Item dicts with `"material"` and `"amount"` keys.

#### .generate_into(inventory, context=None, luck=0.0)

Generate loot and insert directly into an inventory.

- **Parameters:**
  - `inventory` (`Inventory`) — Target inventory.
  - `context` *(Any)* — Context passed to conditions.
  - `luck` *(float)* — Luck factor for bonus rolls.
- **Returns:** `list[Item]` — Inserted items.

Items are spread across random slots (vanilla-style chest distribution).

#### .generate_stacked(context=None, luck=0.0)

Generate loot and combine items of the same material into stacks.

- **Returns:** `list[dict]` — Stacked item dicts.

---

## LootPool

A pool of weighted entries.

### Constructor

```python
pool = LootPool(name="pool", rolls=1, bonus_rolls=0)
```

### Methods

#### .add(item, weight=1, min_amount=1, max_amount=1, condition=None)

Add an entry to this pool.

- **Parameters:**
  - `item` — Material name string, `Item` object, or item dict (`{"material": ..., "amount": ...}`).
  - `weight` *(int)* — Relative probability weight. Default `1`.
  - `min_amount` *(int)* — Minimum stack size. Default `1`.
  - `max_amount` *(int)* — Maximum stack size. Default `1`.
  - `condition` *(Callable | None)* — Optional `(context) -> bool` condition.
- **Returns:** `LootEntry`

#### .entry(item, weight=1, min_amount=1, max_amount=1, condition=None)

Decorator-style entry registration. The decorated function becomes the condition.

```python
@pool.entry("ENCHANTED_GOLDEN_APPLE", weight=1)
def only_hard(ctx):
    return ctx.get("difficulty") == "hard"
```

#### .generate(context=None, luck=0.0)

Generate loot from this pool only.

- **Returns:** `list[dict]`

#### .generate_into(inventory, context=None, luck=0.0)

Generate pool loot and insert into an inventory.

- **Parameters:**
  - `inventory` (`Inventory`) — Target inventory.
  - `context` *(Any)* — Context passed to conditions.
  - `luck` *(float)* — Luck factor for bonus rolls.
- **Returns:** `list[Item]`

Items are spread across random slots (vanilla-style chest distribution).

---

## LootEntry

A single weighted entry.

### Constructor

```python
entry = LootEntry(item, weight=1, min_amount=1, max_amount=1, condition=None)
```

### Attributes

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `item` | `Any` | Material name or item dict |
| `weight` | `int` | Relative probability (min 1) |
| `min_amount` | `int` | Minimum stack size |
| `max_amount` | `int` | Maximum stack size |
| `condition` | `Callable \| None` | Condition function |

---

## Full Example

```python
from bridge import *
from bridge.extensions import LootTable

loot = LootTable("boss_drops")

# Common drops (3 rolls)
common = loot.add_pool("common", rolls=3)
common.add("IRON_INGOT", weight=10, min_amount=2, max_amount=8)
common.add("GOLD_INGOT", weight=5, min_amount=1, max_amount=4)
common.add("EXPERIENCE_BOTTLE", weight=8, min_amount=1, max_amount=3)

# Rare drops (1 roll + 1 bonus with luck)
rare = loot.add_pool("rare", rolls=1, bonus_rolls=1)
rare.add("DIAMOND", weight=5)
rare.add("EMERALD", weight=3, min_amount=1, max_amount=2)
rare.add("NETHERITE_INGOT", weight=1, condition=lambda ctx: ctx.get("boss") == "wither")
rare.add("ENCHANTED_GOLDEN_APPLE", weight=1)

@event("entity_death")
async def on_boss_death(e):
    if e.entity.custom_name and "Boss" in e.entity.custom_name:
        items = loot.generate_stacked(
            context={"boss": "wither"},
            luck=0.5
        )
        for item in items:
            await e.entity.world.drop_item(
                e.entity.location,
                item["material"],
                item.get("amount", 1)
            )
```
