from tanuki.dsl import *

col_r = 4.925
sqr_x = 65/2
sqr_y = 65/2
tolerance = 0.125
focus = 90 - 3.5


def create_dslr_scanner_setup():
    with model("dslr_scanner_setup") as ctx:
        base = cube(60, 80, 7, "base")
        base_supp = cube(80, 15, 7, "base_support")
        h_base_1 = cube(50 + tolerance, 55 + tolerance, 5 + tolerance, "h_base_1")
        base_support_tube = cube(10, 15, 15, "base_support_tube_1")
        h_base_support_tube = cylinder(4.925 + tolerance * 2, 160, "h_base_support_tube_1") | rotate(0, 90, 0)

        base = union([
            base,
            base_supp | translate(0, 65/2, 0),
            base_supp | translate(0, -65/2, 0),
            base_support_tube | translate(35, 65/2, 10),
            base_support_tube | translate(-35, -65/2, 10),
            base_support_tube | translate(35, -65/2, 10),
            base_support_tube | translate(-35, 65/2, 10),
        ])

        base = difference(base, [
            h_base_1 | translate(0, 0, 1),
            h_base_support_tube | translate(0, 65/2, 10.5),
            h_base_support_tube | translate(0, -65/2, 10.5),
            cylinder(10, 15, "h_base_support_tube_2"),
        ])

        output(base)

    return ctx.graph 

def create_cam_mount():
    with model("cam_mount") as ctx:
        base = cube(20, 80, 7, "base")
        base_support_tube = cube(10, 15, 15, "base_support_tube_1")
        h_base_support_tube = cylinder(4.925 + tolerance * 2, 160, "h_base_support_tube_1") | rotate(0, 90, 0)

        base = union([
            base,
            base_support_tube | translate(0, 65/2, 10),
            base_support_tube | translate(0, -65/2, 10),
            cube(20, 20, 50, "base_support_tube_2") | translate(0, 0, 28.5),
        ])

        base = difference(base, [
            h_base_support_tube | translate(0, 65/2, 10.5),
            h_base_support_tube | translate(0, -65/2, 10.5),
            cylinder(4, 100, "h_base_support_tube_2") | translate(0, 0, 40),
            cylinder(7, 50, "h_base_support_tube_3") | translate(0, 0, -3),
        ])

        base = base | translate(-80, 0, 0)
        output(base)

    return ctx.graph


def create_film_slider():
    with model("film_slider") as ctx:
        slider = cube(5, 80, 120, "slider_base") | translate(0, 0, 56.5)
        slider = union([
            slider,
            cube(20, 80, 7, "base") | translate(10, 0, 0),
            cube(20, 15, 15, "base_support_tube_1") | translate(10, 65/2, 10),
            cube(20, 15, 15, "base_support_tube_1") | translate(10, -65/2, 10)
        ])
        h_column1 = cylinder(col_r + tolerance * 2, 100, "column1") | rotate(0, 90, 0) | translate(0,  65/2, 10.5)
        h_column2 = cylinder(col_r + tolerance * 2, 100, "column2") | rotate(0, 90, 0) | translate(0, -65/2, 10.5)
        h_slider_1 = cube(100, 40, 34.5, "h_slider_1") | place(-30, 0, focus)
        h_slider_2 = cube(0.5, 120, 35 + tolerance, "h_slider_2") |  place(2.25, 0, focus)
        h_slider_3 = cube(40, 40, 34.5, "h_slider_3") | rotate(0, 0, 45) | place(5, 0, focus)
        h_below = cube(30, 30, 30, "h_below") | rotate(45, 0, 0) | place(0, 0, 40)
        slider = difference(slider, [h_column1, h_column2, h_slider_1, h_slider_2, h_slider_3, h_below])

        join_1 = cube(3, 40, 3, "join_1") | place(4, 0, focus + 20)
        join_2 = cube(3, 40, 3, "join_1") | place(4, 0, focus - 20)

        slider = union([slider, join_1, join_2])

        slider = slider | translate(-200, 0, 0)

        output(slider)
    return ctx.graph


def create_film_slider_2():
    with model("film_slider_2") as ctx:
        slider = cube(100, 45, 5, "slider") | place(0, 0, -5)
        h_slider_1 = cube(40, 34.5, 30, "h_slider")
        h_sprocket_gear = cube(15, 5, 10, "h_sprocket_gear")
        h_sprocket_gear_1 = h_sprocket_gear | place(30, 28.169/2, -5)
        h_sprocket_gear_2 = h_sprocket_gear | place(30, -28.169/2, -5)
        h_sprocket_col = cylinder(4, 60, "h_sprocket_col") | rotate(90, 0, 0) | place(30, 0, -7.5)

        sprocket_col_base_1 = cylinder(4.5, 3, "h_sprocket_col_base_1", 10) | rotate(90, 0, 0) | place(30, 28.169/2 + 6.9155, -7.5)
        sprocket_col_base_2 = cylinder(4.5, 3, "h_sprocket_col_base_2", 10) | rotate(90, 0, 0) | place(30, -28.169/2 - 6.9155, -7.5)
        h_sprocket_col_base = cylinder(2.25, 43, "h_sprocket_col_base") | rotate(90, 0, 0) | place(30, 0, -7.5)
        sprocket_col_base = union([sprocket_col_base_1, sprocket_col_base_2])
        sprocket_col_base = difference(sprocket_col_base, [h_sprocket_col_base])


        h_join_1 = cube(
            40 + tolerance, 3 + tolerance, 3 + tolerance, "join_1"
        ) | place(0, 20, -4)
        h_join_2 = cube(
            40 + tolerance, 3 + tolerance, 3 + tolerance, "join_1"
        ) | place(0, -20, -4)

        slider = difference(slider, [h_slider_1, h_join_1, h_join_2, h_sprocket_gear_1, h_sprocket_gear_2, h_sprocket_col])
        slider = union([slider, sprocket_col_base])

        slider = slider | rotate(-90, 0, 90) | place(-200, 0, 82)

        output(slider)
    return ctx.graph

def create_tube_support():
    with model("tube_support") as ctx:
        h_top = 82
        tube = cylinder(70/2, 20, "tube_support")
        h_tube = cylinder(62/2 + tolerance * 2, 20 + tolerance * 2, "h_tube_support")
        h_cube = cube(70, 70, 70, "h_cube") | place(-35, 0, 0)

        tube = difference(tube, [h_tube, h_cube]) | rotate(0, 90, 0) | translate(0, 0, h_top)

        base_support_tube = cube(20, 15, 15, "base_support_tube_1")

        base = union([
            cube(20, 80, 7, "base"),
            base_support_tube | translate(0, 65/2, 10),
            base_support_tube | translate(0, -65/2, 10),
            cube(20, 20, 50, "base_support_tube_2") | translate(0, 0, 25),
        ])

        h_base_support_tube = cylinder(4.925 + tolerance * 2, 160, "h_base_support_tube_1") | rotate(0, 90, 0)

        base = difference(base, [
            h_base_support_tube | translate(0, 65/2, 10.5),
            h_base_support_tube | translate(0, -65/2, 10.5),
        ])

        tube = union([tube, base]) | translate(-150, 0, 0)

        output(tube)
    return ctx.graph

ALL_PARTS = [
    create_dslr_scanner_setup(),
    create_cam_mount(),
    create_film_slider(),
    create_tube_support(),
    create_film_slider_2(),
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="DSLR scanner setup")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "dslr_scanner_setup_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "dslr_scanner_setup_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")
