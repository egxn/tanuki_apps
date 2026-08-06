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



def create_openbuilds_2040_camera_carriage():
    """Build the plate by subtracting every specified cylindrical hole."""
    plate_spec = OPENBUILDS_2040_CAMERA_CARRIAGE["plate"]
    size = plate_spec["size"]

    with model("openbuilds_2040_camera_carriage") as ctx:
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
        
        h_tripod_1 = cylinder(3, 10, "tripod_hole_1")
        h_tripod_2 = cylinder(6, 4, "tripod_hole_2") | place(0, 0, 2)
        holes += [h_tripod_1, h_tripod_2]
        
        carriage = difference(plate, holes)
        output(carriage)

    return ctx.graph


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
        base_l_1 = cube(70, 85, 2, "v_slot_2040_base_end_l_1") | place(0, 0, -25)
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
        h_leg = cube(20, 20, 18  + CLR, "v_slot_2040_h_leg") | place(5, 5, 7)
        h_anti_slip_slop = cylinder(6.5, 5, "v_slot_2040_h_anti_slip_slop") | place(0, 0, -20)

        leg = difference(leg, [h_leg, h_screw, h_screw_1, h_anti_slip_slop])

        output(leg)

    return ctx.graph

def cover_l():
    with model("openbuilds_2040_camera_carriage_cover_l") as ctx:
        cover = cube(18, 18, 21, "v_slot_2040_cover_l")
        h_cover = cube(15 + CLR*3, 16.5 + CLR*3, 18 + CLR, "v_slot_2040_h_cover") | place(1.5, 0, -1.5)

        cover = difference(cover, [h_cover])

        output(cover)

    return ctx.graph

ALL_PARTS = [
    # cover_l(),
    create_openbuilds_2040_camera_carriage(),
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
