"""How risky is the static margin actually? Monte Carlo + sensitivity + ballast sizing.

Run:  python scripts/robustness.py [--samples 20000]

The nominal rail-exit static margin is 1.52 cal, which is a perfectly normal high power
value. The question is not whether the nominal number is good -- it is whether it stays
good once the vehicle is built heavier than the budget, the CG lands somewhere other than
predicted, and Barrowman turns out to be a few percent off on CP.

Important framing: for a canard-controlled vehicle, static margin is NOT a
"more is better" quantity. Trim angle of attack, and therefore lateral acceleration, goes
as

    a_lat  ~  q * A * Cm_delta * delta / (m * SM)

so authority is inversely proportional to static margin. Adding a caliber of margin
directly divides your steering authority. The design target is a *band*, not a maximum:
stay above the safety floor with high confidence, and no higher than necessary.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import aero
from design.configure import DesignParams, build_vehicle
from design.mass import build_mass
from design.motors import load_eng

ROOT = Path(__file__).resolve().parents[1]

BASELINE = DesignParams(
    outer_diameter=0.0794,
    wall_thickness=0.0023,
    motor=load_eng(ROOT / "data" / "motors" / "Cesaroni_1261J449-15A.eng"),
    aft_semispan_cal=1.55,
    canard_semispan_cal=0.85,
)

# 1-sigma uncertainties. These are judgement calls; they are stated explicitly so a
# reviewer can argue with them rather than having them buried in an assumption.
SIGMA = dict(
    # Fractional mass error, applied per component. Structural items come from geometry
    # and material density so they are tighter; budgeted subsystems are guesses.
    mass_structural=0.08,
    mass_budgeted=0.20,
    # Axial position error of each component's centre of mass, in metres.
    position=0.015,
    # CP prediction error, in calibers. Barrowman plus the linearised body-lift term.
    cp_calibers=0.35,
    # Motor total mass, fractional. Manufacturer data is good; loading varies slightly.
    motor_mass=0.03,
)

SM_FLOOR = 1.4  # hard safety floor
SM_TARGET = 1.5  # R1 lower bound
SM_CEILING = 3.0  # above this the vehicle weathercocks hard and fights the controller

BUDGETED = ("budget", "contingency", "servos", "shafts", "structure:")


def is_budgeted(name: str) -> bool:
    return any(k in name for k in BUDGETED)


def sample(n: int, seed: int = 0, ballast_kg: float = 0.0, ballast_x: float = 0.15,
           params: DesignParams | None = None):
    """Monte Carlo over mass, position and CP uncertainty. Returns rail-exit SM samples."""
    params = params or BASELINE
    rng = np.random.default_rng(seed)
    rocket = build_vehicle(params)
    masses = build_mass(rocket, params.motor)
    d = rocket.diameter

    items = [it for it in masses.items if it.name != "propellant"]
    prop = next(it for it in masses.items if it.name == "propellant")

    base_m = np.array([it.mass for it in items])
    base_x = np.array([it.x for it in items])
    frac_sigma = np.array(
        [SIGMA["mass_budgeted"] if is_budgeted(it.name) else SIGMA["mass_structural"]
         for it in items]
    )

    m = base_m * (1.0 + rng.normal(0.0, frac_sigma, size=(n, len(items))))
    m = np.clip(m, 0.0, None)
    x = base_x + rng.normal(0.0, SIGMA["position"], size=(n, len(items)))

    prop_m = prop.mass * (1.0 + rng.normal(0.0, SIGMA["motor_mass"], size=n))

    total_m = m.sum(axis=1) + prop_m + ballast_kg
    moment = (m * x).sum(axis=1) + prop_m * prop.x + ballast_kg * ballast_x
    cg = moment / total_m

    # CP at low speed, which is the rail-exit condition.
    cp_nominal = aero.stability(rocket, cg.mean(), mach=0.07).cp_station
    cp = cp_nominal + rng.normal(0.0, SIGMA["cp_calibers"] * d, size=n)

    return (cp - cg) / d, total_m, cg


def report(sm: np.ndarray, label: str) -> None:
    p = np.percentile(sm, [1, 5, 50, 95, 99])
    print(f"  {label}")
    print(f"    median                    {p[2]:6.2f} cal")
    print(f"    5th - 95th percentile     {p[1]:6.2f} - {p[3]:.2f} cal")
    print(f"    1st percentile            {p[0]:6.2f} cal")
    print(f"    P(SM < {SM_FLOOR:.1f} safety floor)  {100 * (sm < SM_FLOOR).mean():6.1f} %")
    print(f"    P(SM < {SM_TARGET:.1f} R1 target)    {100 * (sm < SM_TARGET).mean():6.1f} %")
    print(f"    P(SM < 1.0 unsafe)        {100 * (sm < 1.0).mean():6.1f} %")
    print(f"    P(SM > {SM_CEILING:.1f} over-stable)  {100 * (sm > SM_CEILING).mean():6.1f} %")


def tornado(n: int) -> None:
    """One-at-a-time sensitivity: which uncertainty actually drives the margin?"""
    rocket = build_vehicle(BASELINE)
    masses = build_mass(rocket, BASELINE.motor)
    d = rocket.diameter
    items = list(masses.items)
    nominal_cg = masses.wet_cg
    cp = aero.stability(rocket, nominal_cg, mach=0.07).cp_station
    nominal_sm = (cp - nominal_cg) / d
    total = sum(it.mass for it in items)

    effects = []
    for it in items:
        if it.mass < 0.02:
            continue
        sigma = SIGMA["mass_budgeted"] if is_budgeted(it.name) else SIGMA["mass_structural"]
        dm = it.mass * sigma
        new_cg = (nominal_cg * total + dm * it.x) / (total + dm)
        effects.append((it.name, ((cp - new_cg) / d) - nominal_sm))

    effects.append(("CP prediction error", SIGMA["cp_calibers"]))
    effects.sort(key=lambda e: -abs(e[1]))

    print(f"  nominal rail-exit static margin {nominal_sm:.2f} cal")
    print(f"  effect on SM of a +1 sigma error in each input:\n")
    print(f"    {'input':32s} {'delta SM':>9s}  direction")
    for name, delta in effects[:12]:
        arrow = "more stable" if delta > 0 else "LESS stable"
        bar = "#" * min(int(abs(delta) * 120), 40)
        print(f"    {name:32s} {delta:+9.3f}  {arrow:11s} {bar}")


def ballast_study(n: int) -> None:
    """How much nose ballast buys back a given confidence level?"""
    rocket = build_vehicle(BASELINE)
    ballast_x = 0.6 * rocket.nose.length  # inside the nose cone shoulder
    print(f"  ballast station {ballast_x * 1000:.0f} mm from the nose tip\n")
    print(f"    {'ballast':>8s} {'median SM':>10s} {'5th pct':>8s} "
          f"{'P(<1.4)':>8s} {'authority':>10s}")
    base_median = None
    for grams in (0, 50, 100, 150, 200, 300, 400):
        sm, _, _ = sample(n, seed=1, ballast_kg=grams / 1000.0, ballast_x=ballast_x)
        median = float(np.median(sm))
        if base_median is None:
            base_median = median
        # Authority scales as 1/SM at fixed Cm_delta.
        authority = base_median / median * 100.0
        print(f"    {grams:6d} g {median:10.2f} {np.percentile(sm, 5):8.2f} "
              f"{100 * (sm < SM_FLOOR).mean():7.1f}% {authority:9.0f}%")


def frontier(n: int) -> None:
    """Risk vs authority across aft fin size. Does growing the fins actually help?"""
    from dataclasses import replace

    print(f"    {'aft span':>9s} {'nom SM':>7s} {'P(<1.4)':>8s} {'P(<1.0)':>8s} "
          f"{'Cm_delta':>9s} {'authority':>10s} {'roll lost':>10s}")
    base_authority = None
    for aft in (1.05, 1.15, 1.25, 1.40, 1.55):
        params = replace(BASELINE, aft_semispan_cal=aft)
        rocket = build_vehicle(params)
        masses = build_mass(rocket, params.motor)
        d = rocket.diameter
        cg = masses.wet_cg
        stab = aero.stability(rocket, cg, mach=0.07)
        sm_nom = stab.static_margin_cal

        sm_samples, _, _ = sample(n, seed=2, params=params)

        panel = aero.panel_cn_alpha(rocket.canards, d, 0.07)
        cm_delta = 2.0 * panel * (cg - rocket.canards.cp_station) / d
        authority = cm_delta / sm_nom
        if base_authority is None:
            base_authority = authority

        aft_panel = aero.panel_cn_alpha(rocket.aft_fins, d, 0.07)
        cl_can = rocket.canards.count * panel * (rocket.canards.spanwise_cp_radius / d)
        cl_aft = 0.037 * rocket.aft_fins.count * aft_panel * (
            rocket.aft_fins.spanwise_cp_radius / d
        )  # interdigitated interference strength
        roll_lost = cl_aft / cl_can * 100.0

        print(f"    {aft:9.2f} {sm_nom:7.2f} {100 * (sm_samples < 1.4).mean():7.1f}% "
              f"{100 * (sm_samples < 1.0).mean():7.1f}% {cm_delta:9.2f} "
              f"{authority / base_authority * 100:9.0f}% {roll_lost:9.1f}%")


def optimise(n: int, risk_budget: float = 0.01) -> None:
    """Best steering authority subject to a hard cap on the probability of an unsafe margin.

    Canards and aft fins pull in opposite directions, so sizing them one at a time is
    guesswork. Canard area buys Cm_delta but costs static margin; aft fin area buys margin
    but costs authority twice over (directly, and by moving the CG aft). The question is
    which *combination* maximises authority at an acceptable risk, so search both.
    """
    from dataclasses import replace

    from design import control, flutter
    from design.configure import evaluate
    from design.packaging import SERVOS, torque_margin

    servo = SERVOS["mini_ht"]

    print(f"  constraints: P(SM < 1.0 cal) <= {risk_budget:.0%}, flutter margin >= 1.5,")
    print("               servo torque margin >= 2.0, plus every limit in configure.LIMITS\n")
    print(f"    {'canard':>7s} {'aft':>5s} {'SM':>6s} {'P(<1.0)':>8s} {'lat g':>6s} "
          f"{'xrange':>7s} {'flut':>5s} {'torq':>5s}  {'verdict'}")

    best = None
    for canard in (0.70, 0.85, 1.00, 1.15, 1.30):
        for aft in (1.25, 1.40, 1.55, 1.70, 1.85):
            params = replace(BASELINE, canard_semispan_cal=canard, aft_semispan_cal=aft)
            ev = evaluate(params, deflection_deg=8.0)
            sm, _, _ = sample(n, seed=3, params=params)
            risk = float((sm < 1.0).mean())
            nom = float(np.median(sm))
            r = ev.rocket

            fast = max(ev.flight.points, key=lambda p: p.speed)
            flut = min(
                flutter.evaluate(r.aft_fins, fast.speed, fast.z).margin,
                flutter.evaluate(r.canards, fast.speed, fast.z).margin,
            )
            hinges = [
                control.pitch_authority(r, p, p.mass, 10.0).hinge_moment_per_panel
                for p in ev.flight.points if p.q > 100
            ]
            torq = torque_margin(max(hinges, default=0.0), servo)

            fails = list(ev.violations)
            if risk > risk_budget:
                fails.append(f"risk {risk:.1%}")
            if flut < 1.5:
                fails.append(f"flutter {flut:.2f}")
            if torq < 2.0:
                fails.append(f"torque {torq:.1f}x")

            ok = not fails
            if ok and (best is None or ev.crossrange > best[1].crossrange):
                best = (params, ev, risk, nom)
            print(f"    {canard:7.2f} {aft:5.2f} {nom:6.2f} {100 * risk:7.1f}% "
                  f"{ev.pitch.lateral_accel_g if ev.pitch else 0:6.2f} {ev.crossrange:6.0f}m "
                  f"{flut:5.2f} {torq:4.1f}x  {'ok' if ok else '; '.join(fails)[:38]}")

    if best is None:
        print("\n  nothing in the grid meets every constraint.")
        return
    params, ev, risk, nom = best
    print(f"\n  BEST: canard {params.canard_semispan_cal:.2f} cal, "
          f"aft {params.aft_semispan_cal:.2f} cal -- {ev.crossrange:.0f} m crossrange, "
          f"{ev.pitch.lateral_accel_g:.2f} g, median SM {nom:.2f}, P(unsafe) {risk:.1%}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=20000)
    args = ap.parse_args()
    n = args.samples

    print("=" * 88)
    print(f"STATIC MARGIN ROBUSTNESS  ({n} samples, rail exit, motor loaded)")
    print("=" * 88)
    print("1-sigma assumptions: structural mass "
          f"{SIGMA['mass_structural']:.0%}, budgeted mass {SIGMA['mass_budgeted']:.0%}, "
          f"component position {SIGMA['position'] * 1000:.0f} mm,\n"
          f"CP {SIGMA['cp_calibers']:.2f} cal, motor mass {SIGMA['motor_mass']:.0%}.\n")

    sm, total_m, cg = sample(n, seed=1)
    report(sm, "as designed, no ballast")
    print(f"\n    wet mass  {np.median(total_m):.2f} kg "
          f"(5-95%: {np.percentile(total_m, 5):.2f} - {np.percentile(total_m, 95):.2f})")

    print("\n" + "=" * 88)
    print("SENSITIVITY: WHAT ACTUALLY MOVES THE MARGIN")
    print("=" * 88)
    tornado(n)

    print("\n" + "=" * 88)
    print("REDESIGN OPTION: GROW THE AFT FINS?")
    print("=" * 88)
    frontier(n)

    print("\n" + "=" * 88)
    print("SIZING CANARDS AND AFT FINS TOGETHER")
    print("=" * 88)
    optimise(n)

    print("\n" + "=" * 88)
    print("NOSE BALLAST TRADE")
    print("=" * 88)
    ballast_study(n)

    print("""
Reading the ballast table: ballast buys margin and spends control authority, roughly
proportionally, because a_lat ~ 1/SM. The right answer is not to pick a number now. It is
to *design in the provision* -- a threaded rod and washer stack in the nose shoulder --
and set it after weighing the built vehicle. That converts static margin from a prediction
you are betting on into a parameter you measure and tune, which is the single cheapest
risk reduction available on this airframe.

Note also which way the sensitivity points: the dominant uncertainty is not any mass line,
it is the CP prediction itself. No amount of ballast fixes that. What fixes it is the
OpenRocket cross-check (an independent Barrowman implementation), and ultimately the
GV-1 flight.""")


if __name__ == "__main__":
    main()
