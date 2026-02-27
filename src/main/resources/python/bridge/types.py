"""Bridge type primitives: enums, RaycastResult, BridgeCall, BridgeMethod."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any, Awaitable, Optional, TypeVar

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
        super().__init__(self.TYPE_NAME, str(actual).upper())

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

