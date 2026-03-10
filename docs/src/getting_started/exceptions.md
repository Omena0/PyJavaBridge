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
    await server.after(20)  # Wait 1 second
    try:
        await e.entity.set_fire_ticks(100)
    except EntityGoneException:
        # Entity died or despawned during the wait
        pass
```

### When to expect it

Any awaitable method on `Entity` or `Player` can raise `EntityGoneException` if the underlying Java entity has been garbage collected. This is especially common when:

- You store entity references across ticks
- You use `server.after()` between getting a reference and using it
- You handle events where the entity might die (e.g. `entity_damage`)

---

## ConnectionError

```python
class ConnectionError(BridgeError)
```

Raised when the bridge connection is lost or unavailable. This happens during shutdown or if the Java side crashes.

---

## TimeoutError

```python
class TimeoutError(BridgeError)
```

Raised when a call to Java doesn't respond within the timeout period. Usually indicates the server is badly lagging.

---

## AtomicAbortError

```python
class AtomicAbortError(BridgeError)
```

Raised when an `atomic()` batch is aborted because one of its operations failed. All operations in the batch are rolled back.

---

## PlayerOfflineException

```python
class PlayerOfflineException(BridgeError)
```

Raised when targeting a player who has disconnected.

---

## WorldNotLoadedException

```python
class WorldNotLoadedException(BridgeError)
```

Raised when accessing a world that isn't loaded.

---

## ChunkNotLoadedException

```python
class ChunkNotLoadedException(BridgeError)
```

Raised when accessing a chunk that isn't loaded.

---

## InvalidLocationError

```python
class InvalidLocationError(BridgeError)
```

Raised when a location is invalid or missing required fields (e.g. no world).

---

## InvalidMaterialError

```python
class InvalidMaterialError(BridgeError)
```

Raised when a material name doesn't match any known Minecraft material.

---

## InvalidItemError

```python
class InvalidItemError(BridgeError)
```

Raised when an item operation is invalid.

---

## MethodNotFoundError

```python
class MethodNotFoundError(BridgeError)
```

Raised when calling a method that doesn't exist on the target Java object.

---

## ClassNotFoundError

```python
class ClassNotFoundError(BridgeError)
```

Raised when a Java class cannot be found (e.g. in `reflect.clazz()`).

---

## AccessDeniedError

```python
class AccessDeniedError(BridgeError)
```

Raised when the bridge cannot access a method or field due to Java access controls.

---

## InvalidEventError

```python
class InvalidEventError(BridgeError)
```

Raised when subscribing to an event name that doesn't correspond to a valid Bukkit event.

---

## CommandRegistrationError

```python
class CommandRegistrationError(BridgeError)
```

Raised when command registration fails.

---

## ConfigError

```python
class ConfigError(BridgeError)
```

Raised when a config read/write operation fails.

---

## UnsupportedFormatError

```python
class UnsupportedFormatError(BridgeError)
```

Raised when a file format is not supported (e.g. unknown config file extension).

---

## InvalidEnumError

```python
class InvalidEnumError(BridgeError)
```

Raised when an enum value doesn't match any known constant.

---

## SlotOutOfRangeError

```python
class SlotOutOfRangeError(BridgeError)
```

Raised when an inventory slot index is out of range.

---

## PermissionError

```python
class PermissionError(BridgeError)
```

Raised when a permission check fails.

---

## Java Stack Traces

All exceptions from the Java side include the full Java stack trace when available. Access it via the `java_stacktrace` attribute:

```python
try:
    await entity.some_method()
except BridgeError as e:
    print(e)                    # Includes Java stacktrace in message
    print(e.java_stacktrace)   # Just the stacktrace, or None
```

### Best practice

If you need to use an entity reference after a delay, check `is_valid` first or wrap the call in a try/except:

```python
if entity.is_valid:
    await entity.teleport(location)
```
