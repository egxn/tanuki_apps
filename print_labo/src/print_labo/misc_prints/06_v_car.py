from print_labo.utils import flat_spring
from tanuki.dsl import *

CLR = 0.125  # mm
OPENBUILDS_2040_CAMERA_CARRIAGE = {
    "plate": {
        "size": {
            "x": 80.0,  # mm
            "y": 80.0,  # mm
            "z": 8.0,   # mm
        },
        "origin": "center",
        "notes": (
            "Dimensions are provisional. Based on a simplified OpenBuilds "
            "Mini V Gantry plate for a DSLR scanning carriage."
        ),
    },
    "holes": [
        {
            "id": "wheel_top_left",
            "type": "wheel",
            "x": -20.0,
            "y": 30.0,
            "radius": 2.6,      # Ø5.2
            "through": True,
            "notes": "Fixed wheel."
        },
        {
            "id": "wheel_top_right",
            "type": "wheel",
            "x": 20.0,
            "y": 30.0,
            "radius": 2.6,
            "through": True,
            "notes": "Fixed wheel."
        },
        {
            "id": "wheel_bottom_left",
            "type": "eccentric",
            "x": -20.0,
            "y": -30.0,
            "radius": 3.6,      # Ø7.2
            "through": True,
            "notes": (
                "Hole sized for OpenBuilds eccentric spacer. "
                "May require adjustment after CAD verification."
            )
        },
        {
            "id": "wheel_bottom_right",
            "type": "eccentric",
            "x": 20.0,
            "y": -30.0,
            "radius": 3.6,
            "through": True,
            "notes": (
                "Hole sized for OpenBuilds eccentric spacer. "
                "May require adjustment after CAD verification."
            )
        },
    ],
    "hardware": {
        "profile": "2040 V-Slot",
        "wheels": "625ZZ V-Wheels x4",
        "eccentric_spacers": 2,
        "precision_spacers": 2,
        "wheel_bolts": "M5 x 35",
        "wheel_nuts": "M5 Nyloc",
        "notes": (
            "Matches the hardware purchased for the scanner project."
        ),
    },
    "notes": (
        "Prototype specification. Wheel positions should be verified against "
        "the official OpenBuilds Mini V Gantry CAD before manufacturing."
    ),
}


def generate_car():
    plate_spec = OPENBUILDS_2040_CAMERA_CARRIAGE["plate"]
    size = plate_spec["size"]

    plate = cube(
        size["x"],
        size["y"],
        size["z"],
        "carriage_plate",
    )

    through_height = size["z"] + 2.0
    holes = [
        cylinder(hole["radius"], through_height, hole["id"])
        | place(hole["x"], hole["y"], 0)
        for hole in OPENBUILDS_2040_CAMERA_CARRIAGE["holes"]
        if hole["through"]
    ]

    h_tripod_1 = cylinder(3.2, 50, "tripod_hole_1")
    h_tripod_2 = cylinder(8, 18, "tripod_hole_2") | place(0, 0, 0)

    holes += [h_tripod_1, h_tripod_2]

    holes += [
        cylinder(4.6, 6.2, hole["id"], vertices=6) | place(
            hole["x"], hole["y"], -7)
        for hole in OPENBUILDS_2040_CAMERA_CARRIAGE["holes"]
        if hole["through"]
    ]

    plate = union([plate,
                   cube(70, 76, 6, "carriage_plate_l_1") | place(0, 0, -7),
                   cube(8, 8, 8, "carriage_plate_l_2") | place(-10,  31, -
                                                               10) | rotate(0, 45, 0) | place(0.2 + 8, 0, -10),
                   cube(8, 8, 9, "carriage_plate_l_2") | place(-10, -
                                                               31, -10) | rotate(0, 45, 0) | place(8.5, 0, -10),
                   cube(8, 70, 24, "carriage_plate_l_2") | place(-10, 0, -22),
                   cube(8, 45, 8, "support l") | rotate(
                       0, 45, 0) | place(-14, 0, -10),
                   cylinder(7, 16, "h_bolt", vertices=6) | rotate(
                       0, 0, 30) | place(0, 0, -8)
                   ])
    carriage = difference(plate, [
        *holes,
        cube(35, 54, 70, "tripod_hole_1") | place(0, 0, -52),
        cube(50, 80, 20) | place(0, 0, -45)
    ])
    return carriage


def create_openbuilds_2040_camera_carriage():
    with model("openbuilds_2040_camera_carriage") as ctx:
        carriage = generate_car()
        output(carriage)

    return ctx.graph


def create_bearing(bearing_x, bearing_y, id):
    bearing_name = "bearing_" + id
    carriage = generate_car()
    bearing = cylinder(6, 50, bearing_name) | place(bearing_x, bearing_y)
    bearing = intersect([carriage, bearing])

    return bearing


def create_whasers():
    """Create a set of washers for the OpenBuilds 2040 camera carriage."""
    with model("openbuilds_2040_camera_carriage_washers") as ctx:
        washer_specs = [
            {"id": "washer_m5", "outer_radius": 5.0,
                "inner_radius": 2.7, "thickness": 1.2},
        ]

        washers_m5 = cylinder(
            washer_specs[0]["outer_radius"], washer_specs[0]["thickness"], washer_specs[0]["id"])
        hole_m5 = cylinder(
            washer_specs[0]["inner_radius"], washer_specs[0]["thickness"] + 1.0, "hole_m5")
        washers_m5 = difference(washers_m5, [hole_m5])

        output(washers_m5)

    return ctx.graph


def create_v_slot_2040_base_end():

    with model("openbuilds_2040_camera_carriage_with_washers") as ctx:
        base = cube(30, 50, 50, "v_slot_2040_base_end")
        base_l_1 = cube(
            70, 85, 2, "v_slot_2040_base_end_l_1") | place(0, 0, -25)
        h_v_slot = cube(20 + CLR*4, 40 + CLR*4, 50,
                        "v_slot_2040_h_slot") | place(0, 0, 0)

        base = union([base, base_l_1])
        base = difference(base, [h_v_slot])

        v_cir_axis_1 = cylinder(
            2.10 - CLR*2, 10, "v_slot_2040_v_cir_axis_1") | place(0, 10, -20)
        v_cir_axis_2 = cylinder(
            2.10 - CLR*2, 10, "v_slot_2040_v_cir_axis_2") | place(0, -10, -20)
        h_l_slot_1 = cube(17 + CLR*4, 20 + CLR*4, 22, "v_slot_2040_h_l_v_slot")
        h_l_slot_2 = h_l_slot_1 | rotate(0, 0, 90) | place(0, 0, 0)
        h_l_v_slot_screw = cylinder(3.5, 20, "v_slot_2040_h_l_v_slot_screw")
        sqr_slot_1 = cube(20 - 1.80*2 - CLR*4, 4, 10, "v_slot_2040_sqr_slot")
        h_peg_corner = cylinder(1.5, 20, "v_slot_2040_peg")

        base = union([
            base, v_cir_axis_1,
            v_cir_axis_2,
            sqr_slot_1 | place(0, 0, -20)
        ])

        base = difference(base, [
            h_l_slot_1 | place(0, 30.5, -14),
            h_l_slot_1 | place(0, -30.5, -14),
            h_l_slot_2 | place(20.25, 10, -14),
            h_l_slot_2 | place(-20.25, 10, -14),
            h_l_slot_2 | place(20.25, -10, -14),
            h_l_slot_2 | place(-20.25, -10, -14),
            h_l_v_slot_screw | place(0, 28, -25),
            h_l_v_slot_screw | place(0, -28, -25),
            h_l_v_slot_screw | place(20, 10, -25),
            h_l_v_slot_screw | place(-20, 10, -25),
            h_l_v_slot_screw | place(20, -10, -25),
            h_l_v_slot_screw | place(-20, -10, -25),
            h_peg_corner | place(20, 30, -25),
            h_peg_corner | place(-20, 30, -25),
            h_peg_corner | place(20, -30, -25),
            h_peg_corner | place(-20, -30, -25),
        ])

        output(base)

    return ctx.graph


def create_leg():
    with model("openbuilds_2040_camera_carriage_leg") as ctx:
        leg = cube(30, 30, 40, "v_slot_2040_leg")
        h_screw = cylinder(2, 10, "v_slot_2040_h_screw") | place(5, 5, 20)
        h_screw_1 = cylinder(3, 2, "v_slot_2040_h_screw") | place(5, 5, 19)
        h_leg = cube(20, 20, 18 + CLR, "v_slot_2040_h_leg") | place(5, 5, 7)
        h_anti_slip_slop = cylinder(
            6.5, 5, "v_slot_2040_h_anti_slip_slop") | place(0, 0, -20)

        leg = difference(leg, [h_leg, h_screw, h_screw_1, h_anti_slip_slop])

        output(leg)

    return ctx.graph


def cover_l():
    with model("openbuilds_2040_camera_carriage_cover_l") as ctx:
        cover = cube(18, 18, 21, "v_slot_2040_cover_l")
        h_cover = cube(15 + CLR*3, 16.5 + CLR*3, 18 + CLR,
                       "v_slot_2040_h_cover") | place(1.5, 0, -1.5)

        cover = difference(cover, [h_cover])

        output(cover)

    return ctx.graph


def crate_build_space():
    with model("build_space") as ctx:

        build_space = union([
            cube(40, 5.2, 8, "build space") | place(0, 30, 0),
            cube(40, 5.2, 8, "build space") | place(0, -30, 0),
            cube(5.2, 50, 8, "build space") | place(20, 0, 0),
            cube(5.2, 50, 8, "build space") | place(-20, 0, 0),
            cube(5.2, 76, 8, "build space") | rotate(0, 0, 33.7),
            cube(5.2, 76, 8, "build space") | rotate(0, 0, -33.7)
        ])

        build_space = difference(build_space, [
            cylinder(3.5, 80, "h1") | place(20, 30, 0),
            cylinder(3.5, 80, "h2") | place(20, -30, 0),
            cylinder(3.5, 80, "h3") | place(-20, -30, 0),
            cylinder(3.5, 80, "h4") | place(-20, 30, 0),
            cylinder(9, 80, "h4")
        ])

        carriage = generate_car()
        load_base_1 = cube(14, 70, 100, "load_base_1") | place(-7, 0, 0)
        load_base_2 = cube(20, 45, 100, "load_base_2") | place(-10, 0, 0)

        load_base_a = intersect([carriage, load_base_1])
        load_base_b = intersect([carriage, load_base_2])
        load_base_c = intersect([carriage, cylinder(10, 50, "load_bolt")])

        load_base = union([load_base_a, load_base_b, load_base_c])

        build_space = union([
            build_space,
            load_base,
            create_bearing(20, 30,  "01"),
            create_bearing(-20, 30,  "02"),
            create_bearing(20, -30, "03"),
            create_bearing(-20, -30, "04"),

        ])

        output(build_space)
    return ctx.graph


def create_film_slider():
    with model("film_slider") as ctx:
        slider_base = cube(80, 45, 7, "slider_base") | place(0, 0, 1)

        slider = difference(slider_base, [
            cube(40, 34.25, 30, "light in hole"),
            cube(160, 35 + CLR, 1.5, "recess") | place(0, 0, -2.25),
            cube(35, 34.25, 35, "recess angle") | rotate(
                0, 45, 0) | place(0, 0, -2.25),
        ])

        spring_1 = flat_spring(
            length=28,
            width=20,
            curves=6,
            track_width=2,
            extrusion_height=4,
            start_side="right",
            head_length=4,
            tail_length=4,
        )

        spring_2 = flat_spring(
            length=28,
            width=20,
            curves=6,
            track_width=2,
            extrusion_height=4,
            start_side="right",
            tail_length=2,
        )

        spring_3 = flat_spring(
            length=30,
            width=20,
            curves=7,
            track_width=2,
            extrusion_height=4,
            start_side="right",
            head_length=3,
        )

        slider = union([
            slider,
            cube(80, 3, 3, "join_1") | place(0,  19.0625, -4),
            cube(80, 3, 3, "join_2") | place(0, -19.0625, -4),
            cube(20, 4, 4) | place(0, 57, 2.5),
            spring_1 | place(-10, 23.5, 0.5),
            spring_2 | rotate(0, 0, 90) | place(69, -10, 0.5),
            spring_3 | rotate(0, 0, 90) | place(-41, -10, 0.5)
        ])

        output(slider)
    return ctx.graph


def create_film_slider_2():
    with model("film_slider_2") as ctx:
        slider = union([
            cube(82, 45, 5, "slider") | place(0, 0, -5),
            # cube(42, 38, 20, "slider") | place(0, 0, -15),
        ])

        
        h_slider_1 = cube(40, 34.5, 100, "h_slider")
        h_sprocket_gear = cube(15, 5, 10, "h_sprocket_gear")
        h_sprocket_gear_1 = h_sprocket_gear | place(30, 28.169/2, -5)
        h_sprocket_gear_2 = h_sprocket_gear | place(30, -28.169/2, -5)
        h_sprocket_col = cylinder(1.5, 60, "h_sprocket_col") | rotate(90, 0, 0) | place(30, 0, -7.5)

        sprocket_col_base_1 = cylinder(4.5, 3, "h_sprocket_col_base_1", 10) | rotate(90, 0, 0) | place(30, 28.169/2 + 6.9155, -7.5)
        sprocket_col_base_2 = cylinder(4.5, 3, "h_sprocket_col_base_2", 10) | rotate(90, 0, 0) | place(30, -28.169/2 - 6.9155, -7.5)
        h_sprocket_col_base = cylinder(2.25, 43, "h_sprocket_col_base") | rotate(90, 0, 0) | place(30, 0, -7.5)
        sprocket_col_base = union([sprocket_col_base_1, sprocket_col_base_2])
        sprocket_col_base = difference(sprocket_col_base, [h_sprocket_col_base])

        h_join_1 = cube(80 + CLR, 3 + CLR, 3 + CLR*2, "join_1") | place(0,  19.0625, -4)
        h_join_2 = cube(80 + CLR, 3 + CLR, 3 + CLR*2, "join_1") | place(0, -19.0625, -4)

        slider = difference(slider, [h_slider_1, h_sprocket_gear_1, h_sprocket_gear_2, h_sprocket_col])
        slider = union([slider, sprocket_col_base])
        slider = difference(slider, [
            h_join_1, 
            h_join_2,
            cube(35, 34.5, 35, "recess angle") | rotate(0, 45, 0)
            ]) | translate(0, 0, -3)

        output(slider)
    return ctx.graph


ALL_PARTS = [
    # crate_build_space(),
    # create_openbuilds_2040_camera_carriage()
    # Keep the spring isolated while validating its profile.  The second
    # slider is a separate, non-planar assembly and can be enabled again once
    # the spring has been inspected.
    # create_film_slider(),
    create_film_slider_2(),
]


if __name__ == "__main__":
    from pathlib import Path

    from print_labo.utils.compile_cli import run_compile_cli

    run_compile_cli(
        graphs=ALL_PARTS,
        description="Compile vcar parts",
        source_script=Path(__file__).resolve(),
        default_output="vcar.py",
        default_output_dir="vcar_gen",
        watch_base_dir=Path(__file__).resolve().parent,
    )
