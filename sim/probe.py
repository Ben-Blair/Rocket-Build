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

WHAT IT FOUND (2026-09-05, first run): T2 fails. RocketPy's native fin roll damping is
~4.6x too large on the AFT FINS specifically, and this project's own `roll_damping_cl_p()`
is right to within ~12%. See T2's own commentary -- the consequence is that M1 must override
RocketPy's fin roll damping rather than inherit it.
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


def strip_theory_cl_p(rocket, mach):
    """Cl_p from strip theory, using each fin set's OWN agreed lift slope. The arbiter.

    A rolling panel at radius y sees local AoA p*y/V, so the damping moment weights the
    chord distribution by y^2: the honest quantity is `integral c(y) y^2 dy`, not the lift
    centroid squared. The sectional slope `a0` is pinned by requiring that the same strip
    model reproduce the fin set's total CN_alpha at uniform alpha, which is what makes this
    an independent check rather than a third arbitrary convention.
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
    print("\nT2  roll damping -- repo vs RocketPy vs strip theory (the independent arbiter)")
    pt = min(ev.flight.points, key=lambda p: abs(p.t - tt))
    d, A = ev.rocket.diameter, ev.rocket.reference_area

    cl_p_repo = control.roll_damping_cl_p(ev.rocket, pt.mach)
    cl_p_strip = strip_theory_cl_p(ev.rocket, pt.mach)
    # back RocketPy's out of the measured dynamics, using ITS OWN inertia so the comparison
    # is of aerodynamics alone rather than of two inertia models
    i_roll_rpy = b.rocket.I_33(tt)
    p_hat = 1.0 * d / (2.0 * max(pt.speed, 1.0))
    cl_p_rpy = (resp[roll_i] * i_roll_rpy) / (pt.q * A * d * p_hat)

    _fmt(INFO, "flight condition", f"t={tt:.2f}s q={pt.q:.0f}Pa M={pt.mach:.3f} V={pt.speed:.1f}m/s")
    _fmt(INFO, "strip theory (arbiter)", f"{cl_p_strip:9.2f} /rad")
    _fmt(INFO, "design/control.py", f"{cl_p_repo:9.2f} /rad   ({cl_p_repo/cl_p_strip:.3f}x arbiter)")
    _fmt(INFO, "RocketPy (from dynamics)", f"{cl_p_rpy:9.2f} /rad   ({cl_p_rpy/cl_p_strip:.3f}x arbiter)")

    repo_ok = 0.8 <= cl_p_repo / cl_p_strip <= 1.25
    rpy_ok = 0.8 <= cl_p_rpy / cl_p_strip <= 1.25
    _fmt(PASS if repo_ok else WARN, "repo vs arbiter",
         "point-lumping the panel at its lift centroid costs ~12%, as expected" if repo_ok
         else "repo disagrees with strip theory")
    _fmt(PASS if rpy_ok else FAIL, "RocketPy vs arbiter",
         "agrees" if rpy_ok else "DISAGREES -- do not inherit RocketPy's fin roll damping")

    if not rpy_ok:
        print()
        _fmt(WARN, "localised to", "the AFT FINS; the canards agree. Per-set breakdown:")
        for fins, surf in ((ev.rocket.aft_fins, b.rocket.aerodynamic_surfaces[1][0]),
                           (ev.rocket.canards, b.rocket.aerodynamic_surfaces[2][0])):
            per_fin = surf.clalpha_multiple_fins(pt.mach) / fins.count
            implied = per_fin * A / fins.planform_area_single
            used = surf.clalpha_single_fin(pt.mach)
            _fmt(WARN, f"  {fins.name}", f"lift model implies a0={implied:.3f} but cld_omega "
                 f"uses clalpha_single_fin={used:.3f}  ({used/implied:.2f}x)")
        _fmt(WARN, "reading", "RocketPy's own lift and roll-damping models use inconsistent "
             "slopes, and only for the high span/radius set")

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
    verdict = "M1 MAY PROCEED" if rpy_ok else "M1 BLOCKED until roll damping is overridden"
    print(f"verdict: {verdict}")


if __name__ == "__main__":
    main()
