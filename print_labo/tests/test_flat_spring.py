import math

from print_labo.utils import flat_spring_outline


def test_flat_spring_outline_is_continuous_and_planar():
    points = flat_spring_outline(
        length=32,
        width=20,
        curves=5,
        track_width=2,
        arc_resolution=16,
    )

    # Each track is explicitly traversed between its two semicircle joins.
    assert len(points) == 2 * (2 + 5 * (16 + 2))
    assert all(point[2] == 0.0 for point in points)
    assert all(
        math.dist(points[i], points[(i + 1) % len(points)]) > 1e-9
        for i in range(len(points))
    )


def test_flat_spring_outline_supports_short_longitudinal_length():
    points = flat_spring_outline(length=32, width=20, curves=5)
    assert max(point[0] for point in points) - min(point[0] for point in points) > 20
    assert min(point[1] for point in points) < 0 < max(point[1] for point in points)


def test_flat_spring_outline_is_parameterizable_for_different_layouts():
    short = flat_spring_outline(length=32, width=20, curves=5)
    long = flat_spring_outline(length=120, width=20, curves=5)
    assert max(point[0] for point in long) > max(point[0] for point in short)


def test_flat_spring_outline_supports_even_curve_counts():
    points = flat_spring_outline(length=32, width=20, curves=4)
    assert all(point[2] == 0.0 for point in points)
    assert max(point[1] for point in points) > 25
