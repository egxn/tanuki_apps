from tanuki.dsl import *

tolerance = 0.125

def create_lamp_joint_1():
    with model("lamp_joint_1") as ctx:
        join_1 = union([
            cylinder(28/2, 28, "join_1_wood"),
            cube(28, 28, 28, label="join_1_cube") | place(-14, 0, 0)
        ])

        join_1 = difference(join_1, [
            cube(28 + tolerance, 14  + tolerance, 14, label="l_1") | place(14, -10.5, 0) | rotate(270, 0, 0) | place(-45.5, 0, 0),
            cube(7 + tolerance, 28 + tolerance, 14, label="l_2") | place(28 - 3.5, 0, 0) | rotate(270, 0, 0) | place(-45.5, 0, 0)
        ])

        h_join_1 = cylinder(25/2 + tolerance, 28, "h_join_1") | place(0, 0, -2)
        join_1 = difference(join_1, [h_join_1])
     
        output(join_1)

    return ctx.graph

def create_lamp_joint_2():
    with model("lamp_joint_2") as ctx:
        curve_thread = curve_circle(radius=2, label="curve_thread")
        h_curve_spiral_1 = curve_spiral(
            resolution=100,
            rotations=5,
            start_radius=20/2,
            end_radius=20/2,
            height=28,
            label="h_thread",
        ) | curve_to_mesh(curve_thread, fill_caps=True) | translate(0, 0, -14)

        join_2 = union([
            cylinder(32/2, 14, "join_1_wood"),
            cube(28 - tolerance, 7 - tolerance, 14, label="l_1") | place(14, -10.5, 0),
            cube(7 - tolerance, 28 - tolerance, 14, label="l_2") | place(28 - 3.5, 0, 0)
        ])

        join_2 = difference(
            join_2,
            [cylinder(20/2 + tolerance, 28, "h_join_1"), h_curve_spiral_1])

        join_2 = join_2 | rotate(270, 0, 0) | place(-45.5, 0, 0)

        output(join_2)

    return ctx.graph

def create_lamp_joint_3():
    with model("lamp_joint_3") as ctx:
        join_3 = union([
            cylinder(45/2, 18, "join_3"),
        ])

        join_3 = difference(join_3, [
            cylinder(38/2 + tolerance, 20, "h_join_1")
        ]) | translate(0, 32, 0)

        curve_thread = curve_circle(radius=1.5, label="curve_thread")
        curve_spiral_1 = curve_spiral(
            resolution=100,
            rotations=5,
            start_radius=18/2,
            end_radius=18/2,
            height=28,
            label="h_thread",
        ) | curve_to_mesh(curve_thread, fill_caps=True) | translate(0, 0, -14)

        curve_spiral_1 = union([
            curve_spiral_1,
            cylinder(20/2 + tolerance, 28, "h_join_1")
        ])

        curve_spiral_plane = intersect([
            cube(100, 18, 25, label="curve_spiral_plane"),
            curve_spiral_1,
        ]) | rotate(270, 0, 0)

        join_3 = union([
            join_3,
            curve_spiral_plane,
        ]) | translate(-45, 0, 0)

        output(join_3)

    return ctx.graph

def create_lamp_joint_4():
    with model("lamp_joint_4") as ctx:
        join_4 = union([
            cylinder(40/2, 50, "join_4", vertices=128),
            cube(30, 40, 50, label="join_4_cube") | place(-15, 0, 0)
        ])

        h_join_4 = cylinder(25/2 + tolerance * 2, 60, "h_join_4")
        join_4 = difference(join_4, [
            h_join_4,
            cube(10 + tolerance, 30 + tolerance, 48 + tolerance, label="h_join_4_cube") | place(-20, 0, 2),
            cube(10 + tolerance, 30 + tolerance, 50 + tolerance, label="h_join_4_cube") | place(-30, 0, 25),
            cylinder(2 + tolerance, 50, "h_join_4_cylinder") | rotate(90, 0, 0),
            cylinder(4 + tolerance, 6, "h_join_4_cylinder") | rotate(90, 0, 0) | place(0, 20, 0),
            cylinder(4 + tolerance, 6, "h_join_4_cylinder") | rotate(90, 0, 0) | place(0, -20, 0)
        ])
     
        output(join_4)

    return ctx.graph

def create_lamp_joint_5():
    with model("lamp_joint_5") as ctx:
        curve_thread = curve_circle(radius=2, label="curve_thread")
        h_curve_spiral_1 = curve_spiral(
            resolution=100,
            rotations=5,
            start_radius=20/2,
            end_radius=20/2,
            height=35,
            label="h_thread",
        ) | curve_to_mesh(curve_thread, fill_caps=True) | rotate(90, 0, 0) | place(-44, 18, 9)

        join_5 = union([
            cylinder(32/2, 30 - tolerance, "join_1_wood") | rotate(90, 0, 0) | place(-44, 0, 9),
            cube(10 - tolerance*2, 30 - tolerance*2, 47 - tolerance*2, label="l_2") | place(-20, 0, 1.5),
            cube(24, 30 - tolerance*2, 25, label="l_1") | place(-32, 0, 12.5),
        ])

        join_5 = difference(
            join_5,
            [cylinder(20/2 + tolerance*2, 32, "h_join_1") | rotate(90, 0, 0) | place(-44, 0, 9), h_curve_spiral_1])


        output(join_5)

    return ctx.graph

def create_lamp_joint_6():
    with model("lamp_joint_6") as ctx:
        join_6 = cylinder(40/2, 30, "join_6", vertices=128)
        join_6 = difference(join_6,
                            [cylinder(25/2 + tolerance*3, 35, "h_join_1", vertices=128),
                             cylinder(2, 50, "h_join_1", vertices=128)  | rotate(90, 0, 90),
                             cylinder(3, 4, "h_join_1", vertices=128)  | rotate(90, 0, 90) | translate(20, 0, 0),
                             cylinder(3, 4, "h_join_1", vertices=128)  | rotate(90, 0, 90) | translate(-20, 0, 0),
                             ],
                            ) | translate(-44, 40, 15)

        curve_thread = curve_circle(radius=1.5, label="curve_thread")
        curve_spiral_1 = curve_spiral(
            resolution=100,
            rotations=5,
            start_radius=18/2,
            end_radius=18/2,
            height=35,
            label="h_thread",
        ) | curve_to_mesh(curve_thread, fill_caps=True) | rotate(90, 0, 0) | place(-44, 18, 9)

        curve_spiral_1 = union([
            curve_spiral_1,
            cylinder(20/2 + tolerance, 44, "thread_cylinder", vertices=128) | rotate(90, 0, 0) | place(-44, 5, 9)
        ])

        curve_spiral_plane = intersect([
            cube(100, 50, 18, label="curve_spiral_plane") | place(-44, 0, 9),
            curve_spiral_1,
        ])

        join_6 = union([
            join_6,
            curve_spiral_plane,
        ])

        output(join_6)

    return ctx.graph

def create_lamp_joint_7():
    with model("lamp_joint_7") as ctx:
        base_y_1 = cube(40, 160, 40, label="base")
        base_cyl_1 = cylinder(40, 40, "h_wood", vertices=128)
        base_cyl_2 = cylinder(30, 60, "h_wood", vertices=128) | place(0, 0, 20)

        base = union([
            base_y_1,
            base_cyl_1,
            base_cyl_2
        ])

        join_7 = difference(base, [h_wood])

        output(join_7)
    return ctx.graph

ALL_PARTS = [
    # create_lamp_joint_4(),
    # create_lamp_joint_5(),
    # create_lamp_joint_6()
    create_lamp_joint_7()
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="lamp_joins")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "lamp_joins.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "lamp_joins_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")
