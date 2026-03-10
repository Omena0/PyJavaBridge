---
title: Placeholder
subtitle: Register %placeholder% expansions for messages
---

# PlaceholderRegistry [ext]

`PlaceholderRegistry` provides a system for registering `%placeholder%` expansions that can be resolved in any text string.

```python
from bridge.extensions import PlaceholderRegistry

placeholders = PlaceholderRegistry()

@placeholders.register("player_name")
def name(player):
    return player.name

@placeholders.register("player_health")
def health(player):
    return str(player.health)

msg = placeholders.resolve("Hello %player_name%! HP: %player_health%", player)
# -> "Hello Steve! HP: 20.0"
```

## Import

```python
from bridge.extensions import PlaceholderRegistry
```

## Constructor

```python
placeholders = PlaceholderRegistry()
```

## Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `names` | `list[str]` | All registered placeholder names (read-only) |

## Decorators

### @placeholders.register(name)

Register a placeholder by name. The decorated function receives `(player)` and should return a string.

- **Parameters:**
  - `name` *(str)* — Placeholder name (used as `%name%` in text).

```python
@placeholders.register("server_online")
def online(player):
    import bridge
    return str(len(bridge.server.players))
```

If the function returns `None`, the placeholder is left unresolved.

## Methods

### .add(name, func)

Imperatively register a placeholder.

- **Parameters:**
  - `name` *(str)* — Placeholder name.
  - `func` *(Callable)* — Function `(player) -> str`.

```python
placeholders.add("time", lambda p: str(p.world.time))
```

### .remove(name)

Remove a registered placeholder.

### .has(name)

Check if a placeholder is registered.

- **Returns:** `bool`

### .resolve(text, player=None, **kwargs)

Replace all `%placeholder%` tokens in text with their resolved values.

- **Parameters:**
  - `text` *(str)* — Input string with placeholders.
  - `player` — Player context passed to resolver functions.
  - `**kwargs` — Extra keyword arguments passed to resolvers.
- **Returns:** `str` — Text with placeholders expanded.

Unrecognized placeholders are left as-is.

```python
msg = placeholders.resolve("Hello %player_name%, you have %coins% coins!", player)
```

### .resolve_many(texts, player=None, **kwargs)

Resolve placeholders in a list of strings.

- **Parameters:**
  - `texts` *(list[str])* — List of strings to resolve.
  - `player` — Player context.
- **Returns:** `list[str]`

---

## Full Example

```python
from bridge import *
from bridge.extensions import PlaceholderRegistry

ph = PlaceholderRegistry()

@ph.register("player_name")
def pname(player):
    return player.name

@ph.register("player_world")
def pworld(player):
    return player.world.name

@ph.register("player_health")
def phealth(player):
    return f"{player.health:.0f}"

@ph.register("online")
def online(player):
    return str(len(server.players))

@command("Show player info")
async def info(event: Event):
    msg = ph.resolve(
        "&6%player_name% &7| &c❤ %player_health% &7| &a🌍 %player_world% &7| &b👥 %online%",
        event.player
    )
    await event.player.send_message(msg)
```
