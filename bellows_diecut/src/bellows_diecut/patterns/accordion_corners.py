"""Accordion-with-corners unit cell.

Variant of :mod:`accordion` where each horizontal row is one continuous fold
type: solid, dotted, solid.  Extra vertical valley folds pass through the
corners of the original short trapezoid bases.
"""

from __future__ import annotations

from ..parameters import BellowsParams
from ..core.geometry import FoldPattern, FoldType

def generate(params: BellowsParams) -> FoldPattern:
    """Build the accordion-with-corners cell scaled by ``params.cell_scale``."""
    params.validate()
    s = params.cell_scale
    long_base = params.accordion_long_base
    offset = params.accordion_offset
    height = params.accordion_band_height
    period = 2.0 * (long_base - offset)
    width = period + offset
    mountain: list = [
        ((0.0, 0.0), (width, 0.0)),
        ((0.0, 2.0 * height), (width, 2.0 * height)),
    ]
    valley: list = [
        ((0.0, height), (width, height)),
        # Trapezoid slants from the base accordion pattern.
        ((0.0, 0.0), (offset, height)),
        ((long_base, 0.0), (long_base - offset, height)),
        ((0.0, 2.0 * height), (offset, height)),
        ((long_base, 2.0 * height), (long_base - offset, height)),
    ]

    # Vertical folds through parametrically-derived short-base corners.  One
    # fold is centred; two folds preserve both trapezoid corners.
    corners = (offset, long_base - offset)
    if params.accordion_corner_folds == 1:
        corners = ((corners[0] + corners[1]) / 2.0,)
    elif params.accordion_corner_folds == 0:
        corners = ()
    for x in corners:
        valley.append(((x, 0.0), (x, 2.0 * height)))

    pat = FoldPattern(
        name="accordion_corners",
        width=width * s,
        height=2 * height * s,
        seam=False,
    )
    for a, b in mountain:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.MOUNTAIN)
    for a, b in valley:
        pat.add_fold((a[0] * s, a[1] * s), (b[0] * s, b[1] * s), FoldType.VALLEY)
    pat.add_outline()
    return pat


__all__ = ["generate"]
