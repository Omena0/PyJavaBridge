---
title: Debugging
subtitle: Debug logging, metrics, error codes, and performance tips
---

# Debugging

Tools and techniques for diagnosing issues with the bridge.

---

## Debug Logging

### Enabling

Toggle debug mode at runtime:

- **In-game:** `/bridge debug`
- **Console:** `/bridge debug`

Debug state is per-server (global toggle), not per-script.

### Log format

Debug messages use the `[PJB]` prefix with direction indicators:

```output
[PJB] P2J script.py 2.3ms call getHealth [42] → {"health": 20.0}
[PJB] J2P script.py 0.1ms event PlayerMoveEvent {player: "Steve", ...}
```

Format: `[PJB] {direction} {script} {time} {type} {summary}`

| Field | Values |
| ----- | ------ |
| Direction | `P2J` (Python→Java), `J2P` (Java→Python) |
| Script | Script filename |
| Time | Round-trip or processing time in milliseconds |
| Type | `call`, `event`, `release`, `register_command`, etc. |
| Summary | Truncated message content |

### Message summarization

Large messages are automatically summarized:

- Method calls show: method name + handle + truncated args
- Events show: event name + key fields
- Responses show: truncated return value
- Release batches show: handle count

---

## Metrics

The Python-side `MetricsFacade` exposes server performance data:

```python
from bridge import server

tps = server.tps              # Ticks per second (target: 20.0)
mspt = server.mspt            # Milliseconds per tick
tick_time = server.last_tick   # Last tick time in ms
queue = server.queue_length   # Pending calls in main thread queue
```

### Metric sources

| Metric | Source | Thread-safe |
| ------ | ------ | ----------- |
| `tps` | `Bukkit.getTPS()[0]` | Yes |
| `mspt` | `MinecraftServer.getAverageTickTimeNanos()` | Yes |
| `last_tick` | Bridge-internal counter | Yes |
| `queue_length` | Main thread queue `.size()` | Yes |

These are all read-only and can be safely accessed from async handlers.

---

## Error Codes

### ENTITY_GONE

```text
BridgeError: ENTITY_GONE - Entity no longer exists
```

**Cause:** The proxy refers to an entity that has been removed from the world (died, despawned, unloaded).

**Fix:** Check `entity.is_valid()` before operating, or catch `BridgeError`:

```python
try:
    entity.set_health(20)
except BridgeError:
    pass  # Entity was removed
```

### ATOMIC_ABORT

```text
BridgeError: ATOMIC_ABORT - Atomic batch failed
```

**Cause:** An operation inside an `atomic()` block raised an exception, causing the entire batch to abort.

**Fix:** Ensure all operations in the atomic block are valid:

```python
async with atomic():
    # Every operation here must succeed
    player.set_health(20)
    player.set_food_level(20)
```

### TIMEOUT

```text
BridgeError: TIMEOUT - Call did not complete within timeout
```

**Cause:** The Java side didn't respond within the timeout period. Usually means the main thread is blocked or overloaded.

**Fix:** Check server TPS. If the server is lagging, calls will queue up.

### Generic BridgeError

```text
BridgeError: {message}
```

**Cause:** Java-side exception during method invocation. The exception message is forwarded.

**Common causes:**

- `NullPointerException` — calling methods on null results
- `IllegalArgumentException` — wrong argument types
- `IllegalStateException` — calling Bukkit API from wrong thread

---

## Performance Tips

### Use batching for related operations

```python
# Bad: 20 round-trips
for i in range(20):
    player.get_inventory().set_item(i, item)

# Good: 1 round-trip with frame batching
async with frame():
    for i in range(20):
        player.get_inventory().set_item(i, item)
```

### Use thread-safe APIs when possible

Calls that are [thread-safe](execution.html) skip main thread scheduling and execute immediately:

```python
# These are thread-safe (fast):
player.send_message("Hello")
player.play_sound(...)
player.kick("reason")

# These need main thread (slower):
player.set_health(20)
world.get_block_at(x, y, z)
```

### Keep event handlers fast

Event handlers block the server's main thread while waiting for your Python code to respond:

```python
@event("player_move")
async def on_move(e):
    # BAD: slow operation blocks the server
    result = await some_expensive_call()
    
    # GOOD: only do quick checks in move events
    if e.player.is_sneaking:
        e.cancel()
```

High-frequency events like `player_move` should return as quickly as possible.

### Release references early

```python
# BAD: holds references to all chunks forever
chunks = []
for x in range(10):
    for z in range(10):
        chunks.append(world.get_chunk_at(x, z))

# GOOD: process and discard
for x in range(10):
    for z in range(10):
        chunk = world.get_chunk_at(x, z)
        process(chunk)
        # chunk goes out of scope, handle released on next GC
```

### Use `asyncio.gather` for independent calls

```python
# Sequential: 3 round-trips
health = await player.get_health()
food = await player.get_food_level()
level = await player.get_level()

# Parallel: 1 round-trip (all sent together)
health, food, level = await asyncio.gather(
    player.get_health(),
    player.get_food_level(),
    player.get_level()
)
```

### Monitor with metrics

```python
if server.tps < 18.0:
    # Server is struggling, reduce load
    skip_expensive_operations()

if server.queue_length > 50:
    # Too many pending calls
    await asyncio.sleep(0.1)  # Back off
```
