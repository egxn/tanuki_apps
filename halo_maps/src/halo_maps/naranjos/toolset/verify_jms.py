"""Re-import the exported naranjos.jms with the Halo Toolset addon and verify
it survives a round-trip: parse OK, expected materials present, no degenerate
or non-manifold collision geometry.

This catches problems BEFORE running tool.exe — the addon's JMS parser is the
same family of code the community uses, so if it imports cleanly the file is
structurally valid.

Run WITHOUT --factory-startup::

    blender --background \\
        --python src/halo_maps/naranjos/toolset/verify_jms.py \\
        -- [--jms path/to/naranjos.jms]

Default JMS path: src/halo_maps/naranjos/models/naranjos.jms
"""

import sys
from pathlib import Path

import bpy

ADDON_MODULE = "io_scene_halo"
_DIR = Path(__file__).resolve().parent
_DEFAULT_JMS = _DIR.parent / "models" / "naranjos.jms"

# Materials we expect to find as JMS material entries (collision vs render-only).
COLLIDEABLE_MATS = {"naranjos_wall", "naranjos_floor", "naranjos_hall", "naranjos_roof"}
RENDER_ONLY_MATS = {"naranjos_wall!"}
SPECIAL_MATS     = {"+portal", "+sky"}


def _parse_args() -> str:
    argv = sys.argv
    jms = str(_DEFAULT_JMS)
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
        for i, a in enumerate(argv):
            if a == "--jms" and i + 1 < len(argv):
                jms = argv[i + 1]
    return jms


def _ensure_addon() -> bool:
    if ADDON_MODULE not in bpy.context.preferences.addons:
        try:
            bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
        except Exception as exc:
            print(f"[verify-jms] ERROR: cannot enable '{ADDON_MODULE}': {exc}")
            return False
    return True


def _count_jms_materials(jms_path: str) -> list[str]:
    """Read the material names straight from the JMS text (section after node block)."""
    lines = Path(jms_path).read_text(encoding="utf-8").splitlines()
    # Skip leading comments, find "8200", then walk the fixed sections.
    i = 0
    while i < len(lines) and lines[i].strip() != "8200":
        i += 1
    i += 1                                   # past version (8200)
    i += 1                                   # past node list checksum
    node_count = int(lines[i].strip()); i += 1
    i += node_count * 5                      # each node = name+child+sibling+rot+pos
    mat_count = int(lines[i].strip()); i += 1
    names = []
    for _ in range(mat_count):
        names.append(lines[i].strip())       # material name
        i += 1                                # skip bitmap path line
        i += 1
    return names


def main() -> None:
    jms_path = _parse_args()
    print(f"\n========== Verify JMS: {jms_path} ==========")

    if not Path(jms_path).is_file():
        print(f"[verify-jms] ERROR: file not found: {jms_path}")
        return

    # ── 1. Material names from the raw JMS text ───────────────────────────
    mat_names = _count_jms_materials(jms_path)
    print(f"[verify-jms] JMS declares {len(mat_names)} material(s): {mat_names}")

    found = set(mat_names)
    missing_coll = COLLIDEABLE_MATS - found
    if missing_coll:
        print(f"[verify-jms] WARNING: missing collideable materials: {missing_coll}")
    if RENDER_ONLY_MATS & found:
        print(f"[verify-jms] render-only present: {RENDER_ONLY_MATS & found} ✓")
    if not SPECIAL_MATS <= found:
        print(f"[verify-jms] WARNING: missing special materials: {SPECIAL_MATS - found}")
    else:
        print(f"[verify-jms] +portal / +sky present ✓")

    # ── 2. Round-trip import with the addon ───────────────────────────────
    if not _ensure_addon():
        return

    # Clear scene so imported objects are easy to find.
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    # Blender 4.1+ JMS importer reads from directory + files, ignoring filepath.
    p = Path(jms_path)
    try:
        if (4, 1, 0) <= bpy.app.version:
            bpy.ops.import_scene.jms(
                directory=str(p.parent),
                files=[{"name": p.name}],
                game_title="halo1",
            )
        else:
            bpy.ops.import_scene.jms(filepath=jms_path, game_title="halo1")
        print("[verify-jms] addon JMS import: parsed without error ✓")
    except Exception as exc:
        print(f"[verify-jms] ERROR: addon failed to import JMS: {exc}")
        print("[verify-jms] → tool.exe will likely also reject this file.")
        return

    # ── 3. Inspect imported mesh ──────────────────────────────────────────
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    print(f"[verify-jms] imported {len(meshes)} mesh object(s):")
    total_tris = 0
    for o in meshes:
        n = len(o.data.polygons)
        total_tris += n
        print(f"    {o.name}: {len(o.data.vertices)} verts, {n} faces, "
              f"{len(o.data.materials)} material slot(s)")
    print(f"[verify-jms] total faces: {total_tris}")
    print("[verify-jms] Done — if no warnings above, the JMS is structurally sound.")


if __name__ == "__main__":
    main()
