"""DSL die graphs — import the computed foldcore meshes.

The folded male/female surfaces are computed in :mod:`core.foldcore` and written
to OBJ.  Each die's Tanuki graph is simply ``import_obj(<obj>)`` so the geometry
stays in the **Tanuki DSL → Blender** flow (the bake compiles the graph to
Geometry Nodes, realises the imported mesh, and exports the STL).
"""

from __future__ import annotations

from pathlib import Path

from tanuki.dsl import (
    import_obj, realize_instances, set_geometry_name, output, model,
)
from tanuki.ir.graph import IRGraph

from ..parameters import BellowsParams
from .geometry import FoldPattern
from . import foldcore


def _die_graph(name: str, obj_path: str | Path) -> IRGraph:
    """An IR graph that imports *obj_path* and names it *name*."""
    abs_path = str(Path(obj_path).resolve())
    with model(name) as ctx:
        # Import OBJ outputs *instances* — realise them into a mesh.
        geo = (import_obj(abs_path)
               | realize_instances()
               | set_geometry_name(name=name))
        output(geo)
    return ctx.graph


def build_graphs(
    pattern: FoldPattern, params: BellowsParams, obj_dir: str | Path,
) -> dict[str, IRGraph]:
    """Write the foldcore die OBJs to *obj_dir* and return their import graphs.

    Returns ``{"male": IRGraph, "female": IRGraph}``; each graph imports the
    corresponding ``<obj_dir>/<pattern>_<side>.obj``.
    """
    obj_dir = Path(obj_dir)
    graphs: dict[str, IRGraph] = {}
    for side in ("male", "female"):
        name = f"{pattern.name}_{side}"
        obj = obj_dir / f"{name}.obj"
        foldcore.export_die_obj(pattern, params, obj, side)
        graphs[side] = _die_graph(name, obj)
    return graphs


__all__ = ["build_graphs"]
