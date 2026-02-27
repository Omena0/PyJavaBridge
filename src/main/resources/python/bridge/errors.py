"""Bridge exception hierarchy."""
from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "BridgeError",
    "EntityGoneException",
    "ConnectionError",
    "TimeoutError",
    "AtomicAbortError",
    "PlayerOfflineException",
    "WorldNotLoadedException",
    "ChunkNotLoadedException",
    "InvalidLocationError",
    "InvalidMaterialError",
    "InvalidItemError",
    "MethodNotFoundError",
    "ClassNotFoundError",
    "AccessDeniedError",
    "InvalidEventError",
    "CommandRegistrationError",
    "ConfigError",
    "UnsupportedFormatError",
    "InvalidEnumError",
    "SlotOutOfRangeError",
    "PermissionError",
]


class BridgeError(Exception):
    """Bridge-specific runtime error."""
    def __init__(self, message: str = "", java_stacktrace: Optional[str] = None):
        self.java_stacktrace = java_stacktrace
        if java_stacktrace:
            super().__init__(f"{message}\n--- Java stacktrace ---\n{java_stacktrace}")
        else:
            super().__init__(message)

class EntityGoneException(BridgeError):
    """Raised when an entity/player is no longer available."""
    pass

class ConnectionError(BridgeError):
    """Raised when the bridge connection is lost or unavailable."""
    pass

class TimeoutError(BridgeError):
    """Raised when a call to Java times out."""
    pass

class AtomicAbortError(BridgeError):
    """Raised when an atomic batch is aborted due to an error."""
    pass

class PlayerOfflineException(BridgeError):
    """Raised when targeting a player who is no longer online."""
    pass

class WorldNotLoadedException(BridgeError):
    """Raised when accessing a world that isn't loaded."""
    pass

class ChunkNotLoadedException(BridgeError):
    """Raised when accessing a chunk that isn't loaded."""
    pass

class InvalidLocationError(BridgeError):
    """Raised when a location is invalid or missing required fields."""
    pass

class InvalidMaterialError(BridgeError):
    """Raised when a material name is invalid."""
    pass

class InvalidItemError(BridgeError):
    """Raised when an item operation is invalid."""
    pass

class MethodNotFoundError(BridgeError):
    """Raised when a method doesn't exist on the target object."""
    pass

class ClassNotFoundError(BridgeError):
    """Raised when a Java class cannot be found."""
    pass

class AccessDeniedError(BridgeError):
    """Raised when access to a method or field is denied."""
    pass

class InvalidEventError(BridgeError):
    """Raised when an event name is invalid."""
    pass

class CommandRegistrationError(BridgeError):
    """Raised when command registration fails."""
    pass

class ConfigError(BridgeError):
    """Raised when a config operation fails."""
    pass

class UnsupportedFormatError(BridgeError):
    """Raised when a file format is not supported."""
    pass

class InvalidEnumError(BridgeError):
    """Raised when an enum value is invalid."""
    pass

class SlotOutOfRangeError(BridgeError):
    """Raised when an inventory slot index is out of range."""
    pass

class PermissionError(BridgeError):
    """Raised when a permission check fails."""
    pass


_ERROR_CODE_MAP: Dict[str, type[BridgeError]] = {
    "ENTITY_GONE": EntityGoneException,
    "TIMEOUT": TimeoutError,
    "ATOMIC_ABORT": AtomicAbortError,
    "INVALID_MATERIAL": InvalidMaterialError,
    "INVALID_ENUM": InvalidEnumError,
    "SLOT_OUT_OF_RANGE": SlotOutOfRangeError,
    "METHOD_NOT_FOUND": MethodNotFoundError,
    "CLASS_NOT_FOUND": ClassNotFoundError,
    "ACCESS_DENIED": AccessDeniedError,
    "NULL_REFERENCE": BridgeError,
    "INVALID_ARGUMENT": BridgeError,
}

def _make_bridge_error(message: Dict[str, Any]) -> BridgeError:
    code = message.get("code")
    msg = message.get("message", "Unknown error")
    stacktrace = message.get("stacktrace")
    cls = _ERROR_CODE_MAP.get(code, BridgeError) if code else BridgeError
    return cls(msg, java_stacktrace=stacktrace)
