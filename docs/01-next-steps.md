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
  connectors and the rigid groups are in — **and as of Aug 2026 so are the mates**, added in
  the browser because the API will not author that connector reference. `Assembly 1` now
  carries `Canard 0 (+X) hinge` … `Canard 3 (-Y) hinge`, REVOLUTE, each pairing
  `tube{n}` with `shaft{n}`. Mass and CoM did not move, which is how you know the paired
  connectors really were coincident. **They did not actually turn until Sep 2026** — the
  ±8° mate limit froze all four, and no one had ever driven one to find out
  (correction 39). Limits are off now, the deflection limit lives where it is enforced
  (`DEFLECTION_LIMIT_DEG`), and `scripts/fix_hinge_mate_limits.py --verify` drives every
  hinge and parks it at zero.
- **The hinge is a mechanism now, and closing it found a third thing.** Both fits
  correction 10 left open are closed — see correction 11 and `docs/05` "The hinge stack".
  `design/hinge.py` models the shaft, bearing and coupling as a load path rather than as a
  set of dimensions; `scripts/hinge_report.py` prints it; `scripts/make_hinge_stack.py`
  applies it to Onshape and is safe to re-run. `scripts/baseline.py` now carries a
  hinge-stack verdict, and the check is run against the **as-built** layout too, where it
  fails on five counts. A check that has never failed is not evidence of anything.
- **The hinge load path is closed end to end.** The two items the hinge stack left open
  are both done (corrections 12–14): the **sleeve-to-panel joint** is a 1.8 × 11.9 mm
  tang 25.5 mm into the root — which turns the panel into a 0.6/2.0/0.6 bonded laminate,
  a manufacturing change and not a design one — and the **tube at the hinge station** is
  checked and passes by two to three orders of magnitude on everything except the bearing
  seat, which sits at 3.2× *only* because the housing collar has not been built.
  `design/tube_section.py` and `design/materials.py` are new; `design/hinge.py` carries the
  joint; `scripts/hinge_report.py` prints both and `scripts/baseline.py` carries both
  verdicts so neither can silently regress. **The one open item in the whole hinge is the
  housing collar** — no longer blocked (correction 16 removed the bracket it was waiting
  on), and worth a measured **3.4× → 14.5×** on the bearing seat — see correction 19,
  which is where the 21.3× this document used to quote went.
- **The bearing is geometry now, not a dimension.** It was the last part of the hinge that
  existed only as a number, and an unmodelled part cannot collide with anything — the same
  trap that hid a hard servo clash for weeks when the servo was a bounding box. Part Studio
  `Hinge bearing (⌀6/8 × 6 plain)` holds it, and all four are instanced in `Assembly 1` on
  their hinge axes at R 39.700, in the airframe rigid group because a pressed race does not
  rotate with the panel. `scripts/make_bearing_cad.py` builds it, `scripts/place_bearings.py`
  places it, both are safe to re-run. **This is what the printed bay's collar now gets drawn
  against.**

- **The printed bay is built** (correction 19). `design/bay.py` models it, `cad/canard_bay.fs`
  and `scripts/make_bay_cad.py` build it, `scripts/bay_report.py` prints the argument, and
  `Assembly 1` holds it at identity along with eight retainer bars. One PETG-CF print, 39 g.
  **The hinge load path is now geometry end to end**, tube to panel, with nothing left as a
  dimension. Two things it turned up are open and neither is a bay problem: **the coupling**
  (no bought servo horn fits in 0.515 mm — correction 19) and **the aft gas seal**, which is
  a bulkhead and has never been sized.
- **The coupling is closed** (correction 21). The shaft's inboard end takes a plain
  ⌀4.100 × 3.20 drilled socket, bonded onto the servo spline with anaerobic retaining
  compound that cures into the tooth valleys and becomes the female spline. No broaching, no
  bought adapter, and it comes apart with heat. Cut in the CAD.
- **The aft gas seal is sized, and it was never a seal** (correction 25). `design/seal.py`,
  `scripts/seal_report.py`, verdict in `scripts/baseline.py`, write-up in `docs/05`. A
  **G-10 disc, 4.8 mm, 39 g** — sized not against gas tightness but against being the piston
  the ejection charge pushes on (7329 N in the stuck-joint case) and the anchor the main
  pulls on (1338 N).
- **Everything the seal opened is now closed too**, and each one turned out to be a
  different kind of problem:
  - **The internal bulkhead**, which was a 12.0 mm length allowance in `recovery.py` and
    nothing else, is now the same model applied a second time — **4.8 mm, 39 g**, with a
    charge on both faces and, unlike the seal, **no shear pins protecting it**. Both come
    out at the same pressure for a reason worth knowing: correction 29.
  - **The drogue's firing circuit** runs in a ⌀5 mm bonded conduit through the main
    compartment. Priced in `recovery.py` along with the four U-bolts nobody had counted, and
    together they take the recovery bay's margin from **+13.0 mm to +6.8 mm**. Still fits.
  - **The venting** is `design/venting.py`, and it corrects the seal's own argument
    (correction 28). The canard module vents through **its own wall**, so it is not in the
    altimeter's sense volume and the wiring pass-through is potted solid.
  - **The nav bay has a packing check now** (`design/avionics.py`,
    `scripts/avionics_report.py`) and **it still does not pass**. The tracker and the
    telemetry radio moved into the nose (correction 30) and the shoulder question is settled
    (correction 31); between them the gap went 47 mm → **9 mm short** on estimated
    envelopes. Read correction 27 before doing anything more — this is correction 5's exact
    trap, and it is an `evaluate()` **warning**, not a violation.
- **The joints are modelled** (correction 31). `design/joints.py` — all four of them, which
  `tube_section.py` has wanted since it was written. **A coupler is a tube and its bore is
  usable**, so it costs local diameter and not bay length; only bulkheads cost length. That
  settled the nose shoulder, and it also took the recovery bay from +6.8 mm to +0.1 mm.
- **The recovery bay margin is fixed, and the harness is why** (correction 33). It is
  **+17.8 mm** now, and the fix was not to shave anything: **nothing in this project had
  ever sized the harness.** Its volume came from a budget line nobody had checked, divided
  by an assumed bulk density; its strength came from nowhere. Sized against the opening
  shock it actually carries, it is **3/4" tubular nylon at 4.2×** rather than 1" at 6.7×.
- **The nose is the instrumentation module, and it is meant to come off** (correction 32).
  Tracker and telemetry radio live there, self-contained, on one connector. A future payload
  of **up to about 300 g needs no other change**; past that the vehicle goes over-stable
  rather than unstable, and the nose ballast is the trim knob.
- **Both bulkheads are CAD now** (correction 34). `scripts/make_bulkhead_cad.py` builds
  them, `scripts/place_bulkhead.py` puts the aft gas seal in `Assembly 1` at Z = 142.900,
  and Onshape's own **Check interference reports none across all 35 instances**. Volumes
  agree with the analytic disc-less-holes to 0.000 mm³. **Read the caveat in correction 34
  before trusting that clean result.**
- **The two module vents are CUT** (correction 37). 2 × ⌀2.0 mm at **Z 120.0 mm**, clocked
  **45° / 225°**, placed in `design/venting.py` and cut by `scripts/make_module_vents.py`.
  The station is chosen by the **leak path**, not the flow field — see `docs/05`.
- **The canard module has one open engineering item after all, and it is not in the
  module** (correction 37). The forward wiring pass-through cannot be drawn because **the
  plate it passes through has never been sized**: `joints.py` puts a bulkhead on all four
  joints, `seal.py` sizes the two separation ones, and **neither access bulkhead — the
  nav bay / canard module plate, and the nose's aft face — has ever been sized by
  anything**, while both already spend bay length as allowances. What is otherwise left is
  the Step 3 drawing.
- **Both access bulkheads are sized, and neither is sized by stress** (correction 38).
  `design/access_bulkhead.py`, `scripts/access_bulkhead_report.py`, verdict in
  `baseline.py`. Both clear the thinnest stocked G-10 sheet by 25×+ on every load found —
  the pass-through plate because the bays either side of it (nav bay, canard module) both
  vent to ambient **on their own**, so the only load across it is the nav-bay/module venting
  **lag differential**, about 5.5 Pa; the nose plate against the **trapped
  pad-to-apogee differential** (15.4 kPa, conservative — see below) plus a **300 g payload
  point load** at max boost accel, correction 32's provision ceiling rather than the 105 g
  actually flying. **What actually sets both plates is producibility** — holding a screw
  thread through repeated disassembly, a connector's panel-nut torque — which has no stress
  model here, so a stated practical floor stands in: **2.4 mm / 19.5 g** for the pass-through
  plate, **3.2 mm / 26.0 g** for the nose plate. Same shape of result as `venting.py`'s port
  sizing: the model gives the floor, practice gives the design point.
  `CANARD_MODULE_FREE_VOLUME` also stopped being a two-script duplicate and now lives in
  `design/venting.py`, since this was its third caller.
  **One real gap surfaced, not closed: the nose cavity's own venting has never been modelled
  anywhere in this project** — `design/avionics.py` and `design/venting.py` both stop at the
  nav bay. The nose plate is checked against the fully-sealed case until that gap is closed;
  if a nose vent is added later, that load goes away and the plate stays oversized rather
  than becomes undersized. Two part numbers are still open and don't move the plate: the
  pass-through's wire bundle (no gauge has ever been chosen) and the nose module's panel
  connector. **The pass-through can now be drawn.**
  Both plates are CAD now too: `scripts/make_access_bulkhead_cad.py` builds them (volume
  verified against the analytic disc-less-hole figure on the first build), and
  `scripts/place_access_bulkhead.py` instances the pass-through plate in `Assembly 1` at
  Z = 0.000 — the module's forward face, with identity transform because the disc's own
  frame is built as the aft seal's *mirror* (origin on the forward face, growing aft) rather
  than a copy of it. **Check interference reports none across all 36 instances.** The nose
  plate is a part only, same reasoning as the internal bulkhead: its cavity is unmodelled.
- **D7 is CLOSED** (correction 35). A **custom STM32F405 board** flies the guided vehicle
  and a **Teensy + breakout stack** flies the L1/L2 certs as a passive logger — staged in
  that order, because the cert launches are monthly and eight weeks of PCB work would spend
  them. Deployment stays on an independent commercial altimeter in both stages.
  `docs/06-avionics-selection.md`, `scripts/avionics_trade.py`. **And it dissolved the nav
  bay warning**: every architecture fits, because the guessed flight computer was 2.5× the
  size of the real part.
- **D8 is CLOSED** (correction 36). **IMU + baro + GNSS + magnetometer**, with the
  **estimator staged by guidance level** rather than the sensor set — D7 could stage the
  hardware because a PCB takes eight weeks; D8 cannot, because every sensor has to be on the
  schematic at once. `docs/07-state-estimation.md`, `design/estimation.py`,
  `scripts/estimation_trade.py`, and a verdict in `baseline.py`. It closes **without D1**.
  Four findings, and all four are free before layout and unrecoverable after: **the |a| gate
  this document prescribed opens at burnout and admits drag as gravity**; **the IMU must
  sample at 1 kHz, which is not the 86 Hz control loop rate**; **roll angle was observed by
  nothing on D7's board**, and L1 is defined on roll angle; and **D7's gyro figure was
  computed at 6° and printed under an 8° heading** — the real number at the deflection limit
  saturates a ±2000 dps part. **Step 4.2 below is corrected; do not build from the old
  version.**
- **Correction 37 is the CAD one**, and it came out of finally trying to draw the last two
  holes in the canard module. The vents are cut. The pass-through is not, and the reason is
  the finding: **two of the vehicle's four joint bulkheads have never been sized by any
  model**, and they were invisible because `joints.budgets()` already charges bay length
  for them and `seal.py`'s exclusion list named only the booster's. An allowance that
  nobody turned into a part, for the third time in this project.
- **The Fusion 360 rebuild does not match the Onshape module, and the servos were not why**
  (correction 40). `cad/onshape_export/Assembly_1.step` is imported into the Fusion file
  next to the native rebuild, so the two can be booleaned body-for-body. Four parts
  transferred exactly and the **servos are provably correct** — the merged servo body is
  13.3518 mm3 heavy, which to four decimals is the six flange holes that were not cut, and
  every dimension in `SERVO_GEOMETRY` survived. Two findings are load path and make the
  module unbuildable: **all six radial holes in the tube are blind**, stopping on a plane
  tangent to the bore and leaving a 0.2145 mm crescent web that the bearings and shafts run
  into (and the two vents therefore do not vent, undoing correction 37); and **the bay's
  four bearing bores are plugged by 2.400 mm of uncut shell wall**, with the collar bosses
  run out to R 37.400 instead of R 36.500 so they bury themselves in the tube. Pairwise
  boolean says it plainly: **21 clashing pairs at 0.85-52.95 mm3 in the rebuild, against 6
  tolerance slivers all under 0.028 mm3 in the reference.** Also open, and pointing the
  other way: the Onshape bearing carries ~0.3 mm lead-in chamfers that
  `scripts/make_bearing_cad.py` does not know about. **All four are fixed and the file is
  saved** -- and the repair re-used the check, because for a rebuild that is a superset of
  its source the reference solid is also the cutting tool: `rebuild - (rebuild - reference)`
  lands it exactly, with no dimension re-typed. Tube and bay now boolean to an **empty**
  difference against Onshape; interference is **4 pairs at 0.0192 mm3 against the
  reference's own 6 at 0.0278**, which is parity and is the right bar -- a STEP round trip
  will not reproduce coincident faces to zero. The extra tray webs were confirmed
  unintentional and cut (1127 mm3, ~1.5 g). Still open by choice: the bearing chamfer,
  which belongs in Onshape or in the script rather than in the rebuild. Full write-up in
  `docs/05`, "The Fusion 360 transfer". **Volume and mass agreement is not model
  agreement** -- none of this moved a gram.
- **Step 4 is next in the plan**, and D8 has settled what it is built from. What is left is
  firmware: the filter, the HIL rig, the controller and the safety logic.

Current vehicle: 79.4 mm OD fiberglass, 1361 mm, canards 0.85 cal / aft fins 1.55 cal
interdigitated 45°, **both sets swept 35.4°**, Cesaroni J449 Blue Streak, 4× KST X08 Plus
servos flat-mounted with the hinge at 0.20 of MAC, 100 g nose ballast. Canards 67.5 root /
27.0 tip (0.40 taper). **6.14 kg wet, apogee 1369 m, Mach 0.526, static margin
2.11–2.60 cal, P(SM<1.0) 0.2%, 400 m crossrange.** Telemetry radio and GPS tracker ride in
the **nose** at station 300 mm, not in the nav bay (correction 30). Every one of those
figures moved in Aug 2026 — the missing dual-deploy altimeter (correction 26) and then the
nose move. `scripts/baseline.py` regenerates
all of it; `evaluate()` reports feasible with no violations, and that now includes a check
that the recovery hardware physically fits in the bay.

**One open decision you should know about before the defence:** §7 used to claim the
selected fin sizes gave the highest crossrange of any combination that passes every
constraint. They do not. `scripts/robustness.py` now picks **canard 1.15 / aft 1.85 cal**,
which passes everything and buys **514 m against the selected 390 m** — 32% more. It costs
flutter margin and servo torque; run the script for the current figures rather than quoting
these, because they moved once already when the altimeter went into the budget
(correction 26) and they will move again when parts get weighed. **0.85/1.55 is retained**
on margin, and because the Onshape module is built to it — but that is a choice, and §7 says
so instead of hiding it.

Thirty-nine corrections are worth knowing about — 38's own numbered entry is still only the
bullet above. The first four changed the design; two of the
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
   (**⌀8 H7 since correction 16**) carrying **its own dimension**, so it cannot track the
   shaft again; a ⌀6/⌀8 × 6.0 plain bearing takes the bending at 3.4× margin and the spline
   socket engages 91% of the spline (**that socket is superseded by a bought horn —
   correction 16**). Cost: central void — every band lost the same 8 mm, ⌀20.17 → ⌀12.17 over the
   8.2 mm where the cable bosses sit and ⌀40.77 → ⌀32.77 alongside the cases — plus 1.2 g
   and 1.3% of module roll inertia. **No control conclusion moved.**

12. **The last link was the hard one, and the answer was that the panel is made
   differently.** Correction 11 left the **sleeve-to-panel joint** open — a ⌀6 shaft cannot
   simply enter a 3.0 mm panel. It is the *hard* end of the load path, not the easy one:
   every number in the hinge stack shrinks going inboard because the bearing takes the
   couple out, and going outboard the moment is at its maximum, **0.721 N·m into 3.0 mm of
   G10**. Three of the four candidate joints lose to something already frozen rather than to
   structure — a root boss needs 9 mm of panel thickness and t/c drives flutter; a clevis
   stands proud of the panel in the fastest flow it sees; a one-piece aluminium panel adds
   154 g aft of a CG that already needs 100 g of nose ballast. The winner is a **1.8 × 14 mm
   tang, 30 mm into the root**, tang 2.9× and skin 2.9×, deliberately balanced.

   The finding worth keeping is not the tang. It is that **a 1.8 mm slot 25 mm deep into
   a 3.0 mm plate is a 14:1 blind cut and nobody can machine it**, so the panel becomes a
   **0.6 / 2.0 / 0.6 bonded laminate** with the core cut away (1.8 mm at first, which is
   not a stocked sheet — see correction 16). Same planform — the answer to "how does the shaft meet the panel" turned out to
   be a *manufacturing* change, and it would not have surfaced from any stress number.

14. **The tang was sized against stress, and the binding constraint was geometry.** The
   first version of correction 12 chose 1.8 × 14 × 30 and argued that depth was free —
   slot pressure goes as 1/L², so deeper is better and costs nothing. True, and the wrong
   axis. **The panel is swept 35.4°, so its leading edge runs aft 0.71 mm per mm of span**
   while the tang stays in a fixed axial band about the hinge axis, because it is the end
   of a shaft that turns about that axis. 30 mm of depth left **2.26 mm** of panel ahead of
   the tang. Worse, the "60% of chord" rule meant to bound it **allowed 40.5 mm, where the
   tang stands 5.18 mm proud of the leading edge** — a rule that admits an unbuildable part
   reads like a check and is worse than none.

   Now 1.8 × 11.9 × 25.5, with **6.15 mm** of leading edge and 2.5× on both the skin and
   the tang.

   **And there was a datum error underneath, which only reading the CAD caught.** The first
   fix read 5.50 mm of clearance where the truth was 5.14: `engagement` is measured from the
   panel root face at R 40.200, the planform's sweep and semispan from the theoretical root
   at the tube surface, R 39.700, and the 0.500 mm standoff between them was being ignored.
   The analysis agreed with itself and disagreed with Onshape, where panel 0 runs R 40.20 to
   107.19 — and 107.19 is 39.700 + 67.490. `RootJoint` is now indexed by radius throughout,
   which is what `HingeStack`'s docstring had already said to do.
   The old tang is kept and exercised: **every stress margin in it is better than the
   selected joint's and it is still not buildable**, which is the only case in this project
   that fails on geometry while passing on strength.

   A second bug fell out of writing the check: `slot_chord_fraction` divided engagement by
   the root **chord** when the tang reaches along the **span**. It returned the right number
   anyway, because `canard_root_cal` and `canard_semispan_cal` are both 0.85 and the two
   lengths are both 67.490 mm — and it would have silently read the wrong dimension the
   moment either moved. Same class of error as the sketch that measured to a circle's
   tangent. Found only by trying to build the thing in CAD, which is the general lesson:
   **the model agreed with itself right up until geometry had to exist.**

13. **The tube passed by three orders of magnitude, and the one number that did not is the
   one nobody was worried about.** `check_hinge_stack()` had emitted *"check the tube, not
   just the hinge"* since the hinge stack went in and nothing had. Four ⌀8 bores at one
   station remove 13.2% of a 79.4 × 2.3 tube's circumference; net section runs at **256×**,
   torsion 348×, shell buckling 434×. The airframe was never the risk.

   **The bearing seat is, at 3.2×** — and only because the housing collar does not exist.
   3.700 mm of the 6.0 mm bearing sits inboard of the tube ID, so with no collar the 2.3 mm
   wall holds it alone at 109 MPa; with a PETG-CF collar, 25.5 MPa and 14.5×. (This
   line read "17.4 MPa and 21.3×" until correction 19 asked what the collar was made
   of.) Peak pressure goes
   as 1/L², so those are **6.7× apart**. The printed bay was already blocked on bracket
   hardware; it is now blocked on something with a number attached. Two caveats stated
   rather than buried: the allowables are G-10 *sheet* and a filament-wound tube is not
   sheet (**under 4×, go get the real datasheet** — the seat is under it), and **global
   airframe beam bending under a gust is still not modelled anywhere in this project.**
   `design/tube_section.py` is the first structural model it has, and it runs at trim.

15. **A failing joint was reporting a pass, and only a buyability question found it.** The
   skin over the tang slot was computed as `(panel − tang)/2`. The slot is the tang **plus a
   bond line on each face**, so the real skin was 0.5 mm where the model said 0.6 — and skin
   stress goes as 1/t², so the joint sat at **1.69× against a 2.0× requirement while
   reporting 2.5×**. What surfaced it was not a stress review. It was being asked which G10
   sheets to *order*, which forces the stack to be expressed in thicknesses that exist.
   **"What do I buy" is a different question from "what is optimal", and it finds different
   bugs.**

16. **The panel is a laminate of two stocked sheets, and the shop is a 3D printer.** The
   0.6/1.8/0.6 stack was dead twice over — 1.8 mm G10 is not sold anywhere, and it was the
   thickness that produced correction 15. Now **0.6 / 2.0 / 0.6, 3.2 mm total**, the middle
   sheet cut away at the root so the slot is never machined at all. `canard_thickness` moved
   3.0 → 3.2, a frozen parameter changed for a manufacturing reason: flutter margin improves
   4.46× → 4.92×, static margin improves 2.03 → 2.04 cal (the 9 g lands forward of the CG),
   and crossrange gives up 1%, 424 → 419 m. Still feasible, no violations.

   Three more things fell out of taking "I have to buy this" seriously:
   - **The ⌀7.975 bearing seat is not a reamer that exists.** It is ⌀8 H7 now — the most
     ordinary reamer there is — and the press interference comes from the bushing being
     supplied oversize, which is how polymer bushings are actually fitted.
   - **Do not cut the servo spline.** A ⌀4 mm 15T internal spline in a 0.8 mm wall is
     specialist broaching; a servo horn arrives with it already cut for a few dollars. Safe,
     because the bearing sits outboard of the coupling and takes all the bending, so the
     joint carries torque only — 0.520 N·m at stall.
   - **The commercial servo frames do not do what the BOM claimed.** Hyperflight
     SRB-KST-X08 and the IDS/LDS frames are RC-glider *linkage* hardware; their counter
     bearing supports a swinging arm, not a shaft coaxial with the servo output. The
     third-bearing frame is 50 × 37 × 9 mm against a 23.5 × 8 × 16.8 servo, so four of them
     inside a 74.8 mm bore is its own problem. Dropped. Our own wall bearing already does
     that job, in the right place.

17. **The printed bay is unblocked, and it is the best-value part in the module.** It was
   held on "picking real bracket hardware", and correction 16 removed the bracket. The
   collar on it carries 3.700 mm of the 6.0 mm bearing — worth **3.4× → 14.5×** on the
   bearing seat, because peak pressure goes as 1/L² *and* because load goes where the
   stiffness is (correction 19). The build order is the part to get
   right: print the collar bore undersize, bond the bay in, then ream **⌀8 H7 through the
   wall and the collar in one pass**, so concentricity is a property of the operation rather
   than a tolerance held across two parts. A pinched bearing is a mechanism failure, and no
   margin in these documents protects against it.

18. **The bearing got built, and building it found a laminate that could not be ordered.**
   The Onshape `/features` quota came back and the queued work went in: the bearing Part
   Studio (volume checked against the analytic annulus to 0.001 mm³, which is the only proof
   the bore actually cut — a solid slug reads 301.593 instead of 131.947), the ⌀7.975 → **⌀8
   H7** seat correction from correction 16 finally applied to the CAD, and four instances
   placed in `Assembly 1`. Module mass 276.239 → 276.999 g, roll inertia +0.15%. **Nothing
   in the flight model notices, and that is the correct result** — the bearing was never a
   mass part, it is a load-path part.

   Two things worth keeping from it:
   - **`scripts/hinge_report.py` printed the panel as a `0.6/1.8/0.6` laminate**, which sums
     to 3.0 mm against a 3.2 mm panel. It was printing the **tang** as the middle layer
     instead of the **slot** — they differ by the two 0.1 mm bond lines. `design/hinge.py`'s
     own docstring said the same. The docs here were right and the code was wrong, which is
     the opposite of this project's usual rule, and it only matters because these three
     numbers are *sheets you buy*: acting on the printout would have ordered a 1.8 mm sheet
     that is not sold, to build a panel 0.2 mm too thin. Both fixed; the report now names
     the slot and the tang separately and states that the layers must sum to the panel.
   - **A mass guard that trips on an intended change is doing its job.** `make_hinge_stack.py`
     refused the bore correction because Part Studio mass read 276.227 g against a
     `MASS_BEFORE_G` of 259.856 — a stale constant from before the tang and the 3.2 mm
     panel. The geometry was fine. The constant now carries its own history in a comment and
     the tolerance stays tight deliberately: a guard loose enough never to trip is a guard
     that will not catch the circular pattern dropping materials, which is the failure it
     exists for. **A rise is as suspect as a fall until you can name the geometry.**

19. **The printed bay is built, and building it corrected the number that justified it.**
   `design/bay.py`, `scripts/bay_report.py`, `cad/canard_bay.fs`, `scripts/make_bay_cad.py`.
   One printed part, **PETG-CF, 39 g, 41.5 mm long**, holding four servos and four bearing
   collars; plus eight small retainer bars. It is in `Assembly 1` at identity, because it
   was drawn in the module's own frame.

   **The collar is worth 3.4× → 14.5×, not 3.2× → 21.3×.** Every document here priced it by
   putting the whole 6.0 mm bearing length into `p = 6M/(dL²) + N/(dL)` — a formula for ONE
   material. The seat is 2.300 mm of G10 and 3.700 mm of printed plastic, and **a rigid pin
   shares its couple out by stiffness, not by length**. A soft collar simply moves aside and
   the load walks back into the G10. `design/bay.py` models it as a Winkler foundation with
   a piecewise modulus, and it reduces exactly to the old formula when both materials match
   — there is a regression assertion for that, because a generalisation that cannot recover
   the case it generalises is not worth trusting.

   | collar | E, GPa | peak in wall | wall margin | effective seat |
   |---|---|---|---|---|
   | none | — | 109.0 MPa | 3.4× | 2.37 mm |
   | PETG | 1.7 | 37.1 MPa | 10.0× | 4.08 mm |
   | **PETG-CF** | **4.5** | **25.5 MPa** | **14.5×** | **4.93 mm** |
   | PA6-CF | 6.0 | 23.3 MPa | 15.9× | 5.17 mm |
   | *as stiff as G10* | *18.0* | *17.3 MPa* | *21.4×* | *6.00 mm* |

   **Build it anyway** — 3.4× → 14.5× is still the largest margin improvement anywhere in
   this hinge. But the bay is chosen on STIFFNESS, not strength: every candidate is strong
   enough, and they differ only in how much of the collar's benefit they actually deliver.
   Plain PETG passes everything if there is no hardened nozzle.

   Three more things came out of drawing it:
   - **No bought servo horn fits, and correction 16 says to buy one.** There is
     **0.515 mm** between the servo's output face and the bearing; outboard of that the hole
     is the ⌀6 bearing bore. The thinnest 15T ⌀4 horn hub is ~⌀7.4 × 4 mm. Nothing is
     mis-analysed — `design/hinge.py` never adopted the horn and still models and checks the
     broached ⌀4.4 × 2.9 socket at 29.9 MPa — but a builder following these documents would
     find out with four servos in hand. **The coupling is unresolved and it is not a bay
     problem**: no bay geometry fixes it. Either the shaft's spline gets broached or EDM'd
     with the rest of the part (it is already the one custom-machined piece), or the servo
     moves further inboard, and only ~2 mm of that is available before the four cable
     bosses collide.
   - **The servo is clamped, not screwed through its own flange.** Its lug holes sit 1.5 mm
     beyond the case ends and the tray window has to clear the case, which leaves a
     **0.62 mm ligament** — a perimeter and a half, which a slicer may not fill. The load
     does not go through it, so this is printability rather than strength, but "there may or
     may not be material there" is not a thing to build on. A printed bar clamps each end of
     the flange with 2× M2 into heat-set inserts, which also means a servo can be changed
     after the bay is bonded in — and the bay never comes out again.
   - **The bay would have clashed with the servo's own flange**, bosses and flange both
     wanting R 26.935→27.935. Found in CAD, not in the model, and invisible in an end-on
     view because the tray hides it. Fixed with a flange relief; `design/bay.py` now carries
     a clearance table so it cannot come back.

20. **The mass budget carries 240 g where the CAD now measures 63 g, and that is yours to
   decide.** `design/mass.py` has `canard shafts/bearings/sled = 4 × 0.030 + 0.120`, a
   placeholder from before any of it existed. Measured: 4 shafts 23.5 g, 4 bearings 0.8 g,
   bay and bars 38.6 g — **62.8 g**. The 177 g of difference sits at station 0.507 m, which
   is *forward* of the 0.800 m CG, so deleting it moves the CG aft and **reduces** static
   margin from 2.03–2.53 cal. That is probably a good thing (less weathercocking, more
   crossrange) but it is a vehicle-level change to every number in §1, so **nothing has been
   changed**. What the placeholder still legitimately covers is wiring, connectors,
   fasteners, epoxy and the aft gas seal — call that 40 g, not 177 g.

21. **The coupling is closed, and correction 16 was wrong about how.** Correction 16 said
   "do not broach the spline, buy a horn". Correction 19 found that no horn fits. Both were
   circling the same real constraint: **broaching a 15-tooth socket into a 0.95 mm wall is
   specialist, and every bought female-spline part is ⌀7 or larger against 0.515 mm of space
   and a ⌀6 journal.** The way out is neither.

   **Do not cut teeth — cast them.** Drill the shaft's inboard end **⌀4.100 × 3.20**, a
   plain round hole 0.050 mm on the radius over the spline's crests. Fill it with anaerobic
   retaining compound and push it onto the spline. The compound cures in the tooth valleys
   and *becomes* the female spline: fifteen keys formed by the very part they mate with, so
   they fit by construction. One drilled feature, on a part already being turned.

   | | |
   |---|---|
   | adhesive shear | 6.79 MPa against 17 MPa — **2.50×**, computed as if the socket were smooth |
   | the fifteen cast keys | 29.9 MPa of bearing if they carried it all — **deliberately not counted** |
   | shaft wall in torsion | 15.7 MPa — 10.2× in 6061-T6 |
   | reservoir | 0.30 mm past the engagement, so the blind hole does not hydraulic-lock |
   | serviceable | releases at ~250 °C — the reason for a retaining compound rather than epoxy |

   Allowable **only** because the coupling carries torque and no moment: the bearing sits
   outboard and takes all 0.806 N·m of panel bending, and this joint sees 0.520 N·m of servo
   stall. An adhesive in a bending path would be a bad idea. This is not one. Cut in CAD by
   `scripts/make_spline_socket.py`; `cad/canard_articulation.fs` gained `canardSplineSocket`.
   **Prime the bore** — 6061 is a passive metal and anaerobics need an activator on it.

22. **The shafts were modelled in stainless steel, and every document said 6061-T6.** The
   CAD carried "300 Series Stainless Steel" — 7850 against 2700, **5.86 g a shaft instead
   of 1.90** — while docs/04, docs/05 and an explicit instruction all said aluminium. Only
   a passing remark in `design/materials.py` agreed with the CAD, and it was never a
   decision. Settled on **6061-T6**: better margin (8.0× against 7.0× on sleeve bending),
   15.4 g lighter across four shafts at nearly the module's full radius on the roll axis,
   and far easier to cut a 1.8 mm tang and a 0.95 mm socket wall into.

   **How it hid for months is the transferable part.** Nothing ever read the density back.
   The material was set from an Onshape *library* entry, and a library material returns its
   density as `0` through the metadata API — so an audit that reads part metadata sees
   nothing wrong. What found it was `scripts/make_spline_socket.py` predicting its own mass
   change from the model's OWN measured density rather than from a constant, and printing
   that density in passing. **A safety check that reads what is actually there, instead of
   asserting what it expects, finds things it was not looking for.** Custom materials are
   now used throughout for exactly this reason.

   It also very nearly cancelled the printed bay: +38.6 g of bay, −15.4 g of shaft, so the
   module total moved 276.999 → 299.776 g and looked unremarkable. **A total is a bad place
   to look for an error.**

23. **An interference audit found six modelling defects that every other check passed.**
   Asked to go through the details properly, the useful move turned out to be Onshape's own
   assembly **Check interference** — which the REST API does not expose (`/interferencecheck`
   404s) and which nothing in this project had ever run. It reported **17 interfering pairs**.
   All six causes were invisible to part count, to mass, to the `evaluate()` violations, and
   to the axis-aligned bounding box.

   | what | why it was invisible |
   |---|---|
   | **Tang modelled inside the tube wall**, ×4. Its 1.0 mm union overshoot started the blade at R 39.200 in a wall running 37.400 → 39.700 | the tang is unioned *into* the shaft, so the shaft's bounding box never changed |
   | **Collar boss buried in the tube**, ×4. A flat-ended boss on a *radial* axis has its rim at `hypot(reach, OD/2)`: reaching R 37.250 put it at **37.730**, inside a bore of 37.400 | max X was 37.250 and looked perfect. **Radius is not a coordinate a bounding box knows** |
   | **Retainer bar buried in the servo**, ×8, 20 mm³ each. The flange's inboard face is only exposed in two 3 mm bands off the case ends; a bar long enough to seat an M2 head overran them by 1.7 mm | nothing measured the bar against the case |
   | **Collar bore modelled AS-PRINTED** ⌀7.500 with a ⌀8.000 bearing inside it, ×4 | both numbers were individually right; the model was carrying a manufacturing intermediate |
   | **Bearing bore ⌀6.000 on a ⌀6.000 shaft** — the design's own 0.030 mm running clearance was never modelled | *"zero clearance is not an interference"* — this project's own lesson, repeated one part further out |
   | **Four ⌀12 spikes 22 mm long** through the airframe, from a half-applied rebuild | see below |

   Fixed: tang overshoot 1.0 → **0.4 mm** (now a parameter, not a constant); collar boss stops
   at the shell **bore** plus 0.5 mm rather than reaching the OD; the retainer is a **dog bone**,
   2.6 mm across the flange and 4.7 mm at the screws; the collar bore carries the **as-reamed**
   ⌀8.000; the bearing bore is **⌀6.030**. **Check interference now reports none, across all 34
   instances.** `design/bay.py` grew a collar-rim check on RADIUS and a bridge-vs-case check, so
   none of these can come back silently.

   **The shaft's own bending was also being checked in only one place.** The spline socket makes
   the shaft hollow *inside the bearing*, and `hinge_loads()` checked the solid section at the
   tube wall on the strength of a comment. `shaft_stations()` now checks both, integrating the
   bearing reaction to get the real internal moment: tube wall 34.4 MPa (8.0×) still governs
   against the socket end's 23.0 MPa (12.0×) — **but at about 4.5 mm of socket depth it stops
   governing**, and nothing would have said so.

24. **Three Onshape workflow facts that cost the most time, recorded so they cost it once.**
   - **A feature's Feature Studio namespace is IMMUTABLE.** Editing new FeatureScript into an
     existing feature is refused with *"Feature does not match"* — with and without
     `serializationVersion`, with `rejectMicroversionSkew` both ways, and with no microversion
     at all. New source can only reach a feature by **deleting and re-adding** it.
   - **Rebuilding a Part Studio orphans every assembly instance of it.** Onshape *heals* the
     orphan to an **empty `partId`**: it keeps its name and its transform, still lists in the
     tree, contributes no mass and no geometry, and puts any rigid group holding it into ERROR.
     There is **no instance-delete route on the API**, so the cleanup is manual. Hence the rule
     now enforced by `make_bay_cad.py`: **finish a Part Studio before putting it in an assembly.**
   - **Adding a parameter to a custom feature silently defaults it on existing instances.** A
     half-applied rebuild left `collarOverlap` at Onshape's spec default of **25 mm**; the studio
     regenerated `OK`, kept its part count and its part names, and grew four ⌀12 spikes 22 mm
     long straight out through the airframe. Only the volume check caught it — which is why
     `verify()` compares volume against `design/bay.py` rather than counting parts.

25. **The aft gas seal was never a seal, and the hole in it is what sized it.** `docs/05`
   carried "a bulkhead between this module and the recovery bay, sealing a bore this part
   deliberately leaves open for wiring. Never sized" for six months. Read that and the part
   sounds like a gasket — something whose requirement is gas tightness. It is the **piston
   the ejection charge pushes on to separate the airframe**, and then the **anchor the main
   parachute pulls on when it opens**. Gas tightness is its third requirement. Same error as
   correction 2 and correction 11: **a part named after its smallest load, and then sized
   against the number in its name.**

   The load case that governs is not the nominal flight. A 1.17 g charge sized on the
   compartment's geometric volume, released into the **15% of that volume the parachute
   leaves free** with the joint not yet moving, is **1642 kPa and 7213 N** — seven times the
   design pressure. That is the stuck-joint case, and it sizes the disc for a reason that is
   not caution: **the shear pins are the intended fuse, so the bulkhead has to be stronger
   than the fuse**, or the wrong part fails first. It costs two sheet sizes and 23 g.

   **The feed-through governs, not the plate.** At 4.0 mm the disc passes at 2.8× and the
   wire hole fails at 1.70×. The part is 4.8 mm because of the feature it is *named for*,
   and a bulkhead sized as though it were a bulkhead is not a sized feed-through.

   Three modelling choices, each nearly made the comfortable way, and the first two are the
   transferable part:
   - **Simply supported, not clamped.** A bonded disc is between them and they differ by
     1.6×; assuming the fillet into the answer is how correction 15's joint reported 2.5×
     while sitting at 1.69×.
   - **The hole is placed on one model and checked against the other.** R 22.6 mm is where a
     *clamped* plate's radial stress passes through zero; a *simply supported* plate has no
     such radius. The first version of this used the clamped field for both and printed
     **15×** where the honest number is 2.45×. **Using the favourable model where it helps
     and the conservative one where it does not is not conservatism, it is a bug**, and it
     is worth more attention than any single margin here.
   - **Kt 2.0, not 3.0.** 3.0 is a hole in a plate under *in-plane tension*; this plate is in
     *bending*, where the thin-plate value is about 1.8. Being wrongly conservative is not
     free — at 3.0 the disc goes to 6.4 mm to buy a margin against a stress that is not there.

   **This correction also got the vent path wrong, and correction 28 fixes it.** The
   original argument ran: the module has two faces it could breathe through, it must not be
   the aft one because that is where the charge fires, so it vents *forward* into the nav
   bay and therefore joins the altimeter's static volume. Every step is sound and the
   premise is false — see correction 28. It is left here rather than edited away because
   the reasoning is the interesting part.

   Three things it opened, all now closed: the **drogue's firing circuit** (a ⌀5 mm bonded
   conduit through the main compartment, priced in `recovery.py`), the **internal bulkhead**
   (correction 29), and the **venting** (correction 28).

26. **The BOM and the mass budget disagree by exactly one dual-deploy altimeter.** Found by
   asking a question that had nothing to do with structures — *where does the custom PCB
   go?* `docs/04` §5 lists nine avionics lines totalling **620 g**, including a 60 g
   commercial altimeter. `mass.py`'s `DEFAULT_AVIONICS_BUDGET` lists nine lines totalling
   **560 g**, and the missing one is that altimeter. Every other line agrees to the gram.

   It is not a rounding difference and the altimeter is not optional: it is the independent
   commercial part that fires the charges, it is what the seal in correction 25 is wired to,
   and flying deployment off the custom PCB alone is a different safety argument than the
   one these documents make. **APPLIED Aug 2026** — not treated like correction 20, because
   that one proposes *deleting* a contingency somebody might want and this one is a required
   part the vehicle carries whether or not the budget admits it. Leaving it out does not make
   the rocket lighter.

   | | before | after |
   |---|---|---|
   | dry / wet mass | 5.487 / 6.111 kg | **5.553 / 6.177 kg** |
   | dry CG | 0.800 m | 0.795 m (forward — the altimeter lands ahead of it) |
   | static margin | 2.04–2.53 cal | **2.10–2.58 cal** |
   | P(SM < 1.0) | 0.43% | **0.30%** |
   | apogee | 1376 m | **1358 m** |
   | max Mach | 0.530 | 0.524 |
   | one-sided crossrange at 8° | 419 m | **393 m** |

   Still feasible, no violations, and the stability numbers all move the *right* way. The
   one claim it did break is in `docs/00` §D6 and `docs/02`: **J449BS ranks 11th on
   crossrange among motors passing every constraint, not 9th.** The selection does not
   change — it was never made on crossrange rank — but the sentence was, and now says 11th.

   The transferable part is where it came from. Nothing in this repo cross-checks
   `docs/04` against `design/mass.py`; they are two lists maintained by hand, which is the
   exact condition that produced correction 4. **A question from outside the analysis found
   it in one minute, and no check inside the analysis would ever have.**

27. **The nav bay has never had a packing check, and the first one says it does not fit.**
   `nav_bay_cal = 1.6` was typed at the same time as `recovery_bay_cal = 4.5` and by the same
   hand. The recovery bay got `check_packing()` and an 11 mm scare; the nav bay got nothing,
   for a year, while it quietly became the answer to "where does the custom PCB go".

   `design/avionics.py` is that check. **152 mm of sled wanted against 103 mm available**;
   117 mm with the tracker and radio moved to the nose.

   **The modelling point is worth more than the verdict.** The obvious check — add up
   component volumes, compare against the bay's — gives 150 cm³ in 558 cm³ and says the bay
   is two-thirds empty. It is the wrong check. Boards mount on the two faces of a flat sled,
   and a flat sled in a round tube can only use the rectangle inscribed in the circle: at a
   60 mm sled the usable height is 44.9 mm, not 74.8, and nothing reaches the four corners.
   **The binding quantity is footprint on two faces, and the volume is real but is not the
   constraint.** Same class as reading the hinge moment and concluding a 9 g servo is enough.

   **Do not lengthen the bay on the strength of this.** Every envelope in it is an estimate
   for a part nobody has chosen, which is correction 5's exact configuration — an
   estimate-driven shortfall, acted on, that turned out not to be in the hardware. So it is
   an `evaluate()` **warning** and not a violation: `feasible` stays YES, and the warning
   prints at the top of `scripts/baseline.py` where it cannot be missed. A new field on
   `Evaluation`, because "the vehicle cannot fly" and "the vehicle as *estimated* has a
   problem" are different claims and the model had only one channel for them.

   In order of what it costs: **close D7 and measure** (nine datasheets, and the only thing
   that settles it); **move the tracker and radio to the nose**, worth 35 mm and no frozen
   geometry — and where a tracker belongs anyway, since its job is to still be working when
   nothing else is; **one end closure instead of two**, worth 12 mm if the nose shoulder or
   the canard module's forward face already does the job; **lengthen the nav bay** to 2.0 cal,
   +32 mm, which touches every number in §1 and is therefore last.

28. **A bay is a cylinder, and the third surface is the wall.** Correction 25 argued that the
   canard module has "exactly two faces it could breathe through", that the aft one is
   disqualified because the ejection charge fires there, and that the module therefore vents
   forward into the nav bay — joining the altimeter's static volume, and making a leak past
   the aft seal a pressure-sensor fault rather than a soot problem.

   Every step of that follows. The premise does not: the module vents **overboard through
   its own wall**, like every other bay in high-power rocketry, and that wall already has
   four ⌀8 mm bores through it. Two ⌀2 mm holes cost nothing and the whole chain goes away —
   the sense volume is the nav bay alone, the wiring pass-through gets **potted solid**
   rather than having to pass air, and a leak past the seal goes outside.

   **The framing failed, not any number.** *"It has two faces and one of them is
   disqualified"* is a complete-sounding argument that silently excluded the answer, and
   nothing inside it was ever going to catch that. Correction 1 is the same shape: the servo
   was assumed to point inward and every conclusion after that was sound.

   `design/venting.py` owns this, and it found one more thing by being written. It was built
   to size the static ports against **lag** — a bay that lags on the way down fires the main
   below the 200 m it was set for, which is the failure with no margin under it. **Lag does
   not size these holes, by a factor of about 300.** The model asks for 1.35 mm² and
   convention drills 24.1. So the ports are set by blockage tolerance, by the ejection
   transient, and by what a person can drill and deburr by hand — none of which is modelled
   — and *"the bay must breathe fast enough"*, which is the reason everybody gives for these
   holes, is not the reason. A check that confirms is its own kind of result.

29. **`recovery.FILL_LIMIT` sets the design pressure of every bulkhead in the rocket.**
   Sizing the internal bulkhead should have been a second, easier pass of correction 25's
   model. It was, and it printed something neither part's geometry explains: **both
   bulkheads see the same stuck-joint pressure**, 1668 and 1689 kPa, though one closes a
   1042 cm³ compartment and the other a 429 cm³ one.

   `check_packing()` gives every compartment the length its contents need *at the fill
   limit*, so every compartment leaves the same free fraction — 1 − 0.85 — whatever is in it.
   The charge scales with the geometric volume and the free volume scales with it too, and
   the ratio cancels. **The drogue compartment holds a quarter of the volume and is 1%
   worse.**

   So `FILL_LIMIT = 0.85`, chosen as a packing convenience — *"a bay packed to 100% is a bay
   that will not close on the launch rail with cold hands"* — is a **structural** parameter
   and nothing said so. Pack to 0.90 instead and every bulkhead load rises 50%, to 2502 kPa.
   `check_seal()` prints that sensitivity on every run.

   Two things about the part itself. It is the **only pressure boundary in the vehicle with
   no fuse**: the aft seal is protected by shear pins that go first by design, while this one
   is bonded into the tube at both ends of its load path, so a joint that sticks simply hands
   it the whole charge. For it the stuck case is not a contingency, it is the only case. And
   its **assembled stack is 10.8 mm against the 12.0 mm `BULKHEAD_THICKNESS` allowance** —
   which fits, and which was a typed number nothing had ever compared against a part.

30. **The tracker and the radio moved to the nose, and the nose turned out to be the one
   volume whose width is a function of station.** Correction 27 left the nav bay 49 mm short
   and listed four ways out. This is the second of them and the only one that costs nothing
   structural: **the telemetry radio and the independent GPS tracker now ride in the nose**,
   on the same threaded rod as the ballast, 20 mm behind it.

   It is not a packing dodge. It is where a tracker belongs. Its whole job is to still be
   working when nothing else is, which argues for its own battery in its own compartment as
   far from the servo bus as the airframe allows — and the nose is the best RF position on
   the vehicle, because the shoulder region is the one place a fibreglass airframe stops
   shielding an antenna. Both parts are RF and neither needs a short wire to the flight
   computer.

   **Checking it needed a new kind of check.** Every bay so far could be verified against
   one diameter. A cone cannot: the sled is only as wide as its *narrowest* end allows, so
   the answer is a band rather than a number, and the sled wants to sit as far aft as
   possible where the cone is fullest. `NoseCone.radius_at()` is the tangent-ogive profile
   — ρ = (R² + L²)/2R — and `check_nose_packing()` walks forward from the base until there
   is enough two-sided sled area. **35.4 mm of sled at station 282–318 mm, 59.1 mm wide.**

   | | before | after |
   |---|---|---|
   | nav bay sled wanted | 152 mm | **117 mm**, against 103 available |
   | 105 g of avionics at | station 381 mm | **station 300 mm** |
   | static margin | 2.10–2.58 cal | 2.11–2.60 cal |
   | P(SM < 1.0) | 0.30% | **0.20%** |
   | crossrange | 393 m | 390 m |

   `design/mass.py` now splits the avionics budget between two stations rather than
   averaging it, because this function's own comment records that putting a subsystem in the
   wrong bay is worth about a quarter caliber of static margin.

   **AND THE CHECK TURNED UP SOMETHING BIGGER THAN THE SHORTFALL IT WAS RUN FOR.** The nose
   **shoulder is not modelled anywhere**. `docs/04` carries a 1 caliber — 79 mm — shoulder
   on a 127 mm nav bay, and a shoulder inserts *into* the tube it joins. Which tube's length
   it spends has never been decided, and **the two answers are 79 mm apart**: if the sled
   must sit aft of it the bay is short by ~80 mm rather than 14, and if the sled runs up
   inside it — which is how many high-power av-bays are actually built — the bay gains most
   of that 79 mm and fits with room to spare. `avionics.py` assumes neither; it charges a
   plain end closure at both ends, which is the arrangement nobody has drawn. **The 14 mm is
   the smallest open question about this bay, not the largest one.**

31. **A coupler is a tube, and what is inside it is still bay.** Correction 30 left the nose
   shoulder as the largest open question about the nav bay: `docs/04` carries a 1 caliber —
   79.4 mm — shoulder on a 127 mm bay, and nobody had decided which tube's length it spent.
   The two readings were **79 mm apart**, and the bad one made the bay short by ~80 mm.

   **Both readings were wrong, because the question had a false premise.** A shoulder is a
   hollow tube. So is a coupler. Neither consumes bay *length* — what each costs is local
   *diameter* over its span, `74.8 − 2 × 2.3 = 70.2 mm`. What costs length is a **bulkhead**,
   and bulkheads were already being counted. *"Which bay does the shoulder's length come out
   of"* is a complete-sounding question with two false answers, which is correction 28 one
   joint further forward.

   `design/joints.py` now models **all four joints**, because the shoulder turned out to be
   one instance of something general and because `tube_section.py` has carried *"the
   tube-to-tube joints either side of the module — couplers are a mass line in `mass.py` and
   nothing more"* since it was written. Each joint's **kind is now a stated decision** —
   which ones come apart, and on what — rather than something everyone assumed they knew.

   | bay | tube | usable | bore |
   |---|---|---|---|
   | nav bay | 127.0 mm | **115.0 mm** | 74.8 (70.2 over 79 mm) |
   | canard module | 142.9 mm | 130.9 mm | 74.8 (70.2 over 79 mm) |
   | recovery bay | 357.3 mm | 357.3 mm | 74.8 (70.2 over 79 mm) |
   | booster | 416.3 mm | 404.3 mm | 74.8 (70.2 over 79 mm) |

   For the nav bay it went the good way: one bulkhead instead of two (the forward closure
   belongs to the nose module), so +12 mm of length against −3.6 mm of sled width, and the
   shortfall goes **14 → 9 mm**.

   **For the recovery bay it went the other way, and this is the part to act on.** A sled is
   rigid and takes the narrow bore as its width; a *parachute packs*, so for it the narrowed
   bore is a **volume** penalty. `BayBudget.equivalent_length` restates the bay as the
   full-bore cylinder of the same volume — 357.3 → **347.8 mm** — and the margin goes
   **+6.8 → +0.1 mm.** That is not a pass, it is a coincidence. The sensitivities:

   | change | margin moves |
   |---|---|
   | fill limit 0.85 → 0.87 | +7.7 mm |
   | fill limit 0.85 → 0.82 | **−12.1 mm** |
   | coupler engagement 1.0 → 0.75 cal | +2.5 mm |
   | internal bulkhead 12 → 10 mm | +2.1 mm |

   **Pack the real canopy and measure it.** `recovery.py` has said since it was written that
   this is the only thing that settles the packing, and it has now stopped being advice.

   One number moved on the way past, and it moved *because* it was wrong rather than
   conservative: the U-bolt envelope was **6.0 cm³, and that was a bounding box** — a
   25 × 20 × 12 mm block describing a wire loop with a hole in the middle that the harness
   threads through. Rod plus backing plate is 3.0 cm³. Correction 23's lesson in another
   costume, and worth 2.7 mm of a bay that has 0.1.

32. **The nose is the instrumentation module, and the point of one is that it comes off.**
   Correction 30 put the tracker and the radio in the nose to fix a packing problem. Keeping
   them there on purpose is a different decision, and it is the right one: after GV-2 has
   measured the control derivatives the campaign stops needing telemetry, and the same nose
   can carry a payload instead.

   **Self-contained is a requirement with numbers, not an aspiration.** Three things decide
   it and the third is the one nobody expects:

   - **Its own battery.** The tracker already has one — an "independent" tracker sharing the
     flight computer's battery is not independent. The radio needs one too, or the module is
     a subassembly on the end of a power lead.
   - **One electrical interface.** The tracker needs nothing from the vehicle; the radio
     needs flight data, which is one connector at the joint. A payload that needs nothing
     leaves it unmated.
   - **Its mass is part of the stability solution.** 105 g at station 300 mm sits forward of
     the 794 mm CG, so it is doing the nose ballast's job.

   | nose payload | SM min | SM max | |
   |---|---|---|---|
   | 0 g | 1.99 | 2.48 | ok |
   | 105 g | 2.11 | 2.60 | the instrumentation |
   | 300 g | 2.33 | 2.82 | ok |
   | 500 g | 2.53 | 3.02 | over-stable, SM > 3.0 |

   **Up to about 300 g goes in with no other change**, and past that the vehicle goes
   *over*-stable rather than unstable — it weathercocks and gives up crossrange, a
   performance loss and not a safety one. The nose ballast trims either way. Room: **469 cm³**
   between station 200 mm (clear of the ballast) and the nose base, of which the
   instrumentation uses 155 cm³.

   **The one drawback, stated rather than buried:** the GNSS antenna stays in the nav bay at
   the forward end of its sled, under the shoulder — `configure.py` puts the nav bay forward
   for exactly that reason. A dense payload sitting directly ahead of it is between that
   antenna and the sky. Nothing in this project models RF; if the payload is metallic, check
   the fix on the ground before the flight.

33. **Nothing had ever sized the harness, and it was twenty times stronger than the load.**
   Correction 31 left the recovery bay at **+0.1 mm** — not a pass, a coincidence — and the
   obvious levers were all bad ones: shave the fill limit, shorten the coupler, lengthen a
   frozen airframe. The margin came from somewhere else entirely.

   **The harness is a quarter of the bay's volume and nobody had ever looked at it.** Its
   volume came from `shock_cord_and_links = 0.220 kg` in the mass budget divided by an
   assumed bulk density — an unchecked number turned into a volume by a guess. Its
   *strength* came from nowhere at all: nothing in this project had ever compared a harness
   to a load, though the harness carries every newton of the opening shock and its failure
   loses the vehicle and all its data.

   The opening shock is **1.32 kN** (`seal.opening_shock`, already computed for the U-bolt,
   and already the infinite-mass bound). 1" tubular nylon is rated **17.8 kN**.

   | webbing | rating | after knots | vs shock | g/m |
   |---|---|---|---|---|
   | 1/2" tubular nylon | 4.4 kN | 2.2 kN | 1.7× | 11 |
   | 9/16" tubular nylon | 6.7 kN | 3.3 kN | 2.5× | 14 |
   | **3/4" tubular nylon** | **11.1 kN** | **5.6 kN** | **4.2×** | **20** |
   | 1" tubular nylon | 17.8 kN | 8.9 kN | 6.7× | 30 |

   **The knot derating is what moves the selection, not the rating.** A knot costs roughly
   half the rated strength; without that factor the answer is two sizes smaller and wrong.

   2 × 3.40 m of 3/4" is **136 g against the 170 g the budget assumed**, and the bay goes
   **+0.1 → +17.8 mm**. `mass.py` now carries 0.186 kg as a *result*, and `evaluate()`
   re-derives it every run and warns if the constant drifts from the sized part — because
   the packing check and the mass budget reading different numbers is how this started.

   The internal bulkhead helped too, for the same kind of reason: it is the **measured
   10.8 mm** stack from `design/seal.py` — a 4.8 mm disc with a 3 mm fillet each face — and
   not the 12.0 mm allowance for a bulkhead nobody had designed. Correction 20's shape.

   **Kevlar was the obvious answer and it is the wrong one.** It packs smaller and survives
   the ejection gas, but it does not stretch: nylon takes 20–30% elongation and absorbs the
   shock, Kevlar transmits it, and this project has no model of harness elasticity — so
   switching would raise the very load (`seal.opening_shock`) that nothing here could then
   recompute. A Kevlar *leader* at the charge end is the standard way to get the heat
   resistance without the stiffness.

   **The general lesson is the one this project keeps re-learning from the other end.** The
   tube at the hinge station runs at 256× and that was free. This ran at 20× and it was
   not — it was spending a bay whose margin was 0.1 mm. **An unchecked number that turns out
   enormous is not automatically good news; ask what it is costing.**

34. **The bulkheads are built, and the interference check that passed does not prove what
   it looks like it proves.** `design/seal.py` sized both discs in August 2026 and neither
   had ever been drawn — which is the condition correction 11 and correction 18 both warn
   about: *a part that is not modelled cannot collide with anything.*

   Built: **Aft gas seal** (⌀74.8 × 4.8 G-10, 2 × ⌀4.0 feed-through, 2 × ⌀5.5 U-bolt) and
   **Recovery internal bulkhead** (same disc, 1 × ⌀6.0 conduit hole). Volumes verified
   against the analytic disc-less-holes to **0.000 mm³** — the only proof the holes actually
   cut, since a solid disc and a drilled one differ by 1.7% of mass and no tolerance-based
   check would ever notice. The seal is instanced in `Assembly 1` at Z = 142.900, the
   module's aft face, read from the Part Studio's bounding box rather than typed.

   **Check interference reports none, across all 35 instances.** And here is the caveat:
   **the disc is ⌀74.8 in a ⌀74.8 bore, so it could not have reported one.** This project's
   own rule — *zero clearance is not an interference* (corrections 10 and 18) — applies to
   its own newest part. The clean result says nothing about the seal against the tube; what
   it does say is that the seal does not foul the printed bay, the retainer bars or the
   servos, which is what it was run for. **The bond line is a fit allowance, not geometry**,
   and modelling it would make the disc read as loose in every future clash check — the same
   reasoning `make_bearing_cad.py` uses for its nominal ⌀8.000.

   Two bookkeeping points, both of which would have been wrong if left implicit:
   - **The seal is deliberately NOT in `CANARD_MODULE_CAD`.** It is a structure part,
     budgeted with every other bulkhead in `couplers_bulkheads`, and folding it into the
     canard module's measured tensor without taking it out of that line would count 38 g
     twice — invisibly, because `estimate_inertia` removes a measured component's mass from
     the bulk and adds it back, so a double count shows up as an inertia error and never as
     a mass one. `verify_cad.py` subtracts the seal from the assembly before comparing, and
     recovers the module tensor to zero delta.
   - **`Bulkhead.mass` was the solid disc.** The CAD reads 38.377 g against the model's
     39.022 g, because the model never subtracted the holes. `drilled_mass` does, and the
     two now agree to the milligram. 1.7% is small; two numbers for one part is not.

   The internal bulkhead is **built but not assembled**, and that is the honest state: it
   sits 240 mm aft in a recovery bay nothing has modelled, and a part placed where it is not
   is worse than a part that is missing, because it looks finished.

35. **D7 is closed, the packaging argument for it was wrong, and the gyro nearly was too.**
   Three architectures priced against the nav bay: a Teensy plus breakouts, an Altus Metrum
   TeleMega plus a guidance board, and a custom STM32 board. **Selected: the custom board for
   the guided vehicle, staged behind a breakout stack that flies the cert flights.**

   **The reason is a career one and this is written down as such.** The stated goal is to
   show defense employers hardware capability, and a board taken from requirements through
   layout, bring-up and flight is a far stronger artifact than a soldered protoboard — STM32
   especially, since it is what ArduPilot and PX4 run on. That is a legitimate input to a
   capstone decision. It is not an engineering justification, and **the engineering argument
   people reach for does not survive the numbers**: a custom board is *not* the small one.

   | | sled needed | margin |
   |---|---|---|
   | A. Dev board + breakouts | 107.1 mm | +7.9 mm |
   | B. TeleMega + guidance board | 109.6 mm | +5.5 mm |
   | C. Custom STM32 board | 110.4 mm | +4.6 mm |

   The breakouts are postage stamps and a Teensy is 17.8 mm wide, so **option C needs more
   sled than option A.** Packaging does not select the architecture here, and pretending it
   did would have been the comfortable version of this decision.

   **Staged, because the schedule lands somewhere expensive.** Step 6 flies the avionics as a
   passive logger in the L1 and L2 certs; those launches are monthly and weather-dependent,
   and eight weeks of board work spends them for nothing. A breakout stack exists in a week
   and **every line of the interesting software is identical** — filter, HIL, controller and
   safety logic do not care what the sensors are soldered to. It also becomes the HIL target
   and the reference implementation, which is what makes board bring-up tractable.

   **THE NAV BAY WARNING DISSOLVED, and the cause is one line item.** The guessed "flight
   computer PCB" was 70 × 40 mm = 28.0 cm² against a real Teensy 4.1 at 61 × 17.8 = 10.9 cm².
   Two and a half times the part. **Correction 5 replaying, and it vindicates not having
   lengthened the airframe** — an estimate-driven shortfall, nearly acted on, that was not in
   the hardware. Twice now. Two envelopes moved the other way and are recorded so it does not
   read as good news only: the StratoLoggerCF is larger than guessed, and a GNSS patch
   antenna is bigger than the receiver behind it.

   **And one derived requirement is genuinely tight.** `board_requirements()` computes the
   electrical spec from the flight model rather than from a tutorial, and steady roll rate at
   8° of canard is ~~**1783 °/s — 89% of a ±2000 °/s gyro's full scale**~~ — **THIS FIGURE IS
   WRONG AND CORRECTION 36(d) SUPERSEDES IT.** 1783 °/s is the 6° rate printed under an 8°
   heading; the true figure at the limit is **2378 °/s, which SATURATES a ±2000 dps part.**
   Left in place rather than edited, because the shape of the error is the lesson and the
   conclusion below survives it — the conclusion is in fact stronger. **A saturated rate gyro
   in a roll loop is not a degraded measurement, it is a wrong one, and the controller cannot
   tell.** No tutorial produces that requirement; it would have been found in flight. Fix it
   twice over, both free: cap the roll command (roll needs far less deflection than pitch —
   `baseline.py` already says so; correction 36 makes this **mandatory**, not one option of
   two) and pick an IMU with the range, which is a datasheet line that costs nothing *before*
   layout.

36. **D8 is closed, and every one of its findings is free before layout and unrecoverable
   after.** `docs/07-state-estimation.md`, `design/estimation.py`,
   `scripts/estimation_trade.py`. The decision is **IMU + baro + GNSS + magnetometer, with
   the estimator staged by guidance level** — D7 staged the hardware, D8 cannot, because
   every sensor has to be on the schematic at once. Four things came out of it:

   **(a) The accelerometer gate this document prescribed passes its worst data.** Step 4.2
   said "gated on acceleration magnitude so boost does not corrupt attitude." It does reject
   boost. Then it **opens at burnout** — 1.06 g at t = 2.85 s — and stays open 1.1 s, and
   what it admits is **drag along the body axis, not gravity**. A coasting rocket is in free
   fall; the only specific force on it is aerodynamic and it lies along the body axis, so the
   filter is handed a body-axis vector labelled "down" at exactly the moment the guidance
   loop opens. The heuristic is from multirotor AHRS work where a vehicle really does sit at
   1 g. **This vehicle never sees gravity again after rail exit.** Step 4.2 below is
   corrected. Same shape as corrections 1 and 28: a rule that sounds complete and silently
   admits the wrong answer.

   **(b) The IMU sample rate is not the control loop rate, and it is ten times higher.**
   `board_requirements()` derived 86 Hz from the pitch mode and a reader builds 100 Hz. But
   attitude is *propagated*: first-order quaternion propagation rotates by 2·atan(ω·dt/2),
   not ω·dt, and the shortfall is cubic in the step. At 100 Hz and the roll rate the
   deflection limit allows, that is **33.3 °/s of drift with a perfect gyro** — more than the
   entire sensor error budget, from arithmetic. 1 kHz brings it to 0.34 °/s. It sets the SPI
   clock and the DMA, so it is fixed at layout.

   **(c) Roll angle was observed by nothing on the board D7 selected.** Specific force is
   invariant under rotation about the axis it lies along, so the accelerometer cannot see
   roll; the GNSS velocity vector says where the nose points, not how the vehicle is clocked
   about it. **L1 — hold roll angle — is the minimum success criterion.** Step 4.2 had
   *already assumed* a magnetometer; `STM32_BOARD` did not have one, and nothing had checked.
   **The document and the hardware had disagreed for as long as both existed.** A
   magnetometer is ~$5 and one I2C address before layout. Applied.

   **(d) And the gyro requirement in correction 35 was computed at the wrong deflection.**
   Steady roll rate is **linear** in deflection, and the project was using three values:
   594 °/s at the 2° roll cap, 1783 °/s at `evaluate()`'s 6° default, 2378 °/s at the 8°
   deflection limit. `docs/06` printed the 6° answer under an 8° heading — so the real figure
   at the limit is **119% of a ±2000 dps part, saturated, not the comfortable 89%**. **The
   error and the reassurance came from the same place.** The corrected statement: a ±2000 dps
   gyro is adequate *only because the roll command is capped at 2°*, which makes the cap
   load-bearing for the sensor and not merely a control convenience. `DEFLECTION_LIMIT_DEG`
   and `ROLL_COMMAND_CAP_DEG` now live in `design/configure.py` and `Evaluation` records the
   deflection it was evaluated at. **This is correction 4 recurring** — a constant that lives
   in a script drifts from the document that quotes it.

   The pattern is the result: **four requirements in a row that no tutorial would produce,
   all of them sensing requirements, all of them set at layout.** That is the argument for
   closing D8 before the schematic rather than during firmware.

37. **The vents went in; the pass-through could not, because its plate does not exist.**
   Two jobs were queued as "the last CAD in the canard module". The first is done: the
   module's 2 × ⌀2.0 mm overboard vents are cut at **Z 120.0 mm, clocked 45° / 225°**
   (`design/venting.py`, `scripts/make_module_vents.py`). Two things are worth keeping from
   how they were placed and how they were checked.

   **The station was chosen by the LEAK PATH, not by the flow field.** Two bands of module
   wall have nothing bonded behind them, forward of the printed bay and aft of it.
   `seal.py`'s stated intent is that a leak past the aft gas seal *"goes overboard instead
   of into the sensor that fires the charges"* — and for that to be true the gas has to
   **reach** a vent. Vent only the forward band and the escape path for hot, sooty ejection
   gas runs the full length of the module, across four servos and every wire in the
   vehicle. Vent the aft band and it is a couple of centimetres of empty tube. **The seal's
   argument was written as though the module had a vent somewhere; *where* turned out to be
   load-bearing for it**, and the two parts were designed a month apart. Note also that the
   Cp rule which governs the nav bay's static ports does not govern this bay at all — it
   feeds no sensor — which is why this could be settled without the panel-method model
   `venting.py` correctly says the project does not have.

   **And the first cut was wrong in a way only geometry could catch.** It regenerated with
   featureStatus OK, kept the part count, and passed the mass guard — while sitting at
   **Z 68.270 instead of Z 120.000**, because the sketch it was copied from pins its circle
   with a `DISTANCE` constraint and the constraint solved the geometry straight back. Two
   ⌀2 mm holes are **26.7 mg**, far inside every mass tolerance in `verify_cad.py`, so
   *no mass or count check in this project could ever have found it*. `verify_holes()` now
   reads the two cylindrical faces back out of the model and checks diameter, station and
   clocking on every run. **A check whose resolution is coarser than the thing it is
   checking is not a weak check, it is not a check.** (An angled datum plane failed the
   same way and was caught the same way: `cPlane` with `angle` set regenerates OK and comes
   back with its normal unrotated. The 45° plane is the MID_PLANE of Front and Right, whose
   bisector contains the rocket axis by construction.)

   **The second job is blocked, and that is the finding.** The forward wiring pass-through
   has been *decided* since correction 28 — a wire route, potted solid. It cannot be drawn
   because **the plate it passes through has never been sized.** `design/joints.py` puts a
   bulkhead on all four joints; `design/seal.py` sizes the two *separation* ones and, as of
   this correction, says out loud that it sizes neither *access* one — **the nav bay /
   canard module plate that carries this pass-through, and the nose's aft face that a
   300 g payload would hang from.** Both already consume bay length in `joints.budgets()`.
   So they are **priced as allowances while not existing as parts**, which is correction
   20's shape and correction 33's harness again, and the reason nobody noticed is that
   `seal.py`'s "what this does not do" list named only the booster's bulkhead — **an
   incomplete exclusion list reads as coverage.**

39. **The hinge mates were in, correct, regenerating OK — and frozen solid, because of
   their own ±8° limit.** Every attempt to animate one returned *"Unable to compute any
   steps for this animation. Unable to apply transform. Instance(s) may be constrained."*
   Everything the message points at was fine: all 36 instances are in exactly one rigid
   group each and the groups do not overlap, only the tube is fixed (correctly — it is
   ground), both mate connectors resolve to the right parts, all nine features report OK.

   **On these mates a limit does not clamp the rotation, it abolishes it.** Driving the
   mate through `POST /matevalues` after each edit: limits off, +5° asked and +5.000° got;
   limits on at ±8°, ±60°, ±360° or 80…100°, every one **0.000°**. So it is not the width
   of the limit and not a pose outside it — a limit that would allow a full revolution
   freezes the hinge exactly as hard as ±8° does. Nor is it the rigid groups: suppressing
   the rotating group changes nothing.

   **Nothing was authored wrong.** Onshape's own mate dialog reads and writes
   `limitAxialZMin/Max` for a revolute's rotation limits, which is where the ±8° sat. The
   other Z pair, `limitZMin/Max`, is drivable with limits enabled and **enforces nothing**
   (driven to +12° against a ±8° limit), so moving the number there would have produced a
   ticked Limits box over a limit that does not exist — this project's most-repeated
   failure, one part further out. Fixed by turning the mate limits **off**:
   `scripts/fix_hinge_mate_limits.py`, `--verify` drives all four and parks them at zero.
   Mass and CoM unchanged to the microgram across the write, which is how you know only
   limits moved.

   The transferable part is not the parameter. It is that **the CAD had a working
   mechanism and a check that said so, and neither was true.** `Assembly 1` was recorded
   here as "a mechanism and not just a pose" from the day the mates went in, on the
   strength of the mates existing, mass not moving, and every feature reporting OK — the
   same three signals that were satisfied by the `Hinge Plane` datum driving no geometry
   (correction 4's era) and by the circular pattern silently dropping materials. **Nobody
   had ever turned it.** The one check that finds this class of defect is the one that
   makes the thing do its job: drive the mate and read back what moved, which is now what
   `--verify` does and what no amount of tree-reading would have shown.

Still TBD and only you can close them: C1 (cert held), C3 (budget), C4 (calendar), C6 (fab
access), the cert milestone dates in §2.1, and D1/D9. **D7 and D8 are both closed** —
corrections 35 and 36.

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
2. **State estimation.** **D8 is closed and it corrected this paragraph — read
   `docs/07-state-estimation.md` before writing any of it.** An attitude filter that survives
   9 g of axial acceleration and high angular rates. Quaternion state propagated at **≥ 1 kHz
   — not the 86 Hz control loop rate**, because at 100 Hz the propagation arithmetic alone
   drifts 33 °/s at this vehicle's roll rate. **Gate the corrections on FLIGHT PHASE, never
   on acceleration magnitude.** This paragraph used to say "gated on acceleration magnitude
   so boost does not corrupt attitude", and that gate opens at burnout and admits drag along
   the body axis as if it were gravity — a ballistic vehicle never sees gravity after rail
   exit, so **the accelerometer is a pad-alignment sensor and an event detector and nothing
   else**. In flight the aiding is the **magnetometer** (roll angle — the only sensor that
   observes it) and the **GNSS velocity vector** (pitch/yaw, under small α, which is what
   static margin buys you). This is still where most of your interesting engineering lives.
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
