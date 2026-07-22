import math
from tanuki.dsl import *

tolerance = 0.125

def create_lens_support():
    with model("lens_support") as ctx:
        base = cylinder(60, 3, "base", vertices=128)
        h_trq = cylinder(40, 10, "h_trq", vertices=10)
        base = difference(base, [h_trq])

        bases = clones(base, [
            (0, 0, 0),
            (0, 0, 3),
            (0, 0, 6),
            (0, 0, 9),
            (0, 0, 12),
        ])

        n = 24
        radius = 60
        pegs = []
        for i in range(n):
            angle_deg = 360 * i / n
            x = radius * math.cos(2 * math.pi * i / n)
            y = radius * math.sin(2 * math.pi * i / n)
            peg = (cylinder(9.525/4, 20, "peg", vertices=64)
                | rotate(0, 90, 0)
                | rotate(0, 0, angle_deg)
                | place(x, y, 0))
            pegs.append(peg)
        ring = join(pegs)

        bases = join([
            bases,
            ring  | place(0, 0, 6),
        ])

        output(bases)
    return ctx.graph

def create_lens_tooth():
    with model("lens_tooth") as ctx:
        tooth = cylinder(60, 20, "tooth", vertices=128) | rotate(0, 90, 0) | place(0, 0, 75)
        axis = cylinder(24.5/2, 180, "axis", vertices=128) | rotate(0, 90, 0) | place(-30, 0, 75)
        cog_y = cylinder(50, 3, "axis", vertices=128) | rotate(0, 90, 0)

        n = 16
        radius = 40
        positions = [
            (radius * math.cos(2 * math.pi * i / n),
            radius * math.sin(2 * math.pi * i / n),
            0)
            for i in range(n)
        ]

        cyl = cylinder(9.525/4, 30, "peg", vertices=64) | place(-30, 0, 75)
        ring = clones(cyl, positions)

        axis_small = cylinder(9.525/2, 30, "axis_small", vertices=128) | rotate(0, 90, 0) | place(65, 0, 75)

        tooth = join([
            tooth,
            axis,
            clones(cog_y, [
                (60 - 7.5, 0, 75),
                (63 - 7.5, 0, 75),
                (66 - 7.5, 0, 75),
            ]),
            axis_small,
            ring | rotate(0, 90, 0) | place(0, 0, 45),
        ])

        output(tooth)
    return ctx.graph

def create_base():
    with model("base") as ctx:
        base = cube(270, 60, 10, "base") | place(20, 0, -20)
        base_1 = cube(60, 270, 10, "base_1") | place(0, 0, -20)
        base = union([base, base_1])

        base_axis = cube(20, 40, 120, "base_1") | place(0, 0, 35)
        h_base_axis = cylinder(24.5/2 + tolerance*4, 30, "h_base_axis", vertices=128) | rotate(0, 90, 0) | place(0, 0, 75)
        base_axis = difference(base_axis, [h_base_axis])
        base_small_axis = cube(70, 20, 20, "base_small_axis")

        base = join([
            base,
            base_axis | place(-95, 0, 0),
            base_small_axis | place(105, 0, 75),
            cube(20, 40, 110, "base_1") | place(135, 0, 30)
            ])

        output(base)
    return ctx.graph

def create_cage_cog():
    with model("cage_cog") as ctx:
        cage_top = clones(cylinder(60/2, 3, "cage_top", vertices=128), [
            (0, 0, 0),
            (0, 0, 3),
        ])        
        axis = cylinder(9.525/2, 15, "axis", vertices=128)

        cage_1 = cage_top | place(95, 0, 55)
        cage_2 = cage_top | place(95, 0, -5)

        n = 8
        radius = 20
        positions = [
            (radius * math.cos(2 * math.pi * i / n),
            radius * math.sin(2 * math.pi * i / n),
            0)
            for i in range(n)
        ]

        cyl = cylinder(9.525/4, 60, "peg", vertices=64)
        ring = clones(cyl, positions)


        output(
            join([
                cage_1,
                cage_2,
                ring | place(95, 0, 26.5),
                clones(axis, [
                    (95, 0, 64),
                    (95, 0, -14),
                    ])
            ])
        )
    return ctx.graph

ALL_PARTS = [
    create_lens_support(),
    create_lens_tooth(),
    create_base(),
    create_cage_cog(),
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile lens machine parts")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "lens_machine_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "lens_machine_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")
