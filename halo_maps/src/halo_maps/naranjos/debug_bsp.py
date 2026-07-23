"""Debug BSP visualization — open the output .blend to inspect problems visually.

Creates overlay meshes on top of bsp_merged that highlight:

  🔴  T-junction vertices       → "DEBUG_TJ_verts"   (red dot cloud)
  🟠  T-junction edges          → "DEBUG_TJ_edges"   (orange edge wires)
  🟡  Non-manifold edges        → "DEBUG_nonmanifold" (yellow edge wires)
  🔵  Boundary (open) edges     → "DEBUG_boundary"   (blue edge wires)
  ⬜  bsp_merged                → normal grey display

Usage (from repo root):

    blender --background --factory-startup \\
        --python src/halo_maps/naranjos/debug_bsp.py \\
        -- --output src/halo_maps/naranjos/blend/debug_naranjos.blend

Or open the saved blend from a previous run and run this script on it::

    blender --background src/halo_maps/naranjos/blend/naranjos_dsl_updated.blend \\
        --python src/halo_maps/naranjos/debug_bsp.py \\
        -- --output src/halo_maps/naranjos/blend/debug_naranjos.blend --skip-generate

Tips for manual inspection
--------------------------
* Open the saved .blend in the Blender GUI.
* In the Outliner, toggle the eye icon on DEBUG_* collections to show/hide each layer.
* Select "DEBUG_TJ_edges" and Enter Edit Mode → you can see exactly which edges
  carry T-junction vertices.
* Use N-panel > Item to read vertex coordinates.
* Press Alt+Z (X-ray) to see through the geometry.
* Press Numpad 5 → orthographic; Numpad 1/3/7 for front/right/top views.
"""

from __future__ import annotations

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
import numpy as np

_TJUNCTION_TOL = 1e-5  # same as generate_dsl.py
_MAX_REPORT = 5000     # cap reported T-junctions to keep file small


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    coll = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(coll)
    return coll


def _link_to(obj: bpy.types.Object, coll: bpy.types.Collection) -> None:
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)


def _make_material(name: str, color: tuple[float, float, float], alpha: float = 1.0) -> bpy.types.Material:
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 2.0
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
            mat.blend_method = "BLEND"
    mat.diffuse_color = (*color, alpha)
    return mat


def _edge_only_mesh(
    name: str,
    edge_co_pairs: list[tuple[tuple, tuple]],
    color: tuple[float, float, float],
    coll: bpy.types.Collection,
) -> bpy.types.Object | None:
    """Create a mesh with only edges (no faces) — shows as a coloured wire."""
    if not edge_co_pairs:
        return None

    vert_list: list[tuple] = []
    vert_map: dict[tuple, int] = {}
    edge_list: list[tuple[int, int]] = []

    def _vi(co):
        key = tuple(round(c, 6) for c in co)
        if key not in vert_map:
            vert_map[key] = len(vert_list)
            vert_list.append(key)
        return vert_map[key]

    for co1, co2 in edge_co_pairs:
        edge_list.append((_vi(co1), _vi(co2)))

    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    mesh.from_pydata(vert_list, edge_list, [])
    mesh.update()
    obj.data.materials.append(_make_material(name + "_mat", color))
    obj.display_type = "WIRE"
    obj.show_wire = True
    coll.objects.link(obj)
    return obj


def _vert_cloud(
    name: str,
    positions: list[tuple[float, float, float]],
    color: tuple[float, float, float],
    coll: bpy.types.Collection,
) -> bpy.types.Object | None:
    """Create a mesh whose vertices are at the given positions (visible as dots)."""
    if not positions:
        return None
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    mesh.from_pydata(positions, [], [])
    mesh.update()
    obj.data.materials.append(_make_material(name + "_mat", color))
    obj.show_wire = True
    obj.display_type = "WIRE"
    # Make vertices larger and visible
    obj.show_in_front = True
    coll.objects.link(obj)
    return obj


# ---------------------------------------------------------------------------
# T-junction finder (numpy, O(E×V) single pass)
# ---------------------------------------------------------------------------

def _find_t_junctions(bm: bmesh.types.BMesh, tol: float = _TJUNCTION_TOL, max_report: int = _MAX_REPORT):
    """Return (tj_verts, tj_edge_pairs, tj_edge_set).

    tj_verts      — positions of T-junction vertices
    tj_edge_pairs — (co_a, co_b) pairs for edges that carry T-junctions
    tj_edge_set   — set of edge indices
    """
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    verts = list(bm.verts)
    n = len(verts)
    if n < 3 or not bm.edges:
        return [], [], set()

    vco = np.array([[v.co.x, v.co.y, v.co.z] for v in verts], dtype=np.float64)
    all_rows = np.arange(n)
    vert_to_row = {v: i for i, v in enumerate(verts)}

    tj_vert_positions = []
    tj_edge_pairs = []
    tj_edge_indices = set()
    reported = 0

    for edge in bm.edges:
        if reported >= max_report:
            break
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

        if hits.size:
            tj_edge_pairs.append((tuple(vco[ia]), tuple(vco[ib])))
            tj_edge_indices.add(edge.index)
            for h in hits:
                pos = tuple(vco[int(candidate_rows[h])])
                tj_vert_positions.append(pos)
                reported += 1
                if reported >= max_report:
                    break

    return tj_vert_positions, tj_edge_pairs, tj_edge_indices


# ---------------------------------------------------------------------------
# Main debug-layer builder
# ---------------------------------------------------------------------------

def build_debug_layers(obj_name: str = "bsp_merged") -> None:
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        print(f"[debug-bsp] ERROR: '{obj_name}' not found.", flush=True)
        return

    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    eval_mesh = eval_obj.to_mesh()

    bm = bmesh.new()
    bm.from_mesh(eval_mesh)
    mat = obj.matrix_world
    for v in bm.verts:
        v.co = mat @ v.co
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    eval_obj.to_mesh_clear()

    print(f"[debug-bsp] Loaded '{obj_name}': {len(bm.verts)} verts, {len(bm.edges)} edges, {len(bm.faces)} faces", flush=True)

    # ── 1. Boundary edges ─────────────────────────────────────────────────
    boundary_pairs = [
        (tuple(e.verts[0].co), tuple(e.verts[1].co))
        for e in bm.edges if len(e.link_faces) < 2
    ]
    print(f"[debug-bsp] Boundary edges: {len(boundary_pairs)}", flush=True)

    # ── 2. Non-manifold edges (3+ faces) ──────────────────────────────────
    nonmanifold_pairs = [
        (tuple(e.verts[0].co), tuple(e.verts[1].co))
        for e in bm.edges if len(e.link_faces) > 2
    ]
    print(f"[debug-bsp] Non-manifold edges (3+ faces): {len(nonmanifold_pairs)}", flush=True)

    # ── 3. T-junctions ────────────────────────────────────────────────────
    print("[debug-bsp] Scanning for T-junctions (O(E×V)) …", flush=True)
    tj_verts, tj_edge_pairs, tj_edge_set = _find_t_junctions(bm)
    print(f"[debug-bsp] T-junction vertices: {len(tj_verts)}, T-junction edges: {len(tj_edge_pairs)}", flush=True)

    bm.free()

    # ── 4. Create debug collections ───────────────────────────────────────
    debug_coll = _ensure_collection("DEBUG")
    # Remove stale debug objects from previous runs
    for o in list(debug_coll.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    boundary_coll    = _ensure_collection("DEBUG_boundary",     debug_coll)
    nonmanifold_coll = _ensure_collection("DEBUG_nonmanifold",  debug_coll)
    tj_edge_coll     = _ensure_collection("DEBUG_TJ_edges",     debug_coll)
    tj_vert_coll     = _ensure_collection("DEBUG_TJ_verts",     debug_coll)

    _edge_only_mesh("boundary_edges",    boundary_pairs,    (0.0, 0.4, 1.0), boundary_coll)
    _edge_only_mesh("nonmanifold_edges", nonmanifold_pairs, (1.0, 0.8, 0.0), nonmanifold_coll)
    _edge_only_mesh("tj_edges",          tj_edge_pairs,     (1.0, 0.4, 0.0), tj_edge_coll)
    _vert_cloud    ("tj_verts",          tj_verts,          (1.0, 0.0, 0.0), tj_vert_coll)

    print(
        f"[debug-bsp] Debug layers created:\n"
        f"  🔵 boundary edges:    {len(boundary_pairs)}\n"
        f"  🟡 non-manifold edges:{len(nonmanifold_pairs)}\n"
        f"  🟠 T-junction edges:  {len(tj_edge_pairs)}\n"
        f"  🔴 T-junction verts:  {len(tj_verts)}",
        flush=True,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Parse args
    argv = sys.argv
    skip_generate = False
    output_path = str(Path(__file__).parent / "blend" / "debug_naranjos.blend")
    obj_name = "bsp_merged"

    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    i = 0
    while i < len(argv):
        if argv[i] == "--output" and i + 1 < len(argv):
            output_path = argv[i + 1]; i += 2
        elif argv[i] == "--object" and i + 1 < len(argv):
            obj_name = argv[i + 1]; i += 2
        elif argv[i] == "--skip-generate":
            skip_generate = True; i += 1
        else:
            i += 1

    # Remove default scene objects
    for name in ("Cube", "Light", "Camera"):
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    # Scene setup
    from halo_maps.scene import setup_scene
    setup_scene()

    # Generate buildings if needed
    if not skip_generate or bpy.data.objects.get(obj_name) is None:
        print("[debug-bsp] Running generate_naranjos_dsl() …", flush=True)
        from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
        generate_naranjos_dsl()

    if bpy.data.objects.get(obj_name) is None:
        print(f"[debug-bsp] ERROR: '{obj_name}' still not found after generation.", flush=True)
        sys.exit(1)

    build_debug_layers(obj_name)

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(output_path).resolve()))
    print(f"[debug-bsp] Saved → {output_path}", flush=True)
    print("[debug-bsp] Open in Blender GUI and toggle DEBUG_* collections in the Outliner.", flush=True)
