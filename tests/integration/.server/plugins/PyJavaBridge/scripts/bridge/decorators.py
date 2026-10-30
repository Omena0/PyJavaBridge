"""Decorator-based registration: @event, @task, @command, @preserve."""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import sys
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, cast

__all__ = ["event", "task", "command", "preserve"]

from bridge.utils import _command_signature_params, _parse_command_tokens
from bridge.connection import BridgeConnection
from bridge.types import EventPriority

# Injected by bridge.__init__ during _bootstrap()
_connection:BridgeConnection = None  # type: ignore[assignment]

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def print(*args: Any) -> None:
    """Redirect print to stderr so stdout stays reserved for IPC."""
    _print(*args, file=sys.stderr)

def event(func: Optional[Callable] = None, *, once_per_tick: bool = False, priority: str | EventPriority = "NORMAL", throttle_ms: int = 0, non_blocking: bool = False) -> Any:
    """
    :decorator: event()

    Register an async event handler.

    The handler name is mapped to a Bukkit/Paper event class using snake_case
    (e.g., player_join -> PlayerJoinEvent). Events are registered on demand.

    :param bool once_per_tick: If True, the handler is only run once per tick
    :param priority: Event priority.
    :type priority: EventPriority or string
    :param int throttle_ms: Throttle to only run every n milliseconds.
    :param bool non_blocking: Ignore the return value of the event. Server will not wait for event completion.
    """
    def decorator(handler: Callable) -> Callable:
        """Register *handler* for the event derived from its name."""
        event_name = handler.__name__
        _connection.on(event_name, handler)
        # Preserve backwards-compatible subscribe signature while forwarding
        # the optional `non_blocking` flag which some scripts may declare.
        _connection.subscribe(event_name, once_per_tick, priority, throttle_ms, non_blocking)

        def _unregister() -> None:
            """Remove this handler from the event bus."""
            _connection.off(event_name, handler)

        handler.unregister = _unregister  # type: ignore[attr-defined]
        return handler

    if func is None:
        return decorator

    return decorator(func)

def task(func: Optional[Callable] = None, *, interval: int = 20, delay: int = 0) -> Any:
    """
    Register a repeating async task.

    Args:
        interval: Ticks between each call (default 20 = 1 second).
        delay: Ticks to wait before the first call (default 0).
    """
    def decorator(handler: Callable) -> Callable:
        """Register *handler* as a repeating async task."""
        from bridge import server
        started = False

        async def _loop() -> None:
            """Run the task repeatedly at the configured interval."""
            try:
                if delay > 0:
                    try:
                        await server.after(delay)
                    except Exception:
                        # Fallback to local sleep if bridge wait is briefly unavailable.
                        await asyncio.sleep(max(delay / 20.0, 0.05))

                while _connection is not None and _connection._thread.is_alive():
                    try:
                        result = handler()
                        if hasattr(result, "__await__"):
                            await result
                    except Exception as e:
                        print(f"[PyJavaBridge] Task {handler.__name__} error: {e}")

                    try:
                        await server.after(interval)
                    except Exception as e:
                        # Do not terminate the task loop on transient bridge/scheduler issues.
                        print(f"[PyJavaBridge] Task {handler.__name__} wait error: {e}")
                        await asyncio.sleep(max(interval / 20.0, 0.05))
            except Exception:
                pass

        def _start_loop(_: Any = None) -> None:
            """Start the task loop once."""
            nonlocal started
            if started:
                return

            started = True
            asyncio.ensure_future(_loop())

        async def _on_server_boot(_: Any) -> None:
            """Async wrapper for server_boot registration type expectations."""
            _start_loop()

        _connection.on("server_boot", _on_server_boot)

        async def _start_fallback_once() -> None:
            """Fallback starter if server_boot is missed during a reload race."""
            await asyncio.sleep(0.25)
            _start_loop()

        asyncio.ensure_future(_start_fallback_once())
        return handler

    if func is None:
        return decorator

    return decorator(func)

def command(description: Optional[str] = None, *, name: Optional[str] = None, permission: Optional[str] = None, tab_complete: Optional[dict] = None) -> Any:
    """
    Register a command handler.

    The handler name is registered as a server command unless a custom
    command name is provided via name=.

    Example::

        @command("Greet a player")
        async def greet(event, name: str):
            event.player.send_message(f"Hello, {name}!")
    """
    def decorator(handler: Any) -> Any:
        """Register *handler* as a slash command."""
        from bridge.wrappers import ProxyBase, Player
        from bridge.helpers import ConsolePlayer

        sig = inspect.signature(handler)
        positional_params, keyword_only_names, has_varargs, has_varkw = _command_signature_params(sig)

        def _format_type(annotation: Any) -> str:
            """Return a human-readable type name from a parameter annotation."""
            if annotation is inspect.Parameter.empty:
                return "str"

            if isinstance(annotation, str):
                return annotation

            n = getattr(annotation, "__name__", None)
            if n:
                return n

            text = str(annotation)
            if text.startswith("typing."):
                return text[7:]  # len("typing.") == 7

            return text

        def _usage_text(cmd_name: str) -> str:
            """Build a usage string from the command's parameters."""
            parts: List[str] = []
            for param in positional_params:
                type_name = _format_type(param.annotation)
                token = f"<{param.name}: {type_name}>"
                if param.default is not inspect.Parameter.empty:
                    token = f"[{token}]"

                parts.append(token)

            if has_varargs:
                parts.append("[<args...>]")

            if has_varkw:
                parts.append("[<key:value...>]")

            args_text = " ".join(parts)
            return f"Usage: /{cmd_name}" + (f" {args_text}" if args_text else "")

        func_name = handler.__name__
        func_name = func_name.removeprefix("cmd_")

        command_name = (name or func_name).lower()

        @wraps(handler)
        async def wrapper(event_obj: Any) -> None:
            """Parse raw args and dispatch to the decorated command handler."""
            raw_args: List[str] = []
            if isinstance(event_obj, ProxyBase):
                player = event_obj.fields.get("player")
                sender_obj = event_obj.fields.get("sender")
                if player is None and sender_obj is not None and not isinstance(sender_obj, Player):
                    event_obj.fields["player"] = ConsolePlayer(sender_obj)

                raw_args = event_obj.fields.get("args", []) or []
            elif isinstance(event_obj, dict):
                evt = cast(Dict[str, Any], event_obj)
                player_d: Any = evt.get("player")
                sender_d: Any = evt.get("sender")
                if player_d is None and sender_d is not None and not isinstance(sender_d, Player):
                    evt["player"] = ConsolePlayer(sender_d)

                raw_args = list(evt.get("args", []) or [])

            pos_args, var_args, kwargs, positional_tokens, allowed_kw_names = _parse_command_tokens(
                raw_args,
                positional_params,
                keyword_only_names,
                has_varargs,
                has_varkw,
            )

            if not has_varkw:
                kwargs = {k: v for k, v in kwargs.items() if k in allowed_kw_names}

            used_names = {p.name for p in positional_params[:len(pos_args)]}
            kwargs = {k: v for k, v in kwargs.items() if k not in used_names}

            if positional_tokens and not positional_params and not has_varargs:
                target: Any = None
                if isinstance(event_obj, ProxyBase):
                    target = event_obj.fields.get("player") or event_obj.fields.get("sender")
                elif isinstance(event_obj, dict):
                    evt2 = cast(Dict[str, Any], event_obj)
                    target = evt2.get("player") or evt2.get("sender")

                usage = _usage_text(command_name)
                if target is not None:
                    try:
                        result = target.send_message(usage)
                        if hasattr(result, "__await__"):
                            await result
                    except Exception:
                        pass
                else:
                    print(f"[PyJavaBridge] {usage}")

                return None

            try:
                sig.bind(event_obj, *pos_args, *var_args, **kwargs)
            except TypeError:
                target = None
                if isinstance(event_obj, ProxyBase):
                    target = event_obj.fields.get("player") or event_obj.fields.get("sender")
                elif isinstance(event_obj, dict):
                    evt3 = cast(Dict[str, Any], event_obj)
                    target = evt3.get("player") or evt3.get("sender")

                usage = _usage_text(command_name)
                if target is not None:
                    try:
                        result = target.send_message(usage)
                        if hasattr(result, "__await__"):
                            await result
                    except Exception:
                        pass
                else:
                    print(f"[PyJavaBridge] {usage}")

                return None

            result = handler(event_obj, *pos_args, *var_args, **kwargs)
            if hasattr(result, "__await__"):
                return await result

            return result

        event_name = f"command_{command_name}"
        _connection.on(event_name, wrapper)
        _connection.register_command(command_name, permission=permission, completions=tab_complete)
        setattr(wrapper, "__command_args__", [p.name for p in positional_params])
        setattr(wrapper, "__command_desc__", description)

        def _tab_complete_decorator(tc_handler: Callable[..., Any]) -> Callable[..., Any]:
            """Register *tc_handler* as the tab-completion provider for this command."""
            _connection.register_tab_complete(command_name, tc_handler)
            _connection.register_command(command_name, permission=permission, has_tab_complete=True)
            return tc_handler

        wrapper.tab_complete = _tab_complete_decorator  # type: ignore[attr-defined]
        return wrapper

    return decorator

# ---------------------------------------------------------------------------
# @preserve — hot-reload state persistence
# ---------------------------------------------------------------------------
_PRESERVE_DIR: str | None = None
_PRESERVE_FILE_KEY_RE = re.compile(r"[^A-Za-z0-9_.-]+")

def _preserve_dir() -> str:
    """Return (and lazily create) the preserve data directory path."""
    global _PRESERVE_DIR
    if _PRESERVE_DIR is None:
        base = os.environ.get("PJB_DATA_DIR", "plugins/PyJavaBridge")
        _PRESERVE_DIR = os.path.join(base, "preserve")
        os.makedirs(_PRESERVE_DIR, exist_ok=True)

    return _PRESERVE_DIR

def _preserve_file_key(key: str) -> str:
    """Return a filesystem-safe key for preserve storage files."""
    safe = _PRESERVE_FILE_KEY_RE.sub("_", key).strip("._")
    return safe or "preserved_value"

def preserve(func: Callable[[], Any]) -> Any:
    """Persist a variable across hot reloads.

    Decorate a no-arg factory function.  On first load, the factory runs and
    its return value is cached to disk as JSON.  On subsequent reloads, the
    cached value is returned instead.

    Example::

        @preserve
        def player_scores():
            return {}

        # player_scores is now a dict that survives /pjb reload
    """
    key = func.__qualname__
    path = os.path.join(_preserve_dir(), f"{_preserve_file_key(key)}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            value = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        value = func()

    def _save() -> None:
        """Persist the preserved value to disk as JSON."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f)
        except Exception as e:
            print(f"[PyJavaBridge] preserve save error for {key}: {e}")

    if _connection is not None:
        async def _on_shutdown(_: Any) -> None:
            """Save preserved value on server shutdown."""
            _save()

        async def _on_unload(_: Any) -> None:
            """Save preserved value on script unload."""
            _save()

        _connection.on("server_shutdown", _on_shutdown)
        _connection.on("script_unload", _on_unload)

    # Make the value itself the return, but stash save for explicit use
    if isinstance(value, dict):
        value.setdefault("__preserve_save__", _save)

    return value  # type: ignore[return-value]
