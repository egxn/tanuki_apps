"""Halo CE — BSP geometry validators.

Run from inside Blender. Usage::

    from halo_maps.validators import run_all_validators
    results = run_all_validators("bsp_world")
    for name, errors in results.items():
        if errors:
            print(f"[FAIL] {name}:")
            for e in errors:
                print(f"       {e}")
        else:
            print(f"[OK]   {name}")
"""

from __future__ import annotations

import bpy
import bmesh
import mathutils

__all__ = [
    "validate_closed_geometry",
    "validate_manifold_edges",
    "validate_duplicate_vertices",
    "validate_internal_faces",
    "validate_polygon_budget",
    "validate_normals",
    "run_all_validators",
]

# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _get_bmesh(obj_name: str):
    """Return (obj, bm) for *obj_name*. Caller must call bm.free()."""
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        raise ValueError(f"Object {obj_name!r} not found in the scene.")
    if obj.type != 'MESH':
        raise TypeError(f"Object {obj_name!r} is not a Mesh (type={obj.type!r}).")

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    return obj, bm


# ---------------------------------------------------------------------------
# validate_closed_geometry
# ---------------------------------------------------------------------------

def validate_closed_geometry(obj_name: str = "bsp_world") -> list[str]:
    """Check that the mesh is a fully closed volume.

    A closed mesh has **no boundary edges** — every edge belongs to at least
    two faces.

    Returns:
        A list of human-readable error strings (empty list = OK).
    """
    obj, bm = _get_bmesh(obj_name)
    errors: list[str] = []
    try:
        boundary = [e for e in bm.edges if len(e.link_faces) < 2]
        if boundary:
            errors.append(
                f"{len(boundary)} boundary edge(s) found — mesh is not sealed. "
                f"Example edge indices: {[e.index for e in boundary[:5]]}"
            )
    finally:
        bm.free()
    return errors


# ---------------------------------------------------------------------------
# validate_manifold_edges
# ---------------------------------------------------------------------------

def validate_manifold_edges(obj_name: str = "bsp_world") -> list[str]:
    """Check that every edge belongs to exactly two faces (manifold).

    Returns:
        A list of human-readable error strings (empty list = OK).
    """
    obj, bm = _get_bmesh(obj_name)
    errors: list[str] = []
    try:
        non_manifold = [e for e in bm.edges if len(e.link_faces) != 2]
        if non_manifold:
            under = [e for e in non_manifold if len(e.link_faces) < 2]
            over  = [e for e in non_manifold if len(e.link_faces) > 2]
            if under:
                errors.append(
                    f"{len(under)} edge(s) with < 2 faces (open boundary). "
                    f"Indices: {[e.index for e in under[:5]]}"
                )
            if over:
                errors.append(
                    f"{len(over)} edge(s) with > 2 faces (non-manifold). "
                    f"Indices: {[e.index for e in over[:5]]}"
                )
    finally:
        bm.free()
    return errors


# ---------------------------------------------------------------------------
# validate_duplicate_vertices
# ---------------------------------------------------------------------------

def validate_duplicate_vertices(
    obj_name: str = "bsp_world",
    threshold: float = 1e-4,
) -> list[str]:
    """Detect pairs of vertices closer than *threshold* world units.

    Uses a simple O(n²) approach — suitable for BSP meshes (< ~10k verts).

    Returns:
        A list of human-readable error strings (empty list = OK).
    """
    obj, bm = _get_bmesh(obj_name)
    errors: list[str] = []
    try:
        verts = bm.verts
        duplicates: list[tuple[int, int, float]] = []
        t2 = threshold * threshold
        for i, v1 in enumerate(verts):
            for v2 in verts[i + 1:]:
                d2 = (v1.co - v2.co).length_squared
                if d2 < t2:
                    duplicates.append((v1.index, v2.index, d2 ** 0.5))
        if duplicates:
            errors.append(
                f"{len(duplicates)} duplicate vertex pair(s) found "
                f"(threshold={threshold}). "
                f"First pair: verts {duplicates[0][0]} & {duplicates[0][1]} "
                f"({duplicates[0][2]:.6f} units apart)."
            )
    finally:
        bm.free()
    return errors


# ---------------------------------------------------------------------------
# validate_internal_faces
# ---------------------------------------------------------------------------

def validate_internal_faces(obj_name: str = "bsp_world") -> list[str]:
    """Detect faces whose normal points toward the geometric centre of the mesh.

    Such inward-facing normals indicate internal geometry — a common cause of
    BSP compilation errors and lightmap artefacts.

    Returns:
        A list of human-readable error strings (empty list = OK).
    """
    obj, bm = _get_bmesh(obj_name)
    errors: list[str] = []
    try:
        if not bm.faces:
            return errors

        # Approximate mesh centre as the mean of all face centres
        centre = mathutils.Vector((0.0, 0.0, 0.0))
        for f in bm.faces:
            centre += f.calc_center_median()
        centre /= len(bm.faces)

        inward: list[int] = []
        for f in bm.faces:
            to_face = f.calc_center_median() - centre
            if to_face.dot(f.normal) < 0.0:
                inward.append(f.index)

        if inward:
            errors.append(
                f"{len(inward)} face(s) appear to have inward-pointing normals "
                f"(possible internal geometry). "
                f"Example face indices: {inward[:5]}"
            )
    finally:
        bm.free()
    return errors


# ---------------------------------------------------------------------------
# validate_polygon_budget
# ---------------------------------------------------------------------------

def validate_polygon_budget(
    obj_name: str = "bsp_world",
    limit: int = 10_000,
) -> list[str]:
    """Warn if the polygon count exceeds *limit*.

    Returns:
        A list with a single warning string if over budget, else empty.
    """
    obj, bm = _get_bmesh(obj_name)
    count = len(bm.faces)
    bm.free()
    if count > limit:
        return [
            f"Polygon budget exceeded: {count:,} faces (limit={limit:,}). "
            "Consider reducing geometry complexity."
        ]
    return []


# ---------------------------------------------------------------------------
# validate_normals
# ---------------------------------------------------------------------------

def validate_normals(obj_name: str = "bsp_world") -> list[str]:
    """Check that all face normals are valid (non-degenerate, consistent length).

    Returns:
        A list of human-readable error strings (empty list = OK).
    """
    _EPSILON = 1e-6
    obj, bm = _get_bmesh(obj_name)
    errors: list[str] = []
    try:
        degenerate = [f for f in bm.faces if f.normal.length < _EPSILON]
        if degenerate:
            errors.append(
                f"{len(degenerate)} degenerate face(s) with zero-length normal "
                f"(zero-area polygons). "
                f"Face indices: {[f.index for f in degenerate[:5]]}"
            )
    finally:
        bm.free()
    return errors


# ---------------------------------------------------------------------------
# run_all_validators
# ---------------------------------------------------------------------------

def run_all_validators(
    obj_name: str = "bsp_world",
    polygon_limit: int = 10_000,
    duplicate_threshold: float = 1e-4,
) -> dict[str, list[str]]:
    """Run all validators against *obj_name* and return a summary dict.

    The returned dict maps each validator name to its list of errors.
    An empty list means that check passed.

    Example::

        results = run_all_validators("bsp_world")
        passed  = [k for k, v in results.items() if not v]
        failed  = {k: v for k, v in results.items() if v}

    Returns:
        ``dict[str, list[str]]`` — one key per validator.
    """
    return {
        "closed_geometry":    validate_closed_geometry(obj_name),
        "manifold_edges":     validate_manifold_edges(obj_name),
        "duplicate_vertices": validate_duplicate_vertices(obj_name, duplicate_threshold),
        "internal_faces":     validate_internal_faces(obj_name),
        "polygon_budget":     validate_polygon_budget(obj_name, polygon_limit),
        "normals":            validate_normals(obj_name),
    }
