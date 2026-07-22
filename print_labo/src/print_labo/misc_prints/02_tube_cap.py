from tanuki.dsl import *

tolerance = 0.125

def create_tube_support():
    with model("tube_support") as ctx:
        border = cube(133 - tolerance, 78 - tolerance, 3, "border")
        h_border = cube(128, 73, 3, "h_border")
        border = difference(border, [h_border])
        border_middle_1 = cube(10, 78, 3, "border_middle_1") 
        border_middle_2 = cube(128, 10, 3, "border_middle_2")
        border = union([
            border,
            border_middle_1,
            border_middle_2,
        ])

        slider_base = cylinder(65/2, 3, "slider_base")
        join_1 = cube(40, 3, 3, "join_1") | place(0, 19 + tolerance, 3)
        join_2 = cube(40, 3, 3, "join_2") | place(0, -19 + tolerance, 3)
        slider_base = union([slider_base, join_1, join_2, border])

        h_slider = cube(40, 34 - tolerance*2, 8, "h_slider_base")
        slider_base = difference(slider_base, [h_slider])

        h_cube_border = cube(34 - tolerance*2, 34 - tolerance*2, 34 - tolerance*2, "h_cube_border") | rotate(0, 45, 0) | translate(0, 0, 3)
        slider_base = difference(slider_base, [h_cube_border])

        output(slider_base)
    return ctx.graph


def create_film_slider_round():
    with model("film_slider_round") as ctx:
        slider = cylinder(65/2, 10, "slider")
        h_tube_1 = cylinder(61/2 + tolerance, 6, "h_tube_1", vertices=128) | place(0, 0, 2)
        h_slider_1 = cube(48, 34 , 30, "h_slider")
        h_join_1 = cube(
            40 + tolerance, 3 + tolerance, 3 + tolerance, "join_1"
        ) | place(0, 19 + tolerance, -3.5)
        h_join_2 = cube(
            40 + tolerance, 3 + tolerance, 3 + tolerance, "join_1"
        ) | place(0, -19 - tolerance, -3.5)

        slider = difference(slider, [h_slider_1, h_join_1, h_join_2, h_tube_1])

        output(slider)
    return ctx.graph

ALL_PARTS = [
    create_tube_support(),
    create_film_slider_round(),
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile tube cap parts")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "tube_cap.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "tube_cap_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")