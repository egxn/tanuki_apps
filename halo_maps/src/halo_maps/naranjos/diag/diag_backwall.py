"""Diagnose the back-to-back wall situation at faces 1496/6375 and 824/4452."""
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
from mathutils import Vector

for n in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()
from halo_maps.naranjos.level import assemble_naranjos_level
assemble_naranjos_level()

from halo_maps.naranjos.validate_bsp import _plane_key

obj = bpy.data.objects.get("bsp_world")
assert obj is not None

bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
ev = obj.evaluated_get(dg)
em = ev.to_mesh()
bm = bmesh.new()
bm.from_mesh(em)
ev.to_mesh_clear()
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

print(f"[BACKWALL] Total faces: {len(bm.faces)}, verts: {len(bm.verts)}")

# Analyze the two overlapping pairs
pairs = [(1496, 6375), (824, 4452)]

for (fa_idx, fb_idx) in pairs:
    fa = bm.faces[fa_idx]
    fb = bm.faces[fb_idx]
    print(f"\n[BACKWALL] Pair ({fa_idx}, {fb_idx}):")

    for label, f in [(f"f{fa_idx}", fa), (f"f{fb_idx}", fb)]:
        n = f.normal.normalized()
        coords = [tuple(round(c, 3) for c in v.co) for v in f.verts]
        pk = _plane_key(f)
        print(f"  {label}: mat={f.material_index} normal=({n.x:.3f},{n.y:.3f},{n.z:.3f}) pk={pk}")
        print(f"    verts: {coords}")

        # Edge info
        for e in f.edges:
            n_link = len(e.link_faces)
            vc1 = tuple(round(c, 3) for c in e.verts[0].co)
            vc2 = tuple(round(c, 3) for c in e.verts[1].co)
            status = "BOUNDARY" if n_link == 1 else ("NM" if n_link > 2 else "OK")
            print(f"    edge {vc1}→{vc2}: {n_link} faces [{status}]")
            if n_link > 2:
                for lf in e.link_faces:
                    lf_n = lf.normal.normalized()
                    print(f"      linked face {lf.index}: mat={lf.material_index} n=({lf_n.x:.2f},{lf_n.y:.2f},{lf_n.z:.2f})")

print("\n[BACKWALL] Checking what happens if we delete f1496:")
# Test: which edges of f1496 would become boundary?
fa = bm.faces[1496]
for e in fa.edges:
    n_link = len(e.link_faces)
    remaining = n_link - 1
    vc1 = tuple(round(c, 3) for c in e.verts[0].co)
    vc2 = tuple(round(c, 3) for c in e.verts[1].co)
    state = "BOUNDARY" if remaining == 1 else ("2-MANIFOLD" if remaining == 2 else f"{remaining}-faces")
    if remaining == 1:
        print(f"  Edge {vc1}→{vc2}: would become BOUNDARY (currently {n_link} faces)")

print("\n[BACKWALL] Checking what happens if we delete BOTH f1496 and f6375:")
pair_faces = {bm.faces[1496], bm.faces[6375]}
for f in pair_faces:
    for e in f.edges:
        remaining = sum(1 for lf in e.link_faces if lf not in pair_faces)
        vc1 = tuple(round(c, 3) for c in e.verts[0].co)
        vc2 = tuple(round(c, 3) for c in e.verts[1].co)
        if remaining == 1:
            print(f"  Edge {vc1}→{vc2}: would become BOUNDARY (from f{f.index})")
        elif remaining == 0:
            print(f"  Edge {vc1}→{vc2}: would disappear (both faces deleted)")

# Count NM edges near these faces
all_nm = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"\n[BACKWALL] Total NM edges: {len(all_nm)}")

# Look at NM edges at x≈-47.569
nm_at_x = [e for e in all_nm
            if abs(e.verts[0].co.x - (-47.569)) < 0.01
            and abs(e.verts[1].co.x - (-47.569)) < 0.01]
print(f"[BACKWALL] NM edges at x≈-47.569: {len(nm_at_x)}")
for e in nm_at_x[:5]:
    vc1 = tuple(round(c, 3) for c in e.verts[0].co)
    vc2 = tuple(round(c, 3) for c in e.verts[1].co)
    n_link = len(e.link_faces)
    print(f"  {vc1}→{vc2}: {n_link} faces")

bm.free()
print("[BACKWALL] done")
