---
title: Decorators
subtitle: Register event handlers, commands, and repeating tasks
---

# Decorators

PyJavaBridge uses Python decorators to register event handlers, commands, and repeating tasks. Your decorated functions are discovered automatically when the script loads.

---

## @event

```python
@event
async def player_join(e):
    await e.player.send_message("Welcome!")
```

Register a function as an event handler. The function name determines the event type — it is converted from `snake_case` to `PascalCase` and `Event` is appended. For example, `player_join` becomes `PlayerJoinEvent`.

### Signature

```
@event(*, once_per_tick=False, priority="NORMAL", throttle_ms=0)
```

### Parameters

#### once_per_tick

- **Type:** `bool`
- **Default:** `False`

When `True`, the handler is called at most once per server tick, even if the event fires multiple times. Useful for high-frequency events like `player_move`.

```python
@event(once_per_tick=True)
async def player_move(e):
    # Called at most once per tick per event, not every micro-movement
    pass
```

#### priority

- **Type:** `str`
- **Default:** `"NORMAL"`

The Bukkit event priority. Determines the order in which handlers run. Options (lowest runs first):

| Priority | Description |
|----------|-------------|
| `LOWEST` | Runs first. Use for early cancellation. |
| `LOW` | Runs before normal handlers. |
| `NORMAL` | Default priority. |
| `HIGH` | Runs after normal handlers. |
| `HIGHEST` | Runs last before monitor. |
| `MONITOR` | Read-only observation. Do not modify the event. |

```python
@event(priority="HIGH")
async def block_break(e):
    # This runs after NORMAL-priority handlers
    pass
```

#### throttle_ms

- **Type:** `int`
- **Default:** `0`

Minimum milliseconds between handler invocations. If the event fires more frequently, extra invocations are silently dropped.

```python
@event(throttle_ms=500)
async def player_interact(e):
    # At most once every 500ms, prevents spam-clicking abuse
    pass
```

### Bare decorator

You can use `@event` without parentheses for the default settings:

```python
@event
async def player_quit(e):
    await server.broadcast(f"{e.player.name} left!")
```

---

## @command

```python
@command("Greet a player", permission="myplugin.greet")
async def greet(e):
    await e.player.send_message("Hello!")
```

Register a function as a script command. The command is automatically available as `/functionname` (or as specified via the `name` parameter). Command arguments are parsed from the function's additional parameters after `event`.

### Signature

```
@command(description=None, *, name=None, permission=None)
```

### Parameters

#### description

- **Type:** `str | None`
- **Default:** `None`

A human-readable description of the command. This is the first positional argument.

```python
@command("Teleport to spawn")
async def spawn(e):
    ...
```

#### name

- **Type:** `str | None`
- **Default:** `None` (uses function name)

Override the command name. By default the function name is used.

```python
@command("Teleport home", name="home")
async def teleport_home(e):
    # Registered as /home, not /teleport_home
    ...
```

#### permission

- **Type:** `str | None`
- **Default:** `None`

Permission node required to use the command. Players without this permission cannot execute it.

```python
@command("Ban a player", permission="admin.ban")
async def ban(e, target: str):
    ...
```

### Command arguments

Extra function parameters after the event become command arguments. They are parsed positionally from the player's input:

```python
@command("Give items")
async def give(e, material: str, amount: str = "1"):
    # /give diamond 64
    # material = "diamond", amount = "64"
    await Item.give(e.player, material, int(amount))
```

All arguments are passed as strings. You handle type conversion yourself.

---

## @task

```python
@task(interval=20, delay=0)
async def tick_loop():
    ...
```

Register a repeating async task. The function is called repeatedly at the specified interval after an optional initial delay.

### Signature

```
@task(*, interval=20, delay=0)
```

### Parameters

#### interval

- **Type:** `int`
- **Default:** `20`

Ticks between invocations. Minecraft runs at 20 ticks per second, so `interval=20` means once per second, `interval=1` means every tick.

#### delay

- **Type:** `int`
- **Default:** `0`

Initial delay in ticks before the first invocation. Use this to wait for the server to fully start.

```python
@task(interval=20*60, delay=20*5)
async def auto_save():
    # Runs every 60 seconds, starting 5 seconds after script load
    await server.execute("save-all")
```

### Notes

- Task functions take **no arguments** (unlike event/command handlers).
- The task is cancelled automatically when the script is unloaded.
- If the function is still running when the next invocation is due, the next invocation is skipped.
