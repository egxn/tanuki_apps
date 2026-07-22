"""Neganuki scanner — full film scanner assembly with 20+ parts."""

from tanuki.dsl import *

col_r = 4.925
sqr_x = 30
sqr_y = 30
tolerance = 0.125


def create_sensor_support():
    with model("sensor_support") as ctx:
        sensor_support = cube(
            (sqr_x + 10) * 2, (sqr_x + 10) * 2, 4, "sensor_support"
        ) | place(0, 0, -15)

        column1 = cylinder(col_r + 2, 30, "column1") | place(sqr_x, sqr_y, 0)
        column2 = cylinder(col_r + 2, 30, "column2") | place(-sqr_x, sqr_y, 0)
        column3 = cylinder(col_r + 2, 30, "column3") | place(sqr_x, -sqr_y, 0)
        column4 = cylinder(col_r + 2, 30, "column4") | place(-sqr_x, -sqr_y, 0)

        h_column1 = cylinder(col_r + tolerance, 30, "column1") | place(sqr_x, sqr_y, 0)
        h_column2 = cylinder(col_r + tolerance, 30, "column2") | place(-sqr_x, sqr_y, 0)
        h_column3 = cylinder(col_r + tolerance, 30, "column3") | place(sqr_x, -sqr_y, 0)
        h_column4 = cylinder(col_r + tolerance, 30, "column4") | place(-sqr_x, -sqr_y, 0)

        sensor_col1 = cylinder(4, 6, "sensor_col1") | place(17, 17, -11)
        sensor_col2 = cylinder(4, 6, "sensor_col2") | place(-17, 17, -11)
        sensor_col3 = cylinder(4, 6, "sensor_col3") | place(17, -17, -11)
        sensor_col4 = cylinder(4, 6, "sensor_col4") | place(-17, -17, -11)

        h_sensor_col1 = cylinder(2 - tolerance, 6, "h_sensor_col1") | place(17, 17, -11)
        h_sensor_col2 = cylinder(2 - tolerance, 6, "h_sensor_col2") | place(-17, 17, -11)
        h_sensor_col3 = cylinder(2 - tolerance, 6, "h_sensor_col3") | place(17, -17, -11)
        h_sensor_col4 = cylinder(2 - tolerance, 6, "h_sensor_col4") | place(-17, -17, -11)

        sensor_support = union([
            sensor_support, column1, column2, column3, column4,
            sensor_col1, sensor_col2, sensor_col3, sensor_col4,
        ])
        sensor_support = difference(sensor_support, [
            h_column1, h_column2, h_column3, h_column4,
            h_sensor_col1, h_sensor_col2, h_sensor_col3, h_sensor_col4,
        ])

        t_sensor_support = sensor_support | rotate(0, 180, 0) | translate(0, 0, 170)

        output(t_sensor_support)
    return ctx.graph


def create_columns():
    with model("columns") as ctx:
        column1 = cylinder(col_r, 200, "column1") | place(sqr_x, sqr_y, 0)
        column2 = cylinder(col_r, 200, "column2") | place(-sqr_x, sqr_y, 0)
        column3 = cylinder(col_r, 200, "column3") | place(sqr_x, -sqr_y, 0)
        column4 = cylinder(col_r, 200, "column4") | place(-sqr_x, -sqr_y, 0)

        columns = union([column1, column2, column3, column4])

        t_columns = columns | translate(0, 0, 70)

        output(t_columns)
    return ctx.graph

def create_dummy_stepper():
    with model("dummy_stepper") as ctx:
        stepper = cylinder(14, 19, "stepper")
        wires = cube(19, 10, 19, "wires") | place(0, -10, 0)

        connector_cyl = cylinder(5.8 / 2, 10, "connector") | place(0, 0, (19 / 2) + 5)
        connector_cube = cube(6, 3.8, 10, "connector") | place(0, 0, (19 / 2) + 5)
        connector = intersect([connector_cyl, connector_cube])
        t_connector = connector | translate(0, 8, 0)

        screws_base = cube(35, 4, 1, "screws_base") | place(0, 0, 19 / 2 - 0.5)

        stepper = union([stepper, wires, t_connector, screws_base])
        t_stepper = stepper | rotate(0, 0, 180) | translate(0, 40, -11)

        output(t_stepper)
    return ctx.graph

def create_cam_tripod_support():
    with model("create_cam_tripod_support") as ctx:
        base = cube(sqr_x * 2, 10, 20, "base") | place(0, sqr_y, 0)
        column1 = cylinder(col_r + 2, 20, "column1") | place(sqr_x, sqr_y, 0)
        column2 = cylinder(col_r + 2, 20, "column2") | place(-sqr_x, sqr_y, 0)

        h_column1 = cylinder(col_r + tolerance, 35, "column1") | place(sqr_x, sqr_y, 0)
        h_column2 = cylinder(col_r + tolerance, 35, "column2") | place(-sqr_x, sqr_y, 0)
        h_screw = cylinder(4, 30, "h_screw") | rotate(0, 90, 90) | place(0, sqr_y, 0)

        cam_support = union([base, column1, column2])
        cam_support = difference(cam_support, [h_column1, h_column2, h_screw])

        t_cam_support = cam_support | translate(0, 0, 40)

        output(t_cam_support)
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
            cube(6 + tolerance, 48.25, 6, "base_2") | place(sqr_x, 0, 1.50),
            cube(6 + tolerance, 48.25, 6, "base_2") | place(-sqr_x, 0, 1.50),
        ])
        slider = union([
            slider,
            join_1,
            join_2
        ]) | rotate(180, 0, 0) | translate(0, 0, 11.05) 

        output(slider)
    return ctx.graph


def create_film_slider_2():
    with model("film_slider_2") as ctx:
        slider = cube(80, 45, 5, "slider") | place(0, 0, -5)
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
        slider = union([slider, sprocket_col_base]) | rotate(180, 0, 0) | translate(0, 0, 11.05)

        output(slider)
    return ctx.graph

def create_film_slider_3():
    with model("film_slider_3") as ctx:
        base_1 = cylinder(6, 6, "base_1")
        h_base_2 = cylinder(col_r + tolerance, 6, "column_y") | place(0, 0, 0)

        base_1 = difference(base_1, [h_base_2])

        base_1 = union([
            base_1 | translate(sqr_x, sqr_y, 3.555),
            base_1 | translate(-sqr_x, sqr_y, 3.555),
            base_1 | translate(sqr_x, -sqr_y, 3.555),
            base_1 | translate(-sqr_x, -sqr_y, 3.555),
            cube(49.5, 6, 6, "base_2") | place(0, sqr_y, 3.555),
            cube(49.5, 6, 6, "base_2") | place(0, -sqr_y, 3.555),
            cube(6, 49.5, 12, "base_2") | place(sqr_x, 0, 6.555),
            cube(6, 49.5, 12, "base_2") | place(-sqr_x, 0, 6.555),
        ])

        output(base_1)
    return ctx.graph


def create_sprocket_gear():
    with model("sprocket_gear") as ctx:
        col = cylinder(3, 16, "sprocket_gear", 10)  | rotate(90, 0, 0)  | place(30, 0, -7.5)
        film_cog = cylinder(4, 4, "film_cog") | rotate(90, 0, 0) | place(30, 6, -7.5)
        teeth = cube(1.5, 11, 1.5, "teeth")
        tooth = [
            teeth | rotate(0, 0, 360 / 8 * 1) ,
            teeth | rotate(0, 0, 360 / 8 * 2) ,
            teeth | rotate(0, 0, 360 / 8 * 3) ,
            teeth | rotate(0, 0, 360 / 8 * 4) ,
        ]

        tooth = union(tooth) | rotate(90, 0, 0) | place(30, 6, -7.5)

        sprocket_gear = union([col, film_cog, tooth])
        sprocket_gear = sprocket_gear | place(0, 8, 0)
        h_base_top =  cylinder(2, 5, "h_sprocket_col_base", 10) | rotate(90, 0, 0) | place(30, 2.5, -7.5)
        h_base_bottom =  cylinder(2, 5, "h_sprocket_col_base", 256) | rotate(90, 0, 0) | place(30, 13.5, -7.5)
        sprocket_gear = difference(sprocket_gear, [h_base_top, h_base_bottom])

        join_1 =  cylinder(2 - tolerance, 10 - tolerance * 2, "h_sprocket_col_base", 10) | rotate(90, 0, 0) | place(30, 0, -7.5)
        join_2 =  cylinder(2 - tolerance, 10.5 - tolerance * 2, "h_sprocket_col_base", 256) | rotate(90, 0, 0) | place(30, 16.25, -7.5)

        sprocket_gear = join([sprocket_gear, join_1, join_2]) | rotate(180, 0, 0) | translate(0, 0, 11.05)

        output(sprocket_gear)
    return ctx.graph

def create_dummy_film():
    with model("dummy_film") as ctx:
        d_x_sprockets = 4.7498
        d_y_sprockets = 28.169

        film_35mm = cube(200, 34.95, 0.3, "film_35mm")
        h_sprocket = cube(1.98, 2.98, 5, "h_sprocket")

        n = int((200 / 2) / d_x_sprockets)
        positions = [
            (d_x_sprockets * i, d_y_sprockets / 2, 0)
            for i in range(-n, n + 1)
        ] + [
            (d_x_sprockets * i, -d_y_sprockets / 2, 0)
            for i in range(-n, n + 1)
        ]

        h_sprockets_top = clones(h_sprocket, positions)
        h_sprockets_bottom = clones(h_sprocket, [(x, -y, z) for (x, y, z) in positions])
        film_35mm = difference(film_35mm, [h_sprockets_top, h_sprockets_bottom]) | place(0, 0, -2)

        output(film_35mm)
    return ctx.graph

def create_lens_support():
    with model("lens_support") as ctx:
        lens_support = cube(
            (sqr_x + 10) * 2, (sqr_x + 10) * 2, 4, "lens_support"
        ) | place(0, 0, 15)

        column1 = cylinder(col_r + 2, 30, "column1") | place(sqr_x, sqr_y, 0)
        column2 = cylinder(col_r + 2, 30, "column2") | place(-sqr_x, sqr_y, 0)
        column3 = cylinder(col_r + 2, 30, "column3") | place(sqr_x, -sqr_y, 0)
        column4 = cylinder(col_r + 2, 30, "column4") | place(-sqr_x, -sqr_y, 0)

        h_column1 = cylinder(col_r + tolerance, 50, "column1") | place(sqr_x, sqr_y, 0)
        h_column2 = cylinder(col_r + tolerance, 50, "column2") | place(-sqr_x, sqr_y, 0)
        h_column3 = cylinder(col_r + tolerance, 50, "column3") | place(sqr_x, -sqr_y, 0)
        h_column4 = cylinder(col_r + tolerance, 50, "column4") | place(-sqr_x, -sqr_y, 0)
        h_lens = cylinder(39.25 / 2, 30, "h_lens") | place(0, 0, 15)

        lens_support = union([lens_support, column1, column2, column3, column4])
        lens_support = difference(
            lens_support, [h_column1, h_column2, h_column3, h_column4, h_lens]
        )

        t_lens_support = lens_support | rotate(180, 0, 0) | translate(0, 0, 100)

        output(t_lens_support)
    return ctx.graph

# ---------------------------------------------------------------------------
# CLI: compile all parts to Blender scripts
# ---------------------------------------------------------------------------

ALL_PARTS = [
    # create_sensor_support,
    # create_columns,
    # create_dummy_stepper,
    # create_cam_tripod_support,
    create_film_slider,
    create_film_slider_2,
    # create_sprocket_gear,
    create_dummy_film,
    # create_lens_support,
    create_film_slider_3,
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile neganuki scanner parts")
    parser.add_argument(
        "--mode",
        choices=["combined", "individual"],
        default="combined",
        help="Export mode: combined (single file) or individual (one file per part)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file (combined) or directory (individual)",
    )
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "neganuki_scanner_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "neganuki_scanner_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")

