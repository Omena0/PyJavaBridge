---
title: Party [ext]
subtitle: Player group management
---

# Party [ext]

`Party` manages a temporary player group with a leader, join/leave, kick, and friendly fire prevention.

```python
from bridge.extensions import Party
```

---

## Constructor

```python
Party(name, leader, max_size=10)
```

- **Parameters:**
  - `name` (`str`) — Party name.
  - `leader` (`Player`) — Party leader.
  - `max_size` (`int`) — Maximum members (default 10).

---

## Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `name` | `str` | Party name |
| `leader` | `Player` | Current leader |
| `members` | `list[Player]` | All members including leader |
| `max_size` | `int` | Maximum size |

---

## Methods

### join(player) → bool

Add a player to the party.

### leave(player)

Remove a player. If the leader leaves and members remain, a new leader is promoted.

### kick(player)

Remove a player (leader action).

### promote(player)

Transfer leadership to another member.

### disband()

Remove all members and destroy the party.

### broadcast(message)

Send a message to all members.

---

## Class Methods

### Party.of(player) → Party | None

Find the party a player belongs to.

---

## Decorators

### @party.on_join / @party.on_leave

```python
@my_party.on_join
def joined(player, party):
    party.broadcast(f"{player.name} joined!")
```

---

## Friendly Fire

Party automatically prevents members from damaging each other via an entity damage listener.
