"""Halo CE — Scene initialisation utilities.

Import inside Blender and call the functions directly::

    import halo_maps.scene as hce
    hce.setup_scene()
    hce.create_bsp_root_object()
    hce.initialize_geometry_nodes()

Assumes ``bpy`` and all other Blender built-in modules are already available
in the Python environment (i.e. running inside Blender).
"""

from __future__ import annotations

import bpy

# ---------------------------------------------------------------------------
# Collections required by the Halo CE map pipeline
# ---------------------------------------------------------------------------

HALO_COLLECTIONS = [
    "BSP",
    "SCENERY",
    "SPAWNS",
    "VEHICLES",
    "WEAPONS",
    "MARKERS",
    "COLLISION",
    "DEBUG",
]

BSP_OBJECT_NAME = "bsp_world"
GN_TREE_NAME = "GN_bsp_generator"


# ---------------------------------------------------------------------------
# setup_scene
# ---------------------------------------------------------------------------

def setup_scene() -> None:
    """Initialise the scene for Halo CE map work.

    * Configures Metric units (scale 1.0, length = Meters).
    * Removes the default Cube, Light and Camera if present.
    * Creates the 8 standard Halo CE collections.
    """
    # ── Unit settings ──────────────────────────────────────────────────────
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = 'METERS'

    # ── Remove default objects ─────────────────────────────────────────────
    for name in ('Cube', 'Light', 'Camera'):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)

    # ── Create Halo collections ────────────────────────────────────────────
    for coll_name in HALO_COLLECTIONS:
        if coll_name not in bpy.data.collections:
            coll = bpy.data.collections.new(coll_name)
            bpy.context.scene.collection.children.link(coll)

    print("[tanuki::halo_maps] Scene initialised.")


# ---------------------------------------------------------------------------
# create_bsp_root_object
# ---------------------------------------------------------------------------

def create_bsp_root_object() -> None:
    """Create the root BSP object ``bsp_world``.

    The object:
    * Is a plain empty Mesh.
    * Is placed at the world origin (0, 0, 0).
    * Is linked into the ``BSP`` collection (created if absent).
    """
    # ── Ensure BSP collection exists ───────────────────────────────────────
    if 'BSP' not in bpy.data.collections:
        coll = bpy.data.collections.new('BSP')
        bpy.context.scene.collection.children.link(coll)
    bsp_coll = bpy.data.collections['BSP']

    # ── Create bsp_world mesh object ───────────────────────────────────────
    if BSP_OBJECT_NAME in bpy.data.objects:
        print("[tanuki::halo_maps] bsp_world already exists — skipping.")
    else:
        mesh = bpy.data.meshes.new(BSP_OBJECT_NAME)
        obj  = bpy.data.objects.new(BSP_OBJECT_NAME, mesh)
        obj.location = (0.0, 0.0, 0.0)
        bsp_coll.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        print("[tanuki::halo_maps] bsp_world created in BSP collection.")


# ---------------------------------------------------------------------------
# initialize_geometry_nodes
# ---------------------------------------------------------------------------

def initialize_geometry_nodes() -> None:
    """Create the base Geometry Nodes tree and assign it to ``bsp_world``.

    Creates ``GN_bsp_generator`` with Group Input and Group Output nodes
    and assigns it as a modifier to ``bsp_world``.
    """
    # ── Ensure bsp_world exists ────────────────────────────────────────────
    obj = bpy.data.objects.get(BSP_OBJECT_NAME)
    if obj is None:
        raise RuntimeError("bsp_world not found. Run create_bsp_root_object() first.")

    # ── Create or reuse node tree ──────────────────────────────────────────
    if GN_TREE_NAME in bpy.data.node_groups:
        node_tree = bpy.data.node_groups[GN_TREE_NAME]
        print("[tanuki::halo_maps] Reusing existing node tree GN_bsp_generator.")
    else:
        node_tree = bpy.data.node_groups.new(GN_TREE_NAME, 'GeometryNodeTree')

        # Add required interface sockets (Blender 4.x API)
        if hasattr(node_tree, 'interface'):
            node_tree.interface.new_socket('Geometry', in_out='INPUT',  socket_type='NodeSocketGeometry')
            node_tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        else:
            # Blender 3.x fallback
            node_tree.inputs.new('NodeSocketGeometry',  'Geometry')
            node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

        gi = node_tree.nodes.new('NodeGroupInput')
        go = node_tree.nodes.new('NodeGroupOutput')
        gi.location = (-200, 0)
        go.location  = ( 200, 0)
        node_tree.links.new(gi.outputs[0], go.inputs[0])
        print("[tanuki::halo_maps] GN_bsp_generator node tree created.")

    # ── Assign as modifier to bsp_world ───────────────────────────────────
    existing = [m for m in obj.modifiers if m.type == 'NODES' and m.node_group == node_tree]
    if not existing:
        mod = obj.modifiers.new('GN_bsp_generator', 'NODES')
        mod.node_group = node_tree
        print("[tanuki::halo_maps] Modifier assigned to bsp_world.")
    else:
        print("[tanuki::halo_maps] Modifier already assigned — skipping.")
