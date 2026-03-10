"""PyJavaBridge — Python scripting API for Bukkit/Paper Minecraft servers."""
from __future__ import annotations

from asyncio import gather, as_completed, timeout
from typing import Dict
import asyncio
import os
import runpy
import sys

# ── stderr print override ─────────────────────────────────────────────
_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def print(*args):
    """Redirect print to stderr so stdout stays reserved for IPC."""
    _print(*args, file=sys.stderr)

# ── Sub-module imports ────────────────────────────────────────────────
from bridge.connection import BridgeConnection
from bridge.decorators import *
from bridge.wrappers import *
from bridge.helpers import *
from bridge.errors import *
from bridge.types import *
from bridge.api import *

from bridge.types import async_task

# ── Module-level globals ──────────────────────────────────────────────
_connection: BridgeConnection = None  # type: ignore[assignment]
_player_uuid_cache: Dict[str, str] = {}

def fire_event(event_name: str, data: dict | None = None) -> None:
    """Fire a custom event that all scripts (including this one) can listen to."""
    _connection.fire_event(event_name, data)

# ── Bootstrap ─────────────────────────────────────────────────────────
def _bootstrap(script_path: str):
    """Entry point called by the Java plugin to start a Python script."""
    global _connection, _player_uuid_cache
    if not os.path.isfile(script_path):
        raise RuntimeError(f"Script not found: {script_path}")

    # Create connection
    _connection = BridgeConnection()
    _player_uuid_cache = {}

    # Inject into sub-modules
    from bridge import connection as _conn_mod
    from bridge import wrappers as _wrap_mod
    from bridge import utils as _util_mod
    from bridge import helpers as _help_mod
    from bridge import decorators as _dec_mod
    from bridge import api as _api_mod
    from bridge.extensions import npc as _npc_mod

    _conn_mod._connection = _connection  # type: ignore[attr-defined]
    _wrap_mod._connection = _connection
    _wrap_mod._player_uuid_cache = _player_uuid_cache
    _util_mod._connection = _connection
    _util_mod._player_uuid_cache = _player_uuid_cache
    _help_mod._connection = _connection
    _dec_mod._connection = _connection
    _api_mod._connection = _connection
    _npc_mod._connection = _connection

    # Prime player cache
    from bridge.utils import _prime_player_cache
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_prime_player_cache())
    except Exception:
        pass

    print(f"[PyJavaBridge] Bootstrapping script {script_path}")
    namespace = {
        "__file__": script_path,
        "__name__": "__main__",
        "__builtins__": __builtins__,
    }
    runpy.run_path(script_path, init_globals=namespace)
    _connection.send({"type": "ready"})
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _connection._stop_reader()
