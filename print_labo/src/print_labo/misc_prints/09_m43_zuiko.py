from tanuki.dsl import *


CLEARANCE = 0.125

def create_adapter():
    with model("adapter") as context:
        adapter = cylinder(24, 30, "linkage_rod") 
        h_adpater = cylinder(20, 32, "linkage_rod")
        adapter = difference(adapter, [h_adpater])
        output(adapter)

    return context.graph



ALL_PARTS = [
    create_adapter(),
]

if __name__ == "__main__":
    from pathlib import Path

    from print_labo.utils.compile_cli import run_compile_cli

    run_compile_cli(
        graphs=ALL_PARTS,
        description="Compile lamp parts",
        source_script=Path(__file__).resolve(),
        default_output="lamp.py",
        default_output_dir="lamp_gen",
        watch_base_dir=Path(__file__).resolve().parent,
    )
