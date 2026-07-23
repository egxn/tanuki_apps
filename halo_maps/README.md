# Halo CE Module

This module contains tools for generating and validating maps for **Halo: Combat Evolved** using the Tanuki procedural geometry framework.

The goal of this module is to automate parts of the Halo map creation pipeline while enforcing the technical constraints required by the Halo engine and the Halo Editing Kit (HEK).

## Halo Map Basics

Maps in Halo: Combat Evolved are built around a **BSP (Binary Space Partition)** structure that defines the playable world geometry. The BSP is compiled using the Halo Editing Kit tools and later populated with objects such as weapons, vehicles, and spawn points.

This module focuses primarily on generating **valid BSP geometry** and assisting with procedural map layouts.

## Setup

Run these commands from the project root of the package (the directory that contains `pyproject.toml`):

```bash
python -m venv .venv
source .venv/bin/activate

pip install -e ../../tanuki/
pip install -e ".[dev]"
```

## Generate and validate a map

Run these commands from the project root of the package (the directory that contains `pyproject.toml`). Blender must be installed and available on your `PATH`.

### 1. Generate the map scene and export JMS

```bash
blender --background --python src/halo_maps/naranjos/run_level.py \
  -- --output src/halo_maps/naranjos/blend/naranjos_level.blend \
     --jms src/halo_maps/naranjos/models/naranjos.jms \
     --scale 27
```

This writes the Blender scene to `src/halo_maps/naranjos/blend/naranjos_level.blend` and the Halo JMS export to `src/halo_maps/naranjos/models/naranjos.jms`.

### 1b. Generate only the Naranjos blend from code

If you want to create the `.blend` file directly from the Python pipeline without going through the full export flow, run:

```bash
blender --background --python src/halo_maps/naranjos/run_level.py \
  -- --output src/halo_maps/naranjos/blend/naranjos_level.blend --jms src/halo_maps/naranjos/models/naranjos.jms
```

You can then open the generated file in Blender with:

```bash
blender src/halo_maps/naranjos/blend/naranjos_level.blend
```

### 2. Validate the BSP geometry

```bash
blender --background src/halo_maps/naranjos/blend/naranjos_level.blend \
  --python src/halo_maps/naranjos/validate_bsp.py \
  -- --object bsp_world
```

Use `--object bsp_merged` if you want to validate the intermediate merged mesh from the DSL pipeline.

### 3. Validate the JMS round-trip with the Halo toolset addon

```bash
blender --background \
  --python src/halo_maps/naranjos/toolset/verify_jms.py \
  -- --jms src/halo_maps/naranjos/models/naranjos.jms
```

### 4. Optional: open an overlay of BSP issues

```bash
blender --background src/halo_maps/naranjos/blend/naranjos_level.blend \
  --python src/halo_maps/naranjos/debug_bsp.py \
  -- --output src/halo_maps/naranjos/blend/debug_naranjos.blend
```

## Roadmap

# Halo CE Module – Utility Checklist

This document lists the utilities planned for the **Tanuki Halo CE module**.
The scope of this module is limited to **initial map generation and validation** using Blender (`bpy`) and Geometry Nodes.

The goal is to create a consistent pipeline for generating **valid BSP geometry** and preparing maps for the Halo Editing Kit workflow.

---

# Scene Initialization

## setup_scene

Configures the Blender scene for Halo CE map development.

This utility standardizes units, prepares the project structure, and removes default objects.

### Scene Settings

* Unit System: Metric
* Unit Scale: 1.0
* Length Unit: Meters

### Collections Created

```
BSP
SCENERY
SPAWNS
VEHICLES
WEAPONS
MARKERS
COLLISION
DEBUG
```

These collections help organize map elements according to the Halo level pipeline.

---

# BSP Root Geometry

## create_bsp_root_object

Creates the root object that will contain the BSP geometry.

### Object

```
bsp_world
```

### Properties

* Type: Mesh
* Collection: BSP
* Location: (0,0,0)

This object will host the Geometry Nodes generator used by Tanuki.

---

## initialize_geometry_nodes

Creates the base Geometry Nodes tree used for procedural map generation.

### Node Tree

```
GN_bsp_generator
```

### Default Nodes

```
Group Input
Group Output
```

The node group is assigned to the `bsp_world` object.

---

# Base Map Generation

## generate_base_volume

Creates the base playable space for the map.

### Object

```
bsp_volume
```

### Collection

```
BSP
```

### Purpose

* Define the initial map boundaries
* Ensure the world starts as a closed volume
* Provide a base mesh for procedural modifications

---

## generate_symmetry_layout

Creates layout references for symmetrical map design.

Halo multiplayer maps often use symmetrical layouts to maintain gameplay balance.

### Object

```
layout_symmetry
```

### Type

```
Empty
```

### Collection

```
MARKERS
```

### Possible Symmetry Modes

* mirror
* radial
* lane-based

---

## generate_spawn_zones

Creates spawn markers for players.

### Objects

```
spawn_red_01
spawn_red_02
spawn_red_03

spawn_blue_01
spawn_blue_02
spawn_blue_03
```

### Type

```
Empty
```

### Collection

```
SPAWNS
```

These markers define areas where player spawn points can later be placed.

---


# Geometry Validation Tools

These utilities ensure that the generated BSP geometry respects Halo engine constraints.

---

## validate_closed_geometry

Checks that the BSP mesh is a fully closed volume.

### Object Checked

```
bsp_world
```

### Detects

* open edges
* holes in geometry

Example problem:

```
edge with only one face
```

---

## validate_manifold_edges

Ensures the geometry is manifold.

Each edge must belong to exactly two faces.

### Object Checked

```
bsp_world
```

### Detects

* edges with 3+ faces
* edges with only 1 face

Common causes include:

* incorrect extrusions
* bad boolean operations

---

## validate_duplicate_vertices

Detects duplicated or extremely close vertices.

### Object Checked

```
bsp_world
```

### Prevents

* shading errors
* BSP compilation issues

---

## validate_internal_faces

Detects faces inside the BSP volume.

### Object Checked

```
bsp_world
```

### Prevents

* lighting errors
* collision glitches

---

## validate_polygon_budget

Counts the total number of polygons in the BSP mesh.

### Object Checked

```
bsp_world
```

### Warning Threshold

Approximately 10,000 polygons (configurable).

---

## validate_normals

Checks that face normals are consistent and correctly oriented.

### Object Checked

```
bsp_world
```

### Detects

* inverted normals
* inconsistent face orientation

---

# Export Utilities

## export_jms

Exports BSP geometry to the format used by the Halo Editing Kit.

### Object Exported

```
bsp_world
```

### File Generated

```
map_name.jms
```


---

# Naming Conventions

### Object Names

```
bsp_world
bsp_volume
layout_symmetry

spawn_red_##
spawn_blue_##

vehicle_path_##
```

### Geometry Node Trees

```
GN_bsp_generator
```

---

# Collection Structure

```
BSP
SCENERY
SPAWNS
VEHICLES
WEAPONS
MARKERS
COLLISION
DEBUG
```

---

# Design Philosophy

All Tanuki Halo tools rely on standardized naming conventions.
This allows scripts and validators to automatically discover map elements and operate on the correct geometry without manual configuration.



## Core Geometry Rules

When generating geometry for Halo maps, several important constraints must be respected.

### 1. Sealed World Geometry

The BSP world must be **completely sealed**.

The playable space must form a **closed volume**, meaning:

* no holes in the geometry
* no missing faces
* no open boundaries to the void

Open edges or gaps will cause BSP compilation errors.

Decorative objects placed later (scenery) do not need to be sealed.

---

### 2. Manifold Geometry

The BSP must use **manifold geometry**.

Each edge must belong to exactly **two faces**.

Invalid examples include:

* edges shared by three or more faces
* edges belonging to only one face

These situations produce **non-manifold geometry** and will break BSP compilation.

---

### 3. Clean Topology

Geometry should avoid:

* duplicate vertices
* internal faces
* overlapping surfaces
* zero-area polygons

Clean topology improves BSP stability and lighting calculations.

---

### 4. Polygon Budget

Halo CE runs on a relatively old engine and requires modest polygon counts.

Typical guidelines for multiplayer maps:

* approximately **10,000 polygons for world geometry**
* minimize unnecessary subdivision

Static objects such as scenery may increase total scene complexity but should be used carefully.

---

### 5. Separate World Geometry and Objects

Halo distinguishes between two categories:

**World Geometry (BSP)**
Includes terrain, walls, buildings, and structural elements.

**Placed Objects**
Added later in the level editor:

* weapons
* vehicles
* spawn points
* scenery
* lights

Procedural generation in this module focuses primarily on the **BSP layer**.

---

### 6. Player and Vehicle Boundaries

Maps must control player and vehicle movement using:

* collision surfaces
* clipping volumes
* map boundaries

Improper geometry can allow players or vehicles to escape the intended play area.

---

### 7. BSP Compilation Pipeline

A typical Halo map workflow follows this pipeline:

1. Model world geometry
2. Export to `.JMS`
3. Compile BSP using `tool.exe`
4. Populate objects using Sapien
5. Generate lightmaps
6. Build the final `.map` file

The Tanuki Halo module aims to automate the **geometry generation and validation** steps in this pipeline.

---
