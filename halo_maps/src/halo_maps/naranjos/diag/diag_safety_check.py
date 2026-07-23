"""Debug the safety check — why does it remove triangular faces?"""
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
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass

import bpy, bmesh
from collections import defaultdict

for n in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()
from halo_maps.naranjos.level import assemble_naranjos_level
assemble_naranjos_level()

from halo_maps.naranjos.validate_bsp import (
    _plane_key, _project_tri, _convex_clip, _tri_area_2d, AREA_TOL
)

obj = bpy.data.objects.get("bsp_world")
assert obj is not None

bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = obj.evaluated_get(dg)
em = ev.to_mesh()
bm = bmesh.new()
bm.from_mesh(em)
ev.to_mesh_clear()
bm.faces.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.verts.ensure_lookup_table()

WALL_IDX = 0
HORIZ_Z = 0.9

# Find overlapping pairs (same as validate)
groups: dict = {}
for f in bm.faces:
    if len(f.verts) == 3 and f.material_index == WALL_IDX:
        groups.setdefault(_plane_key(f), []).append(f)

to_del: set = set()
pairs_found = []
for faces in groups.values():
    if len(faces) < 2:
        continue
    for i, a in enumerate(faces):
        if a in to_del:
            continue
        va_set = set(a.verts)
        tri_a = list(_project_tri(a))
        area_a = abs(_tri_area_2d(tri_a))
        if area_a < AREA_TOL:
            to_del.add(a)
            continue
        for b in faces[i + 1:]:
            if b in to_del:
                continue
            if len(va_set.intersection(b.verts)) >= 2:
                continue
            inter = _convex_clip(tri_a, list(_project_tri(b)))
            if len(inter) < 3:
                continue
            if abs(_tri_area_2d(inter)) > AREA_TOL:
                area_b = abs(_tri_area_2d(list(_project_tri(b))))
                pairs_found.append((a, b, area_a, area_b))
                if area_a <= area_b:
                    to_del.add(a)
                    break
                else:
                    to_del.add(b)

print(f"[SC-DEBUG] Overlapping pairs found: {len(pairs_found)}")
print(f"[SC-DEBUG] to_del count: {len(to_del)}")

for f in to_del:
    n = f.normal.normalized()
    is_horiz = abs(n.z) > HORIZ_Z
    coords = [tuple(round(c, 3) for c in v.co) for v in f.verts]
    print(f"  face {f.index}: horiz={is_horiz} normal=({n.x:.3f},{n.y:.3f},{n.z:.3f})")
    print(f"    verts: {coords}")
    for e in f.edges:
        n_link = len(e.link_faces)
        vc1 = tuple(round(c, 3) for c in e.verts[0].co)
        vc2 = tuple(round(c, 3) for c in e.verts[1].co)
        status = "BOUNDARY" if n_link == 1 else ("NM" if n_link > 2 else "2-manifold")
        print(f"    edge {vc1}→{vc2}: {n_link} faces [{status}]")

# Now run the safety check verbosely
horiz_del = {f for f in to_del if abs(f.normal.normalized().z) > HORIZ_Z}
vert_del = to_del - horiz_del
safe = set(vert_del)
print(f"\n[SC-DEBUG] horiz_del: {len(horiz_del)}, vert_del: {len(vert_del)}")

for guard in range(len(vert_del) + 2):
    all_del = safe | horiz_del
    deg: dict = defaultdict(int)
    eo: dict = {}
    for f in safe:
        for e in f.edges:
            rem = sum(1 for lf in e.link_faces if lf not in all_del)
            # Print edge info
            vc1 = tuple(round(c, 3) for c in e.verts[0].co)
            vc2 = tuple(round(c, 3) for c in e.verts[1].co)
            print(f"  f{f.index} edge {vc1}→{vc2}: link_faces={len(e.link_faces)}, rem={rem}")
            if rem == 1:
                deg[e.verts[0]] += 1
                deg[e.verts[1]] += 1
                eo[e] = f

    print(f"  Degree values: {[(v.index, d) for v, d in deg.items()]}")
    ov = [v for v, d in deg.items() if d == 1]
    print(f"  Open vertices (degree=1): {[v.index for v in ov]}")

    if not ov:
        print(f"  -> Clean! No open vertices. Breaking.")
        break

    culp = None
    for v in ov:
        for e, f in eo.items():
            if v in e.verts and f in safe:
                culp = f; break
        if culp:
            break
    if culp:
        print(f"  -> Removing face {culp.index} from safe_del")
        safe.discard(culp)
    else:
        print(f"  -> No culprit found, breaking")
        break

print(f"\n[SC-DEBUG] Final safe count: {len(safe)}")
print(f"[SC-DEBUG] Final all_delete: {len(safe | horiz_del)}")

bm.free()
print("[SC-DEBUG] done")
