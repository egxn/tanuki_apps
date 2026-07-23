"""Miura unit cell.

Two stacked V shapes forming a diapason / Y structure.  The top lateral columns,
the central V arms and the lower central axis are mountains; the inner diagonals,
the mid columns and the lower diagonals are valleys.  Geometry transcribed from
the SVG reference in ``README.md``.
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import cell_from_edges, FoldPattern

_MOUNTAIN = [
    (220, 315, 220, 395), (460, 315, 460, 395),    # top lateral columns (E1, F1)
    (220, 395, 340, 475), (460, 395, 340, 475),    # central V arms (J, K)
    (340, 475, 340, 555),                          # lower central axis (G3)
]
_VALLEY = [
    (220, 315, 340, 395), (460, 315, 340, 395),    # upper diagonals to centre
    (220, 395, 220, 475), (460, 395, 460, 475),    # mid columns
    (340, 395, 340, 475),                          # central mid axis
    (220, 475, 340, 555), (460, 475, 340, 555),    # lower diagonals
]


def generate(params: BellowsParams) -> FoldPattern:
    """Build the Miura unit cell scaled by ``params.cell_scale``."""
    params.validate()
    return cell_from_edges("miura", _MOUNTAIN, _VALLEY, params.cell_scale)


__all__ = ["generate"]
