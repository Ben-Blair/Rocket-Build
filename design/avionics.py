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
# THE INDEPENDENT GPS TRACKER AND THE TELEMETRY RADIO ARE FLAGGED, not because they are
# uncertain but because they are the two parts with somewhere else to go -- see
# `relocatable()`. A tracker in particular wants to be as far from everything else as
# possible and is conventionally carried in the nose.
DEFAULT_STACK: list[Component] = [
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
    Component("telemetry radio", 0.045, 0.045, 0.025, 0.012, note="relocatable"),
    Component("GPS tracker, independent", 0.060, 0.060, 0.030, 0.015,
              note="relocatable -- conventionally lives in the nose"),
]

RELOCATABLE = {"telemetry radio", "GPS tracker, independent"}

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
    """The stack with the parts that have somewhere else to go taken out.

    THE POINT OF THIS FUNCTION is that "the bay is short" has two kinds of answer and only
    one of them touches frozen geometry. Lengthening the nav bay changes every number in the
    vehicle. Moving the tracker into the nose cone changes nothing except a wire run -- and
    it is where a tracker belongs anyway, since its whole job is to still be working when
    nothing else is, which argues for its own battery in its own compartment.
    """
    parts = components if components is not None else DEFAULT_STACK
    return [c for c in parts if c.name not in RELOCATABLE]


def free_volume(inner_diameter: float, bay_length: float,
                components: list[Component] | None = None,
                end_closures: int = 2) -> float:
    """Air left in the bay, m^3 -- what the static ports have to exchange.

    `design/venting.py` needs this and nothing else does. Note that it is the GEOMETRIC
    volume less the components, not less the sled: a sled is a plate a couple of millimetres
    thick and modelling it would be false precision against a 70% packing guess.
    """
    parts = components if components is not None else DEFAULT_STACK
    area = math.pi * inner_diameter**2 / 4.0
    geometric = area * (bay_length - end_closures * END_CLOSURE_THICKNESS)
    return max(geometric - sum(c.volume for c in parts), 0.0)
