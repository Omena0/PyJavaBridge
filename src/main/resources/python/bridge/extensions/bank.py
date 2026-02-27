"""Bank extension — global currency system with per-player balances."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable, Dict, List, Optional

import bridge


class Bank:
    """Global bank instance — tracks per-player currency balances.

    Balances are persisted to a JSON file so they survive restarts.

    Args:
        name: Bank name (used for file persistence).
        currency: Display name of the currency (e.g. "coins").
    """

    _instances: Dict[str, "Bank"] = {}

    def __init__(self, name: str = "default", currency: str = "coins"):
        self.name = name
        self.currency = currency
        self._balances: Dict[str, int] = {}
        self._transaction_handlers: List[Callable[..., Any]] = []
        self._path = os.path.join("plugins", "PyJavaBridge", "banks", f"{name}.json")
        self._load()
        Bank._instances[name] = self

    def _load(self):
        if os.path.isfile(self._path):
            with open(self._path, "r") as f:
                self._balances = json.load(f)

    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._balances, f)

    def _puuid(self, player: Any) -> str:
        if isinstance(player, str):
            return player
        return str(player.uuid)

    def balance(self, player: Any) -> int:
        return self._balances.get(self._puuid(player), 0)

    def deposit(self, player: Any, amount: int):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        puuid = self._puuid(player)
        self._balances[puuid] = self._balances.get(puuid, 0) + amount
        self._save()
        self._fire_transaction(player, "deposit", amount)

    def withdraw(self, player: Any, amount: int) -> bool:
        if amount <= 0:
            raise ValueError("Withdraw amount must be positive")
        puuid = self._puuid(player)
        current = self._balances.get(puuid, 0)
        if current < amount:
            return False
        self._balances[puuid] = current - amount
        self._save()
        self._fire_transaction(player, "withdraw", amount)
        return True

    def transfer(self, source: Any, target: Any, amount: int) -> bool:
        if not self.withdraw(source, amount):
            return False
        self.deposit(target, amount)
        return True

    def set_balance(self, player: Any, amount: int):
        self._balances[self._puuid(player)] = max(0, amount)
        self._save()

    def on_transaction(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: register a transaction handler ``(player, action, amount)``."""
        self._transaction_handlers.append(handler)
        return handler

    def _fire_transaction(self, player: Any, action: str, amount: int):
        for handler in self._transaction_handlers:
            try:
                result = handler(player, action, amount)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception as e:
                import sys
                _print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
                _print(f"[PyJavaBridge] Bank transaction handler error: {e}", file=sys.stderr)

    @classmethod
    def get(cls, name: str = "default") -> Optional["Bank"]:
        return cls._instances.get(name)
