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
inscribed in the circle: at a 60 mm sled width the usable height is +/-22.3 mm, not +/-37.4.
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

# Sled width, as a fraction of the tube bore. A sled has to slide in and out past the
# coupler and needs clearance for the rails or threaded rods that carry it; 0.80 of the bore
# is a working figure and it is the number the usable height falls out of.
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
NAV_BAY_STACK: list[Component] = [
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
DEFAULT_STACK: list[Component] = NAV_BAY_STACK + NOSE_STACK

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
