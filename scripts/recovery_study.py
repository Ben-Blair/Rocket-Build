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

from design.configure import (
    BASELINE_MOTOR_FILE,
    LIMITS,
    baseline,
    build_vehicle,
    evaluate,
)
from design.motors import load_eng
from design.recovery import (
    Canopy,
    bulk_density_sensitivity,
    check_packing,
    required_bay_length,
    simulate_descent,
    size_for_descent_rate,
)

ROOT = Path(__file__).resolve().parents[1]
MOTOR_DIR = ROOT / "data" / "motors"


# The frozen motor is pulled from configure so this study always compares the vehicle you
# are actually building against the alternatives, even if the baseline motor changes.
CANDIDATES = [
    "Cesaroni_821J430-18A.eng",
    BASELINE_MOTOR_FILE.name,
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
        ev = evaluate(baseline(motor=motor), deflection_deg=8.0)
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
    print("RECOVERY BAY PACKING  --  does the nylon actually fit?")
    print("=" * 100)

    params = baseline()
    rocket = build_vehicle(params)
    bay = next(t for t in rocket.tubes if t.name == "recovery bay")
    packing = check_packing(bay.inner_diameter, bay.length)

    print(packing)
    print(packing.report(caliber=params.outer_diameter))

    print("\n  sensitivity to canopy packing density:")
    print(f"    {'density':>12s} {'bay length':>12s} {'calibers':>10s}")
    for rho, length, cal in bulk_density_sensitivity(
        bay.inner_diameter, params.outer_diameter
    ):
        flag = "  <- assumed" if abs(rho - 400.0) < 1e-6 else ""
        print(f"    {rho:9.0f} kg/m3 {length * 1000:9.0f} mm {cal:10.2f}{flag}")

    need = required_bay_length(bay.inner_diameter)
    span = bulk_density_sensitivity(bay.inner_diameter, params.outer_diameter)
    lo_cal, hi_cal = span[-1][2], span[0][2]

    print(f"""
The bay is {params.recovery_bay_cal:.2f} cal and it FITS, with {(bay.length - need) * 1000:.0f} mm to spare. That is worth stating
plainly because it was not always the answer: 4.5 was a number someone typed, nothing had
ever checked it, and the first version of this check said it was 11 mm SHORT.

That verdict was wrong, and how it was wrong is the useful part. Packed volume was being
estimated as budgeted mass divided by an assumed bulk density -- two guesses multiplied
together. The mass budget carries 280 g for the main; a real Fruity Chutes Iris Ultra 60"
Compact is 193 g. Feed a canopy that heavy into a density that high and you manufacture a
shortfall that does not exist in the hardware.

The table above is the calculation those vendor numbers replaced. Read it as the reason to
go and source a real figure, not as a range to pick a bay length from: at {lo_cal:.2f} cal you would
have called 4.5 comfortable and at {hi_cal:.2f} cal you would have cut a new tube, and nothing in
the estimate tells you which. One published number settled it in ten minutes.

What is still an estimate, and what to do about it:

  1. THE HARNESS, NOMEX AND HARDWARE are still density estimates -- see the NOTE above for
     the exact list. They are a smaller share of the volume than the canopies were, and
     they pack far more predictably, so the remaining uncertainty is narrower than what
     you started with. Retire them the same way if you want the number tight.
  2. THE VENDOR FIGURES ASSUME A TIGHT PACK, in their own words. Treat {need / params.outer_diameter:.2f} cal as the
     optimistic end. {(bay.length - need) * 1000:.0f} mm of margin on a tight-pack number is real but it is not
     generous, and a canopy you have to fight into the tube on the pad is a canopy you
     will pack badly.
  3. MEASURE ONCE YOU OWN IT. Pack the real main, slide it into a tube of known ID, read
     the length, and set `measured_volume` from that instead. Nothing here beats the part
     in your hands.

Do NOT wire recovery_bay_cal to required_bay_length() and let the geometry rebuild itself.
The airframe is frozen on purpose, and this check exists to CONFIRM the freeze, not to
drive it -- see docs/01-next-steps.md, correction 4. The one time the geometry was changed
on the strength of the estimate alone, the estimate turned out to be the thing that was
wrong.

One more thing this check does not model: dual deploy needs two SEPARATE pressure vessels,
and the vehicle has one recovery bay with the nav bay forward of the canard module. The
charge wiring therefore has to run from the nav bay, past four servos and their power bus,
across a separation joint, into the recovery bay. That is an architecture question, not a
volume question, and it is still open.""")

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
