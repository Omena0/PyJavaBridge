"""Ability extension — player abilities with cooldowns and optional mana costs."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, Optional

import bridge

class Ability:
    """Base ability class with cooldown tracking and optional mana/bossbar.

    Designed to be subclassed. Override ``on_use`` and ``can_use`` as needed,
    or set them via the constructor/decorators.

    Args:
        name: Ability display name.
        description: Ability description.
        cooldown: Cooldown in seconds.
        use_cost: Optional mana cost (requires a ManaStore).
        cooldown_msg: Message sent when on cooldown.
        display_bossbar: Show cooldown on a BossBarDisplay.
    """

    def __init__(self, name: str, description: str = "",
            cooldown: float = 1.0, use_cost: Optional[float] = None,
            cooldown_msg: str = "§cAbility on cooldown! {remaining:.1f}s",
            display_bossbar: bool = False) -> None:
        """Initialise a new Ability."""
        self.name = name
        self.description = description
        self.cooldown = cooldown
        self.use_cost = use_cost
        self.cooldown_msg = cooldown_msg
        self.display_bossbar = display_bossbar
        self._last_used: Dict[str, float] = {}  # puuid -> timestamp
        self._on_use_handler: Optional[Callable[..., Any]] = None
        self._can_use_handler: Optional[Callable[..., bool]] = None
        self._mana_store: Any = None  # ManaStore reference
        self._bars: Dict[str, bridge.BossBarDisplay] = {}
        self._bar_tasks: Dict[str, asyncio.Task[Any]] = {}

    def set_mana_store(self, mana_store: Any) -> None:
        """Set the mana store."""
        self._mana_store = mana_store

    def on_use(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: register a use handler ``(ability, player)``."""
        self._on_use_handler = func
        return func

    def can_use(self, func: Callable[..., bool]) -> Callable[..., bool]:
        """Decorator: register a check ``(ability, player) -> bool``."""
        self._can_use_handler = func
        return func

    def last_used(self, player: Any) -> Optional[float]:
        """Handle last used."""
        return self._last_used.get(str(player.uuid))

    def remaining_cooldown(self, player: Any) -> float:
        """Handle remaining cooldown."""
        last = self._last_used.get(str(player.uuid))
        if last is None:
            return 0.0

        return max(0.0, self.cooldown - (time.time() - last))

    def use(self, player: Any) -> Any:
        """Attempt to use the ability. Returns True if used successfully."""
        puuid = str(player.uuid)
        now = time.time()
        last = self._last_used.get(puuid)
        if last is not None:
            remaining = self.cooldown - (now - last)
            if remaining > 0:
                msg = self.cooldown_msg.format(remaining=remaining, name=self.name)
                asyncio.ensure_future(player.send_message(msg))
                return False

        if self._can_use_handler is not None and not self._can_use_handler(self, player):
            return False

        # Check mana
        if self.use_cost is not None and self._mana_store is not None:
            if self._mana_store[player] < self.use_cost:
                asyncio.ensure_future(player.send_message("§cNot enough mana!"))
                return False

            self._mana_store.consume(player, self.use_cost)

        self._last_used[puuid] = time.time()

        if self._on_use_handler is not None:
            result = self._on_use_handler(self, player)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)

        if self.display_bossbar:
            self._show_cooldown_bar(player)

        return True

    def _show_cooldown_bar(self, player: Any) -> None:
        """Handle show cooldown bar."""
        puuid = str(player.uuid)
        bar = self._bars.get(puuid)
        if bar is None:
            bar = bridge.BossBarDisplay(self.name, color="RED", style="SOLID")
            self._bars[puuid] = bar

        task = self._bar_tasks.get(puuid)
        if task is not None and not task.done():
            task.cancel()

        bar.max = self.cooldown
        bar.value = self.cooldown
        bar.show(player)

        async def _update() -> None:
            """Asynchronously handle update."""
            from bridge import server
            try:
                while True:
                    remaining = self.remaining_cooldown(player)
                    if remaining <= 0:
                        bar.hide(player)
                        break

                    bar.value = remaining
                    try:
                        await server.after(2)
                    except Exception:
                        break
            finally:
                current = self._bar_tasks.get(puuid)
                if current is asyncio.current_task():
                    self._bar_tasks.pop(puuid, None)

        self._bar_tasks[puuid] = asyncio.ensure_future(_update())
