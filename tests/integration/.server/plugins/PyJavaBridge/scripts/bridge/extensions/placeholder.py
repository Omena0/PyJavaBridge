"""Placeholder extension — register %placeholder% expansions for messages."""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional

_PLACEHOLDER_RE = re.compile(r"%([a-zA-Z0-9_.]+)%")

class PlaceholderRegistry:
    """Global registry for placeholder expansions.

    Register placeholders with ``%name%`` syntax. When text is processed via
    :meth:`resolve`, all registered placeholders are expanded.

    Example::
        placeholders = PlaceholderRegistry()

        @placeholders.register("player_health")
        def health(player):
            return str(player.health)

        @placeholders.register("player_name")
        def name(player):
            return player.name

        @placeholders.register("server_online")
        def online(player):
            import bridge
            return str(len(bridge.server.players))

        # Resolve placeholders in a string
        msg = placeholders.resolve("Hello %player_name%! HP: %player_health%", player)
        # -> "Hello Steve! HP: 20.0"
    """
    __slots__ = ("_placeholders",)

    def __init__(self) -> None:
        """Initialise a new PlaceholderRegistry."""
        self._placeholders: Dict[str, Callable[..., str]] = {}

    def register(self, name: str) -> Any:
        """Decorator: register a placeholder by name.

        The decorated function receives ``(player)`` and should return a string.
        If the function returns None, the placeholder is left unresolved.
        """
        def decorator(func: Callable[..., str]) -> Callable[..., str]:
            """Register as a decorator."""
            self._placeholders[name] = func
            return func

        return decorator

    def add(self, name: str, func: Callable[..., str]) -> None:
        """Imperatively register a placeholder."""
        self._placeholders[name] = func

    def remove(self, name: str) -> None:
        """Remove a placeholder."""
        self._placeholders.pop(name, None)

    def has(self, name: str) -> bool:
        """Handle has."""
        return name in self._placeholders

    @property
    def names(self) -> list:
        """The names value."""
        return list(self._placeholders.keys())

    def resolve(self, text: str, player: Any = None, **kwargs: Any) -> str:
        """Replace all ``%placeholder%`` tokens in *text* with their resolved values.

        Args:
            text: Input string with placeholders.
            player: The player context passed to each resolver function.
            **kwargs: Extra keyword arguments passed to resolver functions.

        Returns:
            The string with all known placeholders expanded.
        """
        def _replace(match: Any) -> Any:
            """Handle replace."""
            name = match.group(1)
            func = self._placeholders.get(name)
            if func is None:
                return match.group(0)  # leave unresolved

            try:
                result = func(player, **kwargs) if kwargs else func(player)
                return str(result) if result is not None else match.group(0)
            except Exception:
                return match.group(0)

        return _PLACEHOLDER_RE.sub(_replace, text)

    def resolve_many(self, texts: list, player: Any = None, **kwargs: Any) -> list:
        """Resolve placeholders in a list of strings."""
        return [self.resolve(t, player, **kwargs) for t in texts]
