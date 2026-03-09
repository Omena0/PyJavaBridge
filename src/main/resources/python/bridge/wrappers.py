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
_PLAYER_UUID_CACHE_MAX = 1000

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
        # Fast path: same handle means same Java object
        if self._handle is not None and self._handle == other._handle:
            return True
        # Compare by UUID if both have one (entities/players)
        s_uuid = self.fields.get("uuid")
        o_uuid = other.fields.get("uuid")
        if s_uuid is not None and o_uuid is not None:
            return s_uuid == o_uuid
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

    # StructureManager
    def save_structure(self, name: str, world, x1: int, y1: int, z1: int,
                       x2: int, y2: int, z2: int):
        """Save a region as a named structure."""
        world_name = world.name if hasattr(world, "name") else str(world)
        return self._call("saveStructure", name, world_name, x1, y1, z1, x2, y2, z2)

    def load_structure(self, name: str, world, x: float, y: float, z: float,
                       include_entities: bool = False):
        """Place a saved structure at a location."""
        world_name = world.name if hasattr(world, "name") else str(world)
        return self._call("loadStructure", name, world_name, x, y, z, include_entities)

    def delete_structure(self, name: str):
        """Delete a saved structure."""
        return self._call("deleteStructure", name)

    @property
    def structures(self):
        """List all saved structure names."""
        return self._call_sync("listStructures")

    # WorldCreator
    def create_world(self, name: str, *, environment: str = "NORMAL",
                     world_type: str = "NORMAL", seed: Optional[int] = None,
                     generate_structures: bool = True):
        """Create or load a world."""
        opts = {"name": name, "environment": environment, "type": world_type,
                "generate_structures": generate_structures}
        if seed is not None:
            opts["seed"] = seed
        return self._call("createWorld", opts)

    def unload_world(self, name: str):
        """Unload (delete from memory) a world."""
        return self._call("deleteWorld", name)

# Per-entity tags keyed by UUID, shared across all instances of the same entity.
_entity_tags: Dict[str, set] = {}

# Transient per-entity metadata keyed by UUID (Python-side only, not persisted).
_entity_metadata: Dict[str, Dict[str, Any]] = {}

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

    def __bool__(self) -> bool:
        try:
            return self._call_sync("isValid")
        except Exception:
            return False

    def teleport(self, location: Location):
        return self._call("teleport", location)

    def remove(self):
        return self._call("remove")

    @property
    def velocity(self):
        return self._call_sync("getVelocity")

    @velocity.setter
    def velocity(self, vector: Vector):
        return self._call("setVelocity", vector)

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

    @fire_ticks.setter
    def fire_ticks(self, ticks: int):
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

    @custom_name.setter
    def custom_name(self, name: str):
        return self._call("setCustomName", name)

    @custom_name.deleter
    def custom_name(self):
        return self._call("setCustomName", None)

    @property
    def custom_name_visible(self) -> bool:
        return self._call_sync("isCustomNameVisible")

    @custom_name_visible.setter
    def custom_name_visible(self, value: bool):
        return self._call("setCustomNameVisible", value)

    @property
    def uuid(self):
        return self._field_or_call_sync("uuid", "getUniqueId")

    @property
    def type(self):
        return self._field_or_call_sync("type", "getType")

    @property
    def is_projectile(self):
        return self.fields.get("is_projectile", False)

    @property
    def shooter(self):
        return self._field_or_call_sync("shooter", "getShooter")

    @property
    def is_tamed(self):
        return self.fields.get("is_tamed", False)

    @property
    def owner(self):
        return self._field_or_call_sync("owner", "getOwner")

    @property
    def owner_uuid(self):
        return self.fields.get("owner_uuid")

    @property
    def owner_name(self):
        return self.fields.get("owner_name")

    @property
    def source(self):
        return self._field_or_call_sync("source", "getSource")

    @property
    def location(self):
        return self._call_sync("getLocation")

    @property
    def yaw(self) -> float:
        loc = self._call_sync("getLocation")
        return float(loc.yaw) if loc else 0.0

    @property
    def pitch(self) -> float:
        loc = self._call_sync("getLocation")
        return float(loc.pitch) if loc else 0.0

    @property
    def look_direction(self) -> Vector:
        """Normalized direction vector from the entity's yaw and pitch."""
        import math
        loc = self._call_sync("getLocation")
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

    @target.setter
    def target(self, entity: Entity | None = None):
        return self._call("setTarget", entity)

    @target.deleter
    def target(self):
        return self._call("setTarget", None)

    @property
    def is_aware(self):
        return self._call_sync("isAware")

    @is_aware.setter
    def is_aware(self, aware: bool):
        return self._call("setAware", aware)

    def pathfind_to(self, location: Location, speed: float = 1.0):
        return self._call_sync("pathfindTo", location, speed)

    def stop_pathfinding(self):
        return self._call("stopPathfinding")

    def has_line_of_sight(self, entity: Entity):
        return self._call_sync("hasLineOfSight", entity)

    def look_at(self, location: Location):
        return self._call("lookAt", location)

    # AI Goals (Paper MobGoals API)
    @property
    def goal_types(self) -> list:
        """List all active AI goal type keys on this mob."""
        return self._call_sync("getGoalTypes")

    def remove_goal(self, goal_key: str) -> bool:
        """Remove an AI goal by its key."""
        return self._call_sync("removeGoal", goal_key)

    def remove_all_goals(self):
        """Remove all AI goals from this mob."""
        return self._call("removeAllGoals")

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

    @property
    def gravity(self) -> bool:
        return self._call_sync("hasGravity")

    @gravity.setter
    def gravity(self, value: bool):
        return self._call("setGravity", value)

    @property
    def glowing(self) -> bool:
        return self._call_sync("isGlowing")

    @glowing.setter
    def glowing(self, value: bool):
        return self._call("setGlowing", value)

    @property
    def invisible(self) -> bool:
        return self._call_sync("isInvisible")

    @invisible.setter
    def invisible(self, value: bool):
        return self._call("setInvisible", value)

    @property
    def invulnerable(self) -> bool:
        return self._call_sync("isInvulnerable")

    @invulnerable.setter
    def invulnerable(self, value: bool):
        return self._call("setInvulnerable", value)

    @property
    def silent(self) -> bool:
        return self._call_sync("isSilent")

    @silent.setter
    def silent(self, value: bool):
        return self._call("setSilent", value)

    @property
    def persistent(self) -> bool:
        return self._call_sync("isPersistent")

    @persistent.setter
    def persistent(self, value: bool):
        return self._call("setPersistent", value)

    @property
    def collidable(self) -> bool:
        return self._call_sync("isCollidable")

    @collidable.setter
    def collidable(self, value: bool):
        return self._call("setCollidable", value)

    @property
    def portal_cooldown(self) -> int:
        return self._call_sync("getPortalCooldown")

    @portal_cooldown.setter
    def portal_cooldown(self, ticks: int):
        return self._call("setPortalCooldown", int(ticks))

    @property
    def max_fire_ticks(self) -> int:
        return self._call_sync("getMaxFireTicks")

    @property
    def freeze_ticks(self) -> int:
        return self._call_sync("getFreezeTicks")

    @freeze_ticks.setter
    def freeze_ticks(self, ticks: int):
        return self._call("setFreezeTicks", int(ticks))

    @property
    def height(self) -> float:
        return self._call_sync("getHeight")

    @property
    def width(self) -> float:
        return self._call_sync("getWidth")

    @property
    def bounding_box(self) -> dict:
        return self._call_sync("getBoundingBox")

    @property
    def metadata(self) -> dict:
        """Transient per-entity key/value storage (Python-side only, not persisted)."""
        uid = self.uuid
        if uid not in _entity_metadata:
            _entity_metadata[uid] = {}
        return _entity_metadata[uid]


# ── Entity Subtypes ──────────────────────────────────────────────────

class ArmorStand(Entity):
    """ArmorStand entity with pose and equipment properties."""

    @property
    def small(self) -> bool:
        return self._call_sync("isSmall")

    @small.setter
    def small(self, value: bool):
        self._call("setSmall", value)

    @property
    def visible(self) -> bool:
        return not self._call_sync("isInvisible")

    @visible.setter
    def visible(self, value: bool):
        self._call("setInvisible", not value)

    @property
    def arms(self) -> bool:
        return self._call_sync("hasArms")

    @arms.setter
    def arms(self, value: bool):
        self._call("setArms", value)

    @property
    def base_plate(self) -> bool:
        return self._call_sync("hasBasePlate")

    @base_plate.setter
    def base_plate(self, value: bool):
        self._call("setBasePlate", value)

    @property
    def marker(self) -> bool:
        return self._call_sync("isMarker")

    @marker.setter
    def marker(self, value: bool):
        self._call("setMarker", value)

    @property
    def head_pose(self):
        return self._call_sync("getHeadPose")

    @head_pose.setter
    def head_pose(self, pose):
        self._call("setHeadPose", pose)

    @property
    def body_pose(self):
        return self._call_sync("getBodyPose")

    @body_pose.setter
    def body_pose(self, pose):
        self._call("setBodyPose", pose)

    @property
    def left_arm_pose(self):
        return self._call_sync("getLeftArmPose")

    @left_arm_pose.setter
    def left_arm_pose(self, pose):
        self._call("setLeftArmPose", pose)

    @property
    def right_arm_pose(self):
        return self._call_sync("getRightArmPose")

    @right_arm_pose.setter
    def right_arm_pose(self, pose):
        self._call("setRightArmPose", pose)

    @property
    def left_leg_pose(self):
        return self._call_sync("getLeftLegPose")

    @left_leg_pose.setter
    def left_leg_pose(self, pose):
        self._call("setLeftLegPose", pose)

    @property
    def right_leg_pose(self):
        return self._call_sync("getRightLegPose")

    @right_leg_pose.setter
    def right_leg_pose(self, pose):
        self._call("setRightLegPose", pose)


class Villager(Entity):
    """Villager entity with profession and trade properties."""

    @property
    def profession(self) -> str:
        return self._call_sync("getProfession")

    @profession.setter
    def profession(self, value: str):
        self._call("setProfession", value)

    @property
    def villager_type(self) -> str:
        return self._call_sync("getVillagerType")

    @villager_type.setter
    def villager_type(self, value: str):
        self._call("setVillagerType", value)

    @property
    def villager_level(self) -> int:
        return self._call_sync("getVillagerLevel")

    @villager_level.setter
    def villager_level(self, value: int):
        self._call("setVillagerLevel", int(value))

    @property
    def villager_experience(self) -> int:
        return self._call_sync("getVillagerExperience")

    @villager_experience.setter
    def villager_experience(self, value: int):
        self._call("setVillagerExperience", int(value))


class ItemFrame(Entity):
    """ItemFrame entity."""

    @property
    def item(self):
        return self._call_sync("getItem")

    @item.setter
    def item(self, value):
        self._call("setItem", value)

    @item.deleter
    def item(self):
        self._call("setItem", None)

    @property
    def rotation(self):
        return self._call_sync("getRotation")

    @rotation.setter
    def rotation(self, value):
        self._call("setRotation", value)

    @property
    def fixed(self) -> bool:
        return self._call_sync("isFixed")

    @fixed.setter
    def fixed(self, value: bool):
        self._call("setFixed", value)

    @property
    def item_drop_chance(self) -> float:
        return self._call_sync("getItemDropChance")

    @item_drop_chance.setter
    def item_drop_chance(self, value: float):
        self._call("setItemDropChance", float(value))


class FallingBlock(Entity):
    """FallingBlock entity."""

    @property
    def material(self):
        return self._call_sync("getBlockData")

    @property
    def drop_item(self) -> bool:
        return self._call_sync("getDropItem")

    @drop_item.setter
    def drop_item(self, value: bool):
        self._call("setDropItem", value)

    @property
    def can_hurt_entities(self) -> bool:
        return self._call_sync("canHurtEntities")

    @can_hurt_entities.setter
    def can_hurt_entities(self, value: bool):
        self._call("setHurtEntities", value)

    @property
    def damage_per_block(self) -> float:
        return self._call_sync("getDamagePerBlock")

    @damage_per_block.setter
    def damage_per_block(self, value: float):
        self._call("setDamagePerBlock", float(value))

    @property
    def max_damage(self) -> int:
        return self._call_sync("getMaxDamage")

    @max_damage.setter
    def max_damage(self, value: int):
        self._call("setMaxDamage", int(value))


class AreaEffectCloud(Entity):
    """AreaEffectCloud entity with radius and effect properties."""

    @property
    def radius(self) -> float:
        return self._call_sync("getRadius")

    @radius.setter
    def radius(self, value: float):
        self._call("setRadius", float(value))

    @property
    def color(self):
        return self._call_sync("getColor")

    @color.setter
    def color(self, value):
        self._call("setColor", value)

    @property
    def duration(self) -> int:
        return self._call_sync("getDuration")

    @duration.setter
    def duration(self, ticks: int):
        self._call("setDuration", int(ticks))

    @property
    def wait_time(self) -> int:
        return self._call_sync("getWaitTime")

    @wait_time.setter
    def wait_time(self, ticks: int):
        self._call("setWaitTime", int(ticks))

    @property
    def radius_on_use(self) -> float:
        return self._call_sync("getRadiusOnUse")

    @radius_on_use.setter
    def radius_on_use(self, value: float):
        self._call("setRadiusOnUse", float(value))

    @property
    def radius_per_tick(self) -> float:
        return self._call_sync("getRadiusPerTick")

    @radius_per_tick.setter
    def radius_per_tick(self, value: float):
        self._call("setRadiusPerTick", float(value))

    @property
    def particle(self):
        return self._call_sync("getParticle")

    @particle.setter
    def particle(self, value):
        self._call("setParticle", value)


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

    @tab_list_header.setter
    def tab_list_header(self, header: str):
        return self._call("setTabListHeader", header)

    @property
    def tab_list_footer(self):
        return self._call_sync("getTabListFooter")

    @tab_list_footer.setter
    def tab_list_footer(self, footer: str):
        return self._call("setTabListFooter", footer)

    def set_tab_list_header_footer(self, header: str = "", footer: str = ""):
        return self._call("setTabListHeaderFooter", header, footer)

    @property
    def tab_list_name(self):
        return self._call_sync("getPlayerListName")

    @tab_list_name.setter
    def tab_list_name(self, name: str):
        return self._call("setPlayerListName", name)

    def set_health(self, health: float):
        return self._call("setHealth", health)

    def set_food_level(self, level: int):
        return self._call("setFoodLevel", level)

    @property
    def level(self):
        return self._call_sync("getLevel")

    @level.setter
    def level(self, level: int):
        return self._call("setLevel", level)

    @property
    def exp(self):
        return self._call_sync("getExp")

    @exp.setter
    def exp(self, exp: float):
        return self._call("setExp", exp)

    @property
    def is_flying(self):
        return self._call_sync("isFlying")

    @is_flying.setter
    def is_flying(self, value: bool):
        return self._call("setFlying", value)

    @property
    def is_sneaking(self):
        return self._call_sync("isSneaking")

    @is_sneaking.setter
    def is_sneaking(self, value: bool):
        return self._call("setSneaking", value)

    @property
    def is_sprinting(self):
        return self._call_sync("isSprinting")

    @is_sprinting.setter
    def is_sprinting(self, value: bool):
        return self._call("setSprinting", value)

    def set_walk_speed(self, speed: float):
        return self._call("setWalkSpeed", speed)

    def set_fly_speed(self, speed: float):
        return self._call("setFlySpeed", speed)

    @property
    def name(self):
        return self.fields.get("name")

    @property
    def uuid(self) -> str:
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
                    if len(_player_uuid_cache) >= _PLAYER_UUID_CACHE_MAX:
                        # Evict oldest quarter
                        keys = list(_player_uuid_cache.keys())
                        for k in keys[:len(keys) // 4]:
                            del _player_uuid_cache[k]
                    _player_uuid_cache[str(ref_id)] = result_text
                return result_text

            raise Exception(f"Could not get UUID: {self}")

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

    @property
    def absorption(self) -> float:
        return self._call_sync("getAbsorptionAmount")

    @absorption.setter
    def absorption(self, value: float):
        return self._call("setAbsorptionAmount", float(value))

    @property
    def saturation(self) -> float:
        return self._call_sync("getSaturation")

    @saturation.setter
    def saturation(self, value: float):
        return self._call("setSaturation", float(value))

    @property
    def exhaustion(self) -> float:
        return self._call_sync("getExhaustion")

    @exhaustion.setter
    def exhaustion(self, value: float):
        return self._call("setExhaustion", float(value))

    @property
    def attack_cooldown(self) -> float:
        return self._call_sync("getAttackCooldown")

    @property
    def allow_flight(self) -> bool:
        return self._call_sync("getAllowFlight")

    @allow_flight.setter
    def allow_flight(self, value: bool):
        return self._call("setAllowFlight", value)

    @property
    def locale(self) -> str:
        return self._call_sync("getLocale")

    @property
    def ping(self) -> int:
        return self._call_sync("getPing")

    @property
    def client_brand(self) -> str:
        return self._call_sync("getClientBrandName")

    # --- Methods needing Java handlers ---

    def hide_player(self, other: Player):
        return self._call("hidePlayer", other)

    def show_player(self, other: Player):
        return self._call("showPlayer", other)

    def can_see(self, other: Player) -> bool:
        return self._call_sync("canSee", other)

    def open_book(self, item: Item):
        return self._call("openBook", item)

    def send_block_change(self, location: Location, material: str):
        return self._call("sendBlockChange", location, material)

    def send_particle(self, particle: str, location: Location, count: int = 1, offset_x: float = 0, offset_y: float = 0, offset_z: float = 0, extra: float = 0):
        return self._call("sendParticle", particle, location, count, offset_x, offset_y, offset_z, extra)

    def get_cooldown(self, material: str) -> int:
        return self._call_sync("getCooldown", material)

    def set_cooldown(self, material: str, ticks: int):
        return self._call("setCooldown", material, ticks)

    def has_cooldown(self, material: str) -> bool:
        return self._call_sync("hasCooldown", material)

    def get_statistic(self, stat: str, material_or_entity: str | None = None) -> int:
        if material_or_entity is not None:
            return self._call_sync("getStatistic", stat, material_or_entity)
        return self._call_sync("getStatistic", stat)

    def set_statistic(self, stat: str, value: int, material_or_entity: str | None = None):
        if material_or_entity is not None:
            return self._call("setStatistic", stat, material_or_entity, value)
        return self._call("setStatistic", stat, value)

    @property
    def max_health(self) -> float:
        return self._call_sync("getMaxHealth")

    @max_health.setter
    def max_health(self, value: float):
        self._call("setMaxHealth", float(value))

    @property
    def bed_spawn_location(self) -> Location | None:
        data = self._call_sync("getBedSpawnLocation")
        if data is None:
            return None
        if isinstance(data, dict):
            return Location(fields=data)
        return data

    @bed_spawn_location.setter
    def bed_spawn_location(self, location: Location | None):
        self._call("setBedSpawnLocation", location)

    @bed_spawn_location.deleter
    def bed_spawn_location(self):
        self._call("setBedSpawnLocation", None)

    @property
    def compass_target(self) -> Location:
        data = self._call_sync("getCompassTarget")
        if isinstance(data, dict):
            return Location(fields=data)
        return data

    @compass_target.setter
    def compass_target(self, location: Location):
        self._call("setCompassTarget", location)

    # --- PersistentDataContainer ---

    def get_persistent_data(self) -> dict:
        return self._call_sync("getPDC")

    def set_persistent_data(self, key: str, value: str):
        return self._call("setPDC", key, value)

    def remove_persistent_data(self, key: str):
        return self._call("removePDC", key)

    def has_persistent_data(self, key: str) -> bool:
        return self._call_sync("hasPDC", key)

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

    @property
    def time(self):
        return self._call_sync("getTime")

    @time.setter
    def time(self, time: int):
        return self._call("setTime", time)

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

    @property
    def difficulty(self):
        return self._call_sync("getDifficulty")

    @difficulty.setter
    def difficulty(self, difficulty: Difficulty):
        return self._call("setDifficulty", difficulty)

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

    @spawn_location.setter
    def spawn_location(self, location: Location):
        return self._call("setSpawnLocation", location)

    @property
    def full_time(self):
        return self._call_sync("getFullTime")

    @full_time.setter
    def full_time(self, time: int):
        return self._call("setFullTime", time)

    @property
    def has_storm(self):
        return self._call_sync("hasStorm")

    @has_storm.setter
    def has_storm(self, value: bool):
        return self._call("setStorm", value)

    @property
    def is_thundering(self):
        return self._call_sync("isThundering")

    @is_thundering.setter
    def is_thundering(self, value: bool):
        return self._call("setThundering", value)

    @property
    def weather_duration(self):
        return self._call_sync("getWeatherDuration")

    @weather_duration.setter
    def weather_duration(self, ticks: int):
        return self._call("setWeatherDuration", ticks)

    @property
    def thunder_duration(self):
        return self._call_sync("getThunderDuration")

    @thunder_duration.setter
    def thunder_duration(self, ticks: int):
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

    @property
    def seed(self) -> int:
        return self._call_sync("getSeed")

    @property
    def pvp(self) -> bool:
        return self._call_sync("getPVP")

    @pvp.setter
    def pvp(self, value: bool):
        return self._call("setPVP", value)

    def __contains__(self, entity) -> bool:
        """Check if an entity is in this world: ``entity in world``."""
        if hasattr(entity, 'world'):
            ew = entity.world
            if hasattr(ew, 'name'):
                return ew.name == self.name
        return False

    # --- Game Rules ---

    def get_game_rule(self, rule: str):
        return self._call_sync("getGameRule", rule)

    def set_game_rule(self, rule: str, value):
        return self._call("setGameRule", rule, value)

    @property
    def game_rules(self) -> dict:
        return self._call_sync("getGameRules")

    # --- World Border ---

    @property
    def world_border(self) -> dict:
        return self._call_sync("getWorldBorder")

    @world_border.setter
    def world_border(self, settings: dict):
        return self._call("setWorldBorder", settings)

    # --- Terrain Queries ---

    def get_highest_block_at(self, x: int, z: int) -> Block:
        data = self._call_sync("getHighestBlockAt", x, z)
        if isinstance(data, dict):
            return Block(world=self, x=data.get("x", x), y=data.get("y", 0), z=data.get("z", z))
        return data

    def generate_tree(self, location: Location, tree_type: str) -> bool:
        return self._call_sync("generateTree", location, tree_type)

    def get_nearby_entities(self, location: Location, dx: float, dy: float, dz: float) -> list:
        return self._call_sync("getNearbyEntities", location, dx, dy, dz)

    def get_chunk_at_async(self, x: int, z: int):
        return self._call("getChunkAtAsync", x, z)

    def batch_spawn(self, specs: list) -> list:
        """Spawn multiple entities in a single call. Each spec is a dict with 'location' and 'type'."""
        return self._call_sync("batchSpawn", specs)

    def ray_trace(self, start: Location, direction, max_distance: float) -> dict | None:
        return self._call_sync("worldRayTrace", start, direction, max_distance)

    def find_entities(self, location: Location, radius: float, predicate=None, entity_type: str | None = None) -> list:
        """Find entities near a location, optionally filtered by type and/or predicate."""
        entities = self.entities_near(location, radius)
        if entity_type is not None:
            type_upper = entity_type.upper()
            entities = [e for e in entities if hasattr(e, 'type') and str(e.type).upper() == type_upper]
        if predicate is not None:
            entities = [e for e in entities if predicate(e)]
        return entities

    # --- Async World Edit ---

    async def async_fill(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, material: str, blocks_per_tick: int = 256):
        """Fill a region with a material, spread across ticks to avoid lag."""
        from bridge import server
        coords = []
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    coords.append((x, y, z))
        for i in range(0, len(coords), blocks_per_tick):
            batch = coords[i:i + blocks_per_tick]
            for x, y, z in batch:
                block = Block(world=self, x=x, y=y, z=z)
                block.set_type(material)
            if i + blocks_per_tick < len(coords):
                await server.after(1)

    async def async_replace(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, from_material: str, to_material: str, blocks_per_tick: int = 256):
        """Replace blocks of one material with another, spread across ticks."""
        from bridge import server
        from_upper = from_material.upper()
        coords = []
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    coords.append((x, y, z))
        for i in range(0, len(coords), blocks_per_tick):
            batch = coords[i:i + blocks_per_tick]
            for x, y, z in batch:
                block = Block(world=self, x=x, y=y, z=z)
                if str(block.type).upper() == from_upper:
                    block.set_type(to_material)
            if i + blocks_per_tick < len(coords):
                await server.after(1)

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

    @base_value.setter
    def base_value(self, value: float):
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

    def __mul__(self, scalar):
        if isinstance(scalar, (int, float)):
            return Location(self.x * scalar, self.y * scalar, self.z * scalar, self.world, self.yaw, self.pitch)
        return NotImplemented

    def __truediv__(self, scalar):
        if isinstance(scalar, (int, float)):
            return Location(self.x / scalar, self.y / scalar, self.z / scalar, self.world, self.yaw, self.pitch)
        return NotImplemented

    def normalize(self) -> Location:
        length = (self.x ** 2 + self.y ** 2 + self.z ** 2) ** 0.5
        if length == 0:
            return self.clone()
        return Location(self.x / length, self.y / length, self.z / length, self.world, self.yaw, self.pitch)

    def midpoint(self, other: Location) -> Location:
        return Location((self.x + other.x) / 2, (self.y + other.y) / 2, (self.z + other.z) / 2, self.world, self.yaw, self.pitch)

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

    @data.setter
    def data(self, data: Any):
        return self._call("setBlockData", data)

    @property
    def light_level(self):
        return self._call_sync("getLightLevel")

    @property
    def biome(self):
        return self._call_sync("getBiome")

    @biome.setter
    def biome(self, biome: Biome):
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

    @sign_lines.setter
    def sign_lines(self, lines: list):
        return self._call("setSignLines", lines)

    @property
    def sign_back_lines(self) -> list:
        return self._call_sync("getSignBackLines")

    @sign_back_lines.setter
    def sign_back_lines(self, lines: list):
        return self._call("setSignBackLines", lines)

    def set_sign_line(self, index: int, text: str):
        return self._call("setSignLine", index, text)

    def set_sign_back_line(self, index: int, text: str):
        return self._call("setSignBackLine", index, text)

    @property
    def is_sign_glowing(self) -> bool:
        return self._call_sync("isSignGlowing")

    @is_sign_glowing.setter
    def is_sign_glowing(self, glowing: bool):
        return self._call("setSignGlowing", glowing)

    @property
    def furnace_burn_time(self) -> int:
        return self._call_sync("getFurnaceBurnTime")

    @furnace_burn_time.setter
    def furnace_burn_time(self, ticks: int):
        return self._call("setFurnaceBurnTime", int(ticks))

    @property
    def furnace_cook_time(self) -> int:
        return self._call_sync("getFurnaceCookTime")

    @furnace_cook_time.setter
    def furnace_cook_time(self, ticks: int):
        return self._call("setFurnaceCookTime", int(ticks))

    @property
    def furnace_cook_time_total(self) -> int:
        return self._call_sync("getFurnaceCookTimeTotal")

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

    @property
    def hardness(self) -> float:
        return self._call_sync("getHardness")

    @property
    def blast_resistance(self) -> float:
        return self._call_sync("getBlastResistance")

    @property
    def is_passable(self) -> bool:
        return self._call_sync("isPassable")

    @property
    def is_liquid(self) -> bool:
        return self._call_sync("isLiquid")

    def get_drops(self, tool: Item | None = None) -> list:
        if tool is not None:
            return self._call_sync("getDrops", tool)
        return self._call_sync("getDrops")

    @property
    def drops(self) -> list:
        return self.get_drops()

    # --- PersistentDataContainer ---

    def get_persistent_data(self) -> dict:
        return self._call_sync("getBlockPDC")

    def set_persistent_data(self, key: str, value: str):
        return self._call("setBlockPDC", key, value)

    def remove_persistent_data(self, key: str):
        return self._call("removeBlockPDC", key)


class BlockSnapshot:
    """Capture and restore a region of blocks.

    Example::

        snap = BlockSnapshot.capture(world, 0, 60, 0, 10, 70, 10)
        # ... modify blocks ...
        await snap.restore()  # restore original blocks
    """

    def __init__(self, world: World, blocks: list[dict]):
        self._world = world
        self._blocks = blocks

    @classmethod
    def capture(cls, world: World, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int) -> BlockSnapshot:
        blocks = []
        for x in range(min(x1, x2), max(x1, x2) + 1):
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for z in range(min(z1, z2), max(z1, z2) + 1):
                    block = Block(world=world, x=x, y=y, z=z)
                    blocks.append({"x": x, "y": y, "z": z, "type": block.type})
        return cls(world, blocks)

    async def restore(self, blocks_per_tick: int = 256):
        """Restore captured blocks, spread across ticks."""
        from bridge import server
        for i in range(0, len(self._blocks), blocks_per_tick):
            batch = self._blocks[i:i + blocks_per_tick]
            for data in batch:
                block = Block(world=self._world, x=data["x"], y=data["y"], z=data["z"])
                block.set_type(data["type"])
            if i + blocks_per_tick < len(self._blocks):
                await server.after(1)

    @property
    def blocks(self) -> list[dict]:
        return list(self._blocks)

    def __len__(self) -> int:
        return len(self._blocks)


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

    @property
    def viewers(self) -> list:
        return self._call_sync("getViewers")

    @property
    def type(self):
        return self._call_sync("getType")

    def __getitem__(self, slot: int):
        return self._call_sync("getItem", slot)

    def __setitem__(self, slot: int, item):
        return _connection.call("setItem", [slot, item], handle=self._handle)

    def __iter__(self):
        contents = self.contents
        if contents:
            yield from contents

    def __len__(self) -> int:
        return self.size

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.update()

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

    @amount.setter
    def amount(self, value: int):
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

    @custom_model_data.setter
    def custom_model_data(self, value: int):
        if self._handle is None:
            self.fields["customModelData"] = int(value)
            return self
        return self._call("setCustomModelData", value)

    @property
    def attributes(self):
        return self._call_sync("getAttributes")

    @attributes.setter
    def attributes(self, attributes: List[Dict[str, Any]]):
        if self._handle is None:
            self.fields["attributes"] = list(attributes)
            return self
        return self._call("setAttributes", attributes)

    @property
    def nbt(self):
        return self._call_sync("getNbt")

    @nbt.setter
    def nbt(self, nbt: Dict[str, Any]):
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

    @property
    def durability(self) -> int:
        return self._call_sync("getDurability")

    @durability.setter
    def durability(self, value: int):
        return self._call("setDurability", int(value))

    @property
    def max_durability(self) -> int:
        return self._call_sync("getMaxDurability")

    @property
    def enchantments(self) -> dict:
        return self._call_sync("getEnchantments")

    def add_enchantment(self, enchantment: str, level: int = 1):
        return self._call("addEnchantment", enchantment, level)

    def remove_enchantment(self, enchantment: str):
        return self._call("removeEnchantment", enchantment)

    @property
    def item_flags(self) -> list:
        return self._call_sync("getItemFlags")

    @item_flags.setter
    def item_flags(self, flags: list):
        return self._call("addItemFlags", *flags)

    def add_item_flags(self, *flags: str):
        return self._call("addItemFlags", *flags)

    def remove_item_flags(self, *flags: str):
        return self._call("removeItemFlags", *flags)

    @property
    def is_unbreakable(self) -> bool:
        return self._call_sync("isUnbreakable")

    @is_unbreakable.setter
    def is_unbreakable(self, value: bool):
        return self._call("setUnbreakable", value)

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


class BookBuilder:
    """Build a written book item.

    Example::

        book = (BookBuilder("My Book", "Author")
                .page("Page 1 content")
                .page("Page 2 content")
                .build())
        player.open_book(book)
    """

    def __init__(self, title: str = "Book", author: str = "Server"):
        self._title = title
        self._author = author
        self._pages: list[str] = []

    def title(self, title: str) -> BookBuilder:
        self._title = title
        return self

    def author(self, author: str) -> BookBuilder:
        self._author = author
        return self

    def page(self, content: str) -> BookBuilder:
        self._pages.append(content)
        return self

    def pages(self, *contents: str) -> BookBuilder:
        self._pages.extend(contents)
        return self

    def build(self) -> Item:
        fields: Dict[str, Any] = {
            "type": Material.from_name("WRITTEN_BOOK"),
            "amount": 1,
            "nbt": {
                "title": self._title,
                "author": self._author,
                "pages": list(self._pages),
            },
        }
        return Item(handle=None, fields=fields)


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

    @title.setter
    def title(self, title: str):
        return self._call("setTitle", title)

    @property
    def progress(self):
        return self._call_sync("getProgress")

    @progress.setter
    def progress(self, value: float):
        return self._call("setProgress", value)

    @property
    def color(self):
        return self._call_sync("getColor")

    @color.setter
    def color(self, color: BarColor):
        return self._call("setColor", color)

    @property
    def style(self):
        return self._call_sync("getStyle")

    @style.setter
    def style(self, style: BarStyle):
        return self._call("setStyle", style)

    @property
    def visible(self):
        return self._call_sync("isVisible")

    @visible.setter
    def visible(self, value: bool):
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

    @color.setter
    def color(self, color: Any):
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

    @display_slot.setter
    def display_slot(self, slot: Any):
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


class TextComponent:
    """Builder for rich text (MiniMessage format).

    Example::

        msg = (TextComponent("Hello ")
               .bold("world")
               .text("! ")
               .color("#ff0000", "Click here")
               .click_url("https://example.com")
               .hover("Tooltip text"))
        player.send_message(str(msg))
    """

    def __init__(self, text: str = ""):
        self._parts: list[str] = []
        if text:
            self._parts.append(text)

    def text(self, content: str) -> TextComponent:
        self._parts.append(content)
        return self

    def bold(self, content: str) -> TextComponent:
        self._parts.append(f"<bold>{content}</bold>")
        return self

    def italic(self, content: str) -> TextComponent:
        self._parts.append(f"<italic>{content}</italic>")
        return self

    def underlined(self, content: str) -> TextComponent:
        self._parts.append(f"<underlined>{content}</underlined>")
        return self

    def strikethrough(self, content: str) -> TextComponent:
        self._parts.append(f"<strikethrough>{content}</strikethrough>")
        return self

    def obfuscated(self, content: str) -> TextComponent:
        self._parts.append(f"<obfuscated>{content}</obfuscated>")
        return self

    def color(self, color: str, content: str) -> TextComponent:
        self._parts.append(f"<color:{color}>{content}</color>")
        return self

    def gradient(self, colors: list[str], content: str) -> TextComponent:
        cols = ":".join(colors)
        self._parts.append(f"<gradient:{cols}>{content}</gradient>")
        return self

    def click_url(self, url: str, content: str = "") -> TextComponent:
        if content:
            self._parts.append(f"<click:open_url:'{url}'>{content}</click>")
        elif self._parts:
            last = self._parts.pop()
            self._parts.append(f"<click:open_url:'{url}'>{last}</click>")
        return self

    def click_command(self, command: str, content: str = "") -> TextComponent:
        if content:
            self._parts.append(f"<click:run_command:'{command}'>{content}</click>")
        elif self._parts:
            last = self._parts.pop()
            self._parts.append(f"<click:run_command:'{command}'>{last}</click>")
        return self

    def click_suggest(self, command: str, content: str = "") -> TextComponent:
        if content:
            self._parts.append(f"<click:suggest_command:'{command}'>{content}</click>")
        elif self._parts:
            last = self._parts.pop()
            self._parts.append(f"<click:suggest_command:'{command}'>{last}</click>")
        return self

    def click_copy(self, text: str, content: str = "") -> TextComponent:
        if content:
            self._parts.append(f"<click:copy_to_clipboard:'{text}'>{content}</click>")
        elif self._parts:
            last = self._parts.pop()
            self._parts.append(f"<click:copy_to_clipboard:'{text}'>{last}</click>")
        return self

    def hover(self, hover_text: str, content: str = "") -> TextComponent:
        if content:
            self._parts.append(f"<hover:show_text:'{hover_text}'>{content}</hover>")
        elif self._parts:
            last = self._parts.pop()
            self._parts.append(f"<hover:show_text:'{hover_text}'>{last}</hover>")
        return self

    def newline(self) -> TextComponent:
        self._parts.append("<newline>")
        return self

    def __str__(self) -> str:
        return "".join(self._parts)

    def __repr__(self) -> str:
        return f"TextComponent({str(self)!r})"

    def __add__(self, other) -> TextComponent:
        result = TextComponent()
        result._parts = self._parts.copy()
        if isinstance(other, TextComponent):
            result._parts.extend(other._parts)
        else:
            result._parts.append(str(other))
        return result

class ReflectFacade(ProxyBase):
    """Reflection helper facade."""
    def clazz(self, name: str):
        return self._call("clazz", name)

# Module-level singleton instances
server = Server(target="server")
chat = ChatFacade(target="chat")
reflect = ReflectFacade(target="reflect")
