"""High-precision inspection of the 4 triangles at y≈-7.3917."""
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
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

obj = bpy.data.objects.get("bsp_merged")
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.faces.ensure_lookup_table()
bm.normal_update()

# Find faces near y=-7.39 with -Y normal and z=[0,0.22]
target_y = -7.39
tol_y = 0.1
candidate_faces = []
for f in bm.faces:
    n = f.normal.normalized()
    if abs(n.y) < 0.9:
        continue
    ys = [v.co.y for v in f.verts]
    zs = [v.co.z for v in f.verts]
    xs = [v.co.x for v in f.verts]
    if abs(sum(ys)/len(ys) - target_y) < tol_y and max(zs) < 0.3:
        candidate_faces.append(f)

print(f"[PRECISE] Found {len(candidate_faces)} candidate faces")
for f in candidate_faces:
    n = f.normal.normalized()
    print(f"\n  f{f.index} n=({n.x:.4f},{n.y:.4f},{n.z:.4f}):")
    for v in f.verts:
        print(f"    v{v.index}: ({v.co.x:.8f}, {v.co.y:.8f}, {v.co.z:.8f})")
    # Show which edges are NM
    for e in f.edges:
        nf = len(e.link_faces)
        if nf > 2:
            v0 = tuple(round(c,5) for c in e.verts[0].co)
            v1 = tuple(round(c,5) for c in e.verts[1].co)
            print(f"    NM edge: {v0}->{v1} ({nf} faces)")

# Also count NM edges at different stages
nm_all = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"\n[PRECISE] Total NM edges: {len(nm_all)}")

bm.free()
print("\n[PRECISE] done")
