from tanuki.dsl import *
from math import cos, radians, sin

tolerance = 0.125
wood = 25.5
joint = wood + 10
joint_vertices = 32
r_screw = 4

def build_cylinder(use_tap=True, h_tap_width=10, coupler_height=60):
        coupler_1 = cylinder(joint/2, coupler_height, "coupler_1", vertices=joint_vertices)

        tap = cube(20, 42, 20, "tap")
        tap_bridge = cube(28, 6, coupler_height, "tap_bridge")

        if use_tap:
            coupler_1 = union([
                coupler_1,
                tap | place(0, wood/2, 20),
                tap | place(0, wood/2, -20),
                tap_bridge | place(0, 15 , 0)
            ])

        h_coupler_1 = cylinder(wood/2 + tolerance * 2, coupler_height, "h_coupler_1", vertices=64)
        h_tap = cube(h_tap_width, 50, 80, "h_tap")             

        coupler_1 = difference(coupler_1, [
            h_coupler_1,
            h_tap | place(0, wood/2 + 5, 0),
            h_tap | place(0, wood/2 + 5, 0)
        ])

        coupler_1 = difference(coupler_1, [
            cylinder(r_screw, 40, "coupler_2", vertices=124) | rotate(0, 90, 0) | place(0, 25,  20),
            cylinder(r_screw, 40, "coupler_3", vertices=124) | rotate(0, 90, 0) | place(0, 25, -20)
        ])

        return coupler_1

def create_tube_support():
    with model("wood_join") as ctx:
        coupler_1 = build_cylinder()
        coupler_2 = coupler_1 | rotate(0, 90, 180) | rotate(-90, 0, 0) | place(0, -33, -11.25)

        coupler_1 = union([
            coupler_1,
            coupler_2,
        ]) | place(0, 0, 500)

        output(coupler_1)
    return ctx.graph

def create_base():
    with model("base") as ctx:
        hub_height = 50
        leg_radius = joint / 2
        leg_length = 50
        leg_tilt = 140
        leg_angles = (0, 120, 240)

        tilt_radians = radians(leg_tilt)
        leg_offset_y = -leg_length / 2 * sin(tilt_radians)
        leg_offset_z = leg_length / 2 * cos(tilt_radians)

        legs = [
            cylinder(leg_radius, leg_length, f"leg_{angle}", vertices=joint_vertices)
            | rotate(leg_tilt, 0, 0)
            | translate(0, leg_offset_y, leg_offset_z)
            | rotate(0, 0, angle)
            for angle in leg_angles
        ]

        h_legs = [
            cylinder(wood/2 + tolerance * 2, leg_length + 10, f"h_leg_{angle}", vertices=64)
            | rotate(leg_tilt, 0, 0)
            | translate(0, leg_offset_y, leg_offset_z)
            | rotate(0, 0, angle)
            for angle in leg_angles
        ]

        # The vertical hub starts at the same origin and joins the three legs.
        hub = build_cylinder(False, 0, hub_height) | place(0, 0, hub_height / 2)
        base = union([hub, *legs])
        base = difference(base, h_legs)

        output(base)
    return ctx.graph

def create_rods():
    with model("lamp") as ctx:
        rod_1 = cylinder(wood/2, 600, "rod_1", vertices=joint_vertices) | place(0, 0, 300)
        rod_2 = cylinder(wood/2, 600, "rod_2", vertices=joint_vertices) | rotate(0, 90, 0) | place(100, -33, 488.75)

        rod_base_length = 300
        rod_base_angles = (0, 120, 240)

        rod_tilt = 140
        tilt_radians = radians(rod_tilt)
        leg_offset_y = -rod_base_length / 2 * sin(tilt_radians)
        leg_offset_z = rod_base_length / 2 * cos(tilt_radians)

        rods = [
            cylinder(wood/2, 300, f"leg_{angle}", vertices=joint_vertices)
            | rotate(rod_tilt, 0, 0)
            | translate(0, leg_offset_y, leg_offset_z)
            | rotate(0, 0, angle)
            for angle in rod_base_angles
        ]


        output(
            join([rod_1, rod_2, *rods])
        )
    return ctx.graph

ALL_PARTS = [
    create_tube_support(),
    create_base(),
    create_rods()
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
