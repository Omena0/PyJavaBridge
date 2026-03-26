"""CustomItem extension — registered custom items with a global registry.

Extends :class:`~bridge.wrappers.ItemBuilder` so every fluent builder
method (`$1`, `$1`, `$1`, `$1`, etc.) is available
directly on CustomItem instances.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from bridge.wrappers import ItemBuilder

class CustomItem(ItemBuilder):
    """Custom item with a global registry, inheriting all ItemBuilder methods.

    Subclass or instantiate to create custom items that can be looked up by id.
    All :class:`~bridge.wrappers.ItemBuilder` fluent methods are available.

    Args:
        item_id: Unique identifier for this custom item type.
        material: Base Minecraft material.
    """

    _registry: Dict[str, "CustomItem"] = {}

    def __init__(self, item_id: str, material: str = "DIAMOND"):
        """Initialise a new CustomItem."""
        super().__init__(material)
        self.item_id = item_id
        CustomItem._registry[item_id] = self

    def give(self, player: Any, amount: int = 1):
        """Give this custom item to a player."""
        self.amount(amount)
        item = self.build()
        player.give(item)

    @classmethod
    def get(cls, item_id: str) -> Optional["CustomItem"]:
        """Get by key."""
        return cls._registry.get(item_id)

    @classmethod
    def all(cls) -> Dict[str, "CustomItem"]:
        """Return all entries."""
        return dict(cls._registry)
