"""Region extension — cuboid region with enter/exit events."""
from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Optional

import bridge

class Region:
    """Cuboid region in a world with enter/exit callbacks.

    Args:
        name: Region identifier.
        world: World name or World object.
        x1, y1, z1: First corner.
        x2, y2, z2: Second corner.
    """

    _all_regions: List["Region"] = []
    _tracker_started = False

    def __init__(self, name: str, world: Any,
            x1: float, y1: float, z1: float,
            x2: float, y2: float, z2: float):
        """Initialise a new Region."""
        self.name = name
        self._world = str(world.name) if hasattr(world, "name") else str(world)
        self.x1, self.y1, self.z1 = min(x1, x2), min(y1, y2), min(z1, z2)
        self.x2, self.y2, self.z2 = max(x1, x2), max(y1, y2), max(z1, z2)
        self._enter_handlers: List[Callable[..., Any]] = []
        self._exit_handlers: List[Callable[..., Any]] = []
        self._inside: Dict[str, bool] = {}  # puuid -> was inside
        Region._all_regions.append(self)
        Region._ensure_tracker()

    @property
    def world(self) -> str:
        """The world value."""
        return self._world

    def contains(self, location: Any) -> bool:
        """Check if a location is inside this region."""
        x = location.x if hasattr(location, "x") else location[0]
        y = location.y if hasattr(location, "y") else location[1]
        z = location.z if hasattr(location, "z") else location[2]
        w = location.world.name if hasattr(location, "world") and hasattr(location.world, "name") else None
        if w is not None and w != self._world:
            return False

        return (self.x1 <= x <= self.x2 and
            self.y1 <= y <= self.y2 and
            self.z1 <= z <= self.z2)

    def is_inside(self, player: Any) -> bool:
        """Check if inside."""
        return self._inside.get(str(player.uuid), False)

    def on_enter(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(player, region)`` when a player enters."""
        self._enter_handlers.append(handler)
        return handler

    def on_exit(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(player, region)`` when a player exits."""
        self._exit_handlers.append(handler)
        return handler

    def remove(self):
        """Remove this object."""
        if self in Region._all_regions:
            Region._all_regions.remove(self)

    @classmethod
    def _ensure_tracker(cls):
        """Ensure tracker."""
        if cls._tracker_started:
            return

        cls._tracker_started = True
        asyncio.ensure_future(cls._track_loop())

    @classmethod
    async def _track_loop(cls):
        """Asynchronously handle track loop."""
        from bridge import server
        while True:
            try:
                online = server.players
                for region in list(cls._all_regions):
                    for p in online:
                        puuid = str(p.uuid)
                        try:
                            loc = p.location
                            inside = region.contains(loc)
                        except Exception:
                            inside = False

                        was = region._inside.get(puuid, False)
                        region._inside[puuid] = inside
                        if inside and not was:
                            for h in region._enter_handlers:
                                try:
                                    r = h(p, region)
                                    if inspect.isawaitable(r):
                                        await r
                                except Exception:
                                    pass
                        elif not inside and was:
                            for h in region._exit_handlers:
                                try:
                                    r = h(p, region)
                                    if inspect.isawaitable(r):
                                        await r
                                except Exception:
                                    pass

                await server.after(10)
            except Exception:
                break
