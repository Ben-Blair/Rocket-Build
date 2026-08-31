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
| **gyro full scale** | **≥ ±2000 °/s** | steady roll at 8° of canard is **1783 °/s** |
| accelerometer | ≥ ±16 g | peak axial 8.3 g, plus ignition and ejection transients |
| loop rate | ≥ 86 Hz | pitch mode 4.30 Hz, and a digital loop wants 20× the mode it closes |
| servo drive | 4 ch, 333 Hz | four KST X08 Plus at 667 °/s; **separate supply from the IMU** |
| logging | ≥ 100 Hz for 150 s | apogee at 17 s, whole flight to landing about 120 s |
| deployment | **not on this board** | independent commercial altimeter fires the charges |

### The one that is tight

**Steady roll rate at full canard deflection is 1783 °/s — 89% of a ±2000 °/s gyro's range,
and many IMUs are ±1000.**

A saturated rate gyro in a roll loop is not a degraded measurement, it is a wrong one, and
the controller cannot tell. This is the requirement no tutorial would have produced, and it
would have been found in flight.

Three ways out; do the first two, they are free and not exclusive:

1. **Cap the roll command.** Roll needs far less deflection than pitch because roll inertia
   is tiny — `baseline.py` already says so. At 2° the rate is about a quarter of this.
2. **Pick a wider part.** Some IMUs reach ±4000 °/s. It is a line in a datasheet and costs
   nothing at design time, *if you check before layout*.
3. **Measure it on GV-2.** That flight exists to turn `Cl_delta` from an assumption into a
   measurement, and this number is downstream of `Cl_delta` — which `docs/01` calls the
   weakest part of the whole analysis.

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

- **D8, state estimation**, follows from this board's sensor set and is where most of the
  interesting engineering lives.
- **Every envelope in `design/avionics.py` that is not marked `measured`.** Three parts are
  now off datasheets; the rest are still correction 5 material, and the custom board's
  70 × 45 mm is a *layout target* rather than a measurement — the one line here whose
  accuracy is under your control.
