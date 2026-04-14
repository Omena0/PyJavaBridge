"""NPC extension — fake NPCs with AI disabled, click handlers, dialog, and movement paths."""
from __future__ import annotations

import asyncio
import inspect
import sys
from typing import Any, Callable, Dict, List, Optional
from bridge.connection import BridgeConnection
from bridge.types import async_task

# Injected by bridge.__init__ during _bootstrap()
_connection:BridgeConnection = None  # type: ignore[assignment]

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def print(*args: Any) -> None:
    """Return the print."""
    _print(*args, file=sys.stderr)

_npc_registry: Dict[str, "NPC"] = {}
_npc_listener_registered = False

class NPC:
    """Fake NPC helper — spawns a mob with AI disabled, click handlers, dialog, and movement paths."""

    def __init__(self, entity: Any, name: str | None = None) -> None:
        """Initialise a new NPC."""
        from bridge import Location
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

    @async_task
    @classmethod
    async def spawn(cls, location: Any, entity_type: Any = "VILLAGER",
            name: str | None = None, **kwargs: Any) -> NPC:
        """Spawn an NPC at a location. AI is disabled automatically."""
        from bridge import Entity
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
        """The entity value."""
        return self._entity

    @property
    def uuid(self) -> Optional[str]:
        """The uuid value."""
        return self._entity.uuid

    @property
    def location(self) -> Any:
        """The location value."""
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

    def dialog(self, messages: List[str], loop: bool = False) -> None:
        """Set a dialog sequence shown on right-click."""
        self._dialog = list(messages)
        self._dialog_loop = loop
        _ensure_npc_listener()

    @async_task
    async def move_to(self, location: Any, speed: float = 1.0) -> Any:
        """Move the NPC to a location using pathfinding."""
        await self._entity.set_aware(True)
        return self._entity.pathfind_to(location, speed)

    @async_task
    async def follow_path(self, waypoints: list, loop: bool = False,
            speed: float = 1.0, delay: float = 0.5) -> None:
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

    def stop_path(self) -> None:
        """Stop the current path."""
        self._path_task = None
        self._entity.stop_pathfinding()
        self._entity.set_aware(False)

    def link_dialog(self, dialog: Any) -> None:
        """Link a Dialog object — right-clicking starts the dialog."""
        self._linked_dialog = dialog
        _ensure_npc_listener()

    def link_player(self, player: Any) -> None:
        """Link a Player. Used for range check."""
        self._linked_player = player

    def set_range(self, distance: float) -> None:
        """Set a range check distance. Use on_range_enter/on_range_exit for callbacks."""
        self._range = distance
        if not self._range_task_started:
            self._range_task_started = True
            asyncio.ensure_future(self._range_check_loop())

    def on_range_enter(self, handler: Callable) -> Callable:
        """Register a callback for when a player enters range. Receives (player, npc)."""
        self._range_enter_handlers.append(handler)
        return handler

    def on_range_exit(self, handler: Callable) -> Callable:
        """Register a callback for when a player exits range. Receives (player, npc)."""
        self._range_exit_handlers.append(handler)
        return handler

    async def _range_check_loop(self) -> None:
        """Asynchronously handle range check loop."""
        from bridge import server, Player
        while self._range is not None:
            try:
                npc_loc = self._entity.location
                if npc_loc is None:
                    await server.after(20)
                    continue

                # Cache NPC coords and pre-compute squared range to avoid sqrt per player
                npc_x, npc_y, npc_z = npc_loc.x, npc_loc.y, npc_loc.z
                range_sq = self._range * self._range
                online = server.players
                for p in online:
                    puuid = str(p.uuid)
                    try:
                        ploc = p.location
                        dx = ploc.x - npc_x
                        dy = ploc.y - npc_y
                        dz = ploc.z - npc_z
                        in_range = (dx * dx + dy * dy + dz * dz) <= range_sq
                    except Exception:
                        in_range = False

                    was_in = self._tracked_players.get(puuid, False)
                    self._tracked_players[puuid] = in_range
                    if in_range and not was_in:
                        for h in self._range_enter_handlers:
                            try:
                                result = h(p, self)
                                if inspect.isawaitable(result):
                                    await result
                            except Exception as e:
                                print(f"[PyJavaBridge] NPC range enter error: {e}")
                    elif not in_range and was_in:
                        for h in self._range_exit_handlers:
                            try:
                                result = h(p, self)
                                if inspect.isawaitable(result):
                                    await result
                            except Exception as e:
                                print(f"[PyJavaBridge] NPC range exit error: {e}")

                await server.after(10)
            except Exception:
                break

    @async_task
    async def remove(self) -> None:
        """Remove the NPC entity and unregister."""
        uuid = self.uuid
        if uuid:
            _npc_registry.pop(str(uuid), None)

        await self._entity.remove()

    async def _handle_interact(self, player: Any, is_right_click: bool) -> None:
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

def _ensure_npc_listener() -> None:
    """Ensure npc listener."""
    global _npc_listener_registered
    if _npc_listener_registered:
        return

    _npc_listener_registered = True

    from bridge import Player, Event

    async def _on_npc_interact(event: Event) -> None:
        """Handle the npc interact event."""
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
