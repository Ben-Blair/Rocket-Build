"""The motor mount `design/mass.py` has priced since the day that dict was written.

THE GAP THIS FILE CLOSES. `design/mass.py:70` carries
`"motor_mount_centering_rings": 0.250` and `:229` puts it at the motor's own mid-station,
and that is the whole of it: no mount tube, no ring count, no ring diameter, no ring
station, no retainer, no thrust path. Four places in the repo say so in writing --
`scripts/make_aft_fin_cad_fusion.py`'s docstring, and `docs/01-next-steps.md` corrections
51 and 52 twice each -- and two CAD generators refuse to draw it on purpose, on the grounds
that inventing centering-ring geometry with nothing sizing it is the mistake this project
keeps finding and fixing elsewhere (correction 19's collar material, correction 21's
coupling, correction 41's sled). It is the fifth allowance in this project to be paid for
without existing.

`design/seal.py` hands one more part over explicitly (`seal.py`, "WHAT THIS FILE DOES NOT
DO"): *"It does not size the booster's forward bulkhead, which closes the drogue
compartment's aft end. That one is part of the motor mount structure and belongs with it."*
It is sized here, and the handover turned out to be right for a reason nobody had noticed --
see THE SECOND FINDING below.

THE ANSWER, STATED BEFORE THE ARITHMETIC BECAUSE IT IS THE ONE IDEA IN THIS FILE: **the
centering rings are not thrust structure, and the part that is has been sitting in
`joints.py` as a 12 mm allowance the whole time.** Thrust enters the airframe at the
BOOSTER'S FORWARD BULKHEAD -- the motor's forward closure bears on it through the mount
tube's bore -- and travels forward from there into the vehicle it is pushing. The rings aft
of it align the motor, tie the fin tabs in, and carry the motor's mass laterally. Sizing
them as though 587 N ran through them would have produced a heavier, wronger part and hidden
the two findings below.

THE FIRST FINDING: THE FROZEN 12 mm FIN TAB AND A 54 mm MOTOR MOUNT TUBE CANNOT BOTH EXIST.
`scripts/make_cad_profiles.py`'s `TAB_DEPTH = 0.012` is measured inward from the booster
tube's OUTER radius (`make_aft_fin_cad_fusion.py`'s `_fin_corners_rz` takes
`root_r_mm = tube_or`), so the tab tip sits at R 27.70 mm. The bare 54 mm motor case is at
R 27.00 -- the tab clears it by 0.70 mm -- and `scripts/make_ork.py`'s assumed 57.0 mm mount
tube is at R 28.50, which the tab buries itself 0.80 mm inside. **The 12 mm tab was drawn as
if the fins bond to the bare motor case**, while `design/flutter.py` and `scripts/baseline.py`
both quote the 1.97x aft-fin flutter margin for "a fin tab bonded through the wall to the
MOTOR MOUNT". Four `AftFin` bodies already occupy R 27.70 in the Fusion document, so this was
never going to survive an interference check -- it survived because there was nothing to
check against. `fin_tab_depth()` derives the depth from the mount tube instead of the mount
tube being fitted around a round number, and `make_cad_profiles.py` and
`make_aft_fin_cad_fusion.py` now import it rather than each carrying the literal.

THE SECOND FINDING: THE BOOSTER'S FORWARD BULKHEAD AND THE MOTOR'S THRUST FACE ARE THE SAME
FEW MILLIMETRES OF THE VEHICLE. The booster is 416.28 mm and the motor is 321 mm, aft-flush,
so 95.28 mm sits forward of the motor. The recovery-bay/booster joint spends 79.40 mm of that
on coupler engagement and `joints.BULKHEAD_ALLOWANCE` budgets 12.00 mm more. **3.88 mm is
what the budget leaves**, and it is the entire axial allowance for everything between the
drogue compartment's aft closure and the motor's forward closure. There is no room for a
separate thrust plate and there does not need to be: one G-10 disc closes the drogue
compartment on its forward face, anchors the drogue harness's aft U-bolt there, and presents
its aft face to the motor. That is why `seal.py` was right to hand this part over rather than
size it as a third bulkhead.

The disc as actually sized is 4.80 mm, not the 12.00 mm the allowance charges, so the real
clear gap is 11.08 mm rather than 3.88. That is not slack to spend. It is the third finding.

THE THIRD FINDING, AND IT IS A FLIGHT SAFETY ONE: THAT GAP IS A CLOSED VOLUME IN FRONT OF A
LIVE EJECTION CHARGE. The Cesaroni Pro54 ships with an ejection charge in its forward
closure. This vehicle deploys on an independent altimeter and **nothing in this project has
ever said what happens to the motor's own charge.** The volume it would fire into is bounded
by the mount tube's bore, the motor's forward closure and this bulkhead: 25.9 cm3, sealed on
every side. `seal.ejection_pressure()` -- the project's own model, not a new one -- puts
1.2 g of black powder in there at **10.2 MPa against a disc whose capacity is 6.69 MPa**.
The margin is under 1.0 at every charge mass down to 0.8 g, so the conclusion does not turn
on the assumed figure. The design answer is a PLUGGED forward closure (Cesaroni sells one;
it is a purchase, not a modification), recorded here as `FORWARD_CLOSURE_PLUGGED` so that
the check fails loudly if anyone ever sets it False. Venting the gap is the alternative and
it is worse: it puts a hole through a pressure boundary to solve a problem a different part
number solves for nothing.

WHAT THIS FILE DOES NOT DO.
  * It does not model the fin root joint's own strength. The tab's bond to the mount tube is
    checked for AREA and for CLEARANCE here; the fin root moment that bond carries has never
    been computed by anything in this project, and `design/flutter.py` says as much about its
    own ideal-rigid-root assumption. That is a real gap and this file does not close it.
  * It does not model the mount tube as anything but a fibreglass tube with G-10 sheet
    properties. `design/materials.py`'s standing caveat applies twice over here: those are
    NEMA G-10 SHEET numbers and a filament-wound tube is a different material with different
    axial properties. Every margin below is quoted against them and none of the ones that
    matter lands under `DATASHEET_CONFIDENCE_MARGIN`, which is the only reason that is
    tolerable.
  * It does not select a retainer part number. `docs/04-bill-of-materials.md` already names
    an Aeropack-class screw-on retainer and prices it; what is sized here is the bond that
    holds its base to the mount tube, which is the part of it this project has to build.
  * It does not model the motor's aft closure geometry. The thrust face is taken to be the
    FORWARD closure, which is the arrangement the aft-flush motor and a screw-on retainer
    force; a case with a proud aft flange would react thrust at the other end of the tube and
    every ring load below would be a different number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import joints
from .materials import (
    DATASHEET_CONFIDENCE_MARGIN, G10_FLEXURAL, G10_INTERLAMINAR_SHEAR, G10_MODULUS,
    STRUCTURAL_EPOXY_SHEAR,
)
from .seal import (
    BP_FLAME_TEMPERATURE, BP_GAS_CONSTANT, Bulkhead, G10_SHEET_THICKNESS, Hole,
    MIN_LIGAMENT, PLATE_MARGIN_REQUIRED, UBOLT_HOLE_DIAMETER, UBOLT_LEG_SPACING,
)

G10_DENSITY = 1850.0  # kg/m3, the figure `seal.Bulkhead.mass` already commits to


# ---------------------------------------------------------------------------------------
# The mount tube
# ---------------------------------------------------------------------------------------

# Diametral slip clearance between the motor case and the mount tube bore. A 54 mm case is
# nominal 54.0 and the tube has to take it dirty, warm and one-handed at the pad; 0.5 mm on
# diameter is the ordinary figure and it is a FIT, not a stress result.
MOTOR_SLIP_CLEARANCE = 0.0005  # m, on diameter

# Wall thicknesses 54 mm airframe-grade tube is actually sold in. Same discipline as
# `seal.G10_SHEET_THICKNESS` and for the same reason correction 15 gave: a wall that is not
# stocked is not a design, and finding that out at order time cost this project a redesign
# of the canard root joint. CONFIRM THE VENDOR'S OWN LIST BEFORE ORDERING -- this is the
# band the common phenolic, Blue Tube and G12 offerings fall in, not a quoted catalogue.
MOUNT_TUBE_WALL_OPTIONS = [0.0009, 0.0013, 0.0016, 0.0020, 0.0023]  # m

# Practical floor on the mount tube wall, and it is the thing that actually sets it -- see
# `size_mount_tube()`. Two centering rings and a retainer base all bond to this tube's
# OUTSIDE, and a 0.9 mm wall is thin enough that squaring a ring on it and torquing a
# retainer cap against it are both real problems. Producibility, not stress, exactly as
# `design/access_bulkhead.py` found for both access plates.
MOUNT_TUBE_WALL_FLOOR = 0.0013  # m

# Axial length of clear mount tube left aft of the aftmost centering ring for the retainer
# base to bond to. An Aeropack-class base is a bonded collar, not a fastener, so this is the
# bond line and it is checked as one in `check_motor_mount()`.
RETAINER_BOND_LENGTH = 0.015  # m


# ---------------------------------------------------------------------------------------
# The centering rings
# ---------------------------------------------------------------------------------------

# Two rings aft of the forward bulkhead, and the aft one sits INSIDE the fin tab band and is
# slotted for the four tabs. That is not a compromise -- it is the arrangement that makes
# "through-the-wall fins bonded to the motor mount" mean something structurally, because it
# ties tab, mount tube and airframe together at one station. It also has to be in the CAD:
# an unslotted ring at that station is four interferences.
N_CENTERING_RINGS = 2

# Practical floor on ring thickness. A ring thinner than this cannot be bonded square in a
# tube by hand -- it tips in the fillet. Stress does not come close to setting it; see
# `check_motor_mount()`, which reports both numbers so the claim is checkable.
RING_THICKNESS_FLOOR = 0.0032  # m

# Clear axial gap kept between the forward ring and the fin tab's leading edge. Small on
# purpose: the ring and the tab may touch and the bond is better if they do, so this exists
# to stop the ring landing ON the tab's forward end where a fillet has nowhere to go.
RING_TAB_CLEARANCE = 0.002  # m

# THE TAB DOES NOT START WHERE IT REACHES FULL DEPTH. `make_cad_profiles.fin_profile()`
# builds the tab as a TRAPEZOID -- `[(0,0), ..., (r,0), (r - 6.0, -d), (6.0, -d)]` -- so its
# forward edge RAMPS from the root leading edge down to full depth over this length, and
# there is tab material at every station in between. This module used to fold the 6 mm into
# `tab_forward` and treat that as the tab's leading edge, which is right for the BOND (only
# the full-depth run lands on the mount tube edge on) and wrong for CLEARANCE: the forward
# ring was placed against the full-depth station and landed in the ramp, 22.59 mm3 into each
# of the four fins. The check meant to catch it used the same station and reported a 2.00 mm
# clearance that did not exist -- so a check whose datum is wrong is worse than no check.
# Found only by building it in CAD; see docs/01 correction 56. The literal is duplicated in
# `fin_profile()` and in `make_aft_fin_cad_fusion.TAB_INSET_MM`, which is correction 4
# material and is recorded rather than silently re-typed a fourth time.
TAB_RAMP_LENGTH = 0.006  # m

# Adhesive allowable for every bonded joint in this assembly, Pa. The G-10-to-G-10 practical
# ceiling and the structural epoxy figure disagree, so the lower governs, and it is derated
# by `DATASHEET_CONFIDENCE_MARGIN` because these are datasheet numbers for a hand-laid joint.
BOND_ALLOWABLE = min(G10_INTERLAMINAR_SHEAR, STRUCTURAL_EPOXY_SHEAR) / DATASHEET_CONFIDENCE_MARGIN

# Required ratio of allowable to actual for every bonded joint here. Matches
# `seal.PLATE_MARGIN_REQUIRED` and `hinge.BEARING_MARGIN_REQUIRED` so a marginal bond is not
# quietly treated as better news than a marginal bearing.
BOND_MARGIN_REQUIRED = 2.0


# ---------------------------------------------------------------------------------------
# The motor's own ejection charge -- see THE THIRD FINDING in the module docstring
# ---------------------------------------------------------------------------------------

# Cesaroni ships Pro54 reloads with an ejection charge in the forward closure and also sells
# a plugged closure for exactly this case. This vehicle deploys on an independent altimeter,
# so the motor charge has no job and this flag records the decision to buy it out rather than
# to fly it and hope. `check_motor_mount()` computes what flying it would do.
FORWARD_CLOSURE_PLUGGED = True

# Charge mass assumed when computing what the unplugged case would do. NO DATASHEET FIGURE
# HAS BEEN OBTAINED -- Cesaroni does not publish one per motor, and this is a working figure
# for a 54 mm three-grain reload. It is here the way `seal.JOINT_FRICTION_ALLOWANCE` is here:
# visible, so a real number can replace it, and load-bearing on nothing except an argument
# whose conclusion does not turn on it: the gap develops 8.5 MPa at 1.0 g and 11.9 MPa at
# 1.4, and the disc lets go at 6.69. There is no plausible charge mass at which this passes.
MOTOR_EJECTION_CHARGE = 0.0012  # kg


# ---------------------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class MountTube:
    """The tube the motor slides into. Stations are LOCAL to the booster tube's forward
    face, positive aft, because every consumer of this module works in that frame."""

    inner_diameter: float  # m
    wall: float  # m
    forward_station: float  # m, from the booster tube's forward face
    aft_station: float  # m

    @property
    def outer_diameter(self) -> float:
        return self.inner_diameter + 2.0 * self.wall

    @property
    def length(self) -> float:
        return self.aft_station - self.forward_station

    @property
    def area(self) -> float:
        """Load-carrying annulus, m2."""
        ro, ri = self.outer_diameter / 2.0, self.inner_diameter / 2.0
        return math.pi * (ro**2 - ri**2)

    @property
    def mass(self) -> float:
        return self.area * self.length * G10_DENSITY

    def axial_stress(self, load: float) -> float:
        return load / self.area

    def buckling_allowable(self, knockdown: float = 0.2) -> float:
        """Local shell buckling allowable, Pa. `tube_section.py`'s own formula and its own
        knockdown, so the two files cannot disagree about what a thin tube does."""
        radius = (self.outer_diameter + self.inner_diameter) / 4.0
        return knockdown * 0.6 * G10_MODULUS * self.wall / radius


@dataclass(frozen=True)
class CenteringRing:
    """One annular ring bonded between the mount tube and the airframe."""

    name: str
    bore: float  # m, the mount tube OD
    outer_diameter: float  # m, the airframe ID
    thickness: float  # m
    station: float  # m, forward face, local to the booster tube's forward face
    slots: int = 0  # fin tab slots cut through it
    slot_width: float = 0.0  # m, tangential
    slot_depth: float = 0.0  # m, radial

    @property
    def aft_station(self) -> float:
        return self.station + self.thickness

    @property
    def web_width(self) -> float:
        """Radial land between bore and rim, m -- the ring's own bending span."""
        return (self.outer_diameter - self.bore) / 2.0

    @property
    def slot_volume(self) -> float:
        return self.slots * self.slot_width * self.slot_depth * self.thickness

    @property
    def volume(self) -> float:
        annulus = math.pi * ((self.outer_diameter / 2.0) ** 2 - (self.bore / 2.0) ** 2)
        return annulus * self.thickness - self.slot_volume

    @property
    def mass(self) -> float:
        return self.volume * G10_DENSITY

    def inner_bond_area(self, fillet: float = 0.0) -> float:
        """Glue line to the mount tube, m2. The ring's thickness plus whatever fillet is
        credited -- and none is credited by default, for correction 15's reason: a fillet is
        a hand-laid thing and assuming it into the answer is how a joint reports a pass it
        has not earned."""
        return math.pi * self.bore * (self.thickness + 2.0 * fillet)

    def outer_bond_area(self, fillet: float = 0.0) -> float:
        """Glue line to the airframe ID, m2."""
        return math.pi * self.outer_diameter * (self.thickness + 2.0 * fillet)


@dataclass(frozen=True)
class Retainer:
    """The screw-on retainer's bonded base. The cap is a bought part; the bond is ours."""

    tube_outer_diameter: float  # m
    bond_length: float  # m
    retained_mass: float  # kg, motor dry -- the loaded case never sees the retention load

    @property
    def bond_area(self) -> float:
        return math.pi * self.tube_outer_diameter * self.bond_length

    def bond_stress(self, load: float) -> float:
        return load / self.bond_area


@dataclass
class MotorMountResult:
    """Everything the report and `baseline.py` need, computed once."""

    tube: MountTube
    rings: list[CenteringRing]
    forward_bulkhead: Bulkhead
    retainer: Retainer
    peak_thrust: float  # N
    thrust_face_radius: float  # m, where the motor's forward closure bears
    airframe_inner_diameter: float
    booster_outer_diameter: float
    motor_length: float
    motor_diameter: float
    motor_dry_mass: float
    motor_forward_station: float  # m, local to the booster forward face
    bulkhead_station: float  # m, forward face, local
    coupler_engagement: float  # m
    fin_tab_forward: float  # m, local -- where the tab reaches FULL DEPTH (bond datum)
    fin_tab_material_forward: float  # m, local -- where tab MATERIAL begins (clearance datum)
    fin_tab_aft: float  # m, local
    fin_thickness: float  # m
    n_fins: int
    drogue_design_pressure: float  # Pa
    drogue_stuck_pressure: float  # Pa
    drogue_shock: float  # N, the drogue harness's opening load through this U-bolt
    tube_wall_governed_by: str
    ring_thickness_governed_by: str
    landing_decel_g: float

    # --- the mount tube ------------------------------------------------------------------
    @property
    def tube_axial_stress(self) -> float:
        """Worst axial stress in the mount tube, Pa.

        THE SIGN IS THE POINT. Thrust enters the airframe at the forward bulkhead, which the
        motor bears on directly, so the mount tube does not carry it -- what the tube carries
        is the RETENTION load, aft, from the retainer at its aft end into the rings. That is
        an order of magnitude smaller and it is tension, not compression, which is why
        `tube_buckling_margin` below is reported as a bound rather than as a design case.
        """
        return self.tube.axial_stress(self.retention_load)

    @property
    def tube_thrust_stress(self) -> float:
        """What the tube WOULD see if the whole thrust ran through it, Pa.

        The redundant path: if the forward bulkhead's bond let go, thrust would go aft into
        the rings through this tube. Checked because a load path with one member is not a
        load path, and because it is the number an aft-bearing motor case would produce.
        """
        return self.tube.axial_stress(self.peak_thrust)

    @property
    def tube_thrust_margin(self) -> float:
        return G10_FLEXURAL / max(self.tube_thrust_stress, 1.0)

    @property
    def tube_buckling_margin(self) -> float:
        return self.tube.buckling_allowable() / max(self.tube_thrust_stress, 1.0)

    @property
    def retention_load(self) -> float:
        """N. What the retainer holds against -- the motor's dry mass at landing decel.
        The loaded case cannot occur: the propellant is gone before descent begins."""
        return self.motor_dry_mass * self.landing_decel_g * 9.80665

    @property
    def retainer_bond_stress(self) -> float:
        return self.retainer.bond_stress(self.retention_load)

    @property
    def retainer_bond_margin(self) -> float:
        return BOND_ALLOWABLE / max(self.retainer_bond_stress, 1.0)

    # --- the rings -----------------------------------------------------------------------
    @property
    def ring_thrust_share(self) -> float:
        """N per ring in the redundant path -- thrust split evenly across the rings."""
        return self.peak_thrust / max(len(self.rings), 1)

    @property
    def ring_inner_bond_stress(self) -> float:
        return max(self.ring_thrust_share / r.inner_bond_area() for r in self.rings)

    @property
    def ring_outer_bond_stress(self) -> float:
        return max(self.ring_thrust_share / r.outer_bond_area() for r in self.rings)

    @property
    def ring_bond_margin(self) -> float:
        return BOND_ALLOWABLE / max(self.ring_inner_bond_stress,
                                    self.ring_outer_bond_stress, 1.0)

    # --- the forward bulkhead ------------------------------------------------------------
    @property
    def thrust_plate_stress(self) -> float:
        """Bending stress in the forward bulkhead under the motor's thrust, Pa.

        NOT `Bulkhead.point_load_stress()`. That function is for a load on a SMALL central
        patch and this one is the opposite -- the motor bears on a ring at R 27.25 against
        support at R 37.40, so the loaded region is nearly the whole disc and only a 10 mm
        annular land is in bending. Modelled as that land: the total moment about the support
        circle, spread around its circumference, in a strip of the plate's own thickness.
        The stretched point-load formula gives 17 MPa here and this gives 7; the strip model
        is the right one and the agreement to within a factor of three is the check on it.
        """
        span = self.forward_bulkhead.radius - self.thrust_face_radius
        moment = self.peak_thrust * span / (2.0 * math.pi * self.forward_bulkhead.radius)
        return 6.0 * moment / self.forward_bulkhead.thickness**2

    @property
    def thrust_plate_margin(self) -> float:
        return self.forward_bulkhead.flexural_allowable / max(self.thrust_plate_stress, 1.0)

    @property
    def bulkhead_pressure_stress(self) -> float:
        return self.forward_bulkhead.stress(self.drogue_stuck_pressure)

    @property
    def bulkhead_pressure_margin(self) -> float:
        return self.forward_bulkhead.flexural_allowable / max(self.bulkhead_pressure_stress, 1.0)

    @property
    def bulkhead_shock_stress(self) -> float:
        """The drogue harness's U-bolt, as a point load. The footprint is the bare nut face
        until `design/recovery_hardware.py` sizes a backing plate for it -- the same 6 mm
        `seal.SealResult.shock_stress` has always assumed."""
        return self.forward_bulkhead.point_load_stress(self.drogue_shock, 0.006)

    @property
    def bulkhead_shock_margin(self) -> float:
        return self.forward_bulkhead.flexural_allowable / max(self.bulkhead_shock_stress, 1.0)

    @property
    def bulkhead_capacity(self) -> float:
        """Pressure at which the forward bulkhead reaches its allowable, Pa. Same expression
        as `seal.SealResult.pressure_capacity`."""
        b = self.forward_bulkhead
        return b.flexural_allowable * 8.0 * b.thickness**2 / (3.0 * (3.0 + b.poisson) * b.radius**2)

    # --- the motor's own ejection charge -------------------------------------------------
    @property
    def forward_gap(self) -> float:
        """Axial clear space between the forward bulkhead's aft face and the motor's forward
        closure, m. THE SECOND FINDING's 3.88 mm."""
        return self.motor_forward_station - (self.bulkhead_station + self.forward_bulkhead.thickness)

    @property
    def forward_gap_volume(self) -> float:
        """m3. The closed volume the motor's own ejection charge would fire into."""
        return math.pi * (self.tube.inner_diameter / 2.0) ** 2 * max(self.forward_gap, 0.0)

    @property
    def motor_charge_pressure(self) -> float:
        """Pa. What an unplugged forward closure develops in that volume."""
        if self.forward_gap_volume <= 0.0:
            return float("inf")
        return MOTOR_EJECTION_CHARGE * BP_GAS_CONSTANT * BP_FLAME_TEMPERATURE / self.forward_gap_volume

    @property
    def motor_charge_margin(self) -> float:
        return self.bulkhead_capacity / max(self.motor_charge_pressure, 1.0)

    # --- the whole assembly --------------------------------------------------------------
    @property
    def fin_tab_depth(self) -> float:
        """Radial depth of the aft fin's through-wall tab, m -- measured inward from the
        booster tube's OUTER radius, which is the frame `fin_profile()` works in.

        DERIVED, NOT CHOSEN. The tab's tip lands tangent on the mount tube so the two bond
        face to face, which is what `design/flutter.py` and `scripts/baseline.py` already
        claim the aft fin root does. See THE FIRST FINDING.
        """
        return (self.booster_outer_diameter - self.tube.outer_diameter) / 2.0

    @property
    def fin_tab_bond_area(self) -> float:
        """Tab-to-mount-tube bond area for all four fins, m2. The tab lands on the tube edge
        on, so this is the tab's own thickness times its axial run, times four -- plus
        whatever the fillet adds, which is not credited here."""
        return self.n_fins * self.fin_thickness * (self.fin_tab_aft - self.fin_tab_forward)

    @property
    def mass(self) -> float:
        return (self.tube.mass + sum(r.mass for r in self.rings)
                + self.forward_bulkhead.mass + self.retainer_mass)

    @property
    def retainer_mass(self) -> float:
        """kg. An Aeropack-class 54 mm retainer, base and cap, as weighed by its vendor --
        a bought part, so this is a catalogue figure and not a computed one."""
        return 0.031

    @property
    def allowance(self) -> float:
        """kg. What `design/mass.py` has been charging for all of this."""
        return 0.250


# ---------------------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------------------
def size_mount_tube(thrust: float, inner_diameter: float,
                    floor: float = MOUNT_TUBE_WALL_FLOOR,
                    walls: list[float] | None = None) -> tuple[float, str]:
    """Thinnest STOCKED wall that carries the redundant full-thrust case, or `floor`,
    whichever is thicker -- and which one governed, as a reason string.

    Mirrors `access_bulkhead.size_access_bulkhead()`, and lands in the same place for the
    same reason: nothing here is sized by stress. 587 N over a 230 mm2 annulus is 2.6 MPa
    against a 480 MPa allowable, and the thinnest tube on the list clears local buckling by
    two orders of magnitude. What sets the wall is that two rings and a retainer base bond
    to its outside.
    """
    options = sorted(walls if walls is not None else MOUNT_TUBE_WALL_OPTIONS)
    stress_pick: float | None = None
    stress_reason = ""
    for w in options:
        trial = MountTube(inner_diameter, w, 0.0, 1.0)  # length is not a
        # variable in either check below; the tube is a section here, not a part
        sigma = trial.axial_stress(thrust)
        if (G10_FLEXURAL / sigma >= PLATE_MARGIN_REQUIRED
                and trial.buckling_allowable() / sigma >= PLATE_MARGIN_REQUIRED):
            stress_pick = w
            stress_reason = ("local buckling" if trial.buckling_allowable() < G10_FLEXURAL
                             else "axial stress")
            break
    if stress_pick is None:
        stress_pick, stress_reason = max(options), "axial stress (no stocked wall clears it)"

    if stress_pick >= floor:
        return stress_pick, stress_reason

    for w in options:
        if w >= floor:
            return w, (
                f"the practical minimum wall -- two rings and a retainer base bond to this "
                f"tube's outside; {stress_reason} alone would have cleared "
                f"{PLATE_MARGIN_REQUIRED:.0f}x at {stress_pick * 1000:.1f} mm")
    return max(options), "the practical minimum wall"


def size_ring(thrust_per_ring: float, bore: float, outer_diameter: float,
              floor: float = RING_THICKNESS_FLOOR,
              thicknesses: list[float] | None = None) -> tuple[float, str]:
    """Thinnest STOCKED G-10 sheet whose two glue lines carry the redundant thrust share,
    or `floor`, whichever is thicker."""
    options = sorted(thicknesses if thicknesses is not None else G10_SHEET_THICKNESS)
    stress_pick: float | None = None
    for t in options:
        ring = CenteringRing("trial", bore, outer_diameter, t, 0.0)
        worst = max(thrust_per_ring / ring.inner_bond_area(),
                    thrust_per_ring / ring.outer_bond_area())
        if BOND_ALLOWABLE / worst >= BOND_MARGIN_REQUIRED:
            stress_pick = t
            break
    if stress_pick is None:
        stress_pick = max(options)

    if stress_pick >= floor:
        return stress_pick, "the mount-tube glue line"
    for t in options:
        if t >= floor:
            return t, (
                f"the practical minimum gauge -- a thinner ring tips in its own fillet and "
                f"cannot be bonded square; the glue line alone would have cleared "
                f"{BOND_MARGIN_REQUIRED:.0f}x at {stress_pick * 1000:.1f} mm")
    return max(options), "the practical minimum gauge"


def motor_mount_from_evaluation(ev, landing_decel_g: float = 30.0) -> MotorMountResult:
    """Build the whole motor mount from the vehicle's own numbers.

    Nothing about the booster, the motor or the joint is restated here, for the reason
    `configure.py` gives: six scripts once each carried their own copy of the baseline.
    The drogue pressure case comes from `seal.internal_bulkhead_from_evaluation()` because
    THE FORWARD BULKHEAD IS THE OTHER END OF THE SAME PRESSURE VESSEL -- one charge, one
    volume, two discs, and no chance of the two ends disagreeing about the pressure between
    them.
    """
    from . import seal as seal_mod

    booster = next(t for t in ev.rocket.tubes if t.name == "booster")
    motor = ev.params.motor
    booster_station = ev.rocket.tube_station(
        [t.name for t in ev.rocket.tubes].index("booster"))

    # The recovery-bay/booster joint, read rather than assumed.
    jnt = next(j for j in joints.for_rocket(ev.rocket, ev.params.wall_thickness, 0.05, 0.05)
               if j.aft_bay == "booster")
    coupler = jnt.engagement

    # The motor sits aft-flush: its aft face is the booster tube's aft face.
    motor_forward_station = booster.length - motor.length

    peak_thrust = max(motor.thrusts)

    # --- the mount tube ------------------------------------------------------------------
    bore = motor.diameter + MOTOR_SLIP_CLEARANCE

    # --- the forward bulkhead ------------------------------------------------------------
    drogue = seal_mod.internal_bulkhead_from_evaluation(ev)
    # Same vessel, so the same two pressures. This end IS protected by the recovery/booster
    # joint's shear pins; the other end is not, which is correction 29's point and the one
    # difference between the two discs.
    bulkhead = Bulkhead(booster.inner_diameter, drogue.bulkhead.thickness)
    bulkhead_station = coupler

    # --- the mount tube ------------------------------------------------------------------
    # It BUTTS against the bulkhead's aft face. It cannot pass through: that disc is the
    # drogue compartment's pressure boundary and a tube through it is a hole in it.
    tube_forward = bulkhead_station + bulkhead.thickness
    wall, wall_reason = size_mount_tube(peak_thrust, bore)
    tube = MountTube(bore, wall, tube_forward, booster.length)

    # --- the centering rings -------------------------------------------------------------
    aft = ev.rocket.aft_fins
    # Two datums, deliberately: the tab ramps from the root LE to full depth over
    # TAB_RAMP_LENGTH (see the constant). `tab_forward` is the FULL-DEPTH station and is what
    # the bond runs between; `tab_material_forward` is where tab material actually starts and
    # is what anything sharing radius with the tab has to clear.
    tab_material_forward = aft.x_root_le - booster_station
    tab_forward = tab_material_forward + TAB_RAMP_LENGTH
    tab_aft = tab_forward + aft.root_chord - 2.0 * TAB_RAMP_LENGTH
    tab_depth = (booster.outer_diameter - tube.outer_diameter) / 2.0

    ring_t, ring_reason = size_ring(peak_thrust / N_CENTERING_RINGS,
                                    tube.outer_diameter, booster.inner_diameter)
    rings = [
        CenteringRing(
            "forward centering ring", tube.outer_diameter, booster.inner_diameter, ring_t,
            tab_material_forward - RING_TAB_CLEARANCE - ring_t),
        # The aft ring sits INSIDE the fin tab band and is slotted for the four tabs, so the
        # tab, the mount tube and the airframe are tied together at one station. Its aft face
        # is set by the retainer's bond line, not by the fin.
        CenteringRing(
            "aft centering ring (slotted)", tube.outer_diameter, booster.inner_diameter,
            ring_t, booster.length - RETAINER_BOND_LENGTH - ring_t,
            slots=aft.count, slot_width=aft.thickness,
            slot_depth=tab_depth - (booster.outer_diameter - booster.inner_diameter) / 2.0),
    ]

    retainer = Retainer(tube.outer_diameter, RETAINER_BOND_LENGTH, motor.dry_mass)

    return MotorMountResult(
        tube=tube,
        rings=rings,
        forward_bulkhead=bulkhead,
        retainer=retainer,
        peak_thrust=peak_thrust,
        thrust_face_radius=bore / 2.0,
        airframe_inner_diameter=booster.inner_diameter,
        booster_outer_diameter=booster.outer_diameter,
        motor_length=motor.length,
        motor_diameter=motor.diameter,
        motor_dry_mass=motor.dry_mass,
        motor_forward_station=motor_forward_station,
        bulkhead_station=bulkhead_station,
        coupler_engagement=coupler,
        fin_tab_forward=tab_forward,
        fin_tab_material_forward=tab_material_forward,
        fin_tab_aft=tab_aft,
        fin_thickness=aft.thickness,
        n_fins=aft.count,
        drogue_design_pressure=drogue.design.pressure,
        drogue_stuck_pressure=drogue.stuck.pressure,
        drogue_shock=drogue.shock_infinite_mass,
        tube_wall_governed_by=wall_reason,
        ring_thickness_governed_by=ring_reason,
        landing_decel_g=landing_decel_g,
    )


def fin_tab_depth_for(rocket, motor) -> float:
    """Radial depth of the aft fin's through-wall tab, m, from the rocket and motor alone.

    Split out from `fin_tab_depth()` because the CAD generators that need this number --
    `scripts/make_cad_profiles.py` and `scripts/make_aft_fin_cad_fusion.py` -- build from
    `build_vehicle()` and have never needed a full `evaluate()`. Making them run a
    trajectory and a packing check to learn a diameter would be a real cost for no result.
    The tab depth genuinely does not depend on either: it is the booster's outer radius less
    the mount tube's, and the mount tube is set by the motor's diameter and a stocked wall.
    """
    booster = next(t for t in rocket.tubes if t.name == "booster")
    bore = motor.diameter + MOTOR_SLIP_CLEARANCE
    wall, _ = size_mount_tube(max(motor.thrusts), bore)
    return (booster.outer_diameter - (bore + 2.0 * wall)) / 2.0


def fin_tab_depth(ev) -> float:
    """Radial depth of the aft fin's through-wall tab, m.

    THE ONE FUNCTION OTHER FILES IMPORT. `scripts/make_cad_profiles.py` and
    `scripts/make_aft_fin_cad_fusion.py` each carried `0.012` as a literal, and that number
    put four fin bodies 0.80 mm inside any mount tube a 54 mm motor can have. It is derived
    now -- see THE FIRST FINDING -- and derived in one place, the same de-duplication
    `venting.CANARD_MODULE_FREE_VOLUME` got in correction 38.
    """
    return fin_tab_depth_for(ev.rocket, ev.params.motor)


def hole_layout(r: MotorMountResult) -> list[Hole]:
    """Every hole in the booster's forward bulkhead, positioned.

    Reuses `seal.Hole` so the CAD script types nothing, exactly as `seal.hole_layout()` and
    `access_bulkhead.hole_layout()` do. Two U-bolt legs for the drogue harness's aft end, and
    one feed-through for the drogue charge's own wiring -- which has to cross this disc
    because the altimeter is in the nav bay and the charge is on the far side.
    """
    half = UBOLT_LEG_SPACING / 2.0
    rq = r.forward_bulkhead.quiet_radius()
    return [
        Hole("drogue charge feed-through", rq, 0.0, 0.004),
        Hole("U-bolt leg A", 0.0, +half, UBOLT_HOLE_DIAMETER),
        Hole("U-bolt leg B", 0.0, -half, UBOLT_HOLE_DIAMETER),
    ]


@dataclass
class MotorMountCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_motor_mount(r: MotorMountResult) -> MotorMountCheck:
    """Everything that has to be true for this assembly to be buildable and to fly.

    Written as a check for the reason `seal.check_seal()` gives: prose has carried "never
    sized" in this project before and nothing acted on it until a check did.
    """
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    # --- the geometry that has to close --------------------------------------------------
    if r.forward_gap < 0.0:
        v.append(
            f"the motor's forward closure overlaps the forward bulkhead by "
            f"{-r.forward_gap * mm:.2f} mm -- the booster's 1.2 cal margin does not hold the "
            f"joint and the motor at once")
    else:
        notes.append(
            f"forward gap {r.forward_gap * mm:.2f} mm between the bulkhead's aft face and the "
            f"motor's forward closure. The booster's whole forward margin is "
            f"{r.motor_forward_station * mm:.2f} mm; the coupler takes "
            f"{r.coupler_engagement * mm:.1f} and joints.BULKHEAD_ALLOWANCE budgets "
            f"{joints.BULKHEAD_ALLOWANCE * mm:.1f} more, which would leave "
            f"{(r.motor_forward_station - r.coupler_engagement - joints.BULKHEAD_ALLOWANCE) * mm:.2f} mm. "
            f"The disc as actually sized is {r.forward_bulkhead.thickness * mm:.1f} mm, so the "
            f"real gap is bigger than the budget -- and it is a CLOSED VOLUME, which is the "
            f"only reason anyone should care how big it is")
        stack = r.forward_bulkhead.thickness + 2.0 * 0.003
        if stack > joints.BULKHEAD_ALLOWANCE:
            v.append(
                f"forward bulkhead assembly {stack * mm:.1f} mm (disc + two 3 mm fillets) "
                f"against the {joints.BULKHEAD_ALLOWANCE * mm:.1f} mm "
                f"joints.BULKHEAD_ALLOWANCE that budgets for it")
        else:
            notes.append(
                f"assembled stack {stack * mm:.1f} mm inside the "
                f"{joints.BULKHEAD_ALLOWANCE * mm:.1f} mm joints.BULKHEAD_ALLOWANCE -- the "
                f"third bulkhead in this vehicle to be checked against that typed number")

    # --- THE FIRST FINDING ---------------------------------------------------------------
    legacy = 0.012
    if abs(r.fin_tab_depth - legacy) > 1e-6:
        notes.append(
            f"FIN TAB DEPTH IS {r.fin_tab_depth * mm:.2f} mm, NOT THE 12.00 mm THAT WAS "
            f"FROZEN. The tab is measured inward from the booster OD, so 12.00 put its tip at "
            f"R {(r.booster_outer_diameter / 2.0 - legacy) * mm:.2f} mm -- "
            f"{((r.tube.outer_diameter / 2.0) - (r.booster_outer_diameter / 2.0 - legacy)) * mm:.2f} mm "
            f"inside this mount tube's own wall, and only "
            f"{(r.booster_outer_diameter / 2.0 - legacy - r.motor_diameter / 2.0) * mm:.2f} mm "
            f"clear of the bare motor case, which is what it was really drawn against. "
            f"scripts/make_cad_profiles.py and scripts/make_aft_fin_cad_fusion.py must import "
            f"motor_mount.fin_tab_depth() and the four AftFin bodies must be regenerated")

    tab_land = r.fin_tab_depth - (r.booster_outer_diameter - r.airframe_inner_diameter) / 2.0
    if tab_land <= 0.0:
        v.append(
            f"the fin tab does not reach past the airframe wall: {r.fin_tab_depth * mm:.2f} mm "
            f"against a {((r.booster_outer_diameter - r.airframe_inner_diameter) / 2.0) * mm:.2f} mm wall")
    else:
        notes.append(
            f"tab stands {tab_land * mm:.2f} mm proud of the airframe bore and lands tangent "
            f"on the mount tube; {r.n_fins} tabs x {r.fin_thickness * mm:.1f} mm x "
            f"{(r.fin_tab_aft - r.fin_tab_forward) * mm:.1f} mm gives "
            f"{r.fin_tab_bond_area * 1e6:.0f} mm2 of tab-to-tube bond, fillets not credited")

    # --- THE THIRD FINDING ---------------------------------------------------------------
    if not FORWARD_CLOSURE_PLUGGED:
        v.append(
            f"THE MOTOR'S OWN EJECTION CHARGE IS LIVE. {MOTOR_EJECTION_CHARGE * 1e3:.1f} g "
            f"into the {r.forward_gap_volume * 1e6:.1f} cm3 forward gap is "
            f"{r.motor_charge_pressure / 1e6:.1f} MPa against a disc that lets go at "
            f"{r.bulkhead_capacity / 1e6:.2f} MPa -- {1.0 / r.motor_charge_margin:.1f}x over. "
            f"Buy the plugged forward closure")
    else:
        notes.append(
            f"forward closure PLUGGED (a purchase, not a modification). Flying it live would "
            f"put {MOTOR_EJECTION_CHARGE * 1e3:.1f} g into {r.forward_gap_volume * 1e6:.1f} cm3 "
            f"-- {r.motor_charge_pressure / 1e6:.1f} MPa against the disc's "
            f"{r.bulkhead_capacity / 1e6:.2f} MPa capacity, {1.0 / r.motor_charge_margin:.1f}x "
            f"over. Nothing in this project had ever asked")

    # --- the load paths ------------------------------------------------------------------
    if r.thrust_plate_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"forward bulkhead as thrust face: {r.thrust_plate_stress / 1e6:.1f} MPa under "
            f"{r.peak_thrust:.0f} N, margin {r.thrust_plate_margin:.1f}x")
    else:
        notes.append(
            f"thrust {r.peak_thrust:.0f} N enters the airframe at the forward bulkhead, not "
            f"through the rings: {r.thrust_plate_stress / 1e6:.1f} MPa in the "
            f"{(r.forward_bulkhead.radius - r.thrust_face_radius) * mm:.2f} mm annular land "
            f"between the motor's bearing circle and the tube wall, {r.thrust_plate_margin:.0f}x")

    if r.bulkhead_pressure_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"forward bulkhead under the stuck-joint drogue case: "
            f"{r.bulkhead_pressure_stress / 1e6:.1f} MPa, margin "
            f"{r.bulkhead_pressure_margin:.1f}x")
    else:
        notes.append(
            f"same disc, same vessel as the internal bulkhead: "
            f"{r.drogue_stuck_pressure / 1e3:.0f} kPa stuck-joint case gives "
            f"{r.bulkhead_pressure_margin:.1f}x, design case "
            f"{r.drogue_design_pressure / 1e3:.0f} kPa")

    if r.bulkhead_shock_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"forward bulkhead U-bolt: {r.drogue_shock:.0f} N gives "
            f"{r.bulkhead_shock_stress / 1e6:.1f} MPa, margin {r.bulkhead_shock_margin:.1f}x")
    else:
        notes.append(
            f"drogue harness U-bolt {r.drogue_shock:.0f} N on a bare 6 mm footprint gives "
            f"{r.bulkhead_shock_margin:.1f}x -- the FOURTH U-bolt, the one "
            f"recovery.default_soft_goods() has priced since it was written and that had no "
            f"bulkhead to stand on until this file")

    if r.ring_bond_margin < BOND_MARGIN_REQUIRED:
        v.append(
            f"centering ring glue line: {max(r.ring_inner_bond_stress, r.ring_outer_bond_stress) / 1e6:.2f} MPa "
            f"against {BOND_ALLOWABLE / 1e6:.2f} MPa allowable, margin {r.ring_bond_margin:.1f}x")
    else:
        notes.append(
            f"rings carry the REDUNDANT path only -- {r.ring_thrust_share:.0f} N each if the "
            f"bulkhead's bond let go -- at {r.ring_bond_margin:.0f}x. Their real job is "
            f"alignment and tying the fin tabs in")

    if r.retainer_bond_margin < BOND_MARGIN_REQUIRED:
        v.append(
            f"retainer base bond: {r.retainer_bond_stress / 1e6:.2f} MPa over "
            f"{r.retainer.bond_length * mm:.0f} mm, margin {r.retainer_bond_margin:.1f}x")
    else:
        notes.append(
            f"retainer holds {r.retention_load:.0f} N ({r.motor_dry_mass * 1e3:.0f} g dry at "
            f"{r.landing_decel_g:.0f} g) over a {r.retainer.bond_length * mm:.0f} mm bond, "
            f"{r.retainer_bond_margin:.0f}x -- the DRY mass, because the propellant is gone "
            f"before descent begins")

    # --- the parts have to fit next to each other ----------------------------------------
    fwd_ring, aft_ring = r.rings[0], r.rings[1]
    # Measured to where tab MATERIAL starts, not to the full-depth station. Using the latter
    # is what let a 2.76 mm overlap report as a 2.00 mm clearance -- see TAB_RAMP_LENGTH.
    gap_fwd = r.fin_tab_material_forward - fwd_ring.aft_station
    if gap_fwd < 0.0:
        v.append(
            f"{fwd_ring.name} overlaps the fin tab's leading edge by {-gap_fwd * mm:.2f} mm "
            f"-- measured to the tab's RAMP start, {r.fin_tab_material_forward * mm:.2f} mm, "
            f"not its full-depth station at {r.fin_tab_forward * mm:.2f} mm")
    else:
        notes.append(
            f"{fwd_ring.name} clears the tab's ramp start by {gap_fwd * mm:.2f} mm "
            f"({(r.fin_tab_forward - fwd_ring.aft_station) * mm:.2f} mm to full depth)")

    if not (r.fin_tab_forward <= aft_ring.station and aft_ring.aft_station <= r.fin_tab_aft):
        notes.append(
            f"{aft_ring.name} at {aft_ring.station * mm:.2f}..{aft_ring.aft_station * mm:.2f} mm "
            f"is NOT inside the tab band {r.fin_tab_forward * mm:.2f}..{r.fin_tab_aft * mm:.2f} -- "
            f"its slots cut material the tabs do not occupy")
    else:
        notes.append(
            f"{aft_ring.name} sits inside the tab band and is slotted "
            f"{aft_ring.slots} x {aft_ring.slot_width * mm:.1f} x {aft_ring.slot_depth * mm:.2f} mm; "
            f"an unslotted ring at that station is {aft_ring.slots} interferences")

    tail = r.tube.aft_station - aft_ring.aft_station
    if tail < RETAINER_BOND_LENGTH - 1e-9:
        v.append(
            f"only {tail * mm:.1f} mm of clear mount tube aft of {aft_ring.name} for a "
            f"{RETAINER_BOND_LENGTH * mm:.0f} mm retainer bond")

    if r.bulkhead_station + r.forward_bulkhead.thickness > r.motor_forward_station:
        v.append("the forward bulkhead and the motor occupy the same station")

    # --- mass against the allowance ------------------------------------------------------
    notes.append(
        f"assembly {r.mass * 1e3:.1f} g against the {r.allowance * 1e3:.0f} g "
        f"mass.py has charged: tube {r.tube.mass * 1e3:.1f}, rings "
        f"{sum(x.mass for x in r.rings) * 1e3:.1f}, bulkhead "
        f"{r.forward_bulkhead.mass * 1e3:.1f}, retainer {r.retainer_mass * 1e3:.1f}")
    if r.mass > r.allowance:
        v.append(
            f"the assembly is {(r.mass - r.allowance) * 1e3:.1f} g over the "
            f"{r.allowance * 1e3:.0f} g allowance mass.py charges for it")

    notes.append(f"mount tube wall governed by: {r.tube_wall_governed_by}")
    notes.append(f"ring thickness governed by: {r.ring_thickness_governed_by}")

    # --- the hole layout in the forward bulkhead -----------------------------------------
    hs = hole_layout(r)
    for i, a in enumerate(hs):
        edge = r.forward_bulkhead.radius - a.radius_in_plate - a.diameter / 2.0
        if edge < MIN_LIGAMENT:
            v.append(
                f"forward bulkhead: {a.name} leaves {edge * mm:.2f} mm to the disc edge, "
                f"under the {MIN_LIGAMENT * mm:.1f} mm minimum")
        for b in hs[i + 1:]:
            gap = math.hypot(a.x - b.x, a.y - b.y) - a.diameter / 2.0 - b.diameter / 2.0
            if gap < MIN_LIGAMENT:
                v.append(
                    f"forward bulkhead: {a.name} and {b.name} leave {gap * mm:.2f} mm of "
                    f"metal between them")

    worst = min(min(r.forward_bulkhead.radius - h.radius_in_plate - h.diameter / 2.0
                    for h in hs),
                min(math.hypot(a.x - b.x, a.y - b.y) - a.diameter / 2.0 - b.diameter / 2.0
                    for i, a in enumerate(hs) for b in hs[i + 1:]))
    notes.append(f"forward bulkhead: {len(hs)} holes, tightest ligament {worst * mm:.1f} mm")

    # --- the standing caveat -------------------------------------------------------------
    notes.append(
        "NOT SOLVED, stated: the fin ROOT MOMENT this tab bond carries has never been "
        "computed by anything in this project -- design/flutter.py says the same about its "
        "own ideal-rigid-root assumption. Area and clearance are checked here; strength is "
        "not, and swinging the finished fin is what would settle it")

    worst_margin = min(r.thrust_plate_margin, r.bulkhead_pressure_margin,
                       r.bulkhead_shock_margin, r.ring_bond_margin, r.retainer_bond_margin,
                       r.tube_thrust_margin)
    if worst_margin < DATASHEET_CONFIDENCE_MARGIN:
        notes.append(
            f"worst margin here is {worst_margin:.1f}x, under {DATASHEET_CONFIDENCE_MARGIN:.0f}x "
            f"-- get the supplier's own datasheet before quoting a third digit, and remember "
            f"these are G-10 SHEET numbers standing in for a filament-wound tube")

    return MotorMountCheck(ok=not v, violations=v, notes=notes)
