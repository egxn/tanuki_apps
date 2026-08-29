"""Mechanical parts for the chess-board mechanism.

Dimensions are in millimetres.  The vocabulary intentionally follows common
mechanical-design terms: housing, shaft, keyway, mounting flange, bore and
clearance.
"""

from tanuki.dsl import *


CLEARANCE = 0.125
ROD_R = 9.5


def build_motor_assembly(clearance: float = 0.0):
    """Build only the motor body and drive components.

    The mounting flange belongs to the chess-board base, not to the motor
    assembly itself.
    """
    housing_diameter = 28 + 2 * clearance
    housing_height = 19 + clearance
    housing = cylinder(housing_diameter / 2, housing_height, "motor_housing")

    output_shaft = cylinder(
        ROD_R / 2, 1.5, "output_shaft") | place(0, 8, 19 / 2 + 1.5 / 2)
    drive_shaft = cylinder(
        5 / 2, 10, "drive_shaft") | place(0, 8, 19 / 2 + 10 / 2)
    keyway_tool = cube(10, 3, 10, "shaft_keyway_tool") | place(
        0, 8, 19 / 2 + 10 / 2)
    keyway_tool = intersect([keyway_tool, drive_shaft])
    drive_shaft = difference(drive_shaft, [keyway_tool])
    shaft_collar = cylinder(5 / 2, 4, "shaft_collar") | place(0, 8, 19 / 2 + 2)

    cable_pocket = cube(14.6, 5, housing_height,
                        "cable_pocket") | place(0, -14.5, 0)
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
    flange = cube(35, 7, flange_thickness, "flange") | place(0, 0, z + 1)
    left_boss = cylinder(7 / 2, flange_thickness,
                         "left_mounting_boss") | place(-17.5, 0, z + 1)
    right_boss = cylinder(7 / 2, flange_thickness,
                          "right_mounting_boss") | place(17.5, 0, z + 1)
    left_bore = cylinder(4 / 2, flange_thickness,
                         "left_mounting_bore") | place(-17.5, 0, z + 1)
    right_bore = cylinder(4 / 2, flange_thickness,
                          "right_mounting_bore") | place(17.5, 0, z + 1)

    flange = union([flange, left_boss, right_boss])
    return difference(flange, [left_bore, right_bore])


def build_motor_mount(clearance: float = CLEARANCE):
    """Build the cylindrical motor seat with its rear cable relief."""
    motor = build_motor_assembly(clearance)
    mounting_flange = build_mounting_flange(clearance, 19 / 2)
    flange = cube(35, 7, 2, "flange") | place(0, 0, 19 / 2)
    motor_flange = build_mounting_flange(clearance, 19 / 2 + 1)
    seat = cylinder(31 / 2, 19, "motor_seat")
    rear_bracket = cube(17, 10, 19, "rear_bracket") | place(0, -13.5, 0)
    cable_relief = cube(12, 10, 6, "cable_relief") | place(0, -20, 7)
    cable_relief_wide = cube(20, 6, 19, "cable_relief") | place(0, -13, 0)
    h_cable_relief_wide = cube(17.5, 4, 39, "cable_relief") | place(0, -12, 0)
    mount = union([seat, rear_bracket, mounting_flange |
                  place(0, 0, -2.125), cable_relief_wide])
    return difference(mount, [motor, cable_relief, flange, motor_flange | place(0, 0, -2), h_cable_relief_wide])


def build_drive_coupler(clearance: float = CLEARANCE, ball_joint: bool = False):
    """Build the shaft coupler, optionally with its ball-joint support."""
    shaft = cylinder(10 / 2, 11.25, "coupler_shaft") | place(0, 0, 0.125)
    keyway = cylinder(5 / 2 + clearance, 6 + clearance, "coupler_keyway")
    keyway_tool = cube(10 + clearance, 3, 6 + clearance, "coupler_keyway_tool")
    keyway = intersect([keyway, keyway_tool]) | place(0, 0, -2.5)
    shaft = difference(shaft, [keyway])

    cross_boss = cylinder(7, 10, "cross_boss") | rotate(
        90, 0, 0) | place(0, 8, -1.5)
    cross_bore = cylinder(ROD_R / 2 + clearance, 55 + clearance,
                          "cross_bore") | rotate(90, 0, 0) | place(0, 32, -1.5)
    coupler = difference(union([shaft, cross_boss]), [cross_bore])
    retaining_groove = cylinder(
        11 / 2, 2, "retaining_groove") | place(0, 0, -8)
    coupler = difference(coupler, [retaining_groove])
    mounting_tab = cube(10, 16, 2.5, "mounting_tab") | place(0, 5, 4.5)
    coupler = union([coupler, mounting_tab])

    if ball_joint:
        ball = sphere(2.75 + 2 * clearance, "ball") | place(0, 0, 4)
        h_wall_cuts = union([
            cube(2, 10, 5.5, "h wall") | place(0, 0, 3.5),
            cube(12, 2, 5.5, "h wall") | place(0, 0, 3.5),
        ])

        coupler = difference(coupler, [ball, h_wall_cuts])
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
    plate_mount_flange = build_mounting_flange(z=7.5)
    mount = union([mount, plate_mount_flange | place(0, 0, -17)])
    housing = cylinder(28 / 2, 20, "motor_seat")

    return make_graph("motor_mount_plate", difference(mount, [housing]))


def create_motor_mount_with_arm_graph():
    mount = build_motor_mount()
    cable_relief = cube(12, 10, 3, "cable_relief") | place(0, -20, 8)
    arm = cube(17, 10, 16, "arm_support")
    arm_bore = cylinder(ROD_R/2, 11, "arm_bore") | rotate(90,
                                                          0, 0) | place(0, -2.5, -1)
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
    leg = cylinder(9 / 2, 55, "linkage_rod") | rotate(90,
                                                      0, 0) | place(0, y, z)
    return make_graph(name, leg)


def create_surfaces(CLR_Z=0, CLR_X=0, CLR_Y=0):
    board_margin = 20
    l_1 = 300 + board_margin - 3
    l_2 = 300 + board_margin - 3

    board_z = 0.5 + CLR_Z
    motor_z = 3 + CLR_Z

    board = cube(l_1, l_2, board_z, "board") | place(0, 0, 30)
    motor_base = cube(l_1, l_2, motor_z, "motor_base")

    motor_base = union([
        motor_base,
        cube(l_1 + 6, 30 + CLR_Y, motor_z, "rib_1") | place(0,  100, 0),
        cube(l_1 + 6, 30 + CLR_Y, motor_z, "rib_1") | place(0, -100, 0),
        cube(l_1 + 6, 30 + CLR_Y, motor_z, "rib_1") | place(0,  33.3, 0),
        cube(l_1 + 6, 30 + CLR_Y, motor_z, "rib_1") | place(0, -33.3, 0),

        cube(30 + CLR_Y, l_1 + 6, motor_z, "rib_1") | place(100,  0, 0),
        cube(30 + CLR_Y, l_1 + 6, motor_z, "rib_1") | place(-100,  0, 0),
        cube(30 + CLR_Y, l_1 + 6, motor_z, "rib_1") | place(33.3,  0, 0),
        cube(30 + CLR_Y, l_1 + 6, motor_z, "rib_1") | place(-33.3,  0, 0)
    ])

    surfaces = union([
        board,
        motor_base | place(0, 0, -11),
        motor_base | place(0, 0, -20)
    ])

    return surfaces


def create_chess_squares():
    chess_squares = []

    area = 300
    rows = 9
    distance = area / rows

    for row in range(rows):
        for column in range(rows):
            x = distance / 2 + column * distance
            y = distance / 2 + row * distance
            sqr = cylinder(2, 60, f"cylinder_{row}_{column}") | place(x, y, 4)
            chess_squares.append(sqr)

    return chess_squares


def create_board():
    with model("board") as context:
        surfaces = create_surfaces()
        chess_squares = create_chess_squares()

        chess_squares = union(chess_squares) | place(-150, -150, 0)
        surfaces = difference(surfaces, [chess_squares])

        output(surfaces)

    return context.graph


def generate_walls(CLR=0):
    surfaces = create_surfaces(CLEARANCE, CLEARANCE, CLEARANCE)
    wall_y = cube(3 + CLR, 300 + CLR, 52 + CLR, "wall_y")
    wall_x = cube(300 + CLR, 3 + CLR, 52 + CLR, "wall_x")

    wall_y_1 = wall_y | place(160, 0,  4)
    wall_y_2 = wall_y | place(-160, 0, 4)
    wall_y_3 = cube(3 + CLR, 310 + CLR, 20 + CLR, "wall_y") | place(160, 0, 4)
    wall_y_4 = cube(3 + CLR, 310 + CLR, 20 + CLR, "wall_y") | place(-160, 0, 4)

    wall_x_1 = wall_x | place(0, 160,  4)
    wall_x_2 = wall_x | place(0, -160, 4)
    wall_x_3 = cube(310 + CLR, 3 + CLR, 20 + CLR, "wall_y") | place(0, 160,  4)
    wall_x_4 = cube(310 + CLR, 3 + CLR, 20 + CLR, "wall_y") | place(0, -160, 4)

    return union([
        difference(wall_x_1, [surfaces]),
        difference(wall_x_2, [surfaces]),
        difference(wall_y_1, [surfaces]),
        difference(wall_y_2, [surfaces]),
        wall_y_3,
        wall_y_4,
        wall_x_3,
        wall_x_4
    ])


def create_walls():
    with model("walls") as context:
        walls = generate_walls()
        output(walls)
    return context.graph


def create_corners():
    with model("corners") as context:
        board_margin = 20
        surfaces = create_surfaces(CLEARANCE)
        l_1 = 300 + board_margin
        l_2 = 300 + board_margin

        corner_position_x = l_1 / 2 - 5
        corner_position_y = l_2 / 2 - 5
        corner = cube(30, 30, 54, "corner")
        corners = union([
            corner | place(corner_position_x, corner_position_y,  4),
            corner | place(corner_position_x, -corner_position_y, 4),
            corner | place(-corner_position_x, -corner_position_y, 4),
            corner | place(-corner_position_x, corner_position_y,  4),
        ])

        walls = generate_walls(CLEARANCE)
        corners = difference(corners, [surfaces, walls])

        output(corners)
    return context.graph


ALL_PARTS = [
    # create_motor_assembly_graph(),
    # create_motor_mount_plate_graph(),
    # create_reversed_motor_assembly_graph(),
    # create_motor_mount_with_arm_graph(),
    # create_shaft_coupler_graph(),
    # create_linkage_rod_graph(),
    # create_shaft_coupler_graph(with_ball_joint=True, name="ball_joint_coupler"),
    # create_linkage_rod_graph(name="rear_linkage_rod", y=128, z=-2.5),
    create_corners(),
    create_board(),
    create_walls(),
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
