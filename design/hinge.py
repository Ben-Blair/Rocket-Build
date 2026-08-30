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

# Static permissible surface pressure for a polymer plain bearing running on a hard shaft.
# 80 MPa is the igus iglidur G class; iglidur J is 35 MPa and iglidur X is ~150 MPa. The
# design factor below is applied on top, so pick the class AFTER reading the margin.
BEARING_PRESSURE_LIMIT = 80.0e6  # Pa

# Required ratio of allowable to actual. 2.0 to match the servo torque margin requirement
# in docs/00 -- a hinge whose bearing is marginal is not a better hinge than one whose
# servo is marginal.
BEARING_MARGIN_REQUIRED = 2.0

# Yield strengths for the shaft. The shaft is small and highly stressed at the bearing;
# 6061-T6 works but 303 stainless is the sensible part to buy for a 7 mm long journal.
SHAFT_YIELD = {"6061-T6": 276.0e6, "303 stainless": 240.0e6, "4140 steel": 655.0e6}
SHAFT_MARGIN_REQUIRED = 2.0

# Minimum diametral running clearance between a turning shaft and whatever it turns
# inside. Any positive number would have caught the defect this file exists for -- the
# wall pass-through was dia 5.000 on dia 5.000, which is not an interference and so is
# invisible to every interference check ever written. 0.020 mm is an H7/g6 running fit on
# a 6 mm shaft; below that a hinge binds.
MIN_RUNNING_CLEARANCE = 0.020e-3  # m, diametral

# Nominal running fit of the journal inside the bearing bore, once there IS a bearing.
BEARING_RUNNING_CLEARANCE = 0.030e-3  # m, diametral

# Press fit for the bearing outer diameter in its seat. Diametral interference, negative
# clearance. H7/r6 on a 8 mm bore is about 0.019-0.034 mm; call it 0.025.
BEARING_SEAT_INTERFERENCE = 0.025e-3  # m, diametral

# A 15-tooth dia 4 spline has roughly 0.20 mm of working tooth height. Used only to state
# the contact pressure in the socket; the sizing case is the servo's own stall torque,
# which the spline is by definition rated for at FULL engagement.
SPLINE_TOOTH_HEIGHT = 0.20e-3  # m


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
        """Diametral fit of the bearing OD in the wall bore. Negative is interference,
        which is what a pressed-in bearing wants."""
        return self.wall_bore_dia - self.bearing_od


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
        wall_bore_dia=bearing_od - BEARING_SEAT_INTERFERENCE,
        sleeve_gap=0.300e-3,
    )
