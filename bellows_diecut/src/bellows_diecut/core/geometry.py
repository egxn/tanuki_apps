"""Bellows Diecut — flat-development geometry model.

This module defines the **pattern data model** produced by ``patterns/*.py``
and consumed by ``core/diecut.py`` and ``core/exporter.py``.  Everything here
is pure Python (only the stdlib + ``math``); no Blender, no NumPy required.

A :class:`FoldPattern` is one tile developed flat: a 2-D set of vertices plus a
list of :class:`FoldLine` segments, each tagged as a mountain, valley or boundary
crease.  The mold builder extrudes mountain/valley lines into ridges/channels;
the exporters draw them as differentiated lines.

Coordinate convention
---------------------
``(x, y)`` are millimetres, Y-up, with the tile's bottom-left corner at the
origin.  :func:`cell_from_edges` builds a tile from a template edge list and
handles the Y-flip + scaling.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

Point2 = tuple[float, float]


class FoldType(Enum):
    """Crease classification.

    ``MOUNTAIN`` folds away from the viewer (ridge on the male plate),
    ``VALLEY`` folds toward the viewer (ridge on the female plate),
    ``BOUNDARY`` is a cut/outline edge that is not creased.
    """

    MOUNTAIN = "mountain"
    VALLEY = "valley"
    BOUNDARY = "boundary"


@dataclass(frozen=True)
class FoldLine:
    """A single crease segment between two flat points.

    ``p0`` / ``p1`` are ``(x, y)`` in millimetres; ``kind`` classifies the fold.
    """

    p0: Point2
    p1: Point2
    kind: FoldType

    @property
    def length(self) -> float:
        """Segment length (mm)."""
        return math.dist(self.p0, self.p1)

    @property
    def midpoint(self) -> Point2:
        """Segment midpoint ``(x, y)`` (mm)."""
        return ((self.p0[0] + self.p1[0]) / 2.0,
                (self.p0[1] + self.p1[1]) / 2.0)

    @property
    def angle_deg(self) -> float:
        """Angle of the segment relative to +X, in degrees (-180, 180]."""
        dx = self.p1[0] - self.p0[0]
        dy = self.p1[1] - self.p0[1]
        return math.degrees(math.atan2(dy, dx))


@dataclass
class FoldPattern:
    """A bellows pattern developed flat.

    Attributes
    ----------
    name:
        Pattern identifier, e.g. ``"yoshimura"`` — used in output filenames.
    width:
        Developed-flat width (mm), nominally ``pi * diameter``.
    height:
        Developed-flat height (mm).
    fold_lines:
        Every crease segment (mountain, valley) plus the outline (boundary).
    vertices:
        Optional flat ``(x, y)`` grid points, handy for OBJ/JSON export.
    seam:
        ``True`` if the pattern is meant to be closed into a cylinder along the
        right edge (``x == width``) — informational for previews.
    """

    name: str
    width: float
    height: float
    fold_lines: list[FoldLine] = field(default_factory=list)
    vertices: list[Point2] = field(default_factory=list)
    seam: bool = True
    #: Tile pitch ``(tx, ty)`` (mm) when this is a tessellation — lets the
    #: foldcore recover the repeat lattice (e.g. to colour the diamond grid).
    tile: tuple[float, float] | None = None

    # -- construction helpers ----------------------------------------------

    def add_fold(self, p0: Point2, p1: Point2, kind: FoldType) -> None:
        """Append a crease, skipping degenerate zero-length segments."""
        if math.dist(p0, p1) < 1e-9:
            return
        self.fold_lines.append(FoldLine(p0, p1, kind))

    def add_outline(self) -> None:
        """Add the rectangular outline (the bounding box of the creases) as
        four boundary folds, so it encloses every crease for any pattern.
        """
        x0, y0, x1, y1 = self.bounds()
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for i in range(4):
            self.add_fold(corners[i], corners[(i + 1) % 4], FoldType.BOUNDARY)

    # -- queries -----------------------------------------------------------

    def lines_of(self, kind: FoldType) -> list[FoldLine]:
        """Return every fold line of a given :class:`FoldType`."""
        return [fl for fl in self.fold_lines if fl.kind == kind]

    @property
    def mountains(self) -> list[FoldLine]:
        """All mountain creases."""
        return self.lines_of(FoldType.MOUNTAIN)

    @property
    def valleys(self) -> list[FoldLine]:
        """All valley creases."""
        return self.lines_of(FoldType.VALLEY)

    @property
    def boundaries(self) -> list[FoldLine]:
        """All boundary (outline) segments."""
        return self.lines_of(FoldType.BOUNDARY)

    def bounds(self) -> tuple[float, float, float, float]:
        """Return ``(x_min, y_min, x_max, y_max)`` over all fold endpoints."""
        if not self.fold_lines:
            return (0.0, 0.0, self.width, self.height)
        xs = [p[0] for fl in self.fold_lines for p in (fl.p0, fl.p1)]
        ys = [p[1] for fl in self.fold_lines for p in (fl.p0, fl.p1)]
        return (min(xs), min(ys), max(xs), max(ys))

    def summary(self) -> dict[str, int]:
        """Count creases by type — useful for logging and tests."""
        return {
            "mountain": len(self.mountains),
            "valley": len(self.valleys),
            "boundary": len(self.boundaries),
            "vertices": len(self.vertices),
        }


# ---------------------------------------------------------------------------
# Unit-cell construction
# ---------------------------------------------------------------------------

Edge = tuple[float, float, float, float]  # (x0, y0, x1, y1) in template units


def cell_from_edges(
    name: str,
    mountains: list[Edge],
    valleys: list[Edge],
    scale: float = 1.0,
) -> FoldPattern:
    """Build a single-cell :class:`FoldPattern` from template edge lists.

    Edges are given in the pattern's own template coordinates (the SVG reference
    in ``README.md``, which is **Y-down**).  They are normalised to the origin,
    flipped to Y-up, and scaled by *scale* (mm per template unit).  A rectangular
    boundary outline is added last.
    """
    pts = [c for e in (*mountains, *valleys)
           for c in ((e[0], e[1]), (e[2], e[3]))]
    min_x = min(p[0] for p in pts)
    min_y = min(p[1] for p in pts)
    max_y = max(p[1] for p in pts)

    def tf(x: float, y: float) -> Point2:
        return ((x - min_x) * scale, (max_y - y) * scale)   # flip Y → Y-up

    width = (max(p[0] for p in pts) - min_x) * scale
    height = (max_y - min_y) * scale
    pat = FoldPattern(name=name, width=width, height=height, seam=False)

    seen: set[Point2] = set()
    for x0, y0, x1, y1 in mountains:
        a, b = tf(x0, y0), tf(x1, y1)
        pat.add_fold(a, b, FoldType.MOUNTAIN)
        seen.update((a, b))
    for x0, y0, x1, y1 in valleys:
        a, b = tf(x0, y0), tf(x1, y1)
        pat.add_fold(a, b, FoldType.VALLEY)
        seen.update((a, b))

    pat.vertices = sorted(seen)
    pat.add_outline()
    return pat


# ---------------------------------------------------------------------------
# Relief sizing — ridge dimensions from the spacing between fold edges
# ---------------------------------------------------------------------------

def _point_segment_distance(p: Point2, a: Point2, b: Point2) -> float:
    """Distance from point *p* to segment *a*–*b*."""
    ax, ay = a
    bx, by = b
    px, py = p
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom < 1e-12:
        return math.dist(p, a)
    t = ((px - ax) * abx + (py - ay) * aby) / denom
    t = max(0.0, min(1.0, t))
    return math.dist(p, (ax + t * abx, ay + t * aby))


def edge_spacing(pattern: FoldPattern) -> float:
    """Characteristic spacing between fold edges (mm).

    For every mountain/valley crease, measure the distance from its midpoint to
    the *nearest other* crease and take the **median** — a robust estimate of how
    far apart the fold lines sit, used to size the relief so neighbouring ridges
    stay proportional and do not collide.
    """
    creases = pattern.mountains + pattern.valleys
    if len(creases) < 2:
        return min(pattern.width, pattern.height)
    nearest: list[float] = []
    for i, fl in enumerate(creases):
        mid = fl.midpoint
        d = min(
            _point_segment_distance(mid, other.p0, other.p1)
            for j, other in enumerate(creases) if j != i
        )
        if d > 1e-6:
            nearest.append(d)
    if not nearest:
        return min(pattern.width, pattern.height)
    nearest.sort()
    return nearest[len(nearest) // 2]


def relief_dims(pattern: FoldPattern, params) -> tuple[float, float]:
    """Return ``(ridge_width, ridge_height)`` in mm for *pattern*.

    Auto-derived from :func:`edge_spacing` so the triangular ridge is
    proportional to how far apart the fold lines are: ``ridge_width =
    width_ratio · spacing`` and ``ridge_height = height_ratio · ridge_width``
    (``height_ratio = 0.5`` ⇒ ~45° wedge).  Explicit ``params.ridge_width`` /
    ``params.ridge_height`` (when set) override the auto value.
    """
    s = edge_spacing(pattern)
    width = (params.ridge_width if getattr(params, "ridge_width", None) is not None
             else params.width_ratio * s)
    height = (params.ridge_height if getattr(params, "ridge_height", None) is not None
              else params.height_ratio * width)
    return width, height


def merge_collinear(folds: list[FoldLine], tol: float = 1e-3) -> list[FoldLine]:
    """Merge collinear, overlapping/touching creases into maximal straight runs.

    Crease tessellations emit one segment per cell, so a straight fold line (a
    full circumferential row, say) arrives as many short collinear segments that
    *overlap*.  Building one box per segment then yields coplanar, coincident
    faces that make Blender's exact boolean solver fail.  Collapsing each run of
    collinear segments to a single segment removes that degeneracy (and cuts the
    instance count).  Segments are bucketed by ``(kind, line)`` so different fold
    types are never merged together.
    """
    from collections import defaultdict

    buckets: dict[tuple, list[FoldLine]] = defaultdict(list)
    for fl in folds:
        ang = fl.angle_deg % 180.0
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        perp = -dy * fl.p0[0] + dx * fl.p0[1]   # signed distance of the line
        key = (fl.kind, round(ang, 2), round(perp, 2))
        buckets[key].append(fl)

    merged: list[FoldLine] = []
    for (kind, ang, perp), items in buckets.items():
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        # Project every endpoint onto the line direction → 1-D intervals.
        intervals = []
        for fl in items:
            t0 = dx * fl.p0[0] + dy * fl.p0[1]
            t1 = dx * fl.p1[0] + dy * fl.p1[1]
            intervals.append((min(t0, t1), max(t0, t1)))
        intervals.sort()
        cur_s, cur_e = intervals[0]
        runs: list[tuple[float, float]] = []
        for s, e in intervals[1:]:
            if s <= cur_e + tol:
                cur_e = max(cur_e, e)
            else:
                runs.append((cur_s, cur_e))
                cur_s, cur_e = s, e
        runs.append((cur_s, cur_e))
        # Reconstruct each run's endpoints on the original infinite line.
        for s, e in runs:
            p0 = (s * dx - perp * dy, s * dy + perp * dx)
            p1 = (e * dx - perp * dy, e * dy + perp * dx)
            merged.append(FoldLine(p0, p1, kind))
    return merged


__all__ = [
    "Point2",
    "Edge",
    "FoldType",
    "FoldLine",
    "FoldPattern",
    "cell_from_edges",
    "edge_spacing",
    "relief_dims",
    "merge_collinear",
]
