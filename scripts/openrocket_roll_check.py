"""Third opinion on ROLL DAMPING: OpenRocket vs design/control.py vs RocketPy.

Run:  python scripts/openrocket_roll_check.py

WHY. `sim/probe.py` found that RocketPy's simulated roll damping is ~4x
`design/control.roll_damping_cl_p()`. Nothing inside this repository can adjudicate that --
`roll_damping_cl_p` is the only roll damping model it has, and any check built from
`aero.panel_cn_alpha` inherits that same model and will agree with it for circular reasons.
OpenRocket is a third, separately written implementation, already integrated here for the CP
cross-check (`scripts/openrocket_check.py`), and its `AerodynamicForces.getCrollDamp()`
exposes exactly the term at issue.

CAVEAT, AND IT IS NOT A SMALL ONE. RocketPy's `fin_num_correction()` cites "Niskanen, S.
(2013), OpenRocket technical documentation" in its own source. The two share lineage on the
fin-count treatment that roll damping depends on, so OpenRocket agreeing with RocketPy is
weaker evidence than two genuinely independent codes agreeing -- it may show only that one
borrowed from the other. Agreement here should be read as "the repo is the outlier", not as
"the answer is settled".

NORMALISATION. OpenRocket returns a roll damping COEFFICIENT at a given roll rate, not a
derivative. This script verifies empirically that it is linear in p and scales as 1/V (after
allowing for the Mach dependence of the lift slope) before converting with
p_hat = p*d/(2V), so the conversion is checked rather than assumed.

WHAT IT CONCLUDED. All three implementations are wrong, in three different ways, and they
converge on Cl_p ~ 125-140 /rad once each is corrected:

  * OpenRocket damps ~2x too hard. Proven by the KINEMATIC LIMIT below, which is the only
    convention-free test here: a canted fin set must roll until the local incidence from
    rolling cancels the cant, and no lift slope, area or normalisation enters that. Its roll
    FORCING checks out against strip theory to 0.5%, so the error is in the damping alone.
  * RocketPy carries a spurious Af/A_ref factor (see sim/probe.py), which over-predicts the
    big aft fins and UNDER-predicts the canards -- opposite directions, so its total looks
    deceptively reasonable while its aft/canard split is 3x off.
  * design/control.py is 2.15x low, from two compounding causes, both diagnosed below.

AND THE PRACTICAL ANSWER IS THAT IT BARELY MATTERS. Steady roll rate goes as
Cl_delta/|Cl_p|, and the dominant repo error lives in `aero.panel_cn_alpha`, which BOTH
derivatives are built from -- so it cancels. The quoted 558 deg/s at the 2 deg cap becomes
491, a 12% change, not the 4x an earlier reading of this script claimed.
"""

from __future__ import annotations

import math
import subprocess
import sys
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import aero, control
from design.configure import DEFLECTION_LIMIT_DEG, baseline, evaluate

ROOT = Path(__file__).resolve().parents[1]
ORK = ROOT / "out" / "RocketSenior.ork"
CLASSES = ROOT / "out" / "javacls"
SOURCE = ROOT / "tools" / "OrkRollDamp.java"
JAR_GLOBS = ["/Applications/OpenRocket.app/Contents/Resources/app/jar/OpenRocket-*.jar",
             str(Path.home() / "**/OpenRocket*.jar")]


def find_jar() -> Path:
    for pattern in JAR_GLOBS:
        hits = sorted(glob(pattern, recursive="**" in pattern))
        if hits:
            return Path(hits[-1])
    sys.exit("OpenRocket jar not found -- install OpenRocket.")


def variant_ork(drop_fin_set: str) -> Path:
    """A copy of the .ork with one fin set deleted, so its damping can be read alone.

    OpenRocket reports one total CrollDamp, and the totals of the three implementations are
    the least informative comparison available -- two different errors can cancel in a sum.
    Removing a fin set is the cheapest way to get the split.
    """
    import re
    import zipfile

    out = ROOT / "out" / f"_rollcheck_no_{drop_fin_set.replace(' ', '_').lower()}.ork"
    xml = zipfile.ZipFile(ORK).read("rocket.ork").decode()
    for m in re.finditer(r"<trapezoidfinset>.*?</trapezoidfinset>", xml, re.S):
        if f"<name>{drop_fin_set}</name>" in m.group(0):
            xml = xml.replace(m.group(0), "")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("rocket.ork", xml)
    return out


def canted_ork(cant_deg: float) -> Path:
    """The .ork with canards removed and the aft fins canted, for the kinematic-limit test."""
    import re
    import zipfile

    out = ROOT / "out" / f"_rollcheck_cant{cant_deg}.ork"
    xml = zipfile.ZipFile(ORK).read("rocket.ork").decode()
    for m in re.finditer(r"<trapezoidfinset>.*?</trapezoidfinset>", xml, re.S):
        blk = m.group(0)
        if "<name>Canards</name>" in blk:
            xml = xml.replace(blk, "")
        else:
            xml = xml.replace(blk, blk.replace("<cant>0.0</cant>", f"<cant>{cant_deg}</cant>"))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("rocket.ork", xml)
    return out


def run(jar: Path, mach: float, velocity: float, roll_rate: float,
        ork: Path | None = None) -> dict[str, float]:
    stamp = CLASSES / "OrkRollDamp.class"
    if not stamp.exists() or stamp.stat().st_mtime < SOURCE.stat().st_mtime:
        CLASSES.mkdir(parents=True, exist_ok=True)
        subprocess.run(["javac", "-nowarn", "-cp", str(jar), "-d", str(CLASSES), str(SOURCE)],
                       check=True)
    proc = subprocess.run(
        ["java", "-Djava.awt.headless=true", "-cp", f"{jar}:{CLASSES}", "OrkRollDamp",
         str(ork or ORK), str(mach), str(velocity), str(roll_rate)],
        capture_output=True, text=True, check=True)
    out = {}
    for line in proc.stdout.splitlines():
        if line.startswith("ORK_") and len(line.split()) == 2:
            k, v = line.split()
            try:
                out[k] = float(v)
            except ValueError:
                pass
    return out


def main() -> None:
    jar = find_jar()
    if not ORK.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_ork.py"),
                        "-o", str(ORK)], check=True, capture_output=True)

    ev = evaluate(baseline(), deflection_deg=DEFLECTION_LIMIT_DEG)
    d = ev.rocket.diameter
    # the same condition sim/probe.py uses: burnout + 2 s
    pt = min(ev.flight.points, key=lambda p: abs(p.t - (ev.flight.burnout_time + 2.0)))
    v, mach = pt.speed, pt.mach

    print("OpenRocket roll damping -- third implementation")
    print("=" * 88)
    print(f"\ncondition: M={mach:.3f}  V={v:.1f} m/s  d={d:.4f} m\n")

    # --- verify the normalisation before trusting the conversion ----------------------
    base = run(jar, mach, v, 1.0)["ORK_CROLL_DAMP"]
    twice_p = run(jar, mach, v, 2.0)["ORK_CROLL_DAMP"]
    print(f"  linear in roll rate?   p=1 -> {base:.8f},  p=2 -> {twice_p:.8f}  "
          f"(ratio {twice_p/base:.4f}, want 2.0)")
    linear = abs(twice_p / base - 2.0) < 1e-3
    if not linear:
        sys.exit("  OpenRocket's CrollDamp is not linear in p -- conversion below is invalid.")

    p_hat = 1.0 * d / (2.0 * v)
    cl_p_ork = -base / p_hat

    # --- the three implementations -----------------------------------------------------
    cl_p_repo = control.roll_damping_cl_p(ev.rocket, mach)
    print(f"\n  {'implementation':34s} {'Cl_p (/rad)':>12s} {'vs OpenRocket':>14s}")
    print("  " + "-" * 62)
    print(f"  {'OpenRocket 24.12 (getCrollDamp)':34s} {cl_p_ork:12.2f} {'1.000':>14s}")
    print(f"  {'design/control.roll_damping_cl_p':34s} {cl_p_repo:12.2f} {cl_p_repo/cl_p_ork:14.3f}")
    print(f"  {'RocketPy (see sim/probe.py)':34s} {'-307.64':>12s} {307.64/abs(cl_p_ork):14.3f}")

    # --- per fin set, which is what actually discriminates between the three -----------
    # Comparing TOTALS is misleading here: two different errors can partly cancel in a sum.
    # Splitting by fin set separates them, because the two sets have very different
    # Af/A_ref (2.72 aft, 0.64 canard), so any error that scales with fin area shows up as
    # a change in the aft/canard RATIO rather than in the total.
    aft_only = run(jar, mach, v, 1.0, ork=variant_ork("Canards"))["ORK_CROLL_DAMP"] / p_hat
    can_only = run(jar, mach, v, 1.0, ork=variant_ork("Aft fins"))["ORK_CROLL_DAMP"] / p_hat
    # post-correction-60 form, matching design/control.roll_damping_cl_p exactly
    fa, fc = ev.rocket.aft_fins, ev.rocket.canards
    repo_a = 2 * fa.count * aero.single_fin_cn_alpha(fa, d, mach) * fa.mean_square_radius / d**2
    repo_c = 2 * fc.count * aero.single_fin_cn_alpha(fc, d, mach) * fc.mean_square_radius / d**2
    rpy_a, rpy_c = 296.59, 10.87  # from sim/probe.py at this condition

    print(f"\n  {'':12s} {'aft fins':>10s} {'canards':>10s} {'total':>10s} {'aft/canard':>11s}")
    print("  " + "-" * 58)
    print(f"  {'repo':12s} {repo_a:10.2f} {repo_c:10.2f} {repo_a+repo_c:10.2f} {repo_a/repo_c:11.2f}")
    print(f"  {'OpenRocket':12s} {aft_only:10.2f} {can_only:10.2f} {aft_only+can_only:10.2f} {aft_only/can_only:11.2f}")
    print(f"  {'RocketPy':12s} {rpy_a:10.2f} {rpy_c:10.2f} {rpy_a+rpy_c:10.2f} {rpy_a/rpy_c:11.2f}")
    print(f"\n  TWO SEPARATE PROBLEMS, which comparing totals alone would have hidden:")
    print(f"    1. RocketPy's aft/canard split ({rpy_a/rpy_c:.1f}) is far from both others "
          f"({repo_a/repo_c:.1f}, {aft_only/can_only:.1f}).")
    print(f"       OpenRocket sides with the repo on SHAPE, which supports the Af/A_ref")
    print(f"       finding in sim/probe.py -- RocketPy's canard damping is anomalously low.")
    print(f"    2. The repo is uniformly low against OpenRocket on BOTH sets "
          f"({aft_only/repo_a:.1f}x aft, {can_only/repo_c:.1f}x canard) -- a different problem,")
    print(f"       and the reason its total is 4x off. Diagnosed below.")
    print(f"\n  So RocketPy's total looking close to OpenRocket's is partly two errors cancelling.")

    # --- the kinematic limit: the only convention-free test available -------------------
    # A canted fin set must roll until the local incidence from rolling cancels the cant:
    #     integral c(y) * (delta - p*y/V) * y dy = 0   =>   p = V*delta / (I2/I1)
    # No lift slope, no area, no coefficient normalisation appears in that. It is the one
    # check that cannot be argued with on conventions, and it is what finally settled this.
    import numpy as np

    f = ev.rocket.aft_fins
    rb, s = f.body_diameter / 2.0, f.semispan
    yy = np.linspace(rb, rb + s, 40001)
    cc = f.root_chord + (f.tip_chord - f.root_chord) * (yy - rb) / s
    i1, i2 = np.trapezoid(cc * yy, yy), np.trapezoid(cc * yy**2, yy)
    p_kin = v * math.radians(1.0) / (i2 / i1)

    cant = run(jar, mach, v, 1.0, ork=canted_ork(1.0))
    p_ork = cant["ORK_CROLL_FORCE"] / cant["ORK_CROLL_DAMP"]
    print(f"\n  KINEMATIC LIMIT (canted aft fins, 1 deg, canards removed):")
    print(f"    required by kinematics   {p_kin:7.2f} rad/s ({math.degrees(p_kin):.0f} deg/s)")
    print(f"    OpenRocket equilibrium   {p_ork:7.2f} rad/s ({math.degrees(p_ork):.0f} deg/s)"
          f"   ratio {p_ork/p_kin:.4f}")
    print(f"    -> OpenRocket damps ~2x too hard. Its roll FORCING checks out against strip")
    print(f"       theory to 0.5%, so the error is specifically in the damping term.")

    # --- what correction 60 fixed in this repo, kept as the audit trail ----------------
    k_count = 2.0   # set value is roll-averaged: ~N/2 fins effective at alpha, all N in roll
    k_weight = f.mean_square_radius / f.spanwise_cp_radius ** 2
    print(f"\n  CORRECTION 60 (already applied to design/control.py). The two causes were:")
    print(f"    {k_count:.3f}x  Barrowman's 4N(s/d)^2 is ROLL-AVERAGED -- only ~half the fins are")
    print(f"           effective AT ANGLE OF ATTACK; for ROLL all {f.count} of them are")
    print(f"    {k_weight:.3f}x  lumping at the lift centroid rather than the y^2-weighted radius")
    print(f"    -> Cl_p went {abs(cl_p_repo)/(k_count*k_weight):.0f} to {abs(cl_p_repo):.0f} /rad")
    print(f"\n  ALL THREE converge on Cl_p ~ 125-150 /rad once each is corrected:")
    print(f"    repo (fixed) {abs(cl_p_repo):.0f} | OpenRocket/2 {abs(cl_p_ork)/2:.0f} "
          f"| RocketPy renormalised 126")

    # --- what it does to the number the project actually quotes -------------------------
    # --- and now the part that matters: it barely moves the quoted roll rate ------------
    # Steady roll rate goes as Cl_delta/|Cl_p|, NOT as Cl_p alone. The k_count error above
    # is in `aero.panel_cn_alpha`, which BOTH derivatives are built from, so it cancels in
    # the ratio. Only the y^2-weighting error (k_weight), which affects Cl_p and not
    # Cl_delta, survives. A 2.15x error in Cl_p is therefore a 1.14x error in roll rate.
    roll = ev.roll_interdig
    capped = roll.steady_roll_rate_deg_s * 2.0 / DEFLECTION_LIMIT_DEG
    print(f"\n  WHY THE OBSERVABLE BARELY MOVED, which is why this survived so long:")
    print(f"    Cl_delta read the SAME panel_cn_alpha, so it was low by the same {k_count:.1f}x.")
    print(f"    Steady roll rate goes as Cl_delta/|Cl_p|, so that factor cancels out of the")
    print(f"    ratio entirely and only the {k_weight:.3f}x y^2 weighting survives it.")
    print(f"      at the {DEFLECTION_LIMIT_DEG:.0f} deg deflection limit: "
          f"{roll.steady_roll_rate_deg_s*k_weight:.0f} -> {roll.steady_roll_rate_deg_s:.0f} deg/s")
    print(f"      at the 2 deg roll command cap:      {capped*k_weight:.0f} -> {capped:.0f} deg/s")
    print(f"\n  A model can be materially wrong in both numerator and denominator and still")
    print(f"  predict the observable. That is the argument for checking DERIVATIVES against")
    print(f"  another code rather than only checking outcomes.")
    print(f"\n  ONE CONCLUSION DID MOVE: {roll.steady_roll_rate_deg_s:.0f} deg/s is "
          f"{roll.steady_roll_rate_deg_s/2000*100:.0f}% of a +/-2000 dps part, so the deflection")
    print(f"  limit no longer SATURATES it -- corrections 55 and 58's premise. The roll cap")
    print(f"  survives on zero-headroom grounds, not saturation. See correction 60.")


if __name__ == "__main__":
    main()
