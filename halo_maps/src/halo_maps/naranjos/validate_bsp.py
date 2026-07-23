"""Validate the generated Naranjos BSP mesh.

Run from the repository root:

    blender --background src/halo_maps/naranjos/blend/naranjos_dsl_updated.blend \
        --python src/halo_maps/naranjos/validate_bsp.py -- --object bsp_merged
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent
for candidate in (_SRC_ROOT, *_SRC_ROOT.parents):
    if (candidate / "src" / "halo_maps").exists():
        _SRC_ROOT = str(candidate / "src")
        break
else:
    _SRC_ROOT = str(_SRC_ROOT)
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

import bpy
import bmesh
from mathutils import Vector

from halo_maps.naranjos.generate_dsl import _check_t_intersections


AREA_TOL = 1e-8
PLANE_TOL = 1e-5


def _args() -> dict[str, str]:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    out = {"object": "bsp_merged", "blend": ""}
    i = 0
    while i < len(argv):
        if argv[i] == "--object" and i + 1 < len(argv):
            out["object"] = argv[i + 1]
            i += 2
        elif argv[i] == "--blend" and i + 1 < len(argv):
            out["blend"] = argv[i + 1]
            i += 2
        else:
            i += 1
    return out


def _mesh_bmesh(obj_name: str) -> tuple[bmesh.types.BMesh | None, str | None]:
    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        return None, f"Object '{obj_name}' not found or not a mesh"

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(eval_mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    eval_obj.to_mesh_clear()
    return bm, None


def _signed_volume(bm: bmesh.types.BMesh) -> float:
    volume = 0.0
    for face in bm.faces:
        verts = list(face.verts)
        if len(verts) < 3:
            continue
        origin = verts[0].co
        for i in range(1, len(verts) - 1):
            v0 = origin
            v1 = verts[i].co
            v2 = verts[i + 1].co
            volume += v0.dot(v1.cross(v2)) / 6.0
    return volume


def _tri_area_2d(poly: list[tuple[float, float]]) -> float:
    area = 0.0
    for i, (x0, y0) in enumerate(poly):
        x1, y1 = poly[(i + 1) % len(poly)]
        area += (x0 * y1) - (x1 * y0)
    return area * 0.5


def _inside(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float], ccw: bool) -> bool:
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return cross >= -1e-9 if ccw else cross <= 1e-9


def _line_intersection(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> tuple[float, float]:
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        return p2
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return px, py


def _convex_clip(
    subject: list[tuple[float, float]],
    clip: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    output = subject
    ccw = _tri_area_2d(clip) >= 0
    for i, a in enumerate(clip):
        b = clip[(i + 1) % len(clip)]
        input_poly = output
        output = []
        if not input_poly:
            break
        prev = input_poly[-1]
        for cur in input_poly:
            cur_in = _inside(cur, a, b, ccw)
            prev_in = _inside(prev, a, b, ccw)
            if cur_in:
                if not prev_in:
                    output.append(_line_intersection(prev, cur, a, b))
                output.append(cur)
            elif prev_in:
                output.append(_line_intersection(prev, cur, a, b))
            prev = cur
    return output


def _project_tri(face: bmesh.types.BMFace) -> tuple[tuple[float, float], ...]:
    normal = face.normal.normalized()
    axis = max(range(3), key=lambda i: abs(normal[i]))
    pts = []
    for vert in face.verts:
        co = vert.co
        if axis == 0:
            pts.append((co.y, co.z))
        elif axis == 1:
            pts.append((co.x, co.z))
        else:
            pts.append((co.x, co.y))
    return tuple(pts)


def _plane_key(face: bmesh.types.BMFace) -> tuple[int, int, int, int]:
    n = face.normal.normalized()
    if (n.x, n.y, n.z) < (0.0, 0.0, 0.0):
        n.negate()
    d = -n.dot(face.verts[0].co)
    return (
        round(n.x / PLANE_TOL),
        round(n.y / PLANE_TOL),
        round(n.z / PLANE_TOL),
        round(d / PLANE_TOL),
    )


def _coplanar_overlaps(bm: bmesh.types.BMesh, max_report: int = 10) -> list[str]:
    # Only check wall faces (material slot 0).  Portal faces (slot 1) and sky
    # faces (slot 2) are intentionally placed on the same planes as building
    # geometry; flagging those as overlaps would be a false positive.
    _WALL_IDX = 0
    groups: dict[tuple[int, int, int, int], list[bmesh.types.BMFace]] = {}
    for face in bm.faces:
        if len(face.verts) == 3 and face.material_index == _WALL_IDX:
            groups.setdefault(_plane_key(face), []).append(face)

    issues: list[str] = []
    for faces in groups.values():
        if len(faces) < 2:
            continue
        for i, a in enumerate(faces):
            verts_a = set(a.verts)
            tri_a = list(_project_tri(a))
            na = a.normal.normalized()
            for b in faces[i + 1:]:
                # Skip anti-parallel pairs: these are back-to-back wall faces
                # (one face per room side on the same partition plane).  They
                # appear in the same plane group because _plane_key canonicalises
                # the normal direction, but they are valid BSP geometry and do
                # NOT cause tool.exe compile failures.
                if na.dot(b.normal.normalized()) < -0.5:
                    continue
                if len(verts_a.intersection(b.verts)) >= 2:
                    continue
                inter = _convex_clip(tri_a, list(_project_tri(b)))
                if len(inter) >= 3 and abs(_tri_area_2d(inter)) > AREA_TOL:
                    issues.append(f"faces {a.index} and {b.index} overlap")
                    if len(issues) >= max_report:
                        return issues
    return issues


def validate(obj_name: str) -> bool:
    bm, error = _mesh_bmesh(obj_name)
    if error:
        print(f"[FAIL] {error}")
        return False
    assert bm is not None

    ok = True

    boundary = [e for e in bm.edges if len(e.link_faces) < 2]
    non_manifold = [e for e in bm.edges if len(e.link_faces) != 2]
    non_tri = [f for f in bm.faces if len(f.verts) != 3]
    degenerate = [f for f in bm.faces if f.calc_area() <= AREA_TOL or f.normal.length < 1e-8]
    volume = _signed_volume(bm)
    t_issues = _check_t_intersections(bm)
    overlaps = _coplanar_overlaps(bm)

    checks = [
        ("BSP sealed", not boundary and not non_manifold, f"{len(boundary)} boundary, {len(non_manifold)} non-manifold"),
        ("triangulated", not non_tri, f"{len(non_tri)} non-triangle faces"),
        ("outward normals", volume > AREA_TOL and not degenerate, f"signed_volume={volume:.6f}, degenerate={len(degenerate)}"),
        ("no T-junctions", not t_issues, (f"{len(t_issues)} found: " + "; ".join(t_issues[:5])) if t_issues else "0 found"),
        ("no coplanar overlaps", not overlaps, (f"{len(overlaps)} found: " + "; ".join(overlaps[:5])) if overlaps else "0 found"),
    ]

    print(f"[validate-bsp] object={obj_name} verts={len(bm.verts)} faces={len(bm.faces)}")
    for label, passed, detail in checks:
        print(f"[{'OK' if passed else 'FAIL'}] {label}: {detail}")
        ok = ok and passed

    bm.free()
    return ok


if __name__ == "__main__":
    args = _args()
    if args["blend"]:
        bpy.ops.wm.open_mainfile(filepath=args["blend"])
    sys.exit(0 if validate(args["object"]) else 1)
