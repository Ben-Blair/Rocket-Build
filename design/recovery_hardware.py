"""The U-bolt, its backing plate and the ejection charge well -- the three parts every
bulkhead script in this project has refused to draw.

THE GAP THIS FILE CLOSES. The U-bolt HOLES have been in the CAD since correction 50
(`scripts/make_seal_cad_fusion.py`, from `seal.hole_layout()`'s own positions). The hardware
standing proud of them has never existed. Three scripts say so in their own docstrings and
one of them is blunt about which one matters -- `scripts/make_bulkhead_cad.py`: *"The
backing plate is the one that matters -- it is STRUCTURE (`seal.point_load_stress` goes as
the log of the plate-to-footprint radius ratio) -- and it is not here, so this part is not
yet the whole harness anchor."* `design/seal.py` says the same thing twice more, at
`UBOLT_HOLE_DIAMETER` and at the end of `check_hole_layout()`.

THE ANSWER, STATED BEFORE THE ARITHMETIC BECAUSE IT IS THE ONE IDEA IN THIS FILE: **a
U-bolt used as a harness anchor is not loaded the way a U-bolt is rated, and the size this
project assumed does not carry its own load.** `seal.py` has carried, since it was written,
the aside that settled the question without asking it: *"An M5 U-bolt on a 25 mm leg spacing
is the ordinary size for this load -- 1.3 kN through two 5 mm legs is 33 MPa of shear in
stainless, which is nothing."* Two things are wrong with that sentence and they compound.

  1. **THE LEGS ARE NOT IN SHEAR.** The harness pulls along the bolt's axis, away from the
     plate. The legs are in TENSION and the nuts react it. Shear never enters.
  2. **THE LEGS ARE NOT WHAT BREAKS.** What breaks is the CROWN, in bending, at the two
     bends where it meets the legs -- which is where U-bolts used as anchors are actually
     observed to straighten. A published U-bolt load rating is for CLAMPING A PIPE, where
     the crown bears on the pipe and the legs really are in tension and nothing bends. Using
     that rating for an anchor compares two different structures.

Sized against the mode that governs, the anchor is **M8 rather than M5**, which means the
5.5 mm holes already cut in both existing bulkheads become 8.5 mm. That is the cost of the
finding and it is cheap: they are not drilled yet.

TWO MORE THINGS FELL OUT, AND BOTH ARE GEOMETRY NOBODY HAD RUN.

  * **THE HARNESS DOES NOT FIT THROUGH THE U-BOLT.** `recovery.size_harness()` selects 3/4"
    tubular nylon -- 19.1 mm of webbing. An M8 U-bolt on `seal.UBOLT_LEG_SPACING` leaves a
    17.0 mm clear opening. Two sized parts of this vehicle, and nothing had ever put them
    next to each other. Opening the U-bolt up until the webbing passes drives it to M10 and
    ~310 g of stainless across four anchors, which is not the answer. The answer is that the
    webbing was never supposed to pass through it: `recovery.HARNESS_HARDWARE_KG` has priced
    "links and swivels" since it was written, and **the harness attaches through a QUICK LINK
    and the link goes through the U-bolt.** A 6 mm link needs 8 mm of opening, not 21. This
    file records that as a requirement rather than leaving it as the thing everybody happens
    to do.
  * **THE INTERNAL BULKHEAD'S CONDUIT HOLE IS IN THE WORST PLACE FOR A BACKING PLATE.**
    `seal.hole_layout()` puts it at 45 degrees "so it is equidistant from both U-bolt legs"
    -- a good choice made when the only things on that face were holes. A backing plate
    spans the legs, so its footprint is long in Y and narrow in X, and 45 degrees is exactly
    where it reaches furthest. Moved to 0 degrees, PERPENDICULAR to the legs, where the plate
    is narrow, it clears by 4.1 mm instead of overlapping by 2.5. Same radius, same stress,
    same everything the placement was chosen for.

WHAT SIZES THE BACKING PLATE, WHICH IS NOT WHAT SIZES MOST PLATES. Its own bending needs
1.2 mm. What it is FOR is the log term in `Bulkhead.point_load_stress()`: the plate sets
`footprint_radius`, and the disc's stress falls as the log of the ratio. `seal.py` has always
passed a hardcoded 6.0 mm there -- a bare nut face -- and said in a comment that this was
the number a real plate would replace. Replaced, the aft gas seal's U-bolt margin goes
**5.34x to 9.09x**. That is a result of the part existing, not a retune: nothing was
softened to get it, and `seal.py`'s default is unchanged so every previously reported number
still reproduces.

WHAT THIS FILE DOES NOT DO.
  * It does not size the DROGUE harness's own opening shock. `seal.py` computes the main's
    and this file anchors all four U-bolts against it, which is conservative for the two on
    the drogue and has the real build advantage of one part number in four places. The
    drogue's own opening load has never been computed by anything here; it is smaller, so
    nothing below is unsafe for it, but the number does not exist.
  * It does not model the crown as anything but a fixed-ended arch. The straight-beam
    idealisation is reported alongside because it is the number a hand calculation reaches
    for, and the anchor does NOT clear 2.0x against it -- see `check_recovery_hardware()`,
    which says so rather than picking the model that passes. A destructive pull test on the
    actual bolt is what settles it and it has not been done.
  * It does not choose an e-match or a terminal block part number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import recovery
from .materials import DATASHEET_CONFIDENCE_MARGIN, G10_BEARING, SHAFT_YIELD
from .seal import (
    BP_FLAME_TEMPERATURE, BP_GAS_CONSTANT, Bulkhead, G10_SHEET_THICKNESS, Hole,
    MIN_LIGAMENT, PLATE_MARGIN_REQUIRED, UBOLT_LEG_SPACING,
)

G10_DENSITY = 1850.0  # kg/m3
STEEL_DENSITY = recovery.STEEL_DENSITY  # 7850, already committed to by recovery.py


# ---------------------------------------------------------------------------------------
# The U-bolt
# ---------------------------------------------------------------------------------------

# Rod diameters U-bolts are stocked in, m. Metric coarse; the imperial sizes interleave and
# 1/4-20 (6.35 mm) sits between M6 and M8, which matters because 1/4-20 is what the hobby
# actually buys and it lands on the wrong side of the answer below.
UBOLT_ROD_OPTIONS = [0.004, 0.005, 0.006, 0.008, 0.010, 0.012]  # m

# Tensile stress area of the thread, m2, for each of the above -- ISO metric coarse. The
# legs are in TENSION (see the module docstring), so this is the area that matters and the
# plain shank area would be optimistic by about 25%.
THREAD_STRESS_AREA = {  # m2
    0.004: 8.78e-6, 0.005: 14.2e-6, 0.006: 20.1e-6,
    0.008: 36.6e-6, 0.010: 58.0e-6, 0.012: 84.3e-6,
}

# The anchor's material. 303 is the free-machining grade design/materials.py already carries;
# a bought U-bolt is more often 304 and slightly weaker annealed, more often stronger
# cold-formed. The band is real and the margin below is quoted knowing it.
UBOLT_MATERIAL = "303 stainless"

# Clear opening the U-bolt has to leave. NOT the webbing width -- see the module docstring.
# A 6 mm quick link needs its stock plus working room to be threaded and closed one-handed
# with cold hands, which is what this number is.
LINK_CLEARANCE = 0.008  # m

# Straight length of leg below the crown's tangent, m: through the backing plate, through the
# bulkhead, a washer, a nyloc nut and two threads of stand-out.
#
# IT IS A STACK, AND UNTIL CORRECTION 57 IT WAS A GLOBAL THAT NOTHING CHECKED AGAINST THE
# SPACE BEHIND EACH ANCHOR. Three of the four anchors have a whole compartment behind them.
# The fourth stands on the booster's forward bulkhead, and what is behind THAT is the motor:
# `motor_mount.forward_gap` is 11.08 mm and this stack needs 15.20 mm aft of the bulkhead, so
# the legs ran 4.12 mm into the motor. Nothing compared the two -- the U-bolt is sized in this
# file, the gap is computed in `motor_mount.py`, and no check imported one into the other.
# Broken out so a station with less room can be given a stack that fits, and so
# `check_recovery_hardware()` can compare the two numbers. See docs/01 correction 57.
UBOLT_WASHER_THICKNESS = 0.0016   # m, a plain M8 washer
UBOLT_NUT_HEIGHT = 0.0080         # m, M8 nyloc (DIN 985)
UBOLT_NUT_HEIGHT_LOW = 0.0060     # m, M8 ALL-METAL prevailing-torque, low pattern
UBOLT_THREAD_STANDOUT = 0.0025    # m, two threads at 1.25 mm pitch
UBOLT_THREAD_STANDOUT_MIN = 0.0013  # m, one thread -- still inspectable


def leg_standout(bulkhead_thickness: float, plate_thickness: float,
                 washer: bool = True, nut_height: float = UBOLT_NUT_HEIGHT,
                 thread_standout: float = UBOLT_THREAD_STANDOUT) -> float:
    """Straight leg length below the crown's tangent, m -- derived, not typed.

    Everything the leg has to pass through or carry, in order: the bulkhead it anchors to,
    the backing plate under the nut, optionally a washer, the nut, and enough thread past
    the nut to see that it is engaged.
    """
    return (bulkhead_thickness + plate_thickness
            + (UBOLT_WASHER_THICKNESS if washer else 0.0)
            + nut_height + thread_standout)


# The default stack, unchanged in value from the constant this replaces (4.8 + 3.2 + 1.6 +
# 8.0 + 2.5 = 20.1 mm, rounded to 20.0 before it was derived).
UBOLT_LEG_STANDOUT = 0.020  # m

# Nut and washer mass per leg, kg. Catalogue figures for stainless, not computed.
UBOLT_FASTENER_MASS = {0.004: 0.0015, 0.005: 0.0022, 0.006: 0.0035,
                       0.008: 0.0060, 0.010: 0.0110, 0.012: 0.0180}


# ---------------------------------------------------------------------------------------
# The backing plate
# ---------------------------------------------------------------------------------------

# G-10, the same stock the bulkheads are cut from. Steel would be stiffer and it is what a
# fender washer would be, but the plate's job is to set a FOOTPRINT, not to be rigid relative
# to a disc of its own material, and four steel plates are 100 g the vehicle does not have.
# One material, one offcut, one supplier.
# 7.0 mm, and it is set by the INTERNAL BULKHEAD'S AFT FACE rather than by the plate.
# 8.5 mm (one hole diameter) is the comfortable figure and it is what this started at; on
# every other face it fits. On that one face -- U-bolt crown, opposing backing plate, conduit
# and drogue charge well, all on a 74.8 mm disc -- 8.5 leaves the well 0.34 mm of ligament to
# the plate, which is not a clearance, it is a coincidence. 7.0 buys 3.2 mm and costs 5.7% of
# the footprint radius, which the disc's U-bolt margin absorbs without noticing.
BACKING_PLATE_EDGE = 0.0070  # m, metal beyond each hole's centre to the plate's own edge

# The plate must not dish under the nuts, or the footprint the log term assumes is not there.
# Its own bending needs 1.2 mm; this is the practical floor, and it is the same argument
# design/access_bulkhead.py makes for both access plates.
BACKING_PLATE_THICKNESS_FLOOR = 0.0032  # m


# ---------------------------------------------------------------------------------------
# The charge well
# ---------------------------------------------------------------------------------------

# Loose-poured black powder, kg/m3. 4Fg pours at about 1.0 g/cm3 and 2Fg a little less; the
# band is 900-1100 and the well is sized on the low end because a well that is too big is a
# nuisance and a well that is too small cannot hold the charge at all.
BP_BULK_DENSITY = 900.0  # kg/m3

# You do not fill a charge well to the brim -- the wadding and the tape cap need the top.
WELL_FILL_FRACTION = 0.70

# Room for the e-match head and its leads inside the well, m3. A working figure.
EMATCH_ALLOWANCE = 0.3e-6  # m3

# Thin-wall tube the well is made from. Bores are stocked sizes; the wall is one figure
# because at this diameter everything thin-walled is about a millimetre.
WELL_BORE_OPTIONS = [0.008, 0.010, 0.012, 0.016]  # m
WELL_WALL = 0.001  # m

# How far the well may stand proud into the packed compartment. A deep narrow well is a worse
# part than a short fat one: it is harder to fill, harder to see into, and it is a lever the
# canopy can catch on. 21 mm is the practical ceiling and it is what picks the bore -- and it
# is 21 rather than a round 20 because at 20 the drogue's well is forced one bore size UP, to
# dia 10, and the extra millimetre of radius is exactly what the internal bulkhead's aft face
# does not have. A ceiling that costs a millimetre of depth to save a millimetre of radius is
# the right way round on a disc that is full.
WELL_MAX_PROUD = 0.021  # m

# Terminal block on the same face, one per well. Catalogue mass.
TERMINAL_BLOCK_MASS = 0.005  # kg


@dataclass(frozen=True)
class UBolt:
    """One harness anchor. Stainless rod bent into a U, through two holes, two nuts."""

    rod_diameter: float  # m
    leg_spacing: float  # m, centre to centre
    load: float  # N, the opening shock it anchors
    # Straight leg below the crown tangent. Defaults to the standard stack; the booster
    # forward anchor is given a shorter one because the motor is 11.08 mm behind it.
    leg_standout: float = UBOLT_LEG_STANDOUT

    @property
    def crown_radius(self) -> float:
        return self.leg_spacing / 2.0

    @property
    def hole_diameter(self) -> float:
        """m. Half a millimetre of clearance, the same rule seal.py's 5.5-for-M5 used."""
        return self.rod_diameter + 0.0005

    @property
    def clear_opening(self) -> float:
        """m. What actually passes through the U -- the spacing less one rod diameter."""
        return self.leg_spacing - self.rod_diameter

    @property
    def section_modulus(self) -> float:
        """m3, round section."""
        return math.pi * self.rod_diameter**3 / 32.0

    @property
    def crown_moment(self) -> float:
        """Peak bending moment in the crown, N.m. DESIGN CASE.

        Fixed-ended semicircular arch, load distributed over the wrap: M = P*R/pi, peaking at
        the two bends rather than at the apex -- which is where a U-bolt used as an anchor is
        actually seen to straighten. The arch carries most of the pull in direct tension along
        the rod and only the remainder in bending, which is why a U-bolt works at all.
        """
        return self.load * self.crown_radius / math.pi

    @property
    def crown_moment_straight(self) -> float:
        """N.m. The same crown idealised as a STRAIGHT simply supported beam of span equal to
        the leg spacing, load at midspan: M = P*R/2. 1.57x the arch value.

        Reported, not designed to. It is the number a hand calculation reaches for and it is
        a different structure, not a bound on this one -- a straight beam has no thrust line.
        `check_recovery_hardware()` prints the margin against it anyway, because it does not
        clear 2.0x and pretending otherwise is how correction 15's joint reported a pass.
        """
        return self.load * self.crown_radius / 2.0

    @property
    def crown_stress(self) -> float:
        return self.crown_moment / self.section_modulus

    @property
    def crown_stress_straight(self) -> float:
        return self.crown_moment_straight / self.section_modulus

    @property
    def leg_tension(self) -> float:
        """Pa. The mode seal.py's aside called shear."""
        return (self.load / 2.0) / THREAD_STRESS_AREA[self.rod_diameter]

    @property
    def allowable(self) -> float:
        return SHAFT_YIELD[UBOLT_MATERIAL]

    @property
    def crown_margin(self) -> float:
        return self.allowable / max(self.crown_stress, 1.0)

    @property
    def crown_margin_straight(self) -> float:
        return self.allowable / max(self.crown_stress_straight, 1.0)

    @property
    def leg_margin(self) -> float:
        return self.allowable / max(self.leg_tension, 1.0)

    @property
    def rod_length(self) -> float:
        """m, centreline: the crown's semicircle plus two straight legs."""
        return math.pi * self.crown_radius + 2.0 * self.leg_standout

    @property
    def rod_volume(self) -> float:
        return math.pi * (self.rod_diameter / 2.0) ** 2 * self.rod_length

    @property
    def proud_volume(self) -> float:
        """m3 displaced in the PACKED compartment -- the crown only. The legs, the nuts and
        the backing plate are all on the other face."""
        return math.pi * (self.rod_diameter / 2.0) ** 2 * (math.pi * self.crown_radius)

    @property
    def proud_height(self) -> float:
        return self.crown_radius + self.rod_diameter / 2.0

    @property
    def mass(self) -> float:
        return self.rod_volume * STEEL_DENSITY + 2.0 * UBOLT_FASTENER_MASS[self.rod_diameter]


@dataclass(frozen=True)
class BackingPlate:
    """The part that makes the U-bolt a harness anchor instead of two holes in a disc."""

    length: float  # m, along the leg spacing
    width: float  # m, across it
    thickness: float  # m
    hole_diameter: float  # m
    leg_spacing: float
    load: float  # N

    @property
    def area(self) -> float:
        return self.length * self.width

    @property
    def footprint_radius(self) -> float:
        """m. THE NUMBER THIS PART EXISTS FOR -- the equivalent radius of the load patch
        `Bulkhead.point_load_stress()` takes, in place of the bare 6 mm nut face seal.py has
        assumed since it was written."""
        return math.sqrt(self.area / math.pi)

    @property
    def overhang(self) -> float:
        """m, plate beyond each leg."""
        return self.length / 2.0 - self.leg_spacing / 2.0

    @property
    def bending_moment(self) -> float:
        """N.m. Two leg loads up, the disc's reaction spread over the plate's own footprint
        down. Worst of the overhang moment and the midspan sag."""
        w = self.load / self.length  # N/m of uniform reaction
        overhang = w * self.overhang**2 / 2.0
        midspan = w * (self.length / 2.0) ** 2 / 2.0 - (self.load / 2.0) * self.overhang
        return max(overhang, abs(midspan))

    @property
    def stress(self) -> float:
        net = self.width  # the section at midspan is uncut; the holes are at the legs
        return 6.0 * self.bending_moment / (net * self.thickness**2)

    @property
    def margin(self) -> float:
        from .materials import G10_FLEXURAL
        return G10_FLEXURAL / max(self.stress, 1.0)

    @property
    def bearing_stress(self) -> float:
        """Pa, the leg's nut washer bearing on the plate. A washer one and a half diameters
        across, less the hole."""
        washer_od = 2.2 * self.hole_diameter
        area = math.pi / 4.0 * (washer_od**2 - self.hole_diameter**2)
        return (self.load / 2.0) / area

    @property
    def bearing_margin(self) -> float:
        return G10_BEARING / max(self.bearing_stress, 1.0)

    @property
    def volume(self) -> float:
        holes = 2.0 * math.pi * (self.hole_diameter / 2.0) ** 2 * self.thickness
        return self.area * self.thickness - holes

    @property
    def mass(self) -> float:
        return self.volume * G10_DENSITY


@dataclass(frozen=True)
class ChargeWell:
    """A thin-wall tube bonded over the charge's own lead hole, on the bulkhead's fired face."""

    name: str
    charge: float  # kg of black powder it has to hold
    bore: float  # m
    depth: float  # m
    station_radius: float  # m, where on the disc it sits
    wall: float = WELL_WALL
    clocking_deg: float = 0.0
    face: str = ""

    @property
    def centre(self) -> tuple[float, float]:
        a = math.radians(self.clocking_deg)
        return self.station_radius * math.cos(a), self.station_radius * math.sin(a)

    @property
    def outer_diameter(self) -> float:
        return self.bore + 2.0 * self.wall

    @property
    def internal_volume(self) -> float:
        return math.pi * (self.bore / 2.0) ** 2 * self.depth

    @property
    def charge_volume(self) -> float:
        return self.charge / BP_BULK_DENSITY

    @property
    def required_volume(self) -> float:
        return self.charge_volume / WELL_FILL_FRACTION + EMATCH_ALLOWANCE

    @property
    def fits(self) -> bool:
        return self.internal_volume >= self.required_volume

    @property
    def utilisation(self) -> float:
        return self.required_volume / self.internal_volume

    @property
    def proud_volume(self) -> float:
        """m3 displaced in the packed compartment -- the whole tube, outside diameter."""
        return math.pi * (self.outer_diameter / 2.0) ** 2 * self.depth

    @property
    def mass(self) -> float:
        tube = math.pi / 4.0 * (self.outer_diameter**2 - self.bore**2) * self.depth
        return tube * G10_DENSITY + TERMINAL_BLOCK_MASS


# ---------------------------------------------------------------------------------------
# Sizing
# ---------------------------------------------------------------------------------------
def size_ubolt(load: float, leg_spacing: float = UBOLT_LEG_SPACING,
               rods: list[float] | None = None,
               margin: float = PLATE_MARGIN_REQUIRED) -> tuple[float, str]:
    """Smallest STOCKED rod whose CROWN clears `margin` in bending, and what governed.

    The crown, not the legs. See the module docstring: a U-bolt used as an anchor fails at
    the bends and a U-bolt's published rating is for a mode it is not in here.
    """
    options = sorted(rods if rods is not None else UBOLT_ROD_OPTIONS)
    for d in options:
        if d >= leg_spacing:
            break
        u = UBolt(d, leg_spacing, load)
        if u.crown_margin >= margin and u.leg_margin >= margin:
            return d, ("the crown in bending" if u.crown_margin <= u.leg_margin
                       else "the legs in tension")
    return max(options), "the crown in bending (no stocked rod clears it)"


def size_backing_plate(load: float, hole_diameter: float, leg_spacing: float,
                       floor: float = BACKING_PLATE_THICKNESS_FLOOR,
                       thicknesses: list[float] | None = None) -> BackingPlate:
    """The plate, sized. Its plan comes from the leg spacing and an edge distance; its
    thickness comes from the practical floor, because its own bending asks for a third of it.
    """
    length = leg_spacing + 2.0 * BACKING_PLATE_EDGE
    width = 2.0 * BACKING_PLATE_EDGE + hole_diameter
    options = sorted(thicknesses if thicknesses is not None else G10_SHEET_THICKNESS)
    for t in options:
        trial = BackingPlate(length, width, t, hole_diameter, leg_spacing, load)
        if trial.margin >= PLATE_MARGIN_REQUIRED and t >= floor:
            return trial
    return BackingPlate(length, width, max(options), hole_diameter, leg_spacing, load)


def size_charge_well(name: str, charge: float, station_radius: float,
                     clocking_deg: float = 0.0, face: str = "",
                     bores: list[float] | None = None) -> ChargeWell:
    """Smallest STOCKED bore whose well stands no more than `WELL_MAX_PROUD` into the packed
    compartment. A deep narrow well is a worse part than a short fat one."""
    options = sorted(bores if bores is not None else WELL_BORE_OPTIONS)
    need = charge / BP_BULK_DENSITY / WELL_FILL_FRACTION + EMATCH_ALLOWANCE

    def cut(b: float) -> float:
        """Depth rounded UP to the next half millimetre -- a cut length, not a volume."""
        exact = need / (math.pi * (b / 2.0) ** 2)
        return math.ceil(exact / 0.0005) * 0.0005

    for b in options:
        if cut(b) <= WELL_MAX_PROUD:
            return ChargeWell(name, charge, b, cut(b), station_radius,
                              clocking_deg=clocking_deg, face=face)
    b = max(options)
    return ChargeWell(name, charge, b, cut(b), station_radius,
                      clocking_deg=clocking_deg, face=face)


@dataclass
class AnchorResult:
    """One bulkhead face's worth of hardware: a U-bolt, its plate, and where it sits."""

    name: str
    bulkhead: Bulkhead
    ubolt: UBolt
    plate: BackingPlate
    governed_by: str
    # Which face the CROWN stands on, and how the legs are clocked. The backing plate is
    # always on the OTHER face, because it goes under the nuts.
    #
    # CLOCKING EXISTS BECAUSE OF THE INTERNAL BULKHEAD. That disc anchors a harness both
    # ways, so it carries a U-bolt on each face -- and two U-bolts cannot share two holes.
    # They clock 90 degrees apart, which is what puts a backing plate along each axis and
    # leaves only the diagonal clear for the conduit and the charge well. See
    # seal.INTERNAL_CONDUIT_RADIUS.
    face: str = ""
    clocking_deg: float = 0.0

    def leg_positions(self) -> list[tuple[float, float]]:
        a = math.radians(self.clocking_deg)
        half = self.ubolt.leg_spacing / 2.0
        return [(-half * math.sin(a), half * math.cos(a)),
                (half * math.sin(a), -half * math.cos(a))]

    def plate_halfspans(self) -> tuple[float, float]:
        """Half-extent of the backing plate in x and y, m, at this anchor's clocking. The
        plate is long ACROSS the legs and narrow the other way."""
        if abs(self.clocking_deg % 180.0) < 1e-9:
            return self.plate.width / 2.0, self.plate.length / 2.0
        return self.plate.length / 2.0, self.plate.width / 2.0

    def crown_halfspans(self) -> tuple[float, float]:
        """Half-extent of the crown standing proud of its own face, m."""
        along = self.ubolt.crown_radius + self.ubolt.rod_diameter / 2.0
        across = self.ubolt.rod_diameter / 2.0
        if abs(self.clocking_deg % 180.0) < 1e-9:
            return across, along
        return along, across

    @property
    def bare_stress(self) -> float:
        """Pa in the disc with no backing plate -- seal.py's hardcoded 6 mm nut face."""
        return self.bulkhead.point_load_stress(self.ubolt.load, 0.006)

    @property
    def backed_stress(self) -> float:
        return self.bulkhead.point_load_stress(self.ubolt.load, self.plate.footprint_radius)

    @property
    def bare_margin(self) -> float:
        return self.bulkhead.flexural_allowable / max(self.bare_stress, 1.0)

    @property
    def backed_margin(self) -> float:
        return self.bulkhead.flexural_allowable / max(self.backed_stress, 1.0)

    @property
    def mass(self) -> float:
        return self.ubolt.mass + self.plate.mass

    @property
    def displaced_volume(self) -> float:
        """m3 of packing this anchor costs on ONE face: its own crown, plus the plate and
        nuts of the anchor on the other face, which lie flat against this one. Both existing
        bulkheads carry a U-bolt each way, so every packed face sees both."""
        nuts = 2.0 * UBOLT_FASTENER_MASS[self.ubolt.rod_diameter] / STEEL_DENSITY
        return self.ubolt.proud_volume + self.plate.volume + nuts


@dataclass
class RecoveryHardwareResult:
    anchors: list[AnchorResult]
    wells: list[ChargeWell]
    webbing_width: float  # m, what recovery.size_harness() picked
    n_anchors: int
    # Clear space aft of the booster's forward bulkhead before the motor, m. Carried on the
    # result rather than recomputed in the check, so the check cannot quietly skip itself --
    # motor_mount.py computes it, this file has to respect it. Correction 57.
    booster_forward_gap: float = 0.0

    @property
    def anchor(self) -> AnchorResult:
        """The design anchor -- one part number in four places."""
        return self.anchors[0]

    @property
    def mass(self) -> float:
        return (self.n_anchors * self.anchor.mass + sum(w.mass for w in self.wells)
                + sum(w.charge for w in self.wells))

    @property
    def envelope_volume(self) -> float:
        """m3 per U-bolt station, to compare against recovery.UBOLT_ENVELOPE_VOLUME."""
        return self.anchor.displaced_volume


def recovery_hardware_from_evaluation(ev) -> RecoveryHardwareResult:
    """Build every piece of recovery hardware from the vehicle's own numbers.

    The load, the charges and the webbing all come from parts this project already sized --
    `seal.from_evaluation()`, `seal.internal_bulkhead_from_evaluation()` and
    `recovery.size_harness()`. Nothing is restated, for the reason `configure.py` gives.
    """
    from . import seal as seal_mod

    aft = seal_mod.from_evaluation(ev)
    internal = seal_mod.internal_bulkhead_from_evaluation(ev)
    load = aft.shock_infinite_mass

    rod, governed = size_ubolt(load)
    u = UBolt(rod, UBOLT_LEG_SPACING, load)
    plate = size_backing_plate(load, u.hole_diameter, UBOLT_LEG_SPACING)

    anchors = [
        AnchorResult("aft gas seal, aft face (main harness fwd)", aft.bulkhead, u, plate,
                     governed, face="aft gas seal / aft", clocking_deg=0.0),
        AnchorResult("internal bulkhead, fwd face (main harness aft)", internal.bulkhead, u,
                     plate, governed, face="internal bulkhead / fwd", clocking_deg=0.0),
        AnchorResult("internal bulkhead, aft face (drogue harness fwd)", internal.bulkhead,
                     u, plate, governed, face="internal bulkhead / aft", clocking_deg=90.0),
    ]
    # The fourth anchor stands on the booster's forward bulkhead, which design/motor_mount.py
    # sizes. Imported rather than rebuilt so the two files cannot disagree about the disc.
    from . import motor_mount as mm
    mount = mm.motor_mount_from_evaluation(ev)
    booster_bulkhead = mount.forward_bulkhead

    # THIS ANCHOR GETS A SHORTER LEG, BECAUSE THE MOTOR IS 11.08 mm BEHIND IT.
    # The standard stack needs 15.20 mm aft of the bulkhead and there is 11.08
    # (`mount.forward_gap`), so the legs ran into the motor. Two changes buy 4.7 mm and
    # neither is a compromise:
    #   * NO SEPARATE WASHER. The washer exists to spread the nut load into the G-10
    #     backing plate, and the plate is nowhere near bearing-limited: 107x with the
    #     washer, 24x with the nut bearing straight on the plate, against a 2.0x
    #     requirement. It was buying 1.6 mm of stack for margin nobody needs.
    #   * AN ALL-METAL NUT, not a nyloc. This nut sits in the sealed gap directly against
    #     the motor's forward closure, and a nylon insert is the wrong part there on
    #     temperature alone -- so the low-profile all-metal nut is the correct choice here
    #     independently of the 2.0 mm it saves.
    # One thread of stand-out instead of two, which is still inspectable. See correction 57.
    u_booster = UBolt(rod, UBOLT_LEG_SPACING, load,
                      leg_standout=leg_standout(
                          booster_bulkhead.thickness, plate.thickness, washer=False,
                          nut_height=UBOLT_NUT_HEIGHT_LOW,
                          thread_standout=UBOLT_THREAD_STANDOUT_MIN))
    anchors.append(
        AnchorResult("booster forward bulkhead (drogue harness aft)", booster_bulkhead,
                     u_booster, plate, governed, face="booster forward bulkhead / fwd",
                     clocking_deg=0.0))

    # The wells go on the FIRED face of each separation bulkhead, over that charge's own
    # lead hole -- so neither well needs a new hole in a pressure boundary.
    # Each well sits ON its own charge's lead hole, so neither needs a new hole through a
    # pressure boundary. The radius and the clocking are the hole's, not a choice made here.
    wells = [
        size_charge_well("main charge", aft.design.charge,
                         aft.feed_through.radius_in_plate, clocking_deg=0.0,
                         face="aft gas seal / aft"),
        size_charge_well("drogue charge", internal.design.charge,
                         internal.feed_through.radius_in_plate, clocking_deg=45.0,
                         face="internal bulkhead / aft"),
    ]

    harness = recovery.size_harness(ev.rocket.length, load)
    return RecoveryHardwareResult(anchors=anchors, wells=wells,
                                  webbing_width=harness.webbing.width,
                                  n_anchors=len(anchors),
                                  booster_forward_gap=mount.forward_gap)


def hole_layout(r: RecoveryHardwareResult, which: int = 0) -> list[Hole]:
    """Every hole one anchored face needs, at the sized U-bolt's diameter.

    Supersedes `seal.hole_layout()`'s U-bolt entries, which are at seal.UBOLT_HOLE_DIAMETER.
    `check_recovery_hardware()` compares the two and fails if they have drifted, the same
    guard `configure.evaluate()` puts on `mass.py`'s harness constant.
    """
    half = UBOLT_LEG_SPACING / 2.0
    d = r.anchor.ubolt.hole_diameter
    return [Hole("U-bolt leg A", 0.0, +half, d), Hole("U-bolt leg B", 0.0, -half, d)]


# Clearance around an opposing leg where its hole reaches under a backing plate. The relief
# is cut as a straight-sided NOTCH in the plate's edge rather than as a hole, because the
# hole's centre is outside the plate: a "hole" there is a notch anyway, and a notch is
# exactly modellable, exactly measurable and easier to cut. See `plate_reliefs()`.
RELIEF_CLEARANCE = 0.0005  # m, added all round the opposing leg's hole


@dataclass(frozen=True)
class Relief:
    """A notch in a backing plate's edge, where an opposing U-bolt's leg passes."""

    face: str
    width: float  # m, across the plate's edge
    depth: float  # m, in from that edge
    at: tuple[float, float]  # m, the opposing leg's centre, in the disc's own frame

    @property
    def volume_for(self) -> float:
        return self.width * self.depth


def plate_reliefs(r: "RecoveryHardwareResult") -> list[Relief]:
    """Every notch every backing plate needs, computed once so the CAD types nothing.

    Only the internal bulkhead produces any: it is the one disc that anchors a harness both
    ways, so it carries a U-bolt on each face, and two U-bolts cannot share two holes.
    """
    out: list[Relief] = []
    for b in r.anchors:                      # b's plate lies on _plate_face(b.face)
        pf = _plate_face(b.face)
        px, py = b.plate_halfspans()
        for c in r.anchors:                  # c's crown stands on pf, so c's legs cross it
            if c.face != pf or c is b:
                continue
            hr = c.ubolt.hole_diameter / 2.0 + RELIEF_CLEARANCE
            for (lx, ly) in c.leg_positions():
                # Which edge does it reach under? The one it is nearest to overrunning.
                over_x, over_y = px - (abs(lx) - hr), py - (abs(ly) - hr)
                if over_x <= 0.0 or over_y <= 0.0:
                    continue
                if over_x < over_y:
                    out.append(Relief(pf, 2.0 * hr, over_x, (lx, ly)))
                else:
                    out.append(Relief(pf, 2.0 * hr, over_y, (lx, ly)))
    return out


def _plate_face(crown_face: str) -> str:
    """The face a crown's backing plate lies on -- the other one."""
    if crown_face.endswith("/ fwd"):
        return crown_face[:-5] + "/ aft"
    if crown_face.endswith("/ aft"):
        return crown_face[:-5] + "/ fwd"
    return crown_face


@dataclass
class RecoveryHardwareCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_recovery_hardware(r: RecoveryHardwareResult) -> RecoveryHardwareCheck:
    from .seal import UBOLT_HOLE_DIAMETER

    v: list[str] = []
    notes: list[str] = []
    mm_ = 1000.0
    u, plate = r.anchor.ubolt, r.anchor.plate

    # --- does each anchor's fastener stack actually fit behind its bulkhead? --------------
    # THE CHECK THAT DID NOT EXIST. The U-bolt is sized here and the space behind the
    # booster's forward bulkhead is computed in `motor_mount.py`, and nothing imported one
    # into the other -- so a 15.20 mm stack sat in an 11.08 mm gap and only the CAD saw it,
    # as 414.19 mm3 of u-bolt inside the motor. Correction 57.
    for a in r.anchors:
        if "booster forward bulkhead" not in a.name:
            continue  # the other three have a whole compartment behind them
        gap = r.booster_forward_gap
        aft_of_bulkhead = a.ubolt.leg_standout - a.bulkhead.thickness
        if aft_of_bulkhead > gap + 1e-9:
            v.append(
                f"{a.name}: the fastener stack needs {aft_of_bulkhead * mm_:.2f} mm aft of "
                f"the bulkhead and the motor leaves {gap * mm_:.2f} mm -- the legs run "
                f"{(aft_of_bulkhead - gap) * mm_:.2f} mm into the motor")
        else:
            notes.append(
                f"{a.name}: stack {aft_of_bulkhead * mm_:.2f} mm aft of the bulkhead into a "
                f"{gap * mm_:.2f} mm gap to the motor, {(gap - aft_of_bulkhead) * mm_:.2f} mm "
                f"spare -- no washer, low-profile all-metal nut (see leg_standout)")

    # --- the U-bolt ----------------------------------------------------------------------
    if u.crown_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"U-bolt crown: M{u.rod_diameter * mm_:.0f} runs {u.crown_stress / 1e6:.0f} MPa "
            f"at {u.load:.0f} N, margin {u.crown_margin:.2f}x")
    else:
        notes.append(
            f"U-bolt M{u.rod_diameter * mm_:.0f} on a {u.leg_spacing * mm_:.0f} mm spacing: "
            f"crown {u.crown_stress / 1e6:.0f} MPa, {u.crown_margin:.2f}x -- governed by "
            f"{r.anchor.governed_by}. THE CROWN, not the legs, which run "
            f"{u.leg_tension / 1e6:.0f} MPa in TENSION at {u.leg_margin:.1f}x")
    if u.crown_margin_straight < PLATE_MARGIN_REQUIRED:
        notes.append(
            f"NOT SOLVED, stated: idealised as a STRAIGHT beam instead of an arch the crown "
            f"runs {u.crown_stress_straight / 1e6:.0f} MPa, {u.crown_margin_straight:.2f}x -- "
            f"under {PLATE_MARGIN_REQUIRED:.1f}x. The arch model is the right one and the "
            f"straight beam is a different structure, not a bound; but this is the single "
            f"most safety-critical joint in the vehicle and a destructive pull test on the "
            f"actual bolt is what settles it. It has not been done")

    if u.rod_diameter > 0.0055 - 0.0005:
        notes.append(
            f"M{u.rod_diameter * mm_:.0f} SUPERSEDES seal.py's assumed M5: the holes already "
            f"placed in both bulkheads go from {UBOLT_HOLE_DIAMETER * mm_:.1f} to "
            f"{u.hole_diameter * mm_:.1f} mm. seal.py's own aside checked the legs in SHEAR, "
            f"and the legs are in tension and are not what breaks")

    if abs(UBOLT_HOLE_DIAMETER - u.hole_diameter) > 1e-9:
        v.append(
            f"seal.UBOLT_HOLE_DIAMETER is {UBOLT_HOLE_DIAMETER * mm_:.1f} mm and this file "
            f"sizes {u.hole_diameter * mm_:.1f} mm -- update seal.py, or every bulkhead CAD "
            f"script drills the wrong hole")

    # --- the harness has to attach to it -------------------------------------------------
    if u.clear_opening < r.webbing_width:
        notes.append(
            f"THE WEBBING DOES NOT PASS THROUGH THE U-BOLT: {r.webbing_width * mm_:.1f} mm of "
            f"3/4\" tubular nylon against a {u.clear_opening * mm_:.1f} mm clear opening. It "
            f"was never meant to -- recovery.HARNESS_HARDWARE_KG has priced links and swivels "
            f"since it was written. REQUIREMENT: the harness attaches through a QUICK LINK, "
            f"and the link goes through the U-bolt. Opening the U up until the webbing passes "
            f"drives it to M10 and ~310 g across four anchors")
    if u.clear_opening < LINK_CLEARANCE:
        v.append(
            f"U-bolt clear opening {u.clear_opening * mm_:.1f} mm will not take a quick link "
            f"({LINK_CLEARANCE * mm_:.0f} mm needed)")
    else:
        notes.append(
            f"clear opening {u.clear_opening * mm_:.1f} mm takes the "
            f"{LINK_CLEARANCE * mm_:.0f} mm quick link with "
            f"{(u.clear_opening - LINK_CLEARANCE) * mm_:.1f} mm to spare")

    # --- the backing plate, which is the point of this file -------------------------------
    if plate.margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"backing plate: {plate.stress / 1e6:.0f} MPa in bending, margin {plate.margin:.1f}x")
    if plate.bearing_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"backing plate: {plate.bearing_stress / 1e6:.0f} MPa bearing under the nut "
            f"washers, margin {plate.bearing_margin:.1f}x")
    notes.append(
        f"backing plate G-10 {plate.length * mm_:.1f} x {plate.width * mm_:.1f} x "
        f"{plate.thickness * mm_:.1f} mm, {plate.mass * 1e3:.1f} g: bending "
        f"{plate.margin:.0f}x, bearing {plate.bearing_margin:.0f}x. Its own bending asks for "
        f"1.2 mm -- what sets it is not dishing under the nuts")

    for a in r.anchors:
        notes.append(
            f"{a.name}: footprint R {a.plate.footprint_radius * mm_:.2f} mm instead of the "
            f"bare 6.00 -- {a.bare_stress / 1e6:.1f} MPa at {a.bare_margin:.2f}x becomes "
            f"{a.backed_stress / 1e6:.1f} MPa at {a.backed_margin:.2f}x")

    # --- the charge wells ----------------------------------------------------------------
    for w in r.wells:
        if not w.fits:
            v.append(
                f"{w.name} well: {w.internal_volume * 1e6:.2f} cm3 against "
                f"{w.required_volume * 1e6:.2f} cm3 needed")
        else:
            notes.append(
                f"{w.name} well dia {w.bore * mm_:.0f} x {w.depth * mm_:.1f} deep at "
                f"R {w.station_radius * mm_:.1f} mm holds {w.charge * 1e3:.4f} g at "
                f"{w.utilisation * 100:.0f}% of its own volume, standing "
                f"{w.depth * mm_:.1f} mm proud")
        if w.depth > WELL_MAX_PROUD:
            v.append(
                f"{w.name} well stands {w.depth * mm_:.1f} mm proud, over the "
                f"{WELL_MAX_PROUD * mm_:.0f} mm ceiling")

    # --- NOTHING ON A FACE MAY COLLIDE -----------------------------------------------------
    # Built as a real per-face occupancy check rather than as one pairwise test, because the
    # internal bulkhead's aft face carries THREE things at once -- its own U-bolt's crown,
    # the opposing U-bolt's backing plate, and the drogue charge well -- and that is the
    # crowded surface in this vehicle. A check written for the aft gas seal's face, which
    # carries one of each, would pass and prove nothing.
    for a in r.anchors:
        pf, pa = _plate_face(a.face), a.face
        occupants: list[tuple[str, float, float, float, float]] = []
        for b in r.anchors:
            if b.face == pa:  # its crown stands on this face
                cx, cy = b.crown_halfspans()
                occupants.append((f"{b.name.split(',')[0]} crown", 0.0, 0.0, cx, cy))
            if _plate_face(b.face) == pa:  # its backing plate lies on this face
                px, py = b.plate_halfspans()
                occupants.append((f"{b.name.split(',')[0]} backing plate", 0.0, 0.0, px, py))
        for w in r.wells:
            if w.face != pa:
                continue
            wx, wy = w.centre
            wr = w.outer_diameter / 2.0
            for (label, ox, oy, hx, hy) in occupants:
                gx = abs(wx - ox) - hx - wr
                gy = abs(wy - oy) - hy - wr
                gap = max(gx, gy)  # clear if it clears in EITHER axis; both are rectangles
                if gap < 0.0:
                    v.append(
                        f"{pa}: the {w.name} well overlaps the {label} by "
                        f"{-gap * mm_:.2f} mm")
                else:
                    notes.append(
                        f"{pa}: {w.name} well clears the {label} by {gap * mm_:.2f} mm")
            edge = a.bulkhead.radius - math.hypot(wx, wy) - wr
            if edge < MIN_LIGAMENT:
                v.append(
                    f"{w.name} well leaves {edge * mm_:.2f} mm to the disc edge, under the "
                    f"{MIN_LIGAMENT * mm_:.1f} mm minimum")

        # Every plate on this face has to pass the legs of every crown that stands on it.
        for b in r.anchors:
            if _plate_face(b.face) != pa:
                continue
            for c in r.anchors:
                if c.face != pa or c is b:
                    continue
                px, py = b.plate_halfspans()
                # The LEG'S OWN HOLE, not its centre. A leg whose centre sits just outside
                # the plate still has 4.25 mm of hole reaching back under it, and a plate
                # laid over half a hole is a plate that does not sit flat.
                hr = c.ubolt.hole_diameter / 2.0
                through = [(lx, ly) for (lx, ly) in c.leg_positions()
                           if abs(lx) - hr <= px and abs(ly) - hr <= py]
                if through:
                    rl = [x for x in plate_reliefs(r) if x.face == pa]
                    notes.append(
                        f"{pa}: the backing plate here is RELIEVED for {len(through)} "
                        f"opposing U-bolt legs at "
                        + ", ".join(f"({lx * mm_:+.1f}, {ly * mm_:+.1f})"
                                    for lx, ly in through)
                        + f" -- {rl[0].width * mm_:.1f} x {rl[0].depth * mm_:.2f} mm notches "
                          f"in its edge, not holes, because the leg centres are OUTSIDE the "
                          f"plate. Two U-bolts on one disc cost this; it is the price of "
                          f"clocking them 90 degrees apart, which is itself the price of two "
                          f"bolts not being able to share two holes")
        plate_edge = a.bulkhead.radius - max(a.plate_halfspans())
        if plate_edge < 0.0:
            v.append(
                f"{pf}: the backing plate is {plate.length * mm_:.1f} mm long and does not "
                f"fit on a {a.bulkhead.bore_diameter * mm_:.1f} mm disc")

    # Every leg of every anchor, against every hole its own disc already carries.
    for a in r.anchors:
        for (lx, ly) in a.leg_positions():
            edge = a.bulkhead.radius - math.hypot(lx, ly) - u.hole_diameter / 2.0
            if edge < MIN_LIGAMENT:
                v.append(f"{a.name}: a leg leaves {edge * mm_:.2f} mm to the disc edge")

    # The conduit radius seal.py carries is set by the plate this file sizes.
    from .seal import INTERNAL_CONDUIT_RADIUS
    wr = r.wells[1].outer_diameter / 2.0
    # On the diagonal a rectangle is cleared by clearing it in EITHER axis, so it is the
    # plate's NARROW half-span that matters, not its long one.
    inner = math.sqrt(2.0) * (min(plate.width, plate.length) / 2.0 + wr + MIN_LIGAMENT)
    outer = r.anchor.bulkhead.radius - wr - MIN_LIGAMENT
    if not (inner <= INTERNAL_CONDUIT_RADIUS <= outer):
        v.append(
            f"seal.INTERNAL_CONDUIT_RADIUS is {INTERNAL_CONDUIT_RADIUS * mm_:.1f} mm and the "
            f"drogue well needs {inner * mm_:.1f}..{outer * mm_:.1f} mm to clear both backing "
            f"plates on the diagonal AND the disc's own edge, each by the "
            f"{MIN_LIGAMENT * mm_:.0f} mm minimum")
    else:
        notes.append(
            f"seal.INTERNAL_CONDUIT_RADIUS {INTERNAL_CONDUIT_RADIUS * mm_:.1f} mm inside the "
            f"{inner * mm_:.1f}..{outer * mm_:.1f} mm the diagonal allows -- that hole's "
            f"radius is set by THIS file's backing plate, not by the stress field, and it is "
            f"the only hole in the vehicle of which that is true")

    # --- what it costs the recovery bay ---------------------------------------------------
    # --- the constants recovery.py carries have to still be the ones sized here -----------
    # Same guard configure.evaluate() puts on mass.py's harness line: recovery.py cannot
    # import this module (it would be circular), so the value lives there and is CHECKED
    # here rather than being a second uncontrolled copy.
    if abs(recovery.UBOLT_ENVELOPE_VOLUME - r.envelope_volume) > 0.05e-6:
        v.append(
            f"recovery.UBOLT_ENVELOPE_VOLUME is {recovery.UBOLT_ENVELOPE_VOLUME * 1e6:.2f} cm3 "
            f"and this file sizes {r.envelope_volume * 1e6:.2f} -- the packing check is "
            f"running on a stale envelope")
    for w in r.wells:
        key = "main" if "main" in w.name else "drogue"
        carried = recovery.WELL_ENVELOPE_VOLUME.get(key)
        if carried is None or abs(carried - w.proud_volume) > 0.05e-6:
            v.append(
                f"recovery.WELL_ENVELOPE_VOLUME[{key!r}] is "
                f"{(carried or 0.0) * 1e6:.2f} cm3 and this file sizes "
                f"{w.proud_volume * 1e6:.2f}")
    notes.append(
        f"one anchor displaces {r.envelope_volume * 1e6:.2f} cm3 of packing against the "
        f"3.00 cm3 recovery.py estimated -- it called that its loosest number and it was low "
        f"by {r.envelope_volume / 3.0e-6:.1f}x, because the U-bolt it described was M5")
    notes.append(
        f"AND THE CHARGE WELLS ARE RIGID TOO: recovery.py's default_soft_goods() said in as "
        f"many words that they 'mount on the bulkhead face and do not consume packing "
        f"volume'. A {r.wells[0].bore * mm_:.0f} mm tube standing {r.wells[0].depth * mm_:.1f} mm "
        f"off the face is directly in the canopy's way; both are priced now")
    notes.append(
        f"{r.n_anchors} anchors + {len(r.wells)} wells + charges = {r.mass * 1e3:.1f} g, of "
        f"which the U-bolts and plates are {r.n_anchors * r.anchor.mass * 1e3:.1f} g. "
        f"design/mass.py has NO line for any of it -- recovery.py's SoftGood(\"2 x U-bolt\", "
        f"0.030) is dead code, overridden by measured_volume and summed by nothing")

    # --- the anchor is self-loading, which nothing else in this project is ---------------
    # Its own mass is now in mass.py, so it raises the descent mass, which raises the opening
    # shock, which is the load it carries. One pass settles it -- the rod size is discrete and
    # M8 survives the round trip -- but the margin is thin enough that the next thing to gain
    # mass anywhere in this vehicle may push it to M10, so the coupling is stated rather than
    # left for someone to rediscover.
    from .mass import DEFAULT_RECOVERY_BUDGET
    carried = DEFAULT_RECOVERY_BUDGET.get("harness_anchors", 0.0)
    sized = r.n_anchors * r.anchor.mass
    if abs(carried - sized) > 0.005:
        v.append(
            f"mass.py carries {carried * 1e3:.0f} g of harness_anchors and this file sizes "
            f"{sized * 1e3:.1f} g -- the mass budget and the part have drifted")
    notes.append(
        f"THE ANCHOR IS SELF-LOADING: its {sized * 1e3:.0f} g is in the recovery budget, so it "
        f"raises the descent mass and therefore the opening shock it carries. One pass settles "
        f"it because the rod size is discrete, and M{u.rod_diameter * mm_:.0f} survives the "
        f"round trip at {u.crown_margin:.2f}x. It is thin: the next thing to gain mass "
        f"anywhere in this vehicle may push it to M10")

    worst = min(u.crown_margin, plate.margin, plate.bearing_margin,
                min(a.backed_margin for a in r.anchors))
    if worst < DATASHEET_CONFIDENCE_MARGIN:
        notes.append(
            f"worst margin here is {worst:.2f}x, under {DATASHEET_CONFIDENCE_MARGIN:.0f}x -- "
            f"and the part it belongs to is bought, so its real allowable is a supplier's "
            f"certificate rather than a table")

    return RecoveryHardwareCheck(ok=not v, violations=v, notes=notes)
