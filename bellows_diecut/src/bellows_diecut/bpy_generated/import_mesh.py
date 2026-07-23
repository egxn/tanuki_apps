"""Blender helper — import a generated diecut/pattern mesh and tag its folds.

Run from Blender's Text Editor (or ``blender --background --python``).  It:

1. Imports the flat-pattern OBJ exported by ``core.exporter.export_obj``.
2. Reads the ``g mountain|valley|boundary`` groups back out of the OBJ and
   stores a per-edge integer attribute ``fold_type`` (0 = boundary, 1 = valley,
   2 = mountain) on the imported mesh.

The ``fold_type`` attribute is what a Geometry Nodes tree (e.g.
``fold_nodes.blend``) reads to drive a collapse-preview slider before printing.

Assumes ``bpy`` is available (i.e. running inside Blender).
"""

from __future__ import annotations

from pathlib import Path

import bpy

_FOLD_CODE = {"boundary": 0, "valley": 1, "mountain": 2}


def _parse_obj_edge_groups(obj_path: Path) -> tuple[list[tuple[float, float, float]],
                                                    list[tuple[int, int, int]]]:
    """Return (vertices, edges) where each edge is ``(v0, v1, fold_code)``.

    OBJ indices are 1-based; the returned edge vertex indices are 0-based.
    """
    verts: list[tuple[float, float, float]] = []
    edges: list[tuple[int, int, int]] = []
    current = 0  # default boundary
    for raw in obj_path.read_text().splitlines():
        tok = raw.split()
        if not tok:
            continue
        if tok[0] == "v":
            verts.append((float(tok[1]), float(tok[2]), float(tok[3])))
        elif tok[0] == "g" and len(tok) > 1:
            current = _FOLD_CODE.get(tok[1].lower(), 0)
        elif tok[0] == "l":
            a, b = int(tok[1]) - 1, int(tok[2]) - 1
            edges.append((a, b, current))
    return verts, edges


def import_mesh(obj_path: str | Path, name: str = "bellows_pattern") -> "bpy.types.Object":
    """Import *obj_path* as a mesh with a ``fold_type`` edge attribute."""
    obj_path = Path(obj_path)
    verts, edges = _parse_obj_edge_groups(obj_path)

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [(a, b) for (a, b, _) in edges], [])
    mesh.update()

    # Map each (sorted) vertex pair to its fold code, then write the attribute
    # in Blender's own edge order.
    code_by_pair = {tuple(sorted((a, b))): c for (a, b, c) in edges}
    attr = mesh.attributes.new(name="fold_type", type="INT", domain="EDGE")
    for i, edge in enumerate(mesh.edges):
        key = tuple(sorted((edge.vertices[0], edge.vertices[1])))
        attr.data[i].value = code_by_pair.get(key, 0)

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    print(f"[bellows_diecut] Imported {name}: {len(verts)} verts, {len(edges)} edges.")
    return obj


if __name__ == "__main__":
    import sys

    # Usage: blender --background --python import_mesh.py -- <pattern.obj>
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if argv:
        import_mesh(argv[0])
    else:
        print("[bellows_diecut] Pass an OBJ path after '--' to import it.")
