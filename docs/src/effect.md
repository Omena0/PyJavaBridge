---
title: Effect
subtitle: Potion effects API
---

# Effect

An `Effect` represents a potion effect (speed, strength, invisibility, etc.) that can be applied to players. Effects have a type, duration, amplifier, and visual settings.

---

## Constructor

```python
Effect(effect_type=None, duration=0, amplifier=0, ambient=False, particles=True, icon=True)
```

Create an effect.

- **Parameters:**
  - `effect_type` ([`EffectType`](enums.md) `| str | None`) — The effect type (e.g. `"SPEED"`, `EffectType.INVISIBILITY`).
  - `duration` (`int`) — Duration in ticks (20 ticks = 1 second). Default 0.
  - `amplifier` (`int`) — Effect level minus 1. Speed II = amplifier 1. Default 0.
  - `ambient` (`bool`) — Whether the effect came from a beacon (translucent particles). Default `False`.
  - `particles` (`bool`) — Whether to show particles. Default `True`.
  - `icon` (`bool`) — Whether to show the effect icon in the HUD. Default `True`.

```python
speed = Effect("SPEED", duration=600, amplifier=1)         # Speed II for 30 seconds
invis = Effect(EffectType.INVISIBILITY, duration=1200)      # Invisibility for 60 seconds
silent = Effect("REGENERATION", 200, particles=False, icon=False) # Hidden regen
```

---

## Class Methods

### apply

```python
await Effect.apply(player, effect_type=None, duration=0, amplifier=0, ambient=False, particles=True, icon=True)
```

Create and apply an effect to a player in one call.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Target player.
  - `effect_type` ([`EffectType`](enums.md) `| str | None`) — Effect type.
  - `duration` (`int`) — Duration in ticks. Default 0.
  - `amplifier` (`int`) — Effect level minus 1. Default 0.
  - `ambient` (`bool`) — Beacon-style particles. Default `False`.
  - `particles` (`bool`) — Show particles. Default `True`.
  - `icon` (`bool`) — Show icon. Default `True`.
- **Returns:** `Awaitable[Any]`

```python
await Effect.apply(player, "SPEED", duration=600, amplifier=1)
```

---

## Attributes

### type

- **Type:** [`EffectType`](enums.md)

The effect type.

### duration

- **Type:** `int`

Remaining duration in ticks.

### amplifier

- **Type:** `int`

Effect amplifier (level minus 1).

### ambient

- **Type:** `bool`

Whether particles are translucent (beacon-style).

### particles

- **Type:** `bool`

Whether particles are visible.

### icon

- **Type:** `bool`

Whether the HUD icon is shown.

---

## Methods

### with_duration

```python
new_effect = await effect.with_duration(duration)
```

Create a copy of this effect with a different duration.

- **Parameters:**
  - `duration` (`int`) — New duration in ticks.
- **Returns:** `Awaitable[`[`Effect`](#)`]`

```python
base = Effect("SPEED", 100, amplifier=2)
long_speed = await base.with_duration(6000)  # 5 minutes
```

### with_amplifier

```python
new_effect = await effect.with_amplifier(amplifier)
```

Create a copy of this effect with a different amplifier.

- **Parameters:**
  - `amplifier` (`int`) — New amplifier.
- **Returns:** `Awaitable[`[`Effect`](#)`]`

---

## Applying to Players

You can apply effects in two ways:

```python
# 1. Using the class method shortcut
await Effect.apply(player, "SPEED", duration=200, amplifier=1)

# 2. Construct then apply via Player
speed = Effect("SPEED", duration=200, amplifier=1)
await player.add_effect(speed)
```

To remove an effect:

```python
await player.remove_effect(EffectType.SPEED)
```

To list active effects:

```python
for effect in player.effects:
    print(f"{effect.type.name}: {effect.duration} ticks remaining")
```

---

## Duration Reference

| Duration | Ticks |
|----------|-------|
| 1 second | 20 |
| 5 seconds | 100 |
| 30 seconds | 600 |
| 1 minute | 1200 |
| 5 minutes | 6000 |
| 10 minutes | 12000 |
