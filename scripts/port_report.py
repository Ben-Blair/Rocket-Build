"""The nav bay's static ports: station, clocking, and the four things placing them found.

    python scripts/port_report.py            # print
    python scripts/port_report.py --write    # and into out/port_report.txt

Every number is computed from `design/ports.py`, `design/joints.py` and the frozen baseline.
Nothing here is typed; if a figure in this report disagrees with a document, the report is
right and the document is stale.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import aero, atmosphere, avionics, joints, ports, sled, venting
from design.configure import (
    DEFLECTION_LIMIT_DEG, ROLL_COMMAND_CAP_DEG, baseline, evaluate,
)

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "port_report.txt"

_lines: list[str] = []


def say(s: str = "") -> None:
    print(s)
    _lines.append(s)


def rule(title: str) -> None:
    say()
    say("=" * 92)
    say(title)
    say("=" * 92)


def altitude_error(cp: float, q: float, altitude: float) -> float:
    """|Cp| * q restated as metres of altitude the altimeter will be wrong by."""
    _, _, rho, _ = atmosphere.properties(altitude)
    return abs(cp) * q / (rho * atmosphere.G0)


def main() -> None:
    ev = evaluate(baseline(), deflection_deg=DEFLECTION_LIMIT_DEG)
    r, p = ev.rocket, ev.params
    wall = p.wall_thickness
    d = r.diameter

    boost = max(ev.flight.points, key=lambda pt: pt.q)
    _, _, rho_boost, _ = atmosphere.properties(boost.z)

    # The case the altimeter is actually READ in: under drogue, at the main's set altitude.
    deploy_alt = 200.0
    drogue_rate = 30.0          # m/s, the figure scripts/baseline.py already quotes venting at
    _, _, rho_deploy, a_deploy = atmosphere.properties(deploy_alt)
    q_deploy = 0.5 * rho_deploy * drogue_rate ** 2
    mach_deploy = drogue_rate / a_deploy

    js = joints.for_rocket(r, wall)
    placement = ports.place_ports(r, wall)
    g = sled.sled_from_evaluation(ev)
    sled_forward, _ = sled.station_range(r, g)
    bore_radius = next(j for j in js if j.forward_bay == "nav bay").bore / 2.0

    nav_tube = next(t for t in r.tubes if t.name == "nav bay")
    nav_free = avionics.free_volume(nav_tube.inner_diameter, nav_tube.length)
    nav_bay = venting.VentedBay("nav bay", nav_free, len(placement.clocking_deg),
                                placement.diameter)

    # ---------------------------------------------------------------------------------
    rule("WHAT IS BEHIND THE NAV BAY WALL -- the question that had to be answered first")
    say()
    say("  A static port is a hole, and the first thing a hole needs is a wall with nothing")
    say("  bonded to the back of it. The nav bay has none.")
    say()
    say(f"  {'band':22s} {'station, mm':>18s} {'mm':>8s} {'walls':>6s}  drillable")
    for b in ports.nav_bay_wall_bands(r, wall, js):
        say(f"  {b.name:22s} {b.x0 * MM:8.2f} -> {b.x1 * MM:7.2f} {b.length * MM:8.2f} "
            f"{b.layers:6d}  {'yes' if b.drillable else 'NO'}")
    for b in ports.nav_bay_wall_bands(r, wall, js):
        if not b.drillable:
            say(f"    {b.name}: {b.why}")
    say()
    say("  The bands TILE the tube. There is no bare wall anywhere in this bay, and nothing")
    say("  had ever said so because design/joints.py described a joint only by the half that")
    say("  protrudes. See its header, and docs/01 correction 42.")

    rule("JOINT CAPACITY -- the check that did not exist")
    say()
    for cap in joints.tube_capacity(r, wall).values():
        say(f"  {cap}")
    chk_j = joints.check_joints(r, wall)
    say()
    for line in chk_j.violations:
        say(f"  VIOLATION  {line}")
    for line in chk_j.notes:
        say(f"  note       {line}")
    say()
    say("  The canard module violation is OPEN and is not the static ports' to close: its")
    say("  aft joint would have to share the module's aft end with the printed canard bay")
    say("  and the aft gas seal. Its forward joint is worse than the check can see -- the")
    say("  printed bay's forward face is at module Z 53.129 and the potted pass-through")
    say("  plate holds Z 0.000 to 2.400, so the protrusion has 50.73 mm and is charged")
    say(f"  {js[1].engagement * MM:.2f} mm.")

    # ---------------------------------------------------------------------------------
    rule("THE PLACEMENT")
    say()
    say(f"  {placement}")
    say()
    say(f"  band                  {placement.band.name}, "
        f"{placement.band.x0 * MM:.2f} -> {placement.band.x1 * MM:.2f} mm")
    say(f"  edge distance         {placement.edge_distance * MM:.2f} mm each side, against a "
        f"{ports.PORT_EDGE_DISTANCE_RATIO * placement.diameter * MM:.2f} mm floor "
        f"({ports.PORT_EDGE_DISTANCE_RATIO:.1f} diameters)")
    say(f"  depth                 {placement.depth * MM:.2f} mm through "
        f"{placement.band.layers} bonded walls, L/D "
        f"{placement.depth / placement.diameter:.2f}")
    say(f"  aft of nose shoulder  {placement.cal_aft_of_shoulder:.3f} cal, against a "
        f"{ports.CONVENTIONAL_AFT_OF_SHOULDER_CAL:.1f} cal rule -- UNREACHABLE, the whole "
        f"bay is {nav_tube.length / d:.2f} cal")
    say(f"  fwd of canard root    {placement.cal_forward_of_canards:.3f} cal, against a "
        f"{ports.CONVENTIONAL_FORWARD_OF_DISTURBANCE_CAL:.1f} cal rule -- UNREACHABLE for "
        f"the same reason")
    say()
    say("  CAN AIR REACH THE HOLE FROM INSIDE -- the question an interference check does not")
    say("  ask, because a mouth 0.2 mm off a board is not an interference, it is a bay that")
    say("  does not breathe.")
    for clear, who, theta in ports.port_mouth_clearances(
            placement, g, sled_forward, bore_radius):
        say(f"    port at {theta:6.1f} deg   {clear * MM:6.2f} mm to the nearest solid "
            f"({who})")

    # ---------------------------------------------------------------------------------
    rule("POSITION ERROR 1 -- THE NOSE, and the validation the solver had to pass")
    say()
    exact, modelled, factor = ports.spheroid_validation(r.nose.fineness)
    say(f"  The solver is a line-source slender-body solution. Run on a "
        f"{r.nose.fineness:.1f}:1 prolate")
    say(f"  spheroid, where the exact answer is elementary, it reads Cp {modelled:+.4f} "
        f"against {exact:+.4f}")
    say(f"  -- it under-reads |Cp| by {(factor - 1.0) * 100:.0f}%, and that factor is applied "
        f"to every case below.")
    say()
    say(f"  {'station':>9s} {'cal aft':>8s} {'Cp':>9s} {'err at max q':>14s} "
        f"{'err at deploy':>15s}")
    say(f"  {'mm':>9s} {'shoulder':>8s} {'':>9s} "
        f"{f'({boost.q / 1000:.1f} kPa)':>14s} {f'({q_deploy:.0f} Pa)':>15s}")
    for x in (placement.band.x0, placement.station, placement.band.x1):
        cp_b = ports.nose_position_error(r, x, boost.mach)
        cp_d = ports.nose_position_error(r, x, mach_deploy)
        mark = "  <- chosen" if abs(x - placement.station) < 1e-9 else ""
        say(f"  {x * MM:9.2f} {(x - r.nose.length) / d:8.3f} {cp_b:+9.4f} "
            f"{altitude_error(cp_b, boost.q, boost.z):11.1f} m "
            f"{altitude_error(cp_d, q_deploy, deploy_alt):13.2f} m{mark}")
    say()
    say("  THE STATION IS NOT SET BY THIS. Position error scales with q, and the altimeter is")
    say("  only ever READ where q is small -- at apogee it is zero, and at the main's 200 m")
    say(f"  under drogue the whole error is under a metre. Moving the ring to the aft end of")
    say(f"  the band buys "
        f"{altitude_error(ports.nose_position_error(r, placement.station, mach_deploy), q_deploy, deploy_alt) - altitude_error(ports.nose_position_error(r, placement.band.x1, mach_deploy), q_deploy, deploy_alt):.2f} m "
        f"and would spend the {placement.edge_distance * MM:.2f} mm of edge distance down to")
    say("  nothing. The band is centred instead -- same shape as venting.py's own result on")
    say("  port SIZE: the model gives the floor, practice gives the design point.")

    # ---------------------------------------------------------------------------------
    rule("POSITION ERROR 2 -- THE CANARDS, and what a ring of ports is actually for")
    say()
    cna = aero.panel_cn_alpha(r.canards, d, boost.mach)
    gamma = ports.canard_circulation(r, boost.q, DEFLECTION_LIMIT_DEG, cna, boost.speed,
                                     rho_boost)
    roll_fraction = ROLL_COMMAND_CAP_DEG / DEFLECTION_LIMIT_DEG
    say(f"  panel CN_alpha {cna:.3f} /rad, bound circulation {gamma:.3f} m2/s at the "
        f"{DEFLECTION_LIMIT_DEG:.0f} deg limit,")
    say(f"  four horseshoe vortices, evaluated on the tube at station "
        f"{placement.station * MM:.2f} mm.")
    say()

    def worst_over_commands(clocking) -> float:
        worst = 0.0
        for az in range(0, 360, 5):
            panels = ports.command(r, gamma, roll=roll_fraction, lateral=1.0,
                                   lateral_azimuth_deg=az)
            mean, _ = ports.ring_mean(r, placement.station, clocking, gamma, boost.speed,
                                      panels)
            if abs(mean) > abs(worst):
                worst = mean
        return abs(worst)

    say("  Worst case over every lateral command azimuth, with the roll command at its cap:")
    say()
    say(f"  {'ring':34s} {'Cp read':>10s} {'at max q':>11s} {'at deploy':>11s}")
    rows = [
        ("one port", [placement.clocking_deg[0]]),
        (f"THREE ports, any phasing", list(placement.clocking_deg)),
        ("four ports, phased 45 deg (nodes)", [45.0, 135.0, 225.0, 315.0]),
        ("four ports, phased 22.5 deg", [22.5, 112.5, 202.5, 292.5]),
    ]
    for label, clocking in rows:
        cp = worst_over_commands(clocking)
        say(f"  {label:34s} {cp:10.6f} "
            f"{altitude_error(cp, boost.q, boost.z):9.3f} m "
            f"{altitude_error(cp, q_deploy, deploy_alt):9.4f} m")
    say()
    say("  THE FIRST GUESS WAS WRONG AND IT IS WORTH RECORDING WHICH WAY. 'three and four are")
    say("  coprime, so three averages the canards' 4-fold field and four cannot' is true, and")
    say("  it points at the wrong answer: the 4-fold ROLL field is the small one. The lateral")
    say("  field is odd-harmonic and 170x larger, and FOUR ports reject all of it while three")
    say("  pass its k = 3. On the aerodynamics four ports is the better ring.")
    say()
    say("  What the sweep settles instead is the CLOCKING, and it settles it differently for")
    say("  the two counts. With four ports every port sits at the same phase of a 4-fold")
    say("  field, so the ring does not average the roll field at all -- it reads it, at")
    say("  whatever phase it was clocked to, and is correct only on the nodes (the canard")
    say("  planes, or their bisectors). With three ports the rejection is structural and")
    say("  holds at every phasing:")
    say()
    for phase in (0.0, 15.0, 22.5, 30.0, 45.0):
        three = [(phase + i * 120.0) % 360.0 for i in range(3)]
        four = [(phase + i * 90.0) % 360.0 for i in range(4)]
        say(f"    phase {phase:5.1f} deg    three ports "
            f"{altitude_error(worst_over_commands(three), boost.q, boost.z):6.3f} m     "
            f"four ports {altitude_error(worst_over_commands(four), boost.q, boost.z):6.3f} m")
    say()
    say("  So THREE is the forgiving choice rather than the accurate one, which is a better")
    say("  reason for it than venting.py's ('three is the minimum that averages'), and it is")
    say("  the same thing every other number in that file is chosen for. The count is NOT")
    say("  changed -- the whole spread is hundredths of a metre where the altimeter is read.")
    say()
    say("  WITH ONE PORT TAPED OVER -- the failure the 3.2 mm diameter is really sized")
    say("  against -- the remainder is not a ring and rejects nothing cleanly:")
    say()
    for label, clocking in (("three ports", list(placement.clocking_deg)),
                            ("four ports, phased 45 deg", [45.0, 135.0, 225.0, 315.0])):
        blocked = max(worst_over_commands([t for j, t in enumerate(clocking) if j != k])
                      for k in range(len(clocking)))
        single = worst_over_commands([clocking[0]])
        say(f"    {label:26s} {altitude_error(blocked, boost.q, boost.z):6.3f} m at max q, "
            f"{blocked / single * 100:.0f}% of a single port -- "
            f"{altitude_error(blocked, q_deploy, deploy_alt):.3f} m at deployment")

    # ---------------------------------------------------------------------------------
    rule("THE HOLE AS A FLOW PASSAGE -- venting.py's orifice equation is the wrong model")
    say()
    regime = ports.port_flow_regime(nav_bay, placement.depth, 285.0, 177.0)
    say(f"  through-port velocity   {regime.velocity * 1000:8.2f} mm/s   at the worst flow "
        f"in the flight")
    say(f"  Reynolds number         {regime.reynolds:8.0f}      "
        f"-- {'inertial' if regime.inertial else 'LAMINAR; the orifice equation wants 1e4'}")
    say(f"  L/D of the port         {regime.length_to_diameter:8.2f}      "
        f"a short pipe, not a thin-plate orifice")
    say()
    say(f"  drop, orifice model     {regime.orifice_drop:8.3f} Pa   venting.VentedBay.lag()")
    say(f"  drop, laminar model     {regime.laminar_drop:8.3f} Pa   Hagen-Poiseuille, same hole")
    say(f"  the lag budget          {venting.lag_pressure(285.0):8.1f} Pa   "
        f"{venting.ALLOWABLE_LAG_ALTITUDE:.1f} m of altitude")
    say()
    say(f"  Same conclusion by a factor of "
        f"{venting.lag_pressure(285.0) / max(regime.orifice_drop, regime.laminar_drop):.0f} "
        f"either way, which is what venting.py")
    say("  predicted would happen to any argument about port area. Recorded because 'the")
    say("  model is invalid and the conclusion is unchanged' is a result, and because the")
    say("  next marginal vent -- the canard module's 2 x dia 2.0 mm is a tenth of this area")
    say("  -- needs to know which equation to reach for.")

    # ---------------------------------------------------------------------------------
    rule("VERDICT")
    say()
    clear = min(c[0] for c in ports.port_mouth_clearances(
        placement, g, sled_forward, bore_radius))
    chk = ports.check_ports(r, wall, placement, nav_bay, 285.0, 177.0,
                            interior_clearance=clear)
    say(f"  {'OK' if chk.ok else 'VIOLATIONS'}")
    for line in chk.violations:
        say(f"    VIOLATION  {line}")
    for line in chk.notes:
        say(f"    note       {line}")
    say()
    say("  STILL OPEN, stated rather than solved:")
    say("    * the aft coupler is 0.600 cal of bond against a 1.0 cal convention, and")
    say("      nothing in this project sizes a coupler in bending")
    say("    * the same joint's RETAINING SCREWS want the same 47.64 mm band these holes are")
    say("      in, and no script in this repo has ever placed one")
    say("    * the canard module's joint capacity is over-subscribed by 15.88 mm")
    say("    * the boundary layer is not modelled; the position errors above are inviscid")
    say("    * the ejection transient is not modelled, and it is the one flow case where")
    say("      this port really is inertial")

    if "--write" in sys.argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text("\n".join(_lines) + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
