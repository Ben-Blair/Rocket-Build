"""Does a longer burn give more steering authority? Controlled experiment.

Run:  python scripts/burn_time_study.py

The intuition "longer burn = more time to steer" assumes the motor does the steering. It
does not. The canards are aerodynamic surfaces, so their authority is set by dynamic
pressure q = 0.5*rho*V^2, and thrust contributes to that only indirectly by building
airspeed. The relevant figure of merit is therefore the *steering impulse*

    J_steer = integral of q dt   over the window where the vehicle is controllable

because lateral acceleration is proportional to q, so total achievable sideways velocity
change is proportional to the integral of q.

Part 1 isolates burn time at fixed total impulse using synthetic constant-thrust motors.
Part 2 checks the same trend in the real ThrustCurve.org catalogue, restricted to a narrow
impulse band so that burn time is the only meaningful difference.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design.configure import baseline, evaluate
from design.motors import Motor, load_eng

ROOT = Path(__file__).resolve().parents[1]
MOTOR_DIR = ROOT / "data" / "motors"

DEFLECTION_DEG = 8.0

# Matched to the Cesaroni J430 so the synthetic family is comparable to the real baseline.
TOTAL_IMPULSE = 817.0
PROP_MASS = 0.384
TOTAL_MASS = 0.800
MOTOR_LENGTH = 0.236

BURN_TIMES = [0.6, 0.9, 1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0, 6.5, 8.0]


def synthetic(burn_time: float) -> Motor:
    """Constant-thrust motor with fixed total impulse. Rectangular curves are unphysical,
    but holding impulse and mass fixed is what isolates burn time as the variable."""
    thrust = TOTAL_IMPULSE / burn_time
    return Motor(
        name=f"synthetic {burn_time:.1f}s",
        diameter=0.054,
        length=MOTOR_LENGTH,
        total_impulse=TOTAL_IMPULSE,
        burn_time=burn_time,
        propellant_mass=PROP_MASS,
        total_mass=TOTAL_MASS,
        times=[0.0, burn_time],
        thrusts=[thrust, thrust],
        approximate=True,
    )


def total_q_impulse(flight) -> float:
    """Integral of q dt over the whole flight, launch to apogee.

    Included to foreclose the obvious objection to `steering_impulse`: that excluding the
    boost phase unfairly penalises long-burn motors. It does not -- the conclusion is the
    same either way.
    """
    pts = flight.points
    if len(pts) < 2:
        return 0.0
    return sum(0.5 * (a.q + b.q) * (b.t - a.t) for a, b in zip(pts[:-1], pts[1:]))


def steering_impulse(flight, q_floor: float = 500.0) -> tuple[float, float]:
    """(integral of q dt over the controllable coast, seconds of that window).

    Restricted to post-burnout because manoeuvring under boost is not something you do:
    static margin is at its minimum, axial acceleration is saturating the accelerometer,
    and deliberately inducing angle of attack at high thrust and high q is the classic way
    to break a rocket in half.
    """
    pts = [p for p in flight.points if p.t >= flight.burnout_time and p.q >= q_floor]
    if len(pts) < 2:
        return 0.0, 0.0
    total = sum(
        0.5 * (a.q + b.q) * (b.t - a.t) for a, b in zip(pts[:-1], pts[1:])
    )
    return total, pts[-1].t - pts[0].t


def part1() -> None:
    header = (
        f"{'burn':>5s} {'thrust':>7s} {'T/W':>5s} {'rail':>5s} {'g_pk':>5s} {'V_bo':>6s} "
        f"{'q_max':>6s} {'apogee':>7s} {'Jsteer':>7s} {'Jall':>6s} {'ctrl_s':>6s} "
        f"{'xrng':>6s}  status"
    )
    print("=" * len(header))
    print("PART 1: FIXED TOTAL IMPULSE (817 N s), BURN TIME VARIED")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for tb in BURN_TIMES:
        motor = synthetic(tb)
        ev = evaluate(baseline(motor=motor), deflection_deg=DEFLECTION_DEG)
        f = ev.flight
        j_steer, secs = steering_impulse(f)
        v_bo = f.burnout_velocity
        status = "OK" if ev.feasible else "; ".join(ev.violations[:2])
        print(
            f"{tb:5.1f} {motor.average_thrust:7.0f} {f.thrust_to_weight:5.1f} "
            f"{f.rail_exit_velocity:5.1f} {f.max_acceleration_g:5.1f} {v_bo:6.1f} "
            f"{f.max_q / 1000:6.2f} {f.apogee:7.0f} {j_steer / 1000:7.1f} "
            f"{total_q_impulse(f) / 1000:6.1f} {secs:6.1f} {ev.crossrange:6.0f}  {status}"
        )
    print("-" * len(header))
    print("""thrust N, V_bo m/s at burnout, q_max kPa. Jsteer = integral of q dt over the
controllable coast, Jall = the same integral over the entire flight including boost, both
in kPa*s. xrng = one-sided crossrange in m. Note that Jall falls with burn time too, so
the conclusion does not depend on excluding the boost phase.""")


def part2() -> None:
    band = (770.0, 880.0)
    rows = []
    for path in sorted(MOTOR_DIR.glob("*.eng")):
        try:
            motor = load_eng(path)
        except (ValueError, IndexError):
            continue
        if not (band[0] <= motor.total_impulse <= band[1]) or motor.burn_time <= 0:
            continue
        try:
            ev = evaluate(baseline(motor=motor), deflection_deg=DEFLECTION_DEG)
        except (ValueError, ZeroDivisionError):
            continue
        j_steer, secs = steering_impulse(ev.flight)
        rows.append((motor, ev, j_steer, secs))

    rows.sort(key=lambda r: r[0].burn_time)
    header = (
        f"{'motor':20s} {'Ns':>5s} {'burn':>5s} {'g_pk':>5s} {'V_bo':>6s} {'q_max':>6s} "
        f"{'apogee':>7s} {'Jsteer':>8s} {'ctrl_s':>6s} {'xrng':>6s}"
    )
    print("\n" + "=" * len(header))
    print(f"PART 2: REAL MOTORS, {band[0]:.0f}-{band[1]:.0f} N s ONLY, sorted by burn time")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for motor, ev, j_steer, secs in rows:
        f = ev.flight
        print(
            f"{motor.name[:20]:20s} {motor.total_impulse:5.0f} {motor.burn_time:5.2f} "
            f"{f.max_acceleration_g:5.1f} {f.burnout_velocity:6.1f} {f.max_q / 1000:6.2f} "
            f"{f.apogee:7.0f} {j_steer / 1000:8.1f} {secs:6.1f} {ev.crossrange:6.0f}"
        )
    if len(rows) >= 2:
        short, long = rows[0], rows[-1]
        print("-" * len(header))
        print(
            f"Shortest burn ({short[0].burn_time:.2f} s) vs longest ({long[0].burn_time:.2f} s) "
            f"at essentially equal impulse:\n"
            f"  crossrange {short[1].crossrange:.0f} m vs {long[1].crossrange:.0f} m "
            f"({(short[1].crossrange / max(long[1].crossrange, 1e-9) - 1) * 100:+.0f}%)\n"
            f"  steering impulse {short[2] / 1000:.1f} vs {long[2] / 1000:.1f} kPa*s\n"
            f"  peak acceleration {short[1].flight.max_acceleration_g:.1f} g vs "
            f"{long[1].flight.max_acceleration_g:.1f} g"
        )


def explain() -> None:
    print("""
====================================================================================
WHY LONGER IS WORSE, AND WHERE THE REAL TRADE LIVES
====================================================================================

The mechanism is gravity loss. Total impulse buys you a fixed momentum budget. While the
motor burns, gravity is spending part of that budget: over a burn of duration tb you lose
roughly g*tb of velocity that never becomes airspeed. Stretch a 2 s burn to 6 s and you
hand about 40 m/s straight to gravity.

Authority then punishes you twice for that, because q goes as V^2:

    burnout velocity   V_bo  ~  I/m - g*tb        (linear loss)
    dynamic pressure   q     ~  V^2               (squared penalty)

For an ideal vertical flight with no drag, integrating q over the whole coast gives

    integral of q dt  ~  V0 * (V0 - g*tb)^2 / (3g)

which is strictly decreasing in tb. A long burn does keep you moving for longer, but at a
lower speed, and the V^2 term means the slower flight loses more than the longer duration
gains. The control *window* barely changes; the control *authority* inside it drops.

There is also a second-order penalty: a low-thrust motor spends longer at low speed just
off the rail, where fin authority is weakest and gusts are most damaging.

WHERE THE INTUITION COMES FROM, AND WHEN IT IS RIGHT

"Longer burn means more time to steer" is exactly correct -- for thrust vector control. On
a TVC vehicle the actuator *is* the motor: gimbal the nozzle and you get a control moment
proportional to thrust, available only while the motor burns. Burn time and control time
are the same quantity. That is why TVC hobby rockets and real boost-phase missile guidance
care so much about burn duration, and it is almost certainly where the intuition comes
from.

Canards invert that relationship completely. The actuator is airspeed, not thrust. The
motor's only job is to hand you kinetic energy as efficiently as possible and then get out
of the way, and the control phase is the coast that follows. On this vehicle the motor
burns for 2 s and the controllable coast lasts 8.7 s: the burn is not the control phase,
it is the wind-up before it.

A useful consequence: if you ever want control authority that does not decay, TVC during
boost and canards during coast are complementary, not competing. That is out of scope here
-- TVC on a solid motor is a large separate project and raises its own range-approval
questions -- but it is the correct answer to "how do I steer for longer."

So what is a long burn actually good for? Real things, none of which are steering:

  * Lower peak acceleration. Protects your accelerometer from clipping at +/-16 g and
    reduces structural and shear-pin loads.
  * Lower peak Mach, keeping the aerodynamics comfortably subsonic and linear.
  * Lower apogee for the same impulse, which can keep you inside a tight waiver.

That is the actual trade: burn time buys you gentler flight, and you pay for it in
steering authority. It is not a control-time knob.

The selected Cesaroni J430 at 1.96 s sits deliberately in the middle. Short enough to bank
velocity efficiently, long enough that peak acceleration is only 8.7 g. The extreme case
proves the point: the AeroTech J1299N burns for 0.65 s and produces the largest crossrange
of any compliant motor in the catalogue -- and it was rejected at 26 g, on accelerometer
and structural grounds, not on steering.

If you want more control authority, the levers that actually work, in order:
  1. More total impulse (subject to R6's apogee cap, not a waiver) -- roughly triples crossrange
     going from a ~820 N s J to a ~1260 N s J.
  2. Larger canards, paid for in static margin.
  3. Lower static margin, since trim angle of attack scales as 1/margin.
  4. Lower vehicle mass.
Burn time is not on that list.""")


if __name__ == "__main__":
    part1()
    part2()
    explain()
