"""TabList extension — full tab list customization with templates, groups, and fake entries."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional

import bridge

class TabEntry:
    """A single entry in a player's tab list.

    Args:
        name: Display name shown in tab.
        ping: Latency in ms (affects the bar icon). Default 0.
        skin: Optional skin texture value (base64).
        game_mode: Game mode shown. Default "SURVIVAL".
    """

    def __init__(self, name: str, ping: int = 0, skin: Optional[str] = None,
            game_mode: str = "SURVIVAL"):
        """Initialise a new TabEntry."""
        self.name = name
        self.ping = ping
        self.skin = skin
        self.game_mode = game_mode

class TabGroup:
    """A named group of tab entries with a shared prefix/sorting order.

    Args:
        name: Group identifier (e.g. "staff", "default").
        prefix: Text prefix prepended to all entries in this group.
        priority: Sorting priority (lower = higher in list). Default 0.
    """

    def __init__(self, name: str, prefix: str = "", priority: int = 0):
        """Initialise a new TabGroup."""
        self.name = name
        self.prefix = prefix
        self.priority = priority
        self._entries: List[TabEntry] = []

    def add_entry(self, entry: TabEntry):
        """Add a TabEntry to this group."""
        self._entries.append(entry)

    def remove_entry(self, name: str):
        """Remove an entry by display name."""
        self._entries = [e for e in self._entries if e.name != name]

    @property
    def entries(self) -> List[TabEntry]:
        """The entries value."""
        return list(self._entries)

class TabList:
    """Per-player tab list manager with header, footer, templates, and fake entries.

    Example::
        tab = TabList()
        tab.header = "&6My Server"
        tab.footer = "&7Online: {online}/{max}"

        staff = tab.create_group("staff", prefix="&c[Staff] ", priority=0)
        staff.add_entry(TabEntry("Admin", ping=5))

        @bridge.event("player_join")
        async def on_join(event):
            player = event.player
            await tab.apply(player)
    """

    def __init__(self):
        """Initialise a new TabList."""
        self._header: str = ""
        self._footer: str = ""
        self._groups: Dict[str, TabGroup] = {}
        self._templates: Dict[str, Callable[..., str]] = {}

    @property
    def header(self) -> str:
        """The header value."""
        return self._header

    @header.setter
    def header(self, value: str):
        """Set the header."""
        self._header = value

    @property
    def footer(self) -> str:
        """The footer value."""
        return self._footer

    @footer.setter
    def footer(self, value: str):
        """Set the footer."""
        self._footer = value

    def create_group(self, name: str, prefix: str = "",
            priority: int = 0) -> TabGroup:
        """Create a named tab group."""
        group = TabGroup(name, prefix, priority)
        self._groups[name] = group
        return group

    def get_group(self, name: str) -> Optional[TabGroup]:
        """Return the group."""
        return self._groups.get(name)

    def remove_group(self, name: str):
        """Remove a group."""
        self._groups.pop(name, None)

    def template(self, name: str):
        """Decorator: register a template function that returns a string.

        The function receives ``(player, server)`` and should return formatted text.

        Example::

            @tab.template("online")
            def online_count(player, server):
                return f"&7Online: {len(server.players)}"
        """
        def decorator(func: Callable[..., str]) -> Callable[..., str]:
            """Register as a decorator."""
            self._templates[name] = func
            return func

        return decorator

    def _resolve_templates(self, text: str, player, server) -> str:
        """Replace {template_name} placeholders in text."""
        for name, func in self._templates.items():
            placeholder = "{" + name + "}"
            if placeholder in text:
                try:
                    text = text.replace(placeholder, str(func(player, server)))
                except Exception:
                    pass

        # Built-in placeholders
        try:
            players = server.players
            text = text.replace("{online}", str(len(players) if players else 0))
            text = text.replace("{max}", str(server.max_players))
        except Exception:
            pass

        try:
            text = text.replace("{player}", str(player.name))
        except Exception:
            pass

        return text

    async def apply(self, player):
        """Apply this tab list configuration to a player."""
        header = self._resolve_templates(self._header, player, bridge.server)
        footer = self._resolve_templates(self._footer, player, bridge.server)
        await player.set_tab_list_header_footer(header, footer)

    async def apply_all(self):
        """Apply tab list to all online players."""
        players = bridge.server.players
        if players:
            for p in players:
                try:
                    await self.apply(p)
                except Exception:
                    pass

    def auto_update(self, interval_ticks: int = 20):
        """Start auto-updating the tab list for all players every *interval_ticks* ticks.

        Returns an ``asyncio.Task`` that can be cancelled.
        """
        async def _loop():
            """Asynchronously handle loop."""
            while True:
                try:
                    await self.apply_all()
                except Exception:
                    pass

                await bridge.server.after(interval_ticks)

        return asyncio.ensure_future(_loop())
