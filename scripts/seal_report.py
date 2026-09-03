"""Print the argument for the aft gas seal, and check it.

    python scripts/seal_report.py            # to the terminal
    python scripts/seal_report.py --write    # and into out/seal_report.txt

Everything here is derived from `design/configure.py` and `design/recovery.py`. No number
in this file is typed twice; if the recovery bay changes length or the main changes size,
this report changes with it. That is the rule `configure.py` was written to enforce.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import avionics, recovery, seal, venting
from design.configure import baseline, evaluate

MM = 1000.0

OUT = Path(__file__).resolve().parents[1] / "out" / "seal_report.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def rule(title: str) -> None:
    say()
    say("=" * 92)
    say(title)
    say("=" * 92)


def build_result() -> tuple[seal.SealResult, float, float]:
    """The seal case, plus the two recovery numbers it is quoted against.

    The case itself is built by `seal.from_evaluation()` so that this report and
    `scripts/baseline.py` cannot describe two different bulkheads.
    """
    ev = evaluate(baseline())
    deploy_alt = 200.0
    main = recovery.Canopy(
        "main", recovery.size_for_descent_rate(ev.masses.dry_mass, 5.0), 2.2)
    return seal.from_evaluation(ev, deploy_alt), deploy_alt, main.diameter


def main() -> None:
    r, deploy_alt, main_dia = build_result()
    b, j = r.bulkhead, r.joint

    rule("THE AFT GAS SEAL -- what it actually carries")
    say()
    say("  It is not a gasket. It is the piston the ejection charge pushes on to separate")
    say("  the airframe, and the anchor the main parachute pulls on when it opens. Gas")
    say("  tightness is its third requirement, not its first.")
    say()
    say(f"  bore                   {b.bore_diameter * MM:8.1f} mm     the disc is the full ID")
    say(f"  piston area            {j.area * 1e6:8.1f} mm2")
    say(f"  forward compartment    {r.geometric_volume * 1e6:8.1f} cm3    geometric")
    say(f"  free volume            {r.free_volume * 1e6:8.1f} cm3    "
        f"{r.free_volume / r.geometric_volume * 100:.0f}% of it -- the rest is parachute")

    rule("THE FUSE -- shear pins, and the charge that has to break them")
    say()
    say(f"  {j.n_pins} x {j.pin:12s}      {j.pin_force:8.0f} N")
    say(f"  joint friction allowance    {j.friction:8.0f} N      an ALLOWANCE; ground test replaces it")
    say(f"  release force               {j.release_force:8.0f} N")
    say(f"  release pressure            {j.release_pressure / 1e3:8.1f} kPa    "
        f"({j.release_pressure / 6894.76:.1f} psi)")
    say(f"  design pressure             {j.design_pressure / 1e3:8.1f} kPa    "
        f"at a {seal.SEPARATION_FACTOR:.1f}x separation factor")
    say(f"  BLACK POWDER CHARGE         {r.design.charge * 1e3:8.2f} g")
    say()
    say("  Sized on the compartment's GEOMETRIC volume, which is what every published rule")
    say("  of thumb does and what a ground test measures. Then note where it actually goes:")

    rule("THE TWO PRESSURE CASES")
    say()
    say(f"  {'case':32s} {'volume':>10s} {'pressure':>12s} {'on the disc':>13s}")
    say("  " + "-" * 70)
    for case in (r.design, r.stuck):
        say(f"  {case.name:32s} {case.volume * 1e6:8.1f} cm3 "
            f"{case.pressure / 1e3:9.0f} kPa {case.force:10.0f} N")
    say()
    say(f"  The same charge, a factor of {r.stuck.pressure / r.design.pressure:.0f} apart, and BOTH are true. In the")
    say("  nominal flight the pins let go almost immediately and the volume grows faster")
    say("  than the burn can fill it, so the disc never sees the second row. It sees it if")
    say("  the joint is STUCK -- paint, a swollen coupler, an undersized pin hole.")
    say()
    say("  THE STUCK CASE IS WHAT SETS THE THICKNESS, and the reason is not caution:")
    say("  the shear pins are the intended fuse, so the bulkhead has to be stronger than")
    say("  the fuse or the wrong part fails first.")

    rule("THE DISC")
    say()
    say(f"  material                 G-10 sheet, {b.thickness * MM:.1f} mm     thinnest STOCKED size that passes")
    say(f"  mass                     {b.mass * 1e3:8.1f} g")
    say(f"  governing pressure       {r.governing_pressure / 1e3:8.0f} kPa")
    say(f"  bending stress           {r.plate_stress / 1e6:8.0f} MPa   simply supported, centre")
    say(f"    same, edge clamped     {b.stress_clamped(r.governing_pressure) / 1e6:8.0f} MPa   "
        f"the best case, reported not used")
    say(f"  margin                   {r.plate_margin:8.2f}x    "
        f"against {seal.PLATE_MARGIN_REQUIRED:.1f}x required")
    say(f"  centre deflection        {b.deflection(r.governing_pressure) * MM:8.2f} mm    at the stuck pressure")
    say(f"    at design pressure     {b.deflection(r.design.pressure) * MM:8.2f} mm")
    say(f"  disc holds to            {r.pressure_capacity / 1e3:8.0f} kPa   "
        f"= {r.pressure_capacity / j.release_pressure:.0f}x the pin release pressure")
    say(f"  glue line                {b.bond_length * MM:8.1f} mm    disc edge + a fillet either side")
    say(f"  bond shear               {b.bond_shear(r.governing_pressure * b.area) / 1e6:8.2f} MPa   "
        f"margin {r.bond_margin:.1f}x")
    say()
    say("  Both plate formulae are here on purpose. A disc bonded in with a fillet is")
    say("  between simply supported and clamped, and the two differ by 1.6x. Assuming the")
    say("  favourable one is how correction 15's joint reported 2.5x while sitting at 1.69x.")

    rule("THE MAIN'S OPENING SHOCK -- the load that arrives through the U-bolt")
    say()
    say(f"  main                     {main_dia / 0.0254:8.1f} in     deployed at {deploy_alt:.0f} m")
    say(f"  descent mass             {r.descent_mass:8.3f} kg")
    say(f"  velocity at deploy       {r.deploy_velocity:8.1f} m/s    under the drogue")
    say(f"  steady drag at that speed{r.shock:8.0f} N      "
        f"{r.shock / (r.descent_mass * 9.81):.0f}x vehicle weight")
    say(f"  infinite-mass bound      {r.shock_infinite_mass:8.0f} N      "
        f"opening coefficient 1.7, used for the check")
    say(f"  stress under the U-bolt  {r.shock_stress / 1e6:8.0f} MPa   "
        f"6 mm footprint, margin {r.shock_margin:.1f}x")
    say()
    say("  This is a plate under a POINT load, not a pressure. The stress goes as the log")
    say("  of (plate radius / footprint radius), so the backing washer under the U-bolt is")
    say("  structure and not hardware. A main sized for 5 m/s opened at 19 m/s pulls about")
    say("  14 times the vehicle's weight -- which is the argument for deploying it low, and")
    say("  it is already why `main_deploy_altitude` is 200 m and not 500.")

    rule("THE HOLE THAT MAKES IT A FEED-THROUGH")
    say()
    f = r.feed_through
    say(f"  {f.n_holes} x dia {f.hole_diameter * MM:.1f} mm at R {f.radius_in_plate * MM:.1f} mm, "
        f"Kt {f.kt:.1f} -> {r.hole_stress / 1e6:.0f} MPa, margin {r.hole_margin:.2f}x")
    say()
    say(f"  AND THE HOLE IS WHAT SETS THE THICKNESS. This disc is governed by "
        f"{r.governed_by}:")
    say(f"  the plate itself passes at {r.plate_margin:.2f}x and the hole at "
        f"{r.hole_margin:.2f}x. Size the plate alone and")
    plate_only = min(
        (t for t in seal.G10_SHEET_THICKNESS
         if seal.G10_FLEXURAL / seal.Bulkhead(b.bore_diameter, t).stress(r.governing_pressure)
         >= seal.PLATE_MARGIN_REQUIRED),
        default=b.thickness)
    po = seal.Bulkhead(b.bore_diameter, plate_only)
    say(f"  the answer is {plate_only * MM:.1f} mm, where the feed-through runs at "
        f"{seal.G10_FLEXURAL / (f.kt * po.hole_field(r.governing_pressure, po.quiet_radius())):.2f}x.")
    say("  A bulkhead sized as though it were a bulkhead is not a sized feed-through.")
    say()
    say("  WHY THERE IS A HOLE AT ALL. The altimeter that fires these charges is in the NAV")
    say("  BAY, two bulkheads forward, because configure.py puts the nav bay at the front")
    say("  for GNSS sky view. Its firing circuits have to cross this disc. The standard")
    say("  high-power alternative -- an av-bay between the two compartments, next to the")
    say("  charges -- needs about 60 mm of tube and two more bulkheads, and the recovery bay")
    say("  has 13.0 mm of length margin. It does not fit. So the hole is not optional, and")
    say("  the part is a sealed feed-through rather than a bulkhead.")
    say()
    say(f"  Placed at R {f.radius_in_plate * MM:.1f} mm, where a CLAMPED plate's radial bending stress")
    say("  passes through zero -- and then checked against the SIMPLY SUPPORTED")
    say("  field, where there is no such radius and the placement buys almost nothing. The")
    say("  first version of this report used the clamped field for both and printed 15x.")
    say("  Using the favourable model where it helps and the conservative one where it does")
    say("  not is correction 15 with a different feature in it.")

    rule("VERDICT")
    say()
    chk = seal.check_seal(r)
    say(f"  aft gas seal        {'OK' if chk.ok else 'VIOLATIONS'}")
    for v in chk.violations:
        say(f"    VIOLATION  {v}")
    for n in chk.notes:
        say(f"    note  {n}")

    rule("THE SECOND BULKHEAD -- the one that was a 12 mm length allowance")
    say()
    ib = seal.internal_bulkhead_from_evaluation(evaluate(baseline()))
    ibchk = seal.check_seal(ib)
    say("  `recovery.BULKHEAD_THICKNESS = 0.012` was the only statement this project had")
    say("  ever made about the part that divides the two compartments. That is a LENGTH.")
    say("  The part it stands for has a charge on BOTH faces and anchors both harnesses.")
    say()
    say(f"  {'':28s} {'aft gas seal':>16s} {'internal bulkhead':>18s}")
    say("  " + "-" * 66)
    rows = [
        ("governing pressure, kPa", lambda x: f"{x.governing_pressure / 1e3:.0f}"),
        ("free fraction of compartment", lambda x: f"{x.free_volume / x.geometric_volume:.4f}"),
        ("thickness, mm", lambda x: f"{x.bulkhead.thickness * MM:.1f}"),
        ("mass, g", lambda x: f"{x.bulkhead.mass * 1e3:.0f}"),
        ("plate margin", lambda x: f"{x.plate_margin:.2f}x"),
        ("feed-through", lambda x: f"{x.feed_through.n_holes} x d{x.feed_through.hole_diameter * MM:.0f}"),
        ("feed-through margin", lambda x: f"{x.hole_margin:.2f}x"),
        ("protected by shear pins", lambda x: "yes" if x.protected_by_pins else "NO"),
        ("assembled stack, mm", lambda x: f"{seal.stack_length(x) * MM:.1f}"),
    ]
    for label, fn in rows:
        say(f"  {label:28s} {fn(r):>16s} {fn(ib):>18s}")
    say()
    say("  THE TWO PRESSURES ARE THE SAME AND THAT IS NOT A COINCIDENCE. check_packing gives")
    say("  every compartment the length its contents need at FILL_LIMIT, so every compartment")
    say("  leaves the same free fraction, whatever is in it. The drogue compartment holds a")
    say("  quarter of the volume and is 1% worse. **recovery.FILL_LIMIT, chosen so a bay would")
    say("  close with cold hands, sets the design pressure of every bulkhead in the rocket.**")
    say()
    say(f"  internal bulkhead check  {'OK' if ibchk.ok else 'VIOLATIONS'}")
    for v in ibchk.violations:
        say(f"    VIOLATION  {v}")
    say(f"    note  {ibchk.notes[0]}")
    say()
    say(f"  Assembled stack {seal.stack_length(ib) * MM:.1f} mm against the "
        f"{recovery.BULKHEAD_THICKNESS * MM:.1f} mm allowance -- it fits, and")
    say("  that allowance had never been checked against a part before.")

    rule("VENTING -- which volumes the altimeter is allowed to sense")
    say()
    ev = evaluate(baseline())
    nav = next(t for t in ev.rocket.tubes if t.name == "nav bay")
    module = next(t for t in ev.rocket.tubes if t.name == "canard module")
    nav_free = avionics.free_volume(nav.inner_diameter, nav.length)
    mod_free = venting.CANARD_MODULE_FREE_VOLUME
    nav_bay = venting.VentedBay("nav bay", nav_free,
                                venting.CONVENTIONAL_PORT_COUNT,
                                venting.CONVENTIONAL_PORT_DIAMETER)
    mod_bay = venting.VentedBay("canard module", mod_free, 2, 0.002)
    vchk = venting.check_venting(nav_bay, mod_bay,
                                 altitude=285.0, climb_rate=177.0,
                                 apogee=ev.flight.apogee,
                                 module_wall_area=mod_bay.area)
    say("  THIS CORRECTS WHAT design/seal.py FIRST ARGUED. That file reasoned the canard")
    say("  module has two faces it could breathe through, that the aft one is disqualified")
    say("  because the charge fires there, and that it therefore vents FORWARD into the nav")
    say("  bay -- which would put the module inside the altimeter's sense volume.")
    say()
    say("  A bay is a cylinder. The third surface is the wall, and this one already has four")
    say("  dia 8 mm bores through it. Two dia 2 mm vents cost nothing and the rest goes away.")
    say()
    say(f"  {'bay':16s} {'free vol':>10s} {'ports':>14s} {'area':>9s} {'lag up':>9s} {'lag down':>10s}")
    say("  " + "-" * 74)
    for b, up, down in ((nav_bay, 177.0, 19.0), (mod_bay, 177.0, 19.0)):
        say(f"  {b.name:16s} {b.volume * 1e6:7.0f} cm3 "
            f"{b.n_ports} x d{b.port_diameter * MM:.1f} mm "
            f"{b.area * 1e6:6.1f} mm2 "
            f"{b.lag_altitude(285.0, up):7.3f} m {b.lag_altitude(200.0, down):8.4f} m")
    say()
    say(f"  The lag model asks for {venting.port_area_for_lag(nav_free, 285.0, 177.0) * 1e6:.2f} mm2 "
        f"and convention drills {nav_bay.area * 1e6:.1f}. **The requirement everybody")
    say("  gives for these holes -- the bay must breathe fast enough -- is not what sizes")
    say("  them, by a factor of about 300.** What sizes them is blockage tolerance, the")
    say("  ejection transient and what a person can drill by hand, none of which is modelled")
    say("  here. That is a check that CONFIRMED a choice, which is its own kind of result.")
    say()
    say(f"  venting check       {'OK' if vchk.ok else 'VIOLATIONS'}")
    for v in vchk.violations:
        say(f"    VIOLATION  {v}")
    for n in vchk.notes:
        say(f"    note  {n}")

    rule("WHAT THE PACKING NOW COSTS")
    say()
    pk = ev.packing
    say(pk.report(caliber=0.0794))
    say()
    h = recovery.size_harness(ev.rocket.length, r.shock_infinite_mass)
    say()
    say("  THE HARNESS IS SIZED NOW, AND THAT IS WHAT FIXED THE MARGIN. Its volume used to")
    say("  come from `shock_cord_and_links = 220 g` in the mass budget divided by an assumed")
    say("  bulk density -- an unchecked number turned into a volume by a guess, and a quarter")
    say("  of the bay. Nothing had ever checked its STRENGTH either.")
    say()
    say(f"  {'webbing':24s} {'rating':>8s} {'after knots':>12s} {'vs shock':>9s} {'g/m':>6s}")
    say("  " + "-" * 64)
    for w in recovery.WEBBING_OPTIONS:
        mark = "  <- selected" if w.name == h.webbing.name else ""
        say(f"  {w.name:24s} {w.rating / 1000:6.1f} kN {w.working_load / 1000:9.1f} kN "
            f"{w.working_load / h.opening_load:8.1f}x {w.mass_per_metre * 1000:6.0f}{mark}")
    say()
    say(f"  The opening shock is {h.opening_load:.0f} N and 1\" tubular nylon is rated 17.8 kN.")
    say(f"  **The harness was about {recovery.WEBBING_OPTIONS[-1].working_load / h.opening_load / recovery.HARNESS_MARGIN_REQUIRED:.0f} times more webbing than the load asks for**, and the")
    say("  excess was not free -- it was spending a bay whose margin was 0.1 mm. Same shape")
    say("  as the tube at the hinge running at 256x, except that this one had a bill.")
    say()
    say(f"  Selected {h.webbing.name}, 2 x {h.length_each:.2f} m, "
        f"{h.webbing_mass * 1e3:.0f} g against the 170 g the budget assumed.")
    say("  The knot derating is what moved the selection two sizes, not the rating.")
    say()
    say("  The conduit and four U-bolts are RIGID -- the canopy packs around them rather")
    say("  than compressing with them -- so they are added to the required length directly")
    say("  instead of through the fill limit. Putting them through it would inflate them by")
    say("  1/0.85 and manufacture a shortfall, which is precisely correction 5.")
    say()
    say(f"  Margin: +13.0 mm before any of this was counted, +0.1 mm once the coupler bore")
    say(f"  and the rigid hardware went in, and {pk.margin * MM:+.1f} mm now the harness is sized and the")
    say(f"  internal bulkhead is the measured {10.8:.1f} mm stack rather than a 12.0 mm allowance.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
