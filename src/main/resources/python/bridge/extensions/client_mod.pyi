from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from bridge.types import BridgeCall


def is_available(player: Any) -> BridgeCall: ...


def send_command(player: Any, capability: str, args: Dict[str, Any] | None = None,
    handle: Optional[str] | None = None, timeout_ms: int = 1000) -> BridgeCall: ...


def send_data(player: Any, channel: str, payload: Dict[str, Any] | None = None,
    timeout_ms: int = 1000) -> BridgeCall: ...


def register_script(player: Any, name: str, source: str, auto_start: bool = True,
    metadata: Dict[str, Any] | None = None, timeout_ms: int = 2000) -> BridgeCall: ...


def set_permissions(player: Any, capabilities: List[str], reason: Optional[str] = None,
    remember_prompt: bool = True, timeout_ms: int = 60_000) -> BridgeCall: ...


def get_permissions(player: Any) -> BridgeCall: ...


def register_request_data(key: str, value: Any) -> BridgeCall: ...


def unregister_request_data(key: str) -> BridgeCall: ...


def on_client_data(handler: Callable[[Any], Any]) -> Callable[[Any], Any]: ...


def on_permission_change(handler: Callable[[Any], Any]) -> Callable[[Any], Any]: ...
