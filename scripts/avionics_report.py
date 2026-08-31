"""Does the avionics stack fit in the nav bay, and where does each board go?

    python scripts/avionics_report.py            # to the terminal
    python scripts/avionics_report.py --write    # and into out/avionics_report.txt

READ THE VERDICT WITH CORRECTION 5 IN HAND. Every envelope in `design/avionics.py` is an
estimate for a part that has not been chosen, because D7 and D8 are open. The last time this
project acted on a packing verdict built from estimates it briefly lengthened a frozen
airframe on the strength of a shortfall that was not in the hardware. So this report says
what it needs, says what would settle it, and does not recommend touching geometry.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import avionics, venting
from design.configure import baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "avionics_report.txt"

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
    nav = next(t for t in ev.rocket.tubes if t.name == "nav bay")
    d, length = nav.inner_diameter, nav.length

    full = avionics.check_packing(d, length, avionics.NAV_BAY_STACK)
    was = avionics.check_packing(d, length, avionics.DEFAULT_STACK)
    nose_fit = avionics.check_nose_packing(
        ev.rocket.nose, forward_limit=baseline().nose_ballast_station + 0.020)

    rule("THE NAV BAY -- where the boards go, and whether they go")
    say()
    say(f"  station               {ev.rocket.tube_station(0) * MM:.0f} -> "
        f"{(ev.rocket.tube_station(0) + length) * MM:.0f} mm from the nose tip")
    say(f"  bay length            {length * MM:.1f} mm ({length / 0.0794:.2f} cal)")
    say(f"  bore                  {d * MM:.1f} mm")
    say(f"  sled width            {full.sled_width * MM:.1f} mm "
        f"({avionics.SLED_WIDTH_FRACTION:.0%} of the bore)")
    say(f"  usable height         {full.usable_height * MM:.1f} mm, NOT {d * MM:.1f}")
    say()
    say("  THE LAST LINE IS THE WHOLE MODELLING POINT. A flat sled in a round tube can only")
    say("  use the rectangle inscribed in the circle, and nothing goes in the corners it")
    say("  cannot reach. Add the component volumes up and the bay looks half empty --")
    import math
    geometric = math.pi * d**2 / 4.0 * length
    say(f"  {sum(c.volume for c in full.components) * 1e6:.0f} cm3 of boards in "
        f"{geometric * 1e6:.0f} cm3 of tube. The binding quantity is FOOTPRINT ON")
    say("  TWO FACES, and the bay's length is what that footprint has to fit into.")

    rule("THE STACK")
    say()
    say(f"  {'component':28s} {'mass':>7s} {'L x W x H mm':>18s} {'cm2':>7s}  note")
    say("  " + "-" * 90)
    for c in full.components:
        say(f"  {c.name:28s} {c.mass * 1e3:5.0f} g "
            f"{c.length * MM:5.0f} x{c.width * MM:4.0f} x{c.height * MM:4.0f} "
            f"{c.footprint * 1e4:7.1f}  {c.note}")
    say(f"  {'wiring loom':28s} {'80 g':>7s} {'along one edge':>18s} "
        f"{avionics.WIRING_FOOTPRINT * 1e4:7.1f}")
    say("  " + "-" * 90)
    say(f"  {'TOTAL FOOTPRINT':28s} {'':7s} {'':18s} {full.total_footprint * 1e4:7.1f} cm2")

    rule("THE NOSE -- where the tracker and the radio went, Aug 2026")
    say()
    say("  A NOSE IS THE ONE VOLUME IN THIS VEHICLE WHOSE WIDTH IS A FUNCTION OF STATION.")
    say("  Every bay so far could be checked with one diameter. Here the sled is only as")
    say("  wide as its NARROWEST end allows -- its forward end -- so the answer is a band,")
    say("  and the sled wants to sit as far aft as it can where the cone is fullest.")
    say()
    say(f"  {'station':>10s} {'OD':>9s} {'usable ID':>11s}")
    say("  " + "-" * 34)
    for x in (0.15, 0.20, 0.25, 0.28, ev.rocket.nose.length):
        say(f"  {x * MM:8.0f} mm {ev.rocket.nose.radius_at(x) * 2 * MM:7.1f} mm "
            f"{ev.rocket.nose.inner_radius_at(x) * 2 * MM:9.1f} mm")
    say()
    say(f"  {nose_fit}")
    say(f"  centroid at station {nose_fit.centroid * MM:.0f} mm, which is where the 105 g")
    say(f"  now sits instead of {ev.rocket.tube_station(0) * MM + length * MM / 2:.0f} mm.")
    say()
    say("  Behind the ballast, not in front of it: the 100 g washer stack is at 191 mm on a")
    say("  threaded rod and these two boards go on the same rod, 20 mm clear of it. Both are")
    say("  RF parts and neither needs a short wire to the flight computer, so the nose is")
    say("  the right place on RF grounds independently of the packing -- the shoulder region")
    say("  is where a fibreglass airframe stops shielding an antenna.")

    rule("THE VERDICT, ON ESTIMATED ENVELOPES")
    say()
    say(f"  {full}")
    say(f"  {was}      before the move")
    say()
    say(f"  available = {length * MM:.0f} mm of bay less two "
        f"{avionics.END_CLOSURE_THICKNESS * MM:.0f} mm end closures = "
        f"{full.available_length * MM:.0f} mm of sled")
    say()
    say("  STILL SHORT BY 14 mm, AND STILL NOT YET A REASON TO CHANGE GEOMETRY.")
    say()
    say("  Correction 5 is the precedent and it is exact: the recovery bay was declared")
    say("  11 mm short on a number built from two multiplied estimates, the airframe was")
    say("  lengthened on the strength of it, and the shortfall turned out not to exist. Every")
    say("  envelope above is that same kind of estimate -- no part here has been chosen.")
    say()
    say("  The move was worth "
        f"{(was.required_length - full.required_length) * MM:.0f} mm of the "
        f"{(was.required_length - was.available_length) * MM:.0f} mm gap. What is left:")
    say()
    say("  1. CLOSE D7 AND MEASURE. Six datasheets replace six guesses, and 14 mm is well")
    say("     inside what a 70% packing efficiency guess is worth -- at 0.80 the stack fits")
    say(f"     with {(2 * full.sled_width * 0.80 * full.available_length - full.total_footprint) * 1e4:+.1f} cm2 to spare. This is the only thing that settles it, and it is")
    say("     ten minutes of work per part.")
    say("  2. THE NOSE SHOULDER IS UNMODELLED AND IT IS BIGGER THAN 14 mm -- see below.")
    say("  3. ONE END CLOSURE, NOT TWO. The bay's aft face is shared with the canard")
    say("     module's forward face. If that plate already exists as the module's structure,")
    say(f"     that is {avionics.END_CLOSURE_THICKNESS * MM:.0f} mm back and the shortfall is gone.")
    say("  4. LENGTHEN THE NAV BAY. 1.6 -> 2.0 cal is +32 mm and it touches every number in")
    say("     the vehicle. Last for that reason, not first.")

    rule("THE THING THIS CHECK CANNOT SEE, AND IT IS LARGER THAN THE SHORTFALL")
    say()
    say("  THE NOSE SHOULDER IS NOT IN THIS MODEL AT ALL. `docs/04` carries a 1 caliber")
    say(f"  (79 mm) shoulder on a {length * MM:.0f} mm nav bay, and a shoulder inserts INTO the")
    say("  forward end of the tube it joins. Which tube's length it spends is a question")
    say("  nobody has answered, and the two answers are 79 mm apart:")
    say()
    say("    * if the sled has to sit AFT of the shoulder, the bay loses 79 mm rather than")
    say(f"      the {avionics.END_CLOSURE_THICKNESS * MM:.0f} mm this check charges, and it is short by ~80 mm, not 14;")
    say("    * if the sled runs UP INSIDE the shoulder -- which is how many high-power")
    say("      av-bays are actually built -- the bay GAINS most of that 79 mm and fits with")
    say("      room to spare.")
    say()
    say("  This check assumes neither. It charges a plain end closure at both ends, which is")
    say("  the arrangement nobody has drawn. **The 14 mm shortfall is the smallest open")
    say("  question about this bay, not the largest one.** Settle the shoulder before")
    say("  spending an afternoon on the packing efficiency.")

    rule("WHAT THE STACK MEANS FOR VENTING")
    say()
    free = avionics.free_volume(d, length)
    bay = venting.VentedBay("nav bay", free, venting.CONVENTIONAL_PORT_COUNT,
                            venting.CONVENTIONAL_PORT_DIAMETER)
    say(f"  free air in the bay   {free * 1e6:.0f} cm3 (geometric less the boards)")
    say(f"  static ports          {bay.n_ports} x dia {bay.port_diameter * MM:.1f} mm, "
        f"{bay.area * 1e6:.1f} mm2")
    say(f"  lag, 177 m/s up       {bay.lag_altitude(285.0, 177.0):.3f} m")
    say(f"  lag, 19 m/s down      {bay.lag_altitude(200.0, 19.0):.4f} m")
    say()
    say("  This is the ONLY volume the altimeter senses. The canard module vents through")
    say("  its own wall and the wiring pass-through between them is potted solid -- see")
    say("  design/venting.py, and note that seal.py argued the opposite first.")

    rule("STILL A GUESS")
    say()
    say(f"  {len(full.estimated)} of {len(full.components)} nav bay envelopes are estimates:")
    for name in full.estimated:
        say(f"    {name}")
    say()
    say("  Replace each with a datasheet as D7 closes and set `measured=True`. When that")
    say("  list is empty this report stops needing its caveat, which is exactly what")
    say("  happened to the recovery bay when the vendor pack volumes went in.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
