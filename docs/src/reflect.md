---
title: Reflect
subtitle: Java reflection helper
---

# Reflect

The `Reflect` helper provides access to Java classes for advanced interop. An instance is available as the global `reflect` variable.

> **Warning:** Reflection is a low-level API. Most scripts won't need it. Use the higher-level bridge classes when possible.

---

## Global Instance

```python
from bridge import reflect
```

---

## Methods

### clazz

```python
cls = await reflect.clazz(name)
```

Get a Java class by its fully qualified name.

- **Parameters:**
  - `name` (`str`) — Fully qualified Java class name.
- **Returns:** `Awaitable[Any]` — The Java class object.

```python
# Access Bukkit classes
bukkit = await reflect.clazz("org.bukkit.Bukkit")

# Access NMS (net.minecraft.server) classes
# The exact path depends on server version
nms = await reflect.clazz("net.minecraft.server.MinecraftServer")
```

---

## Use Cases

### Accessing unsupported Bukkit API

If the bridge doesn't wrap a specific Bukkit method, you can access it directly:

```python
bukkit = await reflect.clazz("org.bukkit.Bukkit")
# Call static methods on the class
```

### Checking server internals

```python
server_cls = await reflect.clazz("org.bukkit.Bukkit")
# Useful for debugging or version-specific code
```

---

## Notes

- Reflection accesses the underlying Java runtime — incorrect class names will raise errors
- The available classes depend on the server implementation (Spigot, Paper, etc.)
- NMS class paths change between Minecraft versions
- Prefer using bridge-provided APIs over reflection when possible
