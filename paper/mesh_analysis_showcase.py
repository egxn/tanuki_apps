from tanuki.dsl import *
from tanuki.dsl.custom import mesh_analysis, mesh_analysis_planar


def make_dodecahedron(radius: float = 2.0, label: str = "dodeca"):
    seed = ico_sphere(radius=radius, subdivisions=1, label=f"{label}_seed")
    return seed | dual_mesh()


# Full joined analysis for a cube
with model("cube_mesh_analysis_showcase") as ctx_cube:
    cube_base = cube(2, 2, 2, "box")
    cube_result = mesh_analysis(cube_base, arm_length=0.3)
    output(cube_result)


# Full joined analysis for a dodecahedron-like solid
with model("dodecahedron_mesh_analysis_showcase") as ctx_dodeca:
    dodeca_base = make_dodecahedron(radius=2.0, label="dodeca")
    dodeca_result = mesh_analysis(dodeca_base, arm_length=0.3)
    output(dodeca_result)


# Flat printable connector layout for the cube
with model("cube_flat_angles_showcase") as ctx_cube_flat:
    cube_base = cube(2, 2, 2, "box")
    cube_parts = mesh_analysis_planar(cube_base, arm_length=0.3, spacing=6.0)
    output(cube_parts["flat_angles"])


# Flat printable connector layout for the dodecahedron-like solid
with model("dodecahedron_flat_angles_showcase") as ctx_dodeca_flat:
    dodeca_base = make_dodecahedron(radius=2.0, label="dodeca")
    dodeca_parts = mesh_analysis_planar(dodeca_base, arm_length=0.3, spacing=6.0)
    output(dodeca_parts["flat_angles"])


combined_export(
    [
        ctx_cube.graph,
        ctx_dodeca.graph,
        ctx_cube_flat.graph,
        ctx_dodeca_flat.graph,
    ],
    "mesh_analysis_showcase_output.py",
)