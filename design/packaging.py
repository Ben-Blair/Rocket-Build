"""Actuator bay packaging: what internal diameter do the canard servos actually need?

CONFIRMED ARRANGEMENT (Aug 2026): the servo lies FLAT against the inner wall with its
output shaft radial, passing through the wall into the canard root. The output shaft on
these parts sits on a large face, not an end face -- verified against the hardware. So the
servo's THICKNESS consumes tube radius (8 mm for the KST X08 Plus), its LENGTH runs
fore-and-aft along the rocket axis, and only its HEIGHT has to fit around the
circumference. Use check_flat_mount(); it is the one that describes the real vehicle.

check_direct_drive() models the alternative -- body pointing inward, output shaft on an end
face, so LENGTH consumes radius. It is kept because it is the conservative bound and
because an earlier version of this project believed it, but no hobby servo is built that
way. It is not the arrangement being built.

That correction matters beyond packaging: the old assumption is what made actuator
packaging look like the constraint that sets airframe diameter. It is not. See
docs/00-requirements.md section 4.

Servo dimensions and torques below are representative of widely used parts but are
APPROXIMATE unless the entry names a manufacturer -- replace with datasheet values for the
exact part you buy before freezing the design.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Servo:
    name: str
    length: float  # m, along the output-shaft-perpendicular long axis
    width: float  # m, thickness (the dimension that eats tube radius when mounted flat)
    height: float  # m, including output shaft boss
    mass: float  # kg
    stall_torque: float  # N*m at nominal voltage
    speed_60deg: float  # s per 60 deg, no load
    note: str = "APPROX - verify against datasheet"


# Two kinds of entry live here.
#
# The lowercase generic keys are size/torque *classes*, not products. They are deliberately
# vague: quoting a part number against them would imply a precision they do not have. Use
# them for exploring the design space.
#
# The keys prefixed with a manufacturer are REAL PARTS with datasheet values, for freezing
# the design against hardware you can actually buy. Both were selected against the 75 mm
# airframe: they must clear 0.30 N*m stall (2.0x margin on the 0.0604 N*m hinge moment
# after a 0.4 derate) while staying under ~24.6 mm long. See docs/00-requirements.md #4.
SERVOS: dict[str, Servo] = {
    "submicro": Servo("sub-micro class (~5 g)", 0.0200, 0.0086, 0.0200, 0.0050, 0.05, 0.11),
    "micro": Servo("micro class (~12 g)", 0.0236, 0.0116, 0.0240, 0.0120, 0.20, 0.14),
    "mini": Servo("mini class (~14 g)", 0.0228, 0.0125, 0.0226, 0.0140, 0.25, 0.10),
    "mini_ht": Servo("mini high-torque HV class (~20 g)", 0.0230, 0.0100, 0.0260, 0.0200, 0.55, 0.07),
    "standard": Servo("standard class (~55 g)", 0.0406, 0.0198, 0.0376, 0.0555, 1.00, 0.18),
    "standard_ht": Servo("standard high-torque HV class (~60 g)", 0.0403, 0.0202, 0.0366, 0.0600, 1.50, 0.08),

    # --- real parts, datasheet values -----------------------------------------------
    # Torque figures are the manufacturers' WORKING torque at the stated voltage, not
    # stall. torque_margin() applies a 0.4 stall derate on top, so the margins these
    # produce are conservative, probably doubly so. Verify against a real part.
    #
    # LENGTH IS THE BODY, NOT THE ENVELOPE. KST quote a 29.5 mm maximum dimension
    # including the mounting lugs against a 23.5 mm case. If the lugs end up in the
    # radial path they eat 6 mm the 75 mm airframe does not have. Check the dimensioned
    # drawing and the shaft position before ordering four of anything.
    "kst_x08_plus": Servo(
        "KST X08 Plus V6.0 (9 g, 8 mm, 5.3 kgf.cm @ 8.4 V)",
        0.0235, 0.0080, 0.0168, 0.0090, 0.520, 0.09,
        note="datasheet; body 23.5x8x16.8 +/-0.2, envelope 29.5x8x25 incl lugs -- verify lug clearance",
    ),
    "mks_hv6100": Servo(
        "MKS HV6100 (10 g, 10 mm, 3.4 kg.cm @ 8.2 V)",
        0.0225, 0.0100, 0.0235, 0.0100, 0.333, 0.10,
        note="datasheet; HV only -- at 6.0 V torque falls to 2.6 kg.cm, which fails the 2.0x margin",
    ),
}


# ---------------------------------------------------------------------------------
# CAD-grade mechanical geometry.
#
# `Servo` above carries the three case dimensions and nothing about where the output
# shaft is or which way it points. That is enough for a mass budget and it is NOT enough
# to build a model you can articulate, which is how the two errors recorded below
# survived: a bounding box has no shaft, so nothing about it can be checked.
#
# Everything here is read off the manufacturer's dimensioned drawing.
@dataclass(frozen=True)
class ServoGeometry:
    """Datasheet mechanical detail for a real servo. All lengths in metres.

    THE SHAFT RUNS ALONG THE CASE *HEIGHT*. On the X08 Plus the drawing's plan view is
    23.5 x 8 with the spline face-on, and its side view is 23.5 x 16.8 with the spline
    standing proud of the top edge. So the output axis is the 16.8 mm dimension, and the
    face the shaft emerges from is the 23.5 x 8 one. Any mount that needs a RADIAL output
    shaft therefore spends `case_height` of tube radius, not `case_width`.

    Axis naming, so it cannot drift: +shaft is the direction the spline points; `along` is
    the case's 23.5 mm axis; `across` is its 8 mm axis. Distances measured `_from_top` are
    measured from the case face the shaft emerges from, positive going INTO the case.
    """

    # Case, as the datasheet's three-number "case dimensions" line quotes it.
    case_length: float          # 23.5 mm axis -- "along"
    case_width: float           # 8 mm axis -- "across"
    case_height: float          # 16.8 mm axis -- THE SHAFT AXIS

    # Mounting lugs.
    envelope_length: float      # tip-to-tip across the lugs
    lug_hole_pitch_along: float
    lug_hole_pitch_across: float
    # Two hole SIZES on the mounting flange, both confirmed against the drawing
    # (KST_0012, callouts "dia 1.50-4" and "dia 2-2") but NEITHER labelled with a
    # function -- the datasheet dimensions the flange, it does not name what either
    # hole is for. What is known, not guessed:
    #   - 4 small holes, one at each corner of the 26.5 x 5.0 rectangle. KST's own
    #     listing says the servo ships with 4 mounting screws, and 4 holes at the
    #     corners of a rectangular flange is the standard screw pattern on this class
    #     of servo. Read as MOUNTING SCREWS, M1.4-ish, until a real screw is held to
    #     one and measured.
    #   - 2 larger holes, one on the flange centreline at EACH lug position (so they
    #     sit BETWEEN the two rows of small holes, not beside them -- see
    #     scripts/make_servo_cad.py, which sketches them at y=0 while the small ones
    #     are at y=+/-2.5). Two holes, centred, larger than a screw needs, is more
    #     consistent with LOCATING DOWELS for repeatable placement in a servo tray
    #     than with a second fastener -- but this is inference from the geometry,
    #     not a labelled callout, and nothing in this project currently uses them
    #     for anything. Confirm before designing a tray that assumes it.
    lug_hole_dia: float
    lug_hole_count: int
    lug_hole_2_dia: float
    lug_hole_2_count: int
    flange_from_top: float      # top face down to the lug plane
    flange_thickness: float

    # Output.
    shaft_from_end: float       # along the 23.5 mm axis, from the NEAR case end
    shaft_proud_of_top: float   # spline height above the top face
    spline_dia: float
    spline_teeth: int
    horn_screw: str

    # Everything below the top face, including the cable boss. This is the real radial
    # keep-out when the shaft points outward, not `case_height`.
    depth_from_top: float

    travel_half_angle: float    # rad, one side of centre

    source: str = "manufacturer dimensioned drawing"

    @property
    def shaft_from_far_end(self) -> float:
        return self.case_length - self.shaft_from_end

    @property
    def shaft_offset_from_centre(self) -> float:
        """How far the output axis sits from the case's own mid-length.

        Zero would mean a bounding box centred on the hinge is the right placeholder.
        It is not zero on any servo the author has checked.
        """
        return self.case_length / 2.0 - self.shaft_from_end

    @property
    def shaft_proud_of_flange(self) -> float:
        """Spline reach above the MOUNTING plane -- the number that decides whether the
        shaft crosses the wall and lands in the canard root."""
        return self.flange_from_top + self.shaft_proud_of_top

    @property
    def depth_below_flange(self) -> float:
        """Radial depth consumed inboard of the mounting plane."""
        return self.depth_from_top - self.flange_from_top


SERVO_GEOMETRY: dict[str, ServoGeometry] = {
    # KST X08 Plus V6.0, datasheet KST_0012 rev 2025-04:
    # https://www.kst-servo-shop.de/media/c2/0f/7d/1749810622/KST_0012_X08_Plus_V6_Datenblatt_04_2025_de.pdf
    # (the filename alone was cited here for a long time with no URL saved anywhere in
    # the project -- fine until someone needs to re-check a number and has to search for
    # the PDF again. Save the source, not just its name.)
    #
    # TWO THINGS ON THIS DRAWING CONTRADICTED WHAT THIS PROJECT HAD ASSUMED. Both had
    # been flagged as unverified in docs/05 and both turned out to be wrong:
    #
    #  - The output shaft is 6.14 mm from one case end, not centred at 11.75 mm. The
    #    drawing dimensions it three times over from three datums (6.14 from the case
    #    end, 7.64 from the lug-hole line, 9.14 from the envelope end), and those datums
    #    are 1.5 mm apart exactly as the 23.50 / 26.50 / 29.50 stack requires, so the
    #    reading is self-checking.
    #  - The shaft runs along the 16.8 mm axis, so a radial output shaft costs 16.8 mm of
    #    radius and stacks only 8 mm around the circumference -- the reverse of what
    #    check_flat_mount() assumed.
    "kst_x08_plus": ServoGeometry(
        case_length=0.0235, case_width=0.0080, case_height=0.0168,
        envelope_length=0.0295,
        lug_hole_pitch_along=0.0265, lug_hole_pitch_across=0.0050,
        lug_hole_dia=0.0015, lug_hole_count=4,
        lug_hole_2_dia=0.0020, lug_hole_2_count=2,
        flange_from_top=0.00525, flange_thickness=0.0010,
        shaft_from_end=0.00614, shaft_proud_of_top=0.0032,
        spline_dia=0.0040, spline_teeth=15, horn_screw="M2",
        depth_from_top=0.0271,
        travel_half_angle=math.radians(60.0),
    ),
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


def check_flat_mount(
    inner_diameter: float,
    servo: Servo,
    n_canards: int = 4,
    frame_thickness: float = 0.004,
    clearance: float = 0.003,
    geometry: "ServoGeometry | None" = None,
    include_cable_boss: bool = True,
    seat_radius: float | None = None,
) -> BayLayout:
    """Servo lying flat against the inner wall, output shaft radial through it.

    This is the OTHER way to arrange a direct drive, and for a servo whose output shaft
    protrudes from a large face (which is every hobby servo) it is the arrangement that
    actually matches the hardware. The servo's THICKNESS eats tube radius, which is the
    weak constraint this arrangement exists to exploit.

    ORIENTATION, because it has been wrong here twice. Pass `geometry` and the function
    reads the orientation off the datasheet instead of guessing it.

    The output shaft runs along the case HEIGHT (16.8 mm on the KST X08 Plus; see
    ServoGeometry). A radial output shaft therefore points along that axis, so it is the
    HEIGHT that eats tube radius and the WIDTH (8 mm) that stacks around the
    circumference. The `Servo`-only path below assumed the opposite -- width radial,
    height circumferential -- which describes a servo whose shaft comes out of its narrow
    edge. No hobby servo is built that way, and it is the same class of error as the
    "servo body points inward" premise this module was written to kill.

    An earlier fix swapped `length` for `height` in the circumferential stack. That was a
    correct fix to a different bug and it is still in force; it just did not question
    which axis the shaft was on, because a `Servo` has no shaft to question.

    The conclusion does not move -- both orientations fit, and by a wide margin either
    way. What moves is the CENTRAL VOID, which is the number the avionics stack and the
    wiring have to live in, and it is the tighter of the two readings that is real.

    The axial dimension is deliberately not checked here. Four servos laid fore-and-aft
    are bounded by the canard module length (142.9 mm against a 23.5 mm body), not by
    anything this function can see.

    check_direct_drive() models the opposite: body pointing inward, length eating radius.
    That only works if the output shaft is on the servo's END face. Keep both, because
    which one applies is a property of the part and the mount, not of the airframe -- and
    the answer moves the required tube diameter by tens of millimetres.

    Commercial servo frames for the KST X08 family (e.g. Hyperflight SRB-KST-X08) carry an
    outboard ball bearing on the output shaft, which is exactly the load path this
    arrangement needs: the bearing takes the canard bending moment, not the servo spline.
    """
    if geometry is not None:
        # Radial depth is everything inboard of the mounting plane. The cable boss is
        # part of that keep-out even though it is not part of the case, so it is included
        # by default; set include_cable_boss=False to see the case alone.
        depth = geometry.depth_below_flange if include_cable_boss else (
            geometry.case_height - geometry.flange_from_top
        )
        stacked = geometry.case_width
    else:
        depth = servo.width
        stacked = servo.height

    radial_band = depth + frame_thickness + clearance
    r_mid = inner_diameter / 2.0 - radial_band / 2.0
    arc_available = 2.0 * math.pi * max(r_mid, 1e-6)
    arc_needed = n_canards * (stacked + clearance)

    # Two ways to answer "how much room is left down the middle", and they are different
    # questions, which is why they used to give different answers in the same report.
    #
    #   Without `seat_radius`: a BUDGET. Assume the servo is pushed as far outboard as it
    #   can go and add allowances for a frame and clearance it does not yet have. Right
    #   for sizing a tube before anything is drawn.
    #
    #   With `seat_radius`: a MEASUREMENT. The servo output face is actually at this
    #   radius in the CAD, so the boss reaches seat_radius - depth_from_top and the void
    #   is twice that. Right once there is a model to read. The two stopped agreeing when
    #   the servo moved 4 mm inboard to make room for the hinge bearing -- see
    #   design/hinge.py -- and the measurement is the one to believe.
    if seat_radius is not None and geometry is not None:
        central_void = 2.0 * (seat_radius - geometry.depth_from_top)
    else:
        central_void = inner_diameter - 2.0 * radial_band

    fits = arc_needed <= arc_available and central_void > 0.0
    if central_void <= 0.0:
        reason = "servos meet at the axis"
    elif not fits:
        reason = f"{n_canards} servos will not fit around the circumference"
    else:
        reason = f"ok, {central_void * 1000:.0f} mm central void"
    return BayLayout(fits, arc_needed, arc_available, arc_available - arc_needed,
                     "flat/tangential", reason)


def hinge_moment(
    dynamic_pressure: float,
    panel_area: float,
    mean_chord: float,
    cn_alpha_panel: float,
    deflection_rad: float,
    hinge_frac: float = 0.20,
    cp_frac: float = 0.25,
) -> float:
    """Aerodynamic moment about the canard hinge line, N*m per panel. SIGNED.

    `hinge_frac` and `cp_frac` are fractions of the mean chord aft of the panel leading
    edge.

    Sign convention, and it matters:

        positive -> hinge FORWARD of the panel CP. The normal force acts aft of the hinge
                    and drives the panel back toward neutral. Restoring, self-centring,
                    what you want.
        negative -> hinge AFT of the panel CP. The normal force acts forward of the hinge
                    and drives the panel to greater deflection. Divergent, "overbalanced".
                    The servo now fights a destabilising moment, and hinge/mass balance in
                    this region is what drives classical control surface flutter.

    Moving the hinge toward the CP shrinks the moment and is the easiest way to make the
    servo requirement tractable -- but the panel CP moves with Mach and angle of attack,
    so a hinge placed too close to it can cross over into divergent in flight. Keep real
    separation, for the same reason you keep static margin.

    An earlier version of this function placed the hinge at 0.30c, aft of the 0.25c CP,
    while its docstring claimed that was self-centring. It was divergent, and the abs()
    on the return value hid it.
    """
    normal_force = dynamic_pressure * panel_area * cn_alpha_panel * deflection_rad
    return normal_force * (cp_frac - hinge_frac) * mean_chord


def torque_margin(required: float, servo: Servo, gear_ratio: float = 1.0, derate: float = 0.4) -> float:
    """Ratio of available to required torque.

    `derate` accounts for the fact that stall torque is not usable torque: you need speed
    and stiffness at the operating point, not a stalled actuator. 0.4 is a reasonable
    starting assumption; measure your actual part.
    """
    available = servo.stall_torque * derate * gear_ratio
    # required is a signed hinge moment; the servo must overcome its magnitude either way.
    return available / max(abs(required), 1e-9)
