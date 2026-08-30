# Ordered plan

## State of play — August 2026

Read this first if you are picking the project back up.

- **Steps 0, 1, 2 are closed.** Sizing tool built, range access and certification path
  resolved, OpenRocket cross-check done and agreeing (CNa to 0.3%, CP to 0.17 cal).
- **Step 3 is nearly closed.** The airframe is frozen in `design/configure.py` — that file
  is the single source of truth for the vehicle and every script imports from it. The BOM
  is drafted (`04-bill-of-materials.md`). **The one remaining deliverable is a dimensioned
  drawing**, which is CAD work in Onshape.
- **The canard module inertia is measured**, not estimated. `design/control.py` now
  superposes the CAD tensor (`CANARD_MODULE_CAD`) on the crude bulk estimate: vehicle roll
  inertia up 6.4%, pitch down 1.5%, pitch mode 4.30 → 4.34 Hz, roll acceleration down ~6%.
  Roll is the axis GV-3 flies, so the 6.4% is the one that matters. The tensor is now read
  off `Assembly 1` rather than Part Studio 1, because the servos are real parts in their own
  studio and only share a frame once assembled. The rest of the airframe is still ±30% until
  you swing it.
- **The CAD is now driven through the Onshape REST API, not the browser.** That change paid
  for itself immediately: reading the feature tree as JSON exposed two defects that clicking
  around had hidden for weeks — a hinge dimension measured to a circle's tangent instead of
  its centre, and a `Hinge Plane` datum that drove no geometry at all. Between them the
  physical hinge sat at 0.029 of MAC instead of 0.200, which is a **0.82× servo torque
  margin against a 2.0× requirement**. Both are fixed and verified; see `docs/05`.
  **If you touch the CAD again, use the API.** Credentials live outside the repo.
- **The servos in the CAD are now the real part, and the CAD articulates.** The
  23.5 × 8 × 16.8 envelope block is superseded by KST X08 Plus geometry built from the
  datasheet, in its own Part Studio, and `Assembly 1` holds the module and four servos in
  position. `python scripts/canard_sweep.py` drives the canards through ±8° for real and
  reports clearances — the interference check `docs/05` had carried as NOT RUN since the
  module was built. Two things the block had hidden came out of it; they are corrections 9
  and 10 below. The four revolute hinge mates are the one piece not finished: the mate
  connectors and the rigid groups are in, the mates are not.
- **The hinge is a mechanism now, and closing it found a third thing.** Both fits
  correction 10 left open are closed — see correction 11 and `docs/05` "The hinge stack".
  `design/hinge.py` models the shaft, bearing and coupling as a load path rather than as a
  set of dimensions; `scripts/hinge_report.py` prints it; `scripts/make_hinge_stack.py`
  applies it to Onshape and is safe to re-run. `scripts/baseline.py` now carries a
  hinge-stack verdict, and the check is run against the **as-built** layout too, where it
  fails on five counts. A check that has never failed is not evidence of anything.
- **Step 4 is next**: avionics. Decisions D7 (flight computer) and D8 (state estimation)
  are open and drive the largest, least specified line in the budget.

Current vehicle: 79.4 mm OD fiberglass, 1361 mm, canards 0.85 cal / aft fins 1.55 cal
interdigitated 45°, **both sets swept 35.4°**, Cesaroni J449 Blue Streak, 4× KST X08 Plus
servos flat-mounted with the hinge at 0.20 of MAC, 100 g nose ballast. Canards 67.5 root /
27.0 tip (0.40 taper). 6.10 kg wet, apogee 1379 m, Mach 0.531, static margin 2.03–2.52 cal,
P(SM<1.0) 0.4%, 424 m crossrange. `scripts/baseline.py` regenerates
all of it; `evaluate()` reports feasible with no violations, and that now includes a check
that the recovery hardware physically fits in the bay.

**One open decision you should know about before the defence:** §7 used to claim the
selected fin sizes gave the highest crossrange of any combination that passes every
constraint. They do not — they rank third. `scripts/robustness.py` picks canard 1.00 / aft
1.70 cal, which passes everything and buys 16% more crossrange (493 m against 424 m) at the
cost of flutter margin (1.78 against 1.97) and servo torque (2.3× against 2.8×). 0.85/1.55
is retained on margin, and because the Onshape module is built to it — but that is a choice,
and §7 now says so instead of hiding it.

Eleven corrections are worth knowing about. The first four changed the design; two of the
rest are checks that CONFIRMED it, which is its own kind of result. Each is the kind of thing
that silently recurs:

1. **Actuator packaging never set the airframe diameter** (§4). The original model assumed
   the servo body points inward; the output shaft is on a large face, so the servo lies
   flat and packaging is not binding at all.
2. **The canard hinge sign was inverted** — hinge aft of the panel CP is divergent, not
   self-centring. Now at 0.20c, forward of the 0.25c CP, and `hinge_moment()` returns a
   signed value so it cannot hide again.
3. **Nose ballast is required, not optional** (§7.1). Real 9 g servos removed ~180 g from
   ahead of the CG and took P(SM<1.0) to 1.8%. The 35.4° sweep briefly retired this — swept
   canards are less destabilising and the bare vehicle dropped to 0.7% — but sharpening the
   taper to 0.40 put the authority back and the risk with it, so it is 1.2% again and
   ballast is required once more. About 25 g is the minimum; 100 g is the design point.
   Canard authority and static margin are the same knob seen from two ends.
4. **The baseline used to live in six places and drifted from the docs.** It now lives
   only in `design/configure.py`. Do not copy those numbers into a script.
5. **The recovery bay is 4.5 cal because it was checked, not because it was typed.** It
   *was* just typed — nothing verified it until `recovery.check_packing()` existed. The
   first run of that check said the bay was 11 mm short and the airframe was briefly
   lengthened to 5.1 cal on the strength of it. **That was wrong, and the way it was wrong
   is worth remembering**: packed volume was estimated as budgeted mass ÷ assumed bulk
   density, and the budget carries a 280 g main against a real Iris Ultra 60" Compact at
   193 g. Two guesses multiplied together manufactured a shortfall that is not in the
   hardware. With the vendor's published pack volumes the chutes need 4.33 cal and fit
   with 13 mm to spare. The airframe was right all along; only the confidence was missing.
   **Do not change frozen geometry on the strength of an estimate when a published number
   is ten minutes away.**
6. **`check_flat_mount()` modelled the servo turned 90°.** It stacked the 23.5 mm body
   length around the circumference where the build puts 16.8 mm, overstating the arc
   requirement by a third — 106 mm against a true 79 mm. Both orientations fit, so no
   conclusion moved, but the wrong figure had already propagated into three documents
   before anything caught it. `check_bellcrank()` always had it right; they now agree.
7. **The canards had no sweep parameter at all.** `sweep_length` was hardcoded to a
   symmetric-taper trapezoid while the aft fins had a real `aft_sweep_cal` — so the canards
   sat at 7° against the aft fins' 35.4° and the vehicle read as two different designs.
   That default was also the maximum-authority shape (symmetric taper puts the mid-chord
   line at zero sweep), so matching the aft fins costs 12.5% of lateral authority: 2.08 →
   1.82 g, 450 → 394 m of crossrange. It buys static margin, torque margin, and a vehicle
   that looks like one object. `canard_sweep_cal = None` now derives the angle from the aft
   fins so the two cannot drift apart. **The hinge sign does not change with sweep** —
   hinge and panel CP are both referenced to the MAC — but the hinge STATION moves a long
   way — 57.2 → 68.3 mm from the module forward face — which is why the CAD had to be
   rebuilt. That rebuild is **done** (`docs/05`), and it turned up two Onshape bugs worth
   knowing: a wall cut that landed exactly on both faces and so cut nothing, and a circular
   pattern that silently dropped the material assignment on all nine copies.
8. **Taper was 0.70 because nothing had tried anything else.** Sharpening it to 0.40 (root
   grown to 0.85 cal to hold panel area at 3188 mm²) recovers most of what the sweep cost —
   1.82 → 1.96 g, 394 → 424 m — because CNa rises as the tip unloads. Root and taper are
   now set as a PAIR and must stay that way, or the area moves and every study downstream
   is invalidated. The price is flutter: the longer root chord drops the canard margin from
   5.42× to 4.46× at fixed 3.0 mm thickness. Still ~3× the requirement, but this is now the
   number to watch if the panel ever gets thinner.

9. **A bounding box has no output shaft, and that is not a small thing.** The servo was
   modelled as a mass-tuned block for long enough that two of its properties were never
   checked, because a block does not have them. The KST drawing says the output shaft is
   **6.14 mm from one case end, not centred at 11.75** — `docs/05` had flagged the centred
   assumption as "unconfirmed", and it was wrong — and that the shaft runs along the
   **16.8 mm axis**, so a radial output shaft spends 16.8 mm of tube radius and stacks only
   8 mm around the circumference. Every document said the reverse, which describes a servo
   whose shaft leaves its narrow edge. Both orientations fit and the packaging conclusion
   does not move, but the **central void goes from 45 mm to 17 mm** once the cable boss is
   counted, and that void is where the wiring and any pass-through structure live. (It is
   ⌀12.17 now: correction 11 moved the servos 4 mm inboard, and `check_flat_mount()` was
   given the servo's real seat so it measures the void instead of budgeting for it.) The
   pattern here is the same one as correction 1 and correction 6: **the actuator keeps
   being modelled as a shape rather than as a mechanism, and every time, the thing that was
   wrong was the bit the shape could not represent.**
10. **The interference sweep needed a mechanism, not a calculation — and then barely needed
   the sweep.** Once the canards could actually turn, the answer fell out of the
   arrangement: the hinge axis is radial and the shaft is coaxial with it, so the shaft
   sweeps nothing; rotation about a radial hinge preserves each panel point's distance from
   the rocket axis, so a panel that starts outboard of the tube stays outboard at every
   deflection; and the servos are entirely inboard of the wall while the panels are
   entirely outboard, so the two never share a radius. Nothing fouls. **What the sweep did
   turn up were two FITS that a static model cannot express**: the wall pass-through is
   ⌀5.000 against a ⌀5.000 shaft, because it reuses the shaft's own sketch — right for
   position, wrong for fit, and invisible to any interference check because zero clearance
   is not an interference — and the servo spline reaches only **0.185 mm** past the panel
   root face, so direct drive from the spline is not geometrically available and the
   spline-to-shaft coupling is an unmodelled design decision. **Both are closed by
   correction 11, and the sentence above about the servos and panels never sharing a radius
   is where the third defect hid: the SHAFT shares a radius with both.**
11. **The two open fits were one problem counted twice, and there was a third underneath.**
   Closing correction 10 started by asking what the shaft was actually made of. It was a
   **solid** ⌀5 rod from R 29.400 to R 40.200 — the API returns 212.058 mm³ against 212.058
   for a solid cylinder, so nothing had ever been cut away for the servo — while the
   servo's output face sat at R 37.185 with its case running inboard from there. **The
   shaft and the servo occupied the same space: 3.015 mm inside the output spline, 7.785 mm
   inside the case.** A hard clash, at zero deflection, in a model whose interference check
   had been signed off. The sweep did not see it because the sweep asked whether *rotation*
   caused a collision, and its answer to the question it asked was correct. The R 29.400
   was a leftover — the inboard face of the obsolete servo *block* — which is the lesson:
   **superseding a part does not supersede the dimensions that were taken from it.**

   The three defects share one cause. Between the servo's output face and the panel root
   there were **3.015 mm of radius and the airframe wall took 2.300 of them**. So there was
   no room for a bearing and therefore no bearing, no room for a coupling and therefore no
   coupling, no room for clearance and therefore none of that either. A LAYOUT problem in
   three tolerance costumes, and no fit callout fixes it.

   What made it visible was **the panel normal force, which nothing had ever computed**.
   The hinge moment is 0.0599 N·m — small, which is exactly why a 9 g servo is enough,
   because the hinge sits 2.4 mm from the panel CP. The same panel makes **25.4 N** at a
   bearing 29 mm away, so **0.734 N·m** of bending. *Reading only the hinge moment is how a
   hinge ends up with no bearing in it.* And peak pressure under an overhung load goes as
   1/L², so the 2.3 mm of wall available was not a slightly worse bearing than a 6 mm one —
   it was 175 MPa against an 80 MPa allowable.

   Fixed by moving the **servo** 4.000 mm inboard rather than the panel: the panel is
   frozen aerodynamics, the central void is a budget line. The shaft is now a ⌀6 sleeve
   from R 33.485 that stops at the servo's output face; the wall bore is a ⌀7.975 seat
   carrying **its own dimension**, so it cannot track the shaft again; a ⌀6/⌀8 × 6.0 plain
   bearing takes the bending at 3.4× margin and the spline socket engages 91% of the
   spline. Cost: central void — every band lost the same 8 mm, ⌀20.17 → ⌀12.17 over the
   8.2 mm where the cable bosses sit and ⌀40.77 → ⌀32.77 alongside the cases — plus 1.2 g
   and 1.3% of module roll inertia. **No control conclusion moved.** The **sleeve-to-panel joint** is
   now the open design decision, in the slot the coupling used to occupy: a ⌀6 shaft cannot
   simply enter a 3.0 mm panel, and that joint carries the full 0.734 N·m.

Still TBD and only you can close them: C1 (cert held), C3 (budget), C4 (calendar), C6 (fab
access), the cert milestone dates in §2.1, and D1/D7/D8/D9.

---

The ordering here is deliberate. Each step exists to remove a specific risk, and the
risks are ordered by how badly they hurt if you discover them late. Airframe geometry is
step 3, not step 1, because two things upstream of it can invalidate everything.

---

## Step 0 — DONE: preliminary sizing tool

`design/` and `scripts/` now answer the questions that were blocking you in OpenRocket.
Baseline: 75 mm fiberglass, 4 interdigitated canards, J-class 54 mm motor.

## Step 1 — DONE: close the two project-killing risks

Neither of these is engineering, and both can end the project if found late.

**1a. Range access and legality.** See `00-requirements.md` §1.2. Email your club prefect
describing exactly what you intend to fly, and get a written answer. Loop in your faculty
advisor and, through them, your university's export control office. Until you have a
"yes," treat the whole flight campaign as unconfirmed.

**1b. Certification path.** You cannot fly a J motor without Level 2, and you cannot get
Level 2 without Level 1 first. Each is a separate flight on a separate launch day, and
launch days are monthly and weather-dependent. Work backwards from your flight window and
book the earliest possible L1 attempt.

Status (Aug 2026): **CLOSED.** Prefect contacted and answered; earliest L1 attempt booked;
recovery area confirmed effectively unbounded, which retires C5a as the governing
constraint (see `00-requirements.md` §2, R6); NAR + TRA code summary written and the
advisor / export control contact made. Keep every written response on file — the artifacts
are what a reviewer asks for, not the fact that it happened.

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
- actuator selection and hinge line position. Put the hinge **forward** of the panel
  centre of pressure so the panel is weakly self-centring rather than divergent. Forward,
  not aft: with the hinge aft of the CP the normal force acts ahead of the hinge line and
  drives the panel to greater deflection, which is an overbalanced surface. The default is
  now 0.20c against a 0.25c CP. Keep real separation — panel CP moves with Mach and angle
  of attack, and a hinge too close to it can cross into divergent in flight;
- static margin at rail exit, target 1.5–2.5 calibers nominal **and** P(SM < 1.0) under 1%
  once you rerun `scripts/robustness.py` with real weighed masses;
- a nose ballast provision — threaded rod and washer stack in the nose shoulder. Do not
  skip this. It is a few dollars and it turns static margin from a prediction you are
  betting the vehicle on into something you set after weighing the finished rocket.
  Roughly 100 g there moves the margin +0.12 cal.

As components arrive, weigh them and replace the estimates in `design/mass.py` with real
numbers, then rerun the robustness script. Every guess you retire shrinks the distribution.

Deliverable: a frozen `DesignParams` in `design/configure.py`, a dimensioned drawing, and
a bill of materials with real part numbers and prices. **BOM drafted** —
`docs/04-bill-of-materials.md`. The dimensioned drawing is the last piece; build the canard
module first, following `docs/05-canard-module-build.md` and the DXF profiles from
`scripts/make_cad_profiles.py`.

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
