"""Trap light — PVC box camera with multiple parts."""

from tanuki.dsl import *

x_axis = (98 / 2) / 2
tolerance = 0.125
case_length = 90


def create_case():
    with model("case") as ctx:
        box = cube(81, 34, 62 - tolerance * 2, label="pvc_box")
        h_box = cube(75, 34, 56, label="hollow_pvc_box") | place(0, 3, 0)
        h_knockout_1 = cylinder(27 / 2, 68, label="knockout_hole_center", vertices=256)
        h_knockout_2 = cylinder(
            19 / 2, 68, label="knockout_hole_left", vertices=256
        ) | place(x_axis, 0, 0)
        h_knockout_3 = cylinder(
            7.5, 68, label="knockout_hole_right", vertices=256
        ) | place(-x_axis, 0, 0)

        case = difference(box, [h_box, h_knockout_1, h_knockout_2, h_knockout_3])

        support = cube(26, 17, 48, label="support") | place(x_axis + 1, -14 / 2 - 1, 0)

        main_cartridge = cylinder(
            13, 44, label="cartridge", vertices=256
        ) | place(x_axis, 0, 0)
        cartridge_cyl = cylinder(
            6, 5, label="cartridge_cyl", vertices=256
        ) | place(x_axis, 0, 43 / 2 + 2.5)
        cartridge_cyl_bottom = cylinder(
            5, 10, label="cartridge_cyl", vertices=256
        ) | place(x_axis, 0, -43 / 2)
        flat_film_output = cube(
            13, 3, 44, label="flat_film_output"
        ) | place(x_axis - 6, -26 / 2 + 1.5, 0)

        h_cartridge = union([main_cartridge, cartridge_cyl, cartridge_cyl_bottom, flat_film_output])
        support = difference(support, [h_cartridge])
        case = union([case, support])

        output(case)
    return ctx.graph


def create_cartridge_film_35mm():
    with model("film_35mm") as ctx:
        main_cartridge = cylinder(
            25 / 2, 43, label="cartridge", vertices=256
        ) | place(x_axis, 0, 0)
        cartridge_cyl = cylinder(
            5.5, 5, label="cartridge_cyl", vertices=256
        ) | place(x_axis, 0, 43 / 2 + 2.5)
        flat_film_output = cube(
            25 / 2, 3, 43, label="flat_film_output"
        ) | place(x_axis - 6, -25 / 2 + 1.5, 0)

        cartridge = union([main_cartridge, cartridge_cyl, flat_film_output])

        output(cartridge)
    return ctx.graph


def create_film_roll():
    with model("film_roll") as ctx:
        film_roll = cylinder(
            8, 48, label="film_roll", vertices=256
        ) | place(-x_axis, 0, 0)
        sprocket_1 = cube(
            1.5, 18, 1, label="sprocket_1"
        ) | rotate(0, 0, 22.5) | place(-x_axis, 0, 14)
        film_roll = union([film_roll, sprocket_1])

        h_film_roll = cylinder(
            4, 48, label="hollow_film_roll", vertices=256
        ) | place(-x_axis, 0, 0)
        h_tooth = cube(3, 20, 40, label="hollow_tooth") | place(-x_axis, 12, 0)
        h_cyl_bottom = cylinder(
            6, 15, label="hollow_cyl_bottom", vertices=8
        ) | place(-x_axis, 0, -25)

        roll = difference(film_roll, [h_tooth, h_cyl_bottom, h_film_roll])
        film_roll_top = cylinder(
            5.5, 7, label="film roll top", vertices=256
        ) | place(-x_axis, 0, 25)

        roll = union([roll, film_roll_top])

        film_roll_bottom = cylinder(
            8, 3.75, label="film roll bottom", vertices=256
        ) | place(-x_axis, 0, -25.5)
        h_film_roll_bottom = cylinder(
            7.5, 6, label="hollow_film_roll_bottom", vertices=256
        ) | place(-x_axis, 0, -25 - 1)
        film_roll_bottom = difference(film_roll_bottom, [h_film_roll_bottom])

        roll = union([roll, film_roll_bottom])

        output(roll)
    return ctx.graph


def create_knockout_covers_top():
    with model("knockout_covers_top") as ctx:
        knockout_1 = cylinder(
            27 / 2 - tolerance, 9, label="knockout_center", vertices=256
        ) | place(0, 0, -1)
        knockout_2 = cylinder(
            19 / 2 - tolerance, 9.75, label="knockout_left", vertices=256
        ) | place(x_axis, 0, -1.5)
        knockout_3 = cylinder(
            7 - tolerance, 9, label="knockout_right", vertices=256
        ) | place(-x_axis, 0, -1)
        top_cover = cube(81, 37, 3, label="top cover") | place(0, 0, 2)

        knockouts = union([knockout_1, knockout_2, knockout_3, top_cover])
        h_knockout_2_1 = cylinder(
            3.5, 12, label="hole knockout_left", vertices=256
        ) | place(x_axis, 0, 0)
        h_knockout_2_2 = cylinder(
            8, 8, label="hole knockout_left", vertices=256
        ) | place(x_axis, 0, -3)
        h_knockout_3 = cylinder(
            6, 4.5, label="hole knockout_right", vertices=256
        ) | place(-x_axis, 0, -3.5)

        h_lens_box_1 = cube(
            10 + tolerance, 20 + tolerance, 3.5 + tolerance, label="film_box"
        ) | place(0, 0, -3.75)
        h_lens_box_2 = cube(
            20 + tolerance, 10 + tolerance, 3.5 + tolerance, label="film_box"
        ) | place(0, 0, -3.75)
        knockouts = difference(
            knockouts,
            [h_knockout_2_1, h_knockout_2_2, h_lens_box_1, h_lens_box_2, h_knockout_3],
        )
        t_knockouts = knockouts | translate(0, 0, 66 / 2 - 2.5)

        output(t_knockouts)
    return ctx.graph


def create_knockout_covers_bottom():
    with model("knockout_covers_bottom") as ctx:
        knockout_1 = cylinder(
            27 / 2 - tolerance, 9, label="knockout_center", vertices=256
        ) | place(0, 0, 1.5)
        knockout_2 = cylinder(
            19 / 2 - tolerance, 8, label="knockout_left", vertices=256
        ) | place(x_axis, 0, 1)
        knockout_3 = cylinder(
            7.5 - tolerance, 8, label="knockout_right", vertices=256
        ) | place(-x_axis, 0, 1)
        bottom_cover = cube(81, 37, 3, label="bottom cover") | place(0, 0, -2)
        film_base = cylinder(
            4.5, 9.5, label="film_base", vertices=256
        ) | place(x_axis, 0, 8.5)

        h_lens_box_1 = cube(
            10 + tolerance, 20 + tolerance, 5 + tolerance, label="film_box"
        ) | place(0, 0, 4)
        h_lens_box_2 = cube(
            20 + tolerance, 10 + tolerance, 5 + tolerance, label="film_box"
        ) | place(0, 0, 4)
        h_knockout_3 = cylinder(
            6.5, 10, label="knockout_right", vertices=256
        ) | place(-x_axis, 0, 0)
        h_knockout_4 = cylinder(
            4, 5, label="knockout_right", vertices=8
        ) | place(x_axis, 0, -1)

        h_bottom_bear = cylinder(
            8 + tolerance, 5 + tolerance * 2, label="hollow_bottom_gear", vertices=256
        ) | place(0, 0, -1)

        knockouts = union([knockout_1, knockout_2, knockout_3, bottom_cover, film_base])
        knockouts = difference(
            knockouts,
            [h_lens_box_1, h_lens_box_2, h_knockout_3, h_knockout_4, h_bottom_bear],
        )

        t_knockouts = knockouts | translate(0, 0, -66 / 2 + 2.5)

        output(t_knockouts)
    return ctx.graph


def create_film_lever():
    with model("film_lever") as ctx:
        knockout_2_1 = cylinder(
            3 - tolerance, 20, label="lever_axis", vertices=8
        ) | place(x_axis, 0, 8)
        knockout_2_2 = cylinder(
            8 - tolerance, 2, label="lever_cover", vertices=256
        ) | place(x_axis, 0, -2)
        knockout_2_3 = cylinder(
            4.5, 7, label="lever_axis_2", vertices=256
        ) | place(x_axis, 0, -5)

        lever = union([knockout_2_1, knockout_2_2, knockout_2_3])

        h_wall = cube(10, 1.5, 5, label="hollow_wall") | place(x_axis, 0, -7)
        lever = difference(lever, [h_wall])

        t_lever = lever | translate(0, 0, 66 / 2 - 3)

        output(t_lever)
    return ctx.graph


def create_film_box():
    with model("film_box") as ctx:
        box = cube(
            20 - tolerance * 2, 10 - tolerance * 2, 57.5, label="film_box"
        )
        h_lens_mount = cylinder(15 / 2 + tolerance, 50, label="lens_mount") | rotate(90, 0, 0)

        box = difference(box, [h_lens_mount])

        t_film_box = box | translate(0, 0, -0.25)

        output(t_film_box)
    return ctx.graph


def cog_roll():
    with model("cog_roll") as ctx:
        cyl_bottom = cylinder(
            6 - tolerance, 21, label="hollow_cyl_bottom", vertices=8
        ) | place(-x_axis, 0, -28)

        output(cyl_bottom)
    return ctx.graph


def cog_axis():
    with model("cog_axis") as ctx:
        axis = cylinder(
            4 - tolerance,
            9.5 - tolerance * 2,
            label="cog_axis",
            vertices=256,
        ) | place(0, 0, -34 + tolerance * 2)

        output(axis)
    return ctx.graph


def cog_film_axis():
    with model("cog_film_axis") as ctx:
        axis = cylinder(
            4 - tolerance,
            9.5 - tolerance * 2,
            label="cog_film_axis",
            vertices=8,
        ) | place(x_axis, 0, -34 + tolerance * 2)

        output(axis)
    return ctx.graph


def lens_mount():
    with model("lens_mount") as ctx:
        mount = cylinder(15 / 2, 28, label="lens_mount") | rotate(90, 0, 0)
        mount_2 = cylinder(
            15, 6, label="hollow_lens_mount 2", vertices=256
        ) | rotate(90, 0, 0) | place(0, 12.5, 0)

        mount = union([mount, mount_2])

        h_mount_1 = cylinder(
            5.75, 40, label="hollow_lens_mount 1", vertices=256
        ) | rotate(90, 0, 0)
        h_mount_2 = cylinder(
            25 / 2, 6, label="hollow_lens_mount 2", vertices=256
        ) | rotate(90, 0, 0) | place(0, 13, 0)

        mount = difference(mount, [h_mount_1, h_mount_2])
        t_mount = mount | translate(0, 11, 0)

        output(t_mount)
    return ctx.graph


def h_motor():
    with model("h_motor") as ctx:
        motor = cube(5, 5, 12, label="motor") | place(0, 0, -34)

        output(motor)
    return ctx.graph


ALL_PARTS = [
    create_case,
    create_cartridge_film_35mm,
    create_film_roll,
    create_knockout_covers_top,
    create_knockout_covers_bottom,
    create_film_lever,
    create_film_box,
    cog_roll,
    cog_axis,
    cog_film_axis,
    lens_mount,
    h_motor,
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile trap light parts")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "trap_light_combined.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "trap_light_individual"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")
