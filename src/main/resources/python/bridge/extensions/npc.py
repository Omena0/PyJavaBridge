"""NPC extension — fake NPCs with AI disabled, click handlers, dialog, and movement paths."""
from __future__ import annotations

import asyncio
import inspect
import sys
from typing import Any, Callable, Dict, List, Optional
from bridge.connection import BridgeConnection

# Injected by bridge.__init__ during _bootstrap()
_connection:BridgeConnection = None  # type: ignore[assignment]

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def print(*args):
    _print(*args, file=sys.stderr)

_npc_registry: Dict[str, "NPC"] = {}
_npc_listener_registered = False


class NPC:
    """Fake NPC helper — spawns a mob with AI disabled, click handlers, dialog, and movement paths."""

    def __init__(self, entity: Any, name: str | None = None):
        from bridge.wrappers import Location
        self._entity = entity
        self._name = name
        self._click_handlers: List[Callable] = []
        self._right_click_handlers: List[Callable] = []
        self._dialog: List[str] = []
        self._dialog_index: Dict[str, int] = {}
        self._path: List[Location] = []
        self._path_loop = False
        self._path_task = None
        self._linked_dialog: Any = None  # Dialog object
        self._linked_player: Any = None  # Player to mimic skin of
        self._range: Optional[float] = None
        self._range_exit_handlers: List[Callable] = []
        self._range_enter_handlers: List[Callable] = []
        self._tracked_players: Dict[str, bool] = {}  # uuid -> was_in_range
        self._range_task_started = False
        uuid = entity.uuid
        if uuid:
            _npc_registry[str(uuid)] = self

    @classmethod
    async def spawn(cls, location: Any, entity_type: Any = "VILLAGER",
                    name: str | None = None, **kwargs: Any) -> NPC:
        """Spawn an NPC at a location. AI is disabled automatically."""
        from bridge.wrappers import Entity
        entity = await Entity.spawn(entity_type, location, **kwargs)
        if name:
            await entity.set_custom_name(name)
            await entity.set_custom_name_visible(True)
        await entity.set_aware(False)
        npc = cls(entity, name)
        _ensure_npc_listener()
        return npc

    @property
    def entity(self) -> Any:
        return self._entity

    @property
    def uuid(self) -> Optional[str]:
        return self._entity.uuid

    @property
    def location(self):
        return self._entity.location

    def on_click(self, handler: Callable) -> Callable:
        """Register a click handler. Handler receives (player, npc)."""
        self._click_handlers.append(handler)
        _ensure_npc_listener()
        return handler

    def on_right_click(self, handler: Callable) -> Callable:
        """Register a right-click handler. Handler receives (player, npc)."""
        self._right_click_handlers.append(handler)
        _ensure_npc_listener()
        return handler

    def dialog(self, messages: List[str], loop: bool = False):
        """Set a dialog sequence shown on right-click."""
        self._dialog = list(messages)
        self._dialog_loop = loop
        _ensure_npc_listener()

    async def move_to(self, location: Any, speed: float = 1.0):
        """Move the NPC to a location using pathfinding."""
        await self._entity.set_aware(True)
        return self._entity.pathfind_to(location, speed)

    async def follow_path(self, waypoints: list, loop: bool = False,
                          speed: float = 1.0, delay: float = 0.5):
        """Make the NPC follow a path of waypoints."""
        self._path = list(waypoints)
        self._path_loop = loop
        if self._path_task:
            self._path_task = None
        self._path_task = True
        await self._entity.set_aware(True)
        idx = 0
        while self._path_task and idx < len(self._path):
            self._entity.pathfind_to(self._path[idx], speed)
            await asyncio.sleep(delay)
            idx += 1
            if idx >= len(self._path) and loop:
                idx = 0
        await self._entity.set_aware(False)

    def stop_path(self):
        """Stop the current path."""
        self._path_task = None
        self._entity.stop_pathfinding()
        self._entity.set_aware(False)

    async def remove(self):
        """Remove the NPC entity and unregister."""
        uuid = self.uuid
        if uuid:
            _npc_registry.pop(str(uuid), None)
        await self._entity.remove()

    async def _handle_interact(self, player: Any, is_right_click: bool):
        """Internal: process interaction."""
        if is_right_click and self._dialog:
            puuid = player.uuid or ""
            idx = self._dialog_index.get(puuid, 0)
            if idx < len(self._dialog):
                await player.send_message(self._dialog[idx])
                idx += 1
                if idx >= len(self._dialog):
                    idx = 0 if getattr(self, "_dialog_loop", False) else len(self._dialog) - 1
                self._dialog_index[puuid] = idx

        handlers = self._right_click_handlers if is_right_click else self._click_handlers
        for handler in handlers:
            try:
                result = handler(player, self)
                if inspect.isawaitable(result):
                    await result
            except Exception as e:
                print(f"[PyJavaBridge] NPC handler error: {e}")


def _ensure_npc_listener():
    global _npc_listener_registered
    if _npc_listener_registered:
        return
    _npc_listener_registered = True

    from bridge.wrappers import Player, Event

    async def _on_npc_interact(event: Event):
        entity = event.fields.get("entity")
        if entity is None or not hasattr(entity, "fields"):
            return
        uuid = entity.fields.get("uuid")
        if not uuid:
            return
        npc = _npc_registry.get(str(uuid))
        if npc is None:
            return

        player = event.fields.get("player")
        if player is None:
            return
        p = Player(fields=player.fields) if hasattr(player, "fields") else player

        action = event.fields.get("action") if hasattr(event, "fields") else None
        is_right = action != "ATTACK" if action else True

        await npc._handle_interact(p, is_right)

    _connection.on("player_interact_entity", _on_npc_interact)
    _connection.subscribe("player_interact_entity", False)
