"""Halo CE — Procedural geometry generators.

Import inside Blender and call the functions directly::

    import halo_maps.generators as gen
    gen.generate_base_volume(100, 200, 20)
    gen.generate_symmetry_layout("mirror")
    gen.generate_spawn_zones(3, 3)

Assumes ``bpy`` and all other Blender built-in modules are already available
in the Python environment (i.e. running inside Blender).

The generators use two layers:
1. **Tanuki DSL** — defines the shape as an ``IRGraph`` (pure Python, no bpy).
2. **bpy** — applies the compiled Geometry Node tree to a real object.
"""

from __future__ import annotations

from .bootstrap import enable_venv

enable_venv()

import bpy

from tanuki.dsl import cube, set_geometry_name, output, model
from tanuki.backends.blender.compiler import compile_to_source

from .scene import BSP_OBJECT_NAME

# ---------------------------------------------------------------------------
# Private DSL helpers
# ---------------------------------------------------------------------------

def _bsp_volume_graph(width: float, depth: float, height: float):
    """Build and return an IRGraph for the base BSP volume using the Tanuki DSL."""
    with model("bsp_volume") as ctx:
        vol = cube(width, depth, height, "bsp_volume")
        vol = vol | set_geometry_name(name="bsp_volume")
        output(vol)
    return ctx.graph


# ---------------------------------------------------------------------------
# generate_base_volume
# ---------------------------------------------------------------------------

def generate_base_volume(
    width: float = 100.0,
    depth: float = 100.0,
    height: float = 20.0,
) -> None:
    """Create the playable BSP volume geometry on ``bsp_world``.

    * Ensures ``bsp_world`` exists in the ``BSP`` collection (creates it if
      absent — mirrors ``create_bsp_root_object``).
    * Compiles the shape via the Tanuki Geometry Nodes DSL.
    * Bakes the resulting Geometry Nodes modifier to an actual mesh so the
      object is ready for validators and the JMS exporter.

    Args:
        width:  Extent along the X axis (world units / metres).
        depth:  Extent along the Y axis.
        height: Extent along the Z axis.
    """
    graph = _bsp_volume_graph(width, depth, height)
    gn_script = compile_to_source(graph)

    # ── Ensure BSP collection and bsp_world object exist ──────────────────
    if 'BSP' not in bpy.data.collections:
        coll = bpy.data.collections.new('BSP')
        bpy.context.scene.collection.children.link(coll)
    bsp_coll = bpy.data.collections['BSP']

    if BSP_OBJECT_NAME not in bpy.data.objects:
        mesh = bpy.data.meshes.new(BSP_OBJECT_NAME)
        obj  = bpy.data.objects.new(BSP_OBJECT_NAME, mesh)
        obj.location = (0.0, 0.0, 0.0)
        bsp_coll.objects.link(obj)
    else:
        obj = bpy.data.objects[BSP_OBJECT_NAME]

    bpy.context.view_layer.objects.active = obj

    # ── Build the Geometry Node tree (Tanuki DSL compiled output) ─────────
    if 'GN_bsp_volume' in bpy.data.node_groups:
        node_tree = bpy.data.node_groups['GN_bsp_volume']
        node_tree.nodes.clear()
    else:
        node_tree = bpy.data.node_groups.new('GN_bsp_volume', 'GeometryNodeTree')
        if hasattr(node_tree, 'interface'):
            node_tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        else:
            node_tree.outputs.new('NodeSocketGeometry', 'Geometry')

    exec(compile(gn_script, "<gn_bsp_volume>", "exec"), {"bpy": bpy, "node_tree": node_tree})

    # ── Assign / refresh modifier ─────────────────────────────────────────
    mod = next((m for m in obj.modifiers if m.name == 'GN_bsp_volume'), None)
    if mod is None:
        mod = obj.modifiers.new('GN_bsp_volume', 'NODES')
    mod.node_group = node_tree

    # ── Apply modifier so the mesh is real (needed for validators + exporter)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier='GN_bsp_volume')

    print(f"[tanuki::halo_maps] bsp_world set to {width}×{depth}×{height} units.")


# ---------------------------------------------------------------------------
# generate_symmetry_layout
# ---------------------------------------------------------------------------

def generate_symmetry_layout(mode: str = "mirror") -> None:
    """Place a symmetry reference Empty in the scene.

    A Custom Property ``symmetry_mode`` is stored on the object for later use
    by layout tools.

    Args:
        mode: One of ``"mirror"``, ``"radial"``, or ``"lane-based"``.
    """
    valid_modes = {"mirror", "radial", "lane-based"}
    if mode not in valid_modes:
        raise ValueError(f"mode must be one of {valid_modes}, got {mode!r}")

    # ── Ensure MARKERS collection ─────────────────────────────────────────
    if 'MARKERS' not in bpy.data.collections:
        coll = bpy.data.collections.new('MARKERS')
        bpy.context.scene.collection.children.link(coll)
    markers_coll = bpy.data.collections['MARKERS']

    # ── Create symmetry Empty ─────────────────────────────────────────────
    name = 'layout_symmetry'
    if name in bpy.data.objects:
        obj = bpy.data.objects[name]
        print(f"[tanuki::halo_maps] {name} already exists — updating mode.")
    else:
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = 'ARROWS'
        obj.empty_display_size = 5.0
        obj.location = (0.0, 0.0, 0.0)
        markers_coll.objects.link(obj)

    obj['symmetry_mode'] = mode
    print(f"[tanuki::halo_maps] layout_symmetry placed (mode={mode!r}).")


# ---------------------------------------------------------------------------
# generate_spawn_zones
# ---------------------------------------------------------------------------

def generate_spawn_zones(
    n_red: int = 3,
    n_blue: int = 3,
    spacing: float = 5.0,
) -> None:
    """Create player spawn-point Empties in the scene.

    Red spawns are placed at negative X, blue spawns at positive X.
    Both sets are centred on Y = 0.

    Args:
        n_red:   Number of red-team spawn points.
        n_blue:  Number of blue-team spawn points.
        spacing: Distance (in world units) between consecutive spawns.
    """
    if n_red < 1 or n_blue < 1:
        raise ValueError("n_red and n_blue must each be at least 1.")

    # ── Ensure SPAWNS collection ──────────────────────────────────────────
    if 'SPAWNS' not in bpy.data.collections:
        coll = bpy.data.collections.new('SPAWNS')
        bpy.context.scene.collection.children.link(coll)
    spawns_coll = bpy.data.collections['SPAWNS']

    def _make_spawn(name: str, location: tuple) -> None:
        if name in bpy.data.objects:
            bpy.data.objects[name].location = location
            return
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = 'SINGLE_ARROW'
        obj.empty_display_size = 1.0
        obj.location = location
        spawns_coll.objects.link(obj)

    red_positions  = [(-spacing * i, 0.0, 0.0) for i in range(n_red)]
    blue_positions = [( spacing * i, 0.0, 0.0) for i in range(n_blue)]

    for i, pos in enumerate(red_positions,  start=1):
        _make_spawn(f'spawn_red_{i:02d}',  pos)
    for i, pos in enumerate(blue_positions, start=1):
        _make_spawn(f'spawn_blue_{i:02d}', pos)

    print(
        f"[tanuki::halo_maps] Created {len(red_positions)} red "
        f"and {len(blue_positions)} blue spawn points."
    )
