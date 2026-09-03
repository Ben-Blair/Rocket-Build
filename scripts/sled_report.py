"""Print the argument for the nav bay sled, and check it.

    python scripts/sled_report.py            # to the terminal
    python scripts/sled_report.py --write    # and into out/sled_report.txt

`design/avionics.py` answers "do the boards fit" with an areal model and says yes by
+4.6 mm. This report puts the same stack through a DISCRETE placement -- real rectangles on
two real faces -- and shows both answers side by side, because a report that can only show
the answer it arrived at is not showing an argument. See `design/sled.py` for the argument
in full, and read its header before acting on the negative result.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import avionics, joints, mass, sled
from design.configure import baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "sled_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def rule(title: str) -> None:
    say()
    say("=" * 92)
    say(title)
    say("=" * 92)


def plan(g: sled.SledGeometry, cols: int = 84) -> list[str]:
    """An ASCII plan of both faces, to scale. The point of drawing it is that a table of
    x/y coordinates hides overlaps and an occupancy grid does not."""
    out: list[str] = []
    if not g.placements:
        return ["    (no placement to draw)"]
    rows = 11
    scale_x = cols / (g.plate_length * MM)
    scale_y = rows / (g.plate_width * MM)
    for face in (0, 1):
        grid = [[" "] * cols for _ in range(rows)]
        here = [p for p in g.placements if p.face == face]
        for k, p in enumerate(sorted(here, key=lambda q: (q.x, q.y))):
            ch = "#@*+%o"[k % 6]
            x0 = int(p.x * MM * scale_x)
            x1 = max(int((p.x + p.length) * MM * scale_x), x0 + 1)
            y0 = int(p.y * MM * scale_y)
            y1 = max(int((p.y + p.width) * MM * scale_y), y0 + 1)
            for yy in range(min(y0, rows - 1), min(y1, rows)):
                for xx in range(min(x0, cols - 1), min(x1, cols)):
                    grid[yy][xx] = ch
        out.append(f"    face {face}   fwd |{'-' * cols}| aft")
        for row in grid:
            out.append("            " + "|" + "".join(row) + "|")
        legend = []
        for k, p in enumerate(sorted(here, key=lambda q: (q.x, q.y))):
            legend.append(f"{'#@*+%o'[k % 6]} {p.name}{' (rotated)' if p.rotated else ''}")
        out.append("            " + " ; ".join(legend))
        out.append("")
    return out


def main() -> None:
    ev = evaluate(baseline())
    bay = joints.budgets(ev.rocket, ev.params.wall_thickness)["nav bay"]

    rule("THE NAV BAY SLED -- an allowance, for the fourth time")
    say()
    say("  design/mass.py has charged 150 g for `sled_and_hardware` since that dict was")
    say("  written, and design/avionics.py has charged 0.80 of the bore for its width. A")
    say("  mass allowance and a length allowance, priced into every budget in the vehicle,")
    say("  for a part that has never been drawn. That is correction 33's shape (the")
    say("  harness), 37's (the pass-through plate) and 38's (both access bulkheads). The")
    say("  tell is the same every time: the thing is charged for, so nothing reports it")
    say("  missing.")

    rule("WHAT THE BAY GIVES THE SLED")
    say()
    say(f"  nav bay tube          {bay.tube_length * MM:8.2f} mm")
    say(f"  less one bulkhead     {joints.BULKHEAD_ALLOWANCE * MM:8.2f} mm   its aft closure,"
        " the pass-through plate")
    say(f"  usable by the sled    {bay.usable_length * MM:8.2f} mm")
    say()
    say(f"  full bore             {bay.full_bore * MM:8.2f} mm")
    # Both halves of both joints, since Sep 2026 -- and for this bay they tile the whole
    # tube, which is docs/01 correction 42. Naming the parts rather than saying "the nose
    # shoulder" matters here: the shoulder is only 79.4 of the 127.0.
    js = joints.for_rocket(ev.rocket, ev.params.wall_thickness)
    sleeves = ", ".join(
        f"{j.narrowed_span('nav bay') * MM:.1f} mm {'nose shoulder' if j.aft_bay == 'nav bay' else 'aft coupler bond'}"
        for j in js if j.narrowed_span("nav bay") > 0.0)
    say(f"  narrowed bore         {bay.narrow_bore * MM:8.2f} mm over"
        f" {bay.narrow_span * MM:.1f} mm -- {sleeves}")
    say(f"  what a SLED sees      {bay.min_bore * MM:8.2f} mm, over its whole length,"
        " because it is one rigid plate")
    say()
    say("  The nose's own plate is charged to the NOSE, not to this bay -- joints.py puts")
    say("  it forward of the joint plane. So the sled really does get all 115.04 mm, and")
    say("  not 8.8 mm less. That was worth deriving rather than inheriting, on a margin")
    say("  quoted as +4.6 mm.")

    g = sled.sled_from_evaluation(ev)                      # design point: widest the rods allow
    old_w = avionics.SLED_WIDTH_FRACTION * bay.min_bore     # what every figure has been quoted at
    boards = sled.sled_from_evaluation(
        ev, plate_width=old_w, components=list(avionics.NAV_BAY_STACK))
    pack = avionics.check_packing(bay.min_bore, bay.usable_length,
                                  avionics.NAV_BAY_STACK, end_closures=0)

    rule("THE TWO ANSWERS")
    say()
    say("  AREAL, as design/avionics.py has always computed it -- footprint summed and")
    say("  divided by 2 x sled width x 0.70 packing efficiency:")
    say()
    say(f"    {pack}")
    say()
    say("  DISCRETE, placing every component as a rectangle on one of two faces, exhaustive")
    say("  over face assignment and 0/90 orientation and exact within a face:")
    say()
    say(f"    the 4 boards, on the same {old_w * MM:.2f} mm plate, "
        f"{boards.clearance * MM:.1f} mm clearance all round: "
        f"{'PLACES' if boards.placed else 'NO PLACEMENT'}")
    say()
    say("  Both are true. They answer different questions, and the areal one is not wrong --")
    say("  it was built to show that footprint binds and volume does not, and it does.")

    if boards.placed:
        say()
        for row in plan(boards):
            say(row)

    rule("AND THEN THE WIRING")
    say()
    say("  avionics.WIRING_FOOTPRINT charges the 80 g loom 70 x 20 mm of SLED FACE. An")
    say("  areal model has no way to say 'along one edge' other than by charging the area.")
    say("  Asked as a rectangle, the question has a different answer:")
    say()
    say(f"  on the {old_w * MM:.2f} mm plate that 0.80 of the bore gives:")
    say()
    say(f"    {'clearance':>12}   {'boards only':>12}   {'boards + loom':>14}")
    say(f"    {'-' * 44}")
    for cl in (0.0, 0.5, 1.0, 1.5, 2.0):
        a = sled.sled_from_evaluation(
            ev, clearance=cl / MM, plate_width=old_w,
            components=list(avionics.NAV_BAY_STACK))
        b = sled.sled_from_evaluation(
            ev, clearance=cl / MM, plate_width=old_w,
            components=list(avionics.NAV_BAY_STACK) + [sled.LOOM])
        say(f"    {cl:9.1f} mm   {'places' if a.placed else 'NO':>12}   "
            f"{'places' if b.placed else 'NO PLACEMENT':>14}")
    say()
    blocked = sled.sled_from_evaluation(
        ev, plate_width=old_w,
        components=list(avionics.NAV_BAY_STACK) + [sled.LOOM])
    if blocked.blocked:
        say(f"  At {blocked.clearance * MM:.1f} mm: {blocked.blocked}")
    say()
    say("  So the boards were never the question. Now sweep the one thing that is free:")
    say("  once the rods sit OUTBOARD of the plate, plate width costs nothing until the")
    say("  rods stop clearing the bore.")
    say()
    say(f"    {'plate':>9}   {'fraction':>9}   {'half-height':>12}   {'tallest part':>13}"
        f"   {'boards + loom':>14}")
    say(f"    {'-' * 70}")
    tallest = max(sled.stack_height(c) for c in
                  list(avionics.NAV_BAY_STACK) + [sled.LOOM]) * MM
    for wd in (56.16, 57.0, 58.0, 59.0, g.plate_width * MM, 61.20, 62.5):
        b = sled.sled_from_evaluation(ev, plate_width=wd / MM)
        hh = b.usable_height / 2.0 * MM
        say(f"    {wd:6.2f} mm   {wd / (bay.min_bore * MM):9.3f}   {hh:9.2f} mm   "
            f"{tallest:10.2f} mm   {'places' if b.placed else 'NO PLACEMENT':>14}"
            f"{'   <- selected' if abs(wd - g.plate_width * MM) < 1e-6 else ''}")
    say()
    say("  WIDTH IS BOUGHT WITH HEIGHT, and that is the only thing limiting it now. A wider")
    say("  plate sits on a longer chord, so the inscribed rectangle gets shorter, and the")
    say("  tallest component on the sled is what pays. The rods USED to limit it too --")
    say("  they do not any more, and why they stopped is the next section.")
    say()
    say("  THERE IS THE ANSWER, AND IT IS A DESIGN CHANGE RATHER THAN A PROBLEM.")
    say("  avionics.SLED_WIDTH_FRACTION = 0.80 gives 56.16 mm, and 56.16 mm cannot carry")
    say("  the loom the same file charges for. 59.00 mm can. M4 rods allow 59.20 mm.")
    say()
    say("  0.80 was never argued for -- avionics.py calls it 'a working figure'. There is")
    say(f"  now an argument for a different one, and design/sled.py takes it: the plate is")
    say(f"  {g.plate_width * MM:.2f} mm, or {g.plate_width / g.bore:.3f} of the bore, set by")
    say(f"  keeping {sled.HALF_HEIGHT_MARGIN * MM:.1f} mm of headroom over the tallest part.")
    say()
    say("  design/configure.py now passes that real width into avionics.check_packing()")
    say("  instead of the 0.80 fallback, so the vehicle's own warning describes the sled")
    say("  that exists. The areal margin goes +4.6 -> +10.7 mm as a RESULT of that, and it")
    say("  is worth being clear this is not the model being retuned until it fits: the part")
    say("  got better, and the constant followed.")
    say()
    say("  How much room is there at other assembly clearances:")
    say()
    say(f"    {'clearance':>10}   {'plate the loom needs':>21}   {'widest the height allows':>22}")
    say(f"    {'-' * 58}")
    for cl in (0.5, 1.0, 1.5, 2.0, 2.5):
        lo, hi, found = 40.0, 61.20, None
        for _ in range(40):
            mid = (lo + hi) / 2.0
            t = sled.sled_from_evaluation(
                ev, plate_width=mid / MM, clearance=cl / MM,
                components=list(avionics.NAV_BAY_STACK) + [sled.LOOM])
            if t.placed:
                hi = mid
                found = mid
            else:
                lo = mid
        top = sled.sled_from_evaluation(
            ev, plate_width=61.20 / MM, clearance=cl / MM,
            components=list(avionics.NAV_BAY_STACK) + [sled.LOOM])
        need = f"{found:.2f} mm" if top.placed else "no width works"
        widest = f"{sled.max_plate_width(bay.min_bore, tallest / MM) * MM:.2f} mm"
        say(f"    {cl:7.1f} mm   {need:>21}   {widest:>22}")
    say()
    say("  At 2.0 mm of clearance nothing in the bore works. 1.0 mm is already tight for")
    say("  hand assembly with connectors plugged, so this is not a margin to spend.")

    rule("WHY NOT JUST PUT THE LOOM IN THE CORNERS")

    say()
    say("  The obvious objection to all of the above: a loom is flexible, and the two corner")
    say("  crescents outboard of the plate are exactly the volume a flat sled cannot reach.")
    say("  That is avionics.py's whole argument. Put the wiring there and the plate stays at")
    say("  0.80. It does not work, and the number says why:")
    say()
    budgeted = mass.DEFAULT_AVIONICS_BUDGET["wiring_connectors"]
    for w, label in ((old_w, "0.80 of the bore"), (g.plate_width, "as built")):
        t = sled.sled_from_evaluation(ev, plate_width=w)
        say(f"    plate {w * MM:5.2f} mm ({label:17s})  crescents"
            f" {t.crescent_volume * 1e6:5.1f} cm^3  ->"
            f" {budgeted / t.crescent_volume / 1000.0:5.2f} g/cm^3 to hold"
            f" {budgeted * MM:.0f} g")
    say()
    say("  Copper is 8.96 g/cm^3 and PVC insulation about 1.4. A bundle with air in it does")
    say("  not reach either figure. THE CRESCENTS DO NOT TAKE 80 g OF LOOM EITHER, and they")
    say("  get worse as the plate widens, so the two fixes work against each other.")
    say()
    say("  Note these are the crescents with the RODS OUT OF THEM. Clocking the rods above")
    say("  and below the plate handed both crescents back whole -- a real gain, and still")
    say("  not enough.")
    say()
    say("  THIS ALL HAS A SECOND READING AND THIS REPORT CANNOT DISTINGUISH THEM:")
    say()
    say("    1. The loom really is 70 x 20 x 12 mm of solid keep-out, in which case the")
    say("       plate must go to 59 mm and there is 0.20 mm in hand.")
    say("    2. The 80 g is a WHOLE-AVIONICS allowance. mass.py calls the line")
    say("       `wiring_connectors`, and connectors are not loom. The servo leads run AFT")
    say("       through the pass-through plate into the canard module, and the pyro leads")
    say("       run aft to the recovery bay -- neither stays in this bay. Charging all 80 g")
    say("       to nav bay sled FACE is then the wrong place for most of it, and the whole")
    say("       squeeze dissolves.")
    say()
    say("  NOTHING HERE RESIZES THE BAY AND NOTHING HERE EDITS avionics.py. Correction 5 is")
    say("  the precedent and it is exact: the recovery bay was declared 11 mm short on a")
    say("  figure built from multiplied estimates, the airframe was lengthened for it, and")
    say("  the shortfall turned out not to exist. What settles this is weighing the loom")
    say("  and counting the conductors. That is an afternoon's work and it has never been")
    say("  done. The wider plate is the cheap insurance in the meantime: it costs nothing,")
    say("  it is inside the bore, and it is right under either reading.")

    rule("THE PART")

    say()
    say(f"  plate                 {g.plate_length * MM:.2f} x {g.plate_width * MM:.2f}"
        f" x {g.plate_thickness * MM:.2f} mm G-10")
    say(f"  end brackets          2 off, R {g.bracket_radius * MM:.2f} mm cropped to"
        f" +/-{sled.BRACKET_HALF_WIDTH * MM:.1f} mm in X,"
        f" {g.bracket_thickness * MM:.1f} mm thick")
    say(f"  rods                  {sled.ROD_COUNT} x M{sled.ROD_DIAMETER * MM:.0f} at"
        f" (0, +/-{g.rod_radius * MM:.2f}) -- PERPENDICULAR to the plate, above and below")
    say(f"                        running the full {g.rod_length * MM:.2f} mm of bay,"
        f" plate to plate")
    say(f"  standoffs             {sum(len(f) for (_x, _y, f, _o) in g.mount_sites())} x"
        f" {sled.STANDOFF_OD * MM:.0f} mm nylon,"
        f" {sled.STANDOFF_HEIGHT * MM:.0f} mm tall")
    say(f"  assembly length       {g.assembly_length * MM:.2f} mm against"
        f" {bay.usable_length * MM:.2f} mm usable")
    say(f"  usable height         {g.usable_height * MM:.2f} mm total,"
        f" {g.usable_height * MM / 2.0:.2f} mm a face")
    say(f"  widest point          R {g.max_radius * MM:.2f} mm against a"
        f" R {g.bore * MM / 2.0:.2f} mm shoulder bore")
    say()
    say(f"    plate               {g.plate_mass * MM:6.1f} g")
    say(f"    end brackets        {g.bracket_mass * MM:6.1f} g")
    say(f"    rods                {g.rod_mass * MM:6.1f} g")
    say(f"    standoffs           {g.standoff_mass * MM:6.1f} g")
    say(f"    hardware            {sled.HARDWARE_MASS * MM:6.1f} g   nuts, washers, screws"
        " -- a guess")
    say(f"    {'-' * 28}")
    say(f"    total               {g.mass * MM:6.1f} g   against"
        f" {sled.SLED_MASS_BUDGET * MM:.0f} g budgeted in mass.py")

    rule("THE MOUNT -- and the thing that had to be got wrong first")

    say()
    say("  Two threaded rods between the two end plates. The rods are clocked PERPENDICULAR")
    say("  to the sled -- one above it, one below -- and not out at its edges, which is")
    say("  where a side-view sketch puts them and where this was first built.")
    say()
    say("  RODS BESIDE THE PLATE DO NOT WORK, and the reason only shows up in three")
    say("  dimensions. A nut on a rod running along the rocket axis clamps ALONG that axis,")
    say("  and a plate lying in the rod's own plane presents nothing to that direction but")
    say("  its 1.6 mm edge. There is no face for a washer to bear on. Widening the plate")
    say("  into ears around each rod does not rescue it either: the rod runs the whole")
    say("  length of the bay, so clearing it means removing every scrap of ear at that")
    say("  radius for every station, and the ear then captures nothing. The Fusion model")
    say("  said so in one line -- 47.31 mm3 of plate inside each rod.")
    say()
    say("  So the capture has to be PERPENDICULAR to the rod: a small end bracket in the")
    say("  cross-section plane, which is a bulkhead in miniature and is what a real")
    say("  avionics bay has always used. Once it is a bracket, the rod can leave the")
    say("  plate's plane, and that buys two things at once:")
    say()
    say(f"    {'rod position':>14}   {'hole ligament in a bracket':>27}"
        f"   {'in the two END PLATES':>23}")
    say(f"    {'-' * 70}")
    for rr in (32.60, 31.0, g.rod_radius * MM, 29.0):
        lig = g.bracket_radius * MM - (rr + g.rod_hole_diameter * MM / 2.0)
        end = 37.40 - rr - g.rod_hole_diameter * MM / 2.0
        say(f"    R {rr:10.2f} mm   {lig:24.2f} mm   {end:20.2f} mm"
            f"{'   <- selected' if abs(rr - g.rod_radius * MM) < 1e-6 else ''}")
    say()
    say("  * THE ROD STOPS CONSTRAINING THE PLATE WIDTH. Beside the plate they compete for")
    say("    the same millimetres. Above it they do not compete at all -- the rod sits at")
    say(f"    Y {(g.rod_radius - g.rod_diameter / 2.0) * MM:.1f}-"
        f"{(g.rod_radius + g.rod_diameter / 2.0) * MM:.1f} mm and the tallest component "
        f"reaches {(g.plate_thickness / 2.0 + max(sled.stack_height(c) for c in g.components)) * MM:.2f} mm.")
    say("  * THE ROD CAN COME INBOARD, so its hole is a real hole. At R 32.60 a 4.5 mm hole")
    say("    leaves -0.05 mm of ligament, which is not a part. At R 30.00 it leaves 2.55 mm.")
    say("    It also takes the hole in each END PLATE from 2.55 to 5.15 mm of edge ligament,")
    say("    and that matters more -- those two plates are pressure boundaries.")
    say()
    say("  The plate BUTTS the brackets and is bonded to them; it does not run through them.")
    say(f"  It cannot: the plate is {g.plate_width * MM:.2f} mm wide and a bracket only")
    say(f"  {2 * sled.BRACKET_HALF_WIDTH * MM:.1f} mm, so a slot for it would run the bracket's")
    say("  full width and cut it into two unconnected halves. A butt bond carries 166x.")

    chk = sled.check_sled(g)
    rule("VERDICT")
    say()
    say(f"  sled check          {'OK' if chk.ok else 'VIOLATIONS: ' + '; '.join(chk.violations)}")
    for n in chk.notes:
        say(f"                      {n}")
    say()
    say("  Read that as narrowly as it is written. Everything places, the part is")
    say("  buildable, and it comes in under its mass allowance -- on a plate 3.25 mm wider")
    say("  than the one every figure in this project was quoted against. Two things in that")
    say("  list are NOT solved and are only reported:")
    say()
    say("    * BATTERY AND LOOM RETENTION. There is 1.00 mm of clear plate beside the")
    say("      battery and 1.41 mm beside the loom, against the ~3 mm a cable-tie slot")
    say("      needs. So the two heaviest items on the sled are held by nothing that is")
    say("      drawn. Adhesive, foam, or a strap anchored to the board standoffs will do")
    say("      it -- 90 g at 8.3 g is only 7.3 N -- but none of those is designed, and a")
    say("      battery coming loose in a guided vehicle is not a small failure.")
    say("    * SIX SCREWS LAND UNDER A COMPONENT ON THE OTHER FACE. They have to be")
    say("      countersunk flush or the part above needs relief. Free to notice now and a")
    say("      filed screw head later.")

    rule("STILL A GUESS")
    say()
    est = [c.name for c in avionics.NAV_BAY_STACK if not c.measured]
    say(f"  {len(est)} of {len(avionics.NAV_BAY_STACK)} nav bay envelopes are estimates:")
    for name in est:
        say(f"    {name}")
    say()
    say("  The STM32 board's 70 x 45 x 12 is called a LAYOUT TARGET in avionics.py, not a")
    say("  measurement, and it is the only line a design decision can shrink. Everything")
    say("  above is parametric on those envelopes -- rerun this one command when a part is")
    say("  chosen. Also a guess: the 30 g of hardware, and the loom's 12 mm bundle height.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
