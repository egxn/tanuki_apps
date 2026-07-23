# Toolset scripts — Halo Asset Blender Toolset integration

Scripts que usan el addon **Halo Asset Blender Development Toolset** (el mismo
que está en `docs/halo-asset-blender-toolset-full-v397@4423317/`) para validar
y depurar el pipeline de Naranjos **antes** de pasar por `tool.exe`.

## Requisito clave: NO usar `--factory-startup`

El flag `--factory-startup` deshabilita los addons del usuario. Para que estos
scripts encuentren el addon `io_scene_halo`, ejecútalos **sin** ese flag:

```bash
# ❌ addon NO disponible
blender --background --factory-startup --python script.py

# ✅ addon disponible
blender --background --python script.py
```

> ⚠️ El addon hace `os.chdir()` a su propia carpeta durante el registro. Por eso
> **siempre pasa rutas absolutas** al `--python` y a los argumentos `--`, o el
> script fallará con "No such file or directory".

---

## Scripts

### `addon_check.py`
Verifica que el addon esté instalado y lista los operadores útiles para el
pipeline de BSP. Si el addon no está activo, intenta activarlo.

```bash
blender --background \
  --python /ruta/abs/halo_maps/naranjos/toolset/addon_check.py
```

Salida esperada: `io_scene_halo is enabled ✓` y una tabla de operadores con `✓`.

---

### `verify_jms.py`
**El más valioso.** Re-importa `naranjos.jms` con el parser del addon (la misma
familia de código que usa la comunidad). Si importa limpio, el archivo es
estructuralmente válido y `tool.exe` debería aceptarlo. Captura errores de
formato JMS antes de compilar.

```bash
blender --background \
  --python /ruta/abs/.../toolset/verify_jms.py \
  -- --jms /ruta/abs/.../naranjos.jms
```

Verifica:
- Materiales declarados (collideable + render-only `!` + especiales `+portal`/`+sky`)
- Que el addon parsee el archivo sin error
- Conteo de meshes / verts / faces importados

> Este script ya cazó **3 bugs reales** del exporter `export.py` (ver abajo).

---

### `import_wrl.py`
Importa la geometría de error `.wrl` que genera `tool.exe` cuando encuentra
problemas (open edges, NM edges, coplanares, T-junctions…). Las caras
problemáticas aparecen coloreadas dentro del nivel para inspección visual.

```bash
blender /ruta/abs/.../naranjos_level.blend \
  --python /ruta/abs/.../toolset/import_wrl.py \
  -- --wrl /ruta/abs/.../naranjos.wrl
```

Sin `--wrl` imprime la leyenda de colores. Guarda un `.wrl_overlay.blend` con la
geometría de error superpuesta al nivel para abrir en la GUI.

Leyenda de colores (ver `docs/bsp_throubleshooting.md`):

| Color | Significado |
|---|---|
| rojo | Open edge / triángulo degenerado |
| verde | Caras casi coplanares (con rojo) |
| naranja | Caras superpuestas (Z-fighting) / triángulo duplicado |
| rosa | Posible T-junction (cara delgada/pequeña) |
| cyan | Superficie fuera del BSP |
| magenta | Arista de portal expuesta / portal fuera del BSP |
| amarillo | Portal no define dos espacios cerrados |
| azul | UVs degeneradas (radiosidad) |
| negro | Dos fog planes en un cluster |

---

## Bugs del exporter JMS corregidos gracias a `verify_jms.py`

El formato JMS **v8200** (< 8205) que espera `tool.exe` difiere del que escribíamos.
Los 3 errores estaban en `halo_maps/export.py`:

1. **Faltaba el node-list checksum** — Después de la línea de versión (`8200`)
   debe ir un entero de checksum (`0` para un esqueleto trivial de un solo nodo),
   *antes* del conteo de nodos. Sin él, el parser leía `frame` donde esperaba un int.

2. **3 índices de nodo en vez de 2** — El formato v8200 (< 8205) almacena
   `<child> <sibling>` (2 índices), no `<parent> <child> <sibling>` (3). El índice
   de parent es del formato ≥ 8205. El índice extra desplazaba todos los tokens.

3. **Faltaba el campo flags por vértice** — Para v ≥ 8199 cada vértice termina con
   un entero "flags" sin uso, después de las UVs. Sin él, cada vértice se
   desfasaba por un token.

### Formato v8200 correcto (referencia)

```
8200                    ← versión
<node checksum>         ← entero (0 para skeleton trivial)
<node count>            ← p.ej. 1
frame                   ← nombre del nodo
<first child>           ← -1 = ninguno
<next sibling>          ← -1 = ninguno
<rot i j k w>           ← cuaternión
<pos x y z>
<material count>
  <name> <bitmap path>  ← por material (halo1: 2 tokens)
<marker count>          ← 0
<region count> <names>  ← (< 8205) p.ej. 1, "unnamed"
<vertex count>
  <node 0 index>        ← 0 (frame)
  <pos x y z>
  <normal x y z>
  <node 1 index>        ← -1 (sin segunda influencia)
  <node 1 weight>       ← 0.0
  <tex u> <tex v>
  <flags>               ← entero sin uso (v >= 8199)
<triangle count>
  <region> <material> <v0> <v1> <v2>   ← (8198 ≤ v < 8205) 5 ints
```

Fuente: `docs/.../io_scene_halo/file_jms/process_file_retail.py`
(la función `process_file_retail`, ramas `JMS.version < 8205`).
