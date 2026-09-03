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

from design import avionics, joints, venting
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

    bays = joints.budgets(ev.rocket, baseline().wall_thickness)
    navb = bays["nav bay"]
    full = avionics.check_packing(navb.min_bore, navb.usable_length,
                                  avionics.NAV_BAY_STACK, end_closures=0)
    was = avionics.check_packing(navb.min_bore, navb.usable_length,
                                 avionics.DEFAULT_STACK, end_closures=0)
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
    say(f"  available = {length * MM:.0f} mm of tube less one "
        f"{joints.BULKHEAD_ALLOWANCE * MM:.0f} mm bulkhead = "
        f"{full.available_length * MM:.0f} mm of sled, at {navb.min_bore * MM:.1f} mm bore")
    say()
    say(f"  {'IT FITS ON THE AREAL MODEL' if full.fits else 'STILL SHORT'}, AND THAT IS "
        f"STILL NOT A REASON TO CHANGE GEOMETRY EITHER WAY.")
    say()
    say("  This line used to read 'STILL SHORT BY 14 mm' as a hardcoded string while the")
    say("  computed verdict three lines above already said FITS. It was stale from before")
    say("  D7 closed, and a report that types its own conclusion is not reporting one.")
    say("  It is derived now. (docs/04 section 5 carried the same stale figure in two more places; both fixed.)")
    say()
    say("  AND THE AREAL ANSWER IS NOT THE WHOLE ANSWER. Placing the same stack as real")
    say("  rectangles on two real faces -- which this model does not do, by design -- says")
    say("  the boards fit and the 80 g wiring loom does not, on a 56.16 mm plate. See")
    say("  design/sled.py and `python scripts/sled_report.py`. Nothing there resizes the")
    say("  bay either.")
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

    rule("THE SHOULDER QUESTION -- SETTLED, and it went the good way")
    say()
    say("  This report used to end by saying the nose shoulder was unmodelled and worth more")
    say("  than the shortfall: a 1 caliber shoulder on a 127 mm bay, and nobody had decided")
    say("  which tube's length it spent. The two readings were 79 mm apart.")
    say()
    say("  BOTH READINGS WERE WRONG, because the question had a false premise. A shoulder is")
    say("  a TUBE. So is a coupler. What is inside it is still bay. Neither costs LENGTH --")
    say("  what each costs is local DIAMETER over its span:")
    say()
    say(f"      coupler / shoulder bore = {navb.full_bore * MM:.1f} - 2 x "
        f"{baseline().wall_thickness * MM:.1f} = {navb.narrow_bore * MM:.1f} mm")
    say()
    say("  What costs length is a BULKHEAD, and bulkheads were already counted. So:")
    say()
    for b in bays.values():
        say(f"    {b}")
    say()
    say(f"  The nav bay gains {(navb.usable_length - 0.103) * MM:.0f} mm of length (one bulkhead, not two -- the")
    say("  forward closure belongs to the nose module) and loses 3.6 mm of sled width to")
    say("  the shoulder bore. Net, the shortfall goes 14 -> 9 mm.")
    say()
    say("  The framing is what had been wrong, not any number. \"Which bay does the")
    say("  shoulder's length come out of\" is a complete-sounding question whose two answers")
    say("  were both false, which is correction 28 one joint further forward.")

    rule("THE NOSE AS A SWAPPABLE MODULE -- and what a future payload may weigh")
    say()
    say("  Putting the tracker and the radio in the nose was a packing fix. Keeping them")
    say("  there on purpose is a different decision: the nose becomes the INSTRUMENTATION")
    say("  MODULE, and the point of one is that it comes off. After GV-2 has measured the")
    say("  control derivatives, the same nose can carry a payload instead.")
    say()
    say("  That needs three things to be true, and the third is the one nobody expects:")
    say()
    for name, iface in avionics.NOSE_MODULE_INTERFACES.items():
        say(f"    {name:26s} {iface}")
    say()
    say("    -> ONE electrical interface for the whole module. A payload that needs nothing")
    say("       leaves it unmated. The tracker having its own battery is not a nicety; an")
    say("       independent tracker sharing the flight computer's battery is not independent.")
    say()
    say("    -> ITS MASS IS PART OF THE STABILITY SOLUTION. 105 g at station 300 mm sits")
    say(f"       forward of the {ev.masses.dry_cg * MM:.0f} mm CG, so it is doing the same job as the nose")
    say("       ballast. Swap it for something heavier and the margin moves:")
    say()
    say(f"  {'nose payload':>14s} {'SM min':>8s} {'SM max':>8s}   verdict")
    say("  " + "-" * 50)
    for m, lo, hi, ok in avionics.payload_envelope(evaluate, baseline(), 0.300):
        tag = "ok" if ok else "SM over 3.0 -- over-stable"
        mark = "  <- instrumentation" if abs(m - 0.105) < 1e-9 else ""
        say(f"  {m * 1000:11.0f} g {lo:8.2f} {hi:8.2f}   {tag}{mark}")
    say()
    say("  SO: ANYTHING UP TO ABOUT 300 g GOES IN WITH NO OTHER CHANGE, and past that the")
    say("  vehicle turns over-stable rather than unstable -- it weathercocks and gives up")
    say("  crossrange, which is a performance loss and not a safety one. The nose ballast is")
    say("  the trim knob either way: 100 g at station 191 mm with provision for 300 g")
    say("  (docs/00 D10), and it was always meant to be set after weighing the real vehicle.")
    say()
    nose = ev.rocket.nose
    free_all = avionics.nose_payload_volume(nose, 0.200, nose.length)
    free_now = avionics.nose_payload_volume(nose, 0.282, nose.length)
    say(f"  Room: {free_all * 1e6:.0f} cm3 between station 200 mm (clear of the ballast) and the")
    say(f"  nose base, of which the instrumentation sled uses {free_now * 1e6:.0f} cm3 at 282-318 mm.")
    say("  A payload gets the lot once the tracker and radio come out.")
    say()
    say("  THE ONE DRAWBACK, stated rather than buried: the GNSS antenna stays in the NAV")
    say("  BAY, at the forward end of its sled, under the shoulder -- configure.py puts the")
    say("  nav bay forward for exactly that reason. A dense payload sitting directly ahead of")
    say("  it is between that antenna and the sky. Nothing here models RF; if the payload is")
    say("  metallic, check the fix before the flight rather than after it.")

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
