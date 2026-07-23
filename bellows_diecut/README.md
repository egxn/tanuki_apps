# Bellows Diecut

Generator of 3D printable diecut molds (male/female) for crafting bellows on handmade analog cameras. From geometric parameters, the project produces STL meshes ready to print that stamp fold patterns onto fabric when pressed together.

---

## Setup

``` bash
python -m venv .venv
source .venv/bin/activate

pip install -e ../../tanuki/
pip install -e ".[dev]"

PYTHONPATH=src python -m bellows_diecut.web
```


## Goal

Fabricate collapsible photographic bellows (Minolta Bellows, vintage Kodak folding cameras style) using structural origami patterns. The pipeline goes from parametric pattern generation in Python to two 3D printable pieces — male and female — that simultaneously stamp all valley and mountain fold lines onto fabric in a single press operation.

The pattern is worked **developed flat**: the fabric comes out of the diecut flat with the folds marked, then gets closed manually into a cylinder with a straight seam.

---

## Supported Patterns

Each pattern is a **unit cell** (transcribed from the SVG reference at the bottom
of this file) that **tessellates** across the print bed via `generate_tessellation`
(see "Tile Specifications" below).

| Pattern | Collapse type | Rotation on compression | Status |
|---|---|---|---|
| Yoshimura | Axial | No | Cell + tessellation |
| Miura | Planar (1 axis) | No | Cell + tessellation |
| Waterbomb | Axial / radial | No | Cell + tessellation |
| Kresling | Axial + torsion | Yes | Cell + tessellation |
| Resch | Complex / bistable | No | Cell + tessellation |
| Accordion | Axial (trapezoidal) | No | Cell + tessellation |

---

## Project Architecture

Tanuki-based module: fold patterns are pure Python; the male/female dies are the
**folded foldcore surface** computed in NumPy, then imported into the **Tanuki
DSL** (`import_obj`) and baked to STL in Blender.

```
bellows_diecut/
│
├── __init__.py             # High-level API: generate_pattern / generate_diecut
├── parameters.py           # BellowsParams (cell_scale + relief sizing)
│
├── patterns/               # Unit-cell generators → FoldPattern (one tile each)
│   ├── __init__.py         # REGISTRY + dispatch
│   ├── yoshimura.py        # V + diamond
│   ├── miura.py            # diapason / Y
│   ├── waterbomb.py        # mirrored trapezoids + X
│   ├── kresling.py         # stacked parallelograms + inner V
│   └── resch.py            # 2×2 squares + attached square + X
│
├── core/
│   ├── geometry.py         # FoldType/FoldLine/FoldPattern, cell_from_edges
│   ├── foldcore.py         # folded surface: arrangement→faces→heights→die  ← mesh
│   ├── tessellate.py       # TILE_SPECS + tessellate() — repeat a cell n×m
│   ├── diecut.py           # DSL graphs: import_obj of the foldcore die OBJs
│   └── exporter.py         # OBJ/SVG/JSON + DSL bake script → STL (Blender)
│
├── bpy_generated/
│   ├── import_mesh.py      # bpy: import the flat OBJ + tag a `fold_type` edge attr
│   └── build_debug.py      # bpy: lay out all molds + fold refs → debug_bellows.blend
│
└── output/                 # Created on demand by the exporters
    ├── stl/                # Print-ready molds (male / female) — NumPy, no Blender
    ├── obj/                # Flat line mesh for the Geometry Nodes preview
    ├── svg/                # Flat pattern reference
    ├── json/               # Full parametric description (params + every crease)
    └── debug_bellows.blend # Inspection scene (all molds + coloured fold refs)
```

---

## Pipeline

```
Python (patterns/*.py)
    → computes vertices and fold lines of the pattern developed flat
    → core/diecut.py builds male + female solids as Tanuki DSL IR graphs
       (ridges along mountain creases, channels = the negative + fabric offset)
    → core/exporter.py writes OBJ / SVG / JSON + a Blender (bpy) script

Blender (run the generated bpy script, then bake_and_export_stl)
    → the DSL graphs compile to Geometry Nodes and rebuild both plates
    → modifiers are applied and exported as STL male + STL female → print
    → bpy_generated/import_mesh.py + Geometry Nodes preview the collapse
```

---

## Generating the Diecut

Pattern generation, the DSL graphs and the OBJ/SVG/JSON run in **plain Python**;
the STL is baked in **Blender** from the DSL. From `src/`:

```python
from bellows_diecut import BellowsParams, generate_diecut, PATTERNS

params = BellowsParams(cell_scale=0.25)   # mm per template unit → tile size
for name in PATTERNS:    # ("yoshimura","miura","waterbomb","kresling","resch","accordion")
    result = generate_diecut(name, params, output_dir="output", bake=True)

result["pattern"]   # FoldPattern — one unit cell, mountain/valley classified
result["graphs"]    # {"male": IRGraph, "female": IRGraph} — Tanuki DSL
result["paths"]     # {"obj":…, "svg":…, "json":…, "bpy":…, "stl_male":…, "stl_female":…}
```

This writes `output/obj` / `output/svg` / `output/json` and a self-contained
`output/<pattern>_diecut.py` (the DSL compiled to a Blender script with a bake
footer). With `bake=True` and Blender on PATH it runs that script to produce
`output/stl/<pattern>_{male,female}.stl`.

### Baking manually / inspecting

Each `<pattern>_diecut.py` runs standalone (it embeds `sys.path` and a bake
footer):

```bash
blender --background --python output/yoshimura_diecut.py     # → output/stl/yoshimura_{male,female}.stl
blender --background --python bpy_generated/build_debug.py   # → output/debug_bellows.blend
```

---

## Diecut Geometry

The working surface is the **folded foldcore** of the pattern: every region
between fold lines becomes a flat tilted facet (mountains up, valleys down) — so
there are **no flat areas between edges**. Male and female are the **same folded
surface** offset by one fabric thickness (matched dies): the male is solid below
it, the female solid above `surface + material_thickness`. Pressed together they
form the cloth into the folded shape, creasing every fold line at once.

```
Foldcore cross-section (flat tilted facets, no flat regions):

  /\    /\    /\        each face = a flat tilted plane
 /  \  /  \  /  \       sharp crease on every fold line
M  V  M  V  M  V        mountains up · valleys down

  FEMALE  \/\/\/   solid above surface + material_thickness
  fabric   ~~~~
  MALE    /\/\/\   solid below the surface
```

How it is computed (`core/foldcore.py`, pure NumPy):

1. **arrangement** — split every fold segment at its crossings into a planar
   graph (vertices + classified edges);
2. **faces** — trace the bounded regions;
3. **heights** — `z = A·(n_mountain − n_valley)/(n_mountain + n_valley)` per
   vertex, with fold depth `A` from the tile size (override via `ridge_height`);
4. **triangulate** each face (low-tilt faces tented from a bumped centroid so no
   facet ends up horizontal);
5. **build_die** — thicken into a closed male/female solid → OBJ.

The OBJ is imported into the **Tanuki DSL** (`import_obj | realize_instances`)
and baked to STL in **Blender** — keeping the DSL → Blender flow while the folded
mesh itself is computed in Python.

---

## Parameters

In this single-cell phase a pattern is one tile. The relief is auto-sized from
the edge spacing; override `ridge_width` / `ridge_height` to pin a value.

```python
@dataclass
class BellowsParams:
    cell_scale: float          # mm per template unit — tile size, default 0.25
    material_thickness: float  # Fabric thickness (mm) — channel clearance / gap
    width_ratio: float         # ridge_width = width_ratio · edge_spacing (0.8)
    height_ratio: float        # ridge_height = height_ratio · ridge_width (0.5)
    ridge_width:  float | None # explicit override (mm); None ⇒ auto
    ridge_height: float | None # explicit override (mm); None ⇒ auto
    base_thickness: float      # floor under the deepest channel (mm), default 5.0
    margin: float              # Flat frame around the tile (mm), default 10.0
    pin_radius, pin_height     # Corner alignment pins (mm)
```

---

## Outputs

### STL male + STL female (primary output)

Two STL files ready to print, baked in Blender from the Tanuki DSL dies
(`generate_diecut(..., bake=True)`):

- `{pattern}_male.stl` — plate with triangular ridges on mountains, channels on valleys
- `{pattern}_female.stl` — the exact negative (ridges/channels swapped), with a
  fabric-thickness offset for clearance

### OBJ (Blender preview)

Pattern mesh developed in 3D with edges classified by fold type (valley / mountain / boundary) for use with Geometry Nodes.

### SVG (optional reference)

Flat pattern with differentiated fold lines — useful for verifying geometry before printing the diecut.

---

## Blender Usage

1. Generate the OBJ from Python (`generate_diecut(...)` → `output/obj/<pattern>.obj`)
2. In Blender, run `bpy_generated/import_mesh.py` (text editor, or
   `blender --background --python bpy_generated/import_mesh.py -- output/obj/<pattern>.obj`)
3. The flat pattern is imported as a line mesh with a per-edge integer attribute
   `fold_type` (0 = boundary, 1 = valley, 2 = mountain)
4. A Geometry Nodes tree can read `fold_type` to drive a collapse-preview slider
   and validate the geometry before printing

The SVG can also be loaded directly into Blender as a curve to extrude and preview the flat fabric layout.

---

## Dependencies

Pattern generation, the DSL die graphs and the OBJ/SVG/JSON exporters use only
the Python **standard library** plus the in-repo **Tanuki DSL**.

**Blender** (tested on **Blender 5.1**) is required to bake the STLs: the DSL
graphs compile to Geometry Nodes and the relief is realised with its boolean
solver using the bundled `bpy`.

---

## Fabric Materials

| Material | Heat-settable | Shape memory | Opacity | Notes |
|---|---|---|---|---|
| Black polyester organza | Yes (iron) | High | Medium | Needs lining or treatment |
| Black polyester taffeta | Yes (iron) | High | High | Primary candidate |
| Black TNT / Spunbond | Partial | Medium | High | Cheap, no fraying |
| Japanese paper (Washi) + shellac | No (treatment) | Very high | High when painted | Historical technique |
| IKEA Blackout fabric | No | Low | Total | Easy to source, not ideal for repeated folds |

---

## References

- Schenk, M. & Guest, S.D. — *Geometry of Miura-folded metamaterials*
- Filipov, E.T. et al. — *Origami tubes assembled into stiff, yet reconfigurable structures and metamaterials*
- Yoshimura, Y. — *On the Mechanism of Buckling of a Circular Cylindrical Shell*
- [Origami Simulator](https://origamisimulator.org/) — visual pattern reference
- [Robert Lang's TreeMaker / ReferenceFinder](https://langorigami.com/article/computational-origami/) — computational origami math

---

## Roller system

An alternative to the flat diecut plates: a pair of complementary **rollers** that
continuously stamp the fold pattern as the fabric is fed between them — better suited for
straight (non-conic) bellows and higher-volume runs where pressing individual flat pieces is
too slow.

Each roller is the tessellated foldcore relief **wrapped around a cylinder**. The
circumference carries an integer number of tiles (`around`), so the pattern meets itself
seamlessly at the wrap — the minimum is one bellows perimeter (`grid[0]`, see *Tile
Specifications*). The **male** roller carries the relief outward; the **female** is its
negative, so the two mesh like gears with the fabric in between. The solid is built by
bending the already-watertight flat foldcore die into a cylinder (`x` → wrap angle,
relief `z` → radius), so the result is closed by construction for every tiling rule.

```python
from bellows_diecut import generate_rollers

# male + female rollers; minimum tiles around for a seamless wrap
generate_rollers("kresling", "output", bake=True)   # → stl/kresling_roller_{male,female}.stl
```

`generate_rollers(name, output_dir, bake, around=None, length=None)` writes the roller OBJs,
a self-contained `<name>_roller_diecut.py` DSL bake script (each side imported via
`import_obj`), and — with `bake=True` and Blender on `PATH` — the STL pair.

### Parametric Geometry Nodes roller

For a **live, editable** roller in Blender there is a Geometry-Nodes version. The fold relief
(one minimal seamless tile block) is baked into a mesh; everything geometric — **arraying**
the block, **wrapping** it onto a cylinder (`θ = x·2π/circumference`, `r = radius + z·depth`),
and **solidifying** it (extrude inward by the wall) — is done in a `BellowsRoller` node group
whose inputs stay adjustable on the modifier:

| Input | Effect |
|---|---|
| Diameter (mm) | cylinder size the relief wraps onto |
| Tiles around / Tiles along | how many tile blocks wrap the circumference / run along the axis |
| Relief depth | relief height multiplier; **negative = female** (the meshing negative) |
| Core wall (mm) | bored-core wall thickness (extrude depth) |

```python
from bellows_diecut import generate_rollers_gn

generate_rollers_gn("yoshimura", "output")     # → output/yoshimura_roller_gn.py
# then in Blender:  blender -b -P output/yoshimura_roller_gn.py   (or open + Run Script)
```

Running the script creates `<name>_roller_male` and `<name>_roller_female` objects, each with
the editable `BellowsRoller` modifier. This version is an interactive **preview / design tool**:
arraying a single block can leave minor non-manifold seams between tiles, so for a watertight,
print-ready STL use the baked `generate_rollers` above (it tessellates the whole mesh at once).


## Configuration

Generation is driven by a small JSON config. Only a few knobs per pattern are exposed —
everything else (tiling rule, fabric gap, backing, roller wall) is computed automatically:

| Key | Meaning |
|---|---|
| `tile` | tile size `[X, Y]` in mm |
| `fold_height` | the mountain height (fold relief depth) in mm |
| `repeats` | how many tiles repeat **along the cylinder height** (axial) |
| `around` | how many tiles repeat **around the circumference** (horizontal); omit it to keep the pattern's automatic bellows-perimeter count |

```json
{
  "patterns": {
    "yoshimura": { "tile": [16, 16], "fold_height": 7.2, "repeats": 10, "around": 10 },
    "miura":     { "tile": [16, 17], "fold_height": 7.7, "repeats": 10, "around": 8 }
  }
}
```

```python
from bellows_diecut import (
    write_config_template, configure, generate_tessellation, generate_rollers, generate_all,
)

write_config_template("bellows_config.json")          # start from the defaults, then edit it

# either pass it to one generator …
generate_rollers("yoshimura", "output", config="bellows_config.json")
# … or apply it once for the whole session …
configure("bellows_config.json")
generate_tessellation("yoshimura", "output")
# … or generate dies + rollers + GN scripts for every pattern at once:
generate_all("output", config="bellows_config.json", bake=False)
```

Every generator (`generate_tessellation`, `generate_rollers`, `generate_diecut`,
`generate_rollers_gn`, `generate_all`) accepts `config=` (a path **or** a dict). A partial config
is merged over the defaults, so you only list the patterns/keys you want to change.





## Web UI

A dependency-free local site to adjust the knobs, preview the tile, and generate the output:

```bash
python -m bellows_diecut.web          # → http://127.0.0.1:8000/
#   --host  --port  --output <dir>   (defaults: 127.0.0.1, 8000, ./bellows_output)
#   --no-reload   disable the auto-restart-on-edit watcher
```

``` bash
PYTHONPATH=src python -m  bellows_diecut.web
```

The server **auto-reloads** on any edit to the package (it watches the source and restarts),
and responses are sent `Cache-Control: no-store`, so changes always take effect on a refresh —
no manual restart needed.

Pick a pattern and set **tile X/Y**, **fold height**, **tiles around (horizontal)** and
**repeats (height)** — tiles around defaults to the pattern's automatic count;
the preview updates live (a 3D foldcore view via three.js, or — offline — a 2D crease-pattern
fallback showing mountains solid and valleys dashed). **Generate rollers + output** writes the
tessellated dies, the male/female rollers and the parametric Geometry-Nodes script for that
pattern into the output directory, and lists the files written.

Tick **Bake STL with Blender** to also bake the print-ready STLs. The generation runs as a
background job (so the page stays responsive) and the server invokes Blender **headless**
(`blender --background`); the status polls until done and the produced `.stl` files are listed
in bold. This needs Blender on `PATH` — without it the job reports the error and the OBJ / SVG /
JSON / DSL / GN files are still written. Built on the Python standard library only (the 3D
preview pulls three.js from a CDN; everything else works offline).


## Fold Patterns — Unit Cells

Each pattern is defined by two types of edges developed flat:

- **Mountain** (solid line) — ridges extruded upward in the male diecut plate
- **Valley** (dashed line) — fold guides, cut as shallow channels in the male plate

### Yoshimura
One **diamond** (square rhombus) of a regular diamond grid. The four diagonal arms are mountains; two families of horizontal valley axes run through it — one along the diamond's **middle** (its horizontal diagonal, left↔right) and one through the **tip/tail junction** between rows. Folded, the diamonds pop in and out alternately (an egg-crate lattice).

### Miura
Two stacked V shapes forming a diapason/Y structure. Top lateral columns (E1, F1), central V arms (J, K), and lower central axis (G3) are mountain. Inner horizontal rows, mid columns, and lower diagonals are valley.

### Waterbomb
Two mirrored vertical trapezoids sharing the short edge at center. Full frame is valley. X crossing both trapezoids is mountain.

### Kresling (symmetric)
Two horizontally stacked parallelograms, mirrored vertically. All frame edges are mountain. The V formed by the two inner diagonals (one per parallelogram) is valley.

### Resch
Four small squares forming one large square, plus one additional small square attached to the right side. All frame edges are mountain. The X crossing the four inner squares is valley.

### Accordion
A trapezoidal corrugation of **horizontal rings** — each tile is one horizontal trapezoid (a flat crest flanked by two slants down to the tile edges). Tiled along Y the crests alternate up/down into an accordion wave, so one tile = one trapezoid ring and the **`repeats` (axial) count sets the number of rings**; `tiles around` just sets the diameter (the relief is constant around the circumference). The relief is built directly (flat crests, straight slants, troughs at `z = 0` on every ring edge), so the dies and rollers stay clean and the cylinder closes seamlessly into smooth, round bellows rings.

---

## Diecut Strategy

The fabrication pipeline works entirely in 2D developed flat:

```
1. Generate the pattern as a flat plane (Python)
       ↓
2. Classify all edges into two types:
   - MOUNTAIN edges → extrude upward → form ridges on the male plate
   - VALLEY edges   → cut as shallow channels → guide folds on fabric
       ↓
3. Export two STL plates:
   - male:   base plate + mountain ridges extruded up
   - female: exact negative of male + fabric thickness offset
       ↓
4. Print both plates, press fabric between them
       ↓
5. Close fabric into cylinder with a straight seam
```

The key insight is that **valley and mountain are the same geometry** — the difference is only which direction they face relative to the fabric. The male plate encodes both by extruding mountains upward; the female mirrors them as channels.

---

## Tessellated Patterns

Each unit cell tiles into a repeating surface. The same diecut logic applies at any scale — the plate simply contains more repetitions of the unit cell.

### Yoshimura tessellated

A regular **square grid of diamonds** (no brick/interlock offset). Each diamond folds along its horizontal middle axis and tip/tail axis; alternate diamonds pop in and out, giving an egg-crate diamond relief.

### Miura tessellated

Offset rows of chevrons. The diapason structure repeats horizontally and vertically, alternating which V arms are mountain and which are valley per row.

### Waterbomb tessellated

Grid of X shapes. Each cell shares its trapezoid frame edges with neighbors — shared edges resolve to valley, X diagonals remain mountain throughout.

### Kresling tessellated

Staggered parallelogram rows with continuous V diagonals running across the full surface. The V pattern produces the characteristic spiral feel of the Kresling cylinder.

### Resch tessellated

Square grid with offset single squares attached alternately left and right. The X pattern repeats across the large squares; the attached small squares create the characteristic asymmetric tabs of the Resch pattern.

![All patterns](./all_patterns_final.svg)

# Tile Specifications — 35mm Bellows

## Base Parameters

| Parameter | Value |
|---|---|
| Bellows section | 32 × 32 mm |
| Flat development | 128 × 175 mm |
| Target extension | 50 mm |
| Print bed | 170 × 170 mm |
| Fabric thickness | 0.5 mm |
| Press tolerance | 0.3 mm |

---

## Tile Specs per Pattern

| Pattern | Tile X × Y (mm) | Tile Z — ridge (mm) | Grid n×m | Total tiles | Area covered (mm) | Resulting folds |
|---|---|---|---|---|---|---|
| Yoshimura | 16 × 14 | 3.5 | 8 × 12 | 96 | 128 × 168 | 12 folds / 24 half-ridges |
| Miura | 16 × 18 | 3.0 | 8 × 10 | 80 | 128 × 180 ⚠️ | 10 folds / 20 faces |
| Waterbomb | 16 × 16 | 4.0 | 8 × 11 | 88 | 128 × 176 ⚠️ | 11 folds / 22 faces |
| Kresling | 18 × 12 | 3.0 | 7 × 14 | 98 | 126 × 168 | 14 folds / 28 faces |
| Resch | 20 × 10 | 3.5 | 6 × 17 | 102 | 120 × 170 ⚠️ | 17 folds / 34 faces |

> ⚠️ Area exceeds 170mm in one axis — reduce tile Y by 1–2mm or drop one row.

### Adjusted for 170×170 bed

| Pattern | Tile X × Y (mm) | Grid n×m | Total tiles | Area covered (mm) |
|---|---|---|---|---|
| Yoshimura | 16 × 14 | 8 × 12 | 96 | 128 × 168 ✅ |
| Miura | 16 × 17 | 8 × 10 | 80 | 128 × 170 ✅ |
| Waterbomb | 16 × 15 | 8 × 11 | 88 | 128 × 165 ✅ |
| Kresling | 18 × 12 | 7 × 14 | 98 | 126 × 168 ✅ |
| Resch | 20 × 10 | 6 × 17 | 102 | 120 × 170 ✅ |

These specs are encoded in `core.tessellate.TILE_SPECS`.  Generate the print-ready
tessellated dies (folded foldcore, fold depth `Z = tile_Y/2 − 0.8`):

```python
from bellows_diecut import generate_tessellation, PATTERNS

for name in PATTERNS:
    generate_tessellation(name, output_dir="output", bake=True)   # needs Blender
    # → output/stl/<name>_tile_{male,female}.stl  (fits the 170×170 bed)

# Override the table per call:
generate_tessellation("miura", "output", bake=True, tile=(16, 17), grid=(8, 10))
```

Each pattern repeats with its own rule (`TILE_SPECS[...]["tiling"]`):

| Pattern | Tiling | How it repeats |
|---|---|---|
| Resch, Waterbomb, Accordion | `square` | plain grid (shift one tile each way) |
| Yoshimura | `square` | regular grid of diamonds — each diamond folds along its horizontal middle and tip/tail axes, alternate diamonds pop in/out |
| Miura | `brick` | alternate rows shift ½ tile — a row's tile **corners** land on the next row's tile **centres** (running bond) |
| Kresling | `square` + V-interlock | the V notch receives the next tile's tip (`pitch_x = 260/300`), shrinking the effective width |

The Miura brick widens the field by ½ tile; the Kresling V-interlock
shrinks it (cells share edges) — all still fit the bed.

---

## Z Calculation

```
Z = (fold_pitch / 2) - fabric_thickness - press_tolerance
  = (tile_Y / 2) - 0.5 - 0.3
  = (tile_Y / 2) - 0.8
```

| Pattern | tile_Y (mm) | Z (mm) |
|---|---|---|
| Yoshimura | 14 | 6.2 |
| Miura | 17 | 7.7 |
| Waterbomb | 15 | 6.7 |
| Kresling | 12 | 5.2 |
| Resch | 10 | 4.2 |

---

## Fabrication Notes

| Pattern | Fits 170×170 | Notes |
|---|---|---|
| Yoshimura | ✅ | Most historically proven in photographic bellows. Straightforward tiling. |
| Miura | ✅ | Lower Z — double-V geometry needs less ridge depth. Adjust tile_Y to 17mm. |
| Waterbomb | ✅ | Highest Z — X ridge marks fabric in two directions simultaneously. Reduce tile_Y to 15mm. |
| Kresling | ✅ | Shear reduces effective width — verify edge tiles don't overlap when tessellating. |
| Resch | ✅ | Asymmetric tile (4sq + tab) — check tiling at development edges; tab alternates L/R. |

---

## Collapse Ratio by Pattern

| Pattern | Fold factor | Extended (mm) | Collapsed (mm) |
|---|---|---|---|
| Yoshimura | 3.5× | 50 | ~14 |
| Miura | 3.0× | 50 | ~17 |
| Waterbomb | 3.5× | 50 | ~15 |
| Kresling | 3.0× | 50 | ~12 |
| Resch | 2.5× | 50 | ~20 |

## Patterns Progress

* [x] Accordion — trapezoidal corrugation
* [x] Yoshimura — diamond grid
* [x] Kresling — stacked parallelograms + inner V
* [ ] Miura — V-shaped chevrons **Wrong repetition direction**
* [ ] Waterbomb — mirrored trapezoids **Wrong tile pattern**
* [ ] Resch — 2×2 squares + attached square + X **Wrong tile pattern**
