---
title: Quest [ext]
subtitle: Quest system with progress tracking
---

# Quest [ext]

`Quest` and `QuestTree` provide a player quest system with progress tracking, time limits, and BossBar integration.

```python
from bridge.extensions import Quest, QuestTree
```

---

## Quest

### Constructor

```python
Quest(name, description="", time_limit=None)
```

- **Parameters:**
  - `name` (`str`) — Quest name.
  - `description` (`str`) — Flavour text.
  - `time_limit` (`float | None`) — Seconds to complete (None = unlimited).

### Lifecycle

`accept(player)` → `start(player)` → `complete(player)` / `fail(player)` / `end(player)`

### Decorators

```python
quest = Quest("Slay the Dragon", time_limit=300)

@quest.on_complete
def completed(player, quest):
    player.send_message("§aQuest complete!")

@quest.progress_getter
def progress(quest, player):
    return kills.get(player, 0) / 10  # 0.0 – 1.0
```

### BossBar Integration

```python
quest.show_bar(player)   # show progress/timer bar
quest.hide_bar(player)   # remove it
```

---

## QuestTree

Layered quest progression. When all quests in a layer are complete, the next layer unlocks.

```python
tree = QuestTree([
    [intro_quest],
    [quest_a, quest_b],
    [final_quest],
])

tree.current_depth(player)  # current layer index
tree.available(player)      # quests the player can start
tree.is_complete(player)    # all layers done?
```
