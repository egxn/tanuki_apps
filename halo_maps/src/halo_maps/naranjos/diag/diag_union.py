"""Diagnose NM edges in bsp_merged and why vertical union groups fail."""
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

import bpy
import bmesh
from collections import defaultdict

for n in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

# Load bsp_merged into a fresh bmesh
src = bpy.data.objects.get("bsp_merged")
depsgraph = bpy.context.evaluated_depsgraph_get()
ev = src.evaluated_get(depsgraph)
em = ev.to_mesh()
bm = bmesh.new()
bm.from_mesh(em)
mat = src.matrix_world
for v in bm.verts:
    v.co = mat @ v.co
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()
ev.to_mesh_clear()

print(f"[DIAG] bsp_merged: {len(bm.verts)} verts, {len(bm.faces)} faces", flush=True)

nm_edges = [e for e in bm.edges if len(e.link_faces) > 2]
nm_boundary = [e for e in bm.edges if len(e.link_faces) < 2]
print(f"[DIAG] NM edges (>2 faces): {len(nm_edges)}", flush=True)
print(f"[DIAG] Boundary edges (<2 faces): {len(nm_boundary)}", flush=True)

# Check normals of NM faces — coplanar?
P = 100000
def plane_key(face):
    n = face.normal.normalized()
    if (n.x, n.y, n.z) < (0., 0., 0.):
        n.negate()
    d = -n.dot(face.verts[0].co)
    return (round(n.x*P), round(n.y*P), round(n.z*P), round(d*P))

coplanar_nm = 0
non_coplanar_nm = 0
for e in nm_edges[:100]:
    keys = set(plane_key(f) for f in e.link_faces)
    if len(keys) == 1:
        coplanar_nm += 1
    else:
        non_coplanar_nm += 1

print(f"[DIAG] First 100 NM edges: coplanar={coplanar_nm}, non-coplanar={non_coplanar_nm}", flush=True)

print("[DIAG] Sample NM edges:", flush=True)
for e in nm_edges[:10]:
    c1 = tuple(round(c, 3) for c in e.verts[0].co)
    c2 = tuple(round(c, 3) for c in e.verts[1].co)
    keys = [plane_key(f) for f in e.link_faces]
    unique_keys = set(keys)
    is_cp = len(unique_keys) == 1
    print(f"  edge {e.index}: {c1}→{c2}  nfaces={len(e.link_faces)}  coplanar={is_cp}  norms_keys={len(unique_keys)}", flush=True)

bm.free()
print("[DIAG] done", flush=True)
