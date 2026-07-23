"""Show actual coordinates and normals for the first 10 NM edges in bsp_merged."""
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

nm_edges = [e for e in bm.edges if len(e.link_faces) > 2]
print(f"\n[DETAIL] Total NM edges: {len(nm_edges)}")

def dominant(n):
    vals = [('x', abs(n.x)), ('y', abs(n.y)), ('z', abs(n.z))]
    ax = max(vals, key=lambda t: t[1])[0]
    comp = n.x if ax=='x' else (n.y if ax=='y' else n.z)
    return (ax, '+' if comp > 0 else '-')

same_dir_shown = 0
anti_shown = 0
for e in nm_edges:
    v0 = e.verts[0].co
    v1 = e.verts[1].co
    faces = list(e.link_faces)
    normals = [f.normal.normalized() for f in faces]
    dom_axes = [dominant(n) for n in normals]
    unique_dirs = set(dom_axes)
    is_anti = len(unique_dirs) > 1

    if is_anti and anti_shown < 5:
        anti_shown += 1
        vc0 = tuple(round(c,3) for c in v0)
        vc1 = tuple(round(c,3) for c in v1)
        print(f"\n[ANTI] edge {vc0}->{vc1}: {len(faces)} faces")
        for i, (f, n) in enumerate(zip(faces, normals)):
            verts = [tuple(round(c,3) for c in v.co) for v in f.verts]
            print(f"  f{f.index} n=({n.x:.2f},{n.y:.2f},{n.z:.2f}) dom={dom_axes[i]} verts={verts}")
    elif not is_anti and same_dir_shown < 5:
        same_dir_shown += 1
        vc0 = tuple(round(c,3) for c in v0)
        vc1 = tuple(round(c,3) for c in v1)
        print(f"\n[SAME] edge {vc0}->{vc1}: {len(faces)} faces")
        for i, (f, n) in enumerate(zip(faces, normals)):
            verts = [tuple(round(c,3) for c in v.co) for v in f.verts]
            print(f"  f{f.index} n=({n.x:.2f},{n.y:.2f},{n.z:.2f}) dom={dom_axes[i]} verts={verts}")

    if anti_shown >= 5 and same_dir_shown >= 5:
        break

from collections import Counter
axis_counts = Counter()
for e in nm_edges:
    for f in e.link_faces:
        n = f.normal.normalized()
        ax = max([('x', abs(n.x)), ('y', abs(n.y)), ('z', abs(n.z))], key=lambda t: t[1])
        sign = '+' if (n.x if ax[0]=='x' else (n.y if ax[0]=='y' else n.z)) > 0 else '-'
        axis_counts[f"{ax[0]}{sign}"] += 1
print(f"\n[DETAIL] NM edge face normal axes: {dict(axis_counts)}")

bm.free()
print("\n[DETAIL] done")
