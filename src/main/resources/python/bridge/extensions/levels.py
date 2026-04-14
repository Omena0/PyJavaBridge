"""LevelSystem extension — XP/level tracking with customisable curve."""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

import bridge

class LevelSystem:
    """Per-player XP and level tracking with a configurable level curve.

    XP required for level *n* is ``multiplier * n ^ exponent``.
    Supports index notation: ``levels[player]`` returns the current level.

    Args:
        multiplier: Base XP per level.
        exponent: Growth exponent.
        persist: Save data to disk.
        name: File name for persistence.
    """

    def __init__(self, multiplier: float = 100.0, exponent: float = 1.5,
            persist: bool = True, name: str = "levels") -> None:
        """Initialise a new LevelSystem."""
        self.multiplier = multiplier
        self.exponent = exponent
        self._persist = persist
        self._name = name
        self._xp: Dict[str, float] = {}
        self._on_level_up: List[Callable[..., Any]] = []
        self._path = os.path.join("plugins", "PyJavaBridge", "data", f"{name}.json")
        if persist:
            self._load()

    def _load(self) -> None:
        """Load data from storage."""
        if os.path.isfile(self._path):
            with open(self._path, "r") as f:
                self._xp = json.load(f)

    def _save(self) -> None:
        """Save data to storage."""
        if not self._persist:
            return

        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._xp, f)

    def _puuid(self, player: Any) -> str:
        """Handle puuid."""
        if isinstance(player, str):
            return player

        return str(player.uuid)

    def xp_for_level(self, level: int) -> float:
        """XP required to reach *level* from 0."""
        return self.multiplier * (level ** self.exponent)

    def level_from_xp(self, xp: float) -> int:
        """Handle level from xp."""
        level = 0
        while xp >= self.xp_for_level(level + 1):
            level += 1

        return level

    def __getitem__(self, player: Any) -> int:
        """Get current level for a player."""
        return self.level(player)

    def xp(self, player: Any) -> float:
        """Handle xp."""
        return self._xp.get(self._puuid(player), 0.0)

    def level(self, player: Any) -> int:
        """Handle level."""
        return self.level_from_xp(self.xp(player))

    def add_xp(self, player: Any, amount: float) -> None:
        """Add a xp."""
        puuid = self._puuid(player)
        old_xp = self._xp.get(puuid, 0.0)
        old_level = self.level_from_xp(old_xp)
        new_xp = old_xp + amount
        self._xp[puuid] = new_xp
        new_level = self.level_from_xp(new_xp)
        self._save()
        if new_level > old_level:
            for handler in self._on_level_up:
                try:
                    import asyncio
                    result = handler(player, new_level)
                    if asyncio.iscoroutine(result):
                        asyncio.ensure_future(result)
                except Exception:
                    pass

    def set_xp(self, player: Any, value: float) -> None:
        """Set the xp."""
        self._xp[self._puuid(player)] = max(0.0, value)
        self._save()

    def set_level(self, player: Any, level: int) -> None:
        """Set the level."""
        self._xp[self._puuid(player)] = self.xp_for_level(level)
        self._save()

    def xp_to_next(self, player: Any) -> float:
        """XP remaining until the next level."""
        current = self.xp(player)
        next_level = self.level_from_xp(current) + 1
        return max(0.0, self.xp_for_level(next_level) - current)

    def progress(self, player: Any) -> float:
        """Progress through the current level (0.0 – 1.0)."""
        current_xp = self.xp(player)
        lvl = self.level_from_xp(current_xp)
        floor = self.xp_for_level(lvl)
        ceiling = self.xp_for_level(lvl + 1)
        span = ceiling - floor
        if span <= 0:
            return 1.0

        return (current_xp - floor) / span

    def on_level_up(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(player, new_level)`` called on level up."""
        self._on_level_up.append(handler)
        return handler
