"""ManaStore extension — per-player mana tracking with regen and BossBarDisplay."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import bridge

class ManaStore:
    """Global mana tracker with per-player values and auto-regen.

    Supports index notation: ``mana[player]`` to get current mana.

    Args:
        default_mana: Starting mana for new players.
        default_max_mana: Max mana for new players.
        default_regen_rate: Mana regenerated per second.
        display_bossbar: Show mana bar to players.
    """

    def __init__(self, default_mana: float = 100.0,
            default_max_mana: float = 100.0,
            default_regen_rate: float = 1.0,
            display_bossbar: bool = False) -> None:
        """Initialise a new ManaStore."""
        self.default_mana = default_mana
        self.default_max_mana = default_max_mana
        self.default_regen_rate = default_regen_rate
        self.display_bossbar = display_bossbar
        self._mana: Dict[str, float] = {}
        self._max_mana: Dict[str, float] = {}
        self._regen_rate: Dict[str, float] = {}
        self._bars: Dict[str, bridge.BossBarDisplay] = {}
        self._regen_started = False
        self._setup_hooks(display_bossbar)

    def _setup_hooks(self, display_bossbar: bool) -> None:
        """Register event hooks that run after the connection is ready."""
        store = self

        @bridge.event
        def server_boot(event: Any) -> None:
            """Handle server boot."""
            store.start_regen()
            if display_bossbar:
                # Show bar to all already-online players (e.g. after /bridge reload)
                for player in bridge.server.players:
                    store._ensure(player)
                    store._update_bar(player)

        if display_bossbar:
            @bridge.event
            def player_join(event: Any) -> None:
                """Handle player join."""
                player = event.fields.get("player")
                if player is not None:
                    store._ensure(player)
                    store._update_bar(player)

            @bridge.event
            def player_quit(event: Any) -> None:
                """Handle player quit."""
                player = event.fields.get("player")
                if player is not None:
                    puuid = store._puuid(player)
                    bar = store._bars.pop(puuid, None)
                    if bar is not None:
                        try:
                            bar.hide(player)
                        except Exception:
                            pass

    def _puuid(self, player: Any) -> str:
        """Handle puuid."""
        if isinstance(player, str):
            return player

        return str(player.uuid)

    def _ensure(self, player: Any, puuid: str | None = None) -> None:
        """Handle ensure."""
        if puuid is None:
            puuid = self._puuid(player)

        if puuid not in self._mana:
            self._mana[puuid] = self.default_mana
            self._max_mana[puuid] = self.default_max_mana
            self._regen_rate[puuid] = self.default_regen_rate
            if self.display_bossbar and not isinstance(player, str):
                self._update_bar(player)

    def __getitem__(self, player: Any) -> float:
        """Get an item by key or index."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        return self._mana[puuid]

    def __setitem__(self, player: Any, value: float) -> None:
        """Set an item by key or index."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        self._mana[puuid] = max(0.0, min(value, self._max_mana[puuid]))
        self._update_bar(player)

    def max_mana(self, player: Any) -> float:
        """Handle max mana."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        return self._max_mana[puuid]

    def set_max_mana(self, player: Any, value: float) -> None:
        """Set the max mana."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        self._max_mana[puuid] = max(0.0, value)
        self._mana[puuid] = min(self._mana[puuid], value)

    def regen_rate(self, player: Any) -> float:
        """Handle regen rate."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        return self._regen_rate[puuid]

    def set_regen_rate(self, player: Any, value: float) -> None:
        """Set the regen rate."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        self._regen_rate[puuid] = value

    def consume(self, player: Any, amount: float) -> bool:
        """Consume a resource."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        if self._mana[puuid] < amount:
            return False

        self._mana[puuid] -= amount
        self._update_bar(player)
        return True

    def restore(self, player: Any, amount: float) -> None:
        """Restore a resource."""
        puuid = self._puuid(player)
        self._ensure(player, puuid)
        self._mana[puuid] = min(self._mana[puuid] + amount, self._max_mana[puuid])
        self._update_bar(player)

    def start_regen(self) -> None:
        """Start the global mana regen loop."""
        if self._regen_started:
            return

        self._regen_started = True
        asyncio.ensure_future(self._regen_loop())

    async def _regen_loop(self) -> None:
        """Asynchronously handle regen loop."""
        from bridge import server
        while True:
            mana = self._mana
            max_mana = self._max_mana
            regen_rate = self._regen_rate
            bars = self._bars
            default_rate = self.default_regen_rate
            default_max = self.default_max_mana
            for puuid in list(mana):
                rate = regen_rate.get(puuid, default_rate)
                current = mana.get(puuid, 0.0)
                cap = max_mana.get(puuid, default_max)
                if current < cap:
                    new_val = min(current + rate, cap)
                    mana[puuid] = new_val
                    bar = bars.get(puuid)
                    if bar is not None:
                        try:
                            bar.max = cap
                            bar.value = new_val
                            bar.text = f"§bMana: {int(new_val)}/{int(cap)}"
                        except Exception:
                            bars.pop(puuid, None)

            try:
                await server.after(20)  # tick every second
            except Exception:
                break

    def _update_bar(self, player: Any) -> None:
        """Update the bar."""
        if not self.display_bossbar:
            return

        puuid = self._puuid(player)
        if puuid not in self._bars:
            bar = bridge.BossBarDisplay("Mana", color="BLUE", style="SEGMENTED_10")
            bar.show(player)
            self._bars[puuid] = bar

        bar = self._bars[puuid]
        mana = self._mana.get(puuid, self.default_mana)
        cap = self._max_mana.get(puuid, self.default_max_mana)
        bar.max = cap
        bar.value = mana
        bar.text = f"§bMana: {int(mana)}/{int(cap)}"
