# halo_maps/bootstrap.py

from pathlib import Path
import site

def enable_venv():
    root = Path(__file__).resolve().parents[2]

    site_packages = next(
        (root / ".venv" / "lib").glob("python*/site-packages")
    )

    site.addsitedir(str(site_packages))