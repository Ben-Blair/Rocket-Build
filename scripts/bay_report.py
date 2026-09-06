"""The printed canard bay: geometry, margins, and the two checks drawing it forced.

    python scripts/bay_report.py

Writes out/bay_report.txt as well as printing. Nothing here is typed twice -- every
station comes from design/hinge.py, design/packaging.py and design/configure.py, and the
seat model is design/bay.py.

Read the SEAT section first. It is the reason this part exists and it is the section that
disagrees with what the rest of the project has been saying about it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import bay, control, hinge
from design.configure import baseline, evaluate
from design.materials import (
    BAY_MATERIAL, G10_BEARING, G10_MODULUS, PRINT_MATERIALS,
)
from design.packaging import SERVOS, SERVO_GEOMETRY

MM = 1000.0
DEFLECTION_LIMIT_DEG = 8.0

_lines: list[str] = []


def say(s: str = "") -> None:
    print(s)
    _lines.append(s)


def rule(title: str) -> None:
    say("")
    say("=" * 92)
    say(title)
    say("=" * 92)


def main() -> None:
    p = baseline()
    ev = evaluate(p, deflection_deg=DEFLECTION_LIMIT_DEG)
    r, f = ev.rocket, ev.flight
    c = r.canards
    geom = SERVO_GEOMETRY[p.servo]
    servo = SERVOS[p.servo]

    worst_pt, worst = max(
        ((pt, control.pitch_authority(r, pt, pt.mass, DEFLECTION_LIMIT_DEG))
         for pt in f.points if pt.q > 100),
        key=lambda pair: abs(pair[1].hinge_moment_per_panel))
    load_r = r.diameter / 2.0 + hinge.spanwise_centroid(
        c.root_chord, c.tip_chord, c.semispan)
    s = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, geom)
    loads = hinge.hinge_loads(s, worst.hinge_moment_per_panel, c.mean_chord, load_r,
                              servo.stall_torque, geom.spline_teeth)

    station = hinge.canard_hinge_station(r) - r.tube_station(1)
    b = bay.build_bay(s, geom, station)
    chk = bay.check_bay(b, loads.moment_at_bearing, loads.normal_force, servo.stall_torque)

    # ==================================================================================
    rule("THE PRINTED CANARD BAY")
    say(f"  one printed part, {b.material.name}, {b.mass * 1000:.1f} g, "
        f"{b.length * MM:.1f} mm long")
    say(f"  it holds  4 x {servo.name}")
    say(f"  it carries the inboard {s.housing_collar_height * MM:.3f} mm of each bearing, "
        f"which is the")
    say(f"            half of the seat the {s.wall_thickness * MM:.1f} mm airframe wall "
        f"cannot reach")

    say("\n  radial stack at a hinge, outboard to inboard (mm from the rocket axis)")
    for label, rad in (
            ("tube OD / bearing outboard end", s.tube_outer_radius),
            ("tube ID", s.tube_inner_radius),
            ("bay shell OD  (epoxy film outboard of it)", b.shell_outer_radius),
            ("bay shell bore", b.shell_inner_radius),
            ("collar inboard end / bearing inboard end", s.bearing_inboard),
            ("servo output face", s.servo_output_face),
            ("servo tray, flange face (servo stops here)", b.tray_flange_face),
            ("servo tray, back face", b.tray_back_face),
            ("servo case, inboard end", s.servo_output_face - s.servo_depth),
    ):
        say(f"    {label:44s} R {rad * MM:8.3f}")
    say(f"    {'bond line (epoxy)':44s}   {bay.BOND_GAP * MM:8.3f} radial")
    say(f"    {'collar stands proud of the shell bore by':44s}   {b.collar_reach * MM:8.3f}")
    say(f"    {'tray webs span':44s}   {b.tray_standoff * MM:8.3f}")

    say("\n  axial extent (mm from the module tube's forward face)")
    for label, z in (
            ("bay forward face", b.forward_face),
            ("servo lug envelope, forward tip", b.servo_forward),
            ("servo lug screws, forward row", b.screw_stations[0]),
            ("HINGE AXIS", b.hinge_station),
            ("servo lug screws, aft row", b.screw_stations[1]),
            ("servo lug envelope, aft tip", b.servo_aft),
            ("bay aft face", b.aft_face),
    ):
        say(f"    {label:44s} Z {z * MM:8.3f}")

    # ==================================================================================
    rule("THE SEAT  --  and why 3.2x -> 21.3x was never the right pair of numbers")
    say("  The bearing seat is made of TWO materials: 2.300 mm of G10 wall outboard and")
    say(f"  {s.housing_collar_height * MM:.3f} mm of printed collar inboard. Every document in this "
        f"project has priced")
    say("  the collar by putting the whole 6.000 mm into p = 6M/(d L^2) + N/(d L), which is")
    say("  the formula for ONE material. A rigid pin shares its couple out by STIFFNESS.")
    say("  Print the collar in something ten times softer than the tube and the collar")
    say("  moves aside: the load walks back into the G10 and the effective seat shortens.")
    say("")
    say(f"  moment at the seat centre   {loads.moment_at_bearing:.4f} N m")
    say(f"  normal force                {loads.normal_force:.3f} N")
    say(f"  bearing                     dia {s.bearing_od * MM:.1f} x {s.bearing_length * MM:.1f} long")
    say("")
    say(f"    {'collar material':12s} {'E':>7s} {'p collar':>10s} {'p wall':>9s} "
        f"{'collar':>8s} {'wall':>8s} {'L eff':>7s}")
    say(f"    {'':12s} {'GPa':>7s} {'MPa':>10s} {'MPa':>9s} "
        f"{'margin':>8s} {'margin':>8s} {'mm':>7s}")
    rows = [("none", 0.0, None)]
    rows += [(k, m.modulus, m) for k, m in PRINT_MATERIALS.items()]
    rows += [("G10 (fiction)", G10_MODULUS, None)]
    for name, e, mat in rows:
        prof = bay.seat_pressure(s, loads.moment_at_bearing, loads.normal_force, e)
        mc = (mat.compressive / prof.peak_collar) if mat and prof.peak_collar > 0 else None
        mw = G10_BEARING / prof.peak_wall
        flag = "  <-- selected" if mat and mat.name == BAY_MATERIAL else ""
        say(f"    {name:12s} {e / 1e9:7.1f} {prof.peak_collar / 1e6:10.2f} "
            f"{prof.peak_wall / 1e6:9.2f} "
            f"{(f'{mc:7.1f}x' if mc else '      --'):>8s} {mw:7.1f}x "
            f"{prof.effective_length * MM:7.2f}{flag}")
    say("")
    say(f"  So the collar IS worth building -- {G10_BEARING / chk.seat_no_collar.peak_wall:.1f}x to "
        f"{G10_BEARING / chk.seat.peak_wall:.1f}x on the wall is the")
    say(f"  single largest margin improvement anywhere in this hinge. But it is worth")
    say(f"  {G10_BEARING / chk.seat.peak_wall:.1f}x and not 21.4x, and the printed collar itself "
        f"runs at "
        f"{chk.margins['bearing seat, printed collar']:.1f}x,")
    say("  which is a number nobody had computed because nobody had asked what the collar")
    say("  was made of. Correct the claim wherever it appears; do not drop the collar.")

    # ==================================================================================
    rule("THE COUPLING  --  a check that should have been run in August")
    cp = chk.coupling
    say(f"  servo output face          R {s.servo_output_face * MM:.3f}")
    say(f"  bearing inboard end        R {s.bearing_inboard * MM:.3f}")
    say(f"  -> space for a coupling      {cp.gap * MM:.3f} mm")
    say(f"  outboard of that the hole is the bearing bore, dia {cp.through_bore * MM:.1f}")
    say("")
    say(f"  a bought 15T dia 4 servo horn hub is about dia {cp.horn_hub_dia * MM:.1f} x "
        f"{cp.horn_hub_height * MM:.1f} tall")
    say(f"  -> {'FITS' if cp.fits else 'DOES NOT FIT'}")
    if not cp.fits:
        say("")
        say("  docs/01 correction 16 and docs/05 both instruct the builder to buy a horn and")
        say("  skip the broaching. That instruction is not buildable. Nothing is")
        say("  MIS-ANALYSED by it -- design/hinge.py never adopted the horn and still models")
        say(f"  and checks the broached socket (dia {s.spline_dia * MM + 0.4:.1f} x "
            f"{s.spline_engagement * MM:.1f} engaged, "
            f"{loads.spline_pressure / 1e6:.1f} MPa) -- but a builder")
        say("  following the documents would discover it with four servos in hand.")

    # ==================================================================================
    rule("CLEARANCES  --  every place the bay comes near something else")
    say("  An assembled render shows none of this: the tube hides the bay and the bay")
    say("  hides the servo. These are the check.")
    say("")
    for what, gap, where in bay.clearances(b):
        flag = "  <-- INTERFERENCE" if gap < -1e-9 and "NEGATIVE is correct" not in where \
            and "zero is correct" not in where else ""
        say(f"    {what:44s} {gap * MM:+8.3f} mm   {where}{flag}")

    rule("MARGINS")
    for name, m in sorted(chk.margins.items(), key=lambda kv: kv[1]):
        say(f"    {name:44s} {m:8.1f}x")
    say("")
    say(f"  mass          {b.mass * 1000:6.1f} g   "
        f"(shell {b.shell_volume * b.density * 1000:.1f}, trays "
        f"{b.tray_volume * b.density * 1000:.1f}, collars "
        f"{b.collar_volume * b.density * 1000:.1f})")
    say(f"  bond area     {b.bond_area * 1e6:6.1f} mm^2 of shell against the tube ID")

    say("")
    if chk.ok:
        say("  VERDICT on the BAY: buildable, every margin met.")
    else:
        say(f"  VERDICT on the BAY: NOT BUILDABLE -- {len(chk.violations)} violation(s)")
    for x in chk.violations:
        say(f"    FAIL  {x}")
    for n in chk.notes:
        say(f"    note  {n}")
    say("")
    say(f"  VERDICT on the COUPLING, which is a separate part and a separate problem: "
        f"{'ok' if chk.coupling.fits else 'UNRESOLVED'}")
    say("  No bay geometry fixes it. See the section above.")

    # ==================================================================================
    rule("HOW IT GETS PRINTED AND FITTED")
    say("  1. Print ROCKET AXIS VERTICAL. The layers then lie normal to the axis, and the")
    say("     panel's normal force -- which is circumferential -- presses on the collar")
    say("     bore IN the layer plane rather than across it. Any other orientation makes")
    say("     interlayer strength the governing property, at roughly half the number.")
    say(f"  2. Collar bores print at dia {b.collar_printed_bore * MM:.1f}, undersize on purpose. "
        f"Do not try to")
    say("     print them to size; FDM holes come out undersize and rough anyway.")
    say("  3. Bond the bay into the tube. Abrade both faces. The weak side of this joint is")
    say("     the PRINTED surface, not the G10.")
    say(f"  4. Only then ream dia {s.wall_bore_dia * MM:.3f} H7 through the wall AND the collar in "
        f"ONE pass.")
    say("     Concentricity becomes a property of the operation instead of a tolerance held")
    say("     across two parts made by different processes. A pinched bearing is a")
    say("     mechanism failure and no margin in this project protects against one.")
    say(f"  5. Melt {8} M2 heat-set inserts into the clamp bosses -- dia "
        f"{bay.INSERT_DIA * MM:.1f} x {bay.INSERT_DEPTH * MM:.1f} deep, at Y +/-"
        f"{bay.RETAINER_SCREW_ACROSS * MM:.1f} on each of the two rows per servo.")
    say(f"  6. Servos drop in from the axis and stop against the tray at R "
        f"{b.tray_flange_face * MM:.3f}.")
    say(f"     A printed bar across each end of the flange clamps it, two M2 x 6 per bar.")
    say(f"     Their own lug holes are NOT used -- there is only {b.screw_ligament * MM:.2f} mm of")
    say(f"     plastic between a lug screw and the servo window, which is a perimeter and a")
    say(f"     half. Clamping moves the fastener to where there is 5 mm of material, and it")
    say(f"     is also the only way to change a servo after the bay is bonded in for good.")
    say(f"  7. The servo's two dia 2.0 flange holes stay empty. Their function is not")
    say(f"     labelled on the KST drawing (see design/packaging.py), so nothing here")
    say(f"     depends on a guess about what they are for.")

    say("")
    say("  STILL NOT THIS PART: the aft gas seal. That is a bulkhead between the canard")
    say("  module and the recovery bay, not a feature of a servo tray -- it has to seal a")
    say("  bore this part deliberately leaves open for wiring. Sized separately.")

    out = Path(__file__).resolve().parents[1] / "out" / "bay_report.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(_lines) + "\n")
    say(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
