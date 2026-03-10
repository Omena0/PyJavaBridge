---
title: Serialization
subtitle: Object handles, type serialization, and proxy classes
---

# Serialization

How Java objects are converted to JSON for the wire, how Python reconstructs them as proxy objects, and how the object handle registry works.

---

## Object Handles

Java objects that cross the bridge are tracked with integer **handles** in an `ObjectRegistry`.

### Registration flow

1. Java serializes an object → registers it in `ObjectRegistry` → gets handle ID
2. Wire sends: `{"_handle": 42, "_type": "Player", "name": "Steve", "uuid": "...", ...}`
3. Python creates a `ProxyBase` (or subclass) holding handle `42` and pre-populated fields
4. Python calls methods: `{"method": "getName", "handle": 42}`
5. Java looks up handle `42` → gets the Player object → invokes method

### ObjectRegistry internals

```java
public class ObjectRegistry {
    private final Map<Integer, Object> objects = new ConcurrentHashMap<>();
    private final IdentityHashMap<Object, Integer> reverseMap = new IdentityHashMap<>();
    private final AtomicInteger counter = new AtomicInteger(1);
}
```

- **Bidirectional mapping:** `objects` (handle → Java object) + `reverseMap` (Java object → handle)
- **Deduplication:** `register()` checks `reverseMap` first. If the same Java object is serialized again, the existing handle is returned — no duplicate registrations.
- **Identity equality:** Uses `IdentityHashMap`, not `equals()`. Two different Player objects with the same UUID get different handles.
- **Thread-safe reads:** `ConcurrentHashMap` allows lock-free `get()` from any thread.
- **Handle 0:** Reserved for `null`. Never registered.
- **Counter:** `AtomicInteger` starting at 1, monotonically increasing.

### Release

Python proxies queue handle releases when garbage collected:

```python
def __del__(self):
    if self._handle is not None and _connection is not None:
        _connection._queue_release(self._handle)
```

Releases are batched — up to 64 handles accumulate before a flush:

```json
{"type": "release", "handles": [42, 43, 44, 45]}
```

Handle releases are always thread-safe and execute on the bridge thread (no main thread involvement).

### Handle leaks

If Python holds references to proxy objects indefinitely (e.g. in a global list), the Java objects remain in the registry:

- **Memory:** Large objects (inventories, worlds) stay alive
- **Stale entities:** Dead/unloaded entities throw `EntityGoneException` on use
- **Fix:** Remove references when done, or use weak references

---

## Java → Python Serialization

The `BridgeSerializer` converts Java objects to JSON with type-specific field extraction.

### Type-specific fields

Each Bukkit type gets custom serialization:

| Type | Fields |
| ---- | ------ |
| **Player** | `name`, `uuid`, `location`, `world`, `gameMode`, `health`, `foodLevel`, `inventory` |
| **Entity** | `uuid`, `type`, `location`, `world`, `is_projectile`, `shooter`/`owner` |
| **Location** | `x`, `y`, `z`, `yaw`, `pitch`, `world` |
| **Block** | `x`, `y`, `z`, `location`, `type`, `world`, `inventory` (if container) |
| **ItemStack** | `type`, `amount`, `meta` (name, lore, customModelData, attributes, NBT) |
| **Inventory** | `size`, `contents[]`, `holder`, `title` |
| **PotionEffect** | `type`, `duration`, `amplifier`, `ambient`, `particles`, `icon` |
| **Chunk** | `x`, `z`, `world` |

### Special type wrappers

Some types use wrapper objects instead of handles:

- **UUID:** `{"__uuid__": "550e8400-e29b-41d4-a716-446655440000"}`
- **Enums:** `{"__enum__": "org.bukkit.Material", "name": "DIAMOND"}`
- **References:** `{"__ref__": "player", "id": "uuid-string"}` — for lazy resolution without a handle

### Circular reference handling

If an object is encountered during serialization that's already being serialized (circular reference), it gets registered in the `ObjectRegistry` and replaced with just a `{"__handle__": N}` to break the cycle.

### Projectile attribution

For projectile entities, the serializer tries multiple methods to find the shooter/owner:

```graph
getShooter() → getOwner() → getOwningPlayer() → getOwningEntity() → getSummoner()
```

Both the entity reference and cached name/UUID fields are included, so the attribution works even if the shooter entity is no longer loaded.

---

## Python → Java Deserialization

Java deserializes incoming arguments through the `BridgeSerializer`:

### Handle resolution

`{"__handle__": 42}` → `ObjectRegistry.get(42)` → Java object

### Reference resolution

`{"__ref__": "player", "id": "uuid"}` → `Bukkit.getPlayer(UUID)` (live lookup)
`{"__ref__": "world", "id": "world_name"}` → `Bukkit.getWorld(name)`
`{"__ref__": "block", "id": "world:x:y:z"}` → parsed and resolved

### Value object reconstruction

- **Location:** `{x, y, z, yaw, pitch, world}` → `new Location(...)`
- **Vector:** `{x, y, z}` → `new Vector(...)`
- **ItemStack:** Full NBT/meta reconstruction

### Argument type coercion

The reflective fallback (`invokeReflective`) automatically converts arguments to match Java method signatures:

- Python `int` → Java `int`, `long`, `Integer`, `Long`
- Python `float` → Java `float`, `double`, `Float`, `Double`
- Python `str` → Java `String`, `Material` (enum lookup), `Sound` (enum lookup)
- Python `list` → Java arrays or `List<>`
- Python `dict` → Java `Map<>`

---

## Python-Side Deserialization

The `BridgeConnection._deserialize()` method reconstructs Python objects from JSON:

```python
def _deserialize(self, value):
    if isinstance(value, dict):
        if "__handle__" in value:
            return _proxy_from(value)      # ProxyBase or subclass
        if "__uuid__" in value:
            return uuid.UUID(value["__uuid__"])
        if "__enum__" in value:
            return _enum_from(...)         # EnumValue wrapper
        if {"x", "y", "z"}.issubset(value):
            return SimpleNamespace(...)     # Location/Vector
        return {k: deserialize(v) for ...} # Generic dict
    if isinstance(value, list):
        return [deserialize(v) for v in value]
    return value                           # Primitives pass through
```

### Proxy class mapping

The `_proxy_from()` function maps Java type names to Python proxy classes:

| Java Type | Python Class |
| --------- | ------------ |
| `Player` | `Player` |
| `Entity` | `Entity` |
| `World` | `World` |
| `Location` | `Location` |
| `Block` | `Block` |
| `Chunk` | `Chunk` |
| `ItemStack` | `Item` |
| `Inventory` | `Inventory` |
| `BossBar` | `BossBar` |
| (unknown) | `ProxyBase` |

Each proxy has pre-populated `fields` from the serialized data. Accessing a known field (like `player.name`) returns the cached value instantly — no round trip.

---

## ProxyBase Internals

`ProxyBase` is the Python wrapper for remote Java objects:

```python
class ProxyBase:
    def __init__(self, handle, type_name, fields, target, ...):
        self._handle = handle        # Java ObjectRegistry ID
        self._type_name = type_name  # "Player", "Entity", etc.
        self.fields = fields or {}   # Pre-deserialized field cache
        self._target = target        # "server", "ref", etc.
```

### Attribute access (`__getattr__`)

1. Check `self.fields` first — if the field was serialized, return it immediately (no RPC)
2. Otherwise, return a `BridgeMethod` wrapper that will dispatch an RPC when called

```python
player.name         # → fields["name"] (cached, instant)
player.get_health() # → BridgeMethod → RPC call (round trip)
```

### Attribute setting (`__setattr__`)

Private attributes (`_handle`, `_target`, etc.) and `fields` are set locally. Public attributes dispatch `set_attr` RPC:

```python
player.custom_tag = "vip"  # → {"method": "set_attr", "handle": 42, "field": "custom_tag", "value": "vip"}
```

### Method dispatch

When you call a method on a proxy:

```python
result = await player.get_health()
```

This goes through:

1. `__getattr__("get_health")` → returns `BridgeMethod(proxy, "get_health")`
2. `BridgeMethod.__call__()` → `_connection.call(method="getHealth", handle=42, args_list=[])`
3. `call()` returns `BridgeCall` wrapping `asyncio.Future`
4. `await` resolves when Java responds

**Name conversion:** Python `get_health` → Java `getHealth`. Snake_case is automatically converted to camelCase.

### Garbage collection

When a proxy is garbage collected, `__del__` queues the handle for release:

```python
def __del__(self):
    if self._handle is not None:
        _connection._queue_release(self._handle)
```

This is why short-lived proxies don't leak handles — Python's GC eventually cleans them up.
