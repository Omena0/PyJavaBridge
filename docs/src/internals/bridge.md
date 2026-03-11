---
title: Architecture
subtitle: Overview of the bridge architecture and wire protocol
---

# Architecture

This section describes how PyJavaBridge works under the hood. Start here for the big picture, then dive into specific topics.

---

## Overview

Each Python script runs as a **separate OS process** spawned by the Java plugin. Communication happens over **stdin/stdout** using a binary protocol. The Python process's stderr is inherited by the Java process, so `print()` output appears in the server console.

```graph
┌──────────────────────┐   stdin (Java→Python)     ┌─────────────────────┐
│                      │ ◄──────────────────────── │                     │
│    Python Process    │                           │    Java Plugin      │
│                      │ ────────────────────────► │                     │
│  - asyncio event     │   stdout (Python→Java)    │  - Bridge thread    │
│    loop (main)       │                           │    (per script)     │
│  - reader thread     │   stderr (Python→Java)    │  - Main thread      │
│    (daemon)          │ ────────────────────────► │    (server tick)    │
│                      │   (console output)        │                     │
└──────────────────────┘                           └─────────────────────┘
```

**Per-script threads on Java side:**

- **Bridge thread** — reads from Python's stdout, writes to Python's stdin. Handles thread-safe calls inline.
- **Main thread** — Bukkit's server thread. Non-thread-safe calls are queued here.

**Per-script threads on Python side:**

- **Event loop** (main thread) — handles async operations, event dispatch, user code.
- **Reader thread** (daemon) — blocks on stdin, dispatches messages to the event loop or sync waiters.

---

## Wire Protocol

All messages use **length-prefixed frames** over stdin/stdout:

```table
┌─────────────┬─────────────────────────────┐
│  4 bytes    │  N bytes                    │
│  uint32 BE  │  payload (msgpack or JSON)  │
│  (length N) │                             │
└─────────────┴─────────────────────────────┘
```

- **Header:** 4-byte big-endian unsigned integer (payload length)
- **Payload:** msgpack binary or UTF-8 encoded JSON, depending on negotiated format
- **Format negotiation:** Python sends a `handshake` message (always JSON) on connect declaring its preferred format. Java switches to that format for all subsequent messages.
- **Serialization chain (Python):** `msgpack` → `orjson` → stdlib `json` — uses the first available library
- **Serialization chain (Java):** `msgpack-core` (shaded) when negotiated, otherwise Gson
- **Thread safety:** Python writes are protected by a `threading.Lock` to keep header+payload atomic

### Example wire message

Calling `player.getName()` where the player object has handle `42`:

```json
{"type": "call", "id": 1, "method": "getName", "args_list": [], "handle": 42}
```

Response:

```json
{"type": "return", "id": 1, "result": "Steve"}
```

### Send implementation (Python)

```python
def send(self, message):
    data = _json_dumps(message)           # msgpack, orjson, or json
    header = struct.pack("!I", len(data))  # 4-byte big-endian length
    with self._lock:
        self._stdout.write(header + data)
        self._stdout.flush()
```

The lock ensures header and payload are written atomically — without it, concurrent sends from different tasks could interleave.

### Format negotiation

On startup, Python sends a handshake (always as JSON, since Java starts in JSON mode):

```json
{"type": "handshake", "format": "msgpack"}
```

Java processes this and switches its `useMsgpack` flag. All subsequent messages in both directions use the negotiated format. If Python doesn't have `msgpack` installed, the handshake says `"format": "json"` and nothing changes.

---

## Message Types

### Python → Java (P2J)

| Type | Purpose | Key Fields |
| ---- | ------- | ---------- |
| `handshake` | Negotiate wire format | `format` (`"msgpack"` or `"json"`) |
| `call` | Invoke a method | `id`, `method`, `handle` or `target`, `args_list`, `no_response`? |
| `call_batch` | Batch multiple calls | `atomic`, `messages[]` |
| `subscribe` | Register event listener | `event`, `priority`, `once_per_tick`, `throttle_ms` |
| `register_command` | Register a `/command` | `name`, `description`, `usage`, `permission` |
| `wait` | Wait N server ticks | `id`, `ticks` |
| `release` | Free object handles | `handles[]` |
| `ready` | Script finished loading | — |
| `shutdown_ack` | Confirm shutdown received | — |
| `event_done` | Event handler finished | `id` |
| `event_cancel` | Cancel the event | `id` |
| `event_result` | Return a value from event | `id`, `result`, `result_type` |

### Java → Python (J2P)

| Type | Purpose | Key Fields |
| ---- | ------- | ---------- |
| `return` | Successful call result | `id`, `result` |
| `error` | Call failed | `id`, `message`, `code` |
| `event` | Bukkit event fired | `event`, `payload`, `id` |
| `event_batch` | Multiple events at once | `event`, `payloads[]` |

---

## Reader Thread

The Python-side reader thread is a daemon thread that blocks on stdin in a loop:

1. Read 4-byte header → decode payload length
2. Read N bytes of payload → deserialize (msgpack or JSON, matching negotiated format)
3. **Sync responses** (`return`/`error` matching a `_pending_sync` ID) → set `threading.Event` directly on the reader thread (fast path, no event loop involvement)
4. **Async responses** → dispatch to event loop via `call_soon_threadsafe()`
5. On disconnect → wake all pending waiters with `BridgeError("Connection lost")`

This two-tier design means sync property access (`player.name`) gets resolved on the reader thread without waiting for the event loop, while async calls integrate with `asyncio` naturally.

---

## Further Reading

- [Execution](execution.html) — Call dispatch, threading model, timing, and batching
- [Events](events_internal.html) — Event subscriptions, dispatch flow, cancellation, overrides
- [Serialization](serialization.html) — Object handles, type serialization, proxy classes
- [Lifecycle](lifecycle.html) — Startup, shutdown, hot reload, commands
- [Debugging](debugging.html) — Debug logging, metrics, error codes, performance tips
