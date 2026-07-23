"""Waterbomb unit cell.

Two mirrored vertical trapezoids sharing the short edge at the centre.  The whole
trapezoid frame is valley; the X crossing both trapezoids is mountain.  Geometry
transcribed from the SVG reference in ``README.md``.
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import cell_from_edges, FoldPattern

# X across both trapezoids — mountain.
_MOUNTAIN = [
    (220, 615, 460, 795),
    (460, 615, 220, 795),
]
# Trapezoid frames (left + right, sharing the central short edge) — valley.
_VALLEY = [
    (220, 615, 340, 675), (220, 615, 220, 795), (220, 795, 340, 735),  # left
    (340, 675, 340, 735),                                              # shared
    (460, 615, 340, 675), (460, 615, 460, 795), (460, 795, 340, 735),  # right
]


def generate(params: BellowsParams) -> FoldPattern:
    """Build the Waterbomb unit cell scaled by ``params.cell_scale``."""
    params.validate()
    return cell_from_edges("waterbomb", _MOUNTAIN, _VALLEY, params.cell_scale)


__all__ = ["generate"]
