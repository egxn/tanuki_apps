"""Tray — cube with multiple subtracted cavities."""

from tanuki.dsl import *

tolerance = 0.125


def create_tray():
    with model("tray") as ctx:
        base = cube(107.5, 31, 9, "base")

        h_base_1 = cube(103, 31, 9, "h_base_1") | place(0, -2, 2)
        h_base_2 = cube(23, 31, 9, "h_base_2") | place(0, 0, 2)
        h_base_3 = cube(12, 31, 9, "h_base_3") | place(25, 0, 2)
        h_base_4 = cube(12, 31, 9, "h_base_4") | place(-25, 0, 2)
        h_base_5 = cube(3, 31, 2, "h_base_5") | place(36.5, 0, -4.5)
        h_base_6 = cube(3, 31, 2, "h_base_6") | place(-36.5, 0, -4.5)

        base = difference(
            base,
            [h_base_1, h_base_2, h_base_3, h_base_4, h_base_5, h_base_6],
        )

        output(base)
    return ctx.graph


ALL_PARTS = [
    create_tray,
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile tray parts")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "tray_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "tray_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")
