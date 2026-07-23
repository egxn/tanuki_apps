"""Diagnostic: analyse coplanar-overlap area distribution in bsp_world."""
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

import bpy, bmesh, collections

for n in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

from halo_maps.naranjos.level import (
    _load_source_into_bm, _delete_duplicate_faces, _fill_boundary_with_portal,
    _add_sky_envelope, WALL_IDX, PORTAL_IDX, SKY_IDX, GROUND_MARGIN_BU, SKY_HEIGHT_BU,
)
src = bpy.data.objects["bsp_merged"]
bm = _load_source_into_bm(src)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()
for f in bm.faces:
    f.material_index = WALL_IDX
_delete_duplicate_faces(bm)
_fill_boundary_with_portal(bm)

xs = [v.co.x for v in bm.verts]
ys = [v.co.y for v in bm.verts]
zs = [v.co.z for v in bm.verts]
gx0, gx1 = min(xs) - GROUND_MARGIN_BU, max(xs) + GROUND_MARGIN_BU
gy0, gy1 = min(ys) - GROUND_MARGIN_BU, max(ys) + GROUND_MARGIN_BU
sky_top = max(max(zs) + 5.0, float(SKY_HEIGHT_BU))
sky_bot = min(zs) - 1.0
_add_sky_envelope(bm, gx0, gx1, gy0, gy1, sky_bot, sky_top)

bm.faces.ensure_lookup_table()
bmesh.ops.triangulate(bm, faces=bm.faces)
bm.normal_update()

PRECISION = 5
AREA_TOL = 1e-8


def _tri_area_2d(pts):
    area = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        area += x0 * y1 - x1 * y0
    return area * 0.5


def _inside(p, a, b, ccw):
    c = (b[0]-a[0])*(p[1]-a[1]) - (b[1]-a[1])*(p[0]-a[0])
    return c >= -1e-9 if ccw else c <= 1e-9


def _isect(p1, p2, p3, p4):
    x1,y1=p1; x2,y2=p2; x3,y3=p3; x4,y4=p4
    d = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(d) < 1e-12:
        return p2
    px = ((x1*y2-y1*x2)*(x3-x4) - (x1-x2)*(x3*y4-y3*x4)) / d
    py = ((x1*y2-y1*x2)*(y3-y4) - (y1-y2)*(x3*y4-y3*x4)) / d
    return px, py


def _clip(subj, clip_poly):
    out = subj
    ccw = _tri_area_2d(clip_poly) >= 0
    for i, a in enumerate(clip_poly):
        b = clip_poly[(i + 1) % len(clip_poly)]
        inp = out; out = []
        if not inp:
            break
        prev = inp[-1]
        for cur in inp:
            ci = _inside(cur, a, b, ccw)
            pi = _inside(prev, a, b, ccw)
            if ci:
                if not pi:
                    out.append(_isect(prev, cur, a, b))
                out.append(cur)
            elif pi:
                out.append(_isect(prev, cur, a, b))
            prev = cur
    return out


def _project(face):
    n = face.normal.normalized()
    axis = max(range(3), key=lambda i: abs(n[i]))
    pts = []
    for v in face.verts:
        c = v.co
        if axis == 0:    pts.append((c.y, c.z))
        elif axis == 1:  pts.append((c.x, c.z))
        else:            pts.append((c.x, c.y))
    return pts


def _plane_key(face):
    n = face.normal.normalized()
    if (n.x, n.y, n.z) < (0.0, 0.0, 0.0):
        n.negate()
    d = -n.dot(face.verts[0].co)
    p = 10 ** PRECISION
    return (round(n.x*p), round(n.y*p), round(n.z*p), round(d*p))


bm.faces.ensure_lookup_table()
groups = {}
for face in bm.faces:
    if len(face.verts) != 3:
        continue
    if face.material_index != WALL_IDX:
        continue
    groups.setdefault(_plane_key(face), []).append(face)

print(f"[DIAG] wall-face plane groups with 2+ triangles: "
      f"{sum(1 for g in groups.values() if len(g)>=2)}", flush=True)
grp_sizes = sorted((len(g) for g in groups.values() if len(g)>=2), reverse=True)
print(f"[DIAG] top group sizes: {grp_sizes[:10]}", flush=True)

area_buckets: dict = collections.Counter()
sample_pairs = []
total_found = 0

for faces in groups.values():
    if len(faces) < 2:
        continue
    for i, a in enumerate(faces):
        proj_a = _project(a)
        for b in faces[i + 1:]:
            if len(set(a.verts).intersection(b.verts)) >= 2:
                continue
            inter = _clip(proj_a, _project(b))
            if len(inter) >= 3:
                ar = abs(_tri_area_2d(inter))
                if ar > AREA_TOL:
                    total_found += 1
                    if   ar < 1e-6:  area_buckets['<1e-6'] += 1
                    elif ar < 1e-4:  area_buckets['<1e-4'] += 1
                    elif ar < 1e-2:  area_buckets['<1e-2'] += 1
                    elif ar < 0.1:   area_buckets['<0.1']  += 1
                    elif ar < 1.0:   area_buckets['<1.0']  += 1
                    else:            area_buckets['>=1.0'] += 1
                    if len(sample_pairs) < 8:
                        sample_pairs.append(
                            (ar, a.index, b.index,
                             [tuple(round(c, 3) for c in v.co) for v in a.verts],
                             [tuple(round(c, 3) for c in v.co) for v in b.verts])
                        )

print(f"[DIAG] total overlapping pairs (area>{AREA_TOL}): {total_found}", flush=True)
print(f"[DIAG] area distribution: {dict(area_buckets)}", flush=True)
for ar, ai, bi, va, vb in sample_pairs:
    print(f"[DIAG]   pair area={ar:.6f}  f{ai}={va}  f{bi}={vb}", flush=True)
