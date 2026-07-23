"""Stdlib HTTP server backing the Bellows Diecut web UI.

Endpoints
---------
``GET  /``              the single-page UI (HTML below).
``GET  /api/patterns``  the pattern list + each pattern's current config.
``GET  /api/tile``      foldcore preview mesh for the given knobs (JSON).
``POST /api/generate``  apply the knobs and write the full output for a pattern.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .. import (
    PATTERNS, config, generate_tessellation, generate_rollers,
    generate_rollers_gn,
)
from ..parameters import BellowsParams
from ..core import tessellate, foldcore

#: Single canonical output directory (the package ``output/``), so the web UI
#: writes to one place regardless of the launch directory.
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "output"

#: Background generate/bake jobs: id → {status, files, dir, error, baked}.
_JOBS: dict[str, dict] = {}
_GEN_LOCK = threading.Lock()        # serialise generation (config is global state)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _around(name: str) -> int:
    """Auto circumference tile count (the bellows perimeter — fixed per pattern)."""
    return tessellate.TILE_SPECS[name]["grid"][0]


def preview_mesh(name: str, tile_x: float, tile_y: float, fold_height: float,
                 repeats: int = 3, around: int | None = None) -> dict:
    """Foldcore preview of a small patch: 3D mesh + flat crease lines + bbox.

    ``around`` (horizontal/circumference) and ``repeats`` (axial) are reflected —
    capped — so changing either visibly changes the preview.  For the accordion
    they are **trapezoid counts** (``= grid × units-per-tile``), so they are
    converted back to a grid here too.
    """
    from .. import config
    ux, uy = config._UNITS_PER_TILE.get(name, (1, 1))
    around_tiles = (_around(name) if around is None else max(1, round(int(around) / ux)))
    along = max(1, min(max(1, round(int(repeats) / uy)), 8))
    a = min(around_tiles, 6)
    pat = tessellate.tessellate(name, tile=(tile_x, tile_y), grid=(max(1, a), along))
    params = BellowsParams(
        material_thickness=tessellate.FABRIC_THICKNESS,
        ridge_height=float(fold_height),
        base_thickness=tessellate.BASE_THICKNESS,
    )
    pts, z, tris, _b = foldcore.build_surface(pat, params)
    positions = []
    for (x, y), zz in zip(pts, z):
        positions += [float(x), float(zz), float(y)]      # y-up for three.js
    indices = [int(i) for t in tris for i in t]
    lines = {
        "mountain": [[fl.p0[0], fl.p0[1], fl.p1[0], fl.p1[1]] for fl in pat.mountains],
        "valley": [[fl.p0[0], fl.p0[1], fl.p1[0], fl.p1[1]] for fl in pat.valleys],
    }
    x0, y0, x1, y1 = pat.bounds()
    return {"positions": positions, "indices": indices,
            "lines": lines, "bbox": [x0, y0, x1, y1]}


def _pattern_config() -> dict:
    cfg = config.current()["patterns"]
    return {n: cfg[n] for n in PATTERNS}


def _run_generation(job_id: str, body: dict, out_root: Path) -> None:
    """Worker: apply the knobs and generate (optionally bake STLs with Blender)."""
    job = _JOBS[job_id]
    try:
        name = body["pattern"]
        bake = bool(body.get("bake", False))
        pat_cfg = {
            "tile": [float(body["tile_x"]), float(body["tile_y"])],
            "fold_height": float(body["fold_height"]),
            "repeats": int(body["repeats"]),
        }
        around = body.get("around")
        if around not in (None, "", "auto") and int(float(around)) > 0:
            pat_cfg["around"] = int(float(around))   # blank/0 → keep auto count
        cfg = {"patterns": {name: pat_cfg}}
        with _GEN_LOCK:                       # TILE_SPECS is global; one at a time
            try:
                config.apply_config(cfg)
                spec = tessellate.TILE_SPECS[name]      # effective (incl. auto around)
                ux, uy = config._UNITS_PER_TILE.get(name, (1, 1))
                effective = {"tile": list(spec["tile"]),
                             "fold_height": spec.get("fold_height"),
                             "around": spec["grid"][0] * ux,
                             "repeats": spec["grid"][1] * uy}
                # OBJ/SVG/JSON/DSL always; STL written natively (no Blender needed)
                generate_tessellation(name, out_root, bake=False)
                generate_rollers(name, out_root, bake=False)
                generate_rollers_gn(name, out_root)
                if bake:
                    from ..core import roller as _roller
                    stl_dir = out_root / "stl"
                    stl_dir.mkdir(parents=True, exist_ok=True)
                    a_tiles = spec["grid"][0]
                    m_tiles = spec["grid"][1]
                    for _side in ("male", "female"):
                        _roller.export_roller_stl(
                            name,
                            stl_dir / f"{name}_roller_{_side}.stl",
                            side=_side, around=a_tiles, length=m_tiles,
                        )
            finally:
                config.reset()                # never leak this run's config globally
        files = sorted(str(p.relative_to(out_root))
                       for p in out_root.rglob("*")
                       if p.is_file() and name in p.name)
        job.update(status="done", files=files, dir=str(out_root.resolve()),
                   pattern=name, params=effective,
                   baked=bake and any(f.endswith(".stl") for f in files))
    except Exception as exc:                  # surface (e.g. Blender missing)
        job.update(status="error", error=str(exc))


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

def make_app(output_dir: str | Path = DEFAULT_OUTPUT):
    out_root = Path(output_dir)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):           # quiet by default
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")   # never serve a stale page
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj))

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                return self._send(200, INDEX_HTML, "text/html; charset=utf-8")
            if url.path == "/api/patterns":
                return self._json(200, {"patterns": list(PATTERNS),
                                        "config": _pattern_config()})
            if url.path == "/api/tile":
                q = parse_qs(url.query)
                try:
                    name = q.get("pattern", ["yoshimura"])[0]
                    tx = float(q.get("tile_x", ["16"])[0])
                    ty = float(q.get("tile_y", ["16"])[0])
                    fold = float(q.get("fold_height", ["6"])[0])
                    rep = int(float(q.get("repeats", ["3"])[0]))
                    aro = q.get("around", [""])[0]
                    aro = int(float(aro)) if aro not in ("", "auto") else None
                    if aro is not None and aro <= 0:       # blank/0 → auto
                        aro = None
                    return self._json(200, preview_mesh(name, tx, ty, fold, rep, aro))
                except Exception as exc:               # surface errors to the UI
                    return self._json(400, {"error": str(exc)})
            if url.path.startswith("/api/job/"):
                job = _JOBS.get(url.path.rsplit("/", 1)[-1])
                return self._json(200 if job else 404, job or {"error": "no such job"})
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            if url.path != "/api/generate":
                return self._json(404, {"error": "not found"})
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
                job_id = uuid.uuid4().hex[:12]
                _JOBS[job_id] = {"status": "running",
                                 "baking": bool(body.get("bake", False))}
                threading.Thread(target=_run_generation,
                                 args=(job_id, body, out_root), daemon=True).start()
                return self._json(202, {"job_id": job_id})
            except Exception as exc:
                return self._json(400, {"error": str(exc)})

    return Handler


def run(host: str = "127.0.0.1", port: int = 8000,
        output_dir: str | Path = DEFAULT_OUTPUT, reload: bool = True) -> None:
    """Start the web UI server (blocking).

    With *reload* (default) the package source is watched and the server restarts
    on any edit, so code changes take effect without a manual restart.
    """
    if reload and os.environ.get("BELLOWS_WEB_CHILD") != "1":
        return _run_with_reload(host, port, output_dir)

    handler = make_app(output_dir)
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"Bellows Diecut web UI → http://{host}:{port}/")
    print(f"  output will be written under: {Path(output_dir).resolve()}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        httpd.server_close()


def _run_with_reload(host: str, port: int, output_dir: str | Path) -> None:
    """Watch the package's ``.py`` files and restart the server on any change."""
    import subprocess
    import sys
    import time

    pkg = Path(__file__).resolve().parent.parent          # bellows_diecut/
    cmd = [sys.executable, "-m", "bellows_diecut.web",
           "--host", host, "--port", str(port),
           "--output", str(output_dir), "--no-reload"]
    env = {**os.environ, "BELLOWS_WEB_CHILD": "1"}

    def snapshot() -> dict:
        # Exclude output/ (generated *.py scripts trigger false reload) and __pycache__
        return {p: p.stat().st_mtime for p in pkg.rglob("*.py")
                if "output" not in p.parts and "__pycache__" not in p.parts}

    print("auto-reload on — editing the package restarts the server (Ctrl-C to stop)",
          flush=True)
    proc = subprocess.Popen(cmd, env=env)
    last = snapshot()
    try:
        while proc.poll() is None:
            time.sleep(1.0)
            cur = snapshot()
            if cur != last:
                changed = [p.name for p in cur if last.get(p) != cur.get(p)]
                print(f"↻ reload: {', '.join(sorted(set(changed))[:5])} changed", flush=True)
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                time.sleep(0.3)
                proc = subprocess.Popen(cmd, env=env)
                last = cur
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


# ---------------------------------------------------------------------------
# Single-page UI
# ---------------------------------------------------------------------------

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bellows Diecut</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; font:14px/1.4 system-ui,sans-serif; background:#1e1e22; color:#e6e6e6;
         display:grid; grid-template-columns:300px 1fr; height:100vh; }
  #panel { padding:18px; overflow:auto; border-right:1px solid #333; }
  h1 { font-size:17px; margin:0 0 14px; }
  label { display:block; margin:12px 0 4px; color:#aab; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
  select, input { width:100%; box-sizing:border-box; padding:7px 8px; background:#26262c;
                  color:#eee; border:1px solid #3a3a44; border-radius:6px; }
  .row { display:flex; gap:8px; } .row > div { flex:1; }
  button { width:100%; margin-top:16px; padding:10px; border:0; border-radius:6px;
           background:#4d7cff; color:#fff; font-weight:600; cursor:pointer; }
  button.sec { background:#2f2f38; color:#cdd; }
  #status { margin-top:14px; font-size:12px; color:#9fb; white-space:pre-wrap; }
  #files { margin-top:8px; font-size:11px; color:#99a; max-height:30vh; overflow:auto; }
  #view { position:relative; } canvas { display:block; }
  .hint { color:#778; font-size:11px; margin-top:2px; }
</style>
<script type="importmap">
{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
}}
</script>
<style> #note{font-size:11px;color:#889;margin:6px 0;} #c2d{display:block;} </style>
</head>
<body>
<div id="panel">
  <h1>Bellows Diecut</h1>
  <label>Pattern</label>
  <select id="pattern"></select>
  <div class="row">
    <div><label>Tile X (mm)</label><input id="tile_x" type="number" step="0.5" min="1"></div>
    <div><label>Tile Y (mm)</label><input id="tile_y" type="number" step="0.5" min="1"></div>
  </div>
  <label>Fold height — mountain (mm)</label>
  <input id="fold_height" type="number" step="0.5" min="0.1">
  <div class="row">
    <div><label id="lab_around">Tiles around (horizontal)</label><input id="around" type="number" step="1" min="1"></div>
    <div><label id="lab_repeats">Repeats (height)</label><input id="repeats" type="number" step="1" min="1"></div>
  </div>
  <div class="hint" id="count_hint">Tiles around defaults to the pattern's automatic circumference count.</div>
  <label style="display:flex;align-items:center;gap:8px;text-transform:none;margin-top:14px;color:#cdd;">
    <input type="checkbox" id="bake" style="width:auto;"> Export STL files (roller solids, ready to print)
  </label>
  <button id="gen">Generate rollers + output</button>
  <div id="status"></div>
  <div id="files"></div>
</div>
<div id="view"></div>

<script>
// Plain script (no imports) so the controls work even if three.js (CDN) is
// unavailable.  3D is loaded best-effort; otherwise a 2D crease-pattern is drawn.
const $ = id => document.getElementById(id);
const view = $('view');
let CFG = {}, GL = null, LAST = null;

// ---- 2D crease-pattern fallback ----
function draw2D(d) {
  view.innerHTML = '';
  const c = document.createElement('canvas'); c.id = 'c2d';
  c.width = view.clientWidth; c.height = view.clientHeight; view.appendChild(c);
  const ctx = c.getContext('2d'); ctx.fillStyle = '#1e1e22'; ctx.fillRect(0,0,c.width,c.height);
  const [x0,y0,x1,y1] = d.bbox, w = (x1-x0)||1, h = (y1-y0)||1, pad = 40;
  const s = Math.min((c.width-2*pad)/w, (c.height-2*pad)/h);
  const ox = (c.width-w*s)/2, oy = (c.height-h*s)/2;
  const X = x => ox+(x-x0)*s, Y = y => oy+(y1-y)*s;
  const draw = (arr,color,dash) => { ctx.strokeStyle=color; ctx.lineWidth=2; ctx.setLineDash(dash);
    ctx.beginPath(); arr.forEach(([a,b,p,q]) => { ctx.moveTo(X(a),Y(b)); ctx.lineTo(X(p),Y(q)); }); ctx.stroke(); };
  draw(d.lines.valley, '#6aa8ff', [6,5]);
  draw(d.lines.mountain, '#ff7a6a', []);
  ctx.setLineDash([]); ctx.strokeStyle='#444'; ctx.strokeRect(X(x0),Y(y1),w*s,h*s);
}

// ---- best-effort 3D ----
async function loadGL() {
  try {
    const THREE = await import('three');
    const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
    const w = view.clientWidth, h = view.clientHeight;
    const scene = new THREE.Scene(); scene.background = new THREE.Color(0x1e1e22);
    const camera = new THREE.PerspectiveCamera(45, w/h, 0.1, 5000); camera.position.set(90,70,120);
    const renderer = new THREE.WebGLRenderer({antialias:true});
    renderer.setSize(w,h); renderer.setPixelRatio(devicePixelRatio);
    const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
    scene.add(new THREE.HemisphereLight(0xffffff,0x334455,1.1));
    const dl = new THREE.DirectionalLight(0xffffff,1.6); dl.position.set(60,120,80); scene.add(dl);
    let mesh = null;
    addEventListener('resize', () => { const w=view.clientWidth,h=view.clientHeight; camera.aspect=w/h; camera.updateProjectionMatrix(); renderer.setSize(w,h); });
    (function loop(){ requestAnimationFrame(loop); controls.update(); renderer.render(scene,camera); })();
    GL = { attach(){ view.innerHTML=''; view.appendChild(renderer.domElement); },
      setMesh(pos,idx){ if(mesh){scene.remove(mesh); mesh.geometry.dispose();}
        const g=new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos,3));
        g.setIndex(idx); g.computeVertexNormals(); g.center();
        mesh=new THREE.Mesh(g, new THREE.MeshStandardMaterial({color:0xbfc4cc,metalness:0.1,roughness:0.7,side:THREE.DoubleSide,flatShading:true}));
        scene.add(mesh); g.computeBoundingSphere(); const r=g.boundingSphere.radius||60;
        camera.position.set(r*1.5,r*1.1,r*1.9); controls.target.set(0,0,0); controls.update(); } };
  } catch(e) { GL = null; }
}

function render(d) { LAST = d;
  if (GL) { GL.attach(); GL.setMesh(d.positions, d.indices); } else { draw2D(d); } }

async function preview() {
  const q = new URLSearchParams({pattern:$('pattern').value, tile_x:$('tile_x').value, tile_y:$('tile_y').value, fold_height:$('fold_height').value, repeats:$('repeats').value, around:$('around').value});
  try { const d = await (await fetch('/api/tile?'+q)).json();
    if (d.error) { $('status').textContent = 'Preview error: '+d.error; return; }
    render(d); $('status').textContent = '';
  } catch(e) { $('status').textContent = 'Preview error: '+e; }
}

function fillFor(p) { const c = CFG[p];
  $('tile_x').value=c.tile[0]; $('tile_y').value=c.tile[1]; $('fold_height').value=c.fold_height;
  $('repeats').value=c.repeats; $('around').value=c.around;
  const trap = p.startsWith('accordion');
  $('lab_around').textContent = trap ? 'Trapezoids horizontal' : 'Tiles around (horizontal)';
  $('lab_repeats').textContent = trap ? 'Trapezoids vertical' : 'Repeats (height)';
  $('count_hint').textContent = trap
    ? 'Number of trapezoids around the circumference and along the height.'
    : "Tiles around defaults to the pattern's automatic circumference count."; }

async function init() {
  await loadGL();
  const d = await (await fetch('/api/patterns')).json(); CFG = d.config;
  const sel = $('pattern');
  d.patterns.forEach(p => { const o=document.createElement('option'); o.value=o.textContent=p; sel.appendChild(o); });
  sel.onchange = () => { fillFor(sel.value); preview(); };
  ['tile_x','tile_y','fold_height','repeats','around'].forEach(id => $(id).addEventListener('change', preview));
  fillFor(sel.value); preview();
  addEventListener('resize', () => { if (!GL && LAST) draw2D(LAST); });

  $('gen').onclick = async () => {
    $('gen').disabled = true; $('files').textContent = '';
    const bake = $('bake').checked;
    $('status').textContent = bake ? 'Generating + writing STL files…' : 'Generating…';
    const body = {pattern:sel.value, tile_x:+$('tile_x').value, tile_y:+$('tile_y').value,
                  fold_height:+$('fold_height').value, repeats:+$('repeats').value,
                  around:+$('around').value, bake};
    try {
      const r = await (await fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})).json();
      if (!r.job_id) { $('status').textContent = 'Error: '+(r.error||'no job'); $('gen').disabled=false; return; }
      const poll = setInterval(async () => {
        let j; try { j = await (await fetch('/api/job/'+r.job_id)).json(); } catch(e){ return; }
        if (j.status === 'done') { clearInterval(poll); $('gen').disabled = false;
          const p = j.params || {};
          $('status').textContent = (j.baked ? '✓ baked + wrote ' : '✓ wrote ') + j.files.length
            + ' files\nused: tile ' + (p.tile? p.tile.join('×'):'?') + 'mm, fold ' + p.fold_height
            + 'mm, around ' + p.around + ', repeats ' + p.repeats + '\n→ ' + j.dir;
          $('files').innerHTML = j.files.map(f => (f.endsWith('.stl') ? '<b>• '+f+'</b>' : '• '+f)).join('<br>'); }
        else if (j.status === 'error') { clearInterval(poll); $('gen').disabled = false; $('status').textContent = 'Error: '+j.error; }
      }, 1200);
    } catch(e) { $('status').textContent = 'Error: '+e; $('gen').disabled = false; }
  };
}
init();
</script>
</body>
</html>
"""
