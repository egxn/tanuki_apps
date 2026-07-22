from tanuki.dsl import *

clearance = 0.125

def create_external_container():
    with model("external_container") as ctx:        
        container = cylinder(55, 110, "container", vertices=10) 
        h_container = cylinder(50, 110, "h_container") | translate(0, 0, 5)
        spool_support = cylinder(25.5/2, 85, "spool_support") | translate(0, 0, -12.5)
        h_spool_support = cylinder(20.5/2, 85, "h_spool_support") | translate(0, 0, -12.5)
        spool_support = difference(spool_support, [h_spool_support])

        container = difference(container, [h_container])
        container = union([container, spool_support])

        output(container)
    return ctx.graph

def create_spool():
    with model("spool") as ctx:
        spool_spiral = cylinder(94/2, 4, "spool", vertices=128)
        spool_curve = curve_spiral(
            resolution=128,
            rotations=8,
            start_radius=37/2,
            end_radius=94/2 - 1,
            height=1,
        )
        profile = curve_quadrilateral(width=1.5, height=8)
        spiral_plane = (
            spool_curve
            | curve_to_mesh(profile=profile, fill_caps=True)
        )
        spool_spiral= difference(spool_spiral, [spiral_plane])

        spool_col = cylinder(37/2, 36, "spool_col")

        spool = union([
            spool_spiral | place(0, 0, 17.5),
            spool_col,
            spool_spiral | place(0, 0, -17.5),
        ])

        h_spool_col = cylinder(27/2, 100, "h_spool_col")

        spool = difference(spool, [h_spool_col]) | translate(0, 0, -28)

        
        output(spool)
    return ctx.graph


ALL_PARTS = [
    create_external_container,
    create_spool,
]

if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile dev tank parts")
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "dev_tank_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = args.output or "dev_tank_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files in {out}/")