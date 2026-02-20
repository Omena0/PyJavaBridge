---
title: Potion
subtitle: Legacy potion API
---

# Potion

The `Potion` class provides a legacy interface for applying potion effects. For new code, prefer using [`Effect`](effect.md) directly.

---

## Class Methods

### apply

```python
await Potion.apply(player, effect_type=None, duration=0, amplifier=0, ambient=False, particles=True, icon=True)
```

Apply a potion effect to a player. This is functionally identical to [`Effect.apply`](effect.md#apply).

- **Parameters:**
  - `player` ([`Player`](player.md)) — Target player.
  - `effect_type` ([`EffectType`](enums.md) `| str | None`) — Effect type.
  - `duration` (`int`) — Duration in ticks (20 ticks = 1 second). Default 0.
  - `amplifier` (`int`) — Effect level minus 1. Default 0.
  - `ambient` (`bool`) — Beacon-style translucent particles. Default `False`.
  - `particles` (`bool`) — Show particles. Default `True`.
  - `icon` (`bool`) — Show HUD icon. Default `True`.
- **Returns:** `Awaitable[Any]`

```python
await Potion.apply(player, "POISON", duration=100, amplifier=0)
```

---

## Attributes

### type

- **Type:** `Any`

The potion's effect type.

### level

- **Type:** `int`

The potion level.

---

## Recommendation

Use [`Effect`](effect.md) for all new code:

```python
# Preferred
await Effect.apply(player, "SPEED", duration=600, amplifier=1)

# Legacy (still works)
await Potion.apply(player, "SPEED", duration=600, amplifier=1)
```

Both are equivalent, but `Effect` provides additional methods like `with_duration()` and `with_amplifier()`.
