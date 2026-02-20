---
title: ImageDisplay
subtitle: Image rendering in-world
---

# ImageDisplay

An `ImageDisplay` renders an image file as a display entity in the world. It converts image pixels to colored map-like displays.

---

## Constructor

```python
ImageDisplay(location, image_path, pixel_size=..., dual_sided=False, dual_side_mode="mirror")
```

Create and spawn an image display.

- **Parameters:**
  - `location` ([`Location`](location.md)) — Spawn position.
  - `image_path` (`str`) — Path to the image file (relative to plugin data folder, or absolute).
  - `pixel_size` (`float`) — Size of each pixel in blocks. Smaller = more detail but more entities.
  - `dual_sided` (`bool`) — Whether the image is visible from both sides. Default `False`.
  - `dual_side_mode` (`str`) — How the back side renders. Default `"mirror"`.

| dual_side_mode | Description |
|----------------|-------------|
| `"mirror"` | Back side is a mirror image |

```python
display = ImageDisplay(
    Location(100, 70, 200, "world"),
    "images/logo.png",
    pixel_size=0.1,
    dual_sided=True
)
```

---

## Methods

### teleport

```python
display.teleport(location)
```

Move the display. This is synchronous.

- **Parameters:**
  - `location` ([`Location`](location.md)) — New position.

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
