"""Full analysis of the baseline vehicle, and the numbers to type into OpenRocket.

Run:  python scripts/baseline.py
      python scripts/baseline.py --plot
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import (
    access_bulkhead, aero, avionics, control, estimation, flight_computer, flutter, hinge,
    joints, motor_mount, pcb_placement, ports, recovery_hardware, seal, sled, trajectory,
    tube_section, venting,
)
# Aliased because `bay` is a local in main() -- check_direct_drive's result. Same reason
# design/configure.py imports mass as mass_mod.
from design import atmosphere
from design import bay as bay_mod
from design.configure import (
    DEFLECTION_LIMIT_DEG, ROLL_COMMAND_CAP_DEG, baseline, build_vehicle, evaluate,
)
from design import recovery
from design.packaging import (
    CP_FRAC_CFD_INFORMED, SERVO_GEOMETRY, SERVOS, check_direct_drive, check_flat_mount,
    torque_margin,
)

ROOT = Path(__file__).resolve().parents[1]

# The frozen airframe and motor both live in design/configure.py. Import, never copy.
BASELINE = baseline()
MOTOR = BASELINE.motor

# Servo is part of the frozen design now -- see design/configure.py.
SERVO_CHOICE = BASELINE.servo
# Free air in the canard module -- tube volume less the servos, printed bay, shafts and
# bearings. Lives in design/venting.py now; it had drifted into two scripts as two copies of
# the same guess.
CANARD_MODULE_FREE_VOLUME = venting.CANARD_MODULE_FREE_VOLUME
# Roll control needs far less deflection than pitch/yaw, because roll inertia is tiny --
# and D8 found that it is also what keeps the rate gyro inside its range, so both limits now
# live in design/configure.py rather than here. See design/estimation.py.
ROLL_DEFLECTION_DEG = ROLL_COMMAND_CAP_DEG
GEAR_RATIO = 1.0


def rule(title: str = "", width: int = 92) -> None:
    if title:
        print("\n" + "=" * width)
        print(title)
        print("=" * width)
    else:
        print("-" * width)


def main() -> None:
    ev = evaluate(BASELINE, deflection_deg=DEFLECTION_LIMIT_DEG)
    r, f, m = ev.rocket, ev.flight, ev.masses
    d = r.diameter

    rule("BASELINE VEHICLE")
    print(f"  airframe            {d * 1000:.1f} mm OD fiberglass, {r.length * 1000:.0f} mm long, "
          f"L/D {r.fineness:.1f}")
    print(f"  motor               {BASELINE.motor.name}  "
          f"({BASELINE.motor.total_impulse:.0f} N s, class {BASELINE.motor.impulse_class}, "
          f"needs L{BASELINE.motor.requires_level})")
    if BASELINE.motor.approximate:
        print("                      ^ PLACEHOLDER motor. Replace with a real .eng curve.")
    print(f"  wet / dry mass      {m.wet_mass:.2f} / {m.dry_mass:.2f} kg")
    print(f"  feasible            {'YES' if ev.feasible else 'NO: ' + '; '.join(ev.violations)}")
    for w in ev.warnings:
        print(f"  WARNING             {w}")

    rule("GEOMETRY  (stations measured from nose tip)")
    print(f"  nose cone           {r.nose.shape}, {r.nose.length * 1000:.0f} mm "
          f"(fineness {r.nose.fineness:.1f}), CP at {r.nose.cp_station * 1000:.0f} mm")
    x = r.nose.length
    for t in r.tubes:
        print(f"  {t.name:19s} {t.length * 1000:6.0f} mm   station "
              f"{x * 1000:6.0f} -> {(x + t.length) * 1000:6.0f} mm   ID {t.inner_diameter * 1000:.1f} mm")
        x += t.length
    for fins, label in ((r.canards, "canards"), (r.aft_fins, "aft fins")):
        print(f"  {label:19s} {fins.count} panels, root {fins.root_chord * 1000:.1f} / "
              f"tip {fins.tip_chord * 1000:.1f} / semispan {fins.semispan * 1000:.1f} mm, "
              f"sweep {fins.sweep_length * 1000:.1f} mm")
        print(f"  {'':19s} root LE at {fins.x_root_le * 1000:.0f} mm, "
              f"CP at {fins.cp_station * 1000:.0f} mm")

    rule("MASS BUDGET")
    print(m.report())

    rule("FLIGHT")
    print(f.summary())
    t0, t1 = trajectory.coast_window(f)
    print(f"  usable control window {t1 - t0:7.1f} s (q > 500 Pa after burnout)")

    rule("STATIC STABILITY at max coast dynamic pressure")
    pt = max((p for p in f.points if p.t >= f.burnout_time), key=lambda p: p.q)
    stab = aero.stability(r, pt.cg, pt.mach)
    print(f"  {'component':16s} {'CNa (/rad)':>12s} {'CP (mm)':>10s} {'share':>8s}")
    for name, (cna, cp) in sorted(stab.contributions.items(), key=lambda kv: -kv[1][0]):
        print(f"  {name:16s} {cna:12.2f} {cp * 1000:10.0f} {cna / stab.cn_alpha * 100:7.1f}%")
    print(f"  {'TOTAL':16s} {stab.cn_alpha:12.2f} {stab.cp_station * 1000:10.0f}")
    print(f"\n  CG {pt.cg * 1000:.0f} mm, CP {stab.cp_station * 1000:.0f} mm, "
          f"static margin {stab.static_margin_cal:.2f} cal")
    print(f"  Cm_alpha {stab.cm_alpha:.1f} /rad")
    print(f"  same airframe with canards removed: {ev.sm_without_canards:.2f} cal")
    print(f"  --> the canards cost {ev.sm_without_canards - stab.static_margin_cal:.2f} cal of "
          f"static margin. That is the price of control authority,\n"
          f"      and it is why you cannot simply make the canards bigger.")

    rule("PITCH AUTHORITY vs DEFLECTION")
    print(f"  {'delta':>6s} {'a_trim':>8s} {'lat accel':>10s} {'canard a':>9s} "
          f"{'hinge Nm':>9s} {'wn (Hz)':>8s}  stall")
    for delta in (2.0, 4.0, 6.0, 8.0, 10.0, 12.0):
        a = control.pitch_authority(r, pt, pt.mass, delta)
        print(f"  {delta:5.0f}d {a.alpha_trim_deg:7.2f}d {a.lateral_accel_g:9.2f}g "
              f"{a.canard_local_alpha_deg:8.2f}d {abs(a.hinge_moment_per_panel):9.4f} "
              f"{a.pitch_natural_freq_hz:8.2f}  {'STALL' if a.stalled else 'ok'}")
    print(f"\n  Cm_delta {control.pitch_authority(r, pt, pt.mass, 8.0).cm_delta:.2f} /rad")
    print(f"  one-sided manoeuvre crossrange at {DEFLECTION_LIMIT_DEG:.0f} deg: "
          f"{ev.crossrange:.0f} m over {ev.control_seconds:.1f} s")

    rule("ROLL AUTHORITY  --  the canard / aft-fin interference problem")
    for label, interf in (("aligned (0 deg offset)", control.InterferenceModel.aligned()),
                          ("interdigitated (45 deg)", control.InterferenceModel.interdigitated())):
        roll = control.roll_authority(r, pt, pt.mass, ROLL_DEFLECTION_DEG, interf)
        print(f"\n  {label}")
        print(f"    canard-to-fin spacing      {roll.spacing_cal:8.2f} cal")
        print(f"    interference strength      {roll.interference_strength:8.3f}")
        print(f"    Cl_delta from canards      {roll.cl_delta_canard:+8.3f} /rad")
        print(f"    Cl_delta from aft fins     {roll.cl_delta_aftfin:+8.3f} /rad  (opposing)")
        print(f"    Cl_delta NET               {roll.cl_delta_net:+8.3f} /rad")
        cancel = abs(roll.cl_delta_aftfin) / abs(roll.cl_delta_canard) * 100.0
        print(f"    cancellation               {cancel:8.1f}% of canard authority lost")
        print(f"    SIGN {'REVERSED -- commanded roll produces opposite roll!' if roll.reversed_sign else 'correct'}")
        print(f"    Cl_p (roll damping)        {roll.cl_p:+8.2f} /rad")
        print(f"    roll accel at {ROLL_DEFLECTION_DEG:.0f} deg      "
              f"{roll.roll_accel_deg_s2:8.0f} deg/s^2")
        print(f"    steady roll rate           {roll.steady_roll_rate_deg_s:8.0f} deg/s")

    print("\n  Sensitivity: where does the net roll moment change sign?")
    print("  Sweeping aft fin semispan (which sets how much fin area sits in the canard")
    print("  wake) against interference strength, aligned canards:\n")
    print(f"    {'aft span':>9s} {'SM':>6s} {'Cl_d can':>9s} {'Cl_d fin':>9s} "
          f"{'net':>8s} {'lost':>7s}  verdict")
    for aft_span in (0.85, 1.05, 1.25, 1.45, 1.65, 1.85):
        from dataclasses import replace as _replace

        probe = build_vehicle(_replace(BASELINE, aft_semispan_cal=aft_span))
        stab_p = aero.stability(probe, pt.cg, pt.mach)
        roll_p = control.roll_authority(
            probe, pt, pt.mass, ROLL_DEFLECTION_DEG, control.InterferenceModel.aligned()
        )
        lost = abs(roll_p.cl_delta_aftfin) / abs(roll_p.cl_delta_canard) * 100.0
        verdict = "REVERSED" if roll_p.reversed_sign else ("fragile" if lost > 70 else "ok")
        print(f"    {aft_span:9.2f} {stab_p.static_margin_cal:6.2f} "
              f"{roll_p.cl_delta_canard:+9.3f} {roll_p.cl_delta_aftfin:+9.3f} "
              f"{roll_p.cl_delta_net:+8.3f} {lost:6.1f}%  {verdict}")
    print("""
  Read this table carefully -- it is the core engineering argument of the project. Growing
  the aft fins raises static margin (good for a safe flight) while simultaneously feeding
  more fin area into the canard wake (bad for roll control). Push far enough and the net
  roll moment reverses: you command right roll and the vehicle rolls left. Any controller
  tuned on the assumed sign then saturates and diverges.

  Two things follow:
    1. Interdigitating the canards at 45 deg is not a cosmetic choice. It cuts the
       opposing term by roughly a factor of four in this model and moves the design well
       away from the reversal boundary.
    2. Because the interference factors are the least trustworthy numbers in this whole
       analysis, the first powered flight must measure them. Fly an open-loop deflection
       sweep, log commanded deflection against measured roll rate, and fit the sign and
       magnitude of Cl_delta before you ever close the loop.""")

    rule("ACTUATOR CHECK")
    servo = SERVOS[SERVO_CHOICE]
    bay = check_direct_drive(r.tubes[1].inner_diameter, servo, BASELINE.n_canards)
    geom = SERVO_GEOMETRY.get(SERVO_CHOICE)
    seat = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness,
                          geom).servo_output_face if geom else None
    flat = check_flat_mount(r.tubes[1].inner_diameter, servo, BASELINE.n_canards,
                            geometry=geom, seat_radius=seat)
    case_only = check_flat_mount(r.tubes[1].inner_diameter, servo, BASELINE.n_canards,
                                 geometry=geom, include_cable_boss=False)
    print(f"  servo               {servo.name}")
    print(f"  packaging (as built) {flat}")
    print(f"  packaging (case only) {case_only}")
    print(f"  packaging (old bound) {bay}")
    print("  -> The servo lies flat against the wall, shaft radial through it. The shaft")
    print("     runs along the 16.8 mm case axis, so THAT is what eats radius; the 8 mm")
    print("     thickness is what stacks around the circumference. Read off the KST")
    print("     dimensioned drawing, not assumed.")
    print("     Packaging still is not binding -- but the central void is 12 mm, measured")
    print("     off where the servo actually seats (R 33.185, 4 mm inboard of the wall to")
    print("     make room for the hinge bearing), over the 8.2 mm band where the cable")
    print("     bosses sit. The case-only line is the same band without the boss. The")
    print("     wiring lives in that void.")
    print("     The last line is the superseded 'body pointing inward' bound, kept only")
    print("     because it is conservative.")
    if geom is not None:
        print(f"  shaft, off case centre {geom.shaft_offset_from_centre * 1000:+.2f} mm "
              f"({geom.shaft_from_end * 1000:.2f} mm from the near end, not "
              f"{geom.case_length * 500:.2f})")
        print(f"  spline above flange {geom.shaft_proud_of_flange * 1000:.2f} mm, "
              f"against {r.tubes[1].wall_thickness * 1000:.1f} mm of wall to cross")
        print(f"  servo travel        +/-{math.degrees(geom.travel_half_angle):.0f} deg, "
              f"so +/-{DEFLECTION_LIMIT_DEG:.0f} deg of canard uses "
              f"{DEFLECTION_LIMIT_DEG / math.degrees(geom.travel_half_angle) * 100:.0f}% of it")
    worst_pt, worst = max(
        ((p, control.pitch_authority(r, p, p.mass, DEFLECTION_LIMIT_DEG))
         for p in f.points if p.q > 100),
        key=lambda pair: abs(pair[1].hinge_moment_per_panel),
    )
    margin = torque_margin(worst.hinge_moment_per_panel, servo, GEAR_RATIO)
    hm = worst.hinge_moment_per_panel
    balance = "restoring (hinge fwd of panel CP)" if hm > 0 else "DIVERGENT (hinge aft of panel CP)"
    print(f"  peak hinge moment   {abs(hm):.4f} N m per panel "
          f"at q = {worst.dynamic_pressure / 1000:.1f} kPa")
    print(f"  hinge balance       {balance}")
    print(f"  usable servo torque {servo.stall_torque * 0.4 * GEAR_RATIO:.4f} N m "
          f"(stall x 0.4 derate, gear {GEAR_RATIO:.1f}:1)")
    print(f"  torque margin       {margin:.1f}x  {'OK' if margin > 2.0 else 'MARGINAL'}"
          f"  (design cp_frac=0.25)")
    hm_cfd = worst.hinge_moment_per_panel_cfd
    margin_cfd = torque_margin(hm_cfd, servo, GEAR_RATIO)
    print(f"  torque margin       {margin_cfd:.2f}x  "
          f"{'OK' if margin_cfd > 2.0 else 'MARGINAL' if margin_cfd > 1.0 else 'FAIL'}"
          f"  CFD-INFORMED, interim (cp_frac={CP_FRAC_CFD_INFORMED}, docs/15 A2/B1 -- SU2 and")
    print(f"                      VLM independently put the canard CP at 0.33-0.36 MAC, not "
          f"0.25; NOT bench-verified, see docs/15 C1)")

    # The hinge is a MECHANISM, and the torque margin above is only its easiest question.
    # The same panel that makes 0.06 N m about the hinge makes 25 N at the bearing, and
    # the bearing is 29 mm away. See design/hinge.py and scripts/hinge_report.py.
    stack = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, geom)
    hl = hinge.hinge_loads(stack, hm, r.canards.mean_chord,
                           r.diameter / 2.0 + hinge.spanwise_centroid(
                               r.canards.root_chord, r.canards.tip_chord,
                               r.canards.semispan),
                           servo.stall_torque, geom.spline_teeth)
    chk = hinge.check_hinge_stack(stack, hl)
    print(f"  panel normal force  {hl.normal_force:.1f} N, so {hl.moment_at_wall:.3f} N m "
          f"of bending where the shaft leaves the tube")
    print(f"  hinge bearing       dia {stack.journal_dia * 1000:.0f} journal in a "
          f"{stack.bearing_length * 1000:.1f} mm plain bearing, "
          f"{hl.bearing_pressure / 1e6:.0f} MPa peak, margin {hl.bearing_margin:.1f}x")
    print(f"  hinge fits          running clearance "
          f"{stack.running_clearance * 1000:.3f} mm, spline engagement "
          f"{stack.spline_engagement * 1000:.3f} mm "
          f"({stack.spline_engagement_fraction * 100:.0f}%)")
    print(f"  hinge stack         {'OK' if chk.ok else 'VIOLATIONS: ' + '; '.join(chk.violations)}")

    # The last link: how the shaft meets the panel. The moment is at its MAXIMUM here --
    # the bearing has not taken it out yet -- and the panel is 3.0 mm of G10.
    joint = hinge.selected_root_joint(stack, r.canards)
    jl = hinge.root_joint_loads(joint, hl.normal_force,
                                r.diameter / 2.0 + hinge.spanwise_centroid(
                                    r.canards.root_chord, r.canards.tip_chord,
                                    r.canards.semispan),
                                servo.stall_torque)
    jchk = hinge.check_root_joint(joint, jl)
    print(f"  root joint          {joint.tang_thickness * 1000:.1f} x "
          f"{joint.tang_width * 1000:.1f} mm tang, {joint.engagement * 1000:.1f} mm engaged; "
          f"tang {min(jl.tang_margin.values()):.1f}-{max(jl.tang_margin.values()):.1f}x, "
          f"skin {hinge.G10_FLEXURAL / jl.skin_bending_stress:.1f}x, "
          f"LE clearance {joint.leading_edge_clearance * 1000:.1f} mm")
    print(f"  root joint check    {'OK' if jchk.ok else 'VIOLATIONS: ' + '; '.join(jchk.violations)}")

    # And the structure all of it is cut into. Four dia 8 bores at one station in a 2.3 mm
    # wall is a 13% net-section loss that nothing had ever priced.
    station = hinge.canard_hinge_station(r)
    cut = tube_section.CutStation(station, r.diameter, r.tubes[1].wall_thickness,
                                  stack.wall_bore_dia, r.canards.count, r.tubes[1].name)
    sl = tube_section.canard_module_loads(
        r, m, f, aero.stability(r, worst_pt.cg, mach=worst_pt.mach), station,
        panel_normal_force=hl.normal_force,
        panel_cp_radius=r.canards.spanwise_cp_radius,
        seat_moment=hl.moment_at_bearing,
        alpha_trim_rad=math.radians(worst.alpha_trim_deg),
        q=worst.dynamic_pressure)
    # No collar yet, so the 2.3 mm wall holds the bearing alone. That is the vehicle today.
    sec = tube_section.check_cut_station(cut, sl, stack.bearing_od,
                                         hinge.BEARING_SEAT_INTERFERENCE,
                                         seat_length=cut.wall_thickness)
    worst_name = min(sec.margins, key=sec.margins.get)
    print(f"  tube at the hinge   {cut.hole_count} x dia {cut.hole_dia * 1000:.2f} bores take "
          f"{cut.area_loss_fraction * 100:.0f}% of the section; worst margin "
          f"{sec.margins[worst_name]:.1f}x ({worst_name})")
    print(f"  tube section check  {'OK' if sec.ok else 'VIOLATIONS: ' + '; '.join(sec.violations)}")
    print(f"  servo speed         {servo.speed_60deg:.2f} s/60deg "
          f"--> {60.0 / servo.speed_60deg:.0f} deg/s slew rate")
    print(f"  pitch mode          {worst.pitch_natural_freq_hz:.1f} Hz; loop rate should be "
          f">= {worst.pitch_natural_freq_hz * 20:.0f} Hz")

    rule("FIN FLUTTER")
    fast = max(f.points, key=lambda p: p.speed)
    print(f"  worst case {fast.speed:.0f} m/s at {fast.z:.0f} m altitude. Flutter speed scales as")
    print("  1/sqrt(ambient pressure), so the danger is speed low down, not Mach at apogee.\n")
    print(f"    {'fin set':10s} {'semispan':>9s} {'thick':>7s} {'AR':>5s} {'t/c':>7s} "
          f"{'V_flutter':>10s} {'margin':>7s}")
    for fins, label in ((r.aft_fins, "aft fins"), (r.canards, "canards")):
        res = flutter.evaluate(fins, fast.speed, fast.z)
        need = flutter.required_thickness(fins, fast.speed, fast.z)
        print(f"    {label:10s} {fins.semispan * 1000:8.1f}mm {fins.thickness * 1000:6.1f}mm "
              f"{res.aspect_ratio:5.2f} {res.thickness_ratio:7.4f} {res.flutter_speed:9.0f} "
              f"{res.margin:6.2f}x  {'OK' if res.ok else 'REDESIGN'}"
              f"   (>=1.5x needs {need * 1000:.1f} mm)")
    print("""
  Built from G10 at the stated thickness with the tab bonded through to the motor mount.
  Shear modulus is the weak input here -- published G10 spans 3 to 7 GPa and the result
  goes as sqrt(G), so read these as +/-25%. Surface-mounting the fins instead of
  through-the-wall invalidates the estimate entirely.""")

    rule("RECOVERY -- the aft gas seal")
    sl = seal.from_evaluation(ev)
    schk = seal.check_seal(sl)
    print(f"  ejection charge     {sl.design.charge * 1e3:.2f} g black powder, "
          f"{sl.joint.n_pins} x {sl.joint.pin} shear pins")
    print(f"  design pressure     {sl.design.pressure / 1e3:.0f} kPa "
          f"({sl.design.force:.0f} N on the disc); joint releases at "
          f"{sl.joint.release_pressure / 1e3:.0f} kPa")
    print(f"  stuck-joint case    {sl.stuck.pressure / 1e3:.0f} kPa "
          f"({sl.stuck.force:.0f} N) -- the same charge in the packed free volume, and "
          f"this is what sizes the disc")
    print(f"  bulkhead            G-10 {sl.bulkhead.thickness * 1000:.1f} mm, "
          f"{sl.bulkhead.mass * 1e3:.0f} g; plate {sl.plate_margin:.1f}x, "
          f"feed-through {sl.hole_margin:.1f}x, bond {sl.bond_margin:.1f}x")
    print(f"  main opening shock  {sl.shock_infinite_mass:.0f} N through the U-bolt "
          f"({sl.shock_margin:.1f}x) -- {sl.shock / (sl.descent_mass * 9.81):.0f}x vehicle "
          f"weight at a 1.0 shock factor")
    print(f"  governed by         {sl.governed_by}")
    print(f"  aft gas seal check  {'OK' if schk.ok else 'VIOLATIONS: ' + '; '.join(schk.violations)}")

    ib = seal.internal_bulkhead_from_evaluation(ev)
    ibchk = seal.check_seal(ib)
    print(f"  internal bulkhead   G-10 {ib.bulkhead.thickness * 1000:.1f} mm, "
          f"{ib.bulkhead.mass * 1e3:.0f} g; plate {ib.plate_margin:.1f}x, "
          f"feed-through {ib.hole_margin:.1f}x -- NO shear pins protect it")
    print(f"  bulkhead allowance  {seal.stack_length(ib) * 1000:.1f} mm assembled against "
          f"recovery.BULKHEAD_THICKNESS {recovery.BULKHEAD_THICKNESS * 1000:.1f} mm")
    print(f"  internal bhd check  {'OK' if ibchk.ok else 'VIOLATIONS: ' + '; '.join(ibchk.violations)}")
    from design import recovery as rec
    h = rec.size_harness(r.length, sl.shock_infinite_mass)
    print(f"  harness             {h.webbing.name}, 2 x {h.length_each:.2f} m, "
          f"{h.webbing_mass * 1e3:.0f} g -- {h.margin:.1f}x on the "
          f"{h.opening_load:.0f} N opening shock after a knot derating")
    print(f"    sized, not budgeted; it was 1\" nylon at "
          f"{rec.WEBBING_OPTIONS[-1].working_load / h.opening_load:.1f}x and a quarter of the bay")
    print(f"  packing             {ev.packing}")
    print("     Full argument: python scripts/seal_report.py")

    rule("JOINTS -- what the couplers cost each bay")
    # Hoisted here from where they used to be built (further down, for the module vent
    # section) because the joint capacity check now needs them too, and building the
    # printed bay twice in one script is the exact drift this project keeps correcting.
    module_len = r.tubes[1].length
    bay_geom = bay_mod.build_bay(stack, geom, hinge.canard_hinge_station(r) - r.tube_station(1))
    abpt = access_bulkhead.pass_through_from_evaluation(ev)
    canard_fwd_room, canard_aft_room = bay_mod.joint_room(
        bay_geom, module_len, abpt.bulkhead.thickness)

    for b in joints.budgets(r, BASELINE.wall_thickness, canard_fwd_room, canard_aft_room).values():
        print(f"  {b}")
    print("  A coupler or a shoulder is a TUBE and its bore is usable, so it costs DIAMETER")
    print("  over its span, not LENGTH. Only bulkheads cost length. That is what settled the")
    print("  nose shoulder question -- see design/joints.py.")
    print("  For anything that PACKS the narrowed bore is a volume penalty, so the recovery")
    print("  bay is checked against its full-bore equivalent length, not its tube length.")
    print()
    print("  AND EVERY JOINT HAS AN ANCHORED HALF, which this model left out until Sep 2026.")
    for cap in joints.tube_capacity(r, BASELINE.wall_thickness, canard_fwd_room,
                                    canard_aft_room).values():
        print(f"  {cap}")
    jchk = joints.check_joints(r, BASELINE.wall_thickness, canard_fwd_room, canard_aft_room)
    print(f"  joint capacity      {'OK' if jchk.ok else 'VIOLATIONS: ' + '; '.join(jchk.violations)}")
    print("  The nav bay is EXACTLY full -- two 1.0 cal joints in a 1.60 cal tube do not fit,")
    print("  so its aft coupler gets the 0.600 cal that is left. The canard module's own two")
    print(f"  joints are bounded by the printed bay sitting in the MIDDLE of its tube (Z "
          f"{bay_geom.forward_face * 1000:.2f} -> {bay_geom.aft_face * 1000:.2f} mm), not by")
    print(f"  convention: {canard_fwd_room * 1000:.2f} mm fwd, {canard_aft_room * 1000:.2f} mm "
          f"aft -- both below the 1.0 cal convention and reported as open")
    print("  notes below, since nothing here sizes a coupler in bending. See docs/01")
    print("  correction 42.")
    for n in jchk.notes:
        print(f"    {n}")


    rule("VENTING and the NAV BAY")
    nav = next(t for t in ev.rocket.tubes if t.name == "nav bay")
    nav_free = avionics.free_volume(nav.inner_diameter, nav.length)
    nav_bay = venting.VentedBay("nav bay", nav_free, venting.CONVENTIONAL_PORT_COUNT,
                                venting.CONVENTIONAL_PORT_DIAMETER)
    mod_bay = venting.VentedBay("canard module", CANARD_MODULE_FREE_VOLUME,
                                venting.MODULE_VENT_COUNT, venting.MODULE_VENT_DIAMETER)
    vchk = venting.check_venting(nav_bay, mod_bay, altitude=285.0, climb_rate=177.0,
                                 apogee=ev.flight.apogee, module_wall_area=mod_bay.area)
    print(f"  static ports        {nav_bay.n_ports} x dia "
          f"{nav_bay.port_diameter * 1000:.1f} mm in the NAV BAY only "
          f"({nav_bay.area * 1e6:.1f} mm2, lag {nav_bay.lag_altitude(285.0, 177.0):.3f} m)")
    print(f"  canard module vent  {mod_bay.n_ports} x dia "
          f"{mod_bay.port_diameter * 1000:.1f} mm through its OWN WALL -- so the module is "
          f"not in the sense volume")
    print(f"  lag model asks for  {venting.port_area_for_lag(nav_free, 285.0, 177.0) * 1e6:.2f} mm2 "
          f"against the {nav_bay.area * 1e6:.1f} mm2 convention drills. Lag does not size these holes")
    print(f"  venting check       {'OK' if vchk.ok else 'VIOLATIONS: ' + '; '.join(vchk.violations)}")

    rule("THE NAV BAY'S STATIC PORTS -- station and clocking, which nothing had")
    pl = ports.place_ports(r, BASELINE.wall_thickness)
    nav_ports = venting.VentedBay("nav bay", nav_free, len(pl.clocking_deg), pl.diameter)
    sled_fwd, _ = sled.station_range(r, sled.sled_from_evaluation(ev))
    bore_r = next(j for j in joints.for_rocket(r, BASELINE.wall_thickness, canard_fwd_room,
                                               canard_aft_room)
                  if j.forward_bay == "nav bay").bore / 2.0
    mouth = min(c[0] for c in ports.port_mouth_clearances(
        pl, sled.sled_from_evaluation(ev), sled_fwd, bore_r))
    pchk = ports.check_ports(r, BASELINE.wall_thickness, pl, nav_ports, 285.0, 177.0,
                             interior_clearance=mouth)
    print(f"  placement           {pl}")
    print(f"  band                {pl.band.name}, {pl.band.x0 * 1000:.2f} -> "
          f"{pl.band.x1 * 1000:.2f} mm -- the ONLY drillable wall in this bay")
    print(f"  edge distance       {pl.edge_distance * 1000:.2f} mm each side; inner mouth "
          f"{mouth * 1000:.2f} mm clear of anything on the sled")
    print(f"  conventions broken  {pl.cal_aft_of_shoulder:.2f} cal aft of the shoulder "
          f"(rule: {ports.CONVENTIONAL_AFT_OF_SHOULDER_CAL:.1f}), "
          f"{pl.cal_forward_of_canards:.2f} cal fwd of the canards "
          f"(rule: {ports.CONVENTIONAL_FORWARD_OF_DISTURBANCE_CAL:.1f}) -- both UNREACHABLE")
    # Both errors computed, never typed: |Cp| * q restated as metres of altitude. The
    # descent case is the one that matters -- it is where the altimeter is actually READ.
    boost_pt = max(f.points, key=lambda pt: pt.q)
    _, _, rho_b, _ = atmosphere.properties(boost_pt.z)
    _, _, rho_d, a_d = atmosphere.properties(200.0)
    q_d = 0.5 * rho_d * 30.0**2
    cp_b = ports.nose_position_error(r, pl.station, boost_pt.mach)
    cp_d = ports.nose_position_error(r, pl.station, 30.0 / a_d)
    print(f"  position error      Cp {cp_b:+.4f} from the nose: "
          f"{abs(cp_b) * boost_pt.q / (rho_b * atmosphere.G0):.1f} m at max q, "
          f"{abs(cp_d) * q_d / (rho_d * atmosphere.G0):.2f} m at the main's 200 m under")
    print(f"                      drogue. It is only read where q is small, so the station is")
    print(f"                      set by edge distance and not by aerodynamics.")
    print(f"  port check          {'OK' if pchk.ok else 'VIOLATIONS: ' + '; '.join(pchk.violations)}")
    print("     Full argument: python scripts/port_report.py")

    rule("ACCESS BULKHEADS -- the two seal.py never sized")
    # abpt already built above, for the joint capacity check -- reused, not rebuilt.
    npl = access_bulkhead.nose_plate_from_evaluation(ev)
    ptchk = access_bulkhead.check_access_bulkhead(abpt)
    nplchk = access_bulkhead.check_access_bulkhead(npl)
    print(f"  pass-through plate  G-10 {abpt.bulkhead.thickness * 1000:.1f} mm, "
          f"{abpt.bulkhead.mass * 1e3:.1f} g; {abpt.plate_margin:.0f}x plate, "
          f"{abpt.hole_margin:.0f}x feed-through -- governed by {abpt.governed_by}")
    print(f"  nose aft face       G-10 {npl.bulkhead.thickness * 1000:.1f} mm, "
          f"{npl.bulkhead.mass * 1e3:.1f} g; {npl.plate_margin:.0f}x plate, "
          f"{npl.point_margin:.0f}x payload mount ({access_bulkhead.NOSE_PAYLOAD_DESIGN_MASS * 1000:.0f} g "
          f"provision at {ev.flight.max_acceleration_g:.1f} g)")
    print(f"  neither is stress-governed -- both clear the thinnest stocked sheet by 25x+.")
    print(f"  the nose cavity's OWN venting has never been modelled anywhere in this project;")
    print(f"  its plate is checked against the fully-sealed trapped-differential case until")
    print(f"  that gap is closed.")
    print(f"  pass-through check  {'OK' if ptchk.ok else 'VIOLATIONS: ' + '; '.join(ptchk.violations)}")
    print(f"  nose plate check    {'OK' if nplchk.ok else 'VIOLATIONS: ' + '; '.join(nplchk.violations)}")
    print("     Full argument: python scripts/access_bulkhead_report.py")

    rule("THE NAV BAY SLED -- the allowance nobody turned into a part")
    sld = sled.sled_from_evaluation(ev)
    sldchk = sled.check_sled(sld)
    old_w = avionics.SLED_WIDTH_FRACTION * sld.bore
    narrow = sled.sled_from_evaluation(ev, plate_width=old_w)
    print(f"  plate               G-10 {sld.plate_length * 1000:.2f} x "
          f"{sld.plate_width * 1000:.2f} x {sld.plate_thickness * 1000:.1f} mm, "
          f"{sld.plate_mass * 1000:.1f} g")
    print(f"  end brackets        2 x G-10 R {sld.bracket_radius * 1000:.2f} mm x "
          f"{sld.bracket_thickness * 1000:.1f} mm, {sld.bracket_mass * 1000:.1f} g -- the "
          f"rods pass through THESE")
    print(f"  rods                {sled.ROD_COUNT} x M{sled.ROD_DIAMETER * 1000:.0f} at "
          f"(0, +/-{sld.rod_radius * 1000:.2f}), PERPENDICULAR to the plate, running the "
          f"full {sld.rod_length * 1000:.2f} mm of bay")
    print(f"  assembly            {sld.assembly_length * 1000:.2f} mm in "
          f"{sld.bore * 1000:.2f} mm bore, widest R {sld.max_radius * 1000:.2f} mm; "
          f"{sld.mass * 1000:.1f} g against the {sled.SLED_MASS_BUDGET * 1000:.0f} g "
          f"mass.py has budgeted since before the part existed")
    print(f"  DISCRETE PLACEMENT, which avionics.check_packing() does not do: all "
          f"{len(sld.components)} components place")
    print(f"  at {sld.clearance * 1000:.1f} mm clearance on the "
          f"{sld.plate_width * 1000:.2f} mm plate -- and NONE place on the "
          f"{old_w * 1000:.2f} mm plate that")
    print(f"  avionics.SLED_WIDTH_FRACTION = {avionics.SLED_WIDTH_FRACTION:.2f} gives. The "
          f"blocker is the 80 g wiring loom, which the areal")
    print(f"  model charges 70 x 20 mm of face and which then has nowhere to go. Read")
    print(f"  design/sled.py before acting on that: it has a second reading, and NOTHING")
    print(f"  here resizes the bay (correction 5).")
    print(f"  sled check          {'OK' if sldchk.ok else 'VIOLATIONS: ' + '; '.join(sldchk.violations)}")
    print(f"  at 0.80 of the bore {'OK' if sled.check_sled(narrow).ok else 'VIOLATIONS: ' + '; '.join(sled.check_sled(narrow).violations)}")
    for n in sldchk.notes:
        if "NOT SOLVED" in n:
            print(f"  OPEN                {n}")
    print("     Full argument: python scripts/sled_report.py")

    # The module vent had a size and a surface but no STATION until Aug 2026, which is not
    # something a hole can be drawn from -- see venting.MODULE_VENT_STATION. Guarded here
    # against the real bay, seal and canard geometry rather than against typed numbers, so
    # that moving any of them fails this instead of quietly putting a hole through one.
    # module_len / bay_geom already built above, for the joint capacity check.
    # The seal is bonded at the module's AFT face, so its forward-most material is the
    # assembled stack back from there -- disc plus the fillet on each side, taken from
    # seal.py rather than typed, for the reason correction 20 gives about allowances.
    seal_fillet_fwd = module_len - seal.stack_length(sl)
    canard_root_te = (r.canards.x_root_le - r.tube_station(1)) + r.canards.root_chord
    vent_clear = venting.module_vent_clearances(
        venting.MODULE_VENT_STATION, bay_geom.aft_face, seal_fillet_fwd,
        canard_root_te, bay_geom.hinge_station)
    fouls = [k for k, v in vent_clear.items() if v <= 0.0]
    print(f"  module vent at      Z {venting.MODULE_VENT_STATION * 1000:.1f} mm, "
          f"{'/'.join(f'{a:.0f}' for a in venting.MODULE_VENT_CLOCKING_DEG)} deg -- "
          f"{'CLEAR' if not fouls else 'FOULS: ' + '; '.join(fouls)}")
    print(f"                      {vent_clear['aft of the printed bay'] * 1000:.1f} mm aft of the "
          f"bay, {vent_clear['forward of the seal fillet'] * 1000:.1f} mm fwd of the seal "
          f"fillet,")
    print(f"                      {vent_clear['aft of the canard root TE'] * 1000:.1f} mm aft of "
          f"the canard root TE. The AFT band is chosen so a leak past")
    print("                      the seal reaches a hole without crossing the servos")

    bays = joints.budgets(r, BASELINE.wall_thickness)
    navb = bays["nav bay"]
    nav_pack = avionics.check_packing(navb.min_bore, navb.usable_length,
                                      avionics.NAV_BAY_STACK, end_closures=0)
    was = avionics.check_packing(navb.min_bore, navb.usable_length,
                                 avionics.DEFAULT_STACK, end_closures=0)
    nose_fit = avionics.check_nose_packing(
        r.nose, forward_limit=BASELINE.nose_ballast_station + 0.020)
    print(f"  nav bay packing     {nav_pack}")
    print(f"    before the move   {was}")
    print(f"  nose stack          {nose_fit}")
    print(f"  the move is worth   {(was.required_length - nav_pack.required_length) * 1000:.0f} mm "
          f"of sled and moves 105 g from station 381 to {nose_fit.centroid * 1000:.0f} mm")
    print(f"  ON ESTIMATED ENVELOPES -- {len(nav_pack.estimated)} of "
          f"{len(nav_pack.components)} parts are guesses. Read")
    print("     correction 5 before touching geometry. python scripts/avionics_report.py")

    est_chk = estimation.check_estimation(ev)
    est_budget = estimation.attitude_error_budget(ev)
    arch = estimation.selected_architecture()
    print(f"  state estimation    {'OK' if est_chk.ok else 'VIOLATIONS: ' + '; '.join(est_chk.violations)}")
    print(f"  D8 architecture     {arch.key}. {arch.name}, to {arch.max_level}")
    print(f"  roll rate seen      {estimation.capped_roll_rate(ev):.0f} deg/s at the "
          f"{ROLL_COMMAND_CAP_DEG:.0f} deg roll cap, "
          f"{estimation.uncapped_roll_rate(ev):.0f} deg/s at the "
          f"{DEFLECTION_LIMIT_DEG:.0f} deg limit -- the cap is what keeps the gyro in range")
    print(f"  IMU sample rate     {est_budget.imu_rate_hz:.0f} Hz minimum, NOT the "
          f"{ev.pitch.pitch_natural_freq_hz * 20:.0f} Hz control loop rate: quaternion "
          f"propagation at")
    print(f"                      100 Hz drifts "
          f"{estimation.integration_drift(estimation.uncapped_roll_rate(ev), 100.0):.1f} "
          f"deg/s with a PERFECT gyro")
    print(f"  attitude, unaided   {est_budget.total_at_apogee:.1f} deg RSS by apogee, led by "
          f"'{est_budget.dominant.source}'")
    print(f"  D8 carries {len(est_chk.notes)} notes that do not fit here, including the one that "
          f"matters most:")
    print("     an |a|-magnitude gate on the accelerometer correction opens AT BURNOUT and "
          "what it")
    print("     admits is drag along the body axis, not gravity. python "
          "scripts/estimation_trade.py")

    rule("RECOVERY HARDWARE -- the U-bolt, its backing plate and the charge well")
    rh_r = recovery_hardware.recovery_hardware_from_evaluation(ev)
    rh_chk = recovery_hardware.check_recovery_hardware(rh_r)
    rh_u, rh_p = rh_r.anchor.ubolt, rh_r.anchor.plate
    print(f"  U-bolt              M{rh_u.rod_diameter * 1000:.0f} stainless on a "
          f"{rh_u.leg_spacing * 1000:.0f} mm spacing, holes dia "
          f"{rh_u.hole_diameter * 1000:.1f} -- NOT the M5 seal.py assumed")
    print(f"  what governs it     the CROWN in bending, {rh_u.crown_stress / 1e6:.0f} MPa at "
          f"{rh_u.crown_margin:.2f}x. seal.py's own aside checked the LEGS in")
    print(f"                      SHEAR, and the legs are in TENSION "
          f"({rh_u.leg_margin:.0f}x) and are not what breaks. A published")
    print(f"                      U-bolt rating is for clamping a pipe, which is a different "
          f"structure.")
    print(f"  backing plate       G-10 {rh_p.length * 1000:.1f} x {rh_p.width * 1000:.1f} x "
          f"{rh_p.thickness * 1000:.1f} mm: footprint R "
          f"{rh_p.footprint_radius * 1000:.2f} mm instead of a bare")
    print(f"                      6.00 mm nut face, so the disc's U-bolt margin goes "
          f"{rh_r.anchor.bare_margin:.2f}x -> {rh_r.anchor.backed_margin:.2f}x")
    print(f"  charge wells        " + "; ".join(
        f"{w.name} dia {w.bore * 1000:.0f} x {w.depth * 1000:.1f} ({w.charge * 1e3:.4f} g)"
        for w in rh_r.wells))
    print(f"  QUICK LINK REQUIRED the {rh_r.webbing_width * 1000:.1f} mm webbing does NOT pass "
          f"through a {rh_u.clear_opening * 1000:.1f} mm opening; the harness")
    print(f"                      attaches through a link, which recovery.py has priced since "
          f"it was written")
    print(f"  mass                {rh_r.mass * 1000:.1f} g -- mass.py had NO line for the "
          f"anchors; it carries 196 g now")
    print(f"  recovery hardware   {'OK' if rh_chk.ok else 'VIOLATIONS: ' + '; '.join(rh_chk.violations)}")
    for n in rh_chk.notes:
        if "NOT SOLVED" in n or "SELF-LOADING" in n:
            print(f"  OPEN                {n}")
    print("     Full argument: python scripts/recovery_hardware_report.py")

    rule("MOTOR MOUNT -- the last unsized structure, and it moved a frozen number")
    mm_r = motor_mount.motor_mount_from_evaluation(ev)
    mm_chk = motor_mount.check_motor_mount(mm_r)
    print(f"  mount tube          dia {mm_r.tube.outer_diameter * 1000:.2f} / "
          f"{mm_r.tube.inner_diameter * 1000:.2f} x {mm_r.tube.length * 1000:.2f} mm, "
          f"{mm_r.tube.mass * 1000:.1f} g -- settles make_ork.py's 331 against docs/04's 416")
    print(f"  forward bulkhead    G-10 {mm_r.forward_bulkhead.thickness * 1000:.1f} mm, "
          f"{mm_r.forward_bulkhead.mass * 1000:.1f} g -- the one seal.py handed over, and it "
          f"is the THRUST FACE")
    print(f"  centering rings     {len(mm_r.rings)} x G-10 "
          f"{mm_r.rings[0].thickness * 1000:.2f} mm; the aft one sits IN the fin tab band and "
          f"is slotted {mm_r.rings[1].slots}x")
    print(f"  thrust path         {mm_r.peak_thrust:.0f} N enters at the forward bulkhead "
          f"({mm_r.thrust_plate_margin:.0f}x), NOT through the rings -- they carry the "
          f"redundant path at {mm_r.ring_bond_margin:.0f}x")
    print(f"  assembly            {mm_r.mass * 1000:.1f} g against the "
          f"{mm_r.allowance * 1000:.0f} g mass.py has charged since that dict was written")
    print(f"  FIN TAB DEPTH       {mm_r.fin_tab_depth * 1000:.2f} mm, DERIVED -- was a frozen "
          f"12.00 that put the tab tip 0.85 mm")
    print(f"                      inside any mount tube a 54 mm motor can have. "
          f"make_cad_profiles.py and")
    print(f"                      make_aft_fin_cad_fusion.py import it now; the four AftFin "
          f"bodies were regenerated.")
    print(f"  MOTOR EJECTION      the forward gap is a SEALED {mm_r.forward_gap_volume * 1e6:.1f} cm3 "
          f"in front of the motor's own charge:")
    print(f"                      {mm_r.motor_charge_pressure / 1e6:.1f} MPa against the disc's "
          f"{mm_r.bulkhead_capacity / 1e6:.2f} MPa. The forward closure must be PLUGGED, and")
    print(f"                      nothing in this project had ever asked. "
          f"FORWARD_CLOSURE_PLUGGED = {motor_mount.FORWARD_CLOSURE_PLUGGED}")
    print(f"  motor mount check   {'OK' if mm_chk.ok else 'VIOLATIONS: ' + '; '.join(mm_chk.violations)}")
    for n in mm_chk.notes:
        if "NOT SOLVED" in n:
            print(f"  OPEN                {n}")
    print("     Full argument: python scripts/motor_mount_report.py")

    rule("STAGE 2 FLIGHT COMPUTER")
    fc_pwr = flight_computer.power_budget(ev)
    fc_log = flight_computer.log_budget(ev)
    fc_env = flight_computer.envelope_check(ev)
    fc_chk = flight_computer.check_flight_computer(ev)
    print(f"  board               {flight_computer.MCU.mpn} + {flight_computer.IMU.mpn} + "
          f"{flight_computer.MAG.mpn} + {flight_computer.BARO.mpn} + "
          f"{flight_computer.GNSS.mpn}")
    print(f"  gyro range          {flight_computer.IMU_FULL_SCALE_DEG_S:.0f} dps against "
          f"{estimation.capped_roll_rate(ev):.0f} deg/s at the roll cap -- the +/-4000 dps "
          f"requirement is DROPPED")
    print(f"                      (docs/06 asked for it; the cap makes the range unusable and "
          f"saturation is a FAULT the R12 latch can see)")
    print(f"  power               logic {fc_pwr.logic_ma_3v3:.0f} mA, servos "
          f"{fc_pwr.servo_active_total_a:.2f} A active / {fc_pwr.servo_stall_total_a:.1f} A "
          f"stalled, NO BEC (the KST is an 8.4 V part on a 2S pack)")
    print(f"  battery             {fc_pwr.total_wh:.2f} Wh needed against "
          f"{fc_pwr.usable_wh:.2f} Wh usable, {fc_pwr.margin:.0f}x -- and "
          f"{fc_pwr.pad_wh / fc_pwr.total_wh * 100:.0f}% of the demand is PAD TIME, not flight")
    print(f"  SERVO DUTY          {fc_pwr.stall_torque_margin:.2f}x on stall torque but "
          f"{fc_pwr.continuous_duty_margin:.2f}x on the datasheet's CONTINUOUS band -- a margin "
          f"no torque check in this project could see")
    print(f"  SERVO DUTY (CFD)    {fc_pwr.stall_torque_margin_cfd:.2f}x on stall torque, "
          f"CFD-informed cp_frac={CP_FRAC_CFD_INFORMED} (interim, docs/15 A2/B1/C1)")
    print(f"  logging             {fc_log.bytes_per_s / 1000:.1f} kB/s, "
          f"{fc_log.total_bytes / 1e6:.2f} MB/flight against "
          f"{fc_log.onchip_usable_bytes / 1e6:.2f} MB on-chip -- "
          f"{1 / fc_log.onchip_margin:.1f}x SHORT, so external flash is not optional")
    print(f"  board envelope      {fc_env.board_l * 1000:.0f} x {fc_env.board_w * 1000:.0f} mm "
          f"on a {fc_env.max_plate_l * 1000:.1f} x {fc_env.max_plate_w * 1000:.1f} mm plate, "
          f"{fc_env.height_margin * 1000:.1f} mm of headroom")
    print(f"  flight computer     {'OK' if fc_chk.ok else 'VIOLATIONS: ' + '; '.join(fc_chk.violations)}")
    # Board GEOMETRY, which is a different question from the board SPEC above and was the
    # one nothing checked: ERC and DRC both passed on a board whose crystal load cap sat
    # 21 mm from its crystal.  Connectivity was right and placement was wrong.
    try:
        pcb_placement.self_check()
        pcb = pcb_placement.check_placement()
        worst = max(pcb.links, key=lambda l: l.mm) if pcb.links else None
        print(f"  board placement     {'OK' if pcb.ok else 'VIOLATIONS: ' + str(len(pcb.failures))}"
              f" -- {pcb.n_pads} pads checked, median {pcb.median_mm:.2f} mm"
              + (f", worst {worst.ref}.{worst.number} [{worst.net}] {worst.mm:.2f} mm"
                 if worst else ""))
        for link in pcb.failures[:6]:
            print(f"                      {link.ref}.{link.number} [{link.net}] "
                  f"{link.mm:.2f} mm from {link.to_ref}.{link.to_number}, "
                  f"limit {link.limit:.1f} mm")
    except (FileNotFoundError, AssertionError) as exc:
        print(f"  board placement     NOT CHECKED -- {exc}")
    print("     Full argument: python scripts/flight_computer_report.py")
    print("                    python scripts/pcb_placement_report.py")

    rule("OPENROCKET ENTRY VALUES")
    print(f"""  Nose cone
    shape                 {r.nose.shape}  (parameter 1.0 for tangent ogive)
    length                {r.nose.length * 1000:.0f} mm
    base diameter         {d * 1000:.1f} mm
    wall thickness        {r.nose.wall_thickness * 1000:.1f} mm
    shoulder length       {d * 1000 * 1.0:.0f} mm (1 caliber, typical)

  Body tubes ({d * 1000:.1f} mm OD, {r.tubes[0].wall_thickness * 1000:.1f} mm wall, fiberglass)""")
    for t in r.tubes:
        print(f"    {t.name:18s}  {t.length * 1000:.0f} mm")
    print(f"""
  Canards (add as a FREEFORM or TRAPEZOIDAL fin set on the canard module)
    count                 {r.canards.count}
    root chord            {r.canards.root_chord * 1000:.1f} mm
    tip chord             {r.canards.tip_chord * 1000:.1f} mm
    height (semispan)     {r.canards.semispan * 1000:.1f} mm
    sweep length          {r.canards.sweep_length * 1000:.1f} mm
    thickness             {r.canards.thickness * 1000:.1f} mm
    position              {(r.canards.x_root_le - r.nose.length - r.tubes[0].length) * 1000:.1f} mm
                          from the front of the canard module
    fin rotation          45 deg relative to the aft fins  (interdigitated)

  Aft fins
    count                 {r.aft_fins.count}
    root chord            {r.aft_fins.root_chord * 1000:.1f} mm
    tip chord             {r.aft_fins.tip_chord * 1000:.1f} mm
    height (semispan)     {r.aft_fins.semispan * 1000:.1f} mm
    sweep length          {r.aft_fins.sweep_length * 1000:.1f} mm
    thickness             {r.aft_fins.thickness * 1000:.1f} mm
    position              bottom of booster tube, trailing edge flush with aft end

  Mass overrides -- OpenRocket cannot know about your avionics, so override these
    canard module         add {sum(p.mass for p in m.items if 'servo' in p.name or 'shaft' in p.name):.3f} kg
                          (servos, shafts, bearings, sled)
    avionics bay          add {sum(p.mass for p in m.items if p.name == 'avionics bay (budget)'):.3f} kg
    nose cone             add {sum(p.mass for p in m.items if p.name == 'avionics in nose (budget)'):.3f} kg (telemetry radio + tracker)
                          plus the {BASELINE.nose_ballast_kg * 1000:.0f} g ballast at {BASELINE.nose_ballast_station * 1000:.0f} mm
    recovery              add {sum(p.mass for p in m.items if 'recovery' in p.name):.3f} kg

  Simulation settings
    launch rod / rail     3.66 m (12 ft), 5 deg from vertical
    motor                 {BASELINE.motor.name}

  Cross-check against this tool:
    expected CG           {pt.cg * 1000:.0f} mm from nose tip (dry-ish, mid coast)
    expected CP           {stab.cp_station * 1000:.0f} mm
    expected margin       {stab.static_margin_cal:.2f} cal
    expected apogee       {f.apogee:.0f} m ({f.apogee * 3.28084:.0f} ft)
    expected max Mach     {f.max_mach:.2f}

  If OpenRocket disagrees by more than about 15% on CP or apogee, find out why before
  trusting either result. Disagreement is information, not an inconvenience.""")

    if "--plot" in sys.argv:
        plot(ev)


def plot(ev) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f, r = ev.flight, ev.rocket
    t = [p.t for p in f.points]
    fig, ax = plt.subplots(2, 2, figsize=(12, 8))

    ax[0][0].plot(t, [p.z for p in f.points])
    ax[0][0].set(xlabel="t (s)", ylabel="altitude (m)", title="Altitude")

    ax[0][1].plot(t, [p.q / 1000.0 for p in f.points], label="q (kPa)")
    ax[0][1].plot(t, [p.mach * 10 for p in f.points], label="Mach x10")
    ax[0][1].axvline(f.burnout_time, ls="--", c="k", lw=0.8)
    ax[0][1].legend()
    ax[0][1].set(xlabel="t (s)", title="Dynamic pressure and Mach")

    ax[1][0].plot(t, [p.static_margin for p in f.points])
    ax[1][0].axhline(1.4, ls="--", c="r", lw=0.8)
    ax[1][0].axhline(3.0, ls="--", c="r", lw=0.8)
    ax[1][0].set(xlabel="t (s)", ylabel="calibers", title="Static margin")

    coast = [p for p in f.points if p.t >= f.burnout_time and p.q > 300]
    for delta in (4.0, 8.0, 12.0):
        g = [control.pitch_authority(r, p, p.mass, delta).lateral_accel_g for p in coast]
        ax[1][1].plot([p.t for p in coast], g, label=f"{delta:.0f} deg")
    ax[1][1].legend(title="canard deflection")
    ax[1][1].set(xlabel="t (s)", ylabel="lateral accel (g)", title="Control authority in coast")

    for a in ax.ravel():
        a.grid(alpha=0.3)
    fig.tight_layout()
    out = Path(__file__).resolve().parents[1] / "out" / "baseline.png"
    fig.savefig(out, dpi=130)
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
