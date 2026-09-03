"""The nav bay sled: the 150 g allowance nobody turned into a part.

THE GAP THIS FILE CLOSES. `design/avionics.py` answers "do the boards fit in the nav bay"
and says they do, by +4.6 mm. It answers it with an AREAL model: it sums every component's
footprint and divides by `2 * sled_width * SLED_PACKING_EFFICIENCY` (`check_packing`). That
is a good model of the thing it was built to see -- that a flat sled in a round tube can
only use the rectangle inscribed in the circle, and that the binding quantity is footprint
rather than volume. It is deliberately not a model of WHERE ANYTHING GOES, and its own
docstring says so.

So the sled has never existed as anything but two numbers: `SLED_WIDTH_FRACTION = 0.80`,
and `design/mass.py`'s `"sled_and_hardware": 0.150`. A length allowance and a mass
allowance, priced into every budget in the vehicle, for a part that has never been drawn.
That is correction 33's shape (the harness), correction 37's (the pass-through plate) and
correction 38's (both access bulkheads), for the fourth time. The tell is the same every
time: the thing is charged for in a budget, so no check ever reports it missing.

WHAT CHANGES WHEN YOU ACTUALLY PLACE THE PARTS. An areal margin is an average, and averages
do not collide. Two things this file finds that the areal model cannot see:

  * THE BATTERY AND THE ALTIMETER CANNOT SIT SIDE BY SIDE. 35.0 + 21.3 = 56.3 mm against a
    56.16 mm sled. They miss by 0.14 mm. The STM32 board, at 45 mm wide, fits beside
    nothing at all.
  * THE WIRING IS WHAT BINDS, NOT THE BOARDS -- and 0.80 OF THE BORE IS THE WRONG WIDTH.
    `avionics.WIRING_FOOTPRINT` charges the 80 g loom 70 x 20 mm of SLED FACE. The four
    boards place on a 56.16 mm plate with 1 mm of clearance and room left over. Add the
    loom as a rectangle and there is no placement at all -- until the plate reaches
    59.00 mm, at which point there is. `SLED_WIDTH_FRACTION = 0.80` is 2.84 mm too narrow
    to carry the thing the same file charges for, and nothing could see that, because an
    areal model cannot tell a plate that is 2.84 mm too narrow from one that is wide
    enough. It only ever sees the product.

SO WIDTH IS THE FIX, AND THIS FILE TAKES IT. The plate here is not 0.80 of the bore. It is
as wide as the rods allow -- `max_plate_width()` -- which is 59.20 mm for M4, or 0.843 of
the bore. That is a DESIGN CHANGE and it is stated rather than absorbed: 0.80 was a working
figure with no argument behind it, and there is now an argument for a different one. It is
also a 0.20 mm margin, which is not comfortable, and the table in `scripts/sled_report.py`
is the honest picture of how little room there is:

    clearance    plate width the loom needs    widest plate the rods allow
      0.5 mm                57.00 mm            59.20 (M4) / 61.20 (M3)
      1.0 mm                59.00 mm            59.20 (M4)  <- 0.20 mm in hand
      1.5 mm                61.00 mm            61.20 (M3)  <- 0.20 mm in hand
      2.0 mm                  no width in the bore works at all

READ THAT BEFORE ACTING ON IT, because the loom rectangle has two readings and this file
cannot distinguish them. Either the loom really is 70 x 20 x 12 of solid keep-out -- or the
80 g is a whole-avionics wiring allowance that `avionics.py` charges, in its entirety, to
nav bay sled face area, which would be the wrong place for most of it: `design/mass.py`
calls the line `wiring_connectors`, connectors are not loom, and the servo and pyro leads
both run AFT out of this bay rather than staying in it. Under the second reading the whole
squeeze dissolves. NOTHING HERE RESIZES THE BAY and nothing here edits `avionics.py` to
make a number come out. Correction 5 is the precedent and it is exact: the recovery bay was
declared 11 mm short on a figure built from multiplied estimates, the airframe was
lengthened for it, and the shortfall turned out not to exist. What settles this is weighing
the loom and counting the conductors.

WHAT HOLDS THE SLED. Two M4 threaded rods between the two end plates, OUTBOARD of the
plate rather than through it -- in the corner crescents the sled cannot use anyway. That
was checked before it was chosen:

    rod   widest plate that still clears the 70.20 shoulder bore
    M3          61.20 mm
    M4          59.20 mm     <- selected
    M5          57.20 mm

Rods THROUGH the plate need the boss under 5 mm a side for the 45 mm STM32 board to
survive, which no rod above M3 gives. Outboard rods cost nothing, leave `avionics.py`'s
56.16 mm plate width intact, and keep the sled simply supported -- so neither G-10 end
plate picks up a bending case, which matters because `design/access_bulkhead.py` sized
both of them against a point load and never against a moment.

WHAT THIS FILE DOES NOT DO. It does not model the sled's stiffness, and it should not be
read as claiming the plate is stiff enough -- a 1.6 mm G-10 plate spanning 115 mm with
400 g on it is a deflection question this project has no vibration model to answer. It does
not place the static ports; they still have no station and no clocking anywhere in this
repo (`design/venting.py` flags that itself). And it does not model connector overhang or
cable bend radius, which is the next thing that will bite: an envelope is a rectangle and a
plugged connector is not.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from . import avionics
from .seal import Hole

G10_DENSITY = 1850.0  # kg/m^3, the one material fact this project has committed to

# --- the sled plate --------------------------------------------------------------------
# 1.6 mm G-10 sheet. A stocked gauge, and the same material family as both end plates so
# the bay is one coefficient of thermal expansion. This is a PRODUCIBILITY floor in exactly
# the sense design/access_bulkhead.py uses the phrase -- it is set by what holds a threaded
# insert and survives handling, not by a stress model, because there is no vibration model
# here to size it against.
PLATE_THICKNESS = 1.6e-3  # m

# Clearance demanded around every component, on every side, in the discrete placement.
# This is the number the whole finding turns on, so it is a named constant and not a
# literal: it buys standoff shoulders, connector shells, a screwdriver, and the fact that a
# board outline is not its keep-out. 1.0 mm is already tight for hand assembly.
PLACEMENT_CLEARANCE = 1.0e-3  # m

# --- the rods --------------------------------------------------------------------------
ROD_DIAMETER = 4.0e-3         # m, M4 stainless threaded rod
ROD_COUNT = 2
ROD_DENSITY = 7900.0          # kg/m^3, 304 stainless

# THE RODS ARE CLOCKED PERPENDICULAR TO THE PLATE -- at (0, +/-ROD_RADIUS), above and below
# it, not out at its edges. That is the single decision this mount turns on, and the first
# attempt got it wrong in a way worth recording.
#
# Putting the rods beside the plate, in the plate's own plane, looks natural and is what a
# side-view sketch suggests. It does not work, for a reason that only shows up in three
# dimensions: a nut on a rod running along Z clamps in Z, and a plate lying in the XZ plane
# presents nothing but its 1.6 mm EDGE to that direction. There is no face for a washer to
# bear on. Widening the plate into "ears" around the rod does not help either -- the rod
# runs the full length of the bay, so clearing it means removing every scrap of ear material
# at that radius, for all Z. The ear then captures nothing. The Fusion model said so
# plainly: 47.31 mm^3 of the plate lay inside each rod.
#
# So the capture has to be PERPENDICULAR to the rod -- a small end bracket in the XY plane,
# which is a bulkhead in miniature and is what a real avionics bay has always used. And once
# the capture is a perpendicular bracket, the rod is free to move off the plate's plane,
# which buys two things at once:
#
#   * THE ROD STOPS CONSTRAINING THE PLATE WIDTH. Beside the plate, every millimetre of rod
#     is a millimetre the plate cannot have. Above it, they do not compete at all: the rod
#     sits at Y 28.0-32.0 and the tallest component reaches Y 16.50.
#   * THE ROD CAN COME INBOARD, so its hole is a real hole. At R 32.60 a 4.5 mm hole leaves
#     -0.05 mm of ligament to the bracket edge, which is not a part. At R 30.00 it leaves
#     2.55 mm. It also takes the hole in each END PLATE from 2.55 mm of edge ligament to
#     5.15 mm, which matters more: those two plates are pressure boundaries.
ROD_RADIUS = 30.0e-3          # m, rod centre from the vehicle axis
ROD_HOLE_CLEARANCE = 0.5e-3   # m on the diameter -- a 4.5 mm hole for an M4 rod
ROD_MIN_LIGAMENT = 2.0e-3     # m, hole edge to the bracket edge

# --- the end brackets --------------------------------------------------------------------
# One at each end of the plate: a flat plate in the XY plane that the rods pass through and
# the sled plate butts into. Bounded by the bore and by a half-width, so it is a vertical
# band rather than a disc -- a disc would close the bay off and there is no reason to.
BRACKET_THICKNESS = 3.0e-3    # m, G-10
BRACKET_HALF_WIDTH = 18.0e-3  # m, in X
BRACKET_BORE_CLEARANCE = 0.3e-3  # m, bracket edge to the shoulder bore

# --- hardware ----------------------------------------------------------------------------
# Standoffs lift each PCB off the plate so the solder side and its through-hole legs clear
# it. 3 mm nylon is the common stocked size and it is the smallest that clears a clinched
# through-hole lead. This is NOT free height: it stacks on top of the component envelope,
# and the envelopes in `avionics.py` already include connectors, so a board's real demand
# on the half-height is `height + STANDOFF_HEIGHT`.
STANDOFF_HEIGHT = 3.0e-3      # m

# Which components sit flat on the plate rather than on standoffs. A LiPo pack is strapped
# or taped down and a loom is cable-tied; neither has a solder side to clear. Named
# explicitly because getting this wrong silently adds 3 mm to the tallest item in the bay,
# and the half-height here is tight enough to care.
STRAPPED_DIRECTLY = frozenset({"battery, 2S 1500 mAh", "wiring loom"})


def stack_height(c: avionics.Component) -> float:
    """How much half-height one component actually demands, m -- envelope plus standoff."""
    return c.height + (0.0 if c.name in STRAPPED_DIRECTLY else STANDOFF_HEIGHT)


# Nuts, washers, standoffs, screws, as one line. A guess of the same character as
# SLED_PACKING_EFFICIENCY and flagged the same way.
HARDWARE_MASS = 0.030         # kg

# Headroom kept between the tallest component stack and the inscribed rectangle's edge. This
# is what now SETS THE PLATE WIDTH, and it is the honest constraint: a wider plate sits on a
# longer chord, so width is bought with height, and the tallest part is what pays.
HALF_HEIGHT_MARGIN = 3.0e-3   # m

# A cable-tie slot needs its own width plus a ligament each side -- call it 3.0 mm of clear
# plate outboard of the item it straps. THERE IS NOT THAT MUCH ROOM, and `check_sled()`
# reports the actual gaps rather than drawing slots that do not fit. See the notes it emits:
# battery retention has to come from adhesive, foam, or a strap anchored to the board
# standoffs, and that is an open item rather than a solved one.
TIE_SLOT_CLEAR_NEEDED = 3.0e-3  # m

# Board mounting. Each PCB sits on four standoffs at its corners, inset from the outline.
STANDOFF_OD = 6.0e-3          # m
STANDOFF_DENSITY = 1150.0     # kg/m^3, nylon
MOUNT_HOLE_DIAMETER = 2.5e-3  # m, clearance for M2.5
BOARD_MOUNT_INSET = 3.5e-3    # m, hole centre in from each edge of the board outline

# Two mounting holes closer than this are not two holes -- they are one ragged slot with no
# material between them, and neither screw has anything to pull against. Boards on OPPOSITE
# faces legitimately share a screw (a standoff on each side of the plate), so the rule here
# is to MERGE a cluster rather than to reject it. This is not a hypothetical: the BEC's
# forward-inboard screw landed exactly on the StratoLoggerCF's, and their aft pair landed
# 1.30 mm apart. Nothing found that until the CAD volume came back 10.7519 mm3 heavy and the
# two overlaps accounted for it to the last hundredth -- which is the entire argument for
# checking volume against an analytic figure instead of eyeballing the model.
MIN_MOUNT_HOLE_PITCH = 5.0e-3  # m, centre to centre

# The wiring, as `avionics.py` charges it. NOT part of `avionics.NAV_BAY_STACK` -- that
# file carries it as `WIRING_FOOTPRINT`, a bare 70 x 20 mm of area added to the footprint
# sum, because an areal model has no way to say "along one edge" other than by charging the
# area. Expressed here as a Component so the placement can be asked the question the areal
# model could not: is there actually a 70 x 20 rectangle left. The height is the loom's own
# bundle diameter and is a guess.
LOOM = avionics.Component(
    "wiring loom", 0.080, 0.070, 0.020, 0.012,
    note="avionics.WIRING_FOOTPRINT as a rectangle -- see this module's header")

# What design/mass.py has been charging for this part since before it existed.
SLED_MASS_BUDGET = 0.150      # kg, mass.DEFAULT_AVIONICS_BUDGET["sled_and_hardware"]


@dataclass(frozen=True)
class Placement:
    """Where one component ends up. `face` is 0 or 1; x runs along the rocket axis."""

    name: str
    face: int
    x: float       # m, from the sled's forward end
    y: float       # m, across the sled, from one edge
    length: float  # m, as placed -- swapped with width if `rotated`
    width: float
    height: float
    rotated: bool


@dataclass
class SledGeometry:
    """Everything the report, `baseline.py` and the CAD script need, computed once."""

    plate_length: float          # m
    plate_width: float           # m
    plate_thickness: float
    bore: float                  # m, the diameter the sled must pass -- the shoulder
    usable_height: float         # m, the inscribed rectangle's height
    rod_diameter: float
    rod_radius: float            # m, rod centre from the vehicle axis, clocked at +/-Y
    rod_length: float
    bracket_thickness: float     # m, one end bracket, taken off the component band twice
    bracket_radius: float        # m, how far a bracket reaches from the axis
    clearance: float             # m, used in the placement
    components: list[avionics.Component]
    placements: list[Placement] = field(default_factory=list)
    blocked: str = ""            # non-empty when no placement exists

    @property
    def placed(self) -> bool:
        return not self.blocked

    @property
    def component_length(self) -> float:
        """Length available to components -- the whole plate.

        The plate does NOT run through the brackets: it butts their inner faces and is
        bonded there. It cannot run through them, and that is worth writing down because a
        through-slot is the obvious G-10 joint and it is wrong here. The plate is 59.41 mm
        wide and the bracket is only 36.0 mm wide, so a slot for it would run the bracket's
        full width at |Y| < 0.8 and cut the bracket cleanly into two unconnected halves.
        """
        return self.plate_length

    @property
    def assembly_length(self) -> float:
        """Plate plus both end brackets -- what has to fit the bay's usable length."""
        return self.plate_length + 2.0 * self.bracket_thickness

    @property
    def bond_area(self) -> float:
        """One plate-to-bracket bonded butt joint, m^2 -- the plate's end edge."""
        return self.plate_width * self.plate_thickness

    @property
    def rod_hole_diameter(self) -> float:
        return self.rod_diameter + ROD_HOLE_CLEARANCE

    @property
    def rod_ligament(self) -> float:
        """Bracket material outboard of a rod hole -- the mount's tightest dimension."""
        return self.bracket_radius - (self.rod_radius + self.rod_hole_diameter / 2.0)

    @property
    def bracket_area(self) -> float:
        """One bracket's face area, m^2: inside `bracket_radius`, cropped to +/-half-width,
        less its two rod holes."""
        r, h = self.bracket_radius, min(BRACKET_HALF_WIDTH, self.bracket_radius)
        # area of the circle cropped by two vertical chords at x = +/-h
        seg = r * r * math.acos(h / r) - h * math.sqrt(max(r * r - h * h, 0.0))
        area = math.pi * r * r - 2.0 * seg
        area -= ROD_COUNT * math.pi * (self.rod_hole_diameter / 2.0) ** 2
        return area

    @property
    def bracket_mass(self) -> float:
        return ROD_COUNT * self.bracket_area * self.bracket_thickness * G10_DENSITY

    @property
    def plate_volume(self) -> float:
        """Plate + the two end ears, less the slots and the board mounting holes.

        A plain rectangle now: the rods pass through the two end BRACKETS, not through the
        plate, so the plate carries nothing but its board mounting holes. That is the whole
        benefit of clocking the rods perpendicular to it -- see ROD_RADIUS.
        """
        t = self.plate_thickness
        v = self.plate_length * self.plate_width * t
        v -= len(self.mount_holes) * math.pi * (MOUNT_HOLE_DIAMETER / 2.0) ** 2 * t
        return v

    @property
    def plate_mass(self) -> float:
        return self.plate_volume * G10_DENSITY

    @property
    def rod_mass(self) -> float:
        return (ROD_COUNT * math.pi * (self.rod_diameter / 2.0) ** 2
                * self.rod_length * ROD_DENSITY)

    @property
    def standoff_mass(self) -> float:
        n = sum(len(f) for (_x, _y, f, _o) in self.mount_sites())
        return (n * math.pi * (STANDOFF_OD / 2.0) ** 2
                * STANDOFF_HEIGHT * STANDOFF_DENSITY)

    def _raw_mount_sites(self) -> list[tuple[float, float, int, str]]:
        """Four screw positions under every component that sits on standoffs, unmerged.

        Positions are in the PLATE's frame: x from the plate's forward end, y across it.
        """
        out = []
        for p in self.placements:
            if p.name in STRAPPED_DIRECTLY:
                continue
            for dx in (BOARD_MOUNT_INSET, p.length - BOARD_MOUNT_INSET):
                for dy in (BOARD_MOUNT_INSET, p.width - BOARD_MOUNT_INSET):
                    out.append((p.x + dx, p.y + dy, p.face, p.name))
        return out

    def mount_sites(self) -> list[tuple[float, float, tuple[int, ...], tuple[str, ...]]]:
        """Screw positions after merging anything closer than MIN_MOUNT_HOLE_PITCH.

        Returns `(x, y, faces, owners)`. A site with two faces is one screw carrying a
        standoff on each side of the plate -- which is a real and tidy way to mount two
        boards, and is what the collision between the BEC and the altimeter turns into.
        """
        raw = self._raw_mount_sites()
        parent = list(range(len(raw)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in range(len(raw)):
            for j in range(i + 1, len(raw)):
                if math.hypot(raw[i][0] - raw[j][0],
                              raw[i][1] - raw[j][1]) < MIN_MOUNT_HOLE_PITCH:
                    parent[find(i)] = find(j)

        groups: dict[int, list[int]] = {}
        for i in range(len(raw)):
            groups.setdefault(find(i), []).append(i)

        out = []
        for members in groups.values():
            xs = [raw[i][0] for i in members]
            ys = [raw[i][1] for i in members]
            out.append((sum(xs) / len(xs), sum(ys) / len(ys),
                        tuple(sorted({raw[i][2] for i in members})),
                        tuple(sorted({raw[i][3] for i in members}))))
        return sorted(out)

    @property
    def mount_holes(self) -> list[Hole]:
        """The merged mounting holes, as `seal.Hole`, for the CAD to cut."""
        return [Hole("/".join(o) + " mount", x, y, MOUNT_HOLE_DIAMETER)
                for (x, y, _f, o) in self.mount_sites()]

    def retention_gaps(self) -> list[tuple[str, float]]:
        """Clear plate outboard of each strapped item, m -- the room a tie slot would need.

        A LiPo pack and a loom are held by something, and on this sled that something cannot
        be a cable tie through the plate: the placement leaves less than
        TIE_SLOT_CLEAR_NEEDED beside them. Reported rather than drawn.
        """
        out = []
        for p in self.placements:
            if p.name not in STRAPPED_DIRECTLY:
                continue
            others = [q for q in self.placements if q.face == p.face and q is not p]
            below = max([q.y + q.width for q in others if q.y + q.width <= p.y] + [0.0])
            above = min([q.y for q in others if q.y >= p.y + p.width]
                        + [self.plate_width])
            out.append((p.name, min(p.y - below, above - (p.y + p.width))))
        return out

    def screws_under_opposite(self) -> list[str]:
        """Board mounting holes whose screw head lands under a component on the other face.

        Those screws have to be countersunk flush or the part above them needs relief. It is
        not a violation, but it is the sort of thing that is free to notice now and a filed
        screw head later.
        """
        out = []
        for (x, y, faces, owners) in self.mount_sites():
            for q in self.placements:
                if q.face in faces or q.name in owners:
                    continue
                if (q.x <= x <= q.x + q.length
                        and q.y <= y <= q.y + q.width):
                    out.append(f"{'/'.join(owners)} screw lands under {q.name}")
                    break
        return out

    @property
    def mass(self) -> float:
        """Plate + both end brackets + rods + standoffs + hardware -- the 150 g line."""
        return (self.plate_mass + self.bracket_mass + self.rod_mass
                + self.standoff_mass + HARDWARE_MASS)

    @property
    def envelope_width(self) -> float:
        """Widest point of the whole assembly -- rods AND the end ears, which reach past
        them. What actually has to pass the shoulder bore."""
        return 2.0 * self.max_radius

    @property
    def max_radius(self) -> float:
        """Radius of the whole assembly's widest point -- what must pass the shoulder."""
        return max(math.hypot(self.plate_width / 2.0, self.plate_thickness / 2.0),
                   self.rod_radius + self.rod_diameter / 2.0,
                   self.bracket_radius)

    @property
    def crescent_area(self) -> float:
        """Free area, m^2, in the two circular segments outboard of the plate.

        This is where a wiring loom would have to live if it does not live on a face, and it
        is the quantity the second finding in the header turns on. The rods are NOT
        subtracted: clocking them above and below the plate handed these two crescents back
        whole, which is a real gain and still not enough to hold 80 g of loom.
        """
        r = self.bore / 2.0
        half = self.plate_width / 2.0
        if half >= r:
            return 0.0
        seg = r * r * math.acos(half / r) - half * math.sqrt(max(r * r - half * half, 0.0))
        return max(2.0 * seg, 0.0)

    @property
    def crescent_volume(self) -> float:
        return self.crescent_area * self.plate_length


def max_plate_width(bore: float, tallest_stack: float,
                    margin: float = HALF_HEIGHT_MARGIN) -> float:
    """Widest plate that still leaves `margin` of headroom over `tallest_stack`.

    THE RODS NO LONGER SET THIS. They used to -- when they lay beside the plate, every
    millimetre of rod was a millimetre the plate could not have. Clocked above and below it
    they do not compete, and what is left is the real constraint, which was always there
    underneath: a wider plate sits on a longer chord, so the inscribed rectangle gets
    shorter, and the tallest component on the sled is what pays for the width.
    """
    r = bore / 2.0
    half = tallest_stack + margin
    return 2.0 * math.sqrt(max(r * r - half * half, 0.0))


# ---------------------------------------------------------------------------------------
# The discrete placement. This is what replaces the areal check -- not because the areal
# check is wrong, but because it answers a different question.
# ---------------------------------------------------------------------------------------

def _fits_face(rects: list[tuple[str, float, float]], face_l: float, face_w: float,
               eps: float = 1e-9):
    """Exact orthogonal packing of pre-oriented rectangles onto one face.

    Backtracking over CORNER POINTS, which loses no solutions: in any feasible packing
    every rectangle can be slid down and left until it touches something, so a packing
    exists iff one exists with every rectangle at a corner point. That is what makes a
    "no" from this function mean NO PACKING EXISTS rather than "the heuristic gave up",
    which is the only reason it is worth reporting a negative result at all.
    """
    placed: list[tuple[float, float, float, float, str]] = []

    def corners() -> list[tuple[float, float]]:
        xs = {0.0} | {p[0] + p[2] for p in placed}
        ys = {0.0} | {p[1] + p[3] for p in placed}
        return sorted((x, y) for x in xs for y in ys
                      if x <= face_l + eps and y <= face_w + eps)

    def clashes(x: float, y: float, l: float, w: float) -> bool:
        return any(x < px + pl - eps and px < x + l - eps
                   and y < py + pw - eps and py < y + w - eps
                   for (px, py, pl, pw, _) in placed)

    def step(i: int) -> bool:
        if i == len(rects):
            return True
        name, l, w = rects[i]
        for (x, y) in corners():
            if x + l > face_l + eps or y + w > face_w + eps or clashes(x, y, l, w):
                continue
            placed.append((x, y, l, w, name))
            if step(i + 1):
                return True
            placed.pop()
        return False

    return list(placed) if step(0) else None


def place_components(components: list[avionics.Component], plate_length: float,
                     plate_width: float, clearance: float,
                     ) -> tuple[list[Placement], str]:
    """Place every component on the sled's two faces, or say what blocks it.

    Returns `(placements, "")` on success and `([], reason)` on failure. Each component is
    grown by `clearance` on all four sides before packing, so the returned x/y are the
    keep-out's corner and the part itself sits `clearance` inside it.

    Exhaustive over face assignment and 0/90 orientation, and exact within a face, so the
    failure case is a real proof of infeasibility and not a search that ran out of ideas.
    """
    n = len(components)
    if n == 0:
        return [], ""
    for assign in itertools.product((0, 1), repeat=n):
        for rot in itertools.product((0, 1), repeat=n):
            faces: dict[int, list[tuple[str, float, float]]] = {0: [], 1: []}
            for i, c in enumerate(components):
                l, w = (c.width, c.length) if rot[i] else (c.length, c.width)
                faces[assign[i]].append((c.name, l + 2 * clearance, w + 2 * clearance))
            out: dict[int, list] = {}
            for f in (0, 1):
                got = _fits_face(faces[f], plate_length, plate_width)
                if got is None:
                    break
                out[f] = got
            else:
                placements = []
                by_name = {c.name: c for c in components}
                for f in (0, 1):
                    for (x, y, l, w, name) in out[f]:
                        c = by_name[name]
                        i = components.index(c)
                        placements.append(Placement(
                            name=name, face=f, x=x + clearance, y=y + clearance,
                            length=l - 2 * clearance, width=w - 2 * clearance,
                            height=c.height, rotated=bool(rot[i])))
                return placements, ""
    return [], _blocker(components, plate_length, plate_width, clearance)


def _blocker(components: list[avionics.Component], plate_length: float,
             plate_width: float, clearance: float) -> str:
    """Name what makes the placement infeasible, rather than only that it is.

    A bare "does not fit" is the kind of result that gets worked around instead of
    understood, so this drops one component at a time and reports EVERY component whose
    removal rescues the set. Reporting only the first would name a blocker that is really
    just the head of the iteration order, and would point the fix at the wrong part.
    """
    rescuers = []
    for c in components:
        rest = [x for x in components if x is not c]
        got, _ = place_components(rest, plate_length, plate_width, clearance)
        if got:
            rescuers.append(c.name)
    if rescuers:
        return (f"the set is infeasible on both faces at {clearance * 1000:.1f} mm "
                f"clearance; removing any ONE of [{', '.join(rescuers)}] makes the rest "
                f"place, so no single part is uniquely at fault -- it is the total")
    over = [c.name for c in components
            if min(c.length, c.width) + 2 * clearance > plate_width]
    if over:
        return (f"{', '.join(over)} is wider than the {plate_width * 1000:.2f} mm plate "
                f"even rotated, with {clearance * 1000:.1f} mm clearance")
    return (f"no placement of {len(components)} components exists on two "
            f"{plate_length * 1000:.2f} x {plate_width * 1000:.2f} mm faces at "
            f"{clearance * 1000:.1f} mm clearance; no single component explains it")


def sled_from_evaluation(ev, clearance: float = PLACEMENT_CLEARANCE,
                         components: list[avionics.Component] | None = None,
                         plate_width: float | None = None) -> SledGeometry:
    """The sled, from the vehicle's own budgets -- no dimension typed.

    `plate_width` defaults to AS WIDE AS THE RODS ALLOW, not to
    `avionics.SLED_WIDTH_FRACTION` of the bore. See this module's header: 0.80 is 2.84 mm
    too narrow to place the loom, and once the rods sit outboard the extra width is free.
    Pass `avionics.SLED_WIDTH_FRACTION * bore` to get the old figure back -- the report
    sweeps both, because "would a wider plate fix this" is the first question the finding
    provokes and it deserves an answer rather than an opinion.
    """
    from . import joints
    budget = joints.budgets(ev.rocket, ev.params.wall_thickness)["nav bay"]
    bore = budget.min_bore
    # The loom is in the default set. It is what the sled carries, `avionics.py` charges
    # for it, and leaving it out is how it stayed invisible -- the boards were never the
    # question. Pass `avionics.NAV_BAY_STACK` alone to see the boards-only answer.
    comps = (list(components) if components is not None
             else list(avionics.NAV_BAY_STACK) + [LOOM])
    tallest = max((stack_height(c) for c in comps), default=0.0)
    width = (plate_width if plate_width is not None
             else max_plate_width(bore, tallest))

    r = bore / 2.0
    bracket_r = r - BRACKET_BORE_CLEARANCE

    # THE ROD SPANS THE WHOLE BAY, not the sled. It is anchored in the pass-through plate at
    # the aft end and takes a nut against the nose plate at the forward end, so it runs the
    # full tube length -- 127.04 mm, not the 115.04 mm of sled. Getting this wrong is what
    # the part was first built with, and it left the rods 12 mm short of anything to hold
    # them: a "simply supported" sled supported at one end by nothing.
    rod_len = budget.tube_length

    # The two end brackets cost length: the PLATE is the usable length less both of them.
    plate_len = budget.usable_length - 2.0 * BRACKET_THICKNESS
    placements, blocked = place_components(comps, plate_len, width, clearance)

    half = width / 2.0
    usable = 2.0 * math.sqrt(max(r * r - half * half, 0.0))

    return SledGeometry(
        plate_length=plate_len,
        plate_width=width,
        plate_thickness=PLATE_THICKNESS,
        bore=bore,
        usable_height=usable,
        rod_diameter=ROD_DIAMETER,
        rod_radius=ROD_RADIUS,
        rod_length=rod_len,
        bracket_thickness=BRACKET_THICKNESS,
        bracket_radius=bracket_r,
        clearance=clearance,
        components=comps,
        placements=placements,
        blocked=blocked,
    )


def station_range(rocket, g: SledGeometry) -> tuple[float, float]:
    """Where the sled ASSEMBLY sits in vehicle stations, m from the nose tip.

    The aft limit is the nav bay's aft end less `joints.BULKHEAD_ALLOWANCE` -- the 12 mm the
    pass-through plate is charged, even though the plate itself sits 2.4 mm INTO the canard
    module -- and the forward end is that less `assembly_length`, which is plate plus both
    brackets and not the plate alone.

    LIVES HERE because it now has two callers. `scripts/make_sled_fusion.py` derived it and
    `design/ports.py` needs the identical frame to ask whether a static port's inner mouth is
    blocked by anything on the sled; two derivations of the same conversion is exactly the
    drift `design/configure.py`'s docstring warns about, and reading it 12 mm the wrong way
    would put the sled straight through the plate.
    """
    from . import joints as joints_mod

    nav = next(t for t in rocket.tubes if t.name == "nav bay")
    aft = rocket.nose.length + nav.length - joints_mod.BULKHEAD_ALLOWANCE
    return aft - g.assembly_length, aft


def solids_at(g: SledGeometry, station_forward: float, x: float
              ) -> list[tuple[str, str, tuple]]:
    """Everything the sled puts in the tube's cross-section at vehicle station `x`.

    Returned as ("name", kind, params) with kind "rect" -- (x0, x1, y0, y1) in the sled's own
    (X across the plate, Y normal to it) frame -- or "disc" -- (cx, cy, r). It exists so that
    `design/ports.py` can ask the one question no check in this project had ever asked of a
    hole: **can air actually get to it from the inside.** An unmodelled part cannot collide
    with anything, and neither can it block anything.
    """
    out: list[tuple[str, str, tuple]] = []
    half_w = g.plate_width / 2.0
    half_t = g.plate_thickness / 2.0
    sx = x - station_forward  # from the forward face of the forward bracket

    # brackets, one at each end of the assembly
    for label, z0 in (("fwd", 0.0), ("aft", g.assembly_length - g.bracket_thickness)):
        if z0 <= sx <= z0 + g.bracket_thickness:
            out.append((f"end bracket {label}", "rect",
                        (-BRACKET_HALF_WIDTH, BRACKET_HALF_WIDTH,
                         -g.bracket_radius, g.bracket_radius)))

    if g.bracket_thickness <= sx <= g.bracket_thickness + g.plate_length:
        out.append(("sled plate", "rect", (-half_w, half_w, -half_t, half_t)))

    for sign in (1.0, -1.0):
        out.append((f"rod {'+' if sign > 0 else '-'}Y", "disc",
                    (0.0, sign * g.rod_radius, g.rod_diameter / 2.0)))

    for pl in g.placements:
        z0 = g.bracket_thickness + pl.x
        if not (z0 <= sx <= z0 + pl.length):
            continue
        comp = next(c for c in g.components if c.name == pl.name)
        standoff = 0.0 if comp.name in STRAPPED_DIRECTLY else STANDOFF_HEIGHT
        sign = 1.0 if pl.face == 0 else -1.0
        y0 = sign * (half_t + standoff)
        y1 = sign * (half_t + standoff + pl.height)
        out.append((pl.name, "rect",
                    (-half_w + pl.y, -half_w + pl.y + pl.width, min(y0, y1), max(y0, y1))))
    return out


def hole_layout(g: SledGeometry) -> list[Hole]:
    """Everything cut out of the PLATE -- reuses `seal.Hole`, as `design/access_bulkhead.py`
    does, so a CAD script can build it off one shape.

    The rod holes are not here: they are in the two end BRACKETS, which lie in a different
    plane. `bracket_holes()` has those.
    """
    return g.mount_holes


def bracket_holes(g: SledGeometry) -> list[Hole]:
    """The two rod holes in one end bracket, in the bracket's own XY plane."""
    return [Hole(f"rod hole {'+Y' if sgn > 0 else '-Y'}", 0.0, sgn * g.rod_radius,
                 g.rod_hole_diameter) for sgn in (1.0, -1.0)]


@dataclass
class SledCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_sled(g: SledGeometry) -> SledCheck:
    """Everything that has to be true for this sled to be buildable.

    Written as a check for the reason `design/seal.py` gives for its own: prose has carried
    "never sized" in this project before and nothing ever acted on it.
    """
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    if g.blocked:
        v.append(f"no discrete placement at {g.clearance * mm:.1f} mm clearance -- {g.blocked}")
    else:
        notes.append(f"all {len(g.components)} components place on two faces at "
                     f"{g.clearance * mm:.1f} mm clearance")

    half = g.usable_height / 2.0
    tall = [c for c in g.components if stack_height(c) > half]
    if tall:
        v.append(", ".join(
            f"{c.name} stands {stack_height(c) * mm:.2f} mm on its standoffs"
            for c in tall) + f" against a {half * mm:.2f} mm half-height")
    else:
        worst = max(g.components, key=stack_height)
        notes.append(f"tallest is {worst.name} at {stack_height(worst) * mm:.2f} mm "
                     f"against {half * mm:.2f} mm of half-height -- "
                     f"{(half - stack_height(worst)) * mm:.2f} mm clear")

    if g.envelope_width > g.bore:
        v.append(f"the assembly is {g.envelope_width * mm:.2f} mm across the rods and will "
                 f"not pass the {g.bore * mm:.2f} mm shoulder bore")
    else:
        notes.append(f"passes the shoulder bore: R {g.max_radius * mm:.2f} mm at its "
                     f"widest against R {g.bore / 2.0 * mm:.2f} mm, "
                     f"{(g.bore / 2.0 - g.max_radius) * mm:.2f} mm to spare")

    # --- the mount ----------------------------------------------------------------------
    if g.rod_ligament < ROD_MIN_LIGAMENT:
        v.append(f"a rod hole at R {g.rod_radius * mm:.2f} mm leaves "
                 f"{g.rod_ligament * mm:.2f} mm of bracket outboard of it, under the "
                 f"{ROD_MIN_LIGAMENT * mm:.1f} mm minimum")
    else:
        notes.append(f"rod holes at R {g.rod_radius * mm:.2f} mm leave "
                     f"{g.rod_ligament * mm:.2f} mm of bracket ligament")

    # The brackets carry the sled's inertia in bearing on the rods. Four holes share it.
    bearing = g.rod_hole_diameter * g.bracket_thickness * 370.0e6   # G10_BEARING
    load = (g.mass + sum(c.mass for c in g.components)) * 9.81 * 8.3 / 4.0
    if bearing < 4.0 * load:
        v.append(f"rod hole bearing {bearing:.0f} N against {load:.1f} N a hole, under 4x")
    else:
        notes.append(f"rod hole bearing {bearing:.0f} N against {load:.1f} N a hole, "
                     f"{bearing / load:.0f}x")

    if g.bracket_radius > g.bore / 2.0 - 1e-9:
        v.append(f"the end brackets reach R {g.bracket_radius * mm:.2f} mm against a "
                 f"{g.bore / 2.0 * mm:.2f} mm bore radius")

    # A rod above the plate must clear the tallest thing standing on it.
    tallest = max((stack_height(c) for c in g.components), default=0.0)
    gap = (g.rod_radius - g.rod_diameter / 2.0) - (g.plate_thickness / 2.0 + tallest)
    if gap < 0.0:
        v.append(f"the rods at R {g.rod_radius * mm:.2f} mm run through the tallest "
                 f"component stack, which reaches {(g.plate_thickness / 2.0 + tallest) * mm:.2f} mm")
    else:
        notes.append(f"rods clear the tallest component stack by {gap * mm:.2f} mm")

    off = [h.name for h in g.mount_holes
           if not (-1e-9 <= h.x <= g.plate_length + 1e-9)]
    if off:
        v.append(f"{len(off)} mounting holes fall off the plate")
    else:
        notes.append(f"{len(g.mount_holes)} board mounting holes, all on the plate")

    # The plate butts each bracket and is bonded there. G-10 to G-10 structural epoxy.
    bond = g.bond_area * 25.0e6      # materials.STRUCTURAL_EPOXY_SHEAR
    shear = (g.mass + sum(c.mass for c in g.components)) * 9.81 * 8.3 / 2.0
    if bond < 4.0 * shear:
        v.append(f"the plate-to-bracket bond carries {bond:.0f} N against {shear:.1f} N, "
                 f"under 4x")
    else:
        notes.append(f"plate-to-bracket bond {g.bond_area * 1e6:.1f} mm2 at 25 MPa = "
                     f"{bond:.0f} N against {shear:.1f} N a joint, {bond / shear:.0f}x")

    if g.assembly_length > g.plate_length + 2.0 * g.bracket_thickness + 1e-9:
        v.append("the assembly is longer than the bay's usable length")

    sites = g.mount_sites()
    close = [(a, b) for i, a in enumerate(sites) for b in sites[i + 1:]
             if math.hypot(a[0] - b[0], a[1] - b[1]) < MIN_MOUNT_HOLE_PITCH]
    if close:
        v.append(f"{len(close)} pairs of mounting holes are still closer than "
                 f"{MIN_MOUNT_HOLE_PITCH * mm:.1f} mm after merging")

    strayed = []
    for (x, y, _faces, owners) in sites:
        for name in owners:
            p0 = next(q for q in g.placements if q.name == name)
            if not (p0.x - 1e-9 <= x <= p0.x + p0.length + 1e-9
                    and p0.y - 1e-9 <= y <= p0.y + p0.width + 1e-9):
                strayed.append(f"{name} at ({x * mm:.2f}, {y * mm:.2f})")
    if strayed:
        v.append(f"merging moved {len(strayed)} mounting holes off their board: "
                 f"{'; '.join(strayed)}")
    else:
        shared = [o for (_x, _y, f, o) in sites if len(f) > 1]
        if shared:
            notes.append(f"{len(sites)} mounting holes from "
                         f"{len(g._raw_mount_sites())} screw positions -- {len(shared)} "
                         f"merged into shared through-holes with a standoff each side: "
                         f"{'; '.join(' + '.join(o) for o in shared)}")

    under = g.screws_under_opposite()
    if under:
        notes.append(f"{len(under)} of {len(sites)} mounting screws land under a component "
                     f"on the other face -- countersink them flush")

    for name, gap in g.retention_gaps():
        if gap < TIE_SLOT_CLEAR_NEEDED:
            notes.append(f"{name} has {gap * mm:.2f} mm of clear plate beside it against "
                         f"the {TIE_SLOT_CLEAR_NEEDED * mm:.1f} mm a cable-tie slot needs "
                         f"-- retention is NOT SOLVED and is not drawn")

    if g.mass > SLED_MASS_BUDGET:
        v.append(f"sled + rods + hardware is {g.mass * mm:.1f} g against the "
                 f"{SLED_MASS_BUDGET * mm:.0f} g budgeted in mass.py")
    else:
        notes.append(f"{g.mass * mm:.1f} g against {SLED_MASS_BUDGET * mm:.0f} g budgeted "
                     f"-- {(SLED_MASS_BUDGET - g.mass) * mm:.1f} g under")

    return SledCheck(ok=not v, violations=v, notes=notes)
