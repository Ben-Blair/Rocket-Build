# Ordered plan

The ordering here is deliberate. Each step exists to remove a specific risk, and the
risks are ordered by how badly they hurt if you discover them late. Airframe geometry is
step 3, not step 1, because two things upstream of it can invalidate everything.

---

## Step 0 — DONE: preliminary sizing tool

`design/` and `scripts/` now answer the questions that were blocking you in OpenRocket.
Baseline: 75 mm fiberglass, 4 interdigitated canards, J-class 54 mm motor.

## Step 1 — MOSTLY DONE: close the two project-killing risks

Neither of these is engineering, and both can end the project if found late.

**1a. Range access and legality.** See `00-requirements.md` §1.2. Email your club prefect
describing exactly what you intend to fly, and get a written answer. Loop in your faculty
advisor and, through them, your university's export control office. Until you have a
"yes," treat the whole flight campaign as unconfirmed.

**1b. Certification path.** You cannot fly a J motor without Level 2, and you cannot get
Level 2 without Level 1 first. Each is a separate flight on a separate launch day, and
launch days are monthly and weather-dependent. Work backwards from your flight window and
book the earliest possible L1 attempt.

Status (Aug 2026): prefect contacted and answered; earliest L1 attempt booked; recovery
area confirmed effectively unbounded, which retires C5a as the governing constraint (see
`00-requirements.md` §2, R6). **Still open in §1.2:** the written NAR + TRA safety code
summary, and the advisor / export control office contact. Those are separate rows and
neither is closed.

Deliverable: a one-page memo with the prefect's written response and dated cert
milestones. This is also the first thing your advisor will ask for.

**Scoping decision to make now:** commit to L1 (roll control) as the minimum success
criterion and L3 (guidance to a ground target) as the stretch goal. See
`00-requirements.md` §1.1. Do not promise "waypoints in the air" in your proposal; it is
not physically achievable for a ballistic vehicle and you will be held to it.

## Step 2 — DONE: validate the sizing tool against OpenRocket

Result in `docs/03-openrocket-correlation.md`: CNa agrees to 0.3%, CP to 0.17 cal
like-for-like, and OpenRocket disagrees in the safe direction. No design change followed.
The rest of this section is kept as the rationale for why the check was worth doing.

**This was the highest-value analysis step remaining.** The margin Monte Carlo
(`scripts/robustness.py`, written up in `docs/00-requirements.md` §7) shows that the
dominant uncertainty in the whole design is the CP prediction, not any mass line. Fin area
and nose ballast cannot fix a CP error — only an independent check can. So do this before
ordering parts.

Run `python scripts/baseline.py` and enter the printed values into OpenRocket. You want
CP, CG, static margin and apogee to agree within about 15%.

Specifically: if OpenRocket's CP lands within ~10 mm of this tool's, the 0.35 cal CP sigma
assumed in the Monte Carlo is conservative and the real risk is lower than quoted. If it
disagrees by more than ~30 mm, stop and resolve it — that discrepancy is worth more than
everything else on this list.

When they disagree, find out why before trusting either. Likely causes, in order:
OpenRocket's mass model versus your budget (its default has no avionics), the body lift
term, drag coefficient, and the canard fin set position. Write down what you found. This
comparison is a legitimate results section in your report, and it is how you earn the
right to cite either tool.

Deliverable: `docs/03-openrocket-correlation.md` with a side-by-side table and an
explanation of each discrepancy. **Done.**

## Step 3 — Freeze the airframe — **YOU ARE HERE**

Step 2 is closed and the range-access blockers are answered, so this is now unblocked.
The motor half is already done: 102 real `.eng` curves are in `data/motors/`, the sweep
and trade study have been rerun against them, and the choice is Cesaroni Pro54 J449 Blue
Streak (`docs/02-motor-selection.md`). An unbounded recovery area does **not** reopen that
choice — four of its five stated reasons never depended on field size. Then freeze:

- diameter, wall, and bay lengths;
- canard and aft fin planforms, with canards interdigitated at 45 degrees;
- actuator selection and hinge line position (put the hinge slightly aft of the panel
  centre of pressure so the panel is weakly self-centring, not divergent);
- static margin at rail exit, target 1.5–2.5 calibers nominal **and** P(SM < 1.0) under 1%
  once you rerun `scripts/robustness.py` with real weighed masses;
- a nose ballast provision — threaded rod and washer stack in the nose shoulder. Do not
  skip this. It is a few dollars and it turns static margin from a prediction you are
  betting the vehicle on into something you set after weighing the finished rocket.
  Roughly 100 g there moves the margin +0.12 cal.

As components arrive, weigh them and replace the estimates in `design/mass.py` with real
numbers, then rerun the robustness script. Every guess you retire shrinks the distribution.

Deliverable: a frozen `DesignParams` in `design/configure.py`, a dimensioned drawing, and
a bill of materials with real part numbers and prices.

**Done so far:** the frozen baseline now lives in one place — `design/configure.py` defines
`BASELINE_OD`, `BASELINE_WALL`, `BASELINE_MOTOR_FILE` and a `baseline()` factory, and the
fin semispans are the `DesignParams` defaults. Six scripts previously carried their own
copy of those numbers; they had already drifted from the documentation once. Every script
now imports. What remains is the physical freeze: real servo dimensions, hinge line, the
drawing, and the BOM.

## Step 4 — Avionics, developed on the ground and flown as a passenger

You are a CS student, so this is the part you will be judged hardest on. Build it in this
order, and do not skip the ground testing.

1. **Sensors and logging.** IMU + barometer + GNSS, logging to flash at ≥ 100 Hz. Get
   this flying as a passive payload in your L1 and L2 cert rockets. By the time it flies
   in the guided vehicle, the sensor stack should already have real flight data behind it.
2. **State estimation.** An attitude filter that survives 9 g of axial acceleration and
   high angular rates. Quaternion state, gyro propagation, accelerometer and magnetometer
   corrections gated on acceleration magnitude so boost does not corrupt attitude. This is
   where most of your interesting engineering lives.
3. **Hardware-in-the-loop simulation.** Feed the flight computer synthetic sensor data
   generated from the model in this repo, and check that the loop commands what you
   expect. This is the single highest-value piece of software in the project: it is how
   you find sign errors, saturation, and timing bugs on the bench instead of in the air.
4. **Controller.** Cascaded loops: attitude rate inner, attitude outer, guidance
   outermost. Gain-schedule on dynamic pressure, because authority falls by roughly an
   order of magnitude between burnout and apogee (see `out/baseline.png`).
5. **Safety logic.** Canards centre and lock on: any sensor fault, loss of state estimate
   validity, deflection command saturation for longer than a set time, burnout plus N
   seconds, or apogee detection. Write this before the controller, not after.

## Step 5 — Ground testing

- Weigh every component and replace the budget in `design/mass.py` with measurements.
- Measure roll and pitch inertia (bifilar pendulum for roll, swing test for pitch).
  Recompute; expect the analytical estimates in `control.py` to be off by tens of percent.
- Measure servo step response under representative load. Confirm it is fast enough not to
  be the dominant lag in your loop.
- Full-authority actuation test on battery power, at flight temperature, for the full
  flight duration plus margin. Check current draw and that servo noise is not corrupting
  the IMU.
- Recovery ground tests: ejection charge sizing, shear pin selection, twice.

## Step 6 — Flight campaign

Each flight has one job. Do not combine them.

| Flight | Configuration | Objective |
|---|---|---|
| L1 cert | Simple kit, avionics as passive logger | Certification + first real sensor data |
| L2 cert | Simple kit, avionics as passive logger | Certification + boost-phase filter validation |
| GV-1 | Guided vehicle, canards mechanically locked at zero | Airframe, recovery, stability, telemetry |
| GV-2 | Open-loop canard deflection sweep, logged | **Measure** Cm_delta and Cl_delta, including sign. This is the flight that validates or refutes the interference model |
| GV-3 | Closed-loop roll control | Minimum success criterion (L1) |
| GV-4 | Closed-loop attitude hold | L2 |
| GV-5 | Guidance to a commanded ground target | Stretch goal (L3) |

GV-2 is the flight your whole thesis rests on. The interference model in `control.py` is
the weakest part of the analysis; GV-2 turns it from an assumption into a measurement, and
that comparison — predicted versus measured control derivatives — is the strongest result
you can put in a senior thesis.

## Things that will bite you

- **Sign conventions.** Body axes, Euler order, servo direction, canard positive
  deflection, magnetometer frame. Write them down once, in one file, and reference it
  everywhere. More student projects fail on a sign error than on anything else here.
- **Roll coupling.** As the vehicle rolls, your canard plane rotates relative to the
  target direction. Guidance commands must be computed in an inertial frame and rotated
  into the body frame every cycle. Closing the roll loop first makes everything downstream
  easier.
- **Authority collapses with dynamic pressure.** Almost all your control capability is in
  the first three or four seconds after burnout. Plan the manoeuvre for that window.
- **Servo noise into the IMU.** Four servos slewing next to a MEMS gyro on a shared power
  bus. Separate the supplies, filter, and mount the IMU on isolation.
- **Recovery is not the interesting part, and it is what will destroy the vehicle.**
  Budget real time for it. A lawn dart takes the avionics and the data with it.
