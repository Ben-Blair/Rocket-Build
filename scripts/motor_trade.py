"""Rank every real 54 mm L2 motor against the baseline airframe.

Run:  python scripts/fetch_motors.py --diameter 54 --classes J K
      python scripts/motor_trade.py

Selection logic for a *guidance* project, in priority order:

  1. Hard requirements from docs/00-requirements.md: T/W >= 5, rail exit >= 15 m/s,
     static margin 1.4 - 3.0 cal, apogee inside the waiver window.
  2. Max Mach <= 0.6, tighter than the 0.8 requirement. Barrowman, the linear control
     derivatives, and the controller you design from them are all subsonic-only. Staying
     well clear of the transonic region is worth more than altitude.
  3. Peak axial acceleration <= 16 g. Most MEMS accelerometers you would put on a flight
     computer clip at +/-16 g. Clipping during boost corrupts the velocity and attitude
     estimate exactly when you cannot afford it. A gentler motor is a cheaper fix than a
     high-g accelerometer plus sensor fusion across two ranges.
  4. Then maximise usable control: seconds of coast with meaningful dynamic pressure, and
     the resulting crossrange.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse

from design.configure import LIMITS, baseline, evaluate
from design.motors import load_eng

ROOT = Path(__file__).resolve().parents[1]
MOTOR_DIR = ROOT / "data" / "motors"


MACH_PREFERRED = 0.60
ACCEL_LIMIT_G = 16.0
DEFLECTION_DEG = 8.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apogee-max", type=float, default=None,
                    help="metres AGL; raise this if your field waiver allows it")
    ap.add_argument("--mach-max", type=float, default=MACH_PREFERRED)
    args = ap.parse_args()
    if args.apogee_max is not None:
        LIMITS["apogee_max_m"] = args.apogee_max
    mach_pref = args.mach_max
    print(f"Apogee window {LIMITS['apogee_min_m']:.0f} - {LIMITS['apogee_max_m']:.0f} m AGL, "
          f"preferred max Mach {mach_pref:.2f}\n")

    files = sorted(MOTOR_DIR.glob("*.eng"))
    if not files:
        print("No .eng files. Run: python scripts/fetch_motors.py --diameter 54 --classes J K")
        return

    rows = []
    skipped = 0
    for path in files:
        try:
            motor = load_eng(path)
        except (ValueError, IndexError):
            skipped += 1
            continue
        if motor.requires_level != 2 or motor.burn_time <= 0 or motor.propellant_mass <= 0:
            skipped += 1
            continue
        try:
            ev = evaluate(baseline(motor=motor), deflection_deg=DEFLECTION_DEG)
        except (ValueError, ZeroDivisionError):
            skipped += 1
            continue

        soft = []
        if ev.flight.max_mach > mach_pref:
            soft.append(f"Mach {ev.flight.max_mach:.2f}")
        if ev.flight.max_acceleration_g > ACCEL_LIMIT_G:
            soft.append(f"{ev.flight.max_acceleration_g:.0f} g")
        rows.append((motor, ev, soft))

    print(f"Evaluated {len(rows)} L2 motors ({skipped} skipped: wrong class or unparseable)\n")

    header = (
        f"{'motor':22s} {'cls':>3s} {'Ns':>6s} {'burn':>5s} {'T/W':>5s} {'rail':>5s} "
        f"{'g_pk':>5s} {'Mach':>5s} {'apogee':>7s} {'SM':>10s} {'ctrl_s':>6s} {'xrng':>6s}  notes"
    )

    passing = [r for r in rows if r[1].feasible and not r[2]]
    passing.sort(key=lambda r: -r[1].crossrange)

    print("=" * len(header))
    print("MOTORS MEETING EVERY HARD REQUIREMENT AND EVERY PREFERENCE")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for motor, ev, _ in passing:
        show(motor, ev, [])

    soft_fail = [r for r in rows if r[1].feasible and r[2]]
    soft_fail.sort(key=lambda r: -r[1].crossrange)
    print("\n" + "=" * len(header))
    print("MEET HARD REQUIREMENTS BUT VIOLATE A PREFERENCE (usable with justification)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for motor, ev, soft in soft_fail[:12]:
        show(motor, ev, soft)

    hard_fail = [r for r in rows if not r[1].feasible]
    print(f"\n{len(passing)} fully compliant, {len(soft_fail)} compliant with caveats, "
          f"{len(hard_fail)} rejected outright.")

    reasons: dict[str, int] = {}
    for _, ev, _ in hard_fail:
        for v in ev.violations:
            key = v.split()[0] + " " + v.split()[1] if len(v.split()) > 1 else v
            key = "apogee" if "apogee" in v else ("T/W" if "T/W" in v else
                  ("SM" if "SM" in v else ("Mach" if "Mach" in v else
                   ("rail" if "rail" in v else "other"))))
            reasons[key] = reasons.get(key, 0) + 1
    print("Rejection reasons: " + ", ".join(f"{k} x{v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])))


def show(motor, ev, soft) -> None:
    f = ev.flight
    print(
        f"{motor.name[:22]:22s} {motor.impulse_class:>3s} {motor.total_impulse:6.0f} "
        f"{motor.burn_time:5.2f} {f.thrust_to_weight:5.1f} {f.rail_exit_velocity:5.1f} "
        f"{f.max_acceleration_g:5.1f} {f.max_mach:5.2f} {f.apogee:7.0f} "
        f"{f.min_static_margin:4.2f}-{f.max_static_margin:<5.2f} "
        f"{ev.control_seconds:6.1f} {ev.crossrange:6.0f}  {', '.join(soft)}"
    )


if __name__ == "__main__":
    main()
