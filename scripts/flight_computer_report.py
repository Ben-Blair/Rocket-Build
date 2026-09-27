"""Print the Stage 2 flight computer's BOM, power budget, log budget and board envelope.

    python scripts/flight_computer_report.py            # to the terminal
    python scripts/flight_computer_report.py --write    # and into out/flight_computer.txt

docs/06 selected a custom STM32F405 board and docs/07 named its sensors. Neither specified
it to the point where parts could be ordered, and three things sat in the gap: a gyro
requirement no real part satisfied, no power budget anywhere in the project, and a logging
requirement that had never been turned into bytes. See `design/flight_computer.py` for the
argument and `docs/14-flight-computer-bom.md` for the write-up.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import estimation as est, flight_computer as fc, packaging
from design.configure import DEFLECTION_LIMIT_DEG, ROLL_COMMAND_CAP_DEG, baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "flight_computer.txt"

lines: list[str] = []


def say(text: str = "") -> None:
    lines.append(text)


def rule(title: str) -> None:
    say()
    say("=" * 92)
    say(title)
    say("=" * 92)


def main() -> None:
    ev = evaluate(baseline(), deflection_deg=DEFLECTION_LIMIT_DEG)

    rule("STAGE 2 FLIGHT COMPUTER -- what to order, and what it has to survive")
    say(f"  evaluated at deflection {ev.deflection_deg:.1f} deg, roll cap "
        f"{ROLL_COMMAND_CAP_DEG:.1f} deg")
    say(f"  apogee {ev.flight.apogee:.0f} m at {ev.flight.apogee_time:.1f} s, "
        f"peak axial {ev.flight.max_acceleration_g:.1f} g, "
        f"control window {ev.control_seconds:.1f} s")

    # ---------------------------------------------------------------- the gyro resolution
    rule("THE GYRO QUESTION docs/06 LEFT OPEN -- closed, by dropping the requirement")
    capped = est.capped_roll_rate(ev)
    uncapped = est.uncapped_roll_rate(ev)
    fs = fc.IMU_FULL_SCALE_DEG_S
    say(f"  selected part           {fc.IMU.mpn}, +/-{fs:.0f} dps")
    say(f"  roll rate at the cap    {capped:7.0f} deg/s  {capped / fs * 100:5.1f}% of full "
        f"scale   ({fs / max(capped, 1e-9):.1f}x margin)")
    say(f"  roll rate uncapped      {uncapped:7.0f} deg/s  {uncapped / fs * 100:5.1f}% -- "
        f"SATURATED, and this is a FAULT condition, not a commanded one")
    say(f"  required IMU rate       {est.required_imu_rate(uncapped):7.0f} Hz against "
        f"32000 Hz available")
    say(f"  accel full scale        {est.ACCEL_16G.accel_full_scale_g:7.0f} g against a "
        f"{ev.flight.max_acceleration_g:.1f} g peak "
        f"({est.ACCEL_16G.accel_full_scale_g / max(ev.flight.max_acceleration_g, 1e-9):.1f}x)")
    say()
    say("  The +/-4000 dps option is REAL and is rejected on the numbers, not for want of a")
    say("  part -- see design/flight_computer.GYRO_ALTERNATE_ICM45686:")
    say(f"    {fc.GYRO_ALTERNATE_ICM45686.name}")
    say(f"    range {fc.GYRO_ALTERNATE_ICM45686.full_scale_deg_s:.0f} dps, ARW "
        f"{fc.GYRO_ALTERNATE_ICM45686.arw_deg_rt_s * 1000:.1f} mdps/sqrt(Hz) against the "
        f"42688's {est.GYRO_ICM42688.arw_deg_rt_s * 1000:.1f}")
    say("    Saturation is DETECTABLE and is wired to the R12 latch instead of bought around.")

    # ---------------------------------------------------------------------------- the BOM
    rule("BOM -- one board, one spin")
    say(f"  {'item':<28} {'MPN':<26} {'pkg/iface':<26} {'qty':>3} {'USD':>7}")
    say("  " + "-" * 90)
    for p in fc.BOARD_BOM:
        flag = "" if p.measured else "  (est)"
        say(f"  {p.name:<28} {p.mpn:<26} {p.package:<26} {p.qty:>3} {p.line_price:>7.2f}{flag}")
    say("  " + "-" * 90)
    say(f"  {'bought whole, off-board':<28}")
    for p in (fc.ALTIMETER, fc.BATTERY):
        flag = "" if p.measured else "  (est)"
        say(f"  {p.name:<28} {p.mpn:<26} {p.package:<26} {p.qty:>3} {p.line_price:>7.2f}{flag}")
    say(f"  {'spares':<28}")
    for p in fc.SPARES:
        say(f"  {p.name:<28} {p.mpn:<26} {p.package:<26} {p.qty:>3} {p.line_price:>7.2f}")
    say()
    say(f"  optional, not flight hardware: {fc.BRINGUP_JIG.mpn} at "
        f"{fc.BRINGUP_JIG.line_price:.2f}")

    ps = fc.price_split()
    say()
    say(f"  parts (chips, passives, connectors)   {ps.parts:7.2f}")
    say(f"  fab (4-layer PCB)                     {ps.fab:7.2f}")
    say(f"  bought whole (altimeter + battery)    {ps.bought_whole:7.2f}")
    say(f"  spares                                {ps.spares:7.2f}")
    say(f"  TOTAL, hand-assembled                 {ps.total_hand_assembled:7.2f}")
    say(f"  TOTAL, with low-volume PCBA           {ps.total_with_pcba:7.2f}")
    say("  The chips are FPV-class cheap and the pain is fab. docs/04 section 5 carries a")
    say("  flat $400 for 'custom STM32F405 board'; that is the assembled-board number and it")
    say("  hides a 3:1 split between silicon and process.")

    # -------------------------------------------------------------------------- the power
    rule("POWER -- the budget this project did not have")
    p = fc.power_budget(ev)
    say(f"  logic rail 3.3 V        {p.logic_ma_3v3:7.1f} mA  ({p.logic_w:.2f} W), so "
        f"{p.logic_pack_ma:.0f} mA off the 2S pack at {fc.BUCK_EFFICIENCY:.0%} buck")
    for part in (fc.MCU, fc.IMU, fc.MAG, fc.BARO, fc.GNSS, fc.FLASH):
        say(f"      {part.name:<22} {part.current_ma:6.2f} mA")
    say()
    say(f"  servos                  {p.servo_count} x {fc.BATTERY.rail_v:.1f} V direct off "
        f"the pack -- the KST X08 Plus is rated 3.8-8.4 V, so THERE IS NO BEC")
    say(f"      peak hinge moment  {p.hinge_moment_nm:7.4f} N m "
        f"({p.hinge_moment_nm * fc.KGFCM_PER_NM:.2f} kgf.cm) per panel")
    say(f"      per servo, active  {p.servo_active_a:7.2f} A   (read off the datasheet curve)")
    say(f"      all four, active   {p.servo_active_total_a:7.2f} A")
    say(f"      all four, stalled  {p.servo_stall_total_a:7.2f} A")
    say(f"      all four, idle     {p.servo_idle_total_a:7.3f} A   (APPROX -- not on the "
        f"datasheet)")
    say()
    say(f"  pad, {fc.PAD_TIME_S / 60:.0f} min armed      {p.pad_wh:7.3f} Wh")
    say(f"  flight, {p.flight_seconds:.0f} s to landing {p.flight_wh:7.3f} Wh  "
        f"(servos work for {p.control_seconds:.1f} s of it)")
    say(f"  total                   {p.total_wh:7.3f} Wh")
    say(f"  pack                    {p.battery_wh:7.3f} Wh, {p.usable_wh:.2f} Wh usable at "
        f"{fc.BATTERY_USABLE_FRACTION:.0%} depth")
    say(f"  MARGIN                  {p.margin:7.1f}x")
    say()
    say(f"  servo torque margin     {p.stall_torque_margin:7.2f}x on STALL torque "
        f"(design cp_frac=0.25)")
    say(f"  servo torque margin     {p.stall_torque_margin_cfd:7.2f}x on STALL torque -- "
        f"CFD-INFORMED, interim (cp_frac={packaging.CP_FRAC_CFD_INFORMED}, docs/15 A2/B1;")
    say(f"                          not a bench-verified number -- see docs/15 C1)")
    say(f"  servo duty margin       {p.continuous_duty_margin:7.2f}x on the datasheet's own "
        f"CONTINUOUS band ({fc.SERVO_CONTINUOUS_KGFCM:.1f} kgf.cm)")
    say(f"  peak pack current       {p.peak_pack_a:7.2f} A -- what sizes the C-rating, the "
        f"battery lead, and the conductors through the potted pass-through")

    # ------------------------------------------------------------------------ the logging
    rule("LOGGING -- 'onboard flash is enough' was never checked, and it is not")
    lb = fc.log_budget(ev)
    say(f"  {'channel':<48} {'B/sample':>9} {'Hz':>8} {'B/s':>10}")
    say("  " + "-" * 90)
    for c in lb.channels:
        say(f"  {c.name:<48} {c.bytes_per_sample:>9} {c.rate_hz:>8.0f} {c.bytes_per_s:>10.0f}")
    say("  " + "-" * 90)
    say(f"  {'total':<48} {'':>9} {'':>8} {lb.bytes_per_s:>10.0f}")
    say()
    say(f"  window logged           {lb.duration_s:.0f} s (pad reference + boost + coast + "
        f"descent)")
    say(f"      that window is a deliberate UPPER BOUND -- the whole descent is priced at the "
        f"main's {fc.DESCENT_RATE_BOUND:.0f} m/s")
    say(f"      when the drogue leg is much faster. Against the requirement's own 150 s "
        f"window it is {lb.bytes_per_s * 150 / 1e6:.2f} MB, still "
        f"{lb.bytes_per_s * 150 / lb.onchip_usable_bytes:.1f}x short. The conclusion does "
        f"not depend on which window is used.")
    say(f"  per flight              {lb.total_bytes / 1e6:.2f} MB")
    say(f"  STM32F405 flash         {fc.MCU_FLASH_BYTES / 1e6:.2f} MB total, "
        f"{lb.onchip_usable_bytes / 1e6:.2f} MB after a "
        f"{fc.FIRMWARE_ALLOWANCE_BYTES / 1024:.0f} KB firmware allowance")
    say(f"      margin              {lb.onchip_margin:.2f}x -- "
        f"{1 / max(lb.onchip_margin, 1e-9):.1f}x SHORT")
    say(f"  {fc.FLASH.mpn:<22}  {lb.external_bytes / 1e6:.0f} MB, margin "
        f"{lb.external_margin:.1f}x, {lb.flights_on_external:.1f} flights")
    say()
    imu_share = lb.channels[0].bytes_per_s / lb.bytes_per_s * 100
    say(f"  The IMU line is {imu_share:.0f}% of the rate and it is the one that cannot be "
        f"cut: logging raw")
    say("  gyro and accel at the PROPAGATION rate is what turns GV-2 into a measurement of")
    say("  Cm_delta and Cl_delta. At the loop rate it would fit on-chip and the flight the")
    say("  thesis rests on would stop producing the data it exists to produce.")

    # ----------------------------------------------------------------------- the envelope
    rule("BOARD ENVELOPE -- against the sled, which is the arbiter")
    e = fc.envelope_check(ev)
    say(f"  board target            {e.board_l * MM:.0f} x {e.board_w * MM:.0f} x "
        f"{e.board_h * MM:.0f} mm  (a LAYOUT TARGET, not a measurement)")
    say(f"  sled plate              {e.max_plate_l * MM:.2f} x {e.max_plate_w * MM:.2f} mm")
    say(f"  usable height per face  {e.usable_height * MM:.2f} mm against a "
        f"{e.stack_h * MM:.1f} mm stack "
        f"({fc.PCB_THICKNESS * MM:.1f} mm PCB + {fc.TALLEST_COMPONENT * MM:.0f} mm tallest)")
    say(f"  margins                 {e.length_margin * MM:+.2f} mm long, "
        f"{e.width_margin * MM:+.2f} mm wide, {e.height_margin * MM:+.2f} mm tall")
    say(f"  fits                    {'YES' if e.fits else 'NO'}")
    say("  Do NOT grow this board. docs/06 records that the sled already widened to 0.846 of")
    say("  the bore to place the 80 g loom, and past that width comes out of headroom.")

    # ------------------------------------------------------------------- interfaces + map
    rule("BUS MAP -- SPI for everything flight-critical, no I2C")
    say("  SPI1  (up to 24 MHz)   CS1  ICM-42688-P      burst read, DMA, 1 kHz+")
    say("        dedicated to the IMU so its transfer never queues behind anything")
    say("  SPI2                   CS2  MMC5983MA        magnetometer, 100 Hz")
    say("                         CS3  MS5611           barometer, 50 Hz")
    say("  SPI3                   CS4  W25Q128JV        log flash, write-mostly")
    say("  USART1                      MAX-M10S         GNSS, 10 Hz, UBX binary")
    say("  USART2                      debug / console  bring-up only")
    say("  TIM4 CH1-4             PB6 PB7 PB8 PB9       4x servo PWM at 333 Hz (1520 us)")
    say("  SWD                         PA13 PA14        bring-up and flashing")
    say()
    say("  KST X08 Plus signal is 3.3-5.0 V HIGH, so the F405's 3.3 V timer outputs drive it")
    say("  directly with no level shift. Its 1520 us / 333 Hz frame is the datasheet's own,")
    say("  which is where avionics.board_requirements()'s 333 Hz figure independently lands.")

    # ---------------------------------------------------------------------------- verdict
    rule("VERDICT")
    chk = fc.check_flight_computer(ev)
    for note in chk.notes:
        say(f"  note      {note}")
    for bad in chk.violations:
        say(f"  VIOLATION {bad}")
    say()
    say(f"  {'OK' if chk.ok else 'VIOLATIONS: ' + '; '.join(chk.violations)}")

    text = "\n".join(lines)
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(text + "\n")
        print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
