"""Debug what wall groups _fix_overlapping_vertical_walls sees."""
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
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

# Get bsp_merged and re-read
# Instead, we instrument: patch the function to print debug info
import halo_maps.naranjos.generate_dsl as gen_mod

# We need to see what's in bsp_merged _before_ T-junction fixing.
# Let's reconstruct the state by re-running just the initial steps.
import importlib, bpy, bmesh

# Re-run generate to get the objects
objs = [o for o in bpy.data.objects if o.name.startswith("bsp_") or 
        any(tag in o.name for tag in ["building","floor","ceiling","wall","roof","stair","door","window"])]
# Actually just use bsp_merged and see the wall faces at y~=-7.392

obj = bpy.data.objects.get("bsp_merged")
bm2 = bmesh.new()
bm2.from_mesh(obj.data)
bm2.faces.ensure_lookup_table()
bm2.normal_update()

# Find all -Y faces near y=-7.392
target_y = -7.392
tol = 0.05
candidate_faces = []
for f in bm2.faces:
    n = f.normal.normalized()
    if abs(n.y) < 0.85:
        continue
    if n.y > 0:
        continue  # only -Y
    centroid_y = sum(v.co.y for v in f.verts) / len(f.verts)
    if abs(centroid_y - target_y) < tol:
        candidate_faces.append(f)

print(f"\n[WALL-DIAG] Found {len(candidate_faces)} -Y faces near y={target_y}")
for f in candidate_faces:
    verts = [tuple(round(c,4) for c in v.co) for v in f.verts]
    xs = [v[0] for v in verts]
    zs = [v[2] for v in verts]
    ys = [v[1] for v in verts]
    print(f"  f{f.index}: x=[{min(xs):.4f},{max(xs):.4f}] y=[{min(ys):.4f},{max(ys):.4f}] z=[{min(zs):.4f},{max(zs):.4f}] nverts={len(f.verts)}")

# Check for NM edges among these faces
nm_among = [e for f in candidate_faces for e in f.edges if len(e.link_faces) > 2]
print(f"[WALL-DIAG] NM edges among these faces: {len(set(id(e) for e in nm_among))}")

bm2.free()
print("\n[WALL-DIAG] done")
