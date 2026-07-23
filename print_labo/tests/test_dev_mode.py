from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from print_labo.utils.compile_cli import build_compile_parser
from print_labo.utils.dev_mode import BLENDER_CLIENT, _snapshot


def test_build_compile_parser():
    parser = build_compile_parser(description="Compile lamp parts")
    args = parser.parse_args(["--development", "--mode", "individual", "--output", "lamp.py", "--watch", "src"])

    assert args.development is True
    assert args.mode == "individual"
    assert args.output == "lamp.py"
    assert args.watch == ["src"]


def test_blender_client_is_self_contained_and_uses_local_server():
    client = BLENDER_CLIENT.format(url="http://127.0.0.1:9999/artifact")
    assert "import bpy" in client
    assert "urllib.request" in client
    assert "from print_labo" not in client
    assert "tanuki" not in client


def test_snapshot_detects_source_changes(tmp_path):
    watch_dir = tmp_path / "watch"
    watch_dir.mkdir()
    source = watch_dir / "source.py"
    source.write_text("x = 1")
    assert _snapshot([watch_dir]) == {source: source.stat().st_mtime_ns}
