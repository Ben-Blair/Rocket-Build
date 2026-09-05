"""D8 -- state estimation: what the flight computer can know, and when.

    python scripts/estimation_trade.py            # to the terminal
    python scripts/estimation_trade.py --write    # and into out/estimation_trade.txt

Written the way `scripts/avionics_trade.py` is: price the architectures against what this
project has already computed, and let the decision be a decision. The difference is that the
binding constraint here is not a dimension, it is OBSERVABILITY -- an estimator cannot
average its way to a state nothing measures, and one of this vehicle's states was not
measured by anything on the board D7 selected.

Three of the findings below were free at design time and unrecoverable after layout. That is
why D8 had to close before the schematic rather than during firmware.
"""

from __future__ import annotations

import math
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import estimation as est
from design.configure import (DEFLECTION_LIMIT_DEG, ROLL_COMMAND_CAP_DEG, baseline,
                              evaluate)

OUT = Path(__file__).resolve().parents[1] / "out" / "estimation_trade.txt"
lines: list[str] = []


def say(t: str = "") -> None:
    lines.append(t)


def rule(t: str) -> None:
    say()
    say("=" * 92)
    say(t)
    say("=" * 92)


def main() -> None:
    # At the deflection LIMIT, matching scripts/baseline.py. Roll rate is linear in
    # deflection and this project has already been bitten once by three callers using three
    # different values -- see design/configure.DEFLECTION_LIMIT_DEG.
    ev = evaluate(baseline(), deflection_deg=DEFLECTION_LIMIT_DEG)
    f = ev.flight

    rule("D8 -- THE FOUR ARCHITECTURES")
    say()
    say(f"  {'':2s} {'sensor set':40s} {'parts':>7s} {'highest level':22s} {'check':>7s}")
    say("  " + "-" * 84)
    for a in est.ARCHITECTURES:
        chk = est.check_estimation(ev, arch=a)
        mark = "  <- SELECTED" if a.key == est.SELECTED else ""
        say(f"  {a.key:2s} {a.name:40s} ${a.cost:6.0f} {a.max_level:22s} "
            f"{'OK' if chk.ok else 'FAIL':>7s}{mark}")
    say()
    for a in est.ARCHITECTURES:
        for i, chunk in enumerate(textwrap.wrap(a.note, 86)):
            say(f"  {a.key + '.' if i == 0 else '  '} {chunk}")
    say()
    say("  What FAILS above is not a packaging verdict, it is an observability one:")
    for a in est.ARCHITECTURES:
        chk = est.check_estimation(ev, arch=a)
        if chk.ok:
            continue
        say(f"    {a.key}:")
        for x in chk.violations:
            for i, chunk in enumerate(textwrap.wrap(x, 82)):
                say(f"       {'-' if i == 0 else ' '} {chunk}")

    rule("THE DECISION: THE SENSOR SET DOES NOT STAGE, THE SOFTWARE DOES")
    say()
    say("  D7 staged the HARDWARE, because a PCB takes eight weeks and the cert launches are")
    say("  monthly. D8 cannot stage the same way: every sensor has to be on the schematic at")
    say("  once or it is not on the board at all. So what stages is the ESTIMATOR, and each")
    say("  flight in the docs/01 step 6 campaign gets exactly one new thing to work.")
    say()
    say(f"  {'level':7s} {'flies':14s} {'estimator':62s}")
    say("  " + "-" * 86)
    for level, flies, what, _ in est.STAGES:
        wrapped = textwrap.wrap(what, 62)
        say(f"  {level:7s} {flies:14s} {wrapped[0]}")
        for extra in wrapped[1:]:
            say(f"  {'':22s} {extra}")
    say()
    say("  **This is also why D8 closes without D1 being closed.** The guidance level is")
    say("  still a decision; the board is not waiting on it.")

    rule("FINDING 1 -- THE ACCELEROMETER GATE docs/01 PRESCRIBES PASSES ITS WORST DATA")
    say()
    say("  docs/01 step 4.2: 'accelerometer and magnetometer corrections gated on")
    say("  acceleration magnitude so boost does not corrupt attitude.' The gate does reject")
    say("  boost. Here is what it does next:")
    say()
    say(f"  {'t (s)':>7s} {'|a| (g)':>9s} {'v (m/s)':>9s}   {'phase':32s}")
    say("  " + "-" * 66)
    gate = est.accel_gate_window(f)
    marks = [0.5, 1.0, 2.0, f.burnout_time, 2.9, 3.5, 5.0, 7.0, 10.0, 13.0, 16.0]
    for t in marks:
        pt = min(est.specific_force_profile(f), key=lambda p: abs(p.t - t))
        if pt.powered:
            phase = "boost -- gate CLOSED, correctly"
        elif gate.opens_at <= pt.t <= gate.closes_at:
            phase = "coast -- GATE OPEN"
        else:
            phase = "coast -- below the band"
        say(f"  {pt.t:7.2f} {pt.specific_force_g:9.3f} {pt.speed:9.1f}   {phase:32s}")
    say()
    when = ("at burnout" if abs(gate.opens_after_burnout) < 0.05
            else f"{gate.opens_after_burnout:.2f} s after burnout")
    say(f"  The gate opens at t = {gate.opens_at:.2f} s -- {when} -- and stays open for")
    say(f"  {gate.duration:.1f} s, peaking at {gate.peak_admitted_g:.2f} g.")
    say()
    say("  **THE VECTOR IT ADMITS IS DRAG ALONG THE BODY AXIS, NOT GRAVITY.** A coasting")
    say("  rocket is in free fall; the only specific force on it is aerodynamic, and that")
    say("  force lies along the body axis. So the filter is handed a body-axis vector")
    say("  labelled 'down' at exactly the moment the guidance loop opens, and a vehicle")
    say("  15 deg off vertical is told it is vertical.")
    say()
    say("  The heuristic comes from multirotor AHRS work, where a vehicle really does sit at")
    say("  1 g in cruise and |a| ~ 1 g really does mean 'this is gravity'. **A ballistic")
    say("  vehicle never sees gravity again after it leaves the rail.** Same shape as")
    say("  correction 1 and correction 28: a rule that sounds complete, is locally true, and")
    say("  silently produces the wrong answer.")
    say()
    say("  FIX: gate on flight PHASE, never on |a|. The accelerometer is a pad-alignment")
    say("  sensor and an event detector, and nothing else. It is free -- it removes code.")

    rule("FINDING 2 -- 100 Hz INTEGRATION DRIFTS FASTER THAN THE GYRO DOES")
    say()
    limit_rate = est.uncapped_roll_rate(ev)
    capped_rate = est.capped_roll_rate(ev)
    say("  board_requirements() derives ONE rate -- the control loop rate, 20x the pitch")
    say(f"  mode, {ev.pitch.pitch_natural_freq_hz * 20:.0f} Hz. A reader builds a 100 Hz system. But attitude is")
    say("  PROPAGATED, not sampled: q <- q * (1, w*dt/2) renormalised rotates by")
    say("  2*atan(|w|*dt/2), not by |w|*dt, and the shortfall is cubic in the step.")
    say()
    say(f"  {'IMU rate':>10s} {'rot/step':>10s} {'drift @ ' + f'{capped_rate:.0f}':>14s} "
        f"{'drift @ ' + f'{limit_rate:.0f}':>14s}")
    say(f"  {'':10s} {'(deg)':>10s} {'deg/s (capped)':>14s} {'deg/s (limit)':>14s}")
    say("  " + "-" * 54)
    for hz in (100.0, 200.0, 500.0, 1000.0, 2000.0):
        step = math.degrees(math.radians(limit_rate) / hz)
        say(f"  {hz:8.0f} Hz {step:10.2f} {est.integration_drift(capped_rate, hz):14.3f} "
            f"{est.integration_drift(limit_rate, hz):14.3f}")
    say()
    say(f"  At 100 Hz and the {limit_rate:.0f} deg/s the deflection limit allows, each step is a")
    say(f"  {math.degrees(math.radians(limit_rate) / 100.0):.1f} degree rotation and the small-angle assumption underneath the")
    say(f"  propagation is simply false. **{est.integration_drift(limit_rate, 100.0):.1f} deg/s -- with a PERFECT gyro.** Over the")
    say(f"  {ev.control_seconds:.1f} s control window that is more than the whole sensor error budget.")
    say()
    say(f"  FIX: sample the IMU at {est.required_imu_rate(limit_rate):.0f} Hz. The error is cubic, so it costs almost")
    say("  nothing -- but it is a DIFFERENT REQUIREMENT from the control loop rate, it sets")
    say("  the SPI clock and the DMA, and it is fixed at layout. The estimator is allowed to")
    say("  run faster than the controller; nothing said it had to.")

    rule("FINDING 3 -- ROLL ANGLE WAS OBSERVED BY NOTHING ON THE SELECTED BOARD")
    say()
    say("  An estimator cannot average its way to a state nothing measures. Per phase:")
    say()
    say(f"  {'state':22s} " + " ".join(f"{ph:16s}" for ph in est.PHASES))
    say("  " + "-" * 88)
    for state in est.STATES:
        row = est.OBSERVABILITY_SHORT[state]
        say(f"  {state:22s} " + " ".join(f"{row[ph]:16s}" for ph in est.PHASES))
    say()
    for state in est.STATES:
        blind = est.unobserved(state)
        if blind:
            say(f"  '{state}' propagates open-loop through: {', '.join(blind)}")
    say()
    say("  ROLL ANGLE is the one with no aiding sensor in ANY phase on D7's board.")
    say("  Specific force is invariant under rotation about the axis it lies along, so the")
    say("  accelerometer cannot see roll; and the GNSS velocity vector fixes where the nose")
    say("  points, not how the vehicle is clocked about it.")
    say()
    say("  **L1 -- hold roll angle -- is the project's MINIMUM success criterion** (docs/00")
    say("  section 1.1, and GV-3 in the step 6 campaign). docs/01 step 4.2 already assumed a")
    say("  magnetometer. STM32_BOARD did not have one, and nothing had checked.")
    say()
    say("  FIX: put a magnetometer on the schematic. About $5 and one I2C address before")
    say("  layout; unbuildable after. Keep it away from the servo bus and the battery leads.")
    say()
    say("  Note what pitch/yaw attitude is aided BY, because it is not obvious: the GNSS")
    say("  VELOCITY VECTOR, under a small-alpha assumption. That assumption is what")
    say(f"  {ev.flight.min_static_margin:.1f}-{ev.flight.max_static_margin:.1f} cal of static margin buys -- the one place in this")
    say("  project where stability margin shows up as a SENSING property rather than a")
    say("  handling one.")

    rule("THE ATTITUDE ERROR BUDGET -- and the ranking is not the one a tutorial predicts")
    say()
    budget = est.attitude_error_budget(ev)
    say(f"  Gyro: {budget.gyro.name}, propagated at {budget.imu_rate_hz:.0f} Hz, roll command")
    say(f"  capped at {ROLL_COMMAND_CAP_DEG:.0f} deg. UNAIDED -- this is what the estimate does with no")
    say("  correction applied at all, which is the L0/L1 configuration.")
    say()
    say(f"  {'source':38s} {'at burnout':>12s} {'at apogee':>12s}")
    say("  " + "-" * 66)
    for t in budget.terms:
        say(f"  {t.source:38s} {t.at_burnout_deg:10.3f} deg {t.at_apogee_deg:10.3f} deg")
    say("  " + "-" * 66)
    say(f"  {'RSS':38s} {'':14s} {budget.total_at_apogee:10.3f} deg")
    say()
    for t in budget.terms:
        say(f"  {t.source}:")
        for chunk in textwrap.wrap(t.note, 84):
            say(f"      {chunk}")
        say()
    say("  **Bias and random walk -- the two terms every AHRS article is about -- are")
    say("  negligible over 17 seconds.** SCALE FACTOR AT HIGH ROLL RATE leads by an order of")
    say("  magnitude, and it leads because of the same roll rate that made D7's gyro line")
    say("  tight. One root cause, and capping the roll command fixes both.")
    say()
    say("  Pad gyro-bias calibration is mandatory and free: averaging on the rail takes the")
    say(f"  bias term from {budget.gyro.bias_uncal_deg_s * f.apogee_time:.1f} deg to "
        f"{budget.gyro.bias_deg_s * f.apogee_time:.2f} deg by apogee.")

    rule("THE GAP CORRECTION 58 FOUND -- THE AIDED NUMBER, WHICH DECIDES IF THE CAP CAN MOVE")
    say()
    say("  Everything above is GYRO-ONLY, propagated open loop. But roll angle is observed by")
    say("  the magnetometer or by nothing (finding 3) -- so the unaided total above is not the")
    say("  number that decides whether `ROLL_COMMAND_CAP_DEG` can ever move, and until now")
    say("  nothing here computed the number that is. `mag_aided_roll_error()` does: the")
    say("  dominant unaided term, scale factor at roll rate, is a RATE error, and an absolute")
    say("  reference turns a rate error into a bounded lag rather than an open-loop integral.")
    say()
    aided_cap = est.mag_aided_roll_error(ev, budget.gyro, roll_rate_deg_s=capped_rate)
    aided_lim = est.mag_aided_roll_error(ev, budget.gyro, roll_rate_deg_s=limit_rate)
    unaided_lim = est.attitude_error_budget(ev, budget.gyro, roll_rate_deg_s=limit_rate)
    say(f"  {'':22s} {'roll rate':>11s} {'tau':>8s} {'gyro lag':>10s} {'mag noise':>10s} "
        f"{'AIDED':>9s} {'UNAIDED':>9s}")
    say("  " + "-" * 82)
    say(f"  {'at the ' + f'{ROLL_COMMAND_CAP_DEG:.0f} deg cap':22s} "
        f"{aided_cap.roll_rate_deg_s:9.0f}°/s {aided_cap.tau_s * 1000:6.1f} ms "
        f"{aided_cap.err_gyro_deg:8.3f}° {aided_cap.err_mag_noise_deg:8.3f}° "
        f"{aided_cap.total_deg:8.2f}° {budget.total_at_apogee:8.2f}°")
    say(f"  {'at the ' + f'{DEFLECTION_LIMIT_DEG:.0f} deg limit':22s} "
        f"{aided_lim.roll_rate_deg_s:9.0f}°/s {aided_lim.tau_s * 1000:6.1f} ms "
        f"{aided_lim.err_gyro_deg:8.3f}° {aided_lim.err_mag_noise_deg:8.3f}° "
        f"{aided_lim.total_deg:8.2f}° {unaided_lim.total_at_apogee:8.2f}°")
    say()

    def para(t: str) -> None:
        for chunk in textwrap.wrap(t, 84):
            say(f"  {chunk}")
        say()

    para(f"**{budget.total_at_apogee:.1f}° unaided becomes {aided_cap.total_deg:.2f}° "
         f"aided at the cap -- and {unaided_lim.total_at_apogee:.1f}° unaided becomes "
         f"{aided_lim.total_deg:.2f}° aided at the limit.** The magnetometer does not "
         f"refine the roll estimate here, it IS the roll estimate, so correction 55's "
         f"uncapped-gyro comparison was made on the wrong instrument in both directions -- "
         f"neither total is the sensor's noise floor: {aided_lim.err_mag_noise_deg:.3f}° "
         f"of it is MMC5983MA noise, which is not what either total is made of.")

    spr_note = ("tracked" if aided_lim.phase_observable else
                "ALIASED -- below the floor this model assumes")
    para(f"This number is only valid if the magnetometer can resolve roll PHASE at the rate "
         f"it is asked to: at the {DEFLECTION_LIMIT_DEG:.0f} deg limit that is "
         f"{aided_lim.samples_per_rev:.1f} samples/rev at a {aided_lim.mag_rate_hz:.0f} Hz "
         f"read rate against a {est.MAG_SAMPLES_PER_REV_MIN:.0f}/rev floor -- {spr_note}, "
         f"{aided_lim.samples_per_rev / est.MAG_SAMPLES_PER_REV_MIN:.1f}x margin. Checked, "
         f"not just computed -- an assumption this model depends on is a thing to read back, "
         f"not a thing to assert and move on from.")

    para(f"**What actually limits the aided number is not the sensor, and this is the part a "
         f"datasheet comparison would miss entirely.** Roll is resolved from the field "
         f"component PERPENDICULAR to a near-vertical roll axis -- the HORIZONTAL component, "
         f"{aided_lim.field_perp_gauss:.3f} gauss of {est.EARTH_FIELD_GAUSS:.2f} at "
         f"{est.MAGNETIC_INCLINATION_DEG:.0f}° inclination, the SMALLER part of the "
         f"field. Against that, {aided_lim.err_mag_noise_deg:.3f}° of MMC5983MA noise is "
         f"nothing. What is not nothing is a disturbance FIXED IN THE BODY FRAME -- it "
         f"rotates with the vehicle, so it is coherent with the signal being measured and no "
         f"filter averages it away. It ADDS to the total rather than RSS'ing into it, which "
         f"is why hard/soft-iron calibration matters more here than picking a quieter part.")

    allowance = est.required_magnetic_cleanliness(ev, budget.gyro, roll_rate_deg_s=limit_rate)
    one_amp_50mm = est.wire_field_gauss(1.0, 0.050)
    para(f"`required_magnetic_cleanliness()` inverts the budget: at the "
         f"{DEFLECTION_LIMIT_DEG:.0f} deg limit, the airframe may carry "
         f"**{allowance * 1000:.1f} mgauss** of body-fixed disturbance and still meet the "
         f"{est.ATTITUDE_ERROR_BUDGET_DEG:.1f} deg budget. One servo lead at 1 A, 50 mm from "
         f"the magnetometer, is {one_amp_50mm * 1000:.0f} mgauss on its own -- **over the "
         f"whole allowance before anything else on the harness is counted.** A twisted pair "
         f"cancels to first order; an untwisted single-ended run past the sensor does not.")

    para("**So correction 58's gap is closed, and closing it moved the open item rather than "
         "retiring it.** The roll cap no longer waits on a gyro decision or an estimator "
         "design -- it waits on HARNESS ROUTING, a number nobody has measured. `docs/07`'s "
         "'four servos and a battery next to a magnetometer, in an airframe nobody has "
         "swung' now has a threshold to swing it against. Swing it before trusting any roll "
         "number this project produces.")
    lines.pop()  # rule() adds its own leading blank

    rule("THE AIDING SENSORS, AND WHAT THEY ARE ACTUALLY FOR")
    say()
    say("  BAROMETER -- not a boost-phase altitude source.")
    say()
    say(f"  {'q (Pa)':>10s} {'alt (m)':>9s} {'port error':>12s} {'sensor noise':>14s}")
    say("  " + "-" * 50)
    for t in (f.burnout_time, 5.0, 10.0, f.apogee_time - 0.5):
        pt = min(f.points, key=lambda x: abs(x.t - t))
        be = est.baro_altitude_error(pt.q, pt.z)
        say(f"  {pt.q:10.0f} {pt.z:9.0f} {be.altitude_error_m:10.1f} m "
            f"{be.noise_error_m:12.2f} m")
    say()
    peak = est.baro_altitude_error(f.max_q, 500.0)
    say(f"  At max q ({f.max_q / 1000:.1f} kPa) a {peak.coefficient * 100:.0f}% static port error coefficient is")
    say(f"  {peak.pressure_error_pa:.0f} Pa, and dp/dh there is {peak.dp_dh_pa_m:.1f} Pa/m: **{peak.altitude_error_m:.0f} m of altitude error**,")
    say(f"  against {peak.noise_error_m:.2f} m of sensor noise. Two orders of magnitude apart, and the")
    say("  error a datasheet comparison would optimise is the small one.")
    say()
    say("  Worse, port error scales with q, so it CORRELATES WITH VELOCITY -- it does not")
    say("  look like noise to a filter, it looks like signal, and a filter that trusts baro")
    say("  during boost will happily fuse it. Baro is for coast and descent altitude, apogee")
    say("  detection, and cross-checking the StratoLoggerCF.")
    say()
    say(f"  One thing that is genuinely NOT a problem: max Mach is {f.max_mach:.3f}, so there is no")
    say("  transonic port anomaly. Worth stating, because the absence of a problem is a")
    say("  result too.")
    say()
    gl = est.gnss_position_lag(f.burnout_velocity, ev.crossrange, f.max_acceleration_g)
    say("  GNSS -- a slow outer-loop sensor, and the only in-flight attitude reference.")
    say()
    say(f"    receiver latency        {gl.latency_s * 1000:.0f} ms  -> {gl.latency_lag_m:5.1f} m at {gl.speed:.0f} m/s")
    say(f"    half-sample staleness   {0.5 / gl.rate_hz * 1000:.0f} ms  -> {gl.sample_lag_m:5.1f} m at {gl.rate_hz:.0f} Hz")
    say(f"    total position lag              {gl.total_lag_m:5.1f} m")
    say(f"    CEP                            {gl.cep_m:5.1f} m")
    say()
    say(f"  **{gl.total_lag_m:.0f} m of lag against {gl.crossrange_m:.0f} m of achievable crossrange "
        f"-- {gl.lag_fraction_of_crossrange * 100:.0f}%.**")
    say("  It is correctable: dead-reckon the fix forward on the IMU, which is what the IMU")
    say("  is for. But only if you know it is there, and the lag is not the CEP -- a")
    say("  datasheet comparison on accuracy alone would have missed it entirely.")
    say()
    if gl.exceeds_dynamics:
        say(f"  AND THE RECEIVER MAY NOT BE TRACKING AT ALL THROUGH BOOST. Peak axial is")
        say(f"  {gl.peak_g:.1f} g, and 'airborne <{gl.max_dynamics_g:.0f} g' is the most permissive dynamic platform")
        say("  model u-blox offers. Expect lock loss under boost and reacquisition in early")
        say("  coast -- which is survivable, because the guidance window does not open until")
        say("  burnout, but it means GNSS cannot be part of the boost-phase estimate.")

    rule("WHAT THIS COST, AND THE PATTERN IT MAKES")
    say()
    say("  Three findings, three fixes, and every one of them is free BEFORE the schematic:")
    say()
    say(f"    {'1. delete the |a| gate':44s}removes code")
    say(f"    {f'2. sample the IMU at {est.required_imu_rate(limit_rate):.0f} Hz':44s}"
        f"a register write, fixed at layout")
    say(f"    {'3. add a magnetometer':44s}about $5, fixed at layout")
    say()
    say("  D7 found the same shape once already -- gyro full scale, free at design time and")
    say("  unrecoverable after. **That is now four in a row, and the pattern is the point:")
    say("  the requirements this vehicle produces that no tutorial would are all sensing")
    say("  requirements, and they are all set at layout.** Which is the argument for closing")
    say("  D8 before the schematic rather than during firmware, and it is why this document")
    say("  exists at all.")
    say()
    say("  A fourth thing fell out on the way past and it is a correction to D7, not to D8:")
    say(f"  the gyro requirement had been computed at 6 deg of deflection and printed under an")
    say(f"  8 deg heading. Roll rate is linear in deflection, so the real figure at the limit")
    say(f"  is {limit_rate:.0f} deg/s -- {limit_rate / 2000 * 100:.0f}% of a +/-2000 dps part, SATURATED, not the")
    say(f"  comfortable 89% docs/06 quoted. The roll command cap was already in baseline.py as")
    say(f"  a control convenience; it is load-bearing for the SENSOR. See")
    say(f"  design/configure.DEFLECTION_LIMIT_DEG.")

    rule("THE CHECK baseline.py CARRIES")
    say()
    chk = est.check_estimation(ev)
    say(f"  state estimation    {'OK' if chk.ok else 'VIOLATIONS: ' + '; '.join(chk.violations)}")
    say()
    for note in chk.notes:
        for i, chunk in enumerate(textwrap.wrap(note, 84)):
            say(f"  {'note' if i == 0 else '    '}  {chunk}")
        say()

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
