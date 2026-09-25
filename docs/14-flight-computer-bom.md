# 14. The Stage 2 flight computer — what to order, and the three things nobody had checked

Model: `design/flight_computer.py`. Regenerate with `python scripts/flight_computer_report.py
--write` (output `out/flight_computer.txt`); the verdict is carried by `scripts/baseline.py`
so it cannot silently regress. Sensor error terms come from `design/estimation.py` (D8) and
the architecture decision from `docs/06` (D7). Nothing here is typed twice: every rate,
duration and load is computed from `configure.evaluate()`, and every part number is a
datasheet value with the source in its note. This document IS correction 64 — like 61–63 it
lives in its own topic file, with the summary in `docs/01`'s state-of-play block rather than
in that file's numbered list, which ends at 60.

## The headline: the board was selected two documents ago and could not be ordered

`docs/06` chose a custom STM32F405 board with the ejection charges left on an independent
commercial altimeter. `docs/07` named its sensors. Between them they left three gaps, and
none of them was visible from either document:

1. **A gyro requirement no real part satisfied.** `docs/06` asked for selectable full scale
   to ±4000 °/s. The named part tops out at ±2000, and the only ±4000 entry in the code was
   an estimate with no part number — `design/estimation.py`'s own rule ("a requirement you
   cannot buy a part against is not a requirement") broken inside `design/estimation.py`.
2. **No power budget anywhere in this project.** The battery was a line in `mass.py` with a
   capacity and a mass and nothing else. The servos were modelled for torque and speed only.
   Nothing had ever asked whether the pack covers a flight.
3. **Logging had never been turned into bytes.** `avionics.board_requirements()` asks for
   "≥ 100 Hz for 150 s" and its own slack note says "onboard flash is enough."

All three are closed below. Two of them changed a part.

## The BOM

One board, one spin. Prices are order-of-magnitude in ones, not quotes.

| item | MPN | package | interface | qty | USD |
|---|---|---|---|---|---|
| MCU | STM32F405RGT6 | LQFP64 | — | 1 | 10 |
| IMU | ICM-42688-P | LGA-14, 2.5 × 3.0 mm | SPI1, CS1 | 1 | 8 |
| magnetometer | MMC5983MA | LGA-16, 3.0 × 3.0 mm | SPI2, CS2 | 1 | 5 |
| barometer | MS5611-01BA03 | QFN-8, 5.0 × 3.0 mm | SPI2, CS3 | 1 | 10 |
| GNSS receiver | MAX-M10S | LCC, 9.7 × 10.1 mm | USART1 | 1 | 30 |
| log flash | W25Q128JVSIQ | SOIC-8 | SPI3, CS4 | 1 | 2 |
| 3.3 V regulator | TPS62162DSGT | SON-8 | 2S in | 1 | 2.50 |
| GNSS antenna | **passive** patch, u.FL — see note | ~25 × 25 mm | RF | 1 | 8 ~ |
| passives, connectors, LEDs, SWD | assorted | 0402/0603 | — | 1 | 20 ~ |
| PCB, 4-layer, ENIG | 70 × 45 mm, 1.6 mm | — | — | 1 | 30 ~ |
| **deployment altimeter** | PerfectFlite StratoLoggerCF | 50.8 × 21.3 × 12.7 mm | **off-board** | 1 | 70 |
| battery | 2S LiPo 1500 mAh | 70 × 35 × 15 mm | **XT30** (board: 18 AWG pigtail) | 1 | 20 ~ |
| spare IMU + magnetometer | ICM-42688-P, MMC5983MA | — | — | 1 ea | 13 |

`~` = estimated price. Optional and **not flight hardware**: a NUCLEO-F446RE or a WeAct F405
"Blackpill", ~$15, purely somewhere to write and single-step the SPI drivers, the scheduler
and the R12 latch before the board exists. Same core family, so the drivers port.

Four layers, not two: a solid ground plane under the IMU and a separate return for the servo
current are the two things that keep this board's own noise out of its own sensors, and
`docs/01`'s "things that will bite you" already names servo noise into the IMU.

## The first finding — the ±4000 dps requirement is dropped, not bought

`docs/06`'s open item said to specify a part with selectable full scale to ±4000 °/s and run
it at ±2000, on the grounds that "the option is free before layout and unbuildable after."
The option is real — **TDK's ICM-45686 does ±4000 dps and ±32 g for about the same money** —
and it is still the wrong buy. Three reasons, in order of weight:

- **The roll cap is locked and it is what keeps the part in range.** R13's
  `ROLL_COMMAND_CAP_DEG = 2.0` puts steady roll at **566 °/s, 28% of ±2000** — 3.5× of
  margin at every *commanded* operating point.
- **Range does not license lifting the cap, and correction 58 already proved it.** 7.94°
  capped against 62.89° uncapped, both dominated by gyro scale factor at roll rate. The roll
  rate that saturates the part is the same one that drives the dominant error term, so a
  wider part flown uncapped is about **8× worse**. L1 is *hold roll angle*.
- **The only thing that saturates ±2000 is a fault, and a fault is detectable.** Uncapped
  roll is 2602 °/s — 130% of full scale — and it only happens if something runs the canards
  to the stops, which R13 forbids as a command. A gyro pegged at full scale is a *readable
  condition*. **Wiring FS saturation into the R12 latch turns the one scenario the extra
  range was for into a detected fault that centres the canards inside 0.5 s.** That is
  strictly better than measuring the fault accurately while flying it, and it costs nothing.

So the requirement is dropped and the cap carries the load it was already carrying.
`estimation.GYRO_WIDE` is gone; `estimation.GYRO_ICM45686` replaces it with the real part's
datasheet numbers, kept so the rejection is against hardware.

**One honest gap, flagged in the code:** the ICM-45686's scale-factor tolerance and
g-sensitivity in that spec are *assumed equal to the ICM-42688-P's and were not read off the
datasheet*. Scale factor is the dominant term in `attitude_error_budget()`, so that spec is
good enough to reject the part on range-usability grounds and not good enough to quote a
computed error from. If the roll cap is ever revisited, read the real number first.

The rest of the sensor set clears comfortably and none of it is tight:

| | required | available | |
|---|---|---|---|
| gyro full scale | 566 °/s at the cap | ±2000 °/s | 3.5× |
| IMU output data rate | 1000 Hz | 32 kHz | 32× |
| accelerometer full scale | 7.1 g peak axial | ±16 g | 2.3× |
| magnetometer ODR | ≥ 100 Hz | 1 kHz | 10× |

## The second finding — there is no BEC, and the battery was never sized by energy

**The KST X08 Plus V6.0 is rated DC 3.8–8.4 V** (KST_0012, 04/2025) and the pack is 2S. The
servos run **directly off the battery**, so `avionics.BEC` — 25 g and a part — is not needed;
"separate supply from the IMU" becomes a separate *feed and filter* off a star point at the
pack, which is a layout rule rather than a component. The same datasheet independently lands
on **1520 µs / 333 Hz**, which is where `board_requirements()`'s 333 Hz came from, and its
signal is 3.3–5.0 V HIGH, so the F405's 3.3 V timer outputs drive it with no level shift.

The budget itself:

| | |
|---|---|
| logic rail, 3.3 V | **112 mA** (MCU 86, flash 15, GNSS 8.5, baro 1, mag 1, IMU 0.9) → 59 mA off the pack |
| four servos, active at the peak hinge moment | **1.03 A** |
| four servos, stalled | **4.0 A** |
| 60 min armed on the pad | **0.73 Wh** |
| whole flight, servos working 9.5 s of it | **0.06 Wh** |
| pack | 11.1 Wh, 8.88 Wh usable at 80% depth |
| **margin** | **11×** |

**Capacity was never the constraint and 92% of the demand is pad time, not flight.** The
flight costs 0.06 Wh out of 8.88 available. What actually sizes the pack is **peak current —
4.1 A with all four servos stalled** — and that is a C-rating, a battery lead and a conductor
question, not a capacity one. It is also the number that sizes the 14 conductors through the
⌀8.0 mm potted pass-through (`design/access_bulkhead.py`), a count this project has carried
since correction 37 and never turned into wire.

A smaller pack is therefore available and worth ~55 g against a nav bay that
`configure.py` already flags as 114 g over budget. Not taken here: it is a real decision with
a scrubbed-launch argument on the other side, and this document's job was to find out whether
the pack works, which it does.

### The margin no torque check in this project could see

The KST datasheet's performance curve carries an **operation-model banding** that no spec
table would have shown: continuous duty only to ~1.2 kgf·cm, "short time < 10 s repeat" to
~4.8, and a red < 1 s / 60 s-cool zone beyond. Against it:

> **Servo torque margin is 2.03× on STALL torque and 1.15× on the datasheet's own CONTINUOUS
> band.** The peak hinge moment is 1.04 kgf·cm and the continuous limit is 1.2.

Both numbers are true and they are about different failure modes — the 2.0× is "can it
push", the 1.15× is "for how long before it gets hot". The control window is 9.5 s against a
10 s short-time rating, so nothing here fails, and the vehicle is inside the band it needs.
But **this is a margin the project has never looked at**, it sits at 1.15× rather than 2×,
and it is read off a chart rather than a table. It belongs on the Step 5 ground-test list:
`docs/01` already calls for "servo step response under representative load" and this is the
reason to instrument current while doing it.

Priced at the **horizontal** flight's dynamic pressure, which is R15's primary mode and the
binding one — a flat flight's max q is ~15.5 kPa against ~12.4 vertical, and hinge moment
goes as q. `scripts/baseline.py` reports the vertical margin (2.5×); the 2.067× that
`configure.py`'s own comment records corresponds to about a 30° rail. At R15's 28° it is
**2.03×**, and at the sweep's 25° search elevation it is **2.001×** — on the requirement, not
above it, which corroborates `docs/01`'s "two margins are now effectively on the line."

## The third finding — "onboard flash is enough" is wrong by 6×

Written out as a channel list rather than as a sentence:

| channel | B/sample | Hz | B/s |
|---|---|---|---|
| raw gyro + accel, 6 × int16 + timestamp | 16 | 1000 | 16 000 |
| magnetometer, 3 × int16 + timestamp | 10 | 100 | 1 000 |
| baro pressure + temperature | 12 | 50 | 600 |
| GNSS position, velocity, fix quality | 36 | 10 | 360 |
| estimator state: quaternion, roll, rate | 24 | 71 | 1 695 |
| control: 4 servo commands, phase, flags | 12 | 71 | 847 |
| **total** | | | **20 502** |

**4.90 MB per flight against 0.79 MB usable on the F405 after a 256 KB firmware allowance —
6.2× short.** The window is a deliberate upper bound (the whole descent priced at the main's
5 m/s when the drogue leg is far faster); against the requirement's own 150 s window it is
3.08 MB, still 3.9× short. The conclusion does not depend on which window is used.

**The IMU line is 78% of the rate and it is the one that cannot be cut.** Logging raw gyro
and accel at the *propagation* rate rather than the loop rate is what turns GV-2 into a
measurement of `Cm_delta` and `Cl_delta` — and `docs/01` calls GV-2 the flight the whole
thesis rests on. Drop that channel to the 71 Hz loop rate and everything fits on-chip, and
the flight that justifies the vehicle stops producing the data it exists to produce.

So: **W25Q128JVSIQ, 16 MiB, soldered.** 3.4 flights of capacity. Soldered rather than a
microSD socket because every COTS altimeter this project already trusts — StratoLogger,
Raven, TeleMetrum — uses soldered flash, and a push-push socket is an ejection-shock
liability for the sake of convenience that a USB dump also provides. The F405 has no QUADSPI,
so it is plain SPI either way; the SDIO pins stay free if a microSD is ever wanted.

## The board, and where it sits

70 × 45 mm, 1.6 mm PCB, ≤ 8 mm tallest component. Against the sled — which is the arbiter,
not this document:

| | |
|---|---|
| sled plate | 109.04 × 59.41 mm |
| usable height per face | 18.70 mm |
| stack (PCB + tallest part) | 9.6 mm |
| margins | +39.0 mm long, +14.4 mm wide, **+9.1 mm tall** |

**Do not grow this board.** `docs/06` records that the sled already had to widen to 0.846 of
the bore to place the 80 g loom, and past that point width comes out of the tallest
component's headroom. The board is the one line in the nav bay whose size is a design
decision, and shrinking it is the cheapest fix available to the packing problem.

The GNSS patch antenna sets the footprint and can stay on-board: the G12 airframe is
RF-transparent, which is the same reason `correction 32` put the tracker in the nose rather
than worrying about shielding.

**The antenna must be PASSIVE, and the BOM line above used to say "chip or patch" without
saying so.** `U8` pins 13 (`LNA_EN`) and 14 (`VCC_RF`) are no-connects on this board, so
there is nothing to bias an active antenna from — and `RF_IN` has a built-in DC block
(u-blox **UBX-20035208 R08**, Table 13), so feeding one would need an external bias tee at
`J5`, not a jumper. Since most u.FL GNSS antennas sold *are* active, ordering the line as it
was written had a good chance of producing an antenna that silently does not work.

This is a choice the part is built for rather than one it merely tolerates — R08 p.4: *"For
maximum sensitivity in **passive antenna designs**, MAX-M10S integrates an LNA followed by a
SAW filter in the RF path."* If an active antenna is ever wanted for link margin, the change
is an inductor from `VCC_RF` plus a DC block at `J5`, and it is cheapest to make before
layout freezes.

### Bus map

SPI everywhere that is flight-critical. No I2C: a stuck I2C bus is a hung transaction, and
roll angle — which the magnetometer alone observes — is the minimum success criterion.

```
SPI1  (≤24 MHz)  CS1  ICM-42688-P    burst read on DMA, ≥1 kHz  [alone on the bus]
SPI2             CS2  MMC5983MA      magnetometer, 100 Hz
                 CS3  MS5611         barometer, 50 Hz
SPI3             CS4  W25Q128JV      log flash, write-mostly
USART1                MAX-M10S       GNSS, 10 Hz, UBX binary
USART2                debug console  bring-up only
TIM4 CH1-4       PB6 PB7 PB8 PB9     4 × servo PWM, 333 Hz / 1520 µs
SWD              PA13 PA14           flashing and single-step
```

The IMU is alone on SPI1 so its transfer never queues behind a baro conversion or a flash
page program — at 1 kHz with 32× of ODR headroom, jitter is the thing to protect, not
throughput.

## Rejected, and why

| rejected | why |
|---|---|
| **ICM-45686** (±4000 dps, ±32 g) | The range is unusable while the roll cap holds, its rate noise is ~36% worse (3.8 vs 2.8 mdps/√Hz), and its driver ecosystem is far younger. For a first board that last one decides it. |
| **ISM330DHCX / LSM6DSV16X** (±4000 dps) | Same range argument, and ST's gyro sensitivity tolerance is looser than the ICM-42688-P's ±0.5% — scale factor is the dominant error term, so range would be bought with accuracy in exactly the wrong place. |
| **BMI088** | ±2000 dps like the selected part but noisier, with no ecosystem advantage. |
| **Any I2C sensor variant** | Flight-critical sensors on a bus that can hang. |
| **microSD as primary log** | Socket eject under ejection shock, for convenience USB already provides. Footprint left free. |
| **STM32H743** | Already argued in `docs/06`: more rails, finer pitch, harder bring-up. Picking a part you can actually bring up is the engineering judgment. If the F4 flies, an H7 spin afterwards is a week. |
| **Teensy 4.1 as the flight board** | It is Stage 1's part and it stays Stage 1's part — the cert-flight passive logger. `docs/06`'s staging argument is unchanged. |
| **TeleMega** | `docs/06` option B: needs a HAM licence and puts tracking back in the nav bay, undoing correction 32's swappable nose. |
| **Pyro on this board** | Non-negotiable. An independent commercial altimeter fires the charges. A guidance bug must be able to lose the mission without losing the vehicle. |
| **Two cheap IMUs plus a denoising filter** | Redundancy that has not been asked for against a failure mode nothing has characterised, on a vehicle whose dominant error is a scale factor a rate table fixes for free. |

## What it costs

| | USD |
|---|---|
| parts — chips, passives, connectors | 95.50 |
| fab — 4-layer PCB | 30.00 |
| bought whole — StratoLoggerCF + battery | 90.00 |
| spares — IMU + magnetometer | 13.00 |
| **total, hand-assembled** | **228.50** |
| **total, with low-volume PCBA** | **348.50** |

The chips are FPV-class cheap and the pain is process. `docs/04` section 5 carries a flat
**$400** for "custom STM32F405 board"; that is an assembled-board number and it hides roughly
a 3:1 split between silicon and fab. LQFP64 was chosen in `docs/06` partly because it is
hand-solderable, and that choice is what makes the $228 column real.

## Order this, fab this

1. **Read the ICM-45686 scale-factor tolerance** off DS-000577 and record it, so the
   rejection above rests on a datasheet rather than on an assumption. Ten minutes, and it is
   the only unverified number this document leans on.
2. **Order the chips** — MCU, IMU, mag, baro, GNSS, flash, regulator, plus the two spares.
   Order 2–3× of every passive value; shipping costs more than the parts.
3. **Order one StratoLoggerCF and one 2S 1500 mAh pack.** Independent of everything above.
4. **Get the bring-up jig now, not later.** The SPI drivers, the scheduler and the R12 latch
   can all be written and stepped before the PCB exists, and `scripts/sil_demo.py` is already
   the reference for what the loop has to do.
5. **Schematic, then layout.** Four layers. IMU over solid ground, magnetometer as far from
   the servo feed and the battery lead as the outline allows — `estimation.required_magnetic_cleanliness()`
   gives an 18.0 mgauss budget against 40 mgauss from a single untwisted 1 A servo lead at
   50 mm, so twisted pairs and mag placement are power-routing decisions, not aesthetics.
6. **Hold 70 × 45 mm.** If layout wants more, take it out of height, not width.
7. **Fab 5, assemble 1.** The minimum order is five and the spares cost nothing.

## What is still open

- **The ICM-45686's real scale-factor tolerance**, above. Flagged in code, not just here.
- **Servo idle current is not on the KST datasheet at all** and the 10 mA in the model is
  sourced from nothing. The pad budget is insensitive to it at 11× margin — that
  insensitivity is checked rather than assumed — but it is the one power number with no
  provenance.
- **The servo current curve is a chart read, not a table.** `SERVO_NO_LOAD_A` and
  `SERVO_STALL_A` are eyeball values off the datasheet's own plot. Both findings that rest on
  them — the 4.1 A peak and the 1.15× continuous-duty margin — should be confirmed with a
  current probe during Step 5's actuation test.
- **The 14 conductors through the ⌀8 mm pass-through have still never been turned into a
  wire gauge**, and now there is a current to size them against.
- **The IMU's lever arm has never been written down, and nothing in `design/` models one.**
  `U4` sits 16.5 mm off the board's own centreline. At R13's roll cap (566 °/s = 9.88 rad/s)
  that radius is ω²r ≈ 1.61 m/s² ≈ **0.16 g** of roll-rate-dependent bias on the lateral
  accelerometers — small against ±16 g, deterministic, and removable in firmware *if the
  offset is known*. Moving the part is the wrong fix: `design/sled.py` mounts the 45 mm board
  on a 56.16 mm plate that is itself a chord offset from the bore axis, so the board's
  centreline is **not** the vehicle's roll axis and centring `U4` on the PCB would be guessing
  at the wrong centre. What is needed is the measurement — `U4`'s position in board
  coordinates plus the board's pose on the sled — recorded once the sled is built. It belongs
  next to the wire-gauge item above: both are "the CAD knows, the model does not".
- **Board envelope is still a layout target**, exactly as `docs/06` says. It becomes a
  measurement when the layout closes, and `scripts/sled_report.py` is the check to re-run
  when it does.
- **Whether the pack shrinks.** 11× of energy margin against a nav bay 114 g over budget is
  an obvious trade and it is deliberately not taken here.
