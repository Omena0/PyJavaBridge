"""Internal utilities — helpers for deserialization, command parsing, config I/O."""
from __future__ import annotations

import inspect
import json
import os
import sys
import uuid
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, cast

from bridge.connection import BridgeConnection
from bridge.errors import BridgeError
from bridge.types import (
    EnumValue, Material, Biome, EffectType, AttributeType, GameMode, Sound,
    Particle, Difficulty, DamageCause, Enchantment, ItemFlag, EquipmentSlot,
    DyeColor, SpawnReason, EntityCategory, EntityPose, BlockFace, TreeType,
    WeatherType, WorldType, Action, ChatColor, EventPriority, TeleportCause,
    InventoryType, Billboard, BarFlag, BarColor, BarStyle, EntityType
)

# Injected by bridge.__init__ during _bootstrap()
_connection:BridgeConnection = None  # type: ignore[assignment]
_player_uuid_cache: Dict[str, str] = {}


def _extract_xyz(pos: tuple[int] | Any) -> tuple:
    """Extract (x, y, z) from a Location, Vector, tuple, list, or namespace."""
    if isinstance(pos, (list, tuple)) and len(pos) >= 3:
        return float(pos[0]), float(pos[1]), float(pos[2])

    from bridge.wrappers import Vector
    if isinstance(pos, Vector):
        return float(pos.x), float(pos.y), float(pos.z)

    raise BridgeError(f"Cannot extract (x, y, z) from {type(pos).__name__}")


def _enum_from(type_name: str, name: str) -> EnumValue:
    mapping: Dict[str, type] = {
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
        "org.bukkit.event.entity.EntityDamageEvent.DamageCause": DamageCause,
        "org.bukkit.enchantments.Enchantment": Enchantment,
        "org.bukkit.inventory.ItemFlag": ItemFlag,
        "org.bukkit.inventory.EquipmentSlot": EquipmentSlot,
        "org.bukkit.DyeColor": DyeColor,
        "org.bukkit.event.entity.CreatureSpawnEvent.SpawnReason": SpawnReason,
        "org.bukkit.entity.EntityCategory": EntityCategory,
        "org.bukkit.entity.Pose": EntityPose,
        "org.bukkit.block.BlockFace": BlockFace,
        "org.bukkit.TreeType": TreeType,
        "org.bukkit.WeatherType": WeatherType,
        "org.bukkit.WorldType": WorldType,
        "org.bukkit.event.block.Action": Action,
        "org.bukkit.ChatColor": ChatColor,
        "org.bukkit.event.EventPriority": EventPriority,
        "org.bukkit.event.player.PlayerTeleportEvent.TeleportCause": TeleportCause,
        "org.bukkit.event.inventory.InventoryType": InventoryType,
        "org.bukkit.entity.Display.Billboard": Billboard,
        "org.bukkit.boss.BarFlag": BarFlag,
    }
    enum_cls = mapping.get(type_name, EnumValue)
    return enum_cls(type_name, name)


def _proxy_from(raw: Dict[str, Any]) -> Any:
    from bridge.wrappers import (
        ProxyBase, Server, Player, Entity, World, Dimension, Location, Block,
        Chunk, Vector, Inventory, Item, Effect, BossBar, Scoreboard, Team,
        Objective, Advancement, AdvancementProgress, Attribute, Event,
    )

    type_name: Optional[str] = raw.get("__type__")
    raw_fields: Any = raw.get("fields") or {}
    fields: Dict[str, Any] = {str(k): _connection._deserialize(v) for k, v in raw_fields.items()}
    handle: Optional[int] = raw.get("__handle__")

    if type_name == "Player":
        name = fields.get("name")
        player_uuid = fields.get("uuid")
        if isinstance(name, str):
            if isinstance(player_uuid, uuid.UUID):
                _player_uuid_cache[name] = str(player_uuid)
            elif isinstance(player_uuid, str):
                _player_uuid_cache[name] = player_uuid

    proxy_map: Dict[str, type] = {
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

        # Last-resort heuristic: if fields look like an entity, treat as Entity
        if proxy_cls is ProxyBase and "uuid" in fields and "type" in fields:
            proxy_cls = Entity

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


# --- TOML writer ---

def _toml_dumps(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    _toml_write_table(data, [], lines)
    return "\n".join(lines) + "\n"


def _toml_write_table(data: Dict[str, Any], path: List[str], lines: List[str]):
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
    if key and all(c.isalnum() or c in "-_" for c in key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_value(value: Any) -> str:
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


# --- Properties I/O ---

def _properties_load(path: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue
            sep = -1
            escaped = False
            for i, ch in enumerate(line):
                if escaped:
                    escaped = False
                    continue
                if ch == "\\":
                    escaped = True
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
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            node[part] = {}
        node = cast(Dict[str, Any], node[part])
    node[parts[-1]] = value


def _properties_parse_value(value: str) -> Any:
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
    lines: List[str] = []
    _properties_flatten(data, [], lines)
    return "\n".join(lines) + "\n"


def _properties_flatten(data: Dict[str, Any], path: List[str], lines: List[str]):
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
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


async def _prime_player_cache():
    from bridge import Player, server
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
