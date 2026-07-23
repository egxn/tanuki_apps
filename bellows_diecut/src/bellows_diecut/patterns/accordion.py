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

# Trapezoid geometry (template units): long base ``_L``, slant run ``_OFF`` →
# short base ``_L − 2·_OFF``; band height ``_H``; x-period ``_P = 2·(_L − _OFF)``.
_L, _OFF, _H = 4.0, 1.0, 3.0
_P = 2.0 * (_L - _OFF)


def _band(ox: float, oy: float, flip: bool, mountain: list, valley: list) -> None:
    """One period (up + down trapezoid) of a band at offset ``(ox, oy)``."""
    def P(x: float, y: float):
        return (ox + x, oy + (_H - y if flip else y))

    mountain += [(P(0.0, 0.0), P(_L, 0.0)),                 # up long base (bottom)
                 (P(_L - _OFF, _H), P(_P + _OFF, _H))]      # down long base (top)
    valley += [(P(_OFF, _H), P(_L - _OFF, _H)),             # up short base (top)
               (P(_L, 0.0), P(_P, 0.0)),                    # down short base (bottom)
               (P(0.0, 0.0), P(_OFF, _H)),                  # up left slant
               (P(_L, 0.0), P(_L - _OFF, _H)),              # shared slant
               (P(_P, 0.0), P(_P + _OFF, _H))]              # down right slant


def generate(params: BellowsParams) -> FoldPattern:
    """Build the trapezoid accordion cell scaled by ``params.cell_scale``."""
    params.validate()
    s = params.cell_scale
    mountain: list = []
    valley: list = []
    _band(0.0, 0.0, flip=False, mountain=mountain, valley=valley)   # row 0
    _band(0.0, _H, flip=True, mountain=mountain, valley=valley)     # row 1 (inverted)

    pat = FoldPattern(name="accordion", width=_P * s, height=2 * _H * s, seam=False)
    for a, b in mountain:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.MOUNTAIN)
    for a, b in valley:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.VALLEY)
    pat.add_outline()
    return pat


__all__ = ["generate"]
