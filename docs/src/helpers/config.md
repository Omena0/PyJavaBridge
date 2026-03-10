---
title: Config
subtitle: Configuration files (TOML, JSON, properties)
---

# Config

`Config` provides a simple interface for reading and writing configuration files. Config files are stored in the plugin's data folder and persist across server restarts.

Supported formats: **TOML** (default), **JSON**, and **properties**.

---

## Constructor

```python
Config(name=None, defaults=None, format="toml")
```

Load or create a configuration file.

- **Parameters:**
  - `name` (`str | None`) — File name (without extension). If `None`, uses the script name.
  - `defaults` (`dict[str, Any] | None`) — Default values to merge into the config if they don't already exist.
  - `format` (`str`) — File format: `"toml"` (default), `"json"`, or `"properties"`.

```python
# Default config.toml
config = Config()

# Named config
bans = Config("bans")

# JSON format
data = Config("data", format="json")

# Properties format
props = Config("server", format="properties")

# With defaults
settings = Config("settings", defaults={
    "spawn_protection_radius": 16,
    "max_homes": 3,
    "welcome_message": "§aWelcome to the server!"
})
```

---

## Attributes

### data

- **Type:** `dict[str, Any]`

The entire config as a dictionary.

### path

- **Type:** `str`

Absolute file path to the config file.

---

## Methods

### get

```python
value = config.get(path, default=None)
```

Get a value by dot-separated path.

- **Parameters:**
  - `path` (`str`) — Dot-separated key path (e.g. `"database.host"`).
  - `default` (`Any`) — Fallback if the key doesn't exist. Default `None`.
- **Returns:** `Any`

```python
radius = config.get("spawn_protection_radius", 16)
db_host = config.get("database.host", "localhost")
```

### get_int

```python
value = config.get_int(path, default=0)
```

Get a value as an integer.

- **Parameters:**
  - `path` (`str`) — Dot-separated key path.
  - `default` (`int`) — Fallback. Default 0.
- **Returns:** `int`

### get_float

```python
value = config.get_float(path, default=0.0)
```

Get a value as a float.

- **Parameters:**
  - `path` (`str`) — Dot-separated key path.
  - `default` (`float`) — Fallback. Default 0.0.
- **Returns:** `float`

### get_bool

```python
value = config.get_bool(path, default=False)
```

Get a value as a boolean.

- **Parameters:**
  - `path` (`str`) — Dot-separated key path.
  - `default` (`bool`) — Fallback. Default `False`.
- **Returns:** `bool`

### get_list

```python
value = config.get_list(path, default=None)
```

Get a value as a list.

- **Parameters:**
  - `path` (`str`) — Dot-separated key path.
  - `default` (`list[Any] | None`) — Fallback. Default `None`.
- **Returns:** `list[Any]`

### set

```python
config.set(path, value)
```

Set a value by dot-separated path. Creates intermediate keys as needed.

- **Parameters:**
  - `path` (`str`) — Dot-separated key path.
  - `value` (`Any`) — Value to set.

```python
config.set("database.host", "localhost")
config.set("database.port", 3306)
```

### delete

```python
result = config.delete(path)
```

Delete a key.

- **Parameters:**
  - `path` (`str`) — Dot-separated key path.
- **Returns:** `bool` — `True` if the key existed and was deleted.

### save

```python
config.save()
```

Write changes to disk. This is synchronous.

```python
config.set("last_restart", "2024-01-15")
config.save()
```

### reload

```python
config.reload()
```

Reload the config from disk, discarding unsaved changes. This is synchronous.

---

## Dict-style Access

Config supports `[]` notation and `in` checks:

```python
# These are equivalent
value = config["key"]
value = config.get("key")

# Set values
config["key"] = "value"
config.set("key", "value")

# Check existence
if "key" in config:
    print("Key exists!")
```

---

## Example: Ban system config

```python
from bridge import *

bans = Config("bans", defaults={"banned_players": {}})

@command("Ban a player")
async def ban(player: Player, args: list[str]):
    if not args:
        await player.send_message("§cUsage: /ban <player> [reason]")
        return

    target = args[0]
    reason = " ".join(args[1:]) or "No reason given"

    bans.set(f"banned_players.{target}", {
        "reason": reason,
        "banned_by": player.name,
    })
    bans.save()
    await player.send_message(f"§aBanned {target}: {reason}")

@event
async def player_login(e: Event):
    ban_info = bans.get(f"banned_players.{e.player.name}")
    if ban_info:
        await e.player.kick(f"§cBanned: {ban_info['reason']}")
```
