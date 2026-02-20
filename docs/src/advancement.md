---
title: Advancement
subtitle: Advancement grant/revoke API
---

# Advancement

The `Advancement` class lets you grant or revoke Minecraft advancements (achievements) for players, and inspect their progress.

---

## Class Methods

### grant

```python
progress = await Advancement.grant(player, key)
```

Grant an advancement to a player (awards all remaining criteria).

- **Parameters:**
  - `player` ([`Player`](player.md)) — Target player.
  - `key` (`str`) — Advancement key in `namespace:path` format.
- **Returns:** `Awaitable[`[`AdvancementProgress`](#advancementprogress)`]`

```python
progress = await Advancement.grant(player, "minecraft:story/mine_stone")
```

### revoke

```python
progress = await Advancement.revoke(player, key)
```

Revoke an advancement from a player (removes all awarded criteria).

- **Parameters:**
  - `player` ([`Player`](player.md)) — Target player.
  - `key` (`str`) — Advancement key in `namespace:path` format.
- **Returns:** `Awaitable[`[`AdvancementProgress`](#advancementprogress)`]`

```python
await Advancement.revoke(player, "minecraft:story/mine_stone")
```

---

## Attributes

### key

- **Type:** `Any`

The advancement's namespaced key.

---

## AdvancementProgress

Returned by `grant()` and `revoke()`, this object tracks per-criterion completion.

### Attributes

#### is_done

- **Type:** `bool`

Whether all criteria have been awarded.

#### remaining_criteria

- **Type:** `set[str]`

Criteria names that have not been awarded yet.

#### awarded_criteria

- **Type:** `set[str]`

Criteria names that have been awarded.

### Methods

#### award_criteria

```python
result = await progress.award_criteria(name)
```

Award a single criterion.

- **Parameters:**
  - `name` (`str`) — Criterion name.
- **Returns:** `Awaitable[bool]` — `True` if the criterion was newly awarded.

#### revoke_criteria

```python
result = await progress.revoke_criteria(name)
```

Revoke a single criterion.

- **Parameters:**
  - `name` (`str`) — Criterion name.
- **Returns:** `Awaitable[bool]` — `True` if the criterion was newly revoked.

---

## Common Advancement Keys

| Key | Description |
|-----|-------------|
| `minecraft:story/mine_stone` | Mine stone with a pickaxe |
| `minecraft:story/upgrade_tools` | Craft a stone pickaxe |
| `minecraft:story/smelt_iron` | Smelt an iron ingot |
| `minecraft:story/obtain_armor` | Craft any armor piece |
| `minecraft:story/enter_the_nether` | Enter the Nether |
| `minecraft:story/enter_the_end` | Enter the End |
| `minecraft:end/kill_dragon` | Kill the Ender Dragon |

You can also use `server.get_advancement(key)` to get the advancement object:

```python
adv = await server.get_advancement("minecraft:story/mine_stone")
```
