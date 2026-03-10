---
title: TabList
subtitle: Advanced tab list management with templates and groups
---

# TabList [ext]

`TabList` provides per-player tab list customization with dynamic headers, footers, templates, and entry groups.

```python
from bridge.extensions import TabList, TabEntry

tab = TabList()
tab.header = "&6My Server"
tab.footer = "&7Online: {online}/{max}"

# Auto-update every second
tab.auto_update(interval_ticks=20)
```

## Import

```python
from bridge.extensions import TabList, TabEntry, TabGroup
```

## TabList

### Constructor

```python
tab = TabList()
```

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `header` | `str` | Tab list header text (get/set) |
| `footer` | `str` | Tab list footer text (get/set) |

### Methods

#### .create_group(name, prefix="", priority=0)

Create a named group of tab entries.

- **Parameters:**
  - `name` *(str)* — Group identifier.
  - `prefix` *(str)* — Prefix for all entries in the group.
  - `priority` *(int)* — Sort order (lower = higher in list).
- **Returns:** `TabGroup`

```python
staff = tab.create_group("staff", prefix="&c[Staff] ", priority=0)
default = tab.create_group("default", prefix="&7", priority=10)
```

#### .get_group(name)

Get a group by name.

- **Returns:** `TabGroup | None`

#### .remove_group(name)

Remove a group by name.

#### @tab.template(name)

Decorator to register a template function for `{name}` placeholders in header/footer.

The function receives `(player, server)` and should return a string.

```python
@tab.template("rank")
def rank(player, server):
    return player.primary_group
```

Then use `{rank}` in the header/footer text.

#### await .apply(player)

Apply the tab list configuration to a specific player.

#### await .apply_all()

Apply the tab list to all online players.

#### .auto_update(interval_ticks=20)

Start auto-updating the tab list on a timer.

- **Parameters:**
  - `interval_ticks` *(int)* — Ticks between updates. Default `20` (1 second).
- **Returns:** `asyncio.Task` — Can be cancelled.

### Built-in Placeholders

These are resolved automatically in header/footer text:

| Placeholder | Value |
| ----------- | ----- |
| `{online}` | Number of online players |
| `{max}` | Maximum player slots |
| `{player}` | Player's name |

---

## TabEntry

A single entry in a tab group.

```python
entry = TabEntry("Admin", ping=5, game_mode="CREATIVE")
```

### Constructor

```python
TabEntry(name, ping=0, skin=None, game_mode="SURVIVAL")
```

- **Parameters:**
  - `name` *(str)* — Display name.
  - `ping` *(int)* — Latency in ms. Default `0`.
  - `skin` *(str | None)* — Optional skin texture (base64).
  - `game_mode` *(str)* — Game mode. Default `"SURVIVAL"`.

---

## TabGroup

A named group of tab entries.

### Methods

#### .add_entry(entry)

Add a `TabEntry` to this group.

#### .remove_entry(name)

Remove an entry by display name.

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `entries` | `list[TabEntry]` | Entries in this group (read-only) |

---

## Full Example

```python
from bridge import *
from bridge.extensions import TabList, TabEntry

tab = TabList()
tab.header = "&6&l✦ My Server ✦\n&7Online: {online}/{max}"
tab.footer = "&8TPS: {tps}"

@tab.template("tps")
def tps(player, srv):
    return f"{srv.tps:.1f}"

staff = tab.create_group("staff", prefix="&c[Staff] ", priority=0)
staff.add_entry(TabEntry("Console", ping=0))

@event("player_join")
async def on_join(e):
    await tab.apply(e.player)

tab.auto_update(20)
```
