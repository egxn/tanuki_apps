"""Naranjos map — DSL-based parametric building, hall, roof, and border generator.

Uses the Tanuki Geometry Nodes DSL to create **parametric** node trees
for each building, hall, roof, and border. The resulting GN modifiers stay
live (not baked) so that floor count, height, wall thickness, etc. can be
adjusted directly in Blender.

Run inside Blender::

    import importlib, halo_maps.naranjos.generate_dsl as gd
    importlib.reload(gd); gd.generate_naranjos_dsl()

Or from CLI::

    blender --background --python src/halo_maps/naranjos/generate_dsl.py
"""

from __future__ import annotations

import json
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

# Ensure tanuki is importable when running standalone inside Blender
_SRC_ROOT = Path(__file__).resolve().parent
for candidate in (_SRC_ROOT, *_SRC_ROOT.parents):
    if (candidate / "src" / "halo_maps").exists():
        _SRC_ROOT = str(candidate / "src")
        break
else:
    _SRC_ROOT = str(_SRC_ROOT)
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

from ..bootstrap import enable_venv

enable_venv()

import bpy
import bmesh
import numpy as np
from mathutils import Vector

# Tanuki DSL imports
from tanuki.dsl import (
    model,
    output,
    object_info,
    curve_to_mesh,
    fill_curve,
    translate,
    join,
    clones,
    realize_instances,
    set_spline_cyclic,
    extrude,
)
from tanuki.dsl.operations import difference  # used by other boolean ops if needed
from tanuki.dsl.curves import curve_line, curve_quadrilateral
from tanuki.backends.blender.compiler import compile_to_source

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DIR = Path(__file__).resolve().parent
_CONFIG_DIR = _DIR / "config"   # JSON building/door/window/etc. definitions
_SVG_DIR    = _DIR / "svg"      # map.svg source curves
_BLEND_DIR  = _DIR / "blend"    # generated .blend files

M_PER_BU = 0.55
WALL_THICKNESS_BU = 0.22
SLAB_THICKNESS_BU = 0.05
LEVEL_FLOOR_THICKNESS_BU = 0.20
LEVEL_FLOOR_TOP_Z_BU = -SLAB_THICKNESS_BU
DEFAULT_INTER_FLOOR_HEIGHT_M = 2.28
MERGE_DISTANCE_BU = 0.001
_TJUNCTION_TOL = 1e-5  # BU — vertex-on-edge distance threshold
T_JUNCTION_FIX_MAX_SPLITS = 0  # disabled: bisect-plane pass handles axis-aligned T-junctions

# Brick/course geometry — ground truth for wall height.
# The building metadata stores the number of 6 cm brick courses:
#   height = bricks_h × 0.06 m
# Example: 38 courses → 38×0.06 = 2.28 m/floor
BRICK_COURSE_H_M = 0.06

# Door opening physical dimensions
DEFAULT_DOOR_HEIGHT_M = 2.0    # door opening height (metres)
DOOR_MARGIN_BU = 0.02         # extra clearance above/below each slab surface

# SVG → BU scale factor.
#
# Blender's SVG importer already applies the SVG document width/viewBox scale,
# so imported curve coordinates are small Blender units, not raw SVG path units.
# Calibration after applying all importer transforms:
#   "limites" long side = 17.094186783 imported BU
#   expected real long side = 112 m = 203.636363636 BU
#   SVG_TO_BU = 203.636363636 / 17.094186783 = 11.912609019
#
# This keeps XY campus scale and Z building heights in the same unit system:
# 38 brick courses = 2.28 m = 4.1455 BU, while the border long side = 203.64 BU.
BORDER_LONG_SIDE_M = 112.0
SVG_TO_BU = 11.912609019

CURVE_RESOLUTION = 12


def m_to_bu(metres: float) -> float:
    return metres / M_PER_BU


def bu_to_m(blam_units: float) -> float:
    return blam_units * M_PER_BU


def floor_height_from_bricks(bricks_h: int) -> float:
    """Return the height of one floor in metres from its brick count.

    The Naranjos data uses one brick course as 6 cm in the SVG/model scale:

        height = N × 0.06

    Examples
    --------
    >>> floor_height_from_bricks(38)   # standard rooms
    2.28
    >>> floor_height_from_bricks(44)   # ludoteca
    2.64
    """
    return bricks_h * BRICK_COURSE_H_M


# ---------------------------------------------------------------------------
# SVG label → id mapping
# ---------------------------------------------------------------------------

_INK_NS = "http://www.inkscape.org/namespaces/inkscape"


def _parse_svg_label_map(svg_path: str | Path) -> dict[str, str]:
    tree = ET.parse(svg_path)
    label_to_id: dict[str, str] = {}
    for elem in tree.iter():
        label = elem.get(f"{{{_INK_NS}}}label")
        svg_id = elem.get("id")
        if label and svg_id:
            label_to_id[label.lower()] = svg_id
    return label_to_id


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_buildings() -> list[dict]:
    with open(_CONFIG_DIR / "buildings.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for b in data:
        if "floors" in b and "floor" not in b:
            b["floor"] = b["floors"]
        b.setdefault("floor", 1)
    return data


def _load_borders() -> dict:
    with open(_CONFIG_DIR / "borders.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _load_roofs_halls() -> list[dict]:
    with open(_CONFIG_DIR / "roofs_halls.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _load_stairs() -> dict:
    with open(_CONFIG_DIR / "stairs.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _load_objects() -> dict:
    with open(_CONFIG_DIR / "objects.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _load_doors() -> dict[str, list[dict]]:
    """Load door data from doors.json.

    Returns a mapping of *edificio* name → list of door dicts, each with::

        {
            "label": "edificio_puerta_N_piso_M",
            "num_puerta": N,
            "piso": M,
            "svg": {"x": ..., "y": ..., "width": ..., "height": ...}
        }
    """
    doors_path = _CONFIG_DIR / "doors.json"
    if not doors_path.exists():
        return {}
    with open(doors_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_windows() -> dict[str, list[dict]]:
    """Load window data from windows.json.

    Returns a mapping of *edificio* name → list of window dicts, each with::

        {
            "label": "edificio_ventana_N_piso_M",
            "num_ventana": N,
            "piso": M,
            "z_bottom_m": 0.9,   # sill height above floor in metres
            "height_m":   1.0,   # window opening height in metres
            "svg": {"x": ..., "y": ..., "width": ..., "height": ...}
        }
    """
    windows_path = _CONFIG_DIR / "windows.json"
    if not windows_path.exists():
        return {}
    with open(windows_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Strip comment / example keys that are not building entries
    return {k: v for k, v in data.items() if k not in ("_comment", "_example")}


def _parse_stair_level(shape_name: str) -> float:
    """Derive the fractional level from a stair shape name.

    Naming convention:  esc_{id}_{part}
      - ``esc_1_1``            → level 1.0  (piso 1)
      - ``esc_1_2``            → level 2.0  (piso 2)
      - ``esc_1_intermedio``   → level 1.5  (intermedio entre piso 1 y 2)
      - ``esc_3_intermedio_1`` → level 1.5  (intermedio N=1)
      - ``esc_3_intermedio_2`` → level 2.5  (intermedio N=2)

    The rule for intermedios:
        level = N + 0.5   where N is the lower floor index (defaults to 1).
    """
    parts = shape_name.split("_")
    # Expected: ['esc', '<id>', '<floor_or_intermedio>', ...]
    if len(parts) < 3 or parts[0] != "esc":
        raise ValueError(f"Cannot parse stair shape name: '{shape_name}'")

    floor_part = parts[2]

    if floor_part.lstrip("-").isdigit():
        return float(floor_part)

    if floor_part == "intermedio":
        # Optional trailing index: esc_3_intermedio_2 → N=2, else N=1
        n = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
        return float(n) + 0.5

    raise ValueError(f"Unknown floor type '{floor_part}' in: '{shape_name}'")


def _stair_z_start_bu(level: float, floor_pitch_bu: float) -> float:
    """Z position in BU for a stair segment at the given level.

    level=1.0 → z=0, level=2.0 → z=floor_pitch_bu, level=1.5 → z=0.5*floor_pitch_bu.
    """
    return (level - 1.0) * floor_pitch_bu


def _stair_height_bu(
    level: float,
    next_level: float | None,
    floor_pitch_bu: float,
    slab_thickness_bu: float,
) -> float:
    """Height of one stair segment.

    If there is a next segment, the height fills the gap to it.
    The final segment (no next level) uses the slab thickness.
    """
    if next_level is not None:
        return (next_level - level) * floor_pitch_bu
    return slab_thickness_bu


def _building_floor_count(building: dict) -> int:
    return int(building.get("floor", building.get("floors", 1)))


def _infer_brick_height_m(buildings_data: list[dict]) -> float | None:
    samples: list[float] = []
    for building in buildings_data:
        floor_height = building.get("floor_height")
        bricks_h = building.get("meta", {}).get("bricks_h")
        if floor_height and bricks_h:
            samples.append(float(floor_height) / float(bricks_h))
    if not samples:
        return None
    samples.sort()
    return samples[len(samples) // 2]


def _building_pitch_m(building: dict, brick_height_m: float | None) -> float | None:
    bricks_h = building.get("meta", {}).get("bricks_h")
    if bricks_h:
        return floor_height_from_bricks(int(bricks_h))
    if "floor_height" in building:
        return float(building["floor_height"])
    return None


def _required_building_floors(entry: dict) -> int:
    floor_base = max(int(entry.get("floor_base", 1)), 1)
    if entry.get("kind") == "hall":
        return floor_base
    return max(floor_base - 1, 1)


def _evaluated_object_height_bu(obj: bpy.types.Object) -> float | None:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    try:
        zs = [vert.co.z for vert in eval_mesh.vertices]
        if not zs:
            return None
        return max(zs) - min(zs)
    finally:
        eval_obj.to_mesh_clear()


def _generated_storey_pitch_bu(
    entry: dict,
    buildings_data: list[dict],
    building_objects: dict[str, bpy.types.Object] | None,
) -> float | None:
    if not building_objects:
        return None

    required_floors = _required_building_floors(entry)
    candidates: list[float] = []
    for building in buildings_data:
        floors = _building_floor_count(building)
        if floors < required_floors:
            continue
        obj = building_objects.get(building["name"])
        if obj is None:
            continue
        height_bu = _evaluated_object_height_bu(obj)
        if height_bu is not None:
            candidates.append(round(height_bu / floors, 4))

    if not candidates:
        return None

    return Counter(candidates).most_common(1)[0][0]


def _storey_pitch_m(entry: dict, buildings_data: list[dict]) -> float:
    if "pitch_m" in entry:
        return float(entry["pitch_m"])

    brick_height_m = _infer_brick_height_m(buildings_data)
    required_floors = _required_building_floors(entry)
    candidates: list[float] = []
    for building in buildings_data:
        if _building_floor_count(building) < required_floors:
            continue
        pitch_m = _building_pitch_m(building, brick_height_m)
        if pitch_m is not None:
            candidates.append(round(pitch_m, 4))

    if not candidates:
        return DEFAULT_INTER_FLOOR_HEIGHT_M

    return Counter(candidates).most_common(1)[0][0]


def _inter_floor_height_m(entry: dict, buildings_data: list[dict]) -> float:
    return bu_to_m(_entry_height_bu(entry, buildings_data))


def _entry_height_bu(
    entry: dict,
    buildings_data: list[dict],
    building_objects: dict[str, bpy.types.Object] | None = None,
) -> float:
    if "height_bu" in entry:
        return float(entry["height_bu"])
    if "height" in entry:
        return m_to_bu(float(entry["height"]))
    pitch_bu = _generated_storey_pitch_bu(entry, buildings_data, building_objects)
    if pitch_bu is None:
        pitch_bu = m_to_bu(_storey_pitch_m(entry, buildings_data))
    return max(pitch_bu - (2 * SLAB_THICKNESS_BU), 0.0)


def _base_z_offset_bu(entry: dict, level_height_bu: float) -> float:
    """Return the Z start for an inter-floor volume.

    ``floor_base`` indexes the upper floor bound of the span:
      - floor_base=2 → volume spans between floors 1 and 2
      - floor_base=3 → volume spans between floors 2 and 3
    """
    floor_base = max(int(entry.get("floor_base", 1)) - 1, 0)
    return floor_base * level_height_bu


def _entry_z_start_bu(
    entry: dict,
    level_height_bu: float,
    buildings_data: list[dict],
    building_objects: dict[str, bpy.types.Object] | None = None,
) -> float:
    if "z_start_bu" in entry:
        return float(entry["z_start_bu"])
    pitch_bu = _generated_storey_pitch_bu(entry, buildings_data, building_objects)
    if pitch_bu is None:
        pitch_bu = m_to_bu(_storey_pitch_m(entry, buildings_data))
    return _base_z_offset_bu(entry, pitch_bu) + SLAB_THICKNESS_BU


# ---------------------------------------------------------------------------
# SVG import
# ---------------------------------------------------------------------------

def _import_svg() -> tuple[list[bpy.types.Object], dict[str, str]]:
    svg_path = _SVG_DIR / "map.svg"
    label_map = _parse_svg_label_map(svg_path)

    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=str(svg_path))
    after = set(bpy.data.objects)
    new_objs = list(after - before)

    if not new_objs:
        return new_objs, label_map

    for obj in new_objs:
        if obj.type == "CURVE":
            obj.data.resolution_u = CURVE_RESOLUTION

    # ── Step 1: bake whatever transforms the SVG importer stored ────────
    # Blender's SVG importer may store SVG path transform="matrix(...)"
    # as the Blender object's rotation / scale rather than baking it into
    # the curve data.  If we later overwrite obj.scale = SVG_TO_BU without
    # first baking the importer-set transforms, the matrix scale factor
    # (×1167 for the 6 rotated school buildings) is silently discarded,
    # leaving footprints that are ~0.035 BU instead of ~44 BU wide.
    # Applying ALL transforms here (location + rotation + scale) is safe:
    # it is a no-op for objects that have identity transforms.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in new_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = new_objs[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.select_all(action="DESELECT")

    # ── Step 2: apply the SVG → BU scale factor ──────────────────────────
    # After Step 1, curve coordinates are in raw SVG user-units.
    # Multiply by SVG_TO_BU to convert to Blender Units (≈ Halo CE WU).
    for obj in new_objs:
        obj.scale = (SVG_TO_BU, SVG_TO_BU, SVG_TO_BU)

    bpy.ops.object.select_all(action="DESELECT")
    for obj in new_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = new_objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.select_all(action="DESELECT")

    # ── Center all objects on the border's bounding-box midpoint ─────────
    # After Steps 1-2, curve coordinates are in BU with all SVG transforms
    # applied.  Find the "limites" border curve, compute its XY centroid,
    # and shift every imported object so the border centre lands at world
    # origin (0,0).  A final transform_apply bakes the offset into the
    # curve data so that Object Info nodes in GN always see centred coords.
    border_id = label_map.get("limites")
    border_obj: bpy.types.Object | None = None
    for obj in new_objs:
        if obj.type != "CURVE":
            continue
        n = obj.name
        if border_id and (n == border_id or n.startswith(border_id + ".")):
            border_obj = obj
            break
        if "limites" in n.lower():
            border_obj = obj
            break

    if border_obj is not None:
        # bound_box: 8 corners in local space.
        # After transform_apply(scale) the object sits at location=(0,0,0)
        # with scale=(1,1,1), so local ≡ world.
        bb = border_obj.bound_box
        xs = [v[0] for v in bb]
        ys = [v[1] for v in bb]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        print(
            f"[naranjos-dsl] Centering: border centroid "
            f"({cx:.4f}, {cy:.4f}) BU → translating all objects to origin."
        )
        for obj in new_objs:
            obj.location.x -= cx
            obj.location.y -= cy
        bpy.ops.object.select_all(action="DESELECT")
        for obj in new_objs:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = new_objs[0]
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
        bpy.ops.object.select_all(action="DESELECT")
    else:
        print("[naranjos-dsl] WARNING: 'limites' curve not found — map NOT centred.")

    return new_objs, label_map


def _find_curve(
    objects: list[bpy.types.Object],
    path_name: str,
    label_map: dict[str, str],
):
    lower = path_name.lower()
    svg_id = label_map.get(lower)
    if svg_id:
        # Exact match or Blender duplicate suffix (.001, .002, …).
        # Avoid prefix collisions: svg_id "rect7764" must NOT match "rect7764-3".
        for obj in objects:
            if obj.type == "CURVE":
                n = obj.name
                if n == svg_id or n.startswith(svg_id + "."):
                    return obj
    for obj in objects:
        if obj.type == "CURVE" and lower in obj.name.lower():
            return obj
    for obj in objects:
        if obj.type == "CURVE" and lower in obj.data.name.lower():
            return obj
    print(f"[naranjos-dsl] No match for '{path_name}' (svg_id={svg_id}).")
    return None


# ---------------------------------------------------------------------------
# Opening (door + window) bound helpers
# ---------------------------------------------------------------------------

Bounds6 = tuple[float, float, float, float, float, float]  # (x0,y0,z0,x1,y1,z1)


def _door_bounds(
    resolved_doors: list[dict],
    floor_height_bu: float,
    z_start_bu: float = 0.0,
) -> list[Bounds6]:
    """Return (x0,y0,z0, x1,y1,z1) world-BU bounds for each resolved door.

    The floor slab is a solid prism from z=floor_base to z=floor_base+SLAB_THICKNESS_BU.
    Its lateral (vertical) side faces have |normal.z|≈0, so _wall_mask marks them as
    "wall faces".  If z0 falls inside the slab those side faces are deleted, opening
    the mesh.  Fix: z0 must clear the top of the floor slab; z1 must clear the bottom
    of the ceiling slab.

        z0 = floor_base + SLAB_THICKNESS_BU + DOOR_MARGIN_BU
        z1 = min(z0 + door_height, floor_base + floor_height - SLAB_THICKNESS_BU - DOOR_MARGIN_BU)
    """
    door_h_bu = m_to_bu(DEFAULT_DOOR_HEIGHT_M)
    bounds: list[Bounds6] = []
    for door in resolved_doors:
        door_curve = bpy.data.objects.get(door["obj_name"])
        if door_curve is None:
            print(
                f"[naranjos-dsl] WARNING: door curve '{door['obj_name']}' "
                f"not found — skipped."
            )
            continue
        x0, y0, x1, y1 = _get_curve_bounds_bu(door_curve)
        floor_base = z_start_bu + (door["piso"] - 1) * floor_height_bu
        # Bottom of cut: strictly above the floor slab's lateral faces
        z0 = floor_base + SLAB_THICKNESS_BU + DOOR_MARGIN_BU
        # Top of cut: strictly below the ceiling slab's lateral faces
        z1_raw = z0 + door_h_bu
        z1_ceil = floor_base + floor_height_bu - SLAB_THICKNESS_BU - DOOR_MARGIN_BU
        z1 = min(z1_raw, z1_ceil)
        if z1 <= z0:
            print(
                f"[naranjos-dsl] WARNING: door '{door['obj_name']}' piso {door['piso']}: "
                f"z1={z1:.4f} ≤ z0={z0:.4f} BU — floor height too small for door, skipped."
            )
            continue
        bounds.append((x0, y0, z0, x1, y1, z1))
    return bounds


def _window_bounds(
    resolved_windows: list[dict],
    floor_height_bu: float,
    z_start_bu: float = 0.0,
) -> list[Bounds6]:
    """Return (x0,y0,z0, x1,y1,z1) world-BU bounds for each resolved window."""
    bounds: list[Bounds6] = []
    for win in resolved_windows:
        win_curve = bpy.data.objects.get(win["obj_name"])
        if win_curve is None:
            print(
                f"[naranjos-dsl] WARNING: window curve '{win['obj_name']}' "
                f"not found — skipped."
            )
            continue
        x0, y0, x1, y1 = _get_curve_bounds_bu(win_curve)
        z0 = (z_start_bu + (win["piso"] - 1) * floor_height_bu
              + m_to_bu(win["z_bottom_m"]))
        z1 = z0 + m_to_bu(win["height_m"])
        bounds.append((x0, y0, z0, x1, y1, z1))
    return bounds


def _cut_openings_direct(
    obj: bpy.types.Object,
    all_bounds: list[Bounds6],
    n_doors: int = 0,
    n_windows: int = 0,
) -> None:
    """Cut door and window openings in a single bisect + face-deletion pass.

    Doing ALL openings in one pass is critical for performance: each
    ``bmesh.ops.bisect_plane`` call grows the mesh, so sequential separate
    passes (doors first, then windows) cause O(N²) mesh growth.  By
    collecting every unique boundary plane once and bisecting the
    *original* baked mesh, the total mesh size stays linear.

    Algorithm:
        1. Bake the GN modifier (``new_from_object``) → static mesh.
        2. Collect all unique axis-aligned planes from every bounding box.
        3. Bisect once per unique plane (deduplication via ``set``).
        4. Delete wall faces (``|normal.z| < 0.5``) inside each bbox.

    Args:
        obj:        Building mesh object (GN modifier may or may not be present).
        all_bounds: Pre-computed ``(x0,y0,z0, x1,y1,z1)`` tuples for every
                    opening (doors and windows combined).
        n_doors:    Number of door openings (for the log message).
        n_windows:  Number of window openings (for the log message).
    """
    if not all_bounds:
        return

    # ── Bake GN modifier → static mesh ───────────────────────────────────
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    baked = bpy.data.meshes.new_from_object(eval_obj)
    old_mesh = obj.data
    obj.data = baked
    obj.modifiers.clear()
    bpy.data.meshes.remove(old_mesh)

    # ── Collect all unique bisect planes (deduped) ────────────────────────
    planes: set[tuple[str, float]] = set()
    for (x0, y0, z0, x1, y1, z1) in all_bounds:
        planes.update([("x", x0), ("x", x1), ("y", y0), ("y", y1),
                       ("z", z0), ("z", z1)])

    AXIS_CO_NO = {
        "x": lambda v: (Vector((v, 0, 0)), Vector((1, 0, 0))),
        "y": lambda v: (Vector((0, v, 0)), Vector((0, 1, 0))),
        "z": lambda v: (Vector((0, 0, v)), Vector((0, 0, 1))),
    }

    bm = bmesh.new()
    bm.from_mesh(obj.data)

    # ── Pre-filter: skip planes outside the mesh AABB ────────────────────
    # bisect_plane is the dominant cost; eliminating out-of-bounds planes
    # saves time and keeps the mesh smaller.  The AABB is stable across
    # bisect operations (bisect only splits, never expands geometry).
    if bm.verts:
        _vco_arr = np.array([[v.co.x, v.co.y, v.co.z] for v in bm.verts])
        _aabb_min = _vco_arr.min(axis=0)
        _aabb_max = _vco_arr.max(axis=0)
        _ax_i = {"x": 0, "y": 1, "z": 2}
        _EPS = 1e-4

        planes_to_cut = {
            (ax, val) for ax, val in planes
            if _aabb_min[_ax_i[ax]] - _EPS <= val <= _aabb_max[_ax_i[ax]] + _EPS
        }
        n_skipped = len(planes) - len(planes_to_cut)
        if n_skipped:
            print(f"[naranjos-dsl] {obj.name}: skipped {n_skipped} planes outside AABB.")
    else:
        planes_to_cut = planes

    print(f"[naranjos-dsl] {obj.name}: bisecting {len(planes_to_cut)} planes "
          f"for {n_doors} door(s) + {n_windows} window(s)…")

    for (axis, val) in planes_to_cut:
        co, no = AXIS_CO_NO[axis](val)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        bmesh.ops.bisect_plane(
            bm,
            geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
            plane_co=co,
            plane_no=no,
            clear_inner=False,
            clear_outer=False,
        )

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # ── Batch-delete wall faces inside opening bounding boxes (NumPy) ─────
    # Key optimisation: compute face centres and normals ONCE, then run
    # vectorised comparisons for all openings in one pass.  A single
    # bmesh.ops.delete call replaces N sequential delete calls.
    # Original: N × 3F calls to calc_center_median().
    # Optimised: F calls upfront + N × O(F) numpy ops (no Python loops).
    total_deleted = 0
    no_hit: list[Bounds6] = []

    all_faces_snap = list(bm.faces)
    if all_faces_snap:
        _centers = [f.calc_center_median() for f in all_faces_snap]
        _fc = np.array([[c.x, c.y, c.z] for c in _centers], dtype=np.float64)
        _fn_z = np.array([abs(f.normal.z) for f in all_faces_snap], dtype=np.float64)
        _wall_mask = _fn_z < 0.5  # True for wall faces (skip slabs)

        to_delete_rows: set[int] = set()
        for bounds in all_bounds:
            x0, y0, z0, x1, y1, z1 = bounds
            in_box = (
                _wall_mask
                & (_fc[:, 0] >= x0) & (_fc[:, 0] <= x1)
                & (_fc[:, 1] >= y0) & (_fc[:, 1] <= y1)
                & (_fc[:, 2] >= z0) & (_fc[:, 2] <= z1)
            )
            hit_rows = np.where(in_box)[0]
            if hit_rows.size:
                to_delete_rows.update(hit_rows.tolist())
            else:
                no_hit.append(bounds)

        if to_delete_rows:
            faces_to_delete = [all_faces_snap[i] for i in to_delete_rows]
            bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")
            bm.faces.ensure_lookup_table()
            total_deleted = len(faces_to_delete)

    parts = []
    if n_doors:   parts.append(f"{n_doors} door(s)")
    if n_windows: parts.append(f"{n_windows} window(s)")
    label = " + ".join(parts) if parts else f"{len(all_bounds)} opening(s)"

    if total_deleted:
        print(f"[naranjos-dsl] {obj.name}: removed {total_deleted} face(s) "
              f"→ {label}.")
    else:
        print(f"[naranjos-dsl] WARNING: {obj.name}: no wall faces removed "
              f"({label}) — check SVG positions.")
    if no_hit:
        print(f"[naranjos-dsl] WARNING: {obj.name}: {len(no_hit)} opening(s) "
              f"had no matching faces.")

    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


# ---------------------------------------------------------------------------
# DSL graph builders
# ---------------------------------------------------------------------------

def _building_graph(
    name: str,
    curve_obj_name: str,
    num_floors: int,
    floor_height_bu: float,
    wall_thickness_bu: float,
    slab_thickness_bu: float,
    z_start_bu: float = 0.0,
):
    """Build an IRGraph for one or more sealed storey volumes.

    Strategy (all in Geometry Nodes):
        1. Object Info → footprint curve
        2. Set Spline Cyclic (ensure closed)
        3. Wall profile = Curve Quadrilateral (wall_thickness × floor_height)
        4. Curve to Mesh (footprint, profile) → hollow walls for one floor
        5. Sweep the footprint along a short vertical line → closed floor slab
        6. Ceiling slab = same sweep translated up
        7. Join walls + floor + ceiling → one floor module
        8. Instance on Points at (0,0, i*floor_height) for each floor
        9. Realize instances → final geometry

    This approach preserves visible floor and ceiling slabs at every storey
    level.  Door holes are cut separately; see ``_cut_openings_direct``.
    """
    with model(f"gn_{name}") as ctx:
        # Footprint curve from the imported SVG object
        footprint = object_info(curve_obj_name)
        footprint = footprint | set_spline_cyclic(cyclic=True)

        # Wall cross-section: rectangle (wall_thickness × floor_height).
        # When swept along the flat XY footprint path, the Height axis of the
        # quadrilateral aligns with the path's UP direction (world Z), so
        # walls are always vertical regardless of footprint orientation.
        wall_profile = curve_quadrilateral(wall_thickness_bu, floor_height_bu)

        # Walls for one floor: sweep profile along footprint.
        # curve_to_mesh centres the profile on the path, so the wall
        # extends from -floor_height/2 to +floor_height/2.  Shift up
        # so walls sit on [0, floor_height] matching the slabs.
        walls = (
            footprint
            | curve_to_mesh(profile=wall_profile, fill_caps=True)
            | translate(0, 0, floor_height_bu / 2)
        )

        # Floor and ceiling slabs: thin horizontal prisms at z=0 and
        # z=floor_height-slab_thickness, respectively.
        # slab_path is a short vertical curve; sweeping the footprint along
        # it produces a slab with the exact shape of the building footprint.
        slab_path = curve_line(
            start=(0.0, 0.0, 0.0),
            end=(0.0, 0.0, slab_thickness_bu),
        )
        floor_slab = slab_path | curve_to_mesh(profile=footprint, fill_caps=True)
        ceiling_slab = (
            slab_path
            | curve_to_mesh(profile=footprint, fill_caps=True)
            | translate(0, 0, floor_height_bu - slab_thickness_bu)
        )

        # One complete floor module
        one_floor = join([walls, floor_slab, ceiling_slab])

        # Stack floors using Instance on Points
        floor_positions = [
            (0.0, 0.0, i * floor_height_bu) for i in range(num_floors)
        ]
        stacked = clones(one_floor, floor_positions)
        result = stacked | realize_instances()
        if z_start_bu:
            result = result | translate(0, 0, z_start_bu)

        output(result)

    return ctx.graph


def _roof_or_hall_graph(
    name: str,
    curve_obj_name: str,
    level_height_bu: float,
    wall_thickness_bu: float,
    slab_thickness_bu: float,
    z_start_bu: float,
):
    return _building_graph(
        name,
        curve_obj_name,
        num_floors=1,
        floor_height_bu=level_height_bu,
        wall_thickness_bu=wall_thickness_bu,
        slab_thickness_bu=slab_thickness_bu,
        z_start_bu=z_start_bu,
    )


def _get_curve_bounds_bu(
    obj: bpy.types.Object,
) -> tuple[float, float, float, float]:
    """Return (x_min, y_min, x_max, y_max) of a curve object in world BU.

    Uses the evaluated mesh so that transforms are fully applied.
    """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()
    try:
        xs = [v.co.x for v in eval_mesh.vertices]
        ys = [v.co.y for v in eval_mesh.vertices]
        if not xs:
            return 0.0, 0.0, 0.0, 0.0
        return min(xs), min(ys), max(xs), max(ys)
    finally:
        eval_obj.to_mesh_clear()


def _curve_outer_polygon_xy(obj: bpy.types.Object) -> list[tuple[float, float]]:
    """Return ordered XY points from the first spline of a closed border curve."""
    if obj.type != "CURVE" or not obj.data.splines:
        return []

    spline = obj.data.splines[0]
    pts: list[tuple[float, float]] = []
    matrix = obj.matrix_world

    if spline.type == "BEZIER":
        for point in spline.bezier_points:
            co = matrix @ point.co
            pts.append((co.x, co.y))
    else:
        for point in spline.points:
            co = matrix @ Vector((point.co.x, point.co.y, point.co.z))
            pts.append((co.x, co.y))

    if len(pts) > 1:
        first = Vector((pts[0][0], pts[0][1], 0.0))
        last = Vector((pts[-1][0], pts[-1][1], 0.0))
        if (first - last).length < 1e-5:
            pts.pop()

    return pts


def _polygon_signed_area_xy(points: list[tuple[float, float]]) -> float:
    area = 0.0
    for i, (x0, y0) in enumerate(points):
        x1, y1 = points[(i + 1) % len(points)]
        area += (x0 * y1) - (x1 * y0)
    return area * 0.5


def _create_level_floor_solid(
    border_curve: bpy.types.Object,
    thickness_bu: float,
    top_z_bu: float,
) -> bpy.types.Object | None:
    """Create a closed solid floor mesh from the exterior border curve."""
    points = _curve_outer_polygon_xy(border_curve)
    if len(points) < 3:
        print("[naranjos-dsl] WARNING: level_floor needs at least 3 border points.")
        return None

    # Ensure top cap points are CCW when viewed from above, so its normal is +Z.
    if _polygon_signed_area_xy(points) < 0:
        points.reverse()

    bottom_z_bu = top_z_bu - thickness_bu
    verts = [(x, y, top_z_bu) for x, y in points]
    verts.extend((x, y, bottom_z_bu) for x, y in points)

    n = len(points)
    faces: list[list[int]] = [
        list(range(n)),                    # top cap
        list(range((2 * n) - 1, n - 1, -1)),  # bottom cap
    ]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, n + j, n + i])

    mesh = bpy.data.meshes.new("level_floor_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new("level_floor", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _bm_add_slab(
    bm: bmesh.types.BMesh,
    x0: float, x1: float,
    y0: float, y1: float,
    z00: float, z01: float,
    z10: float, z11: float,
    thickness: float,
) -> None:
    """Add a closed solid slab to *bm* with independent Z per corner.

    Bottom corners (counter-clockwise from below):
        (x0,y0,z00)  (x1,y0,z01)  (x1,y1,z11)  (x0,y1,z10)
    Top face is the same footprint offset by *thickness* in +Z.

    Flat slab  : z00=z01=z10=z11
    Y-ramp     : z00=z01,  z10=z11   (Z varies along Y only)
    X-ramp     : z00=z10,  z01=z11   (Z varies along X only)
    """
    vb = [
        bm.verts.new((x0, y0, z00)),
        bm.verts.new((x1, y0, z01)),
        bm.verts.new((x1, y1, z11)),
        bm.verts.new((x0, y1, z10)),
    ]
    vt = [bm.verts.new((v.co.x, v.co.y, v.co.z + thickness)) for v in vb]

    bm.faces.new([vb[0], vb[3], vb[2], vb[1]])  # bottom (normal ↓)
    bm.faces.new([vt[0], vt[1], vt[2], vt[3]])  # top    (normal ↑)
    bm.faces.new([vb[0], vb[1], vt[1], vt[0]])  # side y=y0
    bm.faces.new([vb[1], vb[2], vt[2], vt[1]])  # side x=x1
    bm.faces.new([vb[2], vb[3], vt[3], vt[2]])  # side y=y1
    bm.faces.new([vb[3], vb[0], vt[0], vt[3]])  # side x=x0


def _create_staircase_solid(
    staircase_id: int,
    seg_curves: list[tuple[dict, bpy.types.Object | None]],
    slab_thickness: float,
    left_ratio: float = 0.4,
    gap_ratio: float = 0.2,
) -> bpy.types.Object | None:
    """Single merged mesh for a complete staircase.

    Geometry:
      1. A flat closed slab for every landing at its Z level.
      2. For every INTERMEDIATE landing (level == X.5), exactly TWO flight slabs:
         - One slab to PREV (lower) landing: uses the LEFT left_ratio strip of
           the intermediate's split axis (left 40% in X, or bottom 40% in Y).
         - One slab to NEXT (upper) landing: uses the RIGHT (1-left_ratio-gap_ratio)
           strip (right 40% in X, or top 40% in Y).
         The central gap_ratio strip is left open (the staircase "eye").

    The flight slab physically bridges the gap between the two footprints.
    Split axis is perpendicular to the gap direction.
    """
    bm = bmesh.new()
    has_geo = False

    # Pre-compute curve bounding boxes once — _get_curve_bounds_bu() triggers a
    # depsgraph evaluation, so calling it multiple times for the same curve is
    # wasteful.  With N segments, the flat-slab loop + flight loop would otherwise
    # evaluate the same curve 2-3 times each.
    _bounds_cache: dict[str, tuple[float, float, float, float]] = {
        curve.name: _get_curve_bounds_bu(curve)
        for _, curve in seg_curves
        if curve is not None
    }

    # flat landing slabs
    for seg, curve in seg_curves:
        if curve is None:
            continue
        z = float(seg["z_start_bu"])
        x0, y0, x1, y1 = _bounds_cache[curve.name]
        _bm_add_slab(bm, x0, x1, y0, y1, z, z, z, z, slab_thickness)
        has_geo = True

    # inclined flight slabs — one per connection, only from intermediate landings
    for i, (seg, curve) in enumerate(seg_curves):
        if curve is None:
            continue
        level = float(seg["level"])
        if level == int(level):
            continue  # skip regular landings

        ix0, iy0, ix1, iy1 = _bounds_cache[curve.name]
        z_int = float(seg["z_start_bu"])
        span_x = ix1 - ix0
        span_y = iy1 - iy0

        # Split points along both axes of the intermediate landing
        lx = ix0 + left_ratio * span_x
        rx = ix0 + (left_ratio + gap_ratio) * span_x
        ly = iy0 + left_ratio * span_y
        ry = iy0 + (left_ratio + gap_ratio) * span_y

        def _add_flight(curve_adj, z_adj: float, use_left: bool) -> None:
            """Bridge the gap between this intermediate and one adjacent landing.

            use_left=True  → left 40% strip  (connects to PREV / lower landing)
            use_left=False → right 40% strip (connects to NEXT / upper landing)
            """
            if curve_adj is None:
                return
            ax0, ay0, ax1, ay1 = _bounds_cache[curve_adj.name]

            if ay1 <= iy0:
                # adjacent BELOW intermediate in Y → gap [ay1, iy0], split in X
                fx0 = ix0 if use_left else rx
                fx1 = lx  if use_left else ix1
                _bm_add_slab(bm, fx0, fx1, ay1, iy0,
                             z_adj, z_adj, z_int, z_int, slab_thickness)

            elif iy1 <= ay0:
                # adjacent ABOVE intermediate in Y → gap [iy1, ay0], split in X
                fx0 = ix0 if use_left else rx
                fx1 = lx  if use_left else ix1
                _bm_add_slab(bm, fx0, fx1, iy1, ay0,
                             z_int, z_int, z_adj, z_adj, slab_thickness)

            elif ax1 <= ix0:
                # adjacent to the LEFT in X → gap [ax1, ix0], split in Y
                fy0 = iy0 if use_left else ry
                fy1 = ly  if use_left else iy1
                _bm_add_slab(bm, ax1, ix0, fy0, fy1,
                             z_adj, z_int, z_adj, z_int, slab_thickness)

            elif ix1 <= ax0:
                # adjacent to the RIGHT in X → gap [ix1, ax0], split in Y
                fy0 = iy0 if use_left else ry
                fy1 = ly  if use_left else iy1
                _bm_add_slab(bm, ix1, ax0, fy0, fy1,
                             z_int, z_adj, z_int, z_adj, slab_thickness)

            else:
                print(
                    f"[naranjos-dsl] WARNING: overlapping footprints for "
                    f"flight from '{seg['shape']}' — skipped."
                )

        # flight to PREV (lower landing) — left strip of intermediate
        if i > 0:
            seg_p, curve_p = seg_curves[i - 1]
            _add_flight(curve_p, float(seg_p["z_start_bu"]), use_left=True)

        # flight to NEXT (upper landing) — right strip of intermediate
        if i < len(seg_curves) - 1:
            seg_n, curve_n = seg_curves[i + 1]
            _add_flight(curve_n, float(seg_n["z_start_bu"]), use_left=False)

    if not has_geo:
        bm.free()
        return None

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    name = f"staircase_{staircase_id}"
    mesh_data = bpy.data.meshes.new(f"mesh_{name}")
    bm.to_mesh(mesh_data)
    bm.free()

    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _find_cols_curves(group_id: str) -> list:
    """Return all CURVE child objects of an SVG group.

    Blender's SVG importer creates a parent object for ``<g>`` groups and
    individual CURVE objects for each ``<path>`` / ``<circle>`` child.
    Falls back to the group object itself if it is a CURVE (single merged).
    """
    children = [
        obj for obj in bpy.data.objects
        if obj.type == "CURVE"
        and obj.parent is not None
        and obj.parent.name == group_id
    ]
    if children:
        return children
    # Fallback: the group object itself may be a merged multi-spline curve
    group_obj = bpy.data.objects.get(group_id)
    if group_obj and group_obj.type == "CURVE":
        return [group_obj]
    return []


def _spline_circle_center_radius(obj, spline):
    """Return (cx, cy, r) in world BU for a closed circle-like spline.

    SVG circles imported as Bezier curves have 4 control points at the
    cardinal positions (N/S/E/W), so the bounding box of those co-ordinates
    equals the circle bounding box.  Rotated circles (``transform="rotate"``
    in SVG) are handled automatically via ``matrix_world``.
    """
    import mathutils

    if spline.type == "BEZIER":
        pts = [obj.matrix_world @ p.co for p in spline.bezier_points]
    elif spline.type in ("NURBS", "POLY"):
        pts = [
            obj.matrix_world @ mathutils.Vector((p.co.x, p.co.y, p.co.z))
            for p in spline.points
        ]
    else:
        return None
    if len(pts) < 3:
        return None
    xs = [p.x for p in pts]
    ys = [p.y for p in pts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    r  = (max(xs) - min(xs)) / 2.0
    return cx, cy, r


def _create_columns_for_floor(col_curves, z_start_bu, height_bu, floor_num, segments=16):
    """Create a single merged cylinder mesh from all circle splines in *col_curves*.

    Each spline is treated as a closed circle (SVG ``<circle>`` or circular
    ``<path>``).  The cylinder is extruded from *z_start_bu* upward by
    *height_bu*.  Returns a linked Blender mesh object, or None if no valid
    circles were found.
    """
    import math

    bm = bmesh.new()
    has_geo = False
    angle_step = 2.0 * math.pi / segments

    for col_obj in col_curves:
        for spline in col_obj.data.splines:
            res = _spline_circle_center_radius(col_obj, spline)
            if res is None:
                continue
            cx, cy, r = res
            if r < 0.01:
                continue

            bot = [
                bm.verts.new((
                    cx + r * math.cos(i * angle_step),
                    cy + r * math.sin(i * angle_step),
                    z_start_bu,
                ))
                for i in range(segments)
            ]
            top = [
                bm.verts.new((
                    cx + r * math.cos(i * angle_step),
                    cy + r * math.sin(i * angle_step),
                    z_start_bu + height_bu,
                ))
                for i in range(segments)
            ]
            for i in range(segments):
                j = (i + 1) % segments
                bm.faces.new([bot[i], bot[j], top[j], top[i]])
            bm.faces.new(list(reversed(bot)))   # bottom cap
            bm.faces.new(top)                   # top cap
            has_geo = True

    if not has_geo:
        bm.free()
        return None

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    name = f"cols_piso_{floor_num}"
    mesh_data = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh_data)
    bm.free()

    obj = bpy.data.objects.new(name, mesh_data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _get_footprint_polygon_2d(
    obj: bpy.types.Object,
    floor_z: float = 0.0,
    z_tol: float = 0.05,
) -> list[tuple[float, float]] | None:
    """Extract the XY footprint polygon of *obj* at z ≈ floor_z.

    Two code paths:
    - CURVE objects: read spline control-points directly — no mesh needed and
      avoids issues with un-filled curve objects returning empty meshes.
    - MESH objects: find horizontal faces (or edges) at floor_z using the raw
      mesh polygon/edge data with direct world-matrix multiplication.

    Avoids bmesh.ops.transform which can silently mis-apply matrices. Uses
    floor_z=0.0 as the reference (not min_z) so that buildings with slabs
    extending below z=0 are handled correctly.

    Returns an ordered list of (x, y) world-space pairs, or None on failure.
    """
    mwm = obj.matrix_world

    # ── CURVE: read spline data directly ──────────────────────────────────
    if obj.type == 'CURVE':
        for spline in obj.data.splines:
            pts: list[tuple[float, float]] = []
            if spline.type in ('POLY', 'NURBS'):
                for p in spline.points:
                    wco = mwm @ p.co.to_3d()
                    pts.append((wco.x, wco.y))
            elif spline.type == 'BEZIER':
                for bp in spline.bezier_points:
                    wco = mwm @ bp.co
                    pts.append((wco.x, wco.y))
            if len(pts) >= 3:
                return pts
        return None  # no usable spline found

    # ── MESH: find floor boundary at floor_z ──────────────────────────────
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj  = obj.evaluated_get(depsgraph)
    try:
        mesh = eval_obj.to_mesh()
        if not mesh or not mesh.vertices:
            return None

        # World-space vertex positions via direct matrix multiply (no bmesh.ops.transform)
        wverts = [mwm @ v.co for v in mesh.vertices]
        at_floor = frozenset(
            i for i, v in enumerate(wverts) if abs(v.z - floor_z) < z_tol
        )
        if not at_floor:
            return None

        # Try horizontal floor polygons first
        floor_polys: set[int] = set()
        for poly in mesh.polygons:
            if all(vi in at_floor for vi in poly.vertices):
                if abs(poly.normal.z) > 0.5:
                    floor_polys.add(poly.index)

        if floor_polys:
            # Boundary: edges belonging to exactly one floor polygon
            edge_count: dict[frozenset, int] = {}
            edge_vi:    dict[frozenset, tuple[int, int]] = {}
            for poly in mesh.polygons:
                if poly.index not in floor_polys:
                    continue
                vlist = list(poly.vertices)
                n = len(vlist)
                for i in range(n):
                    key = frozenset([vlist[i], vlist[(i + 1) % n]])
                    edge_count[key] = edge_count.get(key, 0) + 1
                    edge_vi[key] = (vlist[i], vlist[(i + 1) % n])
            boundary = [
                vi for key, vi in edge_vi.items() if edge_count[key] == 1
            ]
        else:
            # No floor faces — all edges at floor_z form the boundary
            boundary = [
                (e.vertices[0], e.vertices[1])
                for e in mesh.edges
                if e.vertices[0] in at_floor and e.vertices[1] in at_floor
            ]

        if not boundary:
            return None

        # Walk boundary into ordered polygon
        adj: dict[int, list[int]] = {}
        for v1, v2 in boundary:
            adj.setdefault(v1, []).append(v2)
            adj.setdefault(v2, []).append(v1)

        polygon: list[tuple[float, float]] = []
        visited: set[int] = set()
        cur = next(iter(adj))
        while True:
            polygon.append((wverts[cur].x, wverts[cur].y))
            visited.add(cur)
            nxt = [v for v in adj[cur] if v not in visited]
            if not nxt:
                break
            cur = nxt[0]

        return polygon if len(polygon) >= 3 else None

    finally:
        eval_obj.to_mesh_clear()


def _point_in_polygon_2d(
    px: float,
    py: float,
    polygon: list[tuple[float, float]],
) -> bool:
    """Ray-casting point-in-polygon test (works for concave polygons)."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > py) != (yj > py):
            denom = yj - yi
            if denom != 0 and px < (xj - xi) * (py - yi) / denom + xi:
                inside = not inside
        j = i
    return inside


def _cut_building_footprints_from_floor(
    floor_obj: bpy.types.Object,
    building_objs: list[bpy.types.Object],
) -> None:
    """Cut exact-shape holes in *floor_obj* for every building/landing footprint.

    Replaces the old bounding-box approach: instead of rectangular cuts that
    leave wrong-shaped holes for non-rectangular buildings, we extract the
    actual footprint polygon of each object and bisect the floor along every
    polygon edge, then delete only the faces truly inside each polygon.

    Works for both MESH objects (buildings) and CURVE objects (stair landings).
    """
    # Bake GN modifier → static mesh
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj  = floor_obj.evaluated_get(depsgraph)
    baked     = bpy.data.meshes.new_from_object(eval_obj)
    old_mesh  = floor_obj.data
    floor_obj.data = baked
    floor_obj.modifiers.clear()
    bpy.data.meshes.remove(old_mesh)

    # Collect exact footprint polygons
    footprints: list[list[tuple[float, float]]] = []
    for bldg_obj in building_objs:
        poly = _get_footprint_polygon_2d(bldg_obj)
        if poly is not None:
            footprints.append(poly)
        else:
            print(
                f"[naranjos-dsl] WARNING: could not extract footprint polygon "
                f"for '{bldg_obj.name}' — skipped in floor cut."
            )

    if not footprints:
        return

    # Bisect the floor along every edge of every footprint polygon.
    # This introduces vertices exactly on the polygon boundary so that
    # the subsequent face deletion leaves a clean, T-intersection-free hole.
    bm = bmesh.new()
    bm.from_mesh(floor_obj.data)

    for polygon in footprints:
        n = len(polygon)
        for i in range(n):
            x1, y1 = polygon[i]
            x2, y2 = polygon[(i + 1) % n]
            dx, dy  = x2 - x1, y2 - y1
            length  = (dx * dx + dy * dy) ** 0.5
            if length < 1e-8:
                continue
            # Plane normal perpendicular to edge (either direction is fine for bisect)
            nx, ny = -dy / length, dx / length
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
            bmesh.ops.bisect_plane(
                bm,
                geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                plane_co=Vector((x1, y1, 0.0)),
                plane_no=Vector((nx, ny, 0.0)),
                clear_inner=False,
                clear_outer=False,
            )

    bm.faces.ensure_lookup_table()

    # Delete horizontal floor faces whose centre lies strictly inside each polygon
    total_deleted = 0
    for polygon in footprints:
        faces_to_delete = [
            f for f in bm.faces
            if abs(f.normal.z) > 0.5
            and _point_in_polygon_2d(
                f.calc_center_median().x,
                f.calc_center_median().y,
                polygon,
            )
        ]
        if faces_to_delete:
            bmesh.ops.delete(bm, geom=faces_to_delete, context="FACES")
            bm.faces.ensure_lookup_table()
            total_deleted += len(faces_to_delete)

    bm.to_mesh(floor_obj.data)
    bm.free()
    floor_obj.data.update()

    print(
        f"[naranjos-dsl] level_floor: cut {total_deleted} face(s) "
        f"for {len(footprints)} building footprint(s)."
    )


def _border_graph(
    curve_obj_name: str,
    height_bu: float,
    wall_thickness_bu: float,
):
    """Build an IRGraph for border walls.

    Strategy:
        1. Object Info → border curve
        2. Wall profile = Curve Quadrilateral (wall_thickness × height)
        3. Curve to Mesh (border path, profile) → border wall with thickness
    """
    with model("gn_borders") as ctx:
        border_curve = object_info(curve_obj_name)
        wall_profile = curve_quadrilateral(wall_thickness_bu, height_bu)
        walls = (
            border_curve
            | curve_to_mesh(profile=wall_profile, fill_caps=True)
            | translate(0, 0, height_bu / 2)
        )
        output(walls)

    return ctx.graph


def _floor_graph(
    curve_obj_name: str,
    thickness_bu: float,
    top_z_bu: float,
) -> "IRGraph":
    """Build a closed floor slab from the exterior border curve.

    The top cap is placed at *top_z_bu* and the volume extrudes downward by
    *thickness_bu*, so it can sit below the generated buildings without
    overlapping their floor slabs.
    """
    with model("gn_level_floor") as ctx:
        border_curve = object_info(curve_obj_name) | set_spline_cyclic(cyclic=True)
        floor_mesh = (
            border_curve
            | fill_curve()
            | extrude(offset=(0.0, 0.0, -thickness_bu))
            | translate(0, 0, top_z_bu)
        )
        output(floor_mesh)

    return ctx.graph


# ---------------------------------------------------------------------------
# GN tree application helpers
# ---------------------------------------------------------------------------

def _exec_gn_setup(object_name: str, gn_source: str) -> bpy.types.Object:
    """Execute compiled DSL source which creates the object + GN modifier.

    The compiled ``setup(object_name)`` function:
      - Creates a mesh object named *object_name*
      - Adds a GeometryNodes modifier
      - Builds the full node tree

    The modifier is kept **live** so the GN tree stays parametric.
    Returns the created Blender object.
    """
    namespace: dict = {"bpy": bpy}
    exec(compile(gn_source, f"<gn_{object_name}>", "exec"), namespace)
    # Call the setup function with the desired object name
    namespace["setup"](object_name=object_name)
    return bpy.data.objects[object_name]


def _ensure_collection(name: str) -> bpy.types.Collection:
    if name not in bpy.data.collections:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return bpy.data.collections[name]


def _move_to_collection(obj: bpy.types.Object, coll_name: str) -> None:
    coll = _ensure_collection(coll_name)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


def _cleanup_svg_collection() -> None:
    svg_stem = Path(_SVG_DIR / "map.svg").stem.lower()
    for coll in list(bpy.data.collections):
        if svg_stem in coll.name.lower() and len(coll.objects) == 0:
            bpy.data.collections.remove(coll)


def _bake_object_mesh_world(obj: bpy.types.Object) -> bpy.types.Mesh | None:
    if obj.type != "MESH":
        return None
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=depsgraph)
    matrix = eval_obj.matrix_world.copy()
    for vert in mesh.vertices:
        vert.co = matrix @ vert.co
    mesh.update()
    return mesh


def _find_t_junction_hit(
    bm: bmesh.types.BMesh,
    tol: float = _TJUNCTION_TOL,
    skip_edge_cokeys: set | None = None,
) -> tuple[bmesh.types.BMEdge, bmesh.types.BMVert, float] | None:
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    verts = list(bm.verts)
    edges = list(bm.edges)
    if len(verts) < 3 or not edges:
        return None

    vco = np.array([[v.co.x, v.co.y, v.co.z] for v in verts], dtype=np.float64)
    all_rows = np.arange(len(verts))
    vert_to_row = {v: i for i, v in enumerate(verts)}

    for edge in edges:
        ia = vert_to_row[edge.verts[0]]
        ib = vert_to_row[edge.verts[1]]

        # Skip edges whose coordinate key is in the failure set.
        if skip_edge_cokeys is not None:
            v0k = tuple(round(x, 6) for x in vco[ia])
            v1k = tuple(round(x, 6) for x in vco[ib])
            ekey = (min(v0k, v1k), max(v0k, v1k))
            if ekey in skip_edge_cokeys:
                continue

        v1 = vco[ia]
        ev = vco[ib] - v1
        el2 = float(ev @ ev)
        if el2 < 1e-12:
            continue

        mask = (all_rows != ia) & (all_rows != ib)
        rows = all_rows[mask]
        t = (vco[mask] - v1) @ ev / el2
        in_range = (t > 1e-6) & (t < 1.0 - 1e-6)
        if not in_range.any():
            continue

        candidate_rows = rows[in_range]
        candidate_t = t[in_range]
        proj = v1 + candidate_t[:, np.newaxis] * ev
        dist = np.linalg.norm(vco[candidate_rows] - proj, axis=1)
        hits = np.where(dist < tol)[0]
        if hits.size:
            hit_i = int(hits[0])
            return edge, verts[int(candidate_rows[hit_i])], float(candidate_t[hit_i])

    return None


def _fix_t_junctions(
    bm: bmesh.types.BMesh,
    tol: float = _TJUNCTION_TOL,
    max_splits: int = T_JUNCTION_FIX_MAX_SPLITS,
) -> int:
    """Split edges at existing vertices that lie on them.

    Uses a coordinate-key skip-set so that edges which raise exceptions are
    not retried in subsequent iterations.  Falls through with ``continue``
    instead of aborting the entire loop on the first failure.
    """
    if max_splits <= 0:
        return 0
    fixed = 0
    # Coordinate-based edge keys that failed — stable across bmesh re-indexing.
    skipped_edge_cokeys: set = set()
    MAX_CONSECUTIVE_SKIP = max(50, max_splits // 20)
    consecutive_skip = 0

    for _ in range(max_splits):
        hit = _find_t_junction_hit(bm, tol, skip_edge_cokeys=skipped_edge_cokeys)
        if hit is None:
            break
        edge, existing_vert, factor = hit

        # Build a position-stable key for this edge before any modification.
        try:
            v0k = tuple(round(x, 6) for x in edge.verts[0].co)
            v1k = tuple(round(x, 6) for x in edge.verts[1].co)
            ekey: tuple = (min(v0k, v1k), max(v0k, v1k))
        except ReferenceError:
            break

        try:
            _new_edge, split_vert = bmesh.utils.edge_split(edge, edge.verts[0], factor)
            bmesh.ops.pointmerge(bm, verts=[split_vert, existing_vert], merge_co=existing_vert.co)
            fixed += 1
            consecutive_skip = 0
        except (ReferenceError, ValueError):
            skipped_edge_cokeys.add(ekey)
            consecutive_skip += 1
            if consecutive_skip >= MAX_CONSECUTIVE_SKIP:
                break
            continue
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
    return fixed


def _find_t_junction_axis_heights(
    bm: bmesh.types.BMesh,
    tol: float = _TJUNCTION_TOL,
) -> dict[int, set[float]]:
    """Return {axis_index: set_of_split_values} for T-junction edges.

    For each edge that has at least one T-junction vertex on it, determine
    the edge's *primary axis* (the Cartesian axis with the largest span) and
    record the T-junction vertex's coordinate along that axis.

    The caller uses these per-axis values to invoke ``bisect_plane`` once per
    unique value — three sets of bisect calls (X, Y, Z) — instead of one call
    per T-junction.

    Only edges with a non-negligible span along their primary axis are
    considered, so degenerate / zero-length edges are ignored.

    Returns a dict with keys 0 (X), 1 (Y), 2 (Z), each mapping to a set of
    float values at which the corresponding axis should be bisected.
    """
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    verts = list(bm.verts)
    edges = list(bm.edges)
    if len(verts) < 3 or not edges:
        return {0: set(), 1: set(), 2: set()}

    vco = np.array([[v.co.x, v.co.y, v.co.z] for v in verts], dtype=np.float64)
    all_rows = np.arange(len(verts))
    vert_to_row = {v: i for i, v in enumerate(verts)}

    axis_heights: dict[int, set[float]] = {0: set(), 1: set(), 2: set()}

    for edge in edges:
        ia = vert_to_row[edge.verts[0]]
        ib = vert_to_row[edge.verts[1]]
        v1 = vco[ia]
        ev = vco[ib] - v1
        el2 = float(ev @ ev)
        if el2 < 1e-12:
            continue

        # Primary axis = axis with the largest span
        abs_ev = np.abs(ev)
        primary = int(np.argmax(abs_ev))
        axis_span = float(abs_ev[primary])
        # The primary span must be significant (skip near-zero edges)
        if axis_span < tol * 10:
            continue

        edge_lo = min(float(vco[ia][primary]), float(vco[ib][primary]))
        edge_hi = max(float(vco[ia][primary]), float(vco[ib][primary]))

        mask = (all_rows != ia) & (all_rows != ib)
        rows = all_rows[mask]
        t = (vco[mask] - v1) @ ev / el2
        in_range = (t > 1e-6) & (t < 1.0 - 1e-6)
        if not in_range.any():
            continue

        candidate_rows = rows[in_range]
        candidate_t = t[in_range]
        proj = v1 + candidate_t[:, np.newaxis] * ev
        dist = np.linalg.norm(vco[candidate_rows] - proj, axis=1)
        hits = np.where(dist < tol)[0]
        for h in hits:
            coord_val = float(vco[int(candidate_rows[h])][primary])
            # Guard: the T-junction coordinate must be strictly inside the edge span
            if edge_lo + tol < coord_val < edge_hi - tol:
                axis_heights[primary].add(coord_val)

    return axis_heights


def _fix_t_junctions_by_z_split(
    bm: bmesh.types.BMesh,
    tol: float = _TJUNCTION_TOL,
    merge_tol: float = MERGE_DISTANCE_BU,
) -> int:
    """Resolve T-junctions by bisecting along each primary axis.

    The Naranjos mesh contains T-junctions on edges of all orientations:

    * **Vertical** (Z-primary): multi-floor wall edges crossed by single-floor
      building vertices at floor-boundary Z levels.
    * **Horizontal X-primary**: wall base/top edges crossed by stair or slab
      vertices at intermediate X positions.
    * **Horizontal Y-primary**: similar but along Y.

    A single Z-bisect pass (as attempted previously) fails for horizontal
    T-junctions.  This function handles all three axes.

    Algorithm
    ---------
    1. One O(E × V) vectorised scan to collect, per axis, the unique
       coordinate values at which T-junction vertices lie ON edges whose
       primary axis matches.
    2. For each axis and each unique value, call ``bmesh.ops.bisect_plane``
       (a single, handle-safe C++ call) to insert a new vertex exactly at
       the T-junction position.
    3. ``remove_doubles`` merges the new vertex with the pre-existing
       T-junction vertex, converting a floating T-junction vertex into a
       proper edge endpoint.

    Returns the total number of new vertices created across all bisects.
    """
    axis_heights = _find_t_junction_axis_heights(bm, tol=tol)

    # (axis_index, plane_normal_tuple)
    axes = [
        (0, (1.0, 0.0, 0.0)),
        (1, (0.0, 1.0, 0.0)),
        (2, (0.0, 0.0, 1.0)),
    ]
    axis_names = "XYZ"

    total_new = 0
    half = merge_tol * 0.5

    for axis_idx, plane_no in axes:
        vals = sorted({round(v, 5) for v in axis_heights[axis_idx]})
        if not vals:
            continue
        print(
            f"[naranjos-dsl] T-junction bisect axis {axis_names[axis_idx]}: "
            f"{len(vals)} level(s)"
        )

        for val in vals:
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            # Quick check: any edge straddles this value along axis?
            straddles = any(
                min(e.verts[0].co[axis_idx], e.verts[1].co[axis_idx]) + half
                < val <
                max(e.verts[0].co[axis_idx], e.verts[1].co[axis_idx]) - half
                for e in bm.edges
            )
            if not straddles:
                continue

            n_before = len(bm.verts)

            plane_co = [0.0, 0.0, 0.0]
            plane_co[axis_idx] = val

            bmesh.ops.bisect_plane(
                bm,
                geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                dist=0.0,
                plane_co=tuple(plane_co),
                plane_no=plane_no,
                use_snap_center=False,
                clear_outer=False,
                clear_inner=False,
            )

            bm.verts.ensure_lookup_table()
            new_verts = len(bm.verts) - n_before
            total_new += new_verts

            if new_verts:
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_tol)
                bm.verts.ensure_lookup_table()
                bm.edges.ensure_lookup_table()
                bm.faces.ensure_lookup_table()

    return total_new


def _delete_duplicate_faces(bm: bmesh.types.BMesh, precision: int = 5) -> int:
    bm.faces.ensure_lookup_table()
    seen: dict[tuple[tuple[float, float, float], ...], bmesh.types.BMFace] = {}
    duplicates: list[bmesh.types.BMFace] = []
    for face in bm.faces:
        key = tuple(sorted(
            (round(v.co.x, precision), round(v.co.y, precision), round(v.co.z, precision))
            for v in face.verts
        ))
        if key in seen:
            duplicates.append(face)
        else:
            seen[key] = face
    if duplicates:
        bmesh.ops.delete(bm, geom=duplicates, context="FACES")
        bm.faces.ensure_lookup_table()
    return len(duplicates)


def _remove_double_triangulations(bm: bmesh.types.BMesh) -> int:
    """Post-triangulation: find 4-vertex rectangles covered by two full triangulations
    (4 triangles, two different diagonals) and remove one pair.

    Arises when two overlapping hexagonal wall faces (back-to-back, opposite normals)
    each triangulate the shared rectangle region with a different diagonal, producing
    4 non-identical triangles and NM edges on all 4 outer edges of the rectangle.
    Called after recalc_face_normals + _delete_duplicate_faces so that any truly
    identical triangles are already gone before we look for structural duplicates.
    Returns the number of triangle faces removed."""
    from collections import defaultdict

    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    quad_pairs: dict = defaultdict(list)

    for e in bm.edges:
        tris = [f for f in e.link_faces if len(f.verts) == 3]
        if len(tris) != 2:
            continue
        f1, f2 = tris
        all_verts = frozenset(v.index for v in f1.verts) | frozenset(v.index for v in f2.verts)
        if len(all_verts) == 4:
            edge_key = frozenset(v.index for v in e.verts)
            quad_pairs[all_verts].append((f1, f2, edge_key))

    to_delete: list = []
    for quad_verts, pairs in quad_pairs.items():
        if len(pairs) < 2:
            continue
        seen_edges: set = set()
        unique_pairs = []
        for f1, f2, ek in pairs:
            if ek not in seen_edges:
                seen_edges.add(ek)
                unique_pairs.append((f1, f2))
        if len(unique_pairs) < 2:
            continue
        # Keep the first pair; delete the second (arbitrary — both cover same area)
        f1, f2 = unique_pairs[-1]
        if f1.is_valid and f2.is_valid:
            to_delete.extend([f1, f2])

    if to_delete:
        valid = [f for f in to_delete if f.is_valid]
        if valid:
            bmesh.ops.delete(bm, geom=valid, context="FACES")
            bm.faces.ensure_lookup_table()

    return len(to_delete)


def _fix_overlapping_vertical_walls(
    bm: bmesh.types.BMesh,
    normal_tol: float = 0.85,
    plane_tol: float = 5e-3,
) -> int:
    """Replace groups of overlapping coplanar axis-aligned wall faces with their 2D union.

    Adjacent buildings whose walls lie in the same plane generate overlapping
    quad faces.  After T-junction insertion those quads share sub-edges and
    after triangulation those sub-edges are shared by 3+ triangles (non-manifold).

    This function runs BEFORE any T-junction fixing.  For each group of
    co-planar, same-direction, axis-aligned wall faces whose bounding boxes
    overlap in 2D, it:

    1. Computes the 2D union of all bounding boxes using coordinate compression
       (valid because building walls are axis-aligned rectangles).
    2. Deletes the original faces (keeps edges/verts so neighbors stay valid).
    3. Reconstructs non-overlapping quad faces for each compressed grid cell
       that belongs to the union, reusing existing vertices where possible.

    The resulting cells may introduce T-junctions on adjacent floor/ceiling
    faces (new intermediate vertices on existing floor edges).  The subsequent
    ``_fix_t_junctions_targeted`` pass resolves those automatically.

    Only handles axis-aligned vertical faces (|n.x| >= normal_tol OR
    |n.y| >= normal_tol, |n.z| < normal_tol).  Non-rectangular faces or faces
    on non-axis-aligned planes are left untouched.

    Returns the number of wall-plane groups that were rebuilt.
    """
    from collections import defaultdict
    from mathutils import Vector

    bm.faces.ensure_lookup_table()
    bm.normal_update()

    # ── 1. Group faces by (axis, plane_coord_key, normal_sign) ──────────────
    plane_groups: dict[tuple, list] = defaultdict(list)

    for face in bm.faces:
        n = face.normal.normalized()
        if abs(n.z) >= normal_tol:
            continue  # horizontal — handled by _union_horizontal_faces
        nx_abs, ny_abs = abs(n.x), abs(n.y)
        if nx_abs >= normal_tol:
            axis = "x"
            sign = 1 if n.x > 0 else -1
            pos = sum(v.co.x for v in face.verts) / len(face.verts)
        elif ny_abs >= normal_tol:
            axis = "y"
            sign = 1 if n.y > 0 else -1
            pos = sum(v.co.y for v in face.verts) / len(face.verts)
        else:
            continue  # diagonal wall — skip
        pos_key = round(pos / plane_tol)
        plane_groups[(axis, pos_key, sign)].append(face)

    fixed_groups = 0

    for (axis, pos_key, sign), faces in plane_groups.items():
        if len(faces) < 2:
            continue

        # ── 2. Project each face to 2D bounding box ──────────────────────────
        def _to_2d(v: bmesh.types.BMVert) -> tuple[float, float]:
            return (v.co.y, v.co.z) if axis == "x" else (v.co.x, v.co.z)

        boxes: list[tuple[float, float, float, float]] = []
        for face in faces:
            pts = [_to_2d(v) for v in face.verts]
            u_vals = [p[0] for p in pts]
            z_vals = [p[1] for p in pts]
            boxes.append((min(u_vals), max(u_vals), min(z_vals), max(z_vals)))

        # ── 3. Check for actual area overlap (not just touching) ──────────────
        _EPS = 1e-4
        has_overlap = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if (
                    a[0] < b[1] - _EPS and b[0] < a[1] - _EPS
                    and a[2] < b[3] - _EPS and b[2] < a[3] - _EPS
                ):
                    has_overlap = True
                    break
            if has_overlap:
                break

        if not has_overlap:
            continue

        # ── 4. Coordinate-compression 2D union ───────────────────────────────
        u_coords = sorted({round(b[0], 5) for b in boxes} | {round(b[1], 5) for b in boxes})
        z_coords = sorted({round(b[2], 5) for b in boxes} | {round(b[3], 5) for b in boxes})

        union_cells: list[tuple[float, float, float, float]] = []
        for ui in range(len(u_coords) - 1):
            u_lo, u_hi = u_coords[ui], u_coords[ui + 1]
            u_mid = (u_lo + u_hi) * 0.5
            for zi in range(len(z_coords) - 1):
                z_lo, z_hi = z_coords[zi], z_coords[zi + 1]
                z_mid = (z_lo + z_hi) * 0.5
                covered = any(
                    b[0] - _EPS <= u_mid <= b[1] + _EPS
                    and b[2] - _EPS <= z_mid <= b[3] + _EPS
                    for b in boxes
                )
                if covered:
                    union_cells.append((u_lo, u_hi, z_lo, z_hi))

        # Skip if no actual area overlap (touching quads produce same cells)
        union_area = sum((c[1] - c[0]) * (c[3] - c[2]) for c in union_cells)
        orig_area = sum((b[1] - b[0]) * (b[3] - b[2]) for b in boxes)
        if orig_area - union_area < _EPS * _EPS:
            continue

        # ── 5. Build vertex lookup from existing face/neighbor vertices ───────
        plane_coord = sum(
            (v.co.x if axis == "x" else v.co.y)
            for f in faces
            for v in f.verts
        ) / sum(len(f.verts) for f in faces)

        vert_map: dict[tuple[float, float], bmesh.types.BMVert] = {}
        group_ids = {id(f) for f in faces}

        def _add_vert(v: bmesh.types.BMVert) -> None:
            u, z = _to_2d(v)
            key = (round(u, 4), round(z, 4))
            vert_map.setdefault(key, v)

        for f in faces:
            for v in f.verts:
                _add_vert(v)
            # Also harvest vertices from neighboring (non-group) faces that sit
            # on this same plane (floor/ceiling verts at the wall base/top).
            for e in f.edges:
                for lf in e.link_faces:
                    if id(lf) not in group_ids:
                        for v in lf.verts:
                            if axis == "x":
                                on_plane = abs(v.co.x - plane_coord) < 1e-3
                            else:
                                on_plane = abs(v.co.y - plane_coord) < 1e-3
                            if on_plane:
                                _add_vert(v)

        # Capture material index from first face for new faces.
        mat_idx = faces[0].material_index if faces else 0

        # ── 6. Delete original faces (keep edges/verts) ───────────────────────
        bmesh.ops.delete(bm, geom=faces, context="FACES_ONLY")

        # ── 7. Create replacement non-overlapping quad cells ─────────────────
        def _get_or_make_vert(u: float, z: float) -> bmesh.types.BMVert:
            key = (round(u, 4), round(z, 4))
            if key in vert_map:
                return vert_map[key]
            if axis == "x":
                co = Vector((plane_coord, u, z))
            else:
                co = Vector((u, plane_coord, z))
            new_v = bm.verts.new(co)
            vert_map[key] = new_v
            return new_v

        new_faces_count = 0
        for (u_lo, u_hi, z_lo, z_hi) in union_cells:
            v00 = _get_or_make_vert(u_lo, z_lo)
            v10 = _get_or_make_vert(u_hi, z_lo)
            v11 = _get_or_make_vert(u_hi, z_hi)
            v01 = _get_or_make_vert(u_lo, z_hi)

            if len({id(v00), id(v10), id(v11), id(v01)}) < 3:
                continue  # degenerate cell

            # Winding order: positive-normal faces are CCW when viewed from
            # outside (positive normal direction).
            # x-axis walls:  +x = CCW in +Y/+Z plane  → (v00, v10, v11, v01)
            #                -x = CCW in -Y/+Z plane  → reversed
            # y-axis walls:  +y = CCW in -X/+Z plane  → (v00, v01, v11, v10)
            #                -y = CCW in +X/+Z plane  → reversed
            if axis == "x":
                loop = [v00, v10, v11, v01] if sign > 0 else [v00, v01, v11, v10]
            else:
                loop = [v00, v01, v11, v10] if sign > 0 else [v00, v10, v11, v01]

            try:
                new_face = bm.faces.new(loop)
                new_face.material_index = mat_idx
                new_faces_count += 1
            except ValueError:
                pass  # edge already exists with opposite winding — skip

        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.normal_update()

        print(
            f"[naranjos-dsl] Wall overlap fix {axis}={plane_coord:.3f} "
            f"sign={sign:+d}: {len(faces)} faces → {new_faces_count} cells",
            flush=True,
        )
        fixed_groups += 1

    return fixed_groups


def _fix_t_junctions_targeted(
    bm: bmesh.types.BMesh,
    tol: float = _TJUNCTION_TOL,
) -> int:
    """Fix T-junctions by splitting edges at exact T-junction vertex positions.

    Unlike ``_fix_t_junctions_by_z_split`` (which uses ``bisect_plane`` on the
    whole mesh and creates new T-junctions on newly-inserted edges), this
    function:

    1. Runs **one** O(E × V) NumPy scan to find every (edge, vertex, t)
       T-junction triple — where ``vertex`` lies on ``edge`` at parameter ``t``.
    2. Groups triples by edge and sorts by ``t`` (ascending from verts[0]).
    3. For each edge with ≤ 2 link_faces (manifold or boundary):
       calls ``bmesh.utils.edge_split(edge, edge.verts[0], t)`` and immediately
       merges the new split vertex with the pre-existing T-junction vertex via
       ``bmesh.ops.pointmerge``.  Multiple T-junctions on the same edge are
       handled in one loop with adjusted ``t`` fractions.
    4. Non-manifold edges (3+ link_faces) are skipped — they are handled by
       ``_fix_t_junctions_nonmanifold`` using a local ``bisect_plane``.

    Returns the number of successful edge splits.
    """
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    verts = list(bm.verts)
    n = len(verts)
    if n < 3 or not bm.edges:
        return 0

    # Build positional arrays once
    vco = np.array([[v.co.x, v.co.y, v.co.z] for v in verts], dtype=np.float64)
    all_rows = np.arange(n, dtype=np.int64)
    vert_to_row = {v: i for i, v in enumerate(verts)}

    # Map: edge → [(t, existing_vert), ...]
    edge_splits: dict[bmesh.types.BMEdge, list[tuple[float, bmesh.types.BMVert]]] = {}

    for edge in bm.edges:
        if len(edge.link_faces) > 2:
            # Non-manifold (3+ faces): handled by _fix_t_junctions_nonmanifold
            continue
        # Process manifold (2), boundary (1), and wire (0) edges with edge_split
        ia = vert_to_row[edge.verts[0]]
        ib = vert_to_row[edge.verts[1]]
        v1 = vco[ia]
        ev = vco[ib] - v1
        el2 = float(ev @ ev)
        if el2 < 1e-12:
            continue

        mask = (all_rows != ia) & (all_rows != ib)
        rows = all_rows[mask]
        t = (vco[mask] - v1) @ ev / el2
        in_range = (t > 1e-6) & (t < 1.0 - 1e-6)
        if not in_range.any():
            continue

        candidate_rows = rows[in_range]
        candidate_t = t[in_range]
        proj = v1 + candidate_t[:, np.newaxis] * ev
        dist = np.linalg.norm(vco[candidate_rows] - proj, axis=1)
        hits = np.where(dist < tol)[0]
        if not hits.size:
            continue

        triples = [
            (float(candidate_t[h]), verts[int(candidate_rows[h])])
            for h in hits
        ]
        triples.sort(key=lambda x: x[0])
        edge_splits[edge] = triples

    if not edge_splits:
        return 0

    print(
        f"[naranjos-dsl] T-junction targeted fix: {len(edge_splits)} manifold edge(s) to split, "
        f"{sum(len(v) for v in edge_splits.values())} total T-junction(s)",
        flush=True,
    )

    fixed = 0
    skipped = 0
    for edge, triples in edge_splits.items():
        try:
            # Validate edge handle is still alive
            _ = edge.verts[0]
        except ReferenceError:
            skipped += 1
            continue

        # KEY INSIGHT: after `edge_split(edge, edge.verts[0], t)`, the Python
        # `edge` object is MODIFIED IN PLACE to become the REMAINING portion
        # (new_vert → verts[1]).  `new_edge` is the first portion (verts[0] →
        # new_vert).  We KEEP using `edge` — it correctly advances through the
        # remaining sub-edge after each split, and `edge.verts[0]` is updated
        # to the last split-vertex so `local_t` stays in [0,1].
        # We also use `weld_verts` instead of `pointmerge` so the pre-existing
        # T-junction vertex ALWAYS survives (deterministic; new_vert dissolved).
        t_done = 0.0  # t on original edge at the last split point
        for orig_t, existing_vert in triples:
            remaining_span = 1.0 - t_done
            if remaining_span < 1e-9:
                break
            local_t = (orig_t - t_done) / remaining_span
            if not (1e-6 < local_t < 1.0 - 1e-6):
                continue

            try:
                _new_edge, new_vert = bmesh.utils.edge_split(
                    edge, edge.verts[0], local_t
                )
                # Weld new_vert → existing_vert so the pre-existing vertex
                # survives.  After this, `edge.verts[0]` is `existing_vert`.
                bmesh.ops.weld_verts(bm, targetmap={new_vert: existing_vert})
                t_done = orig_t
                fixed += 1
            except (ReferenceError, ValueError):
                # edge_split can fail when the edge has unusual topology
                # (e.g. caused by a previous weld collapsing a neighbour).
                # Fallback: local bisect_plane restricted to adjacent faces only.
                try:
                    from mathutils import Vector  # noqa: PLC0415
                    adj_faces = list(edge.link_faces)
                    if adj_faces:
                        va_co = Vector(edge.verts[0].co)
                        vb_co = Vector(edge.verts[1].co)
                        ev_vec = vb_co - va_co
                        adj_v = {v for f in adj_faces for v in f.verts}
                        adj_e = {e for f in adj_faces for e in f.edges}
                        bmesh.ops.bisect_plane(
                            bm,
                            geom=list(adj_v) + list(adj_e) + adj_faces,
                            plane_co=existing_vert.co,
                            plane_no=ev_vec.normalized(),
                            use_snap_center=False,
                            clear_outer=False,
                            clear_inner=False,
                        )
                        bm.verts.ensure_lookup_table()
                        bmesh.ops.remove_doubles(
                            bm, verts=bm.verts, dist=tol * 10
                        )
                        fixed += 1
                except Exception:
                    skipped += 1
                # Can't safely continue inner loop after bisect (edge invalid)
                break

    print(
        f"[naranjos-dsl] T-junction targeted fix done: "
        f"fixed={fixed}, skipped={skipped}",
        flush=True,
    )
    return fixed


def _fix_t_junctions_nonmanifold(
    bm: bmesh.types.BMesh,
    tol: float = _TJUNCTION_TOL,
    max_iters: int = 20,
) -> int:
    """Fix T-junctions that lie on non-manifold edges (3+ link_faces).

    ``bmesh.utils.edge_split`` only works on manifold edges.  For edges shared
    by 3 or more faces we use a **local** ``bisect_plane`` restricted to only
    the faces adjacent to that edge.  This inserts a new vertex on the edge at
    the T-junction position without touching unrelated geometry — avoiding the
    T-junction proliferation that a global bisect causes.

    One T-junction per non-manifold edge is resolved per iteration; the loop
    repeats until the mesh is clean or *max_iters* is reached.

    Returns the total number of bisect operations performed.
    """
    from mathutils import Vector  # local import — bmesh scripts only

    total_fixed = 0

    for iteration in range(max_iters):
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        verts = list(bm.verts)
        n = len(verts)
        if n < 3:
            break

        vco = np.array([[v.co.x, v.co.y, v.co.z] for v in verts], dtype=np.float64)
        all_rows = np.arange(n, dtype=np.int64)
        vert_to_row: dict[bmesh.types.BMVert, int] = {v: i for i, v in enumerate(verts)}

        # Collect the FIRST T-junction per non-manifold edge to avoid
        # invalidating edge handles mid-loop.
        edge_first_tj: dict[
            bmesh.types.BMEdge,
            tuple[float, bmesh.types.BMVert],
        ] = {}

        for edge in bm.edges:
            if len(edge.link_faces) <= 2:      # manifold or boundary — skip
                continue
            ia = vert_to_row.get(edge.verts[0])
            ib = vert_to_row.get(edge.verts[1])
            if ia is None or ib is None:
                continue
            v1 = vco[ia]
            ev_arr = vco[ib] - v1
            el2 = float(ev_arr @ ev_arr)
            if el2 < 1e-12:
                continue

            mask = (all_rows != ia) & (all_rows != ib)
            rows = all_rows[mask]
            t = (vco[mask] - v1) @ ev_arr / el2
            in_range = (t > 1e-6) & (t < 1.0 - 1e-6)
            if not in_range.any():
                continue

            candidate_rows = rows[in_range]
            candidate_t = t[in_range]
            proj = v1 + candidate_t[:, np.newaxis] * ev_arr
            dist = np.linalg.norm(vco[candidate_rows] - proj, axis=1)
            hits = np.where(dist < tol)[0]
            if not hits.size:
                continue

            # Pick the T-junction closest to verts[0] to stay numerically stable
            min_idx = int(np.argmin(candidate_t[hits]))
            h = hits[min_idx]
            edge_first_tj[edge] = (
                float(candidate_t[h]),
                verts[int(candidate_rows[h])],
            )

        if not edge_first_tj:
            print(
                f"[naranjos-dsl] NM T-junction fix: converged after "
                f"{iteration} iteration(s), total bisects={total_fixed}",
                flush=True,
            )
            break

        iter_fixed = 0
        for edge, (_t_val, existing_vert) in edge_first_tj.items():
            try:
                va_co = Vector(edge.verts[0].co)
                vb_co = Vector(edge.verts[1].co)
                adj_faces = list(edge.link_faces)
            except ReferenceError:
                continue

            if not adj_faces:
                continue

            adj_verts_set: set[bmesh.types.BMVert] = {
                v for f in adj_faces for v in f.verts
            }
            adj_edges_set: set[bmesh.types.BMEdge] = {
                e for f in adj_faces for e in f.edges
            }
            geom = list(adj_verts_set) + list(adj_edges_set) + adj_faces

            ev_vec = vb_co - va_co
            try:
                bmesh.ops.bisect_plane(
                    bm,
                    geom=geom,
                    plane_co=existing_vert.co,
                    plane_no=ev_vec.normalized(),
                    use_snap_center=False,
                    clear_outer=False,
                    clear_inner=False,
                )
                iter_fixed += 1
            except Exception:
                pass

        if iter_fixed:
            bm.verts.ensure_lookup_table()
            # Use a slightly larger tolerance so the new bisect vertex snaps
            # onto the T-junction vertex even with floating-point noise.
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=tol * 10)
            total_fixed += iter_fixed
            print(
                f"[naranjos-dsl] NM T-junction fix iter {iteration + 1}: "
                f"bisected {iter_fixed} edge(s), total={total_fixed}",
                flush=True,
            )
        else:
            print(
                f"[naranjos-dsl] NM T-junction fix: no progress at iter "
                f"{iteration + 1}, stopping (total={total_fixed})",
                flush=True,
            )
            break

    return total_fixed


def _union_horizontal_faces(
    bm: bmesh.types.BMesh,
    normal_z_tol: float = 0.9,
    z_precision: int = 3,
) -> int:
    """Replace every coplanar group of horizontal faces with its outer-boundary fill.

    Adjacent buildings generate independent ceiling / floor slabs at the same Z.
    Those slabs create non-manifold edges and coplanar-overlapping faces.

    1. Group nearly-horizontal faces (|n.z| ≥ normal_z_tol) by Z level.
    2. Find outer boundary edges (exactly 1 face in the group).
    3. Delete all faces in the group.
    4. Re-fill with ``holes_fill`` to produce a single boundary fill.
    5. Delete nested inner fills (courtyards / stairwells) via centroid
       point-in-polygon test so level.py can seal them as +portal faces.

    Returns the number of Z-levels processed.
    """
    from collections import defaultdict

    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.normal_update()

    # Group horizontal faces by rounded Z of their first vertex.
    z_groups: dict[float, list] = defaultdict(list)
    for face in bm.faces:
        n = face.normal.normalized()
        if abs(n.z) < normal_z_tol:
            continue
        z = round(face.verts[0].co.z, z_precision)
        z_groups[z].append(face)

    def _pt_in_poly(pt, poly):
        """Ray-casting 2-D point-in-polygon test."""
        x, y = pt
        inside = False
        j = len(poly) - 1
        for i in range(len(poly)):
            xi, yi = poly[i]; xj, yj = poly[j]
            if ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / (yj - yi) + xi
            ):
                inside = not inside
            j = i
        return inside

    levels_done = 0
    for z_key, faces in z_groups.items():
        if len(faces) < 2:
            continue  # single face — nothing to merge

        face_set = set(id(f) for f in faces)

        # Outer boundary edges: used by exactly ONE face in this group.
        outer_edges: list = []
        for face in faces:
            for edge in face.edges:
                group_adj = sum(1 for lf in edge.link_faces if id(lf) in face_set)
                if group_adj == 1:
                    outer_edges.append(edge)

        if not outer_edges:
            continue

        print(
            f"[naranjos-dsl] Horizontal union z={z_key}: "
            f"{len(faces)} faces → {len(outer_edges)} boundary edges",
            flush=True,
        )

        # Delete every face in the group.
        bmesh.ops.delete(bm, geom=list(faces), context="FACES")

        # Re-fill closed boundary loops with new polygon face(s).
        bm.edges.ensure_lookup_table()
        valid_edges = [e for e in outer_edges if e.is_valid]
        n_new = 0
        if valid_edges:
            result = bmesh.ops.holes_fill(bm, edges=valid_edges, sides=0)
            new_faces = result.get("faces", [])
            n_new = len(new_faces)

            # Detect and delete nested inner fill faces.
            if n_new > 1:
                areas = [f.calc_area() for f in new_faces]
                proj  = [[(v.co.x, v.co.y) for v in f.verts] for f in new_faces]
                order = sorted(range(n_new), key=lambda i: -areas[i])

                nested_inners: set = set()
                for b_idx in range(n_new):
                    cx = sum(p[0] for p in proj[b_idx]) / len(proj[b_idx])
                    cy = sum(p[1] for p in proj[b_idx]) / len(proj[b_idx])
                    for a_idx in order:
                        if a_idx == b_idx or areas[a_idx] <= areas[b_idx]:
                            continue
                        if _pt_in_poly((cx, cy), proj[a_idx]):
                            nested_inners.add(b_idx)
                            break

                if nested_inners:
                    inner_fills = [
                        new_faces[i] for i in nested_inners
                        if new_faces[i].is_valid
                    ]
                    bmesh.ops.delete(bm, geom=inner_fills, context="FACES")
                    n_new -= len(inner_fills)
                    print(
                        f"[naranjos-dsl] Horizontal union z={z_key}: "
                        f"deleted {len(inner_fills)} nested inner fill(s) "
                        f"(boundary edges sealed as portals by level.py)",
                        flush=True,
                    )

        print(
            f"[naranjos-dsl] Horizontal union z={z_key}: re-filled → {n_new} face(s)",
            flush=True,
        )
        levels_done += 1

    return levels_done


def _remove_interior_faces(obj: bpy.types.Object) -> int:
    """Delete faces buried inside the solid using Blender's interior-face select.

    The staircases (and back-to-back walls) are built as separate solid boxes
    that abut.  Where two solids touch, their contact faces become *interior* —
    buried inside the combined volume.  After the global vertex weld these
    buried faces are what create the 3-way (non-manifold) edges: an interior
    riser / abutment face shares an edge with two surface faces.

    ``mesh.select_interior_faces`` is Blender's purpose-built detector for
    exactly this situation (faces enclosed by solid on both sides).  Removing
    them turns each cluster of abutting boxes into a clean manifold shell.

    Returns the number of faces removed.
    """
    n_before = len(obj.data.polygons)

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.select_interior_faces()
    bpy.ops.mesh.delete(type="FACE")
    bpy.ops.object.mode_set(mode="OBJECT")

    return n_before - len(obj.data.polygons)


def _create_merged_bsp(
    objects: list[bpy.types.Object],
    name: str = "bsp_merged",
) -> bpy.types.Object | None:
    """Bake generated BSP parts into one cleaned, triangulated mesh object."""
    source_meshes: list[bpy.types.Mesh] = []
    bm = bmesh.new()

    for obj in objects:
        mesh = _bake_object_mesh_world(obj)
        if mesh is None:
            continue
        source_meshes.append(mesh)
        bm.from_mesh(mesh)

    if not bm.faces:
        bm.free()
        for mesh in source_meshes:
            bpy.data.meshes.remove(mesh)
        return None

    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    before_v = len(bm.verts)
    before_f = len(bm.faces)

    # Cleanup + merge vertices.
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=MERGE_DISTANCE_BU)
    dup_faces = _delete_duplicate_faces(bm)

    # ── Union coplanar horizontal face groups ────────────────────────────────
    # Adjacent buildings generate independent ceiling/floor slabs at the same Z.
    # Those slabs create non-manifold edges and coplanar-overlapping faces.
    # Replace every coplanar group with its outer boundary fill.
    n_union_levels = _union_horizontal_faces(bm)
    if n_union_levels:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)

    # ── Fix overlapping vertical wall panels ─────────────────────────────────
    # Adjacent buildings whose walls share the same axis-aligned plane (same X
    # or Y coordinate) produce overlapping quad faces.  After T-junction insertion
    # those quads develop shared sub-edges; after triangulation those sub-edges
    # are shared by 3+ triangles → non-manifold.  Replace each overlapping group
    # with a 2D-union decomposition (coordinate-compression grid) of
    # non-overlapping quad cells BEFORE any T-junction fixing so the mesh stays
    # clean throughout the rest of the pipeline.
    n_wall_fixed = _fix_overlapping_vertical_walls(bm)
    if n_wall_fixed:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        bm.faces.ensure_lookup_table()

    # Light retopology before final triangulation: dissolve tiny collinear runs.
    try:
        bmesh.ops.dissolve_limit(
            bm,
            angle_limit=0.001,
            verts=bm.verts,
            edges=bm.edges,
            delimit={"NORMAL"},
        )
    except TypeError:
        pass

    # ── T-junction fix pass 1: targeted split on manifold + boundary edges ──
    # One O(E×V) NumPy scan collects all (edge, vert, t) T-junction triples.
    # Splits edges with ≤ 2 link_faces (manifold + boundary) at exact T-junction
    # positions, in increasing-t order, without touching unrelated geometry.
    # This avoids the bisect_plane proliferation problem (global bisect cuts the
    # whole mesh at a plane, creating new T-junctions on every inserted edge).
    fixed_t_z = _fix_t_junctions_targeted(bm)
    if fixed_t_z:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)

    # ── T-junction fix pass 2: local bisect on non-manifold edges ────────────
    # Non-manifold edges (3+ faces) can't be split with edge_split; we use a
    # local bisect_plane restricted to adjacent faces only (no proliferation).
    fixed_t_nm = _fix_t_junctions_nonmanifold(bm)
    if fixed_t_nm:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)

    # ── Remove back-to-back faces before triangulation ───────────────────────
    # After T-junction fixes align the boundaries of adjacent buildings' walls,
    # the overlapping wall regions now have exact-duplicate quad faces pointing
    # opposite directions.  A second recalc aligns them, then a duplicate check
    # removes one layer before triangulate introduces different diagonals that
    # would make them non-identical and harder to detect.
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    dup_pre_tri = _delete_duplicate_faces(bm)
    if dup_pre_tri:
        print(
            f"[naranjos-dsl] Pre-tri back-to-back faces removed: {dup_pre_tri}"
            f" ({len(bm.faces)} faces remaining, recalc→dup pass 1/3)",
            flush=True,
        )
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        bm.faces.ensure_lookup_table()
        # One more T-junction pass: removing back-to-back faces may expose
        # T-junctions that were hidden behind the duplicate layer.
        _fix_t_junctions_targeted(bm)
        _fix_t_junctions_nonmanifold(bm)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        bm.faces.ensure_lookup_table()
        # The bisect in the NM pass above creates new faces with arbitrary
        # normals — some will be anti-canonical duplicates of the newly-exposed
        # canonical faces.  A second recalc + duplicate removal is essential so
        # that triangulation never sees two quads covering the same rectangle
        # with opposite windings (which would produce two different diagonals
        # and therefore 4 non-identical triangles that escape all later checks).
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        dup_post_exposed = _delete_duplicate_faces(bm)
        if dup_post_exposed:
            print(
                f"[naranjos-dsl] Post-exposure recalc: removed {dup_post_exposed} duplicate(s)"
                f" ({len(bm.faces)} faces remaining, recalc→dup pass 2/3)",
                flush=True,
            )
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
            bm.faces.ensure_lookup_table()

    # ── Unconditional pre-triangulation clean-up ──────────────────────────────
    # Any T-junction bisect runs (passes 1-2 + optional extra pass) can create
    # anti-canonical faces.  The conditional block above may not have run if
    # dup_pre_tri was 0.  Performing one final recalc + duplicate removal here
    # guarantees that no two quads with identical vertex positions survive into
    # triangulation — where they would receive different diagonals and become
    # four non-identical triangles that escape all later duplicate checks.
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    dup_pre_tri2 = _delete_duplicate_faces(bm)
    if dup_pre_tri2:
        print(
            f"[naranjos-dsl] Pre-tri unconditional clean-up: removed {dup_pre_tri2} duplicate(s)"
            f" ({len(bm.faces)} faces remaining, recalc→dup pass 3/3)",
            flush=True,
        )
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        bm.faces.ensure_lookup_table()

    # ── Triangulate ───────────────────────────────────────────────────────────
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
    bm.normal_update()

    # ── T-junction fix pass 3: post-triangulation targeted split ─────────────
    # Triangulation adds diagonal edges across faces.  Those new diagonals can
    # have existing vertices lying on them, creating fresh T-junctions.
    # A second targeted pass on the all-triangle mesh fixes both these new
    # T-junctions and any that were on non-manifold edges pre-triangulation but
    # are now effectively manifold (triangle meshes tend to be more manifold).
    fixed_t_post = _fix_t_junctions_targeted(bm)
    if fixed_t_post:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)

    # ── T-junction fix pass 4: post-triangulation NM bisect ──────────────────
    fixed_t_nm_post = _fix_t_junctions_nonmanifold(bm)
    if fixed_t_nm_post:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        bm.normal_update()

    # ── T-junction fix pass 5: second post-triangulation sweep ───────────────
    # Some edge handles are invalidated by the weld_verts calls in pass 3
    # (a weld on one edge can collapse a neighbour edge).  A fresh O(E×V) scan
    # re-discovers those T-junctions on their now-valid edges and fixes them.
    fixed_t_post2 = _fix_t_junctions_targeted(bm)
    if fixed_t_post2:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)

    # ── Legacy iterative pass (disabled — no-op) ─────────────────────────────
    fixed_t = _fix_t_junctions(bm)
    if fixed_t:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)

    # ── Post-triangulation duplicate face removal ─────────────────────────────
    # After T-junction fixes split tall-building wall edges, the resulting
    # sub-faces can be identical (same vertex positions) to shorter adjacent
    # buildings' walls.  Removing them here reduces non-manifold edge count.
    dup_post = _delete_duplicate_faces(bm)
    if dup_post:
        print(
            f"[naranjos-dsl] Post-tri duplicate faces removed: {dup_post}"
            f" ({len(bm.faces)} faces remaining, post-tri dup pass)",
            flush=True,
        )
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)

    # ── Re-triangulate ngons created by post-tri NM bisect (iterative) ───────
    # _fix_t_junctions_nonmanifold uses bisect_plane which can turn a triangle
    # into a triangle + quad.  Those quads would generate NEW non-manifold edges
    # when level.py re-triangulates them (the new diagonal could land on an
    # existing vertex).  Triangulate them now so bsp_merged is fully triangulated.
    # Triangulating may expose new T-junctions from the new diagonal edges, so
    # run one final T-junction pass after each re-triangulation, then loop until
    # the mesh is stable (no remaining ngons and no new T-junctions).
    for _retri_pass in range(5):
        bm.faces.ensure_lookup_table()
        non_tris = [f for f in bm.faces if len(f.verts) > 3]
        if not non_tris:
            break
        print(
            f"[naranjos-dsl] Re-tri pass {_retri_pass + 1}/5: "
            f"{len(non_tris)} ngon(s) → triangulating"
            f" ({len(bm.faces)} faces total before this pass)",
            flush=True,
        )
        bmesh.ops.triangulate(bm, faces=non_tris)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        bm.normal_update()
        # Fix T-junctions that the new diagonals may have created.
        n_tj_retri = _fix_t_junctions_targeted(bm)
        if n_tj_retri:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        n_nm_retri = _fix_t_junctions_nonmanifold(bm)
        if n_nm_retri:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        print(
            f"[naranjos-dsl] Re-tri pass {_retri_pass + 1}/5: done"
            f" (tj={n_tj_retri} nm={n_nm_retri} → {len(bm.faces)} faces)",
            flush=True,
        )
        if not n_tj_retri and not n_nm_retri:
            # No new T-junctions introduced — any remaining ngons will be stable.
            bm.faces.ensure_lookup_table()
            remaining = [f for f in bm.faces if len(f.verts) > 3]
            if remaining:
                bmesh.ops.triangulate(bm, faces=remaining)
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
            break

    # ── Final recalc: eliminate anti-canonical faces created by bisect_plane ─
    # _fix_t_junctions_nonmanifold uses bisect_plane which creates new faces
    # whose normals are arbitrary and may point anti-canonical (opposite to the
    # face they split).  Those anti-canonical faces survive _delete_duplicate_faces
    # (which only removes exact positional duplicates) and become the source of
    # the 91+ anti-parallel NM edges seen in bsp_merged.
    # A final recalc_face_normals flips all faces to the canonical outward
    # direction so that any two faces covering the same triangle now have
    # identical vertex-position signatures and _delete_duplicate_faces removes
    # the extra copy.
    bm.faces.ensure_lookup_table()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    dup_final = _delete_duplicate_faces(bm)
    if dup_final:
        print(
            f"[naranjos-dsl] Final recalc: removed {dup_final} anti-canonical bisect face(s)"
            f" ({len(bm.faces)} faces remaining)",
            flush=True,
        )
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DISTANCE_BU)
        bm.faces.ensure_lookup_table()

    # ── Double-triangulation removal ──────────────────────────────────────────
    # Two overlapping hexagonal wall faces (back-to-back, opposite normals) each
    # triangulate their shared overlap rectangle with a different diagonal, yielding
    # 4 non-identical triangles for the same rectangle → NM edges on all 4 outer
    # edges.  recalc + _delete_duplicate_faces above can't catch this because the
    # triangles are geometrically different (different diagonals).  This pass finds
    # any 4-vertex set covered by two full triangulations and removes one pair.
    # Double-triangulation fix disabled: created 150 extra boundary edges without
    # reducing NM count. Root cause: outer edges of doubly-triangulated rectangles
    # have exactly 2 faces (the two pairs), so deleting one pair leaves those edges
    # with 1 face (boundary). Needs a pre-triangulation fix instead.
    # dbl_removed = _remove_double_triangulations(bm)

    out_mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(out_mesh)
    bm.free()
    out_mesh.update(calc_edges=True)

    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    merged = bpy.data.objects.new(name, out_mesh)
    bpy.context.collection.objects.link(merged)
    _move_to_collection(merged, "BSP")

    # ── Remove interior (buried) faces from abutting solids ──────────────────
    # NM edges in bsp_merged come almost entirely from staircase boxes and
    # back-to-back walls abutting other solids: their contact faces are buried
    # inside the combined volume.  Delete them so each cluster becomes a clean
    # manifold shell (see _remove_interior_faces).
    def _count_nm(o):
        m = o.data
        m.calc_loop_triangles()
        from collections import Counter
        ec = Counter()
        for poly in m.polygons:
            vs = list(poly.vertices)
            for k in range(len(vs)):
                a, b = vs[k], vs[(k + 1) % len(vs)]
                ec[(min(a, b), max(a, b))] += 1
        return sum(1 for c in ec.values() if c > 2)

    nm_before = _count_nm(merged)
    n_interior = _remove_interior_faces(merged)
    if n_interior:
        bpy.context.view_layer.objects.active = merged
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=MERGE_DISTANCE_BU)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    nm_after = _count_nm(merged)
    print(
        f"[naranjos-dsl] Interior-face removal: deleted {n_interior} buried face(s); "
        f"NM edges {nm_before} → {nm_after}",
        flush=True,
    )

    for mesh in source_meshes:
        bpy.data.meshes.remove(mesh)

    for obj in objects:
        if obj.name != merged.name:
            obj.hide_viewport = True
            obj.hide_render = True

    print(
        f"[naranjos-dsl] BSP merge cleanup: {len(objects)} object(s) → {name}; "
        f"verts {before_v}→{len(out_mesh.vertices)}, faces {before_f}→{len(out_mesh.polygons)}; "
        f"dup_faces={dup_faces}, tj_pre={fixed_t_z}, nm_pre={fixed_t_nm}, "
        f"tj_post={fixed_t_post}, nm_post={fixed_t_nm_post}, "
        f"tj_post2={fixed_t_post2}, triangulated=yes"
    )
    return merged


# ---------------------------------------------------------------------------
# Validators (on evaluated mesh)
# ---------------------------------------------------------------------------

def _check_t_intersections(bm: bmesh.types.BMesh) -> list[str]:
    """Return a list of T-intersection descriptions found in *bm*.

    A T-intersection occurs when a vertex lies exactly on an edge without
    being one of its endpoints.  In Halo CE's BSP compiler this produces
    a "degenerate surface" or split-edge error that prevents compilation.

    Uses NumPy for vectorised distance tests: O(E) Python loop with a
    fully-vectorised O(V) batch per edge instead of O(V × E) nested
    Python loops.  ~30-100× faster than the pure-Python version for
    typical map meshes (500–5 000 verts).
    """
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    n = len(bm.verts)
    if n < 3 or not bm.edges:
        return []

    verts = list(bm.verts)

    # Build vertex-position matrix (n, 3) and index array once.
    vco = np.empty((n, 3), dtype=np.float64)
    vidx = np.empty(n, dtype=np.int32)
    for i, v in enumerate(verts):
        vco[i, 0] = v.co.x
        vco[i, 1] = v.co.y
        vco[i, 2] = v.co.z
        vidx[i] = v.index

    # Map bmesh vertex index → row in vco
    bm_to_row: dict[int, int] = {int(vidx[i]): i for i in range(n)}

    all_rows = np.arange(n)   # base for endpoint mask (reused each edge)
    issues: list[str] = []

    for edge in bm.edges:
        ia = bm_to_row[edge.verts[0].index]
        ib = bm_to_row[edge.verts[1].index]

        v1 = vco[ia]
        ev = vco[ib] - v1
        el2 = float(ev @ ev)
        if el2 < 1e-12:
            continue

        # Boolean mask: exclude the two endpoint rows
        mask = (all_rows != ia) & (all_rows != ib)  # (n,) bool
        vco_m = vco[mask]                            # (m, 3)
        t = (vco_m - v1) @ ev / el2                 # (m,)

        in_range = (t > 0.0) & (t < 1.0)
        if not in_range.any():
            continue

        # Closest point on segment for all in-range vertices
        proj = v1 + t[in_range, np.newaxis] * ev    # (k, 3)
        dist = np.linalg.norm(vco_m[in_range] - proj, axis=1)  # (k,)

        hit = dist < _TJUNCTION_TOL
        if not hit.any():
            continue

        vidx_hit = vidx[mask][in_range][hit]
        for vi in vidx_hit:
            v = bm.verts[int(vi)]
            issues.append(
                f"v{vi} @ ({v.co.x:.4f},{v.co.y:.4f},{v.co.z:.4f})"
                f" on e{edge.index}"
            )

    return issues


def _validate_object(obj_name: str) -> dict[str, list[str]]:
    """Run BSP validators on the *evaluated* (GN-applied) mesh."""
    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        return {"error": [f"Object '{obj_name}' not found or not a mesh."]}

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    bm = bmesh.new()
    bm.from_mesh(eval_mesh)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    results: dict[str, list[str]] = {}

    # closed geometry
    boundary = [e for e in bm.edges if len(e.link_faces) < 2]
    results["closed_geometry"] = (
        [f"{len(boundary)} boundary edge(s)"]
        if boundary else []
    )

    # manifold edges
    non_manifold = [e for e in bm.edges if len(e.link_faces) != 2]
    results["manifold_edges"] = (
        [f"{len(non_manifold)} non-manifold edge(s)"]
        if non_manifold else []
    )

    # polygon budget
    face_count = len(bm.faces)
    results["polygon_budget"] = (
        [f"{face_count:,} faces (consider simplifying)"]
        if face_count > 10_000 else []
    )

    # normals
    degenerate = [f for f in bm.faces if f.normal.length < 1e-6]
    results["normals"] = (
        [f"{len(degenerate)} degenerate face(s)"]
        if degenerate else []
    )

    # T-intersections (vertex lying on an edge — BSP compiler error)
    t_issues = _check_t_intersections(bm)
    results["t_intersections"] = (
        [f"{len(t_issues)} T-intersection(s): " + "; ".join(t_issues[:5])
         + (" …" if len(t_issues) > 5 else "")]
        if t_issues else []
    )

    bm.free()
    eval_obj.to_mesh_clear()

    return results


def _validate_and_warn(obj_name: str, step: str) -> None:
    """Run T-intersection validation immediately after a mesh-editing step.

    Called during geometry creation so problems are reported at the point
    where they are introduced rather than only at the final validation pass.
    Other checks (manifold, budget, …) still run in the end-of-generation
    validation loop.
    """
    obj = bpy.data.objects.get(obj_name)
    if obj is None or obj.type != "MESH":
        return
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    t_issues = _check_t_intersections(bm)
    bm.free()
    if t_issues:
        preview = "; ".join(t_issues[:3]) + (" …" if len(t_issues) > 3 else "")
        print(
            f"[naranjos-dsl] WARNING [{step}] {obj_name}: "
            f"{len(t_issues)} T-intersection(s) — {preview}"
        )
    else:
        print(f"[naranjos-dsl] [{step}] {obj_name}: no T-intersections ✓")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_naranjos_dsl() -> None:
    """Generate Naranjos map volumes with parametric Geometry Nodes.

    Each building, hall, roof, and border gets a **live GN modifier** compiled from the
    Tanuki DSL.  Parameters (floor height, wall thickness, etc.) are baked
    into the node tree but can be adjusted by editing node values in Blender.
    """
    _t_start = time.perf_counter()
    buildings_data = _load_buildings()
    roofs_halls_data = _load_roofs_halls()
    border_data = _load_borders()
    doors_data = _load_doors()
    windows_data = _load_windows()

    print("[naranjos-dsl] Importing map.svg …", flush=True)
    _t_svg = time.perf_counter()
    svg_objects, label_map = _import_svg()
    print(f"[naranjos-dsl] SVG import done: {len(svg_objects)} objects in {time.perf_counter()-_t_svg:.1f}s", flush=True)

    if not svg_objects:
        print("[naranjos-dsl] ERROR: No objects imported from SVG.")
        return

    print(f"[naranjos-dsl] Imported {len(svg_objects)} SVG objects.")

    generated: list[bpy.types.Object] = []
    building_objects: dict[str, bpy.types.Object] = {}

    # ── buildings ─────────────────────────────────────────────────────────
    _t_bldg = time.perf_counter()
    for bldg in buildings_data:
        path_name = bldg["path_name"]
        curve = _find_curve(svg_objects, path_name, label_map)
        if curve is None:
            print(f"[naranjos-dsl] WARNING: no curve for '{path_name}' — skipped.")
            continue

        name = bldg["name"]
        num_floors = bldg.get("floor", 1)
        # Floor height comes from the brick-course count in buildings.json:
        # 6 cm per course, e.g. 38 courses × 6 cm = 2.28 m.
        bricks_h = bldg.get("meta", {}).get("bricks_h")
        if bricks_h:
            floor_height_m = floor_height_from_bricks(int(bricks_h))
            height_src = f"bricks_h={bricks_h} × {BRICK_COURSE_H_M:.2f} m"
        else:
            floor_height_m = float(bldg.get("floor_height", DEFAULT_INTER_FLOOR_HEIGHT_M))
            height_src = "floor_height"
        floor_height_bu = m_to_bu(floor_height_m)
        total_h_bu = floor_height_bu * num_floors
        # Resolve door SVG rect objects for this building
        raw_doors = doors_data.get(name, [])
        resolved_doors: list[dict] = []
        for door in raw_doors:
            door_obj = _find_curve(svg_objects, door["label"], label_map)
            if door_obj is not None:
                resolved_doors.append({"obj_name": door_obj.name, "piso": door["piso"]})
            else:
                print(
                    f"[naranjos-dsl] WARNING: SVG curve not found for door "
                    f"'{door['label']}' — skipped."
                )

        # Resolve window SVG rect objects early (needed for log message below)
        raw_windows = windows_data.get(name, [])
        resolved_windows: list[dict] = []
        for win in raw_windows:
            win_obj = _find_curve(svg_objects, win["label"], label_map)
            if win_obj is not None:
                resolved_windows.append({
                    "obj_name": win_obj.name,
                    "piso": win["piso"],
                    "z_bottom_m": win["z_bottom_m"],
                    "height_m": win["height_m"],
                })
            else:
                print(
                    f"[naranjos-dsl] WARNING: SVG curve not found for window "
                    f"'{win['label']}' — skipped."
                )

        print(
            f"[naranjos-dsl] Building '{name}': "
            f"{num_floors} floor(s), {floor_height_m:.3f} m/floor ({height_src}) "
            f"→ {total_h_bu:.3f} BU total"
            + (f", {len(resolved_doors)}/{len(raw_doors)} door(s)" if raw_doors else "")
            + (f", {len(resolved_windows)}/{len(raw_windows)} window(s)" if raw_windows else "")
        )

        # Build DSL graph → compile → GN source
        _tb = time.perf_counter()
        graph = _building_graph(
            name, curve.name, num_floors,
            floor_height_bu, WALL_THICKNESS_BU, SLAB_THICKNESS_BU,
        )
        gn_src = compile_to_source(graph)
        _tc = time.perf_counter()

        # Execute compiled GN setup (creates object + live modifier)
        obj = _exec_gn_setup(name, gn_src)
        _td = time.perf_counter()
        _move_to_collection(obj, "BSP")

        # Cut doors + windows in a single bisect pass to avoid O(N²) mesh growth.
        # T-intersection validation runs once in the final validation loop below,
        # not per-building, to avoid O(buildings × V × E) redundant checks.
        d_bounds = _door_bounds(resolved_doors, floor_height_bu)
        w_bounds: list = []  # windows disabled
        all_bounds = d_bounds + w_bounds
        if all_bounds:
            _cut_openings_direct(
                obj, all_bounds,
                n_doors=len(d_bounds), n_windows=len(w_bounds),
            )
        _te = time.perf_counter()
        print(
            f"[naranjos-dsl] TIMING {name}: "
            f"compile={_tc-_tb:.2f}s  exec_gn={_td-_tc:.2f}s  "
            f"cut={_te-_td:.2f}s  total={_te-_tb:.2f}s"
        )

        # Keep the footprint curve visible for reference
        _move_to_collection(curve, "DEBUG")

        generated.append(obj)
        building_objects[name] = obj

    print(f"[naranjos-dsl] TIMING buildings total: {time.perf_counter()-_t_bldg:.2f}s")

    # ── halls & roofs ─────────────────────────────────────────────────────
    _t_rh = time.perf_counter()
    for entry in roofs_halls_data:
        path_name = entry["path_name"]
        curve = _find_curve(svg_objects, path_name, label_map)
        if curve is None:
            print(f"[naranjos-dsl] WARNING: no curve for '{path_name}' — skipped.")
            continue

        name = entry["name"]
        kind = entry.get("kind", "volume")
        level_height_bu = _entry_height_bu(entry, buildings_data, building_objects)
        level_height_m = bu_to_m(level_height_bu)
        pitch_bu = _generated_storey_pitch_bu(entry, buildings_data, building_objects)
        if pitch_bu is None:
            pitch_bu = m_to_bu(_storey_pitch_m(entry, buildings_data))
        z_start_bu = _entry_z_start_bu(
            entry,
            level_height_bu,
            buildings_data,
            building_objects,
        )
        placement = (
            f"z={z_start_bu:.2f} BU (override)"
            if "z_start_bu" in entry
            else (
                f"between floors {max(int(entry.get('floor_base', 1)) - 1, 0)} "
                f"and {entry.get('floor_base', 1)}, z={z_start_bu:.2f} BU "
                f"within pitch {pitch_bu:.2f} BU"
            )
        )

        print(
            f"[naranjos-dsl] {kind.title()} '{name}': "
            f"{placement}, height {level_height_bu:.2f} BU "
            f"({level_height_m:.2f} m)"
        )

        graph = _roof_or_hall_graph(
            name,
            curve.name,
            level_height_bu,
            WALL_THICKNESS_BU,
            SLAB_THICKNESS_BU,
            z_start_bu,
        )
        gn_src = compile_to_source(graph)

        obj = _exec_gn_setup(name, gn_src)
        _move_to_collection(obj, "BSP")
        _move_to_collection(curve, "DEBUG")
        generated.append(obj)

    print(f"[naranjos-dsl] TIMING halls/roofs total: {time.perf_counter()-_t_rh:.2f}s")

    # ── stairs ────────────────────────────────────────────────────────────
    _t_stairs = time.perf_counter()
    stairs_data = _load_stairs()
    stair_slab_bu = float(stairs_data["slab_thickness_bu"])

    # Collect first-floor (level=1.0, z=0) landing curves for floor cutouts.
    stair_ground_curves: list[bpy.types.Object] = []

    for staircase in stairs_data["staircases"]:
        staircase_id = staircase["id"]
        segments     = staircase["segments"]
        left_ratio   = float(staircase.get("flight_left_ratio", 0.4))
        gap_ratio    = float(staircase.get("flight_gap_ratio",  0.2))

        seg_curves: list[tuple[dict, bpy.types.Object | None]] = []

        for seg in segments:
            shape = seg["shape"]
            curve = _find_curve(svg_objects, shape, label_map)
            if curve is None:
                print(f"[naranjos-dsl] WARNING: no curve for stair '{shape}' — skipped.")
            else:
                _move_to_collection(curve, "DEBUG")
                if float(seg.get("level", 0)) == 1.0:
                    stair_ground_curves.append(curve)
            seg_curves.append((seg, curve))

        print(
            f"[naranjos-dsl] Staircase {staircase_id}: "
            f"{len(segments)} landings → single merged mesh"
        )

        stair_obj = _create_staircase_solid(
            staircase_id, seg_curves, stair_slab_bu,
            left_ratio=left_ratio, gap_ratio=gap_ratio,
        )
        if stair_obj is not None:
            _move_to_collection(stair_obj, "BSP")
            generated.append(stair_obj)

    print(f"[naranjos-dsl] TIMING stairs total: {time.perf_counter()-_t_stairs:.2f}s")

    # ── objects (extruded circles: columns, etc.) ─────────────────────────
    _t_objs = time.perf_counter()
    objects_data = _load_objects()
    obj_floor_pitch_bu = float(objects_data["floor_pitch_bu"])

    for obj_def in objects_data["objects"]:
        if obj_def["type"] != "extrude_circles":
            continue

        group_id    = obj_def["svg_group_id"]
        group_label = obj_def.get("svg_group_label", group_id)
        floors      = obj_def["floors"]
        gap_top_bu  = float(obj_def["gap_top_bu"])
        segs        = int(obj_def.get("segments", 16))
        height_bu   = obj_floor_pitch_bu - gap_top_bu

        col_curves = _find_cols_curves(group_id)
        if not col_curves:
            print(
                f"[naranjos-dsl] WARNING: no curves found for group "
                f"'{group_id}' ({group_label}) — skipped."
            )
            continue

        print(
            f"[naranjos-dsl] Columns '{group_label}': "
            f"{len(col_curves)} curve(s), "
            f"{len(floors)} floor(s) × {height_bu:.4f} BU"
        )

        for floor_num in floors:
            z_start = (floor_num - 1) * obj_floor_pitch_bu
            col_obj = _create_columns_for_floor(
                col_curves, z_start, height_bu, floor_num, segs
            )
            if col_obj is not None:
                _move_to_collection(col_obj, "BSP")
                generated.append(col_obj)

        # Move group parent and all child curves to DEBUG
        group_parent = bpy.data.objects.get(group_id)
        if group_parent:
            _move_to_collection(group_parent, "DEBUG")
        for curve in col_curves:
            _move_to_collection(curve, "DEBUG")

    print(f"[naranjos-dsl] TIMING objects total: {time.perf_counter()-_t_objs:.2f}s")

    # ── borders ───────────────────────────────────────────────────────────
    _t_borders = time.perf_counter()
    border_path = border_data.get("path_name", "borders")
    border_curve = _find_curve(svg_objects, border_path, label_map)
    if border_curve is None:
        border_curve = _find_curve(svg_objects, "limites", label_map)

    if border_curve:
        h_bu = m_to_bu(float(border_data["height"]))
        print(f"[naranjos-dsl] Borders: {border_data['height']} m → {h_bu:.2f} BU")

        # Border walls
        graph = _border_graph(border_curve.name, h_bu, WALL_THICKNESS_BU)
        gn_src = compile_to_source(graph)
        obj = _exec_gn_setup("borders", gn_src)
        _move_to_collection(obj, "BSP")
        generated.append(obj)

        # Level floor: closed slab below the buildings.  Its top sits below
        # z=0, so it does not overlap the current building floor slabs.
        floor_obj = _create_level_floor_solid(
            border_curve,
            LEVEL_FLOOR_THICKNESS_BU,
            LEVEL_FLOOR_TOP_Z_BU,
        )
        if floor_obj is not None:
            _move_to_collection(floor_obj, "BSP")
            generated.append(floor_obj)
            print(
                f"[naranjos-dsl] Level floor: top z={LEVEL_FLOOR_TOP_Z_BU:.3f} BU, "
                f"bottom z={LEVEL_FLOOR_TOP_Z_BU - LEVEL_FLOOR_THICKNESS_BU:.3f} BU"
            )

        _move_to_collection(border_curve, "DEBUG")
    else:
        print("[naranjos-dsl] WARNING: no curve for borders.")
    print(f"[naranjos-dsl] TIMING borders total: {time.perf_counter()-_t_borders:.2f}s")

    # ── cleanup unused SVG objects (keep curves used by GN) ───────────────
    used_curves = {
        o.name
        for o in generated
        for m in o.modifiers
        if m.type == "NODES" and m.node_group
    }
    for obj in list(svg_objects):
        # Remove objects not used as curve references
        if obj.name in bpy.data.objects and obj not in generated:
            is_debug = any(
                obj.name in c.objects
                for c in bpy.data.collections
                if c.name == "DEBUG"
            )
            if not is_debug:
                bpy.data.objects.remove(obj, do_unlink=True)
    _cleanup_svg_collection()

    # ── final BSP merge / cleanup / light retopology / triangulation ───────
    merged_obj = _create_merged_bsp(generated)
    validation_targets = [merged_obj] if merged_obj is not None else generated

    # ── hide unused gn_* objects (created by the compiled setup() default call) ─
    hidden_gn = 0
    for obj in bpy.data.objects:
        if obj.name.startswith("gn_"):
            obj.hide_viewport = True
            obj.hide_render = True
            hidden_gn += 1
    if hidden_gn:
        print(f"[naranjos-dsl] Hidden {hidden_gn} unused gn_* object(s).")

    # ── validate ──────────────────────────────────────────────────────────
    print("\n[naranjos-dsl] ── Validation ──")
    # Force depsgraph evaluation
    bpy.context.view_layer.update()

    all_ok = True
    for obj in validation_targets:
        results = _validate_object(obj.name)
        failed = {k: v for k, v in results.items() if v}
        passed = [k for k, v in results.items() if not v]
        if failed:
            all_ok = False
            print(f"  {obj.name}:")
            for k, msgs in failed.items():
                for msg in msgs:
                    print(f"    [WARN] {k}: {msg}")
            for k in passed:
                print(f"    [OK]   {k}")
        else:
            print(f"  {obj.name}: all checks passed ✓")

    status = "ALL PASSED" if all_ok else "WARNINGS — see above"
    print(
        f"\n[naranjos-dsl] Done — {len(validation_targets)} final object(s) in BSP.\n"
        f"           Wall thickness : {WALL_THICKNESS_BU} BU "
        f"(~{WALL_THICKNESS_BU * M_PER_BU * 100:.0f} cm)\n"
        f"           Slab thickness : {SLAB_THICKNESS_BU} BU\n"
        f"           SVG scale      : {SVG_TO_BU}\n"
        f"           Validators     : {status}\n"
        f"           GN modifiers are LIVE — adjust values in Blender.\n"
        f"           TOTAL TIME     : {time.perf_counter()-_t_start:.2f}s"
    )


if __name__ == "__main__":
    import sys

    for obj_name in ("Cube", "Light", "Camera"):
        obj = bpy.data.objects.get(obj_name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

    generate_naranjos_dsl()

    blend_out = _BLEND_DIR / "naranjos_dsl.blend"
    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            blend_out = Path(sys.argv[i + 1])
            break
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))
    print(f"[naranjos-dsl] Saved → {blend_out}")
