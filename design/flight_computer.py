"""Stage 2 flight computer -- the parts, and the three questions nobody had asked.

`docs/06` closed D7 by selecting a custom STM32F405 board for the guided vehicle, with the
ejection charges left on an independent commercial altimeter. `docs/07` and
`design/estimation.py` then named the sensor set and computed what it has to achieve. What
neither of them did was specify the board to the point where PARTS CAN BE ORDERED, and
three things stood between the two:

  1. A CONTRADICTION. docs/06 asks for a gyro with selectable full scale to +/-4000 deg/s.
     The named part, ICM-42688-P, tops out at +/-2000, and the only +/-4000 entry in
     estimation.py was `GYRO_WIDE` -- `measured=False`, no real part behind it. A
     requirement satisfied only by a part that does not exist is not a requirement, which
     is estimation.py's own rule turned on estimation.py. RESOLVED BELOW, and the answer is
     to drop the +/-4000 requirement rather than to buy it.

  2. NO POWER BUDGET ANYWHERE IN THE PROJECT. The battery was a bare line in `mass.py`
     ("2S 1500 mAh, 90 g") with no voltage, no watt-hours, no draw and no runtime, and
     `packaging.Servo` modelled the KST X08 Plus for torque and speed only. Nothing had
     ever asked whether the pack covers a flight. It does -- by about an order of
     magnitude -- and the finding is that CAPACITY WAS NEVER THE CONSTRAINT. Peak current
     is, and that is a wire and connector question, not a battery one.

  3. LOGGING HAD NEVER BEEN TURNED INTO BYTES. `avionics.board_requirements()` asks for
     "at least 100 Hz for 150 s" and its own slack note says "onboard flash is enough".
     Written out as a channel list it is not: the F405's 1 MB is short by about 3x, and it
     is short because of the one channel the thesis actually needs.

EVERY RATE, DURATION AND LOAD HERE IS DERIVED FROM `configure.evaluate()`. What is NOT
derived is the parts: those are datasheet numbers, marked `measured` and noted with the
source, exactly as `estimation.SensorSpec` and `avionics.Component` do it. Where a figure
had to be read off a curve rather than a table, the note says so -- see `SERVO_ACTIVE_A`,
which is the least precise number in this file and the one two findings rest on.

Regenerate with `python scripts/flight_computer_report.py`; the verdict is carried by
`scripts/baseline.py` so it cannot silently regress. Write-up in
`docs/14-flight-computer-bom.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import control
from . import estimation as est
from . import packaging

# Required ratio of available to required, matching every other module in this project
# (hinge.py, bay.py, motor_mount.py, seal.py). Applied here to battery energy and to
# storage capacity.
MARGIN_REQUIRED = 2.0

# How long the vehicle sits on the pad, armed, before the button is pushed. THIS IS THE
# ENERGY BUDGET'S DRIVING CASE and it is not a flight number: the flight is about two
# minutes and the pad is up to an hour. A capacity check run over the flight alone answers
# the wrong question by a factor of thirty.
PAD_TIME_S = 3600.0

# Reserve fraction of the pack that is not usable. A LiPo taken below ~20% under load sags,
# and a scrubbed launch that gets recycled wants the margin too.
BATTERY_USABLE_FRACTION = 0.80

# Buck converter efficiency, 2S down to 3.3 V. 0.85 is conservative for a modern synchronous
# part at these currents; it makes the logic rail look worse, not better.
BUCK_EFFICIENCY = 0.85

# Descent rate used ONLY to bound the logging and power window. `configure.py` sizes the
# main canopy for 5.0 m/s and the drogue leg is much faster, so treating the WHOLE descent
# as if it ran at the main's rate overstates the time. That is deliberate: this constant can
# only ever make the log buffer and the battery reserve too big, never too small. It is not
# a vehicle number and nothing else should import it.
DESCENT_RATE_BOUND = 5.0  # m/s

# R15's two launch elevations. NOT in configure.py -- `scripts/sil_demo.py` carries them the
# same way and says so, because the freeze is a rail angle rather than a vehicle parameter.
# 28 deg is the horizontal mode and it is the SIZING one here: a flat flight's max q is
# ~15.5 kPa against ~12.4 vertical, hinge moment goes as q, and so does servo current.
LAUNCH_ELEVATION_DEG = 28.0


# ---------------------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PartSpec:
    """One orderable line of the BOM.

    `measured` carries the same meaning it does in `estimation.SensorSpec` and
    `avionics.Component`: True means the numbers came off a named part's datasheet and the
    note says which. Nothing here has been bought.

    `current_ma` is the ACTIVE draw on the part's own rail, at the operating point this
    vehicle uses it at -- not a datasheet headline. A GNSS receiver in cold acquisition and
    the same receiver tracking are different numbers, and the budget wants the one it runs
    at for an hour on the pad.
    """

    name: str
    mpn: str
    package: str
    interface: str
    unit_price_usd: float
    qty: int = 1
    mass_kg: float = 0.0
    current_ma: float = 0.0
    rail_v: float = 3.3
    measured: bool = False
    note: str = ""

    @property
    def line_price(self) -> float:
        return self.unit_price_usd * self.qty


# --- the board ---------------------------------------------------------------------------
MCU = PartSpec(
    "MCU", "STM32F405RGT6", "LQFP64", "SPI x3, UART, TIM, SDIO", 10.00,
    mass_kg=0.0005, current_ma=86.0, measured=True,
    note="ST DS8626: 168 MHz Cortex-M4F, 1 MB flash, 192 KB RAM. 86 mA typ at 168 MHz with "
         "all peripherals enabled and ART on -- the conservative row, not the 238 uA/MHz "
         "headline. LQFP64 was chosen in docs/06 partly because it is hand-solderable, "
         "which is what makes a one-board spin recoverable")

IMU = PartSpec(
    "IMU", "ICM-42688-P", "LGA-14, 2.5 x 3.0 mm", "SPI (CS1)", 8.00,
    mass_kg=0.0002, current_ma=0.88, measured=True,
    note="TDK: +/-2000 dps, +/-16 g, 32 kHz max ODR, SPI to 24 MHz, 0.0028 deg/sqrt(s) ARW, "
         "+/-0.5% sensitivity tolerance. SELECTED -- see the gyro resolution below. It is "
         "also the part with the deepest ArduPilot/Betaflight driver history, which for a "
         "first board is worth more than any spec line on the alternative")

MAG = PartSpec(
    "magnetometer", "MMC5983MA", "LGA-16, 3.0 x 3.0 mm", "SPI (CS2)", 5.00,
    mass_kg=0.0001, current_ma=1.0, measured=True,
    note="MEMSIC: +/-8 gauss, 0.4 mgauss RMS, 1 kHz max ODR. Range is what matters, not "
         "noise -- estimation.mag_aided_roll_error() shows the sensor's noise is never the "
         "limit and the airframe's own field is. SPI, not I2C: it is flight-critical, "
         "because roll angle is unobservable without it and L1 is the minimum success "
         "criterion")

BARO = PartSpec(
    "barometer", "MS5611-01BA03", "QFN-8, 5.0 x 3.0 mm", "SPI (CS3)", 10.00,
    mass_kg=0.0002, current_ma=1.0, measured=True,
    note="TE: 1.5 Pa RMS at OSR 4096. Sensor grade is irrelevant to this buy -- "
         "estimation.baro_altitude_error() puts static port error two orders above sensor "
         "noise. Bought for continuity with the modelled part; a BMP390 would also do")

GNSS = PartSpec(
    "GNSS receiver", "MAX-M10S", "LCC, 9.7 x 10.1 mm", "UART1", 30.00,
    mass_kg=0.0016, current_ma=8.5, measured=True,
    note="u-blox: 25 mW in continuous tracking, so ~8.5 mA at 3.0 V; acquisition is higher "
         "and is the pad case. 10 Hz nav rate, airborne <4 g dynamic model is the highest "
         "offered -- and estimation.gnss_position_lag() already flags that this vehicle's "
         "6.3 g boost EXCEEDS it, so expect lock loss through boost and do not design the "
         "estimator to need GNSS before burnout")

FLASH = PartSpec(
    "log flash", "W25Q128JVSIQ", "SOIC-8 208 mil", "SPI (CS4)", 2.00,
    mass_kg=0.0001, current_ma=15.0, measured=True,
    note="Winbond: 16 MiB, 133 MHz SPI. SOLDERED, not a microSD socket -- see the storage "
         "finding. 15 mA is the read/program figure and it is only drawn while writing")

BUCK = PartSpec(
    "3.3 V regulator", "TPS62162DSGT", "SON-8", "2S in, 3.3 V out", 2.50,
    mass_kg=0.0003, current_ma=0.0, rail_v=7.4, measured=True,
    note="TI: 3-17 V in, 1 A out, synchronous buck. Sized by the logic rail below with room "
         "to spare; the 1 A part is chosen for headroom and package, not for the load")

ANTENNA = PartSpec(
    "GNSS antenna", "chip or patch, u.FL", "25 x 25 mm patch typ.", "RF", 8.00,
    mass_kg=0.0080,
    note="ESTIMATE. The patch sets the board footprint (avionics.py already says so) and it "
         "is the one part here whose size is a layout decision rather than a purchase. The "
         "G12 airframe is RF-transparent, so it can stay on-board")

PASSIVES = PartSpec(
    "passives, connectors, LEDs, SWD header", "assorted", "0402/0603", "-", 20.00,
    mass_kg=0.0060,
    note="ESTIMATE. Decoupling, the servo header, an 18 AWG XT30 battery pigtail, an arming/status "
         "LED pair and a 4-pin SWD header. Order 2-3x of every passive value; the shipping "
         "costs more than the parts")

PCB = PartSpec(
    "PCB, 4-layer", "70 x 45 mm, 1.6 mm, ENIG", "4L", "-", 30.00,
    mass_kg=0.0120,
    note="ESTIMATE, and it is a FAB cost not a parts cost -- see the price split. 4 layers "
         "because a solid ground plane under the IMU and a separate servo-current return "
         "are the two things that keep this board's own noise out of its own sensors")

BOARD_BOM: list[PartSpec] = [MCU, IMU, MAG, BARO, GNSS, FLASH, BUCK, ANTENNA, PASSIVES, PCB]

# --- bought whole, not on the board ------------------------------------------------------
ALTIMETER = PartSpec(
    "deployment altimeter", "PerfectFlite StratoLoggerCF", "50.8 x 21.3 x 12.7 mm", "-",
    70.00, mass_kg=0.0108, current_ma=1.5, rail_v=9.0, measured=True,
    note="perfectflite.com. FIRES THE CHARGES, AND IT IS NOT THIS BOARD. Independent power, "
         "independent arming. A guidance-software bug must be able to lose the mission "
         "without losing the vehicle -- and the range approval conversation is easier")

BATTERY = PartSpec(
    # XT30, not JST-GH: GH is rated 1 A per contact against 4.1 A all-four-servos-stalled.
    # The board takes an 18 AWG XT30 pigtail on wire pads (pcb/README.md, 2026-09-24).
    "battery", "2S LiPo 1500 mAh", "70 x 35 x 15 mm", "XT30", 20.00,
    mass_kg=0.0900, rail_v=7.4,
    note="ESTIMATE, carried from mass.py and docs/04. 2S because the KST X08 Plus is an "
         "8.4 V-rated HV servo -- see the power finding, which is that this pack is sized "
         "by convention rather than by energy and is about 10x larger than the flight needs")

# Stated once, beside the part it describes. mass.py and docs/04 both carry "2S 1500 mAh"
# as prose; this is the same number as a quantity, and the finding below is that it is about
# ten times what the flight needs.
BATTERY_CAPACITY_MAH = 1500.0

SPARES: list[PartSpec] = [
    PartSpec("spare IMU", "ICM-42688-P", "LGA-14", "SPI", 8.00, qty=1, measured=True,
             note="the classic three-days-before-a-launch-window part"),
    PartSpec("spare magnetometer", "MMC5983MA", "LGA-16", "SPI", 5.00, qty=1, measured=True),
]

BRINGUP_JIG = PartSpec(
    "firmware bring-up jig", "NUCLEO-F446RE (or WeAct F405 'Blackpill')", "board", "USB/SWD",
    15.00, note="OPTIONAL and not part of the flight BOM. Somewhere to write and step the "
                "SPI drivers, the scheduler and the R12 latch before the real board exists. "
                "Same core family, so the drivers port")


# ---------------------------------------------------------------------------------------
# THE GYRO RESOLUTION -- docs/06's "still open" item, closed
# ---------------------------------------------------------------------------------------
# docs/06 asks for a part with SELECTABLE full scale to +/-4000 dps, run at +/-2000, on the
# grounds that the option is free before layout and unbuildable after. The answer is to
# DROP THAT REQUIREMENT, and the argument is not that the wider parts are bad -- it is that
# this vehicle cannot use the range:
#
#   1. THE ROLL CAP IS LOCKED AND IT IS WHAT KEEPS THE PART IN RANGE. R13's
#      ROLL_COMMAND_CAP_DEG = 2.0 puts steady roll at ~28% of a +/-2000 dps part. There is
#      3.5x of margin at every commanded operating point.
#   2. RANGE DOES NOT LICENSE LIFTING THE CAP, and correction 58 already proved it: 7.94 deg
#      capped against 62.89 deg uncapped, BOTH dominated by gyro scale factor at roll rate.
#      The roll rate that saturates the part is the same one that drives the dominant error
#      term, so a wider part uncapped is ~8x WORSE, not better. L1 is hold roll angle.
#   3. THE ONLY CONDITION THAT SATURATES +/-2000 IS A FAULT -- a hardover running deflection
#      to the stops, which R13 forbids as a command. And a gyro pegged at full scale is
#      DETECTABLE. Wiring FS saturation to the R12 latch turns the one scenario the extra
#      range was for into a detected fault that centres the canards within 0.5 s, which is
#      strictly better than measuring the fault accurately while flying it. That is free.
#
# So `GYRO_WIDE` is gone. `estimation.GYRO_ICM45686` replaces it -- the REAL part that does
# what docs/06 asked for, so the rejection is against hardware rather than against a
# placeholder. It is rejected on three counts, none of which is availability: the range is
# unusable while the roll cap holds, its rate noise is ~36% worse, and its driver ecosystem
# is far younger than the ICM-42688-P's. For a first board that last one decides it.
GYRO_ALTERNATE_ICM45686 = est.GYRO_ICM45686

# The selected part's range, named once so the checks below cannot drift from the BOM.
IMU_FULL_SCALE_DEG_S = est.GYRO_ICM42688.full_scale_deg_s


# ---------------------------------------------------------------------------------------
# Power
# ---------------------------------------------------------------------------------------
# Read off the KST X08 Plus V6.0 datasheet's own torque/speed/current curve at 7.4 V
# (KST_0012, 04/2025). THE CURVE IS A CHART, NOT A TABLE, so these are eyeball reads and are
# the least precise numbers in this file -- they are marked as such wherever they surface.
# The chart also carries an OPERATION MODEL banding that no spec table would have shown:
# continuous duty only to ~1.2 kgf.cm, "short time <10 s repeat" to ~4.8, and a red
# <1 s / 60 s cool zone beyond. That banding is the second power finding.
SERVO_NO_LOAD_A = 0.10      # A at 7.4 V, chart intercept at zero torque
SERVO_STALL_A = 1.00        # A at 7.4 V, chart's right-hand limit
SERVO_CONTINUOUS_KGFCM = 1.2  # end of the green continuous band on the same chart
SERVO_CHART_MAX_KGFCM = 6.0   # x-axis limit the stall current is read at
SERVO_IDLE_A = 0.010        # APPROX -- not on the datasheet at all. A digital servo holding
                            # position with no disturbance. Sourced from nothing; it is
                            # small enough that the pad budget is insensitive to it, and
                            # that insensitivity is checked rather than assumed.
KGFCM_PER_NM = 1.0 / 0.0980665


def servo_current_at(hinge_moment_nm: float) -> float:
    """Per-servo current at a given hinge moment, off the datasheet curve at 7.4 V.

    Linear between the no-load intercept and the stall point, which is what the chart's
    own dashed line is to within its own line width.
    """
    kgfcm = abs(hinge_moment_nm) * KGFCM_PER_NM
    frac = min(kgfcm / SERVO_CHART_MAX_KGFCM, 1.0)
    return SERVO_NO_LOAD_A + frac * (SERVO_STALL_A - SERVO_NO_LOAD_A)


def peak_hinge_moment(ev, elevation_deg: float = LAUNCH_ELEVATION_DEG) -> float:
    """Worst hinge moment per panel, priced at the HORIZONTAL flight's own dynamic pressure.

    This is `horizontal_agility_sweep.Candidate`'s method, not a new one: take the worst
    point of the vertical trajectory, raise its q to the flat flight's max, and ask
    `control.pitch_authority` what the panel does there. Hinge moment is linear in q, so
    sizing the servo on the vertical number understates it by the ratio of the two -- and
    R15 makes the flat flight the primary mode. `baseline.py` reports the VERTICAL margin
    (2.5x); the frozen 2.07x in configure.py's own comment is this one.
    """
    from dataclasses import replace

    from . import horizontal
    from .configure import DEFLECTION_LIMIT_DEG

    worst = max(ev.flight.points, key=lambda p: p.q)
    hz = horizontal.fly(ev.rocket, ev.params.motor, ev.masses,
                        elevation_deg=elevation_deg,
                        deflection_deg=DEFLECTION_LIMIT_DEG, dt=0.01)
    probe = replace(worst, q=max(hz.max_q, worst.q))
    return abs(control.pitch_authority(
        ev.rocket, probe, probe.mass, DEFLECTION_LIMIT_DEG).hinge_moment_per_panel)


def peak_hinge_moment_cfd_informed(ev, elevation_deg: float = LAUNCH_ELEVATION_DEG) -> float:
    """Same as `peak_hinge_moment`, at `packaging.CP_FRAC_CFD_INFORMED` instead of the 0.25
    design assumption -- see the comment there. Not a replacement number, a second one to
    look at alongside the first."""
    from dataclasses import replace

    from . import horizontal
    from .configure import DEFLECTION_LIMIT_DEG

    worst = max(ev.flight.points, key=lambda p: p.q)
    hz = horizontal.fly(ev.rocket, ev.params.motor, ev.masses,
                        elevation_deg=elevation_deg,
                        deflection_deg=DEFLECTION_LIMIT_DEG, dt=0.01)
    probe = replace(worst, q=max(hz.max_q, worst.q))
    return abs(control.pitch_authority(
        ev.rocket, probe, probe.mass, DEFLECTION_LIMIT_DEG).hinge_moment_per_panel_cfd)


@dataclass
class PowerBudget:
    logic_ma_3v3: float
    logic_w: float
    logic_pack_ma: float          # what the logic costs the 2S pack after buck losses
    servo_count: int
    hinge_moment_nm: float
    servo_active_a: float         # one servo, at the peak hinge moment
    servo_active_total_a: float
    servo_stall_total_a: float
    servo_idle_total_a: float
    peak_pack_a: float
    pad_wh: float
    flight_wh: float
    total_wh: float
    battery_wh: float
    usable_wh: float
    margin: float
    control_seconds: float
    flight_seconds: float
    continuous_duty_margin: float
    stall_torque_margin: float
    hinge_moment_nm_cfd: float          # packaging.CP_FRAC_CFD_INFORMED -- see there
    stall_torque_margin_cfd: float


def power_budget(ev, servo_key: str = "kst_x08_plus") -> PowerBudget:
    """The budget that did not exist. Everything load-side comes from the flight model."""
    servo = packaging.SERVOS[servo_key]
    n_servo = ev.rocket.canards.count
    hm = peak_hinge_moment(ev)
    hm_cfd = peak_hinge_moment_cfd_informed(ev)

    logic_ma = sum(p.current_ma for p in (MCU, IMU, MAG, BARO, GNSS, FLASH))
    logic_w = logic_ma / 1000.0 * 3.3
    pack_v = BATTERY.rail_v
    logic_pack_ma = logic_w / BUCK_EFFICIENCY / pack_v * 1000.0

    per_servo_a = servo_current_at(hm)
    active_total = per_servo_a * n_servo
    stall_total = SERVO_STALL_A * n_servo
    idle_total = SERVO_IDLE_A * n_servo

    # Flight is the whole thing to landing; the servos only work during the control window.
    flight_s = ev.flight.apogee_time + _descent_seconds(ev)
    ctrl_s = ev.control_seconds

    pad_wh = (logic_pack_ma / 1000.0 + idle_total) * pack_v * PAD_TIME_S / 3600.0
    flight_wh = (
        (logic_pack_ma / 1000.0) * pack_v * flight_s
        + active_total * pack_v * ctrl_s
        + idle_total * pack_v * max(flight_s - ctrl_s, 0.0)
    ) / 3600.0

    battery_wh = _battery_wh()
    usable_wh = battery_wh * BATTERY_USABLE_FRACTION
    total_wh = pad_wh + flight_wh

    return PowerBudget(
        logic_ma_3v3=logic_ma, logic_w=logic_w, logic_pack_ma=logic_pack_ma,
        servo_count=n_servo, hinge_moment_nm=hm, servo_active_a=per_servo_a,
        servo_active_total_a=active_total, servo_stall_total_a=stall_total,
        servo_idle_total_a=idle_total,
        peak_pack_a=stall_total + logic_pack_ma / 1000.0,
        pad_wh=pad_wh, flight_wh=flight_wh, total_wh=total_wh,
        battery_wh=battery_wh, usable_wh=usable_wh,
        margin=usable_wh / max(total_wh, 1e-9),
        control_seconds=ctrl_s, flight_seconds=flight_s,
        continuous_duty_margin=SERVO_CONTINUOUS_KGFCM / max(hm * KGFCM_PER_NM, 1e-9),
        stall_torque_margin=packaging.torque_margin(hm, servo),
        hinge_moment_nm_cfd=hm_cfd,
        stall_torque_margin_cfd=packaging.torque_margin(hm_cfd, servo),
    )


def _battery_wh() -> float:
    return BATTERY_CAPACITY_MAH / 1000.0 * BATTERY.rail_v


def _descent_seconds(ev) -> float:
    """Descent under canopy, bounded above. See DESCENT_RATE_BOUND."""
    return ev.flight.apogee / DESCENT_RATE_BOUND


# ---------------------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LogChannel:
    name: str
    bytes_per_sample: int
    rate_hz: float
    why: str

    @property
    def bytes_per_s(self) -> float:
        return self.bytes_per_sample * self.rate_hz


@dataclass
class LogBudget:
    channels: list[LogChannel]
    bytes_per_s: float
    duration_s: float
    total_bytes: float
    onchip_usable_bytes: float
    external_bytes: float
    onchip_margin: float
    external_margin: float
    flights_on_external: float


# The F405 has 1 MB of flash and the firmware lives in it. 256 KB is a generous allowance
# for a HAL-based flight application with a filesystem; the rest could in principle be log.
MCU_FLASH_BYTES = 1024 * 1024
FIRMWARE_ALLOWANCE_BYTES = 256 * 1024
EXTERNAL_FLASH_BYTES = 16 * 1024 * 1024


def log_channels(ev) -> list[LogChannel]:
    """What actually has to be written, and at what rate.

    THE IMU LINE IS THE WHOLE PROBLEM AND IT IS NOT NEGOTIABLE. Logging raw gyro and accel
    at the propagation rate rather than at the loop rate is what makes GV-2 a measurement
    of Cm_delta and Cl_delta instead of an anecdote, and docs/01 calls that flight the one
    the thesis rests on. Drop it to 100 Hz and everything fits in the MCU -- and the flight
    that justifies the vehicle stops producing the data it exists to produce.
    """
    imu_hz = est.required_imu_rate(est.uncapped_roll_rate(ev))
    loop_hz = ev.pitch.pitch_natural_freq_hz * 20.0
    return [
        LogChannel("raw gyro + accel, 6 x int16 + timestamp", 16, imu_hz,
                   "at the PROPAGATION rate, not the loop rate -- this is GV-2's "
                   "measurement of Cm_delta and Cl_delta"),
        LogChannel("magnetometer, 3 x int16 + timestamp", 10, 100.0,
                   "roll aiding; 100 Hz keeps >10 samples per revolution at the cap"),
        LogChannel("baro pressure + temperature, 2 x int32 + ts", 12, 50.0,
                   "apogee and descent; not a boost sensor"),
        LogChannel("GNSS position, velocity, fix quality", 36, 10.0,
                   "the receiver's own nav rate"),
        LogChannel("estimator state: quaternion, roll, rate", 24, loop_hz,
                   "so a post-flight rerun can reproduce what the controller believed"),
        LogChannel("control: 4 servo commands, phase, flags", 12, loop_hz,
                   "what was commanded, against what the vehicle did"),
    ]


def log_budget(ev) -> LogBudget:
    chans = log_channels(ev)
    bps = sum(c.bytes_per_s for c in chans)
    # Armed on the pad through to landing. The log starts before boost detection because a
    # log that starts at liftoff has no pad reference in it.
    duration = _descent_seconds(ev) + ev.flight.apogee_time + 30.0
    total = bps * duration
    onchip = MCU_FLASH_BYTES - FIRMWARE_ALLOWANCE_BYTES
    return LogBudget(
        channels=chans, bytes_per_s=bps, duration_s=duration, total_bytes=total,
        onchip_usable_bytes=onchip, external_bytes=EXTERNAL_FLASH_BYTES,
        onchip_margin=onchip / max(total, 1.0),
        external_margin=EXTERNAL_FLASH_BYTES / max(total, 1.0),
        flights_on_external=EXTERNAL_FLASH_BYTES / max(total, 1.0),
    )


# ---------------------------------------------------------------------------------------
# The board outline, against the sled that has to carry it
# ---------------------------------------------------------------------------------------
# NOT RESTATED. `avionics.STM32_BOARD` is the board's envelope and the sled packing is
# already checked against it; typing 70 x 45 here as well is how a constant in two places
# becomes two different vehicles, which is correction 4 and has recurred five times since.
# If the layout closes at a different outline, change it THERE and every check follows.
def _board() -> "object":
    from . import avionics
    return avionics.STM32_BOARD

# Tallest thing standing off the PCB. The GNSS module and the electrolytic bulk cap on the
# servo feed are the candidates; 8 mm covers either with the 1.6 mm board under it.
TALLEST_COMPONENT = 0.008
PCB_THICKNESS = 0.0016


@dataclass
class EnvelopeCheck:
    board_l: float
    board_w: float
    board_h: float
    stack_h: float
    max_plate_l: float
    max_plate_w: float
    usable_height: float
    length_margin: float
    width_margin: float
    height_margin: float
    fits: bool


def envelope_check(ev) -> EnvelopeCheck:
    """Does the board fit the sled -- and the sled is the arbiter, not this file."""
    from . import sled as sled_mod
    b = _board()
    s = sled_mod.sled_from_evaluation(ev)
    # The sled carries boards on BOTH faces, so one board gets half the inscribed height --
    # the same halving sled.py does when it places components.
    per_face = s.usable_height / 2.0
    stack = PCB_THICKNESS + TALLEST_COMPONENT
    return EnvelopeCheck(
        board_l=b.length, board_w=b.width, board_h=b.height, stack_h=stack,
        max_plate_l=s.plate_length, max_plate_w=s.plate_width,
        usable_height=per_face,
        length_margin=s.plate_length - b.length,
        width_margin=s.plate_width - b.width,
        height_margin=per_face - stack,
        fits=(b.length <= s.plate_length and b.width <= s.plate_width
              and stack <= per_face),
    )


# ---------------------------------------------------------------------------------------
# Price, split honestly
# ---------------------------------------------------------------------------------------
@dataclass
class PriceSplit:
    parts: float
    fab: float
    bought_whole: float
    spares: float
    total_hand_assembled: float
    total_with_pcba: float


PCBA_SETUP_USD = 120.0  # stencil, feeder setup and one-off assembly at a low-volume house


def price_split() -> PriceSplit:
    fab = PCB.line_price
    parts = sum(p.line_price for p in BOARD_BOM) - fab
    bought = ALTIMETER.line_price + BATTERY.line_price
    spares = sum(p.line_price for p in SPARES)
    return PriceSplit(
        parts=parts, fab=fab, bought_whole=bought, spares=spares,
        total_hand_assembled=parts + fab + bought + spares,
        total_with_pcba=parts + fab + bought + spares + PCBA_SETUP_USD,
    )


# ---------------------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------------------
@dataclass
class FlightComputerCheck:
    ok: bool
    violations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def check_flight_computer(ev) -> FlightComputerCheck:
    """Everything that must hold before a board is ordered.

    A check that has never failed is not evidence of anything, so this one is written to be
    failable: the storage line fails on the F405's own flash, which is the point.
    """
    v: list[str] = []
    n: list[str] = []

    p = power_budget(ev)
    lb = log_budget(ev)
    e = envelope_check(ev)

    if p.margin < MARGIN_REQUIRED:
        v.append(f"battery energy margin {p.margin:.2f}x < {MARGIN_REQUIRED:.1f}x "
                 f"({p.total_wh:.2f} Wh needed, {p.usable_wh:.2f} Wh usable)")
    else:
        n.append(f"battery energy margin {p.margin:.1f}x -- the pack is sized by CONVENTION, "
                 f"not by energy. {p.pad_wh:.2f} Wh of the {p.total_wh:.2f} Wh is the "
                 f"{PAD_TIME_S / 60:.0f} min on the pad and only {p.flight_wh:.3f} Wh is the "
                 f"flight")

    if p.peak_pack_a > 0.0:
        n.append(f"peak pack current {p.peak_pack_a:.1f} A (four servos stalled) -- this, "
                 f"not capacity, is what sizes the pack's C-rating, the battery lead and "
                 f"the 14 conductors through the potted pass-through")

    if p.continuous_duty_margin < 1.0:
        v.append(f"servo continuous-duty margin {p.continuous_duty_margin:.2f}x: the "
                 f"{p.hinge_moment_nm * KGFCM_PER_NM:.2f} kgf.cm hinge moment is outside the "
                 f"datasheet's continuous band")
    else:
        n.append(f"servo duty: {p.stall_torque_margin:.2f}x on STALL torque but only "
                 f"{p.continuous_duty_margin:.2f}x on the datasheet's own CONTINUOUS band "
                 f"({SERVO_CONTINUOUS_KGFCM:.1f} kgf.cm) -- a margin the torque check "
                 f"cannot see, read off a curve and worth measuring on a real part")

    if lb.onchip_margin < 1.0:
        n.append(f"storage: {lb.total_bytes / 1e6:.2f} MB per flight against "
                 f"{lb.onchip_usable_bytes / 1e6:.2f} MB usable on the F405 -- "
                 f"{1 / lb.onchip_margin:.1f}x SHORT. External flash is not a convenience")
    if lb.external_margin < MARGIN_REQUIRED:
        v.append(f"external flash margin {lb.external_margin:.2f}x < {MARGIN_REQUIRED:.1f}x")
    else:
        n.append(f"external flash {lb.external_bytes / 1e6:.0f} MB holds "
                 f"{lb.flights_on_external:.1f} flights")

    if not e.fits:
        v.append(f"board {e.board_l * 1000:.0f} x {e.board_w * 1000:.0f} mm does not fit the "
                 f"sled plate {e.max_plate_l * 1000:.1f} x {e.max_plate_w * 1000:.1f} mm")
    else:
        n.append(f"board fits the sled with {e.width_margin * 1000:.1f} mm across and "
                 f"{e.height_margin * 1000:.1f} mm of headroom over a "
                 f"{e.stack_h * 1000:.1f} mm stack")

    imu_hz = est.required_imu_rate(est.uncapped_roll_rate(ev))
    if imu_hz > 32000.0:
        v.append(f"required IMU rate {imu_hz:.0f} Hz exceeds the ICM-42688-P's 32 kHz")
    else:
        n.append(f"IMU rate: {imu_hz:.0f} Hz required against 32 kHz available, {32000 / imu_hz:.0f}x")

    capped = est.capped_roll_rate(ev)
    if capped > IMU_FULL_SCALE_DEG_S:
        v.append(f"capped roll rate {capped:.0f} deg/s saturates the "
                 f"{IMU_FULL_SCALE_DEG_S:.0f} dps gyro")
    else:
        n.append(f"gyro: {capped:.0f} deg/s at the roll cap is "
                 f"{capped / IMU_FULL_SCALE_DEG_S * 100:.0f}% of +/-{IMU_FULL_SCALE_DEG_S:.0f} "
                 f"dps. Uncapped it is {est.uncapped_roll_rate(ev):.0f} deg/s and SATURATES -- "
                 f"which is a fault condition, is detectable, and is wired to the R12 latch "
                 f"rather than bought around")

    return FlightComputerCheck(ok=not v, violations=v, notes=n)
