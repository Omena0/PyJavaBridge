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
                 display_bossbar: bool = False):
        self.default_mana = default_mana
        self.default_max_mana = default_max_mana
        self.default_regen_rate = default_regen_rate
        self.display_bossbar = display_bossbar
        self._mana: Dict[str, float] = {}
        self._max_mana: Dict[str, float] = {}
        self._regen_rate: Dict[str, float] = {}
        self._bars: Dict[str, bridge.BossBarDisplay] = {}
        self._regen_started = False

    def _puuid(self, player: Any) -> str:
        if isinstance(player, str):
            return player
        return str(player.uuid)

    def _ensure(self, puuid: str):
        if puuid not in self._mana:
            self._mana[puuid] = self.default_mana
            self._max_mana[puuid] = self.default_max_mana
            self._regen_rate[puuid] = self.default_regen_rate

    def __getitem__(self, player: Any) -> float:
        puuid = self._puuid(player)
        self._ensure(puuid)
        return self._mana[puuid]

    def __setitem__(self, player: Any, value: float):
        puuid = self._puuid(player)
        self._ensure(puuid)
        self._mana[puuid] = max(0.0, min(value, self._max_mana[puuid]))
        self._update_bar(player)

    def max_mana(self, player: Any) -> float:
        puuid = self._puuid(player)
        self._ensure(puuid)
        return self._max_mana[puuid]

    def set_max_mana(self, player: Any, value: float):
        puuid = self._puuid(player)
        self._ensure(puuid)
        self._max_mana[puuid] = max(0.0, value)
        self._mana[puuid] = min(self._mana[puuid], value)

    def regen_rate(self, player: Any) -> float:
        puuid = self._puuid(player)
        self._ensure(puuid)
        return self._regen_rate[puuid]

    def set_regen_rate(self, player: Any, value: float):
        puuid = self._puuid(player)
        self._ensure(puuid)
        self._regen_rate[puuid] = value

    def consume(self, player: Any, amount: float) -> bool:
        puuid = self._puuid(player)
        self._ensure(puuid)
        if self._mana[puuid] < amount:
            return False
        self._mana[puuid] -= amount
        self._update_bar(player)
        return True

    def restore(self, player: Any, amount: float):
        puuid = self._puuid(player)
        self._ensure(puuid)
        self._mana[puuid] = min(self._mana[puuid] + amount, self._max_mana[puuid])
        self._update_bar(player)

    def start_regen(self):
        """Start the global mana regen loop."""
        if self._regen_started:
            return
        self._regen_started = True
        asyncio.ensure_future(self._regen_loop())

    async def _regen_loop(self):
        from bridge.wrappers import server
        while True:
            for puuid in list(self._mana.keys()):
                rate = self._regen_rate.get(puuid, self.default_regen_rate)
                current = self._mana.get(puuid, 0.0)
                cap = self._max_mana.get(puuid, self.default_max_mana)
                if current < cap:
                    self._mana[puuid] = min(current + rate, cap)
            try:
                await server.after(20)  # tick every second
            except Exception:
                break

    def _update_bar(self, player: Any):
        if not self.display_bossbar:
            return
        puuid = self._puuid(player)
        self._ensure(puuid)
        if puuid not in self._bars:
            bar = bridge.BossBarDisplay("Mana", color="BLUE", style="SEGMENTED_10")
            bar.show(player)
            self._bars[puuid] = bar
        bar = self._bars[puuid]
        bar.max = self._max_mana[puuid]
        bar.value = self._mana[puuid]
        bar.text = f"§bMana: {int(self._mana[puuid])}/{int(self._max_mana[puuid])}"
