"""Client mod extension — send capability commands and data to connected clients. [ext]"""
from __future__ import annotations

import sys
from typing import Any, Callable
from types import SimpleNamespace
from bridge.connection import BridgeConnection
from bridge.types import async_task

_connection: BridgeConnection = None  # type: ignore[assignment]

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]

def print(*args):
    """Redirect print to stderr so stdout stays reserved for IPC."""
    _print(*args, file=sys.stderr)

_client_data_subscribed = False
_client_permission_subscribed = False


def _ensure_data_subscription() -> None:
    global _client_data_subscribed
    if _client_data_subscribed:
        return
    _connection.subscribe("client_mod_data", False)
    _client_data_subscribed = True

def _ensure_permission_subscription() -> None:
    global _client_permission_subscribed
    if _client_permission_subscribed:
        return
    _connection.subscribe("client_mod_permission", False)
    _client_permission_subscribed = True

@async_task
async def is_available(player: Any) -> bool:
    """Return True when the target player has an active client-mod session."""
    value = await _connection.call(target="client_mod", method="isAvailable", args=[player])
    return bool(value)

@async_task
async def send_command(player: Any, capability: str, args: dict[str, Any] | None = None,
        handle: str | None = None, timeout_ms: int = 1000) -> dict[str, Any]:
    """Send a capability command to the client mod."""
    result = await _connection.call(
        target="client_mod",
        method="sendCommand",
        args=[player, capability, args or {}, handle, int(timeout_ms)],
    )
    return result if isinstance(result, dict) else {"status": "ok", "result": result}

@async_task
async def send_data(player: Any, channel: str, payload: dict[str, Any] | None = None,
        timeout_ms: int = 1000) -> dict[str, Any]:
    """Send custom data payload to the client mod."""
    result = await _connection.call(
        target="client_mod",
        method="sendData",
        args=[player, channel, payload or {}, int(timeout_ms)],
    )
    return result if isinstance(result, dict) else {"status": "ok", "result": result}


@async_task
async def register_script(player: Any, name: str, source: str, auto_start: bool = True,
        metadata: dict[str, Any] | None = None, timeout_ms: int = 2000) -> dict[str, Any]:
    """Register a client-side script source for execution on the player client."""
    result = await _connection.call(
        target="client_mod",
        method="registerScript",
        args=[player, name, source, bool(auto_start), metadata or {}, int(timeout_ms)],
    )
    return result if isinstance(result, dict) else {"status": "ok", "result": result}

@async_task
async def set_permissions(player: Any, capabilities: list[str], reason: str | None = None,
        remember_prompt: bool = True, timeout_ms: int = 60_000) -> dict[str, Any]:
    """Request capability permissions from a client user."""
    result = await _connection.call(
        target="client_mod",
        method="setPermissions",
        args=[player, capabilities, reason or "", bool(remember_prompt), int(timeout_ms)],
    )
    return result if isinstance(result, dict) else {"status": "ok", "result": result}

@async_task
async def get_permissions(player: Any) -> list[str]:
    """Get currently granted client-mod capabilities for the player session."""
    result = await _connection.call(target="client_mod", method="getPermissions", args=[player])
    if isinstance(result, list):
        return [str(value) for value in result]
    return []

@async_task
async def register_request_data(key: str, value: Any) -> bool:
    """Register server-side data for client request() lookup by key."""
    result = await _connection.call(target="client_mod", method="registerRequestData", args=[key, value])
    return bool(result)

@async_task
async def unregister_request_data(key: str) -> bool:
    """Remove a request() data key registration."""
    result = await _connection.call(target="client_mod", method="unregisterRequestData", args=[key])
    return bool(result)

def on_client_data(handler: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Decorator for custom data events emitted from client mod."""
    _ensure_data_subscription()
    # Wrap the user's handler so it receives an event-like object with
    # `.data` and `.channel` attributes. Unwrap common nested shapes.
    def _wrapper(payload: Any) -> Any:
        try:
            p = payload
            if hasattr(payload, "fields"):
                p = payload.fields

            if isinstance(p, dict):
                inner = p.get("data", p)
                channel = None
                data_obj = None
                if isinstance(inner, dict):
                    if "channel" in inner and "payload" in inner:
                        channel = inner.get("channel")
                        data_obj = inner.get("payload")
                    elif "event" in inner and isinstance(inner.get("data"), dict):
                        nested = inner.get("data")
                        channel = nested.get("channel")
                        data_obj = nested.get("payload")
                    else:
                        data_obj = inner
                else:
                    data_obj = inner

                evt = SimpleNamespace(data=data_obj, channel=channel, raw=payload)
                return handler(evt)
        except Exception:
            pass

        return handler(payload)

    _connection.on("client_mod_data", _wrapper)
    return handler

def on_permission_change(handler: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Decorator for permission decision events emitted from client mod."""
    _ensure_permission_subscription()
    _connection.on("client_mod_permission", handler)
    return handler
