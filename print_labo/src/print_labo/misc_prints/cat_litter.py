from tanuki.dsl import *

clearance = 0.125

HOOP_SEGMENTS = 8

HOOP_OUTER_DIAMETER = 422
HOOP_INNER_DIAMETER = 416
HOOP_DEPTH = 400
HOOP_CUT_DEPTH = 450

COVER_BORDER_OUTER_DIAMETER = 440
COVER_BORDER_INNER_DIAMETER = 360
COVER_BORDER_DEPTH = 40
COVER_BORDER_CUT_DEPTH = 60

FRONT_COVER_DIAMETER = 440
FRONT_COVER_DEPTH = 10
FRONT_COVER_CUT_DEPTH = 20

TRACK_OUTER_DIAMETER = 440
TRACK_DEPTH = 50
TRACK_RING_INNER_DIAMETER = 425
TRACK_RING_DEPTH = 30
TRACK_OFFSET_Y = 145

CHEST_WIDTH = 330
CHEST_DEPTH = 420
CHEST_HEIGHT = 140
CHEST_Z_OFFSET = -320
CHEST_INNER_WIDTH = 300
CHEST_INNER_HEIGHT = 110
CHEST_INNER_Y_OFFSET = 10
CHEST_INNER_Z_OFFSET = -250

FRONT_COVER_BORDER_Y = 190
FRONT_COVER_Y = 220
BOTTOM_COVER_BORDER_Y = -190
BOTTOM_COVER_Y = -205


def _hoop_shell(label: str, hollow_label: str):
    hoop = cylinder(
        HOOP_OUTER_DIAMETER / 2, HOOP_DEPTH, label, vertices=HOOP_SEGMENTS
    ) | rotate(90, 0, 0)
    hollow_hoop = cylinder(
        HOOP_INNER_DIAMETER / 2, HOOP_CUT_DEPTH, hollow_label, vertices=HOOP_SEGMENTS
    ) | rotate(90, 0, 0)
    return difference(hoop, [hollow_hoop])

def create_hoop():
    with model("hoop") as ctx:
        hoop = _hoop_shell("hoop", "h_hoop")

        output(hoop)
    return ctx.graph

def front_cover_hoop():
    with model("front_cover_hoop") as ctx:
        hoop = _hoop_shell("hoop", "h_hoop")

        cover_border = cylinder(
            COVER_BORDER_OUTER_DIAMETER / 2, 
            COVER_BORDER_DEPTH, 
            "cover", 
            vertices=256
        ) | rotate(90, 0, 0) | translate(0, FRONT_COVER_BORDER_Y, 0)
        h_cover_border = cylinder(
            COVER_BORDER_INNER_DIAMETER / 2,
            COVER_BORDER_CUT_DEPTH, "h_cover_border", vertices=256
        ) | rotate(90, 0, 0) | translate(0, FRONT_COVER_BORDER_Y, 0)
        cover_border = difference(cover_border, [h_cover_border, hoop])

        output(cover_border)
    return ctx.graph

def bottom_cover_hoop():
    with model("bottom_cover_hoop") as ctx:
        hoop = _hoop_shell("hoop", "h_hoop")

        cover_border = cylinder(
            COVER_BORDER_OUTER_DIAMETER / 2, 
            COVER_BORDER_DEPTH, 
            "cover", vertices=256
        ) | rotate(90, 0, 0) | translate(0, BOTTOM_COVER_BORDER_Y, 0)

        h_cover_border = cylinder(
            COVER_BORDER_INNER_DIAMETER / 2,
            COVER_BORDER_CUT_DEPTH, "h_cover_border", vertices=256
        ) | rotate(90, 0, 0) | translate(0, BOTTOM_COVER_BORDER_Y + 20, 0)

        cover = difference(cover_border, [hoop, h_cover_border])

        output(cover)
    return ctx.graph

def create_roll_track():
    with model("roll_track") as ctx:
        h_hoop = cylinder(
            HOOP_OUTER_DIAMETER / 2, HOOP_DEPTH, "hoop", vertices=HOOP_SEGMENTS
        ) | rotate(90, 0, 0)
        track = cylinder(
            TRACK_OUTER_DIAMETER / 2, TRACK_DEPTH, "cover", vertices=256
        ) | rotate(90, 0, 0)
        track = difference(track, [h_hoop])

        external = cylinder(
            TRACK_OUTER_DIAMETER / 2 + 2, TRACK_RING_DEPTH, "h_external", vertices=256
        ) | rotate(90, 0, 0)
        h_external = cylinder(
            TRACK_RING_INNER_DIAMETER / 2, TRACK_RING_DEPTH + clearance, "h_external", vertices=256
        ) | rotate(90, 0, 0)
        external = difference(external, [h_external])

        track = difference(track, [external])

        output(
            join(
                [
                    track | translate(0, TRACK_OFFSET_Y, 0),
                    track | translate(0, -TRACK_OFFSET_Y, 0),
                ]
            )
        )

    return ctx.graph

def create_chest():
    with model("chest") as ctx:
        chest = cube(
            CHEST_WIDTH, CHEST_DEPTH, CHEST_HEIGHT, "chest"
        ) | translate(0, 0, CHEST_Z_OFFSET)
        h_chest = cube(
            CHEST_INNER_WIDTH, CHEST_DEPTH, CHEST_INNER_HEIGHT, "h_chest"
        ) | translate(0, CHEST_INNER_Y_OFFSET, CHEST_Z_OFFSET)
        chest = difference(chest, [h_chest])

        output(chest)

    return ctx.graph

ALL_PARTS = [
    create_hoop(),
    front_cover_hoop(),
    bottom_cover_hoop(),
    create_roll_track(),
    create_chest(),
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "cat_litter_combined.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "cat_litter_individual"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")