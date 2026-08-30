"""The canard hinge stack: loads, fits, and whether the thing can be built.

    python scripts/hinge_report.py            # print, and write out/hinge_report.txt

docs/05 listed two open items under "loose ends": a wall pass-through that was dia 5.000
against a dia 5.000 shaft, and a servo spline that reached 0.185 mm past the panel root
face. This closes both, and finds a third that neither the static model nor the swept
interference check could see.

Both of the recorded items, and the third one, are the same problem counted three ways:
between the servo's output face and the canard panel root there are 3.015 mm of radius,
the airframe wall takes 2.300 of them, and a hinge needs a bearing and a coupling in what
is left. No tolerance callout fixes that. The layout has to move.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import control, hinge
from design.configure import baseline, evaluate
from design.packaging import SERVO_GEOMETRY, SERVOS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "hinge_report.txt"
DEFLECTION_LIMIT_DEG = 8.0

MM = 1000.0
_lines: list[str] = []


def say(s: str = "") -> None:
    print(s)
    _lines.append(s)


def rule(title: str = "", width: int = 92) -> None:
    if title:
        say("\n" + "=" * width)
        say(title)
        say("=" * width)
    else:
        say("-" * width)


def stations(stack: hinge.HingeStack, label: str) -> None:
    say(f"\n  radial stations, {label} (mm from the rocket axis)")
    rows = [
        ("servo cable boss, inner end", stack.servo_inner_radius),
        ("servo output face", stack.servo_output_face),
        ("shaft sleeve, inboard end", stack.sleeve_inboard),
        ("bearing, inboard end", stack.bearing_inboard),
        ("tube ID", stack.tube_inner_radius),
        ("spline tip", stack.spline_tip),
        ("tube OD / bearing outboard end", stack.tube_outer_radius),
        ("panel root face", stack.panel_root),
    ]
    for name, r in sorted(rows, key=lambda t: t[1]):
        say(f"    {name:34s} R {r * MM:8.3f}")


def report(stack: hinge.HingeStack, loads: hinge.HingeLoads, label: str) -> hinge.HingeCheck:
    chk = hinge.check_hinge_stack(stack, loads)
    stations(stack, label)
    say(f"\n  shaft sleeve      dia {stack.journal_dia * MM:.3f} x "
        f"{stack.sleeve_length * MM:.3f} long")
    say(f"  wall bore         dia {stack.wall_bore_dia * MM:.3f}   "
        f"seat fit {stack.seat_fit * MM:+.3f} mm, running clearance "
        f"{stack.running_clearance * MM:+.3f} mm")
    say(f"  bearing           {stack.bearing_length * MM:.3f} long"
        + (f", {stack.bearing_in_wall * MM:.3f} of it inside the wall" if stack.has_bearing
           else "  -- NONE; the wall is doing this job by default"))
    say(f"  spline engagement {stack.spline_engagement * MM:.3f} mm "
        f"({stack.spline_engagement_fraction * 100:.0f}% of the spline)")
    say(f"  spline past panel root {stack.spline_past_panel_root * MM:+.3f} mm")
    say(f"  central void      dia {stack.central_void * MM:.2f}, "
        f"boss-to-boss margin {stack.boss_collision_margin * MM:+.2f} mm")
    say("")
    say(f"  panel normal force      {loads.normal_force:8.3f} N at R "
        f"{loads.load_radius * MM:.3f} mm")
    say(f"  hinge moment            {abs(loads.hinge_moment):8.4f} N m  "
        f"(the servo's number)")
    say(f"  bending at the tube OD  {loads.moment_at_wall:8.4f} N m  "
        f"(the bearing's number)")
    say(f"  bearing peak pressure   {loads.bearing_pressure / 1e6:8.1f} MPa   "
        f"margin {loads.bearing_margin:.2f}x against "
        f"{hinge.BEARING_PRESSURE_LIMIT / 1e6:.0f} MPa "
        f"(need {hinge.BEARING_MARGIN_REQUIRED:.1f}x)")
    say(f"  sleeve bending stress   {loads.shaft_stress / 1e6:8.1f} MPa   " +
        ", ".join(f"{k} {v:.1f}x" for k, v in loads.shaft_margin.items()))
    say(f"  spline socket pressure  {loads.spline_pressure / 1e6:8.1f} MPa at the servo's "
        f"{loads.spline_torque:.3f} N m stall torque")
    say("")
    if chk.ok:
        say("  VERDICT: buildable, every margin met.")
    else:
        say(f"  VERDICT: NOT BUILDABLE -- {len(chk.violations)} violation(s)")
    for x in chk.violations:
        say(f"    FAIL  {x}")
    for x in chk.notes:
        say(f"    note  {x}")
    return chk


def main() -> None:
    p = baseline()
    ev = evaluate(p, deflection_deg=DEFLECTION_LIMIT_DEG)
    r, f = ev.rocket, ev.flight
    c = r.canards
    geom = SERVO_GEOMETRY[p.servo]
    servo = SERVOS[p.servo]

    worst = max(
        (control.pitch_authority(r, pt, pt.mass, DEFLECTION_LIMIT_DEG)
         for pt in f.points if pt.q > 100),
        key=lambda a: abs(a.hinge_moment_per_panel),
    )
    hm = worst.hinge_moment_per_panel
    load_r = r.diameter / 2.0 + hinge.spanwise_centroid(
        c.root_chord, c.tip_chord, c.semispan)

    rule("CANARD HINGE STACK")
    say(f"  worst case              q = {worst.dynamic_pressure / 1000:.2f} kPa, "
        f"panel local alpha {worst.canard_local_alpha_deg:.2f} deg "
        f"({DEFLECTION_LIMIT_DEG:.0f} deg commanded + {worst.alpha_trim_deg:.2f} deg trim)")
    say(f"  panel                   root {c.root_chord * MM:.2f} / tip {c.tip_chord * MM:.2f} / "
        f"semispan {c.semispan * MM:.2f} mm, {c.planform_area_single * 1e6:.1f} mm^2")
    say(f"  spanwise centroid       {hinge.spanwise_centroid(c.root_chord, c.tip_chord, c.semispan) * MM:.3f} mm "
        f"outboard of the theoretical root")

    rule("AS BUILT  --  the Onshape model before this analysis")
    say("  Servo output face R 37.185. A SOLID dia 5.000 shaft from R 29.400 to R 40.200.")
    say("  The wall pass-through cut from the shaft's own sketch, so dia 5.000 on dia 5.000.")
    say("  No bearing anywhere, and no coupling between the spline and the shaft.")
    built = hinge.as_built(r.diameter / 2.0, r.tubes[1].wall_thickness, geom)
    loads_built = hinge.hinge_loads(built, hm, c.mean_chord, load_r, servo.stall_torque,
                                    geom.spline_teeth)
    chk_built = report(built, loads_built, "as built")

    rule("SELECTED  --  servo 4.000 mm inboard, dia 6 sleeve, bearing seat in the wall")
    say(hinge.selected.__doc__.split("\n", 2)[2].rstrip())
    sel = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, geom)
    loads_sel = hinge.hinge_loads(sel, hm, c.mean_chord, load_r, servo.stall_torque,
                                  geom.spline_teeth)
    chk_sel = report(sel, loads_sel, "selected")

    rule("WHAT THIS COSTS, AND WHAT IT DOES NOT")
    say(f"  central void            dia {built.central_void * MM:.2f} -> "
        f"dia {sel.central_void * MM:.2f}, over the 8.2 mm band where the cable bosses")
    say("                          sit, and dia 40.77 -> dia 32.77 over the 29.5 mm band")
    say("                          alongside the cases. The whole servo moved, so both")
    say("                          bands lost the same 8 mm; the wiring fits the smaller.")
    say("  frozen aerodynamics     UNCHANGED. The panel root stays at R 40.200 and the")
    say("                          planform is untouched, which is the whole reason the")
    say("                          servo moved instead of the panel.")
    say("  servo torque margin     UNCHANGED at 1:1 direct drive; the coupling is a spline")
    say("                          socket, not a gear.")
    say("  still open              the sleeve-to-panel joint. The sleeve ends flush at the")
    say(f"                          panel root and the panel is {c.thickness * MM:.1f} mm thick, so a")
    say(f"                          dia {sel.journal_dia * MM:.0f} shaft cannot simply enter it. That joint has")
    say(f"                          to carry {loads_sel.moment_at_wall:.3f} N m into a "
        f"{c.thickness * MM:.1f} mm panel.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(_lines) + "\n")
    print(f"\n  wrote {OUT}")

    if chk_built.ok:
        raise SystemExit("the as-built layout PASSED, which means this check is not "
                         "checking anything -- fix the check before trusting it")
    if not chk_sel.ok:
        raise SystemExit("the selected layout does not pass its own check")


if __name__ == "__main__":
    main()
