"""gear_generator.py
──────────────────
Parametric gear / roller generator for the Tanuki DSL.

Supports three tooth-profile families:

  ``sinusoidal_profile``  — Smooth sine wave; both peaks and valleys
                            displace radially.  Used for bellows / accordion
                            rollers that mesh by rotating half a tooth pitch.

  ``trapezoidal_profile`` — Clamped sinusoid that approximates involute teeth
                            with flat tops and rounded root fillets.  Good for
                            3-D-printed spur and helical gears.

  ``apply_helix``         — Wraps any profile function with a Z-dependent
                            angular offset to produce a helical tooth.

Top-level builders
──────────────────
  ``spur_gear``           Standard ISO spur gear (trapezoidal + round/hex hole).
  ``helical_gear``        Spur profile with a helix twist along the face width.
  ``sinusoidal_roller``   Bellows / accordion roller (sine + axial bevel).

Pair helpers
────────────
  ``spur_gear_pair``          Two mating spur gears at the correct centre distance.
  ``sinusoidal_roller_pair``   Two identical rollers offset by one half tooth pitch.

All builders return an ``IRNode`` ready to be wrapped in a model context and
compiled to a Blender Geometry Nodes script.

Conventions
───────────
* Dimensions in millimetres.
* Module follows ISO 21771 (module = pitch_diameter / n_teeth).
* Gear axis is Z.  XY is the cross-section plane.
* All angles in degrees unless stated otherwise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from tanuki.dsl import (
    cylinder, cube, intersect, difference,
    translate, rotate,
    position,
    vec_dot, vec_multiply, vec_scale,
    math_add, math_subtract, math_multiply, math_divide,
    math_minimum, math_maximum, math_sin, math_arcsin,
    math_arctan2,
    math_power, math_absolute, math_greater_than, math_less_than,
)
from tanuki.ir.nodes import IRGeometryOp, IRNode, IRValue, IRVector


# ─── Data types ───────────────────────────────────────────────────────────────

@dataclass
class GearBody:
    """Physical dimensions shared by all gear builders.

    Attributes
    ----------
    pitch_diameter : float
        Diameter of the pitch circle (mm) — the reference circle where gear
        teeth have the nominal spacing.  Equal to ``module × n_teeth``.
    width : float
        Face width (axial length) in mm.
    hole_d : float
        Through-hole diameter for a round axle hole.  ``0`` = no hole.
    segments : int
        Angular vertex count for the base cylinder.  Higher = smoother profile.
    side_segments : int
        Axial ring count.  > 1 is required for helical gears and bevelled
        sinusoidal rollers so the vertex density is sufficient.
    tolerance : float
        Radial clearance subtracted from the addendum to provide backlash.
    """
    pitch_diameter: float
    width: float
    hole_d: float = 0.0
    segments: int = 128
    side_segments: int = 1
    tolerance: float = 0.0


@dataclass
class BevelParams:
    """Axial amplitude taper at both ends of a sinusoidal roller.

    The amplitude is held constant in the flat centre section and ramps
    linearly from ``amplitude`` down to ``amplitude − depth`` over the last
    ``length`` mm at each end.

    Attributes
    ----------
    depth : float
        Amplitude reduction at each edge (mm).  ``0`` disables the bevel.
    length : float
        Axial extent of the taper ramp (mm).
    """
    depth: float = 0.0
    length: float = 0.0


@dataclass
class HelixParams:
    """Helix configuration for helical gears.

    Attributes
    ----------
    angle_deg : float
        Helix angle measured from the gear axis in degrees.  ``0`` produces
        a standard spur gear.  Typical values: 15–30°.
    direction : int
        ``+1`` for a right-hand helix, ``-1`` for left-hand.
    """
    angle_deg: float = 0.0
    direction: int = 1


# ─── Private field helpers ────────────────────────────────────────────────────

def _xy_angle() -> IRNode:
    """Circumferential angle of the current vertex: ``atan2(y, x)``."""
    pos = position()
    px  = vec_dot(pos, IRVector(value=(1.0, 0.0, 0.0), label="x_axis"))
    py  = vec_dot(pos, IRVector(value=(0.0, 1.0, 0.0), label="y_axis"))
    return math_arctan2(py, px)


def _z_field() -> IRNode:
    """Z coordinate of the current vertex."""
    return vec_dot(position(), IRVector(value=(0.0, 0.0, 1.0), label="z_axis"))


# ─── Private profile-from-angle helpers ──────────────────────────────────────

def _sinusoidal_from_angle(
    angle: IRNode,
    n_teeth: int,
    amplitude: float,
) -> IRNode:
    """Sinusoidal radial displacement: ``amplitude * sin(n_teeth * angle)``."""
    wave_angle = math_multiply(angle, IRValue(value=float(n_teeth), label="n_teeth"))
    return math_multiply(math_sin(wave_angle), IRValue(value=amplitude, label="amplitude"))


def _trapezoidal_from_angle(
    angle: IRNode,
    n_teeth: int,
    addendum: float,
    dedendum: float,
    sharpness: float,
) -> IRNode:
    """Trapezoidal (flat-top) radial displacement from a pre-computed angle.

    Computes ``clamp(sin(n*θ) * sharpness, −1, +1)`` and then maps the
    clamped value to ``[−dedendum, +addendum]``.
    """
    wave_angle = math_multiply(angle, IRValue(value=float(n_teeth), label="n_teeth"))
    wave       = math_sin(wave_angle)
    amplified  = math_multiply(wave, IRValue(value=sharpness, label="sharpness"))
    clamped    = math_maximum(
        IRValue(value=-1.0, label="neg_one"),
        math_minimum(IRValue(value=1.0, label="pos_one"), amplified),
    )
    # map [−1, +1] → [−dedendum, +addendum]
    t       = math_multiply(
        math_add(clamped, IRValue(value=1.0, label="one")),
        IRValue(value=0.5, label="half"),
    )
    tooth_h = addendum + dedendum
    return math_subtract(
        math_multiply(t, IRValue(value=tooth_h, label="tooth_h")),
        IRValue(value=dedendum, label="dedendum"),
    )


# ─── Public profile functions ─────────────────────────────────────────────────

def sinusoidal_profile(n_teeth: int, amplitude: float) -> IRNode:
    """Full sine-wave displacement: ``amplitude * sin(n_teeth * θ)``.

    Both peaks and valleys displace radially.  Two identical rollers mesh
    when one is rotated half a tooth pitch (``180 / n_teeth`` degrees).

    Parameters
    ----------
    n_teeth : int
        Number of crests around the circumference.
    amplitude : float
        Semi-amplitude in mm.  Peak-to-peak variation = ``2 × amplitude``.
    """
    return _sinusoidal_from_angle(_xy_angle(), n_teeth, amplitude)


def trapezoidal_profile(
    n_teeth: int,
    addendum: float,
    dedendum: float,
    sharpness: float = 3.0,
) -> IRNode:
    """Flat-top teeth via clamped sinusoid — approximates involute geometry.

    Maps ``sin(n_teeth * θ)`` through a clamp so the profile has flat tooth
    tops and rounded root fillets.  The sharpness parameter controls the
    flatness: higher values give wider flat tops and narrower transition zones.

    Parameters
    ----------
    n_teeth : int
        Number of teeth.
    addendum : float
        Height of tooth tip above the pitch circle (mm).
        Standard: ``1 × module``.
    dedendum : float
        Depth of tooth root below the pitch circle (mm).
        Standard: ``1.25 × module``.
    sharpness : float
        Amplification factor before clamping.  ``1.0`` gives a pure sine
        (no flat tops).  ``3.0``–``4.0`` is typical for 3-D-printed gears.
    """
    return _trapezoidal_from_angle(_xy_angle(), n_teeth, addendum, dedendum, sharpness)


# ─── Modifiers ────────────────────────────────────────────────────────────────

def apply_bevel(
    profile: IRNode,
    length: float,
    bevel_length: float,
) -> IRNode:
    """Multiply *profile* by a linear [0 → 1] ramp at both axial ends.

    The profile amplitude tapers to **zero** at each end, transitioning from
    full amplitude at distance *bevel_length* from each edge inward.

    This is useful when the gear face must clear adjacent components.  For
    a bellows-style partial taper (amplitude stays > 0 at the edge) use
    ``sinusoidal_roller`` which computes the envelope internally.

    Parameters
    ----------
    profile : IRNode
        Scalar displacement field.
    length : float
        Total axial length in mm.
    bevel_length : float
        Length of the taper ramp at each end in mm.  Clamped to ``length/2``.
    """
    blen_eff = min(bevel_length, length / 2)
    if blen_eff == 0.0:
        return profile

    z0        = math_add(_z_field(), IRValue(value=length / 2, label="z_shift"))
    z_far     = math_subtract(IRValue(value=length, label="length"), z0)
    dist_edge = math_minimum(z0, z_far)
    ramp_raw  = math_divide(dist_edge, IRValue(value=blen_eff, label="blen_eff"))
    ramp      = math_minimum(IRValue(value=1.0, label="one"), ramp_raw)
    return math_multiply(profile, ramp)


def apply_helix(
    profile_fn,
    pitch_radius: float,
    helix: HelixParams,
) -> IRNode:
    """Evaluate *profile_fn* with a Z-dependent helix angle offset.

    The effective angle fed to *profile_fn* is:

    .. math::

       \\theta_{\\text{eff}} = \\theta + \\text{direction} \\times
       \\frac{\\tan(\\text{angle\\_deg})}{r_{\\text{pitch}}} \\times z

    Parameters
    ----------
    profile_fn : callable
        Signature ``(angle: IRNode) -> IRNode``.  Use the private
        ``_sinusoidal_from_angle`` / ``_trapezoidal_from_angle`` helpers.
    pitch_radius : float
        Pitch circle radius in mm, used to compute the helix rate.
    helix : HelixParams
        Helix angle and direction.
    """
    if helix.angle_deg == 0.0:
        return profile_fn(_xy_angle())

    rate  = (
        math.tan(math.radians(abs(helix.angle_deg)))
        / pitch_radius
        * float(helix.direction)
    )
    angle = math_add(
        _xy_angle(),
        math_multiply(_z_field(), IRValue(value=rate, label="helix_rate")),
    )
    return profile_fn(angle)


# ─── Radial displacement applier ─────────────────────────────────────────────

def _apply_radial_displacement(
    base: IRNode,
    profile: IRNode,
    pitch_radius: float,
    label: str = "displaced",
) -> IRNode:
    """Apply a scalar radial displacement field to a base cylinder.

    Builds a ``GeometryNodeSetPosition`` node whose *Offset* socket receives
    ``unit_radial × profile``, where ``unit_radial`` is the normalised XY
    position vector of each vertex.

    Parameters
    ----------
    base : IRNode
        Base cylinder (centred at origin, axis = Z).
    profile : IRNode
        Per-vertex scalar displacement (positive = outward).
    pitch_radius : float
        Radius of *base*; used to normalise the radial direction.
    label : str
        IR node label.
    """
    pos_xy      = vec_multiply(
        position(),
        IRVector(value=(1.0, 1.0, 0.0), label="xy_mask"),
    )
    unit_radial = vec_scale(pos_xy, IRValue(value=1.0 / pitch_radius, label="r_inv"))
    offset      = vec_scale(unit_radial, profile)
    return IRGeometryOp(
        op_type="GeometryNodeSetPosition",
        child=base,
        properties={},
        extra_children={"Offset": offset},
        label=label,
    )


# ─── Hole cutters ─────────────────────────────────────────────────────────────

def round_hole(
    diameter: float,
    gear_width: float,
    *,
    label: str = "axle_hole",
) -> IRNode:
    """Cylindrical axle hole for boolean subtraction.

    The hole is 4 mm taller than the gear so it cleanly breaks both faces
    in a Mesh Boolean operation.

    Parameters
    ----------
    diameter : float
        Hole diameter in mm.
    gear_width : float
        Axial length of the gear in mm.
    label : str
        IR node label.
    """
    return cylinder(diameter / 2, gear_width + 4, label, vertices=64)


def hex_hole(
    across_flats: float,
    gear_width: float,
    *,
    tolerance: float = 0.1,
    label: str = "hex_hole",
) -> IRNode:
    """Regular hexagonal shaft hole via intersection of three rectangular slabs.

    A regular hexagon is the intersection of three infinite slabs at 0°, 60°
    and 120°.  Each slab has width ``across_flats + 2 × tolerance``; their
    intersection through the gear axle produces a prismatic hex cutout.

    Parameters
    ----------
    across_flats : float
        Distance between parallel faces (wrench size) in mm.
        ISO standard: M3 → 5.5 mm, M5 → 8 mm, M8 → 13 mm.
    gear_width : float
        Axial gear length in mm.  Hole is 4 mm taller.
    tolerance : float
        Clearance added to each side of the hex (mm).
    label : str
        IR node label prefix.
    """
    af   = across_flats + 2.0 * tolerance
    tall = af * 20.0          # extends well beyond any gear radius
    slab = cube(af, tall, gear_width + 4, label)
    return intersect([
        slab,
        slab | rotate(0, 0, 60),
        slab | rotate(0, 0, 120),
    ])


# ─── Top-level gear builders ──────────────────────────────────────────────────

def spur_gear(
    module: float,
    n_teeth: int,
    width: float,
    *,
    sharpness: float = 3.0,
    hole_d: float = 0.0,
    hex_flats: float = 0.0,
    hex_tolerance: float = 0.1,
    segments: int | None = None,
    side_segments: int = 1,
    tolerance: float = 0.0,
    label: str = "spur_gear",
) -> IRNode:
    """Standard spur gear with trapezoidal tooth profile (ISO 21771).

    Geometry follows the module system:

    =========== ==============================
    Pitch dia.  ``module × n_teeth``
    Addendum    ``module`` (tip above pitch ⌀)
    Dedendum    ``1.25 × module`` (root depth)
    Tip dia.    ``(n_teeth + 2) × module``
    Root dia.   ``(n_teeth − 2.5) × module``
    =========== ==============================

    Parameters
    ----------
    module : float
        Gear module in mm.  Common values: 1, 1.5, 2, 2.5, 3.
    n_teeth : int
        Number of teeth (must be ≥ 2).
    width : float
        Face width (axial length) in mm.
    sharpness : float
        Flatness of tooth tops (see ``trapezoidal_profile``).  3–4 is typical.
    hole_d : float
        Round axle hole diameter in mm.  Ignored when ``hex_flats > 0``.
    hex_flats : float
        Hex shaft hole across-flats in mm.  Takes priority over ``hole_d``
        when > 0.
    hex_tolerance : float
        Clearance for hex hole fit (mm, added to each side).
    segments : int | None
        Angular vertex count.  Defaults to ``max(64, n_teeth × 8)``.
    side_segments : int
        Axial ring count.  > 1 not normally needed for spur gears.
    tolerance : float
        Radial clearance subtracted from addendum (mm).  Use when the gear
        will mesh with a partner built from identical parameters.
    label : str
        IR node label prefix.
    """
    r_pitch  = module * n_teeth / 2.0
    addendum = module - tolerance
    dedendum = 1.25 * module

    if segments is None:
        segments = max(64, n_teeth * 8)

    base    = cylinder(r_pitch, width, f"{label}_base",
                       vertices=segments, side_segments=side_segments)
    profile = trapezoidal_profile(n_teeth, addendum, dedendum, sharpness)
    gear    = _apply_radial_displacement(base, profile, r_pitch, label=f"{label}_displaced")

    if hex_flats > 0:
        return difference(gear, [hex_hole(hex_flats, width,
                                         tolerance=hex_tolerance,
                                         label=f"{label}_hex")])
    if hole_d > 0:
        return difference(gear, [round_hole(hole_d, width, label=f"{label}_axle")])
    return gear


def helical_gear(
    module: float,
    n_teeth: int,
    width: float,
    *,
    helix_angle_deg: float = 20.0,
    helix_direction: int = 1,
    sharpness: float = 3.0,
    hole_d: float = 0.0,
    hex_flats: float = 0.0,
    hex_tolerance: float = 0.1,
    segments: int | None = None,
    side_segments: int | None = None,
    tolerance: float = 0.0,
    label: str = "helical_gear",
) -> IRNode:
    """Helical gear — trapezoidal profile with an axial helix twist.

    The normal module is treated as the transverse module for simplicity.
    For true helical gearing the normal module is related to the transverse
    module by ``m_n = m_t × cos(helix_angle)``.

    A mating pair must use opposite helix directions (one +1, one −1).

    Parameters
    ----------
    module : float
        Transverse module in mm.
    n_teeth : int
    width : float
        Face width in mm.  Wider = more helix overlap contact.
    helix_angle_deg : float
        Helix angle from the gear axis in degrees.  Typical: 15–30°.
    helix_direction : int
        ``+1`` right-hand (standard), ``-1`` left-hand.
    (remaining params identical to ``spur_gear``)
    """
    r_pitch  = module * n_teeth / 2.0
    addendum = module - tolerance
    dedendum = 1.25 * module

    if segments is None:
        segments = max(64, n_teeth * 8)
    if side_segments is None:
        # Ensure enough axial rings to resolve the helix twist.
        side_segments = max(16, int(width / module) * 2)

    helix = HelixParams(angle_deg=helix_angle_deg, direction=helix_direction)

    def _profile_fn(angle: IRNode) -> IRNode:
        return _trapezoidal_from_angle(angle, n_teeth, addendum, dedendum, sharpness)

    profile = apply_helix(_profile_fn, r_pitch, helix)
    base    = cylinder(r_pitch, width, f"{label}_base",
                       vertices=segments, side_segments=side_segments)
    gear    = _apply_radial_displacement(base, profile, r_pitch, label=f"{label}_displaced")

    if hex_flats > 0:
        return difference(gear, [hex_hole(hex_flats, width,
                                         tolerance=hex_tolerance,
                                         label=f"{label}_hex")])
    if hole_d > 0:
        return difference(gear, [round_hole(hole_d, width, label=f"{label}_axle")])
    return gear


def sinusoidal_roller(
    n_teeth: int,
    d_base: float,
    amplitude: float,
    length: float,
    *,
    tooth_shape: str = "sine",
    tooth_power: float = 1.0,
    bevel_depth: float = 0.0,
    bevel_length: float = 0.0,
    hole_d: float = 0.0,
    segments: int | None = None,
    side_segments: int | None = None,
    tolerance: float = 0.0,
    label: str = "roller",
) -> IRNode:
    """Sinusoidal roller for camera bellows / accordion and peristaltic drives.

    The cross-section is a full sine wave: displacement = A × sin(N × θ).
    Both peaks and valleys contribute to the coupling — two identical rollers
    mesh when one is rotated ``180 / n_teeth`` degrees.

    An axial *bevel* linearly tapers the amplitude near each face so the
    rollers mesh cleanly at their ends without corner interference.

    Parameters
    ----------
    n_teeth : int
        Number of wave crests around the circumference.
    d_base : float
        Base (pitch) diameter in mm.
    amplitude : float
        Semi-amplitude in mm.  Peak-to-peak = ``2 × amplitude``.
    length : float
        Axial length of the roller in mm.
    bevel_depth : float
        Amplitude reduction at each axial end in mm.  The amplitude at the
        very edge is ``amplitude − bevel_depth``.  ``0`` = flat, no bevel.
    bevel_length : float
        Axial extent of the taper ramp at each end in mm.
    hole_d : float
        Axle hole diameter in mm.  ``0`` = no hole.
    segments : int | None
        Angular vertex count.  Defaults to ``max(64, n_teeth × 40)`` for
        smooth sine wave resolution.
    tooth_shape : str
        Wave shape for the tooth cross-section profile:

        ``"sine"``        — Smooth sinusoidal wave (default).
        ``"triangular"``  — Linear flanks with sharp tips and valleys.
                            Implemented as ``(2/π) × arcsin(sin(Nθ))``.
                            Produces a true V/Λ tooth — each tooth is a
                            triangle and each valley is an inverted triangle.
        ``"powered"``     — ``sign(sin) × |sin|^tooth_power``; controlled
                            base width via the *tooth_power* exponent.

    tooth_power : float
        Shape exponent used only when ``tooth_shape="powered"``.  ``1.0`` =
        sine, > 1 widens base, < 1 flattens tip.
    side_segments : int | None
        Axial ring count.  Auto-selected to resolve the bevel when
        ``bevel_length > 0``.
    tolerance : float
        Radial clearance subtracted from amplitude (mm).
    label : str
        IR node label prefix.
    """
    r_base = d_base / 2.0
    eff_amp = amplitude - tolerance

    if segments is None:
        segments = max(64, n_teeth * 40)
    if side_segments is None:
        side_segments = max(16, int(length * 4)) if bevel_length > 0 else 1

    # ── Build the amplitude envelope field ───────────────────────────────────
    blen_eff   = min(bevel_length, length / 2.0)
    amp_border = max(0.0, eff_amp - bevel_depth)
    amp_range  = eff_amp - amp_border

    angle      = _xy_angle()
    wave_angle = math_multiply(angle, IRValue(value=float(n_teeth), label="n_teeth"))
    raw_wave   = math_sin(wave_angle)

    if tooth_shape == "triangular":
        # triangle wave: (2/π) × arcsin(sin(Nθ))
        # arcsin(sin(x)) ∈ [-π/2, +π/2]; ×(2/π) normalises to [-1, +1]
        # Result: V-shaped teeth with perfectly linear flanks and sharp tips+valleys.
        wave = math_multiply(
            math_arcsin(raw_wave),
            IRValue(value=2.0 / math.pi, label="two_over_pi"),
        )
    elif tooth_shape == "powered" and tooth_power != 1.0:
        # sign(sin) × |sin|^p  — widens base (p>1) or flattens tip (p<1)
        sign = math_subtract(
            math_greater_than(raw_wave, IRValue(value=0.0, label="zero_gt")),
            math_less_than(raw_wave, IRValue(value=0.0, label="zero_lt")),
        )
        wave = math_multiply(
            sign,
            math_power(
                math_absolute(raw_wave),
                IRValue(value=float(tooth_power), label="tooth_power"),
            ),
        )
    else:
        wave = raw_wave

    if blen_eff > 0.0 and amp_range > 0.0:
        z0        = math_add(_z_field(), IRValue(value=length / 2.0, label="z_shift"))
        z_far     = math_subtract(IRValue(value=length, label="length"), z0)
        dist_edge = math_minimum(z0, z_far)
        ramp_raw  = math_divide(dist_edge, IRValue(value=blen_eff, label="blen_eff"))
        ramp      = math_minimum(IRValue(value=1.0, label="one"), ramp_raw)
        envelope  = math_add(
            IRValue(value=amp_border, label="amp_border"),
            math_multiply(IRValue(value=amp_range, label="amp_range"), ramp),
        )
    else:
        envelope = IRValue(value=eff_amp, label="amplitude")

    profile = math_multiply(wave, envelope)

    # ── Assemble gear ─────────────────────────────────────────────────────────
    base   = cylinder(r_base, length, f"{label}_base",
                      vertices=segments, side_segments=side_segments)
    roller = _apply_radial_displacement(base, profile, r_base, label=f"{label}_displaced")

    if hole_d > 0:
        return difference(roller, [round_hole(hole_d, length, label=f"{label}_axle")])
    return roller


# ─── Pair builders ────────────────────────────────────────────────────────────

def spur_gear_pair(
    module: float,
    n_teeth_a: int,
    n_teeth_b: int,
    width: float,
    *,
    hole_d_a: float = 0.0,
    hole_d_b: float = 0.0,
    hex_flats_a: float = 0.0,
    hex_flats_b: float = 0.0,
    sharpness: float = 3.0,
    segments: int | None = None,
    side_segments: int = 1,
    tolerance: float = 0.1,
    label: str = "spur_pair",
) -> tuple[IRNode, IRNode]:
    """Two mating spur gears positioned at the correct centre distance.

    Gear A is placed at the origin.  Gear B is translated along the Y axis
    by the standard centre distance and rotated by half a tooth pitch so
    the teeth interleave.

    Centre distance = ``module × (n_teeth_a + n_teeth_b) / 2``

    Parameters
    ----------
    module : float
    n_teeth_a, n_teeth_b : int
        Tooth counts for each gear.
    width : float
        Face width (both gears use the same width).
    hole_d_a, hole_d_b : float
        Axle hole diameters for each gear.
    hex_flats_a, hex_flats_b : float
        Hex shaft holes (overrides round holes when > 0).
    sharpness, segments, side_segments : float / int
        Passed to :func:`spur_gear`.
    tolerance : float
        Addendum clearance on gear B to provide backlash.
    label : str
        IR node label prefix.
    """
    r_a           = module * n_teeth_a / 2.0
    r_b           = module * n_teeth_b / 2.0
    centre_dist   = r_a + r_b
    half_pitch_b  = 180.0 / n_teeth_b   # degrees, interleaves teeth

    gear_a = spur_gear(
        module, n_teeth_a, width,
        hole_d=hole_d_a, hex_flats=hex_flats_a,
        sharpness=sharpness, segments=segments, side_segments=side_segments,
        label=f"{label}_a",
    )
    gear_b = (
        spur_gear(
            module, n_teeth_b, width,
            hole_d=hole_d_b, hex_flats=hex_flats_b,
            sharpness=sharpness, segments=segments, side_segments=side_segments,
            tolerance=tolerance,
            label=f"{label}_b",
        )
        | translate(0, centre_dist, 0)
        | rotate(0, 0, half_pitch_b)
    )
    return gear_a, gear_b


def sinusoidal_roller_pair(
    n_teeth: int,
    d_base: float,
    amplitude: float,
    length: float,
    *,
    tooth_shape: str = "sine",
    tooth_power: float = 1.0,
    bevel_depth: float = 0.0,
    bevel_length: float = 0.0,
    hole_d: float = 0.0,
    segments: int | None = None,
    side_segments: int | None = None,
    tolerance: float = 0.2,
    label: str = "roller_pair",
) -> tuple[IRNode, IRNode]:
    """Two identical sinusoidal rollers positioned for mesh engagement.

    The centre-to-centre distance equals ``d_base + 2 × tolerance`` (the
    rollers touch at the amplitude peaks with the given clearance).  Roller B
    is rotated by ``180 / n_teeth`` degrees so its peaks align with roller A's
    valleys.

    Parameters
    ----------
    (all parameters are forwarded to :func:`sinusoidal_roller`)
    tolerance : float
        Radial clearance between mating rollers (mm).
    """
    centre_dist    = d_base + 2.0 * tolerance
    half_pitch_deg = 180.0 / n_teeth

    roller_a = sinusoidal_roller(
        n_teeth, d_base, amplitude, length,
        tooth_shape=tooth_shape, tooth_power=tooth_power,
        bevel_depth=bevel_depth, bevel_length=bevel_length,
        hole_d=hole_d, segments=segments, side_segments=side_segments,
        tolerance=0.0,
        label=f"{label}_a",
    )
    roller_b = (
        sinusoidal_roller(
            n_teeth, d_base, amplitude, length,
            tooth_shape=tooth_shape, tooth_power=tooth_power,
            bevel_depth=bevel_depth, bevel_length=bevel_length,
            hole_d=hole_d, segments=segments, side_segments=side_segments,
            tolerance=tolerance,
            label=f"{label}_b",
        )
        | translate(0, centre_dist, 0)
        | rotate(0, 0, half_pitch_deg)
    )
    return roller_a, roller_b
