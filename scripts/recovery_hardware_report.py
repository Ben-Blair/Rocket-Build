"""Print the argument for the recovery bay's U-bolts, backing plates and charge wells.

    python scripts/recovery_hardware_report.py            # to the terminal
    python scripts/recovery_hardware_report.py --write    # and into out/recovery_hardware_report.txt

The U-bolt HOLES have been in the CAD since correction 50. The hardware standing proud of
them has never been sized by anything in this project, and three scripts say so in their own
docstrings. See `design/recovery_hardware.py` for the argument in full.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import recovery, recovery_hardware as rhw, seal
from design.configure import baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "recovery_hardware_report.txt"

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
    r = rhw.recovery_hardware_from_evaluation(ev)
    u, plate = r.anchor.ubolt, r.anchor.plate
    aft = seal.from_evaluation(ev)

    say("RECOVERY HARDWARE -- the U-bolt, its backing plate and the charge well")
    say("Model: design/recovery_hardware.py   Verdict carried by: scripts/baseline.py")
    say(f"One load, four anchors: {u.load:.1f} N, the main's infinite-mass opening shock, "
        f"which design/configure.py")
    say("already uses for the harness. One load, three parts, no chance of them disagreeing.")

    rule("THE HEADLINE -- a U-bolt used as an anchor is not loaded the way a U-bolt is rated")
    say("  design/seal.py has carried this sentence since it was written, and it read as a")
    say("  calculation:")
    say()
    say('      "An M5 U-bolt on a 25 mm leg spacing is the ordinary size for this load --')
    say('       1.3 kN through two 5 mm legs is 33 MPa of shear in stainless, which is')
    say('       nothing."')
    say()
    say("  Two errors, and they compound.")
    say()
    say("  1. THE LEGS ARE NOT IN SHEAR. The harness pulls along the bolt's axis, away from")
    say("     the plate. The legs are in TENSION and the nuts react it. Shear never enters.")
    say("  2. THE LEGS ARE NOT WHAT BREAKS. The CROWN is, in bending, at the two bends where")
    say("     it meets the legs -- which is exactly where a U-bolt used as an anchor is")
    say("     observed to straighten. A published U-bolt rating is for CLAMPING A PIPE, where")
    say("     the crown bears on the pipe and nothing bends. That rating describes a")
    say("     different structure.")
    say()
    say(f"  {'mode':34s} {'stress':>10s} {'margin':>8s}")
    say(f"  {'crown, arch model (DESIGN)':34s} {u.crown_stress / 1e6:9.0f} MPa "
        f"{u.crown_margin:7.2f}x")
    say(f"  {'crown, straight-beam idealisation':34s} {u.crown_stress_straight / 1e6:9.0f} MPa "
        f"{u.crown_margin_straight:7.2f}x")
    say(f"  {'legs, TENSION (not shear)':34s} {u.leg_tension / 1e6:9.0f} MPa "
        f"{u.leg_margin:7.1f}x")
    say()
    say(f"  Sized against the mode that governs: M{u.rod_diameter * MM:.0f}, not M5. The holes")
    say(f"  already placed in both bulkheads go from 5.5 to {u.hole_diameter * MM:.1f} mm.")
    say("  They are not drilled yet, so the finding costs nothing but the drill.")
    say()
    say("  THE STRAIGHT-BEAM ROW DOES NOT CLEAR 2.0x AND THAT IS LEFT VISIBLE. The arch model")
    say("  is the right one -- a curved crown carries most of the pull in direct tension along")
    say("  the rod, which is why U-bolts work at all -- and a straight beam is a different")
    say("  structure rather than a bound on this one. But this is the single most")
    say("  safety-critical joint in the vehicle, and what settles it is a destructive pull")
    say("  test on the actual bolt. That has not been done.")

    rule("THE SECOND FINDING -- the harness does not fit through the U-bolt")
    h = recovery.size_harness(ev.rocket.length, u.load)
    say(f"  recovery.size_harness() selects {h.webbing.name} -- "
        f"{r.webbing_width * MM:.1f} mm of webbing.")
    say(f"  An M{u.rod_diameter * MM:.0f} U-bolt on a {u.leg_spacing * MM:.0f} mm spacing "
        f"leaves a {u.clear_opening * MM:.1f} mm clear opening.")
    say()
    say("  Two sized parts of this vehicle, and nothing had ever put them next to each other.")
    say("  Opening the U up until the webbing passes needs 21 mm of clear opening, which")
    say("  drives the rod to M10 and about 310 g of stainless across four anchors -- more than")
    say("  the whole motor mount. That is not the answer.")
    say()
    say(f"  THE ANSWER IS THAT THE WEBBING WAS NEVER MEANT TO PASS THROUGH IT.")
    say(f"  recovery.HARNESS_HARDWARE_KG has priced {recovery.HARNESS_HARDWARE_KG * 1e3:.0f} g of")
    say(f"  'links and swivels' since it was written. REQUIREMENT, recorded rather than left as")
    say(f"  the thing everybody happens to do: the harness attaches through a QUICK LINK and")
    say(f"  the link goes through the U-bolt. A 6 mm link needs "
        f"{rhw.LINK_CLEARANCE * MM:.0f} mm of opening, not 21, and")
    say(f"  there is {(u.clear_opening - rhw.LINK_CLEARANCE) * MM:.1f} mm to spare.")

    rule("THE BACKING PLATE -- the part scripts/make_bulkhead_cad.py said was the one that mattered")
    say(f"  G-10 {plate.length * MM:.1f} x {plate.width * MM:.1f} x "
        f"{plate.thickness * MM:.1f} mm, {plate.mass * 1e3:.1f} g, one per anchor.")
    say(f"  Same stock the bulkheads are cut from -- one material, one offcut, one supplier.")
    say()
    say(f"  {'check':34s} {'stress':>10s} {'margin':>8s}")
    say(f"  {'its own bending':34s} {plate.stress / 1e6:9.1f} MPa {plate.margin:7.0f}x")
    say(f"  {'bearing under the nut washers':34s} {plate.bearing_stress / 1e6:9.1f} MPa "
        f"{plate.bearing_margin:7.0f}x")
    say()
    say("  ITS OWN BENDING ASKS FOR 1.2 mm. What sets it is that it must not dish under the")
    say("  nuts, because if it dishes the footprint the log term assumes is not there. Same")
    say("  shape of result as design/access_bulkhead.py's two plates: the model gives the")
    say("  floor, practice gives the design point.")
    say()
    say("  WHAT IT IS FOR is seal.Bulkhead.point_load_stress(), which goes as")
    say("  log(disc radius / footprint radius). seal.py passed a hardcoded 6.0 mm there -- a")
    say("  bare nut face -- and said in a comment that a real plate would replace it:")
    say()
    say(f"      footprint R 6.00 mm (bare nut)   ->  {r.anchor.bare_stress / 1e6:5.1f} MPa, "
        f"{r.anchor.bare_margin:.2f}x")
    say(f"      footprint R {plate.footprint_radius * MM:5.2f} mm (this plate)  ->  "
        f"{r.anchor.backed_stress / 1e6:5.1f} MPa, {r.anchor.backed_margin:.2f}x")
    say()
    say("  That is a RESULT of the part existing, not a retune. Nothing was softened to get")
    say("  it, and seal.py's default is unchanged, so every previously reported number still")
    say("  reproduces -- SealResult.shock_footprint_radius is a field a caller passes.")
    say()
    for a in r.anchors:
        say(f"    {a.name:48s} {a.bare_margin:5.2f}x -> {a.backed_margin:5.2f}x")

    rule("THE THIRD FINDING -- the conduit hole is in the worst place for a backing plate")
    say("  seal.hole_layout() puts the internal bulkhead's conduit hole at 45 degrees, 'so it")
    say("  is equidistant from both U-bolt legs'. That was right for as long as the only things")
    say("  on that face were holes.")
    say()
    say(f"  A backing plate spans the legs, so it is {plate.length * MM:.0f} mm long across "
        f"them and {plate.width * MM:.1f} mm wide the")
    say("  other way. 45 degrees is precisely where it reaches furthest. Moved to 0 degrees --")
    say("  PERPENDICULAR to the legs, where the plate is narrow -- the hole clears instead of")
    say("  landing underneath. Same radius, same stress field, same ligament to the legs: the")
    say("  placement loses nothing it was chosen for.")

    rule("THE CHARGE WELLS")
    say(f"  {'well':16s} {'charge':>9s} {'bore x depth':>16s} {'holds':>9s} {'used':>6s} "
        f"{'at R':>7s} {'mass':>7s}")
    for w in r.wells:
        say(f"  {w.name:16s} {w.charge * 1e3:8.4f} g "
            f"{'dia %.0f x %.1f' % (w.bore * MM, w.depth * MM):>16s} "
            f"{w.internal_volume * 1e6:7.2f} cm3 {w.utilisation * 100:5.0f}% "
            f"{w.station_radius * MM:6.1f} {w.mass * 1e3:6.2f} g")
    say()
    say(f"  Both sit over their own charge's LEAD HOLE -- the main over a feed-through, the")
    say(f"  drogue over the conduit hole -- so neither needs a new hole through a pressure")
    say(f"  boundary. Bore is picked as the smallest whose well stands no more than")
    say(f"  {rhw.WELL_MAX_PROUD * MM:.0f} mm proud: a deep narrow well is a worse part than a "
        f"short fat one -- harder to fill,")
    say(f"  harder to see into, and a lever the canopy can catch on.")
    say()
    say(f"  THE DROGUE CHARGE IS PRINTED HERE FOR THE FIRST TIME. "
        f"seal.internal_bulkhead_from_evaluation()")
    say(f"  has computed {r.wells[1].charge * 1e3:.4f} g since it was written and no report in "
        f"this project has ever")
    say(f"  shown it; docs/04 lists only the main's.")

    rule("WHAT IT COSTS -- and the mass line that did not exist")
    say(f"  {'one anchor (U-bolt + nuts + plate)':44s} {r.anchor.mass * 1e3:7.2f} g")
    say(f"  {'x %d anchors' % r.n_anchors:44s} {r.n_anchors * r.anchor.mass * 1e3:7.2f} g")
    say(f"  {'2 wells + terminal blocks + charges':44s} "
        f"{(sum(w.mass for w in r.wells) + sum(w.charge for w in r.wells)) * 1e3:7.2f} g")
    say(f"  {'TOTAL':44s} {r.mass * 1e3:7.2f} g")
    say()
    say("  design/mass.py had NO LINE for any of the anchors. recovery.py's own")
    say('  SoftGood("2 x U-bolt", 0.030, ...) entries are dead code -- measured_volume')
    say("  overrides the mass and nothing sums Compartment.hardware masses -- and docs/04")
    say("  independently lists 120 g for four. Three numbers for one part, none reconciled,")
    say("  and the real one is 196 g because the U-bolt is M8.")
    say()
    say(f"  mass.DEFAULT_RECOVERY_BUDGET['harness_anchors'] = 0.196 kg carries it now.")
    say(f"  Sixth allowance-shaped hole found by drawing the part -- and the first that was")
    say(f"  not even an allowance. It was nothing at all.")
    say()
    say(f"  PACKING. One anchor displaces {r.envelope_volume * 1e6:.2f} cm3 against the 3.00 cm3")
    say(f"  recovery.py estimated -- low by {r.envelope_volume / 3.0e-6:.1f}x, because the "
        f"U-bolt it described was M5.")
    say(f"  And the wells are rigid too: recovery.py's default_soft_goods() said in as many")
    say(f"  words that charge wells 'do not consume packing volume'. A "
        f"{r.wells[0].bore * MM:.0f} mm tube standing")
    say(f"  {r.wells[0].depth * MM:.1f} mm off the face is directly in the canopy's way.")
    say(f"  Recovery bay margin: +8.35 mm -> {ev.packing.margin * MM:+.2f} mm. Still fits, and")
    say(f"  nothing was resized to keep it there.")

    rule("VERDICT")
    chk = rhw.check_recovery_hardware(r)
    say(f"  recovery hardware   {'OK' if chk.ok else 'VIOLATIONS'}")
    for v in chk.violations:
        say(f"    VIOLATION  {v}")
    for n in chk.notes:
        say(f"    note  {n}")

    rule("WHAT IS STILL OPEN")
    say("  * THE CROWN MODEL. The straight-beam idealisation gives "
        f"{u.crown_margin_straight:.2f}x, under 2.0x. A")
    say("    destructive pull test on the bought bolt settles it and has not been done.")
    say("  * THE DROGUE HARNESS'S OWN OPENING SHOCK has never been computed by anything here.")
    say("    All four anchors are sized against the MAIN's, which is conservative for the two")
    say("    on the drogue and buys one part number in four places -- but the number does not")
    say("    exist.")
    say("  * BP_BULK_DENSITY is 900 kg/m3 against a real 900-1100 band, and the well is sized")
    say("    on the low end deliberately: a well too big is a nuisance, a well too small")
    say("    cannot hold the charge at all.")
    say("  * No e-match or terminal block part number is chosen.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
