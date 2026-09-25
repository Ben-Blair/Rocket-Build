"""Does the avionics stack physically fit in the nav bay?

`recovery.check_packing` exists because `recovery_bay_cal = 4.5` was a number somebody typed
and nothing had ever verified. `nav_bay_cal = 1.6` is the same kind of number, typed at the
same time, and until this file nothing had verified it either. This is that check.

READ CORRECTION 5 BEFORE ACTING ON ANYTHING THIS FILE PRINTS. The first run of
`check_packing` said the recovery bay was 11 mm short and the airframe was briefly
lengthened on the strength of it. That verdict was wrong, and the way it was wrong is the
whole lesson: packed volume had been estimated as budgeted mass over an assumed bulk
density -- two guesses multiplied together -- against a real canopy the vendor publishes a
pack volume for. **Do not change frozen geometry on the strength of an estimate when a
published number is ten minutes away.**

Every envelope in this file is exactly that kind of estimate. D7 and D8 are open, so no part
here has been chosen, and the dimensions below are what a part of that description typically
measures rather than what any datasheet says. So this file is built to be REPLACED: each
component carries `measured` alongside its envelope, the report says which ones are still
guesses, and the verdict is stated as "on estimated envelopes" every time it is printed.

WHY A SLED IS NOT A VOLUME PROBLEM, which is the modelling point worth keeping.

The obvious check -- add up component volumes, compare against the bay's -- gives 249 cm3
against 558 cm3 and says the bay is half empty. It is the wrong check. Electronics mount on
the two faces of a flat sled, and a flat sled in a round tube can only use the rectangle
inscribed in the circle: at the 56.16 mm sled width SLED_WIDTH_FRACTION gives, the usable
height is +/-21.06 mm, not +/-37.4. (That worked example used to read "at a 60 mm sled width
... +/-22.3 mm", which was never a width this model produced.)
Nothing goes in the four corners the sled cannot reach, and nothing stacks more than one
board deep. So the binding quantity is FOOTPRINT AREA on two faces, and the bay's length is
what that area has to fit into.

This is the same class of error as reading the hinge moment and concluding a 9 g servo is
enough (correction 11), or as measuring the collar boss on a bounding box when the rim sits
at hypot(reach, OD/2) (correction 23). The volume is real, it is just not the constraint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Sled width, as a fraction of the tube bore.
#
# THIS IS NOW A FALLBACK, NOT THE DESIGN POINT. It was written as "0.80 of the bore is a
# working figure" -- a guess with no argument behind it, made when no sled existed. A sled
# exists now (`design/sled.py`), it is 0.846 of the bore, and `design/configure.py` passes
# that real width into `check_packing()` rather than this constant. 0.80 remains here as the
# figure to use when no part has been designed, which is the situation this whole module was
# written for.
#
# The number moved for a reason worth stating, because "the model was retuned until it fit"
# is the failure mode this project has a correction about (correction 5) and this is NOT
# that. 0.80 assumed the sled's carriers sit BESIDE it, so every millimetre of rod is a
# millimetre the sled cannot have. `sled.py` clocks the two rods perpendicular to the plate
# instead, above and below it, where they do not compete with its width at all -- and the
# width is then set by the only real constraint left, which is that a wider plate sits on a
# longer chord and steals height from the tallest component. The margin got better because
# the part got better, not because the constant was adjusted to suit.
SLED_WIDTH_FRACTION = 0.80

# Packing efficiency on a sled face. Boards are rectangles with connectors on their edges,
# they need standoff clearance, and the wiring has to get past them. 0.70 is what a tidy
# hand-built sled achieves. It is a guess of the same character as recovery.FILL_LIMIT and
# it should be treated with the same suspicion.
SLED_PACKING_EFFICIENCY = 0.70

# The bay's two end closures. A nav bay is closed at both ends -- forward against the nose
# shoulder, aft against the canard module -- and both plates plus their fillets come out of
# the length available to the sled.
END_CLOSURE_THICKNESS = 0.012  # m each, matching recovery.BULKHEAD_THICKNESS


@dataclass(frozen=True)
class Component:
    """One thing that has to sit on the sled.

    `length` runs along the rocket axis, `width` across the sled, `height` off its face.
    `measured` is False until the dimensions come off a datasheet for a part that has
    actually been chosen -- which is what D7 and D8 are for.
    """

    name: str
    mass: float  # kg
    length: float  # m
    width: float  # m
    height: float  # m
    measured: bool = False
    note: str = ""

    @property
    def footprint(self) -> float:
        return self.length * self.width

    @property
    def volume(self) -> float:
        return self.length * self.width * self.height


# The stack, described from `docs/04` section 5. Masses come from that table so this file
# and the BOM cannot disagree; envelopes are typical parts of each description.
#
# THE TRACKER AND THE RADIO MOVED TO THE NOSE, Aug 2026. The nav bay wanted 152 mm of sled
# and had 103. Of the four ways out (docs/01 correction 27) this is the only one that costs
# nothing structural: it touches no frozen geometry and it is where a tracker belongs
# anyway. Its whole job is to still be working when nothing else is, which argues for its
# own battery, in its own compartment, as far from the servo bus as the airframe allows --
# and the nose is also the best RF position on the vehicle, since the shoulder region is
# the one place a fibreglass airframe is not shielding an antenna.
#
# It did NOT make the nav bay fit. See `NAV_BAY_STACK`'s verdict; it went 152 -> 117 mm
# against 103, which is a 14 mm shortfall instead of a 49 mm one.
# SUPERSEDED BY D7, kept as the record of what the bay was checked against before any part
# was chosen. `selected_nav_bay_stack()` below is what the vehicle actually carries now; the
# difference between the two is correction 35, and it is 2.5x on one line item.
GUESSED_NAV_BAY_STACK: list[Component] = [
    Component("flight computer PCB", 0.060, 0.070, 0.040, 0.015,
              note="custom board; D7 sets this"),
    Component("deployment altimeter", 0.060, 0.045, 0.018, 0.010,
              note="commercial, independent of the PCB -- fires the charges"),
    Component("GNSS receiver + antenna", 0.030, 0.035, 0.035, 0.010,
              note="wants sky view; forward end of the sled"),
    Component("IMU daughterboard", 0.020, 0.025, 0.020, 0.008,
              note="isolate from servo noise"),
    Component("battery, 2S 1500 mAh", 0.090, 0.070, 0.035, 0.015),
    Component("servo power BEC", 0.025, 0.030, 0.020, 0.010),
]

# In the nose, on the ballast rod. Both are RF parts and neither talks to the flight
# computer in a way that needs a short wire.
NOSE_STACK: list[Component] = [
    Component("telemetry radio", 0.045, 0.045, 0.025, 0.012,
              note="in the nose, Aug 2026"),
    Component("GPS tracker, independent", 0.060, 0.060, 0.030, 0.015,
              note="in the nose, with its own battery -- independent means independent"),
]

# Kept so that the old arrangement can still be evaluated, and because a report that can
# only show the answer it arrived at is not showing an argument.
DEFAULT_STACK: list[Component] = GUESSED_NAV_BAY_STACK + NOSE_STACK

RELOCATED = {c.name for c in NOSE_STACK}

# Wiring is not a board and does not sit on a face, but it is 80 g of loom that has to go
# somewhere, and a sled with no room for the harness is a sled that does not close. Counted
# as footprint on the assumption it runs along one edge.
WIRING_FOOTPRINT = 0.070 * 0.020  # m^2


@dataclass
class PackingResult:
    fits: bool
    required_length: float  # m
    available_length: float  # m
    margin: float
    sled_width: float
    usable_height: float
    total_footprint: float
    components: list[Component]
    estimated: list[str]
    reason: str

    @property
    def all_measured(self) -> bool:
        return not self.estimated

    def __str__(self) -> str:
        verdict = "FITS" if self.fits else "NO FIT"
        return (
            f"{verdict:6s} nav bay          "
            f"need {self.required_length * 1000:5.1f} mm, "
            f"have {self.available_length * 1000:5.1f} mm "
            f"({self.margin * 1000:+6.1f} mm)  {self.reason}"
        )


def check_packing(inner_diameter: float, bay_length: float,
                  components: list[Component] | None = None,
                  width_fraction: float = SLED_WIDTH_FRACTION,
                  efficiency: float = SLED_PACKING_EFFICIENCY,
                  end_closures: int = 2) -> PackingResult:
    """Sled length the stack needs, against the length the bay has.

    Both faces of the sled are used, at `efficiency`, and the wiring gets its own footprint.
    """
    parts = list(components if components is not None else DEFAULT_STACK)

    sled_width = width_fraction * inner_diameter
    half = inner_diameter / 2.0
    usable_height = 2.0 * math.sqrt(max(half**2 - (sled_width / 2.0) ** 2, 0.0))

    footprint = sum(c.footprint for c in parts) + WIRING_FOOTPRINT
    per_mm = 2.0 * sled_width * efficiency  # two faces
    required = footprint / per_mm

    available = bay_length - end_closures * END_CLOSURE_THICKNESS
    fits = required <= available

    too_tall = [c.name for c in parts if c.height > usable_height / 2.0]

    if too_tall:
        reason = f"{', '.join(too_tall)} stands taller than the sled's half-height"
        fits = False
    elif fits:
        reason = f"{len(parts)} components on two faces at {efficiency:.0%}"
    else:
        reason = f"short by {(required - available) * 1000:.0f} mm"

    return PackingResult(
        fits=fits,
        required_length=required,
        available_length=available,
        margin=available - required,
        sled_width=sled_width,
        usable_height=usable_height,
        total_footprint=footprint,
        components=parts,
        estimated=[c.name for c in parts if not c.measured],
        reason=reason,
    )


def relocatable(components: list[Component] | None = None) -> list[Component]:
    """The nav bay stack, i.e. the full stack less what now lives in the nose.

    Retained after the move so `scripts/avionics_report.py` can still show both
    arrangements side by side. "The bay is short" had two kinds of answer and only one of
    them touched frozen geometry; keeping both computable is what makes that visible.
    """
    parts = components if components is not None else DEFAULT_STACK
    return [c for c in parts if c.name not in RELOCATED]


def free_volume(inner_diameter: float, bay_length: float,
                components: list[Component] | None = None,
                end_closures: int = 2) -> float:
    """Air left in the bay, m^3 -- what the static ports have to exchange.

    `design/venting.py` needs this and nothing else does. Note that it is the GEOMETRIC
    volume less the components, not less the sled: a sled is a plate a couple of millimetres
    thick and modelling it would be false precision against a 70% packing guess.

    Defaults to `NAV_BAY_STACK`, not `DEFAULT_STACK` -- the tracker and the radio are in the
    nose now and their volume is not in this bay's air. Small, and wrong is wrong.
    """
    parts = components if components is not None else NAV_BAY_STACK
    area = math.pi * inner_diameter**2 / 4.0
    geometric = area * (bay_length - end_closures * END_CLOSURE_THICKNESS)
    return max(geometric - sum(c.volume for c in parts), 0.0)


# ---------------------------------------------------------------------------------------
# The nose
# ---------------------------------------------------------------------------------------
@dataclass
class NoseFit:
    fits: bool
    forward_station: float  # m from the tip, where the sled starts
    aft_station: float
    sled_width: float
    length: float
    centroid: float
    footprint: float
    reason: str

    def __str__(self) -> str:
        verdict = "FITS" if self.fits else "NO FIT"
        return (
            f"{verdict:6s} nose stack       "
            f"{self.length * 1000:5.1f} mm sled at station "
            f"{self.forward_station * 1000:.0f}-{self.aft_station * 1000:.0f} mm, "
            f"{self.sled_width * 1000:.1f} mm wide  {self.reason}"
        )


def check_nose_packing(nose, components: list[Component] | None = None,
                       aft_station: float | None = None,
                       forward_limit: float = 0.0,
                       width_fraction: float = SLED_WIDTH_FRACTION,
                       efficiency: float = SLED_PACKING_EFFICIENCY,
                       steps: int = 400) -> NoseFit:
    """Where in the nose the relocated stack fits, and whether it does.

    A NOSE IS THE ONE PART OF THIS VEHICLE WHOSE AVAILABLE WIDTH IS A FUNCTION OF STATION.
    Every bay so far could be checked with one diameter. Here the sled is as wide as its
    NARROWEST end allows, which is its forward end, so the answer is a band and not a
    number -- and the sled wants to sit as far aft as it can, where the cone is fullest.

    `forward_limit` is where the sled is not allowed to go forward of. Pass the ballast
    station: the 100 g washer stack is on the same threaded rod and the boards go behind it.
    """
    parts = list(components if components is not None else NOSE_STACK)
    aft = nose.length if aft_station is None else aft_station
    footprint = sum(c.footprint for c in parts)

    # Walk forward from the base until there is enough two-sided sled area.
    for i in range(1, steps + 1):
        x = aft - (aft - forward_limit) * i / steps
        width = width_fraction * 2.0 * nose.inner_radius_at(x)
        capacity = 2.0 * width * efficiency * (aft - x)
        if capacity >= footprint:
            tallest = max(c.height for c in parts)
            half_height = nose.inner_radius_at(x)
            if tallest > half_height:
                return NoseFit(False, x, aft, width, aft - x, (x + aft) / 2.0, footprint,
                               f"{tallest * 1000:.0f} mm part in {half_height * 1000:.0f} mm "
                               f"of half-height at the forward end")
            return NoseFit(True, x, aft, width, aft - x, (x + aft) / 2.0, footprint,
                           f"{len(parts)} parts, aft of the ballast")
    return NoseFit(False, forward_limit, aft, 0.0, aft - forward_limit,
                   (forward_limit + aft) / 2.0, footprint,
                   "does not fit anywhere aft of the ballast station")


# ---------------------------------------------------------------------------------------
# The nose as a swappable module
# ---------------------------------------------------------------------------------------
#
# WHY THIS SECTION EXISTS. Putting the tracker and the radio in the nose was a packing fix
# (docs/01 correction 30). Keeping them there on purpose is a different decision: it makes
# the nose the vehicle's INSTRUMENTATION MODULE, and the point of an instrumentation module
# is that it comes off. Once GV-2 has measured the control derivatives and the campaign
# stops needing telemetry, the same nose can carry a payload instead.
#
# That only works if the module is genuinely self-contained, and "self-contained" is a
# requirement with a number attached rather than an aspiration. Three things decide it, and
# the third is the one that bites:
#
#   1. ITS OWN BATTERY. The tracker already has one -- an independent tracker that shares a
#      battery with the flight computer is not independent. The radio needs one too, or it
#      is not a module, it is a subassembly on the end of a power lead.
#   2. ONE ELECTRICAL INTERFACE, OR NONE. The tracker needs nothing from the vehicle. The
#      radio needs flight data, which is one connector at the joint -- so the module has
#      exactly one interface and a payload that needs none simply leaves it unmated.
#   3. ITS MASS IS PART OF THE STABILITY SOLUTION. This is the one nobody expects. 105 g at
#      station 300 mm is forward of a 794 mm CG, so it is doing the same job as the nose
#      ballast, and a payload of a different mass moves the static margin. `payload_envelope`
#      below is what that costs.

NOSE_MODULE_INTERFACES = {
    "telemetry radio": "one connector to the flight computer -- flight data downlink",
    "GPS tracker, independent": "none; own battery, own antenna, independent by design",
}


def payload_envelope(evaluate_fn, params, station: float,
                     masses: tuple[float, ...] = (0.0, 0.05, 0.105, 0.2, 0.3, 0.5),
                     baseline_mass: float = 0.105) -> list[tuple[float, float, float, bool]]:
    """Static margin against nose payload mass: (mass, SM min, SM max, within limits).

    Answers "if I take the instrumentation out and put something else there, what can it
    weigh". Swept rather than solved, because the trajectory has to be re-run for each point
    and the answer is a table a person reads, not a number a script consumes.

    THE BALLAST IS THE OTHER HALF OF THIS ANSWER and it is not swept here. 100 g sits at
    station 191 mm with provision for 300 g (docs/00 D10), and it was always meant to be set
    after weighing the finished vehicle. A payload that pushes the margin out of band can be
    trimmed back with it -- so read this table as "what does it cost", not "what is allowed".
    """
    from dataclasses import replace as _replace
    from . import mass as mass_mod

    out: list[tuple[float, float, float, bool]] = []
    original = dict(mass_mod.DEFAULT_AVIONICS_BUDGET)
    try:
        for m in masses:
            budget = dict(original)
            # Replace the two nose lines with a single payload line of the swept mass.
            for k in list(budget):
                if k in mass_mod.NOSE_AVIONICS:
                    budget.pop(k)
            budget["nose_payload"] = m
            mass_mod.NOSE_AVIONICS.add("nose_payload")
            mass_mod.DEFAULT_AVIONICS_BUDGET = budget
            ev = evaluate_fn(params)
            out.append((m, ev.flight.min_static_margin, ev.flight.max_static_margin,
                        ev.feasible))
    finally:
        mass_mod.DEFAULT_AVIONICS_BUDGET = original
        mass_mod.NOSE_AVIONICS.discard("nose_payload")
    return out


def nose_payload_volume(nose, forward_station: float, aft_station: float) -> float:
    """Internal volume of the nose cavity between two stations, m^3.

    What a future payload actually has to fit in. Integrated rather than approximated as a
    cylinder, because the whole point of `NoseCone.radius_at()` is that a cone is not one.
    """
    import math
    steps = 200
    total = 0.0
    dx = (aft_station - forward_station) / steps
    for i in range(steps):
        x = forward_station + (i + 0.5) * dx
        total += math.pi * nose.inner_radius_at(x) ** 2 * dx
    return total


# =======================================================================================
# D7 -- THE FLIGHT COMPUTER TRADE
# =======================================================================================
#
# `docs/00-requirements.md` states D7 as "COTS + custom controller board / full custom" and
# has carried it as TBD since the requirements were written. It is the largest and least
# specified line in the budget, it is the only thing that turns this file's six estimated
# envelopes into measurements, and `docs/01` step 6 wants the avionics flying as a PASSIVE
# LOGGER in the L1 and L2 cert flights -- which are monthly and weather-dependent, so it is
# the one open decision with a calendar attached.
#
# WHAT THIS SECTION IS FOR. Not to make the choice -- that is Ben's, like every other D
# decision -- but to price the three architectures against constraints this project has
# already computed, and in particular against the one nobody else can answer: WILL IT FIT.
# The nav bay is 9 mm short on guesses, and the three options differ by more than 9 mm.
#
# ENVELOPES ARE MARKED. `measured=True` means it came off a datasheet or a vendor page and
# the source is in the note; everything else is still the kind of estimate correction 5
# warns about. Read the `estimated` list in the report before believing any total.

# --- verified parts --------------------------------------------------------------------
TEENSY_41 = Component(
    "Teensy 4.1", 0.015, 0.061, 0.0178, 0.008, measured=True,
    note="61.0 x 17.8 mm (2.4 x 0.7 in), 600 MHz Cortex-M7, SD socket. pjrc.com; "
         "the 15 g is a retailer shipping weight and is almost certainly high")
STRATOLOGGER_CF = Component(
    "StratoLoggerCF", 0.0108, 0.0508, 0.0213, 0.0127, measured=True,
    note="2.0 x 0.84 x 0.5 in, 0.38 oz, 20 Hz logging, dual deploy. perfectflite.com")
TELEMEGA = Component(
    "Altus Metrum TeleMega", 0.030, 0.0826, 0.0318, 0.015,
    note="1.25 x 3.25 in board is VERIFIED; mass estimated. 6 pyro, GPS, telemetry, IMU, "
         "baro. Telemetry needs a HAM licence")

# --- estimated parts, all of them still correction 5 material ---------------------------
IMU_BREAKOUT = Component("IMU breakout", 0.008, 0.0254, 0.0178, 0.006,
                         note="1.0 x 0.7 in, the standard breakout footprint")
BARO_BREAKOUT = Component("barometer breakout", 0.006, 0.0254, 0.0178, 0.005,
                          note="1.0 x 0.7 in")
# Added by D8. Roll angle is unobservable without it -- specific force is invariant under
# rotation about the axis it lies along, and the GNSS velocity vector says where the nose
# points, not how the vehicle is clocked about it. L1, hold roll angle, is the project's
# MINIMUM success criterion, and until design/estimation.py went looking nothing had checked
# that the selected board could support it. It is on the CERT stack too, because the premise
# of the staging in docs/06 is that every line of the interesting software is identical.
MAG_BREAKOUT = Component("magnetometer breakout", 0.005, 0.0254, 0.0178, 0.005,
                         note="1.0 x 0.7 in, MMC5983MA class. About $5 -- see docs/07")
GNSS_MODULE = Component("GNSS module + patch antenna", 0.030, 0.030, 0.030, 0.010,
                        note="wants sky view; the patch antenna sets the footprint")
BATTERY_2S = Component("battery, 2S 1500 mAh", 0.090, 0.070, 0.035, 0.015)
# REPORTED, NOT ADOPTED (docs/14). The KST X08 Plus V6.0 is rated DC 3.8-8.4 V and the pack
# is 2S, so the servos run DIRECTLY off the battery and this part has no job: "separate supply
# from the IMU" is satisfied by a separate feed and filter off a star point at the pack, which
# is a layout rule rather than a component. Deleting it is 25 g and one line item off a nav
# bay that configure.py already flags as 114 g heavy -- but it changes the frozen stack and
# the packing that was checked against it, so it is Ben's call and not this file's.
BEC = Component("servo power BEC", 0.025, 0.030, 0.020, 0.010,
                note="NOT NEEDED -- see docs/14. 2S direct-drives an 8.4 V-rated servo")
STM32_BOARD = Component(
    "custom STM32 guidance board", 0.045, 0.070, 0.045, 0.012,
    note="ONE board: STM32F405, IMU, MAGNETOMETER, baro, GNSS, flash, 4x servo drive. The "
         "magnetometer is D8's doing and it is the whole reason D8 had to close before the "
         "schematic -- see docs/07. The envelope is a "
         "LAYOUT TARGET, not a measurement -- it is the only line here a design decision "
         "can shrink, and the only one whose accuracy is under Ben's control. "
         "docs/14 now specifies what goes on it: STM32F405RGT6, ICM-42688-P, MMC5983MA, "
         "MS5611, MAX-M10S, W25Q128JV, all SPI but the GNSS. The 70 x 45 still fits the "
         "sled with 14.4 mm across and 9.1 mm of headroom -- DO NOT GROW IT")


@dataclass(frozen=True)
class Option:
    """One D7 architecture."""

    key: str
    name: str
    nav_bay: list[Component]
    cost: float  # USD, order of magnitude
    build_weeks: float  # calendar weeks of hardware work before it can log a flight
    note: str
    replaces_nose: bool = False

    @property
    def mass(self) -> float:
        return sum(c.mass for c in self.nav_bay)


OPTIONS: list[Option] = [
    Option(
        "A", "Dev board + breakouts",
        [TEENSY_41, IMU_BREAKOUT, BARO_BREAKOUT, MAG_BREAKOUT, GNSS_MODULE, BATTERY_2S,
         BEC, STRATOLOGGER_CF],
        cost=260.0, build_weeks=1.0,
        note="Breakouts on a protoboard. Flying in a week, and every line of the "
             "interesting software -- filter, HIL, controller -- is identical to option C"),
    Option(
        "B", "TeleMega + guidance board",
        [TELEMEGA, TEENSY_41, IMU_BREAKOUT, BATTERY_2S, BEC],
        cost=520.0, build_weeks=1.5, replaces_nose=True,
        note="TeleMega collapses altimeter + telemetry + tracker + GNSS into one board. "
             "Costs a HAM licence, and it puts tracking back in the NAV BAY -- which undoes "
             "the swappable nose module of correction 32"),
    Option(
        "C", "Custom STM32 board",
        [STM32_BOARD, BATTERY_2S, BEC, STRATOLOGGER_CF],
        cost=400.0, build_weeks=8.0,
        note="Schematic, layout, fab, assembly, bring-up. SELECTED for the guided vehicle "
             "-- see docs/06. The deployment altimeter stays commercial and independent"),
]

SELECTED = "C"
CERT_FLIGHT_OPTION = "A"


# ---------------------------------------------------------------------------------------
# What the BOARD has to do, derived from this vehicle rather than from a tutorial
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class BoardRequirement:
    name: str
    value: str
    why: str
    slack: str = ""


def board_requirements(ev) -> list[BoardRequirement]:
    """The electrical requirements that fall out of the flight model.

    EVERY ONE OF THESE IS COMPUTED, not looked up. That is the point: a flight computer
    specified from a tutorial gets a 6-axis IMU and a 100 Hz loop because that is what
    tutorials say, and this vehicle has at least one requirement that no tutorial would
    produce -- see the gyro line, which is the only one here that is genuinely tight.
    """
    from . import estimation as est
    from .configure import DEFLECTION_LIMIT_DEG, ROLL_COMMAND_CAP_DEG

    f, pitch, roll = ev.flight, ev.pitch, ev.roll_interdig
    loop = pitch.pitch_natural_freq_hz * 20.0
    roll_capped = est.capped_roll_rate(ev)
    roll_limit = est.uncapped_roll_rate(ev)
    imu_hz = est.required_imu_rate(roll_limit)
    return [
        BoardRequirement(
            "gyro full scale", "at least +/-2000 deg/s, AND the roll command capped",
            f"steady roll rate is LINEAR in deflection: {roll_capped:.0f} deg/s at the "
            f"{ROLL_COMMAND_CAP_DEG:.0f} deg roll cap "
            f"({roll_capped / 2000 * 100:.0f}% of a +/-2000 dps part) but "
            f"{roll_limit:.0f} deg/s at the {DEFLECTION_LIMIT_DEG:.0f} deg deflection limit "
            f"({roll_limit / 2000 * 100:.0f}% -- SATURATED). Roll acceleration is "
            f"{roll.roll_accel_deg_s2:.0f} deg/s^2",
            "TIGHT, and D8 found this line had been quoting the wrong deflection: 1783 deg/s "
            "is the 6 deg figure and it was printed under an 8 deg heading, which put the "
            "vehicle at a comfortable-looking 89% of full scale when the deflection limit "
            "actually saturates the part. THE ROLL CAP IS WHAT KEEPS THE GYRO IN RANGE -- it "
            "is a sensing requirement, not only a control one. A +/-1000 dps IMU is out at "
            "any deflection. See design/estimation.py. "
            "THE +/-4000 dps PART OF THIS IS NOW DROPPED (docs/14): the option is real "
            "(ICM-45686) and the range is unusable while the cap holds, correction 58 having "
            "already shown a wider part flown uncapped is ~8x worse. The one condition that "
            "saturates +/-2000 is a FAULT, and a pegged gyro is detectable -- it is wired to "
            "the R12 latch instead of bought around"),
        BoardRequirement(
            "IMU output data rate", f"at least {imu_hz:.0f} Hz",
            f"first-order quaternion propagation rotates by 2*atan(w*dt/2), not w*dt, and "
            f"the shortfall is cubic in the step: at 100 Hz and {roll_limit:.0f} deg/s that "
            f"is {est.integration_drift(roll_limit, 100.0):.1f} deg/s of attitude drift with "
            f"a PERFECT gyro, against {est.integration_drift(roll_limit, imu_hz):.2f} deg/s "
            f"at {imu_hz:.0f} Hz",
            f"TIGHT, and it is NOT the control loop rate below. A board specified to the "
            f"{loop:.0f} Hz loop rate would sample the IMU ten times too slowly and the "
            f"arithmetic would lead every sensor error term combined. It sets the SPI clock "
            f"and the DMA, so it is fixed at layout"),
        BoardRequirement(
            "magnetometer", "required, 3-axis, on the board",
            "roll angle is unobservable without one: specific force is invariant under "
            "rotation about the axis it lies along, so the accelerometer cannot see roll, "
            "and the GNSS velocity vector fixes where the nose points rather than how the "
            "vehicle is clocked about it. L1 -- hold roll angle -- is the MINIMUM success "
            "criterion (docs/00 section 1.1)",
            "about $5 and one I2C address before layout, and unbuildable after. docs/01 step "
            "4.2 already assumed a magnetometer; the board D7 selected did not have one, and "
            "nothing had checked. Keep it away from the servo bus and the battery leads"),
        BoardRequirement(
            "accelerometer full scale", "at least +/-16 g",
            f"peak axial is {f.max_acceleration_g:.1f} g, and motor ignition and ejection "
            f"are transients on top of that",
            "comfortable at +/-16, and docs/02 already picked the motor partly to keep "
            "this under a clipping limit"),
        BoardRequirement(
            "control loop rate", f"at least {loop:.0f} Hz",
            f"pitch mode is {pitch.pitch_natural_freq_hz:.2f} Hz and a digital loop wants "
            f"20x the mode it is closing",
            "trivial for any STM32; an F405 at 168 MHz is three orders of margin"),
        BoardRequirement(
            "servo drive", "4 channels, 333 Hz update",
            f"four KST X08 Plus at {60 / 0.09:.0f} deg/s slew; the actuator must not be "
            f"the dominant lag in the loop",
            "needs 4 timer channels, which is nothing on an F4 -- but they must be on a "
            "SEPARATE SUPPLY from the IMU (docs/01, 'things that will bite you')"),
        BoardRequirement(
            "logging", "at least 100 Hz for 150 s",
            f"apogee at {f.apogee_time:.0f} s and the usable control window is "
            f"{ev.control_seconds:.1f} s; the whole flight to landing is about 120 s",
            "NOT TIGHT, BUT THE SLACK NOTE HERE WAS WRONG. It used to read 'onboard flash is "
            "enough'; written out as a channel list it is 20.5 kB/s and 4.9 MB a flight "
            "against 0.79 MB usable on an F405, which is 6.2x SHORT. The driver is raw IMU "
            "at the 1 kHz PROPAGATION rate -- 78% of the total -- and that channel is what "
            "makes GV-2 a measurement of Cm_delta rather than an anecdote, so it cannot be "
            "cut to fit. External flash, and design/flight_computer.py sizes it"),
        BoardRequirement(
            "power", "2S direct to the servos, 3.3 V buck for logic",
            "the KST X08 Plus is rated DC 3.8-8.4 V, so a 2S pack drives it with NO BEC; "
            "logic is 112 mA at 3.3 V and four servos are 1.03 A active, 4.0 A stalled",
            "CAPACITY IS NOT THE CONSTRAINT and nothing in this project had checked: the "
            "flight costs 0.06 Wh of 8.88 usable and 92% of the demand is an hour armed on "
            "the pad. PEAK CURRENT is what sizes the pack's C-rating, the battery lead and "
            "the 14 conductors through access_bulkhead's potted pass-through. See docs/14"),
        BoardRequirement(
            "storage", "external flash, soldered",
            "4.9 MB per flight at the rates above; the F405 has 1 MB shared with firmware",
            "a microSD socket is an ejection-shock liability for convenience a USB dump "
            "already provides, and every COTS altimeter this project trusts uses soldered "
            "flash. The SDIO pins stay free if that is ever revisited"),
        BoardRequirement(
            "deployment", "NOT on this board",
            "an independent commercial altimeter fires the charges (docs/04 section 5), "
            "and design/seal.py's feed-through is wired to it",
            "a safety argument and a range-approval one, and it also means a board bug "
            "loses the mission rather than the vehicle"),
    ]


def selected_nav_bay_stack() -> list[Component]:
    """What the nav bay actually carries, now that D7 is closed.

    Reads the selected option rather than restating its parts, so the packing check and the
    D7 trade cannot describe different vehicles -- which is the failure `configure.py` was
    written to prevent and the one `GUESSED_NAV_BAY_STACK` above is the fossil of.
    """
    return next(o for o in OPTIONS if o.key == SELECTED).nav_bay


# The name the rest of the project imports. It is the SELECTED stack now; it was the guessed
# one until D7 closed, and that swap is what made the nav bay fit.
NAV_BAY_STACK: list[Component] = selected_nav_bay_stack()
