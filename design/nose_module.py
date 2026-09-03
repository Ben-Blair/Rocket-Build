"""The nose cone as a real part: the ogive shell, its integral shoulder, and the ballast rod.

WHAT WAS MISSING. `design/geometry.py`'s `NoseCone` has always been a shape function
(`radius_at`, `inner_radius_at`) used for aerodynamics and packing -- never a part.
`design/configure.py` carries `nose_ballast_kg = 0.100` and `nose_ballast_station = 0.191`,
and docs/00 R1/D10 call it "an adjustable threaded rod and washer stack in the nose
shoulder", but nothing in this project has ever given that rod a diameter, a washer size,
or a length. A mass and a station are not a part, and this is the fourth time this project
has found that gap (correction 33's harness, correction 37's pass-through plate, correction
38's access bulkheads, correction 42's coupler) -- an allowance that priced correctly and
was never turned into hardware.

THE SHELL ITSELF NEEDS NO NEW MODEL. `NoseCone.radius_at()`/`inner_radius_at()` already give
the outer and inner profile at every station from the tip (x=0) to the base (x=nose.length),
and the base radius already meets the airframe tube's own OD/ID exactly (79.4/74.8 mm) by
construction -- Barrowman's tangent-ogive condition is a tangency to the body tube, so this
was never going to disagree. The INTEGRAL SHOULDER past the base is already fully specified
too, by `design/joints.py`'s nose joint: `engagement` (79.40 mm, how far it reaches into the
nav bay) and `bore`/`airframe_id` (70.2 / 74.8 mm) -- it steps down by exactly one wall
thickness so its OD seats flush inside the nav bay's own ID, the same construction as every
other coupler in this project. So the shell is CAD work, not new modelling: this file adds
only the one thing that was genuinely absent.

THE BALLAST ROD.

WHY M6 STEEL, NOT A COPY OF THE SLED'S M4. The sled's rods (design/sled.py) are a structural
span carrying the sled's own bending load between two brackets; this rod carries nothing but
its own washer stack in tension against one captured nut, so the ordinary criterion is
different -- pick the rod that lets the WASHER STACK do the work within the room the cone
actually gives it, not the rod that survives a beam case. At the ballast station (191 mm) the
cone's own inner radius is 31.2 mm, so there is no shortage of room; the fitting constraint
is washer OD against a common stocked size, and M6 is the smallest metric size with a common
25 mm OD steel washer, which keeps the stack SHORT for a given mass -- the stack length goes
as 1/(OD^2 - ID^2), so a bigger washer buys length back at no cost in rod strength this case
does not need.

THE STACK LENGTH IS DERIVED, NOT CHOSEN. `washer_stack_length(mass)` inverts the washer's own
annular area and steel's density -- there is no dial here, only the arithmetic that turns a
target mass into a length, exactly the shape `seal.stack_length()` and `sled` follow for the
same reason: a physical stack has one length for a given mass and it should be computed, not
picked to look right.

WHAT THIS DOES NOT DO. It does not size the rod in tension or the nose plate's tapped hole
that anchors it -- the load is the washer stack's own weight under axial acceleration, a few
newtons at most, and every fastener in this project so far has been sized against a load two
orders of magnitude larger (the seal's shear pins, the sled's rods); asserting a check here
would be inventing a requirement rather than finding one. It does not model the tracker and
telemetry radio's own mounting sled, which rides further aft on the same rod
(`avionics.NOSE_STACK`, `avionics.check_nose_packing`) -- that is its own part, sized against
the cone's narrowing width the way `sled.py` sizes the nav bay sled against the tube's, and it
is the next thing to draw here, not this session's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

STEEL_DENSITY = 7900.0  # kg/m^3, 304 stainless -- matches sled.ROD_DENSITY

# M6: the smallest metric size with a common 25 mm OD steel washer. See the module
# docstring -- the room available (31.2 mm inner radius at the ballast station) does not
# bind, so the choice is "smallest rod that still uses a normal washer", not a strength case.
ROD_DIAMETER = 6.0e-3       # m
WASHER_OD = 25.0e-3         # m, standard M6 steel flat washer
WASHER_ID = 6.5e-3          # m, clearance hole for M6

# Forward margin ahead of the washer stack for a retaining nut, and aft margin from the
# stack's centre to where the rod can start being useful for the instrumentation sled that
# rides further aft on the same rod (avionics.NOSE_STACK) -- both round numbers, not derived,
# because neither has a load case: they are clearance for a hand tool, not a structural span.
NUT_CLEARANCE = 10.0e-3     # m


def washer_annular_area() -> float:
    return math.pi * ((WASHER_OD / 2.0) ** 2 - (WASHER_ID / 2.0) ** 2)


def washer_stack_length(mass_kg: float) -> float:
    """Length of the washer stack that masses `mass_kg`, m. Inverts area x length x density."""
    return mass_kg / (STEEL_DENSITY * washer_annular_area())


@dataclass(frozen=True)
class BallastRod:
    """The adjustable ballast provision: one M6 rod, a stack of washers, one nut.

    `station` is the stack's CENTRE, metres from the nose tip -- matches
    `configure.DesignParams.nose_ballast_station`, the number every other check already reads.
    """

    station: float
    mass: float
    rod_diameter: float = ROD_DIAMETER
    washer_od: float = WASHER_OD
    washer_id: float = WASHER_ID

    @property
    def stack_length(self) -> float:
        return washer_stack_length(self.mass)

    @property
    def stack_forward(self) -> float:
        return self.station - self.stack_length / 2.0

    @property
    def stack_aft(self) -> float:
        return self.station + self.stack_length / 2.0

    @property
    def rod_forward(self) -> float:
        """Where the rod itself starts -- forward of the stack, room for a nut."""
        return self.stack_forward - NUT_CLEARANCE

    def rod_length(self, anchor_station: float) -> float:
        """Rod length if it is anchored (captured in the nose plate) at `anchor_station`."""
        return anchor_station - self.rod_forward

    def __str__(self) -> str:
        mm = 1000.0
        return (
            f"M6 rod, {self.mass * 1000:.0f} g steel washer stack "
            f"(dia {self.washer_od * mm:.0f}/{self.washer_id * mm:.1f} mm) "
            f"{self.stack_length * mm:.2f} mm long, centred at station "
            f"{self.station * mm:.1f} mm ({self.stack_forward * mm:.1f}-"
            f"{self.stack_aft * mm:.1f} mm)"
        )


def default_ballast(station: float = 0.191, mass: float = 0.100) -> BallastRod:
    """The design-point ballast rod -- `configure.py`'s frozen station and mass."""
    return BallastRod(station=station, mass=mass)


# =======================================================================================
# THE SHELL, AS A REAL VOLUME -- WHAT DRAWING IT FOR REAL FOUND
# =======================================================================================
#
# `design/mass.py` has priced the nose cone since before this file existed as
# `wetted_area * wall_thickness * material_density` -- a thin-shell approximation that is
# exact for a CONSTANT-thickness shell with negligible curvature, and the nose is neither:
# `wetted_area` is a lateral-surface empirical correction (`NoseCone.wetted_area`, "1.06 x
# a cone's"), not the true ogive area, and it was never charged for the INTEGRAL SHOULDER
# at all -- that material was accounted for nowhere, the same gap `design/joints.py`
# correction 42 found on the nav bay side of the same joint.
#
# Once the shell is a real part (this file, and the CAD it drove), its volume is known
# exactly rather than approximated, and the two numbers disagree by more than rounding:
#
#     wetted-area estimate (ogive only)      ~180 g
#     real volume, ogive only                ~216 g
#     real volume, ogive + integral shoulder ~293 g
#
# The shoulder's ~77 g was never in the budget at all. `shell_mass_and_centroid()` replaces
# the estimate in `design/mass.py` with this real figure -- exact integration, not the CAD's
# own frustum approximation, so `design/mass.py` does not have to import Fusion or trust a
# document that might not be open.
def shell_volume_and_centroid(nose, shoulder_or: float, shoulder_ir: float,
                              shoulder_length: float, steps: int = 200
                              ) -> tuple[float, float]:
    """(volume m^3, centroid station m from the nose tip) of the ogive shell + integral
    shoulder, by direct integration of `NoseCone.radius_at`/`inner_radius_at` -- independent
    of any CAD approximation.

    `steps=200` is not a guess: `design/mass.py` calls this from `build_mass()`, which
    `evaluate()` calls on every iteration of every optimizer in this project
    (`robustness.py`, `sweep.py`, `motor_trade.py`), so this integration has to be cheap as
    well as accurate. It is both -- the profile is smooth and monotonic, so 200 steps agrees
    with 4000 to 0.00003% (158220.79 mm3 against 158220.80 -- checked directly, not
    assumed). Checked the other way too: `evaluate()` costs ~300 ms with or without this
    file, at 200 steps or 4000 -- that cost is pre-existing (the flight simulation, not this
    integration) and this function is not the thing to optimize if that ever needs fixing.
    200 was still chosen over 4000 on the general principle that a value called from a hot
    loop should not carry ballast it does not need, not because 4000 was proven to matter.
    """
    h = nose.length / steps
    vol = 0.0
    moment = 0.0
    for i in range(steps):
        x = (i + 0.5) * h
        a = math.pi * (nose.radius_at(x) ** 2 - nose.inner_radius_at(x) ** 2)
        vol += a * h
        moment += a * h * x

    shoulder_area = math.pi * (shoulder_or ** 2 - shoulder_ir ** 2)
    shoulder_vol = shoulder_area * shoulder_length
    shoulder_x = nose.length + shoulder_length / 2.0
    vol += shoulder_vol
    moment += shoulder_vol * shoulder_x

    return vol, (moment / vol if vol > 0.0 else nose.length * 0.5)


def shell_mass_and_centroid(nose, shoulder_or: float, shoulder_ir: float,
                            shoulder_length: float) -> tuple[float, float]:
    """(mass kg, centroid station m) -- `shell_volume_and_centroid` times the nose's own
    material density, so `design/mass.py` prices the real part instead of a wetted-area
    guess."""
    vol, centroid = shell_volume_and_centroid(nose, shoulder_or, shoulder_ir, shoulder_length)
    return vol * nose.material_density, centroid
