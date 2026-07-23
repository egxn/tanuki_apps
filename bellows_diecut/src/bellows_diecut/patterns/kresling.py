"""Kresling unit cell (symmetric).

Two horizontally stacked parallelograms, mirrored vertically.  All frame edges
are mountain; the V formed by the two inner diagonals (one per parallelogram) is
valley.  Geometry transcribed from the SVG reference in ``README.md``.
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import cell_from_edges, FoldPattern

# Parallelogram frames — mountain.
_MOUNTAIN = [
    (200, 855, 460, 855),                          # top edge
    (200, 855, 160, 935), (460, 855, 420, 935),    # upper sides
    (160, 935, 420, 935),                          # middle edge
    (160, 935, 200, 1015), (420, 935, 460, 1015),  # lower sides
    (200, 1015, 460, 1015),                        # bottom edge
]
# The two inner diagonals (one per parallelogram) forming a V — valley.
_VALLEY = [
    (460, 855, 160, 935),
    (160, 935, 460, 1015),
]


def generate(params: BellowsParams) -> FoldPattern:
    """Build the Kresling unit cell scaled by ``params.cell_scale``."""
    params.validate()
    return cell_from_edges("kresling", _MOUNTAIN, _VALLEY, params.cell_scale)


__all__ = ["generate"]
