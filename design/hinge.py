"""The canard hinge as a MECHANISM: shaft, bearing, coupling, and the fits between them.

This module exists because of a specific failure, repeated. The servo was a bounding box
for long enough that three of its properties were never checked, and each of them was
something a box does not have: an output shaft at all, a shaft POSITION, and a shaft AXIS.
See docs/01 corrections 1, 6, 9, 10 and 11.

Building the real part (scripts/make_servo_cad.py) closed the position and the axis.
Building the MECHANISM -- this file -- closes the third kind of error, the one neither a
bounding box nor a dimensionally perfect solid can catch: a model can have every dimension
right and still describe a thing that cannot be assembled, or that cannot carry its
loads.

Three defects that a static Part Studio and a swept interference check both missed:

  1. The wall pass-through was a dia 5.000 hole around a dia 5.000 shaft, because the cut
     reused the shaft's own sketch. Right for POSITION, wrong for FIT, and no interference
     check will ever flag it, because zero clearance is not an interference.

  2. The servo's output spline reached 0.185 mm past the panel root face. Direct drive was
     therefore not geometrically available, and the coupling that has to make up the
     difference was never designed.

  3. The shaft was a SOLID dia 5 rod running from R 29.400 to R 40.200 while the servo's
     output face sat at R 37.185 and its case ran inboard from there. The shaft and the
     servo occupied the same space -- 3.015 mm of it inside the spline, another 7.785 mm
     inside the case. That is not a fit subtlety; it is a hard clash, and the sweep did
     not see it because the sweep asked whether ROTATION caused a collision, and this
     collision was already there at zero deflection.

The through-line is that all three live in the 3.015 mm of radius between the servo's
output face and the panel root, and 2.300 mm of that is airframe wall. That is the real
finding, and it is a LAYOUT problem, not a tolerance problem: no fit callout can create
space that is not there.

Everything here is derived. Nothing is typed twice. The loads come from the same
`packaging.hinge_moment()` the servo sizing uses, and the stations come from
`packaging.SERVO_GEOMETRY` and the frozen airframe in `configure.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ---------------------------------------------------------------------------------------
# Material and bearing allowables.
#
# These are the numbers to argue with. They are stated once, here, so that arguing with
# them changes every conclusion downstream at the same time.
# ---------------------------------------------------------------------------------------

# Allowables live in design/materials.py, stated once for the whole project. They are
# re-exported here because callers already read them off this module -- the design factor
# below is applied on top, so pick the bearing class AFTER reading the margin.
from .materials import (  # noqa: E402
    BEARING_PRESSURE_LIMIT, SHAFT_YIELD,
    G10_BEARING, G10_FLEXURAL, G10_INTERLAMINAR_SHEAR,
    RETAINING_COMPOUND_MAX_RADIAL_GAP, RETAINING_COMPOUND_RELEASE_C,
    RETAINING_COMPOUND_SHEAR, STRUCTURAL_EPOXY_SHEAR,
)

# Required ratio of allowable to actual. 2.0 to match the servo torque margin requirement
# in docs/00 -- a hinge whose bearing is marginal is not a better hinge than one whose
# servo is marginal.
BEARING_MARGIN_REQUIRED = 2.0

SHAFT_MARGIN_REQUIRED = 2.0

# Same 2.0, and stated separately so that arguing about an ADHESIVE margin does not
# silently move the bearing's.
COUPLING_MARGIN_REQUIRED = 2.0

# Minimum diametral running clearance between a turning shaft and whatever it turns
# inside. Any positive number would have caught the defect this file exists for -- the
# wall pass-through was dia 5.000 on dia 5.000, which is not an interference and so is
# invisible to every interference check ever written. 0.020 mm is an H7/g6 running fit on
# a 6 mm shaft; below that a hinge binds.
MIN_RUNNING_CLEARANCE = 0.020e-3  # m, diametral

# Nominal running fit of the journal inside the bearing bore, once there IS a bearing.
BEARING_RUNNING_CLEARANCE = 0.030e-3  # m, diametral

# How the bearing is held in its seat, and this is a BUYABILITY constraint as much as an
# engineering one.
#
# The obvious way to get a press fit is to undersize the hole: a dia 8.000 bushing in a
# dia 7.975 hole gives 0.025 mm of interference. That is what this module specified first,
# and it is wrong in practice, because **dia 7.975 is not a reamer you can buy.** It would
# have to be bored and measured, on a 2.3 mm fibreglass wall, four times.
#
# A polymer plain bearing is not fitted that way. igus and every other supplier specify the
# housing as **H7 at the nominal size** -- here dia 8 H7, +0.015/-0, which is the single
# most ordinary reamer in existence -- and supply the bushing with an OVERSIZE outside
# diameter so that pressing it into that H7 hole gives the interference and sizes the bore
# to running fit as it goes. The interference is a property of the part you order, not of a
# hole you have to hit to a quarter of a thousandth.
#
# So the hole is nominal and the bushing is oversize. Same physics, same interference,
# and the drawing calls out a standard reamer instead of a special one.
BEARING_HOUSING_TOLERANCE = 0.015e-3   # H7 on dia 8: +0.015 / -0
BEARING_SUPPLIED_OVERSIZE = 0.030e-3   # diametral, bushing OD above nominal as supplied
BEARING_SEAT_INTERFERENCE = BEARING_SUPPLIED_OVERSIZE  # what the press actually sees

# A 15-tooth dia 4 spline has roughly 0.20 mm of working tooth height. Used only to state
# the contact pressure in the socket; the sizing case is the servo's own stall torque,
# which the spline is by definition rated for at FULL engagement.
SPLINE_TOOTH_HEIGHT = 0.20e-3  # m

# ======================================================================================
# THE COUPLING, and why it is a plain drilled hole rather than a broached spline
# ======================================================================================
# The problem, stated as geometry: there is 0.515 mm between the servo's output face and
# the bearing's inboard end, and everything OUTBOARD of that has to pass down a dia 6.000
# bore, because that is the journal that turns in the bearing. Fifteen teeth on a dia 4
# pitch circle need metal around them, so every female-spline part anyone sells -- horn,
# hub, adapter -- is dia 7 or larger. None of them fit, in either place. docs/01
# correction 16 and docs/04 both said "buy a horn instead of broaching"; that instruction
# is not buildable, and this block is what replaces it.
#
# So the coupling lives INSIDE the dia 6 shaft. The obvious way to do that is to broach a
# 15-tooth socket in a 0.95 mm wall, which is the specialist operation correction 16 was
# trying to avoid in the first place.
#
# THE WAY OUT: DO NOT CUT TEETH. CAST THEM.
#
# Drill a plain round socket a few hundredths over the spline's crest diameter, fill it
# with anaerobic retaining compound, and push it onto the spline. The compound cures in
# the tooth valleys and BECOMES the female spline -- fifteen adhesive keys, formed by the
# very part they have to mate with, so they fit perfectly by construction. The shaft needs
# one drilled hole, on a part that is already being turned.
#
# This is only allowed because THE COUPLING CARRIES TORQUE AND NOTHING ELSE. The bearing
# sits outboard of it and takes every bit of the 0.806 N m of panel bending; the joint
# sees 0.520 N m of servo stall and no moment at all. An adhesive joint in a bending load
# path would be a bad idea. This one is not in a bending load path.
#
# WHAT SIZES THE SOCKET IS THE GAP, NOT THE STRESS. Retaining compound wants a bond line
# under about 0.1 mm on the radius; a structural epoxy wants a thicker one. Opening the
# socket up REDUCES the adhesive shear stress (bigger radius, more area) and would look
# like an improvement right up until the compound is outside the gap it is specified for.
# So the socket is a slip fit on the crests and the strength comes from the valleys.
SPLINE_CREST_CLEARANCE = 0.050e-3   # m, radial, socket bore over spline crest diameter


@dataclass(frozen=True)
class HingeStack:
    """Radial stations for one canard hinge, all measured from the ROCKET axis, in metres.

    Radius, not "distance from the wall", because radius is the coordinate every one of
    these parts is actually positioned in, and because the two errors this file exists to
    catch were both errors about where something sat in radius.

    Ordered inboard to outboard, the stack is:

        servo cable boss  ->  servo case  ->  servo output face  ->  [spline]
        ->  shaft sleeve inboard end  ->  bearing inboard end  ->  tube ID
        ->  WALL  ->  tube OD  ->  panel root face

    with the spline, the sleeve's spline socket and the bearing all CONCENTRIC over part
    of that range rather than stacked in series. That concentricity is the only reason the
    stack closes at all: in series it needs 12 mm of radius and there are 3.
    """

    tube_outer_radius: float        # R of the tube OD. RADIUS, not diameter: every other
                                    # station here is a radius, and mixing the two is how
                                    # the hinge station ended up at 0.029 of MAC once
                                    # already (docs/01, correction on Sketch 3).
    wall_thickness: float
    panel_root: float               # R of the panel root face
    servo_output_face: float        # R of the face the spline emerges from
    servo_depth: float              # radial depth of the servo inboard of that face
    servo_boss_half_width: float    # half the case width; sets when four bosses collide
    spline_length: float
    spline_dia: float
    journal_dia: float              # shaft sleeve OD; the surface that turns
    bearing_length: float
    bearing_wall: float             # radial wall of the bearing. ZERO means there is no
                                    # bearing and the shaft turns in the airframe itself.
    wall_bore_dia: float            # the hole through the airframe wall, as dimensioned
    sleeve_gap: float               # gap between servo output face and sleeve inboard end

    # ---- derived stations ------------------------------------------------------------

    @property
    def tube_inner_radius(self) -> float:
        return self.tube_outer_radius - self.wall_thickness

    @property
    def has_bearing(self) -> bool:
        return self.bearing_wall > 0.0

    @property
    def spline_tip(self) -> float:
        return self.servo_output_face + self.spline_length

    @property
    def sleeve_inboard(self) -> float:
        return self.servo_output_face + self.sleeve_gap

    @property
    def sleeve_length(self) -> float:
        return self.panel_root - self.sleeve_inboard

    @property
    def bearing_outboard(self) -> float:
        """The bearing's outboard end is flush with the tube OD, so the sleeve emerges
        from a supported hole rather than from an unsupported one."""
        return self.tube_outer_radius

    @property
    def bearing_inboard(self) -> float:
        return self.bearing_outboard - self.bearing_length

    @property
    def bearing_centre(self) -> float:
        return self.bearing_outboard - self.bearing_length / 2.0

    @property
    def bearing_od(self) -> float:
        return self.journal_dia + 2.0 * self.bearing_wall

    @property
    def bearing_in_wall(self) -> float:
        """How much of the bearing the airframe wall actually supports. The remainder has
        to be carried by a housing collar on the tube ID, which is a REQUIREMENT ON THE
        PRINTED BAY, not a detail."""
        return (min(self.bearing_outboard, self.tube_outer_radius)
                - max(self.bearing_inboard, self.tube_inner_radius))

    @property
    def housing_collar_height(self) -> float:
        return max(0.0, self.tube_inner_radius - self.bearing_inboard)

    @property
    def spline_engagement(self) -> float:
        """Overlap between the servo spline and the sleeve's socket. This is the number
        that was 0.185 mm when the panel root was expected to do the job directly."""
        return max(0.0, min(self.spline_length, self.spline_tip - self.sleeve_inboard))

    @property
    def spline_past_panel_root(self) -> float:
        """How far the spline reaches beyond the panel root face. docs/05 carried this as
        0.185 mm and read it as "direct drive is not available", which was right; what it
        did not say is that the same 0.185 mm is what is left of a 3.015 mm radial budget
        after the wall has taken 2.300 of it."""
        return self.spline_tip - self.panel_root

    @property
    def spline_engagement_fraction(self) -> float:
        return self.spline_engagement / self.spline_length

    @property
    def servo_inner_radius(self) -> float:
        return self.servo_output_face - self.servo_depth

    @property
    def central_void(self) -> float:
        """Diameter of the clear cylinder on the rocket axis, over the axial band where
        the servo cable bosses are. This is where the wiring goes, and it is the price
        paid for every millimetre the servo moves inboard."""
        return 2.0 * self.servo_inner_radius

    @property
    def boss_collision_margin(self) -> float:
        """Four bosses at 90 degrees, each `2*boss_half_width` wide and centred on its own
        hinge axis, meet corner to corner when the inner radius falls to the half width.
        Positive is clearance."""
        return self.servo_inner_radius - self.servo_boss_half_width

    @property
    def running_clearance(self) -> float:
        """Diametral clearance between the journal and whatever it actually turns inside.

        With a bearing that is the bearing bore. WITHOUT one the shaft turns in the
        airframe hole itself, and this is the number that was exactly zero.
        """
        if self.has_bearing:
            return BEARING_RUNNING_CLEARANCE
        return self.wall_bore_dia - self.journal_dia

    @property
    def seat_fit(self) -> float:
        """Diametral fit of the bearing in its seat. Negative is interference, which is
        what a pressed bearing wants.

        Measured against the bushing AS SUPPLIED, which is oversize, not against its
        nominal size. The hole is nominal (dia 8 H7) so that it can be cut with a standard
        reamer; the interference comes from the part.
        """
        return self.wall_bore_dia - (self.bearing_od + BEARING_SUPPLIED_OVERSIZE)


@dataclass(frozen=True)
class HingeLoads:
    """What the stack has to carry. Signs follow packaging.hinge_moment()."""

    normal_force: float             # N, panel aerodynamic normal force
    load_radius: float              # m, where it acts
    hinge_moment: float             # N*m about the hinge line, signed
    moment_at_wall: float           # N*m, bending in the sleeve where it leaves the tube
    moment_at_bearing: float        # N*m, about the bearing centre
    bearing_pressure: float         # Pa, peak edge pressure under the couple
    bearing_margin: float           # allowable / actual
    shaft_stress: float             # Pa, bending stress in the sleeve at the tube OD
    shaft_margin: dict[str, float]  # per material
    spline_torque: float            # N*m, the sizing case (servo stall, not aero)
    spline_pressure: float          # Pa on the socket teeth


def panel_normal_force(hinge_moment: float, mean_chord: float,
                       hinge_frac: float = 0.20, cp_frac: float = 0.25) -> float:
    """Invert packaging.hinge_moment() to recover the force that produced it.

    The hinge moment is the number the servo sizing cares about and it is SMALL, because
    the hinge sits close to the panel CP -- that closeness is exactly what makes a 9 g
    servo sufficient. The force is NOT small, and it is the force that sizes the bearing.
    A 0.06 N*m hinge moment and a 25 N panel load are the same panel: the moment is the
    force times a 2.4 mm arm, and the bearing sees the force times a 29 mm arm.

    Reading only the hinge moment is how a hinge ends up with no bearing in it.
    """
    arm = (cp_frac - hinge_frac) * mean_chord
    return abs(hinge_moment) / arm


def spanwise_centroid(root_chord: float, tip_chord: float, semispan: float) -> float:
    """Area centroid of the trapezoidal panel, outboard of the theoretical root."""
    return (semispan / 3.0) * (root_chord + 2.0 * tip_chord) / (root_chord + tip_chord)


def hinge_loads(stack: HingeStack, hinge_moment: float, mean_chord: float,
                load_radius: float, stall_torque: float,
                spline_teeth: int = 15,
                pressure_limit: float = BEARING_PRESSURE_LIMIT) -> HingeLoads:
    """Loads and margins for one hinge.

    Bearing model: a single journal reacting an overhung load. The couple dominates and it
    is reacted by a pressure distribution that peaks at the bearing's ends, so the peak
    goes as 1/L^2 -- which is why the bearing LENGTH is the whole argument, and why a
    2.3 mm long bushing in the airframe wall cannot do this job no matter what it is made
    of. The uniform term from the direct force is added; it is small and it is not the
    reason for anything.

        p_max = 6*M/(d*L^2)  +  N/(d*L)
    """
    n = panel_normal_force(hinge_moment, mean_chord)
    m_wall = n * (load_radius - stack.tube_outer_radius)
    m_bearing = n * (load_radius - stack.bearing_centre)

    d, ell = stack.journal_dia, stack.bearing_length
    p = 6.0 * m_bearing / (d * ell * ell) + n / (d * ell)

    # Sleeve bending where it leaves the tube: solid section there, since the spline
    # socket is at the inboard end.
    z = math.pi * d ** 3 / 32.0
    sigma = m_wall / z

    # The coupling is sized by what the SERVO can do to it, not by what the air does.
    # A servo commanded into a stop delivers stall torque into the socket, and the aero
    # moment is an eighth of that.
    contact_area = spline_teeth * SPLINE_TOOTH_HEIGHT * stack.spline_engagement
    pitch_radius = stack.spline_dia / 2.0
    spline_p = (stall_torque / pitch_radius) / contact_area if contact_area > 0 else float("inf")

    return HingeLoads(
        normal_force=n,
        load_radius=load_radius,
        hinge_moment=hinge_moment,
        moment_at_wall=m_wall,
        moment_at_bearing=m_bearing,
        bearing_pressure=p,
        bearing_margin=pressure_limit / p if p > 0 else float("inf"),
        shaft_stress=sigma,
        shaft_margin={k: v / sigma for k, v in SHAFT_YIELD.items()},
        spline_torque=stall_torque,
        spline_pressure=spline_p,
    )


@dataclass(frozen=True)
class BondedCoupling:
    """The shaft-to-spline joint: a drilled socket, an adhesive, and fifteen cast keys."""

    socket_dia: float           # m, the drilled bore
    spline_dia: float           # m, crest diameter of the servo spline
    engagement: float           # m, how much of the spline is inside the socket
    journal_dia: float          # m, the shaft OD around it
    torque: float               # N m, servo stall -- the sizing case
    teeth: int
    adhesive_shear: float       # Pa
    max_radial_gap: float       # m

    @property
    def radial_gap(self) -> float:
        return (self.socket_dia - self.spline_dia) / 2.0

    socket_depth: float = 0.0   # m, drilled depth from the sleeve's inboard face

    @property
    def socket_wall(self) -> float:
        return (self.journal_dia - self.socket_dia) / 2.0

    @property
    def reservoir(self) -> float:
        """Depth left beyond the spline tip when the joint is home.

        Not slop. A close-fitting plug pushed into a blind hole full of liquid
        hydraulic-locks and either will not seat or blows the adhesive back out past the
        seal. This is where the surplus goes, and the spline's own valleys vent it along
        the axis on the way."""
        return self.socket_depth - self.engagement

    @property
    def bond_area(self) -> float:
        """The cylinder the adhesive is sheared on. Taken at the SOCKET bore, which is the
        adhesive-to-aluminium interface -- the weaker of the two, and the one that is a
        real adhesive bond rather than a mechanical key."""
        return math.pi * self.socket_dia * self.engagement

    @property
    def bond_shear(self) -> float:
        return self.torque / (self.bond_area * self.socket_dia / 2.0)

    @property
    def bond_margin(self) -> float:
        return self.adhesive_shear / self.bond_shear if self.bond_shear > 0 else math.inf

    @property
    def key_bearing_area(self) -> float:
        """The fifteen cast keys, in bearing against the steel spline teeth."""
        return self.teeth * SPLINE_TOOTH_HEIGHT * self.engagement

    @property
    def key_pressure(self) -> float:
        """What the keys carry if they carry everything. Reported, then IGNORED in the
        verdict: the adhesive shear above is computed as though the socket were smooth and
        the teeth did not exist, which is the conservative reading of a joint whose
        mechanical interlock is real but is formed by an adhesive rather than machined."""
        a = self.key_bearing_area
        return (self.torque / (self.spline_dia / 2.0)) / a if a > 0 else math.inf

    @property
    def shaft_torsion(self) -> float:
        """The shaft wall around the socket, in torsion. The section is an annulus here,
        not a circle -- that is the whole point of the wall check."""
        d, di = self.journal_dia, self.socket_dia
        z = math.pi * (d ** 4 - di ** 4) / (32.0 * (d / 2.0))
        return self.torque / z

    @property
    def shaft_torsion_margin(self) -> dict[str, float]:
        # Shear yield by von Mises, 0.577 of tensile yield.
        return {k: 0.577 * v / self.shaft_torsion for k, v in SHAFT_YIELD.items()}


def bonded_coupling(stack: HingeStack, stall_torque: float, teeth: int = 15,
                    adhesive_shear: float = RETAINING_COMPOUND_SHEAR,
                    max_radial_gap: float = RETAINING_COMPOUND_MAX_RADIAL_GAP,
                    crest_clearance: float = SPLINE_CREST_CLEARANCE) -> BondedCoupling:
    return BondedCoupling(
        socket_dia=stack.spline_dia + 2.0 * crest_clearance,
        spline_dia=stack.spline_dia,
        engagement=stack.spline_engagement,
        journal_dia=stack.journal_dia,
        torque=stall_torque,
        teeth=teeth,
        adhesive_shear=adhesive_shear,
        max_radial_gap=max_radial_gap,
        # Drill to the spline's full length, not to the engagement: the difference is the
        # reservoir, and it costs nothing in a sleeve that is 6.715 mm long.
        socket_depth=stack.spline_length,
    )


def check_coupling(c: BondedCoupling) -> HingeCheck:
    v: list[str] = []
    notes: list[str] = []

    if c.bond_margin < COUPLING_MARGIN_REQUIRED:
        v.append(f"adhesive shear margin is {c.bond_margin:.2f}x, short of "
                 f"{COUPLING_MARGIN_REQUIRED:.1f}x, at {c.bond_shear / 1e6:.2f} MPa against a "
                 f"{c.adhesive_shear / 1e6:.0f} MPa allowable")
    if c.radial_gap > c.max_radial_gap:
        v.append(f"the socket leaves {c.radial_gap * 1000:.3f} mm of radial gap, over the "
                 f"{c.max_radial_gap * 1000:.2f} mm a retaining compound is specified for. "
                 f"A wider socket lowers the STRESS and takes the adhesive outside the gap "
                 f"it is rated in, which is the trap in this joint")
    if c.socket_wall < 0.5e-3:
        v.append(f"socket wall is {c.socket_wall * 1000:.3f} mm; below 0.5 mm there is not "
                 f"enough section left to drill against")
    worst_shaft = min(c.shaft_torsion_margin.values())
    if worst_shaft < COUPLING_MARGIN_REQUIRED:
        v.append(f"the shaft wall around the socket runs at {c.shaft_torsion / 1e6:.1f} MPa "
                 f"in torsion, {worst_shaft:.2f}x on the weakest candidate alloy")

    notes.append(f"socket dia {c.socket_dia * 1000:.3f} on a dia {c.spline_dia * 1000:.1f} "
                 f"spline: {c.radial_gap * 1000:.3f} mm radial, a slip fit on the crests "
                 f"with the valleys left open for the compound to key into")
    notes.append(f"socket wall {c.socket_wall * 1000:.3f} mm, shaft torsion "
                 f"{c.shaft_torsion / 1e6:.1f} MPa "
                 f"({', '.join(f'{k} {m:.1f}x' for k, m in c.shaft_torsion_margin.items())})")
    notes.append(f"the fifteen cast keys would carry it at {c.key_pressure / 1e6:.1f} MPa "
                 f"of bearing if they carried everything -- NOT counted in the verdict, "
                 f"which treats the socket as smooth")
    if c.reservoir <= 0.0:
        v.append(f"the socket is {c.socket_depth * 1000:.2f} mm deep against "
                 f"{c.engagement * 1000:.2f} mm of engagement, so there is nowhere for "
                 f"surplus adhesive to go and the joint will hydraulic-lock before it seats")
    else:
        notes.append(f"socket drilled {c.socket_depth * 1000:.2f} mm deep against "
                     f"{c.engagement * 1000:.2f} mm engaged, leaving {c.reservoir * 1000:.2f} mm "
                     f"of reservoir for surplus compound")
    notes.append(f"releases at about {RETAINING_COMPOUND_RELEASE_C:.0f} C, which is the "
                 f"only reason a servo can be changed once its shaft is on")

    return HingeCheck(ok=not v, violations=v, notes=notes)


@dataclass
class HingeCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_hinge_stack(stack: HingeStack, loads: HingeLoads) -> HingeCheck:
    """Everything that has to be true for this hinge to be buildable and to carry its load.

    Written as a CHECK and not as a comment because the three defects it catches were all
    documented as prose first, in a file that the model did not read. `recovery.check_packing`
    is the precedent: the recovery bay was 4.5 cal because it was typed, until something
    verified it.
    """
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    # --- the clash that the sweep could not see -------------------------------------
    if stack.sleeve_inboard < stack.servo_output_face:
        v.append(
            f"shaft sleeve starts at R {stack.sleeve_inboard * mm:.3f} mm, inboard of the "
            f"servo output face at R {stack.servo_output_face * mm:.3f} -- the shaft is "
            f"inside the servo")

    # --- the fit that no interference check can see ---------------------------------
    # Defect 1. A dia 5.000 shaft in a dia 5.000 hole is not an interference, so nothing
    # in the CAD will ever object to it. It is still a hinge that cannot turn.
    if stack.running_clearance < MIN_RUNNING_CLEARANCE:
        where = "its bearing" if stack.has_bearing else "the airframe wall itself"
        v.append(
            f"running clearance between the dia {stack.journal_dia * mm:.3f} journal and "
            f"{where} is {stack.running_clearance * mm:.3f} mm, against a "
            f"{MIN_RUNNING_CLEARANCE * mm:.3f} mm minimum -- zero clearance is not an "
            f"interference, so no interference check will ever report this")
    if not stack.has_bearing:
        v.append(
            "the shaft turns directly in the airframe wall; there is no bearing in the "
            "load path, so the panel bending moment is carried by a 2.3 mm long "
            "fibreglass hole and by the servo's own output shaft")
    elif stack.seat_fit > 0:
        v.append(
            f"the bearing is {stack.seat_fit * mm:.3f} mm loose in its seat; a pressed "
            f"bearing wants interference, not clearance")

    # --- the coupling ---------------------------------------------------------------
    if stack.spline_engagement <= 0:
        v.append("the servo spline does not reach the shaft sleeve at all")
    elif stack.spline_engagement_fraction < 0.75:
        v.append(
            f"spline engagement {stack.spline_engagement * mm:.3f} mm is only "
            f"{stack.spline_engagement_fraction * 100:.0f}% of the {stack.spline_length * mm:.1f} mm "
            f"spline; the coupling is not rated for the servo's stall torque")

    socket_wall = (stack.journal_dia - stack.spline_dia - 2 * SPLINE_TOOTH_HEIGHT) / 2.0
    if socket_wall < 0.5e-3:
        v.append(
            f"sleeve wall over the spline socket is {socket_wall * mm:.3f} mm; below "
            f"0.5 mm there is nothing left to cut teeth into")
    else:
        notes.append(f"sleeve wall over the spline socket {socket_wall * mm:.3f} mm")

    # --- the bearing ----------------------------------------------------------------
    if stack.bearing_inboard < stack.servo_output_face:
        v.append(
            f"bearing reaches R {stack.bearing_inboard * mm:.3f} mm, inboard of the servo "
            f"output face at R {stack.servo_output_face * mm:.3f}")
    if loads.bearing_margin < BEARING_MARGIN_REQUIRED:
        v.append(
            f"bearing pressure {loads.bearing_pressure / 1e6:.1f} MPa against a "
            f"{BEARING_PRESSURE_LIMIT / 1e6:.0f} MPa allowable is only "
            f"{loads.bearing_margin:.2f}x, short of {BEARING_MARGIN_REQUIRED:.1f}x")
    worst_shaft = min(loads.shaft_margin.values())
    if worst_shaft < SHAFT_MARGIN_REQUIRED:
        notes.append(
            f"shaft margin is {worst_shaft:.1f}x in the weakest listed material; specify "
            f"a stronger one")

    # --- does it fit in the airframe -------------------------------------------------
    if stack.wall_bore_dia > 3.0 * stack.wall_thickness:
        notes.append(
            f"the wall bore is dia {stack.wall_bore_dia * mm:.2f} mm in a "
            f"{stack.wall_thickness * mm:.1f} mm wall -- check the tube, not just the hinge")
    if stack.housing_collar_height > 0:
        notes.append(
            f"{stack.housing_collar_height * mm:.3f} mm of the bearing sits inboard of the "
            f"tube ID and needs a housing collar; that is a requirement on the printed bay")
    if stack.boss_collision_margin <= 0:
        v.append(
            f"the four servo cable bosses collide on the rocket axis "
            f"({stack.boss_collision_margin * mm:.2f} mm)")
    elif stack.boss_collision_margin < 1.0e-3:
        v.append(
            f"only {stack.boss_collision_margin * mm:.2f} mm between adjacent servo cable "
            f"bosses at the axis")

    return HingeCheck(ok=not v, violations=v, notes=notes)


# ---------------------------------------------------------------------------------------
# The two layouts. AS_BUILT is what the Onshape model held before this file existed; it is
# kept so the check can be shown to FAIL on it, which is the only proof that the check
# would have caught the defect.
# ---------------------------------------------------------------------------------------

def as_built(tube_outer_radius: float, wall: float, geometry) -> HingeStack:
    """The layout as the Onshape model held it in August 2026, read off the REST API.

    Servo output face R 37.185. A solid dia 5.000 shaft from R 29.400 to R 40.200 -- the
    volume comes back as 212.058 mm^3 against 212.058 for a solid cylinder, so there is no
    bore in it and nothing was ever cut away for the servo. The wall pass-through is
    dia 5.000, cut from that same shaft's sketch. There is no bearing.

    Kept, and exercised by scripts/hinge_report.py, so the check can be shown to FAIL on
    it. A check that has never failed is not evidence of anything.
    """
    return HingeStack(
        tube_outer_radius=tube_outer_radius,
        wall_thickness=wall,
        panel_root=40.200e-3,
        servo_output_face=37.185e-3,
        servo_depth=geometry.depth_from_top,
        servo_boss_half_width=geometry.case_width / 2.0,
        spline_length=geometry.shaft_proud_of_top,
        spline_dia=geometry.spline_dia,
        journal_dia=5.000e-3,
        # No bearing, so the airframe wall is the bearing whether anyone meant it to be
        # or not, and its length is the wall thickness.
        bearing_length=wall,
        bearing_wall=0.0,
        wall_bore_dia=5.000e-3,
        sleeve_gap=29.400e-3 - 37.185e-3,   # negative: the shaft starts inside the servo
    )


SERVO_INBOARD_MOVE = 4.000e-3
JOURNAL_DIA = 6.000e-3
BEARING_LENGTH = 6.000e-3
BEARING_WALL = 1.000e-3


def selected(tube_outer_radius: float, wall: float, geometry,
             servo_inboard_move: float = SERVO_INBOARD_MOVE) -> HingeStack:
    """The layout this module selects.

    Three changes, and they are one decision, not three:

      - The servo moves 4.000 mm inboard. Nothing else creates room. Between the servo's
        output face and the panel root there were 3.015 mm, the airframe wall took 2.300
        of them, and a plain bearing that can carry this load needs about 4.5 mm of
        length -- the peak pressure under an overhung load goes as 1/L^2, so a 2.3 mm
        bushing is not a worse answer than a 6 mm one, it is 7x worse. Moving the PANEL
        outboard would also work and would change frozen aerodynamics. Moving the servo
        spends central void, which is a budget line, not a frozen one.

      - The shaft becomes a dia 6 sleeve rather than a dia 5 rod. Not for strength; dia 5
        is strong enough. It is so that a dia 4 spline socket leaves 0.8 mm of wall to cut
        teeth into instead of 0.3 mm.

      - The wall bore stops being a copy of the shaft's sketch and becomes a bearing seat,
        dimensioned off the bearing OD with a press fit. The shaft then turns in the
        bearing, with a real running clearance, instead of in the airframe.

    4.000 mm is the largest move the four servo cable bosses allow with a millimetre to
    spare before they meet on the rocket axis. It costs 8.0 mm of central void everywhere:
    the constricted band where the cable bosses sit goes dia 20.17 -> dia 12.17 over 8.2 mm
    of length, and the wider band alongside the servo cases goes dia 40.77 -> dia 32.77
    over 29.5 mm. Both are 8 mm smaller, because the whole servo moved, and the wiring has
    to fit the smaller of them.
    """
    face = 37.185e-3 - servo_inboard_move
    bearing_od = JOURNAL_DIA + 2.0 * BEARING_WALL
    return HingeStack(
        tube_outer_radius=tube_outer_radius,
        wall_thickness=wall,
        panel_root=40.200e-3,
        servo_output_face=face,
        servo_depth=geometry.depth_from_top,
        servo_boss_half_width=geometry.case_width / 2.0,
        spline_length=geometry.shaft_proud_of_top,
        spline_dia=geometry.spline_dia,
        journal_dia=JOURNAL_DIA,
        bearing_length=BEARING_LENGTH,
        bearing_wall=BEARING_WALL,
        wall_bore_dia=bearing_od,   # nominal, dia 8 H7 -- a standard reamer
        sleeve_gap=0.300e-3,
    )


# =======================================================================================
# THE SLEEVE-TO-PANEL JOINT
#
# The last link in the load path, and the one docs/05 has carried as "the next real design
# decision, in the place the spline coupling used to occupy".
#
# The problem in one line: the sleeve ends flush at the panel root, R 40.200, and the panel
# is 3.0 mm thick, so a dia 6 shaft cannot simply enter it. And this joint is not the easy
# end of the load path -- it is the HARD end. Every number in the stack above gets smaller
# going inboard, because the bearing takes the couple out; going outboard the moment is at
# its maximum, 0.72 N m at the panel root, and it has to be handed into 3.0 mm of G10.
#
# Four ways to make this joint, and the reason three of them lose:
#
#   ROOT BOSS -- thicken the panel root into a hub and bore it for the dia 6 sleeve. Needs
#     about 9 mm of local thickness for a dia 6 blind bore with any wall. The panel is 3.0
#     and its thickness is frozen aerodynamics: t/c drives the flutter margin, which the
#     0.40 taper already spent down from 5.42x to 4.46x (configure.py). Rejected: it moves
#     a frozen number to solve a joint problem.
#
#   EXTERNAL CLEVIS -- a fork on the sleeve straddling the panel, cross-bolted. Structurally
#     the best of the four and the easiest to build. It also stands proud of the panel
#     surface, at the root, in the highest-velocity flow the panel sees, on all four panels.
#     Rejected on drag and on the interference sweep it would invalidate.
#
#   ONE PIECE -- machine shaft and panel from a single aluminium billet. No joint at all,
#     which is the honest structural answer. It changes the panel from 1850 kg/m^3 G10 to
#     2700 kg/m^3 aluminium: +38 g per panel, +154 g on the vehicle, all of it AFT of the
#     CG at the worst possible station for a static margin that already needs 100 g of nose
#     ballast to satisfy R1. Rejected on mass and CG, not on structure. Worth revisiting if
#     the ballast budget ever grows.
#
#   TANG IN A SLOT -- the sleeve's outboard end is milled to a flat blade that lands in a
#     slot in the panel root and is bonded there. Selected. It spends no aerodynamics, no
#     mass and no CG, and it moves the whole problem into the one place that has room: the
#     PLANE of the panel, which is 67.5 mm of root chord, rather than its thickness.
#
# What the tang costs, and it is a real cost that belongs in the build sheet rather than
# in a footnote: a 1.8 mm slot milled 30 mm deep into the edge of a 3.0 mm plate is a
# 17:1 depth-to-width blind cut, which is not a thing you machine. The panel therefore
# stops being a plate and becomes a LAMINATE -- 0.6 / 1.8 / 0.6 mm G10, bonded, with the
# core cut away where the tang goes. That is a manufacturing change, and it is the reason
# this joint is written up here rather than dimensioned in a table: the answer to "how does
# the shaft meet the panel" turned out to be "the panel is made differently".
# =======================================================================================

# Minimum skin left over a tang slot. Below this the panel is a handling risk before it is
# ever a stress one -- a 0.5 mm G10 skin over a 14 mm slot is a part that gets damaged in
# the lay-up jig, not in flight.
MIN_SKIN_THICKNESS = 0.5e-3

# Material between the tang's forward corner and the panel's leading edge. The leading
# edge gets bevelled or rounded for aerodynamics, the slot carries a bond line, and a
# fibreglass panel has to survive its own lay-up jig: 5 mm covers all three with something
# left over. Nothing subtler is justified until the LE profile is actually drawn.
MIN_EDGE_CLEARANCE = 5.0e-3

# Simply-supported is used for the skin over the slot. The skin is continuous into the
# panel at both slot edges, so the truth is nearer fixed-fixed, which carries the same
# pressure at 2/3 of the stress. Taking the conservative end is worth about 1.5x of margin
# that is deliberately not being claimed.
SKIN_BENDING_COEFFICIENT = 8.0


@dataclass(frozen=True)
class RootJoint:
    """A flat tang on the sleeve, bonded into a slot in the canard panel root.

    All lengths in metres. `engagement` is measured OUTBOARD from the panel root face,
    which is the same R the hinge stack's `panel_root` names, so the two cannot drift.
    """

    panel_root: float          # R of the panel root face
    panel_thickness: float
    panel_root_chord: float
    panel_tip_chord: float
    panel_semispan: float
    panel_sweep: float         # axial offset, root LE to tip LE
    root_le_to_hinge: float    # axial distance from the root LE aft to the hinge axis
    body_radius: float         # R of the tube OD -- the THEORETICAL root, where the
                               # planform's semispan and sweep are measured from. This is
                               # NOT `panel_root`: the panel face stands 0.5 mm off the
                               # tube, so a length measured from the panel and a length
                               # measured from the planform differ by that standoff. The
                               # CAD is what caught it -- panel 0 runs R 40.20 to 107.19,
                               # and 107.19 is 39.700 + 67.490, not 40.200 + 67.490.
    sleeve_dia: float
    tang_thickness: float
    tang_width: float
    engagement: float          # how far the tang reaches OUTBOARD into the panel
    bond_line: float           # adhesive gap on every tang face. NOT cosmetic: the slot
                               # is the tang plus this all round, so it is the SLOT that
                               # eats the panel and the slot that the skin spans. Leaving
                               # it out of the skin overstated the skin by the square of
                               # (tang / slot) -- 1.44x here -- which is the difference
                               # between passing and failing.

    # ---- where the panel's edges are, relative to the hinge axis ---------------------
    # Axial, positive AFT, origin on the hinge axis. This is the frame the tang lives in:
    # the tang is a fixed band [-w/2, +w/2] about the hinge, because it is the end of a
    # shaft that turns about the hinge.

    # Everything below takes a RADIUS, not a span coordinate. `HingeStack` says why in its
    # own docstring -- radius is the coordinate these parts are actually positioned in --
    # and this module got it wrong once by taking `engagement` (measured from the panel
    # root face) into a planform function (measured from the tube surface), which quietly
    # under-read the leading edge by 0.36 mm.

    def _span_at(self, radius: float) -> float:
        """Spanwise station in PLANFORM coordinates, i.e. from the theoretical root."""
        return radius - self.body_radius

    def leading_edge(self, radius: float) -> float:
        """Axial station of the leading edge, relative to the hinge axis, positive aft."""
        return (self.panel_sweep * self._span_at(radius) / self.panel_semispan
                - self.root_le_to_hinge)

    def chord(self, radius: float) -> float:
        t = self._span_at(radius) / self.panel_semispan
        return self.panel_root_chord + (self.panel_tip_chord - self.panel_root_chord) * t

    def trailing_edge(self, radius: float) -> float:
        return self.leading_edge(radius) + self.chord(radius)

    @property
    def tang_tip_radius(self) -> float:
        return self.panel_root + self.engagement

    @property
    def leading_edge_clearance(self) -> float:
        """Material between the tang's forward corner and the panel's leading edge, at the
        TANG TIP, which is where the swept LE has come closest.

        THIS IS THE CONSTRAINT THAT ACTUALLY LIMITS THE TANG, and the first version of this
        module did not have it. The panel is swept 35.4 degrees, so its leading edge runs
        aft at 0.71 mm per mm of span while the tang stays in a fixed axial band. Deep
        enough, and the tang comes out through the leading edge of the panel -- which is
        not a stress failure, it is a part that cannot be made.
        """
        return -self.tang_width / 2.0 - self.leading_edge(self.tang_tip_radius)

    @property
    def trailing_edge_clearance(self) -> float:
        return self.trailing_edge(self.tang_tip_radius) - self.tang_width / 2.0

    @property
    def slot_thickness(self) -> float:
        """The cut in the panel: the tang plus a bond line on each face."""
        return self.tang_thickness + 2.0 * self.bond_line

    @property
    def slot_width(self) -> float:
        return self.tang_width + 2.0 * self.bond_line

    @property
    def skin_thickness(self) -> float:
        """What is left of the panel on each side of the SLOT -- not of the tang.

        This is the number that decides the joint: it goes as the square in the skin's
        bending stress, so every extra tenth the slot takes costs the skin more than it
        looks like it should.

        Built as a laminate, this IS the skin sheet's own thickness, and the slot IS the
        core sheet's, which is why the stack has to be picked from thicknesses that are
        actually sold rather than from whatever the optimiser liked.
        """
        return (self.panel_thickness - self.slot_thickness) / 2.0

    @property
    def tang_section_modulus(self) -> float:
        """Bending about the WEAK axis. The panel's aerodynamic load is perpendicular to
        the panel, so it bends the blade through its thickness, not its width. Getting
        this the other way round would flatter the joint by (w/t)^2 -- a factor of 60."""
        return self.tang_width * self.tang_thickness ** 2 / 6.0

    @property
    def slot_span_fraction(self) -> float:
        """Engagement as a fraction of the SEMISPAN.

        Span, not chord. The tang is the outboard end of a radial shaft, so it reaches
        along the span; the chord is what its WIDTH lies along. The first version of this
        module divided by the root chord and got the right number anyway, because
        `canard_root_cal` and `canard_semispan_cal` are both 0.85 and the two lengths are
        both 67.490 mm. Change either one and the check would have silently read the wrong
        dimension -- the same class of error as the sketch that measured to a circle's
        tangent instead of its centre (docs/01).
        """
        return self.engagement / self.panel_semispan

    @property
    def transition_stress_ratio(self) -> float:
        """Round sleeve section modulus over tang section modulus, at the same station.

        The sleeve goes from a dia 6 round to a flat blade at the panel root, which is the
        maximum-moment station, and the stress steps up by this factor across that
        transition. It is the reason the transition needs a generous blend radius and not
        a shoulder."""
        round_z = math.pi * self.sleeve_dia ** 3 / 32.0
        return round_z / self.tang_section_modulus


@dataclass(frozen=True)
class RootJointLoads:
    moment: float               # N*m, bending at the panel root
    normal_force: float         # N
    torque: float               # N*m about the hinge axis; the SERVO's stall, not the air's
    tang_bending_stress: float
    tang_margin: dict[str, float]
    slot_pressure_bending: float    # Pa, peak on the slot face from the couple
    slot_pressure_torque: float     # Pa, peak from the stall torque, at the slot edges
    skin_bending_stress: float      # Pa, the skin working as a plate across the slot
    bond_shear: float               # Pa, average over the bonded tang faces


def root_joint_loads(joint: RootJoint, normal_force: float, load_radius: float,
                     stall_torque: float) -> RootJointLoads:
    """Loads in the tang joint.

    Two load cases arrive here and they are NOT the same one twice:

      * the air bends the panel, giving a couple about an axis in the panel plane. That is
        the big one, and it is reacted by pressure on the slot faces peaking at the slot
        mouth -- the same 6M/(b*L^2) + N/(b*L) form as the bearing, one interface further
        out, because it is the same physics.

      * the SERVO twists the panel, giving a torque about the hinge axis. Sized by stall
        and not by the aero hinge moment, for the reason the spline socket is: a servo
        driven into a stop delivers stall torque to everything downstream of it, and stall
        is 8.7x the aero moment.

    The torque's pressure peaks at the two slot EDGES, across the width, and the skin is
    supported at exactly those edges -- so it barely bends the skin even though its peak
    pressure is comparable. It is checked against bearing strength, not skin bending, and
    the two pressures are deliberately not summed into one skin stress. Summing them would
    fail this joint on a load path that does not exist.
    """
    m = normal_force * (load_radius - joint.panel_root)
    b, ell, w = joint.tang_width, joint.engagement, joint.tang_width

    p_bend = 6.0 * m / (b * ell * ell) + normal_force / (b * ell)
    p_torque = 6.0 * stall_torque / (ell * w * w)

    sigma_tang = m / joint.tang_section_modulus

    # The skin over the slot, as a strip spanning the slot width under the slot pressure.
    m_per_width = p_bend * joint.slot_width ** 2 / SKIN_BENDING_COEFFICIENT
    sigma_skin = 6.0 * m_per_width / joint.skin_thickness ** 2 if joint.skin_thickness > 0 else math.inf

    # The bond carries the direct force and keeps the tang in the slot; the couple is
    # carried in bearing, not in shear, which is why this number is small and is not the
    # sizing case. Two faces.
    bond_area = 2.0 * joint.tang_width * joint.engagement
    tau_bond = normal_force / bond_area

    return RootJointLoads(
        moment=m,
        normal_force=normal_force,
        torque=stall_torque,
        tang_bending_stress=sigma_tang,
        tang_margin={k: v / sigma_tang for k, v in SHAFT_YIELD.items()},
        slot_pressure_bending=p_bend,
        slot_pressure_torque=p_torque,
        skin_bending_stress=sigma_skin,
        bond_shear=tau_bond,
    )


def check_root_joint(joint: RootJoint, loads: RootJointLoads) -> HingeCheck:
    """Everything that has to be true for the tang joint to carry its load and be built."""
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    if joint.tang_thickness >= joint.panel_thickness:
        v.append(
            f"the tang is {joint.tang_thickness * mm:.2f} mm thick in a "
            f"{joint.panel_thickness * mm:.2f} mm panel -- there is no panel left")
    elif joint.skin_thickness < MIN_SKIN_THICKNESS:
        v.append(
            f"skin over the slot is {joint.skin_thickness * mm:.3f} mm, under the "
            f"{MIN_SKIN_THICKNESS * mm:.2f} mm minimum; that is a handling risk before it "
            f"is a stress one")
    else:
        notes.append(f"skin over the slot {joint.skin_thickness * mm:.2f} mm each side")

    worst_tang = min(loads.tang_margin.values())
    best_tang = max(loads.tang_margin.values())
    if best_tang < SHAFT_MARGIN_REQUIRED:
        v.append(
            f"tang bending {loads.tang_bending_stress / 1e6:.1f} MPa fails "
            f"{SHAFT_MARGIN_REQUIRED:.1f}x in EVERY listed material (best is "
            f"{best_tang:.2f}x); the tang is too thin or too narrow")
    elif worst_tang < SHAFT_MARGIN_REQUIRED:
        notes.append(
            f"tang margin is {worst_tang:.1f}x in the weakest listed material and "
            f"{best_tang:.1f}x in the strongest -- this joint SELECTS the material rather "
            f"than tolerating any of them")

    skin_margin = (G10_FLEXURAL / loads.skin_bending_stress
                   if loads.skin_bending_stress > 0 else math.inf)
    if joint.skin_thickness <= 0:
        pass  # "there is no panel left" above already said this; a skin stress of infinity
              # adds nothing and reads like a second, different problem.
    elif skin_margin < SHAFT_MARGIN_REQUIRED:
        v.append(
            f"the skin over the slot works at {loads.skin_bending_stress / 1e6:.0f} MPa "
            f"against a {G10_FLEXURAL / 1e6:.0f} MPa flexural allowable, only "
            f"{skin_margin:.2f}x; a wider tang makes this WORSE, not better, because the "
            f"skin spans the SLOT, which is the tang plus a bond line all round")

    for label, p in (("bending", loads.slot_pressure_bending),
                     ("stall torque", loads.slot_pressure_torque)):
        m = G10_BEARING / p if p > 0 else math.inf
        if m < SHAFT_MARGIN_REQUIRED:
            v.append(f"slot bearing pressure from {label} is {p / 1e6:.2f} MPa, only {m:.2f}x")

    bond_margin = (G10_INTERLAMINAR_SHEAR / loads.bond_shear
                   if loads.bond_shear > 0 else math.inf)
    if bond_margin < SHAFT_MARGIN_REQUIRED:
        v.append(f"bond shear {loads.bond_shear / 1e6:.2f} MPa is only {bond_margin:.2f}x")

    # THE ONE THAT ACTUALLY BINDS. A depth rule on its own does not catch this: at 60% of
    # the semispan the tang stands 5.2 mm PROUD of the swept leading edge, and a rule that
    # passes an unbuildable part is worse than no rule.
    if joint.leading_edge_clearance < MIN_EDGE_CLEARANCE:
        where = ("stands proud of" if joint.leading_edge_clearance < 0 else "is only "
                 f"{joint.leading_edge_clearance * mm:.2f} mm inside")
        v.append(
            f"at its tip the tang {where} the panel's leading edge "
            f"({joint.leading_edge_clearance * mm:+.2f} mm against a "
            f"{MIN_EDGE_CLEARANCE * mm:.1f} mm minimum) -- the panel is swept "
            f"{math.degrees(math.atan2(joint.panel_sweep, joint.panel_semispan)):.1f} deg, so its "
            f"leading edge runs aft {joint.panel_sweep / joint.panel_semispan:.2f} mm per mm of "
            f"span while the tang stays in a fixed axial band")
    else:
        notes.append(
            f"tang tip clears the swept leading edge by "
            f"{joint.leading_edge_clearance * mm:.2f} mm and the trailing edge by "
            f"{joint.trailing_edge_clearance * mm:.1f} mm")

    if joint.slot_span_fraction > 0.6:
        v.append(
            f"the slot runs {joint.slot_span_fraction * 100:.0f}% of the semispan; past "
            f"about 60% it reaches the panel's own structure rather than its root")
    else:
        notes.append(
            f"slot is {joint.engagement * mm:.1f} mm into a {joint.panel_semispan * mm:.1f} mm "
            f"semispan ({joint.slot_span_fraction * 100:.0f}%)")

    # These two describe how to BUILD the joint, so they are only meaningful once the
    # joint is buildable at all. Emitting them for a tang thicker than its panel produces
    # a negative skin thickness in a manufacturing instruction, which is worse than silence.
    if joint.skin_thickness > 0:
        notes.append(
            f"stress steps up {joint.transition_stress_ratio:.1f}x from the round sleeve to "
            f"the tang, at the maximum-moment station -- blend the transition, do not "
            f"shoulder it")
        notes.append(
            f"PANEL IS A LAMINATE: {joint.skin_thickness * mm:.1f} / "
            f"{joint.slot_thickness * mm:.1f} / {joint.skin_thickness * mm:.1f} mm bonded G10, "
            f"= {joint.panel_thickness * mm:.1f} mm, the middle sheet cut away over "
            f"{joint.slot_width * mm:.1f} x {joint.engagement * mm:.1f} mm at the root. Cutting "
            f"that slot into a solid plate instead would be a "
            f"{joint.engagement / joint.slot_thickness:.0f}:1 deep blind cut needing a "
            f"slitting saw; as a laminate it is a flat shape cut before bonding. Every "
            f"thickness here is a stocked sheet -- check that before changing any of them")

    return HingeCheck(ok=not v, violations=v, notes=notes)


# The tang, and every one of these is set by something you can BUY or by geometry, not by
# an optimiser running free.
#   thickness  the middle sheet of the laminate, 2.0 mm stocked, less a 0.1 mm bond line
#              each face. So the slot IS the sheet and the skins ARE the outer sheets.
#   width      where the tang and the skin land on the same margin, 2.46x and 2.45x.
#   engagement as deep as the swept leading edge allows with 6 mm to spare.
TANG_THICKNESS = 1.800e-3
TANG_WIDTH = 11.900e-3
TANG_ENGAGEMENT = 25.500e-3
BOND_LINE = 0.100e-3


def swept_out_root_joint(stack: HingeStack, canards) -> RootJoint:
    """The 1.8 x 14 x 30 tang this module selected BEFORE the leading edge was checked.

    Every stress margin in it is better than the selected joint's -- tang and skin both
    2.9x against 2.6x -- and it is still not buildable, because it leaves 2.26 mm of panel
    ahead of it against a 5 mm minimum. Kept, and exercised by scripts/hinge_report.py, for
    the same reason `as_built` and `naive_root_joint` are: a check that has never failed is
    not evidence of anything, and this is the only case that fails on GEOMETRY while
    passing on strength.
    """
    return _joint(stack, canards, 1.800e-3, 14.000e-3, 30.000e-3)


def selected_root_joint(stack: HingeStack, canards) -> RootJoint:
    """The joint this module selects: a 1.8 x 11.5 mm tang, 25.0 mm into the panel root.

    How the three numbers were picked, because they are coupled and none is free:

      * THICKNESS 1.8 mm sets the skins at 0.6 mm each. Thicker tang, stronger tang,
        weaker skin -- and the skin's stress goes as 1/t^2, so the trade is sharp. This is
        the one number that did NOT move when the leading-edge constraint arrived, which
        is why the panel is still a 0.6/2.0/0.6 laminate.

        Those three numbers are SHEETS TO BUY and they must sum to the 3.2 mm panel. The
        middle one is the SLOT (2.0 mm, stocked), not the tang (1.8 mm): the tang sits in
        it with a 0.1 mm bond line on each face. Quoting the tang as the middle layer gives
        0.6/1.8/0.6 = 3.0 mm, which is a 0.2 mm hole in the panel and the wrong order at
        the supplier. Both this docstring and scripts/hinge_report.py said exactly that
        until Aug 2026.

      * WIDTH 11.5 mm. A wider tang carries more (sigma goes as 1/w) but its skin spans
        further, and skin stress rises with width overall. It also pushes the tang's
        forward corner towards the leading edge. So width is paid for twice.

      * ENGAGEMENT 25.0 mm, and THIS IS THE ONE THAT WAS WRONG TWICE. The first version of this
        module put it at 30 mm and called depth "bought cheaply -- it improves everything
        at once and is not paid for anywhere", reasoning that slot pressure goes as 1/L^2.
        That is true and it is not the constraint. **The panel is swept 35.4 degrees**, so
        its leading edge runs aft 0.71 mm for every mm of span while the tang stays in a
        fixed axial band about the hinge. Depth is paid for in leading-edge material, at
        better than half a millimetre per millimetre. 30 mm left 2.26 mm of panel ahead of
        the tang; the depth rule that was supposed to catch this allowed 40.5 mm, where the
        tang stands 5.18 mm PROUD of the leading edge and the part cannot be made at all.

    So the shape of the trade is the opposite of what it first looked like: depth is the
    EXPENSIVE axis, not the free one.

    Wrong the second time by 0.36 mm, and only the CAD caught it. `engagement` is measured
    from the PANEL ROOT FACE at R 40.200; the planform's sweep and semispan are measured
    from the THEORETICAL root at the tube surface, R 39.700. Feeding one into the other
    over-read the leading-edge clearance by the 0.500 mm standoff times the 0.71 sweep
    gradient. The model agreed with itself and disagreed with the model in Onshape, where
    panel 0 runs R 40.20 to 107.19 -- and 107.19 is 39.700 + 67.490, not 40.200 + 67.490.
    Everything on this joint is now indexed by RADIUS, which is what `HingeStack` already
    said to do and what this class had not been doing.

    25.0 mm delivers 6.71 mm of leading edge against a 5.0 mm requirement, at 2.5x on the
    skin and 2.4x on the tang against a 2.0x requirement.
    """
    return _joint(stack, canards, TANG_THICKNESS, TANG_WIDTH, TANG_ENGAGEMENT)


# Fraction of MAC at which the hinge sits, matching packaging.hinge_moment()'s default
# and scripts/make_cad_profiles.HINGE_FRAC. Forward of the 0.25c panel CP, so restoring.
HINGE_FRAC_OF_MAC = 0.20


def _joint(stack: HingeStack, canards, thickness: float, width: float,
           engagement: float, bond: float = BOND_LINE) -> RootJoint:
    """Build a RootJoint against a real panel. Every planform number comes from the FinSet
    and the hinge station is derived, so the joint cannot drift from the aerodynamics."""
    taper = canards.tip_chord / canards.root_chord
    mac = (2.0 / 3.0) * canards.root_chord * (1 + taper + taper ** 2) / (1 + taper)
    y_mac = (canards.semispan / 3.0) * (1 + 2 * taper) / (1 + taper)
    x_le_mac = canards.sweep_length * y_mac / canards.semispan
    return RootJoint(
        panel_root=stack.panel_root,
        panel_thickness=canards.thickness,
        panel_root_chord=canards.root_chord,
        panel_tip_chord=canards.tip_chord,
        panel_semispan=canards.semispan,
        panel_sweep=canards.sweep_length,
        root_le_to_hinge=x_le_mac + HINGE_FRAC_OF_MAC * mac,
        body_radius=canards.body_diameter / 2.0,
        sleeve_dia=stack.journal_dia,
        tang_thickness=thickness,
        tang_width=width,
        engagement=engagement,
        bond_line=bond,
    )


def naive_root_joint(stack: HingeStack, canards) -> RootJoint:
    """What the model implies today, and what anyone would draw first: the dia 6 sleeve
    simply entering the panel.

    Kept, and exercised by scripts/hinge_report.py, so `check_root_joint` can be shown to
    FAIL on it. The same reason `as_built` is kept: a check that has never failed is not
    evidence of anything.
    """
    return _joint(stack, canards, stack.journal_dia, stack.journal_dia, stack.journal_dia)


def canard_hinge_station(rocket) -> float:
    """Axial station of the canard hinge line, metres from the nose tip.

    DERIVED, not typed. The hinge sits at `packaging.hinge_moment`'s `hinge_frac` of the
    MAC, aft of the MAC's own leading edge, which is where scripts/make_cad_profiles.py
    puts the HINGE layer in the DXF and where the Onshape sketches are dimensioned to. It
    comes out at 68.27 mm aft of the module's forward face, which is the number docs/05
    carries for the `Hinge Plane` offset -- so this function is also the check that the CAD
    and the analysis still agree about where the hinge is.

    That check is not hypothetical. The hinge station has been wrong in this project once
    already, by 4.4x in hinge moment, because a sketch dimension measured to a circle's
    tangent instead of its centre and a datum plane drove nothing (docs/01, corrections to
    Sketch 3 and the Hinge Plane).
    """
    c = rocket.canards
    taper = c.tip_chord / c.root_chord
    mac = (2.0 / 3.0) * c.root_chord * (1 + taper + taper ** 2) / (1 + taper)
    y_mac = (c.semispan / 3.0) * (1 + 2 * taper) / (1 + taper)
    x_le_mac = c.sweep_length * y_mac / c.semispan
    return c.x_root_le + x_le_mac + HINGE_FRAC_OF_MAC * mac
