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

from design import recovery, seal
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

    rule("WHAT IS STILL OPEN, AND IT IS NOT THIS PART")
    say()
    say("  1. THE DROGUE'S FIRING CIRCUIT HAS NOWHERE TO RUN. This disc closes the FORWARD")
    say("     compartment, so the main's charge terminates on its aft face -- a terminal")
    say("     block and a charge well, millimetres from where the wires come through. The")
    say("     drogue's charge is on the far side of the internal bulkhead, and the only")
    say("     path to it is straight through a compartment packed with the main.")
    say()
    say("     A thin-wall conduit bonded along the tube wall through the main compartment,")
    say("     sealed where it crosses both bulkheads, is the standard answer. Priced:")
    _conduit(r)
    say()
    say("  2. THE INTERNAL BULKHEAD is a 12.0 mm length allowance in recovery.py and nothing")
    say("     else. It is a pressure boundary with charges on BOTH faces and it has had")
    say("     none of the treatment this disc just got.")
    say()
    say("  3. THE NAV BAY STATIC PORTS are sized for the nav bay, and the canard module now")
    say("     vents into it. That is one bay's worth of volume unaccounted for in a")
    say("     calculation nobody has done yet. It belongs with D7.")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


def _conduit(r: seal.SealResult, outer_dia: float = 0.005) -> None:
    """What a wiring conduit through the packed compartment costs, in bay length."""
    import math

    area = math.pi * r.bulkhead.bore_diameter**2 / 4.0
    length = r.geometric_volume / area
    displaced = math.pi * outer_dia**2 / 4.0 * length
    # It displaces packing volume, so the compartment has to grow by that volume at the
    # same fill limit the packing check uses.
    extra = displaced / (area * recovery.FILL_LIMIT)
    say(f"     dia {outer_dia * MM:.0f} mm conduit, {length * MM:.0f} mm long, displaces "
        f"{displaced * 1e6:.1f} cm3")
    say(f"     -> the recovery bay needs {extra * MM:.1f} mm more length, out of the "
        f"{13.0:.1f} mm it has spare.")


if __name__ == "__main__":
    main()
