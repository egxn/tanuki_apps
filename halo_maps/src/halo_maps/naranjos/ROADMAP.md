# Naranjos — Halo CE Map Roadmap

## Estado actual: pipeline completo, listo para prueba con tool.exe

---

## ✅ Completado

### Pipeline de generación
- [x] DSL paramétrico de edificios desde SVG + JSON (`generate_dsl.py`)
- [x] Edificios con puertas, ventanas, escaleras, halls, tejados, bordes del campus
- [x] Merge de toda la geometría en `bsp_merged`
- [x] Fix de T-junctions (bisect + non-manifold passes)
- [x] Fix de aristas back-to-back y coplanares
- [x] Sellado del mundo: portales en puertas/ventanas + sky envelope
- [x] Triangulación y limpieza de faces coplanares superpuestas
- [x] Exportación JMS v8200 con escala ×27 (equivalente a S→27 en Blender Edit Mode)
- [x] Guardado de `naranjos_level.blend` + `naranjos.jms`

### Materiales y texturas
- [x] 4 materiales con texturas TIF (wall, floor, hall, roof)
  - `naranjos_wall`  → paredes verticales
  - `naranjos_floor` → pavimento exterior del campus
  - `naranjos_hall`  → pisos interiores / techos de corredores
  - `naranjos_roof`  → tejados (tejas)
- [x] Box-mapping UV por material con tile configurable
- [x] Paths JMS correctos: `levels\naranjos\materials\<nombre>`
- [x] Imágenes empacadas en el blend (pack)
- [x] Rutas relativas `//materials/*.tif` en el blend

### NM edges (aristas no-manifold) — RESUELTO en la raíz
- [x] **Causa raíz identificada**: las escaleras y paredes back-to-back son cajas
  sólidas que se topan; sus caras de contacto quedan *enterradas* dentro del
  volumen combinado y, tras el weld global, crean aristas de 3+ caras.
- [x] **Fix**: `_remove_interior_faces()` en generate_dsl.py usa
  `mesh.select_interior_faces` (herramienta nativa de Blender) sobre `bsp_merged`
  ya fusionado → elimina las caras enterradas. **94 NM → 0 NM en bsp_merged.**
- [x] Eliminado el hack `naranjos_wall!` (render-only) de level.py — era
  contraproducente: convertía 30 NM en 91 open edges (ver validación más abajo).
- [x] `_dissolve_coplanar_nm_edges` limpia los pocos overlaps coplanares que
  el sellado de portales introduce.
- [x] **Resultado final en bsp_world: 0 boundary, 0 NM colisionable.**
  Quedan 4 NM "geométricos" pero cada uno es 2 caras +portal + 2 colisionables
  (overlap de portal-fill); para colisión cada arista tiene exactamente 2 caras
  sellantes → manifold válido, inofensivo para tool.exe.

### Viewport Blender
- [x] `bsp_merged` oculto para no superponer con `bsp_world`
- [x] Texturas visibles en Material Preview (Alt+Z)
- [x] 7 slots de material en orden correcto (wall, floor, hall, roof, wall!, portal, sky)

### Estructura output para tool.exe
```
output/
├─ data/levels/naranjos/
│  ├─ models/naranjos.jms
│  └─ materials/ (wall/floor/hall/roof).tif
└─ tags/levels/naranjos/
   └─ shaders/  ← tool.exe genera aquí al importar
```

### Validación JMS con el addon (toolset/)
- [x] Scripts de integración con Halo Asset Blender Toolset (`toolset/`)
- [x] `verify_jms.py` re-importa el JMS con el parser del addon → **importa limpio**
- [x] Corregidos 3 bugs de formato JMS v8200 en `export.py`:
  - Faltaba el node-list checksum
  - 3 índices de nodo en vez de 2 (child/sibling)
  - Faltaba el campo flags por vértice (v ≥ 8199)
- [x] `import_wrl.py` listo para visualizar errores de tool.exe
- Ver `toolset/README.md` para el formato v8200 completo

---

## ⏳ Pendiente

### 1. Compilar bitmaps con tool.exe
```bat
tool bitmaps "levels\naranjos\materials"
```
Convierte los 4 TIF → tags `.bitmap` en `tags\levels\naranjos\materials\`.

### 2. Importar BSP con tool.exe
```bat
tool structure "levels\naranjos" naranjos
```
- Cuando pregunte por tipo de shader → elegir **`shader_environment`** para cada material
- Genera automáticamente `naranjos.scenario` y shaders vacíos
- Verifica que no haya errores WRL (open edges, NM edges, coplanares)

### 3. Configurar shaders en Guerilla
Editar cada shader generado en `tags\levels\naranjos\shaders\`:
- `naranjos_wall.shader_environment`  → base map: `levels\naranjos\materials\wall`
- `naranjos_floor.shader_environment` → base map: `levels\naranjos\materials\floor`
- `naranjos_hall.shader_environment`  → base map: `levels\naranjos\materials\hall`
- `naranjos_roof.shader_environment`  → base map: `levels\naranjos\materials\roof`
- `naranjos_wall!` usa el mismo shader que `naranjos_wall` (tool.exe ignora `!` en el nombre)

> ⚠️ Sapien crashea si los shaders tienen referencias de bitmap vacías. Siempre agregar el base map antes de abrir Sapien.

### 4. Re-importar BSP con shaders
```bat
tool structure "levels\naranjos" naranjos
```
Segunda pasada para que el BSP tag quede con los shaders referenciados.

### 5. Configurar el scenario en Guerilla
Abrir `tags\levels\naranjos\naranjos.scenario`:
- **Type** → `multiplayer`
- **Skies** → agregar referencia, ej. `sky\sky_timberland\sky_timberland.sky`
- Guardar

### 6. Lightmaps (draft)
```bat
tool lightmaps "levels\naranjos\naranjos" naranjos 0 0.3
```

### 7. Spawn points en Sapien
- Abrir el scenario en Sapien
- **Player starting points** → colocar al menos:
  - 1 spawn singleplayer (types 0-3 = none)
  - 1 spawn red team (type 0 = all games, team index 0)
  - 1 spawn blue team (type 0 = all games, team index 1)

### 8. Prueba en juego
```
; en la consola de Standalone / Custom Edition:
game_variant slayer
map_name levels\naranjos\naranjos
```

---

## ⚠️ Problemas conocidos

### ✅ Escaleras — RESUELTO
Antes: las escaleras (cajas sólidas apiladas) creaban ~48 NM edges al toparse con
paredes/pisos, "parcheadas" con render-only (que rompía la colisión y creaba open
edges). Ahora `_remove_interior_faces()` elimina las caras enterradas en
`bsp_merged`, dejándolo 100 % manifold (0 NM). Las escaleras son navegables Y
tienen colisión completa en sus paneles laterales.

### `+exactportal` vs `+portal`
Actualmente se usa `+portal` para sellar puertas y ventanas. El doc recomienda
`+exactportal` para mejor PVS/culling en aperturas exactas. Mejora opcional.

### Escala verificada empíricamente
La escala ×27 fue confirmada visualmente comparando con una malla del Capitán
del Halo Blender Toolset. No verificada con medidas exactas de JMS units.

---

## 📐 Referencia de escala

| Magnitud | BU (Blender) | JMS units (×27) |
|---|---|---|
| 1 BU | 1 | 27 |
| Piso 1 (2.28 m) | ~4.15 BU | ~112 JU |
| Campus ancho | ~204 BU | ~5,508 JU |
| Límite Halo CE | — | ±150,000 JU |

---

## 🗂️ Estructura del proyecto

```
naranjos/
├─ generate_dsl.py        Generación paramétrica de edificios desde SVG/JSON
├─ level.py               Ensamble del nivel: portales, sky, materiales, JMS export
├─ run_level.py           Runner CLI completo (DSL + level + save)
├─ generate.py            Generador legacy (no-DSL)
├─ validate_bsp.py        Validador de reglas sealed-world
├─ debug_bsp.py           Overlays de debug (T-junctions, NM, boundary)
├─ check_paths.py         Valida existencia de todos los archivos referenciados
├─ ROADMAP.md             Este archivo
│
├─ config/               ← JSON: definiciones de edificios/puertas/ventanas/etc.
│  ├─ buildings.json  borders.json  roofs_halls.json
│  └─ stairs.json  objects.json  doors.json  windows.json
├─ svg/                  ← Fuente: map.svg, map_bk.svg
├─ blend/                ← Blends generados: naranjos_dsl_updated, naranjos_level
├─ models/               ← naranjos.jms (JMS v8200 — convención HEK models/)
├─ materials/            ← Texturas .tif/.png: wall, floor, hall, roof
├─ output/               ← Estructura lista para copiar en HEK/Mod Tools
├─ toolset/              ← Scripts de validación con Halo Asset Blender Toolset
└─ diag/                 ← Scripts de diagnóstico one-off
```

> Los `.py` de la raíz **son el paquete Python** `halo_maps.naranjos`
> (importados por nombre en todo el proyecto, usan `parents[4]` para llegar a
> `src/`). Por eso permanecen en la raíz — moverlos a subcarpetas rompería los
> imports. Solo los datos (config/svg/blend/models/materials) se agrupan.
>
> Ejecuta `python3 check_paths.py` para validar que toda la estructura esté íntegra.
