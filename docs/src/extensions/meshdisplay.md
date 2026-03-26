---
title: MeshDisplay
subtitle: 3D triangle mesh rendering
---

# MeshDisplay

A `MeshDisplay` renders 3D triangle mesh geometry in-world using TextDisplay entities. Each triangle face is rasterized into colored pixels positioned and oriented in 3D space.

---

## Constructor

```python
MeshDisplay(location, vertices, faces, face_colors=None, vertex_colors=None,
            texture=None, uvs=None, face_uvs=None, pixel_size=..., dual_sided=False)
```

Create and spawn a 3D mesh display.

- **Parameters:**
  - `location` (`Location`) — Base world position (mesh origin).
  - `vertices` (`list[tuple[float, float, float]]`) — Vertex positions in local space.
  - `faces` (`list[tuple[int, int, int]]`) — Triangle face indices (CCW winding for outward normals).
  - `face_colors` (`list[tuple[int,int,int,int]]`) — Per-face RGBA colors. One per face.
  - `vertex_colors` (`list[tuple[int,int,int,int]]`) — Per-vertex RGBA colors, interpolated across faces.
  - `texture` — Texture image (file path, PIL Image, or `(width, height, pixel_data)` tuple).
  - `uvs` (`list[tuple[float, float]]`) — Per-vertex UV coordinates in 0..1 range.
  - `face_uvs` (`list[tuple[int, int, int]]`) — Per-face UV index triples. Defaults to face vertex indices.
  - `pixel_size` (`float`) — Size of each rasterized pixel in blocks.
  - `dual_sided` (`bool`) — Whether faces render from both sides. Default `False`.

Color priority: `texture` > `vertex_colors` > `face_colors` > default grey.

```python
import math

# A simple colored cube
vertices = [
    (-0.5, -0.5, -0.5), ( 0.5, -0.5, -0.5),
    ( 0.5,  0.5, -0.5), (-0.5,  0.5, -0.5),
    (-0.5, -0.5,  0.5), ( 0.5, -0.5,  0.5),
    ( 0.5,  0.5,  0.5), (-0.5,  0.5,  0.5),
]
faces = [
    (0, 2, 1), (0, 3, 2),  # back
    (4, 5, 6), (4, 6, 7),  # front
    (0, 1, 5), (0, 5, 4),  # bottom
    (2, 3, 7), (2, 7, 6),  # top
    (0, 4, 7), (0, 7, 3),  # left
    (1, 2, 6), (1, 6, 5),  # right
]
colors = [
    (255, 0, 0, 255), (255, 0, 0, 255),      # red
    (0, 255, 0, 255), (0, 255, 0, 255),      # green
    (0, 0, 255, 255), (0, 0, 255, 255),      # blue
    (255, 255, 0, 255), (255, 255, 0, 255),  # yellow
    (255, 0, 255, 255), (255, 0, 255, 255),  # magenta
    (0, 255, 255, 255), (0, 255, 255, 255),  # cyan
]

mesh = MeshDisplay(
    Location(100, 70, 200, "world"),
    vertices, faces,
    face_colors=colors,
    pixel_size=1/8,
    dual_sided=True
)
```

---

## Methods

### update

```python
mesh.update(face_colors=None, vertex_colors=None)
```

Update mesh colors without respawning entities.

- **Parameters:**
  - `face_colors` — New per-face RGBA colors.
  - `vertex_colors` — New per-vertex RGBA colors.

### remove

```python
mesh.remove()
```

Despawn and destroy all mesh entities. This is synchronous.

---

## Notes

- Vertex winding order matters: CCW winding produces outward-facing normals
- Each triangle face is independently rasterized into pixel-sized TextDisplay entities
- For animation, remove and recreate the mesh with new vertex positions
- `pixel_size=1/8` is a good balance of detail vs entity count for ~1 block meshes
- Large meshes with small `pixel_size` can create many entities — be mindful of performance
