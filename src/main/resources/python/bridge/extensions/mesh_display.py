"""MeshDisplay — render 3D triangle mesh using TextDisplay entities. [ext]"""
from __future__ import annotations

import math
from typing import Any

import bridge
from bridge.wrappers import (
    World, Location
)
from bridge.extensions.image_display import ImageDisplay

class MeshDisplay:
    """Render 3D triangle mesh using TextDisplay entities with greedy meshing.

    Coplanar same-color triangles are merged into a shared 2D grid, then
    adjacent same-colored cells are greedily merged into larger rectangles —
    one TextDisplay entity per rectangle.

    **[ext]** Import from ``bridge.extensions``::
        from bridge.extensions import MeshDisplay
    """

    @staticmethod
    def _axes_from_normal(snx: Any, sny: Any, snz: Any, ref_edge: Any=None) -> Any:
        """Compute entity yaw, pitch, and local right/up/fwd axes from a face normal."""
        horiz = math.sqrt(snx * snx + snz * snz)
        pitch = math.degrees(math.asin(max(-1.0, min(1.0, -sny))))
        if horiz > 1e-4:
            yaw = math.degrees(math.atan2(-snx, snz))
        elif ref_edge is not None:
            ex, ey, ez = ref_edge
            exz = math.sqrt(ex * ex + ez * ez)
            yaw = math.degrees(math.atan2(ez, ex)) if exz > 1e-9 else 0.0
        else:
            yaw = 0.0

        yaw_rad = math.radians(yaw)
        pitch_rad = math.radians(pitch)
        fwd_x = -math.sin(yaw_rad) * math.cos(pitch_rad)
        fwd_y = -math.sin(pitch_rad)
        fwd_z = math.cos(yaw_rad) * math.cos(pitch_rad)
        rx = math.cos(yaw_rad)
        ry = 0.0
        rz = math.sin(yaw_rad)
        upx = fwd_y * rz - fwd_z * ry
        upy = fwd_z * rx - fwd_x * rz
        upz = fwd_x * ry - fwd_y * rx
        return yaw, pitch, rx, ry, rz, upx, upy, upz, fwd_x, fwd_y, fwd_z

    @staticmethod
    def _rasterize(vertices: Any, faces: Any, pixel_size: Any, face_colors: Any=None,
            vertex_colors: Any=None, tex_data: Any=None, tex_w: Any=0, tex_h: Any=0,
            uvs: Any=None, face_uvs: Any=None, dual_sided: Any=False) -> Any:
        """Handle rasterize."""
        ps = float(pixel_size)
        scale_unit = ps * 8
        scale_z = max(scale_unit * 0.08, 0.001)
        default_argb = 0xFFC8C8C8
        nudge = 0.005

        face_normals: list[tuple[float, float, float]] = []
        for fi_idx, (fi, fj, fk) in enumerate(faces):
            vt0, vt1, vt2 = vertices[fi], vertices[fj], vertices[fk]
            e1x, e1y, e1z = vt1[0] - vt0[0], vt1[1] - vt0[1], vt1[2] - vt0[2]
            e2x, e2y, e2z = vt2[0] - vt0[0], vt2[1] - vt0[1], vt2[2] - vt0[2]
            nx = e1y * e2z - e1z * e2y
            ny = e1z * e2x - e1x * e2z
            nz = e1x * e2y - e1y * e2x
            nl = math.sqrt(nx * nx + ny * ny + nz * nz)
            if nl > 1e-9:
                nx /= nl; ny /= nl; nz /= nl

            face_normals.append((nx, ny, nz))

        groups: dict[tuple, list[int]] = {}
        for fi_idx in range(len(faces)):
            nx, ny, nz = face_normals[fi_idx]
            vt0 = vertices[faces[fi_idx][0]]
            d = nx * vt0[0] + ny * vt0[1] + nz * vt0[2]
            key = (round(nx, 3), round(ny, 3), round(nz, 3), round(d, 2))
            groups.setdefault(key, []).append(fi_idx)

        payload: list[dict[str, Any]] = []
        entity_bary: list[tuple[int, float, float, float]] = []

        for key, group_faces in groups.items():
            nx, ny, nz = face_normals[group_faces[0]]
            nl = math.sqrt(nx * nx + ny * ny + nz * nz)
            if nl < 1e-9:
                continue

            nx /= nl; ny /= nl; nz /= nl

            uniform_argb = None
            if tex_data is None:
                if face_colors is not None:
                    fc0 = face_colors[group_faces[0]]
                    argb0 = (fc0[3] << 24) | (fc0[0] << 16) | (fc0[1] << 8) | fc0[2]
                    if all(face_colors[fi] == fc0 for fi in group_faces):
                        uniform_argb = argb0
                elif vertex_colors is not None:
                    verts_in_group = set()
                    for fi_idx in group_faces:
                        for vi in faces[fi_idx]:
                            verts_in_group.add(vi)

                    first_vc = vertex_colors[next(iter(verts_in_group))]
                    if all(vertex_colors[vi] == first_vc for vi in verts_in_group):
                        uniform_argb = (first_vc[3] << 24) | (first_vc[0] << 16) | (first_vc[1] << 8) | first_vc[2]
                else:
                    uniform_argb = default_argb

            fi0 = group_faces[0]
            v0_ref = vertices[faces[fi0][0]]
            v1_ref = vertices[faces[fi0][1]]
            ref_edge = (v1_ref[0] - v0_ref[0], v1_ref[1] - v0_ref[1], v1_ref[2] - v0_ref[2])

            side_normals = [(nx, ny, nz)]
            if dual_sided:
                side_normals.append((-nx, -ny, -nz))

            for side_idx, (snx, sny, snz) in enumerate(side_normals):
                face_yaw, face_pitch, rx, ry, rz, upx, upy, upz, fwd_x, fwd_y, fwd_z = \
                    MeshDisplay._axes_from_normal(snx, sny, snz, ref_edge)

                dx_d, dy_d, dz_d = -upx, -upy, -upz
                face_nudge = nudge if side_idx == 1 else 0.0

                org = vertices[faces[group_faces[0]][0]]

                all_u: list[float] = []
                all_d: list[float] = []
                for fi_idx in group_faces:
                    for vi in faces[fi_idx]:
                        vt = vertices[vi]
                        ex, ey, ez = vt[0] - org[0], vt[1] - org[1], vt[2] - org[2]
                        all_u.append(ex * rx + ey * ry + ez * rz)
                        all_d.append(ex * dx_d + ey * dy_d + ez * dz_d)

                min_u, max_u = min(all_u), max(all_u)
                min_d, max_d = min(all_d), max(all_d)

                if uniform_argb is not None:
                    face_w = max_u - min_u
                    face_h = max_d - min_d
                    center_u = (min_u + max_u) / 2
                    bottom_up = -max_d

                    wx = org[0] + center_u * rx + bottom_up * upx + face_nudge * fwd_x
                    wy = org[1] + center_u * ry + bottom_up * upy + face_nudge * fwd_y
                    wz = org[2] + center_u * rz + bottom_up * upz + face_nudge * fwd_z

                    sx = max(face_w, ps) * 8
                    sy = max(face_h, ps) * 4

                    payload.append({
                        "xOffset": 0.0, "yOffset": 0.0, "zOffset": 0.0,
                        "baseXShift": wx, "baseYShift": wy, "baseZShift": wz,
                        "yaw": face_yaw, "pitch": face_pitch,
                        "argb": int(uniform_argb), "lineWidth": 1,
                        "scaleX": sx, "scaleY": sy, "scaleZ": scale_z,
                    })
                    entity_bary.append((group_faces[0], 0.333, 0.333, 0.334))
                    continue

                u_start = math.floor(min_u / ps) * ps
                d_start = math.floor(min_d / ps) * ps
                cols = max(1, int(math.ceil((max_u - u_start) / ps)))
                rows = max(1, int(math.ceil((max_d - d_start) / ps)))

                grid: list[int | None] = [None] * (rows * cols)
                grid_fi = [0] * (rows * cols)
                grid_bu = [0.0] * (rows * cols)
                grid_bv = [0.0] * (rows * cols)
                grid_bw = [0.0] * (rows * cols)

                for fi_idx in group_faces:
                    f_i, f_j, f_k = faces[fi_idx]
                    tv0, tv1, tv2 = vertices[f_i], vertices[f_j], vertices[f_k]
                    d0x, d0y, d0z = tv0[0] - org[0], tv0[1] - org[1], tv0[2] - org[2]
                    d1x, d1y, d1z = tv1[0] - org[0], tv1[1] - org[1], tv1[2] - org[2]
                    d2x, d2y, d2z = tv2[0] - org[0], tv2[1] - org[1], tv2[2] - org[2]
                    p0u = d0x * rx + d0y * ry + d0z * rz
                    p0d = d0x * dx_d + d0y * dy_d + d0z * dz_d
                    p1u = d1x * rx + d1y * ry + d1z * rz
                    p1d = d1x * dx_d + d1y * dy_d + d1z * dz_d
                    p2u = d2x * rx + d2y * ry + d2z * rz
                    p2d = d2x * dx_d + d2y * dy_d + d2z * dz_d

                    te1u, te1d = p1u - p0u, p1d - p0d
                    te2u, te2d = p2u - p0u, p2d - p0d
                    td00 = te1u * te1u + te1d * te1d
                    td01 = te1u * te2u + te1d * te2d
                    td11 = te2u * te2u + te2d * te2d
                    tdenom = td00 * td11 - td01 * td01
                    if abs(tdenom) < 1e-12:
                        continue

                    tinv = 1.0 / tdenom

                    tuv0 = tuv1 = tuv2 = None
                    if tex_data and uvs and face_uvs:
                        tuvi, tuvj, tuvk = face_uvs[fi_idx]
                        tuv0, tuv1, tuv2 = uvs[tuvi], uvs[tuvj], uvs[tuvk]

                    tmin_u = min(p0u, p1u, p2u)
                    tmax_u = max(p0u, p1u, p2u)
                    tmin_d = min(p0d, p1d, p2d)
                    tmax_d = max(p0d, p1d, p2d)
                    c0 = max(0, int(math.floor((tmin_u - u_start) / ps)))
                    c1 = min(cols, int(math.ceil((tmax_u - u_start) / ps)))
                    r0 = max(0, int(math.floor((tmin_d - d_start) / ps)))
                    r1 = min(rows, int(math.ceil((tmax_d - d_start) / ps)))

                    for r in range(r0, r1):
                        fd = d_start + (r + 0.5) * ps
                        for c in range(c0, c1):
                            fu = u_start + (c + 0.5) * ps
                            du = fu - p0u
                            dd = fd - p0d
                            td20 = du * te1u + dd * te1d
                            td21 = du * te2u + dd * te2d
                            tbv = (td11 * td20 - td01 * td21) * tinv
                            tbw = (td00 * td21 - td01 * td20) * tinv
                            tbu = 1.0 - tbv - tbw
                            if tbu >= -0.005 and tbv >= -0.005 and tbw >= -0.005:
                                if tuv0 is not None and tuv1 is not None and tuv2 is not None and tex_data is not None:
                                    tu_c = tbu * tuv0[0] + tbv * tuv1[0] + tbw * tuv2[0]
                                    tv_c = tbu * tuv0[1] + tbv * tuv1[1] + tbw * tuv2[1]
                                    txi = int(tu_c * (tex_w - 1)) % tex_w
                                    tyi = int(tv_c * (tex_h - 1)) % tex_h
                                    cr, cg, cb, ca = tex_data[tyi * tex_w + txi]
                                    argb = (ca << 24) | (cr << 16) | (cg << 8) | cb
                                elif vertex_colors:
                                    vc0 = vertex_colors[f_i]
                                    vc1 = vertex_colors[f_j]
                                    vc2 = vertex_colors[f_k]
                                    cr = int(max(0, min(255, tbu * vc0[0] + tbv * vc1[0] + tbw * vc2[0])))
                                    cg = int(max(0, min(255, tbu * vc0[1] + tbv * vc1[1] + tbw * vc2[1])))
                                    cb = int(max(0, min(255, tbu * vc0[2] + tbv * vc1[2] + tbw * vc2[2])))
                                    ca = int(max(0, min(255, tbu * vc0[3] + tbv * vc1[3] + tbw * vc2[3])))
                                    argb = (ca << 24) | (cr << 16) | (cg << 8) | cb
                                elif face_colors:
                                    fc = face_colors[fi_idx]
                                    argb = (fc[3] << 24) | (fc[0] << 16) | (fc[1] << 8) | fc[2]
                                else:
                                    argb = default_argb

                                idx = r * cols + c
                                grid[idx] = argb
                                grid_fi[idx] = fi_idx
                                grid_bu[idx] = tbu
                                grid_bv[idx] = tbv
                                grid_bw[idx] = tbw

                used = [False] * (rows * cols)
                for r in range(rows):
                    for c in range(cols):
                        rc = r * cols + c
                        if used[rc] or grid[rc] is None:
                            continue

                        color = grid[rc]
                        w = 1
                        while c + w < cols:
                            idx2 = r * cols + c + w
                            if grid[idx2] != color or used[idx2]:
                                break

                            w += 1

                        h = 1
                        while r + h < rows:
                            ok = True
                            for dc in range(w):
                                idx2 = (r + h) * cols + c + dc
                                if grid[idx2] != color or used[idx2]:
                                    ok = False
                                    break

                            if not ok:
                                break

                            h += 1

                        for dr in range(h):
                            for dc in range(w):
                                used[(r + dr) * cols + c + dc] = True

                        center_u = u_start + (c + w * 0.5) * ps
                        bottom_up = -(d_start + (r + h) * ps)
                        wx = org[0] + center_u * rx + bottom_up * upx + face_nudge * fwd_x
                        wy = org[1] + center_u * ry + bottom_up * upy + face_nudge * fwd_y
                        wz = org[2] + center_u * rz + bottom_up * upz + face_nudge * fwd_z

                        ci = (r + h // 2) * cols + (c + w // 2)
                        sx = scale_unit * w
                        sy = (scale_unit / 2) * h

                        payload.append({
                            "xOffset": 0.0, "yOffset": 0.0, "zOffset": 0.0,
                            "baseXShift": wx, "baseYShift": wy, "baseZShift": wz,
                            "yaw": face_yaw, "pitch": face_pitch,
                            "argb": int(color),  "lineWidth": 1,  # type: ignore[arg-type]
                            "scaleX": sx, "scaleY": sy, "scaleZ": scale_z,
                        })
                        entity_bary.append((grid_fi[ci], grid_bu[ci], grid_bv[ci], grid_bw[ci]))

        return payload, entity_bary

    def __init__(self, location: Location,
            vertices: list[tuple[float, float, float]],
            faces: list[tuple[int, int, int]],
            face_colors: list[tuple[int,int,int,int]] | None = None,
            vertex_colors: list[tuple[int,int,int,int]] | None = None,
            texture: Any = None,
            uvs: list[tuple[float, float]] | None = None,
            face_uvs: list[tuple[int, int, int]] | None = None,
            pixel_size: float = 1 / 16,
            dual_sided: bool = False) -> None:
        """Initialise a new MeshDisplay."""
        world: Any = location.world
        if isinstance(world, str):
            world = World(name=world)

        if world is None:
            world = World(name='world')

        self._entities: list[Any] = []
        self._location = location
        self._pixel_size = pixel_size
        self._dual_sided = dual_sided
        self._vertices = list(vertices)
        self._faces = list(faces)
        self._face_colors = face_colors
        self._vertex_colors = vertex_colors
        self._entity_bary: list[tuple[int, float, float, float]] = []
        self._world = world

        tex_data = None
        tex_w = tex_h = 0
        if texture is not None:
            tex_w, tex_h, tex_data = ImageDisplay._load_pixels(texture)

        if face_uvs is None:
            face_uvs = faces

        payload, self._entity_bary = MeshDisplay._rasterize(
            vertices, faces, pixel_size, face_colors, vertex_colors,
            tex_data, tex_w, tex_h, uvs, face_uvs, dual_sided)

        spawned = world._call_sync("spawnImagePixels", location, payload)
        self._entities = list(spawned) if isinstance(spawned, list) else []

    def update_geometry(self, vertices: list[tuple[float, float, float]],
            face_colors: list[tuple[int,int,int,int]] | None = None,
            vertex_colors: list[tuple[int,int,int,int]] | None = None) -> None:
        """Update mesh vertex positions and optionally colors."""
        if face_colors is not None:
            self._face_colors = face_colors

        if vertex_colors is not None:
            self._vertex_colors = vertex_colors

        fc = self._face_colors
        vc = self._vertex_colors

        payload, new_bary = MeshDisplay._rasterize(
            vertices, self._faces, self._pixel_size, fc, vc,
            dual_sided=self._dual_sided)

        needed = len(payload)
        have = len(self._entities)
        ox = float(self._location.x)
        oy = float(self._location.y)
        oz = float(self._location.z)

        if needed > have:
            extra = self._world._call_sync("spawnImagePixels", self._location, payload[have:])
            if isinstance(extra, list):
                self._entities.extend(extra)

            have = len(self._entities)

        entries: list[list[Any]] = []
        for i in range(min(needed, have)):
            e = self._entities[i]
            if e._handle is None:
                continue

            p = payload[i]
            entries.append([
                e._handle,
                ox + p["baseXShift"], oy + p["baseYShift"], oz + p["baseZShift"],
                p["yaw"], p["pitch"], p["argb"],
                p["scaleX"], p["scaleY"], p["scaleZ"],
                p["yOffset"],
            ])

        for i in range(needed, have):
            e = self._entities[i]
            if e._handle is None:
                continue

            entries.append([e._handle, ox, oy - 1000, oz, 0.0, 0.0, 0x00000000, 0.001, 0.001, 0.001])

        if entries and bridge._connection is not None:  # type: ignore[attr-defined]
            bridge._connection.send_fire_forget("move_entities", entries=entries)  # type: ignore[attr-defined]

        self._vertices = list(vertices)
        self._entity_bary = new_bary

    def remove(self) -> None:
        """Remove all spawned mesh entities."""
        if not self._entities:
            return

        handles = [e._handle for e in self._entities if e._handle is not None]
        if handles and bridge._connection is not None:  # type: ignore[attr-defined]
            bridge._connection.send_fire_forget("remove_entities", handles=handles)  # type: ignore[attr-defined]

        self._entities.clear()
        self._entity_bary.clear()

    def update(self, face_colors: list[tuple[int,int,int,int]] | None = None,
            vertex_colors: list[tuple[int,int,int,int]] | None = None) -> None:
        """Update mesh colors without respawning entities."""
        if not self._entities:
            return

        entries: list[list[int]] = []
        for i, (face_idx, bu, bv, bw) in enumerate(self._entity_bary):
            if i >= len(self._entities):
                break

            entity = self._entities[i]
            if entity._handle is None:
                continue

            if vertex_colors is not None:
                fi, fj, fk = self._faces[face_idx]
                c0, c1, c2 = vertex_colors[fi], vertex_colors[fj], vertex_colors[fk]
                r = int(max(0, min(255, bu * c0[0] + bv * c1[0] + bw * c2[0])))
                g = int(max(0, min(255, bu * c0[1] + bv * c1[1] + bw * c2[1])))
                b_ = int(max(0, min(255, bu * c0[2] + bv * c1[2] + bw * c2[2])))
                a = int(max(0, min(255, bu * c0[3] + bv * c1[3] + bw * c2[3])))
                argb = (a << 24) | (r << 16) | (g << 8) | b_
            elif face_colors is not None:
                c = face_colors[face_idx]
                argb = (c[3] << 24) | (c[0] << 16) | (c[1] << 8) | c[2]
            else:
                continue

            entries.append([entity._handle, argb])

        if entries and bridge._connection is not None:  # type: ignore[attr-defined]
            bridge._connection.send_fire_forget("update_entities", entries=entries)  # type: ignore[attr-defined]

