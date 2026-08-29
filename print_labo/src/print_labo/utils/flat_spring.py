"""Generate flat, serpentine springs as SVG profiles.

The generated SVG is deliberately made of separate, named components.  This
makes it convenient to import the profile in Blender (or another CAD tool) and
extrude it afterwards.  Dimensions are in millimetres.

``width`` is the distance between the two spring rails and ``track_width`` is
the material/line width.  ``length`` is the length of the centre line, before
the line width is taken into account.  The two end connectors are longer than
the intermediate tracks by ``connector_multiplier`` (2 by default).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape
from pathlib import Path

from tanuki.dsl import (
    mesh_polygon_solid,
    union,
)


@dataclass(frozen=True)
class FlatSpringSpec:
    """Validated dimensions used to build a flat spring SVG."""

    length: float
    width: float
    curves: int
    track_width: float = 1.0
    connector_multiplier: float = 2.0
    extrusion_height: float = 1.0
    arc_resolution: int = 16
    start_side: str = "right"

    def __post_init__(self) -> None:
        if self.length <= 0 or self.width <= 0:
            raise ValueError("length and width must be greater than zero")
        if self.curves < 1 or int(self.curves) != self.curves:
            raise ValueError("curves must be a positive integer")
        if self.track_width <= 0:
            raise ValueError("track_width must be greater than zero")
        if self.connector_multiplier < 1:
            raise ValueError("connector_multiplier must be at least one")
        if self.extrusion_height <= 0:
            raise ValueError("extrusion_height must be greater than zero")
        if self.arc_resolution < 2:
            raise ValueError("arc_resolution must be at least two")
        if self.start_side not in {"left", "right"}:
            raise ValueError("start_side must be 'left' or 'right'")


def _fmt(value: float, precision: int = 4) -> str:
    return f"{value:.{precision}f}".rstrip("0").rstrip(".") or "0"


def evaluate_flat_spring_route(
    length: float,
    width: float,
    curves: int,
    *,
    connector_multiplier: float = 2.0,
    start_side: str = "right",
) -> dict[str, object]:
    """Evaluate the ordered tracks and semicircles before mesh generation."""
    spec = FlatSpringSpec(
        length, width, curves, 1.0, connector_multiplier, 1.0, 16, start_side
    )
    spacing = spec.length / spec.curves
    middle = spec.width / 2
    left, right = 0.0, spec.width
    first_direction = 1 if start_side == "right" else -1
    tracks: list[dict[str, float | int]] = []
    arcs: list[dict[str, float | int | str]] = []

    for track_index in range(curves + 1):
        direction = first_direction * (1 if track_index % 2 == 0 else -1)
        start = middle if track_index == 0 else (
            left if direction > 0 else right
        )
        end = middle if track_index == curves else (
            right if direction > 0 else left
        )
        tracks.append({
            "index": track_index,
            "x_start": start,
            "x_end": end,
            "y": track_index * spacing,
            "direction": direction,
        })
        if track_index < curves:
            side = start_side if track_index % 2 == 0 else (
                "left" if start_side == "right" else "right"
            )
            arcs.append({
                "index": track_index,
                "side": side,
                "x": right if side == "right" else left,
                "y_start": track_index * spacing,
                "y_end": (track_index + 1) * spacing,
                "radius": spacing / 2,
            })

    connector = connector_multiplier * width
    return {
        "track_length": width,
        "track_spacing": spacing,
        "connector_length": connector,
        "tracks": tracks,
        "semicircles": arcs,
        "start_side": start_side,
    }


def validate_flat_spring_route(route: dict[str, object], curves: int) -> None:
    """Validate that every track endpoint has exactly one semicircle join."""
    tracks = route["tracks"]
    arcs = route["semicircles"]
    if len(tracks) != curves + 1 or len(arcs) != curves:
        raise ValueError("route must contain curves + 1 tracks and curves semicircles")
    expected_sides = []
    first_side = str(route["start_side"])
    other_side = "left" if first_side == "right" else "right"
    for index, arc in enumerate(arcs):
        expected = first_side if index % 2 == 0 else other_side
        if str(arc["side"]) != expected:
            raise ValueError(f"semicircle {index} is on the wrong side")
        if float(arc["y_start"]) != float(tracks[index]["y"]):
            raise ValueError(f"semicircle {index} does not start at track {index}")
        if float(arc["y_end"]) != float(tracks[index + 1]["y"]):
            raise ValueError(f"semicircle {index} does not end at track {index + 1}")
        side_x = float(arc["x"])
        if float(tracks[index]["x_end"]) != side_x or float(tracks[index + 1]["x_start"]) != side_x:
            raise ValueError(f"semicircle {index} is not connected to the two different tracks")


def _flat_outline(
    spec: FlatSpringSpec,
    *,
    head_length: float = 0.0,
    tail_length: float = 0.0,
) -> list[tuple[float, float]]:
    """Build one continuous closed outline around the spring centre line."""
    center = _centerline_points(
        spec, head_length=head_length, tail_length=tail_length
    )
    half = spec.track_width / 2
    def offset_side(sign: float) -> list[tuple[float, float]]:
        result: list[tuple[float, float]] = []
        for i, point in enumerate(center):
            p0 = center[max(0, i - 1)]
            p1 = center[min(len(center) - 1, i + 1)]
            u0x, u0y = p1[0] - p0[0], p1[1] - p0[1]
            u0_len = math.hypot(u0x, u0y) or 1.0
            u0x, u0y = u0x / u0_len, u0y / u0_len
            u1x, u1y = u0x, u0y
            if i < len(center) - 1:
                u1x, u1y = center[i + 1][0] - point[0], center[i + 1][1] - point[1]
                u1_len = math.hypot(u1x, u1y) or 1.0
                u1x, u1y = u1x / u1_len, u1y / u1_len
            n0x, n0y = sign * -u0y, sign * u0x
            n1x, n1y = sign * -u1y, sign * u1x
            a = (point[0] + n0x * half, point[1] + n0y * half)
            b = (point[0] + n1x * half, point[1] + n1y * half)
            den = u0x * u1y - u0y * u1x
            if abs(den) < 1e-8:
                result.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
            else:
                t = ((b[0] - a[0]) * u1y - (b[1] - a[1]) * u1x) / den
                result.append((a[0] + t * u0x, a[1] + t * u0y))
        return result

    left = offset_side(1.0)
    right = offset_side(-1.0)
    return left + list(reversed(right))


def flat_spring_outline(
    length: float,
    width: float,
    curves: int,
    *,
    track_width: float = 1.0,
    connector_multiplier: float = 2.0,
    arc_resolution: int = 16,
    start_side: str = "right",
) -> tuple[tuple[float, float, float], ...]:
    """Return the ordered, closed spring outline vertices in the XY plane."""
    spec = FlatSpringSpec(
        length, width, curves, track_width, connector_multiplier, 1.0, arc_resolution, start_side
    )
    return tuple((x, y, 0.0) for x, y in _flat_outline(spec))


def generate_flat_spring_svg(
    length: float,
    width: float,
    curves: int,
    *,
    track_width: float = 1.0,
    connector_multiplier: float = 2.0,
    extrusion_height: float = 1.0,
    arc_resolution: int = 16,
    precision: int = 4,
) -> str:
    """Return an SVG profile for a flat spring.

    ``curves`` is the number of semicircles.  The available length is split
    between the semicircles, the intermediate tracks, and the two connectors.
    End connectors are ``connector_multiplier`` times an intermediate track.
    ``extrusion_height`` is stored as an SVG metadata attribute for the
    subsequent SVG-to-mesh/extrusion step.
    """
    spec = FlatSpringSpec(
        length, width, curves, track_width, connector_multiplier,
        extrusion_height, arc_resolution,
    )
    margin = track_width / 2
    outline = _flat_outline(spec)
    min_x = min(px for px, _ in outline)
    max_x = max(px for px, _ in outline)
    min_y = min(py for _, py in outline)
    max_y = max(py for _, py in outline)
    view_width = max_x - min_x + 2 * margin
    view_height = max_y - min_y + 2 * margin
    outline_points = [
        (px - min_x + margin, py - min_y + margin) for px, py in outline
    ]
    path_data = "M " + " ".join(
        f"{_fmt(px, precision)} {_fmt(py, precision)}"
        for px, py in outline_points
    ) + " Z"

    attrs = (
        f'width="{_fmt(view_width, precision)}mm" '
        f'height="{_fmt(view_height, precision)}mm" '
        f'viewBox="0 0 {_fmt(view_width, precision)} {_fmt(view_height, precision)}" '
        f'data-extrusion-height="{_fmt(extrusion_height, precision)}" '
        f'data-centerline-length="{_fmt(length, precision)}"'
    )
    style = (
        ".spring-component { fill: #000; stroke: none; }"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" {attrs}>\n"
        f"  <title>Flat spring: {escape(str(curves))} semicircles</title>\n"
        f"  <metadata extrusion-height=\"{_fmt(extrusion_height, precision)}\" />\n"
        f"  <style>{style}</style>\n"
        f"  <path id=\"flat-spring-profile\" class=\"spring-component\" d=\"{path_data}\" />\n"
        "</svg>\n"
    )


def _centerline_points(
    spec: FlatSpringSpec,
    *,
    head_length: float = 0.0,
    tail_length: float = 0.0,
) -> list[tuple[float, float]]:
    """Return the spring centre line in the XY plane."""
    route = evaluate_flat_spring_route(
        spec.length, spec.width, spec.curves,
        connector_multiplier=spec.connector_multiplier,
        start_side=spec.start_side,
    )
    validate_flat_spring_route(route, spec.curves)
    tracks = route["tracks"]
    arcs = route["semicircles"]
    middle = spec.width / 2
    first_track = tracks[0]
    points = []
    if head_length > 0:
        points.append((float(first_track["x_start"]), -head_length))
    points.extend([
        (float(first_track["x_start"]), 0.0),
        (float(first_track["x_end"]), 0.0),
    ])
    radius = float(arcs[0]["radius"])
    for arc in arcs:
        side = str(arc["side"])
        side_x = spec.width if side == "right" else 0.0
        start_angle = -90
        sweep = 180 if side == "right" else -180
        center_y = float(arc["y_start"]) + radius
        for segment in range(1, spec.arc_resolution + 1):
            angle = start_angle + sweep * segment / spec.arc_resolution
            points.append((
                side_x + radius * math.cos(math.radians(angle)),
                center_y + radius * math.sin(math.radians(angle)),
            ))
        next_track = tracks[int(arc["index"]) + 1]
        # The arc enters the *start* of the next track.  Using x_end here
        # creates the diagonal shortcuts visible on alternating tracks.
        points.append((float(next_track["x_start"]), float(next_track["y"])))
        points.append((float(next_track["x_end"]), float(next_track["y"])))
    final_direction = int(tracks[-1]["direction"])
    if tail_length > 0:
        points.append((float(tracks[-1]["x_end"]), float(tracks[-1]["y"])))
        points.append((
            float(tracks[-1]["x_end"]),
            float(tracks[-1]["y"]) + tail_length,
        ))
    return points


def flat_spring(
    length: float,
    width: float,
    curves: int,
    *,
    track_width: float = 1.0,
    connector_multiplier: float = 2.0,
    extrusion_height: float = 1.0,
    arc_resolution: int = 16,
    start_side: str = "right",
    head_length: float | None = None,
    tail_length: float | None = None,
) -> object:
    """Return an extruded Tanuki spring geometry.

    The spring profile is calculated from one validated route, materialized as
    one Tanuki planar mesh object, and extruded uniformly in Z.

    ``head_length`` and ``tail_length`` optionally add vertical termination
    extensions in Y. When omitted, no extra end segments are added.
    """
    spec = FlatSpringSpec(
        length, width, curves, track_width, connector_multiplier,
        extrusion_height, arc_resolution, start_side,
    )
    if head_length is not None and head_length <= 0:
        raise ValueError("head_length must be greater than zero")
    if tail_length is not None and tail_length <= 0:
        raise ValueError("tail_length must be greater than zero")
    route = evaluate_flat_spring_route(
        length, width, curves,
        connector_multiplier=connector_multiplier,
        start_side=start_side,
    )
    validate_flat_spring_route(route, curves)

    # Always use the validated component route.  The offset of a single
    # polygon around a serpentine path can create spurious diagonal segments;
    # components keep every track and semicircle exactly on the route.
    spacing = float(route["track_spacing"])
    track_length = float(route["track_length"])
    radius = spacing / 2
    half = track_width / 2
    join_epsilon = min(track_width * 0.02, spacing * 0.005)
    left, right = 0.0, track_length
    middle = track_length / 2
    polygons: list[tuple[tuple[float, float, float], ...]] = []

    def rectangle(x0: float, x1: float, y: float) -> tuple[tuple[float, float, float], ...]:
        # Make neighbouring solids overlap by a tiny, bounded amount. Exact
        # edge-to-edge contact is not a reliable boolean connection in
        # Blender and can leave multiple disconnected springs.
        x0 -= join_epsilon
        x1 += join_epsilon
        return (
            (x0, y - half, 0), (x1, y - half, 0),
            (x1, y + half, 0), (x0, y + half, 0),
        )

    def vertical_rectangle(x: float, y0: float, y1: float) -> tuple[tuple[float, float, float], ...]:
        return (
            (x - half, y0, 0), (x + half, y0, 0),
            (x + half, y1, 0), (x - half, y1, 0),
        )

    def connector_circle(x: float, y: float) -> tuple[tuple[float, float, float], ...]:
        radius = half
        return tuple(
            (
                x + radius * math.cos(2 * math.pi * index / arc_resolution),
                y + radius * math.sin(2 * math.pi * index / arc_resolution),
                0,
            )
            for index in range(arc_resolution)
        )

    def ensure_upward(points: tuple[tuple[float, float, float], ...]) -> tuple[tuple[float, float, float], ...]:
        area = sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
        if area <= 0:
            return tuple(reversed(points))
        return points

    # Keep the initial and final half-tracks. Optional head/tail extensions
    # are vertical in Y and separate, explicit faces.
    for track in route["tracks"]:
        x0, x1 = sorted((float(track["x_start"]), float(track["x_end"])))
        polygons.append(rectangle(x0, x1, float(track["y"])))

    first_track = route["tracks"][0]
    if head_length is not None:
        polygons.append(vertical_rectangle(
            float(first_track["x_start"]),
            float(first_track["y"]) - head_length,
            float(first_track["y"]),
        ))
        polygons.append(connector_circle(
            float(first_track["x_start"]), float(first_track["y"])
        ))

    final_track = route["tracks"][-1]
    if tail_length is not None:
        polygons.append(vertical_rectangle(
            float(final_track["x_end"]),
            float(final_track["y"]),
            float(final_track["y"]) + tail_length,
        ))
        polygons.append(connector_circle(
            float(final_track["x_end"]), float(final_track["y"])
        ))

    for arc in route["semicircles"]:
        index = int(arc["index"])
        side = str(arc["side"])
        side_x = right if side == "right" else left
        center_y = (index + 0.5) * spacing
        outer = radius + half
        inner = max(0.001, radius - half)
        if side_x == right:
            # Right: 12 -> 6 through the right half of the circle.
            outer_angles = [-90 + 180 * i / arc_resolution for i in range(arc_resolution + 1)]
            inner_angles = [90 - 180 * i / arc_resolution for i in range(arc_resolution + 1)]
        else:
            # Left: 6 -> 12 through the left half of the circle.
            outer_angles = [-90 - 180 * i / arc_resolution for i in range(arc_resolution + 1)]
            inner_angles = [-270 + 180 * i / arc_resolution for i in range(arc_resolution + 1)]
        ring_points = [
            (side_x + outer * math.cos(math.radians(a)),
             center_y + outer * math.sin(math.radians(a)), 0)
            for a in outer_angles
        ] + [
            (side_x + inner * math.cos(math.radians(a)),
             center_y + inner * math.sin(math.radians(a)), 0)
            for a in inner_angles
        ]
        polygons.append(ensure_upward(tuple(ring_points)))

    polygons = [ensure_upward(polygon) for polygon in polygons]
    if not all(polygon for polygon in polygons):
        raise ValueError("flat spring contains an empty profile face")
    # Extrude each closed component before joining them.  Extruding one mesh
    # containing coplanar/overlapping faces can leave only side walls in
    # Blender's Extrude Mesh node; separate components retain their caps.
    solids = [
        mesh_polygon_solid(
            polygon, spec.extrusion_height,
            label=f"flat_spring_component_{index}",
        )
        for index, polygon in enumerate(polygons)
    ]
    # Joining only groups disconnected solids.  A boolean union is required
    # so the tracks and semicircles become one connected spring.
    return union(solids)


def write_flat_spring_svg(path: str | Path, *args: object, **kwargs: object) -> Path:
    """Generate a spring SVG and write it to *path*."""
    output = Path(path)
    output.write_text(generate_flat_spring_svg(*args, **kwargs), encoding="utf-8")
    return output


# Short alias useful in small generator scripts.
flat_spring_svg = generate_flat_spring_svg


__all__ = [
    "FlatSpringSpec",
    "generate_flat_spring_svg",
    "flat_spring",
    "flat_spring_outline",
    "evaluate_flat_spring_route",
    "validate_flat_spring_route",
    "flat_spring_svg",
    "write_flat_spring_svg",
]
