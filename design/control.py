"""Canard control authority, and the canard/aft-fin interference problem.

Everything here is a linear, quasi-steady estimate. Its purpose is to answer sizing
questions ("can the canards produce 1 g?", "does my net roll moment change sign?") and to
give you the derivatives you will later use to design and simulate the control loop. The
interference factors are the weakest part of the model and must be *measured* in flight,
which is why the flight test plan starts with an open-loop deflection sweep.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import aero, atmosphere
from .geometry import Rocket
from .trajectory import Flight, FlightPoint

STALL_LIMIT_DEG = 12.0


@dataclass
class InterferenceModel:
    """Canard wake effect on the aft fin set.

    downwash_efficiency
        Fraction of canard deflection that appears as an opposing local angle of attack at
        an aft fin immersed in the canard wake. Aligned canards/fins: 0.4 - 0.7.
    span_overlap
        Fraction of aft fin span actually immersed in the canard wake. Aligned (0 deg
        offset): 0.5 - 0.8. Interdigitated (45 deg offset for 4+4): 0.1 - 0.25, because
        the shed vortex pair passes between the aft fins.
    decay_length_cal
        Wake strength decays with canard-to-fin spacing measured in calibers.
    """

    downwash_efficiency: float = 0.55
    span_overlap: float = 0.65
    decay_length_cal: float = 12.0

    @classmethod
    def interdigitated(cls) -> "InterferenceModel":
        return cls(downwash_efficiency=0.45, span_overlap=0.18)

    @classmethod
    def aligned(cls) -> "InterferenceModel":
        return cls(downwash_efficiency=0.55, span_overlap=0.65)

    def strength(self, spacing_cal: float) -> float:
        return self.downwash_efficiency * self.span_overlap * math.exp(
            -spacing_cal / self.decay_length_cal
        )


@dataclass
class Inertia:
    roll: float  # I_xx, kg m^2
    pitch: float  # I_yy = I_zz, kg m^2


@dataclass(frozen=True)
class MeasuredComponent:
    """A component whose inertia is known from CAD or from a swing test.

    `station_from_module_face` keeps this drift-proof: the absolute station is derived
    from the current geometry rather than frozen here, so moving the nav bay does not
    silently invalidate the number.

    `i_transverse` is about the component's OWN centre of mass. `i_roll` is about the
    vehicle roll axis, which is valid only because this component is centred on that axis
    -- its measured CoM is X = Y = 0 to the precision Onshape reports. A component off the
    axis would need its own parallel-axis term in roll too.
    """

    name: str
    mass: float  # kg
    station_from_module_face: float  # m, aft of the canard module's forward face
    i_transverse: float  # kg m^2, about its own CoM
    i_roll: float  # kg m^2, about the vehicle roll axis
    source: str
    # THE GEOMETRY THIS WAS MEASURED ON. A measured tensor is only a measurement of the
    # part that was measured, and nothing in this file noticed when the part changed
    # underneath it -- see `check_measured_geometry` for what that cost. Recorded so the
    # mismatch is detectable instead of silent.
    measured_at_semispan_cal: float = 0.0
    measured_at_thickness: float = 0.0


# Measured in Onshape from the canard module Part Studio, Aug 2026, after the 35.4 deg
# sweep / 0.40 taper reshape. 13 parts: tube section, 4 canard panels, 4 shafts, 4 servo
# envelopes. Onshape reports Ixx = Iyy = 593.524 and Izz = 626.268 kg mm^2 about the
# module CoM, with every off-diagonal term zero -- the four-fold symmetry check passing.
# Read over the REST API, not off a screenshot, which is also how the hinge-station defect
# behind the previous numbers was found. See docs/05.
#
# WHAT THIS DOES NOT INCLUDE is now only wiring and connectors, perhaps 20 g. Servo
# frames, outboard bearings and the printed bay were all on this list at various times and
# all three are resolved: the frames were investigated and dropped (docs/04), the bearings
# went in Aug 2026, and the bay is now real geometry from design/bay.py. Whatever remains
# unmodelled still sits in the crude bulk term below, which smears it over the whole
# airframe instead of concentrating it 324 mm forward of the CG -- but 20 g smeared is a
# different order of error from the 0.29 kg this note used to describe.
# Measured off the ASSEMBLY, not the Part Studio, because the servos are no longer part
# of it: the 23.5 x 8 x 16.8 envelope block has been replaced by real KST X08 Plus
# geometry in its own Part Studio, and the two only share a frame once assembled.
#
# The change from the envelope figures is small but it is all in one direction, and the
# direction is informative. The real servo's mass is not centred on its own body -- the
# output shaft sits 6.14 mm from one case end, not 11.75 -- and it hangs 16.8 mm inboard
# of the wall on the shaft axis rather than 8 mm. So the servo mass moved inboard and aft:
# CoM 74.138 -> 75.090 mm, transverse 593.524 -> 585.266, roll 626.268 -> 612.442
# kg*mm^2. Roll is down 2.2%, which nudges roll acceleration the other way from the 6.5%
# the CAD tensor bought in the first place.
CANARD_MODULE_CAD = MeasuredComponent(
    name="canard module (Fusion assembly, real servos, hinge stack, root tang, 1.45 cal "
         "4.0 mm POINTED-DELTA panels 88.6/8.9 at 42.2 deg LE, four dia 10/12 hinge "
         "bearings, printed bay)",
    mass=0.390847,
    station_from_module_face=0.083694,
    i_transverse=1169.543e-6,
    i_roll=1539.655e-6,
    measured_at_semispan_cal=1.45,
    measured_at_thickness=0.0040,
    source="Fusion CanardControlModule, Sep 2026, re-read after correction 63 rebuilt "
           "Panel0-3 to the pointed-delta outline. Only the four panels changed: the tube "
           "and shafts verified byte-identical, because the outline was solved to hold the "
           "hinge station. 34 bodies in the module set. Geometry MEASURED; MATERIALS "
           "REASSIGNED per body first -- see the note below, which fired twice.",
)
# CORRECTION 63 RE-READ (pointed-delta panels). ONLY THE FOUR PANELS WERE REBUILT -- the
# outline was solved to hold `hinge.canard_hinge_station` to within a nanometre, so the
# tube and the shafts verified byte-identical and nothing on the hinge axis moved.
#
# THE DENSITY TRAP FIRED TWICE IN ONE REBUILD. The new panels came back Steel, as always.
# But so did the SHAFTS and the CANARD BAY, which were never rebuilt -- deleting the four
# panel occurrences (and the joints attached to them) reverted material assignments made
# after those features in the timeline. Reading the tensor there would have given
# 0.598210 kg against a true 0.390847. **Reassign EVERY module body and verify none is
# Steel before reading, not just the ones you rebuilt.** Cross-check: the previous
# measurement plus four panels' growth is 0.386057 + 4 x (21649.3750 - 21002.0135) mm3 x
# 1850 = 0.390847 kg, which is what Fusion reports to six figures.
#
# i_roll went DOWN, 1735.964 -> 1539.655e-6 kg m^2 (-11%), which is the sharper planform
# doing what a sharper planform does: same span, same mass to within 1%, less area outboard.
#
# CORRECTION 62 RE-READ, AND THE DENSITY TRAP FIRED AGAIN EXACTLY AS WRITTEN BELOW.
# The 34-body module came back at 1.574165 kg -- 4.08x the true 0.386057 -- because
# rebuilding a body does not carry its material across and no generator assigns one. The
# five custom materials the previous rebuild created were still in the document, so the fix
# was reassignment rather than re-creation: G10 1850 to tube and panels (and the aft fins
# and booster tube, which are not in this tensor but are in the document), 6061-T6 2700 to
# the shafts, PETG-CF 1300 to the bay and its retainer bars, iglidur G 1450 to the
# bearings. The servo bodies were never rebuilt and kept their 2304 effective density.
#
# CROSS-CHECKED against the repo's own volumes rather than trusted: 4 panels at 21002.0135
# mm3 x 1850, tube 78577.0227 x 1850, 4 shafts at 1032.7638 x 2700, bay 27683.8621 x 1300,
# 8 retainer bars at 90.8076 x 1300, 4 bearings at 204.5134 x 1450, and 4 servos at a
# datasheet 9 g, sums to 0.386054 kg against Fusion's 0.386057. Three parts in a million,
# from two routes that share no arithmetic.
#
# WHAT MOVED, and it is the whole reason this record exists: mass 0.352842 -> 0.386057 kg
# (+9.4%), i_roll 1313.230 -> 1735.964e-6 kg m^2 (+32%). Roll inertia sets the bandwidth
# every control gain is scheduled against, and a 1.45 cal panel puts its mass further out.
# HOW THIS ONE WAS TAKEN, AND THE ONE THING IT IS NOT.
#
# Fusion reports `getXYZMomentsOfInertia` about the WORLD ORIGIN, not about the body's
# centroid -- verified on the spot rather than assumed, because getting it backwards is a
# silent factor-of-anything error: bearing q0 came back with Izz 0.013866 against an
# m*r^2 of 0.013771 kg*cm^2, which is the parallel-axis term and settles it. The document
# frame has Z = 0 at the canard module's forward face, so `station_from_module_face` is
# read straight off it.
#
# EVERY BODY IN THE REBUILT DOCUMENT CAME BACK AS FUSION'S DEFAULT STEEL, 7850 kg/m^3.
# The module weighed 1525.7 g that way against a real 352.8, and reading the tensor without
# noticing would have written a number 4.3x too big into the roll axis this vehicle flies.
# Rebuilding a body does not carry its material across, and nothing in the generators
# assigns one -- so this will happen again on the next rebuild. Check the density before
# trusting a mass, every time; it is the same trap that put steel shafts in the Aug 2026
# tensor (see the shaft note further down).
#
# TAKEN TWICE, BY TWO ROUTES THAT SHARE NO ARITHMETIC, and they agree:
#   1. Rescaled. Mass and inertia are both LINEAR in density at fixed shape, so each body's
#      steel-density figure was multiplied by rho_true/7850 -- exact, not an approximation.
#   2. Measured directly, after assigning real materials to all 39 rebuilt bodies in the
#      document: G10 1850 (configure.material_density) for tube, panels, aft fins and
#      booster; 6061-T6 2700 for the shafts; PETG-CF 1300 (design/bay.py) for the bay and
#      retainer bars; iglidur G 1450 (docs/04) for the bearings; and an effective
#      2304 kg/m^3 across the servo bodies so the four come to the KST X08 Plus datasheet
#      9 g each.
# Route 1 gave 0.352842 kg and route 2 gave 0.352843; the inertias match to the digits
# printed here. The Fusion document now carries those materials, so the next read needs no
# rescaling.
#
# WHAT IS STILL ASSERTED RATHER THAN MEASURED IS THE DENSITY ITSELF. The geometry is the
# assembly's; the densities are the repo's own numbers, and the servo one is a lumped
# effective value that puts the datasheet 9 g into an envelope rather than modelling a
# gear train. A scale settles that, and nothing else does -- docs/01 step 5.
#
# Two checks it passed: the four-fold symmetry, |Ixx - Iyy| = 4e-6 kg*cm^2 about the CoM;
# and Izz about the CoM equals Izz about the roll axis to 3e-12, which it must, because
# the CoM sits on that axis (x, y = 0 to 3e-5 mm).
#
# WHAT MOVED, against the 0.85 cal / 3.2 mm tensor this replaces:
#   mass          298.729 -> 352.842 g      +54.1 g
#   i_roll        673.185 -> 1313.230e-6    +95.1%, very nearly a doubling
#   i_transverse  622.114 ->  992.057e-6    +59.5%
#   station        75.147 ->   81.173 mm    +6.0 mm aft
# The roll number was predicted at +641 kg*mm^2 from the panel geometry alone before the
# rebuild ran, against +640.0 measured. Agreeing to 0.2% is the check that the rebuild
# put the panels where the analysis thinks they are.
# THE VENTS MOVED THIS AND THE MOVE IS NOTHING: -26.7 mg, -0.01% on both inertias, CoM
# forward by 4 microns. Recorded anyway, and re-measured rather than assumed, for the
# reason verify_cad.py exists -- a tensor that is not re-read after a CAD change is a
# number the model and the geometry have quietly stopped sharing. The correct result for a
# vent is that no flight conclusion notices it, which is also what the bearings did
# (correction 18). It is worth knowing which changes are allowed to be invisible.
# TWO CHANGES IN THIS NUMBER, pulling opposite ways, and they are worth separating.
#
#   +38.6 g  THE PRINTED BAY. PETG-CF at R 35-37 mm, nearly the module's full radius, so
#            it buys roll inertia efficiently.
#   -15.4 g  THE SHAFTS WERE MODELLED IN STEEL. Every document said dia 6 6061-T6 and the
#            CAD carried "300 Series Stainless Steel", 7850 against 2700 -- 5.86 g a shaft
#            instead of 1.90. Nothing had ever read the density back, so nothing caught it.
#            scripts/make_spline_socket.py did, and only because it predicts its own mass
#            change from the model's OWN density rather than from a constant. A safety
#            check that reads what is there instead of what it expects finds things the
#            check was not looking for.
#
# Net: 276.999 -> 298.756 g, roll 665.938 -> 673.225 kg mm^2 (+1.1%), transverse +1.4%.
# The two changes very nearly cancelled, which is exactly why a total is a bad place to
# look for an error.
#
# The last gram of that came off in an interference audit, and none of it was about mass:
#   -0.11 g  the collar bore corrected from its AS-PRINTED dia 7.500 to its AS-REAMED
#            dia 8.000. The printed size had a dia 8 bearing inside a dia 7.5 hole, four
#            times over. An assembly is the vehicle that FLIES, and that one is reamed.
#   -0.07 g  the tang's modelling overshoot cut 1.0 -> 0.4 mm. At 1.0 the blade started at
#            R 39.200, inside a wall running 37.400 -> 39.700.
#   -0.13 g  the collar boss stopped reaching for the shell OD. A flat-ended boss on a
#            RADIAL axis has its rim at hypot(reach, OD/2), so reaching R 37.250 put the
#            rim at 37.730 -- inside a tube bored to 37.400.
#   -0.60 g  the retainer bar became a dog bone, because a rectangle long enough to seat
#            an M2 head buried 1.7 mm of itself in the servo case.
#   -0.01 g  the bearing bore opened dia 6.000 -> 6.030, its actual running clearance.
# Onshape's own assembly interference check went 17 pairs -> 0. Every one of those was
# invisible to part count, to mass, and to the axis-aligned bounding box.
#
# WHAT IS LEFT OUT is now small and it is all electrical: wiring, connectors, the servo
# leads, and whatever holds them. Say 20 g. The module was 0.565 kg in the mass budget
# against 0.316 kg here, and the gap that remains is mostly BUDGET CONSERVATISM rather
# than unmodelled hardware -- worth re-reading the budget line rather than assuming the
# CAD is still missing a third of the part.
# Superseded by the line above. The four bearings were the smallest move this tensor has
# ever made: 0.191 g each, 0.765 g total, mass 276.239 -> 276.999 g, roll 664.908 ->
# 665.938 kg mm^2 (+0.15%). Nothing in the flight model noticed, which was the expected
# result -- the bearing was never a mass problem, it is a LOAD-PATH part. The reason to
# model it was interference with the printed bay, and that paid off directly: the bay's
# collar had something to be checked against, and the check found a servo-flange clash.
#   mass 0.276999 kg, station 0.074923 m, Itrans 614.371e-6, Iroll 665.938e-6
# The root tang and the 3.2 mm panel together are the largest single move this tensor has
# made: mass 258.650 -> 276.239 g, ROLL inertia 604.584 -> 664.908 kg mm^2, up 10.0%, and
# transverse 581.280 -> 613.818, up 5.6%. Roll is the axis GV-3 flies and the canard module
# is roughly 11% of vehicle roll inertia, so this one is worth re-reading rather than
# assuming it washes out. It comes from two changes that are not related to each other:
# +17.5 g of aluminium tang hanging at large radius, and -4.6 g cut out of the panel roots
# at even larger radius, on panels that are themselves 0.2 mm thicker.
#   mass 0.258650 kg, station 0.075122 m, Itrans 581.280e-6, Iroll 604.584e-6
#
# Superseded by the line above, kept because the delta is the whole argument for the
# hinge rebuild and it is small: closing the two open fits cost 1.2 g and took roll
# inertia down 1.3%. The shaft went from a dia 5 x 10.8 rod that ran 7.785 mm into the
# servo to a dia 6 x 6.715 sleeve that stops at its output face, the wall bore opened
# from dia 5.000 to dia 7.975 to seat a bearing, and the four servos moved 4 mm inboard.
# Nothing here moved a control conclusion; that is the point of measuring it.
#   mass 0.259864 kg, station 0.075090 m, Itrans 585.266e-6, Iroll 612.442e-6

MEASURED_COMPONENTS: tuple[MeasuredComponent, ...] = (CANARD_MODULE_CAD,)


def check_measured_geometry(
    rocket: Rocket, measured: tuple[MeasuredComponent, ...] = MEASURED_COMPONENTS,
) -> list[str]:
    """Does the CAD these tensors were measured on still describe the current vehicle?

    THIS EXISTS BECAUSE IT DID NOT, AND NOTHING NOTICED. The Sep 2026 freeze took the
    canards from 0.85 to 1.30 cal and 3.2 to 3.6 mm. `CANARD_MODULE_CAD` was still the
    Aug 2026 measurement of the 0.85 cal module, and `estimate_inertia` went on
    superposing it as though it were current -- silently, because a stale measurement
    looks exactly like a fresh one.

    The error is not small and it is not in a quantity nobody uses. Four canard panels
    at 1.30 cal carry +641 kg*mm^2 of roll inertia against a recorded module total of
    673 -- the tensor understates module roll inertia by about 95%, and its mass by 54 g.
    Roll is the axis this vehicle flies, and roll inertia sets the bandwidth every gain
    is scheduled against.

    A measurement cannot be repaired by arithmetic, so this does NOT try to correct the
    number. It reports that the number is no longer a measurement of anything, which is
    the only honest thing available until the module is rebuilt in Fusion and re-read
    over the API (scripts/verify_cad.py).
    """
    out: list[str] = []
    if rocket.canards is None:
        return out
    d = rocket.diameter
    for c in measured:
        if not c.measured_at_semispan_cal:
            continue  # provenance not recorded; nothing to compare against
        now_cal = rocket.canards.semispan / d
        if abs(now_cal - c.measured_at_semispan_cal) > 0.005:
            out.append(
                f"{c.name.split('(')[0].strip()}: tensor measured at "
                f"{c.measured_at_semispan_cal:.2f} cal canards, vehicle now has "
                f"{now_cal:.2f} cal -- roll inertia and pitch bandwidth are running on a "
                f"measurement of a part that no longer exists. Rebuild the module in "
                f"Fusion and re-read it (scripts/verify_cad.py)")
        elif abs(rocket.canards.thickness - c.measured_at_thickness) > 1e-5:
            out.append(
                f"{c.name.split('(')[0].strip()}: tensor measured on a "
                f"{c.measured_at_thickness * 1000:.1f} mm panel, vehicle now has "
                f"{rocket.canards.thickness * 1000:.1f} mm")
    return out


def estimate_inertia(
    rocket: Rocket,
    mass: float,
    cg: float,
    measured: tuple[MeasuredComponent, ...] = MEASURED_COMPONENTS,
) -> Inertia:
    """Vehicle inertia: crude bulk estimate, with measured components superposed.

    Everything without a measurement is still a thin-walled shell in roll and a slender rod
    in pitch, and those are easily 30% off. Components in `measured` are removed from that
    bulk and added back with their real tensor plus a parallel-axis term, which is exact
    superposition rather than a fudge.

    The canard module is worth doing this for. Its own transverse inertia is only about 2%
    of the vehicle pitch inertia -- the parallel-axis term dominates there -- but in ROLL it
    is roughly 11% of the total, because roll inertia scales with radius and four canard
    panels sit at the largest radius on the vehicle. Roll is the axis GV-3 flies, so that
    11% is the difference between a guessed and a known bandwidth.

    Still replace the remainder with a real measurement (bifilar pendulum for roll, swing
    test for pitch) before tuning gains.
    """
    r = rocket.diameter / 2.0
    l = rocket.length
    face = rocket.nose.length + rocket.tubes[0].length  # canard module forward face

    m_measured = sum(c.mass for c in measured)
    m_bulk = max(mass - m_measured, 0.0)

    i_roll = 0.60 * m_bulk * r**2
    # Slender body about its own CG, corrected for CG not being at mid-length.
    i_pitch = m_bulk * l**2 / 12.0 + m_bulk * (cg - l / 2.0) ** 2 * 0.25

    for c in measured:
        station = face + c.station_from_module_face
        i_roll += c.i_roll
        i_pitch += c.i_transverse + c.mass * (station - cg) ** 2

    return Inertia(i_roll, i_pitch)


@dataclass
class AuthorityResult:
    deflection_deg: float
    dynamic_pressure: float
    cm_delta: float  # per rad
    cm_alpha: float  # per rad
    alpha_trim_deg: float
    lateral_accel_g: float
    canard_local_alpha_deg: float
    stalled: bool
    static_margin_cal: float
    pitch_natural_freq_hz: float
    hinge_moment_per_panel: float  # signed: + restoring, - divergent (see packaging.hinge_moment)


def pitch_authority(
    rocket: Rocket,
    point: FlightPoint,
    mass: float,
    deflection_deg: float,
    panels_per_axis: int = 2,
    include_body_lift: bool = True,
) -> AuthorityResult:
    """Trim angle of attack and lateral acceleration for a commanded canard deflection."""
    if rocket.canards is None:
        raise ValueError("rocket has no canards")

    d = rocket.diameter
    delta = math.radians(deflection_deg)
    stab = aero.stability(rocket, point.cg, point.mach, include_body_lift)

    panel_cna = aero.panel_cn_alpha(rocket.canards, d, point.mach)
    cna_control = panels_per_axis * panel_cna
    arm_cal = (point.cg - rocket.canards.cp_station) / d
    cm_delta = cna_control * arm_cal

    cm_alpha = stab.cm_alpha
    alpha_trim = (cm_delta * delta / -cm_alpha) if cm_alpha < 0 else float("inf")

    cn_total = stab.cn_alpha * alpha_trim + cna_control * delta
    lateral_force = point.q * rocket.reference_area * cn_total
    lateral_g = lateral_force / (mass * atmosphere.G0)

    local_alpha = alpha_trim + delta
    inertia = estimate_inertia(rocket, mass, point.cg)
    omega_n = math.sqrt(
        max(-cm_alpha, 1e-9) * point.q * rocket.reference_area * d / inertia.pitch
    )

    from .packaging import hinge_moment

    hm = hinge_moment(
        point.q,
        rocket.canards.planform_area_single,
        rocket.canards.mean_chord,
        panel_cna * rocket.reference_area / rocket.canards.planform_area_single,
        local_alpha,
    )

    return AuthorityResult(
        deflection_deg=deflection_deg,
        dynamic_pressure=point.q,
        cm_delta=cm_delta,
        cm_alpha=cm_alpha,
        alpha_trim_deg=math.degrees(alpha_trim),
        lateral_accel_g=lateral_g,
        canard_local_alpha_deg=math.degrees(local_alpha),
        stalled=math.degrees(local_alpha) > STALL_LIMIT_DEG,
        static_margin_cal=stab.static_margin_cal,
        pitch_natural_freq_hz=omega_n / (2.0 * math.pi),
        hinge_moment_per_panel=hm,
    )


def roll_damping_cl_p(rocket: Rocket, mach: float = 0.0) -> float:
    """Roll damping derivative Cl_p, per radian of the nondimensional roll rate
    p_hat = p*d/(2V). Negative.

    Derivation: a panel whose spanwise centre of pressure sits at radius y sees a local
    velocity increment p*y from the roll, i.e. a local angle of attack p*y/V. That
    produces a force which acts at radius y, so the damping moment scales as y^2. In
    coefficient form, summed over every lifting surface:

        Cl_p = -2 * sum_over_panels[ CNa_panel * (y_cp / d)^2 ]

    Computing this from geometry matters: a hand-waved constant is easily two orders of
    magnitude off, and roll damping is what sets the steady roll rate you have to control.

    TWO CORRECTIONS APPLIED HERE, both found by cross-checking against OpenRocket and
    RocketPy (`scripts/openrocket_roll_check.py`, `sim/probe.py`); together they were a
    factor of 2.15:

    1. `single_fin_cn_alpha`, not `panel_cn_alpha`. Barrowman's fin-set value is
       roll-averaged -- about N/2 fins carry normal force in any one plane at angle of
       attack -- but EVERY fin damps roll, whatever its clocking, because rolling gives them
       all the same local incidence. Dividing the set value by N understated each fin by 2x.
    2. `mean_square_radius`, not `spanwise_cp_radius**2`. Roll damping weights chord by y^2,
       and the square of the area centroid is not the centroid of the square.

    THE STEADY ROLL RATE BARELY MOVED, which is why this went unnoticed. `roll_authority`
    shares correction 1 (it was reading the same `panel_cn_alpha`), and steady roll rate goes
    as Cl_delta/|Cl_p|, so that factor cancels out of the ratio entirely. Only correction 2
    survives it: 12%, not 2.15x. A model can be materially wrong in both numerator and
    denominator and still predict the observable, which is the argument for checking
    derivatives against another code rather than only checking outcomes.
    """
    d = rocket.diameter
    total = 0.0
    for fins in (rocket.aft_fins, rocket.canards):
        if fins is None:
            continue
        panel = aero.single_fin_cn_alpha(fins, d, mach)
        total += fins.count * panel * fins.mean_square_radius / d**2
    return -2.0 * total


@dataclass
class RollResult:
    cl_delta_canard: float
    cl_delta_aftfin: float
    cl_delta_net: float
    reversed_sign: bool
    interference_strength: float
    spacing_cal: float
    roll_accel_deg_s2: float
    steady_roll_rate_deg_s: float
    cl_p: float


def roll_authority(
    rocket: Rocket,
    point: FlightPoint,
    mass: float,
    deflection_deg: float = 5.0,
    interference: InterferenceModel | None = None,
) -> RollResult:
    """Net roll moment derivative from differentially deflected canards.

    The two terms fight each other:
      * canards produce a roll moment directly, at a small moment arm (their span is
        small, because a large canard would destabilize the vehicle);
      * their downwash reduces the local angle of attack on the aft fins, which are much
        larger and at a much bigger moment arm, producing an *opposing* roll moment.

    When the second term wins, commanded roll and actual roll have opposite signs, and any
    feedback loop tuned on the assumed sign will drive the vehicle to its deflection
    limits. This is the failure mode to design out.
    """
    if rocket.canards is None:
        raise ValueError("rocket has no canards")

    d = rocket.diameter
    interference = interference or InterferenceModel.aligned()
    delta = math.radians(deflection_deg)

    spacing_cal = (rocket.aft_fins.cp_station - rocket.canards.cp_station) / d
    strength = interference.strength(spacing_cal)

    # Every canard contributes its full lift slope to roll regardless of clocking, so this
    # is the single-fin slope, not the roll-averaged per-panel share. Same correction as in
    # roll_damping_cl_p, and applying it to only one of the two would be worse than applying
    # it to neither -- the steady roll rate is their ratio.
    canard_panel_cna = aero.single_fin_cn_alpha(rocket.canards, d, point.mach)
    aft_panel_cna = aero.single_fin_cn_alpha(rocket.aft_fins, d, point.mach)

    cl_canard = rocket.canards.count * canard_panel_cna * (
        rocket.canards.spanwise_cp_radius / d
    )
    cl_aft = -strength * rocket.aft_fins.count * aft_panel_cna * (
        rocket.aft_fins.spanwise_cp_radius / d
    )
    cl_net = cl_canard + cl_aft

    inertia = estimate_inertia(rocket, mass, point.cg)
    moment = point.q * rocket.reference_area * d * cl_net * delta
    roll_accel = moment / inertia.roll

    # Steady rate where the control moment balances aerodynamic roll damping:
    #   q*A*d*Cl_delta*delta = q*A*d*(-Cl_p)*(p*d/2V)   =>   p = 2*V*Cl_delta*delta/(d*|Cl_p|)
    cl_p = roll_damping_cl_p(rocket, point.mach)
    speed = max(point.speed, 1.0)
    steady_rate = 2.0 * speed * cl_net * delta / (d * abs(cl_p)) if cl_p != 0 else 0.0

    return RollResult(
        cl_delta_canard=cl_canard,
        cl_delta_aftfin=cl_aft,
        cl_delta_net=cl_net,
        reversed_sign=cl_net * cl_canard < 0,
        interference_strength=strength,
        spacing_cal=spacing_cal,
        roll_accel_deg_s2=math.degrees(roll_accel),
        steady_roll_rate_deg_s=math.degrees(steady_rate),
        cl_p=cl_p,
    )


def achievable_crossrange(
    rocket: Rocket,
    flight: Flight,
    masses,
    deflection_deg: float = 5.0,
    start_after_burnout: float = 0.5,
    duty_cycle: float = 0.7,
) -> tuple[float, float]:
    """Integrate a full-authority one-sided manoeuvre from burnout to apogee.

    Returns (crossrange_m, usable_seconds). `duty_cycle` is a haircut for the fact that a
    real controller does not hold full deflection continuously. This is the number that
    tells you whether "steer to a ground target" is a meaningful goal for your vehicle.
    """
    t_start = flight.burnout_time + start_after_burnout
    usable = [p for p in flight.points if p.t >= t_start and p.q > 300.0]
    if len(usable) < 2:
        return 0.0, 0.0

    v_lateral = 0.0
    crossrange = 0.0
    for prev, cur in zip(usable[:-1], usable[1:]):
        dt = cur.t - prev.t
        mass = cur.mass
        res = pitch_authority(rocket, cur, mass, deflection_deg)
        accel = res.lateral_accel_g * atmosphere.G0 * duty_cycle
        if res.stalled:
            accel *= 0.6  # crude post-stall authority loss
        crossrange += v_lateral * dt + 0.5 * accel * dt * dt
        v_lateral += accel * dt

    # Coast to apogee carries the accumulated lateral velocity.
    t_end = usable[-1].t
    if flight.apogee_time > t_end:
        crossrange += v_lateral * (flight.apogee_time - t_end)
    return crossrange, t_end - t_start


@dataclass
class TurnResult:
    """How far the velocity vector actually turns, which is the thing a missile comparison
    is really about.

    `achievable_crossrange` answers a different question -- how far sideways does it get --
    and the two diverge badly once you start changing speed, because crossrange rewards
    time of flight while heading rate is punished by speed. See `heading_change`.
    """

    heading_deg: float  # total heading change over the usable window
    peak_rate_deg_s: float
    mean_rate_deg_s: float
    min_radius_m: float
    seconds: float
    peak_lateral_g: float
    stalled_anywhere: bool


def heading_change(
    rocket: Rocket,
    flight: Flight,
    deflection_deg: float = 8.0,
    start_after_burnout: float = 0.5,
    duty_cycle: float = 0.7,
) -> TurnResult:
    """Integrate the turn of the VELOCITY VECTOR, not the sideways displacement.

    THIS IS THE NUMBER THE SIDEWINDER COMPARISON NEEDS, and it is not proportional to
    lateral g. A turn rate is

        omega = n * g0 / V

    so speed appears in the numerator of n (through q ~ V^2) and again in the denominator
    here. Doubling the speed quadruples the g and only doubles the turn rate -- and the
    turn RADIUS, V^2/(n g0), does not improve at all if n went up as V^2, because the two
    V^2 terms cancel exactly.

    That is the trap in reading a "we need 3 g" target off a fixed airspeed: if you reach
    the g by flying faster, the g needed for the same heading rate has gone up too. The
    only knobs that buy heading rate for free are the ones that raise CN at fixed speed --
    lower static margin, more canard area, more deflection.

    `duty_cycle` and the q > 300 Pa window match `achievable_crossrange` deliberately, so
    the two functions describe the same manoeuvre and can be quoted side by side.

    LIMIT OF VALIDITY: `flight` is a vertical-plane trajectory flown with no manoeuvre in
    it, so this integrates the turn a vehicle WOULD make against a speed history it did
    not fly. Turning bleeds energy -- induced drag at trim alpha, and gravity once the
    velocity vector leaves the vertical -- so the real heading change is smaller than this,
    and the error grows with the answer. Treat anything past about 45 deg as an upper
    bound and go to `scripts/virtual_flight.py` for the rest.
    """
    t_start = flight.burnout_time + start_after_burnout
    usable = [p for p in flight.points if p.t >= t_start and p.q > 300.0]
    if len(usable) < 2:
        return TurnResult(0.0, 0.0, 0.0, float("inf"), 0.0, 0.0, False)

    heading = 0.0
    peak_rate = 0.0
    peak_g = 0.0
    min_radius = float("inf")
    stalled = False
    for prev, cur in zip(usable[:-1], usable[1:]):
        dt = cur.t - prev.t
        res = pitch_authority(rocket, cur, cur.mass, deflection_deg)
        g_lat = res.lateral_accel_g * duty_cycle
        if res.stalled:
            stalled = True
            g_lat *= 0.6  # same crude post-stall haircut achievable_crossrange applies
        speed = max(cur.speed, 1.0)
        rate = g_lat * atmosphere.G0 / speed  # rad/s
        heading += rate * dt
        peak_rate = max(peak_rate, rate)
        peak_g = max(peak_g, g_lat)
        min_radius = min(min_radius, speed / rate if rate > 0 else float("inf"))

    seconds = usable[-1].t - t_start
    return TurnResult(
        heading_deg=math.degrees(heading),
        peak_rate_deg_s=math.degrees(peak_rate),
        mean_rate_deg_s=math.degrees(heading) / seconds if seconds > 0 else 0.0,
        min_radius_m=min_radius,
        seconds=seconds,
        peak_lateral_g=peak_g,
        stalled_anywhere=stalled,
    )
