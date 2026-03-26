---
title: ImageDisplay
subtitle: Image rendering in-world
---

# ImageDisplay

An `ImageDisplay` renders an image file as a display entity in the world. It converts image pixels to colored map-like displays.

---

## Constructor

```python
ImageDisplay(location, image, pixel_size=..., dual_sided=False, dual_side_mode="mirror")
```

Create and spawn an image display.

- **Parameters:**
  - `location` (`Location`) — Spawn position.
  - `image` — Image source. Accepts:
    - `str` — File path (relative to plugin data folder, or absolute).
    - PIL `Image` object — Used directly (requires Pillow).
    - `(width, height, pixel_data)` tuple — Raw pixel data. `pixel_data` is a flat list of `(r, g, b, a)` tuples in row-major order.
  - `pixel_size` (`float`) — Size of each pixel in blocks. Smaller = more detail but more entities.
  - `dual_sided` (`bool`) — Whether the image is visible from both sides. Default `False`.
  - `dual_side_mode` (`str`) — How the back side renders. Default `"mirror"`.

| dual_side_mode | Description |
| -------------- | ----------- |
| `"mirror"` | Back side is a mirror image |

```python
# From file
display = ImageDisplay(
    Location(100, 70, 200, "world"),
    "images/logo.png",
    pixel_size=0.1,
    dual_sided=True
)

# From PIL Image
from PIL import Image
img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
display = ImageDisplay(Location(100, 70, 200, "world"), img, pixel_size=0.1)

# From raw pixel data
pixels = [(255, 0, 0, 255)] * (16 * 16)
display = ImageDisplay(Location(100, 70, 200, "world"), (16, 16, pixels), pixel_size=0.1)
```

---

## Methods

### teleport

```python
display.teleport(location)
```

Move the display. This is synchronous.

- **Parameters:**
  - `location` (`Location`) — New position.

### update

```python
display.update(image)
```

Update pixel colors without respawning entities.

- **Parameters:**
  - `image` — New image data. Accepts:
    - `str` — File path. Requires Pillow.
    - PIL `Image` object — Used directly.
    - `(width, height, pixel_data)` tuple — Raw pixel data.
    - `list` of `(r, g, b, a)` tuples — Flat RGBA pixel list (same dimensions as original, row-major).
    - `list` of `int` — Flat ARGB int list, one per entity in spawn order. This is the fastest option.

If the image dimensions differ from the original, the display is destroyed and recreated.

```python
# Update from PIL Image (no file I/O)
img = Image.new("RGBA", (16, 16), (0, 255, 0, 255))
display.update(img)

# Update from raw RGBA tuples (fastest without pre-computing ARGB)
pixels = [(0, 0, 255, 255)] * (16 * 16)
display.update(pixels)
```

### remove

```python
display.remove()
```

Despawn and destroy the display. This is synchronous.

---

## Notes

- Large images with small `pixel_size` can create many display entities and impact performance
- Supported formats depend on the Java ImageIO library (PNG, JPEG, GIF, BMP)
- Place the image files in the plugin's data folder or use an absolute path
- For animated displays, pass PIL Images or raw pixel data directly to `update()` to avoid file I/O overhead
