from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

from .dev_mode import run_dev_mode


def build_compile_parser(*, description: str = "Compile project parts") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--mode", choices=["combined", "individual"], default="combined")
    parser.add_argument("--output", default=None)
    parser.add_argument("--development", action="store_true", help="Compile, open Blender, and reload it after saves")
    parser.add_argument("--watch", nargs="*", default=None, help="Paths to watch for development mode")
    parser.add_argument("--blender", default=None, help="Blender executable (defaults to BLENDER_BIN, BLENDER_EXE, or blender)")
    return parser


def run_compile_cli(
    *,
    graphs: Sequence[object],
    description: str,
    source_script: str | Path | None = None,
    output_path: str | Path | None = None,
    default_output: str | Path | None = None,
    default_output_dir: str | Path | None = None,
    export_combined: Callable[[Sequence[object], str | Path], object] | None = None,
    export_individual: Callable[[Sequence[object], str | Path], object] | None = None,
    watch_base_dir: str | Path | None = None,
    print_label: str | None = None,
) -> None:
    parser = build_compile_parser(description=description)
    args = parser.parse_args()

    resolved_source_script = Path(source_script or Path.cwd()).resolve() if source_script is not None else None
    if resolved_source_script is None:
        resolved_source_script = Path(__file__).resolve()

    resolved_watch_base_dir = Path(watch_base_dir or resolved_source_script.parent).resolve()

    if export_combined is None:
        from tanuki.dsl.export import combined_export

        export_combined = combined_export
    if export_individual is None:
        from tanuki.dsl.export import individual_export

        export_individual = individual_export
    if args.mode == "combined":
        out = Path(args.output or default_output or "output.py")
        if args.development:
            # A fresh child process is essential here.  ``graphs`` was built
            # while this CLI process started, so exporting it again would not
            # include edits saved later in the source module.
            def compile_from_source() -> Path:
                command = [
                    sys.executable,
                    str(resolved_source_script),
                    "--mode",
                    "combined",
                    "--output",
                    str(out.resolve()),
                ]
                subprocess.run(command, check=True)
                return out.resolve()

            run_dev_mode(
                compile_once=compile_from_source,
                output_script=out,
                watch_paths=args.watch or [resolved_watch_base_dir],
                blender_executable=args.blender,
            )
            return
        else:
            if export_combined is None:
                raise ValueError("Combined export handler is required")
            path = export_combined(graphs, out)
        label = print_label or "Generated"
        print(f"{label} {len(graphs)} parts in {path} ({path.stat().st_size // 1024} KB)")
    else:
        out = Path(args.output or default_output_dir or "output")
        if args.development:
            parser.error("--development currently supports --mode combined only")
        else:
            if export_individual is None:
                raise ValueError("Individual export handler is required")
            written = export_individual(graphs, out)
        label = print_label or "Generated"
        print(f"{label} {len(written)} files in {out}/")
