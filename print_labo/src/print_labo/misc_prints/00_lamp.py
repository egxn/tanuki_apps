from tanuki.dsl import *

tolerance = 0.125
wood = 25.5
joint = wood + 10

def create_tube_support():
    with model("wood_join") as ctx:
        cylinder_1 = cylinder(wood/2 + 10, 60, "cylinder_1", vertices=16)
        tap = cube(20, 50, 20, "tap")

        cylinder_1 = union([
            cylinder_1,
            tap | place(0, wood/2, 20),
            tap | place(0, wood/2, -20)
        ])

        h_cylinder_1 = cylinder(joint/2 + tolerance * 2, 70, "h_cylinder_1", vertices=64)
        h_tap = cube(10, 40, 40, "h_tap")

        cylinder_1 = difference(cylinder_1, [
            h_cylinder_1, 
            h_tap | place(0, wood/2, 30),
            h_tap | place(0, wood/2, -30)
        ])

        cylinder_1 = difference(cylinder_1, [
            cylinder(5, 40, "cylinder_2", vertices=124) | rotate(0, 90, 0) | place(0, 30,  20),
            cylinder(5, 40, "cylinder_3", vertices=124) | rotate(0, 90, 0) | place(0, 30, -20)
        ])

        output(cylinder_1)
    return ctx.graph


ALL_PARTS = [
    create_tube_support()
]

if __name__ == "__main__":
    from pathlib import Path

    from print_labo.utils.compile_cli import run_compile_cli

    run_compile_cli(
        graphs=ALL_PARTS,
        description="Compile lamp parts",
        source_script=Path(__file__).resolve(),
        default_output="lamp.py",
        default_output_dir="lamp_gen",
        watch_base_dir=Path(__file__).resolve().parent,
    )