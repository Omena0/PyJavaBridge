from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, cast
from dataclasses import dataclass
from types import SimpleNamespace
from functools import wraps
import itertools
import threading
import inspect
import asyncio
import socket
import struct
import runpy
import uuid
import json
import time
import os
import math

try:
    import orjson as _orjson  # type: ignore[import-not-found]

    def _json_dumps(obj: Any) -> bytes:
        return _orjson.dumps(obj)

    def _json_loads(data: Any) -> Any:
        return _orjson.loads(data)

except Exception:

    def _json_dumps(obj: Any) -> bytes:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _json_loads(data: Any) -> Any:
        return json.loads(data)

__all__ = [
    "event",
    "task",
    "command",
    "raycast",
    "server",
    "chat",
    "reflect",
    "EntityGoneException",
    "Event",
    "Server",
    "Player",
    "Entity",
    "EntityType",
    "World",
    "Dimension",
    "Location",
    "Block",
    "Chunk",
    "Inventory",
    "Item",
    "ItemBuilder",
    "Material",
    "Effect",
    "EffectType",
    "AttributeType",
    "Attribute",
    "GameMode",
    "Sound",
    "Particle",
    "Biome",
    "Vector",
    "BarColor",
    "BarStyle",
    "Difficulty",
    "BossBar",
    "Scoreboard",
    "Team",
    "Objective",
    "Sidebar",
    "Hologram",
    "Menu",
    "MenuItem",
    "Cooldown",
    "ActionBarDisplay",
    "BossBarDisplay",
    "BlockDisplay",
    "ItemDisplay",
    "ImageDisplay",
    "Advancement",
    "AdvancementProgress",
    "Potion",
    "RaycastResult",
    "Config",
]


_EV = TypeVar("_EV", bound="EnumValue")

# Errors
class BridgeError(Exception):
    """Bridge-specific runtime error."""
    pass

class EntityGoneException(BridgeError):
    """Raised when an entity/player is no longer available."""
    pass

# Result classes
@dataclass
class RaycastResult:
    x: float
    y: float
    z: float
    entity: Optional["Entity"]
    block: Optional["Block"]
    start_x: float
    start_y: float
    start_z: float
    yaw: float
    pitch: float
    distance: float = 0.0
    hit_face: Optional[str] = None

# Code datatypes
class _EnumMeta(type):
    """Metaclass enabling class-level attribute access (e.g., Material.DIAMOND)."""
    def __getattr__(cls, name: str) -> "EnumValue":
        if name.startswith("_") or not name.isupper():
            raise AttributeError(name)
        return cls.from_name(name)  # type: ignore[attr-defined]

@dataclass
class EnumValue(metaclass=_EnumMeta):
    """Enum value proxy with class-level access (e.g., Material.DIAMOND)."""
    type: str
    name: str
    TYPE_NAME: str = ""

    def __str__(self) -> str:
        return self.name

    @classmethod
    def from_name(cls: type[_EV], name: str) -> _EV:
        return cls(cls.TYPE_NAME or cls.__name__, name)

class BridgeCall(Awaitable[Any]):
    """Awaitable wrapper for async bridge calls."""
    def __init__(self, future: "asyncio.Future[Any]"):
        self._future = future

    def __await__(self):
        return self._future.__await__()

    def __repr__(self) -> str:
        if self._future.done():
            return f"BridgeCall(result={self._future.result()!r})"
        return "BridgeCall(pending)"

class BridgeMethod:
    """Callable wrapper for late-bound method invocations on proxies."""
    def __init__(self, proxy: "ProxyBase", name: str):
        self._proxy = proxy
        self._name = name

    def __call__(self, *args: Any, **kwargs: Any) -> "BridgeCall":
        return self._proxy._call(self._name, *args, **kwargs)  # type: ignore[reportPrivateUsage]

class _SyncWait:
    def __init__(self):
        self.event = threading.Event()
        self.result: Any = None
        self.error: Optional[Exception] = None

# Core proxy class
class ProxyBase:
    """Base class for all proxy objects."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, ref_type: Optional[str] = None, ref_id: Optional[str] = None, **kwargs: Any):
        if kwargs:
            if fields is None:
                fields = dict(kwargs)
            else:
                fields.update(kwargs)
        self._handle = handle
        self._type_name = type_name
        self.fields = fields or {}
        self._target = target
        self._ref_type = ref_type
        self._ref_id = ref_id

    def __del__(self):
        handle = self.__dict__.get("_handle")
        if handle is not None and _connection is not None:
            try:
                _connection._queue_release(handle)
            except Exception:
                pass

    def _call(self, method: str, *args: Any, **kwargs: Any) -> "BridgeCall":
        if self._handle is None and self._target == "ref":
            if kwargs:
                return _connection.call(method="call", args=[self._ref_type, self._ref_id, method, list(args), kwargs], target="ref")
            return _connection.call(method="call", args=[self._ref_type, self._ref_id, method, list(args)], target="ref")
        return _connection.call(method=method, args=list(args), handle=self._handle, target=self._target, **kwargs)

    def _call_sync(self, method: str, *args: Any, **kwargs: Any) -> Any:
        if self._handle is None and self._target == "ref":
            if kwargs:
                return _connection.call_sync(method="call", args=[self._ref_type, self._ref_id, method, list(args), kwargs], target="ref")
            return _connection.call_sync(method="call", args=[self._ref_type, self._ref_id, method, list(args)], target="ref")
        return _connection.call_sync(method=method, args=list(args), handle=self._handle, target=self._target, **kwargs)

    def __getattr__(self, name: str):
        if name in self.fields:
            return self.fields[name]
        return BridgeMethod(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_") or name == "fields":
            super().__setattr__(name, value)
            return
        if self._handle is None and self._target == "ref":
            _connection.call(method="setAttr", args=[self._ref_type, self._ref_id, name, value], target="ref")
            return
        _connection.call(method="set_attr", handle=self._handle, field=name, value=value)

    def _field_or_call(self, field: str, method: str) -> Any:
        if field in self.fields:
            return self.fields[field]
        return self._call(method)

    def _field_or_call_sync(self, field: str, method: str) -> Any:
        if field in self.fields:
            return self.fields[field]
        return self._call_sync(method)

# Proxies and enums
class Event(ProxyBase):
    """Base event proxy."""
    def cancel(self):
        """Cancel the event if it is cancellable."""
        event_id = self.fields.get("__event_id__")
        if event_id is not None:
            _connection.send({"type": "event_cancel", "id": event_id})
            return _connection.completed_call(None)
        return self._call("setCancelled", True)

class Server(ProxyBase):
    """Server-level API."""
    def broadcast(self, message: str):
        """Broadcast a message to all players and console."""
        return self._call("broadcastMessage", message)

    def execute(self, command: str):
        """Execute a command as the server console."""
        return self._call("execute", command)

    @property
    def players(self):
        """Return the online players."""
        return self._call_sync("getOnlinePlayers")

    @property
    def worlds(self):
        """Return all loaded worlds."""
        return self._call_sync("getWorlds")

    def world(self, name: str):
        """Get a world by name."""
        return self._call("getWorld", name)

    @property
    def scoreboard_manager(self):
        """Get the scoreboard manager."""
        return self._call_sync("getScoreboardManager")

    def create_boss_bar(self, title: str, color: "BarColor", style: "BarStyle"):
        """Create a boss bar."""
        return self._call("createBossBar", title, color, style)

    @property
    def boss_bars(self):
        """Get all boss bars."""
        return self._call_sync("getBossBars")

    def get_advancement(self, key: str):
        """Get an advancement by namespaced key."""
        return self._call("getAdvancement", key)

    @property
    def plugin_manager(self):
        """Get the plugin manager."""
        return self._call_sync("getPluginManager")

    @property
    def scheduler(self):
        """Get the server scheduler."""
        return self._call_sync("getScheduler")

    async def wait(self, ticks: int = 1, after: Optional[Callable[[], Any]] = None):
        """Wait for ticks and optionally run a callback."""
        await _connection.wait(ticks)

        if after is not None:
            result = after()
            if hasattr(result, "__await__"):
                await result

        return None

    def frame(self):
        """
            Batch calls into a single send.
            Will not send before context manager exit.
        """
        return _connection.frame()

    def atomic(self):
        """
            Batch calls atomically (best-effort).
            If a request fails then all further ones are canceled.
            There are no rollbacks.
        """
        return _connection.atomic()

    async def flush(self):
        """Send all pending batched requests immediately."""
        return await _connection.flush()

    @property
    def tps(self):
        return _connection.call_sync(method="tps", target="metrics")

    @property
    def mspt(self):
        return _connection.call_sync(method="mspt", target="metrics")

    @property
    def last_tick_time(self):
        return _connection.call_sync(method="lastTickTime", target="metrics")

    @property
    def queue_len(self):
        return _connection.call_sync(method="queueLen", target="metrics")

    @property
    def name(self):
        return self.fields.get("name") or self._call_sync("getName")

    @property
    def version(self):
        return self.fields.get("version") or self._call_sync("getVersion")

    @property
    def motd(self):
        return self._call_sync("getMotd")

    @property
    def max_players(self):
        return self._call_sync("getMaxPlayers")

class Entity(ProxyBase):
    """Base entity proxy."""
    @classmethod
    def spawn(cls, entity_type: EntityType | str, location: Location, **kwargs: Any):
        """Spawn an entity at a location."""
        world = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            raise BridgeError("Location must have a world to spawn an entity")
        return world.spawn_entity(location, entity_type, **kwargs)

    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, uuid: Optional[str] = None, ref_type: Optional[str] = None, ref_id: Optional[str] = None):
        if handle is None and uuid is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="entity", ref_id=str(uuid))
            self.fields.setdefault("uuid", str(uuid))
            return

        if handle is None and ref_type is not None and ref_id is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type=ref_type, ref_id=ref_id)
            return

        super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    def teleport(self, location: "Location"):
        """Teleport the entity."""
        return self._call("teleport", location)

    def remove(self):
        """Remove the entity."""
        return self._call("remove")

    def set_velocity(self, vector: "Vector"):
        """Set velocity vector."""
        return self._call("setVelocity", vector)

    @property
    def velocity(self):
        """Get velocity vector."""
        return self._call_sync("getVelocity")

    @property
    def is_dead(self):
        """Check if entity is dead."""
        return self._call_sync("isDead")

    @property
    def is_alive(self):
        """Check if entity is alive."""
        return not self.is_dead

    @property
    def is_valid(self):
        """Check if entity is valid."""
        return self._call_sync("isValid")

    @property
    def fire_ticks(self):
        """Get fire ticks."""
        return self._call_sync("getFireTicks")

    def set_fire_ticks(self, ticks: int):
        """Set fire ticks."""
        return self._call("setFireTicks", ticks)

    def add_passenger(self, entity: "Entity"):
        """Add a passenger."""
        return self._call("addPassenger", entity)

    def remove_passenger(self, entity: "Entity"):
        """Remove a passenger."""
        return self._call("removePassenger", entity)

    @property
    def passengers(self):
        """Get passengers."""
        return self._call_sync("getPassengers")

    @property
    def custom_name(self):
        """Get custom name."""
        return self._call_sync("getCustomName")

    def set_custom_name(self, name: str):
        """Set custom name."""
        return self._call("setCustomName", name)

    def set_custom_name_visible(self, value: bool):
        """Show/hide custom name."""
        return self._call("setCustomNameVisible", value)

    @property
    def uuid(self):
        return self.fields.get("uuid")

    @property
    def type(self):
        return self.fields.get("type")

    @property
    def location(self):
        return self._call_sync("getLocation")

    @property
    def world(self):
        return self._call_sync("getWorld")

class Player(Entity):
    """Player API (inherits Entity)."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, uuid: Optional[str] = None, name: Optional[str] = None):
        if isinstance(handle, str) and uuid is None and name is None and type_name is None and fields is None and target is None:
            try:
                import uuid as uuid_mod
                uuid_obj = uuid_mod.UUID(handle)
                uuid = str(uuid_obj)
            except Exception:
                name = handle
            handle = None

        if handle is None and uuid is not None and name is None:
            try:
                import uuid as uuid_mod
                uuid_obj = uuid if isinstance(uuid, uuid_mod.UUID) else uuid_mod.UUID(str(uuid))
                super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", uuid=str(uuid_obj))
                return
            except Exception:
                name = str(uuid)

        if handle is None and name is not None:
            if fields is None:
                cached = _player_uuid_cache.get(str(name))
                if cached is not None:
                    fields = {"uuid": cached, "name": str(name)}
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="player_name", ref_id=str(name))
            return

        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    def send_message(self, message: str):
        """Send a chat message to the player."""
        return self._call("sendMessage", message)

    def chat(self, message: str):
        """Make the player chat a message."""
        return self._call("chat", message)

    def kick(self, reason: str = ""):
        """Kick the player with an optional reason."""
        return self._call("kick", reason)

    def teleport(self, location: "Location"):
        """Teleport the player to a location."""
        return self._call("teleport", location)

    def give_exp(self, amount: int):
        """Give raw experience points."""
        return self._call("giveExp", amount)

    def add_effect(self, effect: "Effect"):
        """Add an active potion effect."""
        return self._call("addPotionEffect", effect)

    def remove_effect(self, effect_type: "EffectType"):
        """Remove a potion effect by type."""
        return self._call("removePotionEffect", effect_type)

    @property
    def effects(self):
        """Get active potion effects."""
        return self._call_sync("getActivePotionEffects")

    def set_game_mode(self, mode: "GameMode"):
        """Set the player's game mode."""
        return self._call("setGameMode", mode)

    @property
    def scoreboard(self):
        """Get the player's scoreboard."""
        return self._call_sync("getScoreboard")

    def set_scoreboard(self, scoreboard: "Scoreboard"):
        """Set the player's scoreboard."""
        return self._call("setScoreboard", scoreboard)

    def has_permission(self, permission: str):
        """Check a permission."""
        return self._call("hasPermission", permission)

    @property
    def is_op(self):
        """Check if the player is op."""
        return self._call_sync("isOp")

    def set_op(self, value: bool):
        """Set op status."""
        return self._call("setOp", value)

    def add_permission(self, permission: str, value: bool = True):
        """Add or set a permission (LuckPerms-aware)."""
        return _connection.call(method="addPermission", args=[self, permission, value], target="permissions")

    def remove_permission(self, permission: str):
        """Remove a permission (LuckPerms-aware)."""
        return _connection.call(method="removePermission", args=[self, permission], target="permissions")

    @property
    def permission_groups(self):
        """Get permission groups (LuckPerms-aware)."""
        return _connection.call_sync(method="groups", args=[self], target="permissions")

    @property
    def primary_group(self):
        """Get primary permission group (LuckPerms-aware)."""
        return _connection.call_sync(method="primaryGroup", args=[self], target="permissions")

    def has_group(self, group: str):
        """Check permission group membership (LuckPerms-only)."""
        return _connection.call(method="hasGroup", args=[self, group], target="permissions")

    def add_group(self, group: str):
        """Add a permission group (LuckPerms-only)."""
        return _connection.call(method="addGroup", args=[self, group], target="permissions")

    def remove_group(self, group: str):
        """Remove a permission group (LuckPerms-only)."""
        return _connection.call(method="removeGroup", args=[self, group], target="permissions")

    def play_sound(self, sound: "Sound", volume: float = 1.0, pitch: float = 1.0):
        """Play a sound to the player."""
        if isinstance(sound, str):
            sound = Sound.from_name(sound.upper())
        return self._call("playSound", sound, volume, pitch)

    def send_action_bar(self, message: str):
        """Send an action bar message."""
        return self._call("sendActionBar", message)

    def send_title(self, title: str, subtitle: str = "", fade_in: int = 10, stay: int = 70, fade_out: int = 20):
        """Send a title/subtitle to the player."""
        return self._call("sendTitle", title, subtitle, fade_in, stay, fade_out)

    @property
    def tab_list_header(self):
        """Get tab list header."""
        return self._call_sync("getTabListHeader")

    @property
    def tab_list_footer(self):
        """Get tab list footer."""
        return self._call_sync("getTabListFooter")

    def set_tab_list_header(self, header: str):
        """Set tab list header."""
        return self._call("setTabListHeader", header)

    def set_tab_list_footer(self, footer: str):
        """Set tab list footer."""
        return self._call("setTabListFooter", footer)

    def set_tab_list_header_footer(self, header: str = "", footer: str = ""):
        """Set tab list header and footer."""
        return self._call("setTabListHeaderFooter", header, footer)

    @property
    def tab_list_name(self):
        """Get tab list name."""
        return self._call_sync("getPlayerListName")

    def set_tab_list_name(self, name: str):
        """Set tab list name."""
        return self._call("setPlayerListName", name)

    def set_health(self, health: float):
        """Set player health."""
        return self._call("setHealth", health)

    def set_food_level(self, level: int):
        """Set hunger level."""
        return self._call("setFoodLevel", level)

    @property
    def level(self):
        """Get player level."""
        return self._call_sync("getLevel")

    def set_level(self, level: int):
        """Set player level."""
        return self._call("setLevel", level)

    @property
    def exp(self):
        """Get experience progress (0..1)."""
        return self._call_sync("getExp")

    def set_exp(self, exp: float):
        """Set experience progress (0..1)."""
        return self._call("setExp", exp)

    @property
    def is_flying(self):
        """Check if the player is flying."""
        return self._call_sync("isFlying")

    def set_flying(self, value: bool):
        """Set flying state."""
        return self._call("setFlying", value)

    @property
    def is_sneaking(self):
        """Check if sneaking."""
        return self._call_sync("isSneaking")

    def set_sneaking(self, value: bool):
        """Set sneaking state."""
        return self._call("setSneaking", value)

    @property
    def is_sprinting(self):
        """Check if sprinting."""
        return self._call_sync("isSprinting")

    def set_sprinting(self, value: bool):
        """Set sprinting state."""
        return self._call("setSprinting", value)

    def set_walk_speed(self, speed: float):
        """Set walking speed."""
        return self._call("setWalkSpeed", speed)

    def set_fly_speed(self, speed: float):
        """Set flying speed."""
        return self._call("setFlySpeed", speed)

    @property
    def name(self):
        return self.fields.get("name")

    @property
    def uuid(self):
        if "uuid" in self.fields:
            return str(self.fields["uuid"])

        ref_type = getattr(self, "_ref_type", None)
        ref_id = getattr(self, "_ref_id", None)

        if ref_type == "player" and ref_id:
            try:
                return str(uuid.UUID(str(ref_id)))
            except Exception:
                pass

        if ref_type == "player_name" and ref_id:
            cached = _player_uuid_cache.get(str(ref_id))
            if cached is not None:
                return cached

        try:
            if self._handle is None and self._target == "ref":
                result = _connection.call_sync(
                    method="call",
                    args=[self._ref_type, self._ref_id, "getUniqueId", []],
                    target="ref",
                )

            else:
                result = _connection.call_sync(method="getUniqueId", handle=self._handle, target=self._target)

            if result is not None:
                result_text = str(result)
                self.fields["uuid"] = result_text
                if ref_type == "player_name" and ref_id:
                    _player_uuid_cache[str(ref_id)] = result_text
                return result_text
            return None

        except Exception as exc:
            import traceback
            traceback.print_exc()
            raise BridgeError(f"Failed to synchronously resolve uuid: {exc}") from exc

    @property
    def location(self):
        return self._call_sync("getLocation")

    @property
    def world(self):
        return self._call_sync("getWorld")

    @property
    def game_mode(self):
        return self._call_sync("getGameMode")

    @property
    def health(self):
        return self._call_sync("getHealth")

    @property
    def food_level(self):
        return self._call_sync("getFoodLevel")

    @property
    def inventory(self):
        if self._handle is None and self._target == "ref":
            ref_id = self._ref_id or self.fields.get("uuid") or self.fields.get("name")
            if ref_id:
                return Inventory(handle=None, target="ref", ref_type="player_inventory", ref_id=str(ref_id))

        return self._call_sync("getInventory")

class EntityType(EnumValue):
    TYPE_NAME = "org.bukkit.entity.EntityType"

class World(ProxyBase):
    """World API."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, name: Optional[str] = None):
        if handle is None and name is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="world", ref_id=str(name))
            self.fields.setdefault("name", str(name))
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    def block_at(self, x: int, y: int, z: int):
        """Get a block at coordinates."""
        return self._call("getBlockAt", x, y, z)

    def spawn_entity(self, location: "Location", entity_type: "EntityType | str", **kwargs: Any):
        """Spawn an entity by type.

        Optional kwargs: velocity (Vector or [x,y,z]), facing (Vector or [x,y,z]),
        yaw, pitch, nbt (SNBT string).
        """
        if isinstance(entity_type, str):
            entity_type = EntityType.from_name(entity_type)
        try:
            return self._call("spawnEntity", location, entity_type, **kwargs)
        except BridgeError as exc:
            if "Method not found: spawnEntity" in str(exc):
                return self._call("spawn", location, entity_type, **kwargs)
            raise

    def chunk_at(self, x: int, z: int):
        """Get a chunk by coordinates."""
        return self._call("getChunkAt", x, z)

    def spawn(self, location: "Location", entity_cls: type, **kwargs: Any):
        """Spawn an entity by class."""
        if isinstance(entity_cls, (EntityType, str)):
            return self.spawn_entity(location, entity_cls, **kwargs)
        return self._call("spawn", location, entity_cls, **kwargs)

    def set_time(self, time: int):
        """Set world time."""
        return self._call("setTime", time)

    @property
    def time(self):
        """Get world time."""
        return self._call_sync("getTime")

    def set_difficulty(self, difficulty: "Difficulty"):
        """Set world difficulty."""
        return self._call("setDifficulty", difficulty)

    @property
    def difficulty(self):
        """Get world difficulty."""
        return self._call_sync("getDifficulty")

    def spawn_particle(self, particle: "Particle", location: "Location", count: int = 1, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        """Spawn particles in the world."""
        return self._call("spawnParticle", particle, location, count, offset_x, offset_y, offset_z, extra)

    def play_sound(self, location: "Location", sound: "Sound", volume: float = 1.0, pitch: float = 1.0):
        """Play a sound at a location."""
        return self._call("playSound", location, sound, volume, pitch)

    def strike_lightning(self, location: "Location"):
        """Strike lightning at a location."""
        return self._call("strikeLightning", location)

    def strike_lightning_effect(self, location: "Location"):
        """Strike lightning effect at a location."""
        return self._call("strikeLightningEffect", location)

    @property
    def spawn_location(self):
        """Get world spawn location."""
        return self._call_sync("getSpawnLocation")

    def set_spawn_location(self, location: "Location"):
        """Set world spawn location."""
        return self._call("setSpawnLocation", location)

    @property
    def full_time(self):
        """Get full world time."""
        return self._call_sync("getFullTime")

    def set_full_time(self, time: int):
        """Set full world time."""
        return self._call("setFullTime", time)

    @property
    def has_storm(self):
        """Check if storming."""
        return self._call_sync("hasStorm")

    def set_storm(self, value: bool):
        """Set storming."""
        return self._call("setStorm", value)

    @property
    def is_thundering(self):
        """Check if thundering."""
        return self._call_sync("isThundering")

    def set_thundering(self, value: bool):
        """Set thundering."""
        return self._call("setThundering", value)

    @property
    def weather_duration(self):
        """Get weather duration."""
        return self._call_sync("getWeatherDuration")

    def set_weather_duration(self, ticks: int):
        """Set weather duration."""
        return self._call("setWeatherDuration", ticks)

    @property
    def thunder_duration(self):
        """Get thunder duration."""
        return self._call_sync("getThunderDuration")

    def set_thunder_duration(self, ticks: int):
        """Set thunder duration."""
        return self._call("setThunderDuration", ticks)

    @property
    def players(self):
        """Get players in this world."""
        return self._call_sync("getPlayers")

    @property
    def entities(self):
        return self._call_sync('getEntities')

    @property
    def name(self):
        return self.fields.get("name")

    @property
    def uuid(self):
        return self.fields.get("uuid")

    @property
    def environment(self):
        return self.fields.get("environment")

    # --- Region utilities (single Java call each, no round-trip per block) ---

    def set_block(self, x: int, y: int, z: int, material: Any, apply_physics: bool = False):
        """Set a single block at coordinates."""
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="setBlock", args=[self, int(x), int(y), int(z), material, apply_physics])

    def fill(self, pos1: Any, pos2: Any, material: Any, apply_physics: bool = False):
        """Fill a rectangular region between two positions with a material.

        pos1/pos2 can be Location, Vector, or (x, y, z) tuples.
        Returns an awaitable that resolves to the number of blocks placed.
        """
        x1, y1, z1 = _extract_xyz(pos1)
        x2, y2, z2 = _extract_xyz(pos2)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="fill", args=[self, int(x1), int(y1), int(z1), int(x2), int(y2), int(z2), material, apply_physics])

    def replace(self, pos1: Any, pos2: Any, from_material: Any, to_material: Any):
        """Replace all blocks of one material with another in a region.

        Returns an awaitable that resolves to the number of blocks replaced.
        """
        x1, y1, z1 = _extract_xyz(pos1)
        x2, y2, z2 = _extract_xyz(pos2)
        if isinstance(from_material, str):
            from_material = Material.from_name(from_material.upper())
        if isinstance(to_material, str):
            to_material = Material.from_name(to_material.upper())
        return _connection.call(target="region", method="replace", args=[self, int(x1), int(y1), int(z1), int(x2), int(y2), int(z2), from_material, to_material])

    def fill_sphere(self, center: Any, radius: float, material: Any, hollow: bool = False):
        """Fill a sphere of blocks centered at a position.

        Returns an awaitable that resolves to the number of blocks placed.
        """
        cx, cy, cz = _extract_xyz(center)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="sphere", args=[self, float(cx), float(cy), float(cz), float(radius), material, hollow])

    def fill_cylinder(self, center: Any, radius: float, height: int, material: Any, hollow: bool = False):
        """Fill a cylinder of blocks from center upward.

        Returns an awaitable that resolves to the number of blocks placed.
        """
        cx, cy, cz = _extract_xyz(center)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="cylinder", args=[self, float(cx), float(cy), float(cz), float(radius), int(height), material, hollow])

    def fill_line(self, start: Any, end: Any, material: Any):
        """Draw a line of blocks between two positions.

        Returns an awaitable that resolves to the number of blocks placed.
        """
        x1, y1, z1 = _extract_xyz(start)
        x2, y2, z2 = _extract_xyz(end)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="line", args=[self, float(x1), float(y1), float(z1), float(x2), float(y2), float(z2), material])

    # --- Particle shape utilities (single Java call each) ---

    def particle_line(self, start: Any, end: Any, particle: Any, density: float = 4.0, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        """Spawn particles along a line between two positions.

        density: particles per block distance.
        Returns an awaitable that resolves to the particle count.
        """
        x1, y1, z1 = _extract_xyz(start)
        x2, y2, z2 = _extract_xyz(end)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="line", args=[self, particle, float(x1), float(y1), float(z1), float(x2), float(y2), float(z2), float(density), float(offset_x), float(offset_y), float(offset_z), float(extra)])

    def particle_sphere(self, center: Any, radius: float, particle: Any, density: float = 4.0, hollow: bool = True, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        """Spawn particles in a sphere shape.

        density: particles per block^2 for hollow, per block^3 for filled.
        Returns an awaitable that resolves to the particle count.
        """
        cx, cy, cz = _extract_xyz(center)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="sphere", args=[self, particle, float(cx), float(cy), float(cz), float(radius), float(density), hollow, float(offset_x), float(offset_y), float(offset_z), float(extra)])

    def particle_cube(self, pos1: Any, pos2: Any, particle: Any, density: float = 4.0, hollow: bool = True, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        """Spawn particles in a cuboid shape.

        density: particles per block distance.
        Returns an awaitable that resolves to the particle count.
        """
        x1, y1, z1 = _extract_xyz(pos1)
        x2, y2, z2 = _extract_xyz(pos2)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="cube", args=[self, particle, float(x1), float(y1), float(z1), float(x2), float(y2), float(z2), float(density), hollow, float(offset_x), float(offset_y), float(offset_z), float(extra)])

    def particle_ring(self, center: Any, radius: float, particle: Any, density: float = 4.0, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        """Spawn particles in a horizontal ring.

        density: particles per block circumference.
        Returns an awaitable that resolves to the particle count.
        """
        cx, cy, cz = _extract_xyz(center)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="ring", args=[self, particle, float(cx), float(cy), float(cz), float(radius), float(density), float(offset_x), float(offset_y), float(offset_z), float(extra)])

    # --- Entity spawn helpers ---

    def spawn_at_player(self, player: "Player", entity_type: Any, offset: Any = None, **kwargs: Any):
        """Spawn an entity at a player's location with an optional offset.

        offset can be a Vector, Location, or (x,y,z) tuple added to the player's position.
        """
        loc = player.location
        if offset is not None:
            ox, oy, oz = _extract_xyz(offset)
            loc = Location(loc.x + ox, loc.y + oy, loc.z + oz, loc.world, loc.yaw, loc.pitch)
        return self.spawn_entity(loc, entity_type, **kwargs)

    def spawn_projectile(self, shooter: "Entity", entity_type: Any, velocity: Any = None, **kwargs: Any):
        """Spawn a projectile entity at the shooter's eye location with optional velocity."""
        loc = shooter.location
        if isinstance(entity_type, str):
            entity_type = EntityType.from_name(entity_type)
        if velocity is not None:
            if isinstance(velocity, (list, tuple)):
                vel = cast(List[Any], velocity)
                if len(vel) >= 3:
                    kwargs["velocity"] = [float(vel[0]), float(vel[1]), float(vel[2])]
            elif isinstance(velocity, (Vector, SimpleNamespace)):
                kwargs["velocity"] = [float(velocity.x), float(velocity.y), float(velocity.z)]
            elif hasattr(velocity, "x") and hasattr(velocity, "y") and hasattr(velocity, "z"):
                v: Any = velocity
                kwargs["velocity"] = [float(v.x), float(v.y), float(v.z)]
        return self.spawn_entity(loc, entity_type, **kwargs)

    def spawn_with_nbt(self, location: "Location", entity_type: Any, nbt: str, **kwargs: Any):
        """Spawn an entity with an SNBT string applied after spawning."""
        kwargs["nbt"] = nbt
        return self.spawn_entity(location, entity_type, **kwargs)

class Dimension(ProxyBase):
    def __init__(self, name: Optional[str] = None, **kwargs: Any):
        if name is not None and "fields" not in kwargs and "handle" not in kwargs:
            fields = {"name": name}
            super().__init__(fields=fields)
        else:
            super().__init__(**kwargs)
    @property
    def name(self) -> Optional[str]:
        return self.fields.get("name")

class Location(ProxyBase):
    """Location in a world with yaw and pitch."""
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, world: Optional[World | str] = None, yaw: float = 0.0, pitch: float = 0.0, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None and target is None:
            if isinstance(world, str):
                world = World(name=world)
            fields = {"x": float(x), "y": float(y), "z": float(z), "yaw": float(yaw), "pitch": float(pitch)}
            if world is not None:
                fields["world"] = world
            super().__init__(handle=None, type_name=type_name, fields=fields, target=target)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)
    @property
    def x(self) -> float:
        return self.fields.get("x", 0.0)

    @property
    def y(self) -> float:
        return self.fields.get("y", 0.0)

    @property
    def z(self) -> float:
        return self.fields.get("z", 0.0)

    @property
    def yaw(self) -> float:
        return self.fields.get("yaw", 0.0)

    @property
    def pitch(self) -> float:
        return self.fields.get("pitch", 0.0)

    @property
    def world(self):
        return self.fields.get("world")

    def add(self, x: float, y: float, z: float) -> "Location":
        """Add coordinates to this location."""
        return Location(self.x + x, self.y + y, self.z + z, self.world, self.yaw, self.pitch)

    def clone(self) -> "Location":
        """Clone this location."""
        return Location(self.x, self.y, self.z, self.world, self.yaw, self.pitch)

    def distance(self, other: "Location") -> float:
        """Distance to another location."""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def distance_squared(self, other: "Location") -> float:
        """Squared distance to another location."""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return dx * dx + dy * dy + dz * dz

class Block(ProxyBase):
    """Block in the world."""
    @classmethod
    def create(cls, location: Location, material: Material | str):
        """Create/set a block at the given location."""
        world = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            raise BridgeError("Location must have a world to create a block")
        block = Block(world=world, x=int(location.x), y=int(location.y), z=int(location.z), material=material)
        block.set_type(material)
        return block

    def __init__(self, world: Optional[World | str] = None, x: Optional[int] = None, y: Optional[int] = None, z: Optional[int] = None, material: Optional[Material | str] = None, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None and world is not None and x is not None and y is not None and z is not None:
            if isinstance(world, str):
                world = World(name=world)
                world_name = world.fields.get("name")
            else:
                world_name = world.fields.get("name")
            fields = {"x": int(x), "y": int(y), "z": int(z), "world": world}
            if material is not None:
                if isinstance(material, str):
                    material = Material.from_name(material.upper())
                fields["type"] = material
            ref_id = f"{world_name}:{int(x)}:{int(y)}:{int(z)}" if world_name is not None else None
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="block", ref_id=ref_id)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)
    def break_naturally(self):
        """Break the block naturally."""
        return self._call("breakNaturally")

    def set_type(self, material: "Material | str"):
        """Set the block type."""
        return self._call("setType", material)

    @property
    def is_solid(self):
        """Check if block is solid."""
        return self._call_sync("isSolid")

    @property
    def data(self):
        """Get block data."""
        return self._call_sync("getBlockData")

    def set_data(self, data: Any):
        """Set block data."""
        return self._call("setBlockData", data)

    @property
    def light_level(self):
        """Get light level."""
        return self._call_sync("getLightLevel")

    @property
    def biome(self):
        """Get biome."""
        return self._call_sync("getBiome")

    def set_biome(self, biome: "Biome"):
        """Set biome."""
        return self._call("setBiome", biome)

    @property
    def inventory(self):
        """Get inventory if block has one."""
        return self._call_sync("getInventory")

    @property
    def x(self) -> int:
        return self.fields.get("x", 0)

    @property
    def y(self) -> int:
        return self.fields.get("y", 0)

    @property
    def z(self) -> int:
        return self.fields.get("z", 0)

    @property
    def location(self):
        return Location(self.x, self.y, self.z, self.world)

    @property
    def type(self):
        return self._call_sync("getType")

    @property
    def world(self):
        return self.fields.get("world")

class Chunk(ProxyBase):
    """Chunk of a world (loadable/unloadable)."""
    def __init__(self, world: Optional[World | str] = None, x: Optional[int] = None, z: Optional[int] = None, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None and world is not None and x is not None and z is not None:
            if isinstance(world, str):
                world = World(name=world)
                world_name = world.fields.get("name")
            else:
                world_name = world.fields.get("name")
            fields = {"x": int(x), "z": int(z), "world": world}
            ref_id = f"{world_name}:{int(x)}:{int(z)}" if world_name is not None else None
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="chunk", ref_id=ref_id)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)
    @property
    def x(self) -> int:
        return self.fields.get("x", 0)

    @property
    def z(self) -> int:
        return self.fields.get("z", 0)

    @property
    def world(self):
        return self.fields.get("world")

    def load(self):
        """Load the chunk."""
        return self._call("load")

    def unload(self):
        """Unload the chunk."""
        return self._call("unload")

    @property
    def is_loaded(self):
        """Check if the chunk is loaded."""
        return self._call_sync("isLoaded")

class Inventory(ProxyBase):
    """
        Inventory. Can belong to an entity or block entity, or exist as a standalone open inventory screen.
    """
    def __init__(self, size: int = 9, title: str = "", contents: Optional[List["Item"]] = None, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, ref_type: Optional[str] = None, ref_id: Optional[str] = None):
        if handle is None and fields is None and ref_type is None and ref_id is None:
            fields = {"size": int(size), "title": str(title)}
            if contents is not None:
                fields["contents"] = list(contents)
            super().__init__(handle=None, type_name=type_name, fields=fields, target=target)
        elif handle is None and ref_type is not None and ref_id is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type=ref_type, ref_id=ref_id)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    def open(self, player: "Player"):
        """Open this inventory for a player."""
        return player._call("openInventory", self)

    def add_item(self, item: "Item"):
        """Add an item to the inventory."""
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            size = int(self.fields.get("size") or len(contents) or 0)
            if size <= 0:
                size = len(contents) or 9
            while len(contents) < size:
                contents.append(None)
            for idx, slot in enumerate(contents):
                if slot is None:
                    contents[idx] = item
                    self.fields["contents"] = contents
                    return None
            contents.append(item)
            self.fields["contents"] = contents
            return None
        return self._call("addItem", item)

    def remove_item(self, item: "Item"):
        """Remove an item from the inventory."""
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            for idx, slot in enumerate(contents):
                if slot == item:
                    contents[idx] = None
                    break
            self.fields["contents"] = contents
            return None
        return self._call("removeItem", item)

    def clear(self):
        """Clear inventory contents."""
        if self._handle is None:
            self.fields["contents"] = []
            return None
        return self._call("clear")

    def close(self, player: Optional["Player"] = None):
        """Close this inventory for a player."""
        if player is not None:
            return player._call("closeInventory")
        return self._call("close")

    @property
    def first_empty(self):
        """Get first empty slot index."""
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            size = int(self.fields.get("size") or len(contents) or 0)
            if size <= 0:
                size = len(contents) or 9
            while len(contents) < size:
                contents.append(None)
            for idx, slot in enumerate(contents):
                if slot is None:
                    return idx
            return -1
        return self._call_sync("firstEmpty")

    def get_item(self, slot: int):
        """Get item in a slot."""
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            return contents[slot] if 0 <= slot < len(contents) else None
        return self._call("getItem", slot)

    def set_item(self, slot: int, item: "Item"):
        """Set item in a slot."""
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            while len(contents) <= slot:
                contents.append(None)
            contents[slot] = item
            self.fields["contents"] = contents
            return None
        return self._call("setItem", slot, item)

    def contains(self, material: "Material", amount: int = 1):
        """Check if inventory contains a material."""
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            count = 0
            for item in contents:
                if item is None:
                    continue
                try:
                    if item.type == material:
                        count += getattr(item, "amount", 1)
                except Exception:
                    pass
            return count >= amount
        return self._call("contains", material, amount)

    @property
    def size(self):
        if self._handle is None:
            return int(self.fields.get("size") or 0)
        return self._call_sync("getSize")

    @property
    def contents(self) -> Any:
        if self._handle is None:
            return self.fields.get("contents") or []
        return self._call_sync("getContents")

    @property
    def title(self):
        return self._call_sync("getTitle")

    @property
    def holder(self):
        return self._call_sync("getHolder")

class Item(ProxyBase):
    """Item (ItemStack) API."""
    @classmethod
    def drop(cls, material: Material | str, location: Location, amount: int = 1, **kwargs: Any):
        """Drop an item at a location."""
        world = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            raise BridgeError("Location must have a world to drop an item")
        item = Item(material=material, amount=amount, **kwargs)
        return world._call("dropItem", location, item)

    @classmethod
    def give(cls, player: Player, material: Material | str, amount: int = 1, **kwargs: Any):
        """Give an item to a player's inventory."""
        item = Item(material=material, amount=amount, **kwargs)
        return player.inventory.add_item(item)

    def __init__(self, material: Optional[Material | str] = None, amount: int = 1, name: Optional[str] = None, lore: Optional[List[str]] = None, custom_model_data: Optional[int] = None, attributes: Optional[List[Dict[str, Any]]] = None, nbt: Optional[Dict[str, Any]] = None, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None and material is not None:
            if isinstance(material, str):
                material = Material.from_name(material.upper())
            fields = {"type": material, "amount": int(amount)}
            if name is not None:
                fields["name"] = str(name)
            if lore is not None:
                fields["lore"] = list(lore)
            if custom_model_data is not None:
                fields["customModelData"] = int(custom_model_data)
            if attributes is not None:
                fields["attributes"] = list(attributes)
            if nbt is not None:
                fields["nbt"] = nbt
            super().__init__(handle=None, type_name=type_name, fields=fields, target=target)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)
    @property
    def type(self):
        return self.fields.get("type")

    @property
    def amount(self):
        return self._call_sync("getAmount")

    def set_amount(self, value: int):
        """Set item amount."""
        return self._call("setAmount", value)

    @property
    def name(self):
        return self._call_sync("getName")

    def set_name(self, name: str):
        """Set display name."""
        if self._handle is None:
            self.fields["name"] = str(name)
            return self
        return self._call("setName", name)

    @property
    def lore(self):
        return self._call_sync("getLore")

    def set_lore(self, lore: List[str]):
        """Set lore lines."""
        if self._handle is None:
            self.fields["lore"] = list(lore)
            return self
        return self._call("setLore", lore)

    @property
    def custom_model_data(self):
        return self._call_sync("getCustomModelData")

    def set_custom_model_data(self, value: int):
        """Set custom model data."""
        if self._handle is None:
            self.fields["customModelData"] = int(value)
            return self
        return self._call("setCustomModelData", value)

    @property
    def attributes(self):
        return self._call_sync("getAttributes")

    def set_attributes(self, attributes: List[Dict[str, Any]]):
        """Set attribute modifiers."""
        if self._handle is None:
            self.fields["attributes"] = list(attributes)
            return self
        return self._call("setAttributes", attributes)

    @property
    def nbt(self):
        return self._call_sync("getNbt")

    def set_nbt(self, nbt: Dict[str, Any]):
        """Set NBT map."""
        if self._handle is None:
            self.fields["nbt"] = nbt
            return self
        return self._call("setNbt", nbt)

    def clone(self):
        """Clone this item."""
        return self._call("clone")

    def is_similar(self, other: "Item"):
        """Check if items are similar."""
        return self._call("isSimilar", other)

    @property
    def max_stack_size(self):
        """Get max stack size."""
        return self._call_sync("getMaxStackSize")

class ItemBuilder:
    """Fluent builder for Item objects. All methods return self for chaining.

    Example::
    ```
        item = (ItemBuilder("diamond_sword")
            .name("§bExcalibur")
            .lore("§7A legendary blade", "§7Forged in fire")
            .enchant("sharpness", 5)
            .enchant("unbreaking", 3)
            .unbreakable()
            .custom_model_data(42)
            .build())
    ```
    """

    def __init__(self, material: Any):
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        self._material = material
        self._amount: int = 1
        self._name: Optional[str] = None
        self._lore: List[str] = []
        self._custom_model_data: Optional[int] = None
        self._attributes: List[Dict[str, Any]] = []
        self._nbt: Optional[Dict[str, Any]] = None
        self._enchantments: Dict[str, int] = {}
        self._unbreakable_flag: bool = False
        self._glow_flag: bool = False
        self._item_flags: List[str] = []

    # --- Fluent setters ---
    def amount(self, n: int) -> "ItemBuilder":
        """Set stack amount."""
        self._amount = int(n)
        return self

    def name(self, n: str) -> "ItemBuilder":
        """Set display name."""
        self._name = str(n)
        return self

    def lore(self, *lines: str) -> "ItemBuilder":
        """Set lore lines (replaces existing)."""
        self._lore = list(lines)
        return self

    def add_lore(self, line: str) -> "ItemBuilder":
        """Append a lore line."""
        self._lore.append(str(line))
        return self

    def enchant(self, enchantment: str, level: int = 1) -> "ItemBuilder":
        """Add an enchantment (e.g. 'sharpness', 'minecraft:unbreaking')."""
        self._enchantments[enchantment.lower()] = int(level)
        return self

    def unbreakable(self, value: bool = True) -> "ItemBuilder":
        """Set whether the item is unbreakable."""
        self._unbreakable_flag = bool(value)
        return self

    def glow(self, value: bool = True) -> "ItemBuilder":
        """Make the item glow (enchantment glint override)."""
        self._glow_flag = bool(value)
        return self

    def custom_model_data(self, value: int) -> "ItemBuilder":
        """Set custom model data."""
        self._custom_model_data = int(value)
        return self

    def attributes(self, attrs: List[Dict[str, Any]]) -> "ItemBuilder":
        """Set attribute modifiers (replaces existing)."""
        self._attributes = list(attrs)
        return self

    def add_attribute(self, attribute: str, amount: float, operation: str = "ADD_NUMBER") -> "ItemBuilder":
        """Add a single attribute modifier."""
        self._attributes.append({"attribute": attribute, "amount": float(amount), "operation": operation})
        return self

    def nbt(self, data: Dict[str, Any]) -> "ItemBuilder":
        """Set raw NBT data."""
        self._nbt = dict(data)
        return self

    def flag(self, *flags: str) -> "ItemBuilder":
        """Add ItemFlags (e.g. 'HIDE_ENCHANTS', 'HIDE_ATTRIBUTES')."""
        self._item_flags.extend(str(f).upper() for f in flags)
        return self

    # --- Build ---
    def build(self) -> "Item":
        """Build and return the Item."""
        fields: Dict[str, Any] = {"type": self._material, "amount": self._amount}
        if self._name is not None:
            fields["name"] = self._name
        if self._lore:
            fields["lore"] = list(self._lore)
        if self._custom_model_data is not None:
            fields["customModelData"] = self._custom_model_data
        if self._attributes:
            fields["attributes"] = list(self._attributes)
        if self._nbt:
            fields["nbt"] = dict(self._nbt)
        if self._enchantments:
            fields["enchantments"] = dict(self._enchantments)
        if self._unbreakable_flag:
            fields["unbreakable"] = True
        if self._glow_flag:
            fields["glow"] = True
        if self._item_flags:
            fields["item_flags"] = list(self._item_flags)
        return Item(handle=None, fields=fields)

    # --- Copy ---
    @classmethod
    def from_item(cls, item: "Item") -> "ItemBuilder":
        """Create a builder from an existing Item, copying its fields."""
        builder = cls(item.type)
        builder._amount = item.amount or 1
        builder._name = item.name if hasattr(item, "fields") and "name" in item.fields else None
        builder._lore = list(item.lore or []) if hasattr(item, "fields") and "lore" in item.fields else []
        if hasattr(item, "fields"):
            builder._custom_model_data = item.fields.get("customModelData")
            builder._attributes = list(item.fields.get("attributes") or [])
            builder._nbt = dict(item.fields["nbt"]) if "nbt" in item.fields else None
            builder._enchantments = dict(item.fields.get("enchantments") or {})
            builder._unbreakable_flag = bool(item.fields.get("unbreakable"))
            builder._glow_flag = bool(item.fields.get("glow"))
            builder._item_flags = list(item.fields.get("item_flags") or [])
        return builder

class Material(EnumValue):
    """
        Material, such as diamond, netherite, wood, etc
    """
    TYPE_NAME = "org.bukkit.Material"

    def __init__(self, name: str, _name: Optional[str] = None):
        actual = _name if _name is not None else name
        super().__init__(self.TYPE_NAME, str(actual).upper())

class Biome(EnumValue):
    """
        Minecraft biome, e.g. plains, void, ice_spikes, etc
    """
    TYPE_NAME = "org.bukkit.block.Biome"

class Effect(ProxyBase):
    """Active potion effect."""
    @classmethod
    def apply(cls, player: "Player", effect_type: Optional[EffectType | str] = None, duration: int = 0, amplifier: int = 0, ambient: bool = False, particles: bool = True, icon: bool = True):
        """Apply a potion effect to a player."""
        effect = Effect(effect_type, duration, amplifier, ambient, particles, icon)
        return player.add_effect(effect)

    def __init__(self, effect_type: Optional[EffectType | str] = None, duration: int = 0, amplifier: int = 0, ambient: bool = False, particles: bool = True, icon: bool = True, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None and effect_type is not None:
            if isinstance(effect_type, str):
                effect_type = EffectType.from_name(effect_type.upper())
            fields = {
                "type": effect_type,
                "duration": int(duration),
                "amplifier": int(amplifier),
                "ambient": bool(ambient),
                "particles": bool(particles),
                "icon": bool(icon),
            }
            super().__init__(handle=None, type_name=type_name, fields=fields, target=target)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    @property
    def type(self):
        return self.fields.get("type")

    @property
    def duration(self) -> int:
        return int(self.fields.get("duration") or 0)

    @property
    def amplifier(self) -> int:
        return int(self.fields.get("amplifier") or 0)

    @property
    def ambient(self) -> bool:
        return bool(self.fields.get("ambient"))

    @property
    def particles(self) -> bool:
        return bool(self.fields.get("particles", True))

    @property
    def icon(self) -> bool:
        return bool(self.fields.get("icon", True))

    def with_duration(self, duration: int):
        """Return a copy with a different duration."""
        if self._handle is None:
            return Effect(self.type, duration, self.amplifier, self.ambient, self.particles, self.icon)
        return self._call("withDuration", duration)

    def with_amplifier(self, amplifier: int):
        """Return a copy with a different amplifier."""
        if self._handle is None:
            return Effect(self.type, self.duration, amplifier, self.ambient, self.particles, self.icon)
        return self._call("withAmplifier", amplifier)

class EffectType(EnumValue):
    """
        Potion effect type. e.g. poison, regeneration, strength, etc
    """
    TYPE_NAME = "org.bukkit.potion.PotionEffectType"

class AttributeType(EnumValue):
    """
        Attribute type, e.g. movement speed, base attack damage, etc
    """
    TYPE_NAME = "org.bukkit.attribute.Attribute"

class Attribute(ProxyBase):
    """Attribute instance for a living entity."""
    @classmethod
    def apply(cls, player: Player, attribute_type: AttributeType | str, base_value: float):
        """Set a player's base attribute value."""
        if isinstance(attribute_type, str):
            attribute_type = AttributeType.from_name(attribute_type.upper())
        attr = player._call_sync("getAttribute", attribute_type)
        if attr is None:
            return None
        return attr.set_base_value(base_value)

    @property
    def attribute_type(self):
        """Get the attribute type."""
        return self._call_sync("getAttribute")

    @property
    def value(self):
        """Get attribute value."""
        return self._call_sync("getValue")

    @property
    def base_value(self):
        """Get base value."""
        return self._call_sync("getBaseValue")

    def set_base_value(self, value: float):
        """Set base value."""
        return self._call("setBaseValue", value)

class GameMode(EnumValue):
    TYPE_NAME = "org.bukkit.GameMode"

class Sound(EnumValue):
    TYPE_NAME = "org.bukkit.Sound"

class Particle(EnumValue):
    TYPE_NAME = "org.bukkit.Particle"

class Difficulty(EnumValue):
    TYPE_NAME = "org.bukkit.Difficulty"

class Vector(ProxyBase):
    """
        Basic Vec3.
    """
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None:
            fields = {"x": float(x), "y": float(y), "z": float(z)}
            super().__init__(handle=None, type_name=type_name, fields=fields, target=target)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    @property
    def x(self) -> float:
        return self.fields.get("x", 0.0)

    @property
    def y(self) -> float:
        return self.fields.get("y", 0.0)

    @property
    def z(self) -> float:
        return self.fields.get("z", 0.0)

class BarColor(EnumValue):
    TYPE_NAME = "org.bukkit.boss.BarColor"

class BarStyle(EnumValue):
    TYPE_NAME = "org.bukkit.boss.BarStyle"

class BossBar(ProxyBase):
    """Boss bar API."""
    @classmethod
    def create(cls, title: str, color: Optional["BarColor"] = None, style: Optional["BarStyle"] = None, players: Optional[List["Player"]] = None):
        """Create a boss bar and optionally add players."""
        if color is None:
            color = BarColor.from_name("PINK")
        if style is None:
            style = BarStyle.from_name("SOLID")
        bar = server._call_sync("createBossBar", title, color, style)
        if players:
            for player in players:
                bar.add_player(player)
        return bar

    def add_player(self, player: Player):
        """Add a player to the boss bar."""
        return self._call("addPlayer", player)

    def remove_player(self, player: Player):
        """Remove a player from the boss bar."""
        return self._call("removePlayer", player)

    @property
    def title(self):
        """Get title."""
        return self._call_sync("getTitle")

    def set_title(self, title: str):
        """Set title."""
        return self._call("setTitle", title)

    @property
    def progress(self):
        """Get progress (0..1)."""
        return self._call_sync("getProgress")

    def set_progress(self, value: float):
        """Set progress (0..1)."""
        return self._call("setProgress", value)

    @property
    def color(self):
        """Get bar color."""
        return self._call_sync("getColor")

    def set_color(self, color: "BarColor"):
        """Set bar color."""
        return self._call("setColor", color)

    @property
    def style(self):
        """Get bar style."""
        return self._call_sync("getStyle")

    def set_style(self, style: "BarStyle"):
        """Set bar style."""
        return self._call("setStyle", style)

    @property
    def visible(self):
        """Check visibility."""
        return self._call_sync("isVisible")

    def set_visible(self, value: bool):
        """Set visibility."""
        return self._call("setVisible", value)

class Scoreboard(ProxyBase):
    """Scoreboard API."""
    @classmethod
    def create(cls):
        """Create a new scoreboard."""
        manager = server._call_sync("getScoreboardManager")
        return manager._call_sync("getNewScoreboard")

    def register_objective(self, name: str, criteria: str, display_name: str = ""):
        """Register a new objective."""
        if display_name:
            return self._call("registerNewObjective", name, criteria, display_name)
        return self._call("registerNewObjective", name, criteria)

    def get_team(self, name: str):
        """Get a team by name."""
        return self._call("getTeam", name)

    def register_team(self, name: str):
        """Register a new team."""
        return self._call("registerNewTeam", name)

    def get_objective(self, name: str):
        """Get an objective by name."""
        return self._call("getObjective", name)

    @property
    def objectives(self):
        """Get all objectives."""
        return self._call_sync("getObjectives")

    @property
    def teams(self):
        """Get all teams."""
        return self._call_sync("getTeams")

    def clear_slot(self, slot: Any):
        """Clear display slot."""
        return self._call("clearSlot", slot)

class Team(ProxyBase):
    """Team API."""
    @classmethod
    def create(cls, name: str, scoreboard: Optional["Scoreboard"] = None):
        """Create a team on a scoreboard."""
        if scoreboard is None:
            scoreboard = Scoreboard.create()  # type: ignore[assignment]
        return scoreboard.register_team(name)  # type: ignore[union-attr]

    def add_entry(self, entry: str):
        """Add an entry to the team."""
        return self._call("addEntry", entry)

    def remove_entry(self, entry: str):
        """Remove an entry from the team."""
        return self._call("removeEntry", entry)

    def set_prefix(self, prefix: str):
        """Set team prefix."""
        return self._call("setPrefix", prefix)

    def set_suffix(self, suffix: str):
        """Set team suffix."""
        return self._call("setSuffix", suffix)

    @property
    def color(self):
        """Get team color."""
        return self._call_sync("getColor")

    def set_color(self, color: Any):
        """Set team color."""
        return self._call("setColor", color)

    @property
    def entries(self):
        """Get team entries."""
        return self._call_sync("getEntries")

class Objective(ProxyBase):
    """Objective API."""
    @classmethod
    def create(cls, name: str, criteria: str, display_name: str = "", scoreboard: Optional["Scoreboard"] = None):
        """Create an objective on a scoreboard."""
        if scoreboard is None:
            scoreboard = Scoreboard.create()  # type: ignore[assignment]
        return scoreboard.register_objective(name, criteria, display_name)  # type: ignore[union-attr]

    def set_display_name(self, name: str):
        """Set display name."""
        return self._call("setDisplayName", name)

    def get_score(self, entry: str):
        """Get a score for an entry."""
        return self._call("getScore", entry)

    @property
    def name(self):
        """Get objective name."""
        return self._call_sync("getName")

    @property
    def criteria(self):
        """Get objective criteria."""
        return self._call_sync("getCriteria")

    @property
    def display_slot(self):
        """Get display slot."""
        return self._call_sync("getDisplaySlot")

    def set_display_slot(self, slot: Any):
        """Set display slot."""
        return self._call("setDisplaySlot", slot)

class Advancement(ProxyBase):
    """Advancement API."""
    @classmethod
    def grant(cls, player: "Player", key: str):
        """Grant an advancement by key to a player."""
        return player._call("grantAdvancement", key)

    @classmethod
    def revoke(cls, player: "Player", key: str):
        """Revoke an advancement by key from a player."""
        return player._call("revokeAdvancement", key)

    @property
    def key(self):
        """Get the advancement key."""
        return self._call_sync("getKey")

class AdvancementProgress(ProxyBase):
    """Advancement progress API."""
    @property
    def is_done(self):
        """Check if completed."""
        return self._call_sync("isDone")

    def award_criteria(self, name: str):
        """Award a criterion."""
        return self._call("awardCriteria", name)

    def revoke_criteria(self, name: str):
        """Revoke a criterion."""
        return self._call("revokeCriteria", name)

    @property
    def remaining_criteria(self):
        """Get remaining criteria."""
        return self._call_sync("getRemainingCriteria")

    @property
    def awarded_criteria(self):
        """Get awarded criteria."""
        return self._call_sync("getAwardedCriteria")

class Potion(ProxyBase):
    """Potion API (legacy)."""
    @classmethod
    def apply(cls, player: "Player", effect_type: Optional[EffectType | str] = None, duration: int = 0, amplifier: int = 0, ambient: bool = False, particles: bool = True, icon: bool = True):
        """Apply a potion effect to a player."""
        return Effect.apply(player, effect_type, duration, amplifier, ambient, particles, icon)

    @property
    def type(self):
        """Get potion type."""
        return self._call_sync("getType")

    @property
    def level(self):
        """Get potion level."""
        return self._call_sync("getLevel")

class ChatFacade(ProxyBase):
    """Chat helper facade."""
    def broadcast(self, message: str):
        """Broadcast a chat message."""
        return self._call("broadcast", message)

class ReflectFacade(ProxyBase):
    """Reflection helper facade."""
    def clazz(self, name: str):
        """Get a Java class by name."""
        return self._call("clazz", name)

# Core classes
class _BatchContext:
    def __init__(self, connection: BridgeConnection, mode: str):
        self._connection = connection
        self._mode = mode

    async def __aenter__(self):
        self._connection._begin_batch(self._mode)  # type: ignore[reportPrivateUsage]
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any):
        self._connection._end_batch()  # type: ignore[reportPrivateUsage]
        if exc_type is None:
            await self._connection.flush()
        return False

class BridgeConnection:
    """Socket bridge connection and dispatcher."""
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port

        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._pending: Dict[int, "asyncio.Future[Any]"] = {}
        self._pending_sync: Dict[int, _SyncWait] = {}
        self._handlers: Dict[str, List[Callable[[Any], Awaitable[None]]]] = {}

        self._id_counter = itertools.count(1)
        self._socket = socket.create_connection((host, port))

        self._file = self._socket.makefile("rwb", buffering=0)
        self._lock = threading.Lock()

        # Send auth token before starting reader thread
        token = os.environ.get("PYJAVABRIDGE_TOKEN", "")
        self.send({"type": "auth", "token": token})

        self._batch_stack: List[str] = []
        self._batch_messages: List[Dict[str, Any]] = []
        self._batch_futures: List["asyncio.Future[Any]"] = []

        self._release_queue: List[int] = []
        self._release_lock = threading.Lock()

        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        print(f"[PyJavaBridge] Connected to {host}:{port}")

    def subscribe(self, event_name: str, once_per_tick: bool, priority: str = "NORMAL", throttle_ms: int = 0):
        print(f"[PyJavaBridge] Subscribing to {event_name} once_per_tick={once_per_tick} priority={priority} throttle_ms={throttle_ms}")
        self.send({"type": "subscribe", "event": event_name, "once_per_tick": once_per_tick, "priority": priority, "throttle_ms": throttle_ms})

    def register_command(self, name: str, permission: Optional[str] = None):
        """Register a command name with the server."""
        msg: Dict[str, Any] = {"type": "register_command", "name": name}
        if permission is not None:
            msg["permission"] = permission
        self.send(msg)

    def on(self, event_name: str, handler: Callable[[Any], Awaitable[None]]):
        self._handlers.setdefault(event_name, []).append(handler)

    def call(self, method: str, args: Optional[List[Any]] = None, handle: Optional[int] = None, target: Optional[str] = None, **kwargs: Any) -> BridgeCall:
        self._flush_releases()
        request_id = self._next_id()
        future = self._loop.create_future()
        self._pending[request_id] = future
        message: Dict[str, Any] = {
            "type": "call",
            "id": request_id,
            "method": method,
            "args_list": [self._serialize(arg) for arg in (args or [])],
        }
        if handle is not None:
            message["handle"] = handle
        if target is not None:
            message["target"] = target
        extra_args = {k: self._serialize(v) for k, v in kwargs.items() if k not in {"field", "value"}}
        if extra_args:
            message["args"] = extra_args
        if "field" in kwargs:
            message["field"] = kwargs["field"]
        if "value" in kwargs:
            message["value"] = self._serialize(kwargs["value"])
        if self._batch_stack:
            self._batch_messages.append(message)
            self._batch_futures.append(future)
            return BridgeCall(future)
        self.send(message)
        return BridgeCall(future)

    def call_sync(self, method: str, args: Optional[List[Any]] = None, handle: Optional[int] = None, target: Optional[str] = None, **kwargs: Any) -> Any:
        request_id = self._next_id()
        wait = _SyncWait()
        self._pending_sync[request_id] = wait
        message: Dict[str, Any] = {
            "type": "call",
            "id": request_id,
            "method": method,
            "args_list": [self._serialize(arg) for arg in (args or [])],
        }
        if handle is not None:
            message["handle"] = handle
        if target is not None:
            message["target"] = target
        extra_args = {k: self._serialize(v) for k, v in kwargs.items() if k not in {"field", "value"}}
        if extra_args:
            message["args"] = extra_args
        if "field" in kwargs:
            message["field"] = kwargs["field"]
        if "value" in kwargs:
            message["value"] = self._serialize(kwargs["value"])
        self.send(message)
        wait.event.wait()
        if wait.error is not None:
            raise wait.error
        return wait.result

    def wait(self, ticks: int = 1) -> BridgeCall:
        request_id = self._next_id()
        future = self._loop.create_future()
        self._pending[request_id] = future
        self.send({"type": "wait", "id": request_id, "ticks": int(ticks)})
        return BridgeCall(future)

    def _begin_batch(self, mode: str):
        self._batch_stack.append(mode)

    def _end_batch(self):
        if self._batch_stack:
            self._batch_stack.pop()

    def _current_batch_mode(self) -> Optional[str]:
        if not self._batch_stack:
            return None
        return "atomic" if "atomic" in self._batch_stack else "frame"

    async def flush(self):
        if not self._batch_messages:
            return None
        mode = self._current_batch_mode()
        messages = self._batch_messages
        futures = self._batch_futures
        self._batch_messages = []
        self._batch_futures = []
        self.send({"type": "call_batch", "atomic": mode == "atomic", "messages": messages})
        results = await asyncio.gather(*futures, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result
        return None

    def frame(self):
        return _BatchContext(self, "frame")

    def atomic(self):
        return _BatchContext(self, "atomic")

    def send(self, message: Dict[str, Any]):
        data = _json_dumps(message)
        header = struct.pack("!I", len(data))
        with self._lock:
            self._file.write(header)
            self._file.write(data)
            self._file.flush()

    def _queue_release(self, handle: int):
        with self._release_lock:
            self._release_queue.append(handle)
            if len(self._release_queue) >= 64:
                self._flush_releases_locked()

    def _flush_releases_locked(self):
        """Flush queued handle releases. Must be called with _release_lock held."""
        if not self._release_queue:
            return
        handles = self._release_queue[:]
        self._release_queue.clear()
        try:
            self.send({"type": "release", "handles": handles})
        except Exception:
            pass

    def _flush_releases(self):
        """Flush queued handle releases."""
        with self._release_lock:
            self._flush_releases_locked()

    def completed_call(self, result: Any):
        future = self._loop.create_future()
        future.set_result(result)
        return BridgeCall(future)

    def _read_exact(self, size: int) -> Optional[bytes]:
        data = bytearray(size)
        view = memoryview(data)
        offset = 0
        while offset < size:
            chunk = self._file.read(size - offset)
            if not chunk:
                return None
            view[offset:offset + len(chunk)] = chunk
            offset += len(chunk)
        return bytes(data)

    def _reader(self):
        try:
            while True:
                header = self._read_exact(4)
                if not header:
                    break
                try:
                    length = struct.unpack("!I", header)[0]
                    payload = self._read_exact(length)
                    if payload is None:
                        break
                    message = _json_loads(payload)
                    msg_type = message.get("type")
                    if msg_type in ("return", "error"):
                        msg_id = message.get("id")
                        if msg_id is not None:
                            wait = self._pending_sync.pop(msg_id, None)
                            if wait is not None:
                                if msg_type == "return":
                                    wait.result = self._deserialize(message.get("result"))
                                else:
                                    code = message.get("code")
                                    if code == "ENTITY_GONE":
                                        wait.error = EntityGoneException(message.get("message"))
                                    else:
                                        wait.error = BridgeError(message.get("message"))
                                wait.event.set()
                                continue
                    self._loop.call_soon_threadsafe(self._handle_message, message)
                except Exception as exc:
                    self._loop.call_soon_threadsafe(self._handle_reader_error, exc)
                    break
        finally:
            # Wake all pending sync waits on disconnect
            disconnect_error = BridgeError("Connection lost")
            for wait in list(self._pending_sync.values()):
                wait.error = disconnect_error
                wait.event.set()
            self._pending_sync.clear()
            # Wake all pending async futures
            self._loop.call_soon_threadsafe(self._handle_reader_error, disconnect_error)

    def _handle_message(self, message: Dict[str, Any]):
        msg_type = message.get("type")
        if msg_type == "return":
            msg_id: int = message.get("id")  # type: ignore[assignment]
            future = self._pending.pop(msg_id, None)
            if future is not None:
                future.set_result(self._deserialize(message.get("result")))
        elif msg_type == "error":
            msg_id: int = message.get("id")  # type: ignore[assignment]
            future = self._pending.pop(msg_id, None)
            if future is not None:
                code = message.get("code")
                if code == "ENTITY_GONE":
                    future.set_exception(EntityGoneException(message.get("message")))
                else:
                    future.set_exception(BridgeError(message.get("message")))
        elif msg_type == "event":
            event_name = message.get("event")
            print(f"[PyJavaBridge] Event received: {event_name}")
            payload = self._deserialize(message.get("payload"))
            if isinstance(payload, dict) and "event" in payload:
                p = cast(Dict[str, Any], payload)
                event_obj = p.get("event")
                if isinstance(event_obj, ProxyBase):
                    if "id" in p:
                        event_obj.fields["__event_id__"] = p.get("id")
                    for key, value in p.items():
                        if key != "event":
                            event_obj.fields[key] = value
                    payload = event_obj
            if event_name is not None:
                asyncio.create_task(self._dispatch_event(event_name, payload))
        elif msg_type == "event_batch":
            event_name = message.get("event")
            payloads = message.get("payloads", [])
            for payload in payloads:
                self._handle_message({"type": "event", "event": event_name, "payload": payload})
        elif msg_type == "shutdown":
            asyncio.create_task(self._handle_shutdown())

    async def _dispatch_event(self, event_name: str, payload: Any):
        handlers = list(self._handlers.get(event_name, []))
        results: List[Any] = []
        try:
            awaitables: List[Awaitable[Any]] = []
            for handler in handlers:
                try:
                    result = handler(payload)
                except Exception as exc:
                    results.append(exc)
                    continue
                if inspect.isawaitable(result):
                    awaitables.append(result)
                else:
                    results.append(result)
            if awaitables:
                gathered = await asyncio.gather(*awaitables, return_exceptions=True)
                results.extend(gathered)
            for result in results:
                if isinstance(result, Exception):
                    print(f"[PyJavaBridge] Handler error: {result}")
        finally:
            event_id = None
            if isinstance(payload, ProxyBase):
                event_id = payload.fields.get("__event_id__")
            if event_id is not None:
                if handlers:
                    override_text = None
                    override_damage = None
                    is_damage_event = isinstance(payload, ProxyBase) and "damage" in payload.fields
                    for result in results:
                        if isinstance(result, str):
                            override_text = result
                        elif is_damage_event and isinstance(result, (int, float)) and not isinstance(result, bool):
                            override_damage = float(result)
                    if override_text is not None:
                        self.send({"type": "event_result", "id": event_id, "result": override_text, "result_type": "chat"})
                    if override_damage is not None:
                        self.send({"type": "event_result", "id": event_id, "result": override_damage, "result_type": "damage"})
                self.send({"type": "event_done", "id": event_id})

    async def _handle_shutdown(self):
        """Handle server shutdown - dispatch to handlers, then ack."""
        try:
            await self._dispatch_event("shutdown", SimpleNamespace(fields={}))
        except Exception as e:
            print(f"[PyJavaBridge] Shutdown handler error: {e}")
        finally:
            try:
                self.send({"type": "shutdown_ack"})
            except Exception:
                pass

    def _handle_reader_error(self, exc: Exception):
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)

    def _next_id(self) -> int:
        return next(self._id_counter)

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, ProxyBase):
            if value._handle is not None:  # type: ignore[reportPrivateUsage]
                return {"__handle__": value._handle}  # type: ignore[reportPrivateUsage]
            if value._target == "ref" and value._ref_type and value._ref_id:  # type: ignore[reportPrivateUsage]
                return {"__ref__": {"type": value._ref_type, "id": value._ref_id}}  # type: ignore[reportPrivateUsage]
            return {"__value__": value.__class__.__name__, "fields": {k: self._serialize(v) for k, v in value.fields.items()}}
        if isinstance(value, EnumValue):
            return {"__enum__": value.type, "name": value.name}
        if isinstance(value, uuid.UUID):
            return {"__uuid__": str(value)}
        if isinstance(value, list):
            items = cast(List[Any], value)
            return [self._serialize(v) for v in items]
        if isinstance(value, dict):
            d = cast(Dict[str, Any], value)
            return {k: self._serialize(v) for k, v in d.items()}
        return value

    def _deserialize(self, value: Any) -> Any:
        if isinstance(value, dict):
            d = cast(Dict[str, Any], value)
            if "__handle__" in d:
                return _proxy_from(d)
            if "__uuid__" in d:
                return uuid.UUID(d["__uuid__"])
            if "__enum__" in d:
                return _enum_from(d["__enum__"], d["name"])
            if {"x", "y", "z"}.issubset(d.keys()):
                return SimpleNamespace(**{k: self._deserialize(v) for k, v in d.items()})
            return {k: self._deserialize(v) for k, v in d.items()}
        if isinstance(value, list):
            items = cast(List[Any], value)
            return [self._deserialize(v) for v in items]
        return value

class _ConsolePlayer:
    def __init__(self, sender_obj: Any):
        self._sender = sender_obj
        self.fields: Dict[str, Any] = {"name": "Console", "uuid": "console"}

    @property
    def name(self):
        return "Console"

    @property
    def uuid(self):
        return "console"

    def is_op(self):
        return _connection.completed_call(True)

    def has_permission(self, permission: str):
        return _connection.completed_call(True)

    def send_message(self, message: str):
        try:
            if isinstance(self._sender, ProxyBase):
                _connection.call_sync(
                    method="sendMessage",
                    args=[message],
                    handle=self._sender._handle,  # type: ignore[reportPrivateUsage]
                    target=self._sender._target,  # type: ignore[reportPrivateUsage]
                )
                return _connection.completed_call(None)
            if self._sender is not None:
                result = self._sender.sendMessage(message)
                if hasattr(result, "__await__"):
                    return result
        except Exception:
            pass
        print(f"[PyJavaBridge] {message}")
        return _connection.completed_call(None)

    def play_sound(self, sound: Any, volume: float = 1.0, pitch: float = 1.0):
        return _connection.completed_call(None)

    def kick(self, reason: str = ""):
        return _connection.completed_call(None)

# Helpers
class Sidebar:
    """Helper for displaying formatted text lines on a sidebar scoreboard.

    Usage:
        sidebar = Sidebar("My Title")
        sidebar[0] = "First line"
        sidebar[1] = "Second line"
        sidebar[2] = ""  # blank line
        sidebar[3] = "Fourth line"
        sidebar.show(player)

        # Update a line later:
        sidebar[1] = "Updated second line"

        # Remove a line:
        del sidebar[3]
    """

    _ENTRIES = [f"\u00a7{c}" for c in "0123456789abcdef"]
    MAX_LINES = len(_ENTRIES)

    def __init__(self, title: str = ""):
        self._board = Scoreboard.create()
        self._obj = self._board._call_sync("registerNewObjective", "sidebar", "dummy", title)
        self._obj._call_sync("setDisplaySlot", EnumValue("org.bukkit.scoreboard.DisplaySlot", "SIDEBAR"))
        self._teams: dict[int, Any] = {}
        self._lines: dict[int, str] = {}

    def _ensure_slot(self, slot: int):
        if slot < 0 or slot >= self.MAX_LINES:
            raise IndexError(f"Sidebar supports lines 0-{self.MAX_LINES - 1}")
        if slot not in self._teams:
            entry = self._ENTRIES[slot]
            team = self._board._call_sync("registerNewTeam", f"_sb{slot}")
            team._call_sync("addEntry", entry)
            score = self._obj._call_sync("getScore", entry)
            score._call_sync("setScore", self.MAX_LINES - slot)
            self._teams[slot] = team

    def __setitem__(self, slot: int, text: str):
        self._ensure_slot(slot)
        self._teams[slot]._call_sync("setPrefix", text)
        self._lines[slot] = text

    def __getitem__(self, slot: int) -> str:
        return self._lines.get(slot, "")

    def __delitem__(self, slot: int):
        if slot in self._teams:
            entry = self._ENTRIES[slot]
            self._teams[slot]._call_sync("unregister")
            self._obj._call_sync("getScore", entry)._call_sync("resetScore")
            del self._teams[slot]
            self._lines.pop(slot, None)

    def show(self, player: "Player"):
        """Show this sidebar to a player."""
        player._call_sync("setScoreboard", self._board)

    @property
    def title(self) -> str:
        return self._obj._call_sync("getDisplayName")

    @title.setter
    def title(self, value: str):
        self._obj._call_sync("setDisplayName", value)

class Config:
    """Per-script configuration helper with dot-path access and file persistence.

    Supported formats: ``"toml"`` (default), ``"json"``, ``"properties"``.

    Usage::

        config = Config(defaults={"welcome": {"enabled": True, "message": "Hello!"}})
        if config.get_bool("welcome.enabled"):
            msg = config.get("welcome.message", "Hi")
        config.set("welcome.message", "Welcome!")
        config.save()
    """

    _EXTENSIONS = {"toml": ".toml", "json": ".json", "properties": ".properties"}

    def __init__(self, name: Optional[str] = None, defaults: Optional[Dict[str, Any]] = None, format: str = "toml"):
        if format not in self._EXTENSIONS:
            raise ValueError(f"Unsupported config format: {format!r} (expected toml, json, or properties)")
        self._format = format
        script_path = os.environ.get("PYJAVABRIDGE_SCRIPT", "")
        if name is None:
            name = os.path.splitext(os.path.basename(script_path))[0] if script_path else "config"
        scripts_dir = os.path.dirname(script_path) if script_path else "."
        plugin_dir = os.path.dirname(scripts_dir)
        config_dir = os.path.join(plugin_dir, "config", name)
        os.makedirs(config_dir, exist_ok=True)

        ext = self._EXTENSIONS[format]
        self._path = os.path.join(config_dir, f"config{ext}")
        self._data: Dict[str, Any] = dict(defaults) if defaults else {}
        self._defaults: Dict[str, Any] = dict(defaults) if defaults else {}
        self.reload()

    def reload(self):
        """Reload config from disk, merging with defaults."""
        data: Dict[str, Any] = {}
        if os.path.exists(self._path):
            try:
                if self._format == "toml":
                    import tomllib
                    with open(self._path, "rb") as fb:
                        data = tomllib.load(fb)
                elif self._format == "json":
                    with open(self._path, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        data = cast(Dict[str, Any], loaded) if isinstance(loaded, dict) else {}
                elif self._format == "properties":
                    data = _properties_load(self._path)
            except Exception:
                data = {}
        merged = dict(self._defaults)
        _deep_merge(merged, data)
        self._data = merged

    def save(self):
        """Save current config to disk."""
        with open(self._path, "w", encoding="utf-8") as f:
            if self._format == "toml":
                f.write(_toml_dumps(self._data))
            elif self._format == "json":
                json.dump(self._data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            elif self._format == "properties":
                f.write(_properties_dumps(self._data))

    def get(self, path: str, default: Any = None) -> Any:
        """Get a value by dot-path (e.g. 'database.host')."""
        keys = path.split(".")
        data = self._data
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default
        return data

    def get_int(self, path: str, default: int = 0) -> int:
        """Get an integer value by dot-path."""
        v = self.get(path)
        return int(v) if v is not None else default

    def get_float(self, path: str, default: float = 0.0) -> float:
        """Get a float value by dot-path."""
        v = self.get(path)
        return float(v) if v is not None else default

    def get_bool(self, path: str, default: bool = False) -> bool:
        """Get a boolean value by dot-path."""
        v = self.get(path)
        if v is None:
            return default
        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on")
        return bool(v)

    def get_list(self, path: str, default: Optional[List[Any]] = None) -> List[Any]:
        """Get a list value by dot-path."""
        v = self.get(path)
        if v is None:
            return default if default is not None else []
        result: List[Any] = list(cast(List[Any], v)) if isinstance(v, (list, tuple)) else [v]
        return result

    def set(self, path: str, value: Any):
        """Set a value by dot-path, creating intermediate dicts as needed."""
        keys = path.split(".")
        data = self._data
        for key in keys[:-1]:
            if key not in data or not isinstance(data[key], dict):
                data[key] = {}
            data = data[key]
        data[keys[-1]] = value

    def delete(self, path: str) -> bool:
        """Delete a value by dot-path. Returns True if the key existed."""
        keys = path.split(".")
        data = self._data
        for key in keys[:-1]:
            if not isinstance(data, dict) or key not in data:
                return False
            data = data[key]
        if isinstance(data, dict) and keys[-1] in data:
            del data[keys[-1]]
            return True
        return False

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None

    @property
    def data(self) -> Dict[str, Any]:
        """Direct access to the underlying data dict."""
        return self._data

    @property
    def path(self) -> str:
        """Path to the config file on disk."""
        return self._path

class Cooldown:
    """Per-player cooldown tracker.

    Usage::

        cd = Cooldown(seconds=5, on_expire=lambda p: p.send_message("Ready!"))
        if cd.check(player):
            # ability available, cooldown now started
            ...
        else:
            player.send_message(f"Wait {cd.remaining(player):.1f}s")
    """

    def __init__(self, seconds: float = 1.0,
                 on_expire: Optional[Callable[["Player"], Any]] = None):
        self.seconds = seconds
        self.on_expire = on_expire
        self._expiry: Dict[str, float] = {}
        self._task_started = False

    def _get_uuid(self, player: "Player") -> str:
        if hasattr(player, "fields") and "uuid" in player.fields:
            return player.fields["uuid"]
        return str(player.uuid)

    def check(self, player: "Player") -> bool:
        """Check if the player can use the ability. If yes, starts the cooldown and returns True."""
        uid = self._get_uuid(player)
        now = time.time()
        if uid in self._expiry and now < self._expiry[uid]:
            return False
        self._expiry[uid] = now + self.seconds
        if self.on_expire is not None and not self._task_started:
            self._start_expire_task()
        return True

    def remaining(self, player: "Player") -> float:
        """Seconds remaining on this player's cooldown (0.0 if not on cooldown)."""
        uid = self._get_uuid(player)
        if uid not in self._expiry:
            return 0.0
        left = self._expiry[uid] - time.time()
        return max(0.0, left)

    def reset(self, player: "Player"):
        """Reset (clear) the cooldown for a player."""
        uid = self._get_uuid(player)
        self._expiry.pop(uid, None)

    def _start_expire_task(self):
        self._task_started = True

        async def _check_expiry():
            while _connection is not None:
                now = time.time()
                expired = [uid for uid, exp in self._expiry.items() if now >= exp]
                for uid in expired:
                    del self._expiry[uid]
                    if self.on_expire is not None:
                        try:
                            p = Player(uuid=uid)
                            result = self.on_expire(p)
                            if hasattr(result, "__await__"):
                                await result
                        except Exception:
                            pass
                await server.wait(10)  # check every 10 ticks (0.5s)

        _connection.on("server_boot", lambda _: asyncio.ensure_future(_check_expiry()))

class Hologram:
    """Floating text display using a TextDisplay entity.

    Usage::

        holo = Hologram(location, "Line 1", "Line 2")
        holo[0] = "Updated"
        holo.append("New line")
        del holo[1]
        holo.teleport(new_location)
        holo.remove()
    """

    def __init__(self, location: "Location", *lines: str,
                 billboard: str = "CENTER"):
        self._lines: list[str] = list(lines)

        world: Any = location.world

        if isinstance(world, str):
            world = World(name=world)

        if world is None:
            world = World(name='world')

        self._entity: Any = world._call_sync(
            "spawnEntity", location, EntityType.from_name("TEXT_DISPLAY"))

        self._entity._call("setBillboard", billboard)
        self._update_text()

    def _update_text(self):
        text = "\n".join(self._lines) if self._lines else ""
        self._entity._call("text", text)

    def __setitem__(self, index: int, text: str):
        if index < 0 or index >= len(self._lines):
            raise IndexError(f"Line index {index} out of range (0-{len(self._lines) - 1})")
        self._lines[index] = text
        self._update_text()

    def __getitem__(self, index: int) -> str:
        return self._lines[index]

    def __delitem__(self, index: int):
        del self._lines[index]
        self._update_text()

    def __len__(self) -> int:
        return len(self._lines)

    def append(self, text: str):
        """Add a line at the bottom."""
        self._lines.append(text)
        self._update_text()

    def teleport(self, location: "Location"):
        """Move the hologram to a new location."""
        self._entity.teleport(location)

    def remove(self):
        """Remove the hologram entity."""
        self._entity.remove()

    @property
    def billboard(self) -> str:
        return self._entity._call_sync("getBillboard")

    @billboard.setter
    def billboard(self, value: str):
        self._entity._call("setBillboard", value)

    @property
    def see_through(self) -> bool:
        return self._entity._call_sync("isSeeThrough")

    @see_through.setter
    def see_through(self, value: bool):
        self._entity._call("setSeeThrough", value)

    @property
    def shadowed(self) -> bool:
        return self._entity._call_sync("isShadowed")

    @shadowed.setter
    def shadowed(self, value: bool):
        self._entity._call("setShadowed", value)

    @property
    def alignment(self) -> str:
        return self._entity._call_sync("getAlignment")

    @alignment.setter
    def alignment(self, value: str):
        self._entity._call("setAlignment", value)

    @property
    def line_width(self) -> int:
        return self._entity._call_sync("getLineWidth")

    @line_width.setter
    def line_width(self, value: int):
        self._entity._call("setLineWidth", value)

    @property
    def background(self) -> Optional[int]:
        return self._entity._call_sync("getBackgroundColor")

    @background.setter
    def background(self, value: Optional[int]):
        if value is None:
            self._entity._call("setDefaultBackground", True)
        else:
            self._entity._call("setDefaultBackground", False)
            self._entity._call("setBackgroundColor", value)

class ActionBarDisplay:
    """Persistent action bar text that auto-refreshes.

    Usage::

        bar = ActionBarDisplay()
        bar[player] = "Health: 20"
        bar[player] = "Health: 18"  # updates immediately
        del bar[player]              # stops showing
    """

    def __init__(self):
        self._texts: Dict[str, str] = {}
        self._players: Dict[str, "Player"] = {}
        self._task_started = False

    def _get_uuid(self, player: "Player") -> str:
        if hasattr(player, "fields") and "uuid" in player.fields:
            return player.fields["uuid"]
        return str(player.uuid)

    def __setitem__(self, player: "Player", text: str):
        uid = self._get_uuid(player)
        self._texts[uid] = text
        self._players[uid] = player
        player.send_action_bar(text)
        if not self._task_started:
            self._start_refresh()

    def __getitem__(self, player: "Player") -> str:
        uid = self._get_uuid(player)
        return self._texts.get(uid, "")

    def __delitem__(self, player: "Player"):
        uid = self._get_uuid(player)
        self._texts.pop(uid, None)
        self._players.pop(uid, None)

    def _start_refresh(self):
        self._task_started = True

        async def _refresh():
            while _connection is not None:
                for uid, text in list(self._texts.items()):
                    p = self._players.get(uid)
                    if p is not None:
                        try:
                            p.send_action_bar(text)
                        except Exception:
                            pass
                await server.wait(40)  # refresh every 2 seconds

        _connection.on("server_boot", lambda _: asyncio.ensure_future(_refresh()))

class BossBarDisplay:
    """Convenient boss bar display with value/max support and cooldown linking.

    Usage::

        # Simple text
        bar = BossBarDisplay("Welcome!", color="BLUE")
        bar.show(player)
        bar.text = "Server TPS: 20"

        # Progress bar
        bar = BossBarDisplay("Loading...", color="RED")
        bar.value = 50
        bar.max = 100

        # Linked to a Cooldown
        cd = Cooldown(seconds=10)
        bar = BossBarDisplay("Ability Cooldown", color="YELLOW")
        bar.link_cooldown(cd, player)
    """

    def __init__(self, title: str = "", color: str = "PINK",
                 style: str = "SOLID"):
        self._bar = BossBar.create(title,
                BarColor.from_name(color.upper()),
                BarStyle.from_name(style.upper())
        )

        self._value: float = 0.0
        self._max: float = 1.0
        self._linked_task_started = False

    def show(self, player: "Player"):
        """Show this boss bar to a player."""
        self._bar.add_player(player)

    def hide(self, player: "Player"):
        """Hide this boss bar from a player."""
        self._bar.remove_player(player)

    @property
    def text(self) -> str:
        return self._bar.title

    @text.setter
    def text(self, value: str):
        self._bar.set_title(value)

    @property
    def color(self) -> str:
        return self._bar.color

    @color.setter
    def color(self, value: str):
        self._bar.set_color(BarColor.from_name(value.upper()))

    @property
    def style(self) -> str:
        return self._bar.style

    @style.setter
    def style(self, value: str):
        self._bar.set_style(BarStyle.from_name(value.upper()))

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float):
        self._value = v
        self._update_progress()

    @property
    def max(self) -> float:
        return self._max

    @max.setter
    def max(self, v: float):
        self._max = max(v, 0.001)
        self._update_progress()

    @property
    def progress(self) -> float:
        return self._bar.progress

    @progress.setter
    def progress(self, v: float):
        self._bar.set_progress(max(0.0, min(1.0, v)))

    @property
    def visible(self) -> bool:
        return self._bar.visible

    @visible.setter
    def visible(self, v: bool):
        self._bar.set_visible(v)

    def _update_progress(self):
        self._bar.set_progress(max(0.0, min(1.0, self._value / self._max)))

    def link_cooldown(self, cooldown: "Cooldown", player: "Player"):
        """Link this boss bar's progress to a Cooldown, auto-updating as it ticks down."""
        self.show(player)
        self._max = cooldown.seconds

        async def _update():
            while _connection is not None:
                remaining = cooldown.remaining(player)
                self._value = remaining
                self._update_progress()
                if remaining <= 0:
                    break
                await server.wait(2)  # update ~10x per second

        asyncio.ensure_future(_update())

class BlockDisplay:
    """Block display entity wrapper.

    Usage::

        display = BlockDisplay(location, "DIAMOND_BLOCK")
        display.teleport(new_location)
        display.remove()
    """

    def __init__(self, location: "Location", block_type: str,
                 billboard: str = "FIXED"):
        world: Any = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            world = World(name='world')

        self._entity: Any = world._call_sync(
            "spawnEntity", location, EntityType.from_name("BLOCK_DISPLAY"))
        self._entity._call("setBlock", block_type)
        self._entity._call("setBillboard", billboard)

    def teleport(self, location: "Location"):
        """Move the display to a new location."""
        self._entity.teleport(location)

    def remove(self):
        """Remove the display entity."""
        self._entity.remove()

    @property
    def billboard(self) -> str:
        return self._entity._call_sync("getBillboard")

    @billboard.setter
    def billboard(self, value: str):
        self._entity._call("setBillboard", value)

class ItemDisplay:
    """Item display entity wrapper.

    Usage::

        display = ItemDisplay(location, "DIAMOND_SWORD")
        display.teleport(new_location)
        display.remove()
    """

    def __init__(self, location: "Location", item: Any,
                 billboard: str = "FIXED"):
        world: Any = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            world = World(name='world')

        self._entity: Any = world._call_sync(
            "spawnEntity", location, EntityType.from_name("ITEM_DISPLAY"))

        if isinstance(item, str):
            item = Item(item)
        self._entity._call("setItemStack", item)
        self._entity._call("setBillboard", billboard)

    def teleport(self, location: "Location"):
        """Move the display to a new location."""
        self._entity.teleport(location)

    def remove(self):
        """Remove the display entity."""
        self._entity.remove()

    @property
    def billboard(self) -> str:
        return self._entity._call_sync("getBillboard")

    @billboard.setter
    def billboard(self, value: str):
        self._entity._call("setBillboard", value)

class ImageDisplay:
    """Render pixel art images in-world using one TextDisplay per pixel.

    This uses TextDisplay background color only (no glyph text) to avoid
    character spacing gaps and row spacing artifacts.
    """

    def __init__(self, location: "Location", image_path: str,
                 pixel_size: float = 1/16,
                 dual_sided: bool = False,
                 dual_side_mode: str = "mirror"):
        try:
            from PIL import Image  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError(
                "Pillow is required for ImageDisplay. Install with: pip install Pillow")

        img: Any = Image.open(image_path).convert("RGBA")
        width: int = int(img.size[0])
        height: int = int(img.size[1])
        pixels: Any = img.load()

        world: Any = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            world = World(name='world')

        self._entities: list[Any] = []
        self._placements: list[tuple[Any, float, float, float, float, float, float, float, float, float, float]] = []
        self._location = location
        self._pixel_size = pixel_size
        self._width = width
        self._height = height
        self._dual_sided = dual_sided

        yaw = float(getattr(location, 'yaw', 0.0))
        pitch = float(getattr(location, 'pitch', 0.0))
        pixel_scale = float(pixel_size) * 8
        pixel_step = pixel_scale / 8
        scale_x = pixel_scale
        scale_y = pixel_scale/2
        scale_z = max(pixel_scale * 0.08, 0.001)

        x_base_offset = pixel_step * 0.5
        y_base_offset = -1.0 * pixel_step
        dual_depth_shift = 0.01

        def _local_to_world_shift(local_x: float, local_y: float, entity_yaw: float, entity_pitch: float, local_z: float = 0.0) -> tuple[float, float, float]:
            yaw_rad = math.radians(entity_yaw)
            pitch_rad = math.radians(entity_pitch)

            fwd_x = -math.sin(yaw_rad) * math.cos(pitch_rad)
            fwd_y = -math.sin(pitch_rad)
            fwd_z = math.cos(yaw_rad) * math.cos(pitch_rad)

            right_x = fwd_z
            right_y = 0.0
            right_z = -fwd_x
            right_len = math.sqrt((right_x * right_x) + (right_y * right_y) + (right_z * right_z))
            if right_len <= 1e-9:
                right_x, right_y, right_z = 1.0, 0.0, 0.0
            else:
                inv = 1.0 / right_len
                right_x *= inv
                right_y *= inv
                right_z *= inv

            up_x = (fwd_y * right_z) - (fwd_z * right_y)
            up_y = (fwd_z * right_x) - (fwd_x * right_z)
            up_z = (fwd_x * right_y) - (fwd_y * right_x)

            return (
                (right_x * local_x) + (up_x * local_y) + (fwd_x * local_z),
                (right_y * local_x) + (up_y * local_y) + (fwd_y * local_z),
                (right_z * local_x) + (up_z * local_y) + (fwd_z * local_z),
            )

        payload: list[dict[str, Any]] = []
        placement_meta: list[tuple[float, float, float, float, float, float, float, float, float, float]] = []

        for row in range(height):
            for col in range(width):
                r, g, b, a = pixels[col, row]
                if a <= 0:
                    continue

                argb = (int(a) << 24) | (int(r) << 16) | (int(g) << 8) | int(b)
                x_offset = x_base_offset + (float(col) * pixel_step)
                y_offset = y_base_offset - (float(row) * pixel_step)
                z_offset = 0.0
                base_z_shift = 0.0
                base_x_shift, base_y_shift, base_xy_z_shift = _local_to_world_shift(x_offset, y_offset, yaw, pitch)

                payload.append({
                    "xOffset": 0.0,
                    "yOffset": 0.0,
                    "zOffset": z_offset,
                    "baseXShift": base_x_shift,
                    "baseYShift": base_y_shift,
                    "baseZShift": base_z_shift + base_xy_z_shift,
                    "yaw": yaw,
                    "pitch": pitch,
                    "argb": int(argb),
                    "lineWidth": 1,
                    "scaleX": scale_x,
                    "scaleY": scale_y,
                    "scaleZ": scale_z,
                })
                placement_meta.append((base_x_shift, base_y_shift, base_z_shift + base_xy_z_shift, z_offset, yaw, pitch, scale_x, scale_y, scale_z, 0.0))

                if dual_sided:
                    back_yaw = yaw + 180.0
                    back_x_offset = -x_offset
                    back_base_x_shift, back_base_y_shift, back_base_z_shift = _local_to_world_shift(back_x_offset, y_offset, back_yaw, pitch, -dual_depth_shift)

                    payload.append({
                        "xOffset": 0.0,
                        "yOffset": 0.0,
                        "zOffset": dual_depth_shift,
                        "baseXShift": back_base_x_shift,
                        "baseYShift": back_base_y_shift,
                        "baseZShift": back_base_z_shift,
                        "yaw": back_yaw,
                        "pitch": pitch,
                        "argb": int(argb),
                        "lineWidth": 1,
                        "scaleX": scale_x,
                        "scaleY": scale_y,
                        "scaleZ": scale_z,
                    })
                    placement_meta.append((back_base_x_shift, back_base_y_shift, back_base_z_shift, dual_depth_shift, back_yaw, pitch, scale_x, scale_y, scale_z, 0.0))

        spawned = world._call_sync("spawnImagePixels", location, payload)
        spawned_list = spawned if isinstance(spawned, list) else []

        for entity, meta in zip(spawned_list, placement_meta):
            base_x_shift, base_y_shift, base_z_shift, z_offset, entity_yaw, entity_pitch, sx, sy, sz, xy_zero = meta
            self._entities.append(entity)
            self._placements.append((entity, base_x_shift, base_y_shift, base_z_shift, z_offset, entity_yaw, entity_pitch, sx, sy, sz, xy_zero))

    def teleport(self, location: "Location"):
        """Move all pixel entities to a new base location."""
        alive_placements: list[tuple[Any, float, float, float, float, float, float, float, float, float, float]] = []
        for entity, base_x_shift, base_y_shift, base_z_shift, z_offset, yaw, pitch, sx, sy, sz, xy_zero in self._placements:
            try:
                loc = Location(
                    x=location.x + float(base_x_shift),
                    y=location.y + float(base_y_shift),
                    z=location.z + float(base_z_shift),
                    world=location.world,
                    yaw=yaw,
                    pitch=pitch,
                )
                entity.teleport(loc)
                entity._call_sync("setRotation", float(yaw), float(pitch))
                entity._call_sync("setTransform", float(xy_zero), float(xy_zero), float(z_offset),
                                  float(sx), float(sy), float(sz))
                alive_placements.append((entity, base_x_shift, base_y_shift, base_z_shift, z_offset, yaw, pitch, sx, sy, sz, xy_zero))
            except EntityGoneException:
                pass

        self._placements = alive_placements
        self._entities = [entry[0] for entry in alive_placements]
        self._location = location

    def remove(self):
        """Remove all spawned pixel entities."""
        for entity in self._entities:
            try:
                entity.remove()
            except EntityGoneException:
                pass
        self._entities.clear()
        self._placements.clear()

class Menu:
    """Interactive chest GUI menu with click handlers.

    Usage::

        menu = Menu("Shop", rows=3)
        menu[13] = MenuItem("diamond_sword", on_click=buy_sword)
        menu[13] = MenuItem(Item("diamond"), on_click=buy_diamond)
        menu.fill_border(Item("black_stained_glass_pane"))
        menu.open(player)
    """

    def __init__(self, title: str = "", rows: int = 3):
        self._title = title
        self._rows = max(1, min(6, rows))
        self._items: Dict[int, MenuItem] = {}

    def __setitem__(self, slot: int, menu_item: MenuItem):
        if slot < 0 or slot >= self._rows * 9:
            raise IndexError(f"Slot {slot} out of range (0-{self._rows * 9 - 1})")
        self._items[slot] = menu_item

    def __getitem__(self, slot: int) -> Optional[MenuItem]:
        return self._items.get(slot)

    def __delitem__(self, slot: int):
        self._items.pop(slot, None)

    def fill_border(self, item: "Item"):
        """Fill the border slots with the given item (no click handler)."""
        size = self._rows * 9
        for slot in range(size):
            row, col = divmod(slot, 9)
            if row == 0 or row == self._rows - 1 or col == 0 or col == 8:
                if slot not in self._items:
                    self._items[slot] = MenuItem(item)

    def open(self, player: "Player"):
        """Open this menu for a player."""
        _register_menu_events()
        inv = Inventory(size=self._rows * 9, title=self._title)
        for slot, menu_item in self._items.items():
            inv.set_item(slot, menu_item.item)
        p_uuid = str(player.uuid)
        _open_menus[p_uuid] = self
        inv.open(player)

    @property
    def title(self) -> str:
        return self._title

    @property
    def rows(self) -> int:
        return self._rows

@dataclass
class MenuItem:
    """An item in a Menu with an optional click callback.

    Args:
        item: An Item instance, or a material name string (e.g. ``"diamond_sword"``).
        on_click: Optional callback ``(player, event) -> None`` called when clicked.
    """
    item: Any  # Item | str
    on_click: Optional[Callable[..., Any]] = None

    def __post_init__(self):
        if isinstance(self.item, str):
            self.item = Item(self.item)

# Global menu tracking
_open_menus: Dict[str, "Menu"] = {}
_menu_events_registered = False

def _register_menu_events():
    global _menu_events_registered
    if _menu_events_registered:
        return
    _menu_events_registered = True

    async def _on_inventory_click(event: Event):
        player = event.fields.get("player")
        if player is None:
            return
        player_uuid = player.fields.get("uuid") if hasattr(player, "fields") else None
        if player_uuid is None:
            return
        menu = _open_menus.get(player_uuid)
        if menu is None:
            return
        event.cancel()
        slot = event.fields.get("slot")
        if slot is not None and 0 <= slot < menu.rows * 9:
            menu_item = menu[slot]
            if menu_item is not None and menu_item.on_click is not None:
                p = Player(fields=player.fields) if hasattr(player, "fields") else player
                try:
                    result = menu_item.on_click(p, event)
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    print(f"[PyJavaBridge] Menu click handler error: {e}")

    async def _on_inventory_close(event: Event):
        player = event.fields.get("player")
        if player is None:
            return
        player_uuid = player.fields.get("uuid") if hasattr(player, "fields") else None
        if player_uuid is None:
            return
        _open_menus.pop(player_uuid, None)

    _connection.on("inventory_click", _on_inventory_click)
    _connection.subscribe("inventory_click", False)
    _connection.on("inventory_close", _on_inventory_close)
    _connection.subscribe("inventory_close", False)

# User util funcs
async def raycast(
    world: World,
    start: Vector|tuple[float,float,float],
    direction: tuple[float,float],
    max_distance: float = 64.0,
    ray_size: float = 0.2,
    include_entities: bool = True,
    include_blocks: bool = True,
    ignore_passable: bool = True,
):
    """Raycast helper returning RaycastResult or None."""
    if isinstance(world, str):
        world = await server.world(world)

    if isinstance(start, (list, tuple)):
        start_xyz = [float(start[0]), float(start[1]), float(start[2])]
    else:
        start_xyz = [float(start.x), float(start.y), float(start.z)]

    yaw, pitch = direction

    result = await _connection.call(
        target="raycast",
        method="trace",
        args=[
            world,
            start_xyz[0],
            start_xyz[1],
            start_xyz[2],
            yaw,
            pitch,
            float(max_distance),
            float(ray_size),
            bool(include_entities),
            bool(include_blocks),
            bool(ignore_passable),
        ]
    )
    if result is None:
        return None

    getter: Callable[..., Any]
    if isinstance(result, dict):
        getter = cast(Dict[str, Any], result).get
    else:
        getter = lambda key, default=None: getattr(result, key, default)  # type: ignore[reportUnknownLambdaType]

    return RaycastResult(
        x=float(getter("x", 0)),
        y=float(getter("y", 0)),
        z=float(getter("z", 0)),
        entity=getter("entity"),
        block=getter("block"),
        start_x=float(getter("startX", 0)),
        start_y=float(getter("startY", 0)),
        start_z=float(getter("startZ", 0)),
        yaw=float(getter("yaw", 0)),
        pitch=float(getter("pitch", 0)),
        distance=float(getter("distance", 0)),
        hit_face=getter("hit_face"),
    )

_connection: Optional[BridgeConnection] = None
_player_uuid_cache: Dict[str, str] = {}

# Utils
def _extract_xyz(pos:Vector | list[float] | tuple[float,float,float] | SimpleNamespace) -> tuple[float,float,float]:
    """Extract (x, y, z) from a Location, Vector, tuple, list, or namespace."""
    if isinstance(pos, (list, tuple)) and len(pos) >= 3:
        return float(pos[0]), float(pos[1]), float(pos[2])

    if hasattr(pos, "x") and hasattr(pos, "y") and hasattr(pos, "z"):
        return float(pos.x), float(pos.y), float(pos.z) # type: ignore

    raise BridgeError(f"Cannot extract (x, y, z) from {type(pos).__name__}")

def _enum_from(type_name: str, name: str) -> EnumValue:
    mapping: Dict[str, type[EnumValue]] = {
        "org.bukkit.Material": Material,
        "org.bukkit.block.Biome": Biome,
        "org.bukkit.GameMode": GameMode,
        "org.bukkit.Sound": Sound,
        "org.bukkit.Particle": Particle,
        "org.bukkit.Difficulty": Difficulty,
        "org.bukkit.attribute.Attribute": AttributeType,
        "org.bukkit.boss.BarColor": BarColor,
        "org.bukkit.boss.BarStyle": BarStyle,
        "org.bukkit.entity.EntityType": EntityType,
        "org.bukkit.potion.PotionEffectType": EffectType,
    }
    enum_cls = mapping.get(type_name, EnumValue)
    return enum_cls(type_name, name)

def _proxy_from(raw: Dict[str, Any]) -> ProxyBase:
    type_name: Optional[str] = raw.get("__type__")
    raw_fields: Any = raw.get("fields") or {}
    fields: Dict[str, Any] = {str(k): _connection._deserialize(v) for k, v in raw_fields.items()}  # type: ignore[reportPrivateUsage]
    handle: Optional[int] = raw.get("__handle__")
    if type_name == "Player":
        name = fields.get("name")
        player_uuid = fields.get("uuid")
        if isinstance(name, str):
            if isinstance(player_uuid, uuid.UUID):
                _player_uuid_cache[name] = str(player_uuid)
            elif isinstance(player_uuid, str):
                _player_uuid_cache[name] = player_uuid
    proxy_map: Dict[str, type[ProxyBase]] = {
        "Server": Server,
        "Player": Player,
        "Entity": Entity,
        "World": World,
        "WorldImpl": World,
        "Dimension": Dimension,
        "Location": Location,
        "Block": Block,
        "Chunk": Chunk,
        "Vector": Vector,
        "Inventory": Inventory,
        "ItemStack": Item,
        "PotionEffect": Effect,
        "BossBar": BossBar,
        "Scoreboard": Scoreboard,
        "Team": Team,
        "Objective": Objective,
        "Advancement": Advancement,
        "AdvancementProgress": AdvancementProgress,
        "AttributeInstance": Attribute,
        "Attribute": Attribute,
        "Event": Event,
    }
    if type_name and type_name.endswith("Event"):
        proxy_cls = Event
    else:
        proxy_cls = proxy_map.get(type_name or "", ProxyBase)
        if proxy_cls is ProxyBase and type_name:
            if type_name.endswith("Player"):
                proxy_cls = Player
            elif type_name.endswith("Entity"):
                proxy_cls = Entity
            elif type_name.endswith("World"):
                proxy_cls = World
            elif type_name.endswith("Location"):
                proxy_cls = Location
            elif type_name.endswith("Block"):
                proxy_cls = Block
            elif type_name.endswith("Chunk"):
                proxy_cls = Chunk
            elif "Inventory" in type_name:
                proxy_cls = Inventory
            elif "ItemStack" in type_name:
                proxy_cls = Item
            elif "PotionEffect" in type_name:
                proxy_cls = Effect
    return proxy_cls(handle=handle, type_name=type_name, fields=fields)

def _command_signature_params(sig: inspect.Signature):
    params = list(sig.parameters.values())
    positional_params: List[inspect.Parameter] = []
    keyword_only_names: List[str] = []
    has_varargs = False
    has_varkw = False
    for index, param in enumerate(params):
        if index == 0:
            continue
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            positional_params.append(param)
        elif param.kind is inspect.Parameter.KEYWORD_ONLY:
            keyword_only_names.append(param.name)
        elif param.kind is inspect.Parameter.VAR_POSITIONAL:
            has_varargs = True
        elif param.kind is inspect.Parameter.VAR_KEYWORD:
            has_varkw = True
    return positional_params, keyword_only_names, has_varargs, has_varkw

def _parse_command_tokens(raw_args: List[str], positional_params: List[inspect.Parameter], keyword_only_names: List[str], has_varargs: bool, has_varkw: bool):
    allowed_kw_names = {p.name for p in positional_params} | set(keyword_only_names)
    positional_tokens: List[str] = []
    kwargs: Dict[str, str] = {}
    index = 0
    while index < len(raw_args):
        token = str(raw_args[index])
        if ":" in token:
            key, value_part = token.split(":", 1)
            if key.isidentifier() and (has_varkw or key in allowed_kw_names):
                value_tokens = [value_part] if value_part else []
                index += 1
                while index < len(raw_args):
                    next_token = str(raw_args[index])
                    if ":" in next_token:
                        next_key = next_token.split(":", 1)[0]
                        if next_key.isidentifier() and (has_varkw or next_key in allowed_kw_names):
                            break
                    value_tokens.append(next_token)
                    index += 1
                kwargs[key] = " ".join(value_tokens).strip()
                continue
        positional_tokens.append(token)
        index += 1

    pos_args: List[str] = []
    var_args: List[str] = []
    if positional_params:
        if has_varargs:
            count = min(len(positional_params), len(positional_tokens))
            for i in range(count):
                pos_args.append(positional_tokens[i])
            if len(positional_tokens) > len(positional_params):
                var_args = positional_tokens[len(positional_params):]
        else:
            count = min(len(positional_params), len(positional_tokens))
            if count > 0:
                for i in range(count - 1):
                    pos_args.append(positional_tokens[i])
                pos_args.append(" ".join(positional_tokens[count - 1:]).strip())
    elif has_varargs:
        var_args = positional_tokens
    return pos_args, var_args, kwargs, positional_tokens, allowed_kw_names

def _toml_dumps(data: Dict[str, Any]) -> str:
    """Dump a dict to TOML format string."""
    lines: List[str] = []
    _toml_write_table(data, [], lines)
    return "\n".join(lines) + "\n"


def _toml_write_table(data: Dict[str, Any], path: List[str], lines: List[str]):
    """Recursively write a TOML table, emitting simple keys first, then sub-tables."""
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            continue
        lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            sub_path = path + [key]
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"[{'.'.join(_toml_key(p) for p in sub_path)}]")
            _toml_write_table(cast(Dict[str, Any], value), sub_path, lines)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            sub_path = path + [key]
            for item in cast(List[Dict[str, Any]], value):
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"[[{'.'.join(_toml_key(p) for p in sub_path)}]]")
                _toml_write_table(item, sub_path, lines)


def _toml_key(key: str) -> str:
    """Return a bare TOML key if safe, otherwise a quoted key."""
    if key and all(c.isalnum() or c in "-_" for c in key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_value(value: Any) -> str:
    """Encode a Python value as a TOML value string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        return f'"{escaped}"'
    if isinstance(value, list):
        items = [_toml_value(v) for v in cast(List[Any], value) if v is not None]
        return f"[{', '.join(items)}]"
    if isinstance(value, dict):
        items = [f"{_toml_key(k)} = {_toml_value(v)}" for k, v in cast(Dict[str, Any], value).items() if v is not None]
        return "{" + ", ".join(items) + "}"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _properties_load(path: str) -> Dict[str, Any]:
    """Load a Java-style .properties file into a nested dict."""
    data: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            sep = -1
            for i, ch in enumerate(line):
                if ch == "\\" :
                    continue
                if ch in ("=", ":"):
                    sep = i
                    break
            if sep < 0:
                continue
            key = line[:sep].rstrip()
            val_str = line[sep + 1:].lstrip()
            _properties_set_nested(data, key, _properties_parse_value(val_str))
    return data


def _properties_set_nested(data: Dict[str, Any], key: str, value: Any):
    """Set a dot-separated key path in a nested dict."""
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = cast(Dict[str, Any], node[part])
    node[parts[-1]] = value


def _properties_parse_value(value: str) -> Any:
    """Parse a properties value string into an appropriate Python type."""
    if not value:
        return ""
    if value in ("true", "True", "TRUE"):
        return True
    if value in ("false", "False", "FALSE"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _properties_dumps(data: Dict[str, Any]) -> str:
    """Dump a nested dict to .properties format with dot-separated keys."""
    lines: List[str] = []
    _properties_flatten(data, [], lines)
    return "\n".join(lines) + "\n"


def _properties_flatten(data: Dict[str, Any], path: List[str], lines: List[str]):
    """Flatten a nested dict into dot-separated key=value lines."""
    for key, value in data.items():
        full_path = path + [key]
        if value is None:
            continue
        if isinstance(value, dict):
            _properties_flatten(cast(Dict[str, Any], value), full_path, lines)
        elif isinstance(value, bool):
            lines.append(f"{'.'.join(full_path)}={'true' if value else 'false'}")
        elif isinstance(value, list):
            serialized = ",".join(str(v) for v in cast(List[Any], value))
            lines.append(f"{'.'.join(full_path)}={serialized}")
        else:
            lines.append(f"{'.'.join(full_path)}={value}")

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]):
    """Recursively merge override into base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)  # type: ignore[reportUnknownArgumentType]
        else:
            base[key] = value

async def _prime_player_cache():
    try:
        players: Any = server.players
        if isinstance(players, list):
            for player in cast(List[Any], players):
                if isinstance(player, Player):
                    name = player.fields.get("name")
                    player_uuid = player.fields.get("uuid")
                    if isinstance(name, str):
                        if isinstance(player_uuid, uuid.UUID):
                            _player_uuid_cache[name] = str(player_uuid)
                        elif isinstance(player_uuid, str):
                            _player_uuid_cache[name] = player_uuid
    except Exception:
        pass

# Decorators
def event(func: Optional[Callable[[Event], Any]] = None, *, once_per_tick: bool = False, priority: str = "NORMAL", throttle_ms: int = 0):
    """
    Register an async event handler.

    The handler name is mapped to a Bukkit/Paper event class using snake_case
    (e.g., player_join -> PlayerJoinEvent). Events are registered on demand.

    Supported events:
    - Any Bukkit/Paper event class reachable in the standard event packages.
    - Common examples: server_boot, player_join, block_break, block_place,
      block_explode, entity_explode, player_move, player_quit, player_chat,
      player_interact, inventory_click, inventory_close, entity_damage,
      entity_death, world_load, world_unload, weather_change.

    Args:
        once_per_tick: If true, the handler is throttled to once per tick.
        priority: Bukkit EventPriority (LOWEST, LOW, NORMAL, HIGH, HIGHEST, MONITOR).
        throttle_ms: Minimum milliseconds between event dispatches (0 = no throttle).
    """
    def decorator(handler: Callable[[Event], Any]):
        event_name = handler.__name__
        _connection.on(event_name, handler)
        _connection.subscribe(event_name, once_per_tick, priority, throttle_ms)
        return handler

    if func is None:
        return decorator

    return decorator(func)

def task(func: Optional[Callable[[], Any]] = None, *, interval: int = 20, delay: int = 0):
    """
    Register a repeating async task.

    The decorated function is called repeatedly with a fixed tick interval.
    Use server.wait() internally for tick-accurate delays.

    Args:
        interval: Ticks between each call (default 20 = 1 second).
        delay: Ticks to wait before the first call (default 0).

    Usage:
        @task(interval=20)
        async def my_loop():
            # runs every second
            ...

        @task  # defaults: interval=20, delay=0
        async def heartbeat():
            ...
    """
    def decorator(handler: Callable[[], Any]):
        async def _loop():
            try:
                if delay > 0:
                    await server.wait(delay)
                while _connection is not None and _connection._thread.is_alive():
                    try:
                        result = handler()
                        if hasattr(result, "__await__"):
                            await result
                    except Exception as e:
                        print(f"[PyJavaBridge] Task {handler.__name__} error: {e}")
                    await server.wait(interval)
            except Exception:
                pass

        _connection.on("server_boot", lambda _: asyncio.ensure_future(_loop()))
        return handler

    if func is None:
        return decorator

    return decorator(func)

def command(description: Optional[str] = None, *, name: Optional[str] = None, permission: Optional[str] = None):
    """
    Register a command handler.

    The handler name is registered as a server command unless a custom
    command name is provided via name=.

    The first decorator argument is a description string.

    The handler receives an event-like object with:
    - event: the CommandSender
    - label: the invoked command label
    - args: list of arguments

    Example:
```
@command("Greet a player")
async def greet(event: Event, name: str):
    event.player.send_message(f"Hello, {name}!")
```
    """
    def decorator(handler: Any) -> Any:
        sig = inspect.signature(handler)
        positional_params, keyword_only_names, has_varargs, has_varkw = _command_signature_params(sig)

        def _format_type(annotation: Any) -> str:
            if annotation is inspect.Parameter.empty:
                return "str"
            if isinstance(annotation, str):
                return annotation
            name = getattr(annotation, "__name__", None)
            if name:
                return name
            text = str(annotation)
            if text.startswith("typing."):
                return text.replace("typing.", "")
            return text

        def _usage_text(command_name: str) -> str:
            parts: List[str] = []
            for param in positional_params:
                type_name = _format_type(param.annotation)
                token = f"<{param.name}: {type_name}>"
                if param.default is not inspect.Parameter.empty:
                    token = f"[{token}]"
                parts.append(token)
            if has_varargs:
                parts.append("[<args...>]" )
            if has_varkw:
                parts.append("[<key:value...>]" )
            args_text = " ".join(parts)
            return f"Usage: /{command_name}" + (f" {args_text}" if args_text else "")

        _allowed_kw_names = {p.name for p in positional_params} | set(keyword_only_names)

        command_name = (name or handler.__name__).lower()

        @wraps(handler)
        async def wrapper(event_obj: Any) -> None:
            if isinstance(event_obj, ProxyBase):
                player = event_obj.fields.get("player")
                sender_obj = event_obj.fields.get("sender")
                if player is None and sender_obj is not None and not isinstance(sender_obj, Player):
                    event_obj.fields["player"] = _ConsolePlayer(sender_obj)
            elif isinstance(event_obj, dict):
                evt = cast(Dict[str, Any], event_obj)
                player: Any = evt.get("player")
                sender_obj: Any = evt.get("sender")
                if player is None and sender_obj is not None and not isinstance(sender_obj, Player):
                    evt["player"] = _ConsolePlayer(sender_obj)

            raw_args: List[str] = []
            if isinstance(event_obj, ProxyBase):
                raw_args = event_obj.fields.get("args", []) or []
            elif isinstance(event_obj, dict):
                raw_args = list(cast(Dict[str, Any], event_obj).get("args", []) or [])

            pos_args, var_args, kwargs, positional_tokens, allowed_kw_names = _parse_command_tokens(
                raw_args,
                positional_params,
                keyword_only_names,
                has_varargs,
                has_varkw,
            )

            if not has_varkw:
                kwargs = {k: v for k, v in kwargs.items() if k in allowed_kw_names}

            used_names = {p.name for p in positional_params[:len(pos_args)]}
            for key in list(kwargs.keys()):
                if key in used_names:
                    kwargs.pop(key)

            if positional_tokens and not positional_params and not has_varargs:
                target: Any = None
                if isinstance(event_obj, ProxyBase):
                    target = event_obj.fields.get("player") or event_obj.fields.get("sender")
                elif isinstance(event_obj, dict):
                    evt = cast(Dict[str, Any], event_obj)
                    target = evt.get("player") or evt.get("sender")
                usage = _usage_text(command_name)
                if target is not None:
                    try:
                        result = target.send_message(usage)
                        if hasattr(result, "__await__"):
                            await result
                    except Exception:
                        pass
                else:
                    print(f"[PyJavaBridge] {usage}")
                return None

            try:
                sig.bind(event_obj, *pos_args, *var_args, **kwargs)
            except TypeError:
                target = None
                if isinstance(event_obj, ProxyBase):
                    target = event_obj.fields.get("player") or event_obj.fields.get("sender")
                elif isinstance(event_obj, dict):
                    evt = cast(Dict[str, Any], event_obj)
                    target = evt.get("player") or evt.get("sender")
                usage = _usage_text(command_name)
                if target is not None:
                    try:
                        result = target.send_message(usage)
                        if hasattr(result, "__await__"):
                            await result
                    except Exception:
                        pass
                else:
                    print(f"[PyJavaBridge] {usage}")
                return None

            return await handler(event_obj, *pos_args, *var_args, **kwargs)
        event_name = f"command_{command_name}"
        _connection.on(event_name, wrapper)
        _connection.register_command(command_name, permission=permission)
        setattr(wrapper, "__command_args__", [p.name for p in positional_params])
        setattr(wrapper, "__command_desc__", description)
        return wrapper

    return decorator

server = Server(target="server")
chat = ChatFacade(target="chat")
reflect = ReflectFacade(target="reflect")

def _bootstrap(script_path: str): # type: ignore
    global _connection
    port = int(os.environ.get("PYJAVABRIDGE_PORT", "0"))
    if port == 0:
        raise RuntimeError("PYJAVABRIDGE_PORT is not set")
    _connection = BridgeConnection("127.0.0.1", port)
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_prime_player_cache())
    except Exception:
        pass
    print(f"[PyJavaBridge] Bootstrapping script {script_path}")
    namespace = {
        "__file__": script_path,
        "__name__": "__main__",
    }
    runpy.run_path(script_path, init_globals=namespace)
    _connection.send({"type": "ready"})
    asyncio.get_event_loop().run_forever()


