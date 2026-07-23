"""Verify the 2 remaining overlapping pairs are anti-parallel (back-to-back walls)."""
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
    _plane_key, _project_tri, _convex_clip, _tri_area_2d, AREA_TOL
)

obj = bpy.data.objects.get("bsp_world")
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = obj.evaluated_get(dg)
em = ev.to_mesh()
bm = bmesh.new()
bm.from_mesh(em)
ev.to_mesh_clear()
bm.faces.ensure_lookup_table()

WALL_IDX = 0
groups: dict = {}
for f in bm.faces:
    if len(f.verts) == 3 and f.material_index == WALL_IDX:
        groups.setdefault(_plane_key(f), []).append(f)

# All overlapping pairs
pairs = []
for pk, faces in groups.items():
    if len(faces) < 2:
        continue
    for i, a in enumerate(faces):
        va_set = set(a.verts)
        tri_a = list(_project_tri(a))
        for b in faces[i + 1:]:
            if len(va_set.intersection(b.verts)) >= 2:
                continue
            inter = _convex_clip(tri_a, list(_project_tri(b)))
            if len(inter) >= 3 and abs(_tri_area_2d(inter)) > AREA_TOL:
                na = a.normal.normalized()
                nb = b.normal.normalized()
                dot = na.dot(nb)
                area = abs(_tri_area_2d(inter))
                is_anti = dot < 0
                print(f"pair ({a.index},{b.index}): area={area:.4e} dot={dot:.3f} anti_parallel={is_anti}")
                print(f"  na=({na.x:.3f},{na.y:.3f},{na.z:.3f})")
                print(f"  nb=({nb.x:.3f},{nb.y:.3f},{nb.z:.3f})")
                pairs.append((a.index, b.index, dot, is_anti))

print(f"\nTotal pairs: {len(pairs)}")
anti = sum(1 for _,_,_,ai in pairs if ai)
same = len(pairs) - anti
print(f"Anti-parallel (back-to-back walls): {anti}")
print(f"Same-direction (real overlaps): {same}")
bm.free()
print("done")
