"""StateMachine extension — per-entity/player state machines for game phases."""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional, Set


class State:
    """A single state in a state machine.

    Args:
        name: Unique state identifier.
    """

    def __init__(self, name: str):
        self.name = name
        self._on_enter: List[Callable[..., Any]] = []
        self._on_exit: List[Callable[..., Any]] = []
        self._on_tick: List[Callable[..., Any]] = []
        self._transitions: Dict[str, str] = {}  # event -> target state name

    def on_enter(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: called when entering this state. Receives ``(entity, old_state)``."""
        self._on_enter.append(func)
        return func

    def on_exit(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: called when leaving this state. Receives ``(entity, new_state)``."""
        self._on_exit.append(func)
        return func

    def on_tick(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: called every tick while in this state. Receives ``(entity,)``."""
        self._on_tick.append(func)
        return func

    def transition(self, event: str, target: str):
        """Register that *event* should move to *target* state."""
        self._transitions[event] = target

    async def _fire(self, handlers: List[Callable[..., Any]], *args):
        for h in handlers:
            try:
                r = h(*args)
                if inspect.isawaitable(r):
                    await r
            except Exception:
                pass


class StateMachine:
    """Per-entity/player state machine for game phases.

    Example::

        sm = StateMachine("boss_fight")

        idle = sm.add_state("idle")
        combat = sm.add_state("combat")
        dead = sm.add_state("dead")

        idle.transition("aggro", "combat")
        combat.transition("die", "dead")
        dead.transition("respawn", "idle")

        @idle.on_enter
        async def enter_idle(entity, old_state):
            await entity.set_custom_name("&7Idle Boss")

        @combat.on_enter
        async def enter_combat(entity, old_state):
            await entity.set_custom_name("&cAngry Boss!")

        # Assign to an entity
        sm.attach(boss_entity)

        # Trigger events
        await sm.trigger(boss_entity, "aggro")   # idle -> combat
        await sm.trigger(boss_entity, "die")      # combat -> dead
    """

    def __init__(self, name: str = "state_machine"):
        self.name = name
        self._states: Dict[str, State] = {}
        self._initial: Optional[str] = None
        self._current: Dict[str, str | None] = {}  # entity_key -> current state name
        self._tick_task: Optional[asyncio.Task] = None
        self._tick_interval: int = 1
        self._attached: Set[str] = set()

    def add_state(self, name: str) -> State:
        """Add a state to this machine. The first added state becomes the initial state."""
        state = State(name)
        self._states[name] = state
        if self._initial is None:
            self._initial = name
        return state

    def get_state(self, name: str) -> Optional[State]:
        return self._states.get(name)

    @property
    def initial_state(self) -> Optional[str]:
        return self._initial

    @initial_state.setter
    def initial_state(self, name: str):
        if name in self._states:
            self._initial = name

    def _key(self, entity) -> str:
        """Get a unique key for the entity."""
        if hasattr(entity, "uuid"):
            return str(entity.uuid)
        return str(id(entity))

    def current_state(self, entity) -> Optional[str]:
        """Get the current state name for an entity."""
        return self._current.get(self._key(entity))

    def attach(self, entity):
        """Attach an entity to this state machine, placing it in the initial state."""
        key = self._key(entity)
        self._current[key] = self._initial
        self._attached.add(key)

    def detach(self, entity):
        """Remove an entity from this state machine."""
        key = self._key(entity)
        self._current.pop(key, None)
        self._attached.discard(key)

    async def trigger(self, entity, event: str) -> bool:
        """Trigger an event for the entity — transitions if the current state handles it.

        Returns True if a transition occurred, False otherwise.
        """
        key = self._key(entity)
        cur_name = self._current.get(key)
        if cur_name is None:
            return False
        cur_state = self._states.get(cur_name)
        if cur_state is None:
            return False
        target_name = cur_state._transitions.get(event)
        if target_name is None or target_name not in self._states:
            return False

        target_state = self._states[target_name]
        # Exit old state
        await cur_state._fire(cur_state._on_exit, entity, target_name)
        # Transition
        self._current[key] = target_name
        # Enter new state
        await target_state._fire(target_state._on_enter, entity, cur_name)
        return True

    async def force_state(self, entity, state_name: str):
        """Force an entity into a specific state, firing exit/enter callbacks."""
        key = self._key(entity)
        old_name = self._current.get(key)
        if state_name not in self._states:
            return
        if old_name and old_name in self._states:
            await self._states[old_name]._fire(self._states[old_name]._on_exit, entity, state_name)
        self._current[key] = state_name
        await self._states[state_name]._fire(self._states[state_name]._on_enter, entity, old_name)

    def start_ticking(self, interval_ticks: int = 1, entity_resolver: Optional[Callable[..., Any]] = None):
        """Start a tick loop that calls ``on_tick`` handlers for all attached entities.

        Args:
            interval_ticks: Ticks between updates.
            entity_resolver: Optional callable that receives a key and returns the entity object.
                If not provided, tick handlers receive the key string.
        """
        import bridge

        self._tick_interval = interval_ticks

        async def _loop():
            while True:
                for key in list(self._attached):
                    state_name = self._current.get(key)
                    if state_name and state_name in self._states:
                        state = self._states[state_name]
                        entity = entity_resolver(key) if entity_resolver else key
                        if entity is not None:
                            await state._fire(state._on_tick, entity)
                await bridge.server.after(self._tick_interval)

        self._tick_task = asyncio.ensure_future(_loop())
        return self._tick_task

    def stop_ticking(self):
        """Stop the tick loop."""
        if self._tick_task:
            self._tick_task.cancel()
            self._tick_task = None
