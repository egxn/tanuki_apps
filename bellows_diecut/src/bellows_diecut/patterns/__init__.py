"""Bellows Diecut — pattern generators (single unit cells).

Each module exposes ``generate(params) -> FoldPattern`` building one tile from the
SVG reference in ``README.md`` (no tessellation yet).  The :data:`REGISTRY` maps a
pattern name to its generator so callers can dispatch by string::

    from bellows_diecut.patterns import get_generator
    pat = get_generator("yoshimura")(params)
"""

from __future__ import annotations

from collections.abc import Callable

from ..parameters import BellowsParams
from ..core.geometry import FoldPattern
from . import (
    yoshimura, miura, waterbomb, kresling, resch, accordion,
    accordion_corners,
)

Generator = Callable[[BellowsParams], FoldPattern]

#: Pattern name → generator function.
REGISTRY: dict[str, Generator] = {
    "yoshimura": yoshimura.generate,
    "miura": miura.generate,
    "waterbomb": waterbomb.generate,
    "kresling": kresling.generate,
    "resch": resch.generate,
    "accordion": accordion.generate,
    "accordion_corners": accordion_corners.generate,
}


def get_generator(name: str) -> Generator:
    """Return the generator for *name*, or raise ``KeyError`` with a hint."""
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown pattern {name!r}. Available: {sorted(REGISTRY)}"
        ) from None


def generate(name: str, params: BellowsParams) -> FoldPattern:
    """Dispatch to the named pattern generator."""
    return get_generator(name)(params)


__all__ = ["REGISTRY", "Generator", "get_generator", "generate",
           "yoshimura", "miura", "waterbomb", "kresling", "resch",
           "accordion", "accordion_corners"]
