"""halo_maps — Halo CE BSP pipeline utilities.

Pipeline overview::

    setup_scene()                       # initialize Blender scene & collections
    create_bsp_root_object()            # create bsp_world empty mesh
    initialize_geometry_nodes()         # attach GN_bsp_generator modifier

    generate_base_volume(w, d, h)       # procedural box (DSL → bpy script)
    generate_symmetry_layout(mode)      # symmetry helper Empty
    generate_spawn_zones(n_red, n_blue) # spawn point Empties

    generate_naranjos()                 # naranjos map buildings + borders

    validate_closed_geometry(obj)       # boundary edge check
    validate_manifold_edges(obj)        # manifold check
    validate_duplicate_vertices(obj)    # merge-distance check
    validate_internal_faces(obj)        # inward normal check
    validate_polygon_budget(obj, limit) # polygon count check
    validate_normals(obj)               # degenerate face check
    run_all_validators(obj)             # run all checks, return dict

    export_jms(obj, path, map_name)     # write JMS v8200 file
"""

from .bootstrap import enable_venv

enable_venv()

from .scene import (
    setup_scene,
    create_bsp_root_object,
    initialize_geometry_nodes,
    HALO_COLLECTIONS,
    BSP_OBJECT_NAME,
    GN_TREE_NAME,
)

from .generators import (
    generate_base_volume,
    generate_symmetry_layout,
    generate_spawn_zones,
)

from .validators import (
    validate_closed_geometry,
    validate_manifold_edges,
    validate_duplicate_vertices,
    validate_internal_faces,
    validate_polygon_budget,
    validate_normals,
    run_all_validators,
)

from .export import export_jms

from .naranjos.generate import generate_naranjos
from .naranjos.generate_dsl import generate_naranjos_dsl

__all__ = [
    # scene
    "setup_scene",
    "create_bsp_root_object",
    "initialize_geometry_nodes",
    "HALO_COLLECTIONS",
    "BSP_OBJECT_NAME",
    "GN_TREE_NAME",
    # generators
    "generate_base_volume",
    "generate_symmetry_layout",
    "generate_spawn_zones",
    # validators
    "validate_closed_geometry",
    "validate_manifold_edges",
    "validate_duplicate_vertices",
    "validate_internal_faces",
    "validate_polygon_budget",
    "validate_normals",
    "run_all_validators",
    # export
    "export_jms",
    # naranjos map
    "generate_naranjos",
    "generate_naranjos_dsl",
]
