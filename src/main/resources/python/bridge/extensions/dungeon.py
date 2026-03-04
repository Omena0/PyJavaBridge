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

    One operation per line using ``fill`` and ``set`` commands.
    Coordinates are local to the room (0-indexed).

    ``fill x1 y1 z1 x2 y2 z2 KEY`` — fill a rectangular region with KEY.
    ``set x y z KEY``               — place a single block.

    Air blocks are omitted unless needed for overwriting.  Operations
    are allowed to **overwrite** previous results — for example a hollow
    room can be expressed as a solid ``fill`` followed by an air ``fill``
    for the interior.  The encoder uses a two-phase algorithm:
    volumetric fills first (with overwriting), then greedy box meshing
    for the remaining blocks.  Each ``fill`` maps to a single
    ``world.fill()`` call at paste time.

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
    fill 0 0 0 0 0 0 S
    fill 2 0 0 2 0 0 S
    set 1 0 1 S
    set 2 0 1 C
    set 3 0 1 S
    fill 0 0 2 4 0 2 S
    fill 1 0 3 3 0 3 S
    fill 4 0 0 4 0 0 S

Use ``/bridge schem <x> <y> <z> <width> <height> <depth>`` in-game
to capture a region as a ``.droom`` file.
"""
from __future__ import annotations

import asyncio
import inspect
import os
import random
import re
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from bridge.extensions.region import Region
from bridge.types import async_task

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def _log(msg: str):
    _print(f"[Dungeon] {msg}", file=sys.stderr)


# -- Facing directions ---------------------------------------------------------
FACING: Dict[str, Tuple[int, int, int]] = {
    "+x": (1, 0, 0),  "-x": (-1, 0, 0),
    "+y": (0, 1, 0),  "-y": (0, -1, 0),
    "+z": (0, 0, 1),  "-z": (0, 0, -1),
}
FACING_NAME: Dict[Tuple[int, int, int], str] = {v: k for k, v in FACING.items()}

def _opposite_facing(f: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return (-f[0], -f[1], -f[2])


# -- Transformation helpers ----------------------------------------------------

# Supported transforms applied around the Y axis.
TRANSFORM_NONE = "none"
TRANSFORM_CW_90 = "cw90"          # 90° clockwise when viewed from above
TRANSFORM_CW_180 = "cw180"
TRANSFORM_CW_270 = "cw270"
TRANSFORM_MIRROR_X = "mirror_x"   # flip along the X axis (negate X)
TRANSFORM_MIRROR_Z = "mirror_z"   # flip along the Z axis (negate Z)

ALL_TRANSFORMS = (
    TRANSFORM_NONE,
    TRANSFORM_CW_90,
    TRANSFORM_CW_180,
    TRANSFORM_CW_270,
    TRANSFORM_MIRROR_X,
    TRANSFORM_MIRROR_Z,
)

def _rotate_facing(facing: Tuple[int, int, int], transform: str) -> Tuple[int, int, int]:
    """Apply *transform* to a facing direction vector."""
    fx, fy, fz = facing
    if transform == TRANSFORM_NONE:
        return facing
    if transform == TRANSFORM_CW_90:
        return (fz, fy, -fx)
    if transform == TRANSFORM_CW_180:
        return (-fx, fy, -fz)
    if transform == TRANSFORM_CW_270:
        return (-fz, fy, fx)
    if transform == TRANSFORM_MIRROR_X:
        return (-fx, fy, fz)
    if transform == TRANSFORM_MIRROR_Z:
        return (fx, fy, -fz)
    return facing


def _transform_local_pos(
    x: int, y: int, z: int,
    w: int, d: int,
    transform: str,
) -> Tuple[int, int, int]:
    """Transform a local coordinate ``(x, y, z)`` within a room of size
    ``w`` (X) × ``d`` (Z).  Returns the new ``(x', y', z')`` inside the
    transformed bounding box.
    """
    if transform == TRANSFORM_NONE:
        return (x, y, z)
    if transform == TRANSFORM_CW_90:
        # (x, z) -> (d-1-z, x);  new width = d, new depth = w
        return (d - 1 - z, y, x)
    if transform == TRANSFORM_CW_180:
        return (w - 1 - x, y, d - 1 - z)
    if transform == TRANSFORM_CW_270:
        # (x, z) -> (z, w-1-x);  new width = d, new depth = w
        return (z, y, w - 1 - x)
    if transform == TRANSFORM_MIRROR_X:
        return (w - 1 - x, y, z)
    if transform == TRANSFORM_MIRROR_Z:
        return (x, y, d - 1 - z)
    return (x, y, z)


def _transform_dims(
    w: int, h: int, d: int, transform: str,
) -> Tuple[int, int, int]:
    """Return ``(new_width, height, new_depth)`` after *transform*."""
    if transform in (TRANSFORM_CW_90, TRANSFORM_CW_270):
        return (d, h, w)
    return (w, h, d)


def _exit_opening_corners(ex: "Exit") -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """Return ``(anchor, opposite)`` corners of an exit's opening rectangle.

    The opening lies on the plane perpendicular to the exit's facing:

    - Facing ``±x``: width along ``+z``, height along ``+y``.
    - Facing ``±z``: width along ``+x``, height along ``+y``.
    - Facing ``±y``: width along ``+x``, height along ``+z``.
    """
    fx, fy, fz = ex.facing
    if fx != 0:       # ±x → width along z, height along y
        wd, hd = (0, 0, 1), (0, 1, 0)
    elif fy != 0:     # ±y → width along x, height along z
        wd, hd = (1, 0, 0), (0, 0, 1)
    else:             # ±z → width along x, height along y
        wd, hd = (1, 0, 0), (0, 1, 0)
    opp = (
        ex.x + (ex.width - 1) * wd[0] + (ex.height - 1) * hd[0],
        ex.y + (ex.width - 1) * wd[1] + (ex.height - 1) * hd[1],
        ex.z + (ex.width - 1) * wd[2] + (ex.height - 1) * hd[2],
    )
    return (ex.x, ex.y, ex.z), opp

# -- .droom file parser / writer -----------------------------------------------
def _expand_rle(row_str: str) -> List[str]:
    """Expand a run-length encoded string into a list of single-char keys.

    ``S3`` -> ``['S','S','S']``, ``~`` -> ``['~']``, ``AB2C`` -> ``['A','B','B','C']``.

    Kept for backwards compatibility with old RLE-format ``.droom`` files.
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


def _compute_ops(
    blocks: List[List[List[str]]],
    reverse_map: Dict[str, str],
    width: int, height: int, depth: int,
) -> List[tuple]:
    """Compute optimal fill/set operations from a 3-D block array.

    Uses a two-phase algorithm that allows overwriting:

    1. **Volumetric fills** — iteratively try filling each block type's
       bounding box.  A fill is accepted when the total operation count
       (this fill + greedy correction of the resulting diffs) is lower
       than the baseline (greedy mesh without the fill).  This enables
       patterns like "fill solid cube, then carve interior with air".

    2. **Greedy meshing** — sweep remaining diff cells (state != target)
       with box expansion to mop up stragglers.

    Returns a list of tuples:

    - ``("set", x, y, z, key_char)``
    - ``("fill", x1, y1, z1, x2, y2, z2, key_char)``
    """
    # Build target grid (char keys)
    target = [
        [
            [reverse_map.get(blocks[y][z][x], "~") for x in range(width)]
            for z in range(depth)
        ]
        for y in range(height)
    ]
    # State grid starts as all air
    state = [
        [["~"] * width for _ in range(depth)]
        for _ in range(height)
    ]

    phase1_ops: List[tuple] = []
    baseline_ops = _greedy_mesh(target, state, width, height, depth)

    # Phase 1: Volumetric fills with overwriting
    while True:
        candidates = _diff_candidates(target, state, width, height, depth)
        if not candidates:
            break

        current_total = len(phase1_ops) + len(baseline_ops)
        best_fill: Optional[tuple] = None
        best_state: Optional[List] = None
        best_corrections: Optional[List[tuple]] = None
        best_total = current_total

        for key, (bx1, by1, bz1, bx2, by2, bz2) in candidates:
            vol = (bx2 - bx1 + 1) * (by2 - by1 + 1) * (bz2 - bz1 + 1)
            if vol <= 1:
                continue

            # Trial: apply this fill to a copy of state
            trial = [[row[:] for row in layer] for layer in state]
            for yi in range(by1, by2 + 1):
                for zi in range(bz1, bz2 + 1):
                    for xi in range(bx1, bx2 + 1):
                        trial[yi][zi][xi] = key

            trial_corrections = _greedy_mesh(target, trial, width, height, depth)
            trial_total = len(phase1_ops) + 1 + len(trial_corrections)

            if trial_total < best_total:
                best_total = trial_total
                best_fill = ("fill", bx1, by1, bz1, bx2, by2, bz2, key)
                best_state = trial
                best_corrections = trial_corrections

        if best_fill is None:
            break

        phase1_ops.append(best_fill)
        assert best_state is not None
        assert best_corrections is not None
        state = best_state
        baseline_ops = best_corrections

    return phase1_ops + baseline_ops


def _diff_candidates(
    target: List[List[List[str]]],
    state: List[List[List[str]]],
    w: int, h: int, d: int,
) -> List[Tuple[str, Tuple[int, int, int, int, int, int]]]:
    """Generate candidate fill regions for each diff block type.

    For each type, returns the tight bounding box plus variants with
    independent per-axis face insets.  XZ faces are inset symmetrically
    (both sides by the same amount), while Y bottom and Y top can shrink
    independently.  This lets the algorithm discover patterns like
    'fill the entire interior' where the Y range doesn't align with a
    uniform inset (e.g. floor at y=1, ceiling structure at y=6,
    but bbox Y extends to y=8).
    """
    bounds: Dict[str, List[int]] = {}
    for y in range(h):
        for z in range(d):
            for x in range(w):
                if state[y][z][x] != target[y][z][x]:
                    k = target[y][z][x]
                    if k not in bounds:
                        bounds[k] = [w, h, d, -1, -1, -1]
                    b = bounds[k]
                    if x < b[0]: b[0] = x
                    if y < b[1]: b[1] = y
                    if z < b[2]: b[2] = z
                    if x > b[3]: b[3] = x
                    if y > b[4]: b[4] = y
                    if z > b[5]: b[5] = z

    seen: set = set()
    result: List[Tuple[str, Tuple[int, int, int, int, int, int]]] = []

    for k, b in bounds.items():
        if b[3] < 0:
            continue
        x1, y1, z1, x2, y2, z2 = b

        # Per-axis insets: xz_inset (symmetric X and Z), y_bot, y_top
        for xz in range(3):
            for yb in range(3):
                for yt in range(3):
                    nx1 = x1 + xz
                    nz1 = z1 + xz
                    nx2 = x2 - xz
                    nz2 = z2 - xz
                    ny1 = y1 + yb
                    ny2 = y2 - yt
                    if nx1 > nx2 or ny1 > ny2 or nz1 > nz2:
                        continue
                    box = (nx1, ny1, nz1, nx2, ny2, nz2)
                    key = (k, box)
                    if key not in seen:
                        seen.add(key)
                        result.append((k, box))

    return result


def _greedy_mesh(
    target: List[List[List[str]]],
    state: List[List[List[str]]],
    w: int, h: int, d: int,
) -> List[tuple]:
    """Greedy box expansion on diff cells using the best of several sweep orders."""
    best: Optional[List[tuple]] = None
    # Try 3 axis orderings: (y,z,x), (x,z,y), (z,x,y)
    for perm in ((1, 2, 0), (0, 2, 1), (2, 0, 1)):
        ops = _greedy_mesh_sweep(target, state, w, h, d, perm)
        if best is None or len(ops) < len(best):
            best = ops
    return best  # type: ignore[return-value]


def _greedy_mesh_sweep(
    target: List[List[List[str]]],
    state: List[List[List[str]]],
    w: int, h: int, d: int,
    perm: Tuple[int, int, int],
) -> List[tuple]:
    """Greedy box expansion using a specific axis sweep order.

    *perm* is ``(outer, mid, inner)`` where ``0 = x, 1 = y, 2 = z``.
    """
    dims = (w, h, d)
    s0, s1, s2 = dims[perm[0]], dims[perm[1]], dims[perm[2]]
    p0, p1, p2 = perm

    visited = [[[False] * s2 for _ in range(s1)] for _ in range(s0)]
    ops: List[tuple] = []

    for a in range(s0):
        for b in range(s1):
            for c in range(s2):
                if visited[a][b][c]:
                    continue
                # Map permuted indices to real (x, y, z)
                r = [0, 0, 0]
                r[p0] = a; r[p1] = b; r[p2] = c
                x, y, z = r[0], r[1], r[2]

                if state[y][z][x] == target[y][z][x]:
                    continue
                key = target[y][z][x]

                # Expand along inner axis (c)
                ec = c
                while ec + 1 < s2:
                    r2 = [0, 0, 0]
                    r2[p0] = a; r2[p1] = b; r2[p2] = ec + 1
                    nx, ny, nz = r2[0], r2[1], r2[2]
                    if (visited[a][b][ec + 1]
                            or state[ny][nz][nx] == target[ny][nz][nx]
                            or target[ny][nz][nx] != key):
                        break
                    ec += 1

                # Expand along mid axis (b)
                eb = b
                expanding = True
                while expanding and eb + 1 < s1:
                    for jc in range(c, ec + 1):
                        r2 = [0, 0, 0]
                        r2[p0] = a; r2[p1] = eb + 1; r2[p2] = jc
                        nx, ny, nz = r2[0], r2[1], r2[2]
                        if (visited[a][eb + 1][jc]
                                or state[ny][nz][nx] == target[ny][nz][nx]
                                or target[ny][nz][nx] != key):
                            expanding = False
                            break
                    if expanding:
                        eb += 1

                # Expand along outer axis (a)
                ea = a
                expanding = True
                while expanding and ea + 1 < s0:
                    for jb in range(b, eb + 1):
                        for jc in range(c, ec + 1):
                            r2 = [0, 0, 0]
                            r2[p0] = ea + 1; r2[p1] = jb; r2[p2] = jc
                            nx, ny, nz = r2[0], r2[1], r2[2]
                            if (visited[ea + 1][jb][jc]
                                    or state[ny][nz][nx] == target[ny][nz][nx]
                                    or target[ny][nz][nx] != key):
                                expanding = False
                                break
                        if not expanding:
                            break
                    if expanding:
                        ea += 1

                # Mark visited
                for ja in range(a, ea + 1):
                    for jb in range(b, eb + 1):
                        for jc in range(c, ec + 1):
                            visited[ja][jb][jc] = True

                # Convert back to (x, y, z) coordinates
                r1 = [0, 0, 0]
                r1[p0] = a; r1[p1] = b; r1[p2] = c
                r2 = [0, 0, 0]
                r2[p0] = ea; r2[p1] = eb; r2[p2] = ec
                x1, y1, z1 = r1[0], r1[1], r1[2]
                x2, y2, z2 = r2[0], r2[1], r2[2]

                if x1 == x2 and y1 == y2 and z1 == z2:
                    ops.append(("set", x1, y1, z1, key))
                else:
                    ops.append(("fill", x1, y1, z1, x2, y2, z2, key))

    return ops


def _ops_to_text(ops: List[tuple]) -> str:
    """Serialize operation tuples to the text block in a ``.droom`` file."""
    lines: List[str] = []
    for op in ops:
        if op[0] == "set":
            _, x, y, z, key = op
            lines.append(f"set {x} {y} {z} {key}")
        else:
            _, x1, y1, z1, x2, y2, z2, key = op
            lines.append(f"fill {x1} {y1} {z1} {x2} {y2} {z2} {key}")
    return "\n".join(lines)


def _parse_ops(
    text: str,
    key_map: Dict[str, str],
    width: int, height: int, depth: int,
) -> List[List[List[str]]]:
    """Parse fill/set operation lines into a ``[y][z][x]`` block array."""
    layers: List[List[List[str]]] = [
        [["minecraft:air"] * width for _ in range(depth)]
        for _ in range(height)
    ]
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "set" and len(parts) == 5:
            x, y, z = int(parts[1]), int(parts[2]), int(parts[3])
            key = parts[4]
            block_def = key_map.get(key, "air")
            layers[y][z][x] = f"minecraft:{block_def}"
        elif parts[0] == "fill" and len(parts) == 8:
            x1, y1, z1 = int(parts[1]), int(parts[2]), int(parts[3])
            x2, y2, z2 = int(parts[4]), int(parts[5]), int(parts[6])
            key = parts[7]
            block_def = key_map.get(key, "air")
            full = f"minecraft:{block_def}"
            for yi in range(y1, y2 + 1):
                for zi in range(z1, z2 + 1):
                    for xi in range(x1, x2 + 1):
                        layers[yi][zi][xi] = full
    return layers

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
                 blocks: List[List[List[str]]],
                 spawns: Optional[List[Dict[str, Any]]] = None):
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
        # Spawn definitions parsed from metadata: list of dicts
        # Each dict: {entity: str, x:int, y:int, z:int, count:int, kwargs: dict}
        self.spawns: List[Dict[str, Any]] = spawns or []

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
        spawns: List[Dict[str, Any]] = []
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
            elif meta_key == "spawn":
                # spawn: <entity> x,y,z [count=N] [k=v ...]
                toks = value.split()
                if len(toks) >= 2:
                    entity = toks[0]
                    coords = toks[1]
                    try:
                        cx, cy, cz = (int(p) for p in coords.split(","))
                    except Exception:
                        continue
                    kwargs: Dict[str, Any] = {}
                    count = 1
                    for extra in toks[2:]:
                        if "=" in extra:
                            k, _, v = extra.partition("=")
                            if k == "count":
                                try:
                                    count = int(v)
                                except Exception:
                                    pass
                            else:
                                kwargs[k] = v
                    spawns.append({"entity": entity, "x": cx, "y": cy, "z": cz, "count": count, "kwargs": kwargs})

        # Block data
        block_text = block_part.strip()
        if not block_text:
            raise ValueError(f"Empty block data in {path}")

        if meta_width is None or meta_height is None or meta_depth is None:
            raise ValueError(f"Missing width/height/depth in metadata of {path}")

        # Detect format: new fill/set ops vs legacy RLE
        first_line = block_text.split("\n", 1)[0].strip()
        is_ops_format = first_line.startswith("fill ") or first_line.startswith("set ")

        if is_ops_format:
            layers = _parse_ops(block_text, key_map, meta_width, meta_height, meta_depth)
        else:
            # Legacy RLE format
            block_line = block_text.replace("\n", "")
            char_keys = _expand_rle(block_line)
            expected = meta_width * meta_height * meta_depth
            if len(char_keys) != expected:
                raise ValueError(
                    f"Block data length {len(char_keys)} != "
                    f"width*height*depth {expected} in {path}"
                )
            layers = []
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
               meta_width, meta_height, meta_depth, layers, spawns)

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

        # Encode blocks as fill/set operations
        ops = _compute_ops(self.blocks, reverse, self.width, self.height, self.depth)
        lines.append(_ops_to_text(ops))
        # Write spawn metadata
        for s in getattr(self, "spawns", []):
            ent = s.get("entity")
            x = s.get("x")
            y = s.get("y")
            z = s.get("z")
            count = s.get("count", 1)
            extras = "".join(f" {k}={v}" for k, v in (s.get("kwargs") or {}).items())
            if ent is not None and x is not None:
                lines.append(f"spawn: {ent} {x},{y},{z} count={count}{extras}")

        return "\n".join(lines) + "\n"

    def transformed(self, transform: str) -> "RoomTemplate":
        """Return a new :class:`RoomTemplate` with blocks, exits, and spawns
        rotated/mirrored by *transform*.

        Valid values: ``TRANSFORM_NONE``, ``TRANSFORM_CW_90``,
        ``TRANSFORM_CW_180``, ``TRANSFORM_CW_270``,
        ``TRANSFORM_MIRROR_X``, ``TRANSFORM_MIRROR_Z``.
        """
        if transform == TRANSFORM_NONE:
            return self

        w, h, d = self.width, self.height, self.depth
        nw, nh, nd = _transform_dims(w, h, d, transform)

        # Transform block grid  [y][z][x]
        new_blocks: List[List[List[str]]] = [
            [["minecraft:air"] * nw for _ in range(nd)]
            for _ in range(nh)
        ]
        for y in range(h):
            for z in range(d):
                for x in range(w):
                    nx, ny, nz = _transform_local_pos(x, y, z, w, d, transform)
                    new_blocks[ny][nz][nx] = self.blocks[y][z][x]

        # Transform exits — normalize anchor to min corner of the opening
        new_exits: List[Exit] = []
        for ex in self.exits:
            # Get both corners of the opening in original coords
            corner_a, corner_b = _exit_opening_corners(ex)
            # Transform both corners
            ta = _transform_local_pos(*corner_a, w, d, transform)
            tb = _transform_local_pos(*corner_b, w, d, transform)
            # New anchor = component-wise min (min corner of the opening)
            ax = min(ta[0], tb[0])
            ay = min(ta[1], tb[1])
            az = min(ta[2], tb[2])
            nf = _rotate_facing(ex.facing, transform)
            new_exits.append(Exit(ax, ay, az, nf, ex.width, ex.height, ex.tag))

        # Transform spawns
        new_spawns: List[Dict[str, Any]] = []
        for s in self.spawns:
            sx, sy, sz = s.get("x", 0), s.get("y", 0), s.get("z", 0)
            nx, ny, nz = _transform_local_pos(sx, sy, sz, w, d, transform)
            ns = dict(s)
            ns["x"], ns["y"], ns["z"] = nx, ny, nz
            new_spawns.append(ns)

        suffix = f"_{transform}"
        return RoomTemplate(
            name=self.name + suffix,
            path=self.path,
            room_type=self.type,
            exits=new_exits,
            weight=self.weight,
            loot=dict(self.loot),
            key_map=dict(self.key_map),
            width=nw, height=nh, depth=nd,
            blocks=new_blocks,
            spawns=new_spawns,
        )

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

    @async_task
    async def paste(self, world: Any):
        """Paste the room blocks into the world and save originals.

        Sends all operations to Java in a single bulk call via
        ``region.pasteOperations``, which handles block-data states,
        saves originals, and applies everything server-side.
        """
        _log(f"paste: {self.template.name!r} at {self.origin}")
        t0 = time.perf_counter()
        bulk_ops = self._build_bulk_ops()
        from bridge.connection import _connection
        originals = await _connection.call(
            target="region", method="pasteOperations",
            args=[world, bulk_ops],
        )
        if isinstance(originals, dict):
            for key, block_str in originals.items():
                parts = key.split(":")
                if len(parts) >= 3:
                    pos = (int(parts[0]), int(parts[1]), int(parts[2]))
                    if pos not in self.original_blocks:
                        self.original_blocks[pos] = block_str
        _log(f"paste: {self.template.name!r} done in {time.perf_counter()-t0:.3f}s")

    def _build_bulk_ops(self) -> List[list]:
        """Build absolute-coordinate operation list for Java bulk paste."""
        ox, oy, oz = self.origin
        reverse: Dict[str, str] = {}
        for ch, block_def in self.template.key_map.items():
            reverse[f"minecraft:{block_def}"] = ch
        ops = _compute_ops(
            self.template.blocks, reverse,
            self.template.width, self.template.height, self.template.depth,
        )
        bulk: List[list] = []
        for op in ops:
            if op[0] == "set":
                _, lx, ly, lz, key = op
                block_def = self.template.key_map.get(key, "air")
                block_str = _strip_loot_name(f"minecraft:{block_def}")
                bulk.append(["set", ox + lx, oy + ly, oz + lz, block_str])
            else:
                _, x1, y1, z1, x2, y2, z2, key = op
                block_def = self.template.key_map.get(key, "air")
                block_str = _strip_loot_name(f"minecraft:{block_def}")
                bulk.append(["fill", ox + x1, oy + y1, oz + z1,
                             ox + x2, oy + y2, oz + z2, block_str])
        return bulk

    @async_task
    async def restore(self, world: Any):
        """Restore original blocks (cleanup) in a single bulk call."""
        if not self.original_blocks:
            return
        entries = [[wx, wy, wz, block_str]
                   for (wx, wy, wz), block_str in self.original_blocks.items()]
        from bridge.connection import _connection
        await _connection.call(
            target="region", method="restoreBlocks",
            args=[world, entries],
        )
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

_LOOT_NAME_RE = re.compile(r',?name=\[loot:\w+\]')

def _strip_loot_name(block_str: str) -> str:
    """Remove name=[loot:...] from a block string so it's not set as a chest title."""
    s = _LOOT_NAME_RE.sub('', block_str)
    s = s.replace('[,', '[').replace(',]', ']')
    if s.endswith('[]'):
        s = s[:-2]
    return s

@async_task
async def _fill_loot(room: PlacedRoom, world: Any):
    """Scan placed room for loot containers and fill them."""
    ox, oy, oz = room.origin
    for yi, layer in enumerate(room.template.blocks):
        for zi, row in enumerate(layer):
            for xi, block_str in enumerate(row):
                # Extract loot tag directly from the template block string
                # (e.g. "minecraft:chest[facing=north,name=[loot:rare]]")
                match = re.search(r'name=\[loot:(\w+)\]', block_str)
                if not match:
                    continue
                tag = match.group(1)
                pool = room.template.loot.get(tag, tag)
                gen = _loot_generators.get(pool)
                if not gen:
                    continue
                wx, wy, wz = ox + xi, oy + yi, oz + zi
                try:
                    blk = await world.block_at(wx, wy, wz)
                    inv = blk.inventory
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

        # Pre-compute all rotated/mirrored variants of every template.
        # Each entry is (transformed_template, original_template) so we
        # can track type counts against the original.
        self._variants: List[Tuple[RoomTemplate, RoomTemplate]] = []
        seen: set = set()
        for t in templates:
            for tf in ALL_TRANSFORMS:
                variant = t.transformed(tf)
                # Deduplicate identical variants (e.g. a symmetric room)
                sig = (t.name, tuple(tuple(tuple(row) for row in layer) for layer in variant.blocks))
                if sig in seen:
                    continue
                seen.add(sig)
                self._variants.append((variant, t))

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
        for every template variant (including rotations/mirrors) that can
        attach to the given open exit without overlapping existing rooms."""
        src_exit = room.template.exits[exit_idx]
        results: List[Tuple[RoomTemplate, int, Tuple[int, int, int]]] = []

        for variant, original in self._variants:
            limit = self.type_limits.get(original.type)
            if limit is not None and self._type_counts.get(original.type, 0) >= limit:
                continue

            for di, dst_exit in enumerate(variant.exits):
                if not src_exit.can_connect(dst_exit):
                    continue
                new_origin = _compute_new_origin(room.origin, src_exit, dst_exit)
                if self._overlaps_any(new_origin, variant):
                    continue
                results.append((variant, di, new_origin))

        return results

    # -- placement / undo helpers ------------------------------------------------

    def _place(self, room: PlacedRoom):
        """Add *room* to the placed set."""
        self.placed.append(room)
        self._aabbs.append(_room_aabb(room.origin, room.template))
        self._type_counts[room.template.type] = (
            self._type_counts.get(room.template.type, 0) + 1
        )

    def _unplace(self, room: PlacedRoom):
        """Remove the most recently placed room (must be *room*)."""
        assert self.placed[-1] is room
        self.placed.pop()
        self._aabbs.pop()
        self._type_counts[room.template.type] -= 1

    # -- main loop -------------------------------------------------------------

    def generate(self, start_template: RoomTemplate,
                 origin: Tuple[int, int, int],
                 world_name: str) -> List[PlacedRoom]:
        """Generate the dungeon layout and return placed rooms."""
        _log(f"generate: start template={start_template.name!r} origin={origin} target={self.room_count} rooms")
        t0 = time.perf_counter()

        # Place starting room
        start = PlacedRoom(start_template, origin, world_name)
        self._place(start)

        # Open exits: (PlacedRoom, exit_index, depth)
        open_exits: List[Tuple[PlacedRoom, int, int]] = [
            (start, i, 0) for i in range(len(start_template.exits))
        ]

        while len(self.placed) < self.room_count and open_exits:
            # Score each open exit by number of viable candidates
            scored: List[Tuple[int, int, Tuple[PlacedRoom, int, int],
                               List[Tuple[RoomTemplate, int, Tuple[int, int, int]]]]] = []

            remaining = self.room_count - len(self.placed)
            n_open = len(open_exits)

            # Adaptive exit pressure: when remaining rooms < 2× open
            # exits, gradually prefer templates with fewer exits
            # (dead-ends) to close off branches before we run out.
            # pressure=0 → no constraint, pressure=1 → strongly prefer dead-ends.
            if n_open > 0 and remaining < 2 * n_open:
                exit_pressure = 1.0 - (remaining / (2.0 * n_open))
            else:
                exit_pressure = 0.0

            # When remaining <= open exits, ONLY allow dead-ends (1 exit)
            # since every placement must close a branch, not grow new ones.
            dead_end_only = remaining <= n_open

            for item in open_exits:
                room, eidx, depth = item
                cands = self._candidates_for_exit(room, eidx)
                if dead_end_only:
                    dead = [c for c in cands if len(c[0].exits) <= 1]
                    if dead:
                        cands = dead
                elif exit_pressure > 0 and cands:
                    # Weight candidates: fewer exits → higher weight
                    max_exits = max(len(c[0].exits) for c in cands)
                    if max_exits > 1:
                        weighted = []
                        for c in cands:
                            ne = len(c[0].exits)
                            # dead-end (1 exit) gets weight 1.0
                            # multi-exit gets weight reduced by pressure
                            w = 1.0 if ne <= 1 else max(1.0 - exit_pressure * 0.9, 0.05)
                            weighted.append((c, w))
                        # Stochastic selection: sort by -weight*random
                        weighted.sort(key=lambda cw: -(cw[1] * random.random()))
                        cands = [cw[0] for cw in weighted]
                if cands:
                    scored.append((len(cands), depth, item, cands))

            if not scored:
                _log(f"generate: no scored exits, stopping at {len(self.placed)} rooms")
                break

            # Prefer exits that meet the minimum candidates threshold
            above = [s for s in scored if s[0] >= self.min_candidates]
            pool = above if above else scored

            # Pick an exit weighted by branch_factor.
            # High branch_factor → prefer shallow (low depth) exits (more branching).
            # Low branch_factor  → prefer deep exits (more linear).
            max_depth = max(e[1] for e in pool) or 1
            weights = []
            for entry in pool:
                d = entry[1]
                # Normalize depth to [0,1], invert for branching preference
                ratio = d / max_depth if max_depth else 0
                # branch_factor=1 → strongly prefer shallow; 0 → strongly prefer deep
                w = (1 - ratio) * self.branch_factor + ratio * (1 - self.branch_factor)
                weights.append(max(w, 0.01))
            chosen_entry = random.choices(pool, weights=weights, k=1)[0]
            _, _, (source_room, src_eidx, depth), cands = chosen_entry

            # Remove this exit from open list
            open_exits = [
                item for item in open_exits
                if not (item[0] is source_room and item[1] == src_eidx)
            ]

            # Shuffle candidates, penalising rooms that were recently placed.
            # Use base name (without transform suffix) for comparison.
            # When exit_pressure > 0, also boost dead-end templates.
            recent_names = []
            for pr in reversed(self.placed[-4:]):
                base = pr.template.name.split("_none")[0].split("_cw_")[0].split("_mirror_")[0]
                recent_names.append(base)

            _ep = exit_pressure  # capture for closure
            def _cand_key(c):
                w = c[0].weight
                base = c[0].name.split("_none")[0].split("_cw_")[0].split("_mirror_")[0]
                for i, rn in enumerate(recent_names):
                    if base == rn:
                        w *= 0.05 * (i + 1)
                        break
                # Boost dead-ends under exit pressure
                ne = len(c[0].exits)
                if _ep > 0:
                    if ne <= 1:
                        w *= 1.0 + _ep * 4.0  # up to 5× boost
                    else:
                        w *= max(1.0 - _ep * 0.9, 0.1)
                return -(w * random.random())
            cands.sort(key=_cand_key)

            _log(f"generate: placing room {len(self.placed)+1}/{self.room_count}, "
                 f"exit on {source_room.template.name!r}[{src_eidx}], {len(cands)} candidates")
            placed_ok = False
            for chosen_t, chosen_di, new_origin in cands:
                new_room = PlacedRoom(chosen_t, new_origin, world_name)
                self._place(new_room)

                # Check that every new open exit on this room has at
                # least one viable candidate — no blocked-off exits.
                new_open = [
                    (new_room, ei, depth + 1)
                    for ei in range(len(chosen_t.exits))
                    if ei != chosen_di
                ]
                blocked = False
                for item in new_open:
                    if not self._candidates_for_exit(item[0], item[1]):
                        blocked = True
                        break

                if blocked:
                    self._unplace(new_room)
                    continue

                # Commit placement
                source_room.connected_exits[src_eidx] = new_room
                new_room.connected_exits[chosen_di] = source_room
                open_exits.extend(new_open)
                placed_ok = True
                break

            if not placed_ok:
                # No candidate works — remove from open list (already removed)
                pass

        # -- Phase 2: close remaining open exits with dead-end rooms -----------
        # After reaching room_count, keep placing 1-exit (dead-end) rooms
        # to fill any remaining open exits so there are no holes.
        cap_count = 0
        while open_exits:
            # Find an open exit that has a dead-end candidate
            found = False
            for i, item in enumerate(open_exits):
                room, eidx, depth = item
                cands = self._candidates_for_exit(room, eidx)
                dead = [c for c in cands if len(c[0].exits) <= 1]
                if not dead:
                    continue
                open_exits.pop(i)
                # Try each dead-end candidate
                for chosen_t, chosen_di, new_origin in dead:
                    new_room = PlacedRoom(chosen_t, new_origin, world_name)
                    self._place(new_room)
                    room.connected_exits[eidx] = new_room
                    new_room.connected_exits[chosen_di] = room
                    cap_count += 1
                    found = True
                    break
                else:
                    # None fit — leave this exit
                    pass
                break
            if not found:
                break

        if cap_count > 0:
            _log(f"generate: placed {cap_count} dead-end caps for open exits")

        open_remaining = sum(
            1 for r in self.placed
            for conn in r.connected_exits.values()
            if conn is None
        )
        _log(f"generate: placed {len(self.placed)} rooms in {time.perf_counter()-t0:.3f}s"
             f" ({open_remaining} open exits remain)")

        # -- post-generation: seal all remaining open exits --------------------
        self._seal_open_exits(world_name)

        _log(f"generate: done in {time.perf_counter()-t0:.3f}s")
        return self.placed

    def _seal_open_exits(self, world_name: str):
        """Replace rooms that have unconnected exits with variants that
        fit but have fewer (ideally zero) unconnected exits.

        Works backwards from the last placed room so that undo order is
        safe.  The start room (index 0) is never replaced.
        """
        MAX_PASSES = 3
        for _pass in range(MAX_PASSES):
            any_swapped = False
            for ri in range(len(self.placed) - 1, 0, -1):
                room = self.placed[ri]
                open_idxs = [
                    ei for ei, conn in room.connected_exits.items()
                    if conn is None
                ]
                if not open_idxs:
                    continue  # all exits connected — fine

                # Collect ALL connected neighbors and which parent exit
                # they use to reach us.
                # neighbors: list of (neighbor_room, neighbor_exit_idx_pointing_here)
                neighbors: List[Tuple[PlacedRoom, int]] = []
                for ei, conn in room.connected_exits.items():
                    if conn is not None:
                        # Find the exit index on `conn` that points to `room`
                        for nei, nconn in conn.connected_exits.items():
                            if nconn is room:
                                neighbors.append((conn, nei))
                                break

                if not neighbors:
                    continue

                # Temporarily null-out this room's AABB and type count
                old_aabb = self._aabbs[ri]
                self._aabbs[ri] = ((0, 0, 0), (-1, -1, -1))
                self._type_counts[room.template.type] -= 1

                best: Optional[Tuple[RoomTemplate, Dict[int, Tuple[PlacedRoom, int]], Tuple[int, int, int]]] = None
                best_open = len(open_idxs)

                for variant, original in self._variants:
                    limit = self.type_limits.get(original.type)
                    if limit is not None and self._type_counts.get(original.type, 0) >= limit:
                        continue

                    # For each neighbor, find which exit on this variant
                    # can connect to it, and verify the origin is consistent.
                    # We iterate over all possible assignments.
                    # Use the first neighbor to anchor the origin.
                    first_neighbor, first_n_eidx = neighbors[0]
                    src_exit_0 = first_neighbor.template.exits[first_n_eidx]

                    for di, dst_exit in enumerate(variant.exits):
                        if not src_exit_0.can_connect(dst_exit):
                            continue
                        new_origin = _compute_new_origin(
                            first_neighbor.origin, src_exit_0, dst_exit
                        )
                        if self._overlaps_any(new_origin, variant):
                            continue

                        # Verify ALL other neighbors can also connect.
                        # Build mapping: variant_exit_idx -> (neighbor, neighbor_eidx)
                        connections: Dict[int, Tuple[PlacedRoom, int]] = {di: (first_neighbor, first_n_eidx)}
                        used_exits = {di}
                        all_ok = True

                        for nb, nb_eidx in neighbors[1:]:
                            nb_src = nb.template.exits[nb_eidx]
                            found = False
                            for vi, vexit in enumerate(variant.exits):
                                if vi in used_exits:
                                    continue
                                if not nb_src.can_connect(vexit):
                                    continue
                                # Verify origin consistency: the origin
                                # computed from this neighbor must match.
                                check_origin = _compute_new_origin(
                                    nb.origin, nb_src, vexit
                                )
                                if check_origin == new_origin:
                                    connections[vi] = (nb, nb_eidx)
                                    used_exits.add(vi)
                                    found = True
                                    break
                            if not found:
                                all_ok = False
                                break

                        if not all_ok:
                            continue

                        unconnected = len(variant.exits) - len(connections)
                        if unconnected < best_open:
                            best = (variant, connections, new_origin)
                            best_open = unconnected
                            if best_open == 0:
                                break
                    if best is not None and best_open == 0:
                        break

                if best is not None and best_open < len(open_idxs):
                    chosen_t, connections, new_origin = best

                    # Disconnect old room from all neighbors
                    for ei, conn in room.connected_exits.items():
                        if conn is not None:
                            for cei, cconn in conn.connected_exits.items():
                                if cconn is room:
                                    conn.connected_exits[cei] = None
                                    break

                    new_room = PlacedRoom(chosen_t, new_origin, world_name)

                    # Wire up all neighbor connections
                    for vi, (nb, nb_eidx) in connections.items():
                        new_room.connected_exits[vi] = nb
                        nb.connected_exits[nb_eidx] = new_room

                    self.placed[ri] = new_room
                    self._aabbs[ri] = _room_aabb(new_origin, chosen_t)
                    self._type_counts[chosen_t.type] = (
                        self._type_counts.get(chosen_t.type, 0) + 1
                    )
                    any_swapped = True
                else:
                    # Restore original AABB
                    self._aabbs[ri] = old_aabb
                    self._type_counts[room.template.type] += 1

            if not any_swapped:
                break

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
        self._all_originals: Dict[Tuple[int, int, int], str] = {}

    @property
    def progress(self) -> float:
        """Fraction of rooms cleared (0.0 - 1.0)."""
        if not self.rooms:
            return 1.0
        return sum(1 for r in self.rooms if r.cleared) / len(self.rooms)

    @property
    def is_complete(self) -> bool:
        return self._completed or all(r.cleared for r in self.rooms)

    @async_task
    async def paste_all(self):
        """Paste all rooms into the world in a single bulk call."""
        _log(f"paste_all: {len(self.rooms)} rooms")
        t0 = time.perf_counter()
        from bridge import World
        from bridge.connection import _connection

        world = World(name=self.world_name)

        # Merge all rooms' ops into one list
        all_ops: List[list] = []
        room_op_ranges: List[Tuple[int, int]] = []
        for room in self.rooms:
            start = len(all_ops)
            all_ops.extend(room._build_bulk_ops())
            room_op_ranges.append((start, len(all_ops)))

        _log(f"paste_all: {len(all_ops)} total ops, sending bulk call")
        originals = await _connection.call(
            target="region", method="pasteOperations",
            args=[world, all_ops],
        )

        # Store originals on the instance for bulk restore
        if isinstance(originals, dict):
            for key, block_str in originals.items():
                parts = key.split(":")
                if len(parts) >= 3:
                    pos = (int(parts[0]), int(parts[1]), int(parts[2]))
                    if pos not in self._all_originals:
                        self._all_originals[pos] = block_str

        _log(f"paste_all: blocks done in {time.perf_counter()-t0:.3f}s, filling loot")

        for room in self.rooms:
            await _fill_loot(room, world)

        _log(f"paste_all: done in {time.perf_counter()-t0:.3f}s")

    @async_task
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

    @async_task
    async def destroy(self):
        """Restore all original blocks and remove the instance."""
        if self._tracker_task and not self._tracker_task.done():
            self._tracker_task.cancel()
        from bridge import World
        from bridge import _connection

        world = World(name=self.world_name)

        # Bulk restore all originals in one call
        if self._all_originals:
            entries = [[wx, wy, wz, block_str]
                       for (wx, wy, wz), block_str in self._all_originals.items()]
            await _connection.call(
                target="region", method="restoreBlocks",
                args=[world, entries],
            )
            self._all_originals.clear()

        for room in self.rooms:
            room.original_blocks.clear()
            if room._region:
                room._region.remove()

        if self in self.dungeon._instances:
            self.dungeon._instances.remove(self)

    def start_tracking(self):
        """Start polling player positions for room enter events."""
        self._tracker_task = asyncio.ensure_future(self._track_loop())

    async def _track_loop(self):
        """Poll players and fire room enter events."""
        from bridge import server
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

        _log(f"create_instance: dungeon={self.name!r} players={len(players)} origin={origin} world={world_name}")
        gen = _DungeonGenerator(
            templates=self._templates,
            room_count=room_count or self.room_count,
            branch_factor=branch_factor if branch_factor is not None else self.branch_factor,
            type_limits=self.type_limits,
            min_candidates=self.min_candidates,
        )

        rooms = gen.generate(start, origin, world_name)
        _log(f"create_instance: generated {len(rooms)} rooms, pasting...")

        for room in rooms:
            room._clear_handlers.extend(self._room_clear_handlers)

        self._next_id += 1
        instance = DungeonInstance(self, players, self._next_id, rooms, world_name)
        self._instances.append(instance)

        await instance.paste_all()

        _log("create_instance: paste_all done, spawning entities...")

        # Auto-spawn entities declared in template metadata, then call
        # any registered room-generate handlers. Handlers may be async.
        from bridge import World

        world = World(name=world_name)

        for i, room in enumerate(rooms):
            # Automatic spawns from template
            for s in getattr(room.template, "spawns", []):
                ent = s.get("entity")
                count = s.get("count", 1)
                kwargs = s.get("kwargs") or {}
                for _i in range(count):
                    loc = (room.origin[0] + s.get("x", 0),
                        room.origin[1] + s.get("y", 0),
                        room.origin[2] + s.get("z", 0))
                    try:
                        r = world.spawn_entity(loc, ent, **kwargs)
                        if inspect.isawaitable(r):
                            await r
                    except Exception:
                        pass

            # Custom handlers
            for h in self._room_generate_handlers:
                try:
                    r = h(room, world)
                    if inspect.isawaitable(r):
                        await r
                except Exception:
                    pass

        _log("create_instance: room handlers done, starting tracker")
        instance.start_tracking()

        _log("create_instance: firing enter handlers")

        for h in self._enter_handlers:
            for p in players:
                try:
                    r = h(instance, p)
                    if inspect.isawaitable(r):
                        await r
                except Exception:
                    pass

        _log("create_instance: complete")
        return instance

    @property
    def instances(self) -> List[DungeonInstance]:
        return list(self._instances)



