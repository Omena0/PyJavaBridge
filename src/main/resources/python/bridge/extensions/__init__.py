"""PyJavaBridge extension modules.

Import extensions individually::

    from bridge.extensions import NPC
    from bridge.extensions import ImageDisplay
    from bridge.extensions import MeshDisplay
    from bridge.extensions import Quest, QuestTree
    from bridge.extensions import Dialog, DialogEntry
    from bridge.extensions import Bank
    from bridge.extensions import Shop
    from bridge.extensions import TradeWindow
    from bridge.extensions import Ability
    from bridge.extensions import ManaStore
    from bridge.extensions import CombatSystem
    from bridge.extensions import LevelSystem
    from bridge.extensions import Region
    from bridge.extensions import Party
    from bridge.extensions import Guild
    from bridge.extensions import CustomItem
    from bridge.extensions import Leaderboard
    from bridge.extensions import VisualEffect
    from bridge.extensions import PlayerDataStore
    from bridge.extensions import Dungeon, DungeonInstance, PlacedRoom, RoomTemplate, loot_pool
"""

from bridge.extensions.npc import NPC
from bridge.extensions.image_display import ImageDisplay
from bridge.extensions.mesh_display import MeshDisplay
from bridge.extensions.quest import Quest, QuestTree
from bridge.extensions.dialog import Dialog, DialogEntry
from bridge.extensions.bank import Bank
from bridge.extensions.shop import Shop
from bridge.extensions.trade import TradeWindow
from bridge.extensions.ability import Ability
from bridge.extensions.mana import ManaStore
from bridge.extensions.combat import CombatSystem
from bridge.extensions.levels import LevelSystem
from bridge.extensions.region import Region
from bridge.extensions.party import Party
from bridge.extensions.guild import Guild
from bridge.extensions.leaderboard import Leaderboard
from bridge.extensions.custom_item import CustomItem
from bridge.extensions.visual_effect import VisualEffect
from bridge.extensions.player_data import PlayerDataStore
from bridge.extensions.dungeon import Dungeon, DungeonInstance, PlacedRoom, RoomTemplate, Exit, loot_pool

__all__ = [
    "NPC",
    "ImageDisplay",
    "MeshDisplay",
    "Quest", "QuestTree",
    "Dialog", "DialogEntry",
    "Bank",
    "Shop",
    "TradeWindow",
    "Ability",
    "ManaStore",
    "CombatSystem",
    "LevelSystem",
    "Region",
    "Party",
    "Guild",
    "CustomItem",
    "Leaderboard",
    "VisualEffect",
    "PlayerDataStore",
    "Dungeon", "DungeonInstance", "PlacedRoom", "RoomTemplate", "Exit", "loot_pool",
]
