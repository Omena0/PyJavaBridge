"""TradeWindow extension — two-player trade GUI with anti-dupe measures."""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

import bridge
from bridge.extensions.bank import Bank


class TradeWindow:
    """Two-player trading window backed by a chest GUI.

    Each player sees both offers. Players add/remove items and adjust balance
    offers. Both must confirm before the trade executes (after a short delay).

    Args:
        bank: Optional Bank for currency offers.
        delay: Seconds after both confirm before executing (anti-scam).
    """

    def __init__(self, bank: Optional[Bank] = None, delay: float = 3.0):
        self._bank = bank
        self._delay = delay
        self._on_trade_handlers: List[Callable[..., Any]] = []
        self._sessions: Dict[str, "_TradeSession"] = {}  # puuid -> session

    def on_trade(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(player1, player2, items1, items2, bal1, bal2)``."""
        self._on_trade_handlers.append(handler)
        return handler

    def open(self, p1: Any, p2: Any):
        session = _TradeSession(self, p1, p2)
        self._sessions[str(p1.uuid)] = session
        self._sessions[str(p2.uuid)] = session
        session.show()

    def close(self, player: Any):
        puuid = str(player.uuid)
        session = self._sessions.get(puuid)
        if session:
            session.cancel()

    def _remove_session(self, session: "_TradeSession"):
        for puuid in (str(session.p1.uuid), str(session.p2.uuid)):
            self._sessions.pop(puuid, None)


class _TradeSession:
    """Internal per-trade state."""

    def __init__(self, window: TradeWindow, p1: Any, p2: Any):
        self.window = window
        self.p1 = p1
        self.p2 = p2
        self.items1: List[Any] = []
        self.items2: List[Any] = []
        self.balance1: int = 0
        self.balance2: int = 0
        self.confirmed: List[bool] = [False, False]  # [p1, p2]
        self._cancelled = False
        self._executing = False

    def show(self):
        """Open trade GUIs for both players."""
        self._show_for(self.p1, 0)
        self._show_for(self.p2, 1)

    def _show_for(self, player: Any, player_idx: int):
        from bridge.wrappers import Inventory, Item as WItem
        from bridge.helpers import Menu, MenuItem, _register_menu_events, _open_menus

        menu = Menu(f"Trade: {self.p1.name} <-> {self.p2.name}", 6)

        # Top section (rows 0-1): P1's offer
        for i, item in enumerate(self.items1[:9]):
            menu[i] = MenuItem(item)
        # Middle section (rows 2-3): P2's offer
        for i, item in enumerate(self.items2[:9]):
            menu[18 + i] = MenuItem(item)

        # Row 4: status and balance offers
        bal_text1 = f"§6{self.p1.name}: §f{self.balance1}"
        bal_text2 = f"§6{self.p2.name}: §f{self.balance2}"
        menu[36] = MenuItem(WItem("GOLD_INGOT", name=bal_text1))
        menu[44] = MenuItem(WItem("GOLD_INGOT", name=bal_text2))

        # Row 4 center: confirm status
        if self.confirmed[0] and self.confirmed[1]:
            status = "§aBoth confirmed!"
        elif self.confirmed[player_idx]:
            status = "§aYou confirmed — waiting..."
        else:
            status = "§eClick to confirm"

        def _make_confirm(idx: int):
            async def _confirm(p: Any, e: Any):
                if self._cancelled or self._executing:
                    return
                if self.confirmed[idx]:
                    # Un-confirm
                    self.confirmed[idx] = False
                    self.show()
                    return
                self.confirmed[idx] = True
                if self.confirmed[0] and self.confirmed[1]:
                    await self._execute()
                else:
                    self.show()
            return _confirm

        confirm_item = WItem("LIME_DYE" if self.confirmed[player_idx] else "GRAY_DYE",
                             name=status)
        menu[40] = MenuItem(confirm_item, on_click=_make_confirm(player_idx))

        # Cancel button
        async def _cancel_click(p: Any, e: Any):
            self.cancel()

        menu[45 + 8] = MenuItem(WItem("BARRIER", name="§cCancel"), on_click=_cancel_click)

        # Add item button (only for own side)
        if not self.confirmed[player_idx]:
            def _make_add_balance(idx: int, amount: int):
                async def _add(p: Any, e: Any):
                    if self._cancelled or self.confirmed[idx]:
                        return
                    if idx == 0:
                        self.balance1 = max(0, self.balance1 + amount)
                    else:
                        self.balance2 = max(0, self.balance2 + amount)
                    self.show()
                return _add

            menu[37 if player_idx == 0 else 45] = MenuItem(
                WItem("EMERALD", name="§a+1"), on_click=_make_add_balance(player_idx, 1))
            menu[38 if player_idx == 0 else 46] = MenuItem(
                WItem("EMERALD_BLOCK", name="§a+10"), on_click=_make_add_balance(player_idx, 10))
            menu[39 if player_idx == 0 else 47] = MenuItem(
                WItem("REDSTONE", name="§c-1"), on_click=_make_add_balance(player_idx, -1))

        menu.open(player)

    async def _execute(self):
        from bridge.wrappers import server
        self._executing = True
        # Countdown
        for p in (self.p1, self.p2):
            await p.send_message(f"§eTrade executing in {self.window._delay:.0f}s...")
        try:
            await server.after(int(self.window._delay * 20))
        except Exception:
            self.cancel()
            return

        if self._cancelled:
            return

        # Validate balances
        bank = self.window._bank
        if bank:
            if self.balance1 > 0 and bank.balance(self.p1) < self.balance1:
                await self.p1.send_message("§cNot enough funds!")
                self.cancel()
                return
            if self.balance2 > 0 and bank.balance(self.p2) < self.balance2:
                await self.p2.send_message("§cNot enough funds!")
                self.cancel()
                return

        # Execute item swap
        for item in self.items1:
            self.p2.inventory.add_item(item)
        for item in self.items2:
            self.p1.inventory.add_item(item)

        # Execute balance swap
        if bank:
            if self.balance1 > 0:
                bank.withdraw(self.p1, self.balance1)
                bank.deposit(self.p2, self.balance1)
            if self.balance2 > 0:
                bank.withdraw(self.p2, self.balance2)
                bank.deposit(self.p1, self.balance2)

        for p in (self.p1, self.p2):
            await p.send_message("§aTrade complete!")

        # Fire handlers
        for handler in self.window._on_trade_handlers:
            try:
                result = handler(self.p1, self.p2, self.items1, self.items2,
                                 self.balance1, self.balance2)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass

        self.window._remove_session(self)

    def cancel(self):
        if self._cancelled:
            return
        self._cancelled = True
        from bridge.helpers import _open_menus
        for p in (self.p1, self.p2):
            _open_menus.pop(str(p.uuid), None)
            asyncio.ensure_future(p.send_message("§cTrade cancelled."))
        self.window._remove_session(self)
