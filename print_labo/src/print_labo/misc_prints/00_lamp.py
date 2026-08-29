from tanuki.dsl import *
from math import cos, radians, sin

tolerance = 0.125
wood = 25.5
joint = wood + 10
joint_vertices = 64
r_screw = 4

def build_cylinder(use_tap=True, h_tap_width=10, coupler_height=40, tap_bridge_tolerance=0, joint_vertices=joint_vertices):
        coupler_1 = cylinder(joint/2, coupler_height, "coupler_1", vertices=joint_vertices)

        tap = cube(20 + tap_bridge_tolerance, 20.5, 20, "tap")
        tap_bridge = cube(28 + tap_bridge_tolerance, 6 + tap_bridge_tolerance, coupler_height, "tap_bridge")

        if use_tap:
            coupler_1 = union([
                coupler_1,
                tap | place(0, wood/2, 10),
                tap | place(0, wood/2, -10),
                tap_bridge | place(0, 20 , 0)
            ])

        h_coupler_1 = cylinder(wood/2 + tolerance * 2, coupler_height, "h_coupler_1", vertices=64)
        h_tap = cube(h_tap_width, 50, 80, "h_tap")             

        coupler_1 = difference(coupler_1, [
            h_coupler_1,
            h_tap | place(0, wood/2 + 5, 0),
            h_tap | place(0, wood/2 + 5, 0)
        ])


        return coupler_1
    
def build_cylinder_seal():
    with model("coupler_seal") as ctx:    
        h_coupler = build_cylinder(tap_bridge_tolerance=tolerance*2)
        seal = cube(35, 10, 40, "seal") | place(0, 20 , 0)
        seal = difference(seal, [h_coupler]) | place(0, 0, 500)
    
        output(seal)
    return ctx.graph

def create_tube_support_y():
    with model("wood_join_y") as ctx:
        coupler_1 = build_cylinder()
        coupler_2 = cylinder(joint/4, 25, "coupler_2_1", vertices=8)
        
        coupler_1 = union([
            coupler_1,
            coupler_2 | rotate(0, 90 , 0) | place(26, 0, 0) ,
        ]) | place(0, 0, 500)

        output(coupler_1)
    return ctx.graph

def create_tube_support_x():
    with model("wood_join_x") as ctx:
        coupler_1 = build_cylinder()
        coupler_2 = cylinder(joint/3, 25, "coupler_2_1") | rotate(0, 90 , 0) | place(26, 0, 0) 
        h_coupler_2 = cylinder(joint/4 + tolerance*4, 25, "coupler_2_1", vertices=8) | rotate(0, 90 , 0) | place(26, 0, 0)
        coupler_2 = difference(coupler_2, [h_coupler_2])
      
        coupler_1 = union([
            coupler_1,
            coupler_2,
        ])  | rotate(90, 0 ,180) | place(57, 0, 500)

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

def create_base_2():
    with model("base_2") as ctx:
        def create_half_spehere(thickness = 0):
            half_sphere = sphere(50 - thickness, "half sphere", 4, 6) | rotate(0 , 0, 45)
            h_sphere = cube(120 + thickness * 2, 120 + thickness * 2, 80 + thickness * 2, "h sphere") | place(0, 0, -47)
            half_sphere = difference(half_sphere, [h_sphere]) | place(0, 0, -10)
            
            return half_sphere

        coupler_1 = build_cylinder(joint_vertices=10) | rotate(90, 0 ,0) | place(0, 50, 0)
        coupler_2 = build_cylinder(joint_vertices=10) | rotate(90, 0, 0) | place(0, -50, 0)
        coupler_3 = build_cylinder(joint_vertices=10) | rotate(90, 0, 90) | place(50, 0, 0)
        coupler_4 = build_cylinder(joint_vertices=10) | rotate(90, 0, 90) | place(-50, 0, 0)

        anti_slop = cylinder(4, 4, "anti_slop")

        half_sphere = difference(
            create_half_spehere(),
            [
                create_half_spehere(5),
                cylinder(wood/2 + tolerance * 2, 200, "h_coupler_1", vertices=64) | rotate(0, 90, 90),
                cylinder(wood/2 + tolerance * 2, 200, "h_coupler_1", vertices=64) | rotate(90, 0, 90),
                anti_slop | place(25, 25, -15),
                anti_slop | place(25, -25, -15),
                anti_slop | place(-25, -25, -15),
                anti_slop | place(-25, 25, -15),
            ]
        )

        base = union([
            half_sphere,
            coupler_1,
            coupler_2,
            coupler_3,
            coupler_4
        ])
        
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
    create_tube_support_x(),
    create_tube_support_y(),
    build_cylinder_seal(),
    create_base_2()
    # create_rods()
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
