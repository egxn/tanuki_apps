"""Development bridge between the project Python environment and Blender.

The compiler and file watcher deliberately run *outside* Blender.  Blender only
runs the exported Python text it obtains from the local HTTP server, so it does
not need Tanuki or any of this project's dependencies installed.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterable


BLENDER_CLIENT = '''# This file is intentionally self-contained: Blender needs no project packages.
import base64
import json
import traceback
import urllib.request

URL = {url!r}
last_revision = -1

def poll_print_labo():
    global last_revision
    try:
        with urllib.request.urlopen(URL, timeout=0.5) as response:
            artifact = json.loads(response.read().decode("utf-8"))
        revision = artifact.get("revision", -1)
        if revision != last_revision and artifact.get("script"):
            source = base64.b64decode(artifact["script"]).decode("utf-8")
            namespace = {{"__name__": "__main__", "__file__": artifact.get("filename", "generated.py")}}
            exec(compile(source, namespace["__file__"], "exec"), namespace, namespace)
            last_revision = revision
            print("Print Labo: loaded revision", revision)
    except Exception:
        traceback.print_exc()
    return 0.5

import bpy
bpy.app.timers.register(poll_print_labo, first_interval=0.1, persistent=True)
print("Print Labo: connected to", URL)
'''


def _snapshot(paths: Iterable[Path], *, exclude: Iterable[Path] = ()) -> dict[Path, int]:
    """Return nanosecond mtimes for Python source files below *paths*."""
    result: dict[Path, int] = {}
    excluded = {path.resolve() for path in exclude}
    for path in paths:
        candidates = path.rglob("*.py") if path.is_dir() else (path,)
        for candidate in candidates:
            try:
                if candidate.is_file() and candidate.resolve() not in excluded:
                    result[candidate] = candidate.stat().st_mtime_ns
            except FileNotFoundError:
                pass
    return result


class _ArtifactServer(ThreadingHTTPServer):
    artifact: dict[str, object]


class _ArtifactHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path != "/artifact":
            self.send_error(404)
            return
        body = json.dumps(self.server.artifact).encode("utf-8")  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def run_dev_mode(
    *,
    compile_once: Callable[[], Path],
    output_script: str | os.PathLike[str],
    watch_paths: Iterable[str | os.PathLike[str]],
    blender_executable: str | None = None,
    poll_interval: float = 0.5,
) -> None:
    """Compile, open Blender, then keep Blender updated until interrupted.

    ``compile_once`` must run in the caller's Python environment.  It is never
    invoked by Blender, which is the important boundary for Tanuki dependencies.
    """
    output = Path(output_script).resolve()
    watched = [Path(path).resolve() for path in watch_paths]
    blender = (
        blender_executable
        or os.environ.get("BLENDER_BIN")
        or os.environ.get("BLENDER_EXE")
        or "blender"
    )

    generated = compile_once()
    if generated.resolve() != output:
        output = generated.resolve()
    script = output.read_text(encoding="utf-8")

    server = _ArtifactServer(("127.0.0.1", 0), _ArtifactHandler)
    server.artifact = {
        "revision": 1,
        "filename": str(output),
        "script": base64.b64encode(script.encode("utf-8")).decode("ascii"),
    }
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/artifact"

    client_file = tempfile.NamedTemporaryFile("w", suffix="_print_labo_client.py", delete=False, encoding="utf-8")
    try:
        client_file.write(BLENDER_CLIENT.format(url=url))
        client_file.close()
        try:
            subprocess.Popen([blender, "--python", client_file.name])
        except FileNotFoundError as exc:
            raise RuntimeError(f"Blender executable not found: {blender}") from exc

        print(f"Development mode: serving {output} at {url}")
        print(f"Development mode: watching {', '.join(map(str, watched))}; press Ctrl-C to stop")
        previous = _snapshot(watched, exclude=[output])
        while True:
            time.sleep(poll_interval)
            current = _snapshot(watched, exclude=[output])
            if current == previous:
                continue
            previous = current
            try:
                generated = compile_once().resolve()
                source = generated.read_text(encoding="utf-8")
                server.artifact = {
                    "revision": int(server.artifact["revision"]) + 1,
                    "filename": str(generated),
                    "script": base64.b64encode(source.encode("utf-8")).decode("ascii"),
                }
                print(f"Development mode: rebuilt {generated}")
            except Exception as exc:
                # Keep the previous artifact active in Blender after a bad save.
                print(f"Development mode: compilation failed; Blender keeps the previous revision\n{exc}")
    except KeyboardInterrupt:
        print("Development mode: stopped")
    finally:
        server.shutdown()
        server.server_close()
        try:
            Path(client_file.name).unlink(missing_ok=True)
        except OSError:
            pass


# Kept as a compatibility import for callers of earlier experimental versions.
install_dev_mode = run_dev_mode
