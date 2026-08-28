"""Fin flutter margin.

Flutter is the aeroelastic instability where a fin's bending and torsion modes couple and
extract energy from the airflow. Past the flutter speed the oscillation grows without
bound and the fin departs the rocket, usually taking the airframe with it. It is the
classic failure mode of a rocket with large, thin fins, and it is not captured anywhere in
a Barrowman analysis or in OpenRocket's simulation -- which is exactly why large fins look
free right up until they are not.

The standard high power estimate comes from NACA TN 4197 (Martin, 1958), in the form
popularised by Apogee's newsletter:

    V_f = a * sqrt( G / ( 1.337 * AR^3 * P * (lambda + 1) / ( 2 * (AR + 2) * (t/c)^3 ) ) )

Caveats worth stating plainly, because this number gets quoted with more confidence than
it deserves:

- It assumes an isotropic, uniform-thickness, solid panel. A layup with a foam or
  honeycomb core, or a plate with a taper in thickness, is not this.
- G, the shear modulus, is the weakest input. Published G10 values span roughly 3 to 7
  GPa depending on weave, resin fraction and orientation. The result scales as sqrt(G),
  so that range alone is a +/-25% band on V_f.
- It ignores the root attachment. A fin tab bonded through the wall to the motor mount
  behaves very differently from a surface-mounted fin, and the formula assumes an ideal
  rigid root.

Treat the output as a screening tool: a margin under about 1.5 means redesign, and a
margin over 2 means stop worrying. Anything between deserves a thicker fin or a stiffer
material rather than an argument.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import atmosphere
from .geometry import FinSet

# Shear modulus, Pa. Deliberately conservative picks within the published spread.
SHEAR_MODULUS = {
    "g10": 5.0e9,
    "carbon": 5.0e9,
    "birch_ply": 6.2e8,
    "basswood": 1.4e8,
}


@dataclass
class FlutterResult:
    flutter_speed: float  # m/s, true airspeed at the evaluated altitude
    flutter_mach: float
    max_speed: float  # m/s, worst case the vehicle actually sees
    margin: float  # flutter_speed / max_speed
    altitude: float
    aspect_ratio: float
    thickness_ratio: float

    @property
    def ok(self) -> bool:
        return self.margin >= 1.5


def flutter_speed(
    fins: FinSet,
    altitude: float,
    material: str = "g10",
    shear_modulus: float | None = None,
) -> tuple[float, float, float, float]:
    """Returns (flutter speed m/s, flutter Mach, aspect ratio, thickness ratio)."""
    g = shear_modulus if shear_modulus is not None else SHEAR_MODULUS[material]
    _, pressure, _, sound_speed = atmosphere.properties(altitude)

    # Panel aspect ratio, exposed semispan squared over exposed panel area.
    ar = fins.semispan**2 / fins.planform_area_single
    taper = fins.tip_chord / fins.root_chord
    # Thickness ratio on the root chord. Using the root rather than the mean chord gives
    # the smaller t/c and therefore the lower, conservative flutter speed.
    tc = fins.thickness / fins.root_chord

    denominator = (1.337 * ar**3 * pressure * (taper + 1.0)) / (2.0 * (ar + 2.0) * tc**3)
    v_f = sound_speed * math.sqrt(g / denominator)
    return v_f, v_f / sound_speed, ar, tc


def evaluate(
    fins: FinSet,
    max_speed: float,
    altitude: float,
    material: str = "g10",
    shear_modulus: float | None = None,
) -> FlutterResult:
    """Flutter margin against the worst speed the vehicle sees.

    Evaluate at low altitude: flutter speed rises with altitude because it scales as
    1/sqrt(P), so the dangerous condition is high speed low down, not max speed at apogee.
    """
    v_f, m_f, ar, tc = flutter_speed(fins, altitude, material, shear_modulus)
    return FlutterResult(
        flutter_speed=v_f,
        flutter_mach=m_f,
        max_speed=max_speed,
        margin=v_f / max_speed if max_speed > 0 else float("inf"),
        altitude=altitude,
        aspect_ratio=ar,
        thickness_ratio=tc,
    )


def required_thickness(
    fins: FinSet,
    max_speed: float,
    altitude: float,
    target_margin: float = 1.5,
    material: str = "g10",
    shear_modulus: float | None = None,
) -> float:
    """Fin thickness needed to reach `target_margin`. V_f scales as (t/c)^1.5."""
    result = evaluate(fins, max_speed, altitude, material, shear_modulus)
    if result.margin <= 0:
        return float("inf")
    return fins.thickness * (target_margin / result.margin) ** (2.0 / 3.0)
