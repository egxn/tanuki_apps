"""Rollers — the fold pattern wrapped onto a cylinder (male / female pair).

An alternative to the flat dies (README "Roller system"): two complementary
rollers stamp the fold pattern continuously as the fabric is fed between them.
Each roller is the tessellated foldcore relief **wrapped around a cylinder** —
the circumference carries an integer number of tiles so the pattern meets itself
seamlessly at the wrap.  The male roller carries the relief outward; the female
is its negative, so the two mesh like gears with the fabric in between.

Build: take the flat tessellated surface (``around × length`` tiles), wrap each
vertex to ``(R + ±relief)`` at angle ``x/circumference·2π``, weld the seam, add a
smooth inner core cylinder and the two end rings → a closed solid.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from ..parameters import BellowsParams
from . import foldcore, tessellate

#: Wall left between the deepest relief and the bored core (mm).
_CORE_WALL = 4.0


def min_tiles_around(name: str) -> int:
    """Minimum tiles around the circumference for a seamless wrap.

    The cells tile seamlessly, so one full pattern width (the grid's ``n``) wraps
    to a closed ring whose seam meets — this matches the bellows perimeter.
    """
    return tessellate.TILE_SPECS[name]["grid"][0]


def build_roller(
    name: str,
    side: str = "male",
    around: int | None = None,
    length: int | None = None,
    core_wall: float | None = None,
):
    """Build a *side* roller solid (verts (M,3), faces (K,3)).

    *around* tiles wrap the circumference (default :func:`min_tiles_around`),
    *length* tiles run along the axis (default the grid's ``m``).  The male
    carries the relief outward; the female carries its negative so the two mesh.

    Built by bending the watertight flat foldcore solid into a cylinder — the
    relief (``z``) becomes the radial offset and ``x`` the wrap angle — so the
    result is closed by construction regardless of the tiling rule.
    """
    if side not in ("male", "female"):
        raise ValueError("side must be 'male' or 'female'")
    if core_wall is None:
        core_wall = _CORE_WALL
    spec = tessellate.TILE_SPECS[name]
    n, m = spec["grid"]
    around = around or min_tiles_around(name)
    length = length or m

    # Periodic strip — exactly one circumference wide, so the wrap meets itself
    # (brick / interlock tilings otherwise overhang the period as a flat seam).
    pat, period = tessellate.tessellate_periodic(name, around, length)
    params = tessellate.tile_params(name)
    # wrap_period makes the relief periodic so the seam closes without a step
    pts, z, tris, boundary = foldcore.build_surface(pat, params, wrap_period=period)

    relief = z if side == "male" else -z          # female = the meshing negative
    z_floor = float(relief.min()) - core_wall
    top = relief
    bottom = np.full_like(relief, z_floor)
    flat, faces = foldcore._thicken(pts, tris, boundary, top, bottom)

    # ── Bend the flat solid into a cylinder: x → wrap angle, z → radius ────
    x = flat[:, 0]
    width = float(pts[:, 0].max() - pts[:, 0].min())   # == period (one wrap)
    radius = width / (2.0 * math.pi)
    theta = (x - float(pts[:, 0].min())) / width * 2.0 * math.pi
    r = radius + flat[:, 2]
    verts = np.column_stack([r * np.cos(theta), r * np.sin(theta), flat[:, 1]])
    return verts, faces


# ---------------------------------------------------------------------------
# OBJ export
# ---------------------------------------------------------------------------

def export_roller_obj(name: str, path: str | Path, side: str = "male",
                      around: int | None = None, length: int | None = None) -> Path:
    """Build *side*'s roller and write it as an OBJ (for the DSL to import)."""
    verts, faces = build_roller(name, side, around, length)
    return foldcore.write_obj(verts, faces, path)


# ---------------------------------------------------------------------------
# STL export (native Python, no Blender required)
# ---------------------------------------------------------------------------

def export_roller_stl(name: str, path: str | Path, side: str = "male",
                      around: int | None = None, length: int | None = None) -> Path:
    """Build *side*'s roller and write it as a binary STL file."""
    import struct

    verts, faces = build_roller(name, side, around, length)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    v = np.asarray(verts, dtype=np.float32)
    f = np.asarray(faces, dtype=np.int32)

    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    normals = np.cross(b - a, c - a).astype(np.float32)
    norms = np.linalg.norm(normals, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normals /= norms

    # Binary STL: 80-byte header + uint32 count + 50 bytes/triangle
    # (12 normal + 36 vertices + 2 attribute, no padding)
    dtype = np.dtype([("n", "<f4", 3), ("v0", "<f4", 3),
                      ("v1", "<f4", 3), ("v2", "<f4", 3), ("attr", "<u2")])
    records = np.zeros(len(f), dtype=dtype)
    records["n"] = normals
    records["v0"] = a; records["v1"] = b; records["v2"] = c

    with open(path, "wb") as fp:
        fp.write(b"\0" * 80)
        fp.write(struct.pack("<I", len(f)))
        fp.write(records.tobytes())
    return path


def build_graphs(name: str, obj_dir: str | Path,
                 around: int | None = None, length: int | None = None) -> dict:
    """Write the roller OBJs to *obj_dir* and return their DSL import graphs."""
    from .diecut import _die_graph

    obj_dir = Path(obj_dir)
    graphs = {}
    for side in ("male", "female"):
        gname = f"{name}_roller_{side}"
        obj = obj_dir / f"{gname}.obj"
        export_roller_obj(name, obj, side=side, around=around, length=length)
        graphs[side] = _die_graph(gname, obj)
    return graphs


__all__ = [
    "min_tiles_around", "build_roller",
    "export_roller_obj", "export_roller_stl",
    "build_graphs",
]
