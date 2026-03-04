"""VisualEffect extension — sequenced particle/sound effects."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, List, Optional
from bridge.types import async_task

class VisualEffect:
    """A reusable sequence of particle effects, sounds, and delays.

    Each step is a callable ``(location) -> None`` (may be async).
    Steps run one after another — use ``await server.after(ticks)``
    inside a step to add pauses.

    Example::

        vfx = VisualEffect("explosion")
        @vfx.step
        async def _boom(loc):
            await server.spawn_particle("EXPLOSION_LARGE", loc, count=5)
            await server.after(5)
            await server.play_sound(loc, "ENTITY_GENERIC_EXPLODE")

        await vfx.trigger(some_location)
    """

    def __init__(self, name: str = "effect"):
        self.name = name
        self._steps: List[Callable[..., Any]] = []

    def step(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: append *func* as the next step in the sequence."""
        self._steps.append(func)
        return func

    def add_step(self, func: Callable[..., Any]):
        """Imperatively add a step."""
        self._steps.append(func)

    @async_task
    async def trigger(self, location: Any):
        """Play the full effect sequence at *location*."""
        for step in self._steps:
            result = step(location)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                await result

