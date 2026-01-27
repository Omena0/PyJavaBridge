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
    "server",
    "chat",
    "reflect",
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
    "ItemMeta",
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
]


class BridgeError(Exception):
    """Bridge-specific runtime error."""
    pass

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

class ProxyBase:
    """Base class for all proxy objects."""
    def __init__(self, handle: Optional[int] = None, type_name: Optional[str] = None, fields: Optional[Dict[str, Any]] = None, target: Optional[str] = None):
        self._handle = handle
        self._type_name = type_name
        self._fields = fields or {}
        self._target = target

    def _call(self, method: str, *args, **kwargs):
        return _connection.call(method=method, args=list(args), handle=self._handle, target=self._target)

    def __getattr__(self, name: str):
        if name in self._fields:
            return self._fields[name]
        return BridgeMethod(self, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            super().__setattr__(name, value)
            return
        _connection.call(method="set_attr", handle=self._handle, field=name, value=value)

    def _field_or_call(self, field: str, method: str):
        if field in self._fields:
            return self._fields[field]
        return self._call(method)

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

    def players(self):
        """Return the online players."""
        return self._call("getOnlinePlayers")

    def worlds(self):
        """Return all loaded worlds."""
        return self._call("getWorlds")

    def world(self, name: str):
        """Get a world by name."""
        return self._call("getWorld", name)

    def scoreboard_manager(self):
        """Get the scoreboard manager."""
        return self._call("getScoreboardManager")

    def create_boss_bar(self, title: str, color: "BarColor", style: "BarStyle"):
        """Create a boss bar."""
        return self._call("createBossBar", title, color, style)

    def get_boss_bars(self):
        """Get all boss bars."""
        return self._call("getBossBars")

    def get_advancement(self, key: str):
        """Get an advancement by namespaced key."""
        return self._call("getAdvancement", key)

    def plugin_manager(self):
        """Get the plugin manager."""
        return self._call("getPluginManager")

    def scheduler(self):
        """Get the server scheduler."""
        return self._call("getScheduler")

    @property
    def name(self):
        return self._fields.get("name") or self._call("getName")

    @property
    def version(self):
        return self._fields.get("version") or self._call("getVersion")

    @property
    def motd(self):
        return self._call("getMotd")

    @property
    def max_players(self):
        return self._call("getMaxPlayers")

class Entity(ProxyBase):
    """Base entity proxy."""
    def teleport(self, location: "Location"):
        """Teleport the entity."""
        return self._call("teleport", location)

    def remove(self):
        """Remove the entity."""
        return self._call("remove")

    def set_velocity(self, vector: "Vector"):
        """Set velocity vector."""
        return self._call("setVelocity", vector)

    def velocity(self):
        """Get velocity vector."""
        return self._call("getVelocity")

    def is_dead(self):
        """Check if entity is dead."""
        return self._call("isDead")

    def is_valid(self):
        """Check if entity is valid."""
        return self._call("isValid")

    def fire_ticks(self):
        """Get fire ticks."""
        return self._call("getFireTicks")

    def set_fire_ticks(self, ticks: int):
        """Set fire ticks."""
        return self._call("setFireTicks", ticks)

    def add_passenger(self, entity: "Entity"):
        """Add a passenger."""
        return self._call("addPassenger", entity)

    def remove_passenger(self, entity: "Entity"):
        """Remove a passenger."""
        return self._call("removePassenger", entity)

    def passengers(self):
        """Get passengers."""
        return self._call("getPassengers")

    def custom_name(self):
        """Get custom name."""
        return self._call("getCustomName")

    def set_custom_name(self, name: str):
        """Set custom name."""
        return self._call("setCustomName", name)

    def set_custom_name_visible(self, value: bool):
        """Show/hide custom name."""
        return self._call("setCustomNameVisible", value)

    @property
    def uuid(self):
        return self._field_or_call("uuid", "getUniqueId")

    @property
    def type(self):
        return self._field_or_call("type", "getType")

    @property
    def location(self):
        return self._field_or_call("location", "getLocation")

    @property
    def world(self):
        return self._field_or_call("world", "getWorld")

class Player(Entity):
    """Player API (inherits Entity)."""
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

    def effects(self):
        """Get active potion effects."""
        return self._call("getActivePotionEffects")

    def set_game_mode(self, mode: "GameMode"):
        """Set the player's game mode."""
        return self._call("setGameMode", mode)

    def scoreboard(self):
        """Get the player's scoreboard."""
        return self._call("getScoreboard")

    def set_scoreboard(self, scoreboard: "Scoreboard"):
        """Set the player's scoreboard."""
        return self._call("setScoreboard", scoreboard)

    def has_permission(self, permission: str):
        """Check a permission."""
        return self._call("hasPermission", permission)

    def is_op(self):
        """Check if the player is op."""
        return self._call("isOp")

    def set_op(self, value: bool):
        """Set op status."""
        return self._call("setOp", value)

    def play_sound(self, sound: "Sound", volume: float = 1.0, pitch: float = 1.0):
        """Play a sound to the player."""
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

    def level(self):
        """Get player level."""
        return self._call("getLevel")

    def set_level(self, level: int):
        """Set player level."""
        return self._call("setLevel", level)

    def exp(self):
        """Get experience progress (0..1)."""
        return self._call("getExp")

    def set_exp(self, exp: float):
        """Set experience progress (0..1)."""
        return self._call("setExp", exp)

    def is_flying(self):
        """Check if the player is flying."""
        return self._call("isFlying")

    def set_flying(self, value: bool):
        """Set flying state."""
        return self._call("setFlying", value)

    def is_sneaking(self):
        """Check if sneaking."""
        return self._call("isSneaking")

    def set_sneaking(self, value: bool):
        """Set sneaking state."""
        return self._call("setSneaking", value)

    def is_sprinting(self):
        """Check if sprinting."""
        return self._call("isSprinting")

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
        return self._field_or_call("name", "getName")

    @property
    def uuid(self):
        return self._field_or_call("uuid", "getUniqueId")

    @property
    def location(self):
        return self._field_or_call("location", "getLocation")

    @property
    def world(self):
        return self._field_or_call("world", "getWorld")

    @property
    def game_mode(self):
        return self._field_or_call("gameMode", "getGameMode")

    @property
    def health(self):
        return self._field_or_call("health", "getHealth")

    @property
    def food_level(self):
        return self._field_or_call("foodLevel", "getFoodLevel")

    @property
    def inventory(self):
        return self._field_or_call("inventory", "getInventory")

class EntityType(EnumValue):
    TYPE_NAME = "org.bukkit.entity.EntityType"

class World(ProxyBase):
    """World API."""
    def block_at(self, x: int, y: int, z: int):
        """Get a block at coordinates."""
        return self._call("getBlockAt", x, y, z)

    def spawn_entity(self, location: "Location", entity_type: EntityType):
        """Spawn an entity by type."""
        return self._call("spawnEntity", location, entity_type)

    def chunk_at(self, x: int, z: int):
        """Get a chunk by coordinates."""
        return self._call("getChunkAt", x, z)

    def spawn(self, location: "Location", entity_cls: type):
        """Spawn an entity by class."""
        return self._call("spawn", location, entity_cls)

    def set_time(self, time: int):
        """Set world time."""
        return self._call("setTime", time)

    def time(self):
        """Get world time."""
        return self._call("getTime")

    def set_difficulty(self, difficulty: "Difficulty"):
        """Set world difficulty."""
        return self._call("setDifficulty", difficulty)

    def difficulty(self):
        """Get world difficulty."""
        return self._call("getDifficulty")

    def players(self):
        """Get players in this world."""
        return self._call("getPlayers")

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

    def spawn_location(self):
        """Get world spawn location."""
        return self._call("getSpawnLocation")

    def set_spawn_location(self, location: "Location"):
        """Set world spawn location."""
        return self._call("setSpawnLocation", location)

    def full_time(self):
        """Get full world time."""
        return self._call("getFullTime")

    def set_full_time(self, time: int):
        """Set full world time."""
        return self._call("setFullTime", time)

    def has_storm(self):
        """Check if storming."""
        return self._call("hasStorm")

    def set_storm(self, value: bool):
        """Set storming."""
        return self._call("setStorm", value)

    def is_thundering(self):
        """Check if thundering."""
        return self._call("isThundering")

    def set_thundering(self, value: bool):
        """Set thundering."""
        return self._call("setThundering", value)

    def weather_duration(self):
        """Get weather duration."""
        return self._call("getWeatherDuration")

    def set_weather_duration(self, ticks: int):
        """Set weather duration."""
        return self._call("setWeatherDuration", ticks)

    def thunder_duration(self):
        """Get thunder duration."""
        return self._call("getThunderDuration")

    def set_thunder_duration(self, ticks: int):
        """Set thunder duration."""
        return self._call("setThunderDuration", ticks)

    @property
    def name(self):
        return self._field_or_call("name", "getName")

    @property
    def uuid(self):
        return self._field_or_call("uuid", "getUID")

    @property
    def environment(self):
        return self._field_or_call("environment", "getEnvironment")

class Dimension(ProxyBase):
    @property
    def name(self):
        return self._field_or_call("name", "getName")

class Location(ProxyBase):
    """Location in a world with yaw and pitch."""
    @property
    def x(self):
        return self._field_or_call("x", "getX")

    @property
    def y(self):
        return self._field_or_call("y", "getY")

    @property
    def z(self):
        return self._field_or_call("z", "getZ")

    @property
    def yaw(self):
        return self._field_or_call("yaw", "getYaw")

    @property
    def pitch(self):
        return self._field_or_call("pitch", "getPitch")

    @property
    def world(self):
        return self._field_or_call("world", "getWorld")

    def add(self, x: float, y: float, z: float):
        """Add coordinates to this location."""
        return self._call("add", x, y, z)

    def clone(self):
        """Clone this location."""
        return self._call("clone")

    def distance(self, other: "Location"):
        """Distance to another location."""
        return self._call("distance", other)

    def distance_squared(self, other: "Location"):
        """Squared distance to another location."""
        return self._call("distanceSquared", other)

    def set_world(self, world: "World"):
        """Set the world reference."""
        return self._call("setWorld", world)

class Block(ProxyBase):
    """Block in the world."""
    def break_naturally(self):
        """Break the block naturally."""
        return self._call("breakNaturally")

    def set_type(self, material: "Material"):
        """Set the block type."""
        return self._call("setType", material)

    def is_solid(self):
        """Check if block is solid."""
        return self._call("getType")._call("isSolid")

    def data(self):
        """Get block data."""
        return self._call("getBlockData")

    def set_data(self, data: Any):
        """Set block data."""
        return self._call("setBlockData", data)

    def light_level(self):
        """Get light level."""
        return self._call("getLightLevel")

    def biome(self):
        """Get biome."""
        return self._call("getBiome")

    def set_biome(self, biome: "Biome"):
        """Set biome."""
        return self._call("setBiome", biome)

    @property
    def x(self):
        return self._field_or_call("x", "getX")

    @property
    def y(self):
        return self._field_or_call("y", "getY")

    @property
    def z(self):
        return self._field_or_call("z", "getZ")

    @property
    def location(self):
        return self._field_or_call("location", "getLocation")

    @property
    def type(self):
        return self._field_or_call("type", "getType")

    @property
    def world(self):
        return self._field_or_call("world", "getWorld")

class Chunk(ProxyBase):
    """Chunk of a world (loadable/unloadable)."""
    @property
    def x(self):
        return self._field_or_call("x", "getX")

    @property
    def z(self):
        return self._field_or_call("z", "getZ")

    @property
    def world(self):
        return self._field_or_call("world", "getWorld")

    def load(self):
        """Load the chunk."""
        return self._call("load")

    def unload(self):
        """Unload the chunk."""
        return self._call("unload")

    def is_loaded(self):
        """Check if the chunk is loaded."""
        return self._call("isLoaded")

class Inventory(ProxyBase):
    """
        Inventory. Can belong to an entity or block entity, or exist as a standalone open inventory screen.
    """
    def add_item(self, item: "Item"):
        """Add an item to the inventory."""
        return self._call("addItem", item)

    def remove_item(self, item: "Item"):
        """Remove an item from the inventory."""
        return self._call("removeItem", item)

    def clear(self):
        """Clear inventory contents."""
        return self._call("clear")

    def first_empty(self):
        """Get first empty slot index."""
        return self._call("firstEmpty")

    def get_item(self, slot: int):
        """Get item in a slot."""
        return self._call("getItem", slot)

    def set_item(self, slot: int, item: "Item"):
        """Set item in a slot."""
        return self._call("setItem", slot, item)

    def contains(self, material: "Material", amount: int = 1):
        """Check if inventory contains a material."""
        return self._call("contains", material, amount)

    @property
    def size(self):
        return self._field_or_call("size", "getSize")

    @property
    def contents(self):
        return self._field_or_call("contents", "getContents")

    @property
    def holder(self):
        return self._field_or_call("holder", "getHolder")

class ItemMeta(ProxyBase):
    """Item metadata proxy."""
    @property
    def has_custom_model_data(self):
        return self._field_or_call("hasCustomModelData", "hasCustomModelData")

    @property
    def custom_model_data(self):
        return self._field_or_call("customModelData", "getCustomModelData")

    def set_custom_model_data(self, value: int):
        """Set custom model data."""
        return self._call("setCustomModelData", value)

    def has_lore(self):
        """Check if lore exists."""
        return self._call("hasLore")

    def lore(self):
        """Get lore lines."""
        return self._call("getLore")

    def set_lore(self, lore: List[str]):
        """Set lore lines."""
        return self._call("setLore", lore)

class Item(ProxyBase):
    """Item (ItemStack) API."""
    @property
    def type(self):
        return self._field_or_call("type", "getType")

    @property
    def amount(self):
        return self._field_or_call("amount", "getAmount")

    def set_amount(self, value: int):
        """Set item amount."""
        return self._call("setAmount", value)

    @property
    def meta(self):
        return self._field_or_call("meta", "getItemMeta")

    def set_meta(self, meta: ItemMeta):
        """Set item meta."""
        return self._call("setItemMeta", meta)

    def clone(self):
        """Clone this item."""
        return self._call("clone")

    def is_similar(self, other: "Item"):
        """Check if items are similar."""
        return self._call("isSimilar", other)

    def max_stack_size(self):
        """Get max stack size."""
        return self._call("getMaxStackSize")

class Material(EnumValue):
    """
        Material, such as diamond, netherite, wood, etc
    """
    TYPE_NAME = "org.bukkit.Material"

class Biome(EnumValue):
    """
        Minecraft biome, e.g. plains, void, ice_spikes, etc
    """
    TYPE_NAME = "org.bukkit.block.Biome"

class Effect(ProxyBase):
    """Active potion effect."""
    @property
    def type(self):
        return self._field_or_call("type", "getType")

    @property
    def duration(self):
        return self._field_or_call("duration", "getDuration")

    @property
    def amplifier(self):
        return self._field_or_call("amplifier", "getAmplifier")

    @property
    def ambient(self):
        return self._field_or_call("ambient", "isAmbient")

    @property
    def particles(self):
        return self._field_or_call("particles", "hasParticles")

    @property
    def icon(self):
        return self._field_or_call("icon", "hasIcon")

    def with_duration(self, duration: int):
        """Return a copy with a different duration."""
        return self._call("withDuration", duration)

    def with_amplifier(self, amplifier: int):
        """Return a copy with a different amplifier."""
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
    def attribute_type(self):
        """Get the attribute type."""
        return self._call("getAttribute")

    def value(self):
        """Get attribute value."""
        return self._call("getValue")

    def base_value(self):
        """Get base value."""
        return self._call("getBaseValue")

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
    @property
    def x(self):
        return self._field_or_call("x", "getX")

    @property
    def y(self):
        return self._field_or_call("y", "getY")

    @property
    def z(self):
        return self._field_or_call("z", "getZ")

class BarColor(EnumValue):
    TYPE_NAME = "org.bukkit.boss.BarColor"

class BarStyle(EnumValue):
    TYPE_NAME = "org.bukkit.boss.BarStyle"

class BossBar(ProxyBase):
    """Boss bar API."""
    def add_player(self, player: Player):
        """Add a player to the boss bar."""
        return self._call("addPlayer", player)

    def remove_player(self, player: Player):
        """Remove a player from the boss bar."""
        return self._call("removePlayer", player)

    def title(self):
        """Get title."""
        return self._call("getTitle")

    def set_title(self, title: str):
        """Set title."""
        return self._call("setTitle", title)

    def progress(self):
        """Get progress (0..1)."""
        return self._call("getProgress")

    def set_progress(self, value: float):
        """Set progress (0..1)."""
        return self._call("setProgress", value)

    def color(self):
        """Get bar color."""
        return self._call("getColor")

    def set_color(self, color: "BarColor"):
        """Set bar color."""
        return self._call("setColor", color)

    def style(self):
        """Get bar style."""
        return self._call("getStyle")

    def set_style(self, style: "BarStyle"):
        """Set bar style."""
        return self._call("setStyle", style)

    def visible(self):
        """Check visibility."""
        return self._call("isVisible")

    def set_visible(self, value: bool):
        """Set visibility."""
        return self._call("setVisible", value)

class Scoreboard(ProxyBase):
    """Scoreboard API."""
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

    def objectives(self):
        """Get all objectives."""
        return self._call("getObjectives")

    def teams(self):
        """Get all teams."""
        return self._call("getTeams")

    def clear_slot(self, slot: Any):
        """Clear display slot."""
        return self._call("clearSlot", slot)

class Team(ProxyBase):
    """Team API."""
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

    def color(self):
        """Get team color."""
        return self._call("getColor")

    def set_color(self, color: Any):
        """Set team color."""
        return self._call("setColor", color)

    def entries(self):
        """Get team entries."""
        return self._call("getEntries")

class Objective(ProxyBase):
    """Objective API."""
    def set_display_name(self, name: str):
        """Set display name."""
        return self._call("setDisplayName", name)

    def get_score(self, entry: str):
        """Get a score for an entry."""
        return self._call("getScore", entry)

    def name(self):
        """Get objective name."""
        return self._call("getName")

    def criteria(self):
        """Get objective criteria."""
        return self._call("getCriteria")

    def display_slot(self):
        """Get display slot."""
        return self._call("getDisplaySlot")

    def set_display_slot(self, slot: Any):
        """Set display slot."""
        return self._call("setDisplaySlot", slot)

class Advancement(ProxyBase):
    """Advancement API."""
    def key(self):
        """Get the advancement key."""
        return self._call("getKey")

class AdvancementProgress(ProxyBase):
    """Advancement progress API."""
    def is_done(self):
        """Check if completed."""
        return self._call("isDone")

    def award_criteria(self, name: str):
        """Award a criterion."""
        return self._call("awardCriteria", name)

    def revoke_criteria(self, name: str):
        """Revoke a criterion."""
        return self._call("revokeCriteria", name)

    def remaining_criteria(self):
        """Get remaining criteria."""
        return self._call("getRemainingCriteria")

    def awarded_criteria(self):
        """Get awarded criteria."""
        return self._call("getAwardedCriteria")

class Potion(ProxyBase):
    """Potion API (legacy)."""
    def type(self):
        """Get potion type."""
        return self._call("getType")

    def level(self):
        """Get potion level."""
        return self._call("getLevel")

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
        self._handlers: Dict[str, List[Callable[[Any], Awaitable[None]]]] = {}
        self._id = 1
        self._socket = socket.create_connection((host, port))
        self._file = self._socket.makefile("rwb")
        self._lock = threading.Lock()
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
        if "field" in kwargs:
            message["field"] = kwargs["field"]
        if "value" in kwargs:
            message["value"] = self._serialize(kwargs["value"])
        self.send(message)
        return BridgeCall(future)

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
        if handlers:
            results = await asyncio.gather(*(handler(payload) for handler in handlers), return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    print(f"[PyJavaBridge] Handler error: {result}")
        event_id = None
        if isinstance(payload, ProxyBase):
            event_id = payload._fields.get("__event_id__")
        if event_id is not None:
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
            return {"__handle__": value._handle}
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
        "ItemMeta": ItemMeta,
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
            elif "Meta" in type_name:
                proxy_cls = ItemMeta
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

        @wraps(handler)
        async def wrapper(event_obj):
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

def _bootstrap(script_path: str):
    global _connection
    port = int(os.environ.get("PYJAVABRIDGE_PORT", "0"))
    if port == 0:
        raise RuntimeError("PYJAVABRIDGE_PORT is not set")
    _connection = BridgeConnection("127.0.0.1", port)
    print(f"[PyJavaBridge] Bootstrapping script {script_path}")
    namespace = {
        "__file__": script_path,
        "__name__": "__main__",
    }
    runpy.run_path(script_path, init_globals=namespace)
    _connection.send({"type": "ready"})
    asyncio.get_event_loop().run_forever()


