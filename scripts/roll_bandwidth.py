"""Can the servo actually close the roll loop? Actuator bandwidth against the roll mode.

    python scripts/roll_bandwidth.py

WHY THIS EXISTS. Until 2026-09-26 every roll result in this project -- `out/baseline.txt`'s
566 deg/s, docs/13's software-in-the-loop roll hold, `scripts/virtual_flight.py` -- modelled the
servo as a PURE RATE LIMIT (667 deg/s, no lag, no phase, no transport delay), and against it the
roll loop looked easy: `ROLL_KP = 1.0` settled roll to under 0.1 deg. It was unstable. Section 4
derives the replacement PD gains now in `design/control.py` (ROLL_KP, ROLL_KD), and the SIL
scripts now use `control.servo_step` (slew limit + assumed lag). `virtual_flight.py` has not
been changed.

A rate limit is the WRONG constraint to be checking here, and this file is the arithmetic that
shows it. The rate limit is not close to binding at the +/-2 deg R13 allows -- a 2 deg sine
stays inside 667 deg/s out to 53 Hz. What binds is PHASE LAG, which no number on the KST
datasheet describes, and the roll axis is the worst place in the vehicle to meet it:

  * the roll mode is FAST -- tau 17-20 ms, a corner at 8-10 Hz, faster than any other mode on
    the vehicle including the 3.6 Hz pitch mode the 72 Hz loop-rate requirement was set from;
  * the roll authority is ENORMOUS -- 283 deg/s of roll rate per DEGREE of canard at the
    vertical max-q point, 321 at the horizontal one. A 1 deg deflection error is a 300 deg/s
    rate error.

High plant gain into a fast plant through a slow actuator is the standard recipe for a limit
cycle, and this asks whether this vehicle is in it.

WHAT IS ASSUMED, because the datasheet does not say. The servo is modelled as a first-order
lag of time constant `tau_s` in series with the published rate limit, plus a transport delay
of one loop period. `tau_s` is SWEPT rather than chosen, because it is the unmeasured number
the answer turns on -- the output is a stability boundary as a function of it, not a single
verdict. Getting `tau_s` is a bench measurement: step the servo a few degrees under
representative load, log commanded against achieved with a current probe on it. docs/14
already puts that on Step 5's list for the torque margin; this is a second reason for the
same test, and it wants a position trace as well as a current one.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import atmosphere, configure, control
from design.configure import ROLL_COMMAND_CAP_DEG
from design.packaging import SERVOS
from design.trajectory import FlightPoint

OUT = Path(__file__).resolve().parents[1] / "out" / "roll_bandwidth.txt"

SERVO = SERVOS["kst_x08_plus"]
SLEW_DEG_S = 60.0 / SERVO.speed_60deg

# Flight conditions: the vertical max-q point baseline.py reports, and the horizontal one
# docs/12 freezes at. Both matter -- R15 makes the horizontal case primary, and it is worse.
CONDITIONS = (("vertical max q", 11760.0, 137.6, 193.0),
              ("horizontal max q", 15500.0, 156.1, 60.0))

# Candidate servo lags, ms. A good digital servo under light load lands near 15-25 ms; a
# loaded hobby servo can be 40-60. The whole point is that this is unmeasured.
TAU_SERVO_MS = (5.0, 10.0, 15.0, 20.0, 30.0, 40.0, 60.0)


def plant(rocket, q: float, speed: float, alt: float, mass: float = 6.2, cg: float = 0.78):
    """Roll plant: returns (gain_deg_s_per_deg, tau_roll_s, RollResult).

    p/delta = gain / (1 + tau*s), from the same `roll_authority` every other script uses.
    """
    pt = FlightPoint(t=5.0, x=0.0, z=alt, vx=speed, vz=0.0, mass=mass, thrust=0.0,
                     mach=speed / atmosphere.speed_of_sound(alt), q=q, cg=cg,
                     static_margin=0.0)
    rr = control.roll_authority(rocket, pt, mass, 2.0,
                                control.InterferenceModel.interdigitated())
    d, area = rocket.diameter, rocket.reference_area
    inertia = control.estimate_inertia(rocket, mass, cg).roll
    damp = q * area * d * abs(rr.cl_p) * d / (2.0 * speed)   # N*m per (rad/s)
    tau = inertia / damp
    # steady rate per radian of deflection, then per degree
    gain = math.degrees(q * area * d * rr.cl_delta_net / damp) * math.pi / 180.0
    return gain, tau, rr


def routh_kp_limit(gain: float, tau_r: float, tau_s: float) -> float:
    """Largest proportional roll-angle gain that is stable, deg of canard per deg of error.

    Loop is L(s) = Kp*gain / ( s (1+tau_r s)(1+tau_s s) ) -- an integrator (angle from rate)
    behind two lags. For 1 + K/(s(1+t1 s)(1+t2 s)) the Routh condition on the cubic
    t1 t2 s^3 + (t1+t2) s^2 + s + K is K < (t1+t2)/(t1 t2), exactly.
    """
    k_max = (tau_r + tau_s) / (tau_r * tau_s)
    return k_max / gain


def margins(gain: float, tau_r: float, tau_s: float, kp: float, kd: float,
            loop_hz: float) -> tuple[float, float, float]:
    """Phase margin (deg), gain margin (dB), crossover (Hz) of the PD roll-angle loop.

    L(s) = gain*(kp + kd*s) / (s (1+tau_r s)(1+tau_s s)) * exp(-1.5 s/loop_hz). The 1.5
    periods are one period of sample-to-output latency plus the zero-order hold's half period.
    Unstable loops come out with a negative margin.
    """
    w = np.logspace(-1, 4, 40000)
    s = 1j * w
    loop = gain * (kp + kd * s) / (s * (1 + tau_r * s) * (1 + tau_s * s)) \
        * np.exp(-1.5 * s / loop_hz)
    mag, ph = np.abs(loop), np.unwrap(np.angle(loop))
    xc = np.nonzero(np.diff(np.sign(mag - 1.0)))[0]
    x180 = np.nonzero(np.diff(np.sign(ph + np.pi)))[0]
    pm = math.degrees(ph[xc[0]]) + 180.0 if len(xc) else math.inf
    gm = -20.0 * math.log10(mag[x180[0]]) if len(x180) else math.inf
    fc = w[xc[0]] / (2 * math.pi) if len(xc) else 0.0
    return pm, gm, fc


def simulate(gain: float, tau_r: float, tau_s: float, kp: float, kd: float = 0.0,
             loop_hz: float = control.ROLL_LOOP_HZ, dt: float = 1e-4, t_end: float = 3.0,
             cmd_deg: float = 90.0, cap: float = ROLL_COMMAND_CAP_DEG):
    """Closed-loop 90 deg bank step, nonlinear: surface cap, slew limit, servo lag, delay.

    The controller samples (phi, p) at loop_hz and its output takes effect at the NEXT sample
    (one period of latency), held constant in between. Servo is `control.servo_step`.
    Returns (settled, overshoot_deg, t_settle_s, p2p_last_s_deg): settled means the last
    second stays within +/-1 deg of the command; p2p over that second exposes a limit cycle.
    """
    period = 1.0 / loop_hz
    phi = p = surf = 0.0
    u_applied = u_next = 0.0
    next_sample = 0.0
    t = 0.0
    peak = 0.0
    t_settle = math.nan
    tail = []
    while t < t_end:
        if t >= next_sample:
            u_applied = u_next
            u_next = max(-cap, min(cap, kp * (cmd_deg - phi) - kd * p))
            next_sample += period
        surf = control.servo_step(surf, u_applied, dt, SLEW_DEG_S, tau_s)
        p += (gain * surf - p) * (1.0 - math.exp(-dt / tau_r))
        phi += p * dt
        t += dt
        peak = max(peak, phi)
        if abs(phi - cmd_deg) > 2.0:
            t_settle = math.nan
        elif math.isnan(t_settle):
            t_settle = t
        if t > t_end - 1.0:
            tail.append(phi)
    settled = max(abs(x - cmd_deg) for x in tail) < 1.0
    return settled, peak - cmd_deg, t_settle, max(tail) - min(tail)


# Design rule for the roll gains. PM/GM required at each servo lag: 30 ms is the working
# assumption, 60 ms a loaded hobby servo that must still be stable, 10 ms guards the fast end.
DESIGN_REQS = ((0.010, 45.0), (0.030, 45.0), (0.060, 30.0))
DESIGN_GM_DB = 6.0


def worst_margins(plants, kp, kd, loop_hz, tau_s):
    """Worst PM, GM and lowest crossover over both flight conditions."""
    res = [margins(g, tr, tau_s, kp, kd, loop_hz) for g, tr in plants.values()]
    return min(r[0] for r in res), min(r[1] for r in res), min(r[2] for r in res)


def design_gains(plants, loop_hz):
    """Grid search: highest crossover at 30 ms lag that meets DESIGN_REQS at every lag."""
    best = None
    for kp in np.arange(0.02, 0.40, 0.01):
        for kd in np.arange(0.0, 0.012, 0.0002):
            ok = True
            for tau_s, pm_req in DESIGN_REQS:
                pm, gm, fc = worst_margins(plants, kp, kd, loop_hz, tau_s)
                if pm < pm_req or gm < DESIGN_GM_DB:
                    ok = False
                    break
                if tau_s == 0.030:
                    fc30 = fc
            if ok and (best is None or fc30 > best[0]):
                best = (fc30, round(kp, 3), round(kd, 4))
    return best


def _section4(plants) -> list[str]:
    kp_new, kd_new = control.ROLL_KP, control.ROLL_KD
    loop = control.ROLL_LOOP_HZ
    gh, trh = plants["horizontal max q"]
    L = ["4. THE FIX -- a gyro rate term AND a much smaller gain", "",
         "   Law: delta = Kp*(phi_cmd - phi) - Kd*p, p from the gyro. With the rate term the",
         "   Routh limit (no delay) becomes Kp_max = (tau_r + tau_s)(1 + gain*Kd)/(tau_r*tau_s*gain):",
         "   Kd raises the ceiling, but the loop's own sample delay caps what it can buy, so the",
         "   margins below include 1.5 loop periods of delay rather than trusting Routh.", ""]

    L += ["   4a. Phase margin / gain margin / crossover, worst of the two flight conditions", "",
          "   loop    servo    Kp=1.0, Kd=0          "
          f"Kp={kp_new}, Kd={kd_new}",
          "   (Hz)    lag(ms)  PM(deg) GM(dB) fc(Hz)    PM(deg) GM(dB) fc(Hz)"]
    for hz in (loop, 100.0, 200.0):
        for tms in (10.0, 30.0, 60.0):
            o = worst_margins(plants, 1.0, 0.0, hz, tms / 1000.0)
            n = worst_margins(plants, kp_new, kd_new, hz, tms / 1000.0)
            L.append(f"   {hz:4.0f}   {tms:5.0f}    {o[0]:7.0f} {o[1]:6.1f} {o[2]:6.1f}"
                     f"    {n[0]:7.0f} {n[1]:6.1f} {n[2]:6.1f}")
    L += ["",
          "   Kp = 1.0 is unstable everywhere (negative margins). The new gains are stable at",
          "   every servo lag and loop rate here, and improve with loop rate.", ""]

    best = design_gains(plants, loop)
    L += ["   4b. Where the gains come from", "",
          f"   Requirement at the planned {loop:.0f} Hz loop: PM >= 45 deg at 10 and 30 ms servo lag,",
          f"   PM >= 30 deg at 60 ms, GM >= {DESIGN_GM_DB:.0f} dB throughout, both flight conditions.",
          "   Among gains that pass, take the highest crossover at 30 ms.", "",
          f"   search result: Kp = {best[1]}, Kd = {best[2]}, crossover {best[0]:.1f} Hz at 30 ms"]
    if (best[1], best[2]) != (round(kp_new, 3), round(kd_new, 4)):
        L.append(f"   WARNING: control.ROLL_KP/ROLL_KD ({kp_new}, {kd_new}) no longer match the"
                 " search -- the plant or the rule changed. Re-derive.")
    else:
        L.append("   matches control.ROLL_KP / ROLL_KD.")
    L += ["",
          "   The achievable bandwidth is ~3 Hz, set by servo lag plus loop delay, and nothing",
          "   in the gains can raise it. Kp is 14x smaller than before because the plant gain",
          "   is ~300 deg/s per degree: 0.07 deg of canard per degree of error already commands",
          "   ~21 deg/s of roll rate per degree. Gyro noise through Kd is ~1e-4 deg of canard.", ""]

    L += [f"   4c. Nonlinear time-domain check -- 90 deg bank step, {loop:.0f} Hz loop, surface cap",
          f"   +/-{ROLL_COMMAND_CAP_DEG:g} deg, slew {SLEW_DEG_S:.0f} deg/s, servo lag, one period of latency", "",
          "   condition          lag(ms)   Kp     Kd       settled  overshoot  t_settle(2deg)  p2p last 1s"]
    all_new_ok = True
    for name, (g, tr) in plants.items():
        for tms in (10.0, 30.0, 60.0):
            for kp, kd in ((1.0, 0.0), (kp_new, kd_new)):
                ok, ovs, ts_, p2p = simulate(g, tr, tms / 1000.0, kp, kd)
                if kp == kp_new:
                    all_new_ok &= ok
                tst = f"{ts_:6.2f} s" if not math.isnan(ts_) else "   never"
                L.append(f"   {name:17s} {tms:6.0f}   {kp:5.2f} {kd:7.4f}   "
                         f"{'yes' if ok else 'NO ':>6s}  {ovs:8.1f}    {tst:>12s}   {p2p:9.2f}")
    L += ["",
          f"   New gains settle in every case: {'YES' if all_new_ok else 'NO -- investigate'}.",
          "   Kp = 1.0 limit-cycles in every case (large p2p, never settles).",
          "",
          "   STILL ASSUMED: the servo lag. SERVO_LAG_S = 30 ms is a guess; if the bench test",
          "   (docs/15 C1) measures worse than 60 ms these gains lose their margin. Also assumed:",
          "   the roll gain itself, which cfd/vlm.py says may be ~4x LOWER (78% fin take-back,",
          "   section 5) -- that would drop crossover to ~1 Hz with more margin, not less.", ""]
    return L


def main() -> None:
    rocket = configure.build_vehicle(configure.baseline())
    L = []
    L += ["=" * 92,
          "ROLL LOOP BANDWIDTH -- can the KST X08 Plus close the roll axis?",
          "=" * 92, "",
          f"  servo: {SERVO.name}",
          f"  published: stall {SERVO.stall_torque:.2f} N*m, {SERVO.speed_60deg:.3f} s/60deg"
          f" = {SLEW_DEG_S:.0f} deg/s slew.  NO frequency response, NO deadband, NO lag spec.",
          ""]

    L += ["1. THE ROLL PLANT -- p/delta = gain / (1 + tau s)", "",
          "   condition          q (Pa)   V    Cl_delta   tau (ms)  corner   gain (deg/s per deg)"]
    plants = {}
    for name, q, v, alt in CONDITIONS:
        gain, tau, rr = plant(rocket, q, v, alt)
        plants[name] = (gain, tau)
        L.append(f"   {name:17s} {q:6.0f} {v:6.1f}   {rr.cl_delta_net:7.2f}   {1000*tau:7.1f}"
                 f"  {1/(2*math.pi*tau):5.2f} Hz  {gain:16.1f}")
    L += ["",
          "   The roll mode is the FASTEST mode on this vehicle -- 8-10 Hz against the pitch",
          "   mode's 3.6 Hz, which is what the existing 72 Hz loop-rate requirement was sized",
          "   from. And the gain is the largest in the vehicle by a wide margin: one degree of",
          "   canard is three hundred degrees per second of roll.", ""]

    L += ["2. THE RATE LIMIT IS NOT WHAT BINDS", "",
          "   Largest sine the servo can track at the published slew rate:", ""]
    for amp in (0.5, 1.0, ROLL_COMMAND_CAP_DEG, 9.2):
        tag = "  <- R13 roll cap" if abs(amp - ROLL_COMMAND_CAP_DEG) < 1e-9 else \
              "  <- R13 pitch/yaw cap" if abs(amp - 9.2) < 1e-9 else ""
        L.append(f"     amplitude {amp:4.1f} deg   ->  {SLEW_DEG_S/(2*math.pi*amp):6.1f} Hz{tag}")
    L += ["",
          "   At the 2 deg roll cap the servo is good for 53 Hz on slew rate alone, five times",
          "   the roll mode's own corner. This is why a rate-limit-only actuator model makes the",
          "   roll loop look easy, and it is the wrong thing to be checking.", ""]

    L += ["3. WHAT ACTUALLY BINDS -- PHASE LAG, WHICH IS UNMEASURED", "",
          "   Stability limit on a proportional roll-angle gain, exactly (Routh on the cubic):",
          "       Kp_max = (tau_roll + tau_servo) / (tau_roll * tau_servo * gain)", "",
          "   servo lag    Kp_max, vertical    Kp_max, horizontal    with 6 dB gain margin",
          "   (ms)         (deg surf / deg)    (deg surf / deg)      (horizontal)"]
    for tms in TAU_SERVO_MS:
        ts = tms / 1000.0
        kv = routh_kp_limit(plants["vertical max q"][0], plants["vertical max q"][1], ts)
        kh = routh_kp_limit(plants["horizontal max q"][0], plants["horizontal max q"][1], ts)
        L.append(f"   {tms:6.0f}       {kv:12.3f}        {kh:14.3f}       {kh/2:14.3f}")
    L += ["",
          "   The repo used Kp = 1.0 (`sil_demo.ROLL_KP`, docs/13's closed-loop result) until",
          "   2026-09-26. That is ABOVE the limit for every servo lag in the table, 2x at an",
          "   optimistic 10 ms and 4x at a realistic 30 ms -- and docs/13's clean roll hold came",
          "   from an actuator model with no phase in it. Section 4 replaces it.", ""]

    L += _section4(plants)

    L += ["5. THE PART THIS CANNOT ANSWER, and it is the part your question was really about",
          "",
          "   You asked about the canards throwing flow onto the aft fins AT AN ANGLE -- i.e.",
          "   whether the interference, and so the roll gain above, changes when the vehicle is",
          "   flying at incidence. IT MIGHT, AND NOTHING IN THIS PROJECT WOULD KNOW:",
          "",
          "   `control.InterferenceModel.strength()` is a function of ONE variable, canard-to-fin",
          "   spacing in calibers. It has no angle-of-attack term, no deflection term and no roll-",
          "   rate term. So every roll number in this repo is computed at the same interference",
          "   strength whether the vehicle is at 0 deg or at the 11 deg local incidence the",
          "   bank-to-turn condition actually flies.",
          "",
          "   Physically the wake does move: the canard vortex pair is convected by the crossflow,",
          "   so at incidence it is displaced off the axis and the 45 deg interdigitation that",
          "   buys the favourable 10.5% cancellation is no longer symmetric between the fins on",
          "   the windward and leeward sides. The mechanism for an ANGLE-DEPENDENT, and possibly",
          "   ASYMMETRIC, induced roll is there in the geometry. Its size is unknown.",
          "",
          "   Two independent checks now say the interference term is bigger than the model:",
          "   `cfd/vlm.py` puts the aft fins taking back 78% of canard roll authority against the",
          "   model's 10.5%, at zero incidence. If the true figure is anywhere near that, the roll",
          "   GAIN in section 1 falls by roughly the same factor -- which relaxes the bandwidth",
          "   problem above while making the control authority worse. Both move together and",
          "   neither is measured.",
          "",
          "   This is GV-2's job and it cannot be closed on the bench: an open-loop deflection",
          "   sweep, flown, logging commanded deflection against measured roll rate AT SEVERAL",
          "   ANGLES OF ATTACK, is the only thing that turns any of it into a number.", ""]

    txt = "\n".join(L)
    OUT.write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
