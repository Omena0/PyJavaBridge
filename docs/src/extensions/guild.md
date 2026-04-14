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

Add `player` to the guild if capacity and rules allow it.

### leave(player)

Remove `player` from the guild.

### kick(uuid)

Remove a member by UUID.

### promote(uuid) / demote(uuid)

Promote or demote a member's guild rank.

### transfer_leadership(uuid)

Transfer guild leadership to the member with the given UUID.

### deposit(amount) / withdraw(amount)

Add to or remove funds from the guild bank balance.

### disband()

Disband the guild and clear persisted state.

### broadcast(message)

Send `message` to all online guild members.

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
