"""Diagnostic: non-manifold edge analysis in bsp_merged."""
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
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene; setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

src = bpy.data.objects.get("bsp_merged")
bpy.context.view_layer.update()
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

nm_edges = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"[DIAG] non-manifold edges in bsp_merged: {len(nm_edges)}", flush=True)

for e in nm_edges[:8]:
    co1 = tuple(round(c, 3) for c in e.verts[0].co)
    co2 = tuple(round(c, 3) for c in e.verts[1].co)
    nf = len(e.link_faces)
    print(f"[DIAG]  edge {e.index}: {co1}→{co2}  nfaces={nf}", flush=True)

z_counter: Counter = Counter()
for e in nm_edges:
    z = round((e.verts[0].co.z + e.verts[1].co.z) / 2, 2)
    z_counter[z] += 1
print(f"[DIAG] NM edges by avg z (top 10): {z_counter.most_common(10)}", flush=True)

# Are NM edges horizontal or vertical?
horiz = sum(1 for e in nm_edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 0.01)
print(f"[DIAG] horizontal NM edges (same z): {horiz}/{len(nm_edges)}", flush=True)

bm.free()
