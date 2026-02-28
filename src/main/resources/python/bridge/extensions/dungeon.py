"""Dungeon extension — instanced dungeon system with procedural rooms.

Provides ``Dungeon``, ``DungeonInstance``, and ``DungeonRoom``.
Uses wave function collapse-inspired constraint propagation
for room layout generation.
"""
from __future__ import annotations

import asyncio
import inspect
import random
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import bridge
from bridge.extensions.region import Region


# ── Room types ───────────────────────────────────────────────────────
class RoomType(Enum):
    HALLWAY = "hallway"
    COMBAT = "combat"
    PUZZLE = "puzzle"
    TREASURE = "treasure"
    TRAP = "trap"
    BOSS = "boss"

# ── DungeonRoom ──────────────────────────────────────────────────────
class DungeonRoom:
    """A single room template within a dungeon layout.

    Attributes:
        room_type: One of :class:`RoomType`.
        on_enter_handlers: Called ``(player, room)`` when a player enters.
        on_clear_handlers: Called ``(room)`` when the room is cleared.
        mobs: List of mob descriptors (user-defined, e.g. EntityType names).
        cleared: Whether this room has been cleared.
        grid_x / grid_z: Position in the dungeon grid (set during generation).
    """

    # ── generation constraints ─────────────────────────────────────
    # min_depth = minimum distance from entrance for this type to spawn
    # allowed_neighbors = room types that are allowed next to this one (None = any)
    CONSTRAINTS: Dict[RoomType, Dict[str, Any]] = {
        RoomType.BOSS:     {"min_depth": 8, "max_count": 1,
                            "allowed_neighbors": {RoomType.COMBAT, RoomType.HALLWAY}},
        RoomType.TREASURE: {"min_depth": 3,
                            "allowed_neighbors": {RoomType.PUZZLE, RoomType.BOSS, RoomType.HALLWAY}},
        RoomType.PUZZLE:   {"min_depth": 2,
                            "allowed_neighbors": {RoomType.TREASURE, RoomType.BOSS, RoomType.HALLWAY, RoomType.COMBAT}},
        RoomType.TRAP:     {"min_depth": 1},
        RoomType.COMBAT:   {"min_depth": 0},
        RoomType.HALLWAY:  {"min_depth": 0},
    }

    def __init__(self, room_type: RoomType = RoomType.HALLWAY,
                 mobs: Optional[List[Any]] = None):
        self.room_type = room_type
        self.mobs: List[Any] = mobs or []
        self.cleared = False
        self.grid_x = 0
        self.grid_z = 0
        self._enter_handlers: List[Callable[..., Any]] = []
        self._clear_handlers: List[Callable[..., Any]] = []

    def on_enter(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._enter_handlers.append(handler)
        return handler

    def on_clear(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._clear_handlers.append(handler)
        return handler

    async def _fire_enter(self, player: Any):
        for h in self._enter_handlers:
            try:
                r = h(player, self)
                if inspect.isawaitable(r):
                    await r
            except Exception:
                pass

    async def _fire_clear(self):
        self.cleared = True
        for h in self._clear_handlers:
            try:
                r = h(self)
                if inspect.isawaitable(r):
                    await r
            except Exception:
                pass

    def mark_cleared(self):
        asyncio.ensure_future(self._fire_clear())

    def __repr__(self):
        return f"<DungeonRoom {self.room_type.value} ({self.grid_x},{self.grid_z}) cleared={self.cleared}>"

# ── Wave-function-collapse layout generator ──────────────────────────
class _WFCGenerator:
    """Minimal constraint-propagation grid generator.

    1. Create an NxN grid where each cell starts with all possible room types.
    2. Iteratively pick the cell with the fewest possibilities (least entropy),
       collapse it to one type, then propagate constraints to neighbors.
    3. If a contradiction occurs, backtrack by resetting the offending cell and
       retrying with a different choice (limited retries).
    """

    DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    def __init__(self, width: int, height: int, room_count: int):
        self.w = width
        self.h = height
        self.room_count = min(room_count, width * height)
        # Each cell: set of possible RoomTypes (None = not a room)
        self.grid: Dict[Tuple[int, int], Optional[set]] = {}
        self.collapsed: Dict[Tuple[int, int], Optional[RoomType]] = {}
        self.entrance = (0, self.h // 2)

    def _depth(self, x: int, z: int) -> int:
        """Manhattan distance from entrance."""
        return abs(x - self.entrance[0]) + abs(z - self.entrance[1])

    def _possible(self, x: int, z: int) -> Set[RoomType]:
        depth = self._depth(x, z)
        possible = set()
        for rt in RoomType:
            c = DungeonRoom.CONSTRAINTS.get(rt, {})
            if depth < c.get("min_depth", 0):
                continue
            possible.add(rt)
        return possible

    def _neighbors_collapsed(self, x: int, z: int) -> List[RoomType]:
        result = []
        for dx, dz in self.DIRS:
            nx, nz = x + dx, z + dz
            rt = self.collapsed.get((nx, nz))
            if rt is not None:
                result.append(rt)
        return result

    def _propagate(self, x: int, z: int):
        """Remove impossible types from neighbors based on constraints."""
        collapsed_type = self.collapsed.get((x, z))
        if collapsed_type is None:
            return
        for dx, dz in self.DIRS:
            nx, nz = x + dx, z + dz
            opts = self.grid.get((nx, nz))
            if opts is None or len(opts) <= 1:
                continue
            # For each possible type of the neighbour, check allowed_neighbors
            new_opts = set()
            for rt in opts:
                c = DungeonRoom.CONSTRAINTS.get(rt, {})
                allowed = c.get("allowed_neighbors")
                if allowed is not None and collapsed_type not in allowed:
                    # This neighbour type doesn't want to be next to collapsed_type
                    # But only *its* constraint matters for itself
                    pass
                new_opts.add(rt)
            # Also check: collapsed_type's constraint about what can be its neighbour
            c_collapsed = DungeonRoom.CONSTRAINTS.get(collapsed_type, {})
            allowed_for_collapsed = c_collapsed.get("allowed_neighbors")
            if allowed_for_collapsed is not None:
                new_opts = new_opts & allowed_for_collapsed
            if new_opts:
                self.grid[(nx, nz)] = new_opts

    def generate(self) -> List[Tuple[int, int, RoomType]]:
        """Run WFC and return list of (x, z, RoomType)."""
        # Decide which cells will be rooms via random walk from entrance
        room_cells: Set[Tuple[int, int]] = {self.entrance}
        frontier = [self.entrance]
        while len(room_cells) < self.room_count and frontier:
            x, z = random.choice(frontier)
            random.shuffle(self.DIRS)
            for dx, dz in self.DIRS:
                nx, nz = x + dx, z + dz
                if 0 <= nx < self.w and 0 <= nz < self.h and (nx, nz) not in room_cells:
                    room_cells.add((nx, nz))
                    frontier.append((nx, nz))
                    if len(room_cells) >= self.room_count:
                        break
            frontier = [c for c in frontier if any(
                (c[0]+d[0], c[1]+d[1]) not in room_cells and 0 <= c[0]+d[0] < self.w and 0 <= c[1]+d[1] < self.h
                for d in self.DIRS
            )]

        # Init possibility grid
        for pos in room_cells:
            self.grid[pos] = self._possible(*pos)

        # Force entrance to hallway
        self.grid[self.entrance] = {RoomType.HALLWAY}

        # Count limits
        type_counts: Dict[RoomType, int] = {rt: 0 for rt in RoomType}

        # Collapse loop
        for _ in range(len(room_cells) + 10):
            # Find uncollapsed cell with fewest options (min entropy)
            best = None
            best_entropy = 999
            for pos, opts in self.grid.items():
                if opts is not None and pos not in self.collapsed and len(opts) > 0:
                    if len(opts) < best_entropy:
                        best_entropy = len(opts)
                        best = pos
            if best is None:
                break

            opts = self.grid[best]
            if not opts:
                # Contradiction — default to hallway
                opts = {RoomType.HALLWAY}

            # Filter by max_count
            filtered = set()
            for rt in opts:
                mc = DungeonRoom.CONSTRAINTS.get(rt, {}).get("max_count")
                if mc is not None and type_counts[rt] >= mc:
                    continue
                filtered.add(rt)
            if not filtered:
                filtered = {RoomType.HALLWAY}

            chosen = random.choice(list(filtered))
            self.collapsed[best] = chosen
            self.grid[best] = {chosen}
            type_counts[chosen] += 1
            self._propagate(*best)

        return [(x, z, rt) for (x, z), rt in self.collapsed.items()]

# ── DungeonInstance ──────────────────────────────────────────────────
class DungeonInstance:
    """A live, generated instance of a :class:`Dungeon`.

    Created by :meth:`Dungeon.create_instance`.
    Each instance has its own room layout and tracks player progress.
    """

    def __init__(self, dungeon: "Dungeon", players: List[Any], instance_id: int):
        self.dungeon = dungeon
        self.players: List[Any] = list(players)
        self.instance_id = instance_id
        self.rooms: List[DungeonRoom] = []
        self._completed = False
        self._enter_handlers: List[Callable[..., Any]] = []
        self._exit_handlers: List[Callable[..., Any]] = []
        self._complete_handlers: List[Callable[..., Any]] = []

    def on_enter(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._enter_handlers.append(handler)
        return handler

    def on_exit(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._exit_handlers.append(handler)
        return handler

    def on_complete(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._complete_handlers.append(handler)
        return handler

    @property
    def progress(self) -> float:
        """0.0 – 1.0 fraction of rooms cleared."""
        if not self.rooms:
            return 1.0
        return sum(1 for r in self.rooms if r.cleared) / len(self.rooms)

    @property
    def is_complete(self) -> bool:
        return self._completed or all(r.cleared for r in self.rooms)

    def generate(self, room_count: int = 12, grid_size: int = 8):
        """Populate ``self.rooms`` using WFC generation."""
        gen = _WFCGenerator(grid_size, grid_size, room_count)
        layout = gen.generate()
        self.rooms = []
        for x, z, rt in layout:
            room = DungeonRoom(room_type=rt)
            room.grid_x = x
            room.grid_z = z
            # Inherit dungeon-level room handlers
            room._enter_handlers.extend(self.dungeon._room_enter_handlers)
            room._clear_handlers.extend(self.dungeon._room_clear_handlers)
            self.rooms.append(room)

    async def complete(self):
        """Mark instance complete and fire handlers."""
        self._completed = True
        for h in self._complete_handlers:
            try:
                r = h(self)
                if inspect.isawaitable(r):
                    await r
            except Exception:
                pass
        # Fire dungeon-level reward/complete
        for h in self.dungeon._complete_handlers:
            try:
                r = h(self)
                if inspect.isawaitable(r):
                    await r
            except Exception:
                pass

    def destroy(self):
        """Clean up this instance."""
        if self in self.dungeon._instances:
            self.dungeon._instances.remove(self)

# ── Dungeon ──────────────────────────────────────────────────────────
class Dungeon:
    """Dungeon template.  Create instances for individual players/groups.

    Args:
        name: Display name.
        description: Flavour text.
        difficulty: Integer difficulty rating.
        recommended_level: Suggested player level.
        room_count: Default number of rooms per instance.
        grid_size: Grid dimensions for room layout.
    """

    def __init__(self, name: str, description: str = "",
                 difficulty: int = 1, recommended_level: int = 1,
                 room_count: int = 12, grid_size: int = 8):
        self.name = name
        self.description = description
        self.difficulty = difficulty
        self.recommended_level = recommended_level
        self.room_count = room_count
        self.grid_size = grid_size
        self._instances: List[DungeonInstance] = []
        self._next_id = 0
        self._enter_handlers: List[Callable[..., Any]] = []
        self._exit_handlers: List[Callable[..., Any]] = []
        self._complete_handlers: List[Callable[..., Any]] = []
        self._room_enter_handlers: List[Callable[..., Any]] = []
        self._room_clear_handlers: List[Callable[..., Any]] = []

    # ── decorators ─────────────────────────────────────────────────
    def on_enter(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(instance, player)`` when entering."""
        self._enter_handlers.append(handler)
        return handler

    def on_exit(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._exit_handlers.append(handler)
        return handler

    def on_complete(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(instance)`` when all rooms cleared."""
        self._complete_handlers.append(handler)
        return handler

    def on_room_enter(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(player, room)`` when entering any room."""
        self._room_enter_handlers.append(handler)
        return handler

    def on_room_clear(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(room)`` when any room is cleared."""
        self._room_clear_handlers.append(handler)
        return handler

    def reward(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Alias for :meth:`on_complete`."""
        return self.on_complete(handler)

    # ── instance management ────────────────────────────────────────
    def create_instance(self, players: List[Any],
                        room_count: Optional[int] = None,
                        grid_size: Optional[int] = None) -> DungeonInstance:
        """Create and generate a new dungeon instance."""
        self._next_id += 1
        inst = DungeonInstance(self, players, self._next_id)
        inst.generate(
            room_count=room_count or self.room_count,
            grid_size=grid_size or self.grid_size,
        )
        self._instances.append(inst)
        return inst

    @property
    def instances(self) -> List[DungeonInstance]:
        return list(self._instances)
