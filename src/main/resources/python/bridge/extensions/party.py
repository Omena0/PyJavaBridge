"""Party extension — player groups for co-op content."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

import bridge


class Party:
    """Player group with leader, invites, and party chat.

    Args:
        name: Party name.
        leader: Player who created the party.
        max_size: Maximum members.
    """

    _all_parties: Dict[str, "Party"] = {}  # party name -> party
    _player_party: Dict[str, str] = {}  # puuid -> party name
    _listener_registered = False

    def __init__(self, name: str, leader: Any, max_size: int = 4):
        self.name = name
        self._leader_uuid: str = str(leader.uuid)
        self.max_size = max_size
        self._members: Dict[str, Any] = {self._leader_uuid: leader}
        self._on_join: List[Callable[..., Any]] = []
        self._on_leave: List[Callable[..., Any]] = []
        self._on_disband: List[Callable[..., Any]] = []
        Party._all_parties[name] = self
        Party._player_party[self._leader_uuid] = name
        Party._ensure_listener()

    @property
    def leader(self) -> Any:
        return self._members.get(self._leader_uuid)

    @property
    def members(self) -> List[Any]:
        return list(self._members.values())

    @property
    def member_uuids(self) -> List[str]:
        return list(self._members.keys())

    @property
    def size(self) -> int:
        return len(self._members)

    def is_member(self, player: Any) -> bool:
        return str(player.uuid) in self._members

    def is_leader(self, player: Any) -> bool:
        return str(player.uuid) == self._leader_uuid

    def join(self, player: Any) -> bool:
        puuid = str(player.uuid)
        if puuid in Party._player_party:
            return False
        if len(self._members) >= self.max_size:
            return False
        self._members[puuid] = player
        Party._player_party[puuid] = self.name
        self._fire(self._on_join, player)
        return True

    def leave(self, player: Any):
        puuid = str(player.uuid)
        if puuid not in self._members:
            return
        del self._members[puuid]
        Party._player_party.pop(puuid, None)
        self._fire(self._on_leave, player)
        if puuid == self._leader_uuid:
            if self._members:
                self._leader_uuid = next(iter(self._members))
            else:
                self.disband()

    def kick(self, player: Any):
        self.leave(player)

    def promote(self, player: Any):
        puuid = str(player.uuid)
        if puuid in self._members:
            self._leader_uuid = puuid

    def disband(self):
        for handler in self._on_disband:
            try:
                result = handler(self)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception:
                pass
        for puuid in list(self._members):
            Party._player_party.pop(puuid, None)
        self._members.clear()
        Party._all_parties.pop(self.name, None)

    def broadcast(self, message: str):
        for member in self._members.values():
            asyncio.ensure_future(member.send_message(f"§d[Party] §f{message}"))

    def on_join(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._on_join.append(handler)
        return handler

    def on_leave(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._on_leave.append(handler)
        return handler

    def on_disband(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._on_disband.append(handler)
        return handler

    def _fire(self, handlers: List[Callable[..., Any]], player: Any):
        for handler in handlers:
            try:
                result = handler(player, self)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception:
                pass

    @classmethod
    def of(cls, player: Any) -> Optional["Party"]:
        puuid = str(player.uuid)
        name = cls._player_party.get(puuid)
        if name:
            return cls._all_parties.get(name)
        return None

    @classmethod
    def _ensure_listener(cls):
        if cls._listener_registered:
            return
        cls._listener_registered = True

        async def _on_damage(event: Any):
            """Prevent party members from damaging each other."""
            attacker = event.fields.get("damager")
            victim = event.fields.get("entity")
            if not attacker or not victim:
                return
            a_uuid = attacker.fields.get("uuid") if hasattr(attacker, "fields") else None
            v_uuid = victim.fields.get("uuid") if hasattr(victim, "fields") else None
            if not a_uuid or not v_uuid:
                return
            a_party = cls._player_party.get(a_uuid)
            v_party = cls._player_party.get(v_uuid)
            if a_party and a_party == v_party:
                event.cancel()

        bridge._connection.on("entity_damage_by_entity", _on_damage)
        bridge._connection.subscribe("entity_damage_by_entity", False)
