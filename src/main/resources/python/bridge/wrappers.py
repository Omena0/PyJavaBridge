"""Proxy wrappers — all ProxyBase subclasses that mirror Bukkit/Paper objects."""
from __future__ import annotations

import asyncio
import inspect
import sys
import uuid
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, cast

from bridge.errors import BridgeError, ConnectionError
from bridge.utils import _extract_xyz
from bridge.types import *
from bridge.connection import BridgeConnection

# Injected by bridge.__init__ during _bootstrap()
_connection:BridgeConnection = None  # type: ignore[assignment]
_player_uuid_cache: Dict[str, str] = {}

# Handle reference counting: track how many Python proxy objects share each Java handle.
# Only release a handle when the last proxy referencing it is garbage collected.
_handle_refcounts: Dict[int, int] = {}

def _handle_acquire(handle: Optional[int]) -> None:
    """Increment the reference count for a Java handle."""
    if handle is not None:
        old = _handle_refcounts.get(handle, 0)
        _handle_refcounts[handle] = old + 1
        if old == 0 and _connection is not None:
            try:
                _connection._cancel_release(handle)
            except Exception:
                pass

def _handle_release(handle: Optional[int]) -> None:
    """Decrement the reference count; queue a Java-side release when it hits zero."""
    if handle is None:
        return
    count = _handle_refcounts.get(handle, 0)
    if count <= 0:
        return
    if count == 1:
        _handle_refcounts.pop(handle, None)
        if _connection is not None:
            try:
                _connection._queue_release(handle)
            except Exception:
                pass
    else:
        _handle_refcounts[handle] = count - 1

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def print(*args):
    _print(*args, file=sys.stderr)

class ProxyBase:
    """Base class for all proxy objects."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, ref_type: Optional[str] = None, ref_id: Optional[str] = None, **kwargs: Any):
        if kwargs:
            if fields is None:
                fields = dict(kwargs)
            else:
                fields.update(kwargs)
        self._handle = handle
        _handle_acquire(handle)
        self._type_name = type_name
        self.fields = fields or {}
        self._target = target
        self._ref_type = ref_type
        self._ref_id = ref_id

    def __del__(self):
        handle = self.__dict__.get("_handle")
        _handle_release(handle)

    def _call(self, method: str, *args: Any, **kwargs: Any) -> BridgeCall:
        if _connection is None:
            raise ConnectionError("Bridge not connected")
        if self._handle is None and self._target == "ref":
            if kwargs:
                return _connection.call(method="call", args=[self._ref_type, self._ref_id, method, list(args), kwargs], target="ref")
            return _connection.call(method="call", args=[self._ref_type, self._ref_id, method, list(args)], target="ref")
        return _connection.call(method=method, args=list(args), handle=self._handle, target=self._target, **kwargs)

    def _call_sync(self, method: str, *args: Any, **kwargs: Any) -> Any:
        if _connection is None:
            raise ConnectionError("Bridge not connected")
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProxyBase):
            return NotImplemented
        # Compare by UUID if both have one (entities/players)
        s_uuid = self.fields.get("uuid")
        o_uuid = other.fields.get("uuid")
        if s_uuid is not None and o_uuid is not None:
            return s_uuid == o_uuid
        # Compare by handle if both have one
        if self._handle is not None and other._handle is not None:
            return self._handle == other._handle
        # Compare by ref identity
        if self._ref_type is not None and self._ref_type == other._ref_type:
            return self._ref_id == other._ref_id
        return self is other

    def __hash__(self) -> int:
        s_uuid = self.fields.get("uuid")
        if s_uuid is not None:
            return hash(s_uuid)
        if self._handle is not None:
            return hash(self._handle)
        return id(self)

class Event(ProxyBase):
    """Base event proxy."""
    def cancel(self):
        event_id = self.fields.get("__event_id__")
        if event_id is not None:
            _connection.send({"type": "event_cancel", "id": event_id})
            return _connection.completed_call(None)
        return self._call("setCancelled", True)

    @property
    def world(self):
        """World from fields, or derived from location/entity/player."""
        if "world" in self.fields:
            return self.fields["world"]
        loc = self.fields.get("location")
        if loc is not None and hasattr(loc, "world") and loc.world is not None:
            return loc.world
        entity = self.fields.get("entity") or self.fields.get("player")
        if entity is not None:
            return entity.world
        return BridgeMethod(self, "world")

    @property
    def location(self):
        """Location from fields, or derived from entity/player."""
        if "location" in self.fields:
            return self.fields["location"]
        entity = self.fields.get("entity") or self.fields.get("player")
        if entity is not None:
            return entity.location
        return BridgeMethod(self, "location")

class WorldTime:
    """Represents a Minecraft world time of day (0-24000 ticks).

    Well-known times:
        WorldTime.DAWN      = 0
        WorldTime.NOON      = 6000
        WorldTime.DUSK      = 12000
        WorldTime.MIDNIGHT  = 18000
    """
    DAWN: WorldTime | None = None
    NOON: WorldTime | None = None
    DUSK: WorldTime | None = None
    MIDNIGHT: WorldTime | None = None

    def __init__(self, ticks: int):
        self.ticks = ticks % 24000

    @classmethod
    def from_hours(cls, hours: float) -> WorldTime:
        mc_hours = (hours - 6.0) % 24.0
        return cls(int(mc_hours * 1000))

    @property
    def hours(self) -> float:
        return ((self.ticks / 1000.0) + 6.0) % 24.0

    @property
    def is_day(self) -> bool:
        return 0 <= self.ticks < 12000

    @property
    def is_night(self) -> bool:
        return self.ticks >= 12000

    def __eq__(self, other: object) -> bool:
        if isinstance(other, WorldTime):
            return self.ticks == other.ticks
        if isinstance(other, int):
            return self.ticks == other % 24000
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.ticks)

    def __int__(self) -> int:
        return self.ticks

    def __repr__(self) -> str:
        h = self.hours
        hh = int(h)
        mm = int((h - hh) * 60)
        return f"WorldTime(ticks={self.ticks}, {hh:02d}:{mm:02d})"

WorldTime.DAWN     = WorldTime(0)
WorldTime.NOON     = WorldTime(6000)
WorldTime.DUSK     = WorldTime(12000)
WorldTime.MIDNIGHT = WorldTime(18000)

_at_time_handlers: Dict[str, List[tuple]] = {}
_at_time_loop_started = False

def _start_at_time_loop():
    global _at_time_loop_started
    if _at_time_loop_started:
        return
    _at_time_loop_started = True

    async def _poll():
        prev_times: Dict[str, int] = {}
        while _connection is not None and _connection._thread.is_alive():
            try:
                for world_name, entries in list(_at_time_handlers.items()):
                    if not entries:
                        continue
                    w = World(name=world_name)
                    current = int(await w._call("getTime"))
                    current_day = current % 24000
                    prev = prev_times.get(world_name)
                    if prev is not None:
                        prev_day = prev % 24000
                        for target_ticks, handler in entries:
                            if prev_day <= target_ticks < current_day or (
                                current_day < prev_day and (target_ticks >= prev_day or target_ticks < current_day)
                            ):
                                try:
                                    result = handler(w)
                                    if inspect.isawaitable(result):
                                        await result
                                except Exception as exc:
                                    _print(f"[PyJavaBridge] at_time handler error: {exc}")
                    prev_times[world_name] = current
            except Exception:
                pass
            await _connection.wait(20)

    _connection.on("server_boot", lambda _: asyncio.ensure_future(_poll()))

class Server(ProxyBase):
    """Server-level API."""
    def broadcast(self, message: str):
        return self._call("broadcastMessage", message)

    def execute(self, command: str):
        return self._call("execute", command)

    @property
    def players(self):
        return self._call_sync("getOnlinePlayers")

    @property
    def worlds(self):
        return self._call_sync("getWorlds")

    def world(self, name: str):
        return self._call("getWorld", name)

    @property
    def scoreboard_manager(self):
        return self._call_sync("getScoreboardManager")

    def create_boss_bar(self, title: str, color: BarColor, style: BarStyle):
        return self._call("createBossBar", title, color, style)

    @property
    def boss_bars(self):
        return self._call_sync("getBossBars")

    def get_advancement(self, key: str):
        return self._call("getAdvancement", key)

    @property
    def plugin_manager(self):
        return self._call_sync("getPluginManager")

    @property
    def scheduler(self):
        return self._call_sync("getScheduler")

    @async_task
    async def after(self, ticks: int = 1, after: Optional[Callable[[], Any]] = None):
        await _connection.wait(ticks)
        if after is not None:
            result = after()
            if hasattr(result, "__await__"):
                await result
        return None

    def frame(self):
        return _connection.frame()

    def atomic(self):
        return _connection.atomic()

    @async_task
    async def flush(self):
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

# Per-entity tags keyed by UUID, shared across all instances of the same entity.
_entity_tags: Dict[str, set] = {}

class Entity(ProxyBase):
    """Base entity proxy."""
    @classmethod
    def spawn(cls, entity_type: EntityType | str, location: Location, **kwargs: Any):
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

    def teleport(self, location: Location):
        return self._call("teleport", location)

    def remove(self):
        return self._call("remove")

    def set_velocity(self, vector: Vector):
        return self._call("setVelocity", vector)

    @property
    def velocity(self):
        return self._call_sync("getVelocity")

    @property
    def is_dead(self):
        return self._call_sync("isDead")

    @property
    def is_alive(self):
        return not self.is_dead

    @property
    def is_valid(self):
        return self._call_sync("isValid")

    @property
    def fire_ticks(self):
        return self._call_sync("getFireTicks")

    def set_fire_ticks(self, ticks: int):
        return self._call("setFireTicks", ticks)

    def add_passenger(self, entity: Entity):
        return self._call("addPassenger", entity)

    def remove_passenger(self, entity: Entity):
        return self._call("removePassenger", entity)

    @property
    def passengers(self):
        return self._call_sync("getPassengers")

    @property
    def custom_name(self):
        return self._call_sync("getCustomName")

    def set_custom_name(self, name: str):
        return self._call("setCustomName", name)

    def set_custom_name_visible(self, value: bool):
        return self._call("setCustomNameVisible", value)

    @property
    def uuid(self):
        return self.fields.get("uuid")

    @property
    def type(self):
        return self.fields.get("type")

    @property
    def is_projectile(self):
        return self.fields.get("is_projectile", False)

    @property
    def shooter(self):
        return self.fields.get("shooter")

    @property
    def is_tamed(self):
        return self.fields.get("is_tamed", False)

    @property
    def owner(self):
        return self.fields.get("owner")

    @property
    def owner_uuid(self):
        return self.fields.get("owner_uuid")

    @property
    def owner_name(self):
        return self.fields.get("owner_name")

    @property
    def source(self):
        return self.fields.get("source")

    @property
    def location(self):
        return self._call_sync("getLocation")

    @property
    def yaw(self) -> float:
        loc = self.location
        return float(loc.yaw) if loc else 0.0

    @property
    def pitch(self) -> float:
        loc = self.location
        return float(loc.pitch) if loc else 0.0

    @property
    def look_direction(self) -> Vector:
        """Normalized direction vector from the entity's yaw and pitch."""
        import math
        loc = self.location
        yaw = math.radians(float(loc.yaw)) if loc else 0.0
        pitch = math.radians(float(loc.pitch)) if loc else 0.0
        x = -math.sin(yaw) * math.cos(pitch)
        y = -math.sin(pitch)
        z = math.cos(yaw) * math.cos(pitch)
        return Vector(x=x, y=y, z=z)

    @property
    def world(self):
        return self._call_sync("getWorld")

    @property
    def equipment(self):
        """The entity's equipment (armor, held items)."""
        return self._call_sync("getEquipment")

    @property
    def inventory(self):
        """Entity inventory — returns equipment for mobs, inventory for players."""
        return self._call_sync("getEquipment")

    @property
    def held_item(self):
        """The item in the entity's main hand (equipment slot)."""
        equipment = self.equipment
        if equipment is None:
            return None
        return equipment._call_sync("getItemInMainHand")

    @property
    def target(self):
        return self._call_sync("getTarget")

    def set_target(self, entity: Entity | None = None):
        return self._call("setTarget", entity)

    @property
    def is_aware(self):
        return self._call_sync("isAware")

    def set_aware(self, aware: bool):
        return self._call("setAware", aware)

    def pathfind_to(self, location: Location, speed: float = 1.0):
        return self._call_sync("pathfindTo", location, speed)

    def stop_pathfinding(self):
        return self._call("stopPathfinding")

    def has_line_of_sight(self, entity: Entity):
        return self._call_sync("hasLineOfSight", entity)

    def look_at(self, location: Location):
        return self._call("lookAt", location)

    def damage(self, amount: float):
        return self._call("damage", amount)

    def add_tag(self, tag: str):
        """Add a tag to this entity (shared across all instances with the same UUID)."""
        _entity_tags.setdefault(self.uuid, set()).add(tag)

    def remove_tag(self, tag: str):
        """Remove a tag from this entity."""
        tags = _entity_tags.get(self.uuid)
        if tags:
            tags.discard(tag)

    @property
    def tags(self) -> set:
        """All tags on this entity."""
        return set(_entity_tags.get(self.uuid, set()))

    def is_tagged(self, tag: str) -> bool:
        """Check if this entity has a tag."""
        tags = _entity_tags.get(self.uuid)
        return tag in tags if tags else False

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
        return self._call("sendMessage", message)

    def chat(self, message: str):
        return self._call("chat", message)

    def kick(self, reason: str = ""):
        return self._call("kick", reason)

    def teleport(self, location: Location):
        return self._call("teleport", location)

    def give_exp(self, amount: int):
        return self._call("giveExp", amount)

    def add_effect(self, effect: Effect):
        return self._call("addPotionEffect", effect)

    def remove_effect(self, effect_type: EffectType):
        return self._call("removePotionEffect", effect_type)

    @property
    def effects(self):
        return self._call_sync("getActivePotionEffects")

    def set_game_mode(self, mode: GameMode):
        return self._call("setGameMode", mode)

    @property
    def scoreboard(self):
        return self._call_sync("getScoreboard")

    def set_scoreboard(self, scoreboard: Scoreboard):
        return self._call("setScoreboard", scoreboard)

    def has_permission(self, permission: str):
        return self._call("hasPermission", permission)

    @property
    def is_op(self):
        return self._call_sync("isOp")

    def set_op(self, value: bool):
        return self._call("setOp", value)

    def add_permission(self, permission: str, value: bool = True):
        return _connection.call(method="addPermission", args=[self, permission, value], target="permissions")

    def remove_permission(self, permission: str):
        return _connection.call(method="removePermission", args=[self, permission], target="permissions")

    @property
    def permission_groups(self):
        return _connection.call_sync(method="groups", args=[self], target="permissions")

    @property
    def primary_group(self):
        return _connection.call_sync(method="primaryGroup", args=[self], target="permissions")

    def has_group(self, group: str):
        return _connection.call(method="hasGroup", args=[self, group], target="permissions")

    def add_group(self, group: str):
        return _connection.call(method="addGroup", args=[self, group], target="permissions")

    def remove_group(self, group: str):
        return _connection.call(method="removeGroup", args=[self, group], target="permissions")

    def play_sound(self, sound: Sound, volume: float = 1.0, pitch: float = 1.0):
        if isinstance(sound, str):
            sound = Sound.from_name(sound.upper())
        return self._call("playSound", sound, volume, pitch)

    def send_action_bar(self, message: str):
        return self._call("sendActionBar", message)

    def send_title(self, title: str, subtitle: str = "", fade_in: int = 10, stay: int = 70, fade_out: int = 20):
        return self._call("sendTitle", title, subtitle, fade_in, stay, fade_out)

    @property
    def tab_list_header(self):
        return self._call_sync("getTabListHeader")

    @property
    def tab_list_footer(self):
        return self._call_sync("getTabListFooter")

    def set_tab_list_header(self, header: str):
        return self._call("setTabListHeader", header)

    def set_tab_list_footer(self, footer: str):
        return self._call("setTabListFooter", footer)

    def set_tab_list_header_footer(self, header: str = "", footer: str = ""):
        return self._call("setTabListHeaderFooter", header, footer)

    @property
    def tab_list_name(self):
        return self._call_sync("getPlayerListName")

    def set_tab_list_name(self, name: str):
        return self._call("setPlayerListName", name)

    def set_health(self, health: float):
        return self._call("setHealth", health)

    def set_food_level(self, level: int):
        return self._call("setFoodLevel", level)

    @property
    def level(self):
        return self._call_sync("getLevel")

    def set_level(self, level: int):
        return self._call("setLevel", level)

    @property
    def exp(self):
        return self._call_sync("getExp")

    def set_exp(self, exp: float):
        return self._call("setExp", exp)

    @property
    def is_flying(self):
        return self._call_sync("isFlying")

    def set_flying(self, value: bool):
        return self._call("setFlying", value)

    @property
    def is_sneaking(self):
        return self._call_sync("isSneaking")

    def set_sneaking(self, value: bool):
        return self._call("setSneaking", value)

    @property
    def is_sprinting(self):
        return self._call_sync("isSprinting")

    def set_sprinting(self, value: bool):
        return self._call("setSprinting", value)

    def set_walk_speed(self, speed: float):
        return self._call("setWalkSpeed", speed)

    def set_fly_speed(self, speed: float):
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

    def set_resource_pack(self, url: str, hash: str = "", prompt: str | None = None, required: bool = False):
        return self._call("setResourcePack", url, hash, required, prompt)

    @property
    def inventory(self):
        if self._handle is None and self._target == "ref":
            ref_id = self._ref_id or self.fields.get("uuid") or self.fields.get("name")
            if ref_id:
                return Inventory(handle=None, target="ref", ref_type="player_inventory", ref_id=str(ref_id))
        return self._call_sync("getInventory")

    @property
    def held_item(self):
        """The item in the player's main hand."""
        return self.inventory._call_sync("getItemInMainHand")

    @property
    def selected_slot(self) -> int:
        """The player's currently selected hotbar slot (0-8)."""
        return self.inventory._call_sync("getHeldItemSlot")

    # -- freeze / vanish helpers (client-side only, no Java counterpart) ------
    _frozen_players: Dict[str, Any] = {}  # uuid -> frozen Location
    _freeze_loop_started: bool = False
    _vanished_players: set = set()

    def freeze(self):
        """Prevent the player from moving by locking their position."""
        Player._frozen_players[self.uuid] = self.location
        Player._start_freeze_loop()

    def unfreeze(self):
        Player._frozen_players.pop(self.uuid, None)

    @property
    def is_frozen(self) -> bool:
        return self.uuid in Player._frozen_players

    @staticmethod
    def _start_freeze_loop():
        if Player._freeze_loop_started:
            return
        Player._freeze_loop_started = True

        async def _loop():
            while _connection is not None and _connection._thread.is_alive():
                for uuid, loc in list(Player._frozen_players.items()):
                    try:
                        p = Player(uuid=uuid)
                        p.teleport(loc)
                    except Exception:
                        pass
                await _connection.wait(1)

        asyncio.ensure_future(_loop())

    def vanish(self):
        """Hide this player from all others."""
        Player._vanished_players.add(self.uuid)
        _connection.call(method="vanish", args=[self], target="player_util")

    def unvanish(self):
        Player._vanished_players.discard(self.uuid)
        _connection.call(method="unvanish", args=[self], target="player_util")

    @property
    def is_vanished(self) -> bool:
        return self.uuid in Player._vanished_players

    # -- extension integration helpers ----------------------------------------
    _default_bank: Any = None
    _default_mana_store: Any = None
    _default_level_system: Any = None

    @property
    def balance(self) -> float:
        """Shortcut: returns balance from the default Bank (set via ``Player._default_bank``)."""
        if Player._default_bank is None:
            raise RuntimeError("No default bank set — assign Player._default_bank first")
        return Player._default_bank.balance(self)

    def deposit(self, amount: float):
        if Player._default_bank is None:
            raise RuntimeError("No default bank set")
        Player._default_bank.deposit(self, amount)

    def withdraw(self, amount: float):
        if Player._default_bank is None:
            raise RuntimeError("No default bank set")
        Player._default_bank.withdraw(self, amount)

    @property
    def mana(self) -> float:
        """Shortcut: current mana from the default ManaStore."""
        if Player._default_mana_store is None:
            raise RuntimeError("No default ManaStore set — assign Player._default_mana_store first")
        return Player._default_mana_store[self]

    @mana.setter
    def mana(self, value: float):
        if Player._default_mana_store is None:
            raise RuntimeError("No default ManaStore set")
        Player._default_mana_store._set(self, value)

    @property
    def xp(self) -> float:
        """Shortcut: XP from the default LevelSystem."""
        if Player._default_level_system is None:
            raise RuntimeError("No default LevelSystem set — assign Player._default_level_system first")
        return Player._default_level_system.xp(self)

    @property
    def player_level(self) -> int:
        """Shortcut: level from the default LevelSystem (distinct from vanilla ``level``)."""
        if Player._default_level_system is None:
            raise RuntimeError("No default LevelSystem set")
        return Player._default_level_system.level(self)

class World(ProxyBase):
    """World API."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, name: Optional[str] = None):
        if handle is None and name is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type="world", ref_id=str(name))
            self.fields.setdefault("name", str(name))
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    def block_at(self, x: int, y: int, z: int):
        return self._call("getBlockAt", x, y, z)

    def spawn_entity(self, location: Location, entity_type: EntityType | str, **kwargs: Any):
        if isinstance(entity_type, str):
            entity_type = EntityType.from_name(entity_type)
        try:
            return self._call("spawnEntity", location, entity_type, **kwargs)
        except BridgeError as exc:
            if "Method not found: spawnEntity" in str(exc):
                return self._call("spawn", location, entity_type, **kwargs)
            raise

    def chunk_at(self, x: int, z: int):
        return self._call("getChunkAt", x, z)

    def spawn(self, location: Location, entity_cls: type, **kwargs: Any):
        if isinstance(entity_cls, (EntityType, str)):
            return self.spawn_entity(location, entity_cls, **kwargs)
        return self._call("spawn", location, entity_cls, **kwargs)

    def set_time(self, time: int):
        return self._call("setTime", time)

    @property
    def time(self):
        return self._call_sync("getTime")

    @property
    def world_time(self) -> WorldTime:
        return WorldTime(self._call_sync("getTime"))

    def at_time(self, time: WorldTime | int):
        if isinstance(time, WorldTime):
            target_ticks = time.ticks
        else:
            target_ticks = int(time) % 24000
        world_name = self.fields.get("name") or self.fields.get("ref_id", "world")

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            _at_time_handlers.setdefault(world_name, []).append((target_ticks, handler))
            _start_at_time_loop()
            return handler
        return decorator

    def set_difficulty(self, difficulty: Difficulty):
        return self._call("setDifficulty", difficulty)

    @property
    def difficulty(self):
        return self._call_sync("getDifficulty")

    def spawn_particle(self, particle: Particle, location: Location, count: int = 1, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        return self._call("spawnParticle", particle, location, count, offset_x, offset_y, offset_z, extra)

    def play_sound(self, location: Location, sound: Sound, volume: float = 1.0, pitch: float = 1.0):
        return self._call("playSound", location, sound, volume, pitch)

    def strike_lightning(self, location: Location):
        return self._call("strikeLightning", location)

    def strike_lightning_effect(self, location: Location):
        return self._call("strikeLightningEffect", location)

    @property
    def spawn_location(self):
        return self._call_sync("getSpawnLocation")

    def set_spawn_location(self, location: Location):
        return self._call("setSpawnLocation", location)

    @property
    def full_time(self):
        return self._call_sync("getFullTime")

    def set_full_time(self, time: int):
        return self._call("setFullTime", time)

    @property
    def has_storm(self):
        return self._call_sync("hasStorm")

    def set_storm(self, value: bool):
        return self._call("setStorm", value)

    @property
    def is_thundering(self):
        return self._call_sync("isThundering")

    def set_thundering(self, value: bool):
        return self._call("setThundering", value)

    @property
    def weather_duration(self):
        return self._call_sync("getWeatherDuration")

    def set_weather_duration(self, ticks: int):
        return self._call("setWeatherDuration", ticks)

    @property
    def thunder_duration(self):
        return self._call_sync("getThunderDuration")

    def set_thunder_duration(self, ticks: int):
        return self._call("setThunderDuration", ticks)

    @property
    def players(self):
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

    def set_block(self, x: int, y: int, z: int, material: Any, apply_physics: bool = False):
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="setBlock", args=[self, int(x), int(y), int(z), material, apply_physics])

    def fill(self, pos1: Any, pos2: Any, material: Any, apply_physics: bool = False):
        x1, y1, z1 = _extract_xyz(pos1)
        x2, y2, z2 = _extract_xyz(pos2)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="fill", args=[self, int(x1), int(y1), int(z1), int(x2), int(y2), int(z2), material, apply_physics])

    def replace(self, pos1: Any, pos2: Any, from_material: Any, to_material: Any):
        x1, y1, z1 = _extract_xyz(pos1)
        x2, y2, z2 = _extract_xyz(pos2)
        if isinstance(from_material, str):
            from_material = Material.from_name(from_material.upper())
        if isinstance(to_material, str):
            to_material = Material.from_name(to_material.upper())
        return _connection.call(target="region", method="replace", args=[self, int(x1), int(y1), int(z1), int(x2), int(y2), int(z2), from_material, to_material])

    def fill_sphere(self, center: Any, radius: float, material: Any, hollow: bool = False):
        cx, cy, cz = _extract_xyz(center)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="sphere", args=[self, float(cx), float(cy), float(cz), float(radius), material, hollow])

    def fill_cylinder(self, center: Any, radius: float, height: int, material: Any, hollow: bool = False):
        cx, cy, cz = _extract_xyz(center)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="cylinder", args=[self, float(cx), float(cy), float(cz), float(radius), int(height), material, hollow])

    def fill_line(self, start: Any, end: Any, material: Any):
        x1, y1, z1 = _extract_xyz(start)
        x2, y2, z2 = _extract_xyz(end)
        if isinstance(material, str):
            material = Material.from_name(material.upper())
        return _connection.call(target="region", method="line", args=[self, float(x1), float(y1), float(z1), float(x2), float(y2), float(z2), material])

    def particle_line(self, start: Any, end: Any, particle: Any, density: float = 4.0, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        x1, y1, z1 = _extract_xyz(start)
        x2, y2, z2 = _extract_xyz(end)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="line", args=[self, particle, float(x1), float(y1), float(z1), float(x2), float(y2), float(z2), float(density), float(offset_x), float(offset_y), float(offset_z), float(extra)])

    def particle_sphere(self, center: Any, radius: float, particle: Any, density: float = 4.0, hollow: bool = True, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        cx, cy, cz = _extract_xyz(center)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="sphere", args=[self, particle, float(cx), float(cy), float(cz), float(radius), float(density), hollow, float(offset_x), float(offset_y), float(offset_z), float(extra)])

    def particle_cube(self, pos1: Any, pos2: Any, particle: Any, density: float = 4.0, hollow: bool = True, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        x1, y1, z1 = _extract_xyz(pos1)
        x2, y2, z2 = _extract_xyz(pos2)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="cube", args=[self, particle, float(x1), float(y1), float(z1), float(x2), float(y2), float(z2), float(density), hollow, float(offset_x), float(offset_y), float(offset_z), float(extra)])

    def particle_ring(self, center: Any, radius: float, particle: Any, density: float = 4.0, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        cx, cy, cz = _extract_xyz(center)
        if isinstance(particle, str):
            particle = Particle.from_name(particle.upper())
        return _connection.call(target="particles", method="ring", args=[self, particle, float(cx), float(cy), float(cz), float(radius), float(density), float(offset_x), float(offset_y), float(offset_z), float(extra)])

    def spawn_at_player(self, player: Player, entity_type: Any, offset: Any = None, **kwargs: Any):
        loc = player.location
        if offset is not None:
            ox, oy, oz = _extract_xyz(offset)
            loc = Location(loc.x + ox, loc.y + oy, loc.z + oz, loc.world, loc.yaw, loc.pitch)
        return self.spawn_entity(loc, entity_type, **kwargs)

    def spawn_projectile(self, shooter: Entity, entity_type: Any, velocity: Any = None, **kwargs: Any):
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

    def spawn_with_nbt(self, location: Location, entity_type: Any, nbt: str, **kwargs: Any):
        kwargs["nbt"] = nbt
        return self.spawn_entity(location, entity_type, **kwargs)

    def create_explosion(self, location: Location, power: float = 4.0, fire: bool = False):
        """Create an explosion at the given location."""
        return self._call("createExplosion", location, float(power), fire)

    def entities_near(self, location: Location, radius: float):
        """Get all entities within radius of the location."""
        return self._call_sync("getNearbyEntities", location, float(radius), float(radius), float(radius))

    def blocks_near(self, location: Location, radius: int) -> list:
        """Get all blocks within a cubic radius of the location."""
        blocks = []
        cx, cy, cz = int(location.x), int(location.y), int(location.z)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    blocks.append(Block(world=self, x=cx + dx, y=cy + dy, z=cz + dz))
        return blocks

class Firework:
    """Launch fireworks with custom effects."""

    @staticmethod
    def launch(location: Location, effects: list | None = None, power: int = 1):
        world = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            raise BridgeError("Location must have a world to launch a firework")
        effect_list = []
        if effects:
            for e in effects:
                if isinstance(e, FireworkEffect):
                    effect_list.append(e._to_dict())
                elif isinstance(e, dict):
                    effect_list.append(e)
        return world._call("spawnFirework", location, power=power, effects=effect_list)

class FireworkEffect:
    """Builder for firework effects."""

    def __init__(self, shape: str = "BALL"):
        self._type = shape.upper()
        self._colors = []
        self._fade_colors = []
        self._flicker = False
        self._trail = False

    def colors(self, *colors) -> FireworkEffect:
        self._colors = list(colors)
        return self

    def fade(self, *colors) -> FireworkEffect:
        self._fade_colors = list(colors)
        return self

    def flicker(self, value: bool = True) -> FireworkEffect:
        self._flicker = value
        return self

    def trail(self, value: bool = True) -> FireworkEffect:
        self._trail = value
        return self

    def _to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self._type}
        if self._colors:
            d["colors"] = [self._serialize_color(c) for c in self._colors]
        if self._fade_colors:
            d["fade_colors"] = [self._serialize_color(c) for c in self._fade_colors]
        if self._flicker:
            d["flicker"] = True
        if self._trail:
            d["trail"] = True
        return d

    @staticmethod
    def _serialize_color(c):
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            return list(c)
        return c

class Effect(ProxyBase):
    """Active potion effect."""
    @classmethod
    def apply(cls, player: Player, effect_type: Optional[EffectType | str] = None, duration: int = 0, amplifier: int = 0, ambient: bool = False, particles: bool = True, icon: bool = True):
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
        if self._handle is None:
            return Effect(self.type, duration, self.amplifier, self.ambient, self.particles, self.icon)
        return self._call("withDuration", duration)

    def with_amplifier(self, amplifier: int):
        if self._handle is None:
            return Effect(self.type, self.duration, amplifier, self.ambient, self.particles, self.icon)
        return self._call("withAmplifier", amplifier)

class Attribute(ProxyBase):
    """Attribute instance for a living entity."""
    @classmethod
    def apply(cls, player: Player, attribute_type: AttributeType | str, base_value: float):
        if isinstance(attribute_type, str):
            attribute_type = AttributeType.from_name(attribute_type.upper())
        attr = player._call_sync("getAttribute", attribute_type)
        if attr is None:
            return None
        return attr.set_base_value(base_value)

    @property
    def attribute_type(self):
        return self._call_sync("getAttribute")

    @property
    def value(self):
        return self._call_sync("getValue")

    @property
    def base_value(self):
        return self._call_sync("getBaseValue")

    def set_base_value(self, value: float):
        return self._call("setBaseValue", value)

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

    def add(self, x: float, y: float, z: float) -> Location:
        return Location(self.x + x, self.y + y, self.z + z, self.world, self.yaw, self.pitch)

    def clone(self) -> Location:
        return Location(self.x, self.y, self.z, self.world, self.yaw, self.pitch)

    def distance(self, other: Location) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx * dx + dy * dy + dz * dz) ** 0.5

    def distance_squared(self, other: Location) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return dx * dx + dy * dy + dz * dz

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y, self.z)[index]

    def __add__(self, other):
        if isinstance(other, Location):
            return Location(self.x + other.x, self.y + other.y, self.z + other.z, self.world, self.yaw, self.pitch)
        if isinstance(other, Vector):
            return Location(self.x + other.x, self.y + other.y, self.z + other.z, self.world, self.yaw, self.pitch)
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, Location):
            return Location(self.x - other.x, self.y - other.y, self.z - other.z, self.world, self.yaw, self.pitch)
        if isinstance(other, Vector):
            return Location(self.x - other.x, self.y - other.y, self.z - other.z, self.world, self.yaw, self.pitch)
        return NotImplemented

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __len__(self) -> int:
        return 3

class Block(ProxyBase):
    """Block in the world."""
    @classmethod
    def create(cls, location: Location, material: Material | str):
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
        return self._call("breakNaturally")

    def set_type(self, material: Material | str):
        return self._call("setType", material)

    @property
    def is_solid(self):
        return self._call_sync("isSolid")

    @property
    def data(self):
        return self._call_sync("getBlockData")

    def set_data(self, data: Any):
        return self._call("setBlockData", data)

    @property
    def light_level(self):
        return self._call_sync("getLightLevel")

    @property
    def biome(self):
        return self._call_sync("getBiome")

    def set_biome(self, biome: Biome):
        return self._call("setBiome", biome)

    @property
    def inventory(self):
        return self._call_sync("getInventory")

    @property
    def is_container(self) -> bool:
        return self._call_sync("isContainer")

    @property
    def state_type(self) -> str:
        return self._call_sync("getStateType")

    @property
    def sign_lines(self) -> list:
        return self._call_sync("getSignLines")

    @property
    def sign_back_lines(self) -> list:
        return self._call_sync("getSignBackLines")

    def set_sign_line(self, index: int, text: str):
        return self._call("setSignLine", index, text)

    def set_sign_lines(self, lines: list):
        return self._call("setSignLines", lines)

    def set_sign_back_line(self, index: int, text: str):
        return self._call("setSignBackLine", index, text)

    def set_sign_back_lines(self, lines: list):
        return self._call("setSignBackLines", lines)

    def set_sign_glowing(self, glowing: bool):
        return self._call("setSignGlowing", glowing)

    @property
    def is_sign_glowing(self) -> bool:
        return self._call_sync("isSignGlowing")

    @property
    def furnace_burn_time(self) -> int:
        return self._call_sync("getFurnaceBurnTime")

    @property
    def furnace_cook_time(self) -> int:
        return self._call_sync("getFurnaceCookTime")

    @property
    def furnace_cook_time_total(self) -> int:
        return self._call_sync("getFurnaceCookTimeTotal")

    def set_furnace_burn_time(self, ticks: int):
        return self._call("setFurnaceBurnTime", ticks)

    def set_furnace_cook_time(self, ticks: int):
        return self._call("setFurnaceCookTime", ticks)

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
        return self._call("load")

    def unload(self):
        return self._call("unload")

    @property
    def is_loaded(self):
        return self._call_sync("isLoaded")

class Inventory(ProxyBase):
    """Inventory. Can belong to an entity or block entity, or exist as a standalone open inventory screen."""
    def __init__(self, size: int = 9, title: str = "", contents: Optional[List[Item]] = None, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None, ref_type: Optional[str] = None, ref_id: Optional[str] = None):
        if handle is None and fields is None and ref_type is None and ref_id is None:
            fields = {"size": int(size), "title": str(title)}
            if contents is not None:
                fields["contents"] = list(contents)
            super().__init__(handle=None, type_name=type_name, fields=fields, target=target)
        elif handle is None and ref_type is not None and ref_id is not None:
            super().__init__(handle=None, type_name=type_name, fields=fields, target="ref", ref_type=ref_type, ref_id=ref_id)
        else:
            super().__init__(handle=handle, type_name=type_name, fields=fields, target=target)

    def open(self, player: Player):
        return player._call("openInventory", self)

    def add_item(self, item: Item):
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

    def remove_item(self, item: Item):
        if self._handle is None and self._target != "ref":
            contents = list(self.fields.get("contents") or [])
            for idx, slot in enumerate(contents):
                if slot == item:
                    contents[idx] = None
                    break
            self.fields["contents"] = contents
            return None
        return self._call("removeItem", item)

    def clear(self):
        if self._handle is None:
            self.fields["contents"] = []
            return None
        return self._call("clear")

    def close(self, player: Optional[Player] = None):
        if player is not None:
            return player._call("closeInventory")
        return self._call("close")

    @property
    def first_empty(self):
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
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            return contents[slot] if 0 <= slot < len(contents) else None
        return self._call("getItem", slot)

    def set_item(self, slot: int, item: Item):
        if self._handle is None:
            contents = list(self.fields.get("contents") or [])
            while len(contents) <= slot:
                contents.append(None)
            contents[slot] = item
            self.fields["contents"] = contents
            return None
        return self._call("setItem", slot, item)

    def contains(self, material: Material, amount: int = 1):
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
    def drop(cls, location: Location, amount: int = 1, material: Material | str | None = None, **kwargs: Any):
        world = location.world
        if isinstance(world, str):
            world = World(name=world)
        if world is None:
            raise BridgeError("Location must have a world to drop an item")
        if isinstance(cls, type):
            if material is None:
                raise ValueError("Material must be set when calling as a classmethod.")
            item = Item(material=material, amount=amount, **kwargs)
        else:
            item = cls
        return world._call("dropItem", location, item)

    @classmethod
    def give(cls, player: Player, material: Material | str | None = None, amount: int = 1, **kwargs: Any):
        if isinstance(cls, type):
            if material is None:
                raise ValueError("Material must be set when calling as a classmethod.")
            item = Item(material=material, amount=amount, **kwargs)
        else:
            item = cls
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
        return self._call("setAmount", value)

    @property
    def name(self):
        return self._call_sync("getName")

    @name.setter
    def name(self, name):
        return self.set_name(name)

    def set_name(self, name: str):
        if self._handle is None:
            self.fields["name"] = str(name)
            return self
        return self._call("setName", name)

    @property
    def lore(self):
        return self._call_sync("getLore")

    @lore.setter
    def lore(self, lore):
        return self.set_lore(lore)

    def set_lore(self, lore: List[str]):
        if self._handle is None:
            self.fields["lore"] = list(lore)
            return self
        return self._call("setLore", lore)

    @property
    def custom_model_data(self):
        return self._call_sync("getCustomModelData")

    def set_custom_model_data(self, value: int):
        if self._handle is None:
            self.fields["customModelData"] = int(value)
            return self
        return self._call("setCustomModelData", value)

    @property
    def attributes(self):
        return self._call_sync("getAttributes")

    def set_attributes(self, attributes: List[Dict[str, Any]]):
        if self._handle is None:
            self.fields["attributes"] = list(attributes)
            return self
        return self._call("setAttributes", attributes)

    @property
    def nbt(self):
        return self._call_sync("getNbt")

    def set_nbt(self, nbt: Dict[str, Any]):
        if self._handle is None:
            self.fields["nbt"] = nbt
            return self
        return self._call("setNbt", nbt)

    def clone(self):
        return self._call("clone")

    def is_similar(self, other: Item):
        return self._call("isSimilar", other)

    @property
    def max_stack_size(self):
        return self._call_sync("getMaxStackSize")

class ItemBuilder:
    """Fluent builder for Item objects."""

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

    def amount(self, n: int) -> ItemBuilder:
        self._amount = int(n)
        return self

    def name(self, n: str) -> ItemBuilder:
        self._name = str(n)
        return self

    def lore(self, *lines: str) -> ItemBuilder:
        self._lore = list(lines)
        return self

    def add_lore(self, line: str) -> ItemBuilder:
        self._lore.append(str(line))
        return self

    def enchant(self, enchantment: str, level: int = 1) -> ItemBuilder:
        self._enchantments[enchantment.lower()] = int(level)
        return self

    def unbreakable(self, value: bool = True) -> ItemBuilder:
        self._unbreakable_flag = bool(value)
        return self

    def glow(self, value: bool = True) -> ItemBuilder:
        self._glow_flag = bool(value)
        return self

    def custom_model_data(self, value: int) -> ItemBuilder:
        self._custom_model_data = int(value)
        return self

    def attributes(self, attrs: List[Dict[str, Any]]) -> ItemBuilder:
        self._attributes = list(attrs)
        return self

    def add_attribute(self, attribute: str, amount: float, operation: str = "ADD_NUMBER") -> ItemBuilder:
        self._attributes.append({"attribute": attribute, "amount": float(amount), "operation": operation})
        return self

    def nbt(self, data: Dict[str, Any]) -> ItemBuilder:
        self._nbt = dict(data)
        return self

    def flag(self, *flags: str) -> ItemBuilder:
        self._item_flags.extend(str(f).upper() for f in flags)
        return self

    def build(self) -> Item:
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

    @classmethod
    def from_item(cls, item: Item) -> ItemBuilder:
        builder = cls(item.type)
        builder._amount = item.fields.get("amount", 1) if hasattr(item, "fields") else 1
        builder._name = item.fields.get("name") if hasattr(item, "fields") else None
        builder._lore = list(item.fields.get("lore") or []) if hasattr(item, "fields") else []
        if hasattr(item, "fields"):
            builder._custom_model_data = item.fields.get("customModelData")
            builder._attributes = list(item.fields.get("attributes") or [])
            builder._nbt = dict(item.fields["nbt"]) if "nbt" in item.fields else None
            builder._enchantments = dict(item.fields.get("enchantments") or {})
            builder._unbreakable_flag = bool(item.fields.get("unbreakable"))
            builder._glow_flag = bool(item.fields.get("glow"))
            builder._item_flags = list(item.fields.get("item_flags") or [])
        return builder

class Recipe:
    """Register custom crafting and smelting recipes."""

    @staticmethod
    def shaped(key: str, result: Material | str, shape: list, ingredients: dict, amount: int = 1):
        result_str = result if isinstance(result, str) else result.name
        ing = {k: (v if isinstance(v, str) else v.name) for k, v in ingredients.items()}
        return _connection.call(method="addShapedRecipe", target="server", args=[key, result_str, shape, ing, amount])

    @staticmethod
    def shapeless(key: str, result: Material | str, ingredients: list, amount: int = 1):
        result_str = result if isinstance(result, str) else result.name
        ing = [(i if isinstance(i, str) else i.name) for i in ingredients]
        return _connection.call(method="addShapelessRecipe", target="server", args=[key, result_str, ing, amount])

    @staticmethod
    def furnace(key: str, input: Material | str, result: Material | str, experience: float = 0, cook_time: int = 200, amount: int = 1):
        input_str = input if isinstance(input, str) else input.name
        result_str = result if isinstance(result, str) else result.name
        return _connection.call(method="addFurnaceRecipe", target="server", args=[key, input_str, result_str, experience, cook_time, amount])

    @staticmethod
    def remove(key: str):
        return _connection.call(method="removeRecipe", target="server", args=[key])

class BossBar(ProxyBase):
    """Boss bar API."""
    @classmethod
    def create(cls, title: str, color: Optional[BarColor] = None, style: Optional[BarStyle] = None, players: Optional[List[Player]] = None):
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
        return self._call("addPlayer", player)

    def remove_player(self, player: Player):
        return self._call("removePlayer", player)

    @property
    def title(self):
        return self._call_sync("getTitle")

    def set_title(self, title: str):
        return self._call("setTitle", title)

    @property
    def progress(self):
        return self._call_sync("getProgress")

    def set_progress(self, value: float):
        return self._call("setProgress", value)

    @property
    def color(self):
        return self._call_sync("getColor")

    def set_color(self, color: BarColor):
        return self._call("setColor", color)

    @property
    def style(self):
        return self._call_sync("getStyle")

    def set_style(self, style: BarStyle):
        return self._call("setStyle", style)

    @property
    def visible(self):
        return self._call_sync("isVisible")

    def set_visible(self, value: bool):
        return self._call("setVisible", value)

class Scoreboard(ProxyBase):
    """Scoreboard API."""
    @classmethod
    def create(cls):
        manager = server._call_sync("getScoreboardManager")
        return manager._call_sync("getNewScoreboard")

    def register_objective(self, name: str, criteria: str, display_name: str = ""):
        if display_name:
            return self._call("registerNewObjective", name, criteria, display_name)
        return self._call("registerNewObjective", name, criteria)

    def get_team(self, name: str):
        return self._call("getTeam", name)

    def register_team(self, name: str):
        return self._call("registerNewTeam", name)

    def get_objective(self, name: str):
        return self._call("getObjective", name)

    @property
    def objectives(self):
        return self._call_sync("getObjectives")

    @property
    def teams(self):
        return self._call_sync("getTeams")

    def clear_slot(self, slot: Any):
        return self._call("clearSlot", slot)

class Team(ProxyBase):
    """Team API."""
    @classmethod
    def create(cls, name: str, scoreboard: Optional[Scoreboard] = None):
        if scoreboard is None:
            scoreboard = Scoreboard.create()  # type: ignore[assignment]
        return scoreboard.register_team(name)  # type: ignore[union-attr]

    def add_entry(self, entry: str):
        return self._call("addEntry", entry)

    def remove_entry(self, entry: str):
        return self._call("removeEntry", entry)

    def set_prefix(self, prefix: str):
        return self._call("setPrefix", prefix)

    def set_suffix(self, suffix: str):
        return self._call("setSuffix", suffix)

    @property
    def color(self):
        return self._call_sync("getColor")

    def set_color(self, color: Any):
        return self._call("setColor", color)

    @property
    def entries(self):
        return self._call_sync("getEntries")

class Objective(ProxyBase):
    """Objective API."""
    @classmethod
    def create(cls, name: str, criteria: str, display_name: str = "", scoreboard: Optional[Scoreboard] = None):
        if scoreboard is None:
            scoreboard = Scoreboard.create()  # type: ignore[assignment]
        return scoreboard.register_objective(name, criteria, display_name)  # type: ignore[union-attr]

    def set_display_name(self, name: str):
        return self._call("setDisplayName", name)

    def get_score(self, entry: str):
        return self._call("getScore", entry)

    @property
    def name(self):
        return self._call_sync("getName")

    @property
    def criteria(self):
        return self._call_sync("getCriteria")

    @property
    def display_slot(self):
        return self._call_sync("getDisplaySlot")

    def set_display_slot(self, slot: Any):
        return self._call("setDisplaySlot", slot)

class Advancement(ProxyBase):
    """Advancement API."""
    @classmethod
    def grant(cls, player: Player, key: str):
        return player._call("grantAdvancement", key)

    @classmethod
    def revoke(cls, player: Player, key: str):
        return player._call("revokeAdvancement", key)

    @property
    def key(self):
        return self._call_sync("getKey")

class AdvancementProgress(ProxyBase):
    """Advancement progress API."""
    @property
    def is_done(self):
        return self._call_sync("isDone")

    def award_criteria(self, name: str):
        return self._call("awardCriteria", name)

    def revoke_criteria(self, name: str):
        return self._call("revokeCriteria", name)

    @property
    def remaining_criteria(self):
        return self._call_sync("getRemainingCriteria")

    @property
    def awarded_criteria(self):
        return self._call_sync("getAwardedCriteria")

class Potion(ProxyBase):
    """Potion API (legacy)."""
    @classmethod
    def apply(cls, player: Player, effect_type: Optional[EffectType | str] = None, duration: int = 0, amplifier: int = 0, ambient: bool = False, particles: bool = True, icon: bool = True):
        return Effect.apply(player, effect_type, duration, amplifier, ambient, particles, icon)

    @property
    def type(self):
        return self._call_sync("getType")

    @property
    def level(self):
        return self._call_sync("getLevel")

class Vector(ProxyBase):
    """Basic Vec3."""
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

    def __add__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x + other.x, self.y + other.y, self.z + other.z)
        if isinstance(other, (list, tuple)) and len(other) == 3:
            return Vector(self.x + other[0], self.y + other[1], self.z + other[2])
        return NotImplemented

    def __sub__(self, other):
        if isinstance(other, Vector):
            return Vector(self.x - other.x, self.y - other.y, self.z - other.z)
        if isinstance(other, (list, tuple)) and len(other) == 3:
            return Vector(self.x - other[0], self.y - other[1], self.z - other[2])
        return NotImplemented

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return Vector(self.x * other, self.y * other, self.z * other)
        if isinstance(other, Vector):
            return Vector(self.x * other.x, self.y * other.y, self.z * other.z)
        if isinstance(other, (list, tuple)) and len(other) == 3:
            return Vector(self.x * other[0], self.y * other[1], self.z * other[2])
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

class ChatFacade(ProxyBase):
    """Chat helper facade."""
    def broadcast(self, message: str):
        return self._call("broadcast", message)

class ReflectFacade(ProxyBase):
    """Reflection helper facade."""
    def clazz(self, name: str):
        return self._call("clazz", name)

# Module-level singleton instances
server = Server(target="server")
chat = ChatFacade(target="chat")
reflect = ReflectFacade(target="reflect")
