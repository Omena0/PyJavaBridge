---
title: Firework
subtitle: Launch fireworks with custom effects
---

# Firework

Launch fireworks with fully customizable effects, colors, and shapes.

---

## Firework.launch

```python
entity = await Firework.launch(location, effects=None, power=1)
```

Spawn a firework rocket at a location.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Where to spawn the firework.
  - `effects` (`list[FireworkEffect | dict] | None`) — List of effects. Defaults to a plain white burst if omitted.
  - `power` (`int`) — Flight duration / height (0–127, default `1`). Higher = goes higher before detonating.
- **Returns:** `Awaitable[`[`Entity`](entity.md)`]`

```python
await Firework.launch(player.location)
```

---

# FireworkEffect

Builder for individual firework effects. Chain methods to configure, then pass to `Firework.launch()`.

```python
effect = FireworkEffect(shape)
```

- **Parameters:**
  - `shape` (`str`) — Effect shape. One of: `BALL`, `BALL_LARGE`, `STAR`, `BURST`, `CREEPER`.

---

## Methods

### colors

```python
effect.colors(*colors)
```

Set the explosion colors.

- **Parameters:**
  - `*colors` — Color names (`"RED"`, `"BLUE"`), hex strings (`"#FF0000"`), RGB tuples (`(255, 0, 0)`), or integers.
- **Returns:** `FireworkEffect` (for chaining)

### fade

```python
effect.fade(*colors)
```

Set the fade-out colors (same formats as `colors()`).

- **Returns:** `FireworkEffect`

### flicker

```python
effect.flicker(value=True)
```

Enable the twinkle/flicker effect.

- **Returns:** `FireworkEffect`

### trail

```python
effect.trail(value=True)
```

Enable particle trails.

- **Returns:** `FireworkEffect`

---

## Examples

### Simple colored firework

```python
effect = FireworkEffect("BALL").colors("RED", "BLUE").trail()
await Firework.launch(player.location, effects=[effect], power=2)
```

### Multiple effects

```python
effects = [
    FireworkEffect("STAR").colors("YELLOW", "ORANGE").flicker(),
    FireworkEffect("BURST").colors("#00FF00").fade("WHITE").trail(),
]
await Firework.launch(location, effects=effects, power=3)
```

### RGB colors

```python
effect = FireworkEffect("BALL_LARGE").colors(
    (255, 0, 128),    # Pink
    (0, 200, 255),    # Cyan
).fade((255, 255, 255)).trail().flicker()

await Firework.launch(player.location.add(0, 5, 0), effects=[effect])
```

### Creeper face

```python
effect = FireworkEffect("CREEPER").colors("GREEN").fade("LIME")
await Firework.launch(player.location, effects=[effect], power=1)
```
