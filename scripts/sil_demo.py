"""Software-in-the-loop: close the roll loop, bank-to-turn, and prove the R12 failsafe.

Step 4 of docs/01-next-steps.md puts "hardware-in-the-loop simulation" before "controller"
and "safety logic" before both -- "write this before the controller, not after." This script
is the SOFTWARE half of that ordering, run with no hardware and no airframe change: a
closed loop built entirely from this repo's own aero/mass/motor model (`design/control.py`,
`design/horizontal.py`, `design/configure.py`'s FROZEN baseline), driven by SYNTHETIC sensor
data rather than the truth state, commanding through the same `DEFLECTION_LIMIT_DEG` /
`ROLL_COMMAND_CAP_DEG` limits the airframe is frozen at.

WHAT THIS PROVES
  1. L1 -- roll hold. An assumed rail-exit roll-rate disturbance is nulled and a commanded
     roll angle held, using a GYRO ESTIMATE (optionally magnetometer-aided), not truth.
  2. Bank-to-turn. Once banked to 90 deg (closed loop, on the estimate), the canards pull
     DEFLECTION_LIMIT_DEG in the banked plane and the velocity vector turns.
  3. R12 failsafe. A fault is injected mid-manoeuvre; both canard channels ramp to centred
     within the 0.5 s latency R12 requires, REGARDLESS of what guidance wanted next. On the
     horizontal case, canards are additionally forced to centre, unconditionally, below
     `design.horizontal.ALTITUDE_FLOOR_M` (50 m AGL) -- the second half of R12.

Two cases, same airframe, same control law: `elevation_deg=28` (R15's horizontal mode) and
`elevation_deg=85` (R15's vertical mode, 5 deg off vertical). Nothing in `configure.py`'s
frozen `DesignParams` is touched -- if a run fails a requirement, the bug is in this script.

WHAT THIS DOES NOT PROVE, and do not let it be quoted as if it did.
  * It does not touch canard/aft-fin wake interference. `roll_authority` and its
    `InterferenceModel` are exactly what `scripts/virtual_flight.py` and every design script
    use -- the WEAKEST part of this project's analysis, per docs/00 section 5 -- and GV-2's
    open-loop deflection sweep is still the only thing that turns it into a measurement.
    Closing this loop in software cannot validate the aerodynamics it runs on.
  * It is not a timing or embedded-execution proof. The controller runs at 100 Hz with one
    period of latency; the servo (`control.servo_step`: slew limit plus an ASSUMED 30 ms lag,
    the datasheet gives none) and the roll axis (exact exponential per substep) are stepped at
    1 kHz inside it. Before 2026-09-26 the servo was a pure slew limit with no lag, which hid
    that the old Kp = 1.0 was unstable -- see scripts/roll_bandwidth.py. Real firmware still needs the >=1 kHz quaternion propagation docs/07 calls for; this
    script says nothing about whether an STM32F405 can hit that rate with margin.
  * The magnetometer is modelled as a virtual roll-angle sensor with an angular noise sigma
    derived the same way `design/estimation.py`'s error budget derives one (field-perpendicular
    component, `_optimal_tau` fusion) -- not a 3-axis field model with body attitude in it.
  * No wind, no thrust misalignment, no launch-rail tip-off measurement (the initial roll
    rate below is an ASSUMED demo disturbance, not a measured one), and no descent-under-
    drogue dynamics after the vertical case's apogee cutoff.
  * This is not hardware-in-the-loop. Nothing here has touched a servo, a real IMU, or a
    flight computer's actual scheduler. That is Step 4 item 3, still ahead of this.

Run:  python scripts/sil_demo.py [--no-mag] [--seed N]
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
PLOT_PATH = OUT / "sil_demo.png"
REPORT_PATH = OUT / "sil_demo.txt"

G0 = atmosphere.G0
SLEW_DEG_S = 60.0 / SERVOS["kst_x08_plus"].speed_60deg  # 667 deg/s, same figure virtual_flight.py uses

# R12: "fault-to-centred latency <= 0.5 s" (docs/00-requirements.md). Not a tuning knob.
R12_LATENCY_S = 0.5
# The COMMAND must reach centre early: the surface trails it by one loop period plus the servo
# lag, and ramping the command over the full 0.5 s left the canards ~0.7 deg off at 0.5 s.
R12_RAMP_S = 0.35

BANK_TARGET_DEG = 90.0   # full bank-to-turn, matching scripts/virtual_flight.py's "btt" mode
BANK_TOL_DEG = 3.0       # roll-hold tolerance before the pitch pull is allowed to start
ROLL_KP, ROLL_KD = control.ROLL_KP, control.ROLL_KD
PHYSICS_SUBSTEPS = 10    # servo lag + roll axis stepped at 10x the controller rate

RAIL_LENGTH_M = 3.66
RAIL_HEIGHT_M = 2.0

# ASSUMED, not measured -- see the module docstring. Large enough to be a real test of L1's
# authority (it is more than half the vehicle's own 2 deg/s-per-1 deg-of-cap sensitivity at
# typical coast dynamic pressure), not chosen to make the loop look good.
INITIAL_ROLL_RATE_DPS = 30.0


def wrap180(deg: float) -> float:
    return (deg + 180.0) % 360.0 - 180.0


def roll_step(p0_dps: float, delta_cmd_deg: float, cl_net: float, cl_p: float,
              q: float, speed: float, inertia_roll: float, d: float, area: float,
              dt: float) -> tuple[float, float]:
    """Advance true roll rate and angle one step, EXACTLY, given locally-frozen coefficients.

    `I_roll * dp/dt = q*A*d*Cl_net*delta - q*A*d*|Cl_p|*(d/2V)*p` is linear in p at fixed
    q/V/delta, so it has a closed-form exponential solution -- used here instead of a fixed
    step integrator so the outer 100 Hz loop cannot destabilise an axis whose own time
    constant is of order 20 ms (see the module docstring). Returns (p1_dps, dtheta_deg).
    """
    if q <= 1.0 or speed <= 1.0 or inertia_roll <= 0.0:
        return p0_dps, p0_dps * dt
    damp_coef = q * area * d * abs(cl_p) * d / (2.0 * speed)  # N*m per (rad/s)
    if damp_coef <= 1e-12:
        moment = q * area * d * cl_net * math.radians(delta_cmd_deg)
        p1 = p0_dps + math.degrees(moment / inertia_roll) * dt
        return p1, 0.5 * (p0_dps + p1) * dt
    tau = inertia_roll / damp_coef
    moment_ctrl = q * area * d * cl_net * math.radians(delta_cmd_deg)
    p_ss = moment_ctrl / damp_coef  # rad/s
    p0 = math.radians(p0_dps)
    decay = math.exp(-dt / tau)
    p1 = p_ss + (p0 - p_ss) * decay
    integral = p_ss * dt + (p0 - p_ss) * tau * (1.0 - decay)
    return math.degrees(p1), math.degrees(integral)


@dataclass
class SilCase:
    label: str
    elevation_deg: float
    horizontal: bool
    samples: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


def run(rocket, motor, masses, ev, *, elevation_deg: float, label: str, horizontal: bool,
        seed: int = 0, mag_aiding: bool = True, dt: float = 0.01, max_time: float = 40.0,
        start_after_burnout: float = 0.5, fault_delay_s: float = 3.0) -> SilCase:
    rng = np.random.default_rng(seed)
    out = SilCase(label=label, elevation_deg=elevation_deg, horizontal=horizontal)

    d, area = rocket.diameter, rocket.reference_area
    el = math.radians(elevation_deg)
    rail_dir = np.array([math.cos(el), 0.0, math.sin(el)])
    steer_start = motor.burn_time + start_after_burnout
    fault_time = steer_start + fault_delay_s

    # Mag-fusion time constant taken directly from the project's own optimal-filter derivation
    # (design/estimation._optimal_tau, via mag_aided_roll_error), not re-tuned here. The noise
    # sigma is the same field-perpendicular-component formula estimation.py's error budget uses.
    aided = estimation.mag_aided_roll_error(ev, roll_rate_deg_s=INITIAL_ROLL_RATE_DPS + 1.0)
    tau_mag = aided.tau_s
    b_perp = estimation._field_perp()
    mag_noise_deg = math.degrees(math.atan2(MAG_MMC5983.mag_noise_gauss, b_perp))
    gyro_sigma_dps = GYRO_ICM42688.arw_deg_rt_s / math.sqrt(dt)

    t = 0.0
    pos = np.array([0.0, 0.0, RAIL_HEIGHT_M])
    vel = np.zeros(3)
    on_rail = True
    roll_true = 0.0
    p_true = INITIAL_ROLL_RATE_DPS
    roll_est = 0.0
    roll_cmd_act = 0.0
    pitch_cmd_act = 0.0
    roll_cmd_out = pitch_cmd_out = 0.0   # last period's command: one period of latency
    fault_latched = False
    roll_cmd_at_fault = pitch_cmd_at_fault = 0.0
    vec_turn_deg = 0.0
    peak_vec_rate_dps = 0.0
    heading_unwrapped = 0.0
    prev_heading = 0.0
    apogee_z = 0.0
    apogee_t = 0.0
    bank_locked_t = None
    floor_tripped = False

    interference = control.InterferenceModel.interdigitated()

    while t < max_time:
        speed = float(np.linalg.norm(vel))
        z = float(pos[2])
        rho = atmosphere.density(max(z, 0.0))
        sound = atmosphere.speed_of_sound(max(z, 0.0))
        mass = masses.dry_mass + max(motor.mass_at(t) - motor.dry_mass, 0.0)
        thrust = motor.thrust(t)
        cg = cg_at_time(masses, motor, t, rocket)
        q = 0.5 * rho * speed * speed
        mach = speed / sound if sound > 1.0 else 0.0
        body = rail_dir.copy() if (on_rail or speed <= 0.1) else vel / speed

        # -- synthetic gyro, and an optional magnetometer correction (L1's sensor model) ---
        gyro_meas = p_true * (1.0 + GYRO_ICM42688.scale_factor) + GYRO_ICM42688.bias_deg_s \
            + rng.normal(0.0, gyro_sigma_dps)
        roll_est += gyro_meas * dt
        if mag_aiding and tau_mag > 0:
            mag_meas = roll_true + rng.normal(0.0, mag_noise_deg)
            k = 1.0 - math.exp(-dt / tau_mag)
            roll_est += k * wrap180(mag_meas - roll_est)

        # -- guidance: L1 roll hold, then bank-to-turn once past burnout ---------------------
        # L1 holds roll from the moment the canards have authority -- rail exit, q >= Q_MIN --
        # with NO altitude gate. R12's 50 m floor is a TERMINAL-phase rule (docs/00: "reaches
        # the ground with the canards fully effective... below 50 m there are 0.75 s and
        # ~101 m/s left" -- an impact margin), not a reason to withhold roll authority while
        # climbing out through the first 50 m of a 28 deg rail. Gating on it here reproduces
        # exactly the failure R12 exists to prevent, just earlier in the flight.
        roll_target = BANK_TARGET_DEG if t >= steer_start else 0.0
        roll_gate = (not on_rail) and q >= Q_MIN
        roll_cmd_nom = 0.0
        if roll_gate:
            err = wrap180(roll_target - roll_est)
            u = ROLL_KP * err - ROLL_KD * gyro_meas
            roll_cmd_nom = max(-ROLL_COMMAND_CAP_DEG, min(ROLL_COMMAND_CAP_DEG, u))
            if abs(err) <= BANK_TOL_DEG and t >= steer_start and bank_locked_t is None:
                bank_locked_t = t

        pitch_cmd_nom = 0.0
        if bank_locked_t is not None and t >= steer_start and q >= Q_MIN:
            pitch_cmd_nom = DEFLECTION_LIMIT_DEG

        # -- R12: fault injection, ramp-to-centre within the 0.5 s latency ------------------
        if t >= fault_time:
            if not fault_latched:
                fault_latched = True
                roll_cmd_at_fault, pitch_cmd_at_fault = roll_cmd_nom, pitch_cmd_nom
            frac = max(0.0, 1.0 - (t - fault_time) / R12_RAMP_S)
            roll_cmd, pitch_cmd = roll_cmd_at_fault * frac, pitch_cmd_at_fault * frac
        else:
            roll_cmd, pitch_cmd = roll_cmd_nom, pitch_cmd_nom

        # R12's second clause: unconditional, regardless of fault or guidance state -- but it
        # is a TERMINAL-phase rule (see above), so it is keyed on DESCENDING below the floor,
        # not merely being below it, or a 28 deg rail would never leave the ground with roll
        # authority at all.
        below_floor = horizontal and z < ALTITUDE_FLOOR_M and vel[2] < 0.0
        if below_floor:
            roll_cmd = pitch_cmd = 0.0
            floor_tripped = True

        roll_apply, pitch_apply = roll_cmd_out, pitch_cmd_out
        roll_cmd_out, pitch_cmd_out = roll_cmd, pitch_cmd
        h = dt / PHYSICS_SUBSTEPS
        for _ in range(PHYSICS_SUBSTEPS):
            pitch_cmd_act = control.servo_step(pitch_cmd_act, pitch_apply, h, SLEW_DEG_S)

        # -- physics: translation (pitch/yaw channel) + roll (analytic step) ----------------
        cd = aero.drag_coefficient(rocket, speed, max(z, 0.0))
        a_lat = 0.0
        lat_g = 0.0
        stalled = False
        if abs(pitch_cmd_act) > 0.05 and not on_rail and q > 50.0:
            pt = FlightPoint(t=t, x=float(pos[0]), z=z, vx=speed, vz=0.0, mass=mass,
                              thrust=thrust, mach=mach, q=q, cg=cg, static_margin=0.0)
            auth = control.pitch_authority(rocket, pt, mass, abs(pitch_cmd_act))
            stalled = auth.stalled
            lat_g = auth.lateral_accel_g * (0.6 if stalled else 1.0)
            a_lat = lat_g * G0
            cn_alpha = aero.stability(rocket, cg, mach).cn_alpha
            cd += aero.induced_drag_coefficient(cn_alpha, math.radians(auth.alpha_trim_deg))

        drag = 0.5 * rho * speed * speed * cd * area
        force = thrust * body - drag * body + np.array([0.0, 0.0, -mass * G0])

        if a_lat > 1e-9 and speed > 1.0:
            lift0 = np.array([body[2], 0.0, -body[0]])
            axis = body / (np.linalg.norm(body) + 1e-12)
            c, s = math.cos(math.radians(roll_true)), math.sin(math.radians(roll_true))
            lift_dir = lift0 * c + np.cross(axis, lift0) * s + axis * np.dot(axis, lift0) * (1.0 - c)
            n = np.linalg.norm(lift_dir)
            if n > 1e-9:
                force = force + mass * a_lat * (lift_dir / n)

        # roll: servo lag and exact analytic roll step per substep, coefficients frozen over dt
        roll_live = not on_rail and q > 50.0 and speed > 1.0
        if roll_live:
            pt = FlightPoint(t=t, x=float(pos[0]), z=z, vx=speed, vz=0.0, mass=mass,
                              thrust=thrust, mach=mach, q=q, cg=cg, static_margin=0.0)
            roll_res = control.roll_authority(rocket, pt, mass, 1.0, interference)
            inertia = control.estimate_inertia(rocket, mass, cg)
        for _ in range(PHYSICS_SUBSTEPS):
            roll_cmd_act = control.servo_step(roll_cmd_act, roll_apply, h, SLEW_DEG_S)
            if roll_live:
                p_true, dtheta = roll_step(p_true, roll_cmd_act, roll_res.cl_delta_net,
                                            roll_res.cl_p, q, speed, inertia.roll, d, area, h)
                roll_true += dtheta
            else:
                roll_true += p_true * h

        acc = force / mass
        if on_rail:
            along = max(float(np.dot(acc, rail_dir)), 0.0)
            acc = along * rail_dir

        # Rotation of the velocity vector due to CANARD force alone -- control.heading_change
        # and design.horizontal.fly's convention, not the total velocity-vector curvature.
        # The latter also counts gravity droop right off the rail (a real ~20 deg/s spike at
        # rail exit on this T/W, per R15's rationale) and would swamp the number this plot
        # exists to show: how much of the turn the CLOSED LOOP produced.
        vec_rate_dps = math.degrees(a_lat / max(speed, 1.0))
        vec_turn_deg += vec_rate_dps * dt
        peak_vec_rate_dps = max(peak_vec_rate_dps, vec_rate_dps)

        if speed > 1.0:
            h = math.degrees(math.atan2(float(vel[1]), float(vel[0])))
            if not on_rail:
                dh = wrap180(h - prev_heading)
                heading_unwrapped += dh
            prev_heading = h

        vel = vel + acc * dt
        pos = pos + vel * dt
        t += dt

        if on_rail and float(np.linalg.norm(pos - np.array([0.0, 0.0, RAIL_HEIGHT_M]))) >= RAIL_LENGTH_M:
            on_rail = False
            prev_heading = math.degrees(math.atan2(float(vel[1]), float(vel[0])))

        if pos[2] > apogee_z:
            apogee_z, apogee_t = float(pos[2]), t

        out.samples.append(dict(
            t=t, x=float(pos[0]), y=float(pos[1]), z=float(pos[2]), speed=speed, q=q, mach=mach,
            roll_true=roll_true, roll_est=roll_est, roll_target=roll_target, p_true=p_true,
            roll_cmd=roll_cmd_act, pitch_cmd=pitch_cmd_act, lat_g=lat_g, stalled=stalled,
            vec_turn_deg=vec_turn_deg, heading_deg=abs(heading_unwrapped),
            fault_active=fault_latched, below_floor=below_floor,
        ))

        if not horizontal and (not on_rail) and t > motor.burn_time and vel[2] <= 0.0:
            break
        if horizontal and pos[2] <= 0.0 and t > 0.5:
            break

    out.summary = dict(
        steer_start=steer_start, fault_time=fault_time, bank_locked_t=bank_locked_t,
        apogee_z=apogee_z, apogee_t=apogee_t, flight_seconds=t,
        peak_vec_rate_dps=peak_vec_rate_dps, final_vec_turn_deg=vec_turn_deg,
        floor_tripped=floor_tripped, mag_aiding=mag_aiding,
    )
    return out


def _check_r12(case: SilCase) -> tuple[bool, str]:
    ft = case.summary["fault_time"]
    after = [s for s in case.samples if ft <= s["t"] <= ft + R12_LATENCY_S + 0.05]
    if not after:
        return False, "no samples after fault injection"
    settle = [s for s in after if s["t"] >= ft + R12_LATENCY_S]
    ok = all(abs(s["roll_cmd"]) < 0.15 and abs(s["pitch_cmd"]) < 0.15 for s in settle) if settle else False
    return ok, (f"centred by t={ft + R12_LATENCY_S:.2f}s" if ok
                else "canards NOT centred within the 0.5 s latency")


def _check_roll_hold(case: SilCase) -> tuple[bool, str]:
    """Did L1 null the rail-exit disturbance and settle by the time bank-to-turn wants it?

    Checked at the END of the hold phase, not the peak over it: the canards have no
    authority below Q_MIN, so the assumed rail-exit disturbance free-drifts the airframe for
    a fraction of a second no controller can do anything about (see the module docstring).
    The question worth asking is whether the loop has recovered by the time it matters.
    """
    ss = case.summary["steer_start"]
    settle = [s for s in case.samples if ss - 0.3 <= s["t"] <= ss]
    if not settle:
        return False, "no hold-phase samples"
    settled_err = max(abs(wrap180(s["roll_target"] - s["roll_true"])) for s in settle)
    ok = settled_err < 2.0
    return ok, f"roll error in the 0.3 s before bank-to-turn starts: {settled_err:.2f} deg"


def _write_plots(cases: dict[str, SilCase]):
    fig, axes = plt.subplots(4, 2, figsize=(13, 13), sharex="col")
    fig.suptitle("SIL demo — closed-loop roll hold, bank-to-turn, R12 failsafe", fontsize=13, fontweight="bold")

    for col, (key, case) in enumerate(cases.items()):
        s = case.samples
        t = [p["t"] for p in s]
        ax = axes[0, col]
        ax.plot(t, [p["roll_true"] for p in s], color="#2E5A8C", lw=1.6, label="roll (true)")
        ax.plot(t, [p["roll_est"] for p in s], color="#C46A3A", lw=1.2, ls="--", label="roll (estimate)")
        ax.plot(t, [p["roll_target"] for p in s], color="#888", lw=1.0, ls=":", label="commanded")
        ax.axvline(case.summary["fault_time"], color="firebrick", lw=1, ls="-.", alpha=0.7)
        ax.set_title(f"{case.label}: roll")
        ax.set_ylabel("deg")
        ax.legend(fontsize=7, loc="lower right")
        ax.grid(alpha=0.3)

        ax = axes[1, col]
        ax.plot(t, [p["roll_cmd"] for p in s], color="#2E5A8C", lw=1.3, label="roll channel (deg)")
        ax.plot(t, [p["pitch_cmd"] for p in s], color="#C46A3A", lw=1.3, label="pitch channel (deg)")
        ax.axvline(case.summary["fault_time"], color="firebrick", lw=1, ls="-.", alpha=0.7, label="fault injected")
        ax.set_title("canard actuator commands")
        ax.set_ylabel("deg")
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)

        ax = axes[2, col]
        ax.plot(t, [p["vec_turn_deg"] for p in s], color="#2E5A8C", lw=1.6)
        ax.set_title("velocity-vector turn (path turn)")
        ax.set_ylabel("deg")
        ax.grid(alpha=0.3)

        ax = axes[3, col]
        ax.plot(t, [p["z"] for p in s], color="#2E5A8C", lw=1.6)
        if case.horizontal:
            ax.axhline(ALTITUDE_FLOOR_M, color="firebrick", lw=1, ls="--", alpha=0.7, label="50 m AGL floor")
            ax.legend(fontsize=7)
        ax.set_title("altitude")
        ax.set_ylabel("m")
        ax.set_xlabel("t (s)")
        ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-mag", action="store_true", help="disable magnetometer aiding (gyro-only roll estimate)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    mag_aiding = not args.no_mag

    ev = evaluate(baseline(), deflection_deg=DEFLECTION_LIMIT_DEG)
    rocket, motor, masses = ev.rocket, ev.params.motor, ev.masses

    cases = {
        "horizontal": run(rocket, motor, masses, ev, elevation_deg=28.0, label="Horizontal (28 deg, R15)",
                           horizontal=True, seed=args.seed, mag_aiding=mag_aiding, max_time=40.0),
        "vertical": run(rocket, motor, masses, ev, elevation_deg=85.0, label="Vertical (85 deg, R15)",
                         horizontal=False, seed=args.seed, mag_aiding=mag_aiding, max_time=25.0),
    }

    lines = []
    lines.append("=== SIL DEMO: closed-loop roll hold, bank-to-turn, R12 failsafe ===")
    lines.append(f"mag aiding: {'ON' if mag_aiding else 'OFF (gyro-only dead reckoning)'}   seed={args.seed}")
    lines.append("")
    for key, case in cases.items():
        s = case.summary
        hold_ok, hold_msg = _check_roll_hold(case)
        r12_ok, r12_msg = _check_r12(case)
        lines.append(f"--- {case.label} ---")
        lines.append(f"  steer_start={s['steer_start']:.2f}s  fault_time={s['fault_time']:.2f}s  "
                      f"bank_locked_t={s['bank_locked_t']}")
        lines.append(f"  L1 roll hold:      {'PASS' if hold_ok else 'FAIL'}  ({hold_msg})")
        lines.append(f"  R12 fault latency: {'PASS' if r12_ok else 'FAIL'}  ({r12_msg})")
        if case.horizontal:
            lines.append(f"  R12 altitude floor: {'tripped' if s['floor_tripped'] else 'never reached'} "
                          f"(<{ALTITUDE_FLOOR_M:.0f} m AGL forces centre)")
        lines.append(f"  peak path-turn rate {s['peak_vec_rate_dps']:.2f} deg/s, "
                      f"total path turn {s['final_vec_turn_deg']:.1f} deg over {s['flight_seconds']:.1f} s")
        lines.append("")

    report = "\n".join(lines)
    print(report)
    OUT.mkdir(exist_ok=True)
    REPORT_PATH.write_text(report + "\n")
    _write_plots(cases)
    print(f"plot:   {PLOT_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
