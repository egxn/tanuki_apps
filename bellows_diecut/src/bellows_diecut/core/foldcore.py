"""Foldcore — the folded 3D state of a fold pattern (matched dies).

The two dies form the fabric into the *folded* pattern: every region between
fold lines becomes a flat tilted facet (mountains up, valleys down), with no flat
horizontal areas.  Male and female are the **same folded surface** offset by one
fabric thickness (matched dies), so pressing them creases the cloth everywhere.

Pipeline (pure Python / NumPy):

1. ``arrangement`` — split every fold segment (mountain/valley/boundary) at its
   crossings into a planar graph of vertices + classified edges.
2. ``faces`` — trace the bounded regions of that graph.
3. ``vertex_heights`` — z per vertex from the mountain/valley balance, scaled by
   the relief amplitude (``relief_dims``).
4. ``build_surface`` — fan-triangulate each face into flat tilted facets.
5. ``build_die`` — thicken the surface into a closed male/female solid.
6. ``write_obj`` — emit the mesh; the DSL then imports it and bakes the STL.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from ..parameters import BellowsParams
from .geometry import FoldPattern, FoldType

_EPS = 1e-7
_ROUND = 5          # decimals for vertex dedup
_FOLD_RATIO = 0.2   # default fold depth as a fraction of the smaller tile side


def fold_amplitude(pattern: FoldPattern, params: BellowsParams) -> float:
    """Peak-to-mid fold depth ``A`` (mm).

    Defaults to a fraction of the tile size so every pattern folds to a
    consistent, clearly-tilted depth; ``params.ridge_height`` overrides it.
    """
    if getattr(params, "ridge_height", None) is not None:
        return float(params.ridge_height)
    return _FOLD_RATIO * min(pattern.width, pattern.height)


# ---------------------------------------------------------------------------
# 1. Planar arrangement (split segments at crossings)
# ---------------------------------------------------------------------------

def _seg_intersection(a, b, c, d):
    """Param ``(t, u)`` where segments a–b and c–d cross, or ``None``."""
    r = b - a
    s = d - c
    rxs = r[0] * s[1] - r[1] * s[0]
    if abs(rxs) < 1e-12:
        return None                       # parallel / collinear
    qp = c - a
    t = (qp[0] * s[1] - qp[1] * s[0]) / rxs
    u = (qp[0] * r[1] - qp[1] * r[0]) / rxs
    if -_EPS <= t <= 1 + _EPS and -_EPS <= u <= 1 + _EPS:
        return t, u
    return None


def arrangement(pattern: FoldPattern):
    """Return ``(points (N,2) array, edges list[(i, j, FoldType)])``.

    Every fold segment is split at its crossings with the others, so the result
    is a proper planar graph (no edge crosses another except at shared vertices).
    """
    segs = [(np.asarray(fl.p0, float), np.asarray(fl.p1, float), fl.kind)
            for fl in pattern.fold_lines]
    n = len(segs)
    # Per-segment axis-aligned bbox, to skip far-apart pairs (O(n²) → ~O(n) for
    # a big tessellation where most edges are nowhere near each other).
    bb = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
          for (a, b, _k) in segs]
    splits = [{0.0, 1.0} for _ in range(n)]
    for i in range(n):
        ai, bi, _ = segs[i]
        bxi0, byi0, bxi1, byi1 = bb[i]
        for j in range(i + 1, n):
            bxj0, byj0, bxj1, byj1 = bb[j]
            if bxi1 < bxj0 - _EPS or bxj1 < bxi0 - _EPS \
                    or byi1 < byj0 - _EPS or byj1 < byi0 - _EPS:
                continue
            aj, bj, _ = segs[j]
            hit = _seg_intersection(ai, bi, aj, bj)
            if hit is None:
                continue
            ti, tj = hit
            if _EPS < ti < 1 - _EPS:
                splits[i].add(ti)
            if _EPS < tj < 1 - _EPS:
                splits[j].add(tj)

    points: list[tuple[float, float]] = []
    index: dict[tuple[float, float], int] = {}

    def vid(p) -> int:
        key = (round(float(p[0]), _ROUND), round(float(p[1]), _ROUND))
        if key not in index:
            index[key] = len(points)
            points.append(key)
        return index[key]

    edges: dict[tuple[int, int], FoldType] = {}
    _PRI = {FoldType.MOUNTAIN: 2, FoldType.VALLEY: 2, FoldType.BOUNDARY: 1}
    for k, (a, b, kind) in enumerate(segs):
        ts = sorted(splits[k])
        for t0, t1 in zip(ts, ts[1:]):
            p0 = a + t0 * (b - a)
            p1 = a + t1 * (b - a)
            i0, i1 = vid(p0), vid(p1)
            if i0 == i1:
                continue
            key = (min(i0, i1), max(i0, i1))
            # On overlap keep the crease over the boundary outline.
            if key not in edges or _PRI[kind] > _PRI[edges[key]]:
                edges[key] = kind

    pts = np.asarray(points, float)
    edge_list = [(i, j, kind) for (i, j), kind in edges.items()]
    return pts, edge_list


# ---------------------------------------------------------------------------
# 2. Face extraction (half-edge tracing)
# ---------------------------------------------------------------------------

def _signed_area(loop, pts) -> float:
    a = 0.0
    for k in range(len(loop)):
        x0, y0 = pts[loop[k]]
        x1, y1 = pts[loop[(k + 1) % len(loop)]]
        a += x0 * y1 - x1 * y0
    return 0.5 * a


def faces(pts, edge_list):
    """Trace the bounded faces of the planar graph as vertex-index loops."""
    out = defaultdict(list)                 # v -> list of (angle, w)
    for (i, j, _kind) in edge_list:
        out[i].append((math.atan2(pts[j][1] - pts[i][1], pts[j][0] - pts[i][0]), j))
        out[j].append((math.atan2(pts[i][1] - pts[j][1], pts[i][0] - pts[j][0]), i))
    for v in out:
        out[v].sort()
    pos = {}                                # (v, w) -> index in out[v]
    for v, lst in out.items():
        for k, (_ang, w) in enumerate(lst):
            pos[(v, w)] = k

    used: set[tuple[int, int]] = set()
    result = []
    for (i, j, _kind) in edge_list:
        for (u, v) in ((i, j), (j, i)):
            if (u, v) in used:
                continue
            loop = []
            cu, cv = u, v
            while (cu, cv) not in used:
                used.add((cu, cv))
                loop.append(cu)
                lst = out[cv]
                k = pos[(cv, cu)]
                nw = lst[(k - 1) % len(lst)][1]   # clockwise next → interior CCW
                cu, cv = cv, nw
                if len(loop) > len(edge_list) * 2 + 4:
                    break
            if len(loop) >= 3 and _signed_area(loop, pts) > 1e-6:
                result.append(loop)
    return result


# ---------------------------------------------------------------------------
# 3. Vertex heights (mountain / valley balance)
# ---------------------------------------------------------------------------

def _seam_pairs(pts, wrap_period: float):
    """Match left-edge (``x≈xmin``) to right-edge (``x≈xmax``) vertices by ``y``.

    Yields ``(left_i, right_j)`` index pairs — the vertices that coincide once the
    strip of width *wrap_period* is wrapped into a cylinder.
    """
    x = pts[:, 0]
    xmin, xmax = float(x.min()), float(x.max())
    tol = 1e-3 * max(xmax - xmin, 1.0)
    left = {round(float(pts[i, 1]), 4): i
            for i in np.where(np.abs(x - xmin) < tol)[0]}
    for j in np.where(np.abs(x - xmax) < tol)[0]:
        i = left.get(round(float(pts[j, 1]), 4))
        if i is not None:
            yield i, j


def vertex_heights(pts, edge_list, amplitude: float, wrap_period: float | None = None):
    """Z per vertex: ``+amplitude`` on mountains, ``−amplitude`` on valleys.

    When *wrap_period* is given the relief is made **periodic** across the wrap
    seam: matched left/right edge vertices share the combined mountain/valley
    balance of both, so a wrapped cylinder closes without a relief step.
    """
    bal = np.zeros((len(pts), 2))           # [mountains, valleys] incident
    for (i, j, kind) in edge_list:
        if kind == FoldType.MOUNTAIN:
            bal[i, 0] += 1; bal[j, 0] += 1
        elif kind == FoldType.VALLEY:
            bal[i, 1] += 1; bal[j, 1] += 1
    if wrap_period is not None:
        for i, j in _seam_pairs(pts, wrap_period):
            combined = bal[i] + bal[j]
            bal[i] = combined; bal[j] = combined
    tot = bal.sum(axis=1)
    z = np.where(tot > 0, amplitude * (bal[:, 0] - bal[:, 1]) / np.maximum(tot, 1), 0.0)
    return z


# ---------------------------------------------------------------------------
# 4. Folded surface (flat tilted facets)
# ---------------------------------------------------------------------------

def _diamond_surface(pattern, pts, edge_list, fcs, amplitude, wrap_period=None):
    """Egg-crate diamond surface for the Yoshimura grid.

    Each diamond is the two large faces sharing a horizontal *middle-axis* valley
    edge; raise their shared centre to ``±amplitude`` (alternating by lattice
    parity) so the diamonds pop in and out, and leave the small inter-diamond gaps
    flat.  Returns ``(pts, z, tris)``.  (The diamond grid's seam vertices already
    sit at the flat base height, so *wrap_period* needs no special handling.)
    """
    pts = list(map(tuple, pts))
    z = [0.0] * len(pts)
    tx, ty = pattern.tile
    x0 = min(p[0] for p in pts)
    y0 = min(p[1] for p in pts)

    def _is_centre(cx, cy) -> bool:
        # Diamond centres sit at (x0+tx/2+i·tx, y0+ty/2+j·ty); only the middle-axis
        # edge of a diamond has its midpoint there (between-row edges do not).
        fx = ((cx - x0 - tx / 2) / tx) % 1.0
        fy = ((cy - y0 - ty / 2) / ty) % 1.0
        return min(fx, 1 - fx) < 1e-3 and min(fy, 1 - fy) < 1e-3

    def _area(loop):
        a = 0.0
        for k in range(len(loop)):
            x0, y0 = pts[loop[k]]
            x1, y1 = pts[loop[(k + 1) % len(loop)]]
            a += x0 * y1 - x1 * y0
        return abs(a) / 2.0

    areas = [_area(l) for l in fcs]
    thresh = 0.5 * (min(areas) + max(areas))   # diamond halves vs small gaps

    e2f: dict[frozenset, list[int]] = defaultdict(list)
    for fi, loop in enumerate(fcs):
        for k in range(len(loop)):
            e2f[frozenset((loop[k], loop[(k + 1) % len(loop)]))].append(fi)

    tris: list[tuple[int, int, int]] = []
    big = [a > thresh for a in areas]
    consumed: set[int] = set()
    # Diamonds: the horizontal valley edge shared by the two large halves — raise
    # their shared centre to ±amplitude (alternating) into a pop-in/out pyramid.
    for e, fis in e2f.items():
        if len(fis) != 2 or not (big[fis[0]] and big[fis[1]]):
            continue
        a, b = tuple(e)
        (ax, ay), (bx, by) = pts[a], pts[b]
        if abs(ay - by) > 1e-6:
            continue
        cx, cy = 0.5 * (ax + bx), 0.5 * (ay + by)
        if not _is_centre(cx, cy):
            continue
        parity = (round((cx - x0 - tx / 2) / tx) + round((cy - y0 - ty / 2) / ty)) % 2
        ci = len(pts)
        pts.append((cx, cy))
        z.append(amplitude if parity == 0 else -amplitude)
        for fi in fis:
            loop = fcs[fi]
            for k in range(len(loop)):
                p, q = loop[k], loop[(k + 1) % len(loop)]
                if frozenset((p, q)) != e:
                    tris.append((p, q, ci))
        consumed.update(fis)
    # Everything else (inter-diamond gaps, clipped boundary halves) stays flat —
    # fan from the face centroid (robust for the non-convex gap polygons).
    for fi, loop in enumerate(fcs):
        if fi in consumed:
            continue
        cx = sum(pts[i][0] for i in loop) / len(loop)
        cy = sum(pts[i][1] for i in loop) / len(loop)
        mz = sum(z[i] for i in loop) / len(loop)
        ci = len(pts)
        pts.append((cx, cy))
        z.append(mz)
        for k in range(len(loop)):
            tris.append((loop[k], loop[(k + 1) % len(loop)], ci))
    return pts, z, tris


def _accordion_surface(pattern: FoldPattern, params: BellowsParams,
                       round_x: bool = False):
    """Clean **flat-topped** trapezoidal corrugation (the accordion's relief).

    A trapezoidal wave along Y (clamped sine/cosine → flat crests/troughs at
    ``±amplitude``), constant around X, so the cross-section is a real trapezoid
    and wrapping makes clean bellows rings.  The flat pattern (SVG) shows the
    trapezoid brick; this is its clean folded realisation.  *round_x* subdivides X
    for a round cylinder (rollers) and shifts the phase so peaks land AT the fold
    lines rather than between them.

    For **accordion_corners** rollers, narrow axial grooves are cut at the vertical
    valley fold positions so the corner folds get creased along the roller axis.
    """
    tx, ty = pattern.tile
    x0, y0, x1, y1 = pattern.bounds()
    nx = max(1, round((x1 - x0) / tx))
    ny = max(1, round((y1 - y0) / ty))
    amp = fold_amplitude(pattern, params)

    if round_x:
        # Roller: cosine puts the ridge/channel peaks exactly AT the mountain/valley
        # fold line y-positions (y=y0, y=y0+ty/2, …) so the roller's pressure zones
        # align with the intended crease lines.
        def zof(y: float) -> float:
            w = math.cos(2.0 * math.pi * (y - y0) / ty)
            return amp * max(-1.0, min(1.0, 1.7 * w))
    else:
        # Tile die: sine keeps the steepest-slope (sharpest crease pressure) at the
        # fold line positions — the zero-crossings of sine = the fold line y values.
        def zof(y: float) -> float:
            w = math.sin(2.0 * math.pi * (y - y0) / ty)
            return amp * max(-1.0, min(1.0, 1.7 * w))

    # Accordion-corners roller: add axial grooves at the vertical valley fold x
    # positions so the corner folds are creased along the roller axis.
    groove_xs: list[float] = []
    if round_x and pattern.name.startswith("accordion_corners"):
        for fl in pattern.fold_lines:
            if (fl.kind == FoldType.VALLEY
                    and abs(fl.p0[0] - fl.p1[0]) < 1e-9       # vertical
                    and abs(fl.p1[1] - fl.p0[1]) > ty * 0.4): # spans most of one tile
                groove_xs.append(fl.p0[0])
        groove_xs = sorted(set(round(gx, 3) for gx in groove_xs))

    groove_depth = amp * 0.4        # groove is 40 % of the main corrugation depth
    groove_sigma = tx * 0.06        # Gaussian half-width ≈ 6 % of tile pitch

    def groove_z(x: float) -> float:
        if not groove_xs:
            return 0.0
        d = min(abs(x - gx) for gx in groove_xs)
        if d > groove_sigma * 4.0:
            return 0.0
        return groove_depth * math.exp(-0.5 * (d / groove_sigma) ** 2)

    nrows = max(1, ny) * 12
    rows = [y0 + (y1 - y0) * r / nrows for r in range(nrows + 1)]
    nseg = max(nx, 48) if round_x else nx
    xs = [x0 + (x1 - x0) * k / nseg for k in range(nseg + 1)]

    pts2: list[tuple[float, float]] = []
    z: list[float] = []
    rowverts: list[list[int]] = []
    for y in rows:
        zc = zof(y)
        ridx = []
        for x in xs:
            ridx.append(len(pts2)); pts2.append((x, y)); z.append(zc - groove_z(x))
        rowverts.append(ridx)
    tris: list[tuple[int, int, int]] = []
    for r in range(len(rows) - 1):
        top, bot = rowverts[r], rowverts[r + 1]
        for c in range(len(xs) - 1):
            a, b = top[c], top[c + 1]
            d, e = bot[c], bot[c + 1]
            tris.append((a, b, e)); tris.append((a, e, d))

    pts2 = np.asarray(pts2, float)
    z = np.asarray(z, float)
    centre = (pts2.min(axis=0) + pts2.max(axis=0)) / 2.0
    return pts2 - centre, z, tris, []


def build_surface(pattern: FoldPattern, params: BellowsParams,
                  wrap_period: float | None = None):
    """Return ``(verts2d (N,2), z (N,), tris list[(a,b,c)], boundary_loop)``.

    *wrap_period* (the roller circumference) makes the relief periodic across the
    wrap seam so the cylinder closes without a step (see :func:`vertex_heights`).
    """
    if pattern.name.startswith("accordion") and pattern.tile is not None:
        return _accordion_surface(pattern, params, round_x=wrap_period is not None)

    pts, edge_list = arrangement(pattern)
    fcs = faces(pts, edge_list)
    amplitude = fold_amplitude(pattern, params)

    if pattern.name.startswith("yoshimura") and pattern.tile is not None:
        pts, z, tris = _diamond_surface(pattern, pts, edge_list, fcs, amplitude,
                                        wrap_period)
        pts = np.asarray(pts, float)
        z = np.asarray(z, float)
        boundary = _boundary_loop(pts, edge_list)
        centre = (pts.min(axis=0) + pts.max(axis=0)) / 2.0
        return pts - centre, z, tris, boundary

    z = vertex_heights(pts, edge_list, amplitude, wrap_period)

    pts = list(map(tuple, pts))
    z = list(z)

    def _near_horizontal(loop) -> bool:
        nx = ny = nz = 0.0
        for k in range(len(loop)):
            ax, ay = pts[loop[k]]; az = z[loop[k]]
            bx, by = pts[loop[(k + 1) % len(loop)]]; bz = z[loop[(k + 1) % len(loop)]]
            nx += (ay - by) * (az + bz)
            ny += (az - bz) * (ax + bx)
            nz += (ax - bx) * (ay + by)
        mag = math.sqrt(nx * nx + ny * ny + nz * nz)
        return mag < 1e-9 or abs(nz) / mag > 0.99

    tris: list[tuple[int, int, int]] = []
    for loop in fcs:
        # Always fan from the face centroid — robust for non-convex faces (a
        # loop[0] fan overlaps them) and lets near-horizontal faces be tented so
        # no facet ends up flat.
        cx = sum(pts[i][0] for i in loop) / len(loop)
        cy = sum(pts[i][1] for i in loop) / len(loop)
        mz = sum(z[i] for i in loop) / len(loop)
        bump = (0.5 * amplitude * (1.0 if mz >= 0 else -1.0)
                if _near_horizontal(loop) else 0.0)
        ci = len(pts)
        pts.append((cx, cy)); z.append(mz + bump)
        for k in range(len(loop)):
            tris.append((loop[k], loop[(k + 1) % len(loop)], ci))

    pts = np.asarray(pts, float)
    z = np.asarray(z, float)
    boundary = _boundary_loop(pts, edge_list)
    # Centre the tile on the world origin so dies drop into scenes cleanly.
    centre = (pts.min(axis=0) + pts.max(axis=0)) / 2.0
    pts = pts - centre
    return pts, z, tris, boundary


def _boundary_loop(pts, edge_list=None):
    """Ordered vertex loop around the tile perimeter (the bounding box).

    Computed geometrically (vertices on the bbox edges, sorted by perimeter
    position) so it is robust even when fold lines run along the bbox edge.
    """
    x0, y0 = pts.min(axis=0)
    x1, y1 = pts.max(axis=0)
    w = max(x1 - x0, 1e-9)
    h = max(y1 - y0, 1e-9)
    tol = 1e-4 * max(w, h)

    def perim_param(x, y):
        if abs(y - y0) <= tol:                 # bottom: left → right
            return 0.0 + (x - x0) / w
        if abs(x - x1) <= tol:                 # right: bottom → top
            return 1.0 + (y - y0) / h
        if abs(y - y1) <= tol:                 # top: right → left
            return 2.0 + (x1 - x) / w
        return 3.0 + (y1 - y) / h              # left: top → bottom

    on = [(perim_param(*pts[i]), i) for i in range(len(pts))
          if (abs(pts[i][0] - x0) <= tol or abs(pts[i][0] - x1) <= tol
              or abs(pts[i][1] - y0) <= tol or abs(pts[i][1] - y1) <= tol)]
    on.sort()
    return [i for _p, i in on]


# ---------------------------------------------------------------------------
# 5. Matched-die solids
# ---------------------------------------------------------------------------

def build_die(pattern: FoldPattern, params: BellowsParams, side: str = "male"):
    """Build the *side* die solid (verts (M,3), faces (K,3)).

    Both dies share the same folded surface ``S``; the male is solid below it,
    the female solid above ``S + material_thickness`` (the fabric gap).
    """
    if side not in ("male", "female"):
        raise ValueError("side must be 'male' or 'female'")
    pts, z, tris, boundary = build_surface(pattern, params)
    t = params.material_thickness
    bt = params.base_thickness

    if side == "male":
        top_z = z
        bottom_z = np.full_like(z, float(z.min()) - bt)
    else:
        bottom_z = z + t
        top_z = np.full_like(z, float(z.max()) + t + bt)
    return _thicken(pts, tris, boundary, top_z, bottom_z)


def _thicken(pts, tris, boundary, top_z, bottom_z):
    """Close a surface into a solid: top + bottom layers + walls on the open edges.

    The walls are raised on every *open* edge of the surface (an edge used by a
    single triangle), recovered from ``tris`` directly — so a ragged zigzag
    perimeter or a periodic seam is closed just as cleanly as a straight bbox
    outline.  ``boundary`` is accepted for backwards compatibility but unused.
    """
    n = len(pts)
    verts = np.empty((2 * n, 3))
    verts[:n, :2] = pts; verts[:n, 2] = top_z
    verts[n:, :2] = pts; verts[n:, 2] = bottom_z

    count: dict[frozenset, int] = defaultdict(int)
    for (a, b, c) in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            count[frozenset((u, v))] += 1

    faces: list[tuple[int, int, int]] = []
    for (a, b, c) in tris:
        faces.append((a, b, c))                       # top (normals up)
        faces.append((a + n, c + n, b + n))           # bottom (normals down)
        for u, v in ((a, b), (b, c), (c, a)):         # walls on open edges
            if count[frozenset((u, v))] == 1:
                faces.append((u, v, v + n))
                faces.append((u, v + n, u + n))
    return verts, np.asarray(faces, np.int64)


# ---------------------------------------------------------------------------
# 6. OBJ export
# ---------------------------------------------------------------------------

def write_obj(verts, faces, path: str | Path) -> Path:
    """Write *verts* (M,3) and triangular *faces* (1-based) to an OBJ file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Bellows Diecut foldcore die"]
    lines += [f"v {x:.5f} {y:.5f} {z:.5f}" for x, y, z in verts]
    lines += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in faces]
    path.write_text("\n".join(lines) + "\n")
    return path


def export_die_obj(pattern: FoldPattern, params: BellowsParams,
                   path: str | Path, side: str = "male") -> Path:
    """Build *side*'s die and write it as an OBJ (for the DSL to import)."""
    verts, faces = build_die(pattern, params, side)
    return write_obj(verts, faces, path)


__all__ = [
    "arrangement", "faces", "vertex_heights",
    "build_surface", "build_die", "write_obj", "export_die_obj",
]
