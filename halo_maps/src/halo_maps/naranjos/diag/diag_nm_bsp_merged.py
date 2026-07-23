"""Count NM edges in bsp_merged (pre-assembly)."""
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

obj = bpy.data.objects.get("bsp_merged")
bm = bmesh.new()
bm.from_mesh(obj.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

nm_edges = [e for e in bm.edges if len(e.link_faces) > 2]
boundary_edges = [e for e in bm.edges if len(e.link_faces) < 2]

print(f"[NM-DSL] bsp_merged: verts={len(bm.verts)}, faces={len(bm.faces)}, tris={sum(1 for f in bm.faces if len(f.verts)==3)}")
print(f"[NM-DSL] NM edges (3+): {len(nm_edges)}")
print(f"[NM-DSL] Boundary edges: {len(boundary_edges)}")

# Characterize NM edges
anti_parallel = 0
same_dir = 0
for e in nm_edges:
    faces = list(e.link_faces)
    has_pos = any((f.normal.normalized().x, f.normal.normalized().y, f.normal.normalized().z) >= (0,0,0) for f in faces)
    has_neg = any((f.normal.normalized().x, f.normal.normalized().y, f.normal.normalized().z) < (0,0,0) for f in faces)
    if has_pos and has_neg:
        anti_parallel += 1
    else:
        same_dir += 1

print(f"[NM-DSL] Anti-parallel NM (back-to-back walls): {anti_parallel}")
print(f"[NM-DSL] Same-direction NM: {same_dir}")

# Sample some anti-parallel NM edges
from halo_maps.naranjos.validate_bsp import _plane_key as vbsp_pk
anti_edges = [e for e in nm_edges
              if any((f.normal.normalized().x, f.normal.normalized().y, f.normal.normalized().z) >= (0,0,0) for f in e.link_faces)
              and any((f.normal.normalized().x, f.normal.normalized().y, f.normal.normalized().z) < (0,0,0) for f in e.link_faces)][:3]

print(f"\n[NM-DSL] Sample anti-parallel NM edges in bsp_merged:")
for e in anti_edges:
    vc1 = tuple(round(c, 3) for c in e.verts[0].co)
    vc2 = tuple(round(c, 3) for c in e.verts[1].co)
    print(f"  edge {vc1}→{vc2}: {len(e.link_faces)} faces")
    for f in e.link_faces:
        n = f.normal.normalized()
        verts = [tuple(round(c, 3) for c in v.co) for v in f.verts]
        print(f"    f{f.index}: n=({n.x:.2f},{n.y:.2f},{n.z:.2f}) verts={verts}")

bm.free()
print("[NM-DSL] done")
