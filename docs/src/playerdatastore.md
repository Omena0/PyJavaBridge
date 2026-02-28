---
title: PlayerDataStore [ext]
subtitle: Persistent per-player key/value storage
---

# PlayerDataStore [ext]

`PlayerDataStore` provides persistent per-player data storage with dict-style access.

```python
from bridge.extensions import PlayerDataStore
```

---

## Constructor

```python
PlayerDataStore(name="default")
```

Data is saved to `plugins/PyJavaBridge/playerdata/<name>/<uuid>.json`.

---

## Usage

### Dict-style access

```python
store = PlayerDataStore("stats")

# Set a value
store[player]["kills"] = 10

# Get a value
kills = store[player]["kills"]

# Check existence
if "kills" in store[player]:
    ...
```

### Methods

#### get(player, field, default=None) → Any

#### set(player, field, value)

#### delete(player, field=None)

If `field` is `None`, deletes all data for that player.

#### all_data(player) → dict

Returns a copy of all stored data for the player.

### Bulk set

```python
store[player] = {"kills": 0, "deaths": 0}
```
