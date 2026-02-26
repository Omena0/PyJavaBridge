---
title: Events
subtitle: Event subscriptions, dispatch, cancellation, overrides, and commands
---

# Events

How Bukkit events are captured, sent to Python, and how Python can cancel them or override their values. Also covers command registration, which follows a similar player-triggered dispatch model.

---

## Subscription

When you use `@event` in Python, the bridge registers a Bukkit event listener on the Java side:

```python
@event
async def player_join(event):
    await event.player.send_message("Welcome!")
```

**Wire message (Python → Java):**

```json
{
  "type": "subscribe",
  "event": "player_join",
  "priority": "NORMAL",
  "once_per_tick": false,
  "throttle_ms": 0
}
```

### Priority

Maps to Bukkit's `EventPriority` — controls the order handlers run relative to other plugins:

| Priority | When to use |
| -------- | ----------- |
| `LOWEST` | Read event data before anyone modifies it |
| `LOW` | Early processing |
| `NORMAL` | Default. Most handlers should use this |
| `HIGH` | Override other plugins' decisions |
| `HIGHEST` | Final say before MONITOR |
| `MONITOR` | Read-only observation. Do not modify the event |

```python
@event(priority="HIGH")
async def player_chat(event):
    return f"[VIP] {event.message}"  # Override after other plugins
```

### Throttling

Two mechanisms prevent event spam:

**`once_per_tick`** — Only dispatch the first occurrence per server tick. Useful for events that fire many times per tick (e.g. `entity_move`):

```python
@event(once_per_tick=True)
async def entity_move(event):
    pass  # Called at most once per tick per subscription
```

**`throttle_ms`** — Minimum milliseconds between dispatches. Nanosecond-precision cooldown:

```python
@event(throttle_ms=100)
async def player_move(event):
    pass  # At most 10 dispatches per second
```

---

## Dispatch Flow

```flow
1. Bukkit event fires (e.g. PlayerJoinEvent)
         │
2. Java EventSubscription executor runs
   ├── Check once_per_tick: skip if already fired this tick
   └── Check throttle_ms: skip if cooldown not elapsed
         │
3. Java EventDispatcher serializes the event
   ├── Auto-extract fields via reflection (player, entity, block, etc.)
   └── For cancellable events: assign event ID, create PendingEvent
         │
4. Java → Python:
   {"type": "event", "event": "player_join", "payload": {...}, "id": 42}
         │
5. Python _dispatch_event() runs all registered @event handlers
   ├── Both sync and async handlers supported
   ├── All handlers for same event run concurrently (asyncio.gather)
   └── Exceptions are caught and logged, don't crash the script
         │
6. Python → Java (in order):
   a. {"type": "event_cancel", "id": 42}         (if event.cancel() called)
   b. {"type": "event_result", "id": 42, ...}    (if handler returned a value)
   c. {"type": "event_done", "id": 42}           (always sent last)
         │
7. Java applies modifications to the Bukkit event
   ├── Cancel: event.setCancelled(true)
   ├── Chat override: replace message text
   └── Damage override: event.setDamage(value)
```

### Payload auto-extraction

The Java EventDispatcher uses reflection to extract common event fields. It tries multiple getter names for compatibility across Bukkit versions:

```java
tryAddPayload(payload, event, "player", "getPlayer", "getWhoClicked");
tryAddPayload(payload, event, "entity", "getEntity");
tryAddPayload(payload, event, "block", "getBlock", "getClickedBlock");
tryAddPayload(payload, event, "inventory", "getInventory", "getClickedInventory");
```

Fields are serialized with the full bridge serializer, so you get proper proxy objects in Python (not raw JSON).

---

## Blocking Behavior

The Java event handler thread **blocks** while waiting for Python to respond. This is necessary for cancellation/modification to work — Java must wait for Python's answer before the event proceeds.

**Timeout:** 1 second. If Python doesn't respond in time, the event continues unmodified.

**While blocking**, Java calls `drainMainThreadQueue()` in a loop. This means Python's event handler can make API calls back to Java and they'll be processed — the event dispatch doesn't deadlock the main thread queue.

```java
while (System.currentTimeMillis() < deadline && pending.latch.getCount() > 0) {
    plugin.drainMainThreadQueue();  // Process API calls while waiting
    pending.latch.await(5, TimeUnit.MILLISECONDS);
}
```

### Implications

- Event handlers should be **fast**. Long operations delay the event (and the server tick).
- Each script receives events independently with its own timeout.
- Non-cancellable events (no `id` field) are fire-and-forget — Java doesn't block.

---

## Cancellation

Call `event.cancel()` inside any handler to cancel a cancellable event:

```python
@event
async def player_chat(event):
    if "bad_word" in event.message.lower():
        event.cancel()
        await event.player.send_message("§cWatch your language!")
```

Python sends `{"type": "event_cancel", "id": 42}` before `event_done`. Java sets `event.setCancelled(true)` on the Bukkit event.

Not all Bukkit events are cancellable. Non-cancellable events (like `player_join`) ignore cancel requests.

---

## Result Overrides

Handlers can modify event data by returning values:

### Chat message override

Return a string from a chat event handler to replace the message:

```python
@event
async def async_chat(event):
    return f"[{event.player.name}] {event.message}"
```

Sends: `{"type": "event_result", "id": 42, "result": "[Steve] Hello", "result_type": "chat"}`

### Damage override

Return a number from a damage event handler to change the damage amount:

```python
@event
async def entity_damage(event):
    if event.entity.type == "PLAYER":
        return event.damage * 0.5  # Half damage
```

Sends: `{"type": "event_result", "id": 42, "result": 2.5, "result_type": "damage"}`

### Multiple handlers

If multiple handlers return values, the last one wins. All handlers run concurrently via `asyncio.gather`, so ordering isn't guaranteed.

---

## Block Explosion Special Handling

Block explosion events (`block_explode`, `entity_explode`) get special treatment. Instead of one event for the entire explosion, Java creates one event per affected block and sends them as a batch:

```json
{"type": "event_batch", "event": "block_explode", "payloads": [{...}, {...}, ...]}
```

Each payload gets dispatched individually on the Python side. Cancelled blocks are removed from the explosion's block list — you can selectively protect blocks:

```python
@event
async def block_explode(event):
    if await event.block.get_type() == "DIAMOND_ORE":
        event.cancel()  # Protect diamond ore from explosions
```

---

## Event Name Mapping

Bukkit event class names are converted to snake_case for Python. The mapping strips common suffixes:

| Bukkit Class | Python Event Name |
| ------------ | ----------------- |
| `PlayerJoinEvent` | `player_join` |
| `AsyncChatEvent` | `async_chat` |
| `EntityDamageByEntityEvent` | `entity_damage_by_entity` |
| `BlockBreakEvent` | `block_break` |
| `InventoryClickEvent` | `inventory_click` |

The `Event` suffix is always stripped. CamelCase is split into snake_case.

---

## Command Registration

Commands follow the same pattern as events — a player action triggers a dispatch from Java to Python.

### The `@command` decorator

Python scripts register commands using the `@command` decorator:

```python
from bridge import command

@command
def greet(player, name: str, count: int = 1):
    for i in range(count):
        player.send_message(f"Hello, {name}!")
```

### Signature parsing

The decorator inspects the function's signature:

1. **First parameter** — Always the command sender (Player). Not included in usage.
2. **Subsequent parameters** — Command arguments
3. **Type annotations** — `str`, `int`, `float` for auto-conversion
4. **Default values** — Make arguments optional

Usage string auto-generated: `/greet <name> [count]`

### Java-side registration

When Python registers a command, it sends:

```json
{"type": "register_command", "name": "greet", "usage": "/greet <name> [count]", "description": "..."}
```

Java creates a `ScriptCommand` and registers it on Bukkit's `CommandMap`:

```java
ScriptCommand cmd = new ScriptCommand(name, usage, description, scriptInstance);
Bukkit.getCommandMap().register("pjb", cmd);
```

### Tab completion

Commands support tab completion. When a player presses Tab, Java sends a completion request to Python, which returns suggestions based on the current argument position and type.

### Command cleanup on shutdown

When a script is stopped or reloaded, its commands are unregistered:

```java
void unregisterCommands() {
    for (ScriptCommand cmd : registeredCommands) {
        cmd.unregister(Bukkit.getCommandMap());
    }
    registeredCommands.clear();
}
```

This means after a hot reload, commands are re-registered fresh from the new script.
