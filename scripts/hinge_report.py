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

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import aero, control, hinge, tube_section
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


def joint_report(joint: hinge.RootJoint, loads: hinge.RootJointLoads) -> hinge.HingeCheck:
    chk = hinge.check_root_joint(joint, loads)
    say(f"    tang              {joint.tang_thickness * MM:.2f} x {joint.tang_width * MM:.2f} mm, "
        f"{joint.engagement * MM:.1f} mm engaged, skins {joint.skin_thickness * MM:+.2f} mm")
    say(f"    moment at root    {loads.moment:.4f} N m from {loads.normal_force:.2f} N")
    say(f"    tang bending      {loads.tang_bending_stress / 1e6:8.1f} MPa   " +
        ", ".join(f"{k} {v:.1f}x" for k, v in loads.tang_margin.items()))
    say(f"    skin over slot    {loads.skin_bending_stress / 1e6:8.1f} MPa   "
        f"{hinge.G10_FLEXURAL / loads.skin_bending_stress:.1f}x against "
        f"{hinge.G10_FLEXURAL / 1e6:.0f} MPa flexural"
        if loads.skin_bending_stress not in (0.0, float("inf")) else
        "    skin over slot      -- there is no skin")
    say(f"    slot bearing      {loads.slot_pressure_bending / 1e6:8.3f} MPa from bending, "
        f"{loads.slot_pressure_torque / 1e6:.3f} MPa from stall torque "
        f"({hinge.G10_BEARING / max(loads.slot_pressure_bending, loads.slot_pressure_torque):.0f}x)")
    say(f"    bond shear        {loads.bond_shear / 1e6:8.3f} MPa   "
        f"{hinge.G10_INTERLAMINAR_SHEAR / loads.bond_shear:.0f}x")
    if chk.ok:
        say("    VERDICT: buildable, every margin met.")
    else:
        say(f"    VERDICT: NOT BUILDABLE -- {len(chk.violations)} violation(s)")
    for x in chk.violations:
        say(f"      FAIL  {x}")
    for x in chk.notes:
        say(f"      note  {x}")
    return chk


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

    # Keep the POINT alongside the authority result: AuthorityResult does not carry Mach,
    # and the airframe bending free body needs it -- CNa at Mach 0.53 is 15% above its
    # incompressible value, which is not a rounding error in a load.
    worst_pt, worst = max(
        ((pt, control.pitch_authority(r, pt, pt.mass, DEFLECTION_LIMIT_DEG))
         for pt in f.points if pt.q > 100),
        key=lambda pair: abs(pair[1].hinge_moment_per_panel),
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

    # ==================================================================================
    rule("THE SLEEVE-TO-PANEL JOINT  --  the last link, and the hardest")
    say(hinge.selected_root_joint.__doc__.split("\n", 2)[2].rstrip())

    naive = hinge.naive_root_joint(sel, c)
    naive_loads = hinge.root_joint_loads(naive, loads_sel.normal_force, load_r,
                                         servo.stall_torque)
    say("\n  THE OBVIOUS JOINT  --  the dia 6 sleeve simply entering the panel")
    chk_naive = joint_report(naive, naive_loads)

    swept = hinge.swept_out_root_joint(sel, c)
    swept_loads = hinge.root_joint_loads(swept, loads_sel.normal_force, load_r,
                                         servo.stall_torque)
    say("\n  STRONG ENOUGH, AND STILL NOT BUILDABLE  --  the 1.8 x 14 x 30 tang this")
    say("  file selected before anything checked the swept leading edge")
    chk_swept = joint_report(swept, swept_loads)

    joint = hinge.selected_root_joint(sel, c)
    jloads = hinge.root_joint_loads(joint, loads_sel.normal_force, load_r,
                                    servo.stall_torque)
    say(f"\n  SELECTED  --  a {joint.tang_thickness * MM:.1f} x {joint.tang_width * MM:.1f} mm tang, "
        f"{joint.engagement * MM:.1f} mm into the panel root")
    chk_joint = joint_report(joint, jloads)

    # ==================================================================================
    rule("THE COUPLING  --  fifteen keys, cast rather than cut")
    cpl = hinge.bonded_coupling(sel, servo.stall_torque, geom.spline_teeth)
    say("  There is 0.515 mm between the servo's output face and the bearing, and outboard")
    say("  of that everything has to pass down the dia 6.000 journal. Fifteen teeth on a")
    say("  dia 4 pitch circle need metal around them, so every female-spline part sold --")
    say("  horn, hub, adapter -- is dia 7 or bigger. None of them fit, in either place.")
    say("")
    say("  So do not cut teeth. CAST them: drill a plain socket a few hundredths over the")
    say("  spline's crests, fill it with anaerobic retaining compound, push it on. The")
    say("  compound cures in the valleys and becomes the female spline -- keys formed by")
    say("  the part they mate with, so they fit by construction. One drilled hole, on a")
    say("  shaft that is already being turned.")
    say("")
    say(f"  socket            dia {cpl.socket_dia * MM:.3f} x {cpl.socket_depth * MM:.2f} deep, "
        f"wall {cpl.socket_wall * MM:.3f} mm")
    say(f"  radial gap        {cpl.radial_gap * MM:.3f} mm on the crests "
        f"(compound is specified to {cpl.max_radial_gap * MM:.2f})")
    say(f"  engagement        {cpl.engagement * MM:.3f} mm, reservoir {cpl.reservoir * MM:.2f} mm")
    say(f"  sizing case       {cpl.torque:.3f} N m, the SERVO's stall -- not the air. The")
    say(f"                    bearing takes all {abs(loads_sel.moment_at_bearing):.3f} N m of "
        f"bending, so this")
    say(f"                    joint sees torque and no moment, which is the only reason an")
    say(f"                    adhesive belongs in it at all.")
    say("")
    say(f"  adhesive shear    {cpl.bond_shear / 1e6:5.2f} MPa against "
        f"{cpl.adhesive_shear / 1e6:.0f} MPa   margin {cpl.bond_margin:.2f}x")
    say(f"  shaft wall        {cpl.shaft_torsion / 1e6:5.1f} MPa in torsion   "
        + ", ".join(f"{k} {m:.1f}x" for k, m in cpl.shaft_torsion_margin.items()))
    say(f"  cast keys         {cpl.key_pressure / 1e6:5.1f} MPa of bearing IF they carried it "
        f"all -- not counted")
    chk_cpl = hinge.check_coupling(cpl)
    say("")
    say(f"  VERDICT: {'buildable' if chk_cpl.ok else 'NOT BUILDABLE'}"
        + ("" if chk_cpl.ok else f" -- {len(chk_cpl.violations)} violation(s)"))
    for x in chk_cpl.violations:
        say(f"    FAIL  {x}")
    for n in chk_cpl.notes:
        say(f"    note  {n}")
    say("")
    say("  BUILD NOTE: anaerobics cure on contact with active metal ions. The spline is")
    say("  steel and cures fine; the 6061 shaft is PASSIVE and wants an activator/primer.")
    say("  Prime the shaft bore, not the spline. Without primer the joint will feel solid")
    say("  and be weak, which is the worst way for an adhesive to fail.")

    # ==================================================================================
    rule("THE TUBE AT THE HINGE STATION  --  four bores at one station")
    say("  check_hinge_stack() has emitted 'check the tube, not just the hinge' since the")
    say("  hinge stack went in, and nothing had. This is that check.")

    station = hinge.canard_hinge_station(r)
    cut = tube_section.CutStation(
        station=station,
        outer_diameter=r.diameter,
        wall_thickness=r.tubes[1].wall_thickness,
        hole_dia=sel.wall_bore_dia,
        hole_count=c.count,
        tube_name=r.tubes[1].name,
    )
    stab = aero.stability(r, worst_pt.cg, mach=worst_pt.mach)
    sloads = tube_section.canard_module_loads(
        r, ev.masses, f, stab, station,
        panel_normal_force=loads_sel.normal_force,
        panel_cp_radius=c.spanwise_cp_radius,
        seat_moment=loads_sel.moment_at_bearing,
        alpha_trim_rad=math.radians(worst.alpha_trim_deg),
        q=worst.dynamic_pressure,
    )

    say(f"\n  station           {station * MM:.2f} mm from the nose tip, "
        f"{(station - r.tube_station(1)) * MM:.2f} mm into the {cut.tube_name}")
    say(f"  section           dia {cut.outer_diameter * MM:.1f} x {cut.wall_thickness * MM:.1f} wall, "
        f"{cut.hole_count} x dia {cut.hole_dia * MM:.3f} bores")
    say(f"  area              {cut.gross_area * 1e6:.1f} mm^2 gross -> "
        f"{cut.net_area * 1e6:.1f} mm^2 net ({cut.area_loss_fraction * 100:.1f}% removed)")
    say(f"  ligament          {cut.ligament * MM:.1f} mm between adjacent bores")
    say("")
    say(f"  axial  {sloads.axial:7.1f} N    {sloads.axial_case}")
    say(f"         {'':7s}      = {sloads.mass_forward:.3f} kg forward of the station at "
        f"{sloads.specific_force_g:.2f} g, plus {sloads.drag_at_axial_case:.0f} N of drag")
    say(f"  bend   {sloads.bending:7.3f} N m  {sloads.bending_case}")
    say(f"  twist  {sloads.torsion:7.3f} N m  {sloads.torsion_case}")

    # The collar does not exist yet, so the wall carries the bearing alone. Price both.
    say("\n  The bearing hands its couple to whatever holds it, and 3.700 mm of it is held")
    say("  by a housing collar that has not been built. Both cases:")
    results = {}
    for label, seat_len in (("no collar (the vehicle today): the 2.3 mm wall alone",
                             cut.wall_thickness),
                            ("with the collar: the full 6.0 mm bearing",
                             sel.bearing_length)):
        res = tube_section.check_cut_station(
            cut, sloads, bearing_od=sel.bearing_od,
            seat_interference=hinge.BEARING_SEAT_INTERFERENCE, seat_length=seat_len)
        results[label] = res
        say(f"    {label}")
        say(f"      seat pressure {res.seat_pressure / 1e6:8.1f} MPa   "
            f"margin {res.margins['bearing seat crush']:.1f}x against "
            f"{tube_section.G10_BEARING / 1e6:.0f} MPa")

    res = results["no collar (the vehicle today): the 2.3 mm wall alone"]
    say(f"\n  net section       {res.peak_stress / 1e6:8.3f} MPa peak at the bore edge "
        f"(Kt = {res.kt_used:.1f})")
    say(f"    of which axial  {res.axial_stress / 1e6:8.3f} MPa, "
        f"bending {res.bending_stress / 1e6:.3f} MPa")
    say(f"  torsional shear   {res.shear_stress / 1e6:8.3f} MPa")
    say(f"  shell buckling    {res.buckling_allowable / 1e6:8.1f} MPa allowable against "
        f"{res.axial_stress / 1e6:.3f} MPa applied")
    say(f"  press-fit hoop    {res.press_fit_hoop / 1e6:8.2f} MPa from a "
        f"{hinge.BEARING_SEAT_INTERFERENCE * MM:.3f} mm interference")
    say("")
    for name, m in sorted(res.margins.items(), key=lambda kv: kv[1]):
        say(f"    {name:42s} {m:10.1f}x")
    say("")
    if res.ok:
        say("  VERDICT: the tube is fine, and it is not close.")
    else:
        say(f"  VERDICT: NOT ACCEPTABLE -- {len(res.violations)} violation(s)")
    for x in res.violations:
        say(f"    FAIL  {x}")
    for x in res.notes:
        say(f"    note  {x}")

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
    say(f"  the panel               CHANGES. The tang joint needs a "
        f"{joint.slot_thickness * MM:.1f} mm slot {joint.engagement * MM:.0f} mm into")
    say(f"                          the root, which is a {joint.engagement / joint.slot_thickness:.0f}:1 blind cut in a "
        f"{c.thickness * MM:.1f} mm plate and is not")
    say(f"                          machinable. The panel becomes a {joint.skin_thickness * MM:.1f}/"
        f"{joint.slot_thickness * MM:.1f}/{joint.skin_thickness * MM:.1f} bonded")
    say(f"                          laminate -- three STOCKED G10 sheets summing to "
        f"{c.thickness * MM:.1f} mm. The middle")
    say(f"                          sheet is the slot; the {joint.tang_thickness * MM:.1f} mm tang goes into it with a "
        f"{joint.bond_line * MM:.1f} mm")
    say("                          bond line each face. Same thickness, same planform,")
    say("                          same mass -- a manufacturing change, not a design one.")
    say("  the tube                UNCHANGED and not close: worst margin at the hinge")
    say("                          station is the bearing seat, and only because the")
    say("                          housing collar has not been built yet.")
    say("  still open              the housing collar. Blocked on bracket hardware, and")
    say(f"                          worth {results['with the collar: the full 6.0 mm bearing'].margins['bearing seat crush'] / results['no collar (the vehicle today): the 2.3 mm wall alone'].margins['bearing seat crush']:.1f}x on the bearing seat when it exists.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(_lines) + "\n")
    print(f"\n  wrote {OUT}")

    if chk_built.ok:
        raise SystemExit("the as-built layout PASSED, which means this check is not "
                         "checking anything -- fix the check before trusting it")
    if not chk_sel.ok:
        raise SystemExit("the selected layout does not pass its own check")
    if chk_swept.ok:
        raise SystemExit("the 1.8 x 14 x 30 tang PASSED, so the leading-edge check is not "
                         "checking anything -- it is 2.26 mm from exiting the panel")
    if chk_naive.ok:
        raise SystemExit("the dia 6 sleeve butted into a 3 mm panel PASSED the root joint "
                         "check, which means that check is not checking anything")
    if not chk_joint.ok:
        raise SystemExit("the selected root joint does not pass its own check")
    if not results["no collar (the vehicle today): the 2.3 mm wall alone"].ok:
        raise SystemExit("the tube does not pass its own section check at the hinge station")


if __name__ == "__main__":
    main()
