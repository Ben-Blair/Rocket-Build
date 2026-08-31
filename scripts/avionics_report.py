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

    full = avionics.check_packing(d, length)
    moved = avionics.check_packing(d, length, avionics.relocatable())

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

    rule("THE VERDICT, ON ESTIMATED ENVELOPES")
    say()
    say(f"  {full}")
    say(f"  {moved}      with the tracker and radio moved out")
    say()
    say(f"  available = {length * MM:.0f} mm of bay less two "
        f"{avionics.END_CLOSURE_THICKNESS * MM:.0f} mm end closures = "
        f"{full.available_length * MM:.0f} mm of sled")
    say()
    say("  SO THE NAV BAY IS SHORT, AND THIS IS NOT YET A REASON TO CHANGE ANYTHING.")
    say()
    say("  Correction 5 is the precedent and it is exact: the recovery bay was declared")
    say("  11 mm short on a number built from two multiplied estimates, the airframe was")
    say("  lengthened on the strength of it, and the shortfall turned out not to exist. Every")
    say("  envelope above is that same kind of estimate -- no part here has been chosen.")
    say()
    say("  What would settle it, in order of how much it costs:")
    say()
    say("  1. CLOSE D7 AND MEASURE. Nine datasheets replace nine guesses. This is ten")
    say("     minutes of work per part and it is the only thing that turns the verdict into")
    say("     a fact. Do this before anything else on this list.")
    say(f"  2. MOVE THE TRACKER AND RADIO TO THE NOSE CONE. Worth "
        f"{(full.required_length - moved.required_length) * MM:.0f} mm, and it changes")
    say("     no frozen geometry. It is also where a tracker belongs: its job is to still be")
    say("     working when nothing else is, which argues for its own battery in its own")
    say("     compartment, as far from the servo bus as the airframe allows.")
    say("  3. ONE END CLOSURE, NOT TWO. The bay's aft face is shared with the canard")
    say("     module's forward face, and the forward one is the nose shoulder. If either is")
    say(f"     structure that already exists, that is {avionics.END_CLOSURE_THICKNESS * MM:.0f} mm back.")
    say("  4. LENGTHEN THE NAV BAY. 1.6 -> 2.0 cal is +32 mm and it is the answer that")
    say("     touches every number in the vehicle. It is last for that reason, not first.")

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
    say(f"  {len(full.estimated)} of {len(full.components)} envelopes are estimates:")
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
