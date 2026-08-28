"""Actuator bay packaging: what internal diameter do the canard servos actually need?

This is the model behind requirement R7. For direct-drive canards the servo is mounted
radially with its output shaft coincident with the canard shaft at the tube wall, so the
servo's *length* consumes tube radius. That is the constraint that rules out small tubes.

Servo dimensions and torques below are representative of widely used parts but are
APPROXIMATE -- replace with the datasheet values for the exact part you buy before
freezing the design.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Servo:
    name: str
    length: float  # m, along the output-shaft-perpendicular long axis
    width: float  # m, thickness (the dimension you stack circumferentially)
    height: float  # m, including output shaft boss
    mass: float  # kg
    stall_torque: float  # N*m at nominal voltage
    speed_60deg: float  # s per 60 deg, no load
    note: str = "APPROX - verify against datasheet"


# Size/torque *classes*, not specific products. Deliberately generic: quoting a part
# number here would imply a precision these numbers do not have. Once you shortlist real
# parts, replace these entries with datasheet values and rerun.
SERVOS: dict[str, Servo] = {
    "submicro": Servo("sub-micro class (~5 g)", 0.0200, 0.0086, 0.0200, 0.0050, 0.05, 0.11),
    "micro": Servo("micro class (~12 g)", 0.0236, 0.0116, 0.0240, 0.0120, 0.20, 0.14),
    "mini": Servo("mini class (~14 g)", 0.0228, 0.0125, 0.0226, 0.0140, 0.25, 0.10),
    "mini_ht": Servo("mini high-torque HV class (~20 g)", 0.0230, 0.0100, 0.0260, 0.0200, 0.55, 0.07),
    "standard": Servo("standard class (~55 g)", 0.0406, 0.0198, 0.0376, 0.0555, 1.00, 0.18),
    "standard_ht": Servo("standard high-torque HV class (~60 g)", 0.0403, 0.0202, 0.0366, 0.0600, 1.50, 0.08),
}


@dataclass
class BayLayout:
    """Result of a packaging check for one (tube, servo, arrangement) combination."""

    fits: bool
    required_id: float
    available_id: float
    margin: float
    arrangement: str
    reason: str

    def __str__(self) -> str:
        verdict = "FITS" if self.fits else "NO FIT"
        return (
            f"{verdict:6s} {self.arrangement:16s} "
            f"need ID {self.required_id * 1000:5.1f} mm, "
            f"have {self.available_id * 1000:5.1f} mm "
            f"({self.margin * 1000:+6.1f} mm)  {self.reason}"
        )


def check_direct_drive(
    inner_diameter: float,
    servo: Servo,
    n_canards: int = 4,
    hub_allowance: float = 0.008,
    liner_thickness: float = 0.0015,
    clearance: float = 0.003,
    pinwheel: bool = True,
) -> BayLayout:
    """Radially mounted servos, output shaft on the canard shaft at the wall.

    `hub_allowance` covers the canard shaft, its bearing/bushing block and the coupler
    between shaft and servo horn. `liner_thickness` is any coupler tube or sled wall.

    Two arrangements:
      - centred: all servos in one plane, each on a radial line. Inner ends must clear
        the axis by half a servo width, so required ID = 2*(L + hub + W/2).
      - pinwheel: servos offset tangentially so each inner end passes alongside its
        neighbour rather than meeting at the axis. Buys back roughly W/2 of radius.
    """
    usable_id = inner_diameter - 2.0 * liner_thickness
    radial_need = servo.length + hub_allowance + clearance
    if pinwheel:
        # Inner ends may reach the axis; the binding dimension becomes the corner radius.
        required_id = 2.0 * math.hypot(radial_need, servo.width / 2.0)
        arrangement = "direct/pinwheel"
    else:
        required_id = 2.0 * (radial_need + servo.width / 2.0)
        arrangement = "direct/centred"

    # Circumferential check: n servos of width W must fit around the bolt circle.
    bolt_circle = math.pi * max(usable_id - servo.height, 1e-6)
    circumferential_ok = n_canards * (servo.width + clearance) <= bolt_circle

    fits = required_id <= usable_id and circumferential_ok
    if not circumferential_ok:
        reason = f"{n_canards} servos will not fit around the circumference"
    elif fits:
        reason = "ok"
    else:
        reason = "servo too long for the radius"
    return BayLayout(fits, required_id, usable_id, usable_id - required_id, arrangement, reason)


def check_bellcrank(
    inner_diameter: float,
    servo: Servo,
    n_canards: int = 4,
    hub_allowance: float = 0.008,
    liner_thickness: float = 0.0015,
    clearance: float = 0.003,
) -> BayLayout:
    """Servos mounted axially (long axis parallel to the rocket axis) driving the canard
    shaft through a bellcrank or pushrod. Trades bay *length* and mechanical complexity
    (and backlash, which hurts a control loop) for a much smaller diameter requirement.
    """
    usable_id = inner_diameter - 2.0 * liner_thickness
    # Servo lies flat against the wall with its long axis fore-aft, so its *thickness*
    # sets radial depth and its *height* is what stacks around the circumference.
    required_id = 2.0 * (servo.width + hub_allowance + clearance)
    bolt_circle = math.pi * max(usable_id - servo.width, 1e-6)
    circumferential_ok = n_canards * (servo.height + clearance) <= bolt_circle
    fits = required_id <= usable_id and circumferential_ok
    reason = "ok" if fits else ("circumference" if not circumferential_ok else "radial depth")
    return BayLayout(fits, required_id, usable_id, usable_id - required_id, "bellcrank/axial", reason)


def hinge_moment(
    dynamic_pressure: float,
    panel_area: float,
    mean_chord: float,
    cn_alpha_panel: float,
    deflection_rad: float,
    hinge_frac: float = 0.30,
    cp_frac: float = 0.25,
) -> float:
    """Aerodynamic moment about the canard hinge line, N*m per panel.

    `hinge_frac` and `cp_frac` are fractions of the mean chord aft of the panel leading
    edge. Putting the hinge line at or just aft of the panel centre of pressure makes the
    hinge moment small, which is the single easiest way to make the servo requirement
    tractable. A hinge slightly aft of the CP is preferred: it makes the panel weakly
    self-centring rather than divergent.
    """
    normal_force = dynamic_pressure * panel_area * cn_alpha_panel * deflection_rad
    return abs(normal_force * (cp_frac - hinge_frac) * mean_chord)


def torque_margin(required: float, servo: Servo, gear_ratio: float = 1.0, derate: float = 0.4) -> float:
    """Ratio of available to required torque.

    `derate` accounts for the fact that stall torque is not usable torque: you need speed
    and stiffness at the operating point, not a stalled actuator. 0.4 is a reasonable
    starting assumption; measure your actual part.
    """
    available = servo.stall_torque * derate * gear_ratio
    return available / max(required, 1e-9)
