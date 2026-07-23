"""Validate that every file the Naranjos pipeline references actually exists
in its expected folder, after the config/ svg/ blend/ models/ reorganisation.

Pure Python — no Blender needed::

    python3 src/halo_maps/naranjos/check_paths.py

Exits 0 if all required files are present, 1 if any are missing.  Optional
build artefacts (generated blends, JMS) are reported as INFO, not failures.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DIR = Path(__file__).resolve().parent

# (relative path, required?) — required files fail the check if missing;
# optional build artefacts are only reported.
REQUIRED: list[str] = [
    # config/ — JSON definitions consumed by generate_dsl.py
    "config/buildings.json",
    "config/borders.json",
    "config/roofs_halls.json",
    "config/stairs.json",
    "config/objects.json",
    "config/doors.json",
    "config/windows.json",
    # svg/ — source curves
    "svg/map.svg",
    # materials/ — textures referenced by level.py (tif = JMS, png = viewport)
    "materials/wall.tif",
    "materials/floor.tif",
    "materials/hall.tif",
    "materials/roof.tif",
    "materials/wall.png",
    "materials/floor.png",
    "materials/hall.png",
    "materials/roof.png",
    # package modules
    "generate_dsl.py",
    "level.py",
    "run_level.py",
    "validate_bsp.py",
]

OPTIONAL: list[str] = [
    # build artefacts — created by running the pipeline
    "blend/naranjos_dsl_updated.blend",  # pipeline input (pre-generated)
    "blend/naranjos_level.blend",        # pipeline output
    "models/naranjos.jms",               # exported JMS
    "svg/map_bk.svg",                    # backup SVG
    # output tree for tool.exe
    "output/data/levels/naranjos/models/naranjos.jms",
    "output/data/levels/naranjos/materials/wall.tif",
]


def main() -> int:
    print(f"\n========== Naranjos path check ==========")
    print(f"root: {_DIR}\n")

    missing = []
    print("Required files:")
    for rel in REQUIRED:
        p = _DIR / rel
        ok = p.is_file()
        print(f"  [{'✓' if ok else '✗ MISSING'}] {rel}")
        if not ok:
            missing.append(rel)

    print("\nOptional build artefacts:")
    for rel in OPTIONAL:
        p = _DIR / rel
        status = "✓" if p.is_file() else "— (not built yet)"
        print(f"  [{status}] {rel}")

    print()
    if missing:
        print(f"✗ {len(missing)} required file(s) MISSING:")
        for m in missing:
            print(f"    {m}")
        return 1

    print("✓ All required files present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
