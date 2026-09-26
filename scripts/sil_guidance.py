"""Software-in-the-loop, L2 and L3: attitude hold, and guidance to a ground target.

    python scripts/sil_guidance.py [--no-mag] [--seed N] [--wind 8]

`scripts/sil_demo.py` closes L1 (roll hold) and demonstrates bank-to-turn open-loop on the
pitch channel. This script closes the two levels above it, from docs/00 section 1.1:

  L2  ATTITUDE HOLD -- hold a commanded pitch attitude against a crosswind that would
      otherwise weathercock the vehicle. This is the first thing in the project that needs
      attitude to be a STATE rather than an assumption.
  L3  GUIDANCE TO A GROUND TARGET -- bank-to-turn onto a commanded ground point and null the
      crossrange error, against the same airframe and the same deflection limits.

WHY THIS NEEDED NEW PHYSICS, and what that says about the L1 result. `sil_demo.py` sets the
body axis equal to the velocity direction (`body = vel / speed`): the vehicle is assumed to
weathercock instantly and fly at whatever trim angle of attack the canards command. That is
a fair assumption for L1 -- roll is decoupled from it -- and it is why L1 could be closed
without an attitude state at all. It is NOT fair for L2, because "hold an attitude against
wind" is precisely a question about the difference between where the vehicle points and where
it is going. So here pitch and yaw are real second-order states:

    I_pitch * omega_dot = q*A*d*( Cm_alpha*alpha + Cm_delta*delta + Cm_q*omega*d/(2V) )

with `Cm_alpha` from `aero.stability`, `Cm_delta` from `control.pitch_authority`, and
`Cm_q` from `control.pitch_damping_cm_q` -- which was added for this script and has never
been cross-checked against another code (see its docstring).

THE NUMBER THAT SHAPES BOTH LOOPS: the damping ratio is 0.079 at max q. The pitch mode is
3.6 Hz and almost undamped, so a proportional attitude loop rings for about 2 s. Both
controllers here therefore use rate feedback, and the rate gain is not optional -- setting
`--kd 0` reproduces the oscillation, which is the point of leaving the flag in.

WHAT THIS DOES NOT PROVE -- everything `sil_demo.py`'s list says, which all still applies
(wake interference unvalidated, not hardware-in-the-loop, no embedded timing), plus:
  * Pitch and yaw are treated as two independent planes. That is a small-angle
    approximation; it drops the gyroscopic and inertial cross-coupling a rolling vehicle
    has, which is exactly what bank-to-turn excites. It is honest for the +/-2 deg roll
    commands R13 allows and NOT honest for a fast 90 deg roll -- so L3's numbers here are
    the guidance law's, not the airframe's last word.
  * `Cm_q` is unverified, and the damping ratio is proportional to it.
  * The wind is a steady, uniform, horizontal crossflow with no gust spectrum and no
    altitude profile. A real gust is the harder case for L2.
  * No canard/aft-fin interference on the PITCH channel at all -- `pitch_authority` has
    never modelled it, and this script inherits that.
  * L3 steers the velocity vector; it does not integrate a ballistic impact prediction.
    "Guidance to a ground target" here means nulling the heading error to the target while
    control authority lasts, which is what this airframe can physically do (docs/00 1.1).
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import atmosphere, aero, control, estimation
from design.configure import DEFLECTION_LIMIT_DEG, ROLL_COMMAND_CAP_DEG, baseline, evaluate
from design.estimation import GYRO_ICM42688, MAG_MMC5983
from design.horizontal import ALTITUDE_FLOOR_M, Q_MIN
from design.mass import cg_at_time
from design.packaging import SERVOS
from design.trajectory import FlightPoint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
PLOT_PATH = OUT / "sil_guidance.png"
REPORT_PATH = OUT / "sil_guidance.txt"

G0 = atmosphere.G0
SLEW_DEG_S = 60.0 / SERVOS["kst_x08_plus"].speed_60deg
R12_LATENCY_S = 0.5
RAIL_LENGTH_M = 3.66
RAIL_HEIGHT_M = 2.0

# Attitude-loop gains. Kp is deg of canard per deg of attitude error; Kd is deg of canard per
# deg/s of body rate. Kd is sized from the damping ratio: the aero gives zeta = 0.079, and the
# rate loop has to supply the rest, so Kd ~ 2*(zeta_target - zeta_aero)*wn / (control power
# per deg). 0.35 lands zeta near 0.6 at max q and is deliberately NOT retuned per case --
# gain scheduling is a firmware decision this script has no business pre-empting.
ATT_KP = 1.2
ATT_KD = 0.35
ROLL_KP, ROLL_KD = control.ROLL_KP, control.ROLL_KD   # roll_bandwidth.py section 4

# L3: how much heading error commands full bank. 20 deg of error -> 90 deg of bank.
# L3 steers the predicted impact point. Gain is deg of bank per metre of crosstrack miss:
# 90 deg of bank for a 60 m miss, so the loop saturates early and eases off on approach.
L3_CROSSTRACK_TO_BANK = 1.5
L3_BANK_MAX_DEG = 90.0
L3_CAPTURE_M = 25.0   # crosstrack miss counted as captured, metres


def wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def slew(cur_deg: float, cmd_deg: float, dt: float, rate_deg_s: float = SLEW_DEG_S) -> float:
    err = cmd_deg - cur_deg
    return cur_deg + max(-rate_deg_s * dt, min(rate_deg_s * dt, err))


@dataclass
class GuidanceCase:
    label: str
    mode: str
    samples: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def predict_impact(pos, vel, rocket, mass, dt=0.05, max_t=60.0):
    """Ballistic impact point of the current state, drag included, canards neutral.

    This is the OBSERVABLE L3 actually steers. docs/00 1.1 defines L3 as "bias attitude to
    steer the impact/apogee point toward a commanded lat/lon" -- the impact point, not the
    instantaneous bearing to the target. The difference is not academic: pure pursuit on
    bearing was tried first here and cannot capture anything, because a coasting rocket flies
    a ballistic arc it cannot extend, so the bearing to a fixed ground point runs away from it
    while it turns. Steering the predicted impact point converges; chasing the target does not.

    Deliberately crude -- point mass, zero angle of attack, `aero.drag_coefficient` at the
    current altitude, 20 Hz. It is a predictor inside a control loop, not a trajectory tool,
    and its errors are what the loop closes against. Flight firmware would run exactly this
    kind of cheap forward propagation.
    """
    p = np.array(pos, dtype=float)
    v = np.array(vel, dtype=float)
    t = 0.0
    while p[2] > 0.0 and t < max_t:
        sp = float(np.linalg.norm(v))
        if sp > 1.0:
            z = max(float(p[2]), 0.0)
            cd = aero.drag_coefficient(rocket, sp, z)
            q = 0.5 * atmosphere.density(z) * sp * sp
            a = -(q * cd * rocket.reference_area / mass) * (v / sp)
        else:
            a = np.zeros(3)
        a = a + np.array([0.0, 0.0, -G0])
        v = v + a * dt
        p = p + v * dt
        t += dt
    return float(p[0]), float(p[1])


def _orthonormalize(b, e1):
    """Gram-Schmidt a body triad back to orthonormal after an Euler step."""
    b = b / np.linalg.norm(b)
    e1 = e1 - float(np.dot(e1, b)) * b
    e1 = e1 / np.linalg.norm(e1)
    return b, e1, np.cross(b, e1)


def run(rocket, motor, masses, ev, *, mode: str, label: str, elevation_deg: float,
        wind_mps: float = 0.0, target_xy: tuple[float, float] | None = None,
        seed: int = 0, mag_aiding: bool = True, dt: float = 0.004, max_time: float = 40.0,
        att_kp: float = ATT_KP, att_kd: float = ATT_KD,
        start_after_burnout: float = 0.5) -> GuidanceCase:
    """One flight. `mode` is 'l2' (attitude hold) or 'l3' (guide to `target_xy`).

    ATTITUDE IS A ROTATING BODY TRIAD (b, e1, e2), not Euler angles, and that is not a
    stylistic choice -- the first version of this script used body elevation/azimuth and an
    85 deg flight reported 68 deg of yaw "drift" that was pure coordinate singularity:
    azimuth is ill-conditioned when the body is near vertical, which is exactly the attitude
    R15's vertical mode flies and exactly the case L2 is specified against. A triad has no
    singular orientation.

        b   body axis, nose forward
        e1  pitch axis (starts along +y, horizontal and normal to the rail plane)
        e2  = b x e1, the nose-up direction at zero roll

    (e1, e2, b) is right-handed, so a moment about e1 rotates b toward e2 (nose up) and a
    moment about e2 rotates b toward e1 (nose to +y). Roll rotates e1 and e2 about b, which
    is what makes bank-to-turn come out of the frame rather than out of a projection factor
    applied by hand.
    """
    rng = np.random.default_rng(seed)
    out = GuidanceCase(label=label, mode=mode)
    d, area = rocket.diameter, rocket.reference_area
    el0 = math.radians(elevation_deg)
    rail_dir = np.array([math.cos(el0), 0.0, math.sin(el0)])
    steer_start = motor.burn_time + start_after_burnout
    wind = np.array([0.0, wind_mps, 0.0])

    aided = estimation.mag_aided_roll_error(ev, roll_rate_deg_s=31.0)
    tau_mag = aided.tau_s
    mag_noise_deg = math.degrees(math.atan2(MAG_MMC5983.mag_noise_gauss,
                                            estimation._field_perp()))
    gyro_sigma = GYRO_ICM42688.arw_deg_rt_s / math.sqrt(dt)

    t = 0.0
    pos = np.array([0.0, 0.0, RAIL_HEIGHT_M])
    vel = np.zeros(3)
    on_rail = True
    b = rail_dir.copy()
    e1 = np.array([0.0, 1.0, 0.0])
    b, e1, e2 = _orthonormalize(b, e1)
    b_cmd = rail_dir.copy()          # L2 holds the rail attitude
    omega = np.zeros(3)              # body angular velocity, rad/s, world frame
    roll_true = 0.0
    p_true = 0.0
    roll_est = 0.0
    att_err_est = np.zeros(3)        # integrated gyro estimate of the attitude error vector
    pitch_act = yaw_act = roll_act = 0.0
    interference = control.InterferenceModel.interdigitated()

    apogee_z = 0.0
    peak_bank = 0.0
    captured_t = None
    impact = (0.0, 0.0)
    last_predict = -1e9
    predict_every = 0.1   # guidance runs the predictor at 10 Hz, not every step
    max_alpha_deg = 0.0
    max_alpha_ctl = 0.0
    max_alpha_exit = 0.0
    stall_seconds = 0.0
    peak_att_err = 0.0

    while t < max_time:
        z = float(pos[2])
        v_rel = vel - wind
        speed = float(np.linalg.norm(v_rel))
        rho = atmosphere.density(max(z, 0.0))
        sound = atmosphere.speed_of_sound(max(z, 0.0))
        mass = masses.dry_mass + max(motor.mass_at(t) - motor.dry_mass, 0.0)
        thrust = motor.thrust(t)
        cg = cg_at_time(masses, motor, t, rocket)
        q = 0.5 * rho * speed * speed
        mach = speed / sound if sound > 1.0 else 0.0

        if on_rail:
            b, e1, e2 = _orthonormalize(rail_dir.copy(), np.array([0.0, 1.0, 0.0]))
            omega = np.zeros(3)

        # angle of attack: the angle between the body axis and the RELATIVE wind
        if speed > 1.0:
            vhat = v_rel / speed
        else:
            vhat = b.copy()
        cos_a = max(-1.0, min(1.0, float(np.dot(b, vhat))))
        alpha = math.acos(cos_a)
        alpha_deg = math.degrees(alpha)
        # the control window is the only place alpha means anything: on the rail the vehicle
        # is constrained, and past apogee at q < Q_MIN the flight path swings through 180 deg
        # while the body cannot follow, which is real but far outside this model's validity.
        in_window = (not on_rail) and q >= Q_MIN
        if in_window:
            max_alpha_deg = max(max_alpha_deg, alpha_deg)
            if t >= steer_start:
                # the CONTROLLED phase. Before it, alpha is whatever the rail exit and the
                # wind hand the vehicle and no controller is running -- counting that as a
                # control-law stall would be measuring the weather.
                max_alpha_ctl = max(max_alpha_ctl, alpha_deg)
                if alpha_deg > control.STALL_LIMIT_DEG:
                    stall_seconds += dt
            else:
                max_alpha_exit = max(max_alpha_exit, alpha_deg)

        # attitude error to the commanded axis, as a rotation vector (b -> b_cmd)
        err_vec = np.cross(b, b_cmd)
        att_err_deg = math.degrees(math.asin(min(1.0, float(np.linalg.norm(err_vec)))))
        if in_window and t >= steer_start:
            peak_att_err = max(peak_att_err, att_err_deg)

        # ---- sensors: rate gyro on all three body axes ---------------------------------
        p_meas = (p_true * (1.0 + GYRO_ICM42688.scale_factor) + GYRO_ICM42688.bias_deg_s
                  + rng.normal(0.0, gyro_sigma))
        roll_est += p_meas * dt
        if mag_aiding and tau_mag > 0:
            k = 1.0 - math.exp(-dt / tau_mag)
            roll_est += k * wrap180(roll_true + rng.normal(0.0, mag_noise_deg) - roll_est)
        # The attitude estimate is truth plus a gyro-integration error that grows with time
        # since the last aiding, rather than a full quaternion filter: docs/07 owns the
        # estimator and a second unvalidated copy here would be worse than none. What this
        # DOES model is that the loop closes on a noisy, biased estimate, not on truth.
        est_age = max(t - steer_start, 0.0)
        att_bias_deg = GYRO_ICM42688.bias_deg_s * est_age
        err_noise = np.array([rng.normal(0.0, gyro_sigma * dt) for _ in range(3)])
        err_meas = err_vec + math.radians(att_bias_deg) * e1 + np.radians(err_noise)
        om_meas = omega + np.array(
            [rng.normal(0.0, math.radians(gyro_sigma)) for _ in range(3)])

        # ---- guidance -----------------------------------------------------------------
        gate = (not on_rail) and q >= Q_MIN and t >= steer_start
        pitch_nom = yaw_nom = roll_nom = 0.0
        bank_cmd = 0.0
        head_err = 0.0
        if gate:
            if mode == "l2":
                # PD on the two body planes: the error vector's e1 component is a pitch
                # error, its e2 component a yaw error. Rate feedback off the body rates.
                e_pitch = math.degrees(float(np.dot(err_meas, e1)))
                e_yaw = math.degrees(float(np.dot(err_meas, e2)))
                r_pitch = math.degrees(float(np.dot(om_meas, e1)))
                r_yaw = math.degrees(float(np.dot(om_meas, e2)))
                pitch_nom = att_kp * e_pitch - att_kd * r_pitch
                yaw_nom = att_kp * e_yaw - att_kd * r_yaw
            else:
                tx, ty = target_xy
                # Steer the PREDICTED IMPACT POINT, not the bearing to the target. Only the
                # CROSSTRACK component of the miss is controllable: a coasting rocket cannot
                # lengthen or shorten its arc much, which is docs/00 1.1's whole point about
                # crossrange being the limited quantity.
                if predict_every <= 0 or (t - last_predict) >= predict_every:
                    impact = predict_impact(pos, vel, rocket, mass)
                    last_predict = t
                miss = np.array([tx - impact[0], ty - impact[1]])
                gnd = np.array([float(vel[0]), float(vel[1])])
                gn = float(np.linalg.norm(gnd))
                if gn > 1.0:
                    # +crosstrack means the target is to the LEFT of the ground track (+y side)
                    left = np.array([-gnd[1], gnd[0]]) / gn
                    crosstrack = float(np.dot(miss, left))
                else:
                    crosstrack = 0.0
                head_err = crosstrack   # reported in metres for L3, not degrees
                bank_cmd = max(-L3_BANK_MAX_DEG,
                               min(L3_BANK_MAX_DEG, L3_CROSSTRACK_TO_BANK * crosstrack))
                if abs(crosstrack) <= L3_CAPTURE_M and captured_t is None:
                    captured_t = t
                roll_nom = max(-ROLL_COMMAND_CAP_DEG,
                               min(ROLL_COMMAND_CAP_DEG,
                                   ROLL_KP * wrap180(bank_cmd - roll_est) - ROLL_KD * p_meas))
                # Pull on the PITCH pair once bank is roughly established. The frame does the
                # rest: e1/e2 have rolled with the vehicle, so a pitch-axis moment now turns
                # the velocity vector sideways. No projection factor applied by hand.
                if abs(wrap180(bank_cmd - roll_est)) < 30.0:
                    pitch_nom = DEFLECTION_LIMIT_DEG

        if z < ALTITUDE_FLOOR_M and vel[2] < 0.0 and not on_rail:
            pitch_nom = yaw_nom = roll_nom = 0.0   # R12 terminal clause

        lim = DEFLECTION_LIMIT_DEG
        pitch_act = slew(pitch_act, max(-lim, min(lim, pitch_nom)), dt)
        yaw_act = slew(yaw_act, max(-lim, min(lim, yaw_nom)), dt)
        # Roll gets the lagged servo; pitch/yaw are still slew-only (their gains are untested
        # against servo lag -- docs/15).
        roll_act = control.servo_step(roll_act, roll_nom, dt, SLEW_DEG_S)

        # ---- aerodynamic moments, as vectors -------------------------------------------
        stab = aero.stability(rocket, cg, mach)
        cm_alpha = stab.cm_alpha
        cm_q = control.pitch_damping_cm_q(rocket, cg, mach)
        panel_cna = aero.panel_cn_alpha(rocket.canards, d, mach)
        cm_delta = 2 * panel_cna * (cg - rocket.canards.cp_station) / d
        inertia = control.estimate_inertia(rocket, mass, cg)

        if not on_rail and q > 20.0 and speed > 1.0:
            qAd = q * area * d
            M = np.zeros(3)
            # static restoring: about (vhat x b), which rotates b back toward vhat. cm_alpha
            # is negative for a stable vehicle, so this comes out restoring without a sign
            # flip anywhere -- see the class docstring in design/aero.StabilityResult.
            axis = np.cross(vhat, b)
            na = float(np.linalg.norm(axis))
            if na > 1e-9:
                M += qAd * cm_alpha * alpha * (axis / na)
            # control: pitch pair about e1, yaw pair about e2
            M += qAd * cm_delta * math.radians(pitch_act) * e1
            M += qAd * cm_delta * math.radians(yaw_act) * e2
            # damping: opposes the transverse rate, cm_q negative
            om_perp = omega - float(np.dot(omega, b)) * b
            M += qAd * cm_q * (om_perp * d / (2.0 * speed))
            omega = omega + (M / inertia.pitch) * dt

        # ---- roll axis: same exact analytic step sil_demo uses --------------------------
        if not on_rail and q > 50.0 and speed > 1.0:
            pt = FlightPoint(t=t, x=float(pos[0]), z=z, vx=speed, vz=0.0, mass=mass,
                             thrust=thrust, mach=mach, q=q, cg=cg, static_margin=0.0)
            rr = control.roll_authority(rocket, pt, mass, 1.0, interference)
            damp = q * area * d * abs(rr.cl_p) * d / (2.0 * speed)
            tau = inertia.roll / damp if damp > 1e-12 else 1e9
            p_ss = q * area * d * rr.cl_delta_net * math.radians(roll_act) / max(damp, 1e-12)
            p0 = math.radians(p_true)
            decay = math.exp(-dt / tau)
            roll_true += math.degrees(p_ss * dt + (p0 - p_ss) * tau * (1.0 - decay))
            p_true = math.degrees(p_ss + (p0 - p_ss) * decay)
        else:
            roll_true += p_true * dt
        peak_bank = max(peak_bank, abs(roll_true))

        # ---- advance the triad: transverse rate from omega, roll rate about b -----------
        if not on_rail:
            om_tot = omega + math.radians(p_true) * b
            b = b + np.cross(om_tot, b) * dt
            e1 = e1 + np.cross(om_tot, e1) * dt
            b, e1, e2 = _orthonormalize(b, e1)

        # ---- translation ----------------------------------------------------------------
        cd = aero.drag_coefficient(rocket, speed, max(z, 0.0))
        cn = stab.cn_alpha * alpha
        if alpha_deg > control.STALL_LIMIT_DEG:
            cn *= 0.6
        cd += aero.induced_drag_coefficient(stab.cn_alpha, alpha)
        drag_dir = vhat if speed > 1e-6 else b
        force = thrust * b - q * cd * area * drag_dir + np.array([0.0, 0.0, -mass * G0])
        if speed > 1.0 and cn > 1e-9:
            n_dir = b - float(np.dot(b, vhat)) * vhat   # turns velocity toward the nose
            nn = float(np.linalg.norm(n_dir))
            if nn > 1e-9:
                force = force + (q * area * cn) * (n_dir / nn)

        acc = force / mass
        if on_rail:
            acc = max(float(np.dot(acc, rail_dir)), 0.0) * rail_dir
        vel = vel + acc * dt
        pos = pos + vel * dt
        t += dt

        if on_rail and float(np.linalg.norm(pos - np.array([0.0, 0.0, RAIL_HEIGHT_M]))) >= RAIL_LENGTH_M:
            on_rail = False
        apogee_z = max(apogee_z, float(pos[2]))

        out.samples.append(dict(
            t=t, x=float(pos[0]), y=float(pos[1]), z=float(pos[2]), speed=speed, q=q,
            alpha_deg=alpha_deg, att_err_deg=att_err_deg, in_window=in_window,
            roll_true=roll_true, bank_cmd=bank_cmd, head_err=head_err,
            impact_x=impact[0], impact_y=impact[1],
            pitch_cmd=pitch_act, yaw_cmd=yaw_act, roll_cmd=roll_act,
            bz=float(b[2]), by=float(b[1]),
        ))

        if float(pos[2]) <= 0.0 and t > 1.0:
            break
        # the vertical case ends at apogee: past it the model is out of validity (see above)
        if elevation_deg > 60.0 and (not on_rail) and t > motor.burn_time and vel[2] <= 0.0:
            break
        if q < Q_MIN and t > steer_start + 1.0 and vel[2] < 0.0:
            break

    out.summary = dict(
        mode=mode, elevation_deg=elevation_deg, wind_mps=wind_mps, apogee_z=apogee_z,
        flight_seconds=t, peak_bank_deg=peak_bank, captured_t=captured_t,
        max_alpha_deg=max_alpha_deg, max_alpha_ctl_deg=max_alpha_ctl,
        max_alpha_exit_deg=max_alpha_exit, stall_seconds=stall_seconds,
        steer_start=steer_start, target_xy=target_xy, peak_att_err_deg=peak_att_err,
        final_xy=(float(pos[0]), float(pos[1])), att_kp=att_kp, att_kd=att_kd,
        final_crosstrack_m=head_err if mode == 'l3' else None,
    )
    return out


# --------------------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------------------

def check_l2(case: GuidanceCase, free: GuidanceCase) -> tuple[bool, str]:
    """L2 passes if the loop holds the commanded attitude materially better than locked canards.

    The metric is the ANGLE BETWEEN the body axis and the commanded axis -- one number, no
    Euler angles, so it does not care that the vehicle is near vertical. Measured only inside
    the control window (off the rail, q >= Q_MIN, past the steering start), because outside it
    the canards have no authority and the comparison would be meaningless.
    """
    steer = case.summary["steer_start"]
    def rms(c):
        v = [s["att_err_deg"] for s in c.samples if s["in_window"] and s["t"] >= steer]
        return math.sqrt(sum(x * x for x in v) / len(v)) if v else float("nan")
    held, drifted = rms(case), rms(free)
    ok = held < 0.5 * drifted
    return ok, (f"attitude-error RMS {held:.2f} deg held vs {drifted:.2f} deg locked "
                f"({drifted/held:.1f}x better)")


def check_l3(case: GuidanceCase) -> tuple[bool, str]:
    """L3 passes if the predicted impact point is steered onto the target inside L3_CAPTURE_M."""
    errs = [abs(s["head_err"]) for s in case.samples if s["in_window"] and s["head_err"]]
    if not errs:
        return False, "no guided samples"
    cap = case.summary["captured_t"]
    tx, ty = case.summary["target_xy"]
    fx, fy = case.summary["final_xy"]
    actual = math.hypot(fx - tx, fy - ty)
    ok = cap is not None
    return ok, (f"crosstrack miss {errs[0]:.0f} -> {min(errs):.1f} m"
                + (f", captured at t={cap:.2f} s" if cap else ", NOT captured")
                + f"; actual impact {actual:.0f} m from target")


def check_stall(case: GuidanceCase) -> tuple[bool, str]:
    s = case.summary
    ok = s["stall_seconds"] == 0.0
    return ok, (f"peak alpha under control {s['max_alpha_ctl_deg']:.2f} deg against the "
                f"{control.STALL_LIMIT_DEG:.0f} deg limit, {s['stall_seconds']:.2f} s stalled"
                f"  (rail-exit transient, before the loop runs: "
                f"{s['max_alpha_exit_deg']:.1f} deg)")


def _plots(cases: dict[str, GuidanceCase]) -> None:
    fig, ax = plt.subplots(2, 3, figsize=(16, 8))
    l2, free, l3 = cases["l2"], cases["l2_free"], cases["l3"]

    a = ax[0][0]
    for c, col, lab in ((free, "tab:red", "canards locked"), (l2, "tab:blue", "L2 hold")):
        w = [s for s in c.samples if s["in_window"]]
        a.plot([s["t"] for s in w], [s["att_err_deg"] for s in w], color=col, label=lab)
    a.set_title(f"L2 -- attitude error vs {l2.summary['wind_mps']:.0f} m/s crosswind")
    a.set_xlabel("t (s)"); a.set_ylabel("angle to commanded axis (deg)")
    a.legend(); a.grid(alpha=0.3)

    a = ax[0][1]
    for c, col, lab in ((free, "tab:red", "locked"), (l2, "tab:blue", "held")):
        a.plot([s["t"] for s in c.samples], [s["by"] for s in c.samples], color=col, label=lab)
    a.axhline(0, ls=":", c="k", lw=0.8)
    a.set_title("L2 -- body axis crosswind component")
    a.set_xlabel("t (s)"); a.set_ylabel("b . y"); a.legend(); a.grid(alpha=0.3)

    a = ax[0][2]
    a.plot([s["t"] for s in l2.samples], [s["yaw_cmd"] for s in l2.samples], label="yaw")
    a.plot([s["t"] for s in l2.samples], [s["pitch_cmd"] for s in l2.samples], label="pitch")
    for sgn in (1, -1):
        a.axhline(sgn * DEFLECTION_LIMIT_DEG, ls=":", c="r")
    a.set_title("L2 -- canard deflection"); a.set_xlabel("t (s)"); a.set_ylabel("deg")
    a.legend(); a.grid(alpha=0.3)

    a = ax[1][0]
    a.plot([s["x"] for s in l3.samples], [s["y"] for s in l3.samples], color="tab:green",
           label="guided track")
    w = [s for s in l3.samples if s["in_window"] and s["impact_x"]]
    a.plot([s["impact_x"] for s in w], [s["impact_y"] for s in w], ls="--", c="tab:orange",
           label="predicted impact")
    tx, ty = l3.summary["target_xy"]
    a.plot([tx], [ty], "r*", ms=14, label="target")
    a.set_title("L3 -- ground track"); a.set_xlabel("x (m)"); a.set_ylabel("y (m)")
    a.legend(); a.grid(alpha=0.3); a.axis("equal")

    a = ax[1][1]
    w = [s for s in l3.samples if s["in_window"]]
    a.plot([s["t"] for s in w], [s["head_err"] for s in w])
    for sgn in (1, -1):
        a.axhline(sgn * L3_CAPTURE_M, ls=":", c="g")
    a.set_title("L3 -- crosstrack miss of the predicted impact point")
    a.set_xlabel("t (s)"); a.set_ylabel("miss (m, + = target to the left)")
    a.grid(alpha=0.3)

    a = ax[1][2]
    a.plot([s["t"] for s in l3.samples], [s["roll_true"] for s in l3.samples], label="roll")
    a.plot([s["t"] for s in l3.samples], [s["bank_cmd"] for s in l3.samples], ls="--",
           label="bank cmd")
    a.set_title("L3 -- bank-to-turn"); a.set_xlabel("t (s)"); a.set_ylabel("deg")
    a.legend(); a.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=130)
    print(f"wrote {PLOT_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mag", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--wind", type=float, default=8.0, help="crosswind, m/s")
    ap.add_argument("--kd", type=float, default=ATT_KD,
                    help="attitude rate gain; 0 to watch the pitch mode ring")
    ap.add_argument("--crossrange", type=float, default=200.0,
                    help="L3 target offset across the unguided ground track, m")
    a = ap.parse_args()

    params = baseline()
    ev = evaluate(params)
    rocket, motor, masses = ev.rocket, params.motor, ev.masses
    common = dict(seed=a.seed, mag_aiding=not a.no_mag, ev=ev)

    cases = {}
    # L2 at the VERTICAL mode -- docs/00 1.1's own example ("hold commanded pitch/yaw
    # attitude, e.g. vertical"), and the case an Euler parameterisation cannot represent.
    cases["l2"] = run(rocket, motor, masses, mode="l2", label="L2 attitude hold",
                      elevation_deg=85.0, wind_mps=a.wind, att_kd=a.kd, **common)
    cases["l2_free"] = run(rocket, motor, masses, mode="l2", label="canards locked",
                           elevation_deg=85.0, wind_mps=a.wind, att_kp=0.0, att_kd=0.0,
                           **common)
    # L3 at the HORIZONTAL mode (R15's primary). The target is placed relative to where this
    # vehicle actually lands UNGUIDED, so the test measures the guidance law rather than the
    # airframe's crossrange -- the offset is the knob, and --crossrange sweeps it.
    ref = run(rocket, motor, masses, mode="l3", label="unguided reference",
              elevation_deg=28.0, target_xy=(1e7, 0.0), **common)
    rx, ry = ref.summary["final_xy"]
    target = (rx, ry + a.crossrange)
    cases["l3"] = run(rocket, motor, masses, mode="l3", label="L3 ground target",
                      elevation_deg=28.0, target_xy=target, **common)

    lines = ["=" * 92,
             "SIL L2 / L3 -- attitude hold, and guidance to a ground target",
             "=" * 92, "",
             f"  airframe: frozen baseline, deflection cap {DEFLECTION_LIMIT_DEG} deg, "
             f"roll cap {ROLL_COMMAND_CAP_DEG} deg",
             f"  magnetometer aiding: {'ON' if not a.no_mag else 'OFF'}     "
             f"attitude gains Kp={ATT_KP} Kd={a.kd}", ""]

    cg = 0.78
    cmq = control.pitch_damping_cm_q(rocket, cg, 0.41)
    stab = aero.stability(rocket, cg, 0.41)
    inertia = control.estimate_inertia(rocket, 6.2, cg)
    q_ref, area, d = 11760.0, rocket.reference_area, rocket.diameter
    wn = math.sqrt(-stab.cm_alpha * q_ref * area * d / inertia.pitch)
    zeta = (-cmq * q_ref * area * d * d / (2 * 137.6)) / (2 * inertia.pitch * wn)
    lines += ["THE PITCH MODE at max coast q -- this is what shapes both loops",
              f"  Cm_alpha {stab.cm_alpha:+.1f} /rad      Cm_q {cmq:+.1f} /rad"
              "   (control.pitch_damping_cm_q, NEW and UNVERIFIED)",
              f"  natural frequency {wn/(2*math.pi):.2f} Hz      damping ratio {zeta:.3f}",
              f"  -> ring-down to 2% takes ~{4/(zeta*wn):.1f} s on aero damping alone, which is",
              "     longer than the control window. The RATE term is doing the work, not the",
              "     airframe: run with --kd 0 and L2 oscillates instead of holding.", ""]

    results = []
    for name, (ok, msg) in (("L2 attitude hold", check_l2(cases["l2"], cases["l2_free"])),
                            ("L2 stall margin", check_stall(cases["l2"])),
                            ("L3 target capture", check_l3(cases["l3"])),
                            ("L3 stall margin", check_stall(cases["l3"]))):
        results.append(ok)
        lines.append(f"  [{'PASS' if ok else 'FAIL'}]  {name:18s}  {msg}")

    l2, free, l3 = cases["l2"], cases["l2_free"], cases["l3"]
    lines += ["", f"L2 -- 85 deg rail, steady {l2.summary['wind_mps']:.0f} m/s crosswind",
              f"  attitude error, peak    {l2.summary['peak_att_err_deg']:6.2f} deg held"
              f"   vs {free.summary['peak_att_err_deg']:6.2f} deg with canards locked",
              f"  apogee                  {l2.summary['apogee_z']:6.0f} m"
              f"      vs {free.summary['apogee_z']:6.0f} m",
              f"  peak alpha under control{l2.summary['max_alpha_ctl_deg']:6.2f} deg",
              "",
              "  THE RAIL-EXIT TRANSIENT IS NOT A CONTROL PROBLEM AND IS THE LARGEST ALPHA IN",
              f"  THE FLIGHT: {l2.summary['max_alpha_exit_deg']:.1f} deg, before the loop is allowed to run. At the"
              f" {l2.summary['wind_mps']:.0f} m/s",
              "  crosswind above and this vehicle's 20.6 m/s rail-exit speed, the relative wind",
              "  is already ~21 deg off the rail -- geometry, not aerodynamics, and no canard",
              "  authority exists there anyway (q < Q_MIN). It is the argument for a wind limit",
              "  on the launch card, and it is what R1's static margin is carrying.",
              ""]
    ctx = math.hypot(*[c - t for c, t in zip(l3.summary["final_xy"], l3.summary["target_xy"])])
    dx = l3.summary["final_xy"][0] - ref.summary["final_xy"][0]
    dy_target = l3.summary["target_xy"][1] - ref.summary["final_xy"][1]
    dy_actual = l3.summary["final_xy"][1] - ref.summary["final_xy"][1]
    lines += [f"L3 -- 28 deg rail, target {dy_target:.0f} m across the unguided ground track",
              f"  unguided impact         {ref.summary['final_xy'][0]:6.0f}, "
              f"{ref.summary['final_xy'][1]:.0f} m",
              f"  target                  {l3.summary['target_xy'][0]:6.0f}, "
              f"{l3.summary['target_xy'][1]:.0f} m",
              f"  guided impact           {l3.summary['final_xy'][0]:6.0f}, "
              f"{l3.summary['final_xy'][1]:.0f} m",
              f"  crossrange achieved     {dy_actual:6.0f} m of the {dy_target:.0f} m asked"
              f" ({100*dy_actual/dy_target:.0f}%)",
              f"  captured at             t = {l3.summary['captured_t']:.2f} s"
              if l3.summary["captured_t"] else "  NOT captured",
              f"  peak bank               {l3.summary['peak_bank_deg']:6.1f} deg",
              "",
              "  TWO THINGS THE LOOP CANNOT FIX, and both are in the numbers above.",
              f"  1. MANOEUVRING COSTS {-dx:.0f} m OF DOWNRANGE ({100*-dx/ref.summary['final_xy'][0]:.0f}%).",
              "     Banking 90 deg points the whole normal force sideways, so nothing holds the",
              "     vehicle up while it turns, and the induced drag of the trimmed alpha is paid",
              "     for the entire manoeuvre. A ballistic vehicle cannot buy that range back.",
              "     Downrange is therefore NOT a controllable axis and the impact will always",
              "     fall short of a target placed at the unguided range.",
              "  2. THE PREDICTOR IS BIASED BY THE MANOEUVRE ITSELF. `predict_impact` propagates",
              "     with canards NEUTRAL, so while the vehicle is banked and pulling, the",
              f"     prediction it is nulling is not the trajectory it is flying -- {abs(dy_target-dy_actual):.0f} m of the",
              "     crossrange asked for is lost to exactly that. Closing this properly needs a",
              "     predictor that carries the current command forward, which is a real firmware",
              "     design decision and is NOT made here.", ""]
    lines += ["WHAT THIS DOES NOT PROVE -- the module docstring has the full list. The short",
              "version: Cm_q is new and unverified, pitch and yaw are treated as independent",
              "planes (which a 90 deg bank violates), the canard wake is still unmeasured on",
              "both channels, and nothing here has touched hardware.", ""]

    txt = "\n".join(lines)
    REPORT_PATH.write_text(txt + "\n")
    print(txt)
    _plots(cases)
    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
