---
title: Leaderboard [ext]
subtitle: Hologram-based live leaderboard
---

# Leaderboard [ext]

`Leaderboard` creates a floating hologram that displays a sorted leaderboard.

```python
from bridge.extensions import Leaderboard
```

---

## Constructor

```python
Leaderboard(location, title="Leaderboard", get_metric=None,
            update_interval=100, max_entries=10)
```

- **Parameters:**
  - `location` — World location for the hologram.
  - `title` (`str`) — Header line.
  - `get_metric` (`Callable[[Player], float] | None`) — Metric getter.
  - `update_interval` (`int`) — Ticks between refreshes (default 100).
  - `max_entries` (`int`) — Number of entries to display.

---

## Methods

### start()

Create the hologram and begin the auto-update loop.

### stop()

Remove the hologram and stop updating.

---

## Decorators

### @leaderboard.metric

Register the metric getter.

```python
lb = Leaderboard(some_location, title="Top Kills")

@lb.metric
def get_kills(player):
    return stats[player]["kills"]

lb.start()
```
