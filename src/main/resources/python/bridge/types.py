"""Bridge type primitives: enums, RaycastResult, BridgeCall, BridgeMethod."""
from __future__ import annotations

import asyncio
import functools
import logging
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, ClassVar, Optional, TypeVar

_EV = TypeVar("_EV", bound="EnumValue")

@dataclass
class RaycastResult:
    """Result of a raycast trace including hit coordinates, entity/block, and origin."""
    x: float
    y: float
    z: float
    entity: Optional[Any]
    block: Optional[Any]
    start_x: float
    start_y: float
    start_z: float
    yaw: float
    pitch: float
    distance: float = 0.0
    hit_face: Optional[str] = None

class _EnumMeta(type):
    """Metaclass enabling class-level attribute access (e.g., Material.DIAMOND)."""
    def __getattr__(cls, name: str) -> "EnumValue":
        """Resolve an uppercase attribute as an enum value."""
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
        """Return the enum name."""
        return self.name

    def __eq__(self, other) -> bool:
        """Check equality by name and type, or by string."""
        if isinstance(other, EnumValue):
            return self.name == other.name and self.type == other.type

        if isinstance(other, str):
            return self.name == other or self.name.lower() == other.lower()

        return NotImplemented

    def __hash__(self) -> int:
        """Hash by type and name."""
        return hash((self.type, self.name))

    _from_name_cache: ClassVar[dict[tuple, EnumValue]] = {}

    @classmethod
    def from_name(cls: type[_EV], name: str) -> _EV:
        """Look up or create an enum value by name."""
        key = (cls, name)
        cached = EnumValue._from_name_cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]

        instance = cls(cls.TYPE_NAME or cls.__name__, name)
        EnumValue._from_name_cache[key] = instance
        return instance

def _bridge_call_done(future: "asyncio.Future[Any]") -> None:
    """Silently consume exceptions on unawaited bridge futures."""
    if future.cancelled():
        return

    exc = future.exception()
    if exc is not None:
        logging.getLogger("bridge").debug("Unawaited bridge call failed: %s", exc)

class BridgeCall(Awaitable[Any]):
    """Awaitable wrapper for async bridge calls.

    Accepts either an ``asyncio.Future`` or a coroutine.  Coroutines are
    automatically scheduled as tasks so they run in the background even
    if the caller never `$1`-s the result.
    """
    def __init__(self, future_or_coro):
        """Wrap a future or coroutine as a BridgeCall."""
        if asyncio.iscoroutine(future_or_coro):
            future_or_coro = asyncio.ensure_future(future_or_coro)

        self._future = future_or_coro
        future_or_coro.add_done_callback(_bridge_call_done)

    def __await__(self):
        """Yield from the underlying future."""
        return self._future.__await__()

    def __repr__(self) -> str:
        """Show the call status and result."""
        if self._future.done():
            return f"BridgeCall(result={self._future.result()!r})"

        return "BridgeCall(pending)"

def async_task(func: Callable[..., Any]) -> Callable[..., BridgeCall]:
    """Decorator: makes an ``async def`` fire-and-forget safe.

    The decorated function, when called, immediately schedules the
    coroutine as a background task and returns a :class:`BridgeCall`.
    Callers can `$1` the result or ignore it — either way the
    work runs.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> BridgeCall:
        """Schedule the coroutine and return a BridgeCall."""
        return BridgeCall(func(*args, **kwargs))

    return wrapper

class BridgeMethod:
    """Callable wrapper for late-bound method invocations on proxies."""
    __slots__ = ("_proxy", "_name")

    def __init__(self, proxy: Any, name: str):
        """Bind a method name to a proxy object."""
        self._proxy = proxy
        self._name = name

    def __call__(self, *args: Any, **kwargs: Any) -> "BridgeCall":
        """Invoke the method on the proxy."""
        return self._proxy._call(self._name, *args, **kwargs)

class _SyncWait:
    """Thread-safe one-shot value container for synchronous bridge calls."""
    __slots__ = ("event", "result", "error")

    def __init__(self):
        """Create a one-shot synchronous waiter."""
        self.event = threading.Event()
        self.result: Any = None
        self.error: Optional[Exception] = None

# --- Enum subclasses ---
_MINECRAFT_PREFIXES = ("minecraft:", "MINECRAFT:", "Minecraft:")

class Material(EnumValue):
    """Material, such as diamond, netherite, wood, etc"""
    TYPE_NAME = "org.bukkit.Material"

    def __init__(self, name: str, _name: Optional[str] = None):
        """Create a Material from a name, stripping 'minecraft:' prefix."""
        actual = _name if _name is not None else name
        actual = str(actual)
        if actual.startswith(_MINECRAFT_PREFIXES):
            actual = actual[10:]  # len("minecraft:") == 10

        super().__init__(self.TYPE_NAME, actual.upper())

class Biome(EnumValue):
    """Minecraft biome, e.g. plains, void, ice_spikes, etc"""
    TYPE_NAME = "org.bukkit.block.Biome"

class EffectType(EnumValue):
    """Potion effect type. e.g. poison, regeneration, strength, etc"""
    TYPE_NAME = "org.bukkit.potion.PotionEffectType"

class AttributeType(EnumValue):
    """Attribute type, e.g. movement speed, base attack damage, etc"""
    TYPE_NAME = "org.bukkit.attribute.Attribute"

class GameMode(EnumValue):
    """Player game mode (SURVIVAL, CREATIVE, ADVENTURE, SPECTATOR)."""
    TYPE_NAME = "org.bukkit.GameMode"

class Sound(EnumValue):
    """Minecraft sound effect, e.g. ENTITY_EXPERIENCE_ORB_PICKUP."""
    TYPE_NAME = "org.bukkit.Sound"

class Particle(EnumValue):
    """Particle effect, e.g. FLAME, HEART, REDSTONE."""
    TYPE_NAME = "org.bukkit.Particle"

class Difficulty(EnumValue):
    """World difficulty (PEACEFUL, EASY, NORMAL, HARD)."""
    TYPE_NAME = "org.bukkit.Difficulty"

class DamageCause(EnumValue):
    """Cause of entity damage, e.g. FALL, FIRE, ENTITY_ATTACK."""
    TYPE_NAME = "org.bukkit.event.entity.EntityDamageEvent.DamageCause"

class Enchantment(EnumValue):
    """Enchantment type, e.g. SHARPNESS, PROTECTION."""
    TYPE_NAME = "org.bukkit.enchantments.Enchantment"

    @classmethod
    def all(cls) -> "BridgeCall":
        """Return a list of all enchantment names."""
        import bridge
        future = bridge._connection.call("getAllEnchantments", target="server")  # type: ignore[attr-defined]
        async def _wrap():
            """Await the future and wrap names as Enchantment instances."""
            names = await future
            return [cls(cls.TYPE_NAME, n) for n in names]

        return BridgeCall(asyncio.ensure_future(_wrap()))

    @classmethod
    def for_item(cls, item) -> "BridgeCall":
        """Return enchantments applicable to a material/item."""
        import bridge
        mat_name = item.name if isinstance(item, (Material, EnumValue)) else str(item)
        future = bridge._connection.call("getEnchantmentsForItem", target="server", args=[mat_name])  # type: ignore[attr-defined]
        async def _wrap():
            """Await the future and wrap names as Enchantment instances."""
            names = await future
            return [cls(cls.TYPE_NAME, n) for n in names]

        return BridgeCall(asyncio.ensure_future(_wrap()))

class ItemFlag(EnumValue):
    """Item display flag controlling which tooltip sections are hidden."""
    TYPE_NAME = "org.bukkit.inventory.ItemFlag"

class EquipmentSlot(EnumValue):
    """Equipment slot on an entity (HAND, OFF_HAND, HEAD, CHEST, LEGS, FEET)."""
    TYPE_NAME = "org.bukkit.inventory.EquipmentSlot"

class DyeColor(EnumValue):
    """Dye or wool colour, e.g. RED, BLUE, WHITE."""
    TYPE_NAME = "org.bukkit.DyeColor"

class SpawnReason(EnumValue):
    """Reason an entity was spawned, e.g. NATURAL, SPAWNER, COMMAND."""
    TYPE_NAME = "org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason"

class EntityCategory(EnumValue):
    """Entity classification category, e.g. UNDEAD, ARTHROPOD, ILLAGER."""
    TYPE_NAME = "org.bukkit.entity.EntityCategory"

class EntityPose(EnumValue):
    """Entity animation pose, e.g. STANDING, CROUCHING, SWIMMING."""
    TYPE_NAME = "org.bukkit.entity.Pose"

class BlockFace(EnumValue):
    """Face of a block (NORTH, SOUTH, EAST, WEST, UP, DOWN)."""
    TYPE_NAME = "org.bukkit.block.BlockFace"

class TreeType(EnumValue):
    """Tree variant for world generation, e.g. OAK, BIRCH, JUNGLE."""
    TYPE_NAME = "org.bukkit.TreeType"

class WeatherType(EnumValue):
    """Weather state (CLEAR, DOWNFALL)."""
    TYPE_NAME = "org.bukkit.WeatherType"

class WorldType(EnumValue):
    """World generator type (NORMAL, FLAT, AMPLIFIED, LARGE_BIOMES)."""
    TYPE_NAME = "org.bukkit.WorldType"

class Action(EnumValue):
    """Block interaction action, e.g. LEFT_CLICK_BLOCK, RIGHT_CLICK_AIR."""
    TYPE_NAME = "org.bukkit.event.block.Action"

class ChatColor(EnumValue):
    """Legacy chat colour code, e.g. RED, GOLD, BOLD."""
    TYPE_NAME = "org.bukkit.ChatColor"

class EventPriority(EnumValue):
    """Bukkit event listener priority (LOWEST through MONITOR)."""
    TYPE_NAME = "org.bukkit.event.EventPriority"

class TeleportCause(EnumValue):
    """Reason for a player teleport, e.g. ENDER_PEARL, COMMAND, PLUGIN."""
    TYPE_NAME = "org.bukkit.event.player.PlayerTeleportEvent.TeleportCause"

class InventoryType(EnumValue):
    """Type of inventory container, e.g. CHEST, FURNACE, ANVIL."""
    TYPE_NAME = "org.bukkit.event.inventory.InventoryType"

class Billboard(EnumValue):
    """Display entity billboard mode (FIXED, VERTICAL, HORIZONTAL, CENTER)."""
    TYPE_NAME = "org.bukkit.entity.Display.Billboard"

class BarFlag(EnumValue):
    """Boss bar rendering flag (DARKEN_SKY, PLAY_BOSS_MUSIC, CREATE_FOG)."""
    TYPE_NAME = "org.bukkit.boss.BarFlag"

class BarColor(EnumValue):
    """Boss bar colour (PINK, BLUE, RED, GREEN, YELLOW, PURPLE, WHITE)."""
    TYPE_NAME = "org.bukkit.boss.BarColor"

class BarStyle(EnumValue):
    """Boss bar visual style (SOLID, SEGMENTED_6, SEGMENTED_10, etc.)."""
    TYPE_NAME = "org.bukkit.boss.BarStyle"

class EntityType(EnumValue):
    """Entity type, e.g. ZOMBIE, CREEPER, ARMOR_STAND."""
    TYPE_NAME = "org.bukkit.entity.EntityType"

