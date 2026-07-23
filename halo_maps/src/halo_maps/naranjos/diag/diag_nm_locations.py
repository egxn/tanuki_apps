"""Show exact positions and face normals of first 20 NM edges in bsp_merged."""
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
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()
bm.normal_update()

nm_edges = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"\n[LOC] Total NM edges: {len(nm_edges)}, boundary: {sum(1 for e in bm.edges if len(e.link_faces)<2)}")

# Classify NM edges by type
anti = []
same_dir = []
for e in nm_edges:
    normals = [f.normal.normalized() for f in e.link_faces]
    # Use dot product to detect anti-parallel
    has_anti = any(
        n1.dot(n2) < -0.5
        for i, n1 in enumerate(normals)
        for n2 in normals[i+1:]
    )
    if has_anti:
        anti.append(e)
    else:
        same_dir.append(e)

print(f"[LOC] Anti-parallel: {len(anti)}, same-direction: {len(same_dir)}")

# Show first 10 anti-parallel
print("\n[LOC] === ANTI-PARALLEL NM EDGES (first 10) ===")
for e in anti[:10]:
    v0 = tuple(round(c, 4) for c in e.verts[0].co)
    v1 = tuple(round(c, 4) for c in e.verts[1].co)
    print(f"  edge {v0}→{v1} ({len(e.link_faces)} faces):")
    for f in e.link_faces:
        n = f.normal.normalized()
        print(f"    n=({n.x:.2f},{n.y:.2f},{n.z:.2f}) verts={len(f.verts)}")

# Show first 10 same-direction
print("\n[LOC] === SAME-DIRECTION NM EDGES (first 10) ===")
for e in same_dir[:10]:
    v0 = tuple(round(c, 4) for c in e.verts[0].co)
    v1 = tuple(round(c, 4) for c in e.verts[1].co)
    print(f"  edge {v0}→{v1} ({len(e.link_faces)} faces):")
    for f in e.link_faces:
        n = f.normal.normalized()
        verts = [tuple(round(c, 4) for c in v.co) for v in f.verts]
        print(f"    n=({n.x:.2f},{n.y:.2f},{n.z:.2f}) {verts}")

bm.free()
print("[LOC] done")
