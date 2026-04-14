"""CombatSystem extension — tracks combat state and prevents combat-logging."""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

import bridge

class CombatSystem:
    """Tracks combat state per-player and prevents combat-logging.

    When a player attacks or is attacked, they enter combat for
    ``combat_timeout`` seconds. Logging out in combat triggers the
    on_combat_log handler.

    Args:
        combat_timeout: Seconds of combat after last attack.
        display_bossbar: Show combat timer to players.
    """

    def __init__(self, combat_timeout: float = 10.0,
            display_bossbar: bool = False) -> None:
        """Initialise a new CombatSystem."""
        self.combat_timeout = combat_timeout
        self.display_bossbar = display_bossbar
        self._last_attack: Dict[str, float] = {}  # puuid -> timestamp
        self._combat_log_handlers: List[Callable[..., Any]] = []
        self._bars: Dict[str, bridge.BossBarDisplay] = {}
        self._listener_registered = False

    def _register_listeners(self) -> None:
        """Register listeners."""
        if self._listener_registered:
            return

        self._listener_registered = True

        async def _on_damage(event: Any) -> None:
            """Handle the damage event."""
            attacker = event.fields.get("damager")
            victim = event.fields.get("entity")
            if attacker and hasattr(attacker, "fields"):
                a_uuid = attacker.fields.get("uuid")
                if a_uuid:
                    self._tag(a_uuid, attacker)

            if victim and hasattr(victim, "fields"):
                v_uuid = victim.fields.get("uuid")
                if v_uuid:
                    self._tag(v_uuid, victim)

        async def _on_quit(event: Any) -> None:
            """Handle the quit event."""
            player = event.fields.get("player")
            if player and hasattr(player, "fields"):
                puuid = player.fields.get("uuid")
                if puuid and self.in_combat_by_uuid(puuid):
                    for handler in self._combat_log_handlers:
                        try:
                            result = handler(player)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            pass

                    self._last_attack.pop(puuid, None)

        bridge._connection.on("entity_damage_by_entity", _on_damage)
        bridge._connection.subscribe("entity_damage_by_entity", False)
        bridge._connection.on("player_quit", _on_quit)
        bridge._connection.subscribe("player_quit", False)

    def start(self) -> None:
        """Register event listeners for combat tracking."""
        self._register_listeners()

    def _tag(self, puuid: str, player: Any) -> None:
        """Handle tag."""
        self._last_attack[puuid] = time.time()
        if self.display_bossbar:
            self._show_bar(puuid, player)

    def in_combat(self, player: Any) -> bool:
        """Handle in combat."""
        return self.in_combat_by_uuid(str(player.uuid))

    def in_combat_by_uuid(self, puuid: str) -> bool:
        """Handle in combat by uuid."""
        last = self._last_attack.get(puuid)
        return last is not None and (time.time() - last) < self.combat_timeout

    def remaining(self, player: Any) -> float:
        """Handle remaining."""
        last = self._last_attack.get(str(player.uuid))
        if last is None:
            return 0.0

        return max(0.0, self.combat_timeout - (time.time() - last))

    def on_combat_log(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: handler called when a player logs out in combat."""
        self._combat_log_handlers.append(handler)
        return handler

    def _show_bar(self, puuid: str, player: Any) -> None:
        """Handle show bar."""
        if puuid not in self._bars:
            bar = bridge.BossBarDisplay("In Combat", color="RED", style="SOLID")
            bar.show(player)
            self._bars[puuid] = bar

        bar = self._bars[puuid]
        bar.max = self.combat_timeout
        bar.value = self.combat_timeout

        async def _update() -> None:
            """Asynchronously handle update."""
            from bridge import server
            while self.in_combat_by_uuid(puuid):
                remaining = self.remaining(player)
                bar.value = remaining
                bar.text = f"§cIn Combat — {remaining:.1f}s"
                try:
                    await server.after(4)
                except Exception:
                    break

            bar.hide(player)

        asyncio.ensure_future(_update())
