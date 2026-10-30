"""Public API helpers: packet API, inter-script communication, raycast."""
from __future__ import annotations

import sys
from typing import Any, Callable, Dict, cast
from bridge.types import async_task

__all__ = [
    "has_packet_api",
    "on_packet_send",
    "on_packet_receive",
    "send_packet",
    "remove_packet_listener",
    "script_send",
    "on_script_message",
    "get_scripts",
    "raycast",
]

from bridge.types import BridgeCall, RaycastResult
from bridge.connection import BridgeConnection

# Injected by bridge.__init__ during _bootstrap()
_connection:BridgeConnection = None  # type: ignore[assignment]

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def print(*args: Any) -> None:
    """Redirect print to stderr so stdout stays reserved for IPC."""
    _print(*args, file=sys.stderr)

def _extract_packet_type(payload: Any) -> str | None:
    """Extract packet_type from bridge payload/event wrappers."""
    if isinstance(payload, dict):
        packet_type = payload.get("packet_type") or payload.get("packetType")
        return str(packet_type) if packet_type is not None else None

    fields = getattr(payload, "fields", None)
    if isinstance(fields, dict):
        packet_type = fields.get("packet_type") or fields.get("packetType")
        return str(packet_type) if packet_type is not None else None

    return None

# --- Packet API (requires ProtocolLib) ---
def has_packet_api() -> BridgeCall:
    """Check if ProtocolLib packet API is available. Returns Awaitable[bool]."""
    return _connection.call("hasPacketApi", target="server")

def on_packet_send(packet_type: str) -> Any:
    """Decorator: listen for outgoing packets of the given type."""
    expected = packet_type.upper()

    def decorator(handler: Callable) -> Callable:
        """Register *handler* for outgoing packets of *packet_type*."""
        def _filtered(payload: Any) -> Any:
            """Run handler only for the requested packet type."""
            actual = _extract_packet_type(payload)
            if actual is None or actual.upper() != expected:
                return None

            return handler(payload)

        _connection.call("listenPacketSend", target="server", args=[packet_type])
        _connection.on("packet_send", _filtered)
        _connection.subscribe("packet_send", False)
        return handler

    return decorator

def on_packet_receive(packet_type: str) -> Any:
    """Decorator: listen for incoming packets of the given type."""
    expected = packet_type.upper()

    def decorator(handler: Callable) -> Callable:
        """Register *handler* for incoming packets of *packet_type*."""
        def _filtered(payload: Any) -> Any:
            """Run handler only for the requested packet type."""
            actual = _extract_packet_type(payload)
            if actual is None or actual.upper() != expected:
                return None

            return handler(payload)

        _connection.call("listenPacketReceive", target="server", args=[packet_type])
        _connection.on("packet_receive", _filtered)
        _connection.subscribe("packet_receive", False)
        return handler

    return decorator

def send_packet(player: Any, packet_type: str, fields: Dict[str, Any] | None = None) -> Any:
    """Send a raw packet to a player. Requires ProtocolLib."""
    return _connection.call("sendPacket", target="server", args=[player, packet_type, fields or {}])

def remove_packet_listener(key: str) -> Any:
    """Remove a packet listener by key (e.g. 'send:ENTITY_VELOCITY')."""
    return _connection.call("removePacketListener", target="server", args=[key])

# --- Inter-script communication ---
def script_send(target: str, data: Any = None) -> None:
    """Send a message to another script (or '*' for all scripts)."""
    _connection.send({"type": "script_message", "target": target, "data": data})

def on_script_message(handler: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Decorator: register a handler for messages from other scripts."""
    _connection.on("script_message", handler)
    return handler

def get_scripts() -> BridgeCall:
    """Get a list of all running script names. Returns Awaitable[list[str]]."""
    request_id = _connection._next_id()
    future = _connection._loop.create_future()
    _connection._pending[request_id] = future
    _connection.send({"type": "get_scripts", "id": request_id})
    return BridgeCall(future)

# --- Raycast ---
@async_task
async def raycast(
    world: Any,
    start: Any,
    direction: tuple[float, float],
    max_distance: float = 64.0,
    ray_size: float = 0.2,
    include_entities: bool = True,
    include_blocks: bool = True,
    ignore_passable: bool = True,
) -> Any:
    """Raycast helper returning RaycastResult or None."""
    from bridge import server

    if isinstance(world, str):
        world = await server.world(world)

    if isinstance(start, (list, tuple)):
        start_xyz = [float(start[0]), float(start[1]), float(start[2])]
    else:
        start_xyz = [float(start.x), float(start.y), float(start.z)]

    yaw, pitch = direction

    result = await _connection.call(
        target="raycast",
        method="trace",
        args=[
            world,
            start_xyz[0],
            start_xyz[1],
            start_xyz[2],
            yaw,
            pitch,
            float(max_distance),
            float(ray_size),
            bool(include_entities),
            bool(include_blocks),
            bool(ignore_passable),
        ]
    )
    if result is None:
        return None

    getter: Callable[..., Any]
    if isinstance(result, dict):
        getter = cast(Dict[str, Any], result).get
    else:
        getter = lambda key, default=None: getattr(result, key, default)  # type: ignore[reportUnknownLambdaType]

    return RaycastResult(
        x=float(getter("x", 0)),
        y=float(getter("y", 0)),
        z=float(getter("z", 0)),
        entity=getter("entity"),
        block=getter("block"),
        start_x=float(getter("startX", 0)),
        start_y=float(getter("startY", 0)),
        start_z=float(getter("startZ", 0)),
        yaw=float(getter("yaw", 0)),
        pitch=float(getter("pitch", 0)),
        distance=float(getter("distance", 0)),
        hit_face=getter("hit_face"),
    )
