"""Accordion-with-corners unit cell.

Variant of :mod:`accordion` where each horizontal row is one continuous fold
type: solid, dotted, solid.  Extra vertical valley folds pass through the
corners of the original short trapezoid bases.
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import FoldPattern, FoldType

# Same template geometry as accordion.py.
_L, _OFF, _H = 4.0, 1.0, 3.0
_P = 2.0 * (_L - _OFF)
_W = _P + _OFF


def generate(params: BellowsParams) -> FoldPattern:
    """Build the accordion-with-corners cell scaled by ``params.cell_scale``."""
    params.validate()
    s = params.cell_scale
    mountain: list = [
        ((0.0, 0.0), (_W, 0.0)),
        ((0.0, 2.0 * _H), (_W, 2.0 * _H)),
    ]
    valley: list = [
        ((0.0, _H), (_W, _H)),
        # Trapezoid slants from the base accordion pattern.
        ((0.0, 0.0), (_OFF, _H)),
        ((_L, 0.0), (_L - _OFF, _H)),
        ((0.0, 2.0 * _H), (_OFF, _H)),
        ((_L, 2.0 * _H), (_L - _OFF, _H)),
    ]

    # Vertical folds through the original short-base corners:
    # top short base x=(1, 3), bottom short base x=(4, 6).
    for x in (_OFF, _L - _OFF):
        valley.append(((x, 0.0), (x, 2.0 * _H)))

    pat = FoldPattern(
        name="accordion_corners",
        width=_W * s,
        height=2 * _H * s,
        seam=False,
    )
    for a, b in mountain:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.MOUNTAIN)
    for a, b in valley:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.VALLEY)
    pat.add_outline()
    return pat


__all__ = ["generate"]
