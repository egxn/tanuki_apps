
from tanuki.dsl import *

tolerance = 0.125


def create_tube_ext():
    with model("tube_ext") as ctx:
        tube_1 = cylinder(65/2, 20, "tube_1", vertices=128)
        h_tube_1 = cylinder(61/2 + tolerance, 20, "h_tube_1", vertices=128) | place(0, 0, -1)
        tube_1 = difference(tube_1, [h_tube_1])

        tube_2 = cylinder(65/2, 10, "tube_2", vertices=128) | place(0, 0, 15)
        h_tube_2 = cylinder(57/2 + tolerance, 10, "h_tube_2", vertices=128) | place(0, 0, 16)
        tube_2 = difference(tube_2, [h_tube_2])

        tube = union([tube_1, tube_2])
        h_tube = cylinder(40/2, 30, "h_tube", vertices=128) 
        tube = difference(tube, [h_tube])

        output(tube)
    return ctx.graph


def create_film_slider_round():
    with model("film_slider_round") as ctx:
        slider = cylinder(65/2, 10, "slider")
        h_tube_1 = cylinder(61/2 + tolerance, 5, "h_tube_1", vertices=128) | place(0, 0, 5)
        h_slider_1 = cube(40, 34.25, 30, "h_slider")
        h_join_1 = cube(
            40 + tolerance, 3 + tolerance, 3 + tolerance, "join_1"
        ) | place(0, 20, -3.5)
        h_join_2 = cube(
            40 + tolerance, 3 + tolerance, 3 + tolerance, "join_1"
        ) | place(0, -20, -3.5)

        slider = difference(slider, [h_slider_1, h_join_1, h_join_2, h_tube_1])

        output(slider)
    return ctx.graph

def create_film_slider():
    with model("film_slider") as ctx:
        slider_base = cube(
            52, 45, 7, "slider_base"
        ) | place(0, 0, 1)

        slider_base = union([
            slider_base,
            cube(72, 10, 6.5, "h_sprocket_gear") | place(0, 0, 1.25),
        ])

        h_slider_1 = cube(40, 34.25, 30, "h_slider")
        h_slider_2 = cube(160, 35 + tolerance, 0.5, "h_slider") | place(0, 0, -2.25)
        h_slider_3 = cube(35, 34.25, 35, "h_below") | rotate(0, 45, 0) | place(0, 0, -2.25)

        join_1 = cube(40, 3, 3, "join_1") | place(0, 20, -4)
        join_2 = cube(40, 3, 3, "join_1") | place(0, -20, -4)

        slider = difference(slider_base, [
            h_slider_1,
            h_slider_2,
            h_slider_3,
            cube(6 + tolerance, 48.25, 6, "base_2") | place(30, 0, 1.50),
            cube(6 + tolerance, 48.25, 6, "base_2") | place(-30, 0, 1.50),
        ])
        slider = union([
            slider,
            join_1,
            join_2
        ]) | rotate(180, 0, 0) | translate(0, 0, 11.05) 

        output(slider)
    return ctx.graph

ALL_PARTS = [
    create_tube_ext,
    create_film_slider_round,
    create_film_slider,
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile tube_ext parts")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "tube_ext_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "tube_ext_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")
