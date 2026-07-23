"""Bellows Diecut — core geometry, foldcore dies, and exporters."""

from .geometry import (
    Point2, Edge, FoldType, FoldLine, FoldPattern,
    cell_from_edges, edge_spacing, relief_dims, merge_collinear,
)
from . import foldcore, tessellate, roller, roller_gn
from .foldcore import build_surface, build_die, fold_amplitude
from .tessellate import TILE_SPECS, tile_depth, tessellated_size
from .roller import build_roller, min_tiles_around
from .roller_gn import flat_block, build_script, generate_rollers_gn
from .diecut import build_graphs
from .exporter import (
    export_bpy_script, bake_and_export_stl, bake_molds,
    export_obj, export_svg, export_json, export_all,
)

__all__ = [
    "Point2", "Edge", "FoldType", "FoldLine", "FoldPattern",
    "cell_from_edges", "edge_spacing", "relief_dims", "merge_collinear",
    "foldcore", "build_surface", "build_die", "fold_amplitude",
    "tessellate", "TILE_SPECS", "tile_depth", "tessellated_size",
    "roller", "build_roller", "min_tiles_around",
    "roller_gn", "flat_block", "build_script", "generate_rollers_gn",
    "build_graphs",
    "export_bpy_script", "bake_and_export_stl", "bake_molds",
    "export_obj", "export_svg", "export_json", "export_all",
]
