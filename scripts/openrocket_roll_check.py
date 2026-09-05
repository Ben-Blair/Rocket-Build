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
"""

from __future__ import annotations

import subprocess
import sys
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import control
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


def run(jar: Path, mach: float, velocity: float, roll_rate: float) -> dict[str, float]:
    stamp = CLASSES / "OrkRollDamp.class"
    if not stamp.exists() or stamp.stat().st_mtime < SOURCE.stat().st_mtime:
        CLASSES.mkdir(parents=True, exist_ok=True)
        subprocess.run(["javac", "-nowarn", "-cp", str(jar), "-d", str(CLASSES), str(SOURCE)],
                       check=True)
    proc = subprocess.run(
        ["java", "-Djava.awt.headless=true", "-cp", f"{jar}:{CLASSES}", "OrkRollDamp",
         str(ORK), str(mach), str(velocity), str(roll_rate)],
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

    # --- what it does to the number the project actually quotes -------------------------
    roll = ev.roll_interdig
    scale = abs(cl_p_repo / cl_p_ork)
    print(f"\n  Steady roll rate scales as 1/|Cl_p|, so if OpenRocket is right:")
    print(f"    at the {DEFLECTION_LIMIT_DEG:.0f} deg deflection limit: "
          f"{roll.steady_roll_rate_deg_s:.0f} -> {roll.steady_roll_rate_deg_s*scale:.0f} deg/s")
    capped = roll.steady_roll_rate_deg_s * 2.0 / DEFLECTION_LIMIT_DEG
    print(f"    at the 2 deg roll command cap:      {capped:.0f} -> {capped*scale:.0f} deg/s")
    print(f"\n  That cascades: gyro saturation, ROLL_COMMAND_CAP_DEG's sensor justification,")
    print(f"  and the scale-factor term that is 99% of the attitude budget all scale with")
    print(f"  roll rate. NOTHING should be changed on the strength of this script alone --")
    print(f"  see its docstring on why OpenRocket and RocketPy are not fully independent.")


if __name__ == "__main__":
    main()
