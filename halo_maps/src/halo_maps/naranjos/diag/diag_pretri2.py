"""Pre-tri: show ALL faces (any normal) near y=-7.39 z<0.3, PLUS +Y faces."""
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

import halo_maps.naranjos.generate_dsl as gen
_orig_tri = bmesh.ops.triangulate
_called = [False]

def _spy(bm, **kw):
    if not _called[0]:
        _called[0] = True
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.normal_update()
        target_y = -7.39172
        tol = 0.02
        
        # All faces near y=-7.39172
        candidate = []
        for f in bm.faces:
            ys = [v.co.y for v in f.verts]
            zs = [v.co.z for v in f.verts]
            centroid_y = sum(ys)/len(ys)
            if abs(centroid_y - target_y) < tol and max(zs) < 0.5:
                candidate.append(f)
        
        nm_count = sum(1 for e in bm.edges if len(e.link_faces) > 2)
        print(f"\n[PRE-TRI2] NM edges: {nm_count}, faces total: {len(bm.faces)}")
        print(f"[PRE-TRI2] Faces near y={target_y}, z<0.5: {len(candidate)}")
        
        # Also: show all faces using any of the 4 target vertices
        # First identify vertices at the target positions
        target_verts = set()
        for v in bm.verts:
            if abs(v.co.y - target_y) < tol and v.co.z < 0.25 and 12 < v.co.x < 21:
                target_verts.add(v.index)
        
        target_vert_faces = []
        for f in bm.faces:
            if all(v.index in target_verts for v in f.verts):
                target_vert_faces.append(f)
        
        print(f"[PRE-TRI2] Target vertices: {sorted(target_verts)}")
        print(f"[PRE-TRI2] Faces using ONLY target verts: {len(target_vert_faces)}")
        
        for f in candidate:
            n = f.normal.normalized()
            nverts = len(f.verts)
            xs = [v.co.x for v in f.verts]
            zs = [v.co.z for v in f.verts]
            ys = [v.co.y for v in f.verts]
            nm_e = sum(1 for e in f.edges if len(e.link_faces) > 2)
            print(f"  f{f.index}: n=({n.x:.2f},{n.y:.2f},{n.z:.2f}) nverts={nverts} NM-edges={nm_e}")
            print(f"    x=[{min(xs):.4f},{max(xs):.4f}] z=[{min(zs):.4f},{max(zs):.4f}] y=[{min(ys):.5f},{max(ys):.5f}]")
            vt = [f"v{v.index}({v.co.x:.4f},{v.co.z:.4f})" for v in f.verts]
            print(f"    verts: {vt}")
    return _orig_tri(bm, **kw)

bmesh.ops.triangulate = _spy
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()
bmesh.ops.triangulate = _orig_tri
print("\n[PRE-TRI2] done")
