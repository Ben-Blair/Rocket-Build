"""What would it take to turn like a Sidewinder? Search the design space and find out.

Run:  python scripts/agility_sweep.py [--samples 4000] [--quick]

docs/11-agility-comparison.md argues qualitatively that 1.4 g is not 10 g. This script
answers the quantitative follow-up: holding every requirement in docs/00-requirements.md,
what is the most agile vehicle this project can actually build, and WHICH REQUIREMENT
STOPS IT? The relaxation ladder at the end is the real output -- a number you cannot reach
is much less useful than the name of the constraint that is in the way.

THE OBSERVABLE IS HEADING RATE, NOT LATERAL g, and getting that wrong is the single
easiest mistake to make here. An AIM-9B pulls ~10 g and turns at ~10 deg/s because it is
doing it at Mach 1.7. Turn rate is

    omega = n * g0 / V

so a "we need 3 g" target read off today's 166 m/s is only a 3 g target if you get there
WITHOUT adding speed. Reach it with a bigger motor instead and the requirement moves with
you: at 242 m/s, 10 deg/s costs 4.3 g, not 3.0. Turn RADIUS is worse still -- V^2/(n g0)
with n going as V^2 is completely insensitive to speed. Speed buys g. It does not buy
turning. Only CN at fixed speed does: less static margin, more canard area, more throw.

So every table below reports deg/s and metres of radius alongside the g, and the search
maximises heading rate. See `design.control.heading_change`.

WHAT IS SEARCHED
    motor                 every 54 mm motor in data/motors (75 mm motors do not fit the
                          mount that docs/09 designed, so they are not options)
    canard_semispan_cal   authority up, static margin down
    aft_semispan_cal      static margin up, authority down, canard wake interference up
    nose_ballast_kg       static margin up, authority down, and R1's tuning knob
    fin_thickness         not an agility knob -- a flutter FIX, sized to whatever speed
                          the motor produces, and rounded to G10 stock

A "*" after a motor name means its case is longer than the 332.08 mm mount tube docs/09
built. The airframe grows to fit parametrically; the hardware does not.

WHAT THIS SEARCH STILL DOES NOT CHECK -- read this before quoting its numbers.

The 1.30/1.70 point below was adopted as the frozen baseline in Sep 2026, and applying it
tripped two checks this script does not run. Both cost authority, and together they are
worth about 6%: the search says 6.91 deg/s and the built vehicle makes 6.47.

  the canard ROOT JOINT   A 1.30 cal panel puts 28.8 N through the tang instead of 21.1,
                          and its CP moves outboard, so bending at the wall DOUBLES
                          (0.610 -> 1.273 N.m). The 0.6 mm skin over the tang slot fell to
                          1.47x against a 2.0x requirement. Fixed by a 3.6 mm laminate
                          (0.8/2.0/0.8), which costs 1.93 -> 1.88 g. See design/hinge.py.
  the RECOVERY ANCHOR     Bigger fins -> more mass -> more descent weight -> more opening
                          shock -> the U-bolt goes M8 to M10 and the four anchors go
                          191 -> 302 g. That mass is itself descent mass, so it is
                          self-loading; it converges in one pass because rod size is
                          discrete. Costs another 1.88 -> 1.76 g, and takes the recovery
                          bay's packing margin from 4.4 mm to 2.2 mm.

Neither is hard to add and neither was foreseen, which is the point worth keeping: a
search is only as honest as its constraint set, and this one has now been wrong twice in
the same way -- first the +/-16 g accelerometer, then these. Anything this script reports
is an UPPER BOUND until the structural chain has been run on the winning point.

WHAT IS NOT SEARCHED, and why
    servo                 it is CHECKED, not searched, and the reason is that there is
                          nothing to search. Of the eight parts in packaging.SERVOS only
                          four fit four-abreast direct drive in a 79.4 mm tube, and the
                          strongest of those is 0.55 N.m against the KST X08 Plus's 0.52 --
                          6%. Buying a bigger servo is not an available move on this
                          airframe. Torque headroom has to come from the hinge line or a
                          reduction, and both are priced in the ladder's servo row.
    outer_diameter        75 mm is set by the 54 mm motor mount, and the whole vehicle is
                          built in Fusion around it
    n_canards             4+4 interdigitated is the roll-sign fix (docs/00 section 5)
    canard_root_cal /     root chord and taper are set together to hold panel area, and
      canard_taper        the area is what the search moves via semispan
    deflection_deg        DEFLECTION_LIMIT_DEG is a SENSING limit as much as a control
                          one -- see configure.py -- so it is reported at 8 deg and the
                          ladder prices lifting it rather than silently doing so
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import robustness  # noqa: E402  -- reuse its Monte Carlo, do not re-implement it
from design import control, flutter  # noqa: E402
from design.configure import DesignParams, LIMITS, baseline, evaluate  # noqa: E402
from design.motors import Motor, load_eng  # noqa: E402
from design.estimation import ACCEL_16G  # noqa: E402
from design.packaging import SERVOS, check_direct_drive, torque_margin  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# The comparison target. AIM-9B: about 10 g at Mach 1.7, which is a ~10 deg/s heading rate
# and a turn radius of roughly 3.2 km. The RATE is the honest thing to chase on a subsonic
# airframe; the radius is not, because radius is where a Mach 1.7 vehicle actually loses.
TARGET_RATE_DEG_S = 10.0
TARGET_RADIUS_M = 3200.0

# G10 sheet is sold in inch fractions. A flutter fix that specifies 3.7 mm is not a fix.
G10_STOCK_M = (0.0032, 0.0040, 0.0048, 0.0064)

MOTOR_BORE_MAX = 0.0545  # 54 mm mount, from docs/09

# `achievable_crossrange` haircuts its manoeuvre by 0.7 for the fact that a real
# controller does not sit at full deflection. THE CAPABILITY TABLES BELOW DO NOT, and the
# two must not be mixed in one row -- a duty-cycled turn rate quoted next to a raw trim g
# is the same class of error as correction 4 (a constant living in one script and quoted
# by another). Everything scored here is full-deflection capability, and the realistic
# heading total is that capability multiplied by this number, once, where it is labelled.
CONTROLLER_DUTY = 0.7

RISK_BUDGET = 0.01  # R1: P(SM < 1.0 cal) < 1%
R1_NOMINAL = (1.5, 2.5)  # R1: nominal rail-exit static margin band, calibers
FLUTTER_MIN = 1.5  # docs/00 section 8
TORQUE_MIN = 2.0  # docs/00, and torque_margin() already derates stall by 0.4

# THE CONSTRAINT THAT IS NOT IN configure.LIMITS, AND IT IS THE ONE THAT BITES.
#
# The accelerometer is a +/-16 g part (design/estimation.ACCEL_16G, docs/06), and docs/02
# has carried "peak axial acceleration <= 16 g" as motor-selection criterion 3 since the
# J449 was chosen. IT WAS WRITTEN DOWN AND NEVER ENCODED. `configure.LIMITS` caps T/W from
# BELOW and never from above, because nothing was ever going to breach it from above on a
# J -- so the criterion lived in prose, where it constrained nobody.
#
# It breaches immediately on a K. The first pass of this search returned the AeroTech
# K2050ST as the best legal motor swap -- 5.95 deg/s, every requirement in LIMITS met --
# and it peaks at 31.4 g axial, twice the accelerometer's full scale. A clipped
# accelerometer through the entire boost does not degrade the state estimate, it removes
# it: design/estimation.py stages the filter on exactly that signal. The most agile
# vehicle in the grid was one that cannot know where it is.
#
# So it is a hard constraint here, not a warning. The lesson generalises: a search is only
# as honest as its constraint set, and the constraint most likely to be missing is the one
# that never mattered for the frozen design.
AXIAL_G_MAX = ACCEL_16G.accel_full_scale_g

# The mount tube as BUILT is 332.08 mm (docs/09), sized around the J449's 321 mm case.
# A longer motor is not infeasible -- `build_vehicle` grows the booster parametrically --
# but it re-cuts the mount tube and moves the aft centering ring, so it is flagged rather
# than silently accepted. This is the difference between "order a different motor" and
# "rebuild the aft end".
BUILT_MOUNT_LENGTH = 0.33208


class Candidate:
    """One vehicle, scored against every requirement at once."""

    def __init__(self, params: DesignParams, deflection: float, samples: int):
        self.params = params
        self.deflection = deflection
        self.ev = ev = evaluate(params, deflection_deg=deflection)
        r, f = ev.rocket, ev.flight

        coast = [p for p in f.points if p.t >= f.burnout_time]
        self.peak_q_point = max(coast, key=lambda p: p.q) if coast else None
        # duty_cycle=1.0: what the vehicle CAN hold. The haircut is applied once, at the
        # point of use, so that g and deg/s in the same row describe the same instant.
        self.turn = control.heading_change(r, f, deflection, duty_cycle=1.0)

        fast = max(f.points, key=lambda p: p.speed)
        self.fast_speed = fast.speed
        self.flutter_aft = flutter.evaluate(r.aft_fins, fast.speed, fast.z).margin
        self.flutter_canard = flutter.evaluate(r.canards, fast.speed, fast.z).margin
        self.flutter = min(self.flutter_aft, self.flutter_canard)

        # THE WORST HINGE MOMENT IS AT THE FLIGHT'S MAX q, WHICH IS IN BOOST, NOT COAST.
        # `robustness.optimise` scans every point above 100 Pa for this; it does not have
        # to. Hinge moment is q * S * CNa * delta * (cp - hinge) * chord, and the only
        # flight-varying terms are q and the local alpha inside CNa -- alpha_trim moves by
        # under a degree across the whole flight, so q dominates completely. Checked
        # directly: the scan and this single point return the same number to 15 digits on
        # the baseline. Worth 400 fewer pitch_authority() calls per candidate in a search
        # this size.
        worst_q = max(f.points, key=lambda p: p.q)
        self.hinge = abs(control.pitch_authority(
            r, worst_q, worst_q.mass, deflection).hinge_moment_per_panel)
        self.servo = SERVOS[params.servo]
        self.torque = torque_margin(self.hinge, self.servo)
        self.servo_fits = check_direct_drive(
            r.tubes[0].inner_diameter, self.servo, params.n_canards).fits

        self.axial_g = f.max_acceleration_g
        self.motor_fits_built_mount = params.motor.length <= BUILT_MOUNT_LENGTH

        sm, _, _ = robustness.sample(samples, seed=3, params=params)
        self.risk = float((sm < 1.0).mean())
        self.sm_nominal = float(np.median(sm))

    # -- derived observables -------------------------------------------------------
    @property
    def lateral_g(self) -> float:
        return self.ev.pitch.lateral_accel_g if self.ev.pitch else 0.0

    @property
    def peak_rate(self) -> float:
        return self.turn.peak_rate_deg_s

    @property
    def radius(self) -> float:
        return self.turn.min_radius_m

    @property
    def speed(self) -> float:
        return self.peak_q_point.speed if self.peak_q_point else 0.0

    @property
    def heading_realistic(self) -> float:
        """Heading change a controller at CONTROLLER_DUTY would actually get."""
        return self.turn.heading_deg * CONTROLLER_DUTY

    def fails(self, ignore: frozenset[str] = frozenset()) -> list[str]:
        """Every requirement this vehicle misses. `ignore` drives the relaxation ladder.

        Names are the requirement IDs from docs/00-requirements.md wherever one exists,
        so that relaxing "R6" here and relaxing R6 in the document mean the same thing.
        """
        out: list[str] = []
        for v in self.ev.violations:
            tag = ("R5" if "Mach" in v else
                   "R6" if "apogee" in v else
                   "R1" if "SM" in v else
                   "stall" if "stall" in v else
                   "R11" if "recovery bay" in v or "harness" in v else "limits")
            if tag not in ignore:
                out.append(f"{tag}: {v}")
        if "R1" not in ignore:
            if self.risk > RISK_BUDGET:
                out.append(f"R1: P(SM<1.0) {self.risk:.1%}")
            if not (R1_NOMINAL[0] <= self.sm_nominal <= R1_NOMINAL[1]):
                out.append(f"R1: nominal SM {self.sm_nominal:.2f} cal")
        if "imu" not in ignore and self.axial_g > AXIAL_G_MAX:
            out.append(f"imu: {self.axial_g:.0f} g axial clips the "
                       f"{AXIAL_G_MAX:.0f} g accelerometer")
        if "flutter" not in ignore and self.flutter < FLUTTER_MIN:
            out.append(f"flutter: {self.flutter:.2f}x")
        if "servo" not in ignore:
            if not self.servo_fits:
                out.append(f"servo: {self.params.servo} does not fit direct drive")
            if self.torque < TORQUE_MIN:
                out.append(f"servo: torque {self.torque:.1f}x")
        return out

    def line(self, ignore: frozenset[str] = frozenset()) -> str:
        p = self.params
        fails = self.fails(ignore)
        return (f"{p.motor.name[:16]:16s} {p.canard_semispan_cal:5.2f} "
                f"{p.aft_semispan_cal:4.2f} {p.nose_ballast_kg * 1000:4.0f}g "
                f"{p.fin_thickness * 1000:4.1f} {self.sm_nominal:5.2f} "
                f"{self.ev.flight.apogee:5.0f} {self.ev.flight.max_mach:4.2f} "
                f"{self.speed:4.0f} {self.lateral_g:5.2f} {self.peak_rate:6.2f} "
                f"{self.radius / 1000:5.2f} {self.heading_realistic:5.1f} "
                f"{self.flutter:4.2f} {self.torque:4.1f}  "
                f"{'ok' if not fails else '; '.join(fails)[:42]}")


# g and deg/s are full-deflection capability at peak coast q; psi is the heading a
# CONTROLLER_DUTY controller accumulates over the whole window. R is the tightest radius.
HEADER = (f"{'motor':17s} {'can':>5s} {'aft':>4s} {'blst':>5s} {'t':>4s} {'SM':>5s} "
          f"{'apo':>5s} {'M':>4s} {'V':>4s} {'g':>5s} {'deg/s':>6s} {'R km':>5s} "
          f"{'psi':>5s} {'flt':>4s} {'trq':>4s}  verdict")


def motor_pool() -> list[Motor]:
    motors = []
    for path in sorted((ROOT / "data" / "motors").glob("*.eng")):
        try:
            m = load_eng(path)
        except Exception:
            continue
        if m.diameter <= MOTOR_BORE_MAX:
            motors.append(m)
    return motors


def with_flutter_fix(params: DesignParams, samples: int, deflection: float) -> Candidate:
    """Score `params`, stepping the aft fin up G10 stock sizes until flutter is legal.

    Fin thickness is not an agility knob and must not be searched as one: it is the price
    of whatever speed the motor produced. Sizing it here rather than gridding it keeps the
    search honest AND keeps it cheap -- one extra evaluate() at most, instead of a whole
    extra dimension. The aft fins are the flutter-critical set at every speed tried
    (the canards are short-chord, so t/c is high and V_f goes as (t/c)^1.5).
    """
    cand = Candidate(params, deflection, samples)
    for t in G10_STOCK_M:
        if t <= params.fin_thickness:
            continue
        if cand.flutter >= FLUTTER_MIN:
            break
        cand = Candidate(replace(params, fin_thickness=t), deflection, samples)
    return cand


def stage_baseline(samples: int, deflection: float) -> Candidate:
    print("=" * 118)
    print("WHERE THE FROZEN BASELINE ACTUALLY SITS")
    print("=" * 118)
    cand = Candidate(baseline(), deflection, samples)
    print(HEADER)
    print(cand.line())
    t = cand.turn
    print(f"\n  At {cand.speed:.0f} m/s, {TARGET_RATE_DEG_S:.0f} deg/s would need "
          f"{TARGET_RATE_DEG_S * math.pi / 180 * cand.speed / 9.80665:.2f} g. "
          f"This vehicle makes {cand.lateral_g:.2f} g.")
    print(f"  Over the whole {t.seconds:.1f} s control window at {deflection:.0f} deg and "
          f"{CONTROLLER_DUTY:.0%} duty it turns {cand.heading_realistic:.1f} deg -- "
          f"{cand.heading_realistic / 90:.2f} of a quarter turn.")
    print(f"  Hinge moment {cand.hinge:.4f} N.m against {cand.servo.name}: "
          f"{cand.torque:.1f}x. Flutter {cand.flutter:.2f}x (aft fins). "
          f"Peak axial {cand.axial_g:.1f} g against a {AXIAL_G_MAX:.0f} g accelerometer.")
    return cand


def stage_ceiling(cand: Candidate) -> None:
    """The stall ceiling in closed form -- and it is NOT a single number.

    The tempting claim is "the canards stall at 12 deg local alpha, so this airframe caps
    out around 3.6 g and 10 g is impossible". The first half is a real limit. The second
    half is circular, and it is worth showing why, because it is the kind of error that
    survives being quoted.

    At trim, body alpha is proportional to deflection:

        alpha_trim = k * delta,    k = Cm_delta / -Cm_alpha

    and the canard's local incidence is alpha_trim + delta = (1 + k) * delta. So the stall
    limit is a budget SHARED between body lean and canard throw, and how much lift you get
    for it depends entirely on where you spend it:

        CN = CNa_vehicle * alpha_trim + CNa_canards * delta

    CNa_vehicle is an order of magnitude larger than the canard-only term, because it
    includes the aft fins and the body. So the same 12 deg is worth far more spent as body
    alpha than as canard deflection -- and k is set by static margin. A "stall ceiling"
    quoted without its static margin is really just a statement about the margin that was
    assumed.

    The table below is the same 12 deg spent at different margins. Today's k = 0.125 caps
    the vehicle near 1.9 g; the ceiling only reaches the 3.6 g figure at k = 0.5, which is
    already an airframe with about a third of today's margin. What actually stops this
    vehicle at today's speed is static margin and the servo, not the canards quitting.

    THE LAST ROW IS NOT A DESIGN. At neutral stability trim alpha is indeterminate and the
    linear aero this whole repo runs on has stopped being true well before 12 deg of BODY
    alpha -- Barrowman is a small-angle theory, and the aft fins see that alpha too. It is
    printed as the asymptote of the formula, to show where the formula's own limit lies.
    """
    ev = cand.ev
    r = ev.rocket
    pt = cand.peak_q_point
    if pt is None or ev.pitch is None:
        return
    from design import aero, atmosphere

    stab = aero.stability(r, pt.cg, pt.mach)
    cna_vehicle = stab.cn_alpha
    cna_canards = 2.0 * aero.panel_cn_alpha(r.canards, r.diameter, pt.mach)
    k_today = ev.pitch.cm_delta / -ev.pitch.cm_alpha
    limit = math.radians(control.STALL_LIMIT_DEG)
    q, S, m = pt.q, r.reference_area, pt.mass

    print("\n" + "=" * 118)
    print("THE STALL CEILING, AT TODAY'S SPEED, AS A FUNCTION OF STATIC MARGIN")
    print("=" * 118)
    print(f"  {control.STALL_LIMIT_DEG:.0f} deg of local canard alpha, split between body "
          f"lean and canard throw, at q = {q / 1000:.1f} kPa and {pt.speed:.0f} m/s.")
    print(f"  CNa vehicle {cna_vehicle:.1f} /rad against CNa canards {cna_canards:.1f} /rad "
          f"-- which is why WHERE you spend the 12 deg matters.")
    print("  ~SM is today's margin scaled as 1/k, NOT a rebuilt vehicle: it says which "
          "margin each row implies,")
    print("  not that a vehicle with that margin has these exact derivatives. Stage 2 "
          "builds real ones.\n")
    print(f"  {'k=a/d':>7s} {'~SM cal':>8s} {'delta':>7s} {'alpha':>7s} {'CN':>6s} "
          f"{'g':>6s} {'deg/s':>7s}  note")
    for k in (k_today, 0.25, 0.5, 1.0, 2.0, 4.0):
        d = limit / (1.0 + k)
        a = k * d
        cn = cna_vehicle * a + cna_canards * d
        n = q * S * cn / (m * atmosphere.G0)
        rate = math.degrees(n * atmosphere.G0 / pt.speed)
        sm = ev.pitch.static_margin_cal * k_today / k
        note = ("today's airframe at its own stall limit" if k == k_today else "")
        print(f"  {k:7.3f} {sm:8.2f} {math.degrees(d):6.1f}d {math.degrees(a):6.1f}d "
              f"{cn:6.2f} {n:6.2f} {rate:7.2f}  {note}")
    n_inf = q * S * cna_vehicle * limit / (m * atmosphere.G0)
    print(f"  {'inf':>7s} {0.0:8.2f} {0.0:6.1f}d {control.STALL_LIMIT_DEG:6.1f}d "
          f"{cna_vehicle * limit:6.2f} {n_inf:6.2f} "
          f"{math.degrees(n_inf * atmosphere.G0 / pt.speed):7.2f}  ASYMPTOTE, not a vehicle "
          f"-- see docstring")
    print(f"\n  Today the vehicle flies {ev.pitch.canard_local_alpha_deg:.1f} deg local at "
          f"{cand.deflection:.0f} deg of throw, so there IS room to "
          f"{control.STALL_LIMIT_DEG / (1.0 + k_today):.1f} deg of deflection before stall "
          f"-- worth {q * S * (cna_vehicle * k_today + cna_canards) * limit / (1 + k_today) / (m * atmosphere.G0):.2f} g.")
    print("  That extra throw is held back by DEFLECTION_LIMIT_DEG, which is a sensing "
          "limit, not an aerodynamic one.")


def stage_motors(samples: int, deflection: float) -> list[Candidate]:
    """Motor first, because it moves q and q is the biggest single term."""
    print("\n" + "=" * 118)
    print("STAGE 1  --  MOTOR ONLY, frozen geometry")
    print("=" * 118)
    print("Every 54 mm motor in the catalogue on today's airframe. Sorted by turn rate.\n")
    cands = []
    for m in motor_pool():
        try:
            cands.append(with_flutter_fix(baseline(motor=m), samples, deflection))
        except Exception:
            continue
    cands.sort(key=lambda c: -c.peak_rate)
    print(HEADER)
    for c in cands[:18]:
        print(c.line())
    feasible = [c for c in cands if not c.fails()]
    if feasible:
        best = max(feasible, key=lambda c: c.peak_rate)
        print(f"\n  Best legal motor swap on the frozen geometry: {best.params.motor.name} "
              f"-- {best.peak_rate:.2f} deg/s, {best.lateral_g:.2f} g, "
              f"{best.radius / 1000:.2f} km radius.")
        print(f"  That is {best.peak_rate / TARGET_RATE_DEG_S:.0%} of the 9B heading rate, "
              f"for the price of a motor.")
    else:
        print("\n  No motor swap alone is legal.")
    return cands


def grid(quick: bool) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    if quick:
        return (0.85, 1.15, 1.45), (1.25, 1.55), (0.025, 0.100)
    return ((0.85, 1.00, 1.15, 1.30, 1.45),
            (1.15, 1.25, 1.40, 1.55, 1.70),
            (0.025, 0.060, 0.100))


COARSE = ((0.85, 1.15, 1.45), (1.25, 1.55), (0.025, 0.100))


def stage_search(motors: list[Candidate], samples: int, deflection: float,
                 quick: bool) -> list[Candidate]:
    """Joint search. Sizing these one at a time is what robustness.optimise() exists to
    stop you doing, and adding the motor to it makes the coupling worse, not better:
    a bigger motor raises q (authority up) and raises max Mach and apogee (R5 and R6
    down), while a bigger canard lowers static margin (authority up) and adds drag
    (apogee down, which BUYS BACK R6 headroom). None of that separates."""
    print("\n" + "=" * 118)
    print("STAGE 2  --  MOTOR x CANARD x AFT FIN x BALLAST, every requirement enforced")
    print("=" * 118)
    # TWO PASSES, because the full grid on every motor is ~6700 vehicles and the search
    # does not need that resolution to answer the question. Pass A is coarse and wide --
    # it has to be wide, because the relaxation ladder below asks what happens when R5 and
    # R6 come off, and those rows are answered by motors that are illegal today. Pass B
    # refines only around the two motors worth refining.
    pool = [c.params.motor for c in motors
            if c.ev.flight.apogee <= 2.0 * LIMITS["apogee_max_m"]
            and c.ev.flight.thrust_to_weight >= LIMITS["twr_min"]]

    results: list[Candidate] = []

    def run(motor_list, canards, afts, ballasts) -> None:
        for m in motor_list:
            for can in canards:
                for aft in afts:
                    for blst in ballasts:
                        p = baseline(motor=m, canard_semispan_cal=can,
                                     aft_semispan_cal=aft, nose_ballast_kg=blst)
                        try:
                            results.append(with_flutter_fix(p, samples, deflection))
                        except Exception:
                            continue

    c_can, c_aft, c_blst = COARSE
    print(f"  pass A (coarse): {len(pool)} motors x "
          f"{len(c_can) * len(c_aft) * len(c_blst)} geometries")
    run(pool, c_can, c_aft, c_blst)

    if not quick:
        fine_can, fine_aft, fine_blst = grid(quick=False)
        legal = [c for c in results if not c.fails()]
        refine = []
        if legal:
            refine.append(max(legal, key=lambda c: c.peak_rate).params.motor)
        top = max(results, key=lambda c: c.peak_rate).params.motor
        if top not in refine:
            refine.append(top)
        print(f"  pass B (fine): {len(refine)} motors "
              f"({', '.join(m.name for m in refine)}) x "
              f"{len(fine_can) * len(fine_aft) * len(fine_blst)} geometries")
        run(refine, fine_can, fine_aft, fine_blst)

    results.sort(key=lambda c: -c.peak_rate)

    feasible = [c for c in results if not c.fails()]
    print(f"  {len(feasible)} of {len(results)} meet every requirement.\n")
    print(HEADER)
    for c in feasible[:12]:
        print(c.line())
    if not feasible:
        print("  none -- the top of the infeasible list, with what each one misses:")
        for c in results[:12]:
            print(c.line())
    return results


def stage_ladder(results: list[Candidate], baseline_cand: Candidate) -> None:
    """One requirement at a time, off. THIS IS THE POINT OF THE SCRIPT.

    A ranked list of vehicles you cannot build tells you nothing. The price of each
    requirement, in degrees per second, tells you which conversation is worth having.
    """
    print("\n" + "=" * 118)
    print("STAGE 3  --  THE RELAXATION LADDER: what is each requirement costing?")
    print("=" * 118)
    print("Each row drops exactly ONE requirement and re-picks the best vehicle in the "
          "same grid.\n")
    print(f"  {'relaxed':34s} {'deg/s':>7s} {'g':>6s} {'R km':>6s} {'psi':>6s}  best vehicle")
    print(f"  {'':34s} {'(peak, full deflection)':>28s}  "
          f"psi is the {CONTROLLER_DUTY:.0%}-duty heading total\n")

    def best(ignore: frozenset[str]) -> Candidate | None:
        ok = [c for c in results if not c.fails(ignore)]
        return max(ok, key=lambda c: c.peak_rate) if ok else None

    rows: list[tuple[str, frozenset[str]]] = [
        ("nothing (all requirements)", frozenset()),
        ("R6 apogee <= 1600 m", frozenset({"R6"})),
        ("R5 Mach <= 0.8", frozenset({"R5"})),
        ("R1 static margin band", frozenset({"R1"})),
        ("servo torque >= 2.0x", frozenset({"servo"})),
        ("+/-16 g accelerometer", frozenset({"imu"})),
        ("flutter >= 1.5x", frozenset({"flutter"})),
        ("R11 recovery packing", frozenset({"R11"})),
        ("R5 + R6 (fly fast and high)", frozenset({"R5", "R6"})),
        ("R6 + servo", frozenset({"R6", "servo"})),
        ("R6 + IMU (a bigger, faster motor)", frozenset({"R6", "imu"})),
        ("everything except stall", frozenset({"R1", "R5", "R6", "R11", "servo",
                                               "flutter", "limits", "imu"})),
    ]
    # NOTE ON RESOLUTION: relaxed rows come largely out of the coarse pass -- a motor that
    # is illegal today never gets a fine grid. These are prices to an order of magnitude,
    # not designs.
    for label, ignore in rows:
        c = best(ignore)
        if c is None:
            print(f"  {label:34s} {'--':>7s} {'--':>6s} {'--':>6s} {'--':>6s}  nothing legal")
            continue
        p = c.params
        print(f"  {label:34s} {c.peak_rate:7.2f} {c.lateral_g:6.2f} "
              f"{c.radius / 1000:6.2f} {c.heading_realistic:6.1f}  "
              f"{p.motor.name[:14]:14s} can {p.canard_semispan_cal:.2f} "
              f"aft {p.aft_semispan_cal:.2f} blst {p.nose_ballast_kg * 1000:.0f}g")

    full = best(frozenset())
    if full is not None:
        print(f"\n  Read the first row against the last: the buildable vehicle turns at "
              f"{full.peak_rate:.1f} deg/s")
        unlimited = best(frozenset({"R1", "R5", "R6", "R11", "servo", "flutter",
                                    "limits", "imu"}))
        if unlimited is not None:
            print(f"  and the same airframe with every requirement switched off reaches "
                  f"{unlimited.peak_rate:.1f} deg/s.")
            print(f"  The gap is {unlimited.peak_rate - full.peak_rate:.1f} deg/s, and it "
                  f"is spread across several requirements rather than sitting behind one.")
        print(f"\n  Against the 9B's {TARGET_RATE_DEG_S:.0f} deg/s: "
              f"{full.peak_rate / TARGET_RATE_DEG_S:.0%} of the heading rate, "
              f"{TARGET_RADIUS_M / full.radius:.2f}x the turn radius"
              f"{' (tighter than a 9B)' if full.radius < TARGET_RADIUS_M else ''}.")
        print(f"  Baseline today is {baseline_cand.peak_rate:.2f} deg/s, so the search "
              f"finds {full.peak_rate / baseline_cand.peak_rate:.1f}x.")


def stage_margin_trade(results: list[Candidate], samples: int, deflection: float) -> None:
    """Turn rate against static margin, with the risk attached to every row.

    THIS IS THE DECISION, and it is the one the relaxation ladder points at: every other
    requirement costs nothing at the optimum, and R1 costs everything. So the question is
    not "can we relax the static margin band" in the abstract -- it is what each tenth of a
    caliber is worth in deg/s and what it costs in P(unsafe).

    The answer is unusually sharp. Margin buys turn rate steadily right down to about
    1.9 cal, which is where R1's 1% risk budget runs out, and past that the risk goes
    non-linear long before the turn rate does: the 10 deg/s vehicle sits near 0.7 cal, and
    at 0.7 cal roughly four flights in five have a static margin under one caliber. That is
    not a relaxed requirement, it is a different and much worse rocket.
    """
    legal = [c for c in results if not c.fails()]
    if not legal:
        return
    motor = max(legal, key=lambda c: c.peak_rate).params.motor

    print("\n" + "=" * 118)
    print(f"STAGE 4  --  WHAT IS A CALIBER OF STATIC MARGIN WORTH?  (motor held at "
          f"{motor.name})")
    print("=" * 118)
    print("  Canard span and nose ballast walked together to move margin, everything else "
          "frozen.\n")
    print(f"  {'canard':>7s} {'aft':>5s} {'blst':>6s} {'nom SM':>7s} {'P(SM<1)':>8s} "
          f"{'g':>6s} {'deg/s':>7s} {'R km':>6s}  verdict")
    for can, aft, blst in ((0.85, 1.55, 0.100), (1.00, 1.55, 0.100), (1.15, 1.55, 0.100),
                           (1.30, 1.70, 0.060), (1.30, 1.55, 0.025), (1.45, 1.40, 0.025),
                           (1.45, 1.25, 0.100), (1.45, 1.15, 0.025)):
        c = Candidate(baseline(motor=motor, canard_semispan_cal=can,
                               aft_semispan_cal=aft, nose_ballast_kg=blst),
                      deflection, samples)
        fails = c.fails()
        print(f"  {can:7.2f} {aft:5.2f} {blst * 1000:5.0f}g {c.sm_nominal:7.2f} "
              f"{c.risk:8.1%} {c.lateral_g:6.2f} {c.peak_rate:7.2f} {c.radius / 1000:6.2f}  "
              f"{'ok' if not fails else '; '.join(fails)[:44]}")
    print("\n  Read the P(SM<1) column, not the deg/s column. Turn rate is smooth in "
          "margin; risk is not.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=4000,
                    help="Monte Carlo samples for the R1 risk check on every candidate")
    ap.add_argument("--quick", action="store_true", help="coarse grid, for a fast look")
    ap.add_argument("--deflection", type=float, default=8.0,
                    help="canard deflection, deg (DEFLECTION_LIMIT_DEG is 8)")
    args = ap.parse_args()

    base = stage_baseline(args.samples, args.deflection)
    stage_ceiling(base)
    motors = stage_motors(args.samples, args.deflection)
    results = stage_search(motors, args.samples, args.deflection, args.quick)
    stage_ladder(results + motors, base)
    stage_margin_trade(results, args.samples, args.deflection)

    print("""
WHAT THIS DOES NOT MODEL, and every one of them makes the answer smaller
  * Turning costs energy. `heading_change` integrates a turn against a speed history from
    a trajectory that flew straight up. Induced drag at trim alpha and the gravity term
    once the velocity vector leaves the vertical both bleed speed, and a slower vehicle
    makes less g. Past ~45 deg of heading this is an upper bound, not a prediction.
  * The aero is linear and attached. Trim alpha stays small enough here that this is fair,
    which is the one part of the missile comparison that is NOT a problem for us.
  * Interference factors are estimates, and docs/00 says so. They set how much aft fin
    area is working, which sets static margin, which sets authority.
  * Nothing here closes a control loop. This is trim authority -- the g the vehicle can
    hold -- not what a real autopilot achieves with rate limits and a duty cycle.""")


if __name__ == "__main__":
    main()
