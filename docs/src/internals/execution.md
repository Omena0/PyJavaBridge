---
title: Execution
subtitle: Call dispatch, threading, timing, and batching
---

# Execution

How method calls travel from Python to Java, get executed, and return results. Covers threading, the thread-safety allowlist, timing characteristics, and call batching.

---

## Call Flow

When Python calls a Java method (e.g. `player.get_health()`):

### 1. Python sends the call

```python
# Inside BridgeConnection.call()
message = {"type": "call", "id": 1, "method": "getHealth", "handle": 42, "args_list": []}
# If inside a batch context: queued to _batch_messages
# Otherwise: sent immediately over stdout
```

The `BridgeCall` wrapper (an `asyncio.Future`) is returned so the caller can `await` the result.

### 2. Java bridge thread reads the message

The bridge thread (one per script) reads from Python's stdout in a blocking loop. Each message is parsed and passed to `handleMessage()`, which routes by type.

### 3. Thread safety check

```diagram
isCallThreadSafe(message)?
├── YES → Execute immediately on bridge thread
│         Response sent directly (sub-millisecond)
└── NO  → Queue to main thread via MinecraftServer.execute()
          Response sent after main thread processes it
```

### 4. Method resolution

Java resolves the call through a dispatch chain:

1. **Type-specific handlers** — checked first. `Player`, `World`, `Server`, `ItemStack`, `Inventory`, `Block`, `Display` each have custom method handling for common operations (e.g. `playSound`, `teleport`, `spawnEntity`)
2. **Special methods** — `get_attr` (field access), `set_attr` (field set), `close` (no-op cleanup)
3. **Reflective fallback** — if no handler matched, Java reflection finds a matching method by name and parameter count, with automatic argument type coercion

### 5. Python receives the response

The reader thread reads the response from stdin:

- **Async path**: `return`/`error` messages matching a pending `asyncio.Future` → resolved via `call_soon_threadsafe()` on the event loop
- **Sync path**: messages matching a `_pending_sync` ID → `threading.Event` set directly on the reader thread (no event loop delay)

---

## Threading Model

### Bridge thread (per script)

Each script gets a dedicated Java thread that:

- Reads messages from Python's stdout
- Executes thread-safe calls inline
- Writes responses to Python's stdin

Thread-safe calls never leave this thread, which is why they're sub-millisecond.

### Main server thread

The Bukkit main thread runs the game loop at 20 TPS (50ms per tick). Non-thread-safe calls must execute here because most Bukkit API methods are not thread-safe.

### Sub-tick scheduling

Non-thread-safe calls are dispatched via `MinecraftServer.execute()` (resolved at startup via reflection). This adds the task to Minecraft's internal `processQueue`, which is checked during the server's idle sleep between ticks. The server wakes up via `LockSupport.unpark()` to process the task immediately.

If `MinecraftServer.execute()` is unavailable (non-Paper server or reflection fails), calls fall back to a `ConcurrentLinkedQueue` drained once per tick by a `runTaskTimer`.

### Spin-wait drain

After executing a main-thread task, the drain loop spins for up to **5ms** checking for follow-up calls. This catches chained sequential calls (Python sends the next call immediately after receiving a response).

Constants:

- **SPIN_WAIT_NS** = 5,000,000 (5ms per-task spin window)
- **MAX_SPIN_NS** = 20,000,000 (20ms hard cap per drain cycle)

After processing a task, the spin deadline resets. But total spin time per drain cycle is capped at 20ms to prevent starvation under continuous load.

---

## Thread-Safe Allowlist

These calls execute immediately on the bridge thread with no tick wait:

| Target / Type | Safe Methods |
| ------------- | ------------ |
| `metrics` facade | ALL methods (reads atomic/volatile values) |
| `reflect` facade | ALL methods (`Class.forName()` is thread-safe) |
| `server` facade | `getName`, `getVersion`, `getBukkitVersion`, `getMaxPlayers` |
| `OfflinePlayer` / `Player` | `getUniqueId`, `getName`, `hasPermission`, `isPermissionSet`, `isWhitelisted`, `isBanned` |
| `Metadatable` objects | `hasMetadata`, `getMetadata` |
| `Entity` (non-Player) | `getUniqueId` |
| Object handle releases | Always (backed by `ConcurrentHashMap`) |

Everything else runs on the main server thread. The allowlist is intentionally conservative — calling a non-thread-safe method from the wrong thread can cause data corruption or crashes.

---

## Timing

### Thread-safe calls

Executed inline on the bridge thread. Typical latency: **< 1ms**.

### Non-thread-safe calls (first in chain)

Must wait for the main thread. With `MinecraftServer.execute()`, typically **1–10ms**. Without it (fallback queue), up to **~50ms** (one full tick).

### Non-thread-safe calls (chained)

The spin-wait catches follow-up calls within **1–3ms** each.

### Example timing scenario

```python
name = await server.name           # Thread-safe → ~0.5ms
health = await player.get_health() # Main thread → 1-10ms (first call)
await player.set_health(20)        # Main thread → 1-3ms (chained, caught by spin-wait)
await player.send_message("Hi")    # Main thread → 1-3ms (chained)
```

Without chaining awareness, each main-thread call would wait up to 50ms. The spin-wait reduces this to under 3ms for follow-up calls.

### Why the first call is slower

The main thread runs a game loop: process tick → sleep until next tick. When a call arrives mid-sleep, `MinecraftServer.execute()` wakes the thread, but it still needs to context-switch and begin processing. The first call pays this wake-up cost. Subsequent calls arrive while the thread is already running, so they're processed immediately.

---

## Sync vs Async Calls

### Async (default)

```python
name = await player.get_name()  # Returns BridgeCall wrapping asyncio.Future
```

- Response dispatched via `call_soon_threadsafe()` to the event loop
- Does not block the event loop while waiting
- Preferred for all user code

### Sync (internal use)

```python
name = player.name  # Property access calls call_sync() internally
```

- Uses `threading.Event` — reader thread sets it directly
- **Blocks the calling thread** until response arrives
- Used for `__getattr__`, `__str__`, `__repr__`, `__len__`, `__iter__`
- Can cause deadlocks if the event loop is blocked waiting for itself

**Rule of thumb:** Use `await` methods in async code. Property access (sync) is fine in top-level code or synchronous contexts.

---

## Batching

Batching groups multiple calls into a single wire message, reducing round-trip overhead. Instead of send-wait-send-wait, all calls are collected and sent together.

### `server.frame()` — Non-atomic batch

Each call is independent. If one fails, the rest still execute.

```python
async with server.frame():
    name = await player.get_name()        # Queued
    health = await player.get_health()    # Queued
    world = await player.get_world()      # Queued
# All 3 sent as one call_batch, results awaited together
```

**Wire message:**

```json
{
  "type": "call_batch",
  "atomic": false,
  "messages": [
    {"type": "call", "id": 1, "method": "getName", "handle": 42, "args_list": []},
    {"type": "call", "id": 2, "method": "getHealth", "handle": 42, "args_list": []},
    {"type": "call", "id": 3, "method": "getWorld", "handle": 42, "args_list": []}
  ]
}
```

Each call gets its own `return` response (3 separate messages back).

### `server.atomic()` — Atomic batch (best-effort)

If any call fails, all subsequent calls are **skipped** (not rolled back — already-executed calls are not undone).

```python
async with server.atomic():
    inv = await player.get_inventory()
    await inv.clear()
    for item in items:
        await inv.add_item(item)
# If any add_item fails, the rest are skipped
```

**On failure:** The failed call gets a normal `error` response. All remaining calls get an error with code `ATOMIC_ABORT`:

```json
{"type": "error", "id": 5, "message": "Atomic batch aborted", "code": "ATOMIC_ABORT"}
```

### Nesting

Batches can nest. The outermost context manager triggers the flush. If any level is `atomic`, the entire batch becomes atomic:

```python
async with server.frame():
    await player.get_name()
    async with server.atomic():
        await player.set_health(20)
        await player.set_food_level(20)
    # Inner atomic doesn't flush yet
# Everything flushes here as atomic=true (because inner was atomic)
```

### Batch thread safety

If **all** calls in a batch are thread-safe, the entire batch executes on the bridge thread. If **any** call is not thread-safe, the entire batch goes to the main thread.

### When to use batching

- **`frame()`** — Multiple independent reads. Good for UI updates, data gathering. Reduces N round trips to 1.
- **`atomic()`** — Related writes where partial failure is bad. Good for inventory operations, multi-step entity setup.
- **Neither** — Single calls, or when each result is needed before the next call.

---

## Wait Mechanism

`server.after(ticks)` pauses execution for N server ticks:

```python
await server.after(20)  # Wait 1 second (20 ticks)
```

**Implementation:** Python sends `{"type": "wait", "id": N, "ticks": 20}`. Java schedules a `runTaskLater` on the Bukkit scheduler. When the delay expires, Java sends `{"type": "return", "id": N, "result": null}`. The Python future resolves and execution continues.

This is the correct way to introduce delays — it integrates with the server's tick system rather than using `asyncio.sleep()` which would be wall-clock time and might not align with server ticks.
