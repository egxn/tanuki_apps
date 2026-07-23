from tanuki.dsl import *
from tanuki.dsl.custom.mesh_analysis import mesh_analysis, mesh_analysis_planar

# Full joined analysis (single object)
with model("cube_mesh_analysis") as ctx:
    base = cube(2, 2, 2, "box")
    result = mesh_analysis(base, arm_length=0.3)
    output(result)

# Separate flat objects for 2D printing — each group is its own collection object,
# projected to XY and positioned side-by-side
with model("cube_edges_flat") as ctx_edges:
    base = cube(2, 2, 2, "box")
    parts = mesh_analysis_planar(base, arm_length=0.3, edge_radius=0.02, spacing=6.0)
    output(parts["edges"])

with model("cube_faces_flat") as ctx_faces:
    base = cube(2, 2, 2, "box")
    parts = mesh_analysis_planar(base, arm_length=0.3, spacing=6.0)
    output(parts["faces"])

with model("cube_flat_angles") as ctx_flat:
    base = cube(2, 2, 2, "box")
    parts = mesh_analysis_planar(base, arm_length=0.3, spacing=6.0)
    output(parts["flat_angles"])

combined_export(
    [ctx.graph, ctx_edges.graph, ctx_faces.graph, ctx_flat.graph],
    "cube_mesh_analysis_output.py",
)
