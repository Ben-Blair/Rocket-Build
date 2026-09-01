# D8 — State estimation

Regenerate the numbers with `python scripts/estimation_trade.py`. Nothing here is typed
twice; every figure comes from `design/estimation.py` and the flight model.

## Decision

**IMU + baro + GNSS + magnetometer on the board, and the estimator staged by guidance
level.**

| stage | flies | the estimator | new sensor |
|---|---|---|---|
| **L0/L1** | GV-1 … GV-3 | pad gyro-bias calibration; gyro-only rate estimate; **no attitude aiding in flight** | gyro |
| **L2** | GV-4 | quaternion propagation at ≥ 1 kHz; GNSS-velocity attitude aiding under small α; magnetometer for roll angle | mag, GNSS |
| **L3** | GV-5 | adds GNSS position dead-reckoned forward through the latency; baro for apogee and the safety logic | baro |

**D7 staged the hardware. D8 cannot.** Every sensor has to be on the schematic at once or it
is not on the board at all, so what stages here is the *software*, and each flight in the
step 6 campaign gets exactly one new thing to work.

That is also why **D8 closes without D1 being closed.** The guidance level is still an open
decision; the board is not waiting on it, and it must not, because three of the findings
below are unrecoverable after layout.

## Why the binding constraint is observability, not packaging

D7's question was whether the boards fit. This one is whether the state they produce is real,
and an estimator cannot average its way to a state nothing measures.

| state | pad | boost | coast | descent |
|---|---|---|---|---|
| roll angle | mag | mag | mag | mag |
| body rates | gyro | gyro | gyro | gyro |
| pitch/yaw attitude | accel | — | GNSS velocity | — |
| altitude | baro | — | baro + GNSS | baro |
| position | GNSS | — | GNSS, lagged | GNSS |

Two things fall out of that table that are not obvious:

- **Pitch/yaw attitude is aided only by the GNSS velocity vector, under a small-α
  assumption.** That assumption is what 2.1–2.6 cal of static margin buys. It is the one
  place in this project where stability margin shows up as a *sensing* property rather than
  a handling one, and it is worth saying out loud at the defence.
- **Roll angle is observed by the magnetometer or by nothing.** See finding 3.

The architectures, scored by `check_estimation()` rather than by argument:

| | sensor set | parts | highest level | check |
|---|---|---|---|---|
| A | IMU only | $12 | L1 (null rate only) | FAIL |
| B | IMU + baro | $20 | L1 + apogee logic | FAIL |
| C | IMU + baro + GNSS | $45 | L3, except roll angle | FAIL |
| **D** | **IMU + baro + GNSS + magnetometer** | **$50** | **L3** | **OK** |

A and B fail on attitude aiding as well as on roll angle; C fails on roll angle alone. The
whole spread is $38, which is the real argument for D: at these prices the sensor set is not
where you economise, and every dollar of it has to be committed before the schematic.

## What would have bitten you

Three findings, from the flight model rather than from a tutorial. Every one of them is free
before layout and unrecoverable after.

### 1. The accelerometer gate `docs/01` prescribes passes its worst data

`docs/01` step 4.2 specifies *"accelerometer and magnetometer corrections gated on
acceleration magnitude so boost does not corrupt attitude."* The gate rejects boost
correctly — 8.3 g is nowhere near 1 g. Then:

| t (s) | body-axis specific force | |
|---|---|---|
| 2.00 | 7.73 g | boost — gate closed, correctly |
| **2.85** | **1.06 g** | **burnout — gate OPENS** |
| 3.50 | 0.90 g | gate still open |
| 5.00 | 0.62 g | below the band |

**The vector it admits is drag along the body axis, not gravity.** A coasting rocket is in
free fall; the only specific force on it is aerodynamic, and aerodynamic force lies along the
body axis. So the filter is handed a body-axis vector labelled "down" at exactly the moment
the guidance loop opens, and a vehicle 15° off vertical is told it is vertical. The window is
1.1 s wide and it starts at burnout — the worst 1.1 s in the flight to be wrong about
attitude.

The heuristic is borrowed from multirotor AHRS work, where a vehicle really does sit at 1 g
in cruise and |a| ≈ 1 g really does mean "this is gravity". **A ballistic vehicle never sees
gravity again after it leaves the rail.**

Same shape as correction 1 (the servo was assumed to point inward) and correction 28 (a bay
was assumed to be a box with two faces): a rule that sounds complete, is locally true, and
silently produces the wrong answer.

**Fix: gate on flight phase, never on |a|.** The accelerometer is a pad-alignment sensor and
an event detector, and nothing else. It costs nothing — it removes code.
`ACCEL_ATTITUDE_AIDING = False` in `design/estimation.py` records it as a decision the check
tests, so turning it back on fails `baseline.py`.

### 2. 100 Hz attitude integration drifts faster than the gyro does

`board_requirements()` derived one rate — the control loop rate, 20× the 4.30 Hz pitch mode,
86 Hz. A reader builds a 100 Hz system. But attitude is *propagated*, not sampled: `q ← q ⊗
(1, ω·dt/2)` renormalised rotates by `2·atan(|ω|·dt/2)`, not by `|ω|·dt`, and the shortfall
is cubic in the step.

| IMU rate | rotation/step | drift @ 594 °/s (capped) | drift @ 2378 °/s (limit) |
|---|---|---|---|
| 100 Hz | 23.8° | 0.53 °/s | **33.3 °/s** |
| 200 Hz | 11.9° | 0.13 °/s | 8.47 °/s |
| 500 Hz | 4.8° | 0.02 °/s | 1.36 °/s |
| **1000 Hz** | 2.4° | 0.005 °/s | **0.34 °/s** |

At 100 Hz each step is a 23.8° rotation and the small-angle assumption underneath the
propagation is simply false. **33.3 °/s — with a perfect gyro.** Over the 11.7 s control
window that is more than the entire sensor error budget, from arithmetic.

**Fix: sample the IMU at ≥ 1 kHz.** The error is cubic so it costs almost nothing — but it is
a **different requirement from the control loop rate**, it sets the SPI clock and the DMA, and
it is fixed at layout. A board specified to the 86 Hz loop rate would sample ten times too
slowly. *The estimator is allowed to run faster than the controller; nothing said it had to
run at the same rate.*

### 3. Roll angle was observed by nothing on the board D7 selected

`STM32_BOARD` was "STM32F405, IMU, baro, GNSS, flash, 4× servo drive". Roll about the body
axis is unobservable from all of it:

- **Specific force is invariant under rotation about the axis it lies along**, so the
  accelerometer cannot see roll — on the pad or in flight.
- **The GNSS velocity vector fixes where the nose points, not how the vehicle is clocked
  about it.**

**L1 — hold roll angle — is the project's minimum success criterion** (§1.1, and GV-3 in the
step 6 campaign). Nulling roll *rate* needs only the gyro; holding roll *angle* could not be
built on the board as specified.

`docs/01` step 4.2 already assumed a magnetometer ("accelerometer and magnetometer
corrections"). The board did not have one, and nothing had checked. **The document and the
hardware had disagreed for as long as both existed.**

**Fix: a magnetometer on the schematic.** About $5 and one I2C address before layout;
unbuildable after. Applied — `design/avionics.py` carries it on the custom board and on the
cert-flight breakout stack, because the premise of D7's staging is that every line of the
interesting software is identical.

Two cautions, so this does not read as free: it sits near four servos and a 2S battery, so
hard- and soft-iron calibration is real work and the part must not saturate on a servo
transient; and the cert flights are where you find out whether it is usable, which is another
reason those flights matter.

## And a correction to D7 that fell out on the way past

**The gyro full-scale requirement had been computed at the wrong deflection.** Steady roll
rate is *linear* in deflection, and the project was using three different values:

| deflection | roll rate | of ±2000 dps | where |
|---|---|---|---|
| 2° | 594 °/s | 30 % | the roll command cap in `baseline.py` |
| 6° | 1783 °/s | 89 % | `evaluate()`'s default — what `avionics_trade.py` took |
| **8°** | **2378 °/s** | **119 % — SATURATED** | the deflection limit `baseline.py` evaluates at |

`docs/06` and `board_requirements()` printed the 6° answer under an 8° heading. That is a
33 % understatement, and it is exactly the understatement that made a saturated part read as
a comfortable 89 %. **The error and the reassurance came from the same place.**

The correct statement: **a ±2000 dps gyro is adequate only because the roll command is
capped.** `ROLL_DEFLECTION_DEG = 2.0` already existed in `baseline.py` as a control
convenience — roll inertia is tiny, so roll needs far less deflection than pitch. It is now
load-bearing for the *sensor*, and a fault that runs the canards to the stops takes the
attitude estimate with it as well as the vehicle.

Both limits now live in `design/configure.py` (`DEFLECTION_LIMIT_DEG`,
`ROLL_COMMAND_CAP_DEG`), and `Evaluation` records the deflection it was evaluated at, so a
document can no longer quote one caller's answer under another caller's heading. **This is
correction 4 recurring: a constant that lives in a script drifts from the document that
quotes it.**

## The attitude error budget, and why the ranking is not the expected one

Unaided propagation — the L0/L1 configuration, ICM-42688-P class gyro, 1 kHz, roll capped:

| source | at burnout | at apogee |
|---|---|---|
| gyro bias, pad-calibrated | 0.06° | 0.34° |
| angular random walk | 0.01° | 0.01° |
| **gyro scale factor at roll rate** | 0.00° | **8.67°** |
| gyro g-sensitivity | 1.19° | 1.19° |
| integration truncation at 1 kHz | 0.00° | 0.02° |
| | | **8.76° RSS** |

**Bias and random walk — the two terms every AHRS article is about — are negligible over
17 seconds.** Scale factor at high roll rate leads by an order of magnitude, and it leads
because of the same roll rate that made D7's gyro line tight. One root cause, and capping the
roll command fixes both. Uncapped, the same term is 35°.

8.76° against a 5° budget means **the aiding is load-bearing, not a refinement.** That is the
quantitative reason architecture A loses, and it is why L0/L1 is scoped as *rate* control
rather than attitude control.

Two free things the budget makes obvious:

- **Pad gyro-bias calibration is mandatory.** Averaging on the rail takes the bias term from
  8.5° to 0.34° by apogee. It is thirty lines of firmware.
- **g-sensitivity is the term the pad calibration cannot see**, because the pad is at 1 g. It
  accrues only during the 2.85 s of boost and then stops, which is why it does not lead.

## What baro and GNSS are actually for

**Barometer — not a boost-phase altitude source.** At max q (19.2 kPa) a 2 % static-port
error coefficient is 383 Pa, and dp/dh is 11.4 Pa/m: **33 m of altitude error, against 0.13 m
of sensor noise.** Two orders of magnitude apart, and the one a datasheet comparison would
optimise is the small one. Worse, port error scales with q and therefore **correlates with
velocity** — it does not look like noise to a filter, it looks like signal. Baro is for coast
and descent altitude, apogee detection, and cross-checking the StratoLoggerCF.

*One thing that is genuinely not a problem:* max Mach is 0.527, so there is no transonic port
anomaly. The absence of a problem is a result too.

**GNSS — a slow outer-loop sensor.** 150 ms of receiver latency at 176 m/s is 26.5 m, and a
half-sample of staleness at 10 Hz is another 8.8 m: **35 m of position lag against 400 m of
achievable crossrange, about 9 %.** It is correctable — dead-reckon the fix forward on the
IMU, which is what the IMU is for — but only if you know it is there. Note that the lag is
not the CEP: a datasheet comparison on accuracy alone (2 m) would have missed it entirely.

And **the receiver may not be tracking at all through boost.** Peak axial is 8.3 g, and
"airborne < 4 g" is the most permissive dynamic platform model u-blox offers. Expect lock
loss under boost and reacquisition in early coast. That is survivable, because the guidance
window does not open until burnout — but it means GNSS cannot be part of the boost-phase
estimate, which is what the observability table already said.

## The pattern, which is the actual result

| finding | fix | cost |
|---|---|---|
| the \|a\| gate admits drag | gate on flight phase | removes code |
| 100 Hz propagation drifts 33 °/s | sample at 1 kHz | a register write, at layout |
| roll angle unobservable | add a magnetometer | ~$5, at layout |
| (D7) gyro quoted at the wrong deflection | cap the roll command | already in the design |

**Four in a row, and every one is a sensing requirement set at layout.** That is the argument
for closing D8 before the schematic rather than during firmware, and it is the reason this
document exists. None of these would have been found by building the board first; all of them
would have been found in flight.

## Still open

- **The filter itself.** Quaternion propagation, the aiding updates, the phase machine that
  replaces the |a| gate — that is `docs/01` step 4.2 and it is firmware. D8 decided what it
  has to be built from and what it is allowed to trust; it did not build it.
- **There is no attitude truth model to validate a filter against.** `design/trajectory.py`
  is 3-DOF by design and says so. Every number in this document is analytic and needs no
  truth model, but a *Monte Carlo* of the estimator does, and that is the 6-DOF work behind
  step 4.3's HIL rig. **Recorded here as a gap rather than left as an omission.**
- **`roll_duty = 0.25`** — the fraction of the coast spent near full roll rate — is a guess
  with the same standing as `control.achievable_crossrange`'s duty cycle, and the dominant
  error term is directly proportional to it.
- **The magnetic environment.** Four servos and a battery next to a magnetometer, in an
  airframe nobody has swung. The cert flights measure it.
- **Everything downstream of `Cl_delta`.** The roll rate that drives both the gyro range and
  the dominant attitude error term comes from the interference model, which `docs/01` calls
  the weakest part of the whole analysis. **GV-2 turns it into a measurement, and both of
  these requirements move when it does.**
