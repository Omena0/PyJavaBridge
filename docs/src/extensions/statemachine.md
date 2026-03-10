---
title: StateMachine
subtitle: Per-entity/player finite state machines for game phases
---

# StateMachine [ext]

`StateMachine` manages per-entity state transitions for game phases, boss fights, NPC behavior, and more. Each entity attached to a state machine has a current state, and events trigger transitions between states.

```python
from bridge.extensions import StateMachine

sm = StateMachine("boss_fight")

idle = sm.add_state("idle")
combat = sm.add_state("combat")
dead = sm.add_state("dead")

idle.transition("aggro", "combat")
combat.transition("die", "dead")
dead.transition("respawn", "idle")
```

## Import

```python
from bridge.extensions import StateMachine, State
```

> **Note:** The `State` class here is `bridge.extensions.state_machine.State`, not `bridge.helpers.State`.

## StateMachine

### Constructor

```python
sm = StateMachine(name="state_machine")
```

- **Parameters:**
  - `name` *(str)* — State machine identifier.

### Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `initial_state` | `str \| None` | Name of the initial state (get/set) |

### Methods

#### .add_state(name)

Add a state. The first added state becomes the initial state.

- **Parameters:**
  - `name` *(str)* — Unique state name.
- **Returns:** `State`

#### .get_state(name)

- **Returns:** `State | None`

#### .current_state(entity)

Get the current state name for an entity.

- **Returns:** `str | None`

#### .attach(entity)

Attach an entity to this state machine, placing it in the initial state.

#### .detach(entity)

Remove an entity from this state machine.

#### await .trigger(entity, event)

Trigger an event for the entity. If the current state has a transition for this event, the state changes.

- **Parameters:**
  - `entity` — The entity.
  - `event` *(str)* — Event name.
- **Returns:** `bool` — `True` if a transition occurred.

```python
transitioned = await sm.trigger(boss, "aggro")
```

#### await .force_state(entity, state_name)

Force an entity into a specific state, firing exit/enter callbacks.

#### .start_ticking(interval_ticks=1, entity_resolver=None)

Start a tick loop that calls `on_tick` handlers for all attached entities.

- **Parameters:**
  - `interval_ticks` *(int)* — Ticks between updates. Default `1`.
  - `entity_resolver` *(Callable | None)* — Function `(key) -> entity` to resolve entities from their keys.
- **Returns:** `asyncio.Task`

#### .stop_ticking()

Stop the tick loop.

---

## State

A single state with enter/exit/tick callbacks and event transitions.

### Constructor

```python
state = State(name)
```

### Decorators

#### @state.on_enter

Called when an entity enters this state. Receives `(entity, old_state_name)`.

```python
@combat.on_enter
async def enter_combat(entity, old_state):
    await entity.set_custom_name("&cAngry!")
```

#### @state.on_exit

Called when an entity leaves this state. Receives `(entity, new_state_name)`.

#### @state.on_tick

Called every tick while an entity is in this state. Receives `(entity,)`.

```python
@combat.on_tick
async def combat_tick(entity):
    # Attack nearest player every tick
    pass
```

### Methods

#### .transition(event, target)

Register that `event` should transition to `target` state.

- **Parameters:**
  - `event` *(str)* — Event name.
  - `target` *(str)* — Target state name.

---

## Full Example

```python
from bridge import *
from bridge.extensions import StateMachine

sm = StateMachine("guard")

patrol = sm.add_state("patrol")
alert = sm.add_state("alert")
chase = sm.add_state("chase")

patrol.transition("see_enemy", "alert")
alert.transition("confirm_enemy", "chase")
alert.transition("timeout", "patrol")
chase.transition("lost_target", "patrol")

@patrol.on_tick
async def patrol_tick(entity):
    # Walk along patrol route
    pass

@alert.on_enter
async def alert_enter(entity, old):
    entity.custom_name = "&eAlert!"

@chase.on_enter
async def chase_enter(entity, old):
    entity.custom_name = "&cChasing!"

# Attach an NPC
sm.attach(guard_entity)
sm.start_ticking(interval_ticks=5)
```
