"""What the tube-to-tube joints cost, and which of them come apart.

THE QUESTION THIS FILE SETTLES, and the answer is not the one that was feared.

`scripts/avionics_report.py` raised it: `docs/04` carries a 1 caliber -- 79.4 mm -- nose
shoulder on a 127 mm nav bay, and a shoulder inserts INTO the tube it joins. Nobody had
decided which tube's length it spends, and the two readings were 79 mm apart. If the sled
had to sit aft of the shoulder the nav bay was short by about 80 mm rather than 14, which
would have been the largest single problem in the vehicle.

**A shoulder is a tube, and its bore is usable.** So is a coupler's. Neither consumes bay
LENGTH -- what each one costs is local DIAMETER, over the span it occupies:

    coupler / shoulder ID  =  airframe ID  -  2 x wall  =  74.8 - 4.6  =  70.2 mm

That is the whole answer. A parachute packs down a 70.2 mm bore perfectly well and a sled
runs up inside one. What actually costs length is a BULKHEAD, and bulkheads were already
being counted. The nav bay's shortfall goes from a possible 80 mm to about 9 mm, which is
inside what the packing-efficiency guess is worth.

The reason it looked frightening is worth keeping: **the question was framed as "which bay
does the shoulder's length come out of", and the answer is neither, because the premise --
that an inserted tube consumes the volume it occupies -- is false for a hollow part.** That
is correction 28's shape exactly, one joint further forward: a complete-sounding question
whose two answers were both wrong.

WHAT IS MODELLED HERE. All four joints, because the nose shoulder turned out to be one
instance of something general, and because `tube_section.py` has carried *"the tube-to-tube
joints either side of the module -- couplers are a mass line in mass.py and nothing more"*
since it was written.

THE HALF THIS FILE USED TO LEAVE OUT, and what leaving it out hid (Sep 2026).

Everything above describes a joint by the half that PROTRUDES -- `engagement` and `into` --
because the question it was written to settle was whether an inserted tube costs the bay it
protrudes into any length. It does not, and that answer still stands. But every coupler also
has an ANCHORED half, bonded into the tube on the other side, and that half was not a field
here. It could not be checked, so it never was, and it turns out the vehicle cannot afford
what convention charges for it:

    the nav bay tube                                       127.04 mm   1.60 cal
    the nose shoulder engaged into it                       79.40 mm   1.00 cal
    what is left for the aft coupler's bonded half          47.64 mm   0.60 cal
    what the same 1.00 cal convention wants                 79.40 mm   -- 31.76 mm short

**Two 1.0 cal joints do not fit in a 1.6 cal bay.** Nothing had ever said so, because no
model held both halves at once. `anchor` is that field now, and `check_joints()` is the
check: a bay's tube has to hold everything inserted into it from either end.

The nav bay / canard module joint's anchor is therefore DERIVED -- `for_rocket()` gives it
whatever the nose shoulder leaves, 0.600 cal here -- rather than typed, so that it cannot
quietly stop fitting if `nav_bay_cal` ever moves. It is BELOW the convention, and it is
stated rather than absorbed. Nothing in this project sizes a coupler in bending -- see the
paragraph below, which has been true since this file was written and is only now
load-bearing -- so the convention was the only argument either way and this joint no longer
satisfies it. That is an open item, and it is the one thing the static ports needed and
could not get: `design/ports.py` puts them in that 47.64 mm because it is the only band of
nav bay wall a hole can go through.

THE CANARD MODULE'S OWN TWO JOINTS ARE RESOLVED THE SAME WAY (Sep 2026, correction 42).
The printed hinge/bearing bay sits in the MIDDLE of the canard module's tube (Z 53.129 to
94.629 mm, `bay.py`'s `forward_face`/`aft_face`), so a coupler bonded into either end of the
tube cannot pass through it -- and each of this module's two joints is bounded by it
separately, unlike the nav bay's single constraint:

    forward joint's ENGAGEMENT, into canard module      53.129 - 2.400 (pass-through plate)
                                                         = 50.729 mm, against 79.40 charged
    aft joint's ANCHOR, into canard module               142.920 - 94.629
                                                         = 48.291 mm, against 79.40 charged
    sum against the tube                                 99.020 mm vs 142.920 mm tube
                                                         -> 43.9 mm SPARE

`bay.joint_room()` computes both from an already-built `BayGeometry`, and
`design/joints.py`'s `canard_forward_room`/`canard_aft_room` parameters take them the same
way `nav_bay_length` takes the nav bay's -- `min(convention, room)`, so a caller with no room
figure still gets the number that FAILS the check rather than one that quietly passes it.
Both derived lengths are BELOW the 1.0 cal convention, exactly like the nav bay's anchor, and
for the same reason nothing closes it: nothing in this project sizes a coupler in bending, so
there is no analysis to confirm or replace the convention with -- `check_joints()` reports
both as notes, not violations, and that stays open. What is resolved is the capacity
violation itself: the module's tube is not physically over-subscribed, only under-served by
a convention it was never going to meet in 142.92 mm either way.

WHAT CHANGED DOWNSTREAM WHEN `anchor` ARRIVED. `narrowed_span` now counts the anchored half
too, because a bonded coupler narrows the bore exactly as much as an inserted one does. The
recovery bay is the only bay where that moves a number anyone reads: its full-bore equivalent
length drops 347.8 -> 338.4 mm and `recovery.check_packing`'s margin goes +17.8 -> +8.4 mm.
It still fits. That was applied rather than merely reported, because leaving half of each
joint out of the bore model is the identical defect to leaving it out of the length model,
and fixing one and not the other would have left the trap in place.

WHAT IS NOT. The joints' STRENGTH. A coupler in bending, the bond line that holds it, and
the shear pins that are supposed to fail before it are all outside this file -- it answers
"what does the joint cost the bay" and nothing else. `design/seal.py` sizes the shear pins
at the two separation joints; nothing sizes a coupler in bending anywhere in this project,
and `tube_section.py`'s note about global airframe beam bending still stands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

JointKind = Literal["bonded", "access", "separation"]

# Engagement length, in calibers, for each kind of joint. These are convention rather than
# analysis -- one caliber of engagement each side of a joint is the standard high-power rule
# and this project has no coupler bending model to argue with it. They are here so the
# convention is visible and can be argued with, not so it can be trusted.
DEFAULT_ENGAGEMENT_CAL = {
    "bonded": 1.0,      # a permanent joint; the coupler is bonded into both tubes
    "access": 1.0,      # comes apart by hand or by screws; nose shoulder is this
    "separation": 1.0,  # comes apart on an ejection charge, held by shear pins
}

# Anchored length, in calibers: how much of the OTHER tube the coupler is bonded into. Same
# convention and the same standing as DEFAULT_ENGAGEMENT_CAL above -- one caliber each side
# is the high-power rule -- and it is a separate dict because the two halves are separately
# negotiable, which is the whole point of having found that the vehicle cannot pay both.
DEFAULT_ANCHOR_CAL = {
    "bonded": 1.0,
    "access": 1.0,
    "separation": 1.0,
}

# An INTEGRAL shoulder -- one moulded as part of the nose cone rather than bonded in as a
# separate tube -- has no anchored half at all. It is not that the anchor is short; it is
# that there is nothing to bond, so it consumes none of the nose's own length. Named so that
# `anchor = 0.0` on the nose joint reads as a fact rather than as a value nobody filled in.
INTEGRAL_SHOULDER = 0.0

# A bulkhead closing the end of a bay: the plate, its fillets, and any boss standing proud.
# Matches recovery.BULKHEAD_THICKNESS, and deliberately so -- a bulkhead is a bulkhead
# wherever it is, and two different numbers for it would be two things to keep in step.
BULKHEAD_ALLOWANCE = 0.012  # m


@dataclass(frozen=True)
class Joint:
    """One tube-to-tube joint, and what it does to the bays either side of it.

    `forward_bay` and `aft_bay` name the two tubes. `into` says which of them the coupler or
    shoulder actually protrudes into -- for a nose cone that is always the aft one, since
    the shoulder hangs off the nose.
    """

    name: str
    kind: JointKind
    forward_bay: str
    aft_bay: str
    engagement: float  # m, how far the coupler/shoulder reaches into `into`
    into: str
    wall_thickness: float
    airframe_id: float
    bulkheads_forward: int = 0
    bulkheads_aft: int = 0
    # m, how far the coupler is BONDED into the other tube. Zero for an integral shoulder,
    # which has nothing to bond. This is the half that was missing -- see the module header.
    anchor: float = 0.0
    note: str = ""

    @property
    def bore(self) -> float:
        """Usable inner diameter INSIDE the coupler or shoulder, m.

        This is the number the whole question turned on. The part is a tube; what is inside
        it is still bay.
        """
        return self.airframe_id - 2.0 * self.wall_thickness

    @property
    def anchor_bay(self) -> str:
        """The bay whose tube the coupler is bonded into -- the one it does not protrude into.

        For an integral shoulder this still names a bay, and `anchor` is zero there, which is
        the distinction the two fields exist to keep: WHERE the anchor is and HOW MUCH tube it
        takes are different questions, and collapsing them is how the nose joint looked free.
        """
        return self.aft_bay if self.into == self.forward_bay else self.forward_bay

    def length_cost(self, bay: str) -> float:
        """Axial length this joint takes out of `bay`, m.

        Bulkheads only. The coupler itself costs none -- see the module docstring.
        """
        n = self.bulkheads_forward if bay == self.forward_bay else self.bulkheads_aft
        return n * BULKHEAD_ALLOWANCE

    def narrowed_span(self, bay: str) -> float:
        """Length of `bay` over which the usable diameter is `bore` rather than full, m.

        BOTH halves count. A coupler bonded into a tube narrows that tube's bore exactly as
        much as one merely inserted into it does -- the wall is the same 2.3 mm either way,
        and whether it is wetted with epoxy makes no difference to what fits inside. Until
        Sep 2026 only `engagement` counted here, which is the same omission `anchor` fixes in
        the capacity check and it was worth 9.5 mm of the recovery bay.
        """
        span = 0.0
        if bay == self.into:
            span += self.engagement
        if bay == self.anchor_bay:
            span += self.anchor
        return span

    def tube_demand(self, bay: str) -> float:
        """How much of `bay`'s tube this joint occupies from its end, m.

        The same quantity as `narrowed_span` today, and a separate method on purpose: one is
        about what still FITS INSIDE the bay and the other about whether the TUBE ITSELF has
        room at that end. They agree only while every joint is a plain concentric sleeve, and
        the moment one is not -- a stepped coupler, a flanged one -- they part company.
        """
        return self.narrowed_span(bay)


def default_joints(airframe_id: float, wall: float, diameter: float,
                   nav_bay_length: float | None = None,
                   canard_forward_room: float | None = None,
                   canard_aft_room: float | None = None) -> list[Joint]:
    """The four joints of this vehicle, nose to tail.

    Each `kind` is a decision, and each is written down here rather than implied by the
    hardware, because "which joints come apart" is the sort of thing everyone assumes they
    know and nobody has stated.

    `nav_bay_length` is optional and, when given, DERIVES the aft joint's anchored half from
    what the nose shoulder leaves instead of charging the convention. `canard_forward_room`
    and `canard_aft_room` do the same for the canard module's own two joints, derived from
    the printed bay's footprint (`bay.joint_room()`, docs/01 correction 42) rather than the
    module's frozen length -- the printed bay sits in the MIDDLE of the tube, so unlike the
    nav bay's single constraint this one bounds both of the canard module's joints at once.
    Prefer `for_rocket()`, which always has all three. Convention is the fallback in every
    case, so a caller who does not know the real room gets the number that is wrong in the
    direction that FAILS the check rather than the one that quietly passes it.
    """
    cal = diameter
    eng = DEFAULT_ENGAGEMENT_CAL
    anc = DEFAULT_ANCHOR_CAL
    nose_engagement = eng["access"] * cal
    if nav_bay_length is None:
        nav_aft_anchor = anc["access"] * cal
    else:
        nav_aft_anchor = min(anc["access"] * cal, nav_bay_length - nose_engagement)

    canard_fwd_conv = eng["access"] * cal
    canard_engagement = (canard_fwd_conv if canard_forward_room is None
                         else min(canard_fwd_conv, canard_forward_room))
    canard_aft_conv = anc["separation"] * cal
    canard_anchor = (canard_aft_conv if canard_aft_room is None
                    else min(canard_aft_conv, canard_aft_room))
    return [
        Joint(
            "nose / nav bay", "access", "nose cone", "nav bay",
            engagement=nose_engagement, into="nav bay",
            wall_thickness=wall, airframe_id=airframe_id,
            # The shoulder is MOULDED as part of the nose cone, so there is no bonded half
            # and it spends none of the nose's own length. That is why this joint looked free
            # for as long as `anchor` did not exist -- it genuinely is, and the aft one is not.
            anchor=INTEGRAL_SHOULDER,
            # One bulkhead, and it belongs to the NOSE: it closes the instrumentation
            # cavity off from the nav bay so the nose is a module that lifts away whole.
            bulkheads_forward=1, bulkheads_aft=0,
            note="the access route to the nav bay sled, and the nose module's own aft face",
        ),
        Joint(
            "nav bay / canard module", "access", "nav bay", "canard module",
            engagement=canard_engagement, into="canard module",
            wall_thickness=wall, airframe_id=airframe_id,
            # ENGAGEMENT (canard-module side) is derived from the printed bay's forward
            # face less the pass-through plate -- 50.729 mm, not the 79.40 mm convention,
            # because the printed bay's structure starts at Z 53.129 and a coupler cannot
            # be bonded through it. See design/bay.py's joint_room() and docs/01
            # correction 42.
            #
            # ANCHOR (nav-bay side) is 0.600 cal, not the 1.0 cal convention, and derived
            # rather than typed: the nose shoulder has already spent the nav bay's forward
            # caliber and this is what is left. Below convention, nothing here sizes a
            # coupler in bending, open item. The static ports go in this band -- see
            # design/ports.py.
            anchor=nav_aft_anchor,
            # The bulkhead here is the wiring pass-through, potted solid (correction 28).
            # It is charged to the nav bay because it closes the nav bay's aft end; the
            # canard module's forward face is the same plate seen from the other side.
            bulkheads_forward=1, bulkheads_aft=0,
            note="carries the potted wiring pass-through; servo access is through it",
        ),
        Joint(
            "canard module / recovery bay", "separation", "canard module", "recovery bay",
            engagement=eng["separation"] * cal, into="recovery bay",
            wall_thickness=wall, airframe_id=airframe_id,
            # ANCHOR (canard-module side) is derived from what is left of the tube behind
            # the printed bay -- 48.291 mm, not the 79.40 mm convention: the bay's own
            # structure runs to Z 94.629 and a coupler cannot be bonded through it either.
            # The aft gas seal's own bulkhead SHARES this span rather than competing for
            # it -- it is bonded inside the coupler, same as at any other station along a
            # tube. Below convention; nothing here sizes a coupler in bending, open item.
            anchor=canard_anchor,
            # The aft gas seal. Charged to the canard module, whose aft end it closes.
            bulkheads_forward=1, bulkheads_aft=0,
            note="MAIN ejection separates here; the aft gas seal is this bulkhead",
        ),
        Joint(
            "recovery bay / booster", "separation", "recovery bay", "booster",
            engagement=eng["separation"] * cal, into="booster",
            wall_thickness=wall, airframe_id=airframe_id,
            anchor=anc["separation"] * cal,
            bulkheads_forward=0, bulkheads_aft=1,
            note="DROGUE ejection separates here; the booster's forward bulkhead closes it",
        ),
    ]


@dataclass
class BayBudget:
    """What one bay actually has, after its joints have taken their share."""

    name: str
    tube_length: float
    usable_length: float
    full_bore: float
    narrow_bore: float
    narrow_span: float
    bulkheads: int
    joints: list[str]

    @property
    def min_bore(self) -> float:
        """The diameter a one-piece SLED has to live inside.

        A sled is one flat plate, so it is as wide as its narrowest station allows, and the
        narrow section governs the whole length. A packed canopy is not like that -- see
        `equivalent_length()`.
        """
        return self.narrow_bore if self.narrow_span > 0.0 else self.full_bore

    @property
    def volume(self) -> float:
        """True internal volume, m^3, with the coupler bore counted where it applies."""
        import math
        full = math.pi * self.full_bore**2 / 4.0
        narrow = math.pi * self.narrow_bore**2 / 4.0
        # An OVER-SUBSCRIBED bay has more joint than tube (see `check_joints`), and the
        # arithmetic below would then hand back a volume with a negative full-bore term --
        # a number that looks like an answer. Clamp instead, and read `check_joints` for
        # whether this bay's volume means anything at all. The canard module is currently
        # in exactly that state.
        span = min(self.narrow_span, self.usable_length)
        return narrow * span + full * (self.usable_length - span)

    @property
    def equivalent_length(self) -> float:
        """Usable length restated as a full-bore cylinder of the same VOLUME, m.

        For anything that packs -- a parachute, a harness -- the narrowed span is not a
        length penalty and not a diameter penalty, it is a volume penalty, and the honest
        way to hand it to a length-based check is to convert it. `recovery.check_packing`
        takes this instead of the raw tube length.

        A sled cannot use this: it is rigid and one width throughout, so it takes
        `min_bore` and `usable_length` separately. Two different parts of the same bay,
        constrained two different ways, and collapsing them into one number would be wrong
        for whichever one it was not written for.
        """
        import math
        return self.volume / (math.pi * self.full_bore**2 / 4.0)

    def __str__(self) -> str:
        return (
            f"{self.name:16s} {self.tube_length * 1000:6.1f} mm tube -> "
            f"{self.usable_length * 1000:6.1f} mm usable, "
            f"bore {self.full_bore * 1000:.1f} mm "
            f"({self.narrow_bore * 1000:.1f} over {self.narrow_span * 1000:.0f} mm)"
        )


def bay_budget(name: str, tube_length: float, airframe_id: float,
               joints: list[Joint]) -> BayBudget:
    """Usable length and the bore profile for one bay."""
    mine = [j for j in joints if name in (j.forward_bay, j.aft_bay)]
    length_cost = sum(j.length_cost(name) for j in mine)
    # SUM, not max. A bay's two joints are at opposite ends, so their narrowed spans are
    # disjoint and both are real: a bay sleeved at both ends is narrow over both. This read
    # `max(...)` until Sep 2026, which was harmless only while `narrowed_span` returned
    # something non-zero for at most one joint per bay -- the moment `anchor` made the second
    # one non-zero, `max` started silently discarding it.
    narrow = sum(j.narrowed_span(name) for j in mine)
    bore = min((j.bore for j in mine if j.narrowed_span(name) > 0.0), default=airframe_id)
    return BayBudget(
        name=name,
        tube_length=tube_length,
        usable_length=tube_length - length_cost,
        full_bore=airframe_id,
        narrow_bore=bore,
        narrow_span=narrow,
        bulkheads=sum(
            (j.bulkheads_forward if name == j.forward_bay else j.bulkheads_aft)
            for j in mine
        ),
        joints=[j.name for j in mine],
    )


def for_rocket(rocket, wall: float, canard_forward_room: float | None = None,
              canard_aft_room: float | None = None) -> list[Joint]:
    """The four joints, with every length this vehicle's own geometry can settle.

    One place, so that `budgets()`, `check_joints()` and `design/ports.py` cannot each build
    a slightly different set of joints -- which is what would have happened the moment the
    nav bay's anchor became a derived number rather than a constant.

    `canard_forward_room`/`canard_aft_room` are optional and come from `bay.joint_room()` --
    a caller that has already built the printed bay (`scripts/baseline.py`,
    `scripts/port_report.py`) should pass them. This function does not build the printed bay
    itself: doing so needs a servo choice (`hinge.selected`, `hinge.canard_hinge_station`),
    not just `(rocket, wall)`, and `design/configure.py`'s `evaluate()` calls this on every
    optimizer iteration while only ever reading the recovery bay's budget -- paying for that
    build on a path that never uses it would be pure cost.
    """
    tube = rocket.tubes[0]
    nav = next(t for t in rocket.tubes if t.name == "nav bay")
    return default_joints(tube.inner_diameter, wall, tube.outer_diameter,
                          nav_bay_length=nav.length,
                          canard_forward_room=canard_forward_room,
                          canard_aft_room=canard_aft_room)


def budgets(rocket, wall: float, canard_forward_room: float | None = None,
           canard_aft_room: float | None = None) -> dict[str, BayBudget]:
    """Every bay's budget, from the vehicle's own geometry."""
    joints = for_rocket(rocket, wall, canard_forward_room, canard_aft_room)
    return {
        t.name: bay_budget(t.name, t.length, t.inner_diameter, joints)
        for t in rocket.tubes
    }


@dataclass(frozen=True)
class TubeCapacity:
    """What one bay's tube is asked to hold at its two ends, against how long it is."""

    bay: str
    tube_length: float
    demands: list[tuple[str, float]]  # (joint name, metres of this tube it occupies)

    @property
    def demanded(self) -> float:
        return sum(d for _, d in self.demands)

    @property
    def spare(self) -> float:
        return self.tube_length - self.demanded

    def __str__(self) -> str:
        parts = ", ".join(f"{n} {d * 1000:.2f}" for n, d in self.demands)
        return (f"{self.bay:16s} {self.tube_length * 1000:6.1f} mm tube holds "
                f"{self.demanded * 1000:6.2f} mm of joint ({parts}) -> "
                f"{self.spare * 1000:+7.2f} mm spare")


def tube_capacity(rocket, wall: float, canard_forward_room: float | None = None,
                  canard_aft_room: float | None = None) -> dict[str, TubeCapacity]:
    """Per bay, the sum of every joint half that lives inside its tube.

    THE CHECK THAT DID NOT EXIST. `bay_budget` answers "what is left to USE"; this answers
    "does the tube physically have room for its own joints", and until `anchor` existed there
    was no way to ask it. The two are not the same question and the nav bay is the proof: it
    has 115.0 mm usable and 0.00 mm spare.
    """
    js = for_rocket(rocket, wall, canard_forward_room, canard_aft_room)
    out: dict[str, TubeCapacity] = {}
    for t in rocket.tubes:
        demands = [(j.name, j.tube_demand(t.name)) for j in js
                   if j.tube_demand(t.name) > 0.0]
        out[t.name] = TubeCapacity(t.name, t.length, demands)
    return out


@dataclass
class JointCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_joints(rocket, wall: float, canard_forward_room: float | None = None,
                 canard_aft_room: float | None = None) -> JointCheck:
    """Can every bay's tube hold its own joints, and does any joint fall under convention?

    Two separate questions and they fail differently. Over-subscription is a VIOLATION --
    two solids cannot share a millimetre of tube. Falling under the 1.0 cal convention is a
    NOTE, because the convention is not a load case and this project has no coupler bending
    model to replace it with; saying otherwise would be inventing a requirement to satisfy.

    Pass `canard_forward_room`/`canard_aft_room` (from `bay.joint_room()`) to check the
    canard module against its printed bay's real footprint rather than the bare convention
    -- without them this reports the canard module as over-subscribed by 15.88 mm, which is
    true of the convention and not of the vehicle. See docs/01 correction 42.
    """
    v: list[str] = []
    notes: list[str] = []
    mm = 1000.0

    for cap in tube_capacity(rocket, wall, canard_forward_room, canard_aft_room).values():
        if cap.spare < -1e-9:
            v.append(
                f"{cap.bay}: {cap.demanded * mm:.2f} mm of joint in a "
                f"{cap.tube_length * mm:.2f} mm tube -- over by {-cap.spare * mm:.2f} mm. "
                f"Two solids cannot share the same millimetre of tube")
        elif cap.spare < 1e-9:
            notes.append(
                f"{cap.bay} is EXACTLY full: {cap.demanded * mm:.2f} mm of joint in "
                f"{cap.tube_length * mm:.2f} mm of tube, 0.00 mm spare. Nothing else can be "
                f"bonded to this bore anywhere along its length")
        else:
            notes.append(f"{cap.bay} has {cap.spare * mm:.2f} mm of tube spare")

    cal = rocket.diameter
    for j in for_rocket(rocket, wall, canard_forward_room, canard_aft_room):
        for half, length in (("engagement", j.engagement), ("anchor", j.anchor)):
            if half == "anchor" and length == INTEGRAL_SHOULDER:
                continue
            want = (DEFAULT_ENGAGEMENT_CAL if half == "engagement"
                    else DEFAULT_ANCHOR_CAL)[j.kind] * cal
            if length < want - 1e-9:
                notes.append(
                    f"{j.name}: {half} {length * mm:.2f} mm is "
                    f"{(want - length) * mm:.2f} mm under the {want / cal:.1f} cal "
                    f"convention. Nothing in this project sizes a coupler in bending, so "
                    f"there is no analysis that either confirms or replaces it -- open")
    return JointCheck(ok=not v, violations=v, notes=notes)
