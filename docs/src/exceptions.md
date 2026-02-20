---
title: Exceptions
subtitle: Error types raised by the bridge
---

# Exceptions

The bridge defines a small exception hierarchy for errors that originate from the Java side.

---

## BridgeError

```python
class BridgeError(Exception)
```

Base exception for all bridge-related errors. Catch this to handle any error that comes from the Java ↔ Python communication layer.

```python
try:
    await entity.teleport(location)
except BridgeError as e:
    print(f"Bridge call failed: {e}")
```

---

## EntityGoneException

```python
class EntityGoneException(BridgeError)
```

Raised when you try to interact with an entity that no longer exists on the server. This happens when:

- The entity was killed or removed between when you got the reference and when you used it.
- The entity's chunk was unloaded.
- The entity despawned naturally.

```python
from bridge import *

@event
async def entity_damage(e):
    await server.wait(20)  # Wait 1 second
    try:
        await e.entity.set_fire_ticks(100)
    except EntityGoneException:
        # Entity died or despawned during the wait
        pass
```

### When to expect it

Any awaitable method on `Entity` or `Player` can raise `EntityGoneException` if the underlying Java entity has been garbage collected. This is especially common when:

- You store entity references across ticks
- You use `server.wait()` between getting a reference and using it
- You handle events where the entity might die (e.g. `entity_damage`)

### Best practice

If you need to use an entity reference after a delay, check `is_valid` first or wrap the call in a try/except:

```python
if entity.is_valid:
    await entity.teleport(location)
```
