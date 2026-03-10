---
title: State
subtitle: Persistent key-value store across reloads
---

# State

A simple persistent key-value store that survives script reloads and server restarts. Data is stored as JSON.

Works like a dict — read, write, and delete keys directly. Auto-saves on script shutdown.

---

## Constructor

```python
State(name=None)
```

- **Parameters:**
  - `name` (`str | None`) — State file name. Defaults to the script filename.

```python
state = State()            # Uses script name
state = State("my_data")   # Custom name
```

---

## Usage

```python
state = State()

# Read/write like a dict
state["kills"] = state.get("kills", 0) + 1
state["banned_players"] = ["Steve", "Alex"]

# Check membership
if "kills" in state:
    print(state["kills"])

# Delete
del state["banned_players"]

# Manual save (also auto-saves on shutdown)
state.save()
```

---

## Methods

### save

```python
state.save()
```

Save state to disk. Called automatically on script shutdown, but you can call it manually for safety.

### load

```python
state.load()
```

Reload state from disk. Called automatically on construction.

### get

```python
state.get(key, default=None)
```

Get a value with a default fallback.

### clear

```python
state.clear()
```

Remove all keys.

### update

```python
state.update({"key": "value", ...})
```

Merge a dict into the state.

---

## Properties

### data

- **Type:** `dict`

Direct access to the underlying data dict.

### path

- **Type:** `str`

Path to the state file on disk.

---

## Example: Kill counter

```python
from bridge import *

state = State()

@event
async def player_death(e):
    killer = e.killer
    if killer:
        name = killer.name
        state[name] = state.get(name, 0) + 1
        await killer.send_message(f"Kills: {state[name]}")
        state.save()
```

## Example: Persistent warps

```python
from bridge import *

state = State("warps")

@command("Set a warp point")
async def setwarp(e, name: str):
    loc = e.player.location
    state[name] = {"x": loc.x, "y": loc.y, "z": loc.z, "world": loc.world.name}
    state.save()
    await e.player.send_message(f"Warp '{name}' set!")

@command("Teleport to warp")
async def warp(e, name: str):
    data = state.get(name)
    if not data:
        await e.player.send_message(f"Warp '{name}' not found.")
        return
    loc = Location(data["x"], data["y"], data["z"], data["world"])
    await e.player.teleport(loc)
```
