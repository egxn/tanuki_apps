"""Tiny self-contained web UI for the Bellows Diecut generators.

Run ``python -m bellows_diecut.web`` and open the printed URL: adjust
the per-pattern knobs (tile X/Y, fold height, axial repeats), see the generated
tile in 3D, and press *Generate output* to write the tessellated dies, the
rollers and the parametric Geometry-Nodes script.  No web framework required —
just the Python standard library (the 3D preview pulls three.js from a CDN).
"""

from .server import run, make_app

__all__ = ["run", "make_app"]
