"""Debug _fix_overlapping_vertical_walls: show all plane groups."""
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
from collections import defaultdict
from mathutils import Vector

for n in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(n)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

from halo_maps.scene import setup_scene
setup_scene()

# Replicate the first few steps of _create_merged_bsp manually
# to get the mesh state right before _fix_overlapping_vertical_walls.
from halo_maps.naranjos import generate_dsl as gmod

# Get the objects that would be passed to _create_merged_bsp.
# We can call generate_naranjos_dsl and then inspect.
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

# Instead, let's just look at the PRE-fix state by examining the mesh
# at the point right after the initial remove_doubles+delete_dupes.

# Re-read bsp_merged (which has already had the full pipeline run)
# and trace what the _fix_overlapping_vertical_walls would see
# at the pre-T-junction stage.

# For that, we patch the function to print ALL groups:
import halo_maps.naranjos.generate_dsl as gen

_orig_fn = gen._fix_overlapping_vertical_walls

def _debug_fn(bm, normal_tol=0.85, plane_tol=5e-3):
    from collections import defaultdict
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    plane_groups = defaultdict(list)
    for face in bm.faces:
        n = face.normal.normalized()
        if abs(n.z) >= normal_tol:
            continue
        nx_abs, ny_abs = abs(n.x), abs(n.y)
        if nx_abs >= normal_tol:
            axis = "x"
            sign = 1 if n.x > 0 else -1
            pos = sum(v.co.y for v in face.verts) / len(face.verts)  # BUG? should be co.x
        elif ny_abs >= normal_tol:
            axis = "y"
            sign = 1 if n.y > 0 else -1
            pos = sum(v.co.y for v in face.verts) / len(face.verts)
        else:
            continue
        pos_key = round(pos / plane_tol)
        plane_groups[(axis, pos_key, sign)].append(face)
    
    print(f"\n[DBG] Total plane groups: {len(plane_groups)}")
    # Print groups near y=-7.39
    target_pos_key = round(-7.3917 / plane_tol)
    print(f"[DBG] Target pos_key for y=-7.3917 (plane_tol={plane_tol}): {target_pos_key}")
    for (axis, pos_key, sign), faces in plane_groups.items():
        if axis == 'y' and abs(pos_key - target_pos_key) <= 2:
            print(f"[DBG] Group (y, {pos_key}, {sign:+d}): {len(faces)} faces")
            for f in faces:
                pts = [(v.co.x, v.co.z) for v in f.verts]
                xs = [p[0] for p in pts]
                zs = [p[1] for p in pts]
                ys = [v.co.y for v in f.verts]
                print(f"  f{f.index}: x=[{min(xs):.5f},{max(xs):.5f}] y=[{min(ys):.5f},{max(ys):.5f}] z=[{min(zs):.5f},{max(zs):.5f}] nverts={len(f.verts)}")
    
    # Also print all groups with 2+ faces
    print(f"\n[DBG] Groups with 2+ faces ({sum(1 for _, faces in plane_groups.items() if len(faces) >= 2)} total):")
    for (axis, pos_key, sign), faces in plane_groups.items():
        if len(faces) < 2:
            continue
        # Get position info
        pos_val = pos_key * plane_tol
        _EPS = 1e-4
        def _to_2d(v):
            return (v.co.y, v.co.z) if axis == "x" else (v.co.x, v.co.z)
        boxes = []
        for face in faces:
            pts = [_to_2d(v) for v in face.verts]
            u_vals = [p[0] for p in pts]
            z_vals = [p[1] for p in pts]
            boxes.append((min(u_vals), max(u_vals), min(z_vals), max(z_vals)))
        has_overlap = any(
            a[0] < b[1]-_EPS and b[0] < a[1]-_EPS and a[2] < b[3]-_EPS and b[2] < a[3]-_EPS
            for i,a in enumerate(boxes) for j,b in enumerate(boxes) if i<j
        )
        if has_overlap:
            print(f"  OVERLAP (axis={axis}, pos≈{pos_val:.4f}, sign={sign:+d}): {len(faces)} faces")
        
    return _orig_fn(bm, normal_tol, plane_tol)

gen._fix_overlapping_vertical_walls = _debug_fn

# Re-run pipeline
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
from halo_maps.scene import setup_scene
setup_scene()
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

print("\n[DBG] done")
