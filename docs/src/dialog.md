---
title: Dialog [ext]
subtitle: Branching NPC dialog sequences
---

# Dialog [ext]

`Dialog` and `DialogEntry` create branching conversational sequences.

```python
from bridge.extensions import Dialog, DialogEntry
```

---

## DialogEntry

A single dialog node.

```python
DialogEntry(speaker, text, answers=None, delay=None)
```

- **Parameters:**
  - `speaker` (`str`) — Speaker name.
  - `text` (`str`) — Message text.
  - `answers` (`list[tuple[str, DialogEntry | Callable]] | None`) — Answer choices: `(text, next_entry_or_callback)`.
  - `delay` (`float | None`) — Auto-advance seconds (if no answers or timeout).

---

## Dialog

### Constructor

```python
Dialog(root)
```

- **Parameters:**
  - `root` (`DialogEntry`) — Starting entry.

### Methods

#### start(player) → Awaitable

Begin the dialog for a player.

#### stop(player)

Abort the dialog.

#### is_active(player) → bool

Whether the player is mid-dialog.

---

## Example

```python
farewell = DialogEntry("Bob", "Goodbye!", delay=3)
greeting = DialogEntry("Bob", "Hello! Want to trade?", answers=[
    ("Yes", trade_entry),
    ("No", farewell),
])
dialog = Dialog(greeting)
await dialog.start(player)
```
