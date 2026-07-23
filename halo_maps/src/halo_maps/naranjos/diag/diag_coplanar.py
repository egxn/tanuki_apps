"""Count ALL coplanar overlaps in bsp_world and characterize them."""
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

for n in ("Cube","Light","Camera"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()
from halo_maps.naranjos.level import assemble_naranjos_level
assemble_naranjos_level()

src = bpy.data.objects.get("bsp_world")
bm = bmesh.new()
bm.from_mesh(src.data)
bm.faces.ensure_lookup_table()
bm.normal_update()

P = 100000
def plane_key(face):
    n = face.normal.normalized()
    if (n.x,n.y,n.z)<(0.,0.,0.): n.negate()
    d = -n.dot(face.verts[0].co)
    return (round(n.x*P),round(n.y*P),round(n.z*P),round(d*P))

# Group by plane
from collections import defaultdict
plane_groups = defaultdict(list)
for f in bm.faces:
    if f.material_index == 0:  # wall only
        plane_groups[plane_key(f)].append(f)

# Sutherland-Hodgman for overlap detection
def _poly_clip(poly, clip):
    def inside(p, a, b):
        return (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0]) >= 0
    def intersect(a, b, c, d):
        A1,B1,C1 = b[1]-a[1], a[0]-b[0], (b[1]-a[1])*a[0]+(a[0]-b[0])*a[1]
        A2,B2,C2 = d[1]-c[1], c[0]-d[0], (d[1]-c[1])*c[0]+(c[0]-d[0])*c[1]
        det = A1*B2 - A2*B1
        if abs(det) < 1e-12: return None
        return ((C1*B2-C2*B1)/det, (A1*C2-A2*C1)/det)
    output = list(poly)
    for i in range(len(clip)):
        if not output: break
        ip = output
        output = []
        a = clip[(i-1)%len(clip)]
        b = clip[i]
        for j in range(len(ip)):
            c = ip[(j-1)%len(ip)]
            d = ip[j]
            if inside(d,a,b):
                if not inside(c,a,b):
                    pt = intersect(a,b,c,d)
                    if pt: output.append(pt)
                output.append(d)
            elif inside(c,a,b):
                pt = intersect(a,b,c,d)
                if pt: output.append(pt)
    return output

def proj_2d(face):
    n = face.normal.normalized()
    ax = max(range(3), key=lambda i: abs(n[i]))
    pts = []
    for v in face.verts:
        c = v.co
        if ax==0: pts.append((c.y,c.z))
        elif ax==1: pts.append((c.x,c.z))
        else: pts.append((c.x,c.y))
    return pts

def poly_area(pts):
    if len(pts)<3: return 0
    a=0
    for i in range(len(pts)):
        ax,ay=pts[i]
        bx,by=pts[(i+1)%len(pts)]
        a+=ax*by-bx*ay
    return abs(a)*0.5

# Count overlaps
total_pairs = 0
total_overlaps = 0
face_overlap_count = Counter()
overlap_examples = []

for pk, faces in plane_groups.items():
    if len(faces) < 2:
        continue
    for i in range(len(faces)):
        for j in range(i+1, len(faces)):
            fi = faces[i]
            fj = faces[j]
            if not fi.is_valid or not fj.is_valid:
                continue
            pi = proj_2d(fi)
            pj = proj_2d(fj)
            total_pairs += 1
            clipped = _poly_clip(pi, pj)
            if not clipped:
                continue
            overlap_area = poly_area(clipped)
            if overlap_area > 1e-6:
                total_overlaps += 1
                face_overlap_count[fi.index] += 1
                face_overlap_count[fj.index] += 1
                if total_overlaps <= 5:
                    overlap_examples.append((fi.index, fj.index, overlap_area))

print(f"[COPLANAR] Total coplanar pairs checked: {total_pairs}", flush=True)
print(f"[COPLANAR] Overlapping pairs found: {total_overlaps}", flush=True)
print(f"[COPLANAR] Most-overlapping faces: {face_overlap_count.most_common(10)}", flush=True)
print(f"[COPLANAR] Sample overlap pairs (face_i, face_j, overlap_area):", flush=True)
for ex in overlap_examples:
    f_i = bm.faces[ex[0]] if ex[0] < len(bm.faces) else None
    f_j = bm.faces[ex[1]] if ex[1] < len(bm.faces) else None
    mat_i = f_i.material_index if f_i and f_i.is_valid else '?'
    mat_j = f_j.material_index if f_j and f_j.is_valid else '?'
    print(f"  faces {ex[0]}(mat={mat_i}) and {ex[1]}(mat={mat_j}): overlap={ex[2]:.4f}", flush=True)
    if f_i and f_i.is_valid:
        coords = [tuple(round(c,3) for c in v.co) for v in f_i.verts]
        print(f"    f{ex[0]} verts: {coords}", flush=True)

bm.free()
print("[COPLANAR] done", flush=True)
