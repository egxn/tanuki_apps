"""Bellows Diecut — exporters.

Four output formats, matching the project README:

* **bpy script** (``export_bpy_script``) — the male+female diecut graphs compiled
  to a standalone Blender Python file.  Running it in Blender rebuilds both
  solids; the STL bake (``bake_and_export_stl`` here, run *inside* Blender) then
  writes the print-ready meshes.
* **OBJ** (``export_obj``) — the flat pattern as a line mesh with edges grouped
  by fold type, for the Geometry Nodes collapse preview.
* **SVG** (``export_svg``) — the flat crease reference, mountains/valleys/outline
  drawn distinctly, to eyeball the geometry before printing.
* **JSON** (``export_json``) — the full parametric description (params + every
  crease) for tooling and reproducibility.

The OBJ/SVG/JSON writers are pure Python.  ``export_bpy_script`` only needs the
Tanuki compiler (no Blender).  ``bake_and_export_stl`` is the one function that
must run inside Blender.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.sax.saxutils import escape

from tanuki.ir.graph import IRGraph
from tanuki.dsl.export import combined_export

from ..parameters import BellowsParams
from .geometry import FoldPattern, FoldType

#: SVG stroke styling per fold type — (stroke colour, dash array, width).
_SVG_STYLE = {
    FoldType.MOUNTAIN: ("#d62728", "none", 0.6),    # red solid
    FoldType.VALLEY:   ("#1f77b4", "2,1.5", 0.6),   # blue dashed
    FoldType.BOUNDARY: ("#000000", "none", 0.8),    # black solid
}

#: Repository source root (the directory that contains the ``tanuki`` package).
#: Embedded into generated scripts so Blender can ``import tanuki`` standalone.
_SRC_ROOT = Path(__file__).resolve().parents[4]


# ---------------------------------------------------------------------------
# Blender script (→ STL via Blender)
# ---------------------------------------------------------------------------

def export_bpy_script(
    graphs: dict[str, IRGraph],
    path: str | Path,
    with_stl_bake: bool = True,
) -> Path:
    """Compile the male/female graphs into one self-contained Blender ``.py``.

    The file defines ``setup_<name>_male()`` / ``setup_<name>_female()`` and
    calls each, so running it rebuilds both diecut solids::

        blender --background --python <file>

    Two conveniences are injected so it runs with no manual setup:

    * a ``sys.path`` line pointing at the repo source root, so ``import tanuki``
      works inside Blender's bundled Python;
    * when *with_stl_bake* is true, a footer that bakes each solid to
      ``<script_dir>/stl/<name>.stl`` via :func:`bake_and_export_stl`.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [graphs[k] for k in ("male", "female") if k in graphs]
    combined_export(ordered, path)

    base = path.read_text()

    # PATH line — insert right after the leading ``import bpy``.
    header = f'import sys\nsys.path.insert(0, r"{_SRC_ROOT}")\n'
    if base.startswith("import bpy"):
        first, _, rest = base.partition("\n")
        base = f"{first}\n{header}{rest}"
    else:  # defensive — combined_export always starts with ``import bpy``
        base = f"import bpy\n{header}{base}"

    if with_stl_bake:
        names = [g.name for g in ordered]
        footer = [
            "",
            "# --- Bake the Geometry Nodes solids to STL "
            "(written next to this script) ---",
            "import os",
            "from bellows_diecut.core.exporter import bake_and_export_stl",
            '_stl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stl")',
        ]
        for n in names:
            footer.append(
                f"bake_and_export_stl({n!r}, os.path.join(_stl_dir, {n + '.stl'!r}))"
            )
        base = base.rstrip() + "\n" + "\n".join(footer) + "\n"

    path.write_text(base)
    return path


def bake_and_export_stl(object_name: str, path: str | Path) -> str:
    """Apply *object_name*'s Geometry Nodes modifier and write an STL.

    Run **inside Blender** after executing the generated bpy script.  Returns
    the absolute path written.
    """
    import bpy  # imported lazily — only available inside Blender

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    obj = bpy.data.objects.get(object_name)
    if obj is None:
        raise ValueError(f"Object {object_name!r} not found in the scene.")

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    for mod in list(obj.modifiers):
        if mod.type == "NODES":
            bpy.ops.object.modifier_apply(modifier=mod.name)

    # STL operator moved across Blender versions: 4.1+ ships ``wm.stl_export``,
    # older builds use the legacy ``export_mesh.stl`` add-on operator.
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(
            filepath=str(path), export_selected_objects=True, ascii_format=False
        )
    else:  # pragma: no cover - legacy Blender < 4.1
        bpy.ops.export_mesh.stl(
            filepath=str(path), use_selection=True, ascii=False
        )
    return str(path.resolve())


# ---------------------------------------------------------------------------
# OBJ (flat line mesh, grouped by fold type)
# ---------------------------------------------------------------------------

def export_obj(pattern: FoldPattern, path: str | Path) -> Path:
    """Write the flat pattern as an OBJ line mesh grouped by fold type."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Deduplicate endpoints into a shared vertex list (1-based OBJ indices).
    index: dict[tuple[float, float], int] = {}
    verts: list[tuple[float, float]] = []

    def vid(p: tuple[float, float]) -> int:
        key = (round(p[0], 5), round(p[1], 5))
        if key not in index:
            verts.append(key)
            index[key] = len(verts)
        return index[key]

    groups: dict[str, list[tuple[int, int]]] = {"mountain": [], "valley": [], "boundary": []}
    for fl in pattern.fold_lines:
        groups[fl.kind.value].append((vid(fl.p0), vid(fl.p1)))

    lines = [f"# Bellows Diecut flat pattern: {pattern.name}",
             f"# width={pattern.width:.3f} height={pattern.height:.3f} (mm)"]
    for x, y in verts:
        lines.append(f"v {x:.5f} {y:.5f} 0.0")
    for name, edges in groups.items():
        if not edges:
            continue
        lines.append(f"g {name}")
        for a, b in edges:
            lines.append(f"l {a} {b}")

    path.write_text("\n".join(lines) + "\n")
    return path


# ---------------------------------------------------------------------------
# SVG (flat crease reference)
# ---------------------------------------------------------------------------

def export_svg(pattern: FoldPattern, path: str | Path, padding: float = 5.0) -> Path:
    """Write the flat crease pattern as an SVG (mm units, Y flipped for view)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    w = pattern.width + 2 * padding
    h = pattern.height + 2 * padding

    def fy(y: float) -> float:
        # Flip Y so the pattern reads bottom-up in typical SVG viewers.
        return h - (y + padding)

    def fx(x: float) -> float:
        return x + padding

    body: list[str] = []
    # Draw boundary last so creases sit under the outline.
    order = [FoldType.VALLEY, FoldType.MOUNTAIN, FoldType.BOUNDARY]
    for kind in order:
        colour, dash, width = _SVG_STYLE[kind]
        dash_attr = "" if dash == "none" else f' stroke-dasharray="{dash}"'
        for fl in pattern.lines_of(kind):
            x1, y1 = fx(fl.p0[0]), fy(fl.p0[1])
            x2, y2 = fx(fl.p1[0]), fy(fl.p1[1])
            body.append(
                f'  <line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
                f'stroke="{colour}" stroke-width="{width}"{dash_attr} />'
            )

    title = escape(f"{pattern.name} bellows pattern")
    svg = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.2f}mm" '
        f'height="{h:.2f}mm" viewBox="0 0 {w:.3f} {h:.3f}">',
        f"  <title>{title}</title>",
        f'  <rect x="0" y="0" width="{w:.3f}" height="{h:.3f}" fill="white" />',
        *body,
        "</svg>",
    ]
    path.write_text("\n".join(svg) + "\n")
    return path


# ---------------------------------------------------------------------------
# JSON (full parametric description)
# ---------------------------------------------------------------------------

def export_json(
    pattern: FoldPattern, params: BellowsParams, path: str | Path
) -> Path:
    """Write params + every crease to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "pattern": pattern.name,
        "parameters": params.to_dict(),
        "developed": {"width": pattern.width, "height": pattern.height,
                      "seam": pattern.seam},
        "summary": pattern.summary(),
        "fold_lines": [
            {"p0": list(fl.p0), "p1": list(fl.p1), "kind": fl.kind.value}
            for fl in pattern.fold_lines
        ],
    }
    path.write_text(json.dumps(data, indent=2))
    return path


# ---------------------------------------------------------------------------
# Convenience: everything at once
# ---------------------------------------------------------------------------

def bake_molds(
    script_path: str | Path, blender_bin: str = "blender",
) -> dict[str, Path]:
    """Run Blender headless on a generated diecut script to bake the STLs.

    Executes ``blender --background --python <script>`` (the script's footer
    calls :func:`bake_and_export_stl` for each plate, writing
    ``<script_dir>/stl/<name>_{male,female}.stl``).  Returns the STL paths that
    were produced.  If Blender is not found on PATH, a ``RuntimeError`` is raised
    so callers can fall back to just shipping the script.
    """
    import shutil
    import subprocess

    script_path = Path(script_path)
    exe = shutil.which(blender_bin) or blender_bin
    if shutil.which(blender_bin) is None and not Path(blender_bin).exists():
        raise RuntimeError(
            f"Blender executable {blender_bin!r} not found — cannot bake STL. "
            f"Run `{blender_bin} --background --python {script_path}` manually."
        )
    subprocess.run([exe, "--background", "--python", str(script_path)],
                   check=True, capture_output=True)
    stl_dir = script_path.parent / "stl"
    name = script_path.stem.replace("_diecut", "")
    return {
        f"stl_{side}": stl_dir / f"{name}_{side}.stl"
        for side in ("male", "female")
        if (stl_dir / f"{name}_{side}.stl").exists()
    }


def export_all(
    pattern: FoldPattern,
    params: BellowsParams,
    output_dir: str | Path,
    graphs: dict[str, IRGraph] | None = None,
    bake: bool = False,
    blender_bin: str = "blender",
) -> dict[str, Path]:
    """Write the flat OBJ/SVG/JSON and the self-contained DSL bake script.

    The molds are produced by the **Tanuki DSL → Blender**: ``graphs`` are
    compiled into ``<name>_diecut.py`` (with a footer that bakes both STLs).
    When *bake* is true and Blender is available, that script is run so the STLs
    land in ``output/stl/``.  Returns a mapping of output kind → written path.
    """
    output_dir = Path(output_dir)
    name = pattern.name
    out: dict[str, Path] = {
        "obj": export_obj(pattern, output_dir / "obj" / f"{name}.obj"),
        "svg": export_svg(pattern, output_dir / "svg" / f"{name}.svg"),
        "json": export_json(pattern, params, output_dir / "json" / f"{name}.json"),
    }
    if graphs:
        script = export_bpy_script(
            graphs, output_dir / f"{name}_diecut.py", with_stl_bake=True
        )
        out["bpy"] = script
        if bake:
            out.update(bake_molds(script, blender_bin))
    return out


__all__ = [
    "export_bpy_script",
    "bake_and_export_stl",
    "bake_molds",
    "export_obj",
    "export_svg",
    "export_json",
    "export_all",
]
