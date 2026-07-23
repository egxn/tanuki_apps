"""``python -m bellows_diecut.web`` — launch the web UI.

Options: ``--host`` (default 127.0.0.1), ``--port`` (default 8000),
``--output`` (default the package ``output/`` dir, so there's a single output
location regardless of where you launch from), ``--no-reload``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .server import DEFAULT_OUTPUT, run


def main() -> None:
    ap = argparse.ArgumentParser(description="Bellows Diecut web UI")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT),
                    help="directory for generated output files")
    ap.add_argument("--no-reload", action="store_true",
                    help="disable auto-restart when the source changes")
    args = ap.parse_args()
    run(host=args.host, port=args.port, output_dir=args.output,
        reload=not args.no_reload)


if __name__ == "__main__":
    main()
