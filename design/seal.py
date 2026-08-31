"""The aft gas seal: the canard module's pressure boundary against the recovery bay.

THE PART THAT HAS BEEN CALLED A SEAL FOR SIX MONTHS AND IS NOT ONE.

`docs/05` has carried "the aft gas seal -- a bulkhead between this module and the recovery
bay, sealing a bore this part deliberately leaves open for wiring. Never sized." since the
module was built. Reading that sentence, the part sounds like a gasket: something whose job
is to be gas-tight, sized by whether hot gas gets past it.

It is not. It is the surface the ejection charge pushes against to separate the airframe.
The whole deployment force -- pressure times the full 74.8 mm bore -- lands on this disc and
has to go into the canard module tube, and the main parachute's opening shock comes back
through the same disc a few seconds later. Naming it after its least demanding requirement
is exactly the error corrections 2 and 11 record: `hinge_moment()` was 0.0599 N m and the
hinge looked like a 9 g problem right up until somebody computed the panel NORMAL FORCE and
found 0.734 N m of bending at a bearing that did not exist.

So this module sizes the part against what it actually carries, in this order:

  1. THE STUCK-JOINT PRESSURE, which governs. See `EjectionCase` below and the long comment
     on `SEPARATION_FACTOR`. The design charge released into the packed compartment's FREE
     volume, with nothing moving, is about 7x the pressure that actually separates the
     joint. That case is not the nominal flight; it is what happens when the joint does not
     let go, and it is the case that decides how thick the disc is.
  2. THE MAIN'S OPENING SHOCK, through the harness U-bolt, as a point load on a plate.
  3. Gas tightness, which is real but is the easiest of the three -- and which matters for
     a reason that is not "hot gas is bad": see THE VENT PATH below.

WHAT DECIDES THE THICKNESS, stated plainly because it is the one idea in this file:
**the shear pins are the intended fuse, so the bulkhead has to be stronger than the fuse.**
A bulkhead sized for the separation pressure is sized for the load it sees when everything
works. Size it for the full charge instead and the pins are guaranteed to be the first thing
that gives, which is the failure you want. It costs two sheet sizes and about 23 g;
`scripts/seal_report.py` prints both thicknesses so the claim cannot go stale.

THE VENT PATH, and why the two open items in `docs/05` are one item.

`docs/05` lists the forward wiring pass-through and the aft gas seal as two separate open
items. They are the same decision seen from both ends. The canard module has to breathe --
a bay sealed at ground pressure carries about 15 kPa outward at apogee -- and it has exactly
two faces it could breathe through. It must not be the aft one, because the volume on the
other side of the aft face is where the ejection charge fires. So the module vents FORWARD,
through the wiring pass-through, into the nav bay, which is where the altimeter's static
ports already are.

That has a consequence nobody has written down: **the canard module's free volume becomes
part of the altimeter's static volume.** Two things follow, and both are checked below.
A leak past the aft seal does not merely put soot in the module; it puts ejection gas into
the pressure sense volume of the altimeter that fires the charges, mid-deployment. And the
nav bay's static ports are sized for the nav bay, which is now the wrong volume.

WHAT THIS MODULE DOES NOT DO.

  * It does not model the ejection transient. `ejection_pressure()` is the closed-volume gas
    law every hobby rocketry charge is sized with; the real event is a burn racing an
    expanding volume and a leak, and the honest statement is that the pressure lies between
    the two cases computed here. GROUND TEST IS THE ARBITER, twice, per docs/01 step 5.
  * It does not choose the recovery wiring architecture. It computes what each option costs
    and says which one fits; see `check_seal()`'s notes and docs/05.
  * It says nothing about the internal bulkhead inside the recovery bay, which is a
    `BULKHEAD_THICKNESS` allowance in `recovery.py` and nothing more. That part now needs
    the same treatment this one just got.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .materials import (
    G10_FLEXURAL, G10_INTERLAMINAR_SHEAR, G10_MODULUS, G10_POISSON,
    DATASHEET_CONFIDENCE_MARGIN,
)

# ---------------------------------------------------------------------------------------
# BLACK POWDER, as a gas generator.
#
# The ejection charge equation used across hobby rocketry is P = m R T / V with
#
#     R = 266 in lbf / (lbm degR)      T = 3307 degR
#
# and both numbers are quoted so consistently, in units so obsolete, that it is worth
# writing down what they mean. R looks far too small for a gas constant: 8314 / 40 g/mol is
# about 208 J/(kg K). It is small because it is stated PER UNIT OF CHARGE, and black powder
# is only about 57% gas by mass -- the rest condenses to potassium carbonate and sulphide
# smoke, which produces no pressure. So this R already carries the gas fraction, and the
# charge mass you weigh out is the mass you put in the formula.
#
# The conversion is done here rather than hardcoded so that it can be checked.
# ---------------------------------------------------------------------------------------
IN_LBF = 0.1129848  # J
LBM = 0.45359237  # kg
RANKINE = 5.0 / 9.0  # K

BP_GAS_CONSTANT = 266.0 * IN_LBF / (LBM * RANKINE)  # 119.3 J/(kg K)
BP_FLAME_TEMPERATURE = 3307.0 * RANKINE  # 1837 K

# ---------------------------------------------------------------------------------------
# SHEAR PINS -- the fuse.
#
# Single-shear strength of a nylon screw in a fibreglass joint. Vendor figures for 2-56
# nylon run 30-40 lbf and the spread is real: it depends on the pin's fit in its hole, on
# how much of the shank is in the shear plane, and on how hot the airframe got on the pad.
# 33 lbf is taken here and the number is deliberately not trusted to two digits -- what the
# design needs from it is a BAND, because the pins have to be weak enough for the charge to
# break and strong enough not to drag-separate, and both edges of that band matter.
# ---------------------------------------------------------------------------------------
SHEAR_PIN_STRENGTH = {  # N, single shear, per pin
    "2-56 nylon": 147.0,
    "4-40 nylon": 245.0,
    "M2 nylon": 130.0,
}

# Coupler friction plus whatever the paint and the tolerance stack contribute. This is an
# ALLOWANCE, not a measurement, and it is the least defensible number in this file: a joint
# that has been sanded loose contributes nearly nothing and one assembled with a fresh coat
# of paint can contribute more than the pins. It is here so that it is visible and so that
# a ground test can replace it, which is the only way it will ever be right.
JOINT_FRICTION_ALLOWANCE = 100.0  # N

# The charge is sized to deliver this multiple of the force needed to release the joint.
# 2.0 matches BEARING_MARGIN_REQUIRED and SHAFT_MARGIN_REQUIRED in hinge.py so that a
# marginal deployment is not quietly treated as better news than a marginal bearing.
SEPARATION_FACTOR = 2.0

# Required ratio of allowable to actual for the disc itself.
PLATE_MARGIN_REQUIRED = 2.0

# Stress concentration at the wire feed-through.
#
# 3.0 IS THE WRONG NUMBER HERE and it is the one everybody reaches for. Kt = 3.0 is the
# circular hole in a wide plate under IN-PLANE tension. This plate is in BENDING, where the
# through-thickness stress gradient relieves the hole and the classical result (Goodier) is
# about 1.8 for a thin plate, rising toward 3.0 only as the plate gets thick relative to the
# hole. 2.0 is taken: a little above the thin-plate value, because this disc is 4.8 mm
# against a 4.0 mm hole and so is not thin.
#
# This is not a licence to use a smaller number. It is the difference between a check that
# is conservative and one that is wrong in a way that hides a real result -- at Kt 3.0 the
# hole sizes the disc at 6.4 mm, and the extra sheet buys nothing that exists.
KT_HOLE_BENDING = 2.0

# G-10 sheet as it is actually sold. The panel laminate (corrections 15 and 16) is the
# precedent for keeping this list in the code: a stack of thicknesses that are not stocked
# is not a design, and finding that out at order time cost this project a redesign of the
# root joint. Metric and imperial sizes are both stocked; both are listed.
G10_SHEET_THICKNESS = [  # m
    0.0016, 0.0020, 0.0024, 0.0032, 0.0040, 0.0048, 0.0064,
]

# High-temperature RTV silicone, for potting the wire feed-through. The number that matters
# is not its strength -- it carries no load -- but its service temperature against a gas
# that leaves the charge at 1837 K. It survives because the event is ~100 ms and the disc
# in front of it is a thermal mass, which is an argument about WHICH FACE the potting goes
# on, not about the material. See `check_seal()`.
RTV_SERVICE_TEMPERATURE_C = 315.0


# ---------------------------------------------------------------------------------------
# Pressure
# ---------------------------------------------------------------------------------------
def ejection_pressure(charge_kg: float, volume_m3: float) -> float:
    """Gauge pressure from a black powder charge in a closed volume, Pa.

    Closed volume, no heat loss, all the gas released at once. Every one of those is
    optimistic in the direction of MORE pressure, which is the right direction for sizing
    a bulkhead and the wrong one for sizing a charge -- hence two call sites and two
    volumes. See `EjectionCase`.
    """
    if volume_m3 <= 0.0:
        raise ValueError("volume must be positive")
    return charge_kg * BP_GAS_CONSTANT * BP_FLAME_TEMPERATURE / volume_m3


def charge_for_pressure(pressure_pa: float, volume_m3: float) -> float:
    """Charge mass, kg, that develops `pressure_pa` in `volume_m3`. Inverse of the above."""
    return pressure_pa * volume_m3 / (BP_GAS_CONSTANT * BP_FLAME_TEMPERATURE)


@dataclass(frozen=True)
class Joint:
    """The pinned tube joint the charge has to open.

    `bore_diameter` is the airframe ID -- the charge pushes on the whole disc, not on the
    coupler's annulus, because the disc IS the piston.
    """

    bore_diameter: float  # m
    n_pins: int
    pin: str = "2-56 nylon"
    friction: float = JOINT_FRICTION_ALLOWANCE  # N

    @property
    def area(self) -> float:
        return math.pi * self.bore_diameter**2 / 4.0

    @property
    def pin_force(self) -> float:
        return self.n_pins * SHEAR_PIN_STRENGTH[self.pin]

    @property
    def release_force(self) -> float:
        """Force that actually opens the joint, N."""
        return self.pin_force + self.friction

    @property
    def release_pressure(self) -> float:
        """Pressure at which the joint lets go, Pa gauge."""
        return self.release_force / self.area

    @property
    def design_pressure(self) -> float:
        """What the charge is sized to deliver: release pressure with margin."""
        return SEPARATION_FACTOR * self.release_pressure


@dataclass(frozen=True)
class EjectionCase:
    """One (charge, volume) pair and the pressure it makes.

    THE TWO CASES, and why the second one is not paranoia.

    A charge is sized on the compartment's GEOMETRIC volume, because that is what every
    published rule of thumb does and what a ground test measures. It then fires into a
    compartment that is 85% full of parachute, so the gas actually has the FREE volume --
    here about a seventh of it. Both statements are true at once, and the difference between
    them is not a modelling error to be resolved. It is the reason ejection works: the
    pressure spikes, the pins go almost immediately, and the volume then grows faster than
    the burn can fill it.

    Unless it does not. If the joint is stuck -- paint, a swollen coupler, a shear pin hole
    drilled undersize -- the volume never grows and the full charge lands in the free volume
    with the disc holding it. That is the case this bulkhead is sized for, because the
    alternative is a bulkhead that fails before the fuse it is supposed to protect.
    """

    name: str
    charge: float  # kg
    volume: float  # m^3
    area: float  # m^2, the disc the pressure acts on

    @property
    def pressure(self) -> float:
        return ejection_pressure(self.charge, self.volume)

    @property
    def force(self) -> float:
        return self.pressure * self.area


def compartment_volumes(inner_diameter: float, packed_volume: float,
                        compartment_length: float) -> tuple[float, float]:
    """(geometric, free) volume of one packed compartment, m^3.

    `packed_volume` is the soft goods' own volume from `recovery.Compartment.volume`, and
    `compartment_length` the tube length `recovery.check_packing` gives them. The free
    volume is what is left, and it is small: the fill limit is on the LENGTH the canopy
    needs, not on how much gas can get around it.
    """
    area = math.pi * inner_diameter**2 / 4.0
    geometric = area * compartment_length
    return geometric, max(geometric - packed_volume, 0.0)


# ---------------------------------------------------------------------------------------
# The disc
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Bulkhead:
    """A flat circular plate bonded into the tube, loaded by pressure on one face.

    EDGE CONDITION IS THE MODELLING CHOICE THAT MATTERS and there is no honest way to pick
    it, so both are computed and the conservative one is used. A disc bonded into a tube
    with an epoxy fillet is somewhere between simply supported (free to rotate at the rim,
    stress peaks at the centre) and clamped (rim held, stress peaks at the rim and is 63%
    of the simply supported centre value). A real bonded joint is nearer clamped, and the
    fillet is exactly what makes it so -- but a fillet is a hand-laid thing and assuming it
    into the answer is how a joint reports a pass it has not earned (correction 15).

    So `stress()` returns the simply supported value. It is 1.6x the clamped one, it is the
    number the margins below use, and the clamped figure is reported alongside it as the
    best case rather than the design case.
    """

    bore_diameter: float  # m, the tube ID the disc is bonded into
    thickness: float  # m
    flexural_allowable: float = G10_FLEXURAL
    modulus: float = G10_MODULUS
    poisson: float = G10_POISSON
    bond_length: float = 0.0  # m, axial length of the glue line; 0 -> the disc edge itself

    @property
    def radius(self) -> float:
        return self.bore_diameter / 2.0

    @property
    def area(self) -> float:
        return math.pi * self.radius**2

    @property
    def mass(self) -> float:
        """kg, at the G-10 density the project has committed to."""
        return self.area * self.thickness * 1850.0

    def stress(self, pressure: float) -> float:
        """Peak bending stress, Pa. Simply supported edge, uniform pressure, centre."""
        return (3.0 * (3.0 + self.poisson) * pressure * self.radius**2
                / (8.0 * self.thickness**2))

    def stress_clamped(self, pressure: float) -> float:
        """Peak bending stress with a fully clamped edge, Pa. At the rim, not the centre."""
        return 3.0 * pressure * self.radius**2 / (4.0 * self.thickness**2)

    def deflection(self, pressure: float) -> float:
        """Centre deflection, m. Simply supported."""
        return (3.0 * pressure * self.radius**4 * (1.0 - self.poisson)
                * (5.0 + self.poisson)
                / (16.0 * self.modulus * self.thickness**3))

    def stress_at(self, pressure: float, r: float) -> float:
        """Radial bending stress at radius `r`, Pa. CLAMPED edge.

        Used only to PLACE the wire feed-through. A clamped plate's radial stress changes
        sign partway out, so there is a radius where it is genuinely zero -- see
        `quiet_radius()`. The margin at that radius is quoted from the simply supported
        case below, not from this one.
        """
        a = self.radius
        return (3.0 * pressure / (8.0 * self.thickness**2)) * (
            a**2 * (1.0 + self.poisson) - r**2 * (3.0 + self.poisson)
        )

    def quiet_radius(self) -> float:
        """Radius at which a clamped plate's radial bending stress passes through zero, m."""
        return self.radius * math.sqrt((1.0 + self.poisson) / (3.0 + self.poisson))

    def hole_field(self, pressure: float, r: float) -> float:
        """Worst in-plane bending stress at radius `r`, Pa. SIMPLY SUPPORTED, both directions.

        THIS IS THE FUNCTION THAT MOVED THE ANSWER, so it is worth saying why it exists.
        The first version of this file placed the feed-through at the radius where a CLAMPED
        plate's radial stress vanishes and then quoted the margin from that same clamped
        field -- which reported 15x. But the disc's own thickness is chosen from the simply
        supported case, on the grounds that assuming a fillet into the answer is how
        correction 15's joint reported 2.5x while sitting at 1.69x. Using the favourable
        model for the hole and the conservative one for the plate is that same error, one
        feature further along.

        A simply supported plate has no quiet radius: the TANGENTIAL stress barely falls
        between the centre and the rim. So the hole is placed where the clamped field is
        quiet, because it costs nothing to put it there, and it is CHECKED against the
        simply supported field, where the placement buys almost nothing.
        """
        a, nu, t = self.radius, self.poisson, self.thickness
        k = 3.0 * pressure / (8.0 * t**2)
        sigma_r = k * (3.0 + nu) * (a**2 - r**2)
        sigma_t = k * ((3.0 + nu) * a**2 - (1.0 + 3.0 * nu) * r**2)
        return max(abs(sigma_r), abs(sigma_t))

    def point_load_stress(self, load: float, footprint_radius: float) -> float:
        """Peak stress from a load applied over a small central patch, Pa.

        Simply supported. This is the harness U-bolt: the main's opening shock arrives
        through two bolts on a patch a few millimetres across, not spread over the disc.
        The logarithm is why a U-bolt with a backing washer is a different part from a
        U-bolt without one.
        """
        r0 = max(footprint_radius, 1e-4)
        return (3.0 * load / (2.0 * math.pi * self.thickness**2)) * (
            (1.0 + self.poisson) * math.log(self.radius / r0) + 1.0
        )

    def bond_shear(self, load: float) -> float:
        """Shear stress in the glue line holding the disc in the tube, Pa."""
        length = self.bond_length if self.bond_length > 0.0 else self.thickness
        return load / (math.pi * self.bore_diameter * length)


def opening_shock(mass: float, deploy_velocity: float, canopy_cd_a: float,
                  density: float, shock_factor: float = 1.0) -> float:
    """Main parachute opening load, N.

    `shock_factor` 1.0 is the steady drag the fully open canopy would make at the speed it
    was deployed at -- which is already about 14 times the vehicle's weight here, because
    the main is sized for 5 m/s and gets opened at 19. The infinite-mass opening coefficient
    for an unreefed solid canopy is nearer 1.7; the finite-mass correction pulls it back
    down because the vehicle decelerates while the canopy is still inflating, and for a
    vehicle this light that correction is large. Both are reported. Nobody should believe
    either to better than a factor of two without a load cell.
    """
    return shock_factor * 0.5 * density * deploy_velocity**2 * canopy_cd_a


# ---------------------------------------------------------------------------------------
# The wire that has to cross the pressure boundary
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class FeedThrough:
    """The sealed hole the ejection wiring passes through.

    WHY IT EXISTS AT ALL, which is the part worth reading. The altimeter that fires these
    charges lives in the NAV BAY, two bulkheads forward, because `configure.py` puts the
    nav bay at the front for GNSS sky view. So its firing circuits have to cross the canard
    module and then cross this bulkhead. The obvious alternative -- move the altimeter aft
    into its own av-bay between the two compartments, which is the standard high-power
    layout -- needs roughly 60 mm of tube plus two more bulkheads, and the recovery bay has
    13.0 mm of length margin. It does not fit, and that is why this hole is not optional.
    """

    hole_diameter: float  # m
    radius_in_plate: float  # m, where the hole sits
    n_holes: int = 2
    kt: float = KT_HOLE_BENDING

    @property
    def wire_area(self) -> float:
        return self.n_holes * math.pi * self.hole_diameter**2 / 4.0


@dataclass
class SealCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


@dataclass
class SealResult:
    """Everything the seal report and `baseline.py` need, computed once."""

    joint: Joint
    bulkhead: Bulkhead
    feed_through: FeedThrough
    design: EjectionCase
    stuck: EjectionCase
    geometric_volume: float
    free_volume: float
    shock: float
    shock_infinite_mass: float
    deploy_velocity: float
    descent_mass: float

    @property
    def governing_pressure(self) -> float:
        return max(self.design.pressure, self.stuck.pressure)

    @property
    def pressure_capacity(self) -> float:
        """Pressure at which the disc itself reaches its allowable, Pa.

        The number the fuse argument is made with: this has to sit well above the pressure
        the pins let go at, or the bulkhead is the fuse instead of the pins.
        """
        b = self.bulkhead
        return b.flexural_allowable * 8.0 * b.thickness**2 / (
            3.0 * (3.0 + b.poisson) * b.radius**2
        )

    @property
    def plate_stress(self) -> float:
        return self.bulkhead.stress(self.governing_pressure)

    @property
    def plate_margin(self) -> float:
        return self.bulkhead.flexural_allowable / self.plate_stress

    @property
    def shock_stress(self) -> float:
        return self.bulkhead.point_load_stress(self.shock_infinite_mass, 0.006)

    @property
    def shock_margin(self) -> float:
        return self.bulkhead.flexural_allowable / self.shock_stress

    @property
    def bond_margin(self) -> float:
        return G10_INTERLAMINAR_SHEAR / self.bulkhead.bond_shear(
            self.governing_pressure * self.bulkhead.area
        )

    @property
    def hole_stress(self) -> float:
        f = self.feed_through
        return f.kt * self.bulkhead.hole_field(self.governing_pressure, f.radius_in_plate)

    @property
    def hole_margin(self) -> float:
        return self.bulkhead.flexural_allowable / max(self.hole_stress, 1.0)

    @property
    def governed_by(self) -> str:
        return "the feed-through hole" if self.hole_margin < self.plate_margin else "the disc"


def size_bulkhead(bore_diameter: float, pressure: float,
                  thicknesses: list[float] | None = None) -> float:
    """Thinnest STOCKED G-10 sheet that carries `pressure` with margin, m.

    THE HOLE IS IN THIS CALCULATION, and it is what the answer turns on. Sizing the plate
    alone lands one sheet size thinner, and then the feed-through -- the feature this part
    is NAMED for -- fails at 1.7x. A bulkhead sized as though it were a bulkhead is not a
    sized feed-through, which is the same shape of mistake as sizing a hinge from the hinge
    moment and finding out later that nothing had computed the panel force.
    """
    options = thicknesses if thicknesses is not None else G10_SHEET_THICKNESS
    for t in sorted(options):
        plate = Bulkhead(bore_diameter, t)
        hole_r = plate.quiet_radius()
        plate_margin = plate.flexural_allowable / plate.stress(pressure)
        hole_margin = plate.flexural_allowable / (
            KT_HOLE_BENDING * plate.hole_field(pressure, hole_r)
        )
        if min(plate_margin, hole_margin) >= PLATE_MARGIN_REQUIRED:
            return t
    return max(options)


def build(inner_diameter: float, packed_volume: float, compartment_length: float,
          descent_mass: float, deploy_velocity: float, main_cd_a: float,
          air_density: float, n_pins: int = 3, thickness: float | None = None,
          ) -> SealResult:
    """Assemble the whole case for the aft gas seal from the vehicle's own numbers.

    Every argument comes from somewhere else in the project -- the compartment from
    `recovery.check_packing`, the descent numbers from `recovery.simulate_descent`. Nothing
    about the recovery bay is restated here, for the reason `configure.py` gives.
    """
    joint = Joint(bore_diameter=inner_diameter, n_pins=n_pins)
    geometric, free = compartment_volumes(inner_diameter, packed_volume, compartment_length)

    charge = charge_for_pressure(joint.design_pressure, geometric)
    design = EjectionCase("design, joint releases", charge, geometric, joint.area)
    stuck = EjectionCase("stuck joint, packed volume", charge, free, joint.area)

    t = thickness if thickness is not None else size_bulkhead(inner_diameter, stuck.pressure)
    # The glue line is the disc edge plus a fillet either side. 6 mm total is a fillet a
    # person can actually lay with a gloved finger through a 74.8 mm tube; claiming more
    # than that is claiming access that does not exist.
    plate = Bulkhead(inner_diameter, t, bond_length=t + 0.006)

    # Two holes: one firing circuit terminates on this disc, one continues aft to the
    # drogue. Placed at the clamped plate's quiet radius -- computed, not typed, because
    # it moves with Poisson's ratio and a hardcoded 0.6 would not.
    feed = FeedThrough(hole_diameter=0.004, radius_in_plate=plate.quiet_radius(), n_holes=2)

    shock = opening_shock(descent_mass, deploy_velocity, main_cd_a, air_density, 1.0)
    shock_inf = opening_shock(descent_mass, deploy_velocity, main_cd_a, air_density, 1.7)

    return SealResult(
        joint=joint, bulkhead=plate, feed_through=feed, design=design, stuck=stuck,
        geometric_volume=geometric, free_volume=free, shock=shock,
        shock_infinite_mass=shock_inf, deploy_velocity=deploy_velocity,
        descent_mass=descent_mass,
    )


def check_seal(r: SealResult) -> SealCheck:
    """Everything that has to be true for this bulkhead to be buildable and to hold.

    Written as a check rather than as prose because the prose already existed: `docs/05` has
    said "never sized" for six months and nothing acted on it. `recovery.check_packing` is
    the precedent -- the recovery bay was 4.5 cal because it was typed, until something
    verified it, and the first thing that verified it found an 11 mm error that turned out
    to be in the verification rather than the bay.
    """
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    # --- the disc under pressure ----------------------------------------------------
    if r.plate_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"bulkhead {r.bulkhead.thickness * mm:.1f} mm runs "
            f"{r.plate_stress / 1e6:.0f} MPa at the stuck-joint pressure "
            f"({r.governing_pressure / 1e3:.0f} kPa), margin {r.plate_margin:.2f}x against "
            f"{PLATE_MARGIN_REQUIRED:.1f}x -- the disc fails before the shear pins do, "
            f"which inverts the fuse")

    # --- the fuse has to be the fuse -------------------------------------------------
    # The whole point of the thickness chosen above. State it as a check so that lowering
    # the thickness, raising the charge, or adding a pin cannot quietly break it.
    pin_pressure = r.joint.release_pressure
    if r.governing_pressure <= pin_pressure:
        v.append(
            "the stuck-joint pressure is below the pin release pressure, which means the "
            "charge cannot open the joint at all")
    else:
        notes.append(
            f"pins release at {pin_pressure / 1e3:.0f} kPa and the disc holds to "
            f"{r.pressure_capacity / 1e3:.0f} kPa, so the pins are "
            f"{r.pressure_capacity / pin_pressure:.0f}x the weaker link. That ratio is the "
            f"design intent, not a coincidence")

    # --- the charge has to be able to open the joint ---------------------------------
    if r.design.force < SEPARATION_FACTOR * r.joint.release_force:
        v.append(
            f"charge makes {r.design.force:.0f} N against {r.joint.release_force:.0f} N of "
            f"pins and friction; that is {r.design.force / r.joint.release_force:.1f}x, "
            f"short of {SEPARATION_FACTOR:.1f}x")

    # --- opening shock through the U-bolt --------------------------------------------
    if r.shock_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"main opening shock {r.shock_infinite_mass:.0f} N puts "
            f"{r.shock_stress / 1e6:.0f} MPa under the U-bolt, margin "
            f"{r.shock_margin:.2f}x")
    else:
        notes.append(
            f"main opens at {r.deploy_velocity:.1f} m/s -- "
            f"{r.shock / (r.descent_mass * 9.81):.0f}x the vehicle's weight at a shock factor "
            f"of 1.0 and {r.shock_infinite_mass / (r.descent_mass * 9.81):.0f}x at 1.7. The U-bolt "
            f"needs a backing plate; the log term in point_load_stress() is the reason")

    # --- the bond line ----------------------------------------------------------------
    if r.bond_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"the disc-to-tube glue line runs "
            f"{r.bulkhead.bond_shear(r.governing_pressure * r.bulkhead.area) / 1e6:.1f} MPa, "
            f"margin {r.bond_margin:.2f}x")

    # --- the hole that makes it a feed-through and not a bulkhead ---------------------
    if r.hole_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"the wire feed-through at R {r.feed_through.radius_in_plate * mm:.1f} mm runs "
            f"{r.hole_stress / 1e6:.0f} MPa with Kt {r.feed_through.kt:.1f}, margin "
            f"{r.hole_margin:.2f}x")
    else:
        notes.append(
            f"{r.feed_through.n_holes} x dia {r.feed_through.hole_diameter * mm:.1f} mm at "
            f"R {r.feed_through.radius_in_plate * mm:.1f} mm runs {r.hole_margin:.2f}x, "
            f"against the disc's own {r.plate_margin:.2f}x -- THE HOLE GOVERNS, and sizing "
            f"the plate without it lands one sheet size thin")

    # --- the two things that are not stress -------------------------------------------
    notes.append(
        f"POT THE FEED-THROUGH ON THE FORWARD FACE. RTV is good to "
        f"{RTV_SERVICE_TEMPERATURE_C:.0f} C and the gas leaves the charge at "
        f"{BP_FLAME_TEMPERATURE:.0f} K; the disc is the heat shield, so the sealant belongs "
        f"behind it. Potting the exposed face is the version of this part that works on the "
        f"bench and sooties the nav bay in flight")
    notes.append(
        "THE MODULE VENTS FORWARD, never aft: the volume aft of this disc is where the "
        "charge fires. That makes the canard module part of the altimeter's static volume, "
        "so the nav bay's static ports have to be sized for both bays together, and a leak "
        "past this seal reaches the pressure sensor that fires the charges")

    if min(r.plate_margin, r.shock_margin, r.bond_margin) < DATASHEET_CONFIDENCE_MARGIN:
        notes.append(
            f"a margin here is under {DATASHEET_CONFIDENCE_MARGIN:.0f}x, and these are G-10 "
            f"SHEET allowables -- for a disc cut from sheet that is the right property, "
            f"unlike the tube, but get the supplier's datasheet before quoting a third digit")

    return SealCheck(ok=not v, violations=v, notes=notes)


def from_evaluation(ev, main_deploy_altitude: float = 200.0) -> SealResult:
    """Build the seal case straight from `configure.evaluate()`.

    One constructor, used by `scripts/seal_report.py` and by `scripts/baseline.py`, so the
    two cannot end up describing different bulkheads. Six scripts once carried their own
    copy of the baseline vehicle and reconciling the drift cost a day; this is that lesson
    applied one part further down.
    """
    from . import atmosphere, recovery

    tube = next(t for t in ev.rocket.tubes if t.name == "recovery bay")

    # The FORWARD compartment is the one this bulkhead closes, and `default_soft_goods()`
    # returns them nose to tail, so it is the first. It is also the awkward one: it holds
    # the MAIN, which is the larger canopy, so it leaves the smaller free volume -- and the
    # smaller free volume is what makes the stuck-joint pressure what it is.
    _, packed_volume, comp_length = ev.packing.compartments[0]

    descent_mass = ev.masses.dry_mass
    main = recovery.Canopy("main", recovery.size_for_descent_rate(descent_mass, 5.0), 2.2)
    drogue = recovery.Canopy("drogue", 0.457, 1.5)  # 18 in, per scripts/recovery_study.py

    return build(
        inner_diameter=tube.inner_diameter,
        packed_volume=packed_volume,
        compartment_length=comp_length,
        descent_mass=descent_mass,
        deploy_velocity=drogue.descent_rate(descent_mass, main_deploy_altitude),
        main_cd_a=main.cd_a,
        air_density=atmosphere.density(main_deploy_altitude),
    )
