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
            display_bossbar: bool = False):
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
        self._bar: Optional[bridge.BossBarDisplay] = None

    def set_mana_store(self, mana_store: Any):
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

    def use(self, player: Any):
        """Attempt to use the ability. Returns True if used successfully."""
        puuid = str(player.uuid)
        remaining = self.remaining_cooldown(player)
        if remaining > 0:
            msg = self.cooldown_msg.format(remaining=remaining, name=self.name)
            asyncio.ensure_future(player.send_message(msg))
            return False

        if self._can_use_handler is not None:
            if not self._can_use_handler(self, player):
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

    def _show_cooldown_bar(self, player: Any):
        """Handle show cooldown bar."""
        if self._bar is None:
            self._bar = bridge.BossBarDisplay(self.name, color="RED", style="SOLID")

        self._bar.max = self.cooldown
        self._bar.value = self.cooldown
        self._bar.show(player)

        async def _update():
            """Asynchronously handle update."""
            from bridge import server
            while True:
                remaining = self.remaining_cooldown(player)
                if remaining <= 0:
                    self._bar.hide(player)  # type: ignore[union-attr]
                    break

                self._bar.value = remaining  # type: ignore[union-attr]
                try:
                    await server.after(2)
                except Exception:
                    break

        asyncio.ensure_future(_update())
