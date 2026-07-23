"""Verify the Halo Asset Blender Toolset addon is installed and list the
operators useful for the Naranjos BSP pipeline.

Run WITHOUT --factory-startup so user addons load::

    blender --background \\
        --python src/halo_maps/naranjos/toolset/addon_check.py

If the addon is not enabled this script attempts to enable it, then prints
the available Halo operators and their key parameters.
"""

import bpy

ADDON_MODULE = "io_scene_halo"

# Operators most relevant to a Halo CE BSP / level workflow.
USEFUL_OPS = [
    ("import_scene.wrl",  "Import tool.exe WRL error geometry (red/magenta faces)"),
    ("import_scene.jms",  "Import a JMS back into Blender (verify our export)"),
    ("export_scene.jms",  "Export JMS via the addon (reference for our exporter)"),
    ("import_scene.tag",  "Import a compiled tag (sbsp / shader_environment / scenario)"),
    ("export_scene.scnr", "Export scenario tag"),
    ("halo_bulk.cull_materials", "Remove unused material slots"),
    ("halo_bulk.scale_model",    "Batch-scale geometry"),
    ("halo_bulk.generate_level", "Generate level/frame helper geometry"),
    ("halo_bulk.import_fixup",   "Clean up imported BSP/portal geometry"),
]


def _op_exists(idname: str) -> bool:
    """Return True if a bpy.ops operator with this idname is registered."""
    try:
        category, name = idname.split(".", 1)
        return hasattr(getattr(bpy.ops, category), name)
    except (ValueError, AttributeError):
        return False


def main() -> None:
    print("\n========== Halo Toolset addon check ==========")

    addons = bpy.context.preferences.addons
    if ADDON_MODULE not in addons:
        print(f"[addon-check] '{ADDON_MODULE}' not enabled — attempting to enable…")
        try:
            bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
            print(f"[addon-check] enabled '{ADDON_MODULE}' ✓")
        except Exception as exc:
            print(f"[addon-check] ERROR: could not enable '{ADDON_MODULE}': {exc}")
            print("[addon-check] Install the addon in Blender Preferences first, or")
            print("[addon-check] do NOT pass --factory-startup (it disables user addons).")
            return
    else:
        ver = addons[ADDON_MODULE].module
        print(f"[addon-check] '{ADDON_MODULE}' is enabled ✓")

    print("\n[addon-check] Useful operators for the Naranjos pipeline:")
    for idname, desc in USEFUL_OPS:
        status = "✓" if _op_exists(idname) else "✗ MISSING"
        print(f"  [{status}] {idname:<28} — {desc}")

    print("\n[addon-check] Done.")


if __name__ == "__main__":
    main()
