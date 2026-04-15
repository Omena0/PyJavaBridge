"""Guild extension — persistent player guilds built on top of Party."""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional

from bridge.extensions.bank import Bank

def _safe_guild_storage_name(name: str) -> str:
    """Return a filesystem-safe guild storage name."""
    cleaned = re.sub(r"[\\/]+", "_", str(name)).replace("..", "_").strip()
    if not cleaned:
        raise ValueError("Guild name must contain at least one valid character")

    return cleaned

class Guild:
    """Persistent player guild with bank, chat, and member management.

    Args:
        name: Guild name.
        leader: Founding player.
        max_size: Maximum members.
        bank: Optional shared Guild bank.
    """

    _all_guilds: Dict[str, "Guild"] = {}
    _player_guild: Dict[str, str] = {}  # puuid -> guild name
    _data_path = os.path.join("plugins", "PyJavaBridge", "guilds")

    def __init__(self, name: str, leader: Any, max_size: int = 50,
            bank: Optional[Bank] = None) -> None:
        """Initialise a new Guild."""
        self.name = name
        self._storage_name = _safe_guild_storage_name(name)
        self._leader_uuid: str = str(leader.uuid)
        self.max_size = max_size
        self._members: Dict[str, str] = {self._leader_uuid: "leader"}  # puuid -> rank
        self._member_names: Dict[str, str] = {self._leader_uuid: str(leader.name)}
        self.bank = bank or Bank(name=f"guild_{self._storage_name}")
        self._on_join: List[Callable[..., Any]] = []
        self._on_leave: List[Callable[..., Any]] = []
        self._on_disband: List[Callable[..., Any]] = []
        Guild._all_guilds[name] = self
        Guild._player_guild[self._leader_uuid] = name
        self._save()

    @property
    def leader_uuid(self) -> str:
        """The leader uuid value."""
        return self._leader_uuid

    @property
    def members(self) -> Dict[str, str]:
        """Returns dict of {uuid: rank}."""
        return dict(self._members)

    @property
    def size(self) -> int:
        """The size value."""
        return len(self._members)

    def is_member(self, player: Any) -> bool:
        """Check if member."""
        return str(player.uuid) in self._members

    def rank(self, player: Any) -> Optional[str]:
        """Handle rank."""
        return self._members.get(str(player.uuid))

    def join(self, player: Any) -> bool:
        """Join the group."""
        puuid = str(player.uuid)
        if puuid in Guild._player_guild:
            return False

        if len(self._members) >= self.max_size:
            return False

        self._members[puuid] = "member"
        self._member_names[puuid] = str(player.name)
        Guild._player_guild[puuid] = self.name
        self._save()
        self._fire(self._on_join, player)
        return True

    def leave(self, player: Any) -> None:
        """Leave the group."""
        puuid = str(player.uuid)
        if puuid not in self._members:
            return

        del self._members[puuid]
        self._member_names.pop(puuid, None)
        Guild._player_guild.pop(puuid, None)
        self._save()
        self._fire(self._on_leave, player)
        if puuid == self._leader_uuid:
            if self._members:
                self._leader_uuid = next(iter(self._members))
                self._members[self._leader_uuid] = "leader"
                self._save()
            else:
                self.disband()

    def kick(self, player: Any) -> None:
        """Kick the player."""
        self.leave(player)

    def promote(self, player: Any, rank: str = "officer") -> None:
        """Promote a member."""
        puuid = str(player.uuid)
        if puuid in self._members:
            self._members[puuid] = rank
            self._save()

    def demote(self, player: Any) -> None:
        """Demote a member."""
        puuid = str(player.uuid)
        if puuid in self._members and puuid != self._leader_uuid:
            self._members[puuid] = "member"
            self._save()

    def transfer_leadership(self, new_leader: Any) -> None:
        """Handle transfer leadership."""
        new_uuid = str(new_leader.uuid)
        if new_uuid not in self._members:
            return

        self._members[self._leader_uuid] = "officer"
        self._leader_uuid = new_uuid
        self._members[new_uuid] = "leader"
        self._save()

    def disband(self) -> None:
        """Disband the group."""
        for handler in self._on_disband:
            try:
                result = handler(self)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception:
                pass

        for puuid in list(self._members):
            Guild._player_guild.pop(puuid, None)

        self._members.clear()
        Guild._all_guilds.pop(self.name, None)
        # Remove save file
        path = os.path.join(Guild._data_path, f"{self._storage_name}.json")
        if os.path.isfile(path):
            os.remove(path)

    def broadcast(self, message: str) -> None:
        """Send a message to all online guild members."""
        member_set = self._members

        async def _send() -> None:
            """Asynchronously handle send."""
            from bridge import server
            online = server.players
            msg = f"§6[Guild] §f{message}"
            for p in online:
                if str(p.uuid) in member_set:
                    await p.send_message(msg)

        asyncio.ensure_future(_send())

    def on_join(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Handle the join event."""
        self._on_join.append(handler)
        return handler

    def on_leave(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Handle the leave event."""
        self._on_leave.append(handler)
        return handler

    def on_disband(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Handle the disband event."""
        self._on_disband.append(handler)
        return handler

    def _fire(self, handlers: List[Callable[..., Any]], player: Any) -> None:
        """Fire callbacks."""
        for handler in handlers:
            try:
                result = handler(player, self)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception:
                pass

    def _save(self) -> None:
        """Save data to storage."""
        os.makedirs(Guild._data_path, exist_ok=True)
        data = {
            "name": self.name,
            "leader": self._leader_uuid,
            "max_size": self.max_size,
            "members": self._members,
            "member_names": self._member_names,
        }
        with open(os.path.join(Guild._data_path, f"{self._storage_name}.json"), "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, name: str) -> Optional["Guild"]:
        """Load from storage."""
        safe_name = _safe_guild_storage_name(name)
        path = os.path.join(cls._data_path, f"{safe_name}.json")
        if not os.path.isfile(path):
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

        if not isinstance(data, dict):
            return None

        # Create a shell guild without a real player object
        guild = object.__new__(cls)
        guild.name = str(data.get("name", name))
        guild._storage_name = safe_name
        guild._leader_uuid = str(data.get("leader", ""))
        guild.max_size = data.get("max_size", 50)
        guild._members = data.get("members", {})
        guild._member_names = data.get("member_names", {})
        guild.bank = Bank(name=f"guild_{safe_name}")
        guild._on_join = []
        guild._on_leave = []
        guild._on_disband = []
        cls._all_guilds[guild.name] = guild
        for puuid in guild._members:
            cls._player_guild[puuid] = guild.name

        return guild

    @classmethod
    def of(cls, player: Any) -> Optional["Guild"]:
        """Handle of."""
        name = cls._player_guild.get(str(player.uuid))
        if name:
            return cls._all_guilds.get(name)

        return None

    @classmethod
    def get(cls, name: str) -> Optional["Guild"]:
        """Get by key."""
        return cls._all_guilds.get(name)
