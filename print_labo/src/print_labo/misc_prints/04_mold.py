from tanuki.dsl import *

clearance = 0.125

def create_mold():
    with model("mold") as ctx:
        mold = cube(150, 150, 20, "mold")
        h_mold = cube(148, 148, 20, "h_mold") 
        mold = difference(mold, [h_mold])

        supp_1 = cube(2, 150, 4, "supp_1")
        supp_2 = cube(150, 2, 4, "supp_2")
        supp_3 = cube(2, 212, 4, "supp_3") | rotate(0, 0, 45)
        supp_4 = cube(2, 212, 4, "supp_4") | rotate(0, 0, -45)

        mold = union([mold, 
                      supp_1 | place(0, 0, 8),
                      supp_2 | place(0, 0, 8),
                      supp_3 | place(0, 0, 8),
                      supp_4 | place(0, 0, 8)
                      ]) | place(0, 0, 10.5)

        output(mold)
    return ctx.graph


ALL_PARTS = [
    create_mold(),
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "mold_combined.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "mold_individual"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")