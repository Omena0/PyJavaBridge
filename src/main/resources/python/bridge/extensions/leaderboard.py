"""Leaderboard extension — Hologram-based live leaderboard."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

import bridge

class Leaderboard:
    """Hologram that displays a sorted leaderboard.

    Args:
        location: World location for the hologram.
        title: Leaderboard title line.
        get_metric: Callable ``(player) -> float|int`` returning the stat.
        update_interval: Ticks between refreshes (default 100 = 5s).
        max_entries: Number of entries to show.
    """

    _MEDALS = ("§6", "§7", "§c")

    def __init__(self, location: Any, title: str = "Leaderboard",
            get_metric: Optional[Callable[..., Any]] = None,
            update_interval: int = 100, max_entries: int = 10) -> None:
        """Initialise a new Leaderboard."""
        self._location = location
        self.title = title
        self._get_metric = get_metric
        self.update_interval = update_interval
        self.max_entries = max_entries
        self._hologram: Optional[bridge.Hologram] = None
        self._running = False

    def start(self) -> None:
        """Create the hologram and start the update loop."""
        if self._hologram is None:
            self._hologram = bridge.Hologram(self._location, self.title)

        self._running = True
        asyncio.ensure_future(self._update_loop())

    def stop(self) -> None:
        """Return the stop."""
        self._running = False
        if self._hologram is not None:
            self._hologram.remove()
            self._hologram = None

    def metric(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: register the metric getter ``(player) -> number``."""
        self._get_metric = func
        return func

    async def _update_loop(self) -> None:
        """Update the loop."""
        from bridge import server
        while self._running:
            try:
                await self._refresh()
                await server.after(self.update_interval)
            except Exception:
                break

    async def _refresh(self) -> None:
        """Asynchronously handle refresh."""
        from bridge import server
        if self._hologram is None or self._get_metric is None:
            return

        online = server.players
        scores: List[tuple[str, float]] = []
        for p in online:
            try:
                val = self._get_metric(p)
                if asyncio.iscoroutine(val):
                    val = await val

                scores.append((str(p.name), float(val)))
            except Exception:
                pass

        scores.sort(key=lambda x: x[1], reverse=True)
        scores = scores[:self.max_entries]

        lines = [f"§e§l{self.title}"]
        for i, (name, val) in enumerate(scores):
            medal = self._MEDALS[i] if i < 3 else "§f"
            lines.append(f"{medal}#{i + 1} §f{name}: §a{val:.0f}")

        # Update hologram lines
        while len(self._hologram) > len(lines):
            del self._hologram[len(self._hologram) - 1]

        for i, line in enumerate(lines):
            if i < len(self._hologram):
                self._hologram[i] = line
            else:
                self._hologram.append(line)
