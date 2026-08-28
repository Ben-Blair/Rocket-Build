"""With no altitude ceiling and no field boundary, how far will you walk -- and can you
afford to?

Run:  python scripts/recovery_study.py

Compares the candidate motors on recovery footprint. This began as the constraint that
replaced the altitude waiver; the club has since confirmed (Aug 2026) that the recovery
area is effectively unbounded, so the walk is now a cost in launch-day time and search
risk rather than a hard limit. It still bounds apogee, just for softer reasons -- see R6.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design.configure import LIMITS, DesignParams, evaluate
from design.motors import load_eng
from design.recovery import Canopy, simulate_descent, size_for_descent_rate

ROOT = Path(__file__).resolve().parents[1]
MOTOR_DIR = ROOT / "data" / "motors"

BASE = dict(
    outer_diameter=0.0794,
    wall_thickness=0.0023,
    aft_semispan_cal=1.55,
    canard_semispan_cal=0.85,
)

CANDIDATES = [
    "Cesaroni_821J430-18A.eng",
    "Cesaroni_1261J449-15A.eng",
    "Cesaroni_1266J760-19A.eng",
    "AeroTech_HP-K535W.eng",
    "Cesaroni_1635K445-17A.eng",
    "Cesaroni_1679K630-15A.eng",
]

TARGET_LANDING_RATE = 5.0  # m/s
MAIN_DEPLOY_ALT = 200.0  # m, ~650 ft


def main() -> None:
    LIMITS["apogee_max_m"] = 1e9  # no ceiling; that is the point of this study

    print("=" * 100)
    print("RECOVERY FOOTPRINT  --  a cost, no longer a hard boundary")
    print("=" * 100)

    rows = []
    for fname in CANDIDATES:
        path = MOTOR_DIR / fname
        if not path.exists():
            print(f"  missing {fname}, skipping")
            continue
        motor = load_eng(path)
        ev = evaluate(DesignParams(motor=motor, **BASE), deflection_deg=8.0)
        dry = ev.masses.dry_mass

        main_d = size_for_descent_rate(dry, TARGET_LANDING_RATE)
        main = Canopy("main", main_d, 2.2)
        drogue = Canopy("drogue", 0.457, 1.5)  # 18 in

        desc = simulate_descent(
            ev.flight.apogee, dry, drogue, main, main_deploy_altitude=MAIN_DEPLOY_ALT
        )
        downrange = ev.flight.points[-1].x if ev.flight.points else 0.0
        rows.append((motor, ev, desc, downrange, main_d))

    header = (
        f"{'motor':18s} {'apogee':>7s} {'Mach':>5s} {'xrng':>6s} {'descent':>8s} "
        f"{'main':>6s} {'KE':>7s} | {'walk @5mph':>10s} {'@10mph':>8s} {'@15mph':>8s} {'@20mph':>8s}"
    )
    print(header)
    print("-" * len(header))
    for motor, ev, desc, downrange, main_d in rows:
        winds = sorted(desc.drift_by_wind)
        walks = [desc.drift_by_wind[w] + downrange for w in winds]
        print(
            f"{motor.name[:18]:18s} {ev.flight.apogee:7.0f} {ev.flight.max_mach:5.2f} "
            f"{ev.crossrange:6.0f} {desc.total_time:7.0f}s {main_d * 39.37:5.0f}\" "
            f"{desc.landing_energy / 1.35582:6.0f}f | "
            + " ".join(f"{w:9.0f}m" for w in walks[:1])
            + " " + " ".join(f"{w:7.0f}m" for w in walks[1:])
        )

    print("-" * len(header))
    print("""apogee m, xrng = steering crossrange m, descent = time under canopy, main = main
canopy diameter for a 5 m/s landing, KE = landing energy in ft-lbf, walk = distance from
the pad to the landing point including ascent downrange.

Read the last four columns as "how long does this flight cost me, and how likely am I to
lose the vehicle and its data?" The recovery area is unbounded, so none of these walks put
the rocket off the property -- but drift scales with descent time, which scales with
apogee, and a rocket you cannot find is a flight you did not get. Doubling apogee roughly
doubles the walk, and a 15 mph day is not unusual.""")

    print("\n" + "=" * 100)
    print("WHAT TO DO WITH AN UNLIMITED CEILING")
    print("=" * 100)
    print("""An unlimited waiver removes a constraint; it does not create an objective. Nothing
about this project gets better by flying higher, and several things get worse:

  * Recovery risk per flight. You need five or six flights. Every one that lands off the
    property, in a tree, or unfound costs you a vehicle, a flight computer, and -- worst --
    the logged data that the whole thesis depends on.
  * Transonic aerodynamics. Above roughly Mach 0.8 the Barrowman method, the linear control
    derivatives and the controller derived from them all stop being valid, and the centre
    of pressure moves sharply. A guidance project that strays transonic has to solve a much
    harder aero problem for no additional credit.
  * Visibility. The deliverable is a demonstration of steering. A manoeuvre you can see and
    film at 3-5000 ft is worth more in a defence than a dot at 15,000 ft.
  * Cost per flight, which directly limits how many flights you get.

What the freedom is genuinely worth: buying more total impulse, because control authority
scales with dynamic pressure. Going from ~820 N s to ~1260 N s roughly triples crossrange
while staying comfortably subsonic. That is the trade worth taking.

Take some of the freedom, not all of it.""")


if __name__ == "__main__":
    main()
