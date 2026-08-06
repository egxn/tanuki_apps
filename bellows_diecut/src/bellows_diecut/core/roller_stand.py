"""Tanuki assembly script for a matched pair of bellows rollers.

The rollers remain independent printable parts.  This module produces a Blender
script from Tanuki IR that imports them and builds two end laterals, each with
two smaller cylindrical pivots that run inside the rollers' hollow cores.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tanuki.dsl import cube, cylinder, import_obj, join, model, output, realize_instances, translate
from tanuki.dsl.export import combined_export

from . import roller
from .exporter import _PACKAGE_SRC, _TANUKI_SRC


def _layout(name: str, around: int, length: int) -> dict[str, float]:
    """Derive stand and pivot dimensions from the actual roller meshes."""
    male, _ = roller.build_roller(name, "male", around, length)
    female, _ = roller.build_roller(name, "female", around, length)
    rm = np.hypot(male[:, 0], male[:, 1])
    rf = np.hypot(female[:, 0], female[:, 1])
    outer_m, outer_f = float(rm.max()), float(rf.max())
    # The smallest radial coordinate is the hollow-core wall.  Leave 15 %
    # clearance on the pivot radius so an FDM-printed roller can turn freely.
    pivot_r = max(1.0, min(float(rm.min()), float(rf.min())) * 0.85)
    separation = outer_m + outer_f + 1.0
    z0 = min(float(male[:, 2].min()), float(female[:, 2].min()))
    z1 = max(float(male[:, 2].max()), float(female[:, 2].max()))
    side_t, pin_d = 4.0, 8.0
    return {"male_x": -separation / 2, "female_x": separation / 2,
            "pivot_r": pivot_r, "z0": z0, "z1": z1,
            "side_t": side_t, "pin_d": pin_d,
            "side_w": separation + 2 * max(outer_m, outer_f) + 16.0,
            "side_h": 2 * max(outer_m, outer_f) + 16.0}


def _graph(name: str, geometry):
    with model(name) as ctx:
        output(geometry | realize_instances())
    return ctx.graph


def build_graphs(name: str, obj_dir: str | Path, around: int, length: int) -> list:
    """Build Tanuki IR graphs for rollers and both pivot laterals."""
    obj_dir = Path(obj_dir)
    d = _layout(name, around, length)
    male = import_obj(str((obj_dir / f"{name}_roller_male.obj").resolve())) | translate(d["male_x"], 0, 0)
    female = import_obj(str((obj_dir / f"{name}_roller_female.obj").resolve())) | translate(d["female_x"], 0, 0)

    def lateral(label: str, z: float, pin_z: float):
        plate = cube(d["side_w"], d["side_h"], d["side_t"], f"{label}_plate") | translate(0, 0, z)
        pins = [
            cylinder(d["pivot_r"], d["pin_d"], f"{label}_male_pivot") | translate(d["male_x"], 0, pin_z),
            cylinder(d["pivot_r"], d["pin_d"], f"{label}_female_pivot") | translate(d["female_x"], 0, pin_z),
        ]
        return _graph(f"{name}_{label}", join([plate, *pins]))

    left_z = d["z0"] - d["side_t"] / 2
    right_z = d["z1"] + d["side_t"] / 2
    return [_graph(f"{name}_roller_male", male), _graph(f"{name}_roller_female", female),
            lateral("roller_lateral_left", left_z, d["z0"] + d["pin_d"] / 2),
            lateral("roller_lateral_right", right_z, d["z1"] - d["pin_d"] / 2)]


def generate_script(name: str, output_dir: str | Path, around: int, length: int) -> Path:
    """Compile a standalone Blender Python script from the Tanuki IR graphs."""
    output_dir = Path(output_dir)
    path = output_dir / f"{name}_roller_stand.py"
    graphs = build_graphs(name, output_dir / "mesh", around, length)
    combined_export(graphs, path)
    base = path.read_text()
    header = (
        "import sys\n"
        f'sys.path.insert(0, r"{_PACKAGE_SRC}")\n'
        f'sys.path.insert(0, r"{_TANUKI_SRC}")\n'
    )
    first, _, rest = base.partition("\n")
    path.write_text(f"{first}\n{header}{rest}")
    return path


__all__ = ["build_graphs", "generate_script"]
