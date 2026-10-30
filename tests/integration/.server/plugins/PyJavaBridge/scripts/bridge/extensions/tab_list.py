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
    __slots__ = ("name", "ping", "skin", "game_mode")

    def __init__(self, name: str, ping: int = 0, skin: Optional[str] = None,
            game_mode: str = "SURVIVAL") -> None:
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
    __slots__ = ("name", "prefix", "priority", "_entries")

    def __init__(self, name: str, prefix: str = "", priority: int = 0) -> None:
        """Initialise a new TabGroup."""
        self.name = name
        self.prefix = prefix
        self.priority = priority
        self._entries: List[TabEntry] = []

    def add_entry(self, entry: TabEntry) -> None:
        """Add a TabEntry to this group."""
        self._entries.append(entry)

    def remove_entry(self, name: str) -> None:
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

    def __init__(self) -> None:
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
    def header(self, value: str) -> None:
        """Set the header."""
        self._header = value

    @property
    def footer(self) -> str:
        """The footer value."""
        return self._footer

    @footer.setter
    def footer(self, value: str) -> None:
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

    def remove_group(self, name: str) -> None:
        """Remove a group."""
        self._groups.pop(name, None)

    def template(self, name: str) -> Any:
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

    def _resolve_templates(self, text: str, player: Any, server: Any) -> str:
        """Replace {template_name} placeholders in text."""
        for name, func in self._templates.items():
            placeholder = f"{{{name}}}"
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

    def _resolve_player_tab_name(self, player: Any) -> Optional[str]:
        """Resolve a configured tab-list name for *player* from group entries."""
        try:
            player_name = str(player.name)
        except Exception:
            return None

        for group in sorted(self._groups.values(), key=lambda g: g.priority):
            for entry in group.entries:
                if entry.name.lower() == player_name.lower():
                    return f"{group.prefix}{entry.name}"

        return None

    def _render_group_lines(self, player: Any, server: Any) -> List[str]:
        """Render configured group/fake entries as footer lines."""
        if not self._groups:
            return []

        online_names: set[str] = set()
        try:
            for online in server.players or []:
                online_names.add(str(online.name).lower())
        except Exception:
            online_names = set()

        lines: List[str] = []
        for group in sorted(self._groups.values(), key=lambda g: g.priority):
            for entry in group.entries:
                label = self._resolve_templates(f"{group.prefix}{entry.name}", player, server)
                if entry.name.lower() in online_names:
                    lines.append(label)
                else:
                    lines.append(f"§7{label}")

        return lines[:20]

    async def apply(self, player: Any) -> None:
        """Apply this tab list configuration to a player."""
        server = bridge.server
        header = self._resolve_templates(self._header, player, server)
        footer = self._resolve_templates(self._footer, player, server)
        group_lines = self._render_group_lines(player, server)
        if group_lines:
            footer = f"{footer}\n" if footer else ""
            footer += "\n".join(group_lines)

        await player.set_tab_list_header_footer(header, footer)

        tab_name = self._resolve_player_tab_name(player)
        if tab_name is not None:
            await player.set_tab_list_name(tab_name)

    async def apply_all(self) -> None:
        """Apply tab list to all online players."""
        players = bridge.server.players
        if players:
            for p in players:
                try:
                    await self.apply(p)
                except Exception:
                    pass

    def auto_update(self, interval_ticks: int = 20) -> Any:
        """Start auto-updating the tab list for all players every *interval_ticks* ticks.

        Returns an ``asyncio.Task`` that can be cancelled.
        """
        async def _loop() -> None:
            """Asynchronously handle loop."""
            while True:
                try:
                    await self.apply_all()
                except Exception:
                    pass

                await bridge.server.after(interval_ticks)

        return asyncio.ensure_future(_loop())
