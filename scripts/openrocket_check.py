"""Cross-check the Python design tool against OpenRocket, automatically.

Run:  python scripts/openrocket_check.py

Generates the .ork, loads it with OpenRocket's own engine headlessly, and prints a
side-by-side comparison. No GUI, no transcribing numbers by hand.

Why this is worth the trouble: scripts/robustness.py found that CP prediction error
dominates every other uncertainty in the design -- it outweighs every mass line combined.
Nothing in this repository can find an error in this repository, so the only way to attack
that uncertainty is a second, independently written Barrowman implementation. OpenRocket
is that second opinion, and turning the comparison into one command means it stays honest
every time the design changes instead of being done once and going stale.

Requires OpenRocket installed and a JDK (for javac). Both are checked for.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import aero
from design.configure import build_vehicle, evaluate
from design.mass import build_mass
from design.packaging import SERVOS

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
JAR_GLOBS = [
    "/Applications/OpenRocket.app/Contents/Resources/app/jar/OpenRocket-*.jar",
    str(Path.home() / "**/OpenRocket*.jar"),
]


def find_jar() -> Path | None:
    from glob import glob

    for pattern in JAR_GLOBS:
        hits = sorted(glob(pattern, recursive="**" in pattern))
        if hits:
            return Path(hits[-1])
    return None


def load_baseline():
    spec = importlib.util.spec_from_file_location("make_ork", ROOT / "scripts" / "make_ork.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_ork_check(jar: Path, ork: Path, mach: float) -> dict[str, str]:
    classes = ROOT / "out" / "javacls"
    source = ROOT / "tools" / "OrkCheck.java"
    stamp = classes / "OrkCheck.class"
    if not stamp.exists() or stamp.stat().st_mtime < source.stat().st_mtime:
        classes.mkdir(parents=True, exist_ok=True)
        print("  compiling tools/OrkCheck.java ...")
        subprocess.run(
            ["javac", "-nowarn", "-cp", str(jar), "-d", str(classes), str(source)],
            check=True,
        )

    proc = subprocess.run(
        ["java", "-Djava.awt.headless=true", "-cp", f"{jar}:{classes}",
         "OrkCheck", str(ork), str(mach)],
        capture_output=True, text=True, check=True,
    )
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if line.startswith("ORK_"):
            key, _, value = line.partition(" ")
            out.setdefault(key, value.strip())
            if key in ("ORK_WARNING", "ORK_LOAD_WARNING", "ORK_COMPONENT"):
                out.setdefault("_list_" + key, "")
                out["_list_" + key] += value.strip() + "\n"
    return out


def row(label: str, mine: float, theirs: float, unit: str, tol: float,
        relative: bool = True) -> tuple[str, bool]:
    delta = theirs - mine
    if relative:
        pct = 100.0 * delta / mine if mine else float("inf")
        ok = abs(pct) <= tol
        detail = f"{pct:+6.1f}%"
    else:
        ok = abs(delta) <= tol
        detail = f"{delta:+7.2f}"
    mark = "ok" if ok else "CHECK"
    return (f"  {label:26s} {mine:10.2f} {theirs:11.2f} {unit:5s} {detail}   {mark}", ok)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mach", type=float, default=0.1)
    args = ap.parse_args()

    jar = find_jar()
    if jar is None:
        sys.exit("OpenRocket jar not found. Install OpenRocket, or edit JAR_GLOBS.")
    if shutil.which("javac") is None:
        sys.exit("javac not found. Install a JDK (brew install openjdk).")

    print(f"OpenRocket: {jar.name}")

    mk = load_baseline()
    params = mk.BASELINE
    xml, _ = mk.build_xml(params)
    ork = ROOT / "out" / "RocketSenior.ork"
    ork.parent.mkdir(parents=True, exist_ok=True)
    import zipfile

    with zipfile.ZipFile(ork, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("rocket.ork", xml)
    print(f"generated:  {ork.relative_to(ROOT)}\n")

    data = run_ork_check(jar, ork, args.mach)

    rocket = build_vehicle(params)
    masses = build_mass(
        rocket, params.motor,
        servo_mass_each=SERVOS[params.servo].mass, n_servos=params.n_canards,
    )
    ev = evaluate(params, deflection_deg=8.0)
    stab = aero.stability(rocket, masses.wet_cg, args.mach)
    stab_nb = aero.stability(rocket, masses.wet_cg, args.mach, include_body_lift=False)
    d = rocket.diameter

    print("=" * 78)
    print(f"CORRELATION  (Mach {args.mach}, motor loaded)")
    print("=" * 78)
    print(f"  {'quantity':26s} {'this tool':>10s} {'OpenRocket':>11s} {'unit':5s} {'delta':>7s}")
    print(f"  {'-' * 26} {'-' * 10} {'-' * 11} {'-' * 5} {'-' * 7}")

    checks = [
        row("total length", rocket.length * 1000, float(data["ORK_LENGTH_MM"]), "mm", 1.0),
        row("dry mass", masses.dry_mass, float(data["ORK_DRY_MASS_KG"]), "kg", 5.0),
        row("loaded mass", masses.wet_mass, float(data["ORK_WET_MASS_KG"]), "kg", 5.0),
        row("CG dry", masses.dry_cg * 1000, float(data["ORK_DRY_CG_MM"]), "mm", 3.0),
        row("CG loaded", masses.wet_cg * 1000, float(data["ORK_WET_CG_MM"]), "mm", 3.0),
        row("CNa (with body lift)", stab.cn_alpha, float(data["ORK_CNA"]), "/rad", 10.0),
        row("CNa (no body lift)", stab_nb.cn_alpha, float(data["ORK_CNA"]), "/rad", 5.0),
        row("CP (with body lift)", stab.cp_station * 1000, float(data["ORK_CP_MM"]), "mm", 5.0),
        row("CP (no body lift)", stab_nb.cp_station * 1000, float(data["ORK_CP_MM"]), "mm", 5.0),
    ]
    for line, _ in checks:
        print(line)

    sm_mine = stab.static_margin_cal
    sm_theirs = float(data["ORK_SM_LOADED_CAL"])
    line, sm_ok = row("static margin loaded", sm_mine, sm_theirs, "cal", 0.5, relative=False)
    print(line)

    print("\n" + "-" * 78)
    motor = data.get("ORK_MOTOR", "NONE RESOLVED")
    print(f"  motor resolved by OpenRocket:\n    {motor}")
    if data.get("ORK_MOTOR_COUNT") != "1":
        print("  *** OpenRocket did not resolve exactly one motor. Fix before trusting anything.")

    warnings = data.get("_list_ORK_WARNING", "") + data.get("_list_ORK_LOAD_WARNING", "")
    print(f"  OpenRocket warnings: {warnings.strip() if warnings.strip() else 'none'}")

    cp_gap_cal = (float(data["ORK_CP_MM"]) / 1000 - stab.cp_station) / d
    cp_gap_nb = (float(data["ORK_CP_MM"]) / 1000 - stab_nb.cp_station) / d
    print(f"""
{'=' * 78}
READING THIS
{'=' * 78}
  CP disagreement, like for like (body lift off) {cp_gap_nb:+.2f} cal
  CP disagreement including body lift            {cp_gap_cal:+.2f} cal

  OpenRocket's Barrowman runs at zero angle of attack and so carries no body lift term.
  This tool includes a Galejs body-lift correction linearised about 4 degrees, which adds
  normal force at the body centroid -- well forward of the fins -- and therefore pulls CP
  forward. Turning it off is the apples-to-apples comparison, and that is the number to
  judge the implementations by.

  A positive gap means OpenRocket thinks the rocket is MORE stable than this tool does,
  which is the safe direction to disagree in: the design is sized against the pessimistic
  of the two.

  What this does and does not prove. Two implementations agreeing tells you neither has a
  coding error. It does not tell you Barrowman is right about this airframe -- both tools
  share the same theory, and that theory does not model canard-to-fin interference at all.
  Only flight data settles that, which is what the GV-1 open-loop sweep is for.""")


if __name__ == "__main__":
    main()
