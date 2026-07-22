"""Sinusoidal bellows cog / roller for camera bellows and accordions.

Parameters
----------
N_TEETH     : int    — crests around the circumference (default 14)
D_BASE      : float  — base diameter in mm (default 60)
AMPLITUDE   : float  — semi-amplitude; peak-to-peak = 2 × amplitude (default 25)
LENGTH      : float  — total axial length in mm (default 60)
BEVEL_DEPTH : float  — amplitude reduction at each axial edge (mm; 0 = no bevel)
BEVEL_LEN   : float  — axial length of the linear taper ramp (mm)
HOLE_D      : float  — central axle hole diameter (mm)
TOLERANCE   : float  — radial clearance between mating rollers (mm)

Print notes
-----------
Material   : PETG or ABS
Orientation: axial (Z), no supports required
Infill     : 40–60 %, gyroid
Perimeters : ≥ 3
Layer      : 0.15–0.20 mm
"""

from tanuki.dsl import join, model, output

try:
    from ..utils import sinusoidal_roller, sinusoidal_roller_pair
except ImportError:  # pragma: no cover - allows direct script execution
    from print_labo.utils import sinusoidal_roller, sinusoidal_roller_pair

# ── Parameters ───────────────────────────────────────────────────────────────
# Amplitude should be ~10–15 % of the base radius so the profile looks like
# a wave roller rather than a flower.  At D_BASE=30 mm, r=15 mm → amplitude
# of 2.5 mm is 17 % of r — enough grip without distorting the cylinder.
N_TEETH     = 18       # fewer teeth → wider, rounder waves (bellows pleats)
D_BASE      = 30.0     # mm — base diameter (compact roller for camera bellows)
AMPLITUDE   = 2.5      # mm — semi-amplitude ≈ 17 % of r (wave, not petals)
LENGTH      = 50.0     # mm — axial length matching typical bellows width
BEVEL_DEPTH = 5      # mm — gentle taper at each end
BEVEL_LEN   = 5      # mm — axial length of the taper ramp
HOLE_D      = 5.0      # mm — M5 shaft
TOLERANCE   = 0.15     # mm — radial clearance for mating rollers
TOOTH_POWER = 1.0      # used only with tooth_shape="powered"
TOOTH_SHAPE = "triangular"  # "sine" | "triangular" | "powered"


def create_bellows_cog():
    """Single sinusoidal bellows roller with central axle hole."""
    with model("bellows_cog") as ctx:
        output(sinusoidal_roller(
            N_TEETH, D_BASE, AMPLITUDE, LENGTH,
            tooth_shape=TOOTH_SHAPE, tooth_power=TOOTH_POWER,
            bevel_depth=BEVEL_DEPTH, bevel_length=BEVEL_LEN,
            hole_d=HOLE_D, tolerance=TOLERANCE,
            label="bellows_cog",
        ))
    return ctx.graph


def create_bellows_cog_pair():
    """Mating pair of bellows rollers positioned at the correct centre distance."""
    with model("bellows_cog_pair") as ctx:
        roller_a, roller_b = sinusoidal_roller_pair(
            N_TEETH, D_BASE, AMPLITUDE, LENGTH,
            tooth_shape=TOOTH_SHAPE, tooth_power=TOOTH_POWER,
            bevel_depth=BEVEL_DEPTH, bevel_length=BEVEL_LEN,
            hole_d=HOLE_D, tolerance=TOLERANCE,
            label="bellows_pair",
        )
        output(join([roller_a, roller_b]))
    return ctx.graph


ALL_PARTS = [create_bellows_cog, create_bellows_cog_pair]


if __name__ == "__main__":
    import argparse
    from tanuki.dsl.export import combined_export, individual_export

    parser = argparse.ArgumentParser(description="Compile bellows_cog parts")
    parser.add_argument(
        "--mode", choices=["combined", "individual"], default="combined"
    )
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.mode == "combined":
        out = args.output or "bellows_cog_gen.py"
        path = combined_export(ALL_PARTS, out)
        print(f"Generated {len(ALL_PARTS)} parts → {path}")
    else:
        out = args.output or "bellows_cog_gen"
        written = individual_export(ALL_PARTS, out)
        print(f"Generated {len(written)} files → {out}/")
