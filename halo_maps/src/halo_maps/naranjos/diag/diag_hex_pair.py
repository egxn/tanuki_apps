"""Inspect the two hexagon faces at y=-7.39172 (f1737, f1757) before triangulation.
Show exact vertex positions, and test what _delete_duplicate_faces sees after recalc."""
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

        candidate = []
        for f in bm.faces:
            ys = [v.co.y for v in f.verts]
            zs = [v.co.z for v in f.verts]
            if abs(sum(ys)/len(ys) - target_y) < tol and max(zs) < 0.5:
                candidate.append(f)

        print(f"\n[HEX-PAIR] {len(candidate)} faces near y={target_y}")
        for f in candidate:
            n2 = f.normal.normalized()
            print(f"\n  f{f.index}: n=({n2.x:.3f},{n2.y:.3f},{n2.z:.3f}) verts={len(f.verts)}")
            # Show verts in winding order
            for v in f.verts:
                print(f"    v{v.index}: ({v.co.x:.6f}, {v.co.y:.6f}, {v.co.z:.6f})")
            # Sorted frozenset (what _delete_duplicate_faces uses)
            key = tuple(sorted(
                (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
                for v in f.verts
            ))
            print(f"  sorted-key: {key}")

        # Now simulate what _delete_duplicate_faces does
        print("\n[HEX-PAIR] Simulating _delete_duplicate_faces matching...")
        from collections import defaultdict
        face_map = defaultdict(list)
        for f in bm.faces:
            key = tuple(sorted(
                (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
                for v in f.verts
            ))
            face_map[key].append(f.index)
        duplicates = {k: v for k, v in face_map.items() if len(v) > 1}
        print(f"  Total duplicate groups: {len(duplicates)}")
        for k, fidxs in list(duplicates.items())[:5]:
            print(f"  faces {fidxs}: key={k}")

        # After recalc, do they become duplicates?
        print("\n[HEX-PAIR] After recalc_face_normals, re-check...")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.faces.ensure_lookup_table()
        face_map2 = defaultdict(list)
        for f in bm.faces:
            key = tuple(sorted(
                (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
                for v in f.verts
            ))
            face_map2[key].append(f.index)
        duplicates2 = {k: v for k, v in face_map2.items() if len(v) > 1}
        print(f"  Total duplicate groups after recalc: {len(duplicates2)}")
        for k, fidxs in list(duplicates2.items())[:5]:
            print(f"  faces {fidxs}: key={k}")

        # Check our target faces specifically
        for f in candidate:
            key2 = tuple(sorted(
                (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
                for v in f.verts
            ))
            hits = face_map2[key2]
            print(f"  f{f.index} key match count: {len(hits)} → {hits}")

    return _orig_tri(bm, **kw)

bmesh.ops.triangulate = _spy
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()
bmesh.ops.triangulate = _orig_tri
print("\n[HEX-PAIR] done")
