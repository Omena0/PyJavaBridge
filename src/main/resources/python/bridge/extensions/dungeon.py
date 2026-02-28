"""Dungeon extension — instanced dungeon system with real world generation.

Rooms are stored as ``.droom`` files.  The generator recursively builds
from a starting room, connecting exits to new rooms, prioritising the
exit with the fewest valid room choices (lowest entropy) first.

Think Minecraft jigsaw blocks: each exit has an exact position within
the room, a facing direction, a size, and a tag.  Two exits can connect
when they have the **same tag and same size** and face opposite
directions.  The generator places the new room so the two openings
line up block-for-block, then checks for AABB overlap against every
room already placed.

.droom file format
------------------
A ``.droom`` file has two sections separated by a ``---`` line:

**Metadata** (key: value, one per line)::

    type: combat
    weight: 10
    width: 9
    height: 5
    depth: 9
    loot: chest1=common chest2=rare

**Exit definitions** (``exit: x,y,z facing WxH [tag]``)::

    exit: 0,0,4 -x 3x3
    exit: 8,0,4 +x 3x3
    exit: 4,3,0 -z 2x2 upper

``facing`` is one of ``+x  -x  +y  -y  +z  -z``.
``tag`` is optional and defaults to ``WxH`` (e.g. ``3x3``).
Exits connect when they share the same **tag** and **size**, facing
opposite directions.

**Block keys** (single character = block definition)::

    S: stone_bricks
    C: chest[facing=north,name=[loot:chest1]]

``~`` is always air (hardcoded, no definition needed).

**Block data** (after the ``---`` separator)::

    A single line of RLE-encoded block keys.
    Blocks are stored in Y -> Z -> X order (row-major), so the first
    ``width`` characters are Y=0, Z=0; the next ``width`` are Y=0, Z=1;
    after ``width * depth`` characters layer Y=1 begins, and so on.
    Run-length: ``S3`` = ``SSS``, ``~5`` = ``~~~~~``.

Example ``.droom`` file::

    type: combat
    weight: 10
    width: 5
    height: 1
    depth: 5
    loot: chest1=common

    exit: 0,0,2 -x 1x1
    exit: 4,0,2 +x 1x1

    S: stone_bricks
    C: chest[facing=north,name=[loot:chest1]]

    ---
    ~2S~3SCS~S5~S3~3S~2

Use ``/bridge schem <x> <y> <z> <width> <height> <depth>`` in-game
to capture a region as a ``.droom`` file.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import random
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from bridge.extensions.region import Region


# -- Facing directions ---------------------------------------------------------
FACING: Dict[str, Tuple[int, int, int]] = {
    "+x": (1, 0, 0),  "-x": (-1, 0, 0),
    "+y": (0, 1, 0),  "-y": (0, -1, 0),
    "+z": (0, 0, 1),  "-z": (0, 0, -1),
}
FACING_NAME: Dict[Tuple[int, int, int], str] = {v: k for k, v in FACING.items()}

def _opposite_facing(f: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return (-f[0], -f[1], -f[2])

# -- .droom file parser / writer -----------------------------------------------
def _expand_rle(row_str: str) -> List[str]:
    """Expand a run-length encoded string into a list of single-char keys.

    ``S3`` -> ``['S','S','S']``, ``~`` -> ``['~']``, ``AB2C`` -> ``['A','B','B','C']``.
    """
    result: List[str] = []
    i = 0
    while i < len(row_str):
        ch = row_str[i]
        i += 1
        num_str = ""
        while i < len(row_str) and row_str[i].isdigit():
            num_str += row_str[i]
            i += 1
        count = int(num_str) if num_str else 1
        result.extend([ch] * count)
    return result

def _compress_rle(keys: List[str]) -> str:
    """Compress a list of single-char keys into an RLE string."""
    if not keys:
        return ""
    parts: List[str] = []
    cur = keys[0]
    count = 1
    for k in keys[1:]:
        if k == cur:
            count += 1
        else:
            parts.append(cur if count == 1 else f"{cur}{count}")
            cur = k
            count = 1
    parts.append(cur if count == 1 else f"{cur}{count}")
    return "".join(parts)

# -- Exit definition -----------------------------------------------------------
class Exit:
    """An exit/connection point within a room template (like a jigsaw block).

    Attributes:
        x, y, z:   Position inside the room (local coordinates).
        facing:     Outward-facing direction ``(dx, dy, dz)`` unit vector.
        width:      Opening width (along the plane perpendicular to facing).
        height:     Opening height.
        tag:        Matching tag -- exits connect when they share the same
                    tag *and* size and face opposite directions.
                    Defaults to ``"WxH"``.
    """

    __slots__ = ("x", "y", "z", "facing", "width", "height", "tag")

    def __init__(self, x: int, y: int, z: int,
                 facing: Tuple[int, int, int],
                 width: int, height: int,
                 tag: Optional[str] = None):
        self.x = x
        self.y = y
        self.z = z
        self.facing = facing
        self.width = width
        self.height = height
        self.tag = tag or f"{width}x{height}"

    def can_connect(self, other: "Exit") -> bool:
        """True if *other* is a valid partner for this exit."""
        return (self.tag == other.tag
                and self.width == other.width
                and self.height == other.height
                and other.facing == _opposite_facing(self.facing))

    def __repr__(self) -> str:
        f = FACING_NAME.get(self.facing, str(self.facing))
        return f"Exit({self.x},{self.y},{self.z} {f} {self.width}x{self.height} {self.tag!r})"

    @classmethod
    def parse(cls, text: str) -> "Exit":
        """Parse ``x,y,z facing WxH [tag]`` from a .droom exit line."""
        parts = text.split()
        if len(parts) < 3:
            raise ValueError(f"Bad exit definition: {text!r}")
        coords = parts[0].split(",")
        x, y, z = int(coords[0]), int(coords[1]), int(coords[2])
        facing = FACING.get(parts[1])
        if facing is None:
            raise ValueError(f"Unknown facing {parts[1]!r} in exit: {text!r}")
        wh = parts[2].lower().split("x")
        w, h = int(wh[0]), int(wh[1])
        tag = parts[3] if len(parts) > 3 else None
        return cls(x, y, z, facing, w, h, tag)

    def serialize(self) -> str:
        """Serialize to .droom format: ``x,y,z facing WxH [tag]``."""
        f = FACING_NAME[self.facing]
        s = f"{self.x},{self.y},{self.z} {f} {self.width}x{self.height}"
        default_tag = f"{self.width}x{self.height}"
        if self.tag != default_tag:
            s += f" {self.tag}"
        return s

# -- Room template -------------------------------------------------------------
class RoomTemplate:
    """A room blueprint loaded from a ``.droom`` file.

    Attributes:
        name:     Filename stem (e.g. ``"hallway_1"``).
        path:     Absolute path to the ``.droom`` file.
        type:     Free-form type tag (``"combat"``, ``"hallway"``, ...).
        exits:    List of :class:`Exit` definitions.
        weight:   Spawn weight for the generator.
        loot:     ``{tag: pool}`` mapping for container filling.
        key_map:  ``{char: block_string}`` (without ``minecraft:`` prefix).
        width:    X size of the room.
        height:   Y size (number of layers).
        depth:    Z size of the room.
        blocks:   3-D list ``[y][z][x]`` of full block strings (with ``minecraft:``).
    """

    def __init__(self, name: str, path: str, room_type: str,
                 exits: List[Exit], weight: int,
                 loot: Dict[str, str],
                 key_map: Dict[str, str],
                 width: int, height: int, depth: int,
                 blocks: List[List[List[str]]]):
        self.name = name
        self.path = path
        self.type = room_type
        self.exits = exits
        self.weight = weight
        self.loot = loot
        self.key_map = key_map
        self.width = width
        self.height = height
        self.depth = depth
        self.blocks = blocks

    @classmethod
    def load(cls, path: str) -> "RoomTemplate":
        """Parse a ``.droom`` file."""
        with open(path, "r") as f:
            raw = f.read()

        if "---" not in raw:
            raise ValueError(f"Missing --- separator in {path}")

        meta_part, block_part = raw.split("---", 1)

        # Parse metadata, exit definitions, and key definitions
        room_type = "generic"
        exits: List[Exit] = []
        weight = 10
        loot: Dict[str, str] = {}
        key_map: Dict[str, str] = {"~": "air"}
        meta_width: Optional[int] = None
        meta_height: Optional[int] = None
        meta_depth: Optional[int] = None

        for line in meta_part.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()

            # Single-character = block key definition
            if len(key) == 1 and key != "~":
                key_map[key] = value
                continue

            meta_key = key.lower()
            if meta_key == "type":
                room_type = value
            elif meta_key == "exit":
                exits.append(Exit.parse(value))
            elif meta_key == "weight":
                weight = int(value)
            elif meta_key == "width":
                meta_width = int(value)
            elif meta_key == "height":
                meta_height = int(value)
            elif meta_key == "depth":
                meta_depth = int(value)
            elif meta_key == "loot":
                for pair in value.split():
                    if "=" in pair:
                        tag, _, pool = pair.partition("=")
                        loot[tag] = pool

        # Block data -- single RLE line, decode with dimensions
        block_line = block_part.strip()
        if not block_line:
            raise ValueError(f"Empty block data in {path}")

        if meta_width is None or meta_height is None or meta_depth is None:
            raise ValueError(f"Missing width/height/depth in metadata of {path}")

        char_keys = _expand_rle(block_line)
        expected = meta_width * meta_height * meta_depth
        if len(char_keys) != expected:
            raise ValueError(
                f"Block data length {len(char_keys)} != "
                f"width*height*depth {expected} in {path}"
            )

        # Reconstruct [y][z][x] from flat list (Y -> Z -> X order)
        layers: List[List[List[str]]] = []
        idx = 0
        for _y in range(meta_height):
            layer: List[List[str]] = []
            for _z in range(meta_depth):
                row: List[str] = []
                for _x in range(meta_width):
                    ch = char_keys[idx]
                    idx += 1
                    block_def = key_map.get(ch, "air")
                    row.append(f"minecraft:{block_def}")
                layer.append(row)
            layers.append(layer)

        name = os.path.splitext(os.path.basename(path))[0]
        return cls(name, path, room_type, exits, weight, loot, key_map,
                   meta_width, meta_height, meta_depth, layers)

    def to_droom(self) -> str:
        """Serialize back to ``.droom`` format."""
        lines: List[str] = []
        lines.append(f"type: {self.type}")
        if self.weight != 10:
            lines.append(f"weight: {self.weight}")
        lines.append(f"width: {self.width}")
        lines.append(f"height: {self.height}")
        lines.append(f"depth: {self.depth}")
        if self.loot:
            pairs = " ".join(f"{t}={p}" for t, p in self.loot.items())
            lines.append(f"loot: {pairs}")
        lines.append("")

        # Write exit definitions
        for ex in self.exits:
            lines.append(f"exit: {ex.serialize()}")
        if self.exits:
            lines.append("")

        # Write key definitions (skip ~ since it's hardcoded)
        for ch, block_def in sorted(self.key_map.items()):
            if ch == "~":
                continue
            lines.append(f"{ch}: {block_def}")
        lines.append("")
        lines.append("---")

        # Build reverse map: full block string -> key char
        reverse: Dict[str, str] = {}
        for ch, block_def in self.key_map.items():
            reverse[f"minecraft:{block_def}"] = ch

        # Flatten blocks to a single RLE string (Y -> Z -> X order)
        flat_keys: List[str] = []
        for layer in self.blocks:
            for row in layer:
                for b in row:
                    flat_keys.append(reverse.get(b, "~"))
        lines.append(_compress_rle(flat_keys))

        return "\n".join(lines) + "\n"

# -- Placed room instance ------------------------------------------------------
class PlacedRoom:
    """A room that has been pasted into the world.

    Attributes:
        template:     The :class:`RoomTemplate` used.
        origin:       ``(x, y, z)`` world position of the (0,0,0) corner.
        world:        World name.
        connected_exits: ``{exit_index: PlacedRoom or None}``.
        cleared:      Whether the room has been cleared.
        original_blocks: Saved block data for cleanup ``{(x,y,z): block_string}``.
    """

    def __init__(self, template: RoomTemplate, origin: Tuple[int, int, int],
                 world_name: str):
        self.template = template
        self.origin = origin
        self.world_name = world_name
        self.connected_exits: Dict[int, Optional["PlacedRoom"]] = {
            i: None for i in range(len(template.exits))
        }
        self.cleared = False
        self.original_blocks: Dict[Tuple[int, int, int], str] = {}
        self._enter_handlers: List[Callable[..., Any]] = []
        self._clear_handlers: List[Callable[..., Any]] = []
        self._region: Optional[Region] = None

    @property
    def aabb(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Axis-aligned bounding box ``(min_corner, max_corner)`` inclusive."""
        ox, oy, oz = self.origin
        return (
            (ox, oy, oz),
            (ox + self.template.width - 1,
             oy + self.template.height - 1,
             oz + self.template.depth - 1),
        )

    @property
    def center(self) -> Tuple[int, int, int]:
        ox, oy, oz = self.origin
        return (
            ox + self.template.width // 2,
            oy + self.template.height // 2,
            oz + self.template.depth // 2,
        )

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
        """Mark this room as cleared and fire handlers."""
        asyncio.ensure_future(self._fire_clear())

    async def paste(self, world: Any):
        """Paste the room blocks into the world and save originals."""
        ox, oy, oz = self.origin
        for yi, layer in enumerate(self.template.blocks):
            for zi, row in enumerate(layer):
                for xi, block_str in enumerate(row):
                    if block_str == "minecraft:air":
                        continue
                    wx, wy, wz = ox + xi, oy + yi, oz + zi
                    try:
                        orig = world.block_at(wx, wy, wz)
                        orig_type = str(orig.type) if orig else "minecraft:air"
                        orig_data = None
                        try:
                            orig_data = orig.data
                        except Exception:
                            pass
                        if orig_data:
                            self.original_blocks[(wx, wy, wz)] = str(orig_data)
                        else:
                            self.original_blocks[(wx, wy, wz)] = orig_type
                    except Exception:
                        self.original_blocks[(wx, wy, wz)] = "minecraft:air"

                    mat = block_str
                    if "[" in mat:
                        mat = mat.split("[")[0]
                    world.set_block(wx, wy, wz, mat)
                    if "[" in block_str:
                        try:
                            blk = world.block_at(wx, wy, wz)
                            blk.set_data(block_str)
                        except Exception:
                            pass

    async def restore(self, world: Any):
        """Restore original blocks (cleanup)."""
        for (wx, wy, wz), block_str in self.original_blocks.items():
            try:
                mat = block_str
                if "[" in mat:
                    mat = mat.split("[")[0]
                world.set_block(wx, wy, wz, mat)
                if "[" in block_str:
                    try:
                        blk = world.block_at(wx, wy, wz)
                        blk.set_data(block_str)
                    except Exception:
                        pass
            except Exception:
                pass
        self.original_blocks.clear()

    def __repr__(self):
        return (f"<PlacedRoom {self.template.name!r} at {self.origin} "
                f"cleared={self.cleared}>")

# -- Loot system ---------------------------------------------------------------

_loot_generators: Dict[str, Callable[..., Any]] = {}

def loot_pool(name: str):
    """Decorator to register a loot generator for a pool name.

    The decorated function receives ``(inventory, room)`` and should
    add items to the inventory.

    Example::

        @loot_pool("common")
        def fill_common(inventory, room):
            inventory.add_item(ItemBuilder("BREAD").amount(5).build())
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        _loot_generators[name] = func
        return func
    return decorator

async def _fill_loot(room: PlacedRoom, world: Any):
    """Scan placed room for loot containers and fill them."""
    ox, oy, oz = room.origin
    for yi, layer in enumerate(room.template.blocks):
        for zi, row in enumerate(layer):
            for xi, block_str in enumerate(row):
                mat_lower = block_str.lower()
                if "chest" not in mat_lower and "barrel" not in mat_lower and "shulker" not in mat_lower:
                    continue
                wx, wy, wz = ox + xi, oy + yi, oz + zi
                try:
                    blk = world.block_at(wx, wy, wz)
                    if not blk.is_container:
                        continue
                    inv = blk.inventory
                    title = inv.title if hasattr(inv, "title") else ""
                    if not title:
                        continue
                    match = re.search(r'\[loot:(\w+)\]', title)
                    if not match:
                        continue
                    tag = match.group(1)
                    pool = room.template.loot.get(tag, tag)
                    gen = _loot_generators.get(pool)
                    if gen:
                        result = gen(inv, room)
                        if inspect.isawaitable(result):
                            await result
                except Exception:
                    pass

# -- AABB helpers --------------------------------------------------------------

def _aabb_overlaps(
    min_a: Tuple[int, int, int], max_a: Tuple[int, int, int],
    min_b: Tuple[int, int, int], max_b: Tuple[int, int, int],
) -> bool:
    """True if two axis-aligned bounding boxes overlap (inclusive)."""
    return (min_a[0] <= max_b[0] and max_a[0] >= min_b[0]
            and min_a[1] <= max_b[1] and max_a[1] >= min_b[1]
            and min_a[2] <= max_b[2] and max_a[2] >= min_b[2])

def _room_aabb(
    origin: Tuple[int, int, int], t: RoomTemplate,
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Compute AABB for a template placed at *origin*."""
    ox, oy, oz = origin
    return (
        (ox, oy, oz),
        (ox + t.width - 1, oy + t.height - 1, oz + t.depth - 1),
    )

# -- Jigsaw-style dungeon generator -------------------------------------------
def _compute_new_origin(
    src_origin: Tuple[int, int, int],
    src_exit: Exit,
    dst_exit: Exit,
) -> Tuple[int, int, int]:
    """Compute the world origin for a new room so two exits align.

    The exits meet face-to-face: one block outside *src_exit* in its
    facing direction is where *dst_exit*'s anchor sits.
    """
    sx = src_origin[0] + src_exit.x
    sy = src_origin[1] + src_exit.y
    sz = src_origin[2] + src_exit.z
    dx, dy, dz = src_exit.facing
    return (sx + dx - dst_exit.x,
            sy + dy - dst_exit.y,
            sz + dz - dst_exit.z)

class _DungeonGenerator:
    """Jigsaw-style recursive dungeon generator.

    Strategy:
    1. Place the starting room.
    2. Collect all open (unconnected) exits across all placed rooms.
    3. For each open exit, find candidate ``(template, exit_index)``
       pairs that could physically attach without overlapping any
       placed room.
    4. **Lowest entropy first** -- prioritise the exit with the fewest
       valid candidates.  Prefer exits with at least ``min_candidates``
       options; if no exit meets the threshold fall back to whatever
       is available.
    5. Pick a candidate weighted by ``template.weight`` and place it.
    6. Repeat until ``room_count`` is reached or no open exits remain.

    Overlap is checked with AABB intersection against every placed room.
    """

    def __init__(self, templates: List[RoomTemplate],
                 room_count: int,
                 branch_factor: float,
                 type_limits: Dict[str, int],
                 min_candidates: int = 5):
        self.templates = templates
        self.room_count = room_count
        self.branch_factor = max(0.0, min(1.0, branch_factor))
        self.type_limits = type_limits
        self.min_candidates = min_candidates

        self.placed: List[PlacedRoom] = []
        self._aabbs: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = []
        self._type_counts: Dict[str, int] = {}

    # -- overlap ---------------------------------------------------------------

    def _overlaps_any(self, origin: Tuple[int, int, int],
                      template: RoomTemplate) -> bool:
        """Check if placing *template* at *origin* overlaps any placed room."""
        new_min, new_max = _room_aabb(origin, template)
        for pmin, pmax in self._aabbs:
            if _aabb_overlaps(new_min, new_max, pmin, pmax):
                return True
        return False

    # -- candidate search ------------------------------------------------------

    def _candidates_for_exit(
        self, room: PlacedRoom, exit_idx: int,
    ) -> List[Tuple[RoomTemplate, int, Tuple[int, int, int]]]:
        """Return ``(template, dst_exit_idx, new_origin)`` tuples
        for every template+exit that can attach to the given open exit
        without overlapping existing rooms."""
        src_exit = room.template.exits[exit_idx]
        results: List[Tuple[RoomTemplate, int, Tuple[int, int, int]]] = []

        for t in self.templates:
            limit = self.type_limits.get(t.type)
            if limit is not None and self._type_counts.get(t.type, 0) >= limit:
                continue

            for di, dst_exit in enumerate(t.exits):
                if not src_exit.can_connect(dst_exit):
                    continue
                new_origin = _compute_new_origin(room.origin, src_exit, dst_exit)
                if self._overlaps_any(new_origin, t):
                    continue
                results.append((t, di, new_origin))

        return results

    # -- main loop -------------------------------------------------------------

    def generate(self, start_template: RoomTemplate,
                 origin: Tuple[int, int, int],
                 world_name: str) -> List[PlacedRoom]:
        """Generate the dungeon layout and return placed rooms."""

        # Place starting room
        start = PlacedRoom(start_template, origin, world_name)
        self.placed.append(start)
        self._aabbs.append(_room_aabb(origin, start_template))
        self._type_counts[start_template.type] = 1

        # Open exits: (PlacedRoom, exit_index, depth)
        open_exits: List[Tuple[PlacedRoom, int, int]] = [
            (start, i, 0) for i in range(len(start_template.exits))
        ]

        while len(self.placed) < self.room_count and open_exits:
            # Score each open exit by number of viable candidates
            scored: List[Tuple[int, int, Tuple[PlacedRoom, int, int],
                               List[Tuple[RoomTemplate, int, Tuple[int, int, int]]]]] = []
            for item in open_exits:
                room, eidx, depth = item
                cands = self._candidates_for_exit(room, eidx)
                if cands:
                    scored.append((len(cands), depth, item, cands))

            if not scored:
                break

            # Prefer exits that meet the minimum candidates threshold
            above = [s for s in scored if s[0] >= self.min_candidates]
            pool = above if above else scored

            # Sort: lowest entropy first; depth tiebreak via branch_factor
            def sort_key(entry):
                entropy, depth, _, _ = entry
                depth_score = depth if self.branch_factor >= 0.5 else -depth
                return (entropy, depth_score, random.random())

            pool.sort(key=sort_key)

            # Occasional second-pick for variety
            pick_idx = 1 if (random.random() < 0.3 and len(pool) > 1) else 0
            _, _, (source_room, src_eidx, depth), cands = pool[pick_idx]

            # Remove this exit from open list
            open_exits = [
                item for item in open_exits
                if not (item[0] is source_room and item[1] == src_eidx)
            ]

            # Weighted random choice among candidates
            total_w = sum(c[0].weight for c in cands)
            r = random.uniform(0, total_w)
            cumulative = 0.0
            chosen_t, chosen_di, new_origin = cands[0]
            for ct, cdi, co in cands:
                cumulative += ct.weight
                if r <= cumulative:
                    chosen_t, chosen_di, new_origin = ct, cdi, co
                    break

            # Place the room
            new_room = PlacedRoom(chosen_t, new_origin, world_name)
            self.placed.append(new_room)
            self._aabbs.append(_room_aabb(new_origin, chosen_t))
            self._type_counts[chosen_t.type] = self._type_counts.get(chosen_t.type, 0) + 1

            # Link exits
            source_room.connected_exits[src_eidx] = new_room
            new_room.connected_exits[chosen_di] = source_room

            # Add the new room's other open exits
            new_depth = depth + 1
            for ei in range(len(chosen_t.exits)):
                if ei == chosen_di:
                    continue
                open_exits.append((new_room, ei, new_depth))

        return self.placed

# -- DungeonInstance -----------------------------------------------------------
class DungeonInstance:
    """A live dungeon placed in the world.

    Created by :meth:`Dungeon.create_instance`.
    """

    def __init__(self, dungeon: "Dungeon", players: List[Any],
                 instance_id: int, rooms: List[PlacedRoom],
                 world_name: str):
        self.dungeon = dungeon
        self.players: List[Any] = list(players)
        self.instance_id = instance_id
        self.rooms = rooms
        self.world_name = world_name
        self._completed = False
        self._tracker_task: Optional[asyncio.Task] = None

    @property
    def progress(self) -> float:
        """Fraction of rooms cleared (0.0 - 1.0)."""
        if not self.rooms:
            return 1.0
        return sum(1 for r in self.rooms if r.cleared) / len(self.rooms)

    @property
    def is_complete(self) -> bool:
        return self._completed or all(r.cleared for r in self.rooms)

    async def paste_all(self):
        """Paste all rooms into the world and fill loot."""
        from bridge.wrappers import World
        world = World(self.world_name)
        for room in self.rooms:
            await room.paste(world)
        for room in self.rooms:
            await _fill_loot(room, world)

    async def complete(self):
        """Mark the dungeon complete and fire completion handlers."""
        self._completed = True
        for h in self.dungeon._complete_handlers:
            try:
                r = h(self)
                if inspect.isawaitable(r):
                    await r
            except Exception:
                pass

    async def destroy(self):
        """Restore all original blocks and remove the instance."""
        if self._tracker_task and not self._tracker_task.done():
            self._tracker_task.cancel()
        from bridge.wrappers import World
        world = World(self.world_name)
        for room in self.rooms:
            await room.restore(world)
            if room._region:
                room._region.remove()
        if self in self.dungeon._instances:
            self.dungeon._instances.remove(self)

    def start_tracking(self):
        """Start polling player positions for room enter events."""
        self._tracker_task = asyncio.ensure_future(self._track_loop())

    async def _track_loop(self):
        """Poll players and fire room enter events."""
        from bridge.wrappers import server
        inside: Dict[str, Optional[PlacedRoom]] = {}

        while not self._completed:
            try:
                for player in self.players:
                    puuid = str(player.uuid)
                    try:
                        loc = player.location
                        px, py, pz = loc.x, loc.y, loc.z
                    except Exception:
                        continue

                    current = None
                    for room in self.rooms:
                        ox, oy, oz = room.origin
                        t = room.template
                        if (ox <= px < ox + t.width and
                                oy <= py < oy + t.height and
                                oz <= pz < oz + t.depth):
                            current = room
                            break

                    prev = inside.get(puuid)
                    if current is not None and current is not prev:
                        inside[puuid] = current
                        await current._fire_enter(player)
                        for h in self.dungeon._room_enter_handlers:
                            try:
                                r = h(player, current)
                                if inspect.isawaitable(r):
                                    await r
                            except Exception:
                                pass
                    elif current is None:
                        inside[puuid] = None

                await server.after(5)
            except asyncio.CancelledError:
                break
            except Exception:
                break

    def __repr__(self):
        return (f"<DungeonInstance #{self.instance_id} "
                f"rooms={len(self.rooms)} progress={self.progress:.0%}>")

# -- Dungeon template ----------------------------------------------------------
class Dungeon:
    """Dungeon template.  Load room files and create world instances.

    Args:
        name:           Display name.
        rooms_dir:      Path to directory containing ``.droom`` files.
        room_count:     Target number of rooms per instance.
        branch_factor:  0.0 = depth-first, 1.0 = breadth-first, 0.5 = balanced.
        min_candidates: Prefer exits with at least this many viable templates
                        before expanding (default 5).
        description:    Flavour text.
        difficulty:     Integer difficulty rating.
        start_room:     Name of the starting room template (without extension).
                        If ``None``, the first loaded template is used.
    """

    def __init__(self, name: str, rooms_dir: str,
                 room_count: int = 12,
                 branch_factor: float = 0.5,
                 min_candidates: int = 5,
                 description: str = "",
                 difficulty: int = 1,
                 start_room: Optional[str] = None):
        self.name = name
        self.rooms_dir = rooms_dir
        self.room_count = room_count
        self.branch_factor = branch_factor
        self.min_candidates = min_candidates
        self.description = description
        self.difficulty = difficulty
        self.start_room_name = start_room

        self._templates: List[RoomTemplate] = []
        self._instances: List[DungeonInstance] = []
        self._next_id = 0

        # Event handlers
        self._enter_handlers: List[Callable[..., Any]] = []
        self._complete_handlers: List[Callable[..., Any]] = []
        self._room_enter_handlers: List[Callable[..., Any]] = []
        # Called after rooms are pasted (room, world) -> optional async
        self._room_generate_handlers: List[Callable[..., Any]] = []
        self._room_clear_handlers: List[Callable[..., Any]] = []

        # Customisation
        self.type_limits: Dict[str, int] = {}

        # Auto-load templates
        self._load_templates()

    def _load_templates(self):
        """Scan ``rooms_dir`` for ``.droom`` files."""
        if not os.path.isdir(self.rooms_dir):
            return
        for fname in sorted(os.listdir(self.rooms_dir)):
            if fname.endswith(".droom"):
                path = os.path.join(self.rooms_dir, fname)
                try:
                    self._templates.append(RoomTemplate.load(path))
                except Exception as e:
                    print(f"[Dungeon] Failed to load {path}: {e}")

    def reload_templates(self):
        """Re-scan the rooms directory."""
        self._templates.clear()
        self._load_templates()

    @property
    def templates(self) -> List[RoomTemplate]:
        return list(self._templates)

    def add_template(self, template: RoomTemplate):
        """Manually add a room template."""
        self._templates.append(template)

    # -- Decorators ------------------------------------------------------------

    def on_enter(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(instance, player)`` when a player enters the dungeon."""
        self._enter_handlers.append(handler)
        return handler

    def on_complete(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(instance)`` when all rooms are cleared."""
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

    def on_room_generate(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator: ``(room, world)`` called after a room is pasted into the world.

        Use this to spawn mobs, create entities, or run custom room setup that
        requires world access. The handler may be async.
        """
        self._room_generate_handlers.append(handler)
        return handler

    def reward(self, handler: Callable[..., Any]) -> Callable[..., Any]:
        """Alias for :meth:`on_complete`."""
        return self.on_complete(handler)

    # -- Instance management ---------------------------------------------------

    async def create_instance(self, players: List[Any],
                              origin: Tuple[int, int, int],
                              world: Any = "world",
                              room_count: Optional[int] = None,
                              branch_factor: Optional[float] = None
                              ) -> DungeonInstance:
        """Generate and place a dungeon instance in the world.

        Args:
            players:       List of players participating.
            origin:        ``(x, y, z)`` world position for the entrance room.
            world:         World name or World object.
            room_count:    Override template room count.
            branch_factor: Override template branch factor.

        Returns:
            The new :class:`DungeonInstance`.
        """
        if not self._templates:
            raise RuntimeError(f"Dungeon {self.name!r} has no room templates loaded")

        world_name = str(world.name) if hasattr(world, "name") else str(world)

        start = None
        if self.start_room_name:
            start = next(
                (t for t in self._templates if t.name == self.start_room_name),
                None,
            )
        if start is None:
            start = self._templates[0]

        gen = _DungeonGenerator(
            templates=self._templates,
            room_count=room_count or self.room_count,
            branch_factor=branch_factor if branch_factor is not None else self.branch_factor,
            type_limits=self.type_limits,
            min_candidates=self.min_candidates,
        )

        rooms = gen.generate(start, origin, world_name)

        for room in rooms:
            room._clear_handlers.extend(self._room_clear_handlers)

        self._next_id += 1
        instance = DungeonInstance(self, players, self._next_id, rooms, world_name)
        self._instances.append(instance)

        await instance.paste_all()
        # Call any room-generate handlers to allow spawning mobs or doing
        # additional world setup that requires the world object.
        from bridge.wrappers import World
        world = World(world_name)
        for room in rooms:
            for h in self._room_generate_handlers:
                try:
                    r = h(room, world)
                    if inspect.isawaitable(r):
                        await r
                except Exception:
                    pass
        instance.start_tracking()

        for h in self._enter_handlers:
            for p in players:
                try:
                    r = h(instance, p)
                    if inspect.isawaitable(r):
                        await r
                except Exception:
                    pass

        return instance

    @property
    def instances(self) -> List[DungeonInstance]:
        return list(self._instances)



