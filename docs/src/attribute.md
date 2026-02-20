---
title: Attribute
subtitle: Entity attribute modifiers
---

# Attribute

An `Attribute` represents a Minecraft entity attribute (max health, movement speed, attack damage, etc.) and its current value. Use it to modify player or entity stats.

---

## Class Methods

### apply

```python
await Attribute.apply(player, attribute_type, base_value)
```

Set an attribute's base value for a player.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Target player.
  - `attribute_type` ([`AttributeType`](enums.md) `| str`) — Attribute to modify.
  - `base_value` (`float`) — New base value.
- **Returns:** `Awaitable[Any]`

```python
# Set max health to 40 (20 hearts)
await Attribute.apply(player, "GENERIC_MAX_HEALTH", 40.0)

# Double movement speed
await Attribute.apply(player, AttributeType.GENERIC_MOVEMENT_SPEED, 0.2)
```

---

## Attributes

### attribute_type

- **Type:** [`AttributeType`](enums.md)

The type of this attribute.

### value

- **Type:** `float`

The current effective value (base + modifiers).

### base_value

- **Type:** `float`

The base value before modifiers.

---

## Methods

### set_base_value

```python
await attribute.set_base_value(value)
```

Change the base value of this attribute.

- **Parameters:**
  - `value` (`float`) — New base value.
- **Returns:** `Awaitable[None]`

---

## Common Attribute Types

| AttributeType | Default | Description |
|---------------|---------|-------------|
| `GENERIC_MAX_HEALTH` | 20.0 | Maximum health (1.0 = half heart) |
| `GENERIC_MOVEMENT_SPEED` | 0.1 | Walk speed |
| `GENERIC_ATTACK_DAMAGE` | 1.0 | Base melee damage |
| `GENERIC_ATTACK_SPEED` | 4.0 | Attack cooldown speed |
| `GENERIC_ARMOR` | 0.0 | Armor points |
| `GENERIC_ARMOR_TOUGHNESS` | 0.0 | Armor toughness |
| `GENERIC_KNOCKBACK_RESISTANCE` | 0.0 | Knockback resistance (0–1) |
| `GENERIC_LUCK` | 0.0 | Luck for loot tables |
| `GENERIC_FLYING_SPEED` | 0.4 | Creative fly speed |

```python
# Tank build
await Attribute.apply(player, "GENERIC_MAX_HEALTH", 40.0)
await Attribute.apply(player, "GENERIC_ARMOR", 20.0)
await Attribute.apply(player, "GENERIC_KNOCKBACK_RESISTANCE", 0.5)

# Speed runner build
await Attribute.apply(player, "GENERIC_MOVEMENT_SPEED", 0.2)
await Attribute.apply(player, "GENERIC_ATTACK_SPEED", 8.0)
```
