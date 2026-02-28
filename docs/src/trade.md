---
title: TradeWindow [ext]
subtitle: Two-player trade GUI
---

# TradeWindow [ext]

`TradeWindow` opens a synchronized trade interface between two players.

```python
from bridge.extensions import TradeWindow
```

---

## Constructor

```python
TradeWindow(bank=None, delay=3)
```

- **Parameters:**
  - `bank` (`Bank | None`) — Optional bank for balance adjustments.
  - `delay` (`int`) — Countdown seconds after both confirm (anti-dupe).

---

## Methods

### open(p1, p2)

Open the trade GUI for both players.

### close(player)

Close the trade for both participants.

---

## Decorators

### @trade.on_trade

```python
@trade.on_trade
def traded(p1, p2, session):
    print(f"Trade between {p1.name} and {p2.name} completed")
```

---

## Features

- Both players see each other's offers in real time.
- Balance adjustment buttons (+1, +10, -1) when a bank is set.
- Both must confirm before the trade executes.
- Anti-dupe countdown delay.
- Cancelling resets the confirm state.
