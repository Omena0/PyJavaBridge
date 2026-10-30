"""ImageDisplay — render pixel art images in-world using TextDisplay entities. [ext]"""
from __future__ import annotations

import math
from typing import Any

import bridge
from bridge.wrappers import (
    World, Location
)
from bridge.errors import (
    EntityGoneException, BridgeError,
)

class ImageDisplay:
    """Render pixel art images in-world using one TextDisplay per pixel.

    This uses TextDisplay background color only (no glyph text) to avoid
    character spacing gaps and row spacing artifacts.

    **[ext]** Import from ``bridge.extensions``::
        from bridge.extensions import ImageDisplay
    """

    @staticmethod
    def _load_pixels(image: Any) -> tuple[int, int, list[tuple[int, int, int, int]]]:
        """Return (width, height, flat_rgba_list) from various image input types."""
        if isinstance(image, str):
            try:
                from PIL import Image as PILImage  # type: ignore[import-not-found]
            except ImportError as e:
                raise ImportError(
                    "Pillow is required for loading images from file paths. "
                    "Install with: pip install Pillow"
                ) from e

            img = PILImage.open(image).convert("RGBA")
            return int(img.size[0]), int(img.size[1]), list(img.getdata())  # type: ignore[arg-type]

        if hasattr(image, 'size') and hasattr(image, 'convert'):
            img = image.convert("RGBA")
            return int(img.size[0]), int(img.size[1]), list(img.getdata())  # type: ignore[arg-type]

        if isinstance(image, (tuple, list)) and len(image) == 3:
            w, h, data = image
            if isinstance(w, int) and isinstance(h, int):
                return w, h, list(data)

        raise TypeError("image must be a file path (str), PIL Image, or (width, height, pixel_data) tuple")

    def __init__(self, location: Location, image: Any,
            pixel_size: float = 1/16,
            dual_sided: bool = False,
            dual_side_mode: str = "mirror") -> None:
        """Initialise a new ImageDisplay."""
        width, height, _flat_pixels = ImageDisplay._load_pixels(image)

        world: Any = location.world
        if isinstance(world, str):
            world = World(name=world)

        if world is None:
            world = World(name='world')

        self._entities: list[Any] = []
        self._placements: list[tuple[Any, float, float, float, float, float, float, float, float, float, float]] = []
        self._pixel_positions: list[tuple[int, int]] = []
        self._location = location
        self._pixel_size = pixel_size
        self._width = width
        self._height = height
        self._dual_sided = dual_sided

        yaw = float(getattr(location, 'yaw', 0.0))
        pitch = float(getattr(location, 'pitch', 0.0))
        pixel_scale = pixel_size * 8
        pixel_step = pixel_scale / 8
        scale_x = pixel_scale
        scale_y = pixel_scale/2
        scale_z = max(pixel_scale * 0.08, 0.001)

        x_base_offset = pixel_step * 0.5
        y_base_offset = -1.0 * pixel_step
        dual_depth_shift = 0.01
        dual_mode = str(dual_side_mode).strip().lower()
        if dual_mode not in {"mirror", "same"}:
            dual_mode = "mirror"

        def _local_to_world_shift(local_x: float, local_y: float, entity_yaw: float, entity_pitch: float, local_z: float = 0.0) -> tuple[float, float, float]:
            """Handle local to world shift."""
            yaw_rad = math.radians(entity_yaw)
            pitch_rad = math.radians(entity_pitch)

            fwd_x = -math.sin(yaw_rad) * math.cos(pitch_rad)
            fwd_y = -math.sin(pitch_rad)
            fwd_z = math.cos(yaw_rad) * math.cos(pitch_rad)

            right_x = fwd_z
            right_y = 0.0
            right_z = -fwd_x
            right_len = math.sqrt(right_x * right_x + right_y**2 + right_z * right_z)
            if right_len <= 1e-9:
                right_x, right_y, right_z = 1.0, 0.0, 0.0
            else:
                inv = 1.0 / right_len
                right_x *= inv
                right_y *= inv
                right_z *= inv

            up_x = (fwd_y * right_z) - (fwd_z * right_y)
            up_y = (fwd_z * right_x) - (fwd_x * right_z)
            up_z = (fwd_x * right_y) - (fwd_y * right_x)

            return (
                (right_x * local_x) + (up_x * local_y) + (fwd_x * local_z),
                (right_y * local_x) + (up_y * local_y) + (fwd_y * local_z),
                (right_z * local_x) + (up_z * local_y) + (fwd_z * local_z),
            )

        payload: list[dict[str, Any]] = []
        placement_meta: list[tuple[float, float, float, float, float, float, float, float, float, float]] = []

        for row in range(height):
            for col in range(width):
                r, g, b, a = _flat_pixels[row * width + col]
                if a <= 0:
                    continue

                self._pixel_positions.append((col, row))
                argb = (int(a) << 24) | (int(r) << 16) | (int(g) << 8) | int(b)
                x_offset = x_base_offset + (float(col) * pixel_step)
                y_offset = y_base_offset - (float(row) * pixel_step)
                z_offset = 0.0
                base_z_shift = 0.0
                base_x_shift, base_y_shift, base_xy_z_shift = _local_to_world_shift(x_offset, y_offset, yaw, pitch, 0.01)

                payload.append({
                    "xOffset": 0.0,
                    "yOffset": 0.0,
                    "zOffset": z_offset,
                    "baseXShift": base_x_shift,
                    "baseYShift": base_y_shift,
                    "baseZShift": base_z_shift + base_xy_z_shift,
                    "yaw": yaw,
                    "pitch": pitch,
                    "argb": int(argb),
                    "lineWidth": 1,
                    "scaleX": scale_x,
                    "scaleY": scale_y,
                    "scaleZ": scale_z,
                })
                placement_meta.append((base_x_shift, base_y_shift, base_z_shift + base_xy_z_shift, z_offset, yaw, pitch, scale_x, scale_y, scale_z, 0.0))

                if dual_sided:
                    back_yaw = yaw + 180.0 if dual_mode == "mirror" else yaw
                    fwd_x_shift, fwd_y_shift, fwd_z_shift = _local_to_world_shift(0.0, 0.0, yaw, pitch, -dual_depth_shift)

                    payload.append({
                        "xOffset": 0.0,
                        "yOffset": 0.0,
                        "zOffset": z_offset,
                        "baseXShift": base_x_shift + fwd_x_shift,
                        "baseYShift": base_y_shift + fwd_y_shift,
                        "baseZShift": base_z_shift + base_xy_z_shift + fwd_z_shift,
                        "yaw": back_yaw,
                        "pitch": pitch,
                        "argb": int(argb),
                        "lineWidth": 1,
                        "scaleX": scale_x,
                        "scaleY": scale_y,
                        "scaleZ": scale_z,
                    })
                    placement_meta.append((base_x_shift + fwd_x_shift, base_y_shift + fwd_y_shift, base_z_shift + base_xy_z_shift + fwd_z_shift, z_offset, back_yaw, pitch, scale_x, scale_y, scale_z, 0.0))

        spawned = world._call_sync("spawnImagePixels", location, payload)
        spawned_list = spawned if isinstance(spawned, list) else []

        for entity, meta in zip(spawned_list, placement_meta):
            base_x_shift, base_y_shift, base_z_shift, z_offset, entity_yaw, entity_pitch, sx, sy, sz, xy_zero = meta
            self._entities.append(entity)
            self._placements.append((entity, base_x_shift, base_y_shift, base_z_shift, z_offset, entity_yaw, entity_pitch, sx, sy, sz, xy_zero))

    def teleport(self, location: Location) -> None:
        """Move all pixel entities to a new base location."""
        alive_placements: list[tuple[Any, float, float, float, float, float, float, float, float, float, float]] = []
        for entity, base_x_shift, base_y_shift, base_z_shift, z_offset, yaw, pitch, sx, sy, sz, xy_zero in self._placements:
            try:
                loc = Location(
                    x=location.x + float(base_x_shift),
                    y=location.y + float(base_y_shift),
                    z=location.z + float(base_z_shift),
                    world=location.world,
                    yaw=yaw,
                    pitch=pitch,
                )
                entity.teleport(loc)
                entity._call_sync("setRotation", float(yaw), float(pitch))
                entity._call_sync("setTransform", float(xy_zero), float(xy_zero), float(z_offset),
                    float(sx), float(sy), float(sz))

                alive_placements.append((entity, base_x_shift, base_y_shift, base_z_shift, z_offset, yaw, pitch, sx, sy, sz, xy_zero))
            except EntityGoneException:
                pass

        self._placements = alive_placements
        self._entities = [entry[0] for entry in alive_placements]
        self._location = location

    def remove(self) -> None:
        """Remove all spawned pixel entities."""
        if not self._entities:
            return

        handles = [e._handle for e in self._entities if e._handle is not None]
        if handles and bridge._connection is not None:  # type: ignore[attr-defined]
            try:
                bridge._connection.call_sync_raw("remove_entities", handles=handles)  # type: ignore[attr-defined]
            except (EntityGoneException, BridgeError):
                pass

        self._entities.clear()
        self._placements.clear()

    def update(self, image: Any) -> None:
        """Update pixel colors without respawning entities.

        Accepts the same types as the constructor: file path (str), PIL Image,
        or (width, height, pixel_data) tuple.

        Additionally accepts:
        - A flat list of RGBA tuples (same dimensions as original image, row-major)
        - A flat list of ARGB ints (one per entity, matching spawn order — fastest)

        If dimensions differ, falls back to remove + recreate.
        """
        if not self._entities:
            return

        if isinstance(image, list) and image and isinstance(image[0], int):
            self._update_argb(image)
            return

        if isinstance(image, list) and image and isinstance(image[0], (tuple, list)):
            self._update_from_flat(image)
            return

        width, height, flat_pixels = ImageDisplay._load_pixels(image)

        if width != self._width or height != self._height:
            loc = self._location
            ps = self._pixel_size
            ds = self._dual_sided
            self.remove()
            new = ImageDisplay(loc, image, ps, ds)
            self._entities = new._entities
            self._placements = new._placements
            self._pixel_positions = new._pixel_positions
            self._width = new._width
            self._height = new._height
            return

        self._update_from_flat(flat_pixels)

    def _update_from_flat(self, flat_pixels: list[tuple[int, int, int, int]]) -> None:
        """Update entities from a flat row-major RGBA pixel list."""
        w = self._width
        h = self._height
        expected = w * h
        if len(flat_pixels) < expected:
            raise ValueError(f"Expected at least {expected} RGBA pixels, got {len(flat_pixels)}")

        entries: list[list[int]] = []
        entity_idx = 0
        for col, row in self._pixel_positions:
            if entity_idx >= len(self._entities):
                raise ValueError("ImageDisplay entity state is inconsistent with pixel mapping")

            r, g, b, a = flat_pixels[row * w + col]
            argb = (a << 24) | (r << 16) | (g << 8) | b
            e = self._entities[entity_idx]
            if e._handle is not None:
                entries.append([e._handle, argb])

            entity_idx += 1
            if self._dual_sided:
                if entity_idx >= len(self._entities):
                    raise ValueError("ImageDisplay dual-sided entity state is inconsistent")

                e = self._entities[entity_idx]
                if e._handle is not None:
                    entries.append([e._handle, argb])

                entity_idx += 1

        if entries and bridge._connection is not None:  # type: ignore[attr-defined]
            bridge._connection.send_fire_forget("update_entities", entries=entries)  # type: ignore[attr-defined]

    def _update_argb(self, argb_list: list[int]) -> None:
        """Update entities from a flat ARGB int list (one per entity)."""
        entries: list[list[int]] = []
        entries.extend(
            [entity._handle, argb_list[i]]
            for i, entity in enumerate(self._entities)
            if i < len(argb_list) and entity._handle is not None
        )
        if entries and bridge._connection is not None:  # type: ignore[attr-defined]
            bridge._connection.send_fire_forget("update_entities", entries=entries)  # type: ignore[attr-defined]
