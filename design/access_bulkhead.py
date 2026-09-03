"""The two access bulkheads `design/seal.py` named and never sized.

THE GAP THIS FILE CLOSES. `design/joints.py` puts a bulkhead on all four tube-to-tube
joints. Two are separation joints -- the aft gas seal and the recovery bay's internal
bulkhead -- and `seal.py` sizes both. The other two are ACCESS joints, and `seal.py` has
carried, since it was written, an explicit note that it does not size either of them:

  * the NOSE'S AFT FACE, which closes the instrumentation cavity and carries the swappable
    nose module's one electrical interface (`design/avionics.py`, "The nose as a swappable
    module");
  * the NAV BAY / CANARD MODULE plate, which carries the forward wiring pass-through.

Both already spend bay length in `joints.budgets()` as a 12 mm `BULKHEAD_ALLOWANCE`, so they
were priced while not existing as parts -- correction 20's shape, and correction 33's. Neither
is in the CAD, which is why the wiring pass-through has never been drawn: the plate it passes
through was not there.

THE ANSWER, STATED BEFORE THE ARITHMETIC BECAUSE IT IS THE ONE IDEA IN THIS FILE: **neither
plate is sized by the loads it carries.** Both clear the thinnest stocked G-10 sheet by more
than 25x on every load this file can find. That is not a rubber stamp -- it is the same shape
of result `design/venting.py` reported for the module vents, and it is worth having for the
same reason: "the bay must breathe fast enough" was the argument everyone gave for those
holes and it turned out not to be the one that sized them. Here the equivalent claim would be
"these plates need to be as thick as the aft gas seal because they are the same kind of
part," and it is just as wrong. **What actually sets these two plates is producibility --
holding a screw thread through repeated disassembly, and surviving a connector's panel-nut
torque -- neither of which has a stress model in this project.** So this file gives the
floor, and a stated practical minimum gives the design point, exactly the shape
`venting.py`'s port sizing already used.

WHY NEITHER PLATE SEES A REAL PRESSURE EVENT, WHICH IS WORTH TRACING RATHER THAN ASSERTING.

  * The NAV BAY / CANARD MODULE plate sits between two bays that both vent to ambient on
    their own -- the nav bay through its static ports, the canard module through its own
    wall (`design/venting.py`, correction 28). Neither is sealed, so the only load that can
    develop across the plate between them is the difference in how fast the two bays track a
    changing ambient pressure, which `venting.VentedBay.lag()` already computes. It comes out
    at single-digit pascals -- see `pass_through_from_evaluation()`. The ejection charge does
    not reach this plate either: it fires in the recovery bay's forward compartment against
    the AFT gas seal, and any leak past that disc is deliberately routed to the canard
    module's OWN vents (`venting.MODULE_VENT_STATION` sits in the aft band precisely so a
    leak finds a hole before it reaches this plate) rather than forward to here.
  * The NOSE'S AFT FACE has no such argument available, because **nobody has ever modelled
    whether the nose cavity is vented at all.** `design/avionics.py` and `design/venting.py`
    both stop at the nav bay. That is a real gap and this file does not close it -- what it
    does is refuse to pretend the gap is zero: it checks this plate against the fully-sealed
    `trapped_differential()` pad-to-apogee case as the conservative bound, the same number
    `venting.py` computes to explain why every sealed volume gets a hole. If the nose cavity
    turns out to need its own vent, that vent removes this load; until it exists, the plate is
    checked as though it does not.

THE SECOND LOAD ON THE NOSE PLATE, AND WHY IT IS A POINT LOAD RATHER THAN A PRESSURE.
`seal.py` says this disc "is what a future payload of up to about 300 g (correction 32) would
hang from." A tapered nose cone has nowhere else flat enough to cantilever a sled from, so
that sentence is taken here as the design intent: the payload or avionics sled mounts to this
plate's forward face on a small boss, and the plate reacts it exactly the way `seal.py`'s
aft-seal disc reacts the harness U-bolt -- `Bulkhead.point_load_stress()`, a load on a small
central patch. The MASS used is `NOSE_PAYLOAD_DESIGN_MASS`, the correction-32 provision
ceiling, not the 105 g of avionics actually flying today -- sizing the mounting for what is
built rather than what the vehicle is designed to carry is the same mistake `recovery.py`'s
harness made when its volume came from a budget line nobody had weighed.

WHAT THIS FILE DOES NOT DO.
  * It does not model the nose cavity's own venting. See above.
  * It does not model the removable joint's mechanical detail -- the flange, screws, or
    O-ring (if any) that let the canard module's forward face and the nav bay's aft face come
    apart by hand. `design/joints.py` prices the joint as a length allowance; this file prices
    the disc bonded at one end of it. The other end -- how the mating tube captures and seals
    against it -- is exactly as undesigned as `design/tube_section.py`'s note on coupler
    bending says it is, and for the same reason: nobody has needed it to be more than an
    allowance yet.
  * It does not choose the wire count or gauge for the pass-through, or the connector part
    number for the nose interface. Neither has ever been specified anywhere in this project
    (`design/control.py` puts servo wiring at "perhaps 20 g" and stops there). The hole sizes
    below are a practical bundle allowance, flagged the way `seal.py` flags
    `JOINT_FRICTION_ALLOWANCE` -- visible so a real harness BOM can replace it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import atmosphere, joints, venting
from .materials import DATASHEET_CONFIDENCE_MARGIN
from .seal import (
    Bulkhead, FeedThrough, G10_SHEET_THICKNESS, Hole, MIN_LIGAMENT, PLATE_MARGIN_REQUIRED,
)

# ---------------------------------------------------------------------------------------
# Assumptions carried openly, because nothing in this project has sized either of them yet.
# ---------------------------------------------------------------------------------------

# The potted wiring pass-through. Four servo leads (signal, power, ground each) plus the
# shared power/ground pair from the nav bay -- a real harness BOM has never been drawn, so
# this is one practical grommet sized for that bundle rather than a computed diameter. It is
# POTTED SOLID (docs/05, "the forward wiring pass-through -- DECIDED"), not a running seal, so
# oversizing it costs plate area and nothing else.
PASS_THROUGH_HOLE_DIAMETER = 0.008  # m
PASS_THROUGH_HOLE_COUNT = 1

# The nose module's one electrical interface (design/avionics.py, NOSE_MODULE_INTERFACES) --
# a panel-mount connector, not potted, because the whole point of the module is that it comes
# apart. Sized for a small multi-pin connector body; no part has been selected.
NOSE_CONNECTOR_HOLE_DIAMETER = 0.008  # m
NOSE_CONNECTOR_HOLE_COUNT = 1

# Practical minimum gauge, G-10 sheet. Neither number comes from a stress model -- see the
# module docstring. The pass-through plate is bonded on one face and is unscrewed for servo
# access repeatedly; the nose plate additionally carries a panel connector's nut torque and
# gets handled every time the module is swapped, so it gets one size more.
ACCESS_PANEL_THICKNESS_FLOOR = 0.0024  # m, nav bay / canard module plate
MODULE_INTERFACE_THICKNESS_FLOOR = 0.0032  # m, nose aft face

# correction 32's stated provision, not the 105 g of avionics actually flying -- see the
# module docstring on why the ceiling and not the built mass is what sizes the mount.
NOSE_PAYLOAD_DESIGN_MASS = 0.300  # kg
NOSE_PAYLOAD_FOOTPRINT_RADIUS = 0.004  # m, a small mounting boss; no sled has been designed


@dataclass
class AccessBulkheadResult:
    """Everything the report and `baseline.py` need for one access bulkhead, computed once."""

    name: str
    bulkhead: Bulkhead
    feed_through: FeedThrough
    pressure: float  # Pa, the governing pressure case
    pressure_case: str
    governed_by: str
    point_load: float = 0.0  # N
    point_load_footprint: float = 0.006  # m
    point_load_case: str = ""

    @property
    def plate_stress(self) -> float:
        return self.bulkhead.stress(self.pressure)

    @property
    def plate_margin(self) -> float:
        return self.bulkhead.flexural_allowable / max(self.plate_stress, 1.0)

    @property
    def hole_stress(self) -> float:
        f = self.feed_through
        if f.hole_diameter <= 0.0:
            return 0.0
        return (f.kt * f.net_section_factor(self.bulkhead.radius)
                * self.bulkhead.hole_field(self.pressure, f.radius_in_plate))

    @property
    def hole_margin(self) -> float:
        if self.feed_through.hole_diameter <= 0.0:
            return float("inf")
        return self.bulkhead.flexural_allowable / max(self.hole_stress, 1.0)

    @property
    def point_stress(self) -> float:
        if self.point_load <= 0.0:
            return 0.0
        return self.bulkhead.point_load_stress(self.point_load, self.point_load_footprint)

    @property
    def point_margin(self) -> float:
        if self.point_load <= 0.0:
            return float("inf")
        return self.bulkhead.flexural_allowable / max(self.point_stress, 1.0)

    @property
    def stress_margin(self) -> float:
        """The worst of the three -- what the disc would need to clear if the practical
        floor did not already set the thickness."""
        return min(self.plate_margin, self.hole_margin, self.point_margin)


def size_access_bulkhead(bore_diameter: float, pressure: float, feed: FeedThrough,
                         point_load: float = 0.0, point_load_footprint: float = 0.006,
                         floor: float = 0.0,
                         thicknesses: list[float] | None = None) -> tuple[float, str]:
    """Thinnest STOCKED G-10 sheet that clears every modelled load, or `floor`, whichever
    is thicker -- and which one actually governed, as a reason string.

    Mirrors `seal.size_bulkhead()`, extended with an optional point load and an optional
    practical floor, because neither plate here is sized by stress alone -- see the module
    docstring for why the floor is real and not a fudge factor.
    """
    options = sorted(thicknesses if thicknesses is not None else G10_SHEET_THICKNESS)
    stress_pick: float | None = None
    stress_reason = ""
    for t in options:
        plate = Bulkhead(bore_diameter, t)
        hole_r = plate.quiet_radius()
        pm = plate.flexural_allowable / plate.stress(pressure)
        hm = (plate.flexural_allowable / (feed.kt * feed.net_section_factor(plate.radius)
              * plate.hole_field(pressure, hole_r))) if feed.hole_diameter > 0.0 else float("inf")
        ptm = (plate.flexural_allowable / plate.point_load_stress(point_load, point_load_footprint)
               ) if point_load > 0.0 else float("inf")
        if min(pm, hm, ptm) >= PLATE_MARGIN_REQUIRED:
            stress_pick = t
            stress_reason = ("the disc" if pm <= hm and pm <= ptm else
                             "the feed-through hole" if hm <= ptm else "the point load")
            break
    if stress_pick is None:
        stress_pick, stress_reason = max(options), "the disc (no stocked sheet clears it)"

    if stress_pick >= floor:
        return stress_pick, stress_reason

    for t in options:
        if t >= floor:
            return t, (
                f"the practical minimum gauge -- handling and repeated fasteners set this; "
                f"{stress_reason} alone would have cleared {PLATE_MARGIN_REQUIRED:.0f}x at "
                f"{stress_pick * 1000:.1f} mm")
    return max(options), "the practical minimum gauge"


def pass_through_from_evaluation(ev, altitude: float = 285.0,
                                 climb_rate: float = 177.0) -> AccessBulkheadResult:
    """The nav bay / canard module plate -- the wiring pass-through, potted solid.

    285 m / 177 m/s is the same burnout point `scripts/baseline.py` and
    `scripts/seal_report.py` already evaluate venting lag at, so this is not a third station
    for the same question.
    """
    bore = ev.rocket.tubes[0].inner_diameter
    nav = next(t for t in ev.rocket.tubes if t.name == "nav bay")

    from . import avionics
    nav_free = avionics.free_volume(nav.inner_diameter, nav.length)
    nav_bay = venting.VentedBay("nav bay", nav_free, venting.CONVENTIONAL_PORT_COUNT,
                                venting.CONVENTIONAL_PORT_DIAMETER)
    mod_bay = venting.VentedBay("canard module", venting.CANARD_MODULE_FREE_VOLUME,
                                venting.MODULE_VENT_COUNT, venting.MODULE_VENT_DIAMETER)

    # Both bays vent to ambient independently; what loads THIS plate is the difference in how
    # fast each one tracks a changing ambient pressure, not either bay's absolute lag.
    pressure = abs(nav_bay.lag(altitude, climb_rate) - mod_bay.lag(altitude, climb_rate))

    trial = Bulkhead(bore, G10_SHEET_THICKNESS[0])
    feed = FeedThrough(hole_diameter=PASS_THROUGH_HOLE_DIAMETER,
                       radius_in_plate=trial.quiet_radius(), n_holes=PASS_THROUGH_HOLE_COUNT)
    t, reason = size_access_bulkhead(bore, pressure, feed, floor=ACCESS_PANEL_THICKNESS_FLOOR)
    plate = Bulkhead(bore, t)
    return AccessBulkheadResult(
        name="nav bay / canard module plate",
        bulkhead=plate,
        feed_through=FeedThrough(hole_diameter=PASS_THROUGH_HOLE_DIAMETER,
                                 radius_in_plate=plate.quiet_radius(),
                                 n_holes=PASS_THROUGH_HOLE_COUNT),
        pressure=pressure,
        pressure_case=(
            f"nav-bay/module venting-lag differential at {climb_rate:.0f} m/s -- NOT the "
            f"trapped pad-to-apogee case, because both bays vent independently"),
        governed_by=reason,
    )


def nose_plate_from_evaluation(ev) -> AccessBulkheadResult:
    """The nose's aft face -- the instrumentation cavity's closure, the swappable module's
    one electrical interface, and what a future payload hangs from (correction 32)."""
    bore = ev.rocket.tubes[0].inner_diameter  # uniform ID; the nose shoulder seats to it
    pressure = venting.trapped_differential(0.0, ev.flight.apogee)
    accel = ev.flight.max_acceleration_g * atmosphere.G0
    point_load = NOSE_PAYLOAD_DESIGN_MASS * accel

    trial = Bulkhead(bore, G10_SHEET_THICKNESS[0])
    feed = FeedThrough(hole_diameter=NOSE_CONNECTOR_HOLE_DIAMETER,
                       radius_in_plate=trial.quiet_radius(), n_holes=NOSE_CONNECTOR_HOLE_COUNT)
    t, reason = size_access_bulkhead(
        bore, pressure, feed, point_load=point_load,
        point_load_footprint=NOSE_PAYLOAD_FOOTPRINT_RADIUS,
        floor=MODULE_INTERFACE_THICKNESS_FLOOR)
    plate = Bulkhead(bore, t)
    return AccessBulkheadResult(
        name="nose aft face",
        bulkhead=plate,
        feed_through=FeedThrough(hole_diameter=NOSE_CONNECTOR_HOLE_DIAMETER,
                                 radius_in_plate=plate.quiet_radius(),
                                 n_holes=NOSE_CONNECTOR_HOLE_COUNT),
        pressure=pressure,
        pressure_case=(
            "trapped differential, pad to apogee -- CONSERVATIVE: the nose cavity's own "
            "venting has never been modelled anywhere in this project, so this checks the "
            "fully-sealed case rather than assume one exists"),
        governed_by=reason,
        point_load=point_load,
        point_load_footprint=NOSE_PAYLOAD_FOOTPRINT_RADIUS,
        point_load_case=(
            f"{NOSE_PAYLOAD_DESIGN_MASS * 1000:.0f} g payload provision (correction 32) at "
            f"{ev.flight.max_acceleration_g:.1f} g boost acceleration -- the provision "
            f"ceiling, not the 105 g of avionics actually flying"),
    )


def hole_layout(r: AccessBulkheadResult) -> list[Hole]:
    """The one hole in this plate, positioned -- reuses `seal.Hole` so `scripts/` can build
    both kinds of bulkhead off the same shape. Neither access plate anchors a harness, so
    there is no U-bolt pair to add alongside it the way `seal.hole_layout()` does.
    """
    f = r.feed_through
    return [Hole(f"{r.name} feed-through", f.radius_in_plate, 0.0, f.hole_diameter)]


def check_hole_layout(r: AccessBulkheadResult) -> AccessBulkheadCheck:
    """Edge clearance for the hole layout, in the shape `scripts/make_bulkhead_cad.py`
    expects before it will build anything."""
    chk = check_access_bulkhead(r)
    edge_notes = [n for n in chk.notes if "disc edge" in n]
    edge_violations = [v for v in chk.violations if "disc edge" in v]
    return AccessBulkheadCheck(ok=not edge_violations, violations=edge_violations,
                               notes=edge_notes)


def stack_length(r: AccessBulkheadResult, fillet: float = 0.003) -> float:
    """Axial length this bulkhead assembly costs, m: the disc plus ONE fillet.

    Unlike `seal.stack_length()`, which fillets both faces because that part is bonded at
    both ends of its load path, an access joint's plate is bonded to only one tube -- the
    other face is the flush mating face of the joint that comes apart by hand or by screws.
    Compared against `joints.BULKHEAD_ALLOWANCE`, the length every bay budget already spends
    on this plate without it existing as a part (see the module docstring).
    """
    return r.bulkhead.thickness + fillet


@dataclass
class AccessBulkheadCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_access_bulkhead(r: AccessBulkheadResult) -> AccessBulkheadCheck:
    """Everything that has to be true for this plate to be buildable -- written as a check
    for the reason `seal.check_seal()` gives: prose has carried "never sized" before and
    nothing acted on it.
    """
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    if r.plate_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"{r.name}: {r.bulkhead.thickness * mm:.1f} mm runs "
            f"{r.plate_stress / 1e6:.1f} MPa under {r.pressure_case}, margin "
            f"{r.plate_margin:.1f}x against {PLATE_MARGIN_REQUIRED:.1f}x")
    if r.hole_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"{r.name}: feed-through at R {r.feed_through.radius_in_plate * mm:.1f} mm runs "
            f"{r.hole_stress / 1e6:.1f} MPa, margin {r.hole_margin:.1f}x")
    if r.point_load > 0.0 and r.point_margin < PLATE_MARGIN_REQUIRED:
        v.append(
            f"{r.name}: {r.point_load_case} puts {r.point_stress / 1e6:.1f} MPa under the "
            f"mount, margin {r.point_margin:.1f}x")

    edge = r.bulkhead.radius - r.feed_through.radius_in_plate - r.feed_through.hole_diameter / 2.0
    if edge < MIN_LIGAMENT:
        v.append(
            f"{r.name}: feed-through leaves {edge * mm:.1f} mm to the disc edge, under the "
            f"{MIN_LIGAMENT * mm:.1f} mm minimum")
    else:
        notes.append(f"feed-through clears the disc edge by {edge * mm:.1f} mm")

    if not v:
        notes.append(
            f"{r.name}: {r.stress_margin:.0f}x on the worst modelled load "
            f"({r.pressure_case}) at the thinnest stocked sheet -- stress does not govern "
            f"this plate")
        notes.append(f"governed by: {r.governed_by}")

    if r.point_load > 0.0:
        notes.append(f"point load case: {r.point_load_case}")
    notes.append(f"pressure case: {r.pressure_case}")

    stack = stack_length(r)
    if stack > joints.BULKHEAD_ALLOWANCE:
        v.append(
            f"{r.name}: assembled stack {stack * mm:.1f} mm against the "
            f"{joints.BULKHEAD_ALLOWANCE * mm:.1f} mm joints.BULKHEAD_ALLOWANCE budgets for "
            f"it -- {(stack - joints.BULKHEAD_ALLOWANCE) * mm:.1f} mm short")
    else:
        notes.append(
            f"assembled stack {stack * mm:.1f} mm (disc + one 3 mm fillet -- one bonded "
            f"face, one flush mating face) inside the "
            f"{joints.BULKHEAD_ALLOWANCE * mm:.1f} mm joints.BULKHEAD_ALLOWANCE, which until "
            f"now was a typed number nothing had checked")

    if 0.0 < r.stress_margin < DATASHEET_CONFIDENCE_MARGIN:
        notes.append(
            f"a margin here is under {DATASHEET_CONFIDENCE_MARGIN:.0f}x -- get the supplier's "
            f"G-10 sheet datasheet before quoting a third digit")

    return AccessBulkheadCheck(ok=not v, violations=v, notes=notes)
