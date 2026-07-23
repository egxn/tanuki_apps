"""Minimal JSON configuration for the Bellows Diecut generators.

A few knobs per pattern are user-facing — **everything else is derived
automatically** (tiling rule, fabric gap, backing, roller wall …):

* ``tile``        — tile size ``[X, Y]`` in mm
* ``fold_height`` — the mountain height (fold relief depth) in mm
* ``repeats``     — how many tiles repeat **along the cylinder height** (axial)
* ``around``      — how many tiles repeat **around the circumference** (horizontal);
  defaults to the pattern's automatic bellows-perimeter count

Schema (every key optional; omitted keys keep their default)::

    {
      "patterns": {
        "yoshimura": {"tile": [16, 16], "fold_height": 7.2, "repeats": 10, "around": 10},
        "miura":     {"tile": [16, 17], "fold_height": 7.7, "repeats": 10, "around": 8},
        ...
      }
    }

Pass a path or dict to any generator's ``config=`` argument, or apply it once with
:func:`configure`.  Omit ``around`` to keep the automatic circumference count.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from .core import tessellate


def _default_fold(name: str) -> float:
    """Auto fold height for a pattern from its tile (the README Z formula)."""
    _tx, ty = tessellate.TILE_SPECS[name]["tile"]
    return round(tessellate.tile_depth(ty), 3)


#: Trapezoids (or cells) per tile, ``(x, y)`` — the accordion packs a 2×2 brick
#: of trapezoids per tile, so its ``around`` / ``repeats`` are **trapezoid counts**
#: that map to ``grid × this``.  Everything else is 1 cell per tile.
_UNITS_PER_TILE = {"accordion": (2, 2), "accordion_corners": (2, 2)}


def _snapshot() -> dict:
    """Capture the current per-pattern config as a JSON-able dict."""
    pats = {}
    for name, spec in tessellate.TILE_SPECS.items():
        ux, uy = _UNITS_PER_TILE.get(name, (1, 1))
        pats[name] = {
            "tile": [spec["tile"][0], spec["tile"][1]],
            "fold_height": spec.get("fold_height", _default_fold(name)),
            "repeats": spec["grid"][1] * uy,
            "around": spec["grid"][0] * ux,
        }
    return {"patterns": pats}


#: The shipped defaults (snapshot of the module values at import).
DEFAULT_CONFIG: dict = _snapshot()


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config(source: str | Path | dict | None) -> dict:
    """Return a complete config dict from *source* merged over the defaults.

    *source* may be a path/str to a JSON file, a dict, or ``None`` (defaults).
    """
    if source is None:
        return copy.deepcopy(DEFAULT_CONFIG)
    if isinstance(source, (str, Path)):
        source = json.loads(Path(source).read_text())
    if not isinstance(source, dict):
        raise TypeError("config must be a path, a dict, or None")
    return _deep_merge(DEFAULT_CONFIG, source)


def apply_config(source: str | Path | dict | None) -> dict:
    """Load *source* and push tile / fold-height / repeats into ``TILE_SPECS``.

    The circumference count, tiling rule and material gaps are left at their
    automatic values.  Returns the resolved (merged) config dict.
    """
    cfg = load_config(source)
    for name, p in cfg["patterns"].items():
        if name not in tessellate.TILE_SPECS:
            continue
        spec = tessellate.TILE_SPECS[name]
        if "tile" in p:
            spec["tile"] = (float(p["tile"][0]), float(p["tile"][1]))
        ux, uy = _UNITS_PER_TILE.get(name, (1, 1))      # trapezoids per tile
        g0, g1 = spec["grid"]                           # (around, repeats) in tiles
        if p.get("around") is not None:
            g0 = max(1, round(int(p["around"]) / ux))
        if p.get("repeats") is not None:
            g1 = max(1, round(int(p["repeats"]) / uy))
        spec["grid"] = (g0, g1)
        if p.get("fold_height") is not None:
            spec["fold_height"] = float(p["fold_height"])
    return cfg


def reset() -> None:
    """Restore the built-in defaults."""
    apply_config(DEFAULT_CONFIG)


def current() -> dict:
    """Return the currently-active config as a JSON-able dict."""
    return _snapshot()


def write_template(path: str | Path, config: str | Path | dict | None = None) -> Path:
    """Write a config JSON to *path* (the defaults, or *config* resolved)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_config(config)
    text = json.dumps(data, indent=2)
    # keep the small [X, Y] arrays on one line for readability
    import re
    text = re.sub(r"\[\s*([\d.eE+-]+),\s*([\d.eE+-]+)\s*\]", r"[\1, \2]", text)
    path.write_text(text + "\n")
    return path


__all__ = [
    "DEFAULT_CONFIG", "load_config", "apply_config", "reset", "current",
    "write_template",
]
