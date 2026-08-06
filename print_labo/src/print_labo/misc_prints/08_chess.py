from tanuki.dsl import *

CLR = 0.125  # mm


def new_motor(clr=0):
    motor = cylinder(28/2 + clr, 19 + clr, "motor") | place(0, 0, 0)
    axis_1 = cylinder(9/2, 1.5, "axis_1") | place(0, 8, 19/2 + 1.5/2)
    axis_2 = cylinder(5/2, 10, "axis_2") | place(0, 8, 19/2 + 10/2)
    axis_3 = cube(10, 3, 10, "axis_3") | place(0, 8, 19/2 + 10/2)

    axis_3 = intersect([axis_3, axis_2])
    axis_2 = difference(axis_2, [axis_3])
    axis_2_5 = cylinder(5/2, 4, "axis_2_5") | place(0, 8, 19/2 + 2)
    wire_box = cube(14.6, 5, 19 + clr, "wire_box") | place(0, -17 + 5/2, 0)

    bolt_support_1 = cube(
        35, 7, 2 + clr, "bolt_support") | place(0, 0, 19/2 - 2/2)
    bolt_support_2 = cylinder(
        7/2, 2 + clr, "bolt_support") | place(35/2, 0, 19/2 - 2/2)
    bolt_support_3 = cylinder(
        7/2, 2 + clr, "bolt_support") | place(-35/2, 0, 19/2 - 2/2)
    h_bolt_support_1 = cylinder(
        4/2, 2 + clr, "bolt_support") | place(35/2, 0, 19/2 - 2/2)
    h_bolt_support_2 = cylinder(
        4/2, 2 + clr, "bolt_support") | place(-35/2, 0, 19/2 - 2/2)
    bolt_support = union([bolt_support_1, bolt_support_2, bolt_support_3])
    bolt_support = difference(
        bolt_support, [h_bolt_support_1, h_bolt_support_2])

    motor = union([motor, axis_1, axis_2_5,  axis_3, wire_box, bolt_support])

    return motor, bolt_support


def create_motor():
    with model("motor") as ctx:
        motor, _ = new_motor()
        output(motor)

    return ctx.graph


def create_motor_base_1():
    with model("motor_base_1") as ctx:
        motor, bolt_support = new_motor(CLR)
        base_1 = cylinder(31/2, 19, "base")
        base_2 = cube(17, 10, 19, "base_2") | place(0, -17 + 7/2, 0)

        base = union([
            base_1,
            base_2,
            bolt_support | place(0, 0, - 2.125),
            bolt_support | place(0, 0, - 19 + 2.0625)
        ])

        h_wires = cube(12, 10, 5, "h_wires") | place(0, -20, 7)

        base = difference(base, [motor, h_wires])
        output(base)

    return ctx.graph


def create_motor_base_2():
    with model("motor_base_2") as ctx:
        motor, bolt_support = new_motor(CLR)
        base_1 = cylinder(31/2, 19, "base")
        base_2 = cube(17, 10, 19, "base_2") | place(0, -17 + 7/2, 0)

        base = union([
            base_1,
            base_2,
            bolt_support | place(0, 0, - 2.125),
        ])

        h_wires = cube(12, 10, 3, "h_wires") | place(0, -20, 8)
    
        arm_support = cube(17, 10, 16, "arm_support")
        h_arm_support = cylinder(9/2, 11, "h_arm_support") | rotate(90, 0, 0) | place(0, -2.5, -1)
        arm_support = difference(arm_support, [h_arm_support]) | place(0, -23.5, -1.5)

        base = difference(base, [motor, h_wires])
        base = union([base, arm_support]) | rotate(0, 180, 0) | place(0, 88, 15)

        output(base)

    return ctx.graph


def create_motor_2():
    with model("motor_2") as ctx:
        motor, _ = new_motor()
        motor = motor | rotate(0, 180, 0) | place(0, 88, 15)
        output(motor)

    return ctx.graph

def create_motor_tap():
    with model("motor_tap") as ctx:
        axis_2 = cylinder(5/2 + CLR, 6 + CLR, "axis_2")
        axis_3 = cube(10 + CLR, 3, 6 + CLR, "axis_3")
        h_axis = intersect([axis_3, axis_2]) | place(0, 0, -2.5)
        axis = cylinder(6/2, 11, "axis") | place(0, 0, 0)
        axis = difference(axis, [h_axis])

        tap_3 = cylinder(7, 10, "tap") | rotate(90, 0, 0) | place(0, 8, -1.5)
        h_leg = cylinder(9/2 + CLR, 55 + CLR, "leg") | rotate(90, 0, 0) | place(0, 32, -1.5)        
        tap_3 = difference(tap_3, [h_leg])
        
        tap = union([axis, tap_3])
        h_base_m = cylinder(11/2, 2, "base") | place(0, 0, -8)
        tap = difference(tap, [h_base_m]) 
        
        base = cube(10, 16, 2.5, "base") | place(0, 5, 4.5)
        tap = union( [tap, base]) | place(0, 8, 19)
        output(tap)

    return ctx.graph

def create_leg():
    with model("leg") as ctx:
        leg = cylinder(9/2, 55, "leg") | rotate(90, 0, 0) | place(0, 40, 17.5)
        output(leg)
        
    return ctx.graph

def create_motor_tap_2():
    with model("motor_tap_2") as ctx:
        axis_2 = cylinder(5/2 + CLR, 6 + CLR, "axis_2")
        axis_3 = cube(10 + CLR, 3, 6 + CLR, "axis_3")
        h_axis = intersect([axis_3, axis_2]) | place(0, 0, -2.5)
        axis = cylinder(6/2, 11, "axis") | place(0, 0, 0)
        axis = difference(axis, [h_axis])

        tap_3 = cylinder(7, 10, "tap") | rotate(90, 0, 0) | place(0, 8, -1.5)
        h_leg = cylinder(9/2 + CLR, 55 + CLR, "leg") | rotate(90, 0, 0) | place(0, 32, -1.5)        
        tap_3 = difference(tap_3, [h_leg])
        
        tap = union([axis, tap_3])
        h_base_m = cylinder(11/2, 2, "base") | place(0, 0, -8)
        tap = difference(tap, [h_base_m]) 
        
        base = cube(10, 16, 2.5, "base") | place(0, 5, 4.5)

        crystall_ball = sphere(5 + CLR*2, "crystall_ball") | place(0, -10, 1)
        h_ring = cylinder(8, 3, "ring") | place(0, -10, 1)
        ball_input = cube(6, 6, 10, "ball_input") | place(0, -15, 1)
        ball_support = difference(h_ring, [ball_input ,crystall_ball])
        base_ball_support = cube(10, 2, 6.25, "base") | place(0, -3, 2.625)
        support = union([ball_support, base_ball_support])

        crystall_ball = sphere(5, "crystall_ball") | place(0, -10, 1)

        tap = union( [tap, base, ball_support, support]) | rotate(0, 180, 0) | place(0, 96, -4)

        output(tap)

    return ctx.graph

def create_leg_2():
    with model("leg_2") as ctx:
        leg = cylinder(9/2, 55, "leg") | rotate(90, 0, 0) | place(0, 128, -2.5)
        output(leg)
        
    return ctx.graph

ALL_PARTS = [
    create_motor, 
    create_motor_base_1(),
    create_motor_2,
    create_motor_base_2(),
    create_motor_tap(),
    create_leg(),
    create_motor_tap(),
    create_motor_tap_2(),
    create_leg_2(),
]


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
