"""High-level helpers — Sidebar, Config, State, Cooldown, display helpers, Menu."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
import weakref
from dataclasses import dataclass

__all__ = [
    "Sidebar",
    "Config",
    "State",
    "Cooldown",
    "Hologram",
    "ActionBarDisplay",
    "BossBarDisplay",
    "BlockDisplay",
    "ItemDisplay",
    "Menu",
    "MenuItem",
    "Paginator",
]
from typing import Any, Callable, Dict, List, Optional, cast

from bridge.errors import BridgeError
from bridge.types import (
    EnumValue, BarColor, BarStyle, EntityType,
)
from bridge.utils import _toml_dumps, _properties_load, _properties_dumps, _deep_merge
from bridge.connection import BridgeConnection

# Injected by bridge.__init__ during _bootstrap()
_connection:BridgeConnection = None  # type: ignore[assignment]

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def print(*args):
    """Redirect print to stderr so stdout stays reserved for IPC."""
    _print(*args, file=sys.stderr)

class ConsolePlayer:
    """Fake player wrapper for console command senders."""
    __slots__ = ("_sender", "fields")

    def __init__(self, sender_obj: Any):
        """Wrap *sender_obj* with player-like fields."""
        self._sender = sender_obj
        self.fields: Dict[str, Any] = {"name": "Console", "uuid": "console"}

    @property
    def name(self):
        """Return the console display name."""
        return "Console"

    @property
    def uuid(self):
        """Return the console pseudo-UUID."""
        return "console"

    def is_op(self):
        """Console is always op."""
        return _connection.completed_call(True)

    def has_permission(self, permission: str):
        """Console has all permissions."""
        return _connection.completed_call(True)

    def send_message(self, message: str):
        """Send a message to the console."""
        from bridge.wrappers import ProxyBase
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
        """No-op: console cannot hear sounds."""
        return _connection.completed_call(None)

    def kick(self, reason: str = ""):
        """No-op: console cannot be kicked."""
        return _connection.completed_call(None)

class Sidebar:
    """Helper for displaying formatted text lines on a sidebar scoreboard."""

    _ENTRIES = [f"\u00a7{c}" for c in "0123456789abcdef"]
    MAX_LINES = len(_ENTRIES)
    __slots__ = ("_board", "_obj", "_teams", "_lines")

    def __init__(self, title: str = ""):
        """Create a sidebar scoreboard with the given title."""
        from bridge.wrappers import Scoreboard

        self._board = Scoreboard.create()
        self._obj = self._board._call_sync("registerNewObjective", "sidebar", "dummy", title)
        self._obj._call_sync("setDisplaySlot", EnumValue("org.bukkit.scoreboard.DisplaySlot", "SIDEBAR"))
        self._teams: dict[int, Any] = {}
        self._lines: dict[int, str] = {}

    def _ensure_slot(self, slot: int):
        """Lazily create the team and score entry for *slot*."""
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
        """Set the text content of a sidebar line."""
        self._ensure_slot(slot)
        self._teams[slot]._call_sync("setPrefix", text)
        self._lines[slot] = text

    def __getitem__(self, slot: int) -> str:
        """Get the current text of a sidebar line."""
        return self._lines.get(slot, "")

    def __delitem__(self, slot: int):
        """Remove a sidebar line and its backing team."""
        if slot in self._teams:
            entry = self._ENTRIES[slot]
            self._teams[slot]._call_sync("unregister")
            self._obj._call_sync("getScore", entry)._call_sync("resetScore")
            del self._teams[slot]
            self._lines.pop(slot, None)

    def show(self, player: Any):
        """Apply this sidebar to the given player."""
        player._call_sync("setScoreboard", self._board)

    @property
    def title(self) -> str:
        """The display name of the sidebar objective."""
        return self._obj._call_sync("getDisplayName")

    @title.setter
    def title(self, value: str):
        """Set the display name of the sidebar objective."""
        self._obj._call_sync("setDisplayName", value)

class Config:
    """Per-script configuration helper with dot-path access and file persistence."""

    _EXTENSIONS = {"toml": ".toml", "json": ".json", "properties": ".properties"}

    def __init__(self, name: Optional[str] = None, defaults: Optional[Dict[str, Any]] = None, format: str = "toml"):
        """Initialise the config, loading from disk and merging defaults."""
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
        """Re-read the config file from disk and merge with defaults."""
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
        """Write the current config data to disk."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                if self._format == "toml":
                    f.write(_toml_dumps(self._data))
                elif self._format == "json":
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
                elif self._format == "properties":
                    f.write(_properties_dumps(self._data))
        except OSError as e:
            raise BridgeError(f"Failed to save config to {self._path}: {e}") from e

    def get(self, path: str, default: Any = None) -> Any:
        """Get a value by dot-separated path, returning *default* if missing."""
        keys = path.split(".")
        data = self._data
        for key in keys:
            if isinstance(data, dict) and key in data:
                data = data[key]
            else:
                return default

        return data

    def get_int(self, path: str, default: int = 0) -> int:
        """Get a value as int."""
        v = self.get(path)
        return int(v) if v is not None else default

    def get_float(self, path: str, default: float = 0.0) -> float:
        """Get a value as float."""
        v = self.get(path)
        return float(v) if v is not None else default

    def get_bool(self, path: str, default: bool = False) -> bool:
        """Get a value as bool, accepting common truthy strings."""
        v = self.get(path)
        if v is None:
            return default

        if isinstance(v, str):
            return v.lower() in ("true", "yes", "1", "on")

        return bool(v)

    def get_list(self, path: str, default: Optional[List[Any]] = None) -> List[Any]:
        """Get a value as a list."""
        v = self.get(path)
        if v is None:
            return default if default is not None else []

        result: List[Any] = list(cast(List[Any], v)) if isinstance(v, (list, tuple)) else [v]
        return result

    def set(self, path: str, value: Any):
        """Set a value by dot-separated path, creating intermediate dicts."""
        keys = path.split(".")
        data = self._data
        for key in keys[:-1]:
            if key not in data or not isinstance(data[key], dict):
                data[key] = {}

            data = data[key]

        data[keys[-1]] = value

    def delete(self, path: str) -> bool:
        """Delete a key by dot-separated path. Returns True if deleted."""
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
        """Dict-style config access."""
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        """Dict-style config mutation."""
        self.set(key, value)

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the config."""
        return self.get(key) is not None

    @property
    def data(self) -> Dict[str, Any]:
        """The raw config data dictionary."""
        return self._data

    @property
    def path(self) -> str:
        """The filesystem path of this config file."""
        return self._path

class State:
    """Simple persistent key-value store that survives script reloads."""

    _instances: list[weakref.ref] = []
    __slots__ = ("_path", "_data")

    def __init__(self, name: Optional[str] = None):
        """Create or load a persistent state file for the current script."""
        script_path = os.environ.get("PYJAVABRIDGE_SCRIPT", "")
        if name is None:
            name = os.path.splitext(os.path.basename(script_path))[0] if script_path else "state"

        scripts_dir = os.path.dirname(script_path) if script_path else "."
        plugin_dir = os.path.dirname(scripts_dir)
        state_dir = os.path.join(plugin_dir, "state")
        os.makedirs(state_dir, exist_ok=True)
        self._path = os.path.join(state_dir, f"{name}.json")
        self._data: Dict[str, Any] = {}
        self.load()
        State._instances.append(weakref.ref(self))

    def load(self):
        """Load the state from its JSON file on disk."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        self._data = loaded
            except Exception:
                pass

    def save(self):
        """Persist the current state to its JSON file."""
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception:
            pass

    def __getitem__(self, key: str) -> Any:
        """Get a state value by key."""
        return self._data[key]

    def __setitem__(self, key: str, value: Any):
        """Set a state value by key."""
        self._data[key] = value

    def __delitem__(self, key: str):
        """Delete a state key."""
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        """Check if a key exists in the state."""
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        """Get a state value with a default fallback."""
        return self._data.get(key, default)

    def keys(self):
        """Return the state's keys."""
        return self._data.keys()

    def values(self):
        """Return the state's values."""
        return self._data.values()

    def items(self):
        """Return the state's key-value pairs."""
        return self._data.items()

    def clear(self):
        """Clear all state data."""
        self._data.clear()

    def update(self, data: dict):
        """Merge *data* into the state."""
        self._data.update(data)

    @property
    def data(self) -> Dict[str, Any]:
        """The raw state data dictionary."""
        return self._data

    @property
    def path(self) -> str:
        """The filesystem path of this state file."""
        return self._path

class Cooldown:
    """Per-player cooldown tracker."""
    __slots__ = ("seconds", "on_expire", "_expiry", "_task_started")

    def __init__(
            self, seconds: float = 1.0,
            on_expire: Optional[Callable[..., Any]] = None,
    ):
        """Create a cooldown tracker with the given duration."""
        self.seconds = seconds
        self.on_expire = on_expire
        self._expiry: Dict[str, float] = {}
        self._task_started = False

    def _get_uuid(self, player: Any) -> str:
        """Extract the UUID string from a player object."""
        if hasattr(player, "fields") and "uuid" in player.fields:
            return player.fields["uuid"]

        return str(player.uuid)

    def check(self, player: Any) -> bool:
        """Return True if the cooldown has expired (and reset it), False otherwise."""
        uid = self._get_uuid(player)
        now = time.time()
        exp = self._expiry.get(uid)
        if exp is not None and now < exp:
            return False

        self._expiry[uid] = now + self.seconds
        if self.on_expire is not None and not self._task_started:
            self._start_expire_task()

        return True

    def remaining(self, player: Any) -> float:
        """Return the seconds remaining on a player's cooldown."""
        uid = self._get_uuid(player)
        exp = self._expiry.get(uid)
        if exp is None:
            return 0.0

        left = exp - time.time()
        return max(0.0, left)

    def reset(self, player: Any):
        """Clear the cooldown for *player*."""
        uid = self._get_uuid(player)
        self._expiry.pop(uid, None)

    def _start_expire_task(self):
        """Start the background task that fires on_expire callbacks."""
        self._task_started = True
        from bridge import Player, server

        async def _check_expiry():
            """Poll for expired cooldowns and invoke callbacks."""
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

                try:
                    await server.after(1)
                except BridgeError:
                    break

        _connection.on("server_boot", lambda _: asyncio.ensure_future(_check_expiry()))

class Hologram:
    """Floating text display using a TextDisplay entity."""
    __slots__ = ("_lines", "_entity")

    def __init__(
            self, location: Any, *lines: str,
            billboard: str = "CENTER",
    ):
        """Spawn a text display entity at *location* with the given lines."""
        from bridge import World
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
        """Send the joined line text to the display entity."""
        text = "\n".join(self._lines) if self._lines else ""
        self._entity._call("text", text)

    def __setitem__(self, index: int, text: str):
        """Set a hologram line by index."""
        if index < 0 or index >= len(self._lines):
            raise IndexError(f"Line index {index} out of range (0-{len(self._lines) - 1})")

        self._lines[index] = text
        self._update_text()

    def __getitem__(self, index: int) -> str:
        """Get a hologram line by index."""
        return self._lines[index]

    def __delitem__(self, index: int):
        """Delete a hologram line."""
        del self._lines[index]
        self._update_text()

    def __len__(self) -> int:
        """Return the number of hologram lines."""
        return len(self._lines)

    def append(self, text: str):
        """Append a new line to the hologram."""
        self._lines.append(text)
        self._update_text()

    def teleport(self, location: Any):
        """Move the hologram to a new location."""
        self._entity.teleport(location)

    def remove(self):
        """Remove the hologram entity from the world."""
        self._entity.remove()

    @property
    def billboard(self) -> str:
        """The billboard mode of the hologram."""
        return self._entity._call_sync("getBillboard")

    @billboard.setter
    def billboard(self, value: str):
        """Set the billboard mode."""
        self._entity._call("setBillboard", value)

    @property
    def see_through(self) -> bool:
        """Whether the hologram text is visible through blocks."""
        return self._entity._call_sync("isSeeThrough")

    @see_through.setter
    def see_through(self, value: bool):
        """Set whether the text is visible through blocks."""
        self._entity._call("setSeeThrough", value)

    @property
    def shadowed(self) -> bool:
        """Whether the hologram text has a shadow."""
        return self._entity._call_sync("isShadowed")

    @shadowed.setter
    def shadowed(self, value: bool):
        """Set whether the text has a shadow."""
        self._entity._call("setShadowed", value)

    @property
    def alignment(self) -> str:
        """The text alignment of the hologram."""
        return self._entity._call_sync("getAlignment")

    @alignment.setter
    def alignment(self, value: str):
        """Set the text alignment."""
        self._entity._call("setAlignment", value)

    @property
    def line_width(self) -> int:
        """The maximum line width before wrapping."""
        return self._entity._call_sync("getLineWidth")

    @line_width.setter
    def line_width(self, value: int):
        """Set the maximum line width."""
        self._entity._call("setLineWidth", value)

    @property
    def background(self) -> Optional[int]:
        """The background colour of the hologram, or None for default."""
        return self._entity._call_sync("getBackgroundColor")

    @background.setter
    def background(self, value: Optional[int]):
        """Set the background colour, or None for default."""
        if value is None:
            self._entity._call("setDefaultBackground", True)
        else:
            self._entity._call("setDefaultBackground", False)
            self._entity._call("setBackgroundColor", value)

class ActionBarDisplay:
    """Persistent action bar text that auto-refreshes."""
    __slots__ = ("_texts", "_players", "_task_started")

    def __init__(self):
        """Create an action bar display manager."""
        self._texts: Dict[str, str] = {}
        self._players: Dict[str, Any] = {}
        self._task_started = False

    def _get_uuid(self, player: Any) -> str:
        """Extract the UUID string from a player object."""
        if hasattr(player, "fields") and "uuid" in player.fields:
            return player.fields["uuid"]

        return str(player.uuid)

    def __setitem__(self, player: Any, text: str):
        """Set the action bar text for *player* and start the refresh loop."""
        uid = self._get_uuid(player)
        self._texts[uid] = text
        self._players[uid] = player
        player.send_action_bar(text)
        if not self._task_started:
            self._start_refresh()

    def __getitem__(self, player: Any) -> str:
        """Get the current action bar text for *player*."""
        uid = self._get_uuid(player)
        return self._texts.get(uid, "")

    def __delitem__(self, player: Any):
        """Stop showing action bar text for *player*."""
        uid = self._get_uuid(player)
        self._texts.pop(uid, None)
        self._players.pop(uid, None)

    def _start_refresh(self):
        """Start the background action bar refresh loop."""
        self._task_started = True
        from bridge import server

        async def _refresh():
            """Periodically re-send action bar text to all tracked players."""
            while _connection is not None:
                for uid, text in list(self._texts.items()):
                    p = self._players.get(uid)
                    if p is not None:
                        try:
                            p.send_action_bar(text)
                        except Exception:
                            pass

                try:
                    await server.after(40)
                except BridgeError:
                    break

        asyncio.ensure_future(_refresh())

class BossBarDisplay:
    """Convenient boss bar display with value/max support and cooldown linking."""
    __slots__ = ("_bar", "_value", "_max", "_linked_task_started")

    def __init__(
            self, title: str = "", color: str = "PINK",
            style: str = "SOLID",
    ):
        """Create a boss bar with the given title, colour, and style."""
        from bridge.wrappers import BossBar
        self._bar = BossBar.create(
            title,
            BarColor.from_name(color.upper()),
            BarStyle.from_name(style.upper()),
        )

        self._value: float = 0.0
        self._max: float = 1.0
        self._linked_task_started = False

    def show(self, player: Any):
        """Show the boss bar to *player*."""
        self._bar.add_player(player)

    def hide(self, player: Any):
        """Hide the boss bar from *player*."""
        self._bar.remove_player(player)

    @property
    def text(self) -> str:
        """The title text of the boss bar."""
        return self._bar.title

    @text.setter
    def text(self, value: str):
        """Set the title text of the boss bar."""
        self._bar.set_title(value)

    @property
    def color(self) -> BarColor:
        """The colour of the boss bar."""
        return self._bar.color

    @color.setter
    def color(self, value: str):
        """Set the boss bar colour by name."""
        self._bar.set_color(BarColor.from_name(value.upper()))

    @property
    def style(self) -> BarStyle:
        """The style of the boss bar."""
        return self._bar.style

    @style.setter
    def style(self, value: str):
        """Set the boss bar style by name."""
        self._bar.set_style(BarStyle.from_name(value.upper()))

    @property
    def value(self) -> float:
        """The current value of the boss bar."""
        return self._value

    @value.setter
    def value(self, v: float):
        """Set the current value and update progress."""
        self._value = v
        self._update_progress()

    @property
    def max(self) -> float:
        """The maximum value of the boss bar."""
        return self._max

    @max.setter
    def max(self, v: float):
        """Set the maximum value and update progress."""
        self._max = max(v, 0.001)
        self._update_progress()

    @property
    def progress(self) -> float:
        """The raw progress fraction (0.0 to 1.0)."""
        return self._bar.progress

    @progress.setter
    def progress(self, v: float):
        """Set the raw progress fraction."""
        self._bar.set_progress(max(0.0, min(1.0, v)))

    @property
    def visible(self) -> bool:
        """Whether the boss bar is visible."""
        return self._bar.visible

    @visible.setter
    def visible(self, v: bool):
        """Set the boss bar visibility."""
        self._bar.set_visible(v)

    def _update_progress(self):
        """Recalculate the bar progress from value/max."""
        self._bar.set_progress(max(0.0, min(1.0, self._value / self._max)))

    def link_cooldown(self, cooldown: Cooldown, player: Any):
        """Deprecated: use link_to instead."""
        print('DeprecationWarning: BossBarDisplay.link_cooldown is deprecated. Please use .link_to instead.')
        self.link_to(cooldown, player)

    def link_to(self, source: Any, player: Any):
        """Link this boss bar to a Cooldown (or any object with .remaining(player) and .seconds)."""
        from bridge import server
        self.show(player)
        self._max = source.seconds

        async def _update():
            """Periodically update the linked boss bar progress."""
            while _connection is not None:
                remaining = source.remaining(player)
                self._value = remaining
                self._update_progress()
                if remaining <= 0:
                    break

                try:
                    await server.after(2)
                except BridgeError:
                    break

        asyncio.ensure_future(_update())

class BlockDisplay:
    """Block display entity wrapper."""
    __slots__ = ("_entity",)

    def __init__(
            self, location: Any, block_type: str,
            billboard: str = "FIXED",
    ):
        """Spawn a block display entity at *location*."""
        from bridge import World
        world: Any = location.world
        if isinstance(world, str):
            world = World(name=world)

        if world is None:
            world = World(name='world')

        self._entity: Any = world._call_sync(
            "spawnEntity", location, EntityType.from_name("BLOCK_DISPLAY"))

        self._entity._call("setBlock", block_type)
        self._entity._call("setBillboard", billboard)

    def teleport(self, location: Any):
        """Move the block display to a new location."""
        self._entity.teleport(location)

    def remove(self):
        """Remove the block display entity from the world."""
        self._entity.remove()

    @property
    def billboard(self) -> str:
        """The billboard mode of the block display."""
        return self._entity._call_sync("getBillboard")

    @billboard.setter
    def billboard(self, value: str):
        """Set the billboard mode of the block display."""
        self._entity._call("setBillboard", value)

class ItemDisplay:
    """Item display entity wrapper."""
    __slots__ = ("_entity",)

    def __init__(
            self, location: Any, item: Any,
            billboard: str = "FIXED",
    ):
        """Spawn an item display entity at *location*."""
        from bridge import World, Item
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

    def teleport(self, location: Any):
        """Move the item display to a new location."""
        self._entity.teleport(location)

    def remove(self):
        """Remove the item display entity from the world."""
        self._entity.remove()

    @property
    def billboard(self) -> str:
        """The billboard mode of the item display."""
        return self._entity._call_sync("getBillboard")

    @billboard.setter
    def billboard(self, value: str):
        """Set the billboard mode of the item display."""
        self._entity._call("setBillboard", value)

class Menu:
    """Interactive chest GUI menu with click handlers."""
    __slots__ = ("_title", "_rows", "_items")

    def __init__(self, title: str = "", rows: int = 3):
        """Create a new menu with the given title and row count."""
        self._title = title
        self._rows = max(1, min(6, rows))
        self._items: Dict[int, MenuItem] = {}

    def __setitem__(self, slot: int, menu_item: MenuItem):
        """Set a menu item at the given slot index."""
        if slot < 0 or slot >= self._rows * 9:
            raise IndexError(f"Slot {slot} out of range (0-{self._rows * 9 - 1})")

        self._items[slot] = menu_item

    def __getitem__(self, slot: int) -> Optional[MenuItem]:
        """Get the menu item at the given slot, or None."""
        return self._items.get(slot)

    def __delitem__(self, slot: int):
        """Remove the menu item at the given slot."""
        self._items.pop(slot, None)

    def fill_border(self, item: Any):
        """Fill the border slots of the menu with the given item."""
        from bridge import Item as WItem
        size = self._rows * 9
        for slot in range(size):
            row, col = divmod(slot, 9)
            if row == 0 or row == self._rows - 1 or col == 0 or col == 8:
                if slot not in self._items:
                    self._items[slot] = MenuItem(item)

    def open(self, player: Any):
        """Open this menu for a player."""
        from bridge import Inventory, Player, Event as WEvent
        _register_menu_events()
        inv = Inventory(size=self._rows * 9, title=self._title)
        for slot, menu_item in self._items.items():
            inv.set_item(slot, menu_item.item)

        p_uuid = str(player.uuid)
        _menu_pending_open.add(p_uuid)
        _open_menus[p_uuid] = self
        inv.open(player)

    @property
    def title(self) -> str:
        """The menu title."""
        return self._title

    @property
    def rows(self) -> int:
        """The number of rows in the menu."""
        return self._rows

@dataclass
class MenuItem:
    """An item in a Menu with an optional click callback."""
    item: Any
    on_click: Optional[Callable[..., Any]] = None

    def __post_init__(self):
        """Convert string item names to Item objects."""
        from bridge import Item
        if isinstance(self.item, str):
            self.item = Item(self.item)

class Paginator(Menu):
    """Menu subclass with multiple pages and navigation buttons."""
    __slots__ = ("_pages", "_page_index")

    def __init__(
        self, title: str = "", rows: int = 3,
        items: Optional[List[MenuItem]] = None,
    ):
        """Create a paginated menu, optionally auto-filling pages from items."""
        super().__init__(title, rows)
        self._pages: List[Dict[int, MenuItem]] = [{}]
        self._page_index: Dict[str, int] = {}  # player uuid -> current page
        usable = (self._rows - 1) * 9  # last row reserved for nav
        if items:
            page: Dict[int, MenuItem] = {}
            slot = 0
            for mi in items:
                page[slot] = mi
                slot += 1
                if slot >= usable:
                    self._pages.append(page)
                    page = {}
                    slot = 0

            if page or not self._pages:
                self._pages.append(page)

            # first page added as empty at init, remove if we filled pages
            if self._pages and not self._pages[0]:
                self._pages.pop(0)

    @property
    def page_count(self) -> int:
        """The total number of pages."""
        return len(self._pages)

    def add_page(self) -> int:
        """Add an empty page and return its index."""
        self._pages.append({})
        return len(self._pages) - 1

    def set_page_item(self, page: int, slot: int, menu_item: MenuItem):
        """Set a menu item at the given slot on a specific page."""
        while page >= len(self._pages):
            self._pages.append({})

        usable = (self._rows - 1) * 9
        if slot < 0 or slot >= usable:
            raise IndexError(f"Slot {slot} out of range (0-{usable - 1})")

        self._pages[page][slot] = menu_item

    def open(self, player: Any, page: int = 0):
        """Open the paginator for a player at the given page."""
        p_uuid = str(player.uuid)
        page = max(0, min(page, len(self._pages) - 1))
        self._page_index[p_uuid] = page
        self._build_page(page)
        super().open(player)

    def _build_page(self, page: int):
        """Populate the menu items dict from the given page index."""
        from bridge import Item as WItem
        self._items.clear()
        if 0 <= page < len(self._pages):
            self._items.update(self._pages[page])

        nav_row_start = (self._rows - 1) * 9
        # Previous button
        if page > 0:
            prev_item = WItem("ARROW", name="<< Previous")
            self._items[nav_row_start] = MenuItem(
                prev_item, on_click=lambda p, e: self.open(p, page - 1))

        # Page indicator
        indicator = WItem("PAPER", name=f"Page {page + 1}/{len(self._pages)}")
        self._items[nav_row_start + 4] = MenuItem(indicator)
        # Next button
        if page < len(self._pages) - 1:
            next_item = WItem("ARROW", name="Next >>")
            self._items[nav_row_start + 8] = MenuItem(
                next_item, on_click=lambda p, e: self.open(p, page + 1))

# Global menu tracking
_open_menus: Dict[str, Menu] = {}
_menu_pending_open: set = set()  # player UUIDs with a menu open in progress
_menu_events_registered = False
_menu_events_lock = threading.Lock()

def _register_menu_events():
    """Register inventory click/close event handlers for menu support."""
    global _menu_events_registered
    with _menu_events_lock:
        if _menu_events_registered:
            return

        _menu_events_registered = True

    from bridge import Player, Event as WEvent

    async def _on_inventory_click(event: Any):
        """Handle inventory click events for open menus."""
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
                try:
                    result = menu_item.on_click(player, event)
                    if hasattr(result, "__await__"):
                        await result

                except Exception as e:
                    print(f"[PyJavaBridge] Menu click handler error: {e}")

    async def _on_inventory_close(event: Any):
        """Handle inventory close events to clean up open menus."""
        player = event.fields.get("player")

        if player is None:
            return

        player_uuid = player.fields.get("uuid") if hasattr(player, "fields") else None

        if player_uuid is None:
            return

        # If a new menu is being opened, this close is from the old one — skip removal
        if player_uuid in _menu_pending_open:
            _menu_pending_open.discard(player_uuid)
            return

        _open_menus.pop(player_uuid, None)

    _connection.on("inventory_click", _on_inventory_click)
    _connection.subscribe("inventory_click", False)
    _connection.on("inventory_close", _on_inventory_close)
    _connection.subscribe("inventory_close", False)

