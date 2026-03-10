"""Shop extension — GUI-based item shop with bank integration."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

from bridge.extensions.bank import Bank

class Shop:
    """Interactive chest-GUI shop backed by a Bank.

    Args:
        name: Shop display name (inventory title).
        bank: Bank instance for payments.
        rows: Inventory rows per page (2-6, last row reserved for nav).
    """

    def __init__(self, name: str = "Shop", bank: Optional[Bank] = None,
            rows: int = 6):
        """Initialise a new Shop."""
        self.name = name
        self._bank = bank
        self._rows = max(2, min(6, rows))
        self._items: List[Tuple[Any, int]] = []  # (Item, price)
        self._on_purchase_handlers: List[Callable[..., Any]] = []
        self._open_pages: Dict[str, int] = {}  # puuid -> current page

    def add_item(self, item: Any, price: int):
        """Add an item for sale. *price* is in bank currency."""
        self._items.append((item, price))

    def remove_item(self, index: int):
        """Remove a item."""
        if 0 <= index < len(self._items):
            self._items.pop(index)

    def on_purchase(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(player, item, price)`` called after purchase."""
        self._on_purchase_handlers.append(handler)
        return handler

    @property
    def items(self) -> List[Tuple[Any, int]]:
        """The items value."""
        return list(self._items)

    def open(self, player: Any, page: int = 0):
        """Open the UI."""
        from bridge import Inventory, Item as WItem
        from bridge.helpers import _register_menu_events, _open_menus, Menu, MenuItem

        usable = (self._rows - 1) * 9
        total_pages = max(1, (len(self._items) + usable - 1) // usable)
        page = max(0, min(page, total_pages - 1))

        puuid = str(player.uuid)
        self._open_pages[puuid] = page

        menu = Menu(f"{self.name} ({page + 1}/{total_pages})", self._rows)
        start = page * usable
        end = min(start + usable, len(self._items))

        for slot_idx, item_idx in enumerate(range(start, end)):
            shop_item, price = self._items[item_idx]
            # Clone the item and add price to lore
            display = self._make_display_item(shop_item, price)
            captured_idx = item_idx

            def _make_click(idx: int):
                """Handle make click."""
                async def _on_click(p: Any, event: Any):
                    """Handle the click event."""
                    await self._try_purchase(p, idx)

                return _on_click

            menu[slot_idx] = MenuItem(display, on_click=_make_click(captured_idx))

        # Navigation row
        nav_start = (self._rows - 1) * 9
        if page > 0:
            prev = WItem("ARROW", name="<< Previous")
            menu[nav_start] = MenuItem(prev, on_click=lambda p, e: self.open(p, page - 1))

        if page < total_pages - 1:
            nxt = WItem("ARROW", name="Next >>")
            menu[nav_start + 8] = MenuItem(nxt, on_click=lambda p, e: self.open(p, page + 1))

        # Balance indicator
        bal = self._bank.balance(player) if self._bank else 0
        info = WItem("GOLD_INGOT", name=f"Balance: {bal}")
        menu[nav_start + 4] = MenuItem(info)

        menu.open(player)

    def close(self, player: Any):
        """Close the UI."""
        from bridge.helpers import _open_menus
        puuid = str(player.uuid)
        _open_menus.pop(puuid, None)
        self._open_pages.pop(puuid, None)

    def _make_display_item(self, item: Any, price: int) -> Any:
        """Handle make display item."""
        from bridge import Item as WItem
        # Create a display copy with price in lore
        lore = list(item.lore) if hasattr(item, "lore") and item.lore else []
        lore.append(f"§ePrice: §f{price} {self._bank.currency if self._bank else 'coins'}")
        return WItem(
            material=item.type if hasattr(item, "type") else str(item),
            amount=item.amount if hasattr(item, "amount") else 1,
            name=item.name if hasattr(item, "name") else None,
            lore=lore,
        )

    async def _try_purchase(self, player: Any, item_idx: int):
        """Asynchronously handle try purchase."""
        if item_idx < 0 or item_idx >= len(self._items):
            return

        item, price = self._items[item_idx]
        if self._bank is None:
            await player.send_message("§cNo bank configured for this shop.")
            return

        if not self._bank.withdraw(player, price):
            await player.send_message(f"§cNot enough {self._bank.currency}! Need {price}.")
            return

        # Give item to player
        from bridge import Item as WItem
        give_item = WItem(
            material=item.type if hasattr(item, "type") else str(item),
            amount=item.amount if hasattr(item, "amount") else 1,
            name=item.name if hasattr(item, "name") else None,
            lore=item.lore if hasattr(item, "lore") else None,
        )
        player.inventory.add_item(give_item)
        await player.send_message(
            f"§aPurchased {item.name or item.type} for {price} {self._bank.currency}!")

        for handler in self._on_purchase_handlers:
            try:
                result = handler(player, item, price)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

        # Refresh the page
        page = self._open_pages.get(str(player.uuid), 0)
        self.open(player, page)
