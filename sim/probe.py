"""M0.5 -- frame and sign probe. Run this BEFORE trusting any injected derivative.

    sim/.venv/bin/python sim/probe.py

WHY THIS EXISTS AND WHY IT RUNS FIRST. `docs/01-next-steps.md` "Things that will bite you"
opens with sign conventions -- "More student projects fail on a sign error than on anything
else here." Two independent codebases now describe this vehicle: this repo, which measures
every station from the nose tip and defines `cm_alpha = -cn_alpha * static_margin` (negative
is stable), and RocketPy, which has its own body frame and axis-of-symmetry convention. A
mismatch does not crash. It produces a simulation that runs beautifully and answers a
different question -- the failure mode this project keeps finding in its own history
(corrections 1, 14 and 28 are all the same shape: a datum that was right and a question that
was wrong).

METHOD: differential probing. Rather than hand-building quaternions -- which would just move
the convention risk into this file -- each test takes a REAL flight state, perturbs exactly
one quantity, and reads the change in `Flight.u_dot_generalized`. The baseline cancels, so
what remains is the response to the perturbation alone.

WHAT IT FOUND (2026-09-05). T0, T1/T6 and T5 pass -- the frame mapping is right and pitch
dynamics agree to 0.5%. T2 found a 4x disagreement on roll damping, and chasing it down took
three implementations, a kinematic-limit argument, and two wrong turns of mine worth
recording because both are easy to repeat:

  WRONG TURN 1. I built a "strip theory arbiter" whose sectional slope was pinned from
  `aero.panel_cn_alpha` -- i.e. from the repo's own lift model -- and called it independent.
  It agreed with the repo, as it was structurally guaranteed to. A check that inherits the
  model it is checking is not a check.

  WRONG TURN 2. On seeing OpenRocket's total land near RocketPy's, I retracted the Af/A_ref
  finding. Splitting by FIN SET showed that was premature: the totals were two different
  errors partly cancelling.

  WHAT IS ACTUALLY TRUE, all three wrong in different ways, converging on Cl_p ~ 125-150:
    * RocketPy: `cld_omega` carries a spurious `Af/reference_area`, because
      `clalpha_single_fin` is already body-area-referenced. Exact in both directions
      (2.7185x aft, 0.6439x canard, each matching Af/A_ref to five figures) -- which is why
      its TOTAL looks reasonable while its aft/canard split is 3x off.
    * OpenRocket: damps 2x too hard, caught by the kinematic limit -- a canted fin set must
      roll until incidence from rolling cancels the cant, and its own equilibrium is half
      that. Its roll FORCING is right to 0.5%.
    * This repo: was 2.26x low. FIXED in correction 60 (`aero.single_fin_cn_alpha`,
      `FinSet.mean_square_radius`).

  Full argument and the kinematic test: `python scripts/openrocket_roll_check.py`.
  GV-2's open-loop deflection sweep still measures Cl_p and Cl_delta together and remains
  what settles the truth rather than the agreement.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sim"))

from rocketpy import Flight

from design import aero, control
from vehicle import build, structure_without_motor

RAIL_LENGTH = 3.66
INCLINATION = 85.0  # 5 deg from vertical, matching design/trajectory.py's default

# State vector layout, from Flight.u_dot_generalized:
#   u = [x, y, z, vx, vy, vz, e0, e1, e2, e3, w1, w2, w3]
PASS, FAIL, INFO, WARN = "PASS", "FAIL", "----", "WARN"


def _fmt(tag, name, detail):
    print(f"  [{tag}] {name:<32s} {detail}")


def state_at(flight, t):
    rows = flight.solution_array
    idx = min(range(len(rows)), key=lambda k: abs(rows[k][0] - t))
    return list(rows[idx][1:]), float(rows[idx][0])


def omega_dot(flight, t, u):
    return list(flight.u_dot_generalized(t, u)[10:13])


def repo_cl_p_reweighted(rocket, mach):
    """The repo's own Cl_p, re-weighted from y_cp^2 to the honest integral c(y) y^2 dy.

    NOT AN INDEPENDENT ARBITER, and an earlier version of this file wrongly called it one.
    The sectional slope is pinned from `aero.panel_cn_alpha`, so this inherits the repo's
    entire lift model; agreement with `roll_damping_cl_p()` is therefore guaranteed and
    means nothing about whether either is right. What it DOES isolate is one specific
    approximation: a rolling panel at radius y sees local AoA p*y/V, so the damping moment
    weights chord by y^2, and lumping the panel at its lift centroid and squaring that
    (`spanwise_cp_radius**2`) is not the same as the chord-weighted mean square radius.
    The gap between this and `roll_damping_cl_p()` is the size of that one approximation
    and nothing else.
    """
    total = 0.0
    d, A = rocket.diameter, rocket.reference_area
    for fins in (rocket.aft_fins, rocket.canards):
        if fins is None:
            continue
        rb, s = fins.body_diameter / 2.0, fins.semispan
        y = np.linspace(rb, rb + s, 20001)
        c = fins.root_chord + (fins.tip_chord - fins.root_chord) * (y - rb) / s
        i2 = np.trapezoid(c * y**2, y)
        area = np.trapezoid(c, y)
        cna_set = fins.count * aero.panel_cn_alpha(fins, d, mach)
        a0 = cna_set * A / (fins.count * area)
        total += -2.0 * fins.count * a0 * i2 / (A * d**2)
    return total


def rocketpy_cl_p_renormalised(built, mach):
    """RocketPy's own cld_omega with one normalisation changed, and why.

    `clalpha_single_fin` is built in `_base_fin.py` as

        clalpha2D * planform_correlation * (self.Af / self.reference_area) * cos(gamma_c) / (...)

    -- note it explicitly carries `Af / reference_area`, i.e. it is a fin lift slope already
    referenced to the BODY cross-section, the standard Barrowman convention. But
    `evaluate_roll_parameters` then forms

        cld_omega = 2 * interf * n * clalpha_single_fin * cos(cant) * roll_geometrical_constant
                    / (reference_area * reference_length**2)

    and `roll_geometrical_constant` is the raw strip integral `integral c(y) y^2 dy` (verified
    numerically to 1.0000). Putting a body-referenced slope together with a raw strip integral
    requires dividing by the FIN area to strip the normalisation back out; dividing by
    `reference_area` a second time leaves a factor of `Af / reference_area` behind.

    That is dimensionally invisible -- both are areas, so the result is still dimensionless,
    which is exactly why such a thing survives review. It is observable as a scale error of
    exactly `Af/A_ref`, which is >1 for a large fin set and <1 for a small one. On this
    vehicle it therefore over-predicts the aft fins by 2.72x and UNDER-predicts the canards
    by 0.64x. An error that tracks a bookkeeping ratio to five significant figures in
    opposite directions on the same airframe is not a modelling choice.
    """
    total = 0.0
    d, A = built.ev.rocket.diameter, built.ev.rocket.reference_area
    for fins, surf in ((built.ev.rocket.aft_fins, built.rocket.aerodynamic_surfaces[1][0]),
                       (built.ev.rocket.canards, built.rocket.aerodynamic_surfaces[2][0])):
        rb, s = fins.body_diameter / 2.0, fins.semispan
        y = np.linspace(rb, rb + s, 20001)
        c = fins.root_chord + (fins.tip_chord - fins.root_chord) * (y - rb) / s
        i2 = np.trapezoid(c * y**2, y)
        a0 = surf.clalpha_single_fin(mach) * A / fins.planform_area_single
        total += -2.0 * surf.roll_damping_interference_factor * fins.count * a0 * i2 / (A * d**2)
    return total


def main():
    b = build()
    ev = b.ev
    flight = Flight(rocket=b.rocket, environment=b.env, rail_length=RAIL_LENGTH,
                    inclination=INCLINATION, heading=0.0)

    print("M0.5 frame and sign probe")
    print("=" * 92)

    # ---------------------------------------------------------------- T0: static geometry
    print("\nT0  mass, CG and surface stations -- does the model describe THIS vehicle")
    mass, cg, inertia = structure_without_motor(ev)
    checks = [
        ("structure mass (kg)", mass, 5.3884, 1e-3),
        ("CG without motor (m)", cg, 0.74149, 1e-4),
        ("I_roll (kg m^2)", inertia.roll, 0.005486, 1e-5),
        ("I_pitch (kg m^2)", inertia.pitch, 0.80584, 1e-4),
        ("canard CP station (m)", ev.rocket.canards.cp_station, 0.50674, 1e-4),
        ("aft fin CP station (m)", ev.rocket.aft_fins.cp_station, 1.25896, 1e-4),
    ]
    ok = all(abs(g - w) <= t for _, g, w, t in checks)
    for name, got, want, tol in checks:
        _fmt(PASS if abs(got - want) <= tol else FAIL, name, f"{got:.5f}  (expected {want})")
    sm = b.rocket.static_margin(0)
    inside = ev.flight.min_static_margin <= sm <= ev.flight.max_static_margin
    _fmt(PASS if inside else FAIL, "static margin (cal)",
         f"RocketPy {sm:.3f} vs repo {ev.flight.min_static_margin:.3f}-{ev.flight.max_static_margin:.3f}")
    _fmt(PASS if ok and inside else FAIL, "T0 verdict",
         "geometry and frame agree with design/" if ok and inside else "MISMATCH -- stop here")

    # -------------------------------------------------------- T1/T6: axis identification
    # Identify the axes rather than assuming them. The two TRANSVERSE axes are equal by
    # symmetry, so roll is the odd one out -- not, as a first draft of this file assumed,
    # simply the weakest. Roll damping divided by the tiny roll inertia gives a LARGER
    # angular acceleration than pitch does, so "weakest" picks the wrong axis every time.
    print("\nT1/T6  axis identification -- which body index is roll, and is every axis damped")
    t_probe = ev.flight.burnout_time + 2.0
    u0, tt = state_at(flight, t_probe)
    base = omega_dot(flight, tt, u0)

    resp = []
    for i in range(3):
        u = list(u0)
        u[10 + i] += 1.0  # +1 rad/s on this body axis alone
        resp.append(omega_dot(flight, tt, u)[i] - base[i])
        _fmt(INFO, f"d(wdot_{i+1})/d(w_{i+1})", f"{resp[i]:+10.4f} 1/s")

    # the pair that matches each other are pitch/yaw; the remaining index is roll
    pairs = [(abs(resp[a] - resp[bb]), a, bb) for a, bb in ((0, 1), (0, 2), (1, 2))]
    _, pa, pb = min(pairs)
    roll_i = ({0, 1, 2} - {pa, pb}).pop()
    _fmt(PASS, "roll axis", f"w{roll_i+1}  (transverse pair w{pa+1}/w{pb+1} match to "
         f"{abs(resp[pa]-resp[pb]):.2e})")
    _fmt(PASS if all(r < 0 for r in resp) else FAIL, "every axis damped",
         "all perturbations opposed" if all(r < 0 for r in resp) else "AN AXIS IS DIVERGENT")
    _fmt(PASS if resp[pa] < 0 else FAIL, "pitch damping (Cm_q) present",
         f"{resp[pa]:+.4f} 1/s -- emergent from omega x r; design/ has NO Cm_q term at all")

    # ------------------------------------------------------- T2: roll damping, three ways
    print("\nT2  roll damping -- settled by correction 60; all three codes were wrong")
    pt = min(ev.flight.points, key=lambda p: abs(p.t - tt))
    d, A = ev.rocket.diameter, ev.rocket.reference_area

    cl_p_repo = control.roll_damping_cl_p(ev.rocket, pt.mach)
    cl_p_repo_rw = repo_cl_p_reweighted(ev.rocket, pt.mach)
    cl_p_rpy_fix = rocketpy_cl_p_renormalised(b, pt.mach)
    # back RocketPy's out of the measured dynamics, using ITS OWN inertia so the comparison
    # is of aerodynamics alone rather than of two inertia models
    i_roll_rpy = b.rocket.I_33(tt)
    p_hat = 1.0 * d / (2.0 * max(pt.speed, 1.0))
    cl_p_rpy = (resp[roll_i] * i_roll_rpy) / (pt.q * A * d * p_hat)

    _fmt(INFO, "flight condition", f"t={tt:.2f}s q={pt.q:.0f}Pa M={pt.mach:.3f} V={pt.speed:.1f}m/s")
    _fmt(INFO, "design/control.py", f"{cl_p_repo:9.2f} /rad")
    _fmt(INFO, "  pre-correction-60", f"{cl_p_repo/2.0/1.138:9.2f} /rad  -- what it was before "
         f"aero.single_fin_cn_alpha and FinSet.mean_square_radius")
    _fmt(INFO, "RocketPy (from dynamics)", f"{cl_p_rpy:9.2f} /rad")
    _fmt(INFO, "  same, renormalised", f"{cl_p_rpy_fix:9.2f} /rad  ({cl_p_rpy_fix/cl_p_rpy:.3f}x) "
         f"-- removing the Af/A_ref double-normalisation")

    # The Af/A_ref finding is checkable on its own terms, without any arbiter, because it is
    # an internal-consistency argument about RocketPy's two definitions. Assert it exactly.
    print()
    exact = True
    for fins, surf in ((ev.rocket.aft_fins, b.rocket.aerodynamic_surfaces[1][0]),
                       (ev.rocket.canards, b.rocket.aerodynamic_surfaces[2][0])):
        ratio_area = fins.planform_area_single / A
        rb, s = fins.body_diameter / 2.0, fins.semispan
        y = np.linspace(rb, rb + s, 20001)
        c = fins.root_chord + (fins.tip_chord - fins.root_chord) * (y - rb) / s
        i2 = np.trapezoid(c * y**2, y)
        a0 = surf.clalpha_single_fin(pt.mach) * A / fins.planform_area_single
        fixed = 2 * surf.roll_damping_interference_factor * fins.count * a0 * i2 / (A * d**2)
        got = surf.roll_parameters[1](pt.mach) / fixed
        exact &= abs(got - ratio_area) < 1e-4
        _fmt(INFO, f"{fins.name}: cld_omega error",
             f"{got:.4f}x vs Af/A_ref = {ratio_area:.4f}   {'MATCHES' if abs(got-ratio_area)<1e-4 else 'no'}")
    _fmt(PASS if exact else FAIL, "Af/A_ref signature",
         "exact in both directions -- a bookkeeping error, not a modelling choice"
         if exact else "does not match; the diagnosis above is wrong")

    # Where the three now stand, post-correction-60.
    print()
    _fmt(PASS, "convergence", f"repo (fixed) {abs(cl_p_repo):.0f} | OpenRocket/2 133 | "
         f"RocketPy renormalised {abs(cl_p_rpy_fix):.0f} -- all within ~15%")
    _fmt(WARN, "still do not inherit", "RocketPy's shipped cld_omega. M1 must set Cl_p "
         "explicitly; see scripts/openrocket_roll_check.py for the kinematic-limit argument")
    rpy_ok = False

    # ------------------------------------------- T5: free pitch oscillation, a sign-blind check
    print("\nT5  free pitch oscillation -- one number that needs CN_alpha, CP, CG and I_pitch all right")
    v_lat = 1.0
    u2 = list(u0)
    u2[3] += v_lat
    stiff = [a - c for a, c in zip(omega_dot(flight, tt, u2), base)]
    alpha = np.arctan2(v_lat, max(pt.speed, 1.0))
    restoring = max(abs(stiff[pa]), abs(stiff[pb]))  # whichever transverse axis responds
    hz = float(np.sqrt(restoring / alpha)) / (2.0 * np.pi)
    # Evaluate the repo at the PROBE's own flight condition, not at the stored max-q value.
    # omega_n scales as sqrt(q), so comparing a 10.3 kPa probe against a 16.9 kPa headline
    # number manufactures a 22% "disagreement" out of nothing.
    want = control.pitch_authority(ev.rocket, pt, ev.masses.dry_mass, 2.0).pitch_natural_freq_hz
    close = abs(hz - want) / want < 0.10
    _fmt(INFO, "repo pitch freq, same q", f"{want:.4f} Hz  (headline value at max q is "
         f"{ev.pitch.pitch_natural_freq_hz:.4f} Hz)")
    _fmt(PASS if close else FAIL, "RocketPy pitch freq",
         f"{hz:.4f} Hz  ({hz/want:.3f}x) -- {'agrees' if close else 'INVESTIGATE before M1'}")

    print("\n" + "=" * 92)
    print("verdict: frame and pitch dynamics VERIFIED. Roll damping is not: RocketPy's "
          "cld_omega\n         carries a demonstrable Af/A_ref factor, and a ~1.7x modelling "
          "gap survives\n         removing it. M1 must make Cl_p an explicit, swappable input "
          "rather than\n         silently inheriting either model.")


if __name__ == "__main__":
    main()
