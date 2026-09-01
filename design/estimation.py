"""D8 -- what the flight computer can actually know, and when.

`avionics.py` asked whether the boards fit. This asks whether the STATE they produce is
real, which is a different question and the one the controller depends on. `docs/01` step 4
calls state estimation "where most of your interesting engineering lives"; this file is the
part of it that has to be settled BEFORE the schematic, because three of its answers are
free at design time and unrecoverable after layout.

THE CORRECTION THIS FILE EXISTS TO RECORD, and it is in `docs/01` itself.

Step 4.2 prescribes "quaternion state, gyro propagation, accelerometer and magnetometer
corrections **gated on acceleration magnitude** so boost does not corrupt attitude." The
gate does reject boost -- 8.3 g is nowhere near 1 g. Then it OPENS AT BURNOUT, and what it
lets through is the worst measurement in the flight.

At burnout this vehicle's accelerometer reads 1.06 g. It is not gravity. A coasting rocket is in free fall, so the only specific force on it is aerodynamic,
and that force lies along the BODY AXIS. The gate therefore hands the filter a body-axis
vector labelled "down" at exactly the moment the guidance loop opens, and a vehicle 15 deg
off vertical is told it is vertical. It stays open for the whole control window, because
drag decays through 1 g rather than jumping past it.

The heuristic is borrowed from multirotor AHRS work, where a vehicle really does sit at 1 g
in cruise and |a| ~ 1 g really does mean "this is gravity". **A ballistic vehicle never sees
gravity again after it leaves the rail.** So the accelerometer here is a pad-alignment
sensor and an event detector and nothing else, and the gate has to be on FLIGHT PHASE, never
on |a|.

Same shape as correction 1 (the servo was assumed to point inward) and correction 28 (a bay
was assumed to be a box with two faces): a rule that sounds complete, is locally true, and
silently produces the wrong answer. `accel_gate_window()` below computes the window rather
than asserting it, so the finding cannot rot.

WHAT IS OBSERVABLE, WHICH IS THE MODELLING POINT WORTH KEEPING.

An estimator cannot average its way to a state nothing measures. Three of the vehicle's
states are aided by something and one is not:

  * pitch/yaw attitude -- aided, but only by the GNSS VELOCITY VECTOR, and only under a
    small-alpha assumption. That assumption is what 2.11-2.60 cal of static margin buys; it
    is the one place in this project where stability margin shows up as a sensing property.
  * position and altitude -- aided by GNSS and baro respectively, both slow, both lagged.
  * ROLL ANGLE -- aided by NOTHING on the board D7 selected. Specific force is invariant
    under rotation about the axis it points along, so the accelerometer cannot see roll; and
    the velocity vector says where the nose points, not how the vehicle is clocked about it.
    A magnetometer is the only sensor in the class that observes it, and `STM32_BOARD` did
    not have one. L1 -- hold roll angle -- is the project's MINIMUM success criterion.

That is finding 3, and it is the reason this file edits `avionics.py` rather than only
reporting on it.

EVERY NUMBER HERE IS COMPUTED FROM THE FLIGHT MODEL. Sensor error coefficients are the
exception and they are marked: they come off datasheets where a real part is named and are
flagged as estimates where one is not, on the same `measured` discipline `avionics.py` uses.
Do not copy baseline constants in here -- take them through `evaluate()`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import atmosphere

G0 = 9.80665  # m/s^2, and the same constant atmosphere.py uses

# The band a "does |a| look like gravity?" gate would accept. Deliberately generous: a
# tighter band does not rescue the heuristic, it just narrows the window in which it is
# wrong, and the point of computing this is to show that the window is not empty.
GRAVITY_GATE_BAND = (0.8, 1.2)  # in g

# Static port pressure error as a fraction of dynamic pressure. A port on a smooth cylinder
# well aft of the nose shoulder does a few percent; 2% is a working figure for a hand-drilled
# port on a hand-laid tube and is an ESTIMATE, not a measurement. It is the coefficient the
# baro finding is most sensitive to, so it is a named constant rather than a literal.
STATIC_PORT_ERROR_COEFF = 0.02

# What the attitude estimate is allowed to lose to pure arithmetic. 0.5 deg/s is a tenth of
# the gyro-scale-factor term below, which is the right place to put a numerical error: small
# enough that it never leads the budget, large enough not to demand a silly sample rate.
INTEGRATION_ALLOWANCE_DEG_S = 0.5

# Attitude error the vehicle can carry into the manoeuvre and still steer. The canards are
# commanded to +/-8 deg, so a 5 deg attitude error is more than half a deflection's worth of
# pointing; past that the guidance law is correcting its own estimate. A requirement, not a
# measurement, and it is here to be argued with.
ATTITUDE_ERROR_BUDGET_DEG = 5.0

# Is accelerometer attitude aiding used in flight? NO, and this constant exists so that the
# answer is a design decision the check can test rather than a sentence in a document. See
# the module docstring: the |a| gate `docs/01` step 4.2 prescribes opens at burnout and what
# it admits is drag along the body axis. Turning this True fails `check_estimation`, on
# purpose.
ACCEL_ATTITUDE_AIDING = False


# ---------------------------------------------------------------------------------------
# Roll rate, at the deflection that actually applies
# ---------------------------------------------------------------------------------------
# STEADY ROLL RATE IS LINEAR IN DEFLECTION, and that is the whole reason these two helpers
# exist rather than reading `ev.roll_interdig.steady_roll_rate_deg_s` directly. The rate on
# an `Evaluation` is the rate at whatever deflection its caller passed, and until D8 went
# looking, three callers passed three different values: 8 deg in `scripts/baseline.py`,
# `evaluate`'s 6 deg default in `scripts/avionics_trade.py`, and docs/06 printed the 6 deg
# answer under an 8 deg heading. The gyro requirement was written against the middle one.
#
# Roll is commanded at the CAP and pitch at the LIMIT, so the sensing question has two
# answers and both matter: the cap is what the gyro sees in normal operation, and the limit
# is what it sees if the cap is ever lifted or a fault runs the canards to the stops.


def roll_rate_at(ev, deflection_deg: float) -> float:
    """Steady roll rate at an arbitrary deflection, scaled off this Evaluation's own."""
    ref = ev.deflection_deg or 1.0
    return ev.roll_interdig.steady_roll_rate_deg_s * deflection_deg / ref


def capped_roll_rate(ev) -> float:
    """Steady roll rate at the roll command cap -- what the gyro sees in normal operation."""
    from .configure import ROLL_COMMAND_CAP_DEG
    return roll_rate_at(ev, ROLL_COMMAND_CAP_DEG)


def uncapped_roll_rate(ev) -> float:
    """Steady roll rate at the deflection LIMIT -- what it sees if the cap is ever lifted."""
    from .configure import DEFLECTION_LIMIT_DEG
    return roll_rate_at(ev, DEFLECTION_LIMIT_DEG)


# ---------------------------------------------------------------------------------------
# Sensors
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SensorSpec:
    """One sensing element and the error terms that matter over a 17-second flight.

    `measured` carries the same meaning as `avionics.Component.measured`: True means the
    numbers came off a named part's datasheet and the note says which, False means they are
    what a part of this description typically does. Nothing here has been bought.
    """

    name: str
    kind: str  # gyro | accel | mag | baro | gnss
    measured: bool = False
    note: str = ""

    # gyro terms
    full_scale_deg_s: float = 0.0
    bias_deg_s: float = 0.0  # residual bias AFTER pad calibration
    bias_uncal_deg_s: float = 0.0  # what you carry if you skip the pad calibration
    arw_deg_rt_s: float = 0.0  # angular random walk, deg/sqrt(s)
    scale_factor: float = 0.0  # fraction, e.g. 0.005 = 0.5%
    g_sensitivity_deg_s_g: float = 0.0

    # accel terms
    accel_full_scale_g: float = 0.0

    # baro terms
    baro_noise_pa: float = 0.0

    # gnss terms
    rate_hz: float = 0.0
    latency_s: float = 0.0
    cep_m: float = 0.0
    max_dynamics_g: float = 0.0


# --- candidate parts --------------------------------------------------------------------
# Named because a requirement you cannot buy a part against is not a requirement. These are
# the parts the requirements below were checked to be satisfiable by; none is selected, and
# the board only has to meet the REQUIREMENTS, not use these.

GYRO_ICM42688 = SensorSpec(
    "ICM-42688-P gyro", "gyro", measured=True,
    full_scale_deg_s=2000.0, bias_deg_s=0.02, bias_uncal_deg_s=0.5,
    arw_deg_rt_s=0.0028, scale_factor=0.005, g_sensitivity_deg_s_g=0.05,
    note="TDK datasheet: +/-2000 dps max FS, 0.0028 deg/sqrt(s) ARW, +/-0.5% SF tolerance, "
         "32 kHz max ODR. The 0.05 deg/s/g g-sensitivity is a typical figure, not a spec "
         "limit -- it is the one term here that is an estimate")
GYRO_WIDE = SensorSpec(
    "wide-range gyro (+/-4000 dps class)", "gyro",
    full_scale_deg_s=4000.0, bias_deg_s=0.03, bias_uncal_deg_s=1.0,
    arw_deg_rt_s=0.005, scale_factor=0.01, g_sensitivity_deg_s_g=0.1,
    note="ESTIMATED. Wider parts exist and trade noise and scale-factor tolerance for range; "
         "listed to price the 'just buy more range' answer to the saturation problem")

ACCEL_16G = SensorSpec(
    "+/-16 g accelerometer", "accel", measured=True, accel_full_scale_g=16.0,
    note="the standard top range on a 6-axis part; ICM-42688-P among many others")

MAG_MMC5983 = SensorSpec(
    "MMC5983MA magnetometer", "mag", measured=True,
    note="MEMSIC: +/-8 gauss, 0.4 mgauss RMS noise, I2C or SPI, 3 x 3 mm. About $5 in ones. "
         "Range matters more than noise here -- a servo bus transient must not saturate it")

BARO_MS5611 = SensorSpec(
    "MS5611 barometer", "baro", measured=True, baro_noise_pa=1.5,
    note="TE Connectivity: 10 Pa absolute accuracy, ~1.5 Pa RMS at OSR 4096. Sensor noise is "
         "NOT the error term that matters -- see baro_altitude_error()")

GNSS_M10 = SensorSpec(
    "u-blox MAX-M10S", "gnss", measured=True,
    rate_hz=10.0, latency_s=0.15, cep_m=2.0, max_dynamics_g=4.0,
    note="u-blox: 10 Hz nav rate, ~2.0 m CEP, and the 'airborne <4 g' dynamic platform "
         "model is the HIGHEST it offers. The 0.15 s latency is measurement-to-output plus "
         "UART and is an ESTIMATE; it is the term the position lag is most sensitive to")

SENSORS: list[SensorSpec] = [
    GYRO_ICM42688, GYRO_WIDE, ACCEL_16G, MAG_MMC5983, BARO_MS5611, GNSS_M10]


# ---------------------------------------------------------------------------------------
# Finding 1 -- what the accelerometer actually reads
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SpecificForcePoint:
    t: float
    specific_force_g: float
    speed: float
    q: float
    powered: bool


def specific_force_profile(flight) -> list[SpecificForcePoint]:
    """What an ideal accelerometer reads, second by second, in g.

    Specific force is total acceleration minus gravity -- it is what an accelerometer
    measures and it is NOT the same as the vehicle's acceleration. Differentiated from the
    trajectory rather than recomputed from thrust and drag, so it cannot disagree with the
    flight the rest of the project flies.
    """
    pts = flight.points
    out: list[SpecificForcePoint] = []
    for i in range(1, len(pts) - 1):
        p, a, b = pts[i], pts[i + 1], pts[i - 1]
        dt = a.t - b.t
        if dt <= 0.0:
            continue
        # gravity is -z, so the z component of specific force is (dvz/dt) + g
        sf = math.hypot((a.vx - b.vx) / dt, (a.vz - b.vz) / dt + G0)
        out.append(SpecificForcePoint(p.t, sf / G0, p.speed, p.q, p.thrust > 1.0))
    return out


@dataclass(frozen=True)
class GateWindow:
    """When a |a| ~ 1 g gate would be open, and what it would be admitting."""

    opens_at: float
    closes_at: float
    burnout_time: float
    apogee_time: float
    peak_admitted_g: float
    band: tuple[float, float]

    @property
    def duration(self) -> float:
        return max(0.0, self.closes_at - self.opens_at)

    @property
    def opens_after_burnout(self) -> float:
        return self.opens_at - self.burnout_time

    @property
    def is_empty(self) -> bool:
        return self.duration <= 0.0


def accel_gate_window(flight, band: tuple[float, float] = GRAVITY_GATE_BAND) -> GateWindow:
    """The interval in which `docs/01` step 4.2's acceleration-magnitude gate is OPEN.

    If this ever returns an empty window the finding has evaporated and the doc should say
    so. It does not: drag decays smoothly through 1 g a few tens of milliseconds after
    burnout, which is the worst possible time for a wrong attitude reference.
    """
    prof = specific_force_profile(flight)
    lo, hi = band
    inside = [p for p in prof if lo <= p.specific_force_g <= hi and not p.powered]
    if not inside:
        return GateWindow(0.0, 0.0, flight.burnout_time, flight.apogee_time, 0.0, band)
    return GateWindow(
        opens_at=inside[0].t,
        closes_at=inside[-1].t,
        burnout_time=flight.burnout_time,
        apogee_time=flight.apogee_time,
        peak_admitted_g=max(p.specific_force_g for p in inside),
        band=band)


def coast_specific_force(flight, t: float) -> float:
    """Specific force in g at a given time -- for quoting single points in a report."""
    prof = specific_force_profile(flight)
    return min(prof, key=lambda p: abs(p.t - t)).specific_force_g


# ---------------------------------------------------------------------------------------
# Finding 2 -- the rate the attitude has to be integrated at
# ---------------------------------------------------------------------------------------
def integration_drift(rate_deg_s: float, hz: float) -> float:
    """Attitude drift, deg/s, from first-order quaternion propagation alone.

    Propagating q <- q * (1, w*dt/2) and renormalising rotates by 2*atan(|w|*dt/2) rather
    than by |w|*dt. The shortfall is O((w*dt)^3), so it is invisible at hobby rates and
    enormous at this vehicle's roll rate: at the 2378 deg/s the deflection limit allows, a
    100 Hz step is a 23.8 degree rotation and the small-angle assumption underneath the
    propagation is simply false. Quote the rate from `uncapped_roll_rate`, not from memory --
    that is how D7's gyro line came to be written against the wrong deflection.

    This is arithmetic, not sensor error. A PERFECT gyro drifts this much.
    """
    if hz <= 0.0 or rate_deg_s <= 0.0:
        return 0.0
    dt = 1.0 / hz
    x = math.radians(rate_deg_s) * dt
    return math.degrees(x - 2.0 * math.atan(x / 2.0)) * hz


def required_imu_rate(rate_deg_s: float,
                      allowance_deg_s: float = INTEGRATION_ALLOWANCE_DEG_S) -> float:
    """Lowest standard IMU output data rate that keeps `integration_drift` under budget.

    Standard rates only, because an IMU's ODR comes from a divider chain and you cannot ask
    a part for 640 Hz.
    """
    for hz in (100.0, 200.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0):
        if integration_drift(rate_deg_s, hz) <= allowance_deg_s:
            return hz
    return 8000.0


# ---------------------------------------------------------------------------------------
# The attitude error budget
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ErrorTerm:
    source: str
    at_burnout_deg: float
    at_apogee_deg: float
    note: str


@dataclass
class ErrorBudget:
    terms: list[ErrorTerm]
    gyro: SensorSpec
    imu_rate_hz: float
    roll_rate_deg_s: float
    burnout_time: float
    apogee_time: float
    control_seconds: float

    @property
    def total_at_apogee(self) -> float:
        """RSS, because these are independent mechanisms and adding them is pessimistic."""
        return math.sqrt(sum(t.at_apogee_deg ** 2 for t in self.terms))

    @property
    def dominant(self) -> ErrorTerm:
        return max(self.terms, key=lambda t: t.at_apogee_deg)


def attitude_error_budget(ev, gyro: SensorSpec = GYRO_ICM42688,
                          imu_rate_hz: float | None = None,
                          roll_duty: float = 0.25,
                          roll_rate_deg_s: float | None = None) -> ErrorBudget:
    """Every mechanism that moves the attitude estimate, ranked.

    Written as a budget rather than as prose because the ranking is the result and it is not
    the one a tutorial predicts. Bias and random walk -- the two terms every AHRS article
    talks about -- are negligible over 17 seconds. SCALE FACTOR AT HIGH ROLL RATE leads by an
    order of magnitude, and it leads because of the same roll rate that made D7's gyro line
    tight. The two findings have one root cause and one free fix.

    `roll_duty` is the fraction of the coast the vehicle spends near full roll rate. 0.25 is
    a guess with the same standing as `control.achievable_crossrange`'s duty cycle, and the
    scale-factor term is directly proportional to it.
    """
    f = ev.flight
    # The CAPPED rate by default, because that is what the vehicle flies. The IMU rate is
    # sized off the UNCAPPED one, because a sample rate is a layout commitment and it has to
    # survive the canards running to the stops on a fault.
    roll_rate = capped_roll_rate(ev) if roll_rate_deg_s is None else roll_rate_deg_s
    if imu_rate_hz is None:
        imu_rate_hz = required_imu_rate(uncapped_roll_rate(ev))

    t_burn = f.burnout_time
    t_apogee = f.apogee_time
    rolling_burnout = 0.0  # the vehicle is not commanded in roll under boost
    rolling_apogee = ev.control_seconds * roll_duty

    terms = [
        ErrorTerm(
            "gyro bias, pad-calibrated",
            gyro.bias_deg_s * t_burn, gyro.bias_deg_s * t_apogee,
            f"{gyro.bias_deg_s:.3f} deg/s residual after averaging on the rail. Free, and "
            f"mandatory: UNcalibrated it is {gyro.bias_uncal_deg_s:.2f} deg/s, or "
            f"{gyro.bias_uncal_deg_s * t_apogee:.1f} deg by apogee"),
        ErrorTerm(
            "angular random walk",
            gyro.arw_deg_rt_s * math.sqrt(t_burn), gyro.arw_deg_rt_s * math.sqrt(t_apogee),
            f"{gyro.arw_deg_rt_s:.4f} deg/sqrt(s) over sqrt(t). Grows as the square root, so "
            f"a 17 s flight barely starts it"),
        ErrorTerm(
            "gyro scale factor at roll rate",
            0.0, gyro.scale_factor * roll_rate * rolling_apogee,
            f"{gyro.scale_factor * 100:.1f}% of {roll_rate:.0f} deg/s is "
            f"{gyro.scale_factor * roll_rate:.1f} deg/s while rolling, and the vehicle is "
            f"taken as rolling for {rolling_apogee:.1f} s of the {ev.control_seconds:.1f} s "
            f"window. THE DOMINANT TERM, and it is strictly proportional to the roll "
            f"command -- at the {uncapped_roll_rate(ev):.0f} deg/s the deflection limit "
            f"allows it would be "
            f"{gyro.scale_factor * uncapped_roll_rate(ev) * rolling_apogee:.0f} deg"),
        ErrorTerm(
            "gyro g-sensitivity",
            gyro.g_sensitivity_deg_s_g * f.max_acceleration_g * t_burn,
            gyro.g_sensitivity_deg_s_g * f.max_acceleration_g * t_burn,
            f"{gyro.g_sensitivity_deg_s_g:.2f} deg/s/g at {f.max_acceleration_g:.1f} g for "
            f"the {t_burn:.2f} s of boost. Stops accruing at burnout, and it is an error the "
            f"pad calibration cannot see because the pad is at 1 g"),
        ErrorTerm(
            f"integration truncation at {imu_rate_hz:.0f} Hz",
            0.0, integration_drift(roll_rate, imu_rate_hz) * rolling_apogee,
            f"arithmetic, not sensor error -- a PERFECT gyro drifts this much. At 100 Hz and "
            f"the uncapped {uncapped_roll_rate(ev):.0f} deg/s the same term is "
            f"{integration_drift(uncapped_roll_rate(ev), 100.0):.1f} deg/s, which is "
            f"{integration_drift(uncapped_roll_rate(ev), 100.0) * rolling_apogee:.0f} deg "
            f"over the rolling window and would lead every sensor term combined"),
    ]
    return ErrorBudget(terms, gyro, imu_rate_hz, roll_rate, t_burn, t_apogee,
                       ev.control_seconds)


# ---------------------------------------------------------------------------------------
# Baro and GNSS -- the aiding sensors, and what they are actually good for
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class BaroError:
    q: float
    altitude: float
    pressure_error_pa: float
    dp_dh_pa_m: float
    altitude_error_m: float
    noise_error_m: float
    coefficient: float


def baro_altitude_error(q: float, altitude: float,
                        coefficient: float = STATIC_PORT_ERROR_COEFF,
                        sensor: SensorSpec = BARO_MS5611) -> BaroError:
    """Altitude error from static port position error, against sensor noise for scale.

    The point of returning both is the ratio. Sensor noise is fractions of a metre and it is
    what a datasheet comparison would optimise; port error is tens of metres, it scales with
    dynamic pressure, and it therefore CORRELATES WITH VELOCITY -- which means it does not
    look like noise to a filter, it looks like signal. A filter that trusts baro during boost
    will happily fuse it.

    dp/dh is taken from `atmosphere.properties` at the altitude in question rather than from
    a sea-level constant, because it is 12% smaller at apogee than on the pad.
    """
    _, p_lo, _, _ = atmosphere.properties(altitude)
    _, p_hi, _, _ = atmosphere.properties(altitude + 1.0)
    dp_dh = abs(p_hi - p_lo)
    err_pa = coefficient * q
    return BaroError(q, altitude, err_pa, dp_dh, err_pa / dp_dh,
                     sensor.baro_noise_pa / dp_dh, coefficient)


@dataclass(frozen=True)
class GnssLag:
    speed: float
    latency_s: float
    rate_hz: float
    latency_lag_m: float
    sample_lag_m: float
    total_lag_m: float
    cep_m: float
    crossrange_m: float
    exceeds_dynamics: bool
    max_dynamics_g: float
    peak_g: float

    @property
    def lag_fraction_of_crossrange(self) -> float:
        return self.total_lag_m / self.crossrange_m if self.crossrange_m else 0.0


def gnss_position_lag(speed: float, crossrange: float, peak_g: float,
                      sensor: SensorSpec = GNSS_M10) -> GnssLag:
    """How far the vehicle moves between a GNSS fix being valid and being usable.

    Two separate lags and they add: the receiver's own measurement-to-output delay, and the
    half-interval of staleness from a discrete update rate. At 176 m/s both are metres per
    ten milliseconds, and the sum is a real fraction of the crossrange the whole vehicle
    exists to demonstrate. It is correctable -- dead-reckon the fix forward on the IMU, which
    is what the IMU is for -- but only if you know it is there.

    `exceeds_dynamics` is the other half: a receiver's dynamic platform model is an assumption
    it makes about how you move, and this vehicle boosts past the most permissive setting
    u-blox offers.
    """
    lat = speed * sensor.latency_s
    samp = speed * (0.5 / sensor.rate_hz) if sensor.rate_hz else 0.0
    return GnssLag(speed, sensor.latency_s, sensor.rate_hz, lat, samp, lat + samp,
                   sensor.cep_m, crossrange,
                   peak_g > sensor.max_dynamics_g, sensor.max_dynamics_g, peak_g)


# ---------------------------------------------------------------------------------------
# Observability -- the table that makes finding 3 visible instead of arguable
# ---------------------------------------------------------------------------------------
PHASES = ("pad", "boost", "coast", "descent")
STATES = ("roll angle", "body rates", "pitch/yaw attitude", "altitude", "position")

# state -> phase -> what observes it. "-" means nothing does, and the estimator is
# propagating open-loop through that phase. Written out per phase rather than per sensor
# because "the board has a magnetometer" is not the question; "is roll angle observable at
# t = 4 s" is.
OBSERVABILITY: dict[str, dict[str, str]] = {
    "roll angle": {
        "pad": "mag (accel cannot: specific force is along the roll axis)",
        "boost": "mag only",
        "coast": "mag only",
        "descent": "mag only",
    },
    "body rates": {
        "pad": "gyro", "boost": "gyro", "coast": "gyro", "descent": "gyro",
    },
    "pitch/yaw attitude": {
        "pad": "accel (rail angle, and this is its ONLY attitude use)",
        "boost": "-  (specific force is thrust; GNSS lock is not assured past 4 g)",
        "coast": "GNSS velocity vector, under small alpha",
        "descent": "-  (under canopy the body axis and the velocity vector are unrelated)",
    },
    "altitude": {
        "pad": "baro (zero reference)",
        "boost": "-  (static port error scales with q; see baro_altitude_error)",
        "coast": "baro, once q has decayed; GNSS",
        "descent": "baro",
    },
    "position": {
        "pad": "GNSS", "boost": "-  (lock loss expected)", "coast": "GNSS, lagged",
        "descent": "GNSS",
    },
}


# Short forms for the per-phase table, so a report can print a grid without truncating the
# reasons. The long strings above are the ones that carry the argument.
OBSERVABILITY_SHORT: dict[str, dict[str, str]] = {
    "roll angle": {"pad": "mag", "boost": "mag", "coast": "mag", "descent": "mag"},
    "body rates": {"pad": "gyro", "boost": "gyro", "coast": "gyro", "descent": "gyro"},
    "pitch/yaw attitude": {"pad": "accel", "boost": "-", "coast": "GNSS velocity",
                           "descent": "-"},
    "altitude": {"pad": "baro", "boost": "-", "coast": "baro + GNSS", "descent": "baro"},
    "position": {"pad": "GNSS", "boost": "-", "coast": "GNSS, lagged", "descent": "GNSS"},
}


def unobserved(state: str) -> list[str]:
    """Phases in which nothing measures `state`. Empty is the answer you want."""
    return [ph for ph in PHASES if OBSERVABILITY[state][ph].startswith("-")]


# ---------------------------------------------------------------------------------------
# D8 -- THE STATE ESTIMATION TRADE
# ---------------------------------------------------------------------------------------
# WHAT THIS SECTION IS FOR. Same as `avionics.OPTIONS`: price the architectures against what
# this project has already computed, and make the choice a choice. The difference is that
# the sensor set and the ESTIMATOR are separable, and separating them is the decision --
# the board carries everything, and what stages is the software.


@dataclass(frozen=True)
class Architecture:
    """One D8 sensor set, and the highest guidance level it can support."""

    key: str
    name: str
    sensors: tuple[str, ...]
    max_level: str
    cost: float  # USD of parts, above a bare MCU
    note: str


ARCHITECTURES: list[Architecture] = [
    Architecture(
        "A", "IMU only", ("gyro", "accel"), "L1 (null rate)", 12.0,
        "Nulls roll RATE and nothing else. Cannot hold roll ANGLE -- nothing observes it -- "
        "and cannot hold attitude, because after rail exit the accelerometer never sees "
        "gravity again. Enough for GV-3 if L1 is read as rate-nulling, and that reading is "
        "a narrower minimum success criterion than docs/00 states"),
    Architecture(
        "B", "IMU + baro", ("gyro", "accel", "baro"), "L1 + apogee logic", 20.0,
        "Baro buys events -- apogee, altitude, a cross-check against the StratoLoggerCF -- "
        "and buys nothing at all for attitude. Worth having for the safety logic in docs/01 "
        "step 4.5, which is not an estimation argument"),
    Architecture(
        "C", "IMU + baro + GNSS", ("gyro", "accel", "baro", "gnss"), "L3, except roll angle",
        45.0,
        "GNSS is the only in-flight attitude reference this vehicle has, via the velocity "
        "vector under small alpha, and the only source of target-relative position. It still "
        "leaves roll angle unobserved, which is the state L1 is defined on"),
    Architecture(
        "D", "IMU + baro + GNSS + magnetometer",
        ("gyro", "accel", "baro", "gnss", "mag"), "L3", 50.0,
        "SELECTED. Adds the only sensor that observes roll angle, for about $5 and one I2C "
        "address -- if it is on the schematic. docs/01 step 4.2 already ASSUMED a "
        "magnetometer; the board D7 selected did not have one, and nothing had checked"),
]

SELECTED = "D"


def selected_architecture() -> Architecture:
    """Read the selection rather than restating it, so nothing can describe two vehicles."""
    return next(a for a in ARCHITECTURES if a.key == SELECTED)


# The estimator, staged by guidance level. This is the actual decision: the SENSOR SET does
# not stage, because everything on it has to be on the schematic at once, and the SOFTWARE
# does, because each flight in the docs/01 step 6 campaign needs exactly one new thing to
# work. It also means D8 closes without D1 being closed.
STAGES: list[tuple[str, str, str, str]] = [
    ("L0/L1", "GV-1 .. GV-3",
     "pad gyro-bias calibration; gyro-only rate estimate; NO attitude aiding in flight",
     "gyro"),
    ("L2", "GV-4",
     "quaternion propagation at the IMU rate; GNSS-velocity attitude aiding under small "
     "alpha; magnetometer for roll angle",
     "gyro, mag, gnss"),
    ("L3", "GV-5",
     "adds GNSS position dead-reckoned forward through the latency; baro for apogee and "
     "the safety logic",
     "gyro, mag, gnss, baro"),
]


# ---------------------------------------------------------------------------------------
# The check `baseline.py` carries
# ---------------------------------------------------------------------------------------
@dataclass
class EstimationCheck:
    ok: bool
    violations: list[str]
    notes: list[str] = field(default_factory=list)


def check_estimation(ev, gyro: SensorSpec = GYRO_ICM42688,
                     arch: Architecture | None = None) -> EstimationCheck:
    """Everything that has to be true for the state estimate to be worth closing a loop on.

    Written as a check for the reason `check_seal` was: the prose already existed. `docs/01`
    has prescribed an acceleration-gated accelerometer correction since it was written, and
    nothing had ever put a number to what the accelerometer actually reads.

    NOTE ON WHAT IS A VIOLATION HERE, because the first draft of this function got it wrong.
    The gate window and the 26 deg unaided drift are facts about the FLIGHT, not faults in
    the vehicle -- they are true of any rocket this shape and they would have made this check
    permanently red, which is the same as making it invisible. What is checkable is whether
    the ARCHITECTURE answers them: does the sensor set observe the states, is accel attitude
    aiding switched off, is there enough aiding to bound a propagation that on its own does
    not close. So the facts are notes and the design responses are violations, and running
    this against architectures A-C fails them, which is what a trade check is for.
    """
    v: list[str] = []
    notes: list[str] = []

    arch = arch or selected_architecture()
    roll_capped = capped_roll_rate(ev)
    roll_limit = uncapped_roll_rate(ev)
    f = ev.flight

    # --- the sensor set has to observe the states the guidance level needs -------------
    if "mag" not in arch.sensors:
        v.append(
            f"roll angle is unobservable in '{arch.name}': no magnetometer, and specific "
            f"force is invariant under rotation about the axis it lies along. L1 -- hold "
            f"roll angle -- is the project's minimum success criterion")
    if "gnss" not in arch.sensors:
        v.append(
            f"pitch/yaw attitude has no in-flight reference in '{arch.name}': the "
            f"accelerometer cannot supply one (see the gate note below), so the GNSS "
            f"velocity vector is the only aiding this vehicle has")

    for state in STATES:
        blind = unobserved(state)
        if blind:
            notes.append(f"'{state}' propagates open-loop through {', '.join(blind)}")

    # --- accel attitude aiding must be OFF, and this is the correction ------------------
    gate = accel_gate_window(f)
    if not gate.is_empty:
        notes.append(
            f"an |a| ~ {gate.band[0]:.1f}-{gate.band[1]:.1f} g gate would be OPEN from "
            f"t = {gate.opens_at:.2f} s to {gate.closes_at:.2f} s -- "
            f"{'at burnout' if abs(gate.opens_after_burnout) < 0.05 else f'{gate.opens_after_burnout:.2f} s after burnout'}"
            f", for {gate.duration:.1f} s, peaking at {gate.peak_admitted_g:.2f} g -- and "
            f"what it would admit is drag along the BODY AXIS, not gravity")
    if ACCEL_ATTITUDE_AIDING:
        v.append(
            "accelerometer attitude aiding is enabled in flight. A coasting rocket is in "
            "free fall and never sees gravity again after rail exit; the correction would "
            "drive the body axis toward vertical whatever the vehicle is doing. Accel is a "
            "pad-alignment sensor and an event detector -- gate on flight PHASE, not on |a|")

    # --- the gyro has to survive the roll rate, and THE CAP IS WHAT MAKES IT FIT --------
    from .configure import DEFLECTION_LIMIT_DEG, ROLL_COMMAND_CAP_DEG
    if gyro.full_scale_deg_s < roll_capped:
        v.append(
            f"gyro saturates in normal operation: {gyro.name} is "
            f"+/-{gyro.full_scale_deg_s:.0f} deg/s against {roll_capped:.0f} deg/s at the "
            f"{ROLL_COMMAND_CAP_DEG:.0f} deg roll cap. A saturated rate gyro in a roll loop "
            f"is a wrong measurement, not a degraded one, and the controller cannot tell")
    elif gyro.full_scale_deg_s < roll_limit:
        notes.append(
            f"THE ROLL COMMAND CAP IS A SENSING REQUIREMENT, not just a control one. At the "
            f"{ROLL_COMMAND_CAP_DEG:.0f} deg cap the vehicle rolls at {roll_capped:.0f} "
            f"deg/s, {roll_capped / gyro.full_scale_deg_s * 100:.0f}% of {gyro.name}'s "
            f"+/-{gyro.full_scale_deg_s:.0f}. At the {DEFLECTION_LIMIT_DEG:.0f} deg "
            f"deflection LIMIT it rolls at {roll_limit:.0f} deg/s, which is "
            f"{roll_limit / gyro.full_scale_deg_s * 100:.0f}% -- SATURATED. Lifting the cap, "
            f"or a fault that runs the canards to the stops, takes the gyro out of range")
    else:
        notes.append(
            f"gyro in range at both the {ROLL_COMMAND_CAP_DEG:.0f} deg cap "
            f"({roll_capped:.0f} deg/s) and the {DEFLECTION_LIMIT_DEG:.0f} deg limit "
            f"({roll_limit:.0f} deg/s)")

    # --- arithmetic must not lead the budget -------------------------------------------
    need_hz = required_imu_rate(roll_limit)
    at_100 = integration_drift(roll_limit, 100.0)
    if at_100 > INTEGRATION_ALLOWANCE_DEG_S:
        notes.append(
            f"IMU output data rate must be at least {need_hz:.0f} Hz: first-order quaternion "
            f"propagation at 100 Hz drifts {at_100:.1f} deg/s at the {roll_limit:.0f} deg/s "
            f"the deflection limit allows, with a PERFECT gyro. THIS IS NOT THE CONTROL LOOP "
            f"RATE, which is {ev.pitch.pitch_natural_freq_hz * 20:.0f} Hz -- a board built "
            f"to the control loop rate would be built ten times too slow")

    # --- unaided propagation does not close, so the aiding is load-bearing --------------
    budget = attitude_error_budget(ev, gyro)
    if budget.total_at_apogee > ATTITUDE_ERROR_BUDGET_DEG:
        notes.append(
            f"UNAIDED propagation reaches {budget.total_at_apogee:.1f} deg RSS by apogee "
            f"against a {ATTITUDE_ERROR_BUDGET_DEG:.1f} deg budget, led by "
            f"'{budget.dominant.source}' at {budget.dominant.at_apogee_deg:.1f} deg. The "
            f"aiding is load-bearing, not a refinement. That is already WITH the roll "
            f"command capped; at the deflection limit the same term is "
            f"{budget.dominant.at_apogee_deg * roll_limit / roll_capped:.0f} deg")
        if not ({"mag", "gnss"} & set(arch.sensors)):
            v.append(
                f"'{arch.name}' has no attitude aiding at all, and unaided propagation "
                f"reaches {budget.total_at_apogee:.1f} deg by apogee against a "
                f"{ATTITUDE_ERROR_BUDGET_DEG:.1f} deg budget")

    return EstimationCheck(not v, v, notes)
