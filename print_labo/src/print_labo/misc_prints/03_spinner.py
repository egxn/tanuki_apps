from tanuki.dsl import *

clearance = 0.125

def create_rect_box():
    with model("rect_box") as ctx:
        rect = cube(105, 50, 67.5, "rect")
        h_rect = cube(100, 47.6, 60, "rect_box") | place(0, 2.4, 0)
        h_knockout_1 = cylinder(13, 70, "h_knockout")
        h_knockout_2 = cylinder(10.5, 120, "h_knockout")

        rect_box = difference(rect, [
            h_rect,
            h_knockout_1,
            h_knockout_2 | place(27.5 , 0 , 0),
            h_knockout_2 | place(-27.5 , 0 , 0),
            h_knockout_2 | rotate(0, 90, 0)
        ])

        output(rect_box)
    return ctx.graph


def create_knockout_34():
    with model("knockout_34") as ctx:
        knockout = cylinder(15.25, 32, "knockout_34")
        h_knockout_1 = cylinder(10, 70, "h_knockout_1")
        h_knockout_2 = cylinder(13.25, 40, "h_knockout_2") | place(0, 0, -16)
        h_knockout_3 = difference(cylinder(15.25, 22, "h_knockout_3"), [
            cylinder(25.5/2, 25, "h_knockout_3_cut")
        ])

        knockout = difference(knockout, [
            h_knockout_1,
            h_knockout_2,
            h_knockout_3 | place(0, 0, 16)
        ]) | place(0, 0, -78/2)

        output(knockout)
    return ctx.graph

def create_knockout_12():
    with model("knockout_12") as ctx:
        knockout = cylinder(13, 32, "knockout_12")
        h_knockout_1 = cylinder(8, 70, "h_knockout_1")
        h_knockout_2 = cylinder(10.5, 40, "h_knockout_2") | place(0, 0, -16)
        h_knockout_3 = difference(cylinder(13, 22, "h_knockout_3"), [
            cylinder(21/2, 25, "h_knockout_3_cut")
        ])

        knockout = difference(knockout, [
            h_knockout_1,
            h_knockout_2,
            h_knockout_3 | place(0, 0, 16)
        ]) | place(-27.5, 0, -78/2)

        output(knockout)
    return ctx.graph

def create_tube():
    with model("tube") as ctx:
        tube = cylinder(61.5/2, 80, "tube")
        h_tube_1 = cylinder(50.8/2, 85, "h_tube_1")

        tube = difference(tube, [
            h_tube_1,
        ]) | place(0, 0, -95)

        output(tube)
    return ctx.graph


def create_tube_base():
    with model("tube_base") as ctx:
        tube_base = cylinder(65/2, 15, "tube_base")
        h_tube_1 = cylinder(61/2, 10, "h_tube_1") | place(0, 0, 5)

        tube_base = difference(tube_base, [
            h_tube_1,
        ]) | place(0, 0, -135)

        output(tube_base)
    return ctx.graph

def create_knockout_base():
    with model("knockout_base") as ctx:
        knockout_base = cube(95, 36, 4, "rect")
        h_knockout_1 = cylinder(13, 70, "h_knockout")
        h_knockout_2 = cylinder(10.5, 120, "h_knockout")
        h_slit_1 = cube(10 + clearance, 3 + clearance, 7 + clearance, "slit_2")


        knockout_base = difference(knockout_base, [
            h_knockout_1,
            h_knockout_2 | place(27.5 , 0 , 0),
            h_knockout_2 | place(-27.5 , 0 , 0),
        ])

        knockout_base_1 = knockout_base
        knockout_base_1 = difference(
            knockout_base_1 | place(0, 0, 28),
            [cylinder(27/2 + clearance, 4, "base_cartridge") | place(27.5, 0, 24.5), h_slit_1 | place(0, -15.5, 24.5)],
            )

        knockout_base_2 = difference(
            knockout_base | place(0, 0, -28),
            [cylinder(28/2 + clearance, 4, "base_cartridge", vertices=10)  | place(27.5, 0, -24.5), h_slit_1 | place(0, -15.5, -24.5)],
            )

        output(
            join([
                knockout_base_1,
                knockout_base_2
            ])
        )
    return ctx.graph

def create_slit():
    with model("slit") as ctx:
        slit = cube(10, 28, 40, "slit")
        slit_1 = cube(10, 4, 52, "slit_1") | place(0, -12, 0)
        slit_2 = cube(10, 3, 56, "slit_2") | place(0, -11.5, 0)
        slit = union([slit, slit_1, slit_2])

        h_slit = cube(2, 30, 35, "h_slit")
        slit = difference(slit, [h_slit]) | place(0, -4, 0)

        output(slit)
    return ctx.graph

def create_film_cartridge():
    with model("film_cartridge") as ctx:
        cartridge = cylinder(24.5/2, 42, "cartridge")
        h_cartridge_1 = cylinder(23/2, 4, "h_cartridge_1")
        h_cartridge_2 = cylinder(9.55/2, 48, "h_cartridge_2")

        cartridge = difference(cartridge, [
            h_cartridge_1 | place(0, 0, 21),
            h_cartridge_1 | place(0, 0, -21),
            h_cartridge_2 | place(0, 0, 21)
        ])

        top_cartridge = cylinder(11/2, 7, "top_cartridge")
        h_top_cartridge_1 = cylinder(9.5/2, 9, "h_top_cartridge_1")

        top_cartridge = difference(top_cartridge, [h_top_cartridge_1])

        cartridge = union([cartridge, top_cartridge | place(0, 0, -24.5)])
        film_out = cube(12.25, 2, 42, "film_out") | place(-12.25/2, 12.25 - 1, 0)

        cartridge = union([cartridge, film_out]) | place(27.5, 0, 0)

        base_cartridge = cylinder(28.5/2, 8, "base_cartridge", vertices=10)  # cube(27, 27, 8, "base_cartridge")
        h_base_cartridge_1 = cylinder(25.5/2 + clearance *2, 8, "cartridge")
        h_base_cartridge_2 = cylinder(11/2 + clearance *2, 20, "h_cartridge_2")

        base_cartridge = difference(base_cartridge, [
            h_base_cartridge_1 | place(0, 0, 5),
        ])

        base_cartridge = union([base_cartridge,
            cylinder(22/2, 2, "base_cartridge") | place(0, 0, 2),
            cylinder(10.5, 14, "h_knockout") | place(0 , 0 , -8)
        ])

        base_cartridge = difference(base_cartridge, [
            h_base_cartridge_2 | place(0, 0, 5),
            cube(14.25, 2.5, 4, "film_out") | place(-14.25/2, 12.25 - 1, 3)
        ]) | place(27.5, 0, -22)

        base_cartridge = union([base_cartridge,
            cylinder(3.5, 2, "h_cartridge_2") | place(27.5, 0, -27)
        ]) | translate(0, 0, -0.5)

        output(
            join([
                base_cartridge,
                # cartridge
                ])
        )
    return ctx.graph

def create_sprocket():
    with model("sprocket") as ctx:
        sprocket_hat = cylinder(6, 7, "sprocket") | place(0, 0, 3)

        sprocket_teeth = cube(1.5, 14, 1, "sprocket_teeth")
        sprocket_tooth = union([
            sprocket_hat,
            sprocket_teeth,
            sprocket_teeth | rotate(0, 0, 45),
            sprocket_teeth | rotate(0, 0, 90),
            sprocket_teeth | rotate(0, 0, 135),
        ])

        sprocket_hat = difference(sprocket_tooth, [
            cylinder(9.55/2 - clearance, 4, "sprocket_hat_cut") | place(0, 0, -1)
        ])
        sprocket_col = cylinder(9.55/2, 35, "sprocket_col")

        sprocket = join([
            sprocket_hat | place(-27.5, 0, 28.167/2),
            sprocket_col | place(-27.5, 0, 0),
            sprocket_hat | rotate(0, 180, 0) | place(-27.5, 0, -28.167/2)
        ])

        output(
            sprocket
        )
    return ctx.graph

def create_clockwork_1():
    with model("clockwork_1") as ctx:
        knockout = cylinder(10 - clearance, 14, "knockout_12") | translate(0, 0, 2)
        knockout_base = cylinder(27/2, 2, "base_cartridge")

        knockout = union([
            knockout | place(0, 0, 0),
            knockout_base | place(0, 0, -4)
        ]) | place(27.5, 0, 29.5)


        knockout = difference(knockout, [
            cylinder(8/2 + clearance, 100, "h_cartridge_2", vertices=256)  | place(27.5, 0, 0)
        ])

        output(knockout)
    return ctx.graph

def create_clockwork_2():
    with model("clockwork_2") as ctx:
        knockout_22 = cylinder(15, 4, "knockout_2")
        h_knockout_22 = cylinder(11, 2, "h_knockout") | place(0, 0, -1)
        knockout_22 = difference(knockout_22, [
            h_knockout_22,
            cylinder(8/2 + clearance, 20, "h_axis", vertices=256)
        ])

        knockout_22 = union([
            knockout_22,
            cylinder(8/2, 30, "h_axis") | place(0, 0, -13)
        ])

        knockout_22 = difference(knockout_22, [
            cube(2, 30, 14, "base_cartridge") | place(0, 0, -25),
            cylinder(3 + clearance, 10, "h_key", vertices=6) | place(0, 0, 2)
        ])

        output(
            join([
                knockout_22 | place(27.5, 0, 39)
            ])
        )
    return ctx.graph

def create_clockwork_key():
    with model("clockwork_key") as ctx:
        key_0 = cylinder(3, 10, "key_1", vertices=6)
        key_1 = cube(15, 4, 2, "key_2") | place(0, 0, 4)
        key_2 = cube(4, 15, 2, "key_2") | place(0, 0, 4)

        key = union([
            key_0,
            key_1,
            key_2
        ]) | place(27.5, 0, 39)

        output(key)
    return ctx.graph


# create_knockout_34(),
# create_knockout_12(),


ALL_PARTS = [
    # create_rect_box(),
    # create_tube(),
    # create_tube_base(),
    create_knockout_base(),
    create_slit(),
    create_film_cartridge(),
    create_sprocket(),
    create_clockwork_1(),
    create_clockwork_2(),
    create_clockwork_key(),
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "spinner_combined.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "spinner_individual"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")