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
