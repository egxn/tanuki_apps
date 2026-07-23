"""Tessellation — repeat a unit cell into a print-bed-sized fold pattern.

Each pattern's unit cell is stretched to its tile ``X × Y`` (mm) and replicated
on an ``n × m`` grid per the README "Tile Specifications — 35mm Bellows"
("Adjusted for 170×170 bed" table).  The fold depth follows the README:

    Z = tile_Y / 2 − fabric_thickness − press_tolerance
      = tile_Y / 2 − 0.8

The result is one big :class:`FoldPattern` that ``core.foldcore`` turns into the
folded male/female dies.
"""

from __future__ import annotations

import math

from ..parameters import BellowsParams
from .geometry import FoldPattern, FoldType
from .. import patterns

#: Print-bed and fabric constants (README "Base Parameters").  These module
#: globals are the single source of truth and may be overridden at runtime by a
#: JSON config (see :mod:`bellows_diecut.config`); read them at call time.
PRINT_BED = 170.0        # mm (square)
FABRIC_THICKNESS = 0.5   # mm
PRESS_TOLERANCE = 0.3    # mm
BASE_THICKNESS = 3.0     # mm — solid backing below the relief

#: Per-pattern tile size (mm), grid, and how the cells repeat:
#: - ``square``: plain grid (Resch, Waterbomb);
#: - ``brick``:  alternate rows shifted ½ tile (Miura — a row's tile corners land
#:   on the next row's tile centres);
#: - ``pitch_x`` / ``pitch_y``: pitch as a fraction of the tile so a cell
#:   interlocks with its neighbour, sharing edges:
#:     * Kresling — the V notch reduces the effective **width** (260/300);
#:     * Yoshimura — the open V overlaps the next tile's closed-rhombus base V,
#:       reducing the effective **height** to the rhombus pitch (120/180) so the
#:       diamonds tile as a regular grid.
TILE_SPECS: dict[str, dict] = {
    "yoshimura": {"tile": (16.0, 16.0), "grid": (10, 10), "tiling": "square"},
    "miura":     {"tile": (16.0, 17.0), "grid": (8, 10), "tiling": "brick"},
    "waterbomb": {"tile": (16.0, 15.0), "grid": (8, 11), "tiling": "square"},
    "kresling":  {"tile": (18.0, 12.0), "grid": (7, 14), "tiling": "square",
                  "pitch_x": 260.0 / 300.0},
    "resch":     {"tile": (20.0, 10.0), "grid": (6, 17), "tiling": "square"},
    "accordion": {"tile": (24.0, 14.0), "grid": (6, 12), "tiling": "square"},
    "accordion_corners": {"tile": (24.0, 14.0), "grid": (6, 12), "tiling": "square"},
}


def tile_depth(tile_y: float) -> float:
    """Fold-ridge depth Z (mm) for a tile of pitch *tile_y* (mm)."""
    return tile_y / 2.0 - FABRIC_THICKNESS - PRESS_TOLERANCE


def tessellate(
    name: str,
    tile: tuple[float, float] | None = None,
    grid: tuple[int, int] | None = None,
) -> FoldPattern:
    """Build the tessellated :class:`FoldPattern` for *name*.

    The unit cell is normalised to a unit square and repeated on the grid, each
    copy scaled to ``tile_X × tile_Y`` (mm) and placed per the pattern's tiling
    rule (square / brick / V-interlock) so the fold lines of adjacent tiles meet.
    """
    spec = TILE_SPECS[name]
    tx, ty = tile or spec["tile"]
    n, m = grid or spec["grid"]
    tiling = spec.get("tiling", "square")
    pitch_x = spec.get("pitch_x", 1.0) * tx       # horizontal step between columns
    pitch_y = spec.get("pitch_y", 1.0) * ty       # vertical step between rows

    cell = patterns.generate(name, BellowsParams(cell_scale=1.0))
    cw = max(cell.width, 1e-9)
    ch = max(cell.height, 1e-9)

    def row_shift(j: int) -> float:
        return (j % 2) * 0.5 * pitch_x if tiling == "brick" else 0.0

    folds: list[tuple[tuple, tuple, FoldType]] = []
    for j in range(m):
        oy = j * pitch_y
        ox0 = row_shift(j)
        for i in range(n):
            ox = ox0 + i * pitch_x
            for kind, lines in ((FoldType.MOUNTAIN, cell.mountains),
                                (FoldType.VALLEY, cell.valleys)):
                for fl in lines:
                    a = (ox + fl.p0[0] / cw * tx, oy + fl.p0[1] / ch * ty)
                    b = (ox + fl.p1[0] / cw * tx, oy + fl.p1[1] / ch * ty)
                    folds.append((a, b, kind))

    xs = [p[0] for a, b, _ in folds for p in (a, b)]
    ys = [p[1] for a, b, _ in folds for p in (a, b)]
    pat = FoldPattern(name=f"{name}_tile",
                      width=max(xs) - min(xs), height=max(ys) - min(ys),
                      seam=False, tile=(tx, ty))
    for a, b, kind in folds:
        pat.add_fold(a, b, kind)
    pat.add_outline()
    return pat


def roller_period(name: str, around: int, tile: tuple[float, float] | None = None) -> float:
    """Horizontal repeat distance (mm) of *around* tiles — the wrap circumference.

    This is ``around × the column pitch`` (``pitch_x·tile_X``), **not** the
    tessellation's bounding-box width: brick / V-interlock tilings overhang the
    last column past the period, which is exactly the flat seam that must be
    removed so the roller closes seamlessly.
    """
    spec = TILE_SPECS[name]
    tx, _ty = tile or spec["tile"]
    return around * spec.get("pitch_x", 1.0) * tx


def _wrap_segments_x(folds, period: float, x0: float):
    """Wrap fold segments into ``x ∈ [x0, x0+period)``, splitting at the seams.

    Brick / interlock columns run past one period; cutting each crossing segment
    at the period boundaries and translating the pieces back makes the strip
    exactly *period* wide and periodic, so wrapping it onto a cylinder meets.
    """
    out = []
    for a, b, kind in folds:
        ax, ay = a
        bx, by = b
        ts = {0.0, 1.0}
        if abs(bx - ax) > 1e-12:
            klo = math.floor((min(ax, bx) - x0) / period)
            khi = math.ceil((max(ax, bx) - x0) / period)
            for k in range(klo, khi + 1):
                t = (x0 + k * period - ax) / (bx - ax)
                if 1e-9 < t < 1.0 - 1e-9:
                    ts.add(t)
        ts = sorted(ts)
        for t0, t1 in zip(ts, ts[1:]):
            p0 = (ax + t0 * (bx - ax), ay + t0 * (by - ay))
            p1 = (ax + t1 * (bx - ax), ay + t1 * (by - ay))
            k = math.floor((0.5 * (p0[0] + p1[0]) - x0) / period + 1e-9)
            sh = k * period
            out.append(((p0[0] - sh, p0[1]), (p1[0] - sh, p1[1]), kind))
    return out


def tessellate_periodic(name: str, around: int, length: int):
    """Tessellation wrapped to exactly one circumference — returns ``(pattern, period)``.

    Like :func:`tessellate` over an ``around × length`` grid, but folded into a
    strip exactly :func:`roller_period` wide and periodic in ``x``, so wrapping it
    onto a cylinder of that circumference closes without a flat seam.
    """
    spec = TILE_SPECS[name]
    tx, _ty = spec["tile"]
    period = roller_period(name, around)
    base = tessellate(name, grid=(around, length))
    x0, y0, _x1, y1 = base.bounds()
    folds = [(fl.p0, fl.p1, fl.kind)
             for fl in base.mountains + base.valleys]
    wrapped = _wrap_segments_x(folds, period, x0)

    pat = FoldPattern(name=f"{name}_roller", width=period, height=y1 - y0,
                      seam=True, tile=(tx, _ty))
    for a, b, kind in wrapped:
        pat.add_fold(a, b, kind)
    pat.add_outline()
    return pat, period


def tessellated_size(name: str) -> tuple[float, float]:
    """Total ``(width, height)`` (mm) covered by the tessellation."""
    x0, y0, x1, y1 = tessellate(name).bounds()
    return x1 - x0, y1 - y0


def tile_params(name: str, base_thickness: float | None = None) -> BellowsParams:
    """``BellowsParams`` for the tessellated die.

    The mountain height is the pattern's configured ``fold_height`` (mm) when set
    (see :mod:`bellows_diecut.config`), else the auto README depth ``tile_Y/2 −
    fabric − tolerance``.  ``base_thickness`` falls back to :data:`BASE_THICKNESS`.
    """
    spec = TILE_SPECS[name]
    _tx, ty = spec["tile"]
    return BellowsParams(
        material_thickness=FABRIC_THICKNESS,
        ridge_height=spec.get("fold_height", tile_depth(ty)),
        base_thickness=BASE_THICKNESS if base_thickness is None else base_thickness,
    )


__all__ = [
    "TILE_SPECS", "PRINT_BED", "FABRIC_THICKNESS", "PRESS_TOLERANCE",
    "BASE_THICKNESS",
    "tile_depth", "tessellated_size", "tessellate", "tile_params",
    "roller_period", "tessellate_periodic",
]
