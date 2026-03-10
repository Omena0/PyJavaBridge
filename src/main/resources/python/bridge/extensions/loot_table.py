"""LootTable extension — custom loot tables with weights, conditions, and rolls."""
from __future__ import annotations

import random
from typing import Any, Callable, Dict, List, Optional, Tuple

class LootEntry:
    """A single entry in a loot pool.

    Args:
        item: Material name or dict with ``{"material": ..., "amount": ..., "name": ...}``.
        weight: Relative probability weight. Default 1.
        min_amount: Minimum stack size. Default 1.
        max_amount: Maximum stack size. Default 1.
        condition: Optional callable ``(context) -> bool`` that must return True for this entry to drop.
    """

    def __init__(self, item: Any, weight: int = 1, min_amount: int = 1,
            max_amount: int = 1, condition: Optional[Callable[..., bool]] = None):
        """Initialise a new LootEntry."""
        self.item = item
        self.weight = max(1, weight)
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.condition = condition

    def _matches(self, context: Any) -> bool:
        """Handle matches."""
        if self.condition is None:
            return True

        try:
            return bool(self.condition(context))
        except Exception:
            return False

    def _roll_amount(self) -> int:
        """Return the roll amount."""
        return random.randint(self.min_amount, self.max_amount)

    def _resolve_item(self) -> dict:
        """Return a dict representation of the dropped item."""
        if isinstance(self.item, dict):
            result = dict(self.item)
            result.setdefault("amount", self._roll_amount())
            return result

        return {"material": str(self.item), "amount": self._roll_amount()}

class LootPool:
    """A pool of loot entries with configurable rolls.

    Args:
        name: Pool identifier.
        rolls: Number of items to pick per generation. Default 1.
        bonus_rolls: Extra rolls based on luck. Default 0.
    """

    def __init__(self, name: str = "pool", rolls: int = 1, bonus_rolls: int = 0):
        """Initialise a new LootPool."""
        self.name = name
        self.rolls = rolls
        self.bonus_rolls = bonus_rolls
        self._entries: List[LootEntry] = []

    def add(
            self, item: Any, weight: int = 1, min_amount: int = 1,
            max_amount: int = 1,
            condition: Optional[Callable[..., bool]] = None,
    ) -> LootEntry:
        """Add an entry to this pool.

        Args:
            item: Material name or item dict.
            weight: Relative probability weight.
            min_amount: Minimum stack size.
            max_amount: Maximum stack size.
            condition: Optional condition function.
        """
        entry = LootEntry(item, weight, min_amount, max_amount, condition)
        self._entries.append(entry)
        return entry

    def entry(self, item: Any, weight: int = 1, min_amount: int = 1,
            max_amount: int = 1,
            condition: Optional[Callable[..., bool]] = None):
        """Decorator-style entry registration. Returns the condition function."""
        def decorator(func: Callable[..., bool]) -> Callable[..., bool]:
            """Register as a decorator."""
            self.add(item, weight, min_amount, max_amount, condition=func)
            return func

        return decorator

    def generate(self, context: Any = None, luck: float = 0.0) -> List[dict]:
        """Generate loot from this pool.

        Args:
            context: Arbitrary context passed to condition functions.
            luck: Luck factor that scales bonus_rolls.

        Returns:
            List of item dicts representing dropped items.
        """
        eligible = [e for e in self._entries if e._matches(context)]
        if not eligible:
            return []

        total_rolls = self.rolls + int(self.bonus_rolls * luck)
        total_rolls = max(0, total_rolls)

        weights = [e.weight for e in eligible]
        results: List[dict] = []

        for _ in range(total_rolls):
            chosen = random.choices(eligible, weights=weights, k=1)[0]
            results.append(chosen._resolve_item())

        return results

class LootTable:
    """Custom loot table with multiple pools.

    Example::
        loot = LootTable("dungeon_chest")

        common = loot.add_pool("common", rolls=3)
        common.add("IRON_INGOT", weight=10, min_amount=1, max_amount=5)
        common.add("GOLD_INGOT", weight=5, min_amount=1, max_amount=3)
        common.add("DIAMOND", weight=1)

        rare = loot.add_pool("rare", rolls=1, bonus_rolls=1)
        rare.add("ENCHANTED_GOLDEN_APPLE", weight=1, condition=lambda ctx: ctx.get("difficulty") == "hard")
        rare.add("GOLDEN_APPLE", weight=5)

        # Generate loot
        items = loot.generate(context={"difficulty": "hard"}, luck=1.0)
        # -> [{"material": "IRON_INGOT", "amount": 3}, {"material": "GOLD_INGOT", "amount": 2}, ...]
        # Give to player
        for item_data in items:
            await player.inventory.add_item(item_data["material"], item_data.get("amount", 1))
    """

    def __init__(self, name: str = "loot_table"):
        """Initialise a new LootTable."""
        self.name = name
        self._pools: Dict[str, LootPool] = {}

    def add_pool(self, name: str = "pool", rolls: int = 1,
            bonus_rolls: int = 0) -> LootPool:
        """Add a loot pool to this table."""
        pool = LootPool(name, rolls, bonus_rolls)
        self._pools[name] = pool
        return pool

    def get_pool(self, name: str) -> Optional[LootPool]:
        """Return the pool."""
        return self._pools.get(name)

    def remove_pool(self, name: str):
        """Remove a pool."""
        self._pools.pop(name, None)

    @property
    def pools(self) -> List[LootPool]:
        """The pools value."""
        return list(self._pools.values())

    def generate(self, context: Any = None, luck: float = 0.0) -> List[dict]:
        """Generate loot from all pools.

        Args:
            context: Arbitrary context passed to all pool condition functions.
            luck: Luck factor applied to bonus rolls in all pools.

        Returns:
            Combined list of item dicts from all pools.
        """
        results: List[dict] = []
        for pool in self._pools.values():
            results.extend(pool.generate(context, luck))

        return results

    def generate_stacked(self, context: Any = None,
            luck: float = 0.0) -> List[dict]:
        """Generate loot and combine items of the same material into stacks.

        Returns:
            List of item dicts with amounts combined.
        """
        raw = self.generate(context, luck)
        stacked: Dict[str, dict] = {}
        for item in raw:
            key = item.get("material", "")
            if key in stacked:
                stacked[key]["amount"] = stacked[key].get("amount", 1) + item.get("amount", 1)
            else:
                stacked[key] = dict(item)

        return list(stacked.values())
