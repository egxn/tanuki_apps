from tanuki.dsl import *
from tanuki.dsl.custom.mesh_analysis import mesh_analysis, mesh_analysis_planar

# Full joined analysis (single object)
with model("polygonal_sphere_mesh_analysis") as ctx:
    base = sphere(2, segments=16, rings=8, label="poly_sphere")
    result = mesh_analysis(base, arm_length=0.3)
    output(result)

# Separate flat objects for 2D printing
with model("sphere_edges_flat") as ctx_edges:
    base = sphere(2, segments=16, rings=8, label="poly_sphere")
    parts = mesh_analysis_planar(base, arm_length=0.3, edge_radius=0.02, spacing=6.0)
    output(parts["edges"])

with model("sphere_faces_flat") as ctx_faces:
    base = sphere(2, segments=16, rings=8, label="poly_sphere")
    parts = mesh_analysis_planar(base, arm_length=0.3, spacing=6.0)
    output(parts["faces"])

with model("sphere_flat_angles") as ctx_flat:
    base = sphere(2, segments=16, rings=8, label="poly_sphere")
    parts = mesh_analysis_planar(base, arm_length=0.3, spacing=6.0)
    output(parts["flat_angles"])

combined_export(
    [ctx.graph, ctx_edges.graph, ctx_faces.graph, ctx_flat.graph],
    "polygonal_sphere_mesh_analysis_output.py",
)
