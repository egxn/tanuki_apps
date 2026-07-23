"""Test dissolve_faces behavior on a minimal case of overlapping coplanar walls."""
import sys
from pathlib import Path
_SRC_ROOT = Path(__file__).resolve().parent
for candidate in (_SRC_ROOT, *_SRC_ROOT.parents):
    if (candidate / "src" / "halo_maps").exists():
        _SRC_ROOT = str(candidate / "src")
        break
else:
    _SRC_ROOT = str(_SRC_ROOT)
if _SRC_ROOT not in sys.path:
    sys.path.insert(0, _SRC_ROOT)
try:
    sys.stdout.reconfigure(line_buffering=True)
except AttributeError:
    pass
import bpy, bmesh

# Build a minimal test: 2 quads at x=-17 sharing one edge (overlapping vertical wall case)
# A: y=[-12,-2], z=[0,5]  (canonical +x)
# B: y=[-7,3], z=[0,3]    (anti → recalc'd to +x too)
# After T-junction fix: A gets vertex at y=-7, y=-2 z-split at 3

bm = bmesh.new()

# A vertices (large quad)
a_bl = bm.verts.new((-17, -12, 0))
a_br = bm.verts.new((-17, -2,  0))
a_tr = bm.verts.new((-17, -2,  5))
a_tl = bm.verts.new((-17, -12, 5))

# B vertices (overlapping shorter quad, shares y=-7..-2, z=0..3 with A after T-fix)
b_bl = bm.verts.new((-17, -7, 0))   # T-junction on A's bottom
b_br = bm.verts.new((-17,  3, 0))
b_tr = bm.verts.new((-17,  3, 3))
b_tl = bm.verts.new((-17, -7, 3))   # T-junction on A's left

bm.verts.ensure_lookup_table()

# Create A as +x quad (CCW in YZ from +x view)
f_a = bm.faces.new([a_bl, a_br, a_tr, a_tl])

# Create B as +x quad
f_b = bm.faces.new([b_bl, b_br, b_tr, b_tl])

bm.normal_update()
print(f"A normal: {f_a.normal}")
print(f"B normal: {f_b.normal}")

# Merge coincident vertices (simulate remove_doubles — none here)
# Simulate T-junction fix: b_bl lies on A's bottom edge (a_bl to a_br)
# b_tl lies on A's left edge (a_bl to a_tl)
# After T-junction fix, these vertices would be inserted into A.
# Let's simulate by re-creating A as an n-gon with the T-junction vertices:

bm.faces.remove(f_a)  # remove old A

# A after T-junction fix (b_bl on bottom edge, b_tl on left edge):
# going CCW: a_bl → b_bl → a_br → a_tr → a_tl (top) → b_tl → a_bl
# But we also need b_br-like T-junction at (-17,-2,3) if h_B < h_A on right edge.
# Actually: b_tl = (-17,-7,3), which lies on A's left edge (-17,-12,0)→(-17,-12,5)?
# NO, b_tl = (-17,-7,3) has y=-7, A's left edge has y=-12. Different y.
# Actually A's bottom edge is (-17,-12,0)→(-17,-2,0). b_bl=(-17,-7,0) lies ON this.
# A's right edge is (-17,-2,0)→(-17,-2,5). Does any B vertex lie on this?
# b_br=(-17,3,0) has y=3 ≠ -2. No. But (-17,-2,3) would be on A's right edge... but that's not in B.
# A's left edge (-17,-12,0)→(-17,-12,5): b_tl=(-17,-7,3) has y=-7 ≠ -12. Not on A's left.
#
# So only b_bl is a T-junction on A's bottom edge. NOT b_tl.
# A after T-junction fix: a_bl → b_bl → a_br → a_tr → a_tl → a_bl (pentagon)
v_split = b_bl  # re-use b_bl as the T-junction point on A's bottom

f_a2 = bm.faces.new([a_bl, v_split, a_br, a_tr, a_tl])
bm.normal_update()
print(f"\nA (pentagon) normal: {f_a2.normal}")

# Now A (pentagon) and B (quad) share edge: v_split(b_bl) → a_br
# A edges: a_bl-v_split, v_split-a_br, a_br-a_tr, a_tr-a_tl, a_tl-a_bl
# B edges: b_bl-b_br, b_br-b_tr, b_tr-b_tl, b_tl-b_bl
# Shared: b_bl → a_br = v_split → a_br (B's bottom from y=-7 to y=-2)... but a_br=(-17,-2,0) and b_br=(-17,3,0)
# B's bottom edge: b_bl(y=-7) → b_br(y=3), NOT → a_br(y=-2)!

# Actually B and A share only ONE edge: the edge from b_bl(v_split) to a_br...
# Wait: B's bottom edge goes from b_bl(-17,-7,0) to b_br(-17,3,0).
# A's (pentagon) sub-bottom edge goes from v_split(b_bl) to a_br(-17,-2,0).
# These are DIFFERENT edges (b_br ≠ a_br). They don't share this edge!
# The only shared vertex is b_bl = v_split.

bm.edges.ensure_lookup_table()
shared = [e for e in bm.edges if
          all(any(v is vx for vx in e.verts) for f in [f_a2, f_b] for v in f.verts)
          and len(e.link_faces) >= 2
          and any(f is f_a2 for f in e.link_faces)
          and any(f is f_b for f in e.link_faces)]
print(f"\nShared edges between A(pentagon) and B(quad): {len(shared)}")
for e in shared:
    v0 = tuple(round(c,3) for c in e.verts[0].co)
    v1 = tuple(round(c,3) for c in e.verts[1].co)
    print(f"  edge {v0}→{v1}: {len(e.link_faces)} faces")

print(f"\nA(pentagon) edges: {len(f_a2.edges)}")
for e in f_a2.edges:
    v0 = tuple(round(c,3) for c in e.verts[0].co)
    v1 = tuple(round(c,3) for c in e.verts[1].co)
    print(f"  {v0}→{v1}: {len(e.link_faces)} faces")

print(f"\nB(quad) edges: {len(f_b.edges)}")
for e in f_b.edges:
    v0 = tuple(round(c,3) for c in e.verts[0].co)
    v1 = tuple(round(c,3) for c in e.verts[1].co)
    print(f"  {v0}→{v1}: {len(e.link_faces)} faces")

bm.free()
print("\ndone")
