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


# Measured in Onshape from the canard module Part Studio, Aug 2026, after the 35.4 deg
# sweep / 0.40 taper reshape. 13 parts: tube section, 4 canard panels, 4 shafts, 4 servo
# envelopes. Onshape reports Lxx = Lyy = 601.588 and Lzz = 623.179 kg mm^2 about the
# module CoM, with every off-diagonal term zero -- the four-fold symmetry check passing.
#
# WHAT THIS DOES NOT INCLUDE, and it matters: the servo frames, outboard bearings and the
# printed bay are not modelled yet, so the CAD module is 0.260 kg against roughly 0.565 kg
# in the mass budget. The missing ~0.3 kg stays in the crude bulk term below, which smears
# it over the whole airframe instead of concentrating it here. That UNDERSTATES the pitch
# inertia, because the real hardware sits 324 mm forward of the CG where the parallel-axis
# term is large. Re-measure once the printed bay exists.
CANARD_MODULE_CAD = MeasuredComponent(
    name="canard module (CAD, 13 parts)",
    mass=0.2604,
    station_from_module_face=0.072418,
    i_transverse=601.588e-6,
    i_roll=623.179e-6,
    source="Onshape canard-control module, Part Studio 1, Aug 2026",
)

MEASURED_COMPONENTS: tuple[MeasuredComponent, ...] = (CANARD_MODULE_CAD,)


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
    """
    d = rocket.diameter
    total = 0.0
    for fins in (rocket.aft_fins, rocket.canards):
        if fins is None:
            continue
        panel = aero.panel_cn_alpha(fins, d, mach)
        total += fins.count * panel * (fins.spanwise_cp_radius / d) ** 2
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

    canard_panel_cna = aero.panel_cn_alpha(rocket.canards, d, point.mach)
    aft_panel_cna = aero.panel_cn_alpha(rocket.aft_fins, d, point.mach)

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
