"""Vortex-lattice model of the canard + aft fin cruciform -- the fast second opinion.

    python3 cfd/vlm.py            # stdlib + numpy only; writes out/cfd/vlm_report.txt

WHY A VLM AS WELL AS SU2. They fail differently, which is the point of having both. A VLM
is linear potential flow on thin panels: it cannot stall, it has no body (so no body
carry-over and no body upwash), and its wake is a flat, rigid sheet that never rolls up.
But it is exact within those assumptions, runs in a second, and -- unlike Barrowman --
it actually computes WHERE ON THE CHORD the load sits and HOW THE CANARD WAKE LOADS THE
AFT FINS, the two quantities this vehicle's servo margin and roll-control sign rest on.
SU2 (cfd/run.py) has the body and a wake that convects and rolls up, but costs an hour a
case. Where the two agree the answer is robust; where they disagree the body or the
wake roll-up is responsible, and that is information too.

Written from scratch rather than taken from AeroSandbox because ASB's section twist
rotates about each section's own leading edge, and this vehicle's canards rotate about a
fixed radial HINGE LINE at 0.20 MAC -- getting that wrong would put the error exactly in
the hinge moment this file exists to check. Here every panel corner is rotated about the
true hinge axis, so there is nothing to get wrong.

Method: Katz & Plotkin's horseshoe-vortex lattice. Bound vortex on each panel's quarter
chord, control point at three-quarter chord, trailing legs to +infinity along +x.
Compressibility by the Goethert rule: stretch x by 1/beta, solve incompressible, and the
pressure-derived loads scale by 1/beta^2 -- which for a low-aspect-ratio panel is much
less than the 1/beta Barrowman applies to the lift slope, and is correct.

VALIDATED in `validate()` against Helmbold's lifting-surface lift slope for a flat
rectangular wing, CLa = 2 pi A / (2 + sqrt(A^2 + 4)), at three aspect ratios.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design import configure, hinge, packaging  # noqa: E402

OUT = ROOT / "out" / "cfd"
CANARD_CLOCK_DEG = (0.0, 90.0, 180.0, 270.0)
FIN_CLOCK_DEG_INTERDIG = (45.0, 135.0, 225.0, 315.0)
FIN_CLOCK_DEG_ALIGNED = (0.0, 90.0, 180.0, 270.0)
MACH = 0.45


def _rot(axis: np.ndarray, ang: float) -> np.ndarray:
    a = axis / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


@dataclass
class Surface:
    name: str
    corners: np.ndarray  # (n_span, n_chord, 4, 3): panel corners FL, FR, BR, BL


def panel_surface(name, f, r_body, clock_deg, n_span, n_chord, hinge_x=None,
                  delta_deg=0.0) -> Surface:
    """Trapezoid spanning radially from the body surface at clock angle `clock_deg`.

    Span along +y before clocking. A deflection rotates every corner about the radial
    hinge axis through (hinge_x, 0, 0) -- right-hand rule about the OUTWARD span axis.
    Clocking then rotates about +x.
    """
    s = f.semispan
    eta = (1 - np.cos(np.linspace(0, math.pi, n_span + 1))) / 2  # cosine spacing
    xi = np.linspace(0, 1, n_chord + 1)
    grid = np.zeros((n_span + 1, n_chord + 1, 3))
    for i, e in enumerate(eta):
        c = f.root_chord + (f.tip_chord - f.root_chord) * e
        x_le = f.x_root_le + f.sweep_length * e
        grid[i, :, 0] = x_le + xi * c
        grid[i, :, 1] = r_body + e * s
    if delta_deg:
        R = _rot(np.array([0.0, 1.0, 0.0]), math.radians(delta_deg))
        p0 = np.array([hinge_x, 0.0, 0.0])
        grid = (grid - p0) @ R.T + p0
    Rc = _rot(np.array([1.0, 0.0, 0.0]), math.radians(clock_deg))
    grid = grid @ Rc.T
    corners = np.stack([grid[:-1, :-1], grid[1:, :-1], grid[1:, 1:], grid[:-1, 1:]], axis=2)
    # corners order: (span i, chord j) -> FL=(i,j) FR=(i+1,j) BR=(i+1,j+1) BL=(i,j+1)
    return Surface(name, corners)


def _seg_induced(P, A, B):
    """Velocity at points P (N,3) from unit-strength segments A->B (M,3): returns (N,M,3)."""
    r1 = P[:, None, :] - A[None, :, :]
    r2 = P[:, None, :] - B[None, :, :]
    cr = np.cross(r1, r2)
    cr2 = np.einsum("nmk,nmk->nm", cr, cr)
    n1 = np.linalg.norm(r1, axis=2)
    n2 = np.linalg.norm(r2, axis=2)
    r0 = (B - A)[None, :, :]
    k = (np.einsum("nmk,nmk->nm", r0, r1) / np.maximum(n1, 1e-12)
         - np.einsum("nmk,nmk->nm", r0, r2) / np.maximum(n2, 1e-12))
    with np.errstate(divide="ignore", invalid="ignore"):
        f = np.where(cr2 > 1e-14, k / (4 * math.pi * cr2), 0.0)
    return cr * f[:, :, None]


def _semi_infinite(P, A, d):
    """Velocity from a unit semi-infinite vortex starting at A running along unit d."""
    r = P[:, None, :] - A[None, :, :]
    cr = np.cross(d[None, None, :], r)
    cr2 = np.einsum("nmk,nmk->nm", cr, cr)
    rn = np.linalg.norm(r, axis=2)
    cosang = np.einsum("k,nmk->nm", d, r) / np.maximum(rn, 1e-12)
    # Biot-Savart for a semi-infinite line: |v| = (1 + cos th)/(4 pi h) along d x r / h
    with np.errstate(divide="ignore", invalid="ignore"):
        f = np.where(cr2 > 1e-14, (1 + cosang) / (4 * math.pi * cr2), 0.0)
    return cr * f[:, :, None]


@dataclass
class Solution:
    surfaces: list[Surface]
    forces: np.ndarray  # (N,3) per panel, nondimensional by q_inf (i.e. force / q)
    points: np.ndarray  # (N,3) bound-vortex midpoints (where the force acts)
    owner: np.ndarray   # (N,) surface index


def _image(P: np.ndarray, R: float) -> np.ndarray:
    """Crossflow-plane image of points P in a cylinder of radius R along the x axis."""
    r2 = P[:, 1] ** 2 + P[:, 2] ** 2
    k = R**2 / np.maximum(r2, 1e-12)
    return np.stack([P[:, 0], P[:, 1] * k, P[:, 2] * k], axis=1)


def solve(surfaces: list[Surface], alpha_deg: float = 0.0, mach: float = 0.0,
          body_radius: float | None = None) -> Solution:
    """Solve the lattice. With `body_radius`, the body is represented slender-body style:

    * every horseshoe gets an IMAGE horseshoe of opposite strength at the crossflow-plane
      inverse point R^2/r, which makes the body surface a streamline for the trailing
      vorticity. Without it, a panel's load ends abruptly at the body and sheds a strong
      spurious ROOT vortex -- the single largest error a body-less VLM makes on a fin
      set, and it lands exactly on the roll-interference answer;
    * the freestream crossflow gets the cylinder's own upwash, W (1 + R^2/zeta^2).
    """
    beta = math.sqrt(1 - mach**2)
    C = np.concatenate([s.corners.reshape(-1, 4, 3) for s in surfaces])
    owner = np.concatenate([np.full(s.corners.shape[0] * s.corners.shape[1], k)
                            for k, s in enumerate(surfaces)])
    S = np.array([1 / beta, 1.0, 1.0])  # Goethert stretch
    Cs = C * S
    FL, FR, BR, BL = Cs[:, 0], Cs[:, 1], Cs[:, 2], Cs[:, 3]
    A = FL + 0.25 * (BL - FL)
    B = FR + 0.25 * (BR - FR)
    cp = 0.5 * ((FL + 0.75 * (BL - FL)) + (FR + 0.75 * (BR - FR)))
    n = np.cross(BR - FL, FR - BL)
    n /= np.linalg.norm(n, axis=1)[:, None]
    ex = np.array([1.0, 0.0, 0.0])
    a = math.radians(alpha_deg)
    if body_radius:
        Ai, Bi = _image(A, body_radius), _image(B, body_radius)

    def induced(P):
        v = (_seg_induced(P, A, B) + _semi_infinite(P, B, ex) - _semi_infinite(P, A, ex))
        if body_radius:
            v -= (_seg_induced(P, Ai, Bi) + _semi_infinite(P, Bi, ex)
                  - _semi_infinite(P, Ai, ex))
        return v

    def freestream(P):
        V = np.tile([math.cos(a), 0.0, 0.0], (len(P), 1))
        W = math.sin(a)
        if body_radius and W:
            zeta = P[:, 1] + 1j * P[:, 2]
            w = -1j * W * (1 + body_radius**2 / zeta**2)  # = vy - i vz
            V[:, 1] = w.real
            V[:, 2] = -w.imag
        elif W:
            V[:, 2] = W
        return V

    AIC = np.einsum("nmk,nk->nm", induced(cp), n)
    rhs = -np.einsum("nk,nk->n", freestream(cp), n)
    gamma = np.linalg.solve(AIC, rhs)
    mid = 0.5 * (A + B)
    v_mid = freestream(mid) + np.einsum("nmk,m->nk", induced(mid), gamma)
    # force per unit rho: rho * Gamma * (V x l); divide by q = rho V^2 / 2 with |V| = 1
    F = 2.0 * gamma[:, None] * np.cross(v_mid, B - A)
    # Goethert: undo the stretch on the lever arm, scale loads by 1/beta^2
    F = F / beta**2
    return Solution(surfaces, F, mid / S, owner)


def moment(sol: Solution, idx, point, axis) -> float:
    """Moment (per q) of surfaces `idx` about the line through `point` along `axis`."""
    mask = np.isin(sol.owner, np.atleast_1d(idx))
    r = sol.points[mask] - np.asarray(point)
    m = np.cross(r, sol.forces[mask]).sum(axis=0)
    return float(m @ (np.asarray(axis) / np.linalg.norm(axis)))


def force(sol: Solution, idx) -> np.ndarray:
    mask = np.isin(sol.owner, np.atleast_1d(idx))
    return sol.forces[mask].sum(axis=0)


def _wing(semispan, root, tip, sweep, ns=24, nc=10):
    """A full symmetric wing built as two mirrored halves (no body)."""
    f = type("P", (), dict(semispan=semispan, root_chord=root, tip_chord=tip,
                           sweep_length=sweep, x_root_le=0.0))
    right = panel_surface("r", f, 0.0, 0.0, ns, nc)
    left = panel_surface("l", f, 0.0, 180.0, ns, nc)
    left.corners[..., 2] *= -1  # clock 180 flips z as well as y; mirror back
    return [right, left]


def _ac_frac_mac(sol, root, tip, semispan, sweep) -> float:
    """Aerodynamic centre of a wing solved at alpha, as a fraction of MAC aft of MAC LE."""
    fz = force(sol, [0, 1])[2]
    my = moment(sol, [0, 1], (0, 0, 0), (0, 1, 0))
    x_cp = -my / fz
    lam = tip / root
    mac = (2 / 3) * root * (1 + lam + lam**2) / (1 + lam)
    y_mac = (semispan / 3) * (1 + 2 * lam) / (1 + lam)
    return (x_cp - sweep * y_mac / semispan) / mac


def validate() -> list[str]:
    """Two checks, both against textbook results, both on the quantity that matters:

    * LIFT SLOPE of flat rectangular wings against Helmbold's lifting-surface formula.
    * CHORDWISE CENTRE OF PRESSURE -- the thing the hinge moment turns on -- for a high-
      aspect-ratio rectangle (thin-airfoil / lifting-line: 0.25 MAC) and a low-aspect-
      ratio pure delta (slender-wing theory: 2/3 of the root chord from the apex, which is
      0.50 MAC). A VLM that gets both ends right can be trusted in between, where this
      vehicle's AR 2.4, 10:1 taper, 42 deg canard sits.
    """
    lines = ["VALIDATION 1 -- flat rectangular wing, lift slope vs Helmbold",
             "     AR   VLM CLa   Helmbold    error"]
    for AR in (1.0, 2.36, 6.0):
        b = AR
        sol = solve(_wing(b / 2, 1.0, 1.0, 0.0), 2.0)
        cl = force(sol, [0, 1])[2] / b / math.radians(2.0)
        helm = 2 * math.pi * AR / (2 + math.sqrt(AR**2 + 4))
        lines.append(f"  {AR:5.2f}  {cl:8.3f}  {helm:9.3f}  {100*(cl/helm-1):+6.1f}%")
    lines += ["", "VALIDATION 2 -- chordwise centre of pressure, fraction of MAC",
              "  wing                              VLM    theory"]
    sol = solve(_wing(4.0, 1.0, 1.0, 0.0, 30, 12), 2.0)
    lines.append(f"  rectangle, AR 8                 {_ac_frac_mac(sol, 1, 1, 4.0, 0.0):6.3f}    0.25 (lifting line), ~0.24 lifting surface")
    for AR in (0.5, 1.0):
        # pure delta, apex at root LE... built as root chord c, tip 0, semispan AR*c/4
        c, s_ = 1.0, AR / 4
        sol = solve(_wing(s_, c, 1e-4, c, 30, 12), 2.0)
        lines.append(f"  pure delta, AR {AR:<4}            {_ac_frac_mac(sol, c, 1e-4, s_, c):6.3f}    0.50 (slender-wing theory, AR -> 0)")
    return lines


def main() -> None:
    rocket = configure.build_vehicle(configure.baseline())
    d, R = rocket.diameter, rocket.diameter / 2
    A_ref = rocket.reference_area
    can, fin = rocket.canards, rocket.aft_fins
    hx = hinge.canard_hinge_station(rocket)
    taper = can.tip_chord / can.root_chord
    mac = (2 / 3) * can.root_chord * (1 + taper + taper**2) / (1 + taper)
    y_mac = (can.semispan / 3) * (1 + 2 * taper) / (1 + taper)
    x_le_mac = can.x_root_le + can.sweep_length * y_mac / can.semispan
    from design import aero, control

    def build(fin_clocks, defl, ns=14, nc=10):
        s = [panel_surface(f"C{i}", can, R, ck, ns, nc, hx, defl[i])
             for i, ck in enumerate(CANARD_CLOCK_DEG)]
        s += [panel_surface(f"F{i}", fin, R, ck, ns, nc) for i, ck in enumerate(fin_clocks)]
        return s

    out = validate()
    out += ["", f"VEHICLE -- frozen baseline, Mach {MACH}",
            f"  hinge station {hx*1000:.2f} mm = 0.200 MAC; canard MAC {mac*1000:.2f} mm,"
            f" MAC LE at {x_le_mac*1000:.2f} mm",
            "  Two body treatments: NONE (panels in free air) and IMAGES (slender-body image",
            "  vortices in an infinite cylinder -- the physically right one; NONE is shown so",
            "  the size of the body effect is visible, not so it can be quoted)."]
    results = {}

    # ---- 1. canard pitch pair: hinge moment and chordwise CP --------------------------
    delta = 6.0
    out += ["", "1. CANARD HINGE MOMENT -- pitch pair at +/-6 deg, alpha 0",
            "  body     resolution   CN/panel /rad   CP (MAC)   arm mm   x design arm"]
    for body in (None, R):
        for ns, nc in ((10, 6), (14, 10), (20, 16)):
            sol = solve(build(FIN_CLOCK_DEG_INTERDIG, (delta, 0, -delta, 0), ns, nc), 0.0,
                        MACH, body)
            hm0 = moment(sol, 0, (hx, 0, 0), (0, 1, 0))
            fz0 = force(sol, 0)[2]
            x_cp = hx - hm0 / fz0
            frac = (x_cp - x_le_mac) / mac
            cn = fz0 / math.radians(delta) / A_ref
            out.append(f"  {'IMAGES' if body else 'NONE':7s}  {ns:3d} x {nc:<3d}     {cn:8.3f}      "
                       f"{frac:6.3f}    {(x_cp-hx)*1000:6.2f}   {(x_cp-hx)/(0.05*mac):6.2f}x")
            results[("hinge", bool(body))] = (frac, cn)
    out += [f"  design (packaging.hinge_moment): CP 0.250 MAC, arm {0.05*mac*1000:.2f} mm",
            "  The ratio in the last column multiplies EVERY hinge moment and servo-torque",
            "  number in the repo -- it is the fraction the moment arm was underestimated by."]

    # ---- 2. roll: canard couple vs the aft fins' induced opposing couple ----------------
    out += ["", "2. ROLL -- all four canards +5 deg about their own span axis, alpha 0",
            "  body     clocking          canards Cl/rad   aft fins Cl/rad   net Cl/rad   lost   design"]
    pt = type("Pt", (), dict(mach=MACH, q=1.0, speed=150.0, cg=0.78))
    for body in (None, R):
        for label, clocks, model in (("interdigitated", FIN_CLOCK_DEG_INTERDIG,
                                      control.InterferenceModel.interdigitated()),
                                     ("aligned", FIN_CLOCK_DEG_ALIGNED,
                                      control.InterferenceModel.aligned())):
            sol = solve(build(clocks, (5, 5, 5, 5)), 0.0, MACH, body)
            per = A_ref * d * math.radians(5)
            m_can = moment(sol, [0, 1, 2, 3], (0, 0, 0), (1, 0, 0)) / per
            m_fin = moment(sol, [4, 5, 6, 7], (0, 0, 0), (1, 0, 0)) / per
            rr = control.roll_authority(rocket, pt, 6.2, 5.0, model)
            lost_d = -rr.cl_delta_aftfin / rr.cl_delta_canard
            out.append(f"  {'IMAGES' if body else 'NONE':7s}  {label:15s} {m_can:+14.3f} {m_fin:+17.3f}"
                       f" {m_can+m_fin:+12.3f}  {100*-m_fin/m_can:5.1f}%  {100*lost_d:5.1f}%")
            results[("roll", bool(body), label)] = (m_can, m_fin)
    out += ["  'lost' = fraction of the canards' own roll authority the aft fins take back.",
            "  This is the classic canard-roll-control problem: the four canard tip vortices",
            "  all turn the same way, so between them and the body they set up a SWIRL that",
            "  the aft fins see as incidence opposite to the command. The VLM's wake is a rigid",
            "  sheet that never rolls up or moves; SU2's does both -- trust SU2 over this."]

    # ---- 3. panel lift slopes vs Barrowman ---------------------------------------------
    out += ["", "3. PANEL LIFT SLOPE at alpha 2 deg, one panel, ref body area",
            "  panel     VLM none   VLM images   Barrowman (with its body factor)"]
    for nm, f in (("canard", can), ("aft fin", fin)):
        vals = []
        for body in (None, R):
            s1 = panel_surface("a", f, R, 0.0, 14, 10)
            s2 = panel_surface("b", f, R, 180.0, 14, 10)
            sol = solve([s1, s2], 2.0, MACH, body)
            # both panels lift +z (clock 180 rotates the panel but the freestream does not care)
            vals.append(force(sol, [0, 1])[2] / 2 / math.radians(2.0) / A_ref)
        barr = aero.single_fin_cn_alpha(f, d, MACH)
        out.append(f"  {nm:8s}  {vals[0]:8.3f}   {vals[1]:10.3f}   {barr:8.3f}")
    out += ["  Barrowman's single-fin slope includes its (1 + R/(s+R)) body factor, so the",
            "  IMAGES column is the like-for-like one."]

    OUT.mkdir(parents=True, exist_ok=True)
    txt = "\n".join(out)
    (OUT / "vlm_report.txt").write_text(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
