from tanuki.dsl import *
from tanuki.dsl.custom import mesh_analysis


def make_dodecahedron(radius: float = 2.0, label: str = "dodeca"):
    seed = ico_sphere(radius=radius, subdivisions=1, label=f"{label}_seed")
    return seed | dual_mesh()

with model("dodecahedron_mesh_analysis") as ctx:
    base = make_dodecahedron(2.0, label="dodeca")
    result = mesh_analysis(base, arm_length=0.3)
    output(result)

combined_export([ctx.graph], "dodecahedron_mesh_analysis_output.py")
