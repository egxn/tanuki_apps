"""Trace NM edge count at each step of level.py's assemble_naranjos_level.

Run from project root:
  blender --background --factory-startup --python diag_level_steps.py
"""
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

for n in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

def nm_count(bm):
    return sum(1 for e in bm.edges if len(e.link_faces) > 2)

def boundary_count(bm):
    return sum(1 for e in bm.edges if len(e.link_faces) < 2)

# ── Replicate level.py logic step-by-step ────────────────────────────────
from halo_maps.naranjos.level import (
    _load_source_into_bm, _delete_duplicate_faces, _fill_boundary_with_portal,
    _add_sky_envelope, _fix_coplanar_overlaps,
    WALL_IDX, PORTAL_IDX, SKY_IDX,
    SKY_HEIGHT_BU, GROUND_MARGIN_BU,
)
from halo_maps.naranjos.generate_dsl import (
    _fix_t_junctions_targeted, _fix_t_junctions_nonmanifold,
    MERGE_DISTANCE_BU as _MERGE_DIST,
)

source = bpy.data.objects.get("bsp_merged")
bm = _load_source_into_bm(source)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
print(f"[STEP 1] After load: nm={nm_count(bm)}, boundary={boundary_count(bm)}, faces={len(bm.faces)}", flush=True)

# Step 2: assign WALL_IDX
for f in bm.faces:
    f.material_index = WALL_IDX
print(f"[STEP 2] After assign WALL_IDX: nm={nm_count(bm)}, boundary={boundary_count(bm)}", flush=True)

# Step 3: delete duplicates
n_dup = _delete_duplicate_faces(bm)
print(f"[STEP 3] After delete dupes ({n_dup}): nm={nm_count(bm)}, boundary={boundary_count(bm)}", flush=True)

# Step 4: fill boundary with portals
bm.edges.ensure_lookup_table()
n_portal = _fill_boundary_with_portal(bm)
bm.edges.ensure_lookup_table()
print(f"[STEP 4] After portal fill ({n_portal} portals): nm={nm_count(bm)}, boundary={boundary_count(bm)}", flush=True)

# Step 5: compute bbox (no mesh change)
xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
x_min,x_max = min(xs),max(xs); y_min,y_max = min(ys),max(ys); z_min,z_max = min(zs),max(zs)
gx0 = x_min-GROUND_MARGIN_BU; gx1 = x_max+GROUND_MARGIN_BU
gy0 = y_min-GROUND_MARGIN_BU; gy1 = y_max+GROUND_MARGIN_BU
sky_top = max(z_max+5.0, float(SKY_HEIGHT_BU)); sky_bot = z_min-1.0

# Step 7: add sky envelope
_add_sky_envelope(bm, gx0, gx1, gy0, gy1, sky_bot, sky_top)
bm.faces.ensure_lookup_table(); bm.edges.ensure_lookup_table()
print(f"[STEP 7] After sky envelope: nm={nm_count(bm)}, boundary={boundary_count(bm)}, faces={len(bm.faces)}", flush=True)

# Step 8: triangulate
bmesh.ops.triangulate(bm, faces=bm.faces)
bm.normal_update()
print(f"[STEP 8] After triangulate: nm={nm_count(bm)}, boundary={boundary_count(bm)}, faces={len(bm.faces)}", flush=True)

# Detailed: NM by material after triangulation
bm.edges.ensure_lookup_table()
from collections import Counter
mat_counter = Counter()
for e in bm.edges:
    if len(e.link_faces) > 2:
        mats = tuple(sorted(set(f.material_index for f in e.link_faces)))
        mat_counter[mats] += 1
print(f"[STEP 8] NM by mat combo: {dict(mat_counter)}", flush=True)

# NM edges that were all-wall before triangulation but now involve portals/sky
wall_nm = [e for e in bm.edges if len(e.link_faces) > 2 and all(f.material_index == WALL_IDX for f in e.link_faces)]
portal_nm = [e for e in bm.edges if len(e.link_faces) > 2 and any(f.material_index == PORTAL_IDX for f in e.link_faces)]
sky_nm = [e for e in bm.edges if len(e.link_faces) > 2 and any(f.material_index == SKY_IDX for f in e.link_faces)]
print(f"[STEP 8] NM: all-wall={len(wall_nm)}, involves-portal={len(portal_nm)}, involves-sky={len(sky_nm)}", flush=True)

# Sample portal NM edges
print("[STEP 8] Sample portal NM edges:", flush=True)
for e in portal_nm[:6]:
    c1 = tuple(round(c,3) for c in e.verts[0].co)
    c2 = tuple(round(c,3) for c in e.verts[1].co)
    mats = [f.material_index for f in e.link_faces]
    print(f"  edge: {c1}→{c2}  nfaces={len(e.link_faces)}  mats={mats}", flush=True)

# Step 8b: fix coplanar overlaps
n_overlap = _fix_coplanar_overlaps(bm, wall_mat_index=WALL_IDX)
print(f"[STEP 8b] After coplanar fix ({n_overlap} removed): nm={nm_count(bm)}, boundary={boundary_count(bm)}", flush=True)

# Step 8c: T-junction fix
total_tj = 0
for _p in range(5):
    bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table(); bm.faces.ensure_lookup_table()
    n1 = _fix_t_junctions_targeted(bm)
    if n1: bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=_MERGE_DIST)
    n2 = _fix_t_junctions_nonmanifold(bm)
    if n2: bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=_MERGE_DIST)
    total_tj += n1 + n2
    if not n1 and not n2: break

bm.faces.ensure_lookup_table()
ngons = [f for f in bm.faces if len(f.verts) > 3]
if ngons:
    bmesh.ops.triangulate(bm, faces=ngons)
print(f"[STEP 8c] After TJ fix ({total_tj} splits): nm={nm_count(bm)}, boundary={boundary_count(bm)}, faces={len(bm.faces)}", flush=True)

bm.free()
print("[DIAG] done", flush=True)
