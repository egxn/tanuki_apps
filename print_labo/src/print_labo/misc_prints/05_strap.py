from tanuki.dsl import *

clearance = 0.125

def create_strap_tube():
    with model("strap_tube") as ctx:
        strap_tube = cylinder(6, 20, "strap_tube")
        h_strap = cylinder(5, 25, "h_strap") 
        mold = difference(strap_tube, [h_strap])

        output(mold)
    return ctx.graph


ALL_PARTS = [
    create_strap_tube(),
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "strap_tube_combined.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "strap_tube_individual"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")