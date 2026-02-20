---
title: Server
subtitle: Global server API
---

# Server

The `server` object is a module-level global available in every script. It provides access to players, worlds, boss bars, and server-wide operations.

```python
from bridge import *
# `server` is available immediately
players = server.players
```

---

## Attributes

### players

- **Type:** `list[`[`Player`](player.md)`]`

All currently online players. This is a snapshot — the list is re-fetched each time you access it.

```python
for p in server.players:
    await p.send_message("Hello everyone!")
```

### worlds

- **Type:** `list[`[`World`](world.md)`]`

All loaded worlds.

### name

- **Type:** `str`

The server name as configured in `server.properties`.

### version

- **Type:** `str`

The full server version string (e.g. `"git-Paper-123 (MC: 1.21.4)"`).

### motd

- **Type:** `str`

The server's Message of the Day.

### max_players

- **Type:** `int`

Maximum number of players allowed.

### tps

- **Type:** `list[float]`

Server TPS (ticks per second) values. Typically contains 1-minute, 5-minute, and 15-minute averages. A healthy server runs at 20 TPS.

### mspt

- **Type:** `float`

Milliseconds per tick. Lower is better. At 20 TPS, this should be ≤ 50ms.

### last_tick_time

- **Type:** `float`

Duration of the last tick in milliseconds.

### queue_len

- **Type:** `int`

Number of tasks currently in the main thread queue.

### boss_bars

- **Type:** `list[`[`BossBar`](bossbar.md)`]`

All active boss bars on the server.

### plugin_manager

- **Type:** `any`

The Bukkit plugin manager. Primarily useful for advanced reflection use cases.

### scheduler

- **Type:** `any`

The Bukkit scheduler. Rarely needed — use `server.wait()` and `@task` instead.

### scoreboard_manager

- **Type:** `any`

The server's scoreboard manager.

---

## Methods

### broadcast

```python
await server.broadcast(message: str)
```

Broadcast a message to all online players and the server console.

- **Parameters:**
  - `message` (`str`) — The message to broadcast. Supports Minecraft color codes with `§`.
- **Returns:** `Awaitable[None]`

```python
await server.broadcast("§a[Server]§r Restarting in 10 seconds!")
```

### execute

```python
result = await server.execute(command: str)
```

Execute a command as the server console. This runs with full server permissions.

- **Parameters:**
  - `command` (`str`) — The command to execute, without the leading `/`.
- **Returns:** `Awaitable[bool]` — `True` if the command was recognized.

```python
await server.execute("weather clear")
await server.execute("give Steve diamond 64")
```

### world

```python
w = await server.world(name: str)
```

Get a world by name.

- **Parameters:**
  - `name` (`str`) — The world name (e.g. `"world"`, `"world_nether"`).
- **Returns:** `Awaitable[`[`World`](world.md)`]`

```python
nether = await server.world("world_nether")
```

### create_boss_bar

```python
bar = await server.create_boss_bar(title: str, color: BarColor, style: BarStyle)
```

Create a new boss bar.

- **Parameters:**
  - `title` (`str`) — Display title.
  - `color` ([`BarColor`](enums.md)) — Bar color.
  - `style` ([`BarStyle`](enums.md)) — Bar style.
- **Returns:** `Awaitable[`[`BossBar`](bossbar.md)`]`

```python
bar = await server.create_boss_bar("Event Timer", BarColor.RED, BarStyle.SEGMENTED_6)
```

### get_advancement

```python
adv = await server.get_advancement(key: str)
```

Get an advancement by its namespaced key.

- **Parameters:**
  - `key` (`str`) — The advancement key (e.g. `"minecraft:story/mine_diamond"`).
- **Returns:** `Awaitable[`[`Advancement`](advancement.md)`]`

### wait

```python
await server.wait(ticks: int = 1, after: callable | None = None)
```

Pause execution for a number of ticks. Optionally run a callback after the wait.

- **Parameters:**
  - `ticks` (`int`) — Number of ticks to wait. Default `1`. (20 ticks = 1 second)
  - `after` (`callable | None`) — Optional callback to run after the wait completes.
- **Returns:** `Awaitable[None]`

```python
await server.wait(20)  # Wait 1 second
await server.wait(60)  # Wait 3 seconds

# With callback
await server.wait(20, after=lambda: print("Done waiting!"))
```

### frame

```python
async with server.frame():
    await player.send_message("Line 1")
    await player.send_message("Line 2")
```

Async context manager that batches multiple bridge calls into a single network send. Useful for reducing round-trips when making many calls at once.

### atomic

```python
async with server.atomic():
    await player.set_health(20)
    await player.set_food_level(20)
```

Async context manager that batches calls as an atomic group. All calls succeed or fail together.

### flush

```python
await server.flush()
```

Send all pending batched requests immediately. Use this inside a `frame()` or `atomic()` block if you need partial results before the block ends.

- **Returns:** `Awaitable[None]`
