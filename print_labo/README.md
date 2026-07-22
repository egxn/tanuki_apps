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
