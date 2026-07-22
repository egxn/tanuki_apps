"""Mogura exposimeter — container, box, and clockwork knob."""

from tanuki.dsl import *

tolerance = 0.125


def create_container():
    with model("container") as ctx:
        container = cube(26, 26, 36, "container")

        h_esp_32 = cube(23 + tolerance * 2, 2, 36, "ESP32") | place(0, 10, 1.5)
        h_esp_32_2 = cube(20.5, 6, 36, "hole") | place(0, 10, 1.5)
        h_esp_usb = cube(10, 4, 18, "ESP32_USB") | place(0, 12.5, -18)

        h_battery = cube(24 + tolerance * 2, 12, 36, "battery") | place(0, 0, 1.5)
        h_battery_usb = cube(10, 4, 10, "h_battery_usb") | place(-13, 4, 3)
        h_switch = cylinder(2.5, 6, "switch") | rotate(90, 0, 90) | place(-13, 3, 13)

        h_encoder = cube(20 + tolerance * 2, 2, 36, "encoder") | place(0, -10, 1.5)
        h_encoder_2 = cube(18.5, 6, 36, "hole") | place(0, -10, 1.5)

        h_t = cube(12, 24, 36, "t") | place(0, 0, 1.5)

        container = difference(
            container,
            [
                h_encoder, h_esp_32, h_battery, h_esp_32_2,
                h_encoder_2, h_t, h_esp_usb, h_battery_usb, h_switch,
            ],
        )

        output(container)
    return ctx.graph


def create_box():
    with model("box") as ctx:
        box = cube(28, 33, 38, "box") | place(0, -4, 0)
        h_container = cube(
            26 + tolerance * 2, 31 + tolerance * 2, 38, "container_hole"
        ) | place(0, -4, -1)
        h_side_1 = cube(4, 8, 36, "side_hole_1") | place(-12, 1, -1)
        h_side_2 = cube(12, 7, 8, "side_hole_2") | place(0, 14, -1)
        h_side_3 = cube(8, 6, 20, "side_hole_3") | place(-3, -19, -10)
        h_side_4 = cube(12, 12, 20, "side_hole_4") | place(0, 0, 19)

        box = difference(box, [h_container, h_side_1, h_side_2, h_side_3, h_side_4])

        box_1 = cube(4, 1.5, 8, "box_lid") | place(4, 10, 14)
        box_2 = cube(4, 1.5, 8, "box_lid") | place(-4, 10, 14)

        box = union([box, box_1, box_2])

        output(box)
    return ctx.graph


def create_clockwork_knob():
    with model("clockwork_knob") as ctx:
        knob = cylinder(4, 13, "knob_base")
        h_knob = cylinder(3 + tolerance, 13, "knob_top") | place(0, 0, -1)

        knob_1 = cylinder(
            5, 4, "knob_part_1", vertices=10
        ) | rotate(0, 90, 90) | place(4, 0, 6)
        knob_2 = cylinder(
            5, 4, "knob_part_2", vertices=10
        ) | rotate(0, 90, 90) | place(-4, 0, 6)

        knob = union([knob, knob_1, knob_2])
        knob = difference(knob, [h_knob])

        output(knob)
    return ctx.graph


ALL_PARTS = [
    create_container,
    create_box,
    create_clockwork_knob,
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile mogura exposimeter parts")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "mogura_exposimeter_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "mogura_exposimeter_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")
