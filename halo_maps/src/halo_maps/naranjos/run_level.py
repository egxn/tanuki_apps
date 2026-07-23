"""Runner: generate Naranjos buildings + assemble BSP level + export JMS.

Usage (background mode):
    blender --background --factory-startup \
        --python src/halo_maps/naranjos/run_level.py \
        -- [--output src/halo_maps/naranjos/blend/naranjos_level.blend] [--jms naranjos.jms] [--scale 27]

Steps:
  1. setup_scene()             — metric units, standard collections
  2. generate_naranjos_dsl()   — import SVG, create all building objects
  3. assemble_and_export()     — ground + sky + buildings → bsp_world → JMS
  4. Save .blend

--scale applies a uniform multiplier to all JMS vertex positions (default 27.0).
  Equivalent to S→<value>→Enter in Blender Edit Mode on bsp_world.
  The .blend is saved at working scale (1×); only the JMS is scaled.
"""

import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent
for candidate in (_SRC_ROOT, *_SRC_ROOT.parents):
    if (candidate / "src" / "halo_maps").exists():
        _SRC_ROOT = str(candidate / "src")
        break
else:
    _SRC_ROOT = str(_SRC_ROOT)
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)

# Force line-buffered stdout so print() output is visible in real-time
# even when stdout is a pipe or file (not a tty).
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass  # Python < 3.7

import bpy

# ---------------------------------------------------------------------------
# Parse optional CLI args passed after "--"
# ---------------------------------------------------------------------------
_blend_out = Path(__file__).parent / "blend" / "naranjos_level.blend"
_jms_out   = None    # None → level.py default (naranjos.jms in same dir)
_jms_scale = 27.0    # Halo CE world-unit convention

_argv = sys.argv
if "--" in _argv:
    _argv = _argv[_argv.index("--") + 1:]
    i = 0
    while i < len(_argv):
        if _argv[i] == "--output" and i + 1 < len(_argv):
            _blend_out = Path(_argv[i + 1])
            i += 2
        elif _argv[i] == "--jms" and i + 1 < len(_argv):
            _jms_out = _argv[i + 1]
            i += 2
        elif _argv[i] == "--scale" and i + 1 < len(_argv):
            _jms_scale = float(_argv[i + 1])
            i += 2
        else:
            i += 1

# ---------------------------------------------------------------------------
# Step 1 — clean scene
# ---------------------------------------------------------------------------
for obj_name in ("Cube", "Light", "Camera"):
    obj = bpy.data.objects.get(obj_name)
    if obj is not None:
        bpy.data.objects.remove(obj, do_unlink=True)

# ---------------------------------------------------------------------------
# Step 2 — setup_scene (metric units + collections)
# ---------------------------------------------------------------------------
from halo_maps.scene import setup_scene
setup_scene()

# ---------------------------------------------------------------------------
# Step 3 — generate buildings
# ---------------------------------------------------------------------------
from halo_maps.naranjos.generate_dsl import generate_naranjos_dsl
generate_naranjos_dsl()

# ---------------------------------------------------------------------------
# Step 4 — assemble level (ground + sky + buildings → bsp_world + JMS)
# ---------------------------------------------------------------------------
from halo_maps.naranjos.level import assemble_and_export
assemble_and_export(export_path=_jms_out, jms_scale=_jms_scale)

# ---------------------------------------------------------------------------
# Step 5 — save .blend
# ---------------------------------------------------------------------------
# Pack all external images into the blend so textures always show in Blender
# regardless of where the file is opened from.
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(_blend_out.resolve()), relative_remap=True)
print(f"[run_level] Blend saved → {_blend_out.resolve()}")
