"""Mechanical parts for the chess-board mechanism.

Dimensions are in millimetres.  The vocabulary intentionally follows common
mechanical-design terms: housing, shaft, keyway, mounting flange, bore and
clearance.
"""

from tanuki.dsl import *


CLEARANCE = 0.125


def build_motor_assembly(clearance: float = 0.0):
    """Build only the motor body and drive components.

    The mounting flange belongs to the chess-board base, not to the motor
    assembly itself.
    """
    housing_diameter = 28 + 2 * clearance
    housing_height = 19 + clearance
    housing = cylinder(housing_diameter / 2, housing_height, "motor_housing")

    output_shaft = cylinder(9 / 2, 1.5, "output_shaft") | place(0, 8, 19 / 2 + 1.5 / 2)
    drive_shaft = cylinder(5 / 2, 10, "drive_shaft") | place(0, 8, 19 / 2 + 10 / 2)
    keyway_tool = cube(10, 3, 10, "shaft_keyway_tool") | place(0, 8, 19 / 2 + 10 / 2)
    keyway_tool = intersect([keyway_tool, drive_shaft])
    drive_shaft = difference(drive_shaft, [keyway_tool])
    shaft_collar = cylinder(5 / 2, 4, "shaft_collar") | place(0, 8, 19 / 2 + 2)

    cable_pocket = cube(14.6, 5, housing_height, "cable_pocket") | place(0, -14.5, 0)
    motor = union([
        housing,
        output_shaft,
        shaft_collar,
        keyway_tool,
        cable_pocket,
    ])
    return motor


def build_mounting_flange(clearance: float = 0.0, z: float = 8.5):
    """Build the transverse flange used to retain the motor."""
    flange_thickness = 2 + clearance
    flange = cube(35, 7, flange_thickness, "mounting_flange") | place(0, 0, z)
    left_boss = cylinder(7 / 2, flange_thickness, "left_mounting_boss") | place(-17.5, 0, z)
    right_boss = cylinder(7 / 2, flange_thickness, "right_mounting_boss") | place(17.5, 0, z)
    left_bore = cylinder(4 / 2, flange_thickness, "left_mounting_bore") | place(-17.5, 0, z)
    right_bore = cylinder(4 / 2, flange_thickness, "right_mounting_bore") | place(17.5, 0, z)
    flange = union([flange, left_boss, right_boss])
    return difference(flange, [left_bore, right_bore])


def build_motor_mount(clearance: float = CLEARANCE):
    """Build the cylindrical motor seat with its rear cable relief."""
    motor = build_motor_assembly(clearance)
    mounting_flange = build_mounting_flange(clearance, 19 / 2 - 1)
    motor_flange = build_mounting_flange(clearance, 19 / 2 + 1)
    seat = cylinder(31 / 2, 19, "motor_seat")
    rear_bracket = cube(17, 10, 19, "rear_bracket") | place(0, -13.5, 0)
    cable_relief = cube(12, 10, 5, "cable_relief") | place(0, -20, 7)
    mount = union([seat, rear_bracket, mounting_flange | place(0, 0, -2.125)])
    return difference(mount, [motor, cable_relief, motor_flange | place(0, 0, -2)])


def build_drive_coupler(clearance: float = CLEARANCE, ball_joint: bool = False):
    """Build the shaft coupler, optionally with its ball-joint support."""
    shaft = cylinder(6 / 2, 11, "coupler_shaft")
    keyway = cylinder(5 / 2 + clearance, 6 + clearance, "coupler_keyway")
    keyway_tool = cube(10 + clearance, 3, 6 + clearance, "coupler_keyway_tool")
    keyway = intersect([keyway, keyway_tool]) | place(0, 0, -2.5)
    shaft = difference(shaft, [keyway])

    cross_boss = cylinder(7, 10, "cross_boss") | rotate(90, 0, 0) | place(0, 8, -1.5)
    cross_bore = cylinder(9 / 2 + clearance, 55 + clearance, "cross_bore") | rotate(90, 0, 0) | place(0, 32, -1.5)
    coupler = difference(union([shaft, cross_boss]), [cross_bore])
    retaining_groove = cylinder(11 / 2, 2, "retaining_groove") | place(0, 0, -8)
    coupler = difference(coupler, [retaining_groove])
    mounting_tab = cube(10, 16, 2.5, "mounting_tab") | place(0, 5, 4.5)
    coupler = union([coupler, mounting_tab])

    if ball_joint:
        ball = sphere(2.5 + 2 * clearance, "ball") | place(0, 0, 3.5)
        coupler = difference(coupler, [ball])
    return coupler


def make_graph(name, geometry):
    with model(name) as context:
        output(geometry)
    return context.graph


def create_motor_assembly_graph():
    motor = build_motor_assembly()
    return make_graph("motor_assembly", motor)


def create_motor_mount_plate_graph():
    mount = build_motor_mount()
    plate_mount_flange = build_mounting_flange(z=8.5)
    mount = union([mount, plate_mount_flange | place(0, 0, -17)])
    housing = cylinder(28 / 2, 20, "motor_seat")

    return make_graph("motor_mount_plate", difference(mount, [housing]))


def create_motor_mount_with_arm_graph():
    mount = build_motor_mount()
    cable_relief = cube(12, 10, 3, "cable_relief") | place(0, -20, 8)
    arm = cube(17, 10, 16, "arm_support")
    arm_bore = cylinder(9 / 2, 11, "arm_bore") | rotate(90, 0, 0) | place(0, -2.5, -1)
    arm = difference(arm, [arm_bore]) | place(0, -23.5, -1.5)
    return make_graph("motor_mount_with_arm", union([difference(mount, [cable_relief]), arm]) | rotate(0, 180, 0) | place(0, 88, 15))


def create_reversed_motor_assembly_graph():
    motor = build_motor_assembly()
    return make_graph("reversed_motor_assembly", motor | rotate(0, 180, 0) | place(0, 88, 15))


def create_shaft_coupler_graph(with_ball_joint: bool = False, name: str = "shaft_coupler", y: float = 19):
    coupler = build_drive_coupler(ball_joint=with_ball_joint)
    rotate_y = 180 if with_ball_joint else 0
    place_y = 96 if with_ball_joint else y - 11
    place_z = -4 if with_ball_joint else y 
    
    return make_graph(name, coupler | rotate(0, rotate_y, 0) | place(0, place_y, place_z))


def create_linkage_rod_graph(name: str = "linkage_rod", y: float = 40, z: float = 17.5):
    leg = cylinder(9 / 2, 55, "linkage_rod") | rotate(90, 0, 0) | place(0, y, z)
    return make_graph(name, leg)


ALL_PARTS = [
    create_motor_assembly_graph(),
    create_motor_mount_plate_graph(),
    create_reversed_motor_assembly_graph(),
    create_motor_mount_with_arm_graph(),
    create_shaft_coupler_graph(),
    create_linkage_rod_graph(),
    create_shaft_coupler_graph(with_ball_joint=True, name="ball_joint_coupler"),
    create_linkage_rod_graph(name="rear_linkage_rod", y=128, z=-2.5),
]


if __name__ == "__main__":
    from pathlib import Path
    from print_labo.utils.compile_cli import run_compile_cli

    run_compile_cli(
        graphs=ALL_PARTS,
        description="Compile chess-board mechanical parts",
        source_script=Path(__file__).resolve(),
        default_output="chess.py",
        default_output_dir="chess_parts",
        watch_base_dir=Path(__file__).resolve().parent,
    )
