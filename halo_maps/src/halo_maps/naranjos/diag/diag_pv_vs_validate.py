"""Debug why _pv_fix finds 0 but validate finds 2 overlaps."""
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
    _plane_key, _project_tri, _convex_clip, _tri_area_2d, AREA_TOL, PLANE_TOL
)

obj = bpy.data.objects.get("bsp_world")
assert obj is not None

WALL_IDX = 0

def find_overlaps_verbose(bm, label):
    bm.faces.ensure_lookup_table()
    groups: dict = {}
    for f in bm.faces:
        if len(f.verts) == 3 and f.material_index == WALL_IDX:
            groups.setdefault(_plane_key(f), []).append(f)

    overlaps = []
    for pk, faces in groups.items():
        if len(faces) < 2:
            continue
        for i, a in enumerate(faces):
            verts_a = set(a.verts)
            tri_a = list(_project_tri(a))
            for b in faces[i + 1:]:
                if len(verts_a.intersection(b.verts)) >= 2:
                    continue
                inter = _convex_clip(tri_a, list(_project_tri(b)))
                if len(inter) >= 3 and abs(_tri_area_2d(inter)) > AREA_TOL:
                    area = abs(_tri_area_2d(inter))
                    overlaps.append((a.index, b.index, area, pk))

    print(f"[DBG] {label}: {len(overlaps)} overlapping pairs")
    for a_idx, b_idx, area, pk in overlaps:
        fa = bm.faces[a_idx]
        fb = bm.faces[b_idx]
        na = fa.normal.normalized()
        nb = fb.normal.normalized()
        coords_a = [tuple(round(c, 3) for c in v.co) for v in fa.verts]
        coords_b = [tuple(round(c, 3) for c in v.co) for v in fb.verts]
        print(f"  pair ({a_idx},{b_idx}): area={area:.2e} plane_key={pk}")
        print(f"    f{a_idx}: mat={fa.material_index} normal=({na.x:.4f},{na.y:.4f},{na.z:.4f}) verts={coords_a}")
        print(f"    f{b_idx}: mat={fb.material_index} normal=({nb.x:.4f},{nb.y:.4f},{nb.z:.4f}) verts={coords_b}")
    return overlaps


# ─── Load 1: via eval ────────────────────────────────────────────────────
bpy.context.view_layer.update()
dg1 = bpy.context.evaluated_depsgraph_get()
ev1 = obj.evaluated_get(dg1)
em1 = ev1.to_mesh()
bm1 = bmesh.new()
bm1.from_mesh(em1)
ev1.to_mesh_clear()

overlaps1 = find_overlaps_verbose(bm1, "eval (same as _pv_fix & validate)")
bm1.free()

# ─── Now simulate _pv_fix: group by plane key, look for to_del ────────────
print("\n[DBG] Simulating _pv_fix overlap detection:")
bpy.context.view_layer.update()
dg2 = bpy.context.evaluated_depsgraph_get()
ev2 = obj.evaluated_get(dg2)
em2 = ev2.to_mesh()
bm2 = bmesh.new()
bm2.from_mesh(em2)
ev2.to_mesh_clear()
bm2.faces.ensure_lookup_table()

groups2: dict = {}
for f in bm2.faces:
    if len(f.verts) == 3 and f.material_index == WALL_IDX:
        groups2.setdefault(_plane_key(f), []).append(f)

to_del_pv: set = set()
for _faces_pv in groups2.values():
    if len(_faces_pv) < 2:
        continue
    for _i, _fa in enumerate(_faces_pv):
        if _fa in to_del_pv:
            print(f"  SKIP: face {_fa.index} already in to_del")
            continue
        _va_set = set(_fa.verts)
        _tri_a = list(_project_tri(_fa))
        _area_a = abs(_tri_area_2d(_tri_a))
        if _area_a < AREA_TOL:
            to_del_pv.add(_fa)
            continue
        for _fb in _faces_pv[_i + 1:]:
            if _fb in to_del_pv:
                continue
            if len(_va_set.intersection(_fb.verts)) >= 2:
                continue
            _inter = _convex_clip(_tri_a, list(_project_tri(_fb)))
            if len(_inter) < 3:
                continue
            if abs(_tri_area_2d(_inter)) > AREA_TOL:
                _area_b = abs(_tri_area_2d(list(_project_tri(_fb))))
                print(f"  FOUND: faces {_fa.index} and {_fb.index}: area_a={_area_a:.2e} area_b={_area_b:.2e}")
                if _area_a <= _area_b:
                    to_del_pv.add(_fa)
                    print(f"    -> mark {_fa.index} (smaller)")
                    break
                else:
                    to_del_pv.add(_fb)
                    print(f"    -> mark {_fb.index} (smaller)")

print(f"[DBG] _pv_fix to_del_pv count: {len(to_del_pv)}")

# Safety check: check if they're horizontal or vertical
HORIZ_Z = 0.9
horiz_del = {f for f in to_del_pv if abs(f.normal.normalized().z) > HORIZ_Z}
vert_del = to_del_pv - horiz_del
print(f"  horizontal: {len(horiz_del)}, vertical: {len(vert_del)}")

# Run safety check on vert_del
from collections import defaultdict as dd
safe = set(vert_del)
for guard in range(len(vert_del) + 1):
    all_del = safe | horiz_del
    deg: dict = dd(int)
    eo: dict = {}
    for f in safe:
        for e in f.edges:
            rem = sum(1 for lf in e.link_faces if lf not in all_del)
            if rem == 1:
                deg[e.verts[0]] += 1
                deg[e.verts[1]] += 1
                eo[e] = f
    ov = [v for v, d in deg.items() if d == 1]
    if not ov:
        break
    culp = None
    for v in ov:
        for e, f in eo.items():
            if v in e.verts and f in safe:
                culp = f; break
        if culp:
            break
    if culp:
        print(f"  Safety check: removing face {culp.index} from safe_del")
        safe.discard(culp)
    else:
        break

all_delete = safe | horiz_del
print(f"[DBG] Final all_delete count: {len(all_delete)}")
for f in all_delete:
    n = f.normal.normalized()
    print(f"  would delete face {f.index}: normal=({n.x:.4f},{n.y:.4f},{n.z:.4f})")

bm2.free()
print("[DBG] done")
