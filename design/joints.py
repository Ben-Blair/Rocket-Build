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
    note: str = ""

    @property
    def bore(self) -> float:
        """Usable inner diameter INSIDE the coupler or shoulder, m.

        This is the number the whole question turned on. The part is a tube; what is inside
        it is still bay.
        """
        return self.airframe_id - 2.0 * self.wall_thickness

    def length_cost(self, bay: str) -> float:
        """Axial length this joint takes out of `bay`, m.

        Bulkheads only. The coupler itself costs none -- see the module docstring.
        """
        n = self.bulkheads_forward if bay == self.forward_bay else self.bulkheads_aft
        return n * BULKHEAD_ALLOWANCE

    def narrowed_span(self, bay: str) -> float:
        """Length of `bay` over which the usable diameter is `bore` rather than full, m."""
        return self.engagement if bay == self.into else 0.0


def default_joints(airframe_id: float, wall: float, diameter: float) -> list[Joint]:
    """The four joints of this vehicle, nose to tail.

    Each `kind` is a decision, and each is written down here rather than implied by the
    hardware, because "which joints come apart" is the sort of thing everyone assumes they
    know and nobody has stated.
    """
    cal = diameter
    eng = DEFAULT_ENGAGEMENT_CAL
    return [
        Joint(
            "nose / nav bay", "access", "nose cone", "nav bay",
            engagement=eng["access"] * cal, into="nav bay",
            wall_thickness=wall, airframe_id=airframe_id,
            # One bulkhead, and it belongs to the NOSE: it closes the instrumentation
            # cavity off from the nav bay so the nose is a module that lifts away whole.
            bulkheads_forward=1, bulkheads_aft=0,
            note="the access route to the nav bay sled, and the nose module's own aft face",
        ),
        Joint(
            "nav bay / canard module", "access", "nav bay", "canard module",
            engagement=eng["access"] * cal, into="canard module",
            wall_thickness=wall, airframe_id=airframe_id,
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
            # The aft gas seal. Charged to the canard module, whose aft end it closes.
            bulkheads_forward=1, bulkheads_aft=0,
            note="MAIN ejection separates here; the aft gas seal is this bulkhead",
        ),
        Joint(
            "recovery bay / booster", "separation", "recovery bay", "booster",
            engagement=eng["separation"] * cal, into="booster",
            wall_thickness=wall, airframe_id=airframe_id,
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
        return (narrow * self.narrow_span
                + full * (self.usable_length - self.narrow_span))

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
    narrow = max((j.narrowed_span(name) for j in mine), default=0.0)
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


def budgets(rocket, wall: float) -> dict[str, BayBudget]:
    """Every bay's budget, from the vehicle's own geometry."""
    tube = rocket.tubes[0]
    joints = default_joints(tube.inner_diameter, wall, rocket.tubes[0].outer_diameter)
    return {
        t.name: bay_budget(t.name, t.length, t.inner_diameter, joints)
        for t in rocket.tubes
    }
