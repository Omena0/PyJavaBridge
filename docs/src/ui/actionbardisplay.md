---
title: ActionBarDisplay
subtitle: Persistent action bar text
---

# ActionBarDisplay

`ActionBarDisplay` manages persistent action bar messages per player. Unlike `player.send_action_bar()` which fades after a few seconds, `ActionBarDisplay` continuously re-sends the message to keep it visible.

---

## Constructor

```python
ActionBarDisplay()
```

Create a new action bar display manager.

```python
status = ActionBarDisplay()
```

---

## Player Access

ActionBarDisplay uses `[]` notation with players as keys.

### Set text

```python
display[player] = text
```

Start showing persistent action bar text to a player.

- **Parameters:**
  - `player` ([`Player`](player.md)) — Target player.
  - `text` (`str`) — Action bar text. Supports `§` color codes.

### Get text

```python
text = display[player]
```

Get the current action bar text for a player.

- **Returns:** `str`

### Remove

```python
del display[player]
```

Stop showing action bar text to a player.

---

## Example: Status bar

```python
from bridge import *

status_bar = ActionBarDisplay()

@event
async def player_join(e: Event):
    p = e.player
    status_bar[p] = f"§a❤ {int(p.health)}/20 §7| §e⚔ Kills: 0"

@event
async def entity_damage(e: Event):
    if hasattr(e.player, 'name'):
        p = e.player
        status_bar[p] = f"§a❤ {int(p.health)}/20 §7| §c-{e.damage}"

@event
async def player_quit(e: Event):
    del status_bar[e.player]
```

## Example: Ability cooldown indicator

```python
from bridge import *

cd_display = ActionBarDisplay()
ability_cd = Cooldown(seconds=5.0)

@command("Use ability")
async def ability(player: Player, args: list[str]):
    if not ability_cd.check(player):
        r = ability_cd.remaining(player)
        cd_display[player] = f"§c⏳ Cooldown: {r:.1f}s"
        return

    cd_display[player] = "§a✓ Ability used!"
    await player.send_message("§aAbility activated!")
```
