# D7 — Flight computer selection

Regenerate the numbers with `python scripts/avionics_trade.py`. Nothing here is typed twice;
every figure comes from `design/avionics.py` and the flight model.

## Decision

**A custom STM32 board flies the guided vehicle, and a breakout stack flies the cert
flights.** Staged, in that order, and the staging is the decision — not a hedge.

| | flies | what it is |
|---|---|---|
| **Stage 1** | L1 and L2 cert, as a passive logger | Teensy 4.1 + IMU/baro/GNSS breakouts + StratoLoggerCF |
| **Stage 2** | GV-1 onward | Custom STM32F405 board + StratoLoggerCF |

The board's sensor set is D8's, not D7's: **IMU, magnetometer, baro, GNSS** — see
`07-state-estimation.md`. The magnetometer was added after D7 closed, because roll angle
is unobservable without one.

Deployment stays on the **independent commercial altimeter in both stages**. It is not on
the custom board and it is not on the Teensy.

## Why a custom board at all

The engineering case is weak and the career case is strong, and it is worth saying which is
which.

**The engineering case does not survive contact with the numbers.** The obvious argument for
an integrated board is packaging — the nav bay was 9 mm short and one PCB ought to beat a dev
board plus three breakouts. It does not:

| | sled needed | margin |
|---|---|---|
| A. Dev board + breakouts | 107.1 mm | +7.9 mm |
| B. TeleMega + guidance board | 109.6 mm | +5.5 mm |
| **C. Custom STM32 board** | **110.4 mm** | **+4.6 mm** |

The breakouts are postage stamps (25.4 × 17.8 mm) and a Teensy 4.1 is narrow (61 × 17.8).
**Option C needs more sled than option A.** So the packaging argument for eight weeks of
hardware work is not there, and dressing the choice up as one would be dishonest.

**The career case is real and it is the actual reason.** The stated goal is to show defense
employers hardware capability. A board taken from requirements through schematic, layout,
fab, bring-up and flight is a substantially stronger artifact than a soldered protoboard, and
**STM32 specifically is the right family for that audience** — it is what ArduPilot and PX4
run on, and it is what is inside the flight controllers those employers actually build.
Teensy is a hobbyist ecosystem; STM32 with HAL or bare metal is professional practice.

That is a legitimate input to a capstone decision. It is not an engineering justification,
and this document does not pretend it is one.

## Why staged, and why staging helps the career case too

The cost of the custom board is schedule, and the schedule lands somewhere expensive.
`docs/01` step 6 flies the avionics as a **passive logger in the L1 and L2 cert flights** so
that the sensor stack has real boost data behind it before it ever flies in the guided
vehicle. Cert launches are monthly and weather-dependent. Eight weeks of board work before
anything can log means those launch days pass with no data, and that data cannot be bought
back later.

Stage 1 removes that entirely. A breakout stack exists in a week, flies as a passenger, and
**every line of the interesting software is identical** — the attitude filter, the HIL rig,
the controller and the safety logic do not care what the sensors are soldered to.

Three things follow that are worth having anyway:

- **The breakout stack becomes the HIL target and the reference implementation.** Board
  bring-up against a known-good reference is a different job from bring-up against nothing.
- **It separates two failures that otherwise arrive together.** If the first board does not
  come up, you find out whether the problem is the hardware or the filter, because the filter
  already flew.
- **It reads better, not worse.** "I breadboarded it, flew it, then spun a board" is staged
  risk retirement. That is what an interviewer is actually looking for, more than a PCB.

## The board

**STM32F405RGT6, LQFP64.** 168 MHz Cortex-M4F, 1 MB flash, hand-solderable package, and
there are open ArduPilot/Betaflight target schematics for it you can read. An STM32H743 is
the Pixhawk-class part and is more impressive on paper; it is also a harder first layout —
more rails, finer pitch, harder bring-up. **Picking a part you can actually bring up is
itself the engineering judgment the audience is looking for**, and if the F4 board flies, an
H7 spin afterwards is a week.

### What it has to do, derived from this vehicle

Every one of these comes out of the flight model, not a tutorial. `board_requirements()` in
`design/avionics.py` computes them.

| requirement | value | why |
|---|---|---|
| **gyro full scale** | **≥ ±2000 °/s**, *and the roll command capped*. Prefer a part with **selectable** FS to ±4000, **run at ±2000** | see the correction below — 594 °/s at the 2° roll cap, **2378 °/s at the 8° limit**. The wider range is an option to hold, not to use: correction 58 |
| **IMU output data rate** | **≥ 1 kHz** | not the loop rate: quaternion propagation at 100 Hz drifts 33.3 °/s with a perfect gyro (D8) |
| **magnetometer** | **required** | roll angle is unobservable without one, and L1 is the minimum success criterion (D8) |
| accelerometer | ≥ ±16 g | peak axial 8.3 g, plus ignition and ejection transients |
| loop rate | ≥ 86 Hz | pitch mode 4.30 Hz, and a digital loop wants 20× the mode it closes |
| servo drive | 4 ch, 333 Hz | four KST X08 Plus at 667 °/s; **separate supply from the IMU** |
| logging | ≥ 100 Hz for 150 s | apogee at 17 s, whole flight to landing about 120 s |
| deployment | **not on this board** | independent commercial altimeter fires the charges |

### The one that is tight — and this section was wrong when it was written

It used to say: *"steady roll rate at full canard deflection is 1783 °/s — 89% of a ±2000 °/s
gyro's range."* **Both halves of that are wrong, and D8 found it.** Steady roll rate is
*linear* in deflection, and 1783 °/s is the **6°** figure — `evaluate()`'s default, which
`avionics_trade.py` happened to take — printed under an 8° heading:

| deflection | roll rate | of ±2000 dps | |
|---|---|---|---|
| 2° | 594 °/s | 30 % | the roll command cap |
| 6° | 1783 °/s | 89 % | `evaluate()`'s default — *what this document quoted* |
| **8°** | **2378 °/s** | **119 % — SATURATED** | the deflection limit |

A saturated rate gyro in a roll loop is not a degraded measurement, it is a wrong one, and
the controller cannot tell. That part was right. What was wrong is the comfort: **the error
and the reassurance came from the same place**, because a 33 % understatement is exactly what
turns a saturated part into a comfortable-looking 89 %.

The corrected statement: **a ±2000 dps gyro is adequate only because the roll command is
capped at 2°.** So the first way out below is not one option of three, it is a requirement:

1. **Cap the roll command — not optional.** Roll needs far less deflection than pitch because
   roll inertia is tiny, and `ROLL_DEFLECTION_DEG = 2.0` already existed in `baseline.py` as a
   control convenience. It is now **load-bearing for the sensor**: it is what keeps the gyro
   in range, and a fault that runs the canards to the stops takes the attitude estimate with
   it as well as the vehicle.
2. **Pick a wider part.** Some IMUs reach ±4000 °/s. It is a line in a datasheet and costs
   nothing at design time, *if you check before layout*.
3. **Measure it on GV-2.** That flight exists to turn `Cl_delta` from an assumption into a
   measurement, and this number is downstream of `Cl_delta` — which `docs/01` calls the
   weakest part of the whole analysis.

Both deflection limits now live in `design/configure.py` and `Evaluation` records the one it
was evaluated at, so a document cannot quote one caller's answer under another's heading
again. That is correction 4 recurring — see `docs/01` correction 36.

## What this closed on the way past

**The nav bay's 9 mm shortfall was an artefact of the guesses.** Every architecture fits.
The cause is a single line: the guessed "flight computer PCB" was 70 × 40 mm = 28.0 cm²
against a real Teensy 4.1 at 61 × 17.8 = 10.9 cm². The guess was two and a half times the
part.

**This is correction 5 replaying, and it vindicates not having lengthened the airframe** —
an estimate-driven shortfall, nearly acted on, that was not in the hardware. That rule has
now held twice.

Two envelopes moved the other way, stated so this does not read as good news only: the
StratoLoggerCF is 50.8 × 21.3 mm against a guessed 45 × 18, and a GNSS patch antenna is
larger than the receiver behind it.

## Option B, and why not

TeleMega collapses altimeter, telemetry, tracker and GNSS into one 1.25 × 3.25 in board, and
that is genuinely tidy. Two reasons it loses:

- It needs a **HAM licence** for the telemetry.
- It puts **tracking back in the nav bay**, which undoes the swappable nose module of
  correction 32 — the whole point of which is that the instrumentation comes out later and a
  payload goes in.

It stays on the list because if the custom board slips badly, B is the fastest route to a
fully instrumented vehicle.

## Still open

- ~~**SPECIFY A GYRO WITH SELECTABLE FULL SCALE TO ±4000 dps**~~ **CLOSED, AND THE
  REQUIREMENT IS DROPPED — `14-flight-computer-bom.md`, correction 64.** The bullet below is
  kept as written because its reasoning is still right; only its conclusion is reversed.
  Three things settled it:
  1. The option is **real** — TDK's ICM-45686 does ±4000 dps and ±32 g for about the same
     money — so this is a decision against hardware, not a shortage. `GYRO_WIDE`, the
     `measured=False` placeholder everything below was checked against, is deleted;
     `estimation.GYRO_ICM45686` replaces it.
  2. The range is **unusable while the roll cap holds**, and the bullet below is what proves
     it. The cap is R13 and it is locked.
  3. The one condition that saturates ±2000 dps is a **fault** — 2602 °/s at the deflection
     limit, which R13 forbids as a command — and **a gyro pegged at full scale is
     detectable.** Wiring FS saturation into the R12 latch turns that scenario into a
     detected fault that centres the canards inside 0.5 s. That is better than measuring the
     fault accurately while flying it, and it is free.

  Also closed on the way past: the bullet below ends "the number that would decide this does
  not exist yet — `attitude_error_budget()` is gyro-only." **Correction 59 built it.** Aided,
  the 7.94°/62.89° pair becomes 0.08°/0.12°, and what limits roll angle is the airframe's own
  magnetic cleanliness, not the sensor.

- **THE NUMBERS IN THE REQUIREMENTS TABLE ABOVE ARE PRE-CORRECTION-63 AND ARE STALE.**
  They are left in place because the table's *arguments* are unchanged and rewriting a
  document to match a regenerated number is how this project loses the record of what it
  used to believe. Current values, from `python scripts/flight_computer_report.py`:

  | table says | now | why it moved |
  |---|---|---|
  | 594 °/s at the 2° cap | **566 °/s** | corrections 60–63 |
  | 2378 °/s at the 8° limit | **2602 °/s at the 9.2° limit** | R13's deflection cap moved |
  | peak axial 8.3 g | **6.3 g vertical, 7.1 g horizontal** | correction 62's freeze |
  | loop rate ≥ 86 Hz | **≥ 72 Hz** | pitch mode 4.30 → 3.6 Hz |
  | drift 33.3 °/s at 100 Hz | **43.4 °/s** | it scales with roll rate, which grew |

  The requirement that did NOT move is the IMU rate: still **≥ 1 kHz**, and it now passes its
  own 0.5 °/s budget by only 11%, which is why `docs/14` buys a part that does 32 kHz.

- **SUPERSEDED — the original bullet, kept for its reasoning.**
  **SPECIFY A GYRO WITH SELECTABLE FULL SCALE TO ±4000 dps — AND RUN IT AT ±2000**
  (`docs/01` correction 58, which reverses correction 55). Way out 1 above — *"cap the roll
  command — not optional"* — is still the right answer, and way out 2 ("pick a wider part")
  does **not** let you lift the cap. Correction 55 claimed it did, on the saturation
  arithmetic alone. Running `estimation.attitude_error_budget()` at both operating points
  settles it:

  | | roll rate | RSS attitude error at apogee |
  |---|---|---|
  | ICM-42688-P at the 2° cap | 558 °/s | **7.94°** |
  | ±4000 dps part at the 8° limit | 2232 °/s | **62.89°** |

  Both are dominated by **gyro scale factor at roll rate**, and the roll rate that saturates
  the part is the same one that drives that term — so range does not buy the ability to use
  it, and uncapped the wide part is **8× worse**. L1 is *hold roll angle*.

  So what is free before the schematic is the **option**, not the capability: a selectable-FS
  part costs nothing, keeps today's resolution and scale-factor behaviour at ±2000, and
  leaves ±4000 one register write away if the estimator ever earns it. **The lever that
  actually moves the dominant term is scale-factor CALIBRATION** — the 0.5% in the budget is
  a datasheet spec limit; measured per unit against a rate table it is nearer 0.05–0.1%,
  which is 5–10× off 99% of the budget, for a procedure and no hardware.

  **And the number that would decide this does not exist yet:** `attitude_error_budget()` is
  gyro-only — there is no magnetometer term in it — so 62.89° is the *unaided* figure, while
  bounding roll angle is the whole reason D8 added the magnetometer. Build the aided model
  before revisiting the cap.
- ~~**D8, state estimation.**~~ **CLOSED** — `07-state-estimation.md`. It added a
  magnetometer to this board and two requirements to the table above, and it found the gyro
  error corrected in the section before this one. All three were free before layout and
  unrecoverable after, which is the argument for having closed it before the schematic.
- **Every envelope in `design/avionics.py` that is not marked `measured`.** Three parts are
  now off datasheets; the rest are still correction 5 material, and the custom board's
  70 × 45 mm is a *layout target* rather than a measurement — the one line here whose
  accuracy is under your control.

---

## Where the boards physically go — Sep 2026

The sled these boards mount on is a part now: **`docs/08-nav-bay-sled.md`**,
`design/sled.py`, `python scripts/sled_report.py`.

Drawing it changed one number that belongs here. The board footprint above is **70 × 45 mm
and is a layout target, not a measurement** — and it is now the line with the least room in
it. Placing the selected stack as real rectangles rather than as summed area shows the four
boards fit comfortably, and the **80 g wiring loom** then does not: the sled has to widen
from `0.80` of the bore to **0.846**, and past that point width is bought out of the tallest
component's headroom, of which there is **3.0 mm**. Anything that grows the board — in
footprint *or* in height — grows that problem, and anything that shrinks it is the cheapest
fix available.

Two things in this document are still the binding unknowns for that packing, and both are
under your control: the **board outline**, and the **conductor count** the loom carries.

---

## What goes on the board — Sep 2026

**`14-flight-computer-bom.md`**, `design/flight_computer.py`,
`python scripts/flight_computer_report.py`. The board this document selected is specified to
the point of an order: STM32F405RGT6, ICM-42688-P, MMC5983MA, MS5611, MAX-M10S, W25Q128JV,
SPI for every flight-critical sensor and UART for the GNSS. **$228 hand-assembled, $348 with
low-volume PCBA** — against the flat $400 `docs/04` §5 carries, which turns out to hide a 3:1
split between silicon and fab.

Three things it found that this document could not have:

- **There is no BEC.** The KST X08 Plus is rated DC 3.8–8.4 V and the pack is 2S, so the
  servos run directly off the battery. Reported, not adopted — it is 25 g and a line item,
  and it changes a frozen stack.
- **Servo torque margin is 2.03× on stall and 1.15× on the datasheet's own CONTINUOUS-duty
  band.** Two different failure modes, and this project had only ever looked at the first.
- **"Onboard flash is enough" was wrong by 6×.** 4.9 MB a flight against 0.79 MB usable, and
  the channel that causes it is the one GV-2 exists to record.
