"""Design sweep: which (diameter, motor, fin) combinations satisfy the requirements?

Run:  python scripts/sweep.py
"""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design.configure import BASELINE_OD, BASELINE_WALL, DesignParams, evaluate
from design.motors import GENERIC

AIRFRAMES = {
    "75mm": (BASELINE_OD, BASELINE_WALL),
    "98mm": (0.1016, 0.0024),
}

MOTOR_KEYS = ["I-38", "I-54-long", "J-54", "J-54-long", "K-54", "K-54-long"]

# Aft fin semispan sets static stability; canard semispan sets control authority. They
# pull in opposite directions, which is the central trade of the whole airframe.
#
# These ranges must bracket the frozen design (canard 0.85, aft 1.55 cal -- see
# design/configure.py). They previously topped out at aft 1.20 / canard 0.70, which left
# the selected airframe outside the swept region entirely, so the sweep could not have
# recommended it and silently disagreed with every other script.
AFT_SPANS = [1.05, 1.25, 1.40, 1.55, 1.70]
CANARD_SPANS = [0.55, 0.70, 0.85, 1.00]
DEFLECTION_DEG = 8.0


def main() -> None:
    rows = []
    for (name, (od, wall)), key, aft_span, can_span in product(
        AIRFRAMES.items(), MOTOR_KEYS, AFT_SPANS, CANARD_SPANS
    ):
        motor = GENERIC[key]
        if motor.diameter > od - 2 * wall - 0.010:
            continue
        p = DesignParams(
            outer_diameter=od,
            wall_thickness=wall,
            motor=motor,
            aft_semispan_cal=aft_span,
            canard_semispan_cal=can_span,
        )
        rows.append((name, key, aft_span, can_span, evaluate(p, deflection_deg=DEFLECTION_DEG)))

    header = (
        f"{'tube':6s} {'motor':12s} {'aft':5s} {'can':5s} {'mass':>6s} {'L/D':>5s} "
        f"{'T/W':>5s} {'rail':>5s} {'Mach':>5s} {'apogee':>7s} {'SM':>10s} "
        f"{'g_lat':>6s} {'xrange':>7s} {'ctrl_s':>6s}  status"
    )
    print("=" * len(header))
    print("DESIGN SWEEP  (GENERIC placeholder motors -- replace with real .eng curves)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    rows.sort(key=lambda r: (not r[4].feasible, -r[4].crossrange))
    for name, key, span, rec, ev in rows:
        f = ev.flight
        g_lat = ev.pitch.lateral_accel_g if ev.pitch else 0.0
        status = "OK" if ev.feasible else "; ".join(ev.violations[:2])
        print(
            f"{name:6s} {key:12s} {span:5.2f} {rec:5.2f} {ev.masses.wet_mass:6.2f} "
            f"{ev.rocket.fineness:5.1f} {f.thrust_to_weight:5.1f} {f.rail_exit_velocity:5.1f} "
            f"{f.max_mach:5.2f} {f.apogee:7.0f} "
            f"{f.min_static_margin:4.2f}-{f.max_static_margin:<5.2f} "
            f"{g_lat:6.2f} {ev.crossrange:7.1f} {ev.control_seconds:6.1f}  {status}"
        )

    feasible = [r for r in rows if r[4].feasible]
    print("-" * len(header))
    print(f"{len(feasible)} of {len(rows)} configurations satisfy all requirements.")
    if feasible:
        best = feasible[0]
        ev = best[4]
        print(
            f"\nHighest crossrange feasible config: {best[0]} on {best[1]}, "
            f"aft semispan {best[2]:.2f} cal, canard semispan {best[3]:.2f} cal\n"
            f"  wet mass {ev.masses.wet_mass:.2f} kg, apogee {ev.flight.apogee:.0f} m "
            f"({ev.flight.apogee * 3.28084:.0f} ft), crossrange {ev.crossrange:.0f} m "
            f"in {ev.control_seconds:.1f} s of control\n"
            f"  canards cost {ev.sm_without_canards - ev.flight.max_static_margin:+.2f} cal "
            f"of static margin"
        )
    print(
        f"\nColumns: aft/can are aft fin and canard semispan in calibers; SM is the static\n"
        f"margin range over the powered and coast flight; g_lat is lateral acceleration at\n"
        f"{DEFLECTION_DEG:.0f} deg canard deflection at max coast dynamic pressure; xrange is the\n"
        f"one-sided manoeuvre crossrange from burnout to apogee."
    )


if __name__ == "__main__":
    main()
