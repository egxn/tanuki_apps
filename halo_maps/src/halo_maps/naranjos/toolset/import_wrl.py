"""Import a tool.exe WRL error file and report what kind of errors it contains.

When ``tool structure`` or ``tool lightmaps`` finds geometry problems it writes
a ``.wrl`` file containing the offending faces, colour-coded by error type
(red = open/degenerate, orange = overlap, pink = T-junction, etc.).  This
script imports that WRL with the addon so the error geometry appears alongside
``bsp_world`` for visual inspection, and prints a summary of what was loaded.

Run WITHOUT --factory-startup::

    blender src/halo_maps/naranjos/blend/naranjos_level.blend \\
        --python src/halo_maps/naranjos/toolset/import_wrl.py \\
        -- --wrl path/to/naranjos.wrl

Open the resulting scene in the GUI to see the error faces highlighted inside
the level.  Each WRL colour maps to an error type — see WRL_COLOURS below and
docs/bsp_throubleshooting.md for the meaning of each.
"""

import sys
from pathlib import Path

import bpy

ADDON_MODULE = "io_scene_halo"

# WRL vertex colours → error meaning (from c20 / bsp_throubleshooting.md).
WRL_COLOURS = {
    "red":     "Open edge / degenerate triangle (most common)",
    "green":   "Nearly coplanar surface (paired with red)",
    "orange":  "Overlapping surfaces (Z-fighting) / duplicate triangle",
    "pink":    "Possible T-junction (thin/small face)",
    "cyan":    "Surface clipped to no leaves (outside BSP)",
    "magenta": "Unearthed portal edge / portal outside BSP",
    "yellow":  "Portal does not define two closed spaces",
    "blue":    "Degenerate UVs (radiosity)",
    "black":   "Two fog planes intersect in a cluster",
}


def _parse_args() -> str | None:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
        for i, a in enumerate(argv):
            if a == "--wrl" and i + 1 < len(argv):
                return argv[i + 1]
    return None


def _ensure_addon() -> bool:
    if ADDON_MODULE not in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
        except Exception as exc:
            print(f"[import-wrl] ERROR: cannot enable '{ADDON_MODULE}': {exc}")
            return False
    return True


def main() -> None:
    wrl_path = _parse_args()
    print("\n========== Import WRL error geometry ==========")

    if not wrl_path:
        print("[import-wrl] No --wrl path given.")
        print("[import-wrl] Usage: ... --python import_wrl.py -- --wrl <file.wrl>")
        print("[import-wrl] WRL colour legend (see docs/bsp_throubleshooting.md):")
        for colour, meaning in WRL_COLOURS.items():
            print(f"    {colour:<8} → {meaning}")
        return

    if not Path(wrl_path).is_file():
        print(f"[import-wrl] ERROR: file not found: {wrl_path}")
        return

    if not _ensure_addon():
        return

    before = set(bpy.data.objects.keys())
    try:
        bpy.ops.import_scene.wrl(filepath=wrl_path)
    except Exception as exc:
        print(f"[import-wrl] ERROR: addon failed to import WRL: {exc}")
        return

    new_objs = [o for k, o in bpy.data.objects.items() if k not in before]
    print(f"[import-wrl] imported {len(new_objs)} error-geometry object(s):")
    total_faces = 0
    for o in new_objs:
        if o.type == "MESH":
            n = len(o.data.polygons)
            total_faces += n
            print(f"    {o.name}: {n} error face(s)")

    if total_faces == 0:
        print("[import-wrl] No error faces found — WRL may be empty (clean compile?).")
    else:
        print(f"[import-wrl] {total_faces} total error face(s) loaded.")
        print("[import-wrl] Open the GUI and look for coloured faces inside bsp_world.")
        print("[import-wrl] Colour legend:")
        for colour, meaning in WRL_COLOURS.items():
            print(f"    {colour:<8} → {meaning}")

    # Save a copy so the GUI can be opened on the merged scene.
    out = Path(wrl_path).with_suffix(".wrl_overlay.blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print(f"[import-wrl] saved overlay scene → {out}")


if __name__ == "__main__":
    main()
