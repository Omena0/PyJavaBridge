"""Bridge type primitives: enums, RaycastResult, BridgeCall, BridgeMethod."""
from __future__ import annotations

import asyncio
import functools
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, TypeVar

_EV = TypeVar("_EV", bound="EnumValue")

@dataclass
class RaycastResult:
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
    def __getattr__(cls: type[_EV], name: str) -> _EV:
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

    def __eq__(self, other) -> bool:
        if isinstance(other, EnumValue):
            return self.name == other.name and self.type == other.type
        if isinstance(other, str):
            return self.name == other or self.name.lower() == other.lower()
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.type, self.name))

    @classmethod
    def from_name(cls: type[_EV], name: str) -> _EV:
        return cls(cls.TYPE_NAME or cls.__name__, name)

def _bridge_call_done(future: "asyncio.Future[Any]") -> None:
    """Silently consume exceptions on unawaited bridge futures."""
    if future.cancelled():
        return
    exc = future.exception()
    if exc is not None:
        import logging
        logging.getLogger("bridge").debug("Unawaited bridge call failed: %s", exc)

class BridgeCall(Awaitable[Any]):
    """Awaitable wrapper for async bridge calls.

    Accepts either an ``asyncio.Future`` or a coroutine.  Coroutines are
    automatically scheduled as tasks so they run in the background even
    if the caller never ``await``-s the result.
    """
    def __init__(self, future_or_coro):
        if asyncio.iscoroutine(future_or_coro):
            future_or_coro = asyncio.ensure_future(future_or_coro)
        self._future = future_or_coro
        future_or_coro.add_done_callback(_bridge_call_done)

    def __await__(self):
        return self._future.__await__()

    def __repr__(self) -> str:
        if self._future.done():
            return f"BridgeCall(result={self._future.result()!r})"
        return "BridgeCall(pending)"


def async_task(func: Callable[..., Any]) -> Callable[..., BridgeCall]:
    """Decorator: makes an ``async def`` fire-and-forget safe.

    The decorated function, when called, immediately schedules the
    coroutine as a background task and returns a :class:`BridgeCall`.
    Callers can ``await`` the result or ignore it — either way the
    work runs.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> BridgeCall:
        return BridgeCall(func(*args, **kwargs))
    return wrapper

class BridgeMethod:
    """Callable wrapper for late-bound method invocations on proxies."""
    def __init__(self, proxy: Any, name: str):
        self._proxy = proxy
        self._name = name

    def __call__(self, *args: Any, **kwargs: Any) -> "BridgeCall":
        return self._proxy._call(self._name, *args, **kwargs)

class _SyncWait:
    def __init__(self):
        self.event = threading.Event()
        self.result: Any = None
        self.error: Optional[Exception] = None

# --- Enum subclasses ---

class Material(EnumValue):
    """Material, such as diamond, netherite, wood, etc"""
    TYPE_NAME = "org.bukkit.Material"

    def __init__(self, name: str, _name: Optional[str] = None):
        actual = _name if _name is not None else name
        actual = str(actual)
        if actual.lower().startswith("minecraft:"):
            actual = actual[len("minecraft:"):]
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
    TYPE_NAME = "org.bukkit.GameMode"

class Sound(EnumValue):
    TYPE_NAME = "org.bukkit.Sound"

class Particle(EnumValue):
    TYPE_NAME = "org.bukkit.Particle"

class Difficulty(EnumValue):
    TYPE_NAME = "org.bukkit.Difficulty"

class DamageCause(EnumValue):
    TYPE_NAME = "org.bukkit.event.entity.EntityDamageEvent.DamageCause"

class Enchantment(EnumValue):
    TYPE_NAME = "org.bukkit.enchantments.Enchantment"

    @classmethod
    def all(cls) -> "BridgeCall":
        """Return a list of all enchantment names."""
        import bridge
        future = bridge._connection.call("getAllEnchantments", target="server")  # type: ignore[attr-defined]
        async def _wrap():
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
            names = await future
            return [cls(cls.TYPE_NAME, n) for n in names]
        return BridgeCall(asyncio.ensure_future(_wrap()))

class ItemFlag(EnumValue):
    TYPE_NAME = "org.bukkit.inventory.ItemFlag"

class EquipmentSlot(EnumValue):
    TYPE_NAME = "org.bukkit.inventory.EquipmentSlot"

class DyeColor(EnumValue):
    TYPE_NAME = "org.bukkit.DyeColor"

class SpawnReason(EnumValue):
    TYPE_NAME = "org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason"

class EntityCategory(EnumValue):
    TYPE_NAME = "org.bukkit.entity.EntityCategory"

class EntityPose(EnumValue):
    TYPE_NAME = "org.bukkit.entity.Pose"

class BlockFace(EnumValue):
    TYPE_NAME = "org.bukkit.block.BlockFace"

class TreeType(EnumValue):
    TYPE_NAME = "org.bukkit.TreeType"

class WeatherType(EnumValue):
    TYPE_NAME = "org.bukkit.WeatherType"

class WorldType(EnumValue):
    TYPE_NAME = "org.bukkit.WorldType"

class Action(EnumValue):
    TYPE_NAME = "org.bukkit.event.block.Action"

class ChatColor(EnumValue):
    TYPE_NAME = "org.bukkit.ChatColor"

class EventPriority(EnumValue):
    TYPE_NAME = "org.bukkit.event.EventPriority"

class TeleportCause(EnumValue):
    TYPE_NAME = "org.bukkit.event.player.PlayerTeleportEvent.TeleportCause"

class InventoryType(EnumValue):
    TYPE_NAME = "org.bukkit.event.inventory.InventoryType"

class Billboard(EnumValue):
    TYPE_NAME = "org.bukkit.entity.Display.Billboard"

class BarFlag(EnumValue):
    TYPE_NAME = "org.bukkit.boss.BarFlag"

class BarColor(EnumValue):
    TYPE_NAME = "org.bukkit.boss.BarColor"

class BarStyle(EnumValue):
    TYPE_NAME = "org.bukkit.boss.BarStyle"

class EntityType(EnumValue):
    TYPE_NAME = "org.bukkit.entity.EntityType"

