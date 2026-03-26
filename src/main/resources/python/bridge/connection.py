"""BridgeConnection — stdin/stdout IPC with the Java plugin."""
from __future__ import annotations

import asyncio
import inspect
import itertools
import json
import os
import struct
import threading
import sys
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast
from bridge.types import async_task

from bridge.errors import (
    ConnectionError, _make_bridge_error,
)
from bridge.types import BridgeCall, EnumValue, _SyncWait

# msgpack / orjson / json — attempt fastest available format
_use_msgpack = False
try:
    import msgpack as _msgpack  # type: ignore[import-not-found]
    _use_msgpack = True

    def _json_dumps(obj: Any) -> bytes:
        """Serialize *obj* to compact msgpack bytes."""
        return _msgpack.packb(obj, use_bin_type=True)

    def _json_loads(data: Any) -> Any:
        """Deserialize msgpack bytes."""
        return _msgpack.unpackb(data, raw=False)

except (ImportError, ModuleNotFoundError):
    try:
        import orjson as _orjson  # type: ignore[import-not-found]

        def _json_dumps(obj: Any) -> bytes:
            """Serialize *obj* to compact JSON bytes via orjson."""
            return _orjson.dumps(obj)

        def _json_loads(data: Any) -> Any:
            """DeSerialize JSON bytes/str via orjson."""
            return _orjson.loads(data)

    except (ImportError, ModuleNotFoundError):

        def _json_dumps(obj: Any) -> bytes:
            """Serialize *obj* to compact JSON bytes via stdlib json."""
            return json.dumps(obj, separators=_JSON_SEPARATORS, ensure_ascii=False).encode("utf-8")

        def _json_loads(data: Any) -> Any:
            """DeSerialize JSON bytes/str via stdlib json."""
            return json.loads(data)

# Reused constant to avoid recreating the tuple on every call
_JSON_SEPARATORS = (",", ":")

# Frozenset for O(1) membership checks in _build_call_message
_RESERVED_KWARGS = frozenset(("field", "value"))

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]

# Pre-allocated frozenset for the common {x,y,z} location/vector check in deserialization
_XYZ_KEYS = frozenset(("x", "y", "z"))
_SYNC_CALL_TIMEOUT_SECONDS = 3.0

# Late-bound imports — avoids circular import overhead on every call.
# Populated once on first use via _ensure_lazy_imports().
import uuid as _uuid_mod
_ProxyBase: type = None # type: ignore[assignment]
_Entity_cls: type = None # type: ignore[assignment]
_Location_cls: type = None # type: ignore[assignment]
_proxy_from_fn: Optional[Callable[..., Any]] = None
_enum_from_fn: Optional[Callable[..., Any]] = None
_State_cls: type = None # type: ignore[assignment]

def _ensure_lazy_imports() -> None:
    """Populate late-bound imports on first use to break circular dependencies."""
    global _ProxyBase, _Entity_cls, _Location_cls, _proxy_from_fn, _enum_from_fn, _State_cls
    if _ProxyBase is not None:
        return

    from bridge.wrappers import ProxyBase, Entity, Location
    from bridge.utils import _proxy_from, _enum_from
    from bridge.helpers import State
    _ProxyBase = ProxyBase
    _Entity_cls = Entity
    _Location_cls = Location
    _proxy_from_fn = _proxy_from
    _enum_from_fn = _enum_from
    _State_cls = State

def print(*args):
    """Redirect print to stderr so stdout stays reserved for IPC."""
    _print(*args, file=sys.stderr)

class _BatchContext:
    """Context manager for batched bridge calls (frame or atomic mode)."""

    def __init__(self, connection: "BridgeConnection", mode: str):
        """Store the connection and batch mode."""
        self._connection = connection
        self._mode = mode

    def __enter__(self):
        """Begin a synchronous batch."""
        self._connection._begin_batch(self._mode)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any):
        """End the synchronous batch."""
        self._connection._end_batch()
        return False

    async def __aenter__(self):
        """Begin an async batch."""
        self._connection._begin_batch(self._mode)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any):
        """End the async batch, flushing on success."""
        self._connection._end_batch()
        if exc_type is None:
            await self._connection.flush()

        return False

class BridgeConnection:
    """Stdin/stdout bridge connection and dispatcher."""

    def __init__(self):
        """Set up the event loop, IPC channels, and start the reader thread."""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

        self._pending: Dict[int, "asyncio.Future[Any]"] = {}
        self._pending_sync: Dict[int, _SyncWait] = {}
        self._handlers: Dict[str, List[Callable[[Any], Awaitable[None]]]] = {}
        self._tab_complete_handlers: Dict[str, Callable[..., Any]] = {}

        self._id_counter = itertools.count(1)
        self._stdin = sys.stdin.buffer
        self._stdout = sys.stdout.buffer
        self._lock = threading.Lock()

        self._batch_stack: List[str] = []
        self._batch_messages: List[Dict[str, Any]] = []
        self._batch_futures: List["asyncio.Future[Any]"] = []

        self._release_queue: set[int] = set()
        self._release_lock = threading.Lock()

        self._stdin_fd = sys.stdin.fileno()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        fmt = "msgpack" if _use_msgpack else "json"
        print(f"[PyJavaBridge] Connected via stdin/stdout ({fmt})")
        # Handshake MUST be sent as JSON since Java hasn't switched format yet
        handshake = json.dumps({"type": "handshake", "format": fmt}).encode("utf-8")
        header = struct.pack("!I", len(handshake))
        with self._lock:
            self._stdout.write(header + handshake)
            self._stdout.flush()

    def subscribe(self, event_name: str, once_per_tick: bool, priority: str | EnumValue = "NORMAL", throttle_ms: int = 0, non_blocking: bool = False):
        """Subscribe to a Bukkit event on the Java side.

        Adds support for an optional `non_blocking` flag that scripts may
        pass (legacy compatibility). When provided the flag will be sent
        to the Java plugin to influence dispatch behaviour.
        """
        priority_name = priority.name if isinstance(priority, EnumValue) else str(priority)
        print(f"[PyJavaBridge] Subscribing to {event_name} once_per_tick={once_per_tick} priority={priority_name} throttle_ms={throttle_ms} non_blocking={non_blocking}")
        self.send({
            "type": "subscribe",
            "event": event_name,
            "once_per_tick": once_per_tick,
            "priority": priority_name,
            "throttle_ms": throttle_ms,
            "non_blocking": non_blocking,
        })

    def register_command(self, name: str, permission: Optional[str] = None, completions: Optional[dict] = None, has_tab_complete: bool = False):
        """Register a command name with the server."""
        msg: Dict[str, Any] = {"type": "register_command", "name": name}
        if permission is not None:
            msg["permission"] = permission

        if completions is not None:
            msg["completions"] = {str(k): v for k, v in completions.items()}

        if has_tab_complete:
            msg["has_tab_complete"] = True

        self.send(msg)

    def on(self, event_name: str, handler: Callable[[Any], Awaitable[None]]):
        """Register a handler for the given event name."""
        self._handlers.setdefault(event_name, []).append(handler)

    def off(self, event_name: str, handler: Callable[[Any], Awaitable[None]]):
        """Remove a previously registered event handler."""
        handlers = self._handlers.get(event_name)
        if handlers:
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    def _build_call_message(self, request_id: int, method: str, args: Optional[List[Any]], handle: Optional[int], target: Optional[str], kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Construct the JSON message dict for a bridge call."""
        message: Dict[str, Any] = {
            "type": "call",
            "id": request_id,
            "method": method,
            "args_list": [self._serialize(arg) for arg in args] if args else [],
        }
        if handle is not None:
            message["handle"] = handle

        if target is not None:
            message["target"] = target

        if kwargs:
            extra_args = {k: self._serialize(v) for k, v in kwargs.items() if k not in _RESERVED_KWARGS}
            if extra_args:
                message["args"] = extra_args

            if "field" in kwargs:
                message["field"] = kwargs["field"]

            if "value" in kwargs:
                message["value"] = self._serialize(kwargs["value"])

        return message

    def call(self, method: str, args: Optional[List[Any]] = None, handle: Optional[int] = None, target: Optional[str] = None, **kwargs: Any) -> BridgeCall:
        """Send an async call to the Java plugin and return a BridgeCall."""
        self._maybe_flush_releases()
        request_id = self._next_id()
        future = self._loop.create_future()
        self._pending[request_id] = future
        message = self._build_call_message(request_id, method, args, handle, target, kwargs)
        if self._batch_stack:
            self._batch_messages.append(message)
            self._batch_futures.append(future)
            return BridgeCall(future)

        self.send(message)
        return BridgeCall(future)

    def call_fire_forget(self, method: str, args: Optional[List[Any]] = None, handle: Optional[int] = None, target: Optional[str] = None, **kwargs: Any) -> None:
        """Send a call without waiting for a response (fire-and-forget)."""
        self._maybe_flush_releases()
        request_id = self._next_id()
        message = self._build_call_message(request_id, method, args, handle, target, kwargs)
        message["no_response"] = True
        if self._batch_stack:
            self._batch_messages.append(message)
            return

        self.send(message)

    def call_sync(self, method: str, args: Optional[List[Any]] = None, handle: Optional[int] = None, target: Optional[str] = None, **kwargs: Any) -> Any:
        """Send a synchronous call that blocks the current thread until a response."""
        request_id = self._next_id()
        wait = _SyncWait()
        self._pending_sync[request_id] = wait
        message = self._build_call_message(request_id, method, args, handle, target, kwargs)
        self.send(message)
        # Never block forever on sync calls; connection loss/reload can otherwise hang shutdown.
        signaled = wait.event.wait(timeout=_SYNC_CALL_TIMEOUT_SECONDS)
        if not signaled:
            self._pending_sync.pop(request_id, None)
            raise ConnectionError(
                f"Synchronous bridge call timed out after {_SYNC_CALL_TIMEOUT_SECONDS:.1f}s: {method}"
            )
        if wait.error is not None:
            raise wait.error

        return wait.result

    def call_sync_raw(self, msg_type: str, **fields: Any) -> Any:
        """Send a raw typed message and wait synchronously for response."""
        request_id = self._next_id()
        wait = _SyncWait()
        self._pending_sync[request_id] = wait
        msg: Dict[str, Any] = {"type": msg_type, "id": request_id}
        msg.update(fields)
        self.send(msg)
        signaled = wait.event.wait(timeout=_SYNC_CALL_TIMEOUT_SECONDS)
        if not signaled:
            self._pending_sync.pop(request_id, None)
            raise ConnectionError(
                f"Synchronous bridge message timed out after {_SYNC_CALL_TIMEOUT_SECONDS:.1f}s: {msg_type}"
            )
        if wait.error is not None:
            raise wait.error

        return wait.result

    def send_fire_forget(self, msg_type: str, **fields: Any) -> None:
        """Send a message without waiting for a response (fire-and-forget)."""
        msg: Dict[str, Any] = {"type": msg_type}
        msg.update(fields)
        self.send(msg)

    def fire_event(self, event_name: str, data: Dict[str, Any] | None = None) -> None:
        """Fire a custom event that all scripts (including this one) can listen to."""
        self.send_fire_forget("fire_event", event=event_name, data=data or {})

    def wait(self, ticks: int = 1) -> BridgeCall:
        """Wait for the given number of server ticks."""
        request_id = self._next_id()
        future = self._loop.create_future()
        self._pending[request_id] = future
        self.send({"type": "wait", "id": request_id, "ticks": int(ticks)})
        return BridgeCall(future)

    def _begin_batch(self, mode: str):
        """Push a batch mode onto the stack."""
        self._batch_stack.append(mode)

    def _end_batch(self):
        """Pop the current batch mode from the stack."""
        if self._batch_stack:
            self._batch_stack.pop()

    def _current_batch_mode(self) -> Optional[str]:
        """Return 'atomic' or 'frame' depending on the active batch stack."""
        if not self._batch_stack:
            return None

        return "atomic" if "atomic" in self._batch_stack else "frame"

    @async_task
    async def flush(self):
        """Flush all queued batch messages to the bridge."""
        if not self._batch_messages:
            return None

        mode = self._current_batch_mode()
        messages = self._batch_messages
        futures = self._batch_futures

        self._batch_messages = []
        self._batch_futures = []
        self.send({"type": "call_batch", "atomic": mode == "atomic", "messages": messages})

        results = await asyncio.gather(*futures, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                raise result

        return None

    def frame(self):
        """Return a context manager for a frame-batched call sequence."""
        return _BatchContext(self, "frame")

    def atomic(self):
        """Return a context manager for an atomic-batched call sequence."""
        return _BatchContext(self, "atomic")

    def send(self, message: Dict[str, Any]):
        """Write a length-prefixed JSON message to stdout."""
        data = _json_dumps(message)
        header = struct.pack("!I", len(data))
        with self._lock:
            self._stdout.write(header + data)
            self._stdout.flush()

    def _cancel_release(self, handle: int):
        """Remove a handle from the pending release queue (re-acquired before flush)."""
        with self._release_lock:
            self._release_queue.discard(handle)

    def _queue_release(self, handle: int):
        """Enqueue a handle for deferred release, flushing when the queue is full."""
        with self._release_lock:
            self._release_queue.add(handle)
            if len(self._release_queue) >= 64:
                self._flush_releases_locked()

    def _flush_releases_locked(self):
        """Flush queued handle releases. Must be called with _release_lock held."""
        if not self._release_queue:
            return

        handles = list(self._release_queue)

        self._release_queue.clear()
        try:
            self.send({"type": "release", "handles": handles})
        except Exception:
            pass

    def _flush_releases(self):
        """Flush queued handle releases with lock."""
        with self._release_lock:
            self._flush_releases_locked()

    def _maybe_flush_releases(self):
        """Flush releases only if the queue is worth flushing."""
        if len(self._release_queue) >= 16:
            self._flush_releases()

    def completed_call(self, result: Any):
        """Return a BridgeCall that is already resolved with *result*."""
        future = self._loop.create_future()
        future.set_result(result)
        return BridgeCall(future)

    def _stop_reader(self):
        """Interrupt the reader thread and wait for it to exit."""
        try:
            os.close(self._stdin_fd)
        except OSError:
            pass

        self._thread.join(timeout=2)

    def _read_exact(self, size: int) -> Optional[bytes]:
        """Read exactly *size* bytes from stdin, returning None on EOF."""
        try:
            data = os.read(self._stdin_fd, size)
            if not data:
                return None

            if len(data) == size:
                return data

            # Partial read — accumulate remaining
            buf = bytearray(data)

            while len(buf) < size:
                chunk = os.read(self._stdin_fd, size - len(buf))
                if not chunk:
                    return None

                buf.extend(chunk)

            return bytes(buf)
        except OSError:
            return None

    def _reader(self):
        """Background thread: read framed messages from stdin and dispatch them."""
        try:
            while True:
                header = self._read_exact(4)

                if not header:
                    break

                try:
                    length = struct.unpack("!I", header)[0]
                    payload = self._read_exact(length)
                    if payload is None:

                        break

                    message = _json_loads(payload)
                    msg_type = message.get("type")

                    if msg_type in ("return", "error"):
                        msg_id = message.get("id")

                        if msg_id is not None:
                            wait = self._pending_sync.pop(msg_id, None)

                            if wait is not None:
                                if msg_type == "return":
                                    wait.result = self._deserialize(message.get("result"))
                                else:
                                    wait.error = _make_bridge_error(message)

                                wait.event.set()
                                continue

                    self._loop.call_soon_threadsafe(self._handle_message, message)

                except Exception as exc:
                    self._loop.call_soon_threadsafe(self._handle_reader_error, exc)
                    break

        finally:
            disconnect_error = ConnectionError("Connection lost")

            for wait in list(self._pending_sync.values()):
                wait.error = disconnect_error
                wait.event.set()

            self._pending_sync.clear()
            self._loop.call_soon_threadsafe(self._handle_reader_error, disconnect_error)

    def _handle_message(self, message: Dict[str, Any]):
        """Dispatch a decoded message to the appropriate handler on the event loop."""
        _ensure_lazy_imports()
        msg_type = message.get("type")

        if msg_type == "return":
            msg_id: int = message.get("id") # pyright: ignore[reportAssignmentType]
            future = self._pending.pop(msg_id, None)

            if future is not None and not future.done():
                future.set_result(self._deserialize(message.get("result")))

        elif msg_type == "error":
            msg_id: int = message.get("id") # pyright: ignore[reportAssignmentType]
            future = self._pending.pop(msg_id, None)

            if future is not None and not future.done():
                future.set_exception(_make_bridge_error(message))

        elif msg_type == "event":
            event_name = message.get("event")

            print(f"[PyJavaBridge] Event received: {event_name}")
            payload = self._deserialize(message.get("payload"))

            if isinstance(payload, dict) and "event" in payload:
                p = cast(Dict[str, Any], payload)
                event_obj = p.get("event")

                if event_obj and isinstance(event_obj, _ProxyBase):
                    if "id" in p:
                        event_obj.fields["__event_id__"] = p.get("id")

                    for key, value in p.items():
                        if key != "event":
                            event_obj.fields[key] = value

                    payload = event_obj

            if event_name is not None:
                asyncio.create_task(self._dispatch_event(event_name, payload))

        elif msg_type == "event_batch":
            event_name = message.get("event")
            for raw_payload in message.get("payloads", []):
                payload = self._deserialize(raw_payload)

                if isinstance(payload, dict) and "event" in payload:
                    p = cast(Dict[str, Any], payload)
                    event_obj = p.get("event")

                    if event_obj and isinstance(event_obj, _ProxyBase):
                        if "id" in p:
                            event_obj.fields["__event_id__"] = p.get("id")

                        for key, value in p.items():
                            if key != "event":
                                event_obj.fields[key] = value

                        payload = event_obj

                if event_name is not None:
                    asyncio.create_task(self._dispatch_event(event_name, payload))

        elif msg_type == "tab_complete":
            asyncio.create_task(self._handle_tab_complete(message))

        elif msg_type == "shutdown":
            asyncio.create_task(self._handle_shutdown())

    async def _handle_tab_complete(self, message: Dict[str, Any]):
        """Handle a tab-completion request from the Java side."""
        request_id = message.get("id")
        command_name = message.get("command", "")
        args = message.get("args", [])
        handler = self._tab_complete_handlers.get(command_name)
        results: List[str] = []
        if handler is not None:
            try:
                sender_data = self._deserialize(message.get("sender"))
                player_data = self._deserialize(message.get("player")) if "player" in message else None
                event_obj = sender_data
                if player_data is not None:
                    event_obj = player_data

                result = handler(event_obj, args)
                if inspect.isawaitable(result):
                    result = await result

                if isinstance(result, (list, tuple)):
                    results = [str(x) for x in result]
            except Exception as exc:
                print(f"[PyJavaBridge] Tab complete handler error: {exc}")

        self.send({"type": "tab_complete_response", "id": request_id, "results": results})

    def register_tab_complete(self, command_name: str, handler: Callable[..., Any]):
        """Register a dynamic tab completion handler for a command."""
        self._tab_complete_handlers[command_name] = handler

    async def _dispatch_event(self, event_name: str, payload: Any):
        """Run all handlers for *event_name* and send back event results."""
        handlers = list(self._handlers.get(event_name, []))
        event_id = None
        if isinstance(payload, _ProxyBase):
            event_id = payload.fields.get("__event_id__")

        # Fast path: no handlers — immediately ack the event so Java doesn't block
        if not handlers:
            if event_id is not None:
                self.send({"type": "event_done", "id": event_id})

            return

        # Command events originate from Bukkit command handling and can deadlock
        # if handlers synchronously call back into Java before event_done is sent.
        if event_name.startswith("command_"):
            async def _run_detached(handler: Callable[[Any], Any]) -> None:
                try:
                    result = handler(payload)
                    if inspect.isawaitable(result):
                        await result
                except Exception as exc:
                    print(f"[PyJavaBridge] Handler error: {exc}")

            for handler in handlers:
                asyncio.create_task(_run_detached(handler))

            if event_id is not None:
                self.send({"type": "event_done", "id": event_id})
            return

        results: List[Any] = []
        try:
            if len(handlers) == 1:
                # Fast path: single handler — skip list/gather overhead
                try:
                    result = handlers[0](payload)
                    if inspect.isawaitable(result):
                        result = await result

                    results.append(result)
                except Exception as exc:
                    results.append(exc)
            else:
                awaitables: List[Awaitable[Any]] = []
                for handler in handlers:
                    try:
                        result = handler(payload)
                    except Exception as exc:
                        results.append(exc)
                        continue

                    if inspect.isawaitable(result):
                        awaitables.append(result)
                    else:
                        results.append(result)

                if awaitables:
                    gathered = await asyncio.gather(*awaitables, return_exceptions=True)
                    results.extend(gathered)

            for result in results:
                if isinstance(result, Exception):
                    print(f"[PyJavaBridge] Handler error: {result}")

        finally:
            if event_id is not None:
                if handlers:
                    override_text = None
                    override_damage = None
                    override_respawn = None
                    override_target = None

                    is_damage_event = isinstance(payload, _ProxyBase) and "damage" in payload.fields
                    is_respawn_event = event_name in ("player_respawn",)
                    is_target_event = event_name in ("entity_target", "entity_target_living_entity")

                    for result in results:
                        if isinstance(result, _Entity_cls):
                            if is_target_event:
                                override_target = result

                        elif isinstance(result, _Location_cls):
                            if is_respawn_event:
                                override_respawn = result

                        elif isinstance(result, str):
                            override_text = result

                        elif is_damage_event and isinstance(result, (int, float)) and not isinstance(result, bool):
                            override_damage = float(result)

                    if override_text is not None:
                        self.send({"type": "event_result", "id": event_id, "result": override_text, "result_type": "chat"})

                    if override_damage is not None:
                        self.send({"type": "event_result", "id": event_id, "result": override_damage, "result_type": "damage"})

                    if override_respawn is not None:
                        self.send({"type": "event_result", "id": event_id, "result": self._serialize(override_respawn), "result_type": "respawn"})

                    if override_target is not None:
                        self.send({"type": "event_result", "id": event_id, "result": self._serialize(override_target), "result_type": "target"})

                self.send({"type": "event_done", "id": event_id})

    async def _handle_shutdown(self):
        """Handle server shutdown."""
        _ensure_lazy_imports()
        try:
            # Prevent proxy __del__ methods from issuing bridge calls while tearing down.
            import bridge.wrappers as _wrappers
            mark = getattr(_wrappers, "_mark_shutting_down", None)
            if callable(mark):
                mark()
        except Exception:
            pass

        try:
            for ref in _State_cls._instances:
                try:
                    state = ref()
                    if state is not None:
                        state.save()
                except Exception:
                    pass

            await self._dispatch_event("shutdown", SimpleNamespace(fields={}))
        except Exception as e:
            print(f"[PyJavaBridge] Shutdown handler error: {e}")

        finally:
            try:
                self.send({"type": "shutdown_ack"})
            except Exception:
                pass

            self._stop_reader()
            self._loop.stop()

    def _handle_reader_error(self, exc: Exception):
        """Fail all pending futures with the given exception."""
        for future in self._pending.values():
            if not future.done():
                future.set_exception(exc)

    def _next_id(self) -> int:
        """Return the next unique message ID."""
        return next(self._id_counter)

    def _serialize(self, value: Any) -> Any:
        """Convert a Python value into its JSON-serializable bridge representation."""
        if isinstance(value, _ProxyBase):
            if value._handle is not None:
                return {"__handle__": value._handle}

            if value._target == "ref" and value._ref_type and value._ref_id:
                return {"__ref__": {"type": value._ref_type, "id": value._ref_id}}

            return {"__value__": value.__class__.__name__, "fields": {k: self._serialize(v) for k, v in value.fields.items()}}

        if isinstance(value, EnumValue):
            return {"__enum__": value.type, "name": value.name}

        if isinstance(value, _uuid_mod.UUID):
            return {"__uuid__": str(value)}

        if isinstance(value, list):
            items = cast(List[Any], value)
            return [self._serialize(v) for v in items]

        if isinstance(value, dict):
            d = cast(Dict[str, Any], value)
            return {k: self._serialize(v) for k, v in d.items()}

        return value

    def _deserialize(self, value: Any) -> Any:
        """Reconstruct Python objects from their bridge JSON representation."""
        if isinstance(value, dict):
            d = cast(Dict[str, Any], value)
            if "__handle__" in d:
                assert _proxy_from_fn is not None
                return _proxy_from_fn(d)

            if "__uuid__" in d:
                return _uuid_mod.UUID(d["__uuid__"])

            if "__enum__" in d:
                assert _enum_from_fn is not None
                return _enum_from_fn(d["__enum__"], d["name"])

            # Faster than _XYZ_KEYS.issubset(d.keys()) — avoids view creation
            if "x" in d and "y" in d and "z" in d:
                return SimpleNamespace(**{k: self._deserialize(v) for k, v in d.items()})

            return {k: self._deserialize(v) for k, v in d.items()}

        if isinstance(value, list):
            items = cast(List[Any], value)
            return [self._deserialize(v) for v in items]

        return value
