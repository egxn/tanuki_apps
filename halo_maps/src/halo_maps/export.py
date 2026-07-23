"""Halo CE — JMS v8200 exporter.

Exports a Blender mesh object to the Halo CE ``.jms`` (Joint Mesh Skeleton)
format used by the Halo Editing Kit. Run from inside Blender.

Coordinate transform: Blender is Z-up right-handed; Halo CE is Y-up.
Mapping: ``blender(x, y, z)`` → ``halo(x, -z, y)``

JMS v8200 section order
-----------------------
::

    <version>              # 8200
    <node_count>
    <node: name; parent; sibling; rot(i,j,k,w); pos(x,y,z)>...
    <material_count>
    <material: name; texture_path>...
    <marker_count>
    <marker: name; region; parent; rot; pos; radius>...
    <region_count>
    <region: name>...
    <vertex_count>
    <vertex: parent; pos(x,y,z); normal(x,y,z); uv_count; uv(u,v)>...
    <triangle_count>
    <triangle: region; material; v0; v1; v2>...

Material slots
--------------
The exporter reads material names directly from ``obj.data.materials``.
Each material in the object's slot list becomes one JMS material entry.
If no materials are assigned the whole mesh is exported as ``+sky``.
"""

from __future__ import annotations

import os
from pathlib import Path

import bpy
import bmesh

__all__ = ["export_jms"]

# ---------------------------------------------------------------------------
# Coordinate transform helpers
# ---------------------------------------------------------------------------

def _halo_xyz(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Convert Blender world coord (Z-up) to Halo world coord (Y-up)."""
    return (x, -z, y)


def _halo_normal(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Same rotation applied to direction vectors."""
    return _halo_xyz(x, y, z)


def _jms_bitmap_path(mat: bpy.types.Material | None) -> str:
    """Return the Halo CE bitmap path for a material, or ``<none>``.

    Reads the filepath from the first Image Texture node in the material's
    node tree and converts it to a Halo CE-style path relative to the
    ``data/`` directory (backslash-separated, no extension).

    Convention: the source .tif lives at
    ``data/levels/<map>/materials/<name>.tif``
    → JMS path = ``levels\\<map>\\materials\\<name>``
    """
    if mat is None or not mat.use_nodes:
        return "<none>"
    for node in mat.node_tree.nodes:
        if node.type != "TEX_IMAGE" or node.image is None:
            continue
        abs_fp = Path(bpy.path.abspath(node.image.filepath))
        # Walk up looking for a 'levels' anchor directory.
        # Expected: …/naranjos/materials/wall.tif
        #  → try to build: levels\naranjos\materials\wall
        parts = abs_fp.parts
        # Find 'levels' or fall back to building from 'naranjos' upward
        for anchor in ("levels",):
            try:
                idx = next(i for i, p in enumerate(parts) if p == anchor)
                rel = "\\".join(parts[idx:])            # levels\naranjos\…\wall.tif
                return rel.rsplit(".", 1)[0]             # strip extension
            except StopIteration:
                pass
        # Fallback: use naranjos\materials\<stem>
        try:
            idx = next(i for i, p in enumerate(parts) if p == "naranjos")
            rel = "\\".join(["levels"] + list(parts[idx:]))
            return rel.rsplit(".", 1)[0]
        except StopIteration:
            pass
        # Last resort: just the stem
        return abs_fp.stem
    return "<none>"


# ---------------------------------------------------------------------------
# Main exporter
# ---------------------------------------------------------------------------

def export_jms(
    obj_name: str,
    output_path: str,
    map_name: str = "unnamed",
    scale: float = 1.0,
) -> str:
    """Export a Blender mesh to JMS v8200 format.

    The mesh is **triangulated in a temporary bmesh copy** — the original
    object data is not modified.

    Material names are read from the object's material slots.  If the object
    has no materials the entire mesh is written with the ``+sky`` material
    (Halo CE open-sky convention).  This allows multi-material BSP meshes
    (e.g. ground + wall + sky) to be exported correctly.

    Parameters
    ----------
    obj_name:
        Name of the Blender mesh object to export.
    output_path:
        Filesystem path for the ``.jms`` file.  Parent directory must exist.
    map_name:
        Human-readable name embedded in a leading comment.  Defaults to
        ``"unnamed"``.
    scale:
        Uniform scale applied to all vertex positions before writing.
        Equivalent to pressing S→<scale>→Enter and applying the scale in
        Blender Edit Mode.  Normals and UV coordinates are not affected.
        Use ``27.0`` to match the Halo CE world-unit convention when the
        scene is modelled in Blender metres (M_PER_BU = 0.55).

    Returns
    -------
    str
        The absolute path of the written file.

    Raises
    ------
    ValueError
        If *obj_name* is not found in the scene.
    TypeError
        If *obj_name* is not a Mesh object.
    """
    # ------------------------------------------------------------------
    # 1. Acquire object + evaluated mesh
    # ------------------------------------------------------------------
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        raise ValueError(f"Object {obj_name!r} not found in the scene.")
    if obj.type != 'MESH':
        raise TypeError(f"Object {obj_name!r} is not a Mesh (type={obj.type!r}).")

    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval  = obj.evaluated_get(depsgraph)
    mesh_eval = obj_eval.to_mesh()

    bm = bmesh.new()
    bm.from_mesh(mesh_eval)
    bmesh.ops.triangulate(bm, faces=bm.faces)

    uv_layer = bm.loops.layers.uv.active

    # ------------------------------------------------------------------
    # 2. Collect material names from object slots
    # ------------------------------------------------------------------
    raw_mats: list[bpy.types.Material | None] = [
        slot.material for slot in obj.material_slots
    ]
    if raw_mats:
        mat_names: list[str] = [
            (m.name if m is not None else "+sky") for m in raw_mats
        ]
    else:
        mat_names = ["+sky"]
        raw_mats  = [None]

    # ------------------------------------------------------------------
    # 3. Build vertex + triangle lists
    # ------------------------------------------------------------------
    verts = list(bm.verts)
    faces = list(bm.faces)

    # ------------------------------------------------------------------
    # 4. Format sections
    # ------------------------------------------------------------------
    lines: list[str] = []

    # -- header comment (not part of spec, helps with debugging) --------
    lines.append(f"; JMS v8200 — {map_name}")
    lines.append(f"; exported by halo_maps.export")

    # -- version ---------------------------------------------------------
    lines.append("8200")

    # -- nodes ------------------------------------------------------------
    # JMS v8200 (< 8205) node block layout:
    #   <node list checksum>   ← integer, 0 for a trivial single-frame skeleton
    #   <node count>
    #   per node: <name> <first-child index> <next-sibling index> <rot> <pos>
    # Note: the old format stores *child* + *sibling* indices (2 ints), NOT a
    # parent index — that is the >= 8205 layout.  Writing 3 ints here shifts
    # every later token by one and makes tool.exe / the Blender toolset misparse
    # the file ("invalid literal for int(): 'frame'").
    lines.append("0")          # node list checksum (trivial skeleton)
    lines.append("1")          # node count
    lines.append("frame")      # name
    lines.append("-1")         # first child  (-1 = none)
    lines.append("-1")         # next sibling (-1 = none)
    lines.append("0.000000\t0.000000\t0.000000\t1.000000")  # rot i j k w
    lines.append("0.000000\t0.000000\t0.000000")            # pos x y z

    # -- materials --------------------------------------------------------
    lines.append(str(len(mat_names)))
    for mname, mat in zip(mat_names, raw_mats):
        lines.append(mname)
        lines.append(_jms_bitmap_path(mat))

    # -- markers ----------------------------------------------------------
    lines.append("0")          # marker count (none)

    # -- regions ----------------------------------------------------------
    lines.append("1")
    lines.append("unnamed")

    # -- vertices ---------------------------------------------------------
    lines.append(str(len(verts)))
    for v in verts:
        co    = v.co
        norm  = v.normal
        hx, hy, hz   = _halo_xyz(co.x * scale, co.y * scale, co.z * scale)
        nx, ny, nz   = _halo_normal(norm.x, norm.y, norm.z)

        # Collect UVs from the first loop that owns this vertex
        uv_u, uv_v = 0.0, 0.0
        if uv_layer and v.link_loops:
            loop_uv = v.link_loops[0][uv_layer]
            uv_u = loop_uv.uv.x
            uv_v = loop_uv.uv.y

        # JMS v8200 (< 8205) per-vertex layout:
        #   <node 0 index> <pos x y z> <normal x y z>
        #   <node 1 index> <node 1 weight> <tex u> <tex v>
        # There is NO "uv pair count" field in v8200 (that belongs to >= 8205).
        # A vertex bound only to the frame node uses node 1 index = -1, weight 0.
        lines.append("0")          # node 0 index (frame)
        lines.append(f"{hx:.6f}\t{hy:.6f}\t{hz:.6f}")
        lines.append(f"{nx:.6f}\t{ny:.6f}\t{nz:.6f}")
        lines.append("-1")         # node 1 index (no second influence)
        lines.append("0.000000")   # node 1 weight
        lines.append(f"{uv_u:.6f}\t{uv_v:.6f}")
        lines.append("0")          # vertex flags (unused int, required for v >= 8199)

    # -- triangles --------------------------------------------------------
    lines.append(str(len(faces)))
    n_mats = len(mat_names)
    for f in faces:
        v_indices = [v.index for v in f.verts]
        if len(v_indices) != 3:
            # Should never happen after triangulate — defensive guard
            continue
        i0, i1, i2 = v_indices
        # Clamp material_index to valid range (guard against slot mismatches)
        mat_idx = min(f.material_index, n_mats - 1)
        # region=0 (unnamed)
        lines.append(f"0\t{mat_idx}\t{i0}\t{i1}\t{i2}")

    # ------------------------------------------------------------------
    # 5. Cleanup bmesh + temporary mesh
    # ------------------------------------------------------------------
    bm.free()
    obj_eval.to_mesh_clear()

    # ------------------------------------------------------------------
    # 6. Write file
    # ------------------------------------------------------------------
    output_path = os.path.abspath(output_path)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
        fh.write("\n")

    return output_path
