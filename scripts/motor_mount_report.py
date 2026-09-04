"""Print the argument for the motor mount, and check it.

    python scripts/motor_mount_report.py            # to the terminal
    python scripts/motor_mount_report.py --write    # and into out/motor_mount_report.txt

Everything here is derived from `design/configure.py`. `design/mass.py` has charged 250 g
for this assembly since that dict was written, with no ring diameter, ring count, ring
station, mount tube or retainer behind it anywhere in the project -- the fifth allowance
here to be priced without existing. See `design/motor_mount.py` for the argument in full.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import joints, motor_mount as mmount, seal
from design.configure import baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "motor_mount_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def rule(title: str) -> None:
    say()
    say("=" * 92)
    say(title)
    say("=" * 92)


def main() -> None:
    ev = evaluate(baseline())
    r = mmount.motor_mount_from_evaluation(ev)
    motor = ev.params.motor
    booster = next(t for t in ev.rocket.tubes if t.name == "booster")

    say("MOTOR MOUNT -- the last unsized structure in the vehicle")
    say("Model: design/motor_mount.py   Verdict carried by: scripts/baseline.py")
    say(f"Motor: {motor.name if hasattr(motor, 'name') else 'Cesaroni Pro54 J449'}  "
        f"dia {motor.diameter * MM:.1f} x {motor.length * MM:.1f} mm, "
        f"{motor.total_mass:.3f} kg loaded / {motor.dry_mass:.3f} kg dry")

    rule("WHY THIS WAS NEVER SIZED, AND WHAT IT WAS HIDING")
    say("  design/mass.py:70 carries motor_mount_centering_rings = 0.250 kg and :229 puts it")
    say("  at the motor's own mid-station. That is the whole of the design. scripts/make_ork.py")
    say("  needed SOMETHING to hand OpenRocket and typed 54 mm ID / 1.5 mm wall / 331 mm long")
    say("  into itself; docs/04 says 416 mm for the same part. Neither number is imported by")
    say("  anything in design/, and the two have never been reconciled.")
    say()
    say("  An allowance nobody turned into a part, for the fifth time -- after correction 20's")
    say("  bulkhead, correction 33's harness, correction 38's access plates and correction 41's")
    say("  sled. The pattern is now reliable enough to be a search strategy.")

    rule("THE FIRST FINDING -- the frozen 12 mm fin tab and a 54 mm mount tube cannot coexist")
    legacy = 0.012
    say(f"  scripts/make_cad_profiles.py's TAB_DEPTH = 12.00 mm is measured inward from the")
    say(f"  booster tube's OUTER radius, so the tab tip sits at "
        f"R {(r.booster_outer_diameter / 2.0 - legacy) * MM:.2f} mm.")
    say()
    say(f"    booster OD                          R {r.booster_outer_diameter / 2.0 * MM:8.2f} mm")
    say(f"    booster ID                          R {r.airframe_inner_diameter / 2.0 * MM:8.2f} mm")
    say(f"    tab tip at the frozen 12.00 mm      R {(r.booster_outer_diameter / 2.0 - legacy) * MM:8.2f} mm")
    say(f"    mount tube OD (this file)           R {r.tube.outer_diameter / 2.0 * MM:8.2f} mm"
        f"   <- the tab was 0.85 mm INSIDE it")
    say(f"    mount tube ID                       R {r.tube.inner_diameter / 2.0 * MM:8.2f} mm")
    say(f"    bare motor case                     R {r.motor_diameter / 2.0 * MM:8.2f} mm"
        f"   <- 0.70 mm clear: what 12.00 was really drawn against")
    say()
    say("  So the 12 mm tab describes a fin bonded to the BARE MOTOR CASE, while design/flutter.py")
    say("  and scripts/baseline.py both quote the aft-fin flutter margin for a tab 'bonded")
    say("  through the wall to the MOTOR MOUNT'. Four AftFin bodies already occupy R 27.70 in")
    say("  the Fusion document. This was never going to survive an interference check; it")
    say("  survived because there was nothing yet to check it against.")
    say()
    say(f"  DERIVED, NOT CHOSEN: tab depth = booster OR - mount tube OR = "
        f"{r.fin_tab_depth * MM:.2f} mm.")
    say(f"  The tab then stands {(r.fin_tab_depth - (r.booster_outer_diameter - r.airframe_inner_diameter) / 2.0) * MM:.2f} mm "
        f"proud of the airframe bore and lands tangent on the mount tube,")
    say(f"  giving {r.fin_tab_bond_area * 1e6:.0f} mm2 of tab-to-tube bond across "
        f"{r.n_fins} fins with no fillet credited.")

    rule("THE SECOND FINDING -- the forward bulkhead and the thrust face are the same part")
    say(f"  booster tube                        {booster.length * MM:8.2f} mm")
    say(f"  motor, aft-flush                    {motor.length * MM:8.2f} mm")
    say(f"  forward margin                      {r.motor_forward_station * MM:8.2f} mm")
    say(f"    less coupler engagement          -{r.coupler_engagement * MM:8.2f} mm")
    say(f"    less joints.BULKHEAD_ALLOWANCE   -{joints.BULKHEAD_ALLOWANCE * MM:8.2f} mm")
    say(f"    = what the BUDGET leaves          {(r.motor_forward_station - r.coupler_engagement - joints.BULKHEAD_ALLOWANCE) * MM:8.2f} mm")
    say()
    say("  There is no room for a separate thrust plate and there does not need to be. One")
    say("  disc closes the drogue compartment on its forward face, anchors the drogue harness's")
    say("  aft U-bolt there, and presents its aft face to the motor. That is exactly why")
    say("  design/seal.py handed this part to the motor mount rather than sizing it as a third")
    say("  bulkhead -- a reason seal.py stated without knowing.")
    say()
    say(f"  The disc as sized is {r.forward_bulkhead.thickness * MM:.1f} mm, not the "
        f"{joints.BULKHEAD_ALLOWANCE * MM:.1f} mm the allowance charges, so the real clear")
    say(f"  gap is {r.forward_gap * MM:.2f} mm. That is not slack to spend.")

    rule("THE THIRD FINDING -- that gap is a closed volume in front of a live ejection charge")
    say("  The Cesaroni Pro54 ships with an ejection charge in its forward closure. This")
    say("  vehicle deploys on an independent altimeter, and nothing in this project has ever")
    say("  said what happens to the motor's own charge.")
    say()
    say(f"  volume bounded by mount tube bore, forward closure and this disc:  "
        f"{r.forward_gap_volume * 1e6:.2f} cm3")
    say(f"  disc capacity (seal.py's own expression):                          "
        f"{r.bulkhead_capacity / 1e6:.2f} MPa")
    say()
    say("    charge      pressure      over capacity")
    for g in (0.0008, 0.0010, 0.0012, 0.0014, 0.0016):
        p = seal.ejection_pressure(g, r.forward_gap_volume)
        say(f"    {g * 1e3:4.1f} g     {p / 1e6:6.2f} MPa     {p / r.bulkhead_capacity:5.2f}x")
    say()
    say("  It fails at every plausible charge mass, so the conclusion does not turn on the")
    say("  assumed figure -- which is just as well, because Cesaroni does not publish one.")
    say(f"  DESIGN ANSWER: a PLUGGED forward closure (a purchase, not a modification), recorded")
    say(f"  as motor_mount.FORWARD_CLOSURE_PLUGGED = {mmount.FORWARD_CLOSURE_PLUGGED}. Venting the gap is the")
    say("  alternative and it is worse: a hole through a pressure boundary to solve what a")
    say("  different part number solves for nothing.")

    rule("THE PART -- stations local to the booster tube's forward face, positive aft")
    say(f"  {'forward bulkhead / thrust face':34s} dia {r.forward_bulkhead.bore_diameter * MM:6.2f} x "
        f"{r.forward_bulkhead.thickness * MM:4.2f}   "
        f"{r.bulkhead_station * MM:7.2f} .. {(r.bulkhead_station + r.forward_bulkhead.thickness) * MM:7.2f}   "
        f"{r.forward_bulkhead.mass * 1e3:6.1f} g")
    say(f"  {'mount tube':34s} dia {r.tube.outer_diameter * MM:6.2f} / "
        f"{r.tube.inner_diameter * MM:.2f}   "
        f"{r.tube.forward_station * MM:7.2f} .. {r.tube.aft_station * MM:7.2f}   "
        f"{r.tube.mass * 1e3:6.1f} g")
    for ring in r.rings:
        slot = (f" [{ring.slots} x {ring.slot_width * MM:.1f} x {ring.slot_depth * MM:.2f} slots]"
                if ring.slots else "")
        say(f"  {ring.name:34s} dia {ring.outer_diameter * MM:6.2f} / "
            f"{ring.bore * MM:.2f} x {ring.thickness * MM:.2f}   "
            f"{ring.station * MM:7.2f} .. {ring.aft_station * MM:7.2f}   {ring.mass * 1e3:6.1f} g{slot}")
    say(f"  {'retainer (bought, Aeropack class)':34s} bond {r.retainer.bond_length * MM:.0f} mm on the "
        f"tube OD           {(r.tube.aft_station - r.retainer.bond_length) * MM:7.2f} .. "
        f"{r.tube.aft_station * MM:7.2f}   {r.retainer_mass * 1e3:6.1f} g")
    say(f"  {'motor, aft-flush':34s} dia {r.motor_diameter * MM:6.2f} x {r.motor_length * MM:.2f}  "
        f"{r.motor_forward_station * MM:8.2f} .. {(r.motor_forward_station + r.motor_length) * MM:7.2f}")
    say(f"  {'aft fin tab band':34s} depth {r.fin_tab_depth * MM:.2f} mm            "
        f"{r.fin_tab_forward * MM:7.2f} .. {r.fin_tab_aft * MM:7.2f}")
    say()
    say(f"  ASSEMBLY {r.mass * 1e3:.1f} g against the {r.allowance * 1e3:.0f} g "
        f"design/mass.py has charged -- {(r.allowance - r.mass) * 1e3:+.1f} g.")
    say(f"  Mount tube length {r.tube.length * MM:.2f} mm settles make_ork.py's 331 against")
    say(f"  docs/04's 416: neither, and 416 was the booster's own length copied by mistake.")

    rule("WHAT CARRIES WHAT -- and the headline is that the rings do not carry thrust")
    say(f"  {'peak thrust':38s} {r.peak_thrust:8.1f} N")
    say(f"  {'thrust into the forward bulkhead':38s} {r.thrust_plate_stress / 1e6:8.2f} MPa   "
        f"{r.thrust_plate_margin:6.0f}x   annular land "
        f"{(r.forward_bulkhead.radius - r.thrust_face_radius) * MM:.2f} mm")
    say(f"  {'drogue stuck-joint pressure':38s} {r.bulkhead_pressure_stress / 1e6:8.2f} MPa   "
        f"{r.bulkhead_pressure_margin:6.1f}x   at {r.drogue_stuck_pressure / 1e3:.0f} kPa")
    say(f"  {'drogue U-bolt, bare 6 mm footprint':38s} {r.bulkhead_shock_stress / 1e6:8.2f} MPa   "
        f"{r.bulkhead_shock_margin:6.1f}x   at {r.drogue_shock:.0f} N")
    say(f"  {'ring glue lines, REDUNDANT path':38s} "
        f"{max(r.ring_inner_bond_stress, r.ring_outer_bond_stress) / 1e6:8.2f} MPa   "
        f"{r.ring_bond_margin:6.0f}x   {r.ring_thrust_share:.0f} N each")
    say(f"  {'retainer base bond':38s} {r.retainer_bond_stress / 1e6:8.2f} MPa   "
        f"{r.retainer_bond_margin:6.0f}x   at {r.retention_load:.0f} N")
    say(f"  {'mount tube, full thrust (redundant)':38s} {r.tube_thrust_stress / 1e6:8.2f} MPa   "
        f"{r.tube_thrust_margin:6.0f}x   buckling {r.tube_buckling_margin:.0f}x")
    say()
    say("  THRUST ENTERS THE AIRFRAME AT THE FORWARD BULKHEAD, not through the rings. The")
    say("  motor's forward closure bears on that disc through the mount tube's bore, and the")
    say("  load travels forward into the vehicle it is pushing. The rings align the motor, tie")
    say("  the fin tabs in, and carry the motor's mass laterally. They are checked against the")
    say("  full thrust anyway, as the redundant path -- a load path with one member is not one.")
    say()
    say(f"  Neither the tube wall nor the ring thickness is set by stress:")
    say(f"    mount tube wall   {r.tube.wall * MM:.2f} mm -- {r.tube_wall_governed_by}")
    say(f"    ring thickness    {r.rings[0].thickness * MM:.2f} mm -- {r.ring_thickness_governed_by}")
    say("  Same shape of result as design/access_bulkhead.py's two plates and design/venting.py's")
    say("  port sizing: the model gives the floor, practice gives the design point.")

    rule("THE HOLES IN THE FORWARD BULKHEAD")
    for h in mmount.hole_layout(r):
        edge = r.forward_bulkhead.radius - h.radius_in_plate - h.diameter / 2.0
        say(f"  {h.name:28s} x {h.x * MM:+7.2f}  y {h.y * MM:+7.2f}  dia {h.diameter * MM:4.1f}  "
            f"edge {edge * MM:5.2f} mm")
    say()
    say("  Positions come from design/motor_mount.hole_layout(), reusing seal.Hole, so the CAD")
    say("  script types nothing -- the same rule seal.py and access_bulkhead.py already follow.")

    rule("VERDICT")
    chk = mmount.check_motor_mount(r)
    say(f"  motor mount    {'OK' if chk.ok else 'VIOLATIONS'}")
    for v in chk.violations:
        say(f"    VIOLATION  {v}")
    for n in chk.notes:
        say(f"    note  {n}")

    rule("WHAT IS STILL OPEN")
    say("  * THE FIN ROOT MOMENT. The tab-to-mount-tube bond is checked here for AREA and for")
    say("    CLEARANCE. The moment it carries has never been computed by anything in this")
    say("    project, and design/flutter.py says the same about its own ideal-rigid-root")
    say("    assumption. Swinging the finished fin is what settles it.")
    say("  * THE MOUNT TUBE'S MATERIAL. Every margin above uses G-10 SHEET properties for a")
    say("    filament-wound tube, because design/materials.py has nothing else. The margins")
    say("    that matter are all well clear, which is the only reason that is tolerable.")
    say("  * THE MOTOR'S EJECTION CHARGE MASS. Assumed, not obtained. The conclusion does not")
    say("    turn on it -- see the table above -- but the number should be replaced.")
    say("  * MOUNT_TUBE_WALL_OPTIONS is the band the common 54 mm offerings fall in, not a")
    say("    quoted catalogue. Confirm the vendor's own list before ordering.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
