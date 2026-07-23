"""Inject a hook right before triangulate to inspect the mesh."""
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

# Patch bmesh.ops.triangulate to spy on the mesh just before it's called
import halo_maps.naranjos.generate_dsl as gen
_orig_tri = bmesh.ops.triangulate

_tri_called = [False]

def _spy_triangulate(bm, **kwargs):
    if not _tri_called[0]:
        _tri_called[0] = True
        # Inspect mesh at y≈-7.39172, z<0.3
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.normal_update()
        target_y = -7.39172
        tol = 0.01
        candidate = []
        for f in bm.faces:
            n = f.normal.normalized()
            if abs(n.y) < 0.9:
                continue
            if n.y > 0:
                continue
            ys = [v.co.y for v in f.verts]
            zs = [v.co.z for v in f.verts]
            if abs(sum(ys)/len(ys) - target_y) < tol and max(zs) < 0.3:
                candidate.append(f)
        nm_before = sum(1 for e in bm.edges if len(e.link_faces) > 2)
        print(f"\n[PRE-TRI] NM edges: {nm_before}, total faces: {len(bm.faces)}")
        print(f"[PRE-TRI] -Y faces at y≈-7.39172, z<0.3: {len(candidate)}")
        for f in candidate:
            nverts = len(f.verts)
            xs = [v.co.x for v in f.verts]
            zs = [v.co.z for v in f.verts]
            ys = [v.co.y for v in f.verts]
            vt = [tuple(round(c,4) for c in v.co) for v in f.verts]
            # Which edges are NM?
            nm_e = [e for e in f.edges if len(e.link_faces) > 2]
            print(f"  f{f.index}: nverts={nverts} x=[{min(xs):.4f},{max(xs):.4f}] y=[{min(ys):.4f},{max(ys):.4f}] z=[{min(zs):.4f},{max(zs):.4f}] NM-edges={len(nm_e)} verts={vt}")
    return _orig_tri(bm, **kwargs)

bmesh.ops.triangulate = _spy_triangulate

from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()
bmesh.ops.triangulate = _orig_tri
print("\n[PRE-TRI] done")
