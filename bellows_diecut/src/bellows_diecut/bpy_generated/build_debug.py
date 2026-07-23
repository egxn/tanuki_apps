"""Build a debug Blender scene for the bellows diecuts.

Lays out every pattern's male + female plates (with their Geometry Nodes
modifiers kept **live**, so the DSL node tree is inspectable) next to the flat
crease pattern, then saves a ``.blend`` for visual debugging.

Run headless::

    blender --background --python bpy_generated/build_debug.py
    # → output/debug_bellows.blend

or from Blender's Text Editor (Run Script).  Assumes ``bpy`` is available.
"""

from __future__ import annotations

import sys
from pathlib import Path

import bpy

# Make ``tanuki`` importable when Blender runs this file standalone.
_SRC_ROOT = Path(__file__).resolve().parents[4]
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from bellows_diecut import BellowsParams, PATTERNS, generate_pattern
from bellows_diecut.core import foldcore
from bellows_diecut.core.geometry import FoldType

_MODULE_ROOT = Path(__file__).resolve().parent.parent

#: One unit-cell tile per pattern at a shared scale.
_PARAMS = BellowsParams(cell_scale=0.25)
CASES = {name: _PARAMS for name in PATTERNS}

#: Edge attribute codes for the flat reference mesh.
_FOLD_CODE = {FoldType.BOUNDARY: 0, FoldType.VALLEY: 1, FoldType.MOUNTAIN: 2}

#: Viewport colour per fold type — mountains red, valleys blue, boundary grey.
_FOLD_COLOUR = {
    FoldType.MOUNTAIN: (0.84, 0.15, 0.15, 1.0),
    FoldType.VALLEY: (0.12, 0.47, 0.80, 1.0),
    FoldType.BOUNDARY: (0.1, 0.1, 0.1, 1.0),
}


def _fold_material(kind: FoldType) -> "bpy.types.Material":
    """Return (creating once) a flat-coloured material for a fold type."""
    mname = f"fold_{kind.value}"
    mat = bpy.data.materials.get(mname)
    if mat is None:
        mat = bpy.data.materials.new(mname)
        mat.diffuse_color = _FOLD_COLOUR[kind]
    return mat

# Layout (mm).
_ROW_GAP = 120.0     # spacing between patterns along Y
_X_MALE = -100.0     # male plate centre X
_X_FEMALE = 100.0    # female plate centre X
_REF_LIFT_Z = 40.0   # flat crease reference floats above the plates


def _clear_scene() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _build_solid(pattern, params, side, location) -> "bpy.types.Object":
    """Build the foldcore die mesh directly in the scene."""
    verts, faces = foldcore.build_die(pattern, params, side)
    name = f"{pattern.name}_{side}"
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(map(float, v)) for v in verts], [],
                     [tuple(map(int, f)) for f in faces])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _build_flat_reference(pattern, name, location) -> list["bpy.types.Object"]:
    """Build the flat creases as **one object per fold type**.

    Separating mountains / valleys / boundary (and the fold vertices that go
    with each) into distinct, distinctly-coloured objects makes it trivial to
    see at a glance which creases fold and which don't — they can be hidden or
    soloed independently in the outliner.
    """
    # Centre the pattern (which lives in 0..w × 0..h) over the plates.
    x0, y0, x1, y1 = pattern.bounds()
    ox = location[0] - (x0 + x1) / 2.0
    oy = location[1] - (y0 + y1) / 2.0
    oz = location[2]

    objs: list[bpy.types.Object] = []
    for kind in (FoldType.MOUNTAIN, FoldType.VALLEY, FoldType.BOUNDARY):
        lines = pattern.lines_of(kind)
        if not lines:
            continue
        index: dict[tuple[float, float], int] = {}
        verts: list[tuple[float, float, float]] = []
        edges: list[tuple[int, int]] = []

        def vid(p):
            key = (round(p[0], 5), round(p[1], 5))
            if key not in index:
                index[key] = len(verts)
                verts.append((key[0] + ox, key[1] + oy, oz))
            return index[key]

        for fl in lines:
            edges.append((vid(fl.p0), vid(fl.p1)))

        mesh = bpy.data.meshes.new(f"{name}_{kind.value}")
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        attr = mesh.attributes.new(name="fold_type", type="INT", domain="EDGE")
        for i in range(len(edges)):
            attr.data[i].value = _FOLD_CODE[kind]

        obj = bpy.data.objects.new(f"{name}_{kind.value}", mesh)
        obj.data.materials.append(_fold_material(kind))
        bpy.context.scene.collection.objects.link(obj)
        objs.append(obj)
    return objs


def _add_camera_and_light(n_rows: int) -> None:
    span_y = (n_rows - 1) * _ROW_GAP
    cy = span_y / 2.0
    cam_data = bpy.data.cameras.new("debug_cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(360.0, span_y + 120.0)
    cam = bpy.data.objects.new("debug_cam", cam_data)
    # Slight tilt so the relief reads, centred on all rows.
    cam.location = (0.0, cy - 70.0, 480.0)
    cam.rotation_euler = (0.32, 0.0, 0.0)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    light_data = bpy.data.lights.new("debug_sun", type="SUN")
    light_data.energy = 3.0
    light = bpy.data.objects.new("debug_sun", light_data)
    light.rotation_euler = (0.6, 0.2, 0.0)
    bpy.context.scene.collection.objects.link(light)


def build_debug_scene(blend_path: str | Path | None = None) -> Path:
    """Build the full debug scene and save it as a ``.blend``.

    Returns the path of the written blend file.
    """
    _clear_scene()

    import math as _math
    for i, (name, params) in enumerate(CASES.items()):
        y = i * _ROW_GAP
        pattern = generate_pattern(name, params)
        # Matched dies: the male's folded face is on top, the female's on its
        # underside.  Flip the female in the debug scene so its fold shows.
        _build_solid(pattern, params, "male", (_X_MALE, y, 0.0))
        fem = _build_solid(pattern, params, "female", (_X_FEMALE, y, 0.0))
        fem.rotation_euler = (_math.pi, 0.0, 0.0)
        _build_flat_reference(pattern, f"{name}_pattern", (0.0, y, _REF_LIFT_Z))
        print(f"[debug] laid out {name} (male + female + flat reference)")

    _add_camera_and_light(len(CASES))

    if blend_path is None:
        blend_path = _MODULE_ROOT / "output" / "debug_bellows.blend"
    blend_path = Path(blend_path)
    blend_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path.resolve()))
    print(f"[debug] saved {blend_path}")
    return blend_path


if __name__ == "__main__":
    build_debug_scene()
