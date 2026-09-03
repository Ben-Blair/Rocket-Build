"""Print the argument for the two access bulkheads, and check them.

    python scripts/access_bulkhead_report.py            # to the terminal
    python scripts/access_bulkhead_report.py --write    # and into out/access_bulkhead_report.txt

Everything here is derived from `design/configure.py`. `design/seal.py` sizes the two
SEPARATION bulkheads (the aft gas seal and the recovery bay's internal bulkhead) and has
carried, since it was written, an explicit note that it does not size the two ACCESS
bulkheads -- the nose's aft face and the nav bay / canard module plate. This is that note,
closed. See `design/access_bulkhead.py` for the argument in full.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import access_bulkhead as ab, joints, seal
from design.configure import baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "access_bulkhead_report.txt"

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
    pt = ab.pass_through_from_evaluation(ev)
    np = ab.nose_plate_from_evaluation(ev)

    rule("WHY THESE TWO WERE NEVER SIZED")
    say()
    say("  design/joints.py puts a bulkhead on all four tube-to-tube joints. Two are")
    say("  SEPARATION joints and design/seal.py sizes both. The other two are ACCESS joints")
    say("  -- come apart by hand or by screws, not on an ejection charge -- and seal.py has")
    say("  carried a note since it was written that it does not size either of them. Both")
    say("  already spend bay length in joints.budgets() as a 12 mm allowance, so they were")
    say("  priced while not existing as parts. Neither is in the CAD, which is why the")
    say("  forward wiring pass-through has never been drawn -- the plate it passes through")
    say("  was not there.")

    rule("THE HEADLINE: NEITHER PLATE IS SIZED BY STRESS")
    say()
    say(f"  {'':32s} {'pass-through plate':>20s} {'nose aft face':>16s}")
    say("  " + "-" * 72)
    rows = [
        ("thickness, mm", lambda x: f"{x.bulkhead.thickness * MM:.1f}"),
        ("mass, g", lambda x: f"{x.bulkhead.mass * 1e3:.1f}"),
        ("governing pressure, Pa", lambda x: f"{x.pressure:.1f}"),
        ("plate margin", lambda x: f"{x.plate_margin:.0f}x"),
        ("feed-through margin", lambda x: f"{x.hole_margin:.0f}x"),
        ("point-load margin", lambda x: f"{x.point_margin:.0f}x" if x.point_load > 0 else "n/a"),
        ("assembled stack, mm", lambda x: f"{ab.stack_length(x) * MM:.1f}"),
    ]
    for label, fn in rows:
        say(f"  {label:32s} {fn(pt):>20s} {fn(np):>16s}")
    say()
    say("  Both clear the thinnest stocked G-10 sheet by more than 25x on every load this")
    say("  file can find. That is the same shape of result design/venting.py reported for")
    say("  the module vents: the argument everyone reaches for -- 'this is a bulkhead, size")
    say("  it like one' -- is not what sizes these two. What sets them is producibility:")
    say("  holding a screw thread through repeated disassembly, and a connector's panel-nut")
    say("  torque. Neither has a stress model in this project, so a practical floor stands")
    say("  in for one, stated rather than hidden inside a 'looks about right' thickness.")

    rule("THE PASS-THROUGH PLATE -- nav bay / canard module")
    say()
    say("  Both bays it separates vent to ambient ON THEIR OWN: the nav bay through its")
    say("  static ports, the canard module through its own wall (correction 28). Neither is")
    say("  sealed, so the only load that can develop across THIS plate is the difference in")
    say("  how fast the two bays track a changing ambient pressure -- not either bay's own")
    say("  lag, which venting.py already showed does not bind by a factor of 300.")
    say()
    from design import avionics, venting
    nav = next(t for t in ev.rocket.tubes if t.name == "nav bay")
    nav_free = avionics.free_volume(nav.inner_diameter, nav.length)
    nav_bay = venting.VentedBay("nav bay", nav_free, venting.CONVENTIONAL_PORT_COUNT,
                                venting.CONVENTIONAL_PORT_DIAMETER)
    mod_bay = venting.VentedBay("canard module", venting.CANARD_MODULE_FREE_VOLUME,
                                venting.MODULE_VENT_COUNT, venting.MODULE_VENT_DIAMETER)
    say(f"  nav bay lag at 177 m/s      {nav_bay.lag(285.0, 177.0):8.2f} Pa")
    say(f"  canard module lag           {mod_bay.lag(285.0, 177.0):8.2f} Pa    "
        f"(smaller vent area, so it lags MORE)")
    say(f"  differential across plate   {pt.pressure:8.2f} Pa    "
        f"{pt.pressure * 3.14159 * (pt.bulkhead.bore_diameter ** 2) / 4 * 1000:.2f} mN total")
    say()
    say("  The ejection charge does not reach this plate either. It fires in the recovery")
    say("  bay's forward compartment against the AFT gas seal, and a leak past that disc is")
    say("  deliberately routed to the canard module's OWN vents -- venting.MODULE_VENT_STATION")
    say("  sits in the aft band specifically so a leak finds a hole before it travels forward")
    say("  to here.")
    say()
    f = pt.feed_through
    say(f"  wire route (potted solid)   {f.n_holes} x dia {f.hole_diameter * MM:.1f} mm at "
        f"R {f.radius_in_plate * MM:.1f} mm -- NO WIRE GAUGE HAS EVER BEEN CHOSEN in this")
    say("                               project; this is a practical bundle allowance for 4")
    say("                               servo leads + the shared power/ground pair, flagged")
    say("                               the way seal.py flags JOINT_FRICTION_ALLOWANCE")

    rule("THE NOSE AFT FACE -- the module interface and the payload mount")
    say()
    say("  Two loads, neither of them the aft gas seal's kind:")
    say()
    say(f"  1. TRAPPED DIFFERENTIAL, pad to apogee   {np.pressure / 1e3:8.2f} kPa")
    say("     CONSERVATIVE, and said plainly rather than assumed away: nobody has ever")
    say("     modelled whether the nose cavity is vented. design/avionics.py and")
    say("     design/venting.py both stop at the nav bay. If the nose needs its own vent,")
    say("     that is a real open item this file surfaces rather than closes -- until it")
    say("     exists, the plate is checked as though the cavity is fully sealed.")
    say()
    say(f"  2. THE PAYLOAD MOUNT   {ab.NOSE_PAYLOAD_DESIGN_MASS * 1e3:.0f} g at "
        f"{ev.flight.max_acceleration_g:.1f} g boost accel = {np.point_load:.1f} N")
    say("     seal.py: this disc 'is what a future payload of up to about 300 g would hang")
    say("     from.' A tapered nose cone has nowhere else flat enough to cantilever a sled")
    say("     from, so that sentence is taken as the design intent -- a point load on a")
    say("     small boss, sized against the CORRECTION-32 PROVISION CEILING, not the 105 g")
    say("     of avionics actually flying today. Sizing the mount for what is built rather")
    say("     than what the vehicle is designed to carry is the harness's old mistake, one")
    say("     part further forward.")
    say()
    f = np.feed_through
    say(f"  the module's one electrical interface   {f.n_holes} x dia {f.hole_diameter * MM:.1f} mm "
        f"at R {f.radius_in_plate * MM:.1f} mm, panel-mount connector -- no part selected")

    rule("VERDICT")
    say()
    for r in (pt, np):
        chk = ab.check_access_bulkhead(r)
        say(f"  {r.name:32s} {'OK' if chk.ok else 'VIOLATIONS'}")
        for v in chk.violations:
            say(f"    VIOLATION  {v}")
        for n in chk.notes:
            say(f"    note  {n}")
        say()
    say("  Neither plate blocks the drawing any longer: thickness, feed-through diameter and")
    say("  placement, and axial stack are all numbers now instead of an allowance. What is")
    say("  still open -- flagged, not solved -- is the nose cavity's venting and the two")
    say("  connector/wire part numbers. None of the three change the plate.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
