"""Bellows Diecut — parameters.

All dimensions are in **millimetres**.  In this single-unit-cell phase a pattern
is one tile (no repetition yet), so the only pattern knob is ``cell_scale`` — the
size of the tile.  The rest describe the diecut relief and frame.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class BellowsParams:
    """Geometry of a single bellows tile and its diecut.

    The triangular relief is sized **automatically from the spacing between fold
    edges** (see :func:`core.geometry.relief_dims`): wider-apart creases get
    proportionally bigger ridges.  Set ``ridge_width`` / ``ridge_height`` to
    pin an explicit value instead.

    Attributes
    ----------
    cell_scale:
        Millimetres per unit-cell coordinate unit — scales the tile template.
    material_thickness:
        Fabric thickness (mm).  Channel clearance / gap between the matched dies.
    width_ratio:
        Auto ridge base width = ``width_ratio · edge_spacing``.
    height_ratio:
        Auto ridge height = ``height_ratio · ridge_width`` (0.5 ⇒ ~45° wedge).
    ridge_width, ridge_height:
        Explicit overrides (mm); ``None`` ⇒ auto-derive from the edge spacing.
    base_thickness:
        Thickness of the solid backing plate below the relief (mm).
    margin:
        Flat border around the tile (mm) where the pins live.
    pin_radius, pin_height:
        Corner alignment-pin dimensions (mm).
    """

    cell_scale: float = 0.25
    material_thickness: float = 0.3
    width_ratio: float = 0.8
    height_ratio: float = 0.5
    ridge_width: float | None = None
    ridge_height: float | None = None
    base_thickness: float = 5.0
    margin: float = 10.0
    pin_radius: float = 2.5
    pin_height: float = 6.0

    def validate(self) -> None:
        """Raise ``ValueError`` if any parameter is physically nonsensical."""
        if self.cell_scale <= 0:
            raise ValueError("cell_scale must be positive.")
        if self.material_thickness < 0:
            raise ValueError("material_thickness must be non-negative.")
        if self.base_thickness <= 0:
            raise ValueError("base_thickness must be positive.")
        if self.width_ratio <= 0 or self.height_ratio <= 0:
            raise ValueError("width_ratio and height_ratio must be positive.")
        for fld in ("ridge_width", "ridge_height"):
            v = getattr(self, fld)
            if v is not None and v <= 0:
                raise ValueError(f"{fld} must be positive when set.")
        if self.margin < 0:
            raise ValueError("margin must be non-negative.")

    def to_dict(self) -> dict:
        """Serialise to a plain dict (used by the JSON exporter)."""
        return asdict(self)


__all__ = ["BellowsParams"]
