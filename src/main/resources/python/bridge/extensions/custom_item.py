"""CustomItem extension — registered custom items with a global registry."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import bridge


class CustomItem:
    """Base class for custom items with a global registry.

    Subclass this to create custom items that can be looked up by id.

    Args:
        item_id: Unique identifier for this custom item type.
        material: Base Minecraft material.
        name: Display name.
        lore: Item lore lines.
        custom_model_data: Custom model data int.
    """

    _registry: Dict[str, "CustomItem"] = {}

    def __init__(self, item_id: str, material: str = "DIAMOND",
                 name: Optional[str] = None, lore: Optional[List[str]] = None,
                 custom_model_data: Optional[int] = None,
                 **kwargs: Any):
        self.item_id = item_id
        self.material = material
        self.display_name = name
        self.lore = lore or []
        self.custom_model_data = custom_model_data
        self._extra = kwargs
        CustomItem._registry[item_id] = self

    def build(self) -> Any:
        """Create a bridge Item from this custom item definition."""
        from bridge.wrappers import Item
        return Item(
            material=self.material,
            name=self.display_name,
            lore=self.lore,
            custom_model_data=self.custom_model_data,
        )

    def give(self, player: Any, amount: int = 1):
        """Give this custom item to a player."""
        from bridge.wrappers import Item
        Item.give(player, material=self.material, amount=amount,
                  name=self.display_name, lore=self.lore,
                  custom_model_data=self.custom_model_data)

    @classmethod
    def get(cls, item_id: str) -> Optional["CustomItem"]:
        return cls._registry.get(item_id)

    @classmethod
    def all(cls) -> Dict[str, "CustomItem"]:
        return dict(cls._registry)
