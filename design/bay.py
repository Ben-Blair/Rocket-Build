"""The printed canard bay: what holds the four servos and the four bearing collars.

WHAT THIS PART IS FOR, in one sentence: it puts each servo's output spline on its hinge
axis and it carries the inboard 3.700 mm of each bearing, which is the half of the bearing
seat the airframe wall cannot reach.

Everything here is derived from `design/hinge.py`, `design/packaging.py` and
`design/configure.py`. No station is typed twice.

--------------------------------------------------------------------------------------
THE MODEL THAT MATTERS: A BEARING SEAT MADE OF TWO DIFFERENT MATERIALS
--------------------------------------------------------------------------------------
Every document in this project until now has priced the housing collar by putting the FULL
6.0 mm bearing length into `p_max = 6M/(d L^2) + N/(d L)` and reading off 3.2x -> 21.3x.
That formula assumes ONE material. The real seat is 2.300 mm of G10 wall and 3.700 mm of
printed polymer, and G10 is four to ten times stiffer than anything an FDM printer makes.

A rigid pin in an elastic housing distributes its couple by STIFFNESS, not by length. Make
the collar out of something soft and the collar simply gets out of the way: the load walks
back into the G10, the effective length falls toward 2.300 mm, and the collar stops being
worth what it was sold for. Length is necessary and it is not sufficient.

So `seat_pressure()` below is a Winkler foundation with a piecewise modulus:

    w(x) = a + b*(x - L/2)          rigid pin: translation + rotation, nothing else
    q(x) = k(x) * w(x),  k(x) proportional to E(x)
    integral q dx = N,  integral q*(x - L/2) dx = M     two equations, two unknowns

which collapses to exactly `6M/(d L^2) + N/(d L)` when E is constant -- there is a
regression test for that in `check_bay()`, because a model that cannot reproduce the
simple case it generalises is not worth trusting on the case it was written for.

The consequence is a design rule, and it is the reason this file selects a material rather
than leaving it to taste: THE BAY IS CHOSEN ON STIFFNESS, NOT STRENGTH. Every candidate
material is strong enough. They differ in how much of the collar's promised benefit they
actually deliver.

--------------------------------------------------------------------------------------
WHAT ELSE THIS FILE FOUND
--------------------------------------------------------------------------------------
`coupling_clearance()` exists because drawing the bay is what finally forced the question
of what physically occupies the space between the servo's output face and the bearing.
There is 0.515 mm of it. docs/01 correction 16 and docs/05 both instruct the builder to
buy a servo horn and skip the broaching -- and no bought horn is 0.515 mm tall. See the
function; it is a geometry check, not an opinion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .hinge import HingeStack
from .materials import (
    BAY_MATERIAL,
    G10_BEARING,
    G10_MODULUS,
    PRINT_MATERIALS,
    PrintMaterial,
)
from .packaging import ServoGeometry

# A2-70 stainless M2, the ordinary thing to buy.
SHAFT_YIELD_M2 = 450.0e6

MM = 1000.0

# --- how the part is printed ----------------------------------------------------------
NOZZLE = 0.400e-3
LAYER = 0.200e-3
MIN_WALL = 4.0 * NOZZLE          # 1.6 mm: four perimeters, no infill dependence
BOND_GAP = 0.150e-3              # radial epoxy film, bay OD to tube ID
SHELL_WALL = 2.400e-3            # six perimeters
# 4.0 mm, and it is the SCREW that sets it, not stiffness: 2-3x diameter is the thread
# engagement a self-tapper wants, and M1.4 x 3 = 4.2. Making the whole tray that thick is
# one number; the alternative was a 3 mm tray with a local boss at each of the eight screws,
# which is eight more features and one more thing to get out of step with the servo.
TRAY_THICKNESS = 4.000e-3
SCREW_BOSS_THICKNESS = TRAY_THICKNESS
SERVO_POCKET_CLEARANCE = 0.300e-3
SHELL_END_MARGIN = 6.000e-3      # shell past the servo lug envelope, each end

COLLAR_OD = 12.000e-3

# TWO DIAMETERS, AND THE CAD CARRIES THE SECOND ONE.
#
# The collar comes off the printer at dia 7.500, undersize on purpose, and is reamed to
# dia 8 H7 through the wall in one pass after the bay is bonded in. So the part has two
# sizes in its life, and it matters which one the model holds: the assembly represents the
# vehicle that FLIES, and the vehicle that flies has been reamed.
#
# Modelling the printed size instead put a dia 8.000 bearing inside a dia 7.500 hole -- a
# real 0.25 mm radial interference over 3.550 mm, four times over, 86 mm^3 of two solids
# occupying the same space. It would have been found by the first person to run a clash
# check and believed by anyone who did not.
#
# The printed size stays here because it has to be printed, but nothing geometric uses it.
COLLAR_PRINTED_BORE = 7.500e-3   # what comes off the printer

# How far the collar boss reaches PAST the shell bore, to guarantee the union bites. It
# must NOT reach the shell OD: the boss is flat-ended on a radial axis and the shell's
# outer surface is curved about the rocket axis, so a boss run out to R 37.250 puts its
# rim at hypot(37.250, 6) = 37.730 -- inside a tube bored to 37.400. See cad/canard_bay.fs.
COLLAR_BOSS_OVERLAP = 0.500e-3


# --- how the servo is held, and why not by its own lug screws -------------------------
# The obvious mounting is the servo's own four M1.4 screws through the flange into the
# tray. It was drawn that way first and the geometry argued it out.
#
# The lug holes sit (26.5 - 23.5)/2 = 1.5 mm beyond the ends of the case, and the tray
# window has to clear the case. That leaves 1.2 mm from screw centre to window edge and a
# 0.62 mm LIGAMENT of plastic between them -- one and a half extrusion widths, which a
# slicer may simply not fill. The load is not the problem: the servo's reaction torque
# pushes those screws along Y, into 5 mm of tray, not across the 0.62 mm. It is a
# PRINTABILITY problem, and the honest description of accepting it is "there may or may
# not be material there, and I will not know until I cut one open".
#
# So the flange is CLAMPED instead, by a printed bar across it screwed into the tray on
# both sides of the case, well clear of the window. Three things come free with that:
#
#   * the marginal feature stops existing rather than being argued about;
#   * the fastener becomes M2, which is buyable, and takes a heat-set insert, which M1.4
#     does not -- and printed threads in a part that is BONDED INTO THE AIRFRAME get one
#     chance to be right;
#   * a servo can be swapped after the bay is bonded in. The bay never comes out again.
#
# Cost: one more printed part per servo, about a gram, and eight M2 x 6 screws.
RETAINER_THICKNESS = 1.500e-3
# The bar is a dog bone. Across the flange it may only be as long in Z as the flange's
# exposed inboard face, which is the 3.0 mm the 29.5 mm flange overhangs the 23.5 mm case
# at each end; any longer and the bar buries itself in the servo body, which sits at a
# radius the bar has to pass through. At the screws it can be longer, because the screws
# are outboard of the 8 mm case in Y where nothing is in the way.
RETAINER_BRIDGE_HALF_Z = 1.300e-3
RETAINER_PAD_HALF_Z = 2.350e-3
RETAINER_SCREW_ACROSS = 6.000e-3     # +/- Y of the clamp screws, clear of the 8 mm case
INSERT_DIA = 3.200e-3                # M2 heat-set insert
INSERT_DEPTH = 4.000e-3
SCREW_DIA = 2.000e-3
SCREW_SHEAR_AREA = math.pi * SCREW_DIA ** 2 / 4.0

# Margins this module requires. Same 2.0x the hinge uses, for the same reason.
MARGIN_REQUIRED = 2.0
# Below this, the printed-material numbers in design/materials.py are not good enough to
# quote -- the FDM equivalent of DATASHEET_CONFIDENCE_MARGIN.
PRINT_CONFIDENCE_MARGIN = 3.0

EPOXY_SHEAR = 15.0e6             # Pa, structural epoxy on abraded G10 / abraded polymer.
                                 # Deliberately well under G10_INTERLAMINAR_SHEAR: the
                                 # weak side of this joint is the PRINTED surface, not the
                                 # tube, and a printed surface fails between layers.


# ======================================================================================
# the seat
# ======================================================================================

@dataclass
class SeatProfile:
    """Pressure distribution along one bearing seat, and where each material peaks."""

    length: float                 # m, total seat
    collar_length: float          # m, the printed part of it
    wall_length: float            # m, the G10 part of it
    collar_modulus: float
    peak_collar: float            # Pa
    peak_wall: float              # Pa
    uniform_peak: float           # Pa, what the single-material formula would say
    effective_length: float       # m, the single-material length giving the same wall peak
    stations: list[tuple[float, float]] = field(default_factory=list)  # (x, p) samples

    @property
    def collar_margin_against(self) -> float:
        return self.peak_collar

    @property
    def stiffness_penalty(self) -> float:
        """How much of the collar's promised benefit the material actually delivers.

        1.0 would mean a collar as stiff as the tube. This is the number the 21.3x claim
        assumed without saying so.
        """
        return self.uniform_peak / self.peak_wall if self.peak_wall > 0 else math.inf


def _modulus_moments(length: float, collar_length: float,
                     e_collar: float, e_wall: float) -> tuple[float, float, float]:
    """S0, S1, S2 -- the zeroth, first and second moments of E(x) about the seat centre.

    x runs from 0 at the INBOARD end (deep in the printed collar) to `length` at the
    outboard end (flush with the tube OD). The collar occupies [0, collar_length].
    """
    xc = length / 2.0

    def moments(a: float, b: float, e: float) -> tuple[float, float, float]:
        ua, ub = a - xc, b - xc
        return (e * (ub - ua),
                e * (ub ** 2 - ua ** 2) / 2.0,
                e * (ub ** 3 - ua ** 3) / 3.0)

    c = moments(0.0, collar_length, e_collar)
    w = moments(collar_length, length, e_wall)
    return c[0] + w[0], c[1] + w[1], c[2] + w[2]


def seat_pressure(stack: HingeStack, moment: float, normal: float,
                  collar_modulus: float, collar_length: float | None = None,
                  wall_modulus: float = G10_MODULUS, samples: int = 121) -> SeatProfile:
    """Peak contact pressure in each material of a two-material bearing seat.

    `moment` is taken about the seat CENTRE, which is how hinge.hinge_loads() reports
    `moment_at_bearing` and how tube_section.check_cut_station() consumes it. Getting that
    datum wrong is worth a factor of two and would not look wrong. Note that the datum is
    the centre of the WHOLE seat and stays there even when part of the seat carries
    nothing: equilibrium is taken about a fixed point, not about wherever the support
    happens to be.

    Pass `collar_modulus=0` for "no collar at all". Pass `collar_length` to ask what a
    SHORTER collar would do -- a different question, and a live one, since the collar's
    length is the only variable the printed part actually controls.

    A negative pressure here means the pin has lifted off that end rather than pulled on
    it; the magnitude is still the contact pressure on the opposite side of the bore, which
    is why the peaks below are taken on |p|. The single-material formula this generalises
    makes exactly the same simplification.
    """
    length = stack.bearing_length
    collar = stack.housing_collar_height if collar_length is None else collar_length
    wall = length - collar
    d = stack.bearing_od

    s0, s1, s2 = _modulus_moments(length, collar, collar_modulus, wall_modulus)
    det = s0 * s2 - s1 * s1
    if abs(det) < 1e-30:
        raise ValueError("degenerate seat: zero length or zero modulus")
    a = (normal * s2 - moment * s1) / det
    b = (moment * s0 - normal * s1) / det

    xc = length / 2.0

    def pressure(x: float) -> float:
        e = collar_modulus if x < collar else wall_modulus
        return e * (a + b * (x - xc)) / d

    stations = [(x, pressure(x))
                for x in (i * length / (samples - 1) for i in range(samples))]
    # Linear in x within each material, so the extremes are at the segment ends. Sample
    # anyway and take the max: it costs nothing and it survives someone adding a third
    # material later.
    peak_collar = max(abs(pressure(x)) for x in (0.0, collar * 0.999999))
    peak_wall = max(abs(pressure(x)) for x in (collar * 1.000001, length)) if wall > 0 else 0.0

    uniform = 6.0 * moment / (d * length ** 2) + normal / (d * length)
    # The single-material length that would produce the wall's actual peak: what the
    # collar is REALLY buying, expressed in the units the rest of the project argues in.
    eff = _effective_length(d, moment, normal, peak_wall)

    return SeatProfile(length=length, collar_length=collar, wall_length=wall,
                       collar_modulus=collar_modulus, peak_collar=peak_collar,
                       peak_wall=peak_wall, uniform_peak=uniform,
                       effective_length=eff, stations=stations)


def _effective_length(d: float, moment: float, normal: float, peak: float) -> float:
    """Invert p = 6M/(d L^2) + N/(d L) for L. Quadratic in 1/L; take the positive root."""
    if peak <= 0:
        return math.inf
    # p*d*L^2 - N*L - 6M = 0
    aa, bb, cc = peak * d, -normal, -6.0 * moment
    disc = bb * bb - 4 * aa * cc
    return (-bb + math.sqrt(disc)) / (2 * aa)


# ======================================================================================
# the geometry
# ======================================================================================

@dataclass
class BayGeometry:
    """Every dimension of the printed bay, derived -- none typed twice.

    Radii are from the rocket axis; axial stations are from the FORWARD FACE of the canard
    module tube, which is the datum the CAD uses (the tube runs Z 0 -> 142.900).
    """

    stack: HingeStack
    servo: ServoGeometry
    material: PrintMaterial
    hinge_station: float          # m, Z of the hinge axis from the module's forward face

    # ---- radial stack, outboard to inboard -------------------------------------------
    @property
    def shell_outer_radius(self) -> float:
        return self.stack.tube_inner_radius - BOND_GAP

    @property
    def shell_inner_radius(self) -> float:
        return self.shell_outer_radius - SHELL_WALL

    @property
    def collar_bore(self) -> float:
        """As REAMED -- the size the flying part has, and the size the CAD carries.

        Taken from the hinge stack rather than restated, so that it cannot drift from the
        bearing it has to hold."""
        return self.stack.wall_bore_dia

    @property
    def collar_wall(self) -> float:
        return (COLLAR_OD - self.collar_bore) / 2.0

    @property
    def ream_stock_on_radius(self) -> float:
        return (self.collar_bore - COLLAR_PRINTED_BORE) / 2.0

    @property
    def collar_reach(self) -> float:
        """How far the collar boss stands proud of the shell bore, plus its overlap."""
        return (self.shell_inner_radius + COLLAR_BOSS_OVERLAP
                - self.stack.bearing_inboard)

    @property
    def collar_rim_radius(self) -> float:
        """Distance from the ROCKET axis to the outer rim of the collar boss.

        The number the bounding box cannot tell you and the tube cares about."""
        return math.hypot(self.shell_inner_radius + COLLAR_BOSS_OVERLAP, COLLAR_OD / 2.0)

    @property
    def collar_bore_length(self) -> float:
        """Printed material actually supporting the bearing.

        Less than housing_collar_height by the epoxy film, which is counted with the
        plastic in the seat model because a 0.15 mm glue line is not a structural member
        and pretending it is one would be the second-best way to overstate this collar.
        """
        return self.shell_outer_radius - self.stack.bearing_inboard

    @property
    def tray_flange_face(self) -> float:
        """The face the servo flange lands on. Set by the servo, not chosen.

        Named for the face rather than for a direction: it is at the SMALLER radius of the
        two tray faces, so calling it "outer" -- as this file briefly did -- reads as
        outboard and means the opposite. The servo goes in from the axis and moves
        outward until its flange stops here."""
        return self.stack.servo_output_face - self.servo.flange_from_top

    @property
    def tray_back_face(self) -> float:
        """The tray's outboard face, TRAY_THICKNESS further from the axis."""
        return self.tray_flange_face + TRAY_THICKNESS

    @property
    def tray_standoff(self) -> float:
        """Radial gap the webs span, tray back face out to the shell bore."""
        return self.shell_inner_radius - self.tray_back_face

    @property
    def tray_width(self) -> float:
        """Set by the CLAMP SCREWS, not by the window: it has to reach past them with a
        wall left over."""
        return 2.0 * (RETAINER_SCREW_ACROSS + INSERT_DIA / 2.0 + MIN_WALL)

    @property
    def boss_face(self) -> float:
        """Inboard face of the clamp bosses -- flush with the servo flange's inboard face,
        so the retainer bar lands on both at once and actually clamps."""
        return self.tray_flange_face - self.servo.flange_thickness

    @property
    def insert_depth_available(self) -> float:
        return self.tray_back_face - self.boss_face

    @property
    def flange_relief_width(self) -> float:
        """The flange has to be relieved over the SAME width as the case window but over
        the FULL lug-envelope length, because the flange is 6 mm longer than the case and
        lands in exactly the band the clamp bosses occupy.

        This is the clash the CAD found: bosses and flange both wanting R 26.935 -> 27.935
        at Y within +/-4. An end-on view does not show it -- the tray hides it."""
        return self.window_width

    @property
    def flange_clear(self) -> bool:
        """Is the servo's flange envelope free of bay material?"""
        return (self.flange_relief_width >= self.servo.case_width
                and self.boss_face <= self.tray_flange_face - self.servo.flange_thickness
                + 1e-9)

    @property
    def window_length(self) -> float:
        return self.servo.case_length + 2.0 * SERVO_POCKET_CLEARANCE

    @property
    def window_width(self) -> float:
        return self.servo.case_width + 2.0 * SERVO_POCKET_CLEARANCE

    @property
    def window_forward(self) -> float:
        """Z of the forward edge of the servo window -- the CASE, not the lug envelope,
        which is what leaves solid tray under the two screw rows."""
        return self.hinge_station - self.servo.shaft_from_end - SERVO_POCKET_CLEARANCE

    @property
    def window_aft(self) -> float:
        return self.window_forward + self.window_length

    # ---- axial extent -----------------------------------------------------------------
    @property
    def servo_forward(self) -> float:
        """Z of the forward tip of the servo's lug envelope."""
        return self.hinge_station - self.servo.shaft_from_end - self._lug_overhang

    @property
    def _lug_overhang(self) -> float:
        return (self.servo.envelope_length - self.servo.case_length) / 2.0

    @property
    def servo_aft(self) -> float:
        return self.servo_forward + self.servo.envelope_length

    @property
    def forward_face(self) -> float:
        return self.servo_forward - SHELL_END_MARGIN

    @property
    def aft_face(self) -> float:
        return self.servo_aft + SHELL_END_MARGIN

    @property
    def length(self) -> float:
        return self.aft_face - self.forward_face

    @property
    def screw_stations(self) -> tuple[float, float]:
        """Z of the two rows of servo lug holes."""
        centre = self.hinge_station - self.servo.shaft_from_end + self.servo.case_length / 2.0
        half = self.servo.lug_hole_pitch_along / 2.0
        return centre - half, centre + half

    @property
    def screw_edge_distance(self) -> float:
        """Centre of a lug screw to the edge of the servo window.

        This one is set by the SERVO and cannot be designed away: the lug holes sit
        (26.5 - 23.5)/2 = 1.5 mm beyond the case ends, and the window has to clear the
        case. Edge distance is how printed parts crack, so it gets a number rather than a
        shrug."""
        return self.window_forward - self.screw_stations[0]

    # The lug hole the servo ships with. Kept as a NUMBER even though nothing screws into
    # it any more, because it is the measurement that ruled the obvious mounting out and
    # the next person to look at this will ask why the flange is clamped.
    LUG_PILOT_DIA = 1.150e-3

    @property
    def screw_ligament(self) -> float:
        """What would have been left between a lug screw and the window edge, had the
        servo been mounted by its own flange holes. See the header."""
        return self.screw_edge_distance - self.LUG_PILOT_DIA / 2.0

    # ---- what it weighs ----------------------------------------------------------------
    @property
    def shell_volume(self) -> float:
        """The cylinder, less the four collar bores that pass through it.

        Those bores have to come off HERE and not out of the collar's own volume: the
        bore is 3.550 mm long and the collar boss only stands 1.150 mm proud, so charging
        the whole bore to the boss makes four collars weigh MINUS 0.1 g. A negative part
        mass is the kind of thing a total hides."""
        ro, ri = self.shell_outer_radius, self.shell_inner_radius
        shell = math.pi * (ro ** 2 - ri ** 2) * self.length
        bores = 4.0 * math.pi * (self.collar_bore / 2.0) ** 2 * SHELL_WALL
        return shell - bores

    @property
    def tray_volume(self) -> float:
        """Four trays plus their webs, as a plate the size of the lug envelope with the
        servo window removed, plus two webs per servo spanning the standoff."""
        plate = self.servo.envelope_length * self.tray_width * TRAY_THICKNESS
        window = self.window_length * self.window_width * TRAY_THICKNESS
        webs = 2.0 * self.servo.envelope_length * self.tray_standoff * MIN_WALL
        # Clamp bosses, less the flange relief through them.
        boss_depth = self.tray_flange_face - self.boss_face
        boss = 2.0 * (2.0 * INSERT_DIA) * self.tray_width * boss_depth
        relief = (self.servo.envelope_length * self.flange_relief_width * boss_depth)
        return 4.0 * (plate - window + webs + boss - relief)

    @property
    def collar_volume(self) -> float:
        """Only the part of each collar that stands PROUD of the shell bore. The rest of
        the collar's bore length is shell, and is accounted for there."""
        annulus = math.pi * ((COLLAR_OD / 2.0) ** 2
                             - (self.collar_bore / 2.0) ** 2)
        return 4.0 * annulus * self.collar_reach

    @property
    def flange_overhang(self) -> float:
        """How far the flange projects past the case at each end -- the only place a clamp
        can touch its inboard face."""
        return (self.servo.envelope_length - self.servo.case_length) / 2.0

    @property
    def retainer_volume(self) -> float:
        """Eight dog-bone bars: a bridge across the flange plus two screw pads."""
        bridge = (self.window_width * 2.0 * RETAINER_BRIDGE_HALF_Z * RETAINER_THICKNESS)
        pads = 2.0 * ((self.tray_width / 2.0 - self.window_width / 2.0)
                      * 2.0 * RETAINER_PAD_HALF_Z * RETAINER_THICKNESS)
        return 8.0 * (bridge + pads)

    @property
    def volume(self) -> float:
        return (self.shell_volume + self.tray_volume + self.collar_volume
                + self.retainer_volume)

    @property
    def mass(self) -> float:
        """Printed at 100% infill. A 2.4 mm wall is all perimeter anyway, so infill is not
        a lever here -- if this needs to be lighter, the lever is the shell length."""
        return self.volume * self.density

    @property
    def density(self) -> float:
        return {"PETG": 1270.0, "ASA": 1070.0, "PETG-CF": 1300.0, "PA6-CF": 1180.0}[
            self.material.name]

    # ---- the bond ----------------------------------------------------------------------
    @property
    def bond_area(self) -> float:
        holes = 4.0 * math.pi * (COLLAR_OD / 2.0) ** 2
        return 2.0 * math.pi * self.shell_outer_radius * self.length - holes


def build_bay(stack: HingeStack, servo: ServoGeometry, hinge_station: float,
              material: str = BAY_MATERIAL) -> BayGeometry:
    return BayGeometry(stack=stack, servo=servo, material=PRINT_MATERIALS[material],
                       hinge_station=hinge_station)


# ======================================================================================
# the check the bay was supposed to run
# ======================================================================================

@dataclass
class CouplingSpace:
    """What physically fits between the servo's output face and the bearing.

    docs/01 correction 16 and docs/05 both say: do not broach the spline socket, buy a
    servo horn. This is the check nobody had run on that instruction.
    """

    gap: float                   # m, servo output face to bearing inboard end
    through_bore: float          # m, the bearing ID -- anything outboard must fit this
    horn_hub_height: float       # m, thinnest bought 15T horn hub
    horn_hub_dia: float          # m
    fits: bool
    reason: str


# Thinnest bought 4 mm 15T horn/adapter this project could find. Aluminium horns are 4-6 mm
# at the hub and the moulded ones are thicker; the splined insert alone is about 4 mm and
# dia 7.4, because 15 teeth on a 4 mm pitch circle need that much metal around them.
# Measure a real one before treating these as gospel -- but they cannot be under 1 mm.
HORN_HUB_HEIGHT = 4.000e-3
HORN_HUB_DIA = 7.400e-3


def coupling_clearance(stack: HingeStack) -> CouplingSpace:
    gap = stack.bearing_inboard - stack.servo_output_face
    bore = stack.journal_dia
    fits = gap >= HORN_HUB_HEIGHT or HORN_HUB_DIA <= bore
    if fits:
        reason = "a bought horn fits"
    else:
        reason = (
            f"a bought horn needs {HORN_HUB_HEIGHT * MM:.1f} mm of height at "
            f"dia {HORN_HUB_DIA * MM:.1f}, and there is {gap * MM:.3f} mm between the servo "
            f"output face and the bearing. Outboard of that the hole is the bearing bore, "
            f"dia {bore * MM:.1f}, which a dia {HORN_HUB_DIA * MM:.1f} hub cannot enter. So the "
            f"coupling has to live INSIDE the dia {bore * MM:.1f} journal -- which is the "
            f"broached socket design/hinge.py already models and checks"
        )
    return CouplingSpace(gap=gap, through_bore=bore, horn_hub_height=HORN_HUB_HEIGHT,
                         horn_hub_dia=HORN_HUB_DIA, fits=fits, reason=reason)


def clearances(bay: "BayGeometry") -> list[tuple[str, float, str]]:
    """Every place bay material comes near servo, shaft or bearing.

    A rendered view of the assembled module shows none of this -- the tube hides the bay
    and the bay hides the servo. The numbers are the check; the picture is a courtesy.
    Each entry is (what, clearance in metres, which direction).
    """
    s, sv = bay.stack, bay.servo
    return [
        ("servo case side vs tray window",
         (bay.window_width - sv.case_width) / 2.0, "circumferential, each side"),
        ("servo case end vs tray window",
         (bay.window_length - sv.case_length) / 2.0, "axial, each end"),
        ("servo flange vs flange relief",
         (bay.flange_relief_width - sv.case_width) / 2.0, "circumferential, each side"),
        ("servo top face vs collar inboard end",
         s.bearing_inboard - s.servo_output_face, "radial"),
        ("servo top face vs shell bore",
         bay.shell_inner_radius - s.servo_output_face, "radial"),
        ("servo top face vs tray back face",
         bay.tray_back_face - s.servo_output_face, "radial -- NEGATIVE is correct here, "
         "the servo stands proud of the tray into the standoff gap"),
        ("servo spline tip vs shell OD",
         bay.shell_outer_radius - s.spline_tip, "radial, inside the collar bore"),
        ("shaft sleeve vs collar bore, as printed",
         (COLLAR_PRINTED_BORE - s.journal_dia) / 2.0, "radial, before reaming"),
        ("bearing OD vs collar bore, as reamed",
         (bay.collar_bore - s.bearing_od) / 2.0,
         "radial -- zero is correct, this is the press fit, and it is the size the CAD "
         "carries"),
        ("retainer bar vs servo flange",
         bay.boss_face - (s.servo_output_face - sv.flange_from_top - sv.flange_thickness),
         "radial -- zero is correct, the bar clamps the flange"),
        ("retainer bridge vs servo case, in Z",
         (bay.flange_overhang - 2.0 * RETAINER_BRIDGE_HALF_Z) / 2.0,
         "axial, each end -- the bar may only be this long where it crosses the flange, "
         "because the case body occupies the radius the bar sits at"),
    ]


@dataclass
class BayCheck:
    ok: bool
    violations: list[str]
    notes: list[str]
    seat: SeatProfile
    seat_no_collar: SeatProfile
    coupling: CouplingSpace
    margins: dict[str, float]


def check_bay(bay: BayGeometry, moment: float, normal: float,
              servo_stall: float) -> BayCheck:
    """Everything the bay has to survive, plus the two checks drawing it forced."""
    v: list[str] = []
    notes: list[str] = []
    s = bay.stack

    # --- 1. the seat, honestly ---------------------------------------------------------
    seat = seat_pressure(s, moment, normal, bay.material.modulus)

    # Regression: with one material this must reproduce 6M/(dL^2) + N/(dL) exactly. A
    # generalisation that cannot recover the case it generalises is not trustworthy.
    same = seat_pressure(s, moment, normal, G10_MODULUS)
    if abs(same.peak_wall - same.uniform_peak) > 1.0:  # Pa
        v.append(f"INTERNAL: the two-material seat model does not reduce to the "
                 f"single-material formula ({same.peak_wall / 1e6:.4f} vs "
                 f"{same.uniform_peak / 1e6:.4f} MPa)")

    # And with no collar at all: the vehicle as it stands today, the bearing hanging
    # 3.700 mm into thin air with only the wall gripping it.
    #
    # THE WAY TO SAY "NO COLLAR" IS ZERO STIFFNESS, NOT ZERO LENGTH. Zeroing the length
    # instead leaves a full-length seat that is G10 all the way through and reports the
    # BEST case as if it were the worst -- 21.4x where the answer is 3.4x. The seat's
    # extent is fixed by the bearing; what a missing collar removes is support, and
    # support is stiffness.
    #
    # Note this comes out at 3.4x rather than the 3.2x quoted elsewhere in the project,
    # and the difference is real rather than rounding: the simple formula takes the couple
    # about the centre of the SUPPORTED length, while equilibrium takes it about a fixed
    # point regardless of where the support happens to be. The 2.300 mm of wall sits
    # outboard of the bearing's centre, so it has a slightly longer arm than the simple
    # formula credits it with. Both are the same answer to within the confidence of a
    # G10 sheet allowable applied to a filament-wound tube.
    no_collar = seat_pressure(s, moment, normal, 0.0)

    m_collar = bay.material.compressive / seat.peak_collar if seat.peak_collar > 0 else math.inf
    m_wall = G10_BEARING / seat.peak_wall if seat.peak_wall > 0 else math.inf

    # --- 2. the bond -------------------------------------------------------------------
    # Each collar hands its couple to the shell and the shell hands it to the tube. Taking
    # that over the WHOLE bond area is the flattering way to ask the question and returns
    # a four-figure margin, which is a sign the model is not answering anything. The load
    # is local, so check it locally: the patch of glue line within one collar diameter of
    # each bore, which is about as far as shear lag will carry it in a joint this stiff.
    patch = 4.0 * (3.0 * COLLAR_OD) ** 2
    bond_load = moment / bay.shell_outer_radius
    bond_stress = 4.0 * bond_load / patch
    m_bond = EPOXY_SHEAR / bond_stress if bond_stress > 0 else math.inf

    # --- 3. the clamp ------------------------------------------------------------------
    # The servo reacts its own stall torque into the retainer bars. Two bars, separated by
    # the lug pitch, so each takes the couple as a force pair.
    screw_force = servo_stall / bay.servo.lug_hole_pitch_along / 2.0
    # Pull-out of a heat-set insert: shear on the knurled cylinder it was melted into.
    thread_area = math.pi * INSERT_DIA * INSERT_DEPTH
    thread_stress = screw_force / thread_area
    m_thread = (bay.material.compressive / 2.0) / thread_stress if thread_stress > 0 else math.inf

    # --- 3b. the insert has to fit in the tray ------------------------------------------
    if bay.insert_depth_available < INSERT_DEPTH:
        v.append(f"an M2 insert needs {INSERT_DEPTH * MM:.1f} mm and the tray only offers "
                 f"{bay.insert_depth_available * MM:.2f} mm at the clamp boss")
    else:
        notes.append(f"M2 heat-set inserts, dia {INSERT_DIA * MM:.1f} x {INSERT_DEPTH * MM:.1f}, "
                     f"into {bay.insert_depth_available * MM:.2f} mm of tray at Y +/-"
                     f"{RETAINER_SCREW_ACROSS * MM:.1f} -- clear of the "
                     f"{bay.servo.case_width * MM:.0f} mm case, which is the whole point of "
                     f"clamping rather than using the servo's own lug holes "
                     f"({bay.screw_ligament * MM:.2f} mm of ligament, see the header)")

    # --- 4. can it be printed ----------------------------------------------------------
    if SHELL_WALL < MIN_WALL:
        v.append(f"shell wall {SHELL_WALL * MM:.2f} mm is under the {MIN_WALL * MM:.2f} mm "
                 f"four-perimeter minimum")
    if bay.collar_reach < 0:
        v.append(f"the collar does not reach the bearing: shell bore is at R "
                 f"{bay.shell_inner_radius * MM:.3f} and the bearing starts at R "
                 f"{s.bearing_inboard * MM:.3f}")
    if bay.tray_standoff < 0:
        v.append(f"the servo tray at R {bay.tray_back_face * MM:.3f} is outboard of the "
                 f"shell bore at R {bay.shell_inner_radius * MM:.3f} -- the servo will not "
                 f"go in")
    if bay.ream_stock_on_radius <= 0:
        v.append(f"the collar is printed at dia {COLLAR_PRINTED_BORE * MM:.2f}, which the "
                 f"dia {bay.collar_bore * MM:.2f} reamer would not clean up")
    else:
        notes.append(
            f"collar printed dia {COLLAR_PRINTED_BORE * MM:.2f} and reamed to dia "
            f"{bay.collar_bore * MM:.3f} H7 through the wall in one pass -- "
            f"{bay.ream_stock_on_radius * MM:.3f} mm of stock on the radius, which is what "
            f"an FDM hole needs to come out round. THE CAD CARRIES THE REAMED SIZE, because "
            f"the assembly is the vehicle that flies")
    if bay.collar_wall < MIN_WALL:
        v.append(f"the collar leaves {bay.collar_wall * MM:.2f} mm of wall around a "
                 f"dia {bay.collar_bore * MM:.2f} bore, under the {MIN_WALL * MM:.2f} mm "
                 f"four-perimeter minimum")

    # --- 3c. the clamp bar must not bury itself in the servo ------------------------------
    if RETAINER_BRIDGE_HALF_Z * 2.0 > bay.flange_overhang:
        v.append(f"the retainer bridge is {RETAINER_BRIDGE_HALF_Z * 2.0 * MM:.2f} mm long in "
                 f"Z where it crosses the flange, against {bay.flange_overhang * MM:.2f} mm "
                 f"of exposed flange -- the rest of it lands inside the servo case, which "
                 f"occupies the very radius the bar sits at")
    else:
        notes.append(f"retainer bridge {RETAINER_BRIDGE_HALF_Z * 2.0 * MM:.2f} mm across a "
                     f"{bay.flange_overhang * MM:.2f} mm exposed flange band, widening to "
                     f"{RETAINER_PAD_HALF_Z * 2.0 * MM:.2f} mm at the screws where the case "
                     f"is not in the way")
    if SCREW_DIA * 1.9 > RETAINER_PAD_HALF_Z * 2.0:
        v.append(f"an M{SCREW_DIA * MM:.0f} head is about "
                 f"{SCREW_DIA * 1.9 * MM:.1f} mm across and the screw pad is only "
                 f"{RETAINER_PAD_HALF_Z * 2.0 * MM:.2f} mm long in Z")

    # --- 4a. does the collar boss stay inside the tube ------------------------------------
    # The check a bounding box cannot do. A flat-ended boss on a radial axis has its rim
    # further from the ROCKET axis than its centre, and the tube bore is a radius.
    if bay.collar_rim_radius > s.tube_inner_radius:
        v.append(f"the collar boss rim reaches R {bay.collar_rim_radius * MM:.3f}, "
                 f"{(bay.collar_rim_radius - s.tube_inner_radius) * MM:.3f} mm inside a tube "
                 f"bored to R {s.tube_inner_radius * MM:.3f}. A flat-ended boss on a radial "
                 f"axis puts its rim at hypot(reach, OD/2), not at `reach` -- and an "
                 f"axis-aligned bounding box will report the reach and look fine")
    else:
        notes.append(f"collar boss rim at R {bay.collar_rim_radius * MM:.3f}, "
                     f"{(s.tube_inner_radius - bay.collar_rim_radius) * MM:.3f} mm clear of "
                     f"the tube bore -- checked on RADIUS, not on the bounding box")

    # --- 4b. does the SERVO FLANGE clear the bay -----------------------------------------
    if not bay.flange_clear:
        v.append(f"the clamp bosses and the servo's own flange both want R "
                 f"{bay.boss_face * MM:.3f} -> {bay.tray_flange_face * MM:.3f}; the flange "
                 f"relief is {bay.flange_relief_width * MM:.2f} mm wide against a "
                 f"{bay.servo.case_width * MM:.1f} mm flange")
    else:
        notes.append(f"flange relieved {bay.flange_relief_width * MM:.2f} mm wide over the "
                     f"full {bay.servo.envelope_length * MM:.1f} mm lug envelope, so the "
                     f"clamp bosses sit beside the flange rather than under it")

    # --- 5. does the servo actually clear the collar ------------------------------------
    servo_to_collar = s.bearing_inboard - s.servo_output_face
    if servo_to_collar < 0:
        v.append(f"the collar reaches R {s.bearing_inboard * MM:.3f}, inboard of the servo "
                 f"output face at R {s.servo_output_face * MM:.3f}")
    else:
        notes.append(f"{servo_to_collar * MM:.3f} mm between the servo output face and the "
                     f"collar's inboard end")

    # The coupling conflict is reported by this module because drawing the bay is what
    # exposed it, but it is NOT a defect of the bay: no bay geometry fixes it, and the
    # bay is buildable either way. Keeping it out of `violations` is what lets the bay's
    # own verdict mean something. It has its own verdict on `BayCheck.coupling`.
    coupling = coupling_clearance(s)
    if not coupling.fits:
        notes.append(f"NOT A BAY DEFECT, but found here: no bought servo horn fits. "
                     f"{coupling.reason}")

    margins = {
        "bearing seat, printed collar": m_collar,
        "bearing seat, G10 wall": m_wall,
        "heat-set insert pull-out": m_thread,
        "bay-to-tube bond shear": m_bond,
        "servo clamp screw shear": (SHAFT_YIELD_M2 / 2.0) / (screw_force / SCREW_SHEAR_AREA),
    }
    for name, m in margins.items():
        if m < MARGIN_REQUIRED:
            v.append(f"{name} margin is {m:.2f}x, short of {MARGIN_REQUIRED:.1f}x")
        elif m < PRINT_CONFIDENCE_MARGIN:
            notes.append(f"{name} is {m:.2f}x, under the {PRINT_CONFIDENCE_MARGIN:.1f}x at "
                         f"which printed-material numbers stop being good enough to quote "
                         f"-- print coupons and test, or move up a material")

    notes.append(
        f"the collar buys an EFFECTIVE seat length of {seat.effective_length * MM:.3f} mm "
        f"out of the {s.bearing_length * MM:.1f} mm it is long, because "
        f"{bay.material.name} is {G10_MODULUS / bay.material.modulus:.1f}x softer than the "
        f"G10 it shares the seat with")

    if bay.material.heat_deflection_c < 70.0:
        v.append(f"{bay.material.name} deflects at {bay.material.heat_deflection_c:.0f} C, "
                 f"which a dark airframe reaches on a pad")

    return BayCheck(ok=not v, violations=v, notes=notes, seat=seat,
                    seat_no_collar=no_collar, coupling=coupling, margins=margins)
