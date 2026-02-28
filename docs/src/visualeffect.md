---
title: VisualEffect [ext]
subtitle: Sequenced particle/sound effects
---

# VisualEffect [ext]

`VisualEffect` chains multiple visual/audible steps into a reusable sequence.

```python
from bridge.extensions import VisualEffect
```

---

## Constructor

```python
VisualEffect(name="effect")
```

---

## Methods

### add_step(func)

Imperatively add a step callable.

### trigger(location) → Awaitable

Play the full sequence at the given location.

---

## Decorators

### @effect.step

```python
vfx = VisualEffect("explosion")

@vfx.step
async def boom(loc):
    await server.spawn_particle("EXPLOSION_LARGE", loc, count=5)
    await server.after(5)

@vfx.step
async def sound(loc):
    await server.play_sound(loc, "ENTITY_GENERIC_EXPLODE")
```

Then trigger it:

```python
await vfx.trigger(some_location)
```
