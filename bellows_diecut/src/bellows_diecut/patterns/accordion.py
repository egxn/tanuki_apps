"""Accordion unit cell — a brick of **trapezoids** (the user's design).

Across X, up- and down-trapezoids alternate (each the vertical reflection of its
neighbour) and **share their slanted sides** — no rhombi between them.  The next
row inverts vertically.  The **long bases are the mountains** (the main folds);
the short bases and the shared slants are valleys.

The relief is a clean trapezoidal corrugation built by
:func:`core.foldcore._accordion_surface` (flat tilted facets, no tenting).
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import FoldPattern, FoldType

def _band(ox: float, oy: float, flip: bool, mountain: list, valley: list,
          long_base: float, offset: float, height: float) -> None:
    """One period (up + down trapezoid) of a band at offset ``(ox, oy)``."""
    def P(x: float, y: float):
        return (ox + x, oy + (height - y if flip else y))

    period = 2.0 * (long_base - offset)
    mountain += [(P(0.0, 0.0), P(long_base, 0.0)),
                 (P(long_base - offset, height), P(period + offset, height))]
    valley += [(P(offset, height), P(long_base - offset, height)),
               (P(long_base, 0.0), P(period, 0.0)),
               (P(0.0, 0.0), P(offset, height)),
               (P(long_base, 0.0), P(long_base - offset, height)),
               (P(period, 0.0), P(period + offset, height))]


def generate(params: BellowsParams) -> FoldPattern:
    """Build the trapezoid accordion cell scaled by ``params.cell_scale``."""
    params.validate()
    s = params.cell_scale
    long_base = params.accordion_long_base
    offset = params.accordion_offset
    height = params.accordion_band_height
    period = 2.0 * (long_base - offset)
    mountain: list = []
    valley: list = []
    _band(0.0, 0.0, False, mountain, valley, long_base, offset, height)
    _band(0.0, height, True, mountain, valley, long_base, offset, height)

    pat = FoldPattern(name="accordion", width=period * s, height=2 * height * s, seam=False)
    for a, b in mountain:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.MOUNTAIN)
    for a, b in valley:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.VALLEY)
    pat.add_outline()
    return pat


__all__ = ["generate"]
