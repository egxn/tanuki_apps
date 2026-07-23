"""Yoshimura unit cell — one diamond of a regular diamond grid.

A *square rhombus* (diamond) whose four diagonal arms are mountains.  Two families
of horizontal valley creases run through it: one along the diamond's **middle**
(its horizontal diagonal, left↔right) and one through its **tip/tail** junction
(the line where this row's bottom point meets the next row's top point).  Tiled on
a plain square grid the diamonds repeat as a regular lattice — no brick offset.
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import cell_from_edges, FoldPattern

# Diamond corners in a 100×100 cell: L/R on the mid line, T/B at the tip/tail.
_L, _R = (0, 50), (100, 50)
_T, _B = (50, 0), (50, 100)

# Diagonal arms — mountain.
_MOUNTAIN = [
    (*_L, *_T), (*_T, *_R),            # upper arms
    (*_R, *_B), (*_B, *_L),            # lower arms
]
# Horizontal fold axes — valley: through the middle and through the tip/tail line.
_VALLEY = [
    (*_L, *_R),                        # middle axis (horizontal diagonal)
    (0, 0, 100, 0),                    # tip/tail junction (between rows)
]


def generate(params: BellowsParams) -> FoldPattern:
    """Build the Yoshimura diamond cell scaled by ``params.cell_scale``."""
    params.validate()
    return cell_from_edges("yoshimura", _MOUNTAIN, _VALLEY, params.cell_scale)


__all__ = ["generate"]
