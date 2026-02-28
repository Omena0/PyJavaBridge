---
title: Guild [ext]
subtitle: Persistent guild system
---

# Guild [ext]

`Guild` is a persistent organization with ranks, a guild bank, and guild chat.

```python
from bridge.extensions import Guild
```

---

## Constructor

```python
Guild(name, leader, max_size=50)
```

Data is stored in `plugins/PyJavaBridge/guilds/<name>.json`.

---

## Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `name` | `str` | Guild name |
| `leader` | `Player` | Guild leader |
| `members` | `dict[str, str]` | UUID → rank mapping |
| `bank` | `float` | Guild bank balance |

---

## Ranks

Three built-in ranks: `leader`, `officer`, `member`.

---

## Methods

### join(player) → bool

### leave(player)

### kick(uuid)

### promote(uuid) / demote(uuid)

### transfer_leadership(uuid)

### deposit(amount) / withdraw(amount)

### disband()

### broadcast(message)

---

## Class Methods

### Guild.load(name) → Guild | None

Load a guild from disk by name.

---

## Decorators

### @guild.on_join / @guild.on_leave

```python
@my_guild.on_join
def welcome(player, guild):
    guild.broadcast(f"§a{player.name} joined the guild!")
```
