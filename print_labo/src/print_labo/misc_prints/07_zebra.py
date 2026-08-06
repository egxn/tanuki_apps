"""Tanuki model of the early ``board`` geometry.

The original version built a Blender Geometry Nodes tree imperatively.  This
version keeps the dimensions as data and describes the same solid directly in
Tanuki's geometry DSL.
"""

from tanuki.dsl import *


CLR = 0.125  # mm

BOARD_SPEC = {
    "name": "board",
    "length": 396.0,
    "decks": [
        {"id": "top_chest", "size": (396.0, 396.0, 2.0), "z": 24.0},
        {"id": "middle_chest", "size": (396.0, 396.0, 2.0), "z": -16.0},
        {"id": "bottom_chest", "size": (396.0, 396.0, 2.0), "z": -24.0},
    ],
    "walls": {
        "size": (400.0, 2.0, 50.0),
        "y": 199.0,
        "z": 0.0,
    },
    "columns": {
        "size": (20.0, 20.0),
        "upper_height": 38.0,
        "upper_z": 4.0,
        "lower_height": 6.0,
        "lower_z": -20.0,
        "inset": 10.0,
    },
}


def _cube(size, name, position=(0.0, 0.0, 0.0)):
    """Create a centered Tanuki cube and place it at ``position``."""
    return cube(*size, name) | place(*position)


def create_board():
    """Build the board described by :data:`BOARD_SPEC`."""
    spec = BOARD_SPEC
    length = spec["length"]

    with model(spec["name"]) as ctx:
        pieces = [
            _cube(deck["size"], deck["id"], (0, 0, deck["z"]))
            for deck in spec["decks"]
        ]

        wall_x, wall_y, wall_z = spec["walls"]["size"]
        wall_offset = spec["walls"]["y"]
        pieces.extend([
            _cube((wall_x, wall_y, wall_z), "wall_1", (0, wall_offset, 0)),
            _cube((wall_y, wall_x, wall_z), "wall_2", (wall_offset, 0, 0)),
            _cube((wall_y, wall_x, wall_z), "wall_3", (-wall_offset, 0, 0)),
            _cube((wall_x, wall_y, wall_z), "wall_4", (0, -wall_offset, 0)),
        ])

        column = spec["columns"]
        half = length / 2.0 - column["inset"]
        for x in (-half, half):
            for y in (-half, half):
                pieces.append(_cube(
                    (column["size"][0], column["size"][1], column["upper_height"]),
                    "column",
                    (x, y, column["upper_z"]),
                ))
                pieces.append(_cube(
                    (column["size"][0], column["size"][1], column["lower_height"]),
                    "column_bottom",
                    (x, y, column["lower_z"]),
                ))

        output(union(pieces))

    return ctx.graph


ALL_PARTS = [create_board()]


if __name__ == "__main__":
    from pathlib import Path

    from print_labo.utils.compile_cli import run_compile_cli

    run_compile_cli(
        graphs=ALL_PARTS,
        description="Compile zebra board parts",
        source_script=Path(__file__).resolve(),
        default_output="zebra.py",
        default_output_dir="zebra_parts",
        watch_base_dir=Path(__file__).resolve().parent,
    )
