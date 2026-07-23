"""Check polygon type distribution in bsp_merged."""
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

for n in ("Cube","Light","Camera"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

src = bpy.data.objects.get("bsp_merged")

# Check RAW mesh
bm = bmesh.new()
bm.from_mesh(src.data)
bm.faces.ensure_lookup_table()
tris = sum(1 for f in bm.faces if len(f.verts)==3)
quads = sum(1 for f in bm.faces if len(f.verts)==4)
ngons = sum(1 for f in bm.faces if len(f.verts)>4)
nm = sum(1 for e in bm.edges if len(e.link_faces)>2)
boundary = sum(1 for e in bm.edges if len(e.link_faces)<2)
print(f"[CHECK] RAW bsp_merged: tris={tris}, quads={quads}, ngons={ngons}, nm={nm}, boundary={boundary}", flush=True)
bm.free()

# Check EVALUATED mesh
depsgraph = bpy.context.evaluated_depsgraph_get()
ev = src.evaluated_get(depsgraph)
em = ev.to_mesh()
bm2 = bmesh.new()
bm2.from_mesh(em)
bm2.faces.ensure_lookup_table()
tris2 = sum(1 for f in bm2.faces if len(f.verts)==3)
quads2 = sum(1 for f in bm2.faces if len(f.verts)==4)
ngons2 = sum(1 for f in bm2.faces if len(f.verts)>4)
nm2 = sum(1 for e in bm2.edges if len(e.link_faces)>2)
print(f"[CHECK] EVAL bsp_merged: tris={tris2}, quads={quads2}, ngons={ngons2}, nm={nm2}", flush=True)

# Show some quads if they exist
if quads2 > 0:
    quad_faces = [f for f in bm2.faces if len(f.verts)==4][:5]
    for f in quad_faces:
        coords = [tuple(round(c,3) for c in v.co) for v in f.verts]
        nm_check = sum(1 for e in f.edges if len(e.link_faces)>2)
        print(f"  quad face {f.index}: nm_edges={nm_check} verts={coords}", flush=True)

bm2.free()
ev.to_mesh_clear()
print("[CHECK] done", flush=True)
