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
            x2: float, y2: float, z2: float) -> None:
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

    def remove(self) -> None:
        """Remove this object."""
        if self in Region._all_regions:
            Region._all_regions.remove(self)

    @classmethod
    def _ensure_tracker(cls) -> None:
        """Ensure tracker."""
        if cls._tracker_started:
            return

        cls._tracker_started = True
        asyncio.ensure_future(cls._track_loop())

    @classmethod
    async def _track_loop(cls) -> None:
        """Asynchronously handle track loop."""
        from bridge import server
        while True:
            try:
                online = server.players
                # Pre-fetch all player locations once per tick (avoid repeated bridge calls)
                player_data: list[tuple[Any, str, Any]] = []
                for p in online:
                    try:
                        player_data.append((p, str(p.uuid), p.location))
                    except Exception:
                        pass

                for region in list(cls._all_regions):
                    rx1, ry1, rz1 = region.x1, region.y1, region.z1
                    rx2, ry2, rz2 = region.x2, region.y2, region.z2
                    rworld = region._world
                    for p, puuid, loc in player_data:
                        try:
                            x = loc.x if hasattr(loc, "x") else loc[0]
                            y = loc.y if hasattr(loc, "y") else loc[1]
                            z = loc.z if hasattr(loc, "z") else loc[2]
                            w = loc.world.name if hasattr(loc, "world") and hasattr(loc.world, "name") else None
                            if w is not None and w != rworld:
                                inside = False
                            else:
                                inside = (rx1 <= x <= rx2 and ry1 <= y <= ry2 and rz1 <= z <= rz2)
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
                try:
                    await asyncio.sleep(0.5)
                except Exception:
                    break
