"""Live-server test probe for PyJavaBridge.

The Node integration harness copies this file into ``plugins/PyJavaBridge/scripts``.
Each probe case is a coroutine registered with :func:`probe`; the ``/pjbtest``
command runs a case and writes its JSON result so the harness can assert on it.
"""

from __future__ import annotations

import asyncio
import json
import os
import traceback
from typing import Any, Awaitable, Callable, Dict, Optional

from bridge import *  # noqa: F401,F403
from bridge import _connection
from bridge.wrappers import ProxyBase  # noqa: F401

try:
    from bridge.api import has_packet_api
except Exception:  # pragma: no cover - old bridge fallback
    has_packet_api = None


DATA_DIR = os.environ.get("PJB_DATA_DIR", os.path.join(os.getcwd(), "plugins", "PyJavaBridge"))
REQUEST_DIR = os.path.join(DATA_DIR, "test-requests")
RESULT_DIR = os.path.join(DATA_DIR, "test-results")
READY_FILE = os.path.join(DATA_DIR, ".probe-ready")
INFO_FILE = os.path.join(DATA_DIR, ".probe-info.json")

CASES: Dict[str, Callable[[Any, Dict[str, Any]], Awaitable[Any]]] = {}


def probe(name: str) -> Callable:
    """Register a probe case."""
    def decorator(func: Callable) -> Callable:
        CASES[name] = func
        return func
    return decorator


def ok(value: Any = None) -> Any:
    """Return a passing probe result."""
    return value


def assert_true(value: Any, message: str = "expected truthy value") -> Any:
    """Assert a truthy value and return it."""
    if not value:
        raise AssertionError(f"{message}: {value!r}")
    return value


def assert_equal(actual: Any, expected: Any, message: str = "values differ") -> Any:
    """Assert equality and return the actual value."""
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")
    return actual


def assert_between(value: float, low: float, high: float, message: str = "value out of range") -> Any:
    """Assert a numeric range and return the value."""
    if value < low or value > high:
        raise AssertionError(f"{message}: {value!r} not in [{low!r}, {high!r}]")
    return value


def assert_close(actual: float, expected: float, tolerance: float = 1e-6, message: str = "values differ") -> Any:
    """Assert floating-point closeness and return the actual value."""
    if abs(float(actual) - float(expected)) > tolerance:
        raise AssertionError(f"{message}: expected {expected!r} +/- {tolerance!r}, got {actual!r}")
    return actual


def assert_type(value: Any, expected_type: Any, message: str = "unexpected type") -> Any:
    """Assert a type and return the value."""
    if not isinstance(value, expected_type):
        raise AssertionError(f"{message}: expected {expected_type!r}, got {type(value)!r} ({value!r})")
    return value


def as_dict(value: Any) -> Dict[str, Any]:
    """Return a SerializedValue-like object as a plain dict."""
    if isinstance(value, dict):
        return value
    fields = getattr(value, "fields", None)
    if isinstance(fields, dict):
        return fields
    return {}


def as_list(value: Any) -> list:
    """Return list-like bridge values as a Python list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    try:
        return list(value)
    except TypeError:
        return [value]


def player_by_name(name: str) -> Any:
    """Resolve an online player by name."""
    from bridge.wrappers import Player
    return Player(name=name)


def write_json(path: str, value: Any) -> None:
    """Atomically write JSON to *path*."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(value, handle, default=str)
    os.replace(tmp, path)


def read_json(path: str) -> Any:
    """Read JSON from *path*."""
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


async def execute_case(name: str, data: Dict[str, Any], event: Any) -> Any:
    """Run one probe case and return its serialized result."""
    case = CASES.get(name)
    if case is None:
        raise KeyError(f"Unknown probe case: {name}")
    return await case(event, data)


@command("Run a PyJavaBridge integration probe", name="pjbtest")
async def pjbtest(event: Event, case: str, request: str) -> None:
    """Execute a named probe case and report the result to the harness."""
    try:
        data = read_json(os.path.join(REQUEST_DIR, f"{request}.json")).get("data", {})
        value = await execute_case(case, data, event)
        result = {"ok": True, "case": case, "value": value}
    except Exception as exc:  # noqa: BLE001 - probe must report all failures
        result = {
            "ok": False,
            "case": case,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    write_json(os.path.join(RESULT_DIR, f"{request}.json"), result)
    try:
        event.player.send_message(f"PJBIT:{request}:{'ok' if result['ok'] else 'fail'}")
    except Exception:
        print(f"PJBIT:{request}:fail")


@command("Return the probe case registry", name="pjbcases")
async def pjbcases(event: Event) -> None:
    """Send the case list to the requesting player."""
    names = sorted(CASES)
    for index in range(0, len(names), 30):
        event.player.send_message("PJBCASES:" + ",".join(names[index:index + 30]))


@event(non_blocking=True)
async def server_boot(event: Event) -> None:
    """Record capability information once the bridge is ready."""
    packet_api = False
    if has_packet_api is not None:
        try:
            packet_api = bool(await has_packet_api())
        except Exception as exc:
            print(f"[probe] has_packet_api failed: {exc}")
    write_json(INFO_FILE, {
        "packet_api": packet_api,
        "python": os.sys.version,
        "version": str(server.version),
    })


@probe("ping")
async def ping(event: Event, data: Dict[str, Any]) -> Any:
    """Basic liveness check."""
    return {"message": data.get("message", "pong")}


def _write_ready() -> None:
    """Signal to the harness that the probe script finished loading."""
    os.makedirs(DATA_DIR, exist_ok=True)
    write_json(READY_FILE, {"ready": True, "cases": sorted(CASES)})


_write_ready()


# ─────────────────────────────────────────────────────────────────────────────
# Server API tests
# ─────────────────────────────────────────────────────────────────────────────


@probe("server_props")
async def server_props(event: Event, data: Dict[str, Any]) -> Any:
    """Test server attributes and basic methods."""
    players = as_list(server.players)
    worlds = as_list(server.worlds)
    boss_bars = as_list(server.boss_bars)
    structures = as_list(server.structures)

    result = {
        "name": str(server.name),
        "version": str(server.version),
        "motd": str(server.motd),
        "max_players": int(server.max_players),
        "tps": as_list(server.tps),
        "mspt": float(server.mspt),
        "last_tick_time": float(server.last_tick_time),
        "queue_len": int(server.queue_len),
        "players_count": len(players),
        "worlds_count": len(worlds),
        "boss_bars_count": len(boss_bars),
        "structures": structures,
    }

    # broadcast and execute
    await server.broadcast("§7[PJB-TEST] server_props")
    exec_result = await server.execute("time set day")
    result["execute_time_set"] = exec_result

    # get_advancement
    try:
        adv = await server.get_advancement("minecraft:story/root")
        result["has_advancement"] = adv is not None
    except Exception as exc:
        result["get_advancement_error"] = str(exc)

    return result


@probe("server_world")
async def server_world(event: Event, data: Dict[str, Any]) -> Any:
    """Test server.world and world management."""
    world = await server.world("world")
    wname = getattr(world, "name", None)
    if wname is None and hasattr(world, "fields"):
        wname = world.fields.get("name")
    result = {"world_name": wname}

    # create and unload world
    try:
        created = await server.create_world("pjb_test_world", environment="NORMAL", world_type="NORMAL", seed=12345, generate_structures=False)
        c_name = getattr(created, "name", None)
        if c_name is None and hasattr(created, "fields"):
            c_name = created.fields.get("name")
        result["created_world"] = c_name
        await server.after(20)
        unloaded = await server.unload_world("pjb_test_world")
        result["unloaded"] = bool(unloaded)
    except Exception as exc:
        result["world_manage_error"] = str(exc)

    return result


@probe("server_bossbar_create")
async def server_bossbar_create(event: Event, data: Dict[str, Any]) -> Any:
    """Test create_boss_bar."""
    try:
        bar = await server.create_boss_bar("Test Bar", BarColor.RED, BarStyle.SEGMENTED_6)
        title = getattr(bar, "title", None)
        if title is None and hasattr(bar, "fields"):
            title = bar.fields.get("title")
        result = {"bar_created": bar is not None, "title": title}
        # clean up if possible
        try:
            bar.remove()
        except Exception:
            pass
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("server_flush_frame_atomic")
async def server_flush_frame_atomic(event: Event, data: Dict[str, Any]) -> Any:
    """Test frame, atomic, flush."""
    result = {}
    try:
        frame = server.frame()
        result["has_frame"] = frame is not None
    except Exception as exc:
        result["frame_error"] = str(exc)
    try:
        atomic_ctx = server.atomic()
        result["has_atomic"] = atomic_ctx is not None
    except Exception as exc:
        result["atomic_error"] = str(exc)
    try:
        flushed = await server.flush()
        result["flush_count"] = flushed
    except Exception as exc:
        result["flush_error"] = str(exc)
    return result


@probe("server_after")
async def server_after(event: Event, data: Dict[str, Any]) -> Any:
    """Test server.after."""
    try:
        await server.after(5)
        result = {"after_ok": True}
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("server_structures")
async def server_structures(event: Event, data: Dict[str, Any]) -> Any:
    """Test structure save/load/delete."""
    result = {}
    try:
        world = await server.world("world")
        # save a small structure
        name = "pjb_test_struct"
        try:
            saved = await server.save_structure(name, world, 0, -60, 0, 1, -59, 1)
            result["saved"] = saved
        except Exception as exc:
            result["save_error"] = str(exc)
        try:
            loaded = await server.load_structure(name, world, 10, -60, 10, include_entities=False)
            result["loaded"] = loaded
        except Exception as exc:
            result["load_error"] = str(exc)
        try:
            deleted = await server.delete_structure(name)
            result["deleted"] = str(deleted)
        except Exception as exc:
            result["delete_error"] = str(exc)
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("server_chat_broadcast")
async def server_chat_broadcast(event: Event, data: Dict[str, Any]) -> Any:
    """Test chat and server.broadcast."""
    try:
        await chat.broadcast("PJB chat broadcast test")
        result = {"chat_broadcast": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("server_reflect_clazz")
async def server_reflect_clazz(event: Event, data: Dict[str, Any]) -> Any:
    """Test reflect.clazz."""
    try:
        cls = await reflect.clazz("org.bukkit.Material")
        result = {"reflect_ok": cls is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# Player API tests
# ─────────────────────────────────────────────────────────────────────────────


@probe("player_props")
async def player_props(event: Event, data: Dict[str, Any]) -> Any:
    """Test player attributes."""
    p = event.player
    result = {
        "name": getattr(p, "name", None),
        "uuid": str(getattr(p, "uuid", None)),
        "health": getattr(p, "health", None),
        "max_health": getattr(p, "max_health", None),
        "food_level": getattr(p, "food_level", None),
        "game_mode": str(getattr(p, "game_mode", None)),
        "level": getattr(p, "level", None),
        "exp": getattr(p, "exp", None),
        "is_op": getattr(p, "is_op", None),
        "is_flying": getattr(p, "is_flying", None),
        "ping": getattr(p, "ping", None),
        "locale": getattr(p, "locale", None),
        "absorption": getattr(p, "absorption", None),
        "saturation": getattr(p, "saturation", None),
    }
    # location
    try:
        loc = p.location
        result["loc_x"] = getattr(loc, "x", None)
        result["loc_y"] = getattr(loc, "y", None)
        result["loc_z"] = getattr(loc, "z", None)
    except Exception as exc:
        result["loc_error"] = str(exc)
    return result


@probe("player_messages")
async def player_messages(event: Event, data: Dict[str, Any]) -> Any:
    """Test player messaging."""
    p = event.player
    try:
        await p.send_message("PJB test message")
        await p.chat("PJB test chat")
        await p.send_action_bar("PJB action bar")
        result = {"messages_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_teleport")
async def player_teleport(event: Event, data: Dict[str, Any]) -> Any:
    """Test player teleport."""
    p = event.player
    try:
        start = p.location
        sx, sy, sz = getattr(start, "x", 0), getattr(start, "y", -60), getattr(start, "z", 0)
        await p.teleport(Location(start.world, sx + 5, sy + 1, sz + 5))
        await server.after(10)
        end = p.location
        result = {"teleported": True, "ex": getattr(end, "x", None)}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_experience")
async def player_experience(event: Event, data: Dict[str, Any]) -> Any:
    """Test exp/level."""
    p = event.player
    try:
        await p.give_exp(10)
        await p.set_exp(0.5)
        await p.set_level(5)
        result = {"level": p.level, "exp": p.exp}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_health_food")
async def player_health_food(event: Event, data: Dict[str, Any]) -> Any:
    """Test health and food."""
    p = event.player
    try:
        await p.set_health(20)
        await p.set_food_level(20)
        result = {"health": p.health, "food_level": p.food_level}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_gamemode_op_fly")
async def player_gamemode_op_fly(event: Event, data: Dict[str, Any]) -> Any:
    """Test gamemode, op, flying."""
    p = event.player
    try:
        await p.set_game_mode(GameMode.SURVIVAL)
        await p.set_game_mode(GameMode.CREATIVE)
        await p.set_op(True)
        await p.set_flying(True)
        result = {"gamemode": str(p.game_mode), "is_op": p.is_op, "is_flying": p.is_flying}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_sneak_sprint_speed")
async def player_sneak_sprint_speed(event: Event, data: Dict[str, Any]) -> Any:
    """Test sneaking/sprinting/speeds."""
    p = event.player
    try:
        await p.set_sneaking(False)
        await p.set_sprinting(False)
        await p.set_walk_speed(0.2)
        await p.set_fly_speed(0.1)
        result = {"walk_speed": p.walk_speed, "fly_speed": p.fly_speed}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_give_item")
async def player_give_item(event: Event, data: Dict[str, Any]) -> Any:
    """Test giving items."""
    p = event.player
    try:
        item = ItemBuilder(Material.DIAMOND).amount(5).name("§bTest Diamond").build()
        await p.give(item)
        result = {"gave": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_inventory")
async def player_inventory(event: Event, data: Dict[str, Any]) -> Any:
    """Test player inventory access."""
    p = event.player
    try:
        inv = p.inventory
        result = {"inv_size": getattr(inv, "size", None)}
        if inv is not None:
            try:
                item = await inv.get_item(0)
                result["slot0"] = str(item) if item is not None else None
            except Exception as exc:
                result["slot_error"] = str(exc)
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_effects")
async def player_effects(event: Event, data: Dict[str, Any]) -> Any:
    """Test potion effects."""
    p = event.player
    try:
        await p.add_effect(EffectType.SPEED, duration=200, amplifier=1)
        effects = as_list(getattr(p, "effects", []))
        result = {"effects_count": len(effects)}
        try:
            await p.remove_effect(EffectType.SPEED)
            result["removed"] = True
        except Exception as exc:
            result["remove_error"] = str(exc)
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_cooldown")
async def player_cooldown(event: Event, data: Dict[str, Any]) -> Any:
    """Test cooldowns."""
    p = event.player
    try:
        await p.set_cooldown(Material.ENDER_PEARL, 100)
        cd = await p.get_cooldown(Material.ENDER_PEARL)
        result = {"cooldown": cd, "has_cooldown": bool(await p.has_cooldown(Material.ENDER_PEARL))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_title_tablist")
async def player_title_tablist(event: Event, data: Dict[str, Any]) -> Any:
    """Test titles and tab list."""
    p = event.player
    try:
        await p.send_title("Hello", "World", fade_in=10, stay=20, fade_out=10)
        await p.set_tab_list_header_footer("§aHeader", "§bFooter")
        await p.set_tab_list_name("§eTestName")
        result = {"title_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_permissions")
async def player_permissions(event: Event, data: Dict[str, Any]) -> Any:
    """Test permissions/groups."""
    p = event.player
    try:
        has = await p.has_permission("pjb.test")
        groups = as_list(await p.permission_groups)
        primary = await p.primary_group
        result = {"has_perm": has, "groups": groups, "primary_group": primary}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_pdc")
async def player_pdc(event: Event, data: Dict[str, Any]) -> Any:
    """Test persistent data container."""
    p = event.player
    try:
        await p.set_persistent_data("testkey", "testvalue")
        val = await p.get_persistent_data("testkey")
        has = await p.has_persistent_data("testkey")
        await p.remove_persistent_data("testkey")
        result = {"set_get": val == "testvalue", "has": has}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_scoreboard")
async def player_scoreboard(event: Event, data: Dict[str, Any]) -> Any:
    """Test player scoreboard."""
    p = event.player
    try:
        sb = getattr(p, "scoreboard", None)
        result = {"has_scoreboard": sb is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_freeze_vanish")
async def player_freeze_vanish(event: Event, data: Dict[str, Any]) -> Any:
    """Test freeze and vanish."""
    p = event.player
    try:
        await p.freeze()
        frozen = await p.is_frozen()
        await p.unfreeze()
        unfrozen = await p.is_frozen()
        result = {"frozen": frozen, "unfrozen": unfrozen}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_kick")
async def player_kick(event: Event, data: Dict[str, Any]) -> Any:
    """Test kick method exists."""
    p = event.player
    result = {"kick_method": callable(getattr(p, "kick", None))}
    return result



# ─────────────────────────────────────────────────────────────────────────────
# World API tests
# ─────────────────────────────────────────────────────────────────────────────


@probe("world_props")
async def world_props(event: Event, data: Dict[str, Any]) -> Any:
    """Test world attributes."""
    w = await server.world("world")
    result = {
        "name": getattr(w, "name", None),
        "environment": str(getattr(w, "environment", None)),
        "time": getattr(w, "time", None),
        "full_time": getattr(w, "full_time", None),
        "difficulty": str(getattr(w, "difficulty", None)),
        "pvp": getattr(w, "pvp", None),
        "seed": getattr(w, "seed", None),
    }
    try:
        sl = w.spawn_location
        result["spawn_x"] = getattr(sl, "x", None)
    except Exception as exc:
        result["spawn_error"] = str(exc)
    return result


@probe("world_time_weather")
async def world_time_weather(event: Event, data: Dict[str, Any]) -> Any:
    """Test time and weather."""
    w = await server.world("world")
    try:
        w.time = 6000
        await w.set_full_time(1000)
        await w.set_difficulty(Difficulty.NORMAL)
        await w.set_storm(False)
        await w.set_thundering(False)
        result = {"time": w.time, "difficulty": str(w.difficulty)}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_spawn_location")
async def world_spawn_location(event: Event, data: Dict[str, Any]) -> Any:
    """Test spawn location."""
    w = await server.world("world")
    try:
        loc = event.player.location
        await w.set_spawn_location(int(loc.x), int(loc.y), int(loc.z))
        result = {"spawn_set": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_game_rules")
async def world_game_rules(event: Event, data: Dict[str, Any]) -> Any:
    """Test gamerules."""
    w = await server.world("world")
    try:
        await w.set_game_rule("doDaylightCycle", False)
        rule = await w.get_game_rule("doDaylightCycle")
        await w.set_game_rule("doDaylightCycle", True)
        result = {"gamerule": rule}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_block_ops")
async def world_block_ops(event: Event, data: Dict[str, Any]) -> Any:
    """Test block operations."""
    w = await server.world("world")
    p = event.player
    try:
        base = Location(w, p.location.x + 2, -60, p.location.z + 2)
        await w.set_block(base, Material.STONE)
        block = await w.block_at(base)
        result = {"block_type": str(getattr(block, "type", None))}
        await block.set_type(Material.DIAMOND_BLOCK)
        result["changed"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_region_ops")
async def world_region_ops(event: Event, data: Dict[str, Any]) -> Any:
    """Test region fill/replace."""
    w = await server.world("world")
    p = event.player
    try:
        x, z = int(p.location.x) + 10, int(p.location.z) + 10
        await w.fill(x, -59, z, x + 2, -59, z + 2, Material.GLASS)
        await w.replace(x, -59, z, x, -59, z, Material.GLASS, Material.GOLD_BLOCK)
        result = {"fill_replace_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_spawn_entities")
async def world_spawn_entities(event: Event, data: Dict[str, Any]) -> Any:
    """Test spawning."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 3, p.location.y, p.location.z + 3)
        cow = await w.spawn(EntityType.COW, loc)
        result = {"spawned": cow is not None}
        try:
            cow.remove()
        except Exception:
            pass
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_spawn_particle")
async def world_spawn_particle(event: Event, data: Dict[str, Any]) -> Any:
    """Test particles."""
    w = await server.world("world")
    p = event.player
    try:
        loc = p.location
        await w.spawn_particle(Particle.FLAME, loc, 10)
        await w.particle_line(loc, Location(w, loc.x + 5, loc.y, loc.z), Particle.HEART, density=2)
        await w.particle_sphere(loc, 2, Particle.VILLAGER_HAPPY, density=2)
        await w.particle_cube(loc, Location(w, loc.x + 1, loc.y + 1, loc.z + 1), Particle.CRIT, density=2)
        result = {"particles_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_strike_lightning")
async def world_strike_lightning(event: Event, data: Dict[str, Any]) -> Any:
    """Test lightning."""
    w = await server.world("world")
    p = event.player
    try:
        loc = p.location
        await w.strike_lightning_effect(loc)
        result = {"lightning_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_explosion")
async def world_explosion(event: Event, data: Dict[str, Any]) -> Any:
    """Test explosion."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 10, p.location.y, p.location.z + 10)
        await w.create_explosion(loc, 0, False)
        result = {"explosion_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_nearby_entities")
async def world_nearby_entities(event: Event, data: Dict[str, Any]) -> Any:
    """Test entity queries."""
    w = await server.world("world")
    p = event.player
    try:
        nearby = await w.get_nearby_entities(p.location, 16, 16, 16)
        result = {"nearby_count": len(as_list(nearby))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_ray_trace")
async def world_ray_trace(event: Event, data: Dict[str, Any]) -> Any:
    """Test ray trace."""
    w = await server.world("world")
    p = event.player
    try:
        result_rt = await w.ray_trace(p.location, p.location.direction, max_distance=10)
        result = {"has_raytrace": result_rt is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_time_constants")
async def world_time_constants(event: Event, data: Dict[str, Any]) -> Any:
    """Test WorldTime constants."""
    try:
        wt = WorldTime.NOON
        result = {"noon_ticks": wt.ticks}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_block_snapshot")
async def world_block_snapshot(event: Event, data: Dict[str, Any]) -> Any:
    """Test BlockSnapshot."""
    w = await server.world("world")
    p = event.player
    try:
        x, z = int(p.location.x) + 20, int(p.location.z) + 20
        await w.set_block(Location(w, x, -60, z), Material.COBBLESTONE)
        snap = BlockSnapshot.capture(w, x, -60, z, x, -60, z)
        result = {"snapshot_len": len(snap)}
        await w.set_block(Location(w, x, -60, z), Material.STONE)
        await snap.restore()
        result["restored"] = True
    except Exception as exc:
        result["error"] = str(exc)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# Entity and Block API tests
# ─────────────────────────────────────────────────────────────────────────────


@probe("entity_spawn_props")
async def entity_spawn_props(event: Event, data: Dict[str, Any]) -> Any:
    """Test entity attributes."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 4, p.location.y, p.location.z + 4)
        ent = await Entity.spawn(EntityType.SHEEP, loc)
        result = {
            "uuid": str(getattr(ent, "uuid", None)),
            "type": str(getattr(ent, "type", None)),
            "is_alive": getattr(ent, "is_alive", None),
            "is_valid": getattr(ent, "is_valid", None),
        }
        try:
            ent.remove()
        except Exception:
            pass
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("entity_teleport_velocity")
async def entity_teleport_velocity(event: Event, data: Dict[str, Any]) -> Any:
    """Test entity teleport and velocity."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 6, p.location.y, p.location.z + 6)
        ent = await Entity.spawn(EntityType.PIG, loc)
        await ent.teleport(Location(w, p.location.x + 7, p.location.y, p.location.z + 7))
        await ent.set_velocity(Vector(0, 0.5, 0))
        await ent.set_fire_ticks(10)
        result = {"teleport_vel_ok": True}
        try:
            ent.remove()
        except Exception:
            pass
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("entity_damage")
async def entity_damage(event: Event, data: Dict[str, Any]) -> Any:
    """Test entity damage."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 8, p.location.y, p.location.z + 8)
        ent = await Entity.spawn(EntityType.CHICKEN, loc)
        await ent.damage(2, p)
        result = {"damaged": True}
        try:
            ent.remove()
        except Exception:
            pass
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("entity_tags_metadata")
async def entity_tags_metadata(event: Event, data: Dict[str, Any]) -> Any:
    """Test entity tags and metadata."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 9, p.location.y, p.location.z + 9)
        ent = await Entity.spawn(EntityType.RABBIT, loc)
        await ent.add_tag("pjb_test")
        tags = as_list(ent.tags)
        ent.metadata["test"] = "value"
        result = {"tagged": "pjb_test" in tags, "meta": ent.metadata.get("test")}
        try:
            await ent.remove_tag("pjb_test")
            ent.remove()
        except Exception:
            pass
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("block_props")
async def block_props(event: Event, data: Dict[str, Any]) -> Any:
    """Test block attributes."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 11, -60, p.location.z + 11)
        await w.set_block(loc, Material.IRON_BLOCK)
        block = await w.block_at(loc)
        result = {
            "type": str(getattr(block, "type", None)),
            "x": getattr(block, "x", None),
            "y": getattr(block, "y", None),
            "z": getattr(block, "z", None),
            "is_solid": getattr(block, "is_solid", None),
        }
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("block_drops")
async def block_drops(event: Event, data: Dict[str, Any]) -> Any:
    """Test block drops."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 12, -60, p.location.z + 12)
        await w.set_block(loc, Material.DIAMOND_ORE)
        block = await w.block_at(loc)
        drops = as_list(await block.get_drops(p.held_item))
        result = {"drops_count": len(drops)}
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("block_pdc")
async def block_pdc(event: Event, data: Dict[str, Any]) -> Any:
    """Test block PDC."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 13, -60, p.location.z + 13)
        await w.set_block(loc, Material.CHEST)
        block = await w.block_at(loc)
        await block.set_persistent_data("bkey", "bval")
        val = await block.get_persistent_data("bkey")
        result = {"pdc": val == "bval"}
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("chunk_ops")
async def chunk_ops(event: Event, data: Dict[str, Any]) -> Any:
    """Test chunk operations."""
    w = await server.world("world")
    p = event.player
    try:
        chunk = w.chunk_at(p.location)
        result = {"x": getattr(chunk, "x", None), "z": getattr(chunk, "z", None), "is_loaded": getattr(chunk, "is_loaded", None)}
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("location_ops")
async def location_ops(event: Event, data: Dict[str, Any]) -> Any:
    """Test location operations."""
    w = await server.world("world")
    p = event.player
    try:
        loc = p.location.clone()
        loc2 = loc + Vector(1, 0, 0)
        loc3 = loc2 - Vector(0.5, 0, 0)
        dist = loc.distance(loc3)
        result = {"dist": dist}
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("vector_ops")
async def vector_ops(event: Event, data: Dict[str, Any]) -> Any:
    """Test vector operations."""
    try:
        v = Vector(1, 2, 3)
        v2 = v * 2
        v3 = v2.normalize()
        result = {"len": v3.length()}
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("itembuilder")
async def itembuilder(event: Event, data: Dict[str, Any]) -> Any:
    """Test ItemBuilder."""
    try:
        item = ItemBuilder(Material.DIAMOND_SWORD).amount(1).name("§cBlade").lore(["line1", "line2"]).enchant(Enchantment.SHARPNESS, 5).glow().build()
        result = {"name": getattr(item, "name", None), "amount": getattr(item, "amount", None)}
    except Exception as exc:
        result = {"error": str(exc)}
    return result


@probe("inventory_ops")
async def inventory_ops(event: Event, data: Dict[str, Any]) -> Any:
    """Test inventory operations."""
    p = event.player
    try:
        inv = p.inventory
        item = ItemBuilder(Material.EMERALD).amount(3).build()
        await inv.add_item(item)
        has = await inv.contains(Material.EMERALD)
        result = {"has": has}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("recipe")
async def recipe_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test recipe methods exist."""
    try:
        result = {"has_shaped": callable(getattr(Recipe, "shaped", None)), "has_shapeless": callable(getattr(Recipe, "shapeless", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# Effects, UI, Helpers API tests
# ─────────────────────────────────────────────────────────────────────────────


@probe("effect_potion")
async def effect_potion(event: Event, data: Dict[str, Any]) -> Any:
    """Test effects and potions."""
    p = event.player
    try:
        eff = Effect(EffectType.REGENERATION, duration=100, amplifier=0)
        await eff.apply(p)
        result = {"applied": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("attribute")
async def attribute_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test attributes."""
    p = event.player
    try:
        await Attribute.apply(p, AttributeType.GENERIC_MAX_HEALTH, 40)
        attrs = getattr(p, "attributes", {})
        result = {"applied": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("textcomponent")
async def textcomponent_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test TextComponent."""
    try:
        tc = TextComponent("Hello").bold().color("red").click_command("/help")
        s = str(tc)
        result = {"str": len(s) > 0}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("bookbuilder")
async def bookbuilder_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test BookBuilder."""
    try:
        book = BookBuilder("Title", "Author").page("Page 1").build()
        result = {"built": book is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("firework")
async def firework_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Firework."""
    w = await server.world("world")
    p = event.player
    try:
        loc = p.location
        result = {"firework_class": Firework is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("bossbar_ui")
async def bossbar_ui(event: Event, data: Dict[str, Any]) -> Any:
    """Test BossBar and BossBarDisplay."""
    p = event.player
    try:
        bar = BossBar.create("Boss", BarColor.PURPLE, BarStyle.SOLID)
        bar.add_player(p)
        bar.set_progress(0.5)
        bar.remove_player(p)
        bar.remove()
        result = {"bossbar_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("scoreboard_objective_team")
async def scoreboard_objective_team(event: Event, data: Dict[str, Any]) -> Any:
    """Test scoreboard API."""
    try:
        sb = Scoreboard.create("pjb_test_sb")
        obj = Objective.create(sb, "test_obj", "dummy", "Test")
        obj.set_display_name("Test")
        team = Team.create(sb, "pjb_team")
        team.set_color("RED")
        result = {"scoreboard_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("sidebar")
async def sidebar_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Sidebar."""
    p = event.player
    try:
        sb = Sidebar("§6Test Sidebar")
        sb[0] = "§fLine 1"
        sb[1] = "§fLine 2"
        sb.show(p)
        result = {"sidebar_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("menu")
async def menu_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Menu."""
    p = event.player
    try:
        m = Menu("§8Test Menu", rows=3)
        item = MenuItem(ItemBuilder(Material.APPLE).name("Click").build())
        m[0, 0] = item
        result = {"menu_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("actionbar_display")
async def actionbar_display_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test ActionBarDisplay."""
    p = event.player
    try:
        abd = ActionBarDisplay(p)
        abd.text = "Test"
        result = {"actionbar_ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("hologram")
async def hologram_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Hologram."""
    w = await server.world("world")
    p = event.player
    try:
        holo = Hologram(Location(w, p.location.x + 15, p.location.y + 2, p.location.z + 15))
        holo[0] = "§aHello"
        holo.append_line("§bWorld")
        result = {"hologram_ok": True}
        try:
            holo.remove()
        except Exception:
            pass
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("display_entities")
async def display_entities_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test BlockDisplay and ItemDisplay."""
    w = await server.world("world")
    p = event.player
    try:
        bd = BlockDisplay(Location(w, p.location.x + 16, p.location.y + 2, p.location.z + 16), Material.GLOWSTONE)
        result = {"block_display": bd is not None}
        try:
            bd.remove()
        except Exception:
            pass
    except Exception as exc:
        result["block_display_error"] = str(exc)
    try:
        idisp = ItemDisplay(Location(w, p.location.x + 17, p.location.y + 2, p.location.z + 17), Material.DIAMOND)
        result["item_display"] = idisp is not None
        try:
            idisp.remove()
        except Exception:
            pass
    except Exception as exc:
        result["item_display_error"] = str(exc)
    return result


@probe("config_state_cooldown")
async def config_state_cooldown_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Config, State, Cooldown."""
    try:
        cfg = Config("pjbtest")
        cfg.set("test", "value")
        cfg.save()
        cfg2 = Config("pjbtest")
        cfg2.reload()
        result = {"config": cfg2.get("test")}
    except Exception as exc:
        result["config_error"] = str(exc)
    try:
        st = State("pjbtest")
        st.update({"count": 1})
        st.save()
        st2 = State("pjbtest")
        st2.load()
        result["state"] = st2.get("count")
    except Exception as exc:
        result["state_error"] = str(exc)
    try:
        cd = Cooldown(5)
        ok = cd.check()
        result["cooldown_ok"] = ok is not None
    except Exception as exc:
        result["cooldown_error"] = str(exc)
    return result


@probe("paginator")
async def paginator_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Paginator."""
    try:
        pg = Paginator("Test")
        pg.add_page()
        pg.add_page()
        result = {"pages": pg.page_count}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("raycast")
async def raycast_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test raycast function."""
    w = await server.world("world")
    p = event.player
    try:
        res = await raycast(w, p.location, (p.location.yaw, p.location.pitch), max_distance=10)
        result = {"has_result": res is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("enums")
async def enums_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test enum access."""
    try:
        result = {
            "material_diamond": str(Material.DIAMOND),
            "gamemode_creative": str(GameMode.CREATIVE),
            "particle_flame": str(Particle.FLAME),
        }
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("datapack")
async def datapack_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Datapack class."""
    try:
        dp = Datapack("test")
        result = {"has_datapack": dp is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("script_messaging")
async def script_messaging_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test inter-script messaging."""
    try:
        result = {"has_script_send": callable(script_send), "has_get_scripts": callable(get_scripts)}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("event_fire")
async def event_fire_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test fire_event."""
    try:
        fire_event("pjb_test_custom", {"x": 1})
        result = {"fired": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# Decorators and exceptions tests
# ─────────────────────────────────────────────────────────────────────────────


@probe("decorators_presence")
async def decorators_presence(event: Event, data: Dict[str, Any]) -> Any:
    """Test decorators are importable."""
    try:
        result = {
            "has_event": callable(event),
            "has_command": callable(command),
            "has_task": callable(task),
            "has_preserve": callable(preserve),
        }
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("exceptions")
async def exceptions_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test exception classes exist."""
    try:
        result = {
            "BridgeError": issubclass(BridgeError, Exception),
            "PlayerOfflineException": issubclass(PlayerOfflineException, BridgeError),
            "EntityGoneException": issubclass(EntityGoneException, BridgeError),
            "WorldNotLoadedException": issubclass(WorldNotLoadedException, BridgeError),
            "ChunkNotLoadedException": issubclass(ChunkNotLoadedException, BridgeError),
            "InvalidLocationError": issubclass(InvalidLocationError, BridgeError),
            "InvalidMaterialError": issubclass(InvalidMaterialError, BridgeError),
            "InvalidItemError": issubclass(InvalidItemError, BridgeError),
            "MethodNotFoundError": issubclass(MethodNotFoundError, BridgeError),
            "ClassNotFoundError": issubclass(ClassNotFoundError, BridgeError),
            "AccessDeniedError": issubclass(AccessDeniedError, BridgeError),
            "InvalidEventError": issubclass(InvalidEventError, BridgeError),
            "CommandRegistrationError": issubclass(CommandRegistrationError, BridgeError),
            "ConfigError": issubclass(ConfigError, BridgeError),
            "UnsupportedFormatError": issubclass(UnsupportedFormatError, BridgeError),
            "InvalidEnumError": issubclass(InvalidEnumError, BridgeError),
            "SlotOutOfRangeError": issubclass(SlotOutOfRangeError, BridgeError),
            "PermissionError": issubclass(PermissionError, BridgeError),
            "AtomicAbortError": issubclass(AtomicAbortError, BridgeError),
            "TimeoutError": issubclass(TimeoutError, BridgeError),
            "ConnectionError": issubclass(ConnectionError, BridgeError),
        }
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("entity_subtypes")
async def entity_subtypes_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test entity subtype classes exist."""
    try:
        result = {
            "ArmorStand": ArmorStand is not None,
            "Villager": Villager is not None,
            "ItemFrame": ItemFrame is not None,
            "FallingBlock": FallingBlock is not None,
            "AreaEffectCloud": AreaEffectCloud is not None,
        }
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_vanish_unvanish")
async def player_vanish_unvanish(event: Event, data: Dict[str, Any]) -> Any:
    """Test vanish methods."""
    p = event.player
    try:
        await p.vanish()
        v = await p.is_vanished()
        await p.unvanish()
        v2 = await p.is_vanished()
        result = {"vanished": v, "unvanished": v2}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_open_book")
async def player_open_book(event: Event, data: Dict[str, Any]) -> Any:
    """Test open_book."""
    p = event.player
    try:
        book = BookBuilder("Test", "Server").page("Hello").build()
        result = {"open_book_method": callable(getattr(p, "open_book", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("console_player")
async def console_player_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test ConsolePlayer."""
    try:
        result = {"ConsolePlayer": ConsolePlayer is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_at_time")
async def world_at_time_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test world.at_time."""
    w = await server.world("world")
    try:
        result = {"has_at_time": callable(getattr(w, "at_time", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_world_time")
async def world_world_time_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test world.world_time."""
    w = await server.world("world")
    try:
        wt = getattr(w, "world_time", None)
        result = {"has_world_time": wt is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result



# ─────────────────────────────────────────────────────────────────────────────
# Additional coverage
# ─────────────────────────────────────────────────────────────────────────────


@probe("player_send_particle_block_change")
async def player_send_particle_block_change(event: Event, data: Dict[str, Any]) -> Any:
    """Test player particle and block change."""
    p = event.player
    try:
        await p.send_particle(Particle.FLAME, p.location, count=5)
        await p.send_block_change(p.location, Material.GOLD_BLOCK)
        result = {"ok": True}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_set_resource_pack")
async def player_set_resource_pack(event: Event, data: Dict[str, Any]) -> Any:
    """Test set_resource_pack method exists."""
    p = event.player
    try:
        result = {"method_exists": callable(getattr(p, "set_resource_pack", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("entity_remove_passenger")
async def entity_remove_passenger(event: Event, data: Dict[str, Any]) -> Any:
    """Test passenger methods."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 18, p.location.y, p.location.z + 18)
        ent = await Entity.spawn(EntityType.HORSE, loc)
        result = {"has_add_passenger": callable(getattr(ent, "add_passenger", None))}
        try:
            ent.remove()
        except Exception:
            pass
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_get_chunk_at_async")
async def world_get_chunk_at_async(event: Event, data: Dict[str, Any]) -> Any:
    """Test get_chunk_at_async."""
    w = await server.world("world")
    p = event.player
    try:
        chunk = await w.get_chunk_at_async(int(p.location.x) >> 4, int(p.location.z) >> 4)
        result = {"chunk": chunk is not None}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_entities_near_blocks_near")
async def world_entities_near_blocks_near(event: Event, data: Dict[str, Any]) -> Any:
    """Test entities_near and blocks_near."""
    w = await server.world("world")
    p = event.player
    try:
        ents = as_list(w.entities_near(p.location, 10))
        blocks = as_list(w.blocks_near(p.location, 5))
        result = {"ents": len(ents), "blocks": len(blocks)}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_batch_spawn")
async def world_batch_spawn(event: Event, data: Dict[str, Any]) -> Any:
    """Test batch_spawn."""
    w = await server.world("world")
    p = event.player
    try:
        loc = p.location
        spawned = await w.batch_spawn([(EntityType.CHICKEN, Location(w, loc.x + 19, loc.y, loc.z))])
        result = {"count": len(as_list(spawned))}
        for s in as_list(spawned):
            try:
                s.remove()
            except Exception:
                pass
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_find_entities")
async def world_find_entities(event: Event, data: Dict[str, Any]) -> Any:
    """Test find_entities."""
    w = await server.world("world")
    try:
        ents = as_list(await w.find_entities(limit=10))
        result = {"count": len(ents)}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("world_spawn_at_player_spawn_projectile")
async def world_spawn_at_player_spawn_projectile(event: Event, data: Dict[str, Any]) -> Any:
    """Test spawn helpers."""
    w = await server.world("world")
    p = event.player
    try:
        result = {"has_spawn_at_player": callable(getattr(w, "spawn_at_player", None))}
        result["has_spawn_projectile"] = callable(getattr(w, "spawn_projectile", None))
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("location_arithmetic")
async def location_arithmetic(event: Event, data: Dict[str, Any]) -> Any:
    """Test location arithmetic."""
    w = await server.world("world")
    p = event.player
    try:
        loc = p.location
        loc2 = loc * 2
        loc3 = loc2 / 2
        result = {"ok": abs(loc3.x - loc.x) < 0.01}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("inventory_menu_open_close")
async def inventory_menu_open_close(event: Event, data: Dict[str, Any]) -> Any:
    """Test inventory/menu methods."""
    p = event.player
    try:
        inv = p.inventory
        result = {"has_open": callable(getattr(inv, "open", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("block_create")
async def block_create(event: Event, data: Dict[str, Any]) -> Any:
    """Test Block.create."""
    try:
        result = {"has_create": callable(getattr(Block, "create", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("entity_pathfind")
async def entity_pathfind_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test pathfinding methods exist."""
    w = await server.world("world")
    p = event.player
    try:
        loc = Location(w, p.location.x + 20, p.location.y, p.location.z + 20)
        ent = await Entity.spawn(EntityType.ZOMBIE, loc)
        result = {"has_pathfind": callable(getattr(ent, "pathfind_to", None))}
        try:
            ent.remove()
        except Exception:
            pass
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("player_hide_show")
async def player_hide_show_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test hide_player/show_player."""
    p = event.player
    try:
        await p.hide_player(p)
        can = await p.can_see(p)
        await p.show_player(p)
        can2 = await p.can_see(p)
        result = {"hid_self": not can, "showed_self": can2}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("item_methods")
async def item_methods_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Item methods."""
    try:
        result = {"has_drop": callable(getattr(Item, "drop", None)), "has_give": callable(getattr(Item, "give", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("advancement")
async def advancement_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Advancement."""
    try:
        result = {"has_grant": callable(getattr(Advancement, "grant", None))}
    except Exception as exc:
        result["error"] = str(exc)
    return result


@probe("enchantment")
async def enchantment_test(event: Event, data: Dict[str, Any]) -> Any:
    """Test Enchantment enum."""
    try:
        result = {"sharpness": str(Enchantment.SHARPNESS)}
    except Exception as exc:
        result["error"] = str(exc)
    return result

