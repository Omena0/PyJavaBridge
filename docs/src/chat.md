---
title: Chat
subtitle: Chat broadcast helper
---

# Chat

The `Chat` helper provides broadcast functionality. An instance is available as the global `chat` variable.

---

## Global Instance

```python
from bridge import chat
```

---

## Methods

### broadcast

```python
await chat.broadcast(message)
```

Send a message to all online players.

- **Parameters:**
  - `message` (`str`) — Message text. Supports `§` color codes.
- **Returns:** `Awaitable[None]`

```python
await chat.broadcast("§a§lServer restarting in 5 minutes!")
```

---

## Chat vs Server.broadcast

Both `chat.broadcast()` and `server.broadcast()` send messages to all players:

```python
# These are equivalent
await chat.broadcast("Hello everyone!")
await server.broadcast("Hello everyone!")
```

The `chat` helper exists for convenience and semantic clarity when your script is focused on chat operations.

---

## Example: Announcement system

```python
from bridge import *

@command("Announce a message")
async def announce(player: Player, args: list[str]):
    if not args:
        await player.send_message("§cUsage: /announce <message>")
        return

    message = " ".join(args)
    await chat.broadcast(f"§6§l[Announcement] §f{message}")
```
