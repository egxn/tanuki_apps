"""Analyse the 89 NM edges in bsp_merged in detail."""
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
from collections import Counter

for n in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

src = bpy.data.objects.get("bsp_merged")
depsgraph = bpy.context.evaluated_depsgraph_get()
ev = src.evaluated_get(depsgraph)
em = ev.to_mesh()
bm = bmesh.new()
bm.from_mesh(em)
mat = src.matrix_world
for v in bm.verts: v.co = mat @ v.co
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
ev.to_mesh_clear()

nm_edges = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"[DIAG] bsp_merged: {len(bm.verts)} verts, {len(bm.faces)} faces", flush=True)
print(f"[DIAG] NM edges: {len(nm_edges)}", flush=True)

P = 100000
def plane_key(face):
    n = face.normal.normalized()
    if (n.x, n.y, n.z) < (0., 0., 0.): n.negate()
    d = -n.dot(face.verts[0].co)
    return (round(n.x*P), round(n.y*P), round(n.z*P), round(d*P))

# Classify by orientation and coplanarity
horiz_nm = 0
vert_nm = 0
coplanar_nm = 0
non_coplanar_nm = 0
nkeys_counter = Counter()

for e in nm_edges:
    # Horizontal = both endpoints at same z
    dz = abs(e.verts[0].co.z - e.verts[1].co.z)
    if dz < 0.01:
        horiz_nm += 1
    else:
        vert_nm += 1
    keys = set(plane_key(f) for f in e.link_faces)
    if len(keys) == 1:
        coplanar_nm += 1
    else:
        non_coplanar_nm += 1
    nkeys_counter[len(keys)] += 1

print(f"[DIAG] Horizontal NM (same z): {horiz_nm}", flush=True)
print(f"[DIAG] Non-horizontal NM: {vert_nm}", flush=True)
print(f"[DIAG] Coplanar NM: {coplanar_nm}", flush=True)
print(f"[DIAG] Non-coplanar NM: {non_coplanar_nm}", flush=True)
print(f"[DIAG] NM by num plane keys: {dict(nkeys_counter)}", flush=True)

# By z-level of horizontal NM edges
z_counter = Counter()
for e in nm_edges:
    dz = abs(e.verts[0].co.z - e.verts[1].co.z)
    if dz < 0.01:
        z = round((e.verts[0].co.z + e.verts[1].co.z) / 2, 3)
        z_counter[z] += 1
print(f"[DIAG] Horizontal NM by z (top 15): {z_counter.most_common(15)}", flush=True)

# Sample non-coplanar NM edges (corner edges)
nc_edges = [e for e in nm_edges if len(set(plane_key(f) for f in e.link_faces)) > 1]
print(f"[DIAG] Sample non-coplanar NM edges:", flush=True)
for e in nc_edges[:8]:
    c1 = tuple(round(c,3) for c in e.verts[0].co)
    c2 = tuple(round(c,3) for c in e.verts[1].co)
    keys = [plane_key(f) for f in e.link_faces]
    print(f"  {c1}→{c2} nfaces={len(e.link_faces)} unique_planes={len(set(keys))}", flush=True)

# Sample coplanar NM edges
cp_edges = [e for e in nm_edges if len(set(plane_key(f) for f in e.link_faces)) == 1]
print(f"[DIAG] Sample coplanar NM edges:", flush=True)
for e in cp_edges[:8]:
    c1 = tuple(round(c,3) for c in e.verts[0].co)
    c2 = tuple(round(c,3) for c in e.verts[1].co)
    print(f"  {c1}→{c2} nfaces={len(e.link_faces)} coplanar=True", flush=True)

bm.free()
print("[DIAG] done", flush=True)
