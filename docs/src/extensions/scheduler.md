---
title: Scheduler
subtitle: Cron-like real-world-time task scheduling
---

# Scheduler [ext]

`Scheduler` provides real-world-time (seconds-based) task scheduling with named tasks, repeat intervals, and one-shot delays.

```python
from bridge.extensions import Scheduler

sched = Scheduler()

@sched.every(60, name="announce")
async def announce():
    await bridge.server.broadcast("&6Remember to vote!")

sched.start()
```

## Import

```python
from bridge.extensions import Scheduler, ScheduledTask
```

## Scheduler

### Constructor

```python
sched = Scheduler()
```

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `tasks` | `dict[str, ScheduledTask]` | All registered tasks (read-only copy) |

### Decorators

#### @sched.every(seconds, name=None, delay=0)

Schedule a function to run every `seconds` seconds.

- **Parameters:**
  - `seconds` *(float)* — Interval between executions.
  - `name` *(str | None)* — Task name. Defaults to function name.
  - `delay` *(float)* — Initial delay before first execution.

```python
@sched.every(30, name="heal")
async def heal_all():
    for p in bridge.server.players:
        await p.set_health(20)
```

#### @sched.after(seconds, name=None)

Schedule a function to run **once** after `seconds` seconds.

- **Parameters:**
  - `seconds` *(float)* — Delay before execution.
  - `name` *(str | None)* — Task name. Defaults to function name.

```python
@sched.after(10, name="welcome")
async def welcome():
    await bridge.server.broadcast("&aServer ready!")
```

### Methods

#### .schedule(name, handler, interval=0, delay=0, repeat=True)

Imperatively schedule a task.

- **Parameters:**
  - `name` *(str)* — Task identifier.
  - `handler` *(Callable)* — Async or sync callable.
  - `interval` *(float)* — Seconds between runs (0 = one-shot).
  - `delay` *(float)* — Initial delay in seconds.
  - `repeat` *(bool)* — Whether to repeat.
- **Returns:** `ScheduledTask`

#### .cancel(name)

Cancel a named task.

#### .cancel_all()

Cancel all tasks.

#### .start()

Start all registered tasks.

#### .stop()

Stop all tasks.

---

## ScheduledTask

A single scheduled task.

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `cancelled` | `bool` | Whether the task was cancelled (read-only) |
| `run_count` | `int` | Number of times executed (read-only) |
| `last_run` | `float \| None` | Timestamp of last execution (read-only) |

### Attributes

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `name` | `str` | Task identifier |
| `handler` | `Callable` | The task function |
| `interval` | `float` | Seconds between runs |
| `delay` | `float` | Initial delay |
| `repeat` | `bool` | Whether it repeats |

### Methods

#### .cancel()

Cancel this task.

---

## Full Example

```python
from bridge import *
from bridge.extensions import Scheduler

sched = Scheduler()

@sched.every(300, name="save_warning")
async def save_warning():
    await server.broadcast("&eSaving world in 10 seconds...")
    await server.after(200)  # 10 seconds
    await server.execute("save-all")

@sched.every(60, delay=5, name="tip")
async def random_tip():
    import random
    tips = ["Use /help for commands", "Join our Discord!", "Vote for rewards!"]
    await server.broadcast(f"&b[Tip] &7{random.choice(tips)}")

@sched.after(0.5, name="startup")
async def on_start():
    await server.broadcast("&aAll systems online!")

sched.start()
```
