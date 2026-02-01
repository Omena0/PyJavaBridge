from typing import Any, Awaitable, Callable, Dict, List, Optional
from dataclasses import dataclass
from types import SimpleNamespace
from functools import wraps
import inspect
import threading
import asyncio
import socket
import runpy
import uuid
import json
import os

__all__ = [
    "event",
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
    "Advancement",
    "AdvancementProgress",
    "Potion",
    "RaycastResult",
]


class BridgeError(Exception):
    """Bridge-specific runtime error."""
    pass

class EntityGoneException(BridgeError):
    """Raised when an entity/player is no longer available."""
    pass

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

@dataclass
class EnumValue:
    """Enum value proxy with class-level access (e.g., Material.DIAMOND)."""
    type: str
    name: str
    TYPE_NAME: str = ""

    def __str__(self) -> str:
        return self.name

    @classmethod
    def _from_name(cls, name: str) -> "EnumValue":
        return cls(cls.TYPE_NAME or cls.__name__, name)

    def __class_getattr__(cls, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return cls._from_name(name)

class BridgeCall(Awaitable):
    """Awaitable wrapper for async bridge calls."""
    def __init__(self, future: asyncio.Future):
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

    def __call__(self, *args, **kwargs):
        return self._proxy._call(self._name, *args, **kwargs)

class _SyncWait:
    def __init__(self):
        self.event = threading.Event()
        self.result: Any = None
        self.error: Optional[Exception] = None

class ProxyBase:
    """Base class for all proxy objects."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, ref_type: Optional[str] = None, ref_id: Optional[str] = None, **kwargs):
        if kwargs:
            if fields is None:
                fields = dict(kwargs)
            else:
                fields.update(kwargs)
        self._handle = handle
        self._type_name = type_name
        self._fields = fields or {}
        self._target = target
        self._ref_type = ref_type
        self._ref_id = ref_id

    def _call(self, method: str, *args, **kwargs):
        if self._handle is None and self._target == "ref":
            if kwargs:
                return _connection.call(method="call", args=[self._ref_type, self._ref_id, method, list(args), kwargs], target="ref")
            return _connection.call(method="call", args=[self._ref_type, self._ref_id, method, list(args)], target="ref")
        return _connection.call(method=method, args=list(args), handle=self._handle, target=self._target, **kwargs)

    def _call_sync(self, method: str, *args, **kwargs):
        if self._handle is None and self._target == "ref":
            if kwargs:
                return _connection.call_sync(method="call", args=[self._ref_type, self._ref_id, method, list(args), kwargs], target="ref")
            return _connection.call_sync(method="call", args=[self._ref_type, self._ref_id, method, list(args)], target="ref")
        return _connection.call_sync(method=method, args=list(args), handle=self._handle, target=self._target, **kwargs)

    def __getattr__(self, name: str):
        if name in self._fields:
            return self._fields[name]
        return BridgeMethod(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        if self._handle is None and self._target == "ref":
            _connection.call(method="setAttr", args=[self._ref_type, self._ref_id, name, value], target="ref")
            return
        _connection.call(method="set_attr", handle=self._handle, field=name, value=value)

    def _field_or_call(self, field: str, method: str):
        if field in self._fields:
            return self._fields[field]
        return self._call(method)

    def _field_or_call_sync(self, field: str, method: str):
        if field in self._fields:
            return self._fields[field]
        return self._call_sync(method)

class Event(ProxyBase):
    """Base event proxy."""
    def cancel(self):
        """Cancel the event if it is cancellable."""
        event_id = self._fields.get("__event_id__")
        if event_id is not None:
            _connection.send({"type": "event_cancel", "id": event_id})
            return _connection.completed_call(None)
        return self._call("setCancelled", True)

class Server(ProxyBase):
    """Server-level API."""
    def broadcast(self, message: str):
        """Broadcast a message to all players and console."""
        return self._call("broadcastMessage", message)

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
        """Batch calls into a single send."""
        return _connection.frame()

    def atomic(self):
        """Batch calls atomically (best-effort)."""
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
        return self._fields.get("name") or self._call_sync("getName")

    @property
    def version(self):
        return self._fields.get("version") or self._call_sync("getVersion")

    @property
    def motd(self):
        return self._call_sync("getMotd")

    @property
    def max_players(self):
        return self._call_sync("getMaxPlayers")

class Entity(ProxyBase):
    """Base entity proxy."""
    @classmethod
    def spawn(cls, entity_type: "EntityType" | str, location: "Location", **kwargs):
        """Spawn an entity at a location."""
        world = None
        if isinstance(location, Location):
            world = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            raise BridgeError("Location must have a world to spawn an entity")
        return world.spawn_entity(location, entity_type, **kwargs)

    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, uuid: Optional[str] = None, ref_type: Optional[str] = None, ref_id: Optional[str] = None):
        if handle is None and uuid is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="entity", ref_id=str(uuid))
            self._fields.setdefault("uuid", str(uuid))
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
        return self._field_or_call_sync("uuid","getUniqueId")

    @property
    def type(self):
        return self._field_or_call_sync("type", "getType")

    @property
    def location(self):
        return self._field_or_call_sync("location", "getLocation")

    @property
    def world(self):
        return self._field_or_call_sync("world", "getWorld")

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
                uuid_obj = uuid if isinstance(uuid, uuid_mod.UUID) else uuid and uuid_mod.UUID(str(uuid))
                if uuid_obj is not None:
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
            sound = Sound._from_name(sound.upper())
        return self._call("playSound", sound, volume, pitch)

    def send_action_bar(self, message: str):
        """Send an action bar message."""
        return self._call("sendActionBar", message)

    def send_title(self, title: str, subtitle: str = "", fade_in: int = 10, stay: int = 70, fade_out: int = 20):
        """Send a title/subtitle to the player."""
        return self._call("sendTitle", title, subtitle, fade_in, stay, fade_out)

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
        return self._field_or_call_sync("name", "getName")

    @property
    def uuid(self):
        if "uuid" in self._fields:
            return str(self._fields["uuid"])

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
                self._fields["uuid"] = result_text
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
        return self._field_or_call_sync("location", "getLocation")

    @property
    def world(self):
        return self._field_or_call_sync("world", "getWorld")

    @property
    def game_mode(self):
        return self._field_or_call_sync("gameMode", "getGameMode")

    @property
    def health(self):
        return self._field_or_call_sync("health", "getHealth")

    @property
    def food_level(self):
        return self._field_or_call_sync("foodLevel", "getFoodLevel")

    @property
    def inventory(self):
        if self._handle is None and self._target == "ref":
            ref_id = self._ref_id or self._fields.get("uuid") or self._fields.get("name")
            if ref_id:
                return Inventory(handle=None, target="ref", ref_type="player_inventory", ref_id=str(ref_id))

        return self._field_or_call_sync("inventory", "getInventory")

class EntityType(EnumValue):
    TYPE_NAME = "org.bukkit.entity.EntityType"
    
class World(ProxyBase):
    """World API."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, name: Optional[str] = None):
        if handle is None and name is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="world", ref_id=str(name))
            self._fields.setdefault("name", str(name))
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    def block_at(self, x: int, y: int, z: int):
        """Get a block at coordinates."""
        return self._call("getBlockAt", x, y, z)

    def spawn_entity(self, location: "Location", entity_type: EntityType, **kwargs):
        """Spawn an entity by type.

        Optional kwargs: velocity (Vector or [x,y,z]), facing (Vector or [x,y,z]),
        yaw, pitch, nbt (SNBT string).
        """
        if isinstance(entity_type, str):
            entity_type = EntityType._from_name(entity_type)
        try:
            return self._call("spawnEntity", location, entity_type, **kwargs)
        except BridgeError as exc:
            if "Method not found: spawnEntity" in str(exc):
                return self._call("spawn", location, entity_type, **kwargs)
            raise

    def chunk_at(self, x: int, z: int):
        """Get a chunk by coordinates."""
        return self._call("getChunkAt", x, z)

    def spawn(self, location: "Location", entity_cls: type, **kwargs):
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
        return self._field_or_call_sync("name", "getName")

    @property
    def uuid(self):
        return self._field_or_call_sync("uuid", "getUID")

    @property
    def environment(self):
        return self._field_or_call_sync("environment", "getEnvironment")

class Dimension(ProxyBase):
    def __init__(self, name: Optional[str] = None, **kwargs):
        if name is not None and "fields" not in kwargs and "handle" not in kwargs:
            fields = {"name": name}
            super().__init__(fields=fields)
        else:
            super().__init__(**kwargs)
    @property
    def name(self):
        return self._field_or_call_sync("name", "getName")

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
    def x(self):
        return self._field_or_call_sync("x", "getX")

    @property
    def y(self):
        return self._field_or_call_sync("y", "getY")

    @property
    def z(self):
        return self._field_or_call_sync("z", "getZ")

    @property
    def yaw(self):
        return self._field_or_call_sync("yaw", "getYaw")

    @property
    def pitch(self):
        return self._field_or_call_sync("pitch", "getPitch")

    @property
    def world(self):
        return self._field_or_call_sync("world", "getWorld")

    def add(self, x: float, y: float, z: float):
        """Add coordinates to this location."""
        if self._handle is None and self._fields:
            return Location(self.x + x, self.y + y, self.z + z, self.world, self.yaw, self.pitch)
        return self._call("add", x, y, z)

    def clone(self):
        """Clone this location."""
        if self._handle is None and self._fields:
            return Location(self.x, self.y, self.z, self.world, self.yaw, self.pitch)
        return self._call("clone")

    def distance(self, other: "Location"):
        """Distance to another location."""
        if self._handle is None and self._fields and isinstance(other, Location) and other._fields:
            dx = self.x - other.x
            dy = self.y - other.y
            dz = self.z - other.z
            return (dx * dx + dy * dy + dz * dz) ** 0.5
        return self._call("distance", other)

    def distance_squared(self, other: "Location"):
        """Squared distance to another location."""
        if self._handle is None and self._fields and isinstance(other, Location) and other._fields:
            dx = self.x - other.x
            dy = self.y - other.y
            dz = self.z - other.z
            return dx * dx + dy * dy + dz * dz
        return self._call("distanceSquared", other)

    def set_world(self, world: "World"):
        """Set the world reference."""
        return self._call("setWorld", world)

class Block(ProxyBase):
    """Block in the world."""
    @classmethod
    def create(cls, location: "Location", material: "Material" | str):
        """Create/set a block at the given location."""
        if not isinstance(location, Location):
            raise BridgeError("Block.create requires a Location")
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
                world_name = world._fields.get("name")
            else:
                world_name = world._fields.get("name") if isinstance(world, World) else None
            fields = {"x": int(x), "y": int(y), "z": int(z), "world": world}
            if material is not None:
                if isinstance(material, str):
                    material = Material._from_name(material.upper())
                fields["type"] = material
            ref_id = f"{world_name}:{int(x)}:{int(y)}:{int(z)}" if world_name is not None else None
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="block", ref_id=ref_id)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)
    def break_naturally(self):
        """Break the block naturally."""
        return self._call("breakNaturally")

    def set_type(self, material: "Material"):
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
        return self._field_or_call_sync("inventory", "getInventory")

    @property
    def x(self):
        return self._field_or_call_sync("x", "getX")

    @property
    def y(self):
        return self._field_or_call_sync("y", "getY")

    @property
    def z(self):
        return self._field_or_call_sync("z", "getZ")

    @property
    def location(self):
        return self._field_or_call_sync("location", "getLocation")

    @property
    def type(self):
        return self._field_or_call_sync("type", "getType")

    @property
    def world(self):
        return self._field_or_call_sync("world", "getWorld")

class Chunk(ProxyBase):
    """Chunk of a world (loadable/unloadable)."""
    def __init__(self, world: Optional[World | str] = None, x: Optional[int] = None, z: Optional[int] = None, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None and world is not None and x is not None and z is not None:
            if isinstance(world, str):
                world = World(name=world)
                world_name = world._fields.get("name")
            else:
                world_name = world._fields.get("name") if isinstance(world, World) else None
            fields = {"x": int(x), "z": int(z), "world": world}
            ref_id = f"{world_name}:{int(x)}:{int(z)}" if world_name is not None else None
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="chunk", ref_id=ref_id)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)
    @property
    def x(self):
        return self._field_or_call_sync("x", "getX")

    @property
    def z(self):
        return self._field_or_call_sync("z", "getZ")

    @property
    def world(self):
        return self._field_or_call_sync("world", "getWorld")

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
            contents = list(self._fields.get("contents") or [])
            size = int(self._fields.get("size") or len(contents) or 0)
            if size <= 0:
                size = len(contents) or 9
            while len(contents) < size:
                contents.append(None)
            for idx, slot in enumerate(contents):
                if slot is None:
                    contents[idx] = item
                    self._fields["contents"] = contents
                    return None
            contents.append(item)
            self._fields["contents"] = contents
            return None
        return self._call("addItem", item)

    def remove_item(self, item: "Item"):
        """Remove an item from the inventory."""
        if self._handle is None:
            contents = list(self._fields.get("contents") or [])
            for idx, slot in enumerate(contents):
                if slot == item:
                    contents[idx] = None
                    break
            self._fields["contents"] = contents
            return None
        return self._call("removeItem", item)

    def clear(self):
        """Clear inventory contents."""
        if self._handle is None:
            self._fields["contents"] = []
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
            contents = list(self._fields.get("contents") or [])
            size = int(self._fields.get("size") or len(contents) or 0)
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
            contents = list(self._fields.get("contents") or [])
            return contents[slot] if 0 <= slot < len(contents) else None
        return self._call("getItem", slot)

    def set_item(self, slot: int, item: "Item"):
        """Set item in a slot."""
        if self._handle is None:
            contents = list(self._fields.get("contents") or [])
            while len(contents) <= slot:
                contents.append(None)
            contents[slot] = item
            self._fields["contents"] = contents
            return None
        return self._call("setItem", slot, item)

    def contains(self, material: "Material", amount: int = 1):
        """Check if inventory contains a material."""
        if self._handle is None:
            contents = list(self._fields.get("contents") or [])
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
            return int(self._fields.get("size") or 0)
        return self._field_or_call_sync("size", "getSize")

    @property
    def contents(self):
        if self._handle is None:
            return self._fields.get("contents") or []
        return self._field_or_call_sync("contents", "getContents")

    @property
    def title(self):
        return self._field_or_call_sync("title", "getTitle")

    @property
    def holder(self):
        return self._field_or_call_sync("holder", "getHolder")

class Item(ProxyBase):
    """Item (ItemStack) API."""
    @classmethod
    def drop(cls, material: "Material" | str, location: "Location", amount: int = 1, **kwargs):
        """Drop an item at a location."""
        if not isinstance(location, Location):
            raise BridgeError("Item.drop requires a Location")
        world = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            raise BridgeError("Location must have a world to drop an item")
        item = Item(material=material, amount=amount, **kwargs)
        return world._call("dropItem", location, item)

    @classmethod
    def give(cls, player: "Player", material: "Material" | str, amount: int = 1, **kwargs):
        """Give an item to a player's inventory."""
        item = Item(material=material, amount=amount, **kwargs)
        return player.inventory.add_item(item)

    def __init__(self, material: Optional[Material | str] = None, amount: int = 1, name: Optional[str] = None, lore: Optional[List[str]] = None, custom_model_data: Optional[int] = None, attributes: Optional[List[Dict[str, Any]]] = None, nbt: Optional[Dict[str, Any]] = None, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        if handle is None and fields is None and material is not None:
            if isinstance(material, str):
                material = Material._from_name(material.upper())
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
        return self._field_or_call_sync("type", "getType")

    @property
    def amount(self):
        return self._field_or_call_sync("amount", "getAmount")

    def set_amount(self, value: int):
        """Set item amount."""
        return self._call("setAmount", value)

    @property
    def name(self):
        return self._field_or_call_sync("name", "getName")

    def set_name(self, name: str):
        """Set display name."""
        if self._handle is None:
            self._fields["name"] = str(name)
            return self
        return self._call("setName", name)

    @property
    def lore(self):
        return self._field_or_call_sync("lore", "getLore")

    def set_lore(self, lore: List[str]):
        """Set lore lines."""
        if self._handle is None:
            self._fields["lore"] = list(lore)
            return self
        return self._call("setLore", lore)

    @property
    def custom_model_data(self):
        return self._field_or_call_sync("customModelData", "getCustomModelData")

    def set_custom_model_data(self, value: int):
        """Set custom model data."""
        if self._handle is None:
            self._fields["customModelData"] = int(value)
            return self
        return self._call("setCustomModelData", value)

    @property
    def attributes(self):
        return self._field_or_call_sync("attributes", "getAttributes")

    def set_attributes(self, attributes: List[Dict[str, Any]]):
        """Set attribute modifiers."""
        if self._handle is None:
            self._fields["attributes"] = list(attributes)
            return self
        return self._call("setAttributes", attributes)

    @property
    def nbt(self):
        return self._field_or_call_sync("nbt", "getNbt")

    def set_nbt(self, nbt: Dict[str, Any]):
        """Set NBT map."""
        if self._handle is None:
            self._fields["nbt"] = nbt
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
                effect_type = EffectType._from_name(effect_type.upper())
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
        if self._handle is None:
            return self._fields.get("type")
        return self._field_or_call_sync("type", "getType")

    @property
    def duration(self):
        if self._handle is None:
            return int(self._fields.get("duration") or 0)
        return self._field_or_call_sync("duration", "getDuration")

    @property
    def amplifier(self):
        if self._handle is None:
            return int(self._fields.get("amplifier") or 0)
        return self._field_or_call_sync("amplifier", "getAmplifier")

    @property
    def ambient(self):
        if self._handle is None:
            return bool(self._fields.get("ambient"))
        return self._field_or_call_sync("ambient", "isAmbient")

    @property
    def particles(self):
        if self._handle is None:
            return bool(self._fields.get("particles", True))
        return self._field_or_call_sync("particles", "hasParticles")

    @property
    def icon(self):
        if self._handle is None:
            return bool(self._fields.get("icon", True))
        return self._field_or_call_sync("icon", "hasIcon")

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
    def apply(cls, player: "Player", attribute_type: "AttributeType" | str, base_value: float):
        """Set a player's base attribute value."""
        if isinstance(attribute_type, str):
            attribute_type = AttributeType._from_name(attribute_type.upper())
        attr = player._call("getAttribute", attribute_type)
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
    def x(self):
        return self._field_or_call_sync("x", "getX")

    @property
    def y(self):
        return self._field_or_call_sync("y", "getY")

    @property
    def z(self):
        return self._field_or_call_sync("z", "getZ")

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
            color = BarColor._from_name("PINK")
        if style is None:
            style = BarStyle._from_name("SOLID")
        bar = server._call("createBossBar", title, color, style)
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
        manager = server._call("getScoreboardManager")
        return manager._call("getNewScoreboard")

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
            scoreboard = Scoreboard.create()
        return scoreboard.register_team(name)

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
            scoreboard = Scoreboard.create()
        return scoreboard.register_objective(name, criteria, display_name)

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

class _BatchContext:
    def __init__(self, connection: BridgeConnection, mode: str):
        self._connection = connection
        self._mode = mode

    async def __aenter__(self):
        self._connection._begin_batch(self._mode)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._connection._end_batch()
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
        self._pending: Dict[int, asyncio.Future] = {}
        self._pending_sync: Dict[int, _SyncWait] = {}
        self._handlers: Dict[str, List[Callable[[Any], Awaitable[None]]]] = {}
        self._id = 1
        self._socket = socket.create_connection((host, port))
        self._file = self._socket.makefile("rwb")
        self._lock = threading.Lock()
        self._batch_stack: List[str] = []
        self._batch_messages: List[Dict[str, Any]] = []
        self._batch_futures: List[asyncio.Future] = []
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        print(f"[PyJavaBridge] Connected to {host}:{port}")

    def subscribe(self, event_name: str, once_per_tick: bool):
        print(f"[PyJavaBridge] Subscribing to {event_name} once_per_tick={once_per_tick}")
        self.send({"type": "subscribe", "event": event_name, "once_per_tick": once_per_tick})

    def register_command(self, name: str):
        """Register a command name with the server."""
        self.send({"type": "register_command", "name": name})

    def on(self, event_name: str, handler: Callable[[Any], Awaitable[None]]):
        self._handlers.setdefault(event_name, []).append(handler)

    def call(self, method: str, args: Optional[List[Any]] = None, handle: Optional[int] = None, target: Optional[str] = None, **kwargs) -> BridgeCall:
        request_id = self._next_id()
        future = self._loop.create_future()
        self._pending[request_id] = future
        message = {
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

    def call_sync(self, method: str, args: Optional[List[Any]] = None, handle: Optional[int] = None, target: Optional[str] = None, **kwargs) -> Any:
        request_id = self._next_id()
        wait = _SyncWait()
        self._pending_sync[request_id] = wait
        message = {
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
        data = (json.dumps(message) + "\n").encode("utf-8")
        with self._lock:
            self._file.write(data)
            self._file.flush()

    def completed_call(self, result: Any):
        future = self._loop.create_future()
        future.set_result(result)
        return BridgeCall(future)

    def _reader(self):
        while True:
            line = self._file.readline()
            if not line:
                break
            try:
                message = json.loads(line.decode("utf-8"))
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

    def _handle_message(self, message: Dict[str, Any]):
        msg_type = message.get("type")
        if msg_type == "return":
            future = self._pending.pop(message.get("id"), None)
            if future is not None:
                future.set_result(self._deserialize(message.get("result")))
        elif msg_type == "error":
            future = self._pending.pop(message.get("id"), None)
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
                event_obj = payload.get("event")
                if isinstance(event_obj, ProxyBase):
                    if "id" in payload:
                        event_obj._fields["__event_id__"] = payload.get("id")
                    for key, value in payload.items():
                        if key != "event":
                            event_obj._fields[key] = value
                    payload = event_obj
            asyncio.create_task(self._dispatch_event(event_name, payload))
        elif msg_type == "event_batch":
            event_name = message.get("event")
            payloads = message.get("payloads", [])
            for payload in payloads:
                self._handle_message({"type": "event", "event": event_name, "payload": payload})

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
                event_id = payload._fields.get("__event_id__")
            if event_id is not None:
                if handlers:
                    override_text = None
                    override_damage = None
                    is_damage_event = isinstance(payload, ProxyBase) and "damage" in payload._fields
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

    def _handle_reader_error(self, exc: Exception):
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)

    def _next_id(self) -> int:
        self._id += 1
        return self._id - 1

    def _serialize(self, value: Any) -> Any:
        if isinstance(value, ProxyBase):
            if value._handle is not None:
                return {"__handle__": value._handle}
            if value._target == "ref" and value._ref_type and value._ref_id:
                return {"__ref__": {"type": value._ref_type, "id": value._ref_id}}
            return {"__value__": value.__class__.__name__, "fields": {k: self._serialize(v) for k, v in value._fields.items()}}
        if isinstance(value, EnumValue):
            return {"__enum__": value.type, "name": value.name}
        if isinstance(value, uuid.UUID):
            return {"__uuid__": str(value)}
        if isinstance(value, list):
            return [self._serialize(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize(v) for k, v in value.items()}
        return value

    def _deserialize(self, value: Any) -> Any:
        if isinstance(value, dict):
            if "__handle__" in value:
                return _proxy_from(value)
            if "__uuid__" in value:
                return uuid.UUID(value["__uuid__"])
            if "__enum__" in value:
                return _enum_from(value["__enum__"], value["name"])
            if {"x", "y", "z"}.issubset(value.keys()):
                return SimpleNamespace(**{k: self._deserialize(v) for k, v in value.items()})
            return {k: self._deserialize(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._deserialize(v) for v in value]
        return value

_connection: BridgeConnection
_player_uuid_cache: Dict[str, str] = {}

def _enum_from(type_name: str, name: str) -> EnumValue:
    mapping = {
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
    type_name = raw.get("__type__")
    fields = raw.get("fields") or {}
    fields = {k: _connection._deserialize(v) for k, v in fields.items()}
    handle = raw.get("__handle__")
    if type_name == "Player":
        name = fields.get("name")
        player_uuid = fields.get("uuid")
        if isinstance(name, str):
            if isinstance(player_uuid, uuid.UUID):
                _player_uuid_cache[name] = str(player_uuid)
            elif isinstance(player_uuid, str):
                _player_uuid_cache[name] = player_uuid
    proxy_map = {
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
        proxy_cls = proxy_map.get(type_name, ProxyBase)
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

def event(func: Optional[Callable] = None, *, once_per_tick: bool = False):
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
    """
    def decorator(handler):
        event_name = handler.__name__
        _connection.on(event_name, handler)
        _connection.subscribe(event_name, once_per_tick)
        return handler

    if func is None:
        return decorator
    return decorator(func)

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

def command(description: Optional[str] = None, *, name: Optional[str] = None):
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
    def decorator(handler):
        sig = inspect.signature(handler)
        positional_params, keyword_only_names, has_varargs, has_varkw = _command_signature_params(sig)

        def _format_type(annotation: Any) -> str:
            if annotation is inspect._empty:
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
                if param.default is not inspect._empty:
                    token = f"[{token}]"
                parts.append(token)
            if has_varargs:
                parts.append("[<args...>]" )
            if has_varkw:
                parts.append("[<key:value...>]" )
            args_text = " ".join(parts)
            return f"Usage: /{command_name}" + (f" {args_text}" if args_text else "")

        allowed_kw_names = {p.name for p in positional_params} | set(keyword_only_names)

        command_name = (name or handler.__name__).lower()

        class _ConsolePlayer:
            def __init__(self, sender_obj: Any):
                self._sender = sender_obj
                self._fields: Dict[str, Any] = {"name": "Console", "uuid": "console"}

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
                            handle=self._sender._handle,
                            target=self._sender._target,
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

        @wraps(handler)
        async def wrapper(event_obj):
            if isinstance(event_obj, ProxyBase):
                player = event_obj._fields.get("player")
                sender_obj = event_obj._fields.get("sender")
                if player is None and sender_obj is not None and not isinstance(sender_obj, Player):
                    event_obj._fields["player"] = _ConsolePlayer(sender_obj)
            elif isinstance(event_obj, dict):
                player = event_obj.get("player")
                sender_obj = event_obj.get("sender")
                if player is None and sender_obj is not None and not isinstance(sender_obj, Player):
                    event_obj["player"] = _ConsolePlayer(sender_obj)

            raw_args: List[str] = []
            if isinstance(event_obj, ProxyBase):
                raw_args = event_obj._fields.get("args", []) or []
            elif isinstance(event_obj, dict):
                raw_args = event_obj.get("args", []) or []

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
                target = None
                if isinstance(event_obj, ProxyBase):
                    target = event_obj._fields.get("player") or event_obj._fields.get("sender")
                elif isinstance(event_obj, dict):
                    target = event_obj.get("player") or event_obj.get("sender")
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
                    target = event_obj._fields.get("player") or event_obj._fields.get("sender")
                elif isinstance(event_obj, dict):
                    target = event_obj.get("player") or event_obj.get("sender")
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
        _connection.register_command(command_name)
        wrapper.__command_args__ = [p.name for p in positional_params]
        wrapper.__command_desc__ = description
        return wrapper

    return decorator

server = Server(target="server")
chat = ChatFacade(target="chat")
reflect = ReflectFacade(target="reflect")

async def _prime_player_cache():
    try:
        players = server.players
        if isinstance(players, list):
            for player in players:
                if isinstance(player, Player):
                    name = player._fields.get("name")
                    player_uuid = player._fields.get("uuid")
                    if isinstance(name, str):
                        if isinstance(player_uuid, uuid.UUID):
                            _player_uuid_cache[name] = str(player_uuid)
                        elif isinstance(player_uuid, str):
                            _player_uuid_cache[name] = player_uuid
    except Exception:
        pass

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

    if hasattr(start, "x") and hasattr(start, "y") and hasattr(start, "z"):
        start_xyz = [float(start.x), float(start.y), float(start.z)]

    else:
        start_xyz = list(start)

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

    if isinstance(result, dict):
        getter = result.get
    else:
        getter = lambda key, default=None: getattr(result, key, default)

    return RaycastResult(
        x=float(getter("x")),
        y=float(getter("y")),
        z=float(getter("z")),
        entity=getter("entity"),
        block=getter("block"),
        start_x=float(getter("startX")),
        start_y=float(getter("startY")),
        start_z=float(getter("startZ")),
        yaw=float(getter("yaw")),
        pitch=float(getter("pitch")),
    )

def _bootstrap(script_path: str):
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


