"""bellows_diecut — 3D-printable matched dies for camera bellows.

Generates a male/female die pair that creases an origami fold pattern into
fabric.  Each pattern is one **unit cell** (single tile, no repetition yet —
tessellation comes later).  Following the README "Diecut Strategy", each die is a
flat plate with the fold edges extruded as triangular ridges (mountains, up) and
channels (valleys, down); the female is the negative.  The relief is built with
the **Tanuki Geometry Nodes DSL** (a cube plus boolean cuts) and the STL is baked
in **Blender**.  The ridge height is derived from the spacing between fold edges.

Quick start::

    from bellows_diecut import BellowsParams, generate_diecut

    params = BellowsParams(cell_scale=0.25)
    result = generate_diecut("yoshimura", params, "output", bake=True)  # needs Blender
    # result["paths"] → {'obj':…, 'svg':…, 'json':…, 'bpy':…, 'stl_male':…, 'stl_female':…}

Pipeline overview::

    patterns/<name>.generate(params)     →  FoldPattern  (one tile)
    core.diecut.build_graphs(...)        →  {male, female} Tanuki IR graphs
    core.exporter.export_all(..., bake)  →  OBJ/SVG/JSON + DSL script → STL (Blender)
"""

from __future__ import annotations

from pathlib import Path

from .parameters import BellowsParams
from .core.geometry import FoldPattern, FoldLine, FoldType
from .core import diecut, exporter, tessellate
from . import patterns, config
from .config import load_config, apply_config, write_template

#: Patterns available as single unit cells (see README "Fold Patterns").
PATTERNS = (
    "yoshimura", "miura", "waterbomb", "kresling", "resch", "accordion",
    "accordion_corners",
)


def configure(source: str | Path | dict | None) -> dict:
    """Apply a JSON config (path or dict) to all generators; returns the merged
    dict.  Equivalent to passing ``config=`` to a single generator, but global
    and persistent for the session.  See :mod:`bellows_diecut.config`."""
    return config.apply_config(source)


def write_config_template(path: str | Path) -> Path:
    """Write a starter config JSON (the current defaults) to *path*."""
    return config.write_template(path)


def generate_pattern(name: str, params: BellowsParams) -> FoldPattern:
    """Generate the unit-cell :class:`FoldPattern` for *name*."""
    return patterns.generate(name, params)


def generate_diecut(
    name: str,
    params: BellowsParams,
    output_dir: str | Path | None = None,
    bake: bool = False,
    config: str | Path | dict | None = None,
) -> dict:
    """Full pipeline: unit cell → DSL male/female dies → exported files.

    Parameters
    ----------
    name:
        Pattern key — one of :data:`PATTERNS`.
    params:
        A :class:`BellowsParams`.
    output_dir:
        Required for the die meshes: the foldcore OBJs, the flat OBJ/SVG/JSON
        and the self-contained DSL bake script ``<name>_diecut.py`` are written
        there.  When ``None`` only the :class:`FoldPattern` is returned.
    bake:
        If ``True`` (and Blender is on PATH), run the bake script to produce
        ``stl/<name>_{male,female}.stl``.
    config:
        Optional JSON config (path or dict) applied first; see
        :mod:`bellows_diecut.config`.

    Returns
    -------
    dict
        ``{"pattern": FoldPattern, "graphs": {male, female}, "paths": {...}}``.
        ``graphs`` / ``paths`` are empty when *output_dir* is ``None``.
    """
    from pathlib import Path

    if config is not None:
        apply_config(config)
    pattern = generate_pattern(name, params)
    if output_dir is None:
        return {"pattern": pattern, "graphs": {}, "paths": {}}

    graphs = diecut.build_graphs(pattern, params, Path(output_dir) / "mesh")
    paths = exporter.export_all(
        pattern, params, output_dir, graphs=graphs, bake=bake
    )
    return {"pattern": pattern, "graphs": graphs, "paths": paths}


def generate_tessellation(
    name: str,
    output_dir: str | Path | None = None,
    bake: bool = False,
    tile: tuple[float, float] | None = None,
    grid: tuple[int, int] | None = None,
    base_thickness: float | None = None,
    config: str | Path | dict | None = None,
) -> dict:
    """Tile *name* across the print bed and build the folded male/female dies.

    Uses the README "Tile Specifications" (size ``tile_X × tile_Y`` mm, grid
    ``n × m``, fold depth ``Z = tile_Y/2 − 0.8``) unless *tile* / *grid* override
    them, or a JSON *config* changes them globally (see
    :mod:`bellows_diecut.config`).  See :func:`generate_diecut` for
    *output_dir* / *bake* semantics.
    """
    if config is not None:
        apply_config(config)
    pattern = tessellate.tessellate(name, tile=tile, grid=grid)
    params = tessellate.tile_params(name, base_thickness=base_thickness)
    if output_dir is None:
        return {"pattern": pattern, "params": params, "graphs": {}, "paths": {}}

    graphs = diecut.build_graphs(pattern, params, Path(output_dir) / "mesh")
    paths = exporter.export_all(
        pattern, params, output_dir, graphs=graphs, bake=bake
    )
    return {"pattern": pattern, "params": params, "graphs": graphs, "paths": paths}


def generate_rollers(
    name: str,
    output_dir: str | Path | None = None,
    bake: bool = False,
    around: int | None = None,
    length: int | None = None,
    config: str | Path | dict | None = None,
) -> dict:
    """Build the male + female **rollers** for *name* — the fold pattern wrapped
    onto a cylinder.

    *around* tiles wrap the circumference (default the minimum for a seamless
    wrap — one bellows perimeter); *length* tiles run along the axis.  A JSON
    *config* (path or dict) applied first overrides tile sizes / grids / wall
    (see :mod:`bellows_diecut.config`).  See :func:`generate_diecut` for
    *output_dir* / *bake* semantics.
    """
    from .core import roller

    if config is not None:
        apply_config(config)
    a = around or roller.min_tiles_around(name)
    m = length or tessellate.TILE_SPECS[name]["grid"][1]
    pattern = tessellate.tessellate(name, grid=(a, m))
    pattern.name = f"{name}_roller"
    params = tessellate.tile_params(name)
    if output_dir is None:
        return {"pattern": pattern, "params": params, "graphs": {}, "paths": {}}

    graphs = roller.build_graphs(name, Path(output_dir) / "mesh", around=a, length=m)
    paths = exporter.export_all(
        pattern, params, output_dir, graphs=graphs, bake=bake
    )
    return {"pattern": pattern, "params": params, "graphs": graphs, "paths": paths}


def generate_rollers_gn(
    name: str,
    output_dir: str | Path,
    config: str | Path | dict | None = None,
) -> Path:
    """Write a **parametric Geometry Nodes** roller script for *name*.

    Emits ``<output_dir>/<name>_roller_gn.py`` — a self-contained Blender script
    that builds male + female roller objects with a ``BellowsRoller`` node group
    whose Diameter / Tiles / Relief depth / Core wall stay editable in Blender.
    Run it with ``blender -b -P <name>_roller_gn.py`` (or open and Run Script).
    A JSON *config* applied first seeds the default tile block + slider values.
    """
    from .core import roller_gn

    if config is not None:
        apply_config(config)
    return roller_gn.generate_rollers_gn(name, Path(output_dir))


def generate_all(
    output_dir: str | Path,
    config: str | Path | dict | None = None,
    bake: bool = False,
    gn: bool = True,
) -> dict:
    """Generate tessellated dies + rollers (+ GN roller scripts) for **every**
    pattern, driven by an optional JSON *config*.  Returns ``{name: {...}}``."""
    if config is not None:
        apply_config(config)
    out: dict[str, dict] = {}
    for name in PATTERNS:
        res = {"tessellation": generate_tessellation(name, output_dir, bake=bake),
               "rollers": generate_rollers(name, output_dir, bake=bake)}
        if gn:
            res["roller_gn"] = generate_rollers_gn(name, output_dir)
        out[name] = res
    return out


__all__ = [
    "BellowsParams",
    "FoldPattern", "FoldLine", "FoldType",
    "diecut", "exporter", "patterns", "tessellate", "config",
    "PATTERNS",
    "configure", "write_config_template", "load_config", "apply_config",
    "generate_pattern", "generate_diecut", "generate_tessellation",
    "generate_rollers", "generate_rollers_gn", "generate_all",
]
