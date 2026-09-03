"""Where the nav bay's static ports go, and what placing three holes had to find out first.

THE GAP THIS FILE CLOSES. `design/venting.py` SIZES the static ports -- 3 x dia 3.2 mm --
and says, in its own header, that it "says nothing about where the NAV BAY's ports go
beyond the ring rule". `design/sled.py` repeats it, and `docs/08` closes with it: *"the nav
bay's static ports still have no station and no clocking anywhere in this repo. That is the
next open CAD item in this bay, and it needs a decision rather than a script."*

It needed a script. The first question a hole asks is not "where is the pressure right" --
it is **what is behind the wall**, and the answer turned out to be: in this bay, always
something.

---------------------------------------------------------------------------------------
FINDING 1. THE NAV BAY HAS NO BARE WALL, AND THE ARITHMETIC IS NOT CLOSE.

The nav bay tube is 1.60 cal, 127.04 mm. Its two joints are both `access` joints and
`design/joints.py` gives each of them 1.0 cal of engagement, which is the standard
high-power rule:

    nose shoulder, engaged INTO the nav bay      79.40 mm     station 317.60 -> 397.00
    left for the aft coupler's bonded half       47.64 mm     station 397.00 -> 444.64
    what the same 1.0 cal convention wants       79.40 mm     short by 31.76 mm

**Two 1.0 cal joints do not fit in a 1.60 cal tube.** Nothing had noticed, and the reason
is structural to the model rather than a slip: `joints.py` describes a joint only by the
half that PROTRUDES -- `engagement` and `into` -- because the question it was written to
settle (correction 31) was whether an inserted tube costs the bay it protrudes into any
length. It does not. But every coupler also has an ANCHORED half, bonded into the other
tube, and that half was never a field, so no check could ask whether the bay had room for
it. An allowance nobody turned into a part, for the fifth time in this project -- except
that this one was not even an allowance. It was a part with no allowance at all.

It is over-subscribed at the other end of the same joint too, and worse. The coupler
protrudes AFT into the canard module, and the module's first 53.13 mm are already spoken
for: the potted pass-through plate occupies Z 0.000 -> 2.400, and the printed canard bay is
bonded to the bore from Z 53.129. So the protrusion has 50.73 mm to live in against the
79.40 mm `joints.py` charges -- 28.67 mm short, and it would have driven a coupler straight
through the bay that carries the hinge bearings.

WHAT IS DONE ABOUT IT: `joints.py` now carries `anchor` as well as `engagement`, and
`check_joints()` fails a bay whose tube cannot hold what its joints demand. The nav bay /
canard module joint is set to the 0.600 cal + 0.639 cal that the geometry actually leaves,
which is a stated design decision and not a retune -- see that file. Both are below the
1.0 cal convention, and **nothing in this project sizes a coupler in bending**, so the
convention is the only argument either way. That is an open item, recorded, not closed.

---------------------------------------------------------------------------------------
FINDING 2. SO THE PORTS ARE DRILLED THROUGH TUBE AND COUPLER TOGETHER -- WHICH IS WHAT AN
AV-BAY HAS ALWAYS DONE.

Given Finding 1 there are exactly two bands to choose between and one of them is
disqualified:

  * FORWARD, station 317.60 -> 397.00, tube + nose shoulder. Disqualified. That joint COMES
    APART; a hole through both walls has to re-align every time the nose goes back on, and
    the annulus between the two tubes is a leak path the altimeter would then be sensing
    through.
  * AFT, station 397.00 -> 444.64, tube + the aft coupler's BONDED half. Qualified, because
    the bond makes the two walls one wall. The hole is drilled after bonding, so it cannot
    mis-align, and it is deburred from inside the nav bay before the coupler ever goes into
    the module.

This is not a workaround. The classic high-power avionics bay IS a coupler with its static
ports drilled through it, and the only reason it looked like one here is that this vehicle's
av-bay is a full-diameter tube rather than a coupler, so the doubled wall arrives from the
joint instead of from the bay.

The port is therefore 4.60 mm deep through a 3.2 mm hole -- L/D 1.44 -- and that is what
turned up Finding 5.

---------------------------------------------------------------------------------------
FINDING 3. NEITHER CONVENTIONAL PLACEMENT RULE CAN BE MET, AND IT COSTS ABOUT A METRE.

The two rules everyone quotes for a static port are "at least 2 calibers aft of the nose
shoulder" and "at least 1 caliber forward of the next disturbance". This bay can offer
1.00 -> 1.45 cal on the first and 0.63 cal on the second, because **the nav bay is 1.6 cal
long and it is sandwiched between the nose junction and the canards.** There is no station
anywhere in the vehicle's sensed volume that satisfies either rule, let alone both.

So the violation had to be priced rather than avoided, and both fields are modelled here:

  * `nose_position_error()` -- the over-expansion on the cylinder aft of a tangent ogive,
    from an axisymmetric line-source slender-body solution, Prandtl-Glauert corrected.
    It is VALIDATED, by `spheroid_validation()`, against the exact potential solution for a
    4:1 prolate spheroid in axial flow -- the same fineness as this nose -- where it
    under-reads |Cp| by 17%. That factor is applied. A model that has never been run against
    a case with a known answer is a number, not a model.
  * `canard_position_error()` -- the canards' own upstream field, as four horseshoe
    vortices solved by Biot-Savart. It matters because 0.63 cal is close, and because on a
    GUIDED vehicle this term is *modulated by the control input*: the altimeter would be
    reading the controller.

And the answer is that it does not matter, for a reason worth stating plainly: **position
error scales with dynamic pressure, and the altimeter is only ever read where q is small.**
At max q the total is tens of metres. At main deployment -- 200 m, under drogue, q of a few
hundred pascals -- the whole error is under a metre, and at apogee it is zero. The station
is therefore NOT set by aerodynamics; it is set by edge distance in the bonded band, and
the ports go in the middle of it. The aerodynamic optimum (as far aft as the band allows)
is worth 0.12 m at the moment the altimeter is actually read -- 0.69 m of error against
0.56 m -- and buys it by spending the 23.8 mm of edge distance each side down to nothing. Same shape as `venting.py`'s own result on port SIZE: the model gives
the floor, practice gives the design point, and the model's job was to find that out.

WHAT DOES NOT FOLLOW FROM THIS. `design/estimation.py` carries
`STATIC_PORT_ERROR_COEFF = 0.02` for the baro-during-boost finding, described as "a port on
a smooth cylinder well aft of the nose shoulder". This port is not well aft of the nose
shoulder -- it cannot be -- and the model above puts the real figure at the chosen station
in the same neighbourhood as the guess. That constant is NOT edited here. It is an estimate
that was flagged as an estimate, the finding it feeds is qualitative (baro error correlates
with velocity, so it looks like signal to a filter), and moving it would change nothing
except to make a computed number look like a measured one.

---------------------------------------------------------------------------------------
FINDING 4. THE PORT COUNT IS NOT DECIDED BY THE FLOW EITHER -- BUT FOR FOUR PORTS THE
CLOCKING WOULD BE, AND FOR THREE IT IS NOT. THAT IS THE REASON TO KEEP THREE.

A ring of N equally spaced ports feeds ONE plenum, so the altimeter reads the MEAN of the
wall pressure at those N points. Decompose the circumferential disturbance into harmonics
e^(i k theta): the mean over N equally spaced samples kills every k that is not a multiple
of N, exactly, and passes the rest untouched. So "how many ports" is really "which harmonics
does this vehicle make", and a four-canard vehicle makes exactly two kinds:

    a LATERAL command -- panels deflected as cos(panel - command)   k = 1, 3, 5, 7, ...
    a ROLL command    -- all four panels deflected alike            k = 4, 8, 12, ...
    angle of attack and sideslip                                    k = 1 (plus small 2, 3)

    N = 3 rejects k = 1, 2, 4, 5, 7, 8 ...  passes k = 3, 6, 9 ...
    N = 4 rejects k = 1, 2, 3, 5, 6, 7 ...  passes k = 4, 8, 12 ...

THE FIRST GUESS HERE WAS WRONG AND IT IS WORTH RECORDING WHICH WAY. "Three and four are
coprime, so a 3-port ring averages the canards' 4-fold field and a 4-port ring cannot" is
true as far as it goes, and it points at the wrong answer, because the 4-fold ROLL field is
the small one. The lateral field is 170x larger, it is odd-harmonic, and **N = 4 rejects
every one of its harmonics while N = 3 passes its k = 3**. Computed at the chosen station,
at max q, worst case over every lateral command azimuth:

    one port                              4.216 m of altitude error
    three ports, at ANY phasing           0.265 m
    four ports, phased on 0 or 45 deg     0.000 m
    four ports, phased anywhere else      0.024 m   -- this is the roll field getting through

So on the aerodynamics four ports is the better ring, by 0.24 m at max q, which is 0.007 m
at the moment the altimeter is actually read (Finding 3). **Nothing here is a reason to
change the count, and it is not changed.** What the sweep does settle is something that
would not have been visible without it:

**A 4-PORT RING'S CLOCKING IS LOAD-BEARING AND A 3-PORT RING'S IS NOT.** Four ports reject
the roll field only when every port lands on one of its nodes -- the canard planes or their
bisectors -- because with a 4-fold field every port on a 4-port ring sits at the SAME phase
of it, so the ring does not average it at all; it just reads it, at whatever phase it was
clocked to. Three ports reject it at every phasing, structurally. A vehicle that clocked its
four ports at 45 deg to bisect the canard gaps -- which is what the canard module's own
vents do, for a completely unrelated reason (`venting.MODULE_VENT_CLOCKING_DEG`) -- would be
correct by luck, and would stop being correct if anyone ever rotated the pattern.

Three ports is therefore the FORGIVING choice rather than the accurate one, and that is a
better reason for it than the one `venting.py` recorded ("three is the minimum that
averages; four is easier to lay out on a 90 degree pattern"). It is also the choice that
tolerates being got slightly wrong, which is the same thing every other number in that file
is chosen for.

WITH ONE PORT TAPED OVER -- paint, a wasp, a scrap of wadding, which is the case
`venting.CONVENTIONAL_PORT_DIAMETER` is really sized against -- the remaining holes are not
a ring and reject nothing cleanly: three ports degrade to 2.315 m and four to 1.522 m at max
q, against the 4.216 m a single port reads. Four is better here too, and both are under
0.07 m at main deployment. It is the one case where the ring's rejection is worth quoting as
a factor of two rather than as an exact zero, and the honest way to state a ring's
robustness.

CLOCKING, then, is free -- and it is chosen on the one criterion that has a physical
consequence: whether air can reach the hole from inside. `port_mouth_clearances()` measures
each port's inner mouth against everything the sled puts in that cross-section. The sweep is
nearly flat there too (7.89 to 8.62 mm over the whole phase range), so **15 deg is taken for
legibility**: it is within 0.73 mm of the computed optimum, it is a number a person can lay
out on a wrap, and it is the phasing that keeps every port furthest from a canard plane --
15 deg, which is the most a 3-fold ring can get from a 4-fold pattern. Every criterion this
file can compute is nearly flat in phase, and saying that is more useful than dressing one
of them up as the reason.

---------------------------------------------------------------------------------------
FINDING 5. THE ORIFICE EQUATION IN `venting.py` IS THE WRONG MODEL, AND IT DOES NOT MATTER.

`venting.VentedBay.lag()` puts the bay behind a sharp-edged orifice at Cd = 0.62 and a
pressure drop going as v^2. That is the inertial regime, and it is valid above about
Re = 10^4. Drilling the port revealed the flow through it: at the worst case in the whole
flight -- burnout, 177 m/s -- the port Reynolds number is **67**. The flow is laminar
and viscous-dominated, so the drop goes LINEARLY with velocity, not quadratically, and a
4.60 mm deep hole is a short pipe rather than an orifice.

`port_flow_regime()` computes both -- 0.153 Pa and 0.081 Pa, within a factor of two of each
other -- and both are 230 times inside the lag budget, so nothing moves -- which is exactly
what `venting.py` predicted would happen for any argument about port area, and is the
second independent confirmation of it. It is written down because "the model is invalid and
the conclusion is unchanged" is a result, and because the next person to look at a marginal
vent -- the canard module's 2 x dia 2.0 mm, say, which is a tenth of this area -- needs to
know which equation to reach for.

---------------------------------------------------------------------------------------
WHAT THIS FILE DOES NOT DO.

It does not model the ejection transient, which `venting.py` also excludes and which is the
one flow case where the port really is inertial. It does not model the boundary layer: the
position-error models here are inviscid, and a real port reads through a turbulent boundary
layer several millimetres thick, which is a further error of the same order and the wrong
sign to guess at. It does not size the aft coupler in bending -- nothing in this project
does -- so the 0.600 cal bond is a stated floor and not a result. And it says nothing about
the SCREW pattern that retains the same joint, which will want the same 47.64 mm of band the
ports are in; that is the next thing to draw here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import atmosphere, venting

MM = 1000.0

# Air viscosity at the temperatures this flight sees. Sutherland at 250-290 K moves this by
# a few percent and the finding it feeds is a factor of 100, so one number is enough.
AIR_VISCOSITY = 1.79e-5  # Pa.s

# Edge distance from a hole to the end of the bonded band it is drilled in. 1.5 diameters is
# the ordinary fastener rule and it is used here for the same reason -- it is the distance at
# which the material round a hole stops being a ligament and starts being a plate. It is a
# FLOOR; the ports end up with five times it, because the band is centred rather than pushed
# to one end. See PLACEMENT below.
PORT_EDGE_DISTANCE_RATIO = 1.5

# The two rules of thumb the placement has to break, kept as named constants so that the
# violation is reported against a number rather than against a memory.
CONVENTIONAL_AFT_OF_SHOULDER_CAL = 2.0
CONVENTIONAL_FORWARD_OF_DISTURBANCE_CAL = 1.0

# Ring phase, degrees, measured the same way the canards and the module vents are: 0 deg is
# the +X canard plane. 15 deg is derived in Finding 4 and is not a preference -- it is the
# phasing that maximises the minimum angle from a canard plane for a 3-port ring on a 4-fold
# pattern. `ring_phase_optimum()` recomputes it rather than trusting this.
NAV_BAY_PORT_PHASE_DEG = 15.0


# =======================================================================================
# WHAT IS BEHIND THE WALL
# =======================================================================================
@dataclass(frozen=True)
class WallBand:
    """One axial band of a bay's tube, and what is bonded or inserted behind it."""

    name: str
    x0: float          # m, station from the nose tip
    x1: float
    layers: int        # how many walls a drill passes through
    drillable: bool
    why: str

    @property
    def length(self) -> float:
        return self.x1 - self.x0


def nav_bay_wall_bands(rocket, wall: float, joint_list=None) -> list[WallBand]:
    """The nav bay tube, band by band, from what its joints actually occupy.

    This is the function that had to exist before a hole could be drawn, and writing it is
    what produced Finding 1: the bands tile the tube with nothing left over.
    """
    from . import joints as joints_mod

    nav = next(t for t in rocket.tubes if t.name == "nav bay")
    x0 = rocket.nose.length
    x1 = x0 + nav.length
    js = joint_list if joint_list is not None else joints_mod.for_rocket(rocket, wall)

    nose_joint = next(j for j in js if j.aft_bay == "nav bay")
    aft_joint = next(j for j in js if j.forward_bay == "nav bay")

    shoulder_end = x0 + nose_joint.engagement
    anchor_start = x1 - aft_joint.anchor

    bands = [
        WallBand(
            "nose shoulder", x0, shoulder_end, 2, False,
            "the nose joint COMES APART -- a hole through both walls would have to "
            "re-align on every assembly, and the annulus between them is a leak path"),
    ]
    if anchor_start > shoulder_end + 1e-9:
        bands.append(WallBand(
            "bare tube", shoulder_end, anchor_start, 1, True,
            "single wall, nothing behind it"))
    bands.append(WallBand(
        "aft coupler bond", max(anchor_start, shoulder_end), x1, 2, True,
        "tube and coupler bonded into one wall -- drilled after bonding, so it cannot "
        "mis-align, and deburred from inside the nav bay"))
    return bands


def port_band(rocket, wall: float, joint_list=None) -> WallBand:
    """The band the ports have to go in: the longest drillable one."""
    return max((b for b in nav_bay_wall_bands(rocket, wall, joint_list) if b.drillable),
               key=lambda b: b.length)


# =======================================================================================
# POSITION ERROR 1 -- THE NOSE
# =======================================================================================
def _line_source_cp(radius_of, x_max: float, x: float, r: float, panels: int = 2000
                    ) -> float:
    """Incompressible Cp at (x, r) from a body whose forebody radius is `radius_of`.

    Slender-body axisymmetric potential flow: the body is replaced by a line of sources on
    its own axis of strength U * dS/dx, S the cross-sectional area. Aft of `x_max` the body
    is a cylinder, S' = 0, and it contributes nothing -- so the entire pressure field on the
    tube is the tail of the nose's own source distribution.

    Returned per unit freestream, second order retained:  Cp = -2u/U - (u^2 + v^2)/U^2.
    """
    h = x_max / panels
    u = v = 0.0
    for i in range(panels):
        xi = (i + 0.5) * h
        a = max(0.0, xi - 0.5 * h)
        b = min(x_max, xi + 0.5 * h)
        s_prime = (math.pi * radius_of(b) ** 2 - math.pi * radius_of(a) ** 2) / (b - a)
        dx = x - xi
        d2 = dx * dx + r * r
        d3 = d2 * math.sqrt(d2)
        u += s_prime * dx / (4.0 * math.pi * d3) * h
        v += s_prime * r / (4.0 * math.pi * d3) * h
    return -2.0 * u - (u * u + v * v)


def spheroid_validation(fineness: float = 4.0) -> tuple[float, float, float]:
    """Run the same solver on a case with a closed-form answer, and return the shortfall.

    A prolate spheroid in axial flow is the one non-trivial body of revolution whose exact
    potential solution is elementary, and at 4:1 it is the same fineness as this nose. The
    solver is asked for the equator, where the exact surface speed is U(1 + k) with k from
    Lamb's alpha_0.

    Returns (exact Cp, modelled Cp, correction factor to apply). The factor is a MODEL
    property, not a fudge: it is measured once, on a case with an answer, and applied to
    every case without one.
    """
    b = 1.0
    a = fineness * b
    e = math.sqrt(1.0 - (b / a) ** 2)
    alpha0 = (2.0 * (1.0 - e * e) / e ** 3) * (0.5 * math.log((1.0 + e) / (1.0 - e)) - e)
    k = alpha0 / (2.0 - alpha0)
    exact = 1.0 - (1.0 + k) ** 2

    def radius_of(x: float) -> float:
        # solver frame runs 0 -> 2a; spheroid frame is -a -> +a
        t = (x - a) / a
        return b * math.sqrt(max(0.0, 1.0 - t * t))

    modelled = _line_source_cp(radius_of, 2.0 * a, a, b, panels=4000)
    return exact, modelled, exact / modelled


# Measured once by `spheroid_validation()` at the fineness of this nose. Kept as a constant
# so the expensive validation does not run on every call, and asserted against the live
# computation by `check_ports()` so it cannot go stale.
SLENDER_BODY_CORRECTION = 1.167


def prandtl_glauert(mach: float) -> float:
    return 1.0 / math.sqrt(max(1.0 - mach * mach, 1e-6))


def nose_position_error(rocket, x: float, mach: float,
                        correction: float = SLENDER_BODY_CORRECTION) -> float:
    """Cp on the tube at station `x`, from the nose's over-expansion. Negative = suction.

    The port reads this as a pressure error of Cp * q, so an altimeter behind it reads HIGH
    -- it thinks it is above where it is -- by Cp * q / (rho g).
    """
    nose = rocket.nose
    cp = _line_source_cp(nose.radius_at, nose.length, x, rocket.diameter / 2.0)
    return cp * prandtl_glauert(mach) * correction


# =======================================================================================
# POSITION ERROR 2 -- THE CANARDS, WHICH ARE UPSTREAM OF NOTHING AND YET NOT
# =======================================================================================
def _segment_velocity(p, a, b, gamma: float) -> tuple[float, float, float]:
    """Biot-Savart velocity at `p` from a straight vortex filament a -> b."""
    r1 = tuple(p[i] - a[i] for i in range(3))
    r2 = tuple(p[i] - b[i] for i in range(3))
    cx = r1[1] * r2[2] - r1[2] * r2[1]
    cy = r1[2] * r2[0] - r1[0] * r2[2]
    cz = r1[0] * r2[1] - r1[1] * r2[0]
    n2 = cx * cx + cy * cy + cz * cz
    if n2 < 1e-18:
        return (0.0, 0.0, 0.0)
    r0 = tuple(b[i] - a[i] for i in range(3))
    m1 = math.sqrt(sum(c * c for c in r1))
    m2 = math.sqrt(sum(c * c for c in r2))
    k = gamma / (4.0 * math.pi * n2) * (
        sum(r0[i] * r1[i] for i in range(3)) / m1
        - sum(r0[i] * r2[i] for i in range(3)) / m2)
    return (k * cx, k * cy, k * cz)


def canard_circulation(rocket, q: float, deflection_deg: float, cn_alpha: float,
                       speed: float, density: float) -> float:
    """Bound circulation of one fully deflected panel, m^2/s.

    Kutta-Joukowski with uniform spanwise loading: N = rho * U * Gamma * s. Uniform rather
    than elliptic is deliberate -- elliptic loading concentrates circulation inboard, which
    is nearer the port and would read HIGHER, so uniform is the conservative direction only
    for the tip and the optimistic one for the root. The whole term comes out two orders
    below the nose term, which is why this is not refined further.
    """
    c = rocket.canards
    normal = q * c.planform_area_single * cn_alpha * math.radians(deflection_deg)
    return normal / (density * speed * c.semispan)


def command(rocket, gamma: float, roll: float = 0.0, lateral: float = 0.0,
            lateral_azimuth_deg: float = 0.0) -> list[tuple[float, float]]:
    """One control command as (panel azimuth, bound circulation) for every panel.

    `roll` and `lateral` are fractions of `gamma`, which is the circulation of a panel at the
    deflection the caller sized it for. A pure roll deflects all four panels alike; a lateral
    command deflects them as cos(panel - command azimuth), which is the ordinary resolution
    for an interdigitated four-panel set and is what makes a lateral command a k = 1 field
    while a roll command is k = 4.

    Deflections COMBINE on a real vehicle -- the autopilot commands roll and lateral at once
    -- and the sweep in `scripts/port_report.py` walks the lateral azimuth for exactly that
    reason: a ring that rejects two fields separately need not reject their sum, and only
    saying so after checking is honest.
    """
    n = rocket.canards.count
    out = []
    for k in range(n):
        az = k * 360.0 / n
        g = roll + lateral * math.cos(math.radians(az - lateral_azimuth_deg))
        out.append((az, g * gamma))
    return out


def canard_position_error(rocket, x: float, theta_deg: float, gamma: float, speed: float,
                          mode: str = "roll",
                          panels: list[tuple[float, float]] | None = None) -> float:
    """Cp at (x, theta) on the tube from the canards' own upstream field.

    Give `panels` from `command()` for the general case. `mode` is the shorthand for the two
    pure cases: "roll" (all four panels deflected alike -- a 4-fold field) or "pitch" (one
    opposed pair -- a 1-fold field). Each panel is a horseshoe: a bound filament along the
    quarter-chord line from root to tip, and two trailing filaments running aft.

    A straight streamwise filament induces no axial velocity anywhere, so the trailing legs
    contribute nothing to Cp at first order and the whole term is the bound vortex's -- which
    is why this is small, and why it would not have been obvious without computing it.

    NOT MODELLED: the body's image system. A vortex sitting on a cylinder has an image inside
    it, and including it would roughly double this term. It is left out and said so rather
    than half-included; doubling two orders below the leading term changes nothing.
    """
    c = rocket.canards
    body_r = rocket.diameter / 2.0
    qc_root = (c.x_root_le + 0.25 * c.root_chord, body_r)
    qc_tip = (c.x_root_le + c.sweep_length + 0.25 * c.tip_chord, body_r + c.semispan)

    if panels is None:
        if mode == "roll":
            panels = [(a, gamma) for a in (0.0, 90.0, 180.0, 270.0)]
        elif mode == "pitch":
            panels = [(0.0, gamma), (180.0, -gamma)]
        else:
            raise ValueError(f"unknown mode {mode!r}")

    th = math.radians(theta_deg)
    p = (x, body_r * math.cos(th), body_r * math.sin(th))
    trail = 50.0  # m, "downstream infinity" -- 300 body lengths

    u = 0.0
    for panel_deg, g in panels:
        a = math.radians(panel_deg)
        er = (0.0, math.cos(a), math.sin(a))
        root = (qc_root[0], er[1] * qc_root[1], er[2] * qc_root[1])
        tip = (qc_tip[0], er[1] * qc_tip[1], er[2] * qc_tip[1])
        u += _segment_velocity(p, root, tip, g)[0]
        u += _segment_velocity(p, tip, (tip[0] + trail, tip[1], tip[2]), g)[0]
        u += _segment_velocity(p, root, (root[0] + trail, root[1], root[2]), -g)[0]
    return -2.0 * u / speed


# =======================================================================================
# WHAT A RING OF PORTS DOES TO A FIELD -- FINDING 4
# =======================================================================================
def ring_mean(rocket, x: float, clocking_deg, gamma: float, speed: float,
              panels: list[tuple[float, float]]) -> tuple[float, float]:
    """(what the ring reads, what the worst single port in it reads) for one command.

    The ring feeds ONE plenum, so the altimeter sees the mean. The second number is what the
    same holes would have been worth as a single port, and the ratio between them is the only
    honest way to state what a ring buys.
    """
    vals = [canard_position_error(rocket, x, t, gamma, speed, panels=panels)
            for t in clocking_deg]
    return sum(vals) / len(vals), max(vals, key=abs)


def ring_rejects(n_ports: int, harmonic: int) -> bool:
    """Does a ring of `n_ports` equally spaced ports average away circumferential mode k?

    The mean of e^(i k theta) over N equally spaced theta is zero unless N divides k, in
    which case it is the mode's full amplitude. That is the whole content of "ports go in a
    ring", and it is why the count is not free.
    """
    return harmonic % n_ports != 0


def ring_phase_optimum(n_ports: int, n_canards: int) -> float:
    """Ring phase, degrees, that puts every port as far as possible from a canard plane.

    Returns the phase maximising the minimum angular distance from any port to any canard
    plane. For 3 ports on 4 canards this is 15 deg and the minimum distance is 15 deg; there
    is no phasing that does better, which is the honest way to state a constraint you cannot
    satisfy.

    THIS IS A TIEBREAKER AND NOT A REQUIREMENT, and Finding 4 is why: at three ports the
    ring's response to the canards is flat in phase to three figures, and the interior
    clearance is flat to within 0.73 mm, so nothing forces a phasing. 15 deg is taken because
    it is legible, layout-able on a wrap, and derived from a stated rule rather than picked.
    At FOUR ports this function would stop being a tiebreaker and become the requirement --
    the ring only rejects the roll field on the canard planes or their bisectors -- which is
    the asymmetry between the two counts worth remembering.
    """
    step = 360.0 / n_ports
    canard_step = 360.0 / n_canards
    best_phase, best = 0.0, -1.0
    for i in range(3601):
        phase = i * 0.1
        worst = min(
            min(abs((phase + k * step) % canard_step - m * canard_step)
                for m in (0, 1))
            for k in range(n_ports))
        if worst > best + 1e-9:
            best, best_phase = worst, phase
    return best_phase % step


def blocked_port_residual(n_ports: int, harmonic: int) -> float:
    """Fraction of a single port's error that survives with ONE port taped over.

    The reason this is worth a function: a ring's rejection is exact only while every port is
    open, and paint, tape, a wasp or a scrap of wadding is the failure `venting.py` sizes the
    hole diameter against in the first place. With one of N gone the remaining N-1 sample an
    incomplete ring, and for a PURE mode the full ring rejected, the residual is exactly
    1/(N-1) of the amplitude one port alone would have read.

    It is an approximation for the real field, and the size of the approximation is worth
    knowing rather than hiding: swept over every lateral command azimuth at the chosen
    station, the measured residuals are 0.55 (N = 3) and 0.33 (N = 4) against the 0.50 and
    0.33 this returns. The extra is the k = 3 content a real four-panel command carries and a
    pure k = 1 does not.
    """
    if not ring_rejects(n_ports, harmonic) or n_ports < 2:
        return 1.0
    return 1.0 / (n_ports - 1)


# =======================================================================================
# THE HOLE AS A FLOW PASSAGE -- FINDING 5
# =======================================================================================
@dataclass(frozen=True)
class FlowRegime:
    velocity: float
    reynolds: float
    orifice_drop: float     # Pa, venting.py's inertial model
    laminar_drop: float     # Pa, Hagen-Poiseuille through the same hole
    depth: float
    diameter: float

    @property
    def inertial(self) -> bool:
        """Is the sharp-edged orifice equation applicable? It wants Re above ~1e4."""
        return self.reynolds > 1.0e4

    @property
    def length_to_diameter(self) -> float:
        return self.depth / self.diameter


def port_flow_regime(bay: venting.VentedBay, depth: float, altitude: float,
                     climb_rate: float) -> FlowRegime:
    """Both models of the same hole, at the worst flow rate in the flight.

    The bay's demand is the same in either model -- it is set by the volume and by how fast
    ambient is changing -- so the two differ only in what that flow costs in pressure.
    """
    _, p_amb, rho, _ = atmosphere.properties(altitude)
    dpdt = venting.pressure_lapse(altitude) * climb_rate
    volumetric = bay.volume * dpdt / p_amb
    velocity = volumetric / bay.area
    reynolds = rho * velocity * bay.port_diameter / AIR_VISCOSITY

    orifice_v = volumetric / (venting.DISCHARGE_COEFFICIENT * bay.area)
    orifice = 0.5 * rho * orifice_v ** 2
    laminar = 32.0 * AIR_VISCOSITY * depth * velocity / bay.port_diameter ** 2
    return FlowRegime(velocity, reynolds, orifice, laminar, depth, bay.port_diameter)


# =======================================================================================
# PLACEMENT
# =======================================================================================
@dataclass(frozen=True)
class PortPlacement:
    station: float                  # m from the nose tip
    clocking_deg: tuple[float, ...]
    diameter: float
    depth: float
    band: WallBand
    edge_distance: float            # m to the nearer end of the band
    cal_aft_of_shoulder: float
    cal_forward_of_canards: float

    def __str__(self) -> str:
        clocks = "/".join(f"{c:.0f}" for c in self.clocking_deg)
        return (f"{len(self.clocking_deg)} x dia {self.diameter * MM:.1f} mm at station "
                f"{self.station * MM:.2f} mm, clocked {clocks} deg, "
                f"{self.depth * MM:.2f} mm deep")


def place_ports(rocket, wall: float, n_ports: int = venting.CONVENTIONAL_PORT_COUNT,
                diameter: float = venting.CONVENTIONAL_PORT_DIAMETER,
                joint_list=None) -> PortPlacement:
    """Station and clocking for the nav bay's static ports.

    STATION: the centre of the drillable band. Finding 3 is why that is allowed to be the
    rule -- the aerodynamic gradient across the band is worth a fifth of a metre at the
    moment the altimeter is read, and edge distance in a bonded double wall is worth more.

    CLOCKING: `ring_phase_optimum`, which is Finding 4.
    """
    band = port_band(rocket, wall, joint_list)
    station = 0.5 * (band.x0 + band.x1)
    phase = ring_phase_optimum(n_ports, rocket.canards.count)
    clocking = tuple((phase + i * 360.0 / n_ports) % 360.0 for i in range(n_ports))
    depth = band.layers * wall
    return PortPlacement(
        station=station,
        clocking_deg=clocking,
        diameter=diameter,
        depth=depth,
        band=band,
        edge_distance=min(station - band.x0, band.x1 - station),
        cal_aft_of_shoulder=(station - rocket.nose.length) / rocket.diameter,
        cal_forward_of_canards=(rocket.canards.x_root_le - station) / rocket.diameter,
    )


def drilled_volume(hole_radius: float, r_inner: float, r_outer: float,
                   steps: int = 20000) -> float:
    """Material a RADIAL hole removes from a cylindrical shell, m^3. Exact to the quadrature.

    Not pi*a^2*t. A radial hole through a curved wall breaks out over an area larger than its
    own cross-section, because the bore curves away from the drill on both faces. Here that
    is only +0.02%, 18.5017 mm^3 against 18.4977 -- but it is 0.0040 mm^3, which is forty
    times the 0.0001 mm^3 that the four-decimal agreement every CAD check in this project is
    verified to would resolve. A correction too small to matter and too large to ignore is
    exactly the kind that gets spent a session chasing.

    AND THEN IT TURNED OUT THE CAD CANNOT RESOLVE IT EITHER, which is the more useful half.
    This figure agrees with a Monte Carlo integration of the same solid to 0.002 mm^3, so it
    is right. FUSION'S OWN VOLUME OF THE SAME HOLE IS NOT, and it is wrong by clocking:
    asked for the material a drill removes by the two routes that must agree exactly --
    (body - cut body) and (body INTERSECT drill) -- Fusion returns +0.037/-0.017 at 15 deg,
    +0.000/+0.001 at 135 deg, and +0.048/+0.000 at 255 deg. A hole on a 45 deg diagonal is
    exact and one at 15 deg is not, and cutting three in sequence compounds it to 0.12 mm^3
    on the tube and 0.36 on the coupler. So the volume check on a radially-drilled shell is
    worth about 0.05 mm^3 per hole and no more -- against the 0.01 mm^3 that a flat plate
    with eleven holes and a plain annulus both meet exactly. `scripts/make_sled_fusion.py`
    loosens the volume tolerance on those two bodies accordingly and checks the ports by
    FACE instead: count the cylindrical faces at the port radius and read their axes back,
    which is exact, and which tests the thing that was actually asked for -- right number,
    right size, right clocking -- where a volume never did. **The check had a resolution and
    nobody had measured it.** `scripts/make_sled_fusion.py` checks the built tube against
    this figure, so "the ports are cut and the right size" is a number rather than a look.

    Take the hole axis along x, its centre on the shell's mid-plane. A line through the hole
    at offset (y, w) from that axis crosses the wall over

        sqrt(r_outer^2 - y^2) - sqrt(r_inner^2 - y^2)

    which does not depend on w, so the double integral collapses to one dimension:

        V = INT_-a^a  2 sqrt(a^2 - y^2) [sqrt(ro^2 - y^2) - sqrt(ri^2 - y^2)]  dy
    """
    a = hole_radius
    total = 0.0
    for i in range(steps):
        y = -a + (i + 0.5) * 2.0 * a / steps
        chord = 2.0 * math.sqrt(max(a * a - y * y, 0.0))
        depth = math.sqrt(max(r_outer ** 2 - y * y, 0.0)) - math.sqrt(
            max(r_inner ** 2 - y * y, 0.0))
        total += chord * depth
    return total * 2.0 * a / steps


# =======================================================================================
# CAN AIR GET TO THE HOLE FROM INSIDE
# =======================================================================================
def _distance_to_rect(px: float, py: float, r: tuple) -> float:
    x0, x1, y0, y1 = r
    dx = max(x0 - px, 0.0, px - x1)
    dy = max(y0 - py, 0.0, py - y1)
    return math.hypot(dx, dy)


def port_mouth_clearances(placement: PortPlacement, sled_geometry, station_forward: float,
                          bore_radius: float) -> list[tuple[float, str, float]]:
    """(clearance, what is nearest, port clocking) for each port's INNER mouth.

    THE QUESTION NO CHECK IN THIS PROJECT HAD ASKED OF A HOLE: can air reach it. An
    interference check answers whether two solids overlap, and a port that opens 0.2 mm from
    the face of a board is not an interference -- it is a bay that does not breathe. This is
    correction 10's shape ("zero clearance is not an interference") applied to a void instead
    of to a shaft.

    The mouth is taken at `bore_radius`, the INSIDE of the coupler, because that is the plane
    the air has to leave through. Zero or negative means the mouth is inside something.
    """
    from . import sled as sled_mod

    solids = sled_mod.solids_at(sled_geometry, station_forward, placement.station)
    out = []
    for theta in placement.clocking_deg:
        a = math.radians(theta)
        px, py = bore_radius * math.cos(a), bore_radius * math.sin(a)
        best, who = float("inf"), "nothing"
        for name, kind, params in solids:
            if kind == "rect":
                d = _distance_to_rect(px, py, params)
            else:
                cx, cy, r = params
                d = math.hypot(px - cx, py - cy) - r
            if d < best:
                best, who = d, name
        out.append((best, who, theta))
    return out


# =======================================================================================
# THE CHECK
# =======================================================================================
@dataclass
class PortCheck:
    ok: bool
    violations: list[str]
    notes: list[str]


def check_ports(rocket, wall: float, placement: PortPlacement,
                bay: venting.VentedBay, altitude: float, climb_rate: float,
                interior_clearance: float | None = None) -> PortCheck:
    """Everything about these three holes that can fail, and what merely has to be known."""
    v: list[str] = []
    notes: list[str] = []
    n = len(placement.clocking_deg)

    # --- is the hole in a wall that will hold it -------------------------------------
    floor = PORT_EDGE_DISTANCE_RATIO * placement.diameter
    if placement.edge_distance < floor:
        v.append(f"port edge distance {placement.edge_distance * MM:.2f} mm is under the "
                 f"{floor * MM:.2f} mm floor ({PORT_EDGE_DISTANCE_RATIO:.1f} diameters)")
    else:
        notes.append(f"edge distance {placement.edge_distance * MM:.2f} mm each side, "
                     f"{placement.edge_distance / floor:.1f}x the "
                     f"{PORT_EDGE_DISTANCE_RATIO:.1f}-diameter floor")
    if not placement.band.drillable:
        v.append(f"the ports are in the {placement.band.name} band, which is not drillable: "
                 f"{placement.band.why}")
    if placement.band.layers > 1:
        notes.append(f"the port passes {placement.band.layers} walls, "
                     f"{placement.depth * MM:.2f} mm -- {placement.band.name}: "
                     f"{placement.band.why}")

    # --- the harmonics, which is what the count and the clocking really turn on ------
    roll_harmonic = rocket.canards.count       # all four panels alike
    lateral_harmonic = 1                       # panels as cos(panel - command)
    if n < venting.MIN_PORT_COUNT:
        v.append(f"{n} port(s) is under the {venting.MIN_PORT_COUNT} a ring needs to average "
                 f"anything at all")
    notes.append(
        f"{n} ports reject circumferential modes k = "
        + ", ".join(str(k) for k in range(1, 10) if ring_rejects(n, k))
        + f" and pass k = "
        + ", ".join(str(k) for k in range(1, 13) if not ring_rejects(n, k)))
    if ring_rejects(n, roll_harmonic):
        notes.append(
            f"a ROLL command is a k = {roll_harmonic} field and {n} ports reject it AT ANY "
            f"CLOCKING -- which is the argument for {n} rather than {roll_harmonic}: a "
            f"{roll_harmonic}-port ring puts every port at the same phase of a "
            f"{roll_harmonic}-fold field, so it rejects it only where every port lands on a "
            f"node, and its clocking becomes load-bearing")
    else:
        notes.append(
            f"a ROLL command is a k = {roll_harmonic} field and {n} ports do NOT reject it: "
            f"every port sits at the same phase of it, so this ring is only correct where it "
            f"is clocked onto the field's nodes -- the canard planes or their bisectors. "
            f"CLOCKING IS LOAD-BEARING at this port count")
    if not ring_rejects(n, 3) and lateral_harmonic == 1:
        notes.append(
            f"a LATERAL command is odd-harmonic (k = 1, 3, 5 ...) and this ring passes its "
            f"k = 3. That is the dominant residual and it is priced in scripts/port_report.py "
            f"rather than assumed small")
    notes.append(
        f"with ONE port taped over the remainder is not a ring and rejects nothing exactly: "
        f"about {blocked_port_residual(n, 1) * 100:.0f}% of a single port's k = 1 error "
        f"survives, which is the case the {placement.diameter * MM:.1f} mm diameter is "
        f"chosen against")

    # --- the two conventions that cannot be met --------------------------------------
    if placement.cal_aft_of_shoulder < CONVENTIONAL_AFT_OF_SHOULDER_CAL:
        notes.append(
            f"CONVENTION BROKEN, and it cannot be met: {placement.cal_aft_of_shoulder:.2f} "
            f"cal aft of the nose shoulder against the {CONVENTIONAL_AFT_OF_SHOULDER_CAL:.1f} "
            f"cal rule. The nav bay is 1.60 cal long and its forward caliber is the shoulder, "
            f"so no station in the sensed volume can satisfy it")
    if placement.cal_forward_of_canards < CONVENTIONAL_FORWARD_OF_DISTURBANCE_CAL:
        notes.append(
            f"CONVENTION BROKEN, and it cannot be met: "
            f"{placement.cal_forward_of_canards:.2f} cal forward of the canard root against "
            f"the {CONVENTIONAL_FORWARD_OF_DISTURBANCE_CAL:.1f} cal rule. Priced by "
            f"canard_position_error() rather than avoided")

    # --- the solver, against the one case with a known answer ------------------------
    exact, modelled, factor = spheroid_validation(rocket.nose.fineness)
    if abs(factor - SLENDER_BODY_CORRECTION) > 0.02:
        v.append(f"SLENDER_BODY_CORRECTION is {SLENDER_BODY_CORRECTION:.3f} but the live "
                 f"spheroid validation returns {factor:.3f} -- the constant has gone stale")
    else:
        notes.append(
            f"the position-error solver reads {modelled:+.4f} against an exact {exact:+.4f} "
            f"on a {rocket.nose.fineness:.1f}:1 prolate spheroid, so it under-reads |Cp| by "
            f"{(factor - 1.0) * 100:.0f}% and that factor is applied")

    # --- the hole as a flow passage --------------------------------------------------
    regime = port_flow_regime(bay, placement.depth, altitude, climb_rate)
    if regime.inertial:
        notes.append(f"port Re {regime.reynolds:.0f} -- inertial, so venting.py's orifice "
                     f"equation is the right model")
    else:
        notes.append(
            f"port Re {regime.reynolds:.0f} at the worst flow in the flight, so the flow is "
            f"LAMINAR and venting.py's sharp-edged orifice equation is the wrong model. Both "
            f"are computed: orifice {regime.orifice_drop:.3f} Pa, laminar "
            f"{regime.laminar_drop:.3f} Pa through the {regime.depth * MM:.2f} mm depth "
            f"(L/D {regime.length_to_diameter:.2f}), against a "
            f"{venting.lag_pressure(altitude):.1f} Pa budget. Same conclusion either way, "
            f"by a factor of {venting.lag_pressure(altitude) / max(regime.orifice_drop, regime.laminar_drop):.0f}")

    # --- can air actually reach the hole from inside ---------------------------------
    if interior_clearance is not None:
        if interior_clearance <= 0.0:
            v.append(f"a port's inner mouth is blocked: {interior_clearance * MM:.2f} mm to "
                     f"the nearest thing on the sled")
        else:
            notes.append(f"nearest sled solid to any port's inner mouth "
                         f"{interior_clearance * MM:.2f} mm -- the bay can breathe through "
                         f"all {n}")

    return PortCheck(ok=not v, violations=v, notes=notes)
