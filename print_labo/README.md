# Print Labo

Small collection of printable utility parts generated from Tanuki DSL scripts.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e ../../tanuki/
pip install -e ".[dev]"
```

If you want to run the scripts from the project root, also set the source path:

```bash
export PYTHONPATH=src
```

---

## Generate meshes

Run any generator script from the `src/print_labo/misc_prints` folder:

```bash
python src/print_labo/misc_prints/02_tube_cap.py --mode combined --output output.py
```

Or generate separate files:

```bash
python src/print_labo/misc_prints/02_tube_cap.py --mode individual --output output
```

You can replace `02_tube_cap.py` with any other script such as `01_dev_tank.py`, `03_spinner.py`, `04_mold.py`, `05_strap.py`, `bellows_cog.py`, `cat_litter.py`, `dslr_scanner_setup.py`, `film_spooler.py`, `lamp_parts.py`, `lens_machine.py`, `minolta_tap.py`, `mogura_exposimeter.py`, `neganuki_scanner.py`, `trap_light.py`, `tray.py`, or `tube_ext.py`.

---

## Development mode

Development mode runs the compiler and watcher in your normal project Python environment. Blender receives only the already-generated Python through a local (`127.0.0.1`) server, so Blender does **not** need Tanuki or this project's libraries installed.

You can enable automatic rebuild + reload by compiling in development mode:

```bash
python src/print_labo/misc_prints/00_lamp.py --development --mode combined --output output.py --watch src/print_labo/misc_prints
```

This command stays running until `Ctrl-C` and will:

- compile the Geometry Nodes Python script once;
- start Blender and load it;
- watch the configured paths for changes and rebuild automatically after each save;
- send each successful rebuild to that same Blender session;
- keep the last successful output available if a compilation fails.

Development mode currently targets the combined export, which is the single script Blender reloads.

If `blender` is not in your `PATH`, pass its executable explicitly with `--blender /path/to/blender`, or set `BLENDER_BIN` (also supports `BLENDER_EXE`).

You can reuse the same pattern for other generator scripts by passing the same flags to the corresponding entry point.
