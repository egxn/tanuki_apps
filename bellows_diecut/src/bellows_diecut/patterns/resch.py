"""Resch unit cell.

Four small squares forming one large square, plus one extra small square attached
to the right side.  All square frame edges are mountain; the X crossing the four
inner squares is valley.  Geometry transcribed from the SVG reference in
``README.md``.
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import cell_from_edges, FoldPattern

# Square frame edges (2×2 block + the attached right square) — mountain.
_MOUNTAIN = [
    # Sq1 (120,1075)-(200,1155)
    (120, 1075, 200, 1075), (120, 1075, 120, 1155),
    (120, 1155, 200, 1155), (200, 1075, 200, 1155),
    # Sq2 (200,1075)-(280,1155)
    (200, 1075, 280, 1075), (280, 1075, 280, 1155), (200, 1155, 280, 1155),
    # Sq3 (120,1155)-(200,1235)
    (120, 1155, 120, 1235), (120, 1235, 200, 1235), (200, 1155, 200, 1235),
    # Sq4 (200,1155)-(280,1235)
    (200, 1235, 280, 1235), (280, 1155, 280, 1235),
    # Sq5 attached right (280,1155)-(360,1235)
    (280, 1155, 360, 1155), (360, 1155, 360, 1235), (280, 1235, 360, 1235),
]
# X across the four inner squares — valley.
_VALLEY = [
    (120, 1075, 280, 1235),
    (280, 1075, 120, 1235),
]


def generate(params: BellowsParams) -> FoldPattern:
    """Build the Resch unit cell scaled by ``params.cell_scale``."""
    params.validate()
    return cell_from_edges("resch", _MOUNTAIN, _VALLEY, params.cell_scale)


__all__ = ["generate"]
