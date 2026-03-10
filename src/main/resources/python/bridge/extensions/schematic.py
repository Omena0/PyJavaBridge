"""Schematic extension — general-purpose block schematic system.

Stores block structures as ``.bschem`` (bridge schematic) files with
markers for arbitrary named points and metadata.

.bschem file format
-------------------
A ``.bschem`` file has two sections separated by a ``---`` line:

**Metadata** (key: value, one per line)::
    width: 9
    height: 5
    depth: 9
    custom_key: custom_value

``width``, ``height``, and ``depth`` are required.  All other keys
are stored as arbitrary metadata.

**Marker definitions** (``marker: type x,y,z [key=value ...]``)::
    marker: exit 0,0,4 facing=-x width=3 height=3
    marker: spawn 4,2,4 entity=zombie count=3

Markers are named points with a type string and arbitrary key-value
metadata.  Use them for connection points, spawn locations, points
of interest, loot positions, or anything else.

**Block keys** (single character = block definition)::
    S: stone_bricks
    C: chest[facing=north]

``~`` is always air (hardcoded, no definition needed).

**Block data** (after the ``---`` separator)::
    One operation per line using ``fill`` and ``set`` commands.
    Coordinates are local to the schematic (0-indexed).

    ``fill x1 y1 z1 x2 y2 z2 KEY`` — fill a rectangular region with KEY.
    ``set x y z KEY``               — place a single block.

    Operations may overwrite previous results — for example a hollow
    room can be expressed as a solid ``fill`` followed by an air ``fill``
    for the interior.

Example ``.bschem`` file::
    width: 5
    height: 1
    depth: 5
    custom: hello

    marker: exit 0,0,2 facing=-x width=1 height=1
    marker: exit 4,0,2 facing=+x width=1 height=1
    marker: spawn 2,0,2 entity=zombie count=3

    S: stone_bricks
    C: chest[facing=north]

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
to capture a region as a ``.bschem`` file.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from bridge.types import async_task

_print = __builtins__["print"] if isinstance(__builtins__, dict) else __builtins__.print  # type: ignore[index]
def _log(msg: str):
    """Handle log."""
    _print(f"[Schematic] {msg}", file=sys.stderr)

# -- Facing directions ---------------------------------------------------------
FACING: Dict[str, Tuple[int, int, int]] = {
    "+x": (1, 0, 0),  "-x": (-1, 0, 0),
    "+y": (0, 1, 0),  "-y": (0, -1, 0),
    "+z": (0, 0, 1),  "-z": (0, 0, -1),
}
FACING_NAME: Dict[Tuple[int, int, int], str] = {v: k for k, v in FACING.items()}

def _opposite_facing(f: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Handle opposite facing."""
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
    """Transform a local coordinate ``(x, y, z)`` within a schematic of size
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

# -- .bschem file parser / writer ----------------------------------------------
def _expand_rle(row_str: str) -> List[str]:
    """Expand a run-length encoded string into a list of single-char keys.

    ``S3`` -> ``['S','S','S']``, ``~`` -> ``['~']``, ``AB2C`` -> ``['A','B','B','C']``.

    Kept for backwards compatibility with old RLE-format files.
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
       than the baseline (greedy mesh without the fill).

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
    """Generate candidate fill regions for each diff block type."""
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
    """Serialize operation tuples to the text block in a ``.bschem`` file."""
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

# -- Marker class --------------------------------------------------------------
class Marker:
    """A named point within a schematic with arbitrary metadata.

    Attributes:
        type:       Marker type string (e.g. ``"exit"``, ``"spawn"``,
                    ``"point_of_interest"``).

        x, y, z:    Position inside the schematic (local coordinates).
        metadata:   Dict of arbitrary key-value string pairs.
    """

    __slots__ = ("type", "x", "y", "z", "metadata")

    def __init__(self, marker_type: str, x: int, y: int, z: int,
            metadata: Optional[Dict[str, str]] = None):
        """Initialise a new Marker."""
        self.type = marker_type
        self.x = x
        self.y = y
        self.z = z
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        """Return a string representation."""
        meta = " ".join(f"{k}={v}" for k, v in self.metadata.items())
        return f"Marker({self.type!r} {self.x},{self.y},{self.z}{' ' + meta if meta else ''})"

    @classmethod
    def parse(cls, text: str) -> "Marker":
        """Parse ``type x,y,z [key=value ...]`` from a .bschem marker line."""
        parts = text.split()
        if len(parts) < 2:
            raise ValueError(f"Bad marker definition: {text!r}")

        marker_type = parts[0]
        coords = parts[1].split(",")
        x, y, z = int(coords[0]), int(coords[1]), int(coords[2])
        metadata: Dict[str, str] = {}
        for extra in parts[2:]:
            if "=" in extra:
                k, _, v = extra.partition("=")
                metadata[k] = v

        return cls(marker_type, x, y, z, metadata)

    def serialize(self) -> str:
        """Serialize to .bschem format: ``type x,y,z [key=value ...]``."""
        s = f"{self.type} {self.x},{self.y},{self.z}"
        for k, v in self.metadata.items():
            s += f" {k}={v}"

        return s

# -- Schematic template --------------------------------------------------------
class Schematic:
    """A block schematic loaded from a ``.bschem`` file.

    Attributes:
        name:       Filename stem (e.g. ``"hallway_1"``).
        path:       Absolute path to the ``.bschem`` file.
        markers:    List of :class:`Marker` definitions.
        metadata:   Dict of arbitrary key-value metadata from the file header.
        key_map:    ``{char: block_string}`` (without ``minecraft:`` prefix).
        width:      X size.
        height:     Y size (number of layers).
        depth:      Z size.
        blocks:     3-D list ``[y][z][x]`` of full block strings (with ``minecraft:``).
    """

    def __init__(self, name: str, path: str,
            markers: List[Marker],
            metadata: Dict[str, str],
            key_map: Dict[str, str],
            width: int, height: int, depth: int,
            blocks: List[List[List[str]]]):
        """Initialise a new Schematic."""
        self.name = name
        self.path = path
        self.markers = markers
        self.metadata = metadata
        self.key_map = key_map
        self.width = width
        self.height = height
        self.depth = depth
        self.blocks = blocks

    def markers_by_type(self, marker_type: str) -> List[Marker]:
        """Return all markers with the given type."""
        return [m for m in self.markers if m.type == marker_type]

    @classmethod
    def load(cls, path: str) -> "Schematic":
        """Parse a ``.bschem`` file."""
        with open(path, "r") as f:
            raw = f.read()

        if "---" not in raw:
            raise ValueError(f"Missing --- separator in {path}")

        meta_part, block_part = raw.split("---", 1)

        markers: List[Marker] = []
        metadata: Dict[str, str] = {}
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
            if meta_key == "marker":
                markers.append(Marker.parse(value))
            elif meta_key == "width":
                meta_width = int(value)
            elif meta_key == "height":
                meta_height = int(value)
            elif meta_key == "depth":
                meta_depth = int(value)
            else:
                metadata[key] = value

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
        return cls(name, path, markers, metadata, key_map,
            meta_width, meta_height, meta_depth, layers)

    def save(self, path: Optional[str] = None) -> str:
        """Serialize to ``.bschem`` format.

        If *path* is given, also writes the result to that file.
        Returns the serialized string.
        """
        lines: List[str] = []
        lines.append(f"width: {self.width}")
        lines.append(f"height: {self.height}")
        lines.append(f"depth: {self.depth}")
        for k, v in self.metadata.items():
            lines.append(f"{k}: {v}")

        lines.append("")

        # Marker definitions
        for m in self.markers:
            lines.append(f"marker: {m.serialize()}")

        if self.markers:
            lines.append("")

        # Block key definitions (skip ~ since it's hardcoded)
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

        text = "\n".join(lines) + "\n"
        if path:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(text)

        return text

    def transformed(self, transform: str) -> "Schematic":
        """Return a new :class:`Schematic` with blocks and marker positions
        rotated/mirrored by *transform*.

        Marker metadata is preserved as-is.  If your markers contain
        directional metadata (e.g. facing), transform it after calling
        this method.

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

        # Transform marker positions (metadata preserved)
        new_markers: List[Marker] = []
        for m in self.markers:
            nx, ny, nz = _transform_local_pos(m.x, m.y, m.z, w, d, transform)
            new_markers.append(Marker(m.type, nx, ny, nz, dict(m.metadata)))

        suffix = f"_{transform}"
        return Schematic(
            name=self.name + suffix,
            path=self.path,
            markers=new_markers,
            metadata=dict(self.metadata),
            key_map=dict(self.key_map),
            width=nw, height=nh, depth=nd,
            blocks=new_blocks,
        )

    def __repr__(self) -> str:
        """Return a string representation."""
        return (f"<Schematic {self.name!r} {self.width}x{self.height}x{self.depth} "
            f"markers={len(self.markers)}>")

# -- Placed schematic instance -------------------------------------------------
class PlacedSchematic:
    """A schematic that has been pasted into the world.

    Attributes:
        schematic:      The :class:`Schematic` used.
        origin:         ``(x, y, z)`` world position of the (0,0,0) corner.
        world_name:     World name.
        original_blocks: Saved block data for cleanup ``{(x,y,z): block_string}``.
    """

    def __init__(self, schematic: Schematic, origin: Tuple[int, int, int],
            world_name: str):
        """Initialise a new PlacedSchematic."""
        self.schematic = schematic
        self.origin = origin
        self.world_name = world_name
        self.original_blocks: Dict[Tuple[int, int, int], str] = {}

    @property
    def aabb(self) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """Axis-aligned bounding box ``(min_corner, max_corner)`` inclusive."""
        ox, oy, oz = self.origin
        return (
            (ox, oy, oz),
            (ox + self.schematic.width - 1,
                oy + self.schematic.height - 1,
                oz + self.schematic.depth - 1),
            )

    @property
    def center(self) -> Tuple[int, int, int]:
        """The center value."""
        ox, oy, oz = self.origin
        return (
            ox + self.schematic.width // 2,
            oy + self.schematic.height // 2,
            oz + self.schematic.depth // 2,
        )

    def _build_bulk_ops(self) -> List[list]:
        """Build absolute-coordinate operation list for Java bulk paste."""
        ox, oy, oz = self.origin
        reverse: Dict[str, str] = {}
        for ch, block_def in self.schematic.key_map.items():
            reverse[f"minecraft:{block_def}"] = ch

        ops = _compute_ops(
            self.schematic.blocks, reverse,
            self.schematic.width, self.schematic.height, self.schematic.depth,
        )
        bulk: List[list] = []
        for op in ops:
            if op[0] == "set":
                _, lx, ly, lz, key = op
                block_def = self.schematic.key_map.get(key, "air")
                bulk.append(["set", ox + lx, oy + ly, oz + lz,
                             f"minecraft:{block_def}"])
            else:
                _, x1, y1, z1, x2, y2, z2, key = op
                block_def = self.schematic.key_map.get(key, "air")
                bulk.append(["fill", ox + x1, oy + y1, oz + z1,
                             ox + x2, oy + y2, oz + z2,
                             f"minecraft:{block_def}"])

        return bulk

    @async_task
    async def paste(self, world: Any):
        """Paste the schematic blocks into the world and save originals.

        Sends all operations to Java in a single bulk call via
        ``region.pasteOperations``.
        """
        _log(f"paste: {self.schematic.name!r} at {self.origin}")
        t0 = time.perf_counter()
        bulk_ops = self._build_bulk_ops()
        from bridge import _connection
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

        _log(f"paste: {self.schematic.name!r} done in {time.perf_counter()-t0:.3f}s")

    @async_task
    async def restore(self, world: Any):
        """Restore original blocks (cleanup) in a single bulk call."""
        if not self.original_blocks:
            return

        entries = [[wx, wy, wz, block_str]
                   for (wx, wy, wz), block_str in self.original_blocks.items()]

        from bridge import _connection
        await _connection.call(
            target="region", method="restoreBlocks",
            args=[world, entries],
        )
        self.original_blocks.clear()

    def __repr__(self):
        """Return a string representation."""
        return (f"<PlacedSchematic {self.schematic.name!r} at {self.origin}>")

