"""Quest system — Quest, QuestTree for RPG progression."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

import bridge

class Quest:
    """Base quest class with progress tracking and BossBarDisplay integration.

    Designed to be subclassed. Override ``progress_getter`` to compute
    progress for a player (should return 0.0 – 1.0).

    Args:
        name: Quest display name.
        description: Quest description text.
        time_limit: Optional time limit in seconds.
    """
    __slots__ = ("name", "description", "time_limit", "_status",
                 "_start_times", "_end_times", "_on_complete",
                 "_progress_getter", "_bar")

    def __init__(self, name: str, description: str = "",
            time_limit: Optional[float] = None):
        """Initialise a new Quest."""
        self.name = name
        self.description = description
        self.time_limit = time_limit
        self._status: Dict[str, str] = {}  # player uuid -> status
        self._start_times: Dict[str, float] = {}
        self._end_times: Dict[str, float] = {}
        self._on_complete: Optional[Callable[..., Any]] = None
        self._progress_getter: Optional[Callable[..., float]] = None
        self._bar: Optional[bridge.BossBarDisplay] = None

    # -- decorator setters --
    def on_complete(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator to register a completion callback ``(quest, player)``."""
        self._on_complete = func
        return func

    def progress_getter(self, func: Callable[..., float]) -> Callable[..., float]:
        """Decorator to register a progress getter ``(quest, player) -> float``."""
        self._progress_getter = func
        return func

    # -- status helpers --
    def status(self, player: Any) -> str:
        """Handle status."""
        return self._status.get(str(player.uuid), "not_started")

    def progress(self, player: Any) -> float:
        """Handle progress."""
        if self._progress_getter is not None:
            return self._progress_getter(self, player)

        return 0.0

    def start_time(self, player: Any) -> Optional[float]:
        """Start the time."""
        return self._start_times.get(str(player.uuid))

    def end_time(self, player: Any) -> Optional[float]:
        """Handle end time."""
        return self._end_times.get(str(player.uuid))

    # -- lifecycle --
    def accept(self, player: Any):
        """Accept the quest."""
        puuid = str(player.uuid)
        if self._status.get(puuid) in (None, "not_started", "failed"):
            self._status[puuid] = "accepted"

    def start(self, player: Any):
        """Start the process."""
        puuid = str(player.uuid)
        self._status[puuid] = "active"
        self._start_times[puuid] = time.time()
        if self.time_limit is not None:
            asyncio.ensure_future(self._time_limit_task(player))

    def complete(self, player: Any):
        """Mark as complete."""
        puuid = str(player.uuid)
        self._status[puuid] = "completed"
        self._end_times[puuid] = time.time()
        if self._on_complete is not None:
            result = self._on_complete(self, player)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                asyncio.ensure_future(result)

    def fail(self, player: Any):
        """Mark as failed."""
        puuid = str(player.uuid)
        self._status[puuid] = "failed"
        self._end_times[puuid] = time.time()

    def end(self, player: Any):
        """End the quest regardless of progress (marks completed)."""
        self.complete(player)

    # -- bossbar integration --
    def show_bar(self, player: Any, color: str = "GREEN", style: str = "SEGMENTED_10"):
        """Show the bar."""
        if self._bar is None:
            self._bar = bridge.BossBarDisplay(self.name, color, style)

        self._bar.show(player)
        asyncio.ensure_future(self._bar_update_task(player))

    def hide_bar(self, player: Any):
        """Hide the bar."""
        if self._bar is not None:
            self._bar.hide(player)

    async def _bar_update_task(self, player: Any):
        """Asynchronously handle bar update task."""
        from bridge import server
        while self.status(player) == "active":
            prog = self.progress(player)
            if self._bar is not None:
                self._bar.progress = prog
                if self.time_limit is not None:
                    elapsed = time.time() - self._start_times.get(str(player.uuid), time.time())
                    remaining = max(0, self.time_limit - elapsed)
                    self._bar.text = f"{self.name} — {int(remaining)}s"
                else:
                    self._bar.text = f"{self.name} — {int(prog * 100)}%"

            if prog >= 1.0:
                self.complete(player)
                break

            try:
                await server.after(20)
            except Exception:
                break

    async def _time_limit_task(self, player: Any):
        """Asynchronously handle time limit task."""
        from bridge import server
        puuid = str(player.uuid)
        start = self._start_times.get(puuid, time.time())
        limit = self.time_limit
        status = self._status
        while status.get(puuid) == "active":
            if time.time() - start >= limit:  # type: ignore[operator]
                self.fail(player)
                break

            try:
                await server.after(20)
            except Exception:
                break

class QuestTree:
    """Linear quest tree — complete each depth to unlock the next.

    Args:
        tree: List of quest layers. Each layer is a list of Quest objects.
              All quests in a layer must be completed to unlock the next layer.
    """
    __slots__ = ("_tree",)

    def __init__(self, tree: List[List[Quest] | Quest]):
        """Initialise a new QuestTree."""
        self._tree: List[List[Quest]] = []
        for entry in tree:
            if isinstance(entry, Quest):
                self._tree.append([entry])
            else:
                self._tree.append(list(entry))

    @property
    def depth(self) -> int:
        """The depth value."""
        return len(self._tree)

    def current_depth(self, player: Any) -> int:
        """Handle current depth."""
        for i, layer in enumerate(self._tree):
            if any(q.status(player) != "completed" for q in layer):
                return i

        return len(self._tree)

    def available(self, player: Any) -> List[Quest]:
        """Handle available."""
        d = self.current_depth(player)
        if d >= len(self._tree):
            return []

        return [q for q in self._tree[d]
                if q.status(player) not in ("completed", "active")]

    def active(self, player: Any) -> List[Quest]:
        """Handle active."""
        d = self.current_depth(player)
        if d >= len(self._tree):
            return []

        return [q for q in self._tree[d] if q.status(player) == "active"]

    def is_complete(self, player: Any) -> bool:
        """Check if complete."""
        return self.current_depth(player) >= len(self._tree)

    def all_quests(self) -> List[Quest]:
        """Return the all quests."""
        return [q for layer in self._tree for q in layer]
