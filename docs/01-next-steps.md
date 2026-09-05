# Ordered plan

## State of play — September 2026

Read this first if you are picking the project back up.

- **STEP 3'S CAD IS BUILT — the whole vehicle is now real geometry, and building it found
  six defects (Sep 2026, correction 56).** The three queued generators were finally RUN.
  Booster tube + four aft fins at the derived **11.15 mm** tab, the **motor mount** (forward
  bulkhead, mount tube, two centering rings, motor envelope) and the **recovery hardware**
  (4 U-bolts, 4 backing plates, 2 charge wells) are all built and verified against their
  analytic volumes, most at **delta +0.0000**. Interference **12 pairs → 5**.
  **One geometric fact caused three of the six: the fin tab is a TRAPEZOID, not a
  rectangle** — `fin_profile()` ramps it from the root LE to full depth over 6 mm, and both
  the forward centering ring and the tube's own slots were placed as if it began at the
  6 mm station. Fixed by naming the two datums apart (`fin_tab_forward` for the bond,
  `fin_tab_material_forward` for clearance, `SLOT_INSET_MM = 0.0`). Also fixed: the internal
  bulkhead had **one** U-bolt hole pair where correction 54's own comment called for two at
  90°; both bulkheads still carried **⌀5.5** holes after correction 54 took them to ⌀8.5;
  `make_sled_fusion.py`'s bore check had excluded airframe bodies by name and never learned
  about correction 42's `aft coupler`, so it failed a bonded part for not fitting through a
  bore; and a **duplicate orphan fin** (`DiagFin`, 100% coincident with `AftFin0`) was
  deleted. **No vehicle number moves** — feasible, apogee 1270.8 m, dry 5.886 kg.
  **Both real defects are now closed (correction 57) and the CAD is interference-free**:
  the ballast rod has a tapped hole, and the booster anchor's fastener stack is derived per
  anchor -- no washer, low-profile all-metal nut -- fitting the motor's 11.08 mm gap with
  0.58 mm spare, with the check that compares them finally existing. The two superseded
  context bodies are gone and `NoseAftFace` is placed. **Interference is 1 pair at
  1.1936 mm3, which is 1.6 microns of radial overlap** where the nose plate seats into the
  shoulder bore -- two parts that are meant to touch.
- **THE CONTROL ARCHITECTURE WAS RE-OPENED AND SURVIVED — AND ONE SENSOR LINE ITEM NOW HAS
  A DEADLINE (Sep 2026, correction 55).** Asked whether the vehicle could fly sharp,
  precomputed direction changes instead of one slow biased curve, three alternative
  architectures were evaluated and **all three lost to the bank-to-turn design already
  built**: canted fins + spin-and-pulse (its spin rate is a *decaying schedule* that sweeps
  the **4.1 Hz pitch mode**, and a direction change costs half a revolution — 0.25 s early
  but **1.64 s** late), a freewheeling tail (removes **86%** of the vehicle's roll damping,
  and is a passive substitute for an active roll loop this vehicle already has), and
  cold-gas/jet vanes (blocked outright — hardware in a certified motor's exhaust).
  **`ROLL_COMMAND_CAP_DEG = 2.0` costs a factor of four in roll rate, and correction 55
  concluded a wider gyro should buy it back. CORRECTION 58 REVERSED THAT** — running
  `attitude_error_budget()` gives **7.94° capped against 62.89° uncapped**, because the roll
  rate that saturates the gyro is the same one that drives the dominant error term (scale
  factor at roll rate). L1 is *hold roll angle*, so uncapping breaks the thing it was meant
  to enable. At layout: specify **selectable** FS to ±4000 dps and **run at ±2000** — the
  option is free, the capability is not. The real lever is scale-factor **calibration**
  (0.5% spec limit vs ~0.05–0.1% measured). Correction 55's original gap here — that
  `attitude_error_budget()` had **no magnetometer term at all**, so the aided number that
  decides whether the cap can ever move did not exist — **is CLOSED by correction 59**:
  aided, the same 7.94°/31.45° unaided pair becomes **0.08°/0.12°**, and what now actually
  limits roll angle is the airframe's own magnetic cleanliness (an 18.0 mgauss budget
  against one servo lead's 40), not the sensor or the gyro range. Also corrected on the way past:
  the vehicle does not respond sluggishly (pitch quarter-period is **60–68 ms** across every
  geometry tried) — "slow curve" is a lateral-g magnitude problem, not a bandwidth one, so
  the authority/altitude menu in correction 55 is the knob, and **it is left open, not
  taken: `configure.py` still carries 0.85/1.55.** Every number in that correction is from a
  throwaway probe rather than a checked-in script, and all of it sits downstream of the
  unmeasured `Cl_delta`.
- **STEP 3'S DIMENSIONED DRAWING IS CLOSED (Sep 2026, corrections 53 and 54).** The two
  genuinely unsized items — the motor mount, and the recovery bay's U-bolt / backing plate /
  charge well — are both sized, checked, in `baseline.py`, and drawn.
  `design/motor_mount.py` + `docs/09-motor-mount.md`; `design/recovery_hardware.py` +
  `docs/10-recovery-hardware.md`. **Nothing in this vehicle is an allowance any more.**
  Between them they turned up four things worth knowing before anything else is built:
  - **The frozen 12 mm aft-fin tab and a 54 mm motor mount tube cannot both exist.** The tab
    is measured from the booster's OUTER radius, so its tip sat at R 27.70 — 0.85 mm inside
    any mount tube a 54 mm motor can have, and 0.70 mm off the bare motor case, which is what
    the round number was really drawn against. It is **11.15 mm** and derived now. **The four
    `AftFin` bodies and the four booster tab slots must be rebuilt in Fusion.**
  - **The Pro54's own forward-closure ejection charge fires into a sealed 25.9 cm³** between
    the motor and the booster's forward bulkhead — 10.2 MPa against a disc that lets go at
    6.69, and it fails at every plausible charge mass. **Buy the plugged forward closure.**
    Nothing in this project had ever asked what happens to the motor's own charge.
  - **The M5 U-bolt `seal.py` assumed does not carry its own load.** Its aside checked the
    LEGS in SHEAR; the legs are in tension and the CROWN is what bends. **M8**, and the
    ⌀5.5 holes already placed in both bulkheads become ⌀8.5.
  - **The 3/4" harness does not pass through the U-bolt** (19.1 mm of webbing, 17.0 mm of
    opening). It was never meant to: the harness attaches through a **quick link**, which
    `recovery.py` has priced since it was written.
  Vehicle level, from 191 g of harness anchors `mass.py` had no line for at all: dry
  **5.68 → 5.89 kg**, apogee **1326 → 1271 m**, crossrange **340 → 297 m**, static margin
  **2.30–2.77 cal**, recovery bay margin **+8.35 → +4.63 mm**. No requirement moves out of
  bounds. **What is left is CAD execution, not design:** the two Fusion generators are
  written and their emitted scripts verified offline, and running them in Fusion — with the
  fin rebuild first — is the remaining step.
- **CAD moved from Onshape to Fusion, and full-module migration is DONE (Sep 2026).**
  Everything below this bullet through the end of "State of play" predates that move and
  is Onshape-only history — read it for the ENGINEERING content (the hinge, the joints,
  the loads all still apply), not for which CAD tool to open. `CanardControlModule` in
  Fusion now holds the tube, 4 panels, 4 shafts, the printed bay, 4 servos, 4 bearings,
  the aft gas seal and the pass-through plate as native, from-scratch, regeneratable
  geometry (eight generator scripts under `scripts/*_fusion.py`, each deriving every
  dimension from `design/*.py`, same discipline as the Onshape scripts below), all
  correctly placed, interference-clean at rest AND driven through 0°/±4°/±8° deflection,
  genuinely ARTICULATING on 8 native `AsBuiltJoint`s — and **`Onshape_reference` (the STEP
  import) and the old hand-built 28-body rebuild are both DELETED from the live document.**
  Full blow-by-blow in **corrections 44–50** at the bottom of this file (M0 plumbing/
  joint-API spike, M1 bay, M2 servo+bearing, M3 tube/panel/shaft, M4 placement+
  interference, M5 joints, M6 cutover) — read correction 44 first for the architecture and
  milestone list, then whichever of 45–50 you need. Onshape's `canard-control module`
  document is untouched and still the thing the *rest* of this file's Onshape-era
  corrections describe — it is history now, not a live dependency of anything that moves.
- **The recovery bay has a tube now, and its internal bulkhead is finally assembled, not
  just drawn (Sep 2026, correction 51).** `scripts/make_recovery_bay_cad_fusion.py` builds
  `RecoveryBayTube` (357.3 mm, the same OD/ID as the canard module's own tube) directly
  aft of the canard module in the same `CanardControlModule` document — Z 142.92 → 500.22,
  continuing from the aft gas seal's own aft face — and moves the already-built
  `RecoveryInternalBulkhead` (correction 50) from its unplaced local origin to its real
  station, read off `evaluate().packing`'s own main/drogue compartment lengths rather than
  assumed: main compartment forward (229.50 mm), the bulkhead centred in its 10.8 mm
  allowance band, drogue compartment aft (89.72 mm), 27.3 mm of slack left at the tube's
  own aft face for the recovery-bay/booster joint's coupler. Interference-clean against the
  tube, the aft gas seal, and the canard module's own tube. **Still open, and not drawable
  yet**: the U-bolt, backing plate and charge well — none of the three has ever been SIZED
  by anything in this project, Onshape included, so drawing them now would be inventing a
  design decision rather than recording one.
- **The booster tube and all four aft fins are drawn (Sep 2026, correction 52) — the
  vehicle is modelled nose to tail in Fusion for the first time.** Correction 51 assumed
  the booster + aft fins had no design-side sizing at all; checking before drawing found
  that was wrong — the planform (`aft_root_cal`/`aft_semispan_cal`/`aft_sweep_cal`/
  `aft_taper`, `design/configure.py`) and the root attachment (a 12 mm through-wall tab,
  already baked into `scripts/make_cad_profiles.py`'s `fin_profile()`) were both already
  decided, just never built as 3D geometry. `scripts/make_aft_fin_cad_fusion.py` builds
  `BoosterTube` (continuing directly from `RecoveryBayTube`'s own aft face) and
  `AftFin0`-`AftFin3`, clocked 45/135/225/315° (interdigitated 45° off the canards, a
  number this project had only ever stated in prose until now). Interference-clean
  everywhere: tube-to-tube, fin-to-tube, and every fin pair, all exactly 0.0000 mm³. Found
  and fixed a real Fusion API gotcha along the way — renaming a Sketch/Extrude-sourced body
  inside the same script transaction does not reliably persist, even into a fresh empty
  component; `scripts/fusion_common.py`'s shared `_inject()` now renames after
  `finishEdit()` via a fresh query instead. **Only the motor mount (never sized by
  anything, Onshape included) and the recovery bay's U-bolt/backing-plate/charge-well
  (correction 51) are what's left of Step 3's dimensioned-drawing deliverable.**
- **Steps 0, 1, 2 are closed.** Sizing tool built, range access and certification path
  resolved, OpenRocket cross-check done and agreeing (CNa to 0.3%, CP to 0.17 cal).
- **Step 3 is closed** (corrections 53 and 54; see the top bullet). The airframe is frozen
  in `design/configure.py` — that file
  is the single source of truth for the vehicle and every script imports from it. The BOM
  is drafted (`04-bill-of-materials.md`). **The dimensioned drawing now covers the whole
  vehicle except the motor mount and the recovery bay's U-bolt/backing-plate/charge-well**
  (both genuinely unsized, not just undrawn) — CAD work in Fusion (`CanardControlModule`),
  see the two bullets above; do not go looking for any of it in Onshape.
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
- **The recovery bay margin is fixed, and the harness is why** (correction 33). It went to
  **+17.8 mm**, and is **+8.4 mm** now that correction 42 made the joints pay for both of
  their halves. The fix was not to shave anything: **nothing in this project had
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
- **The nav bay sled is a part now, and drawing it found three things** (correction 41).
  `design/sled.py`, `scripts/sled_report.py`, `scripts/make_sled_fusion.py`, verdict in
  `baseline.py`, full write-up in `docs/08-nav-bay-sled.md`. The sled was the fourth
  allowance in this project to be priced without existing: `mass.py` has charged **150 g**
  for `sled_and_hardware` since that dict was written and `avionics.SLED_WIDTH_FRACTION`
  set its width, for a part nobody had drawn. It is **G-10 plate 109.04 x 59.41 x 1.6 mm,
  two end brackets, two M4 rods, 101.6 g** against that 150 g, in Fusion as `NavBay` at
  Z -127.04 -> -12.00 with the nav bay tube, the nose shoulder and the nose plate drawn
  around it. Three findings, and the first is the one that matters:
  - **0.80 OF THE BORE IS TOO NARROW TO CARRY THE WIRING THE SAME FILE CHARGES FOR.**
    `avionics.check_packing()` is an **areal** model -- footprint summed and divided by
    `2 x sled_width x 0.70` -- and it reports the bay FITS by +4.6 mm. Place the same stack
    as **real rectangles on two faces** (exhaustive over face assignment and 0/90
    orientation, exact within a face, so a negative is a proof and not a search that gave
    up) and the four boards fit fine, but the **80 g wiring loom then has nowhere to go**:
    no 70 x 20 mm rectangle left on either face, and the corner crescents would need it at
    **1.82 g/cm3** against copper's 8.96 and PVC's 1.4. The plate has to reach **59 mm**.
    An areal model cannot see this because it only ever sees the product -- it cannot tell
    a plate 2.84 mm too narrow from one that is wide enough. `configure.py` now passes the
    real sled width into `check_packing()` instead of the 0.80 fallback, and the areal
    margin goes **+4.6 -> +10.7 mm** as a *result* of the part improving, not as a retune.
  - **THE MOUNT AS FIRST DRAWN DID NOT HOLD ANYTHING.** Rods beside the plate, in its own
    plane, is what a side-view sketch gives and it is wrong in three dimensions: a nut on
    an axial rod clamps axially, and a plate in that rod's plane offers nothing but its
    1.6 mm edge for a washer to bear on. Ears around the rods do not help -- the rod runs
    the whole bay, so clearing it removes every scrap of ear at that radius. Pairwise
    interference said it in one line: **47.31 mm3 of plate inside each rod.** The capture
    has to be **perpendicular** to the rod -- an end bracket, a bulkhead in miniature -- and
    once it is, the rods can move off the plate's plane, where they stop competing with its
    width and can come inboard to **R 30.00**, taking the hole ligament from **-0.05 mm to
    2.55 mm** in the bracket and from 2.55 to **5.15 mm** in the two end plates, which
    matters more because those are pressure boundaries. The rods were also **12 mm too
    short** -- drawn the length of the sled instead of the length of the bay, so a "simply
    supported" sled was supported at one end by nothing.
  - **TWO MOUNTING SCREWS COLLIDED AND NOTHING SAW IT UNTIL THE VOLUME DID.** The BEC's and
    the altimeter's corner screws landed exactly on top of each other at one corner and
    1.30 mm apart at another -- two holes 1.30 mm apart are one ragged slot. Found because
    the CAD came back **+10.7519 mm3** against the analytic figure and the two overlaps
    accounted for it to the last hundredth. Colliding holes now merge into shared
    through-holes with a standoff each side.
  **STILL OPEN AND STATED RATHER THAN SOLVED:** the loom result has a second reading --
  the 80 g is a `mass.py` line called `wiring_connectors`, connectors are not loom, and the
  servo and pyro leads both run AFT out of this bay -- so **nothing was resized and
  `avionics.py`'s model was not edited** (correction 5's discipline). Weighing the loom and
  counting its conductors settles it and has never been done. Also open: **battery and loom
  retention is not drawn** -- 1.00 mm of clear plate beside the battery against the ~3 mm a
  cable-tie slot needs, so the two heaviest items on the sled are held by nothing that
  exists yet. Interference is **zero pairs involving any sled body** across 861, and
  **0.0000 mm3 of the sled lies outside the 70.20 mm shoulder bore** -- the "does it slide
  past the nose shoulder" check no script in this repo had ever performed. Three stale
  strings fixed on the way past: `avionics_report.py` hardcoded "STILL SHORT BY 14 mm"
  **directly under its own computed FITS verdict**, `avionics.py`'s docstring worked its
  example at a sled width the model never produces, and `docs/04` section 5 still said
  9 mm short. Next in this bay: the nav bay's static ports still have **no station and no
  clocking** anywhere in the repo.
- **The nav bay's static ports are placed, and placing them found that the nav bay has no
  bare wall** (correction 42). `design/ports.py`, `scripts/port_report.py`, verdict in
  `baseline.py`, and it is built and interference-checked in Fusion. **3 × ⌀3.2 mm at
  station 420.82 mm, clocked 15/135/255°, 4.60 mm deep**, through the airframe tube *and
  the bonded aft coupler together*, because that band is the only drillable wall
  there is: the nose shoulder takes the forward caliber and that joint comes apart. The cause
  is that **`joints.py` described a joint only by the half that PROTRUDES**, so nothing could
  ask whether a bay had room for the anchored half — and **two 1.0 cal joints do not fit in a
  1.60 cal tube.** `anchor` is a field now and `check_joints()` is the check; the nav bay is
  exactly full, and **the canard module failed it by 15.88 mm — resolved same-session,
  correction 42's second half** (below): both of its joints are bounded by the printed
  bay sitting mid-tube, not by convention, and fit with 43.9 mm spare once derived from
  the bay's own footprint. One number moved elsewhere: the recovery bay's packing margin
  **+17.8 → +8.4 mm**, because `bay_budget` was taking the `max` of a bay's two narrowed
  spans instead of their sum. Four findings, and the two worth carrying are that **neither
  conventional placement rule can be met and it costs about a metre** (the error is only
  ever read where q is small), and that **the port-count argument came out backwards from
  the first guess** — four ports is the more accurate ring and three is the forgiving one,
  because a 4-port ring's clocking is load-bearing against a four-canard vehicle's own
  field and a 3-port ring's is not.
- **The hinge mechanism actually articulates in CAD now, and the nose cone is drawn for the
  first time** (correction 43). Neither was true before this session: the canard hinges had
  mates in Onshape (correction 39) but nothing equivalent existed in the Fusion document,
  and the nose cone had never been more than the parametric shape `aero`/`mass`/`avionics`
  read numbers off. Fixed together, in Fusion, and verified rather than assumed:
  - **Four AS-BUILT joints** (one rigid panel-to-shaft bond, one revolute shaft-to-tube
    hinge, per canard) connect the STEP-imported reference assembly's own components — an
    as-built joint freezes the current position and never snaps geometry to align, which
    matters here because nothing but the STEP import's own accuracy holds these parts
    together. Driven to 8° and screenshotted before being trusted, then reset to 0° — the
    same rule this project has applied to every mate since correction 39: a joint that
    "added successfully" and one that actually turns are different claims.
  - **The nose cone is a real part**: the ogive shell (piecewise-frustum revolve, 150
    segments, verified against an independent 20000-step numerical integration to 0.0007%)
    plus its integral shoulder — the same material `design/joints.py`'s nose/nav-bay joint
    already priced from the nav bay's side, now drawn from the nose's own side instead of
    left as an anonymous annular placeholder. Found in the process: **the wetted-area mass
    estimate `design/mass.py` had used since before this project's history began was ~113 g
    light** — it approximates a thin constant-thickness shell reasonably for the ogive
    (~180 g estimate against ~216 g real) but never counted the shoulder at all (~77 g).
    `design/mass.py` now prices the nose cone from the real drawn volume.
  - **The adjustable ballast provision also has real hardware for the first time**:
    `design/nose_module.py` sizes an M6 rod and a 25×6.5 mm steel washer stack to the
    design-point 100 g (docs/00 §7.1) — a mass and a station existed for this since D10
    closed; a rod diameter and a washer size did not. The rod itself is genuinely new mass
    (33.6 g) that nothing had ever charged for, the same shape as the sled's rods, the
    U-bolts, and every other "priced but not drawn" gap this project keeps finding.
  - **The vehicle got heavier and MORE stable, not less**: +156 g total, almost all of it
    forward of the CG, moves static margin **2.11–2.60 → 2.27–2.76 cal** and P(SM<1.0)
    **0.2% → 0.1%** — at the cost of apogee (1369 → 1326 m) and crossrange (400 → 340 m).
    Nothing was retuned to get this; it fell out of the mass model becoming honest. See
    `scripts/baseline.py` and `scripts/robustness.py` for the regenerated figures.
  - A performance regression was caught, not shipped: the first version of the new nose
    mass calculation ran a 4000-step integration inside `evaluate()`, which every optimizer
    in this project calls thousands of times per run. Measured before committing to it —
    `evaluate()` cost ~300 ms regardless of step count, an existing cost this change did not
    create — and the step count was still cut to 200 on the general principle that a hot
    loop should not carry unneeded weight. See `design/nose_module.py`'s
    `shell_volume_and_centroid` docstring for the numbers.
- **Asked whether Step 4 (firmware) was really next, the honest answer was no.** By the end
  of correction 52 the whole vehicle has real CAD, nose to aft fins, in one document. **What
  is left standing between here and Step 3's own deliverable, "a dimensioned drawing"
  covering the whole vehicle, is two genuinely unsized items, not undrawn ones**: the
  recovery bay's U-bolt/backing-plate/charge-well and the booster's motor mount — neither
  has ever been sized by anything in this project, Onshape included, so neither is a CAD
  task until it is a design decision. Step 4 is still next in the sense that
  D8 settled what it is built from, but calling it "next" before Step 3's drawing covers the
  whole vehicle was premature, and correction 43 exists because that got questioned rather
  than assumed.

Current vehicle: 79.4 mm OD fiberglass, 1361 mm, canards 0.85 cal / aft fins 1.55 cal
interdigitated 45°, **both sets swept 35.4°**, Cesaroni J449 Blue Streak, 4× KST X08 Plus
servos flat-mounted with the hinge at 0.20 of MAC, 100 g nose ballast. Canards 67.5 root /
27.0 tip (0.40 taper). **6.30 kg wet, apogee 1326 m, Mach 0.513, static margin
2.27–2.76 cal, P(SM<1.0) 0.1%, 340 m crossrange.** (Mass +156 g and margin up since Sep
2026 correction 43, when the nose cone was finally drawn and its real volume — including
the integral shoulder, never counted before — replaced a wetted-area estimate.) Telemetry
radio and GPS tracker ride in
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

Fifty-eight corrections are worth knowing about — 38's, 40's and 41's own numbered entries are
still only the bullets above. The first four changed the design; two of the
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

   *(347.8 mm was itself too generous, and correction 42 says why: this bay is sleeved at
   BOTH ends and `bay_budget` was taking the `max` of its two narrowed spans rather than
   their sum, because until `anchor` existed at most one of them was ever non-zero. It is
   338.4 mm now.)*

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
   **+0.1 → +17.8 mm** (and to **+8.4 mm** at correction 42, which is still the harness's
   margin and not a new problem). `mass.py` now carries 0.186 kg as a *result*, and `evaluate()`
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

42. **The nav bay's static ports could not be placed until something else was found, and
   what was found is that the nav bay has no bare wall.** Three ⌀3.2 mm holes were the last
   open CAD item in this bay, and `docs/08` closed with the note that they *"need a decision
   rather than a script"*. They needed a script, because the first question a hole asks is
   not "where is the pressure right" — it is **what is behind the wall**.

   | | |
   |---|---|
   | nav bay tube | 127.04 mm, 1.60 cal |
   | nose shoulder engaged into it | 79.40 mm, 1.00 cal |
   | left for the aft coupler's bonded half | **47.64 mm, 0.600 cal** |
   | what the same 1.0 cal convention wants | 79.40 mm — **31.76 mm short** |

   **Two 1.0 cal joints do not fit in a 1.6 cal bay.** Nothing had ever said so, and the
   reason is structural rather than a slip: `design/joints.py` described a joint only by the
   half that PROTRUDES — `engagement` and `into` — because the question it was written to
   settle (correction 31) was whether an inserted tube costs the bay it protrudes into any
   length. It does not, and that answer still stands. But every coupler also has an
   **anchored** half bonded into the other tube, and that half was not a field, so no check
   could ask whether the bay had room for it. It is the fifth allowance in this project that
   nobody turned into a part — except that this one was never even an allowance.

   `anchor` is that field now, `check_joints()` is the check, and the nav bay's aft anchor is
   **derived** from what the nose shoulder leaves rather than typed, so it cannot quietly
   stop fitting if `nav_bay_cal` moves. `narrowed_span` now counts both halves, and
   `bay_budget` **sums** them instead of taking their `max` — which was harmless only while
   at most one half per bay was non-zero. That is the one number this correction moved
   anywhere else: **the recovery bay's packing margin goes +17.8 → +8.4 mm.** It still fits,
   and it was applied rather than merely reported, because leaving half of every joint out of
   the bore model is the identical defect to leaving it out of the length model.

   **The canard module fails the same check by 15.88 mm, and it is RESOLVED the same
   session, the same way.** Its forward joint is worse than the raw check can even see: the
   protrusion would have run 79.40 mm into a printed canard bay whose own structure starts
   at module Z 53.129 (the potted pass-through plate holds Z 0.000–2.400 ahead of it) — a
   coupler driven straight through the part that carries the hinge bearings. The fix is the
   nav bay's, one joint further aft: `design/bay.py` gains `printed_bay_from_evaluation()`
   and `joint_room()`, which read the printed bay's own `forward_face`/`aft_face`
   (53.129 / 94.629 mm) and hand `design/joints.py` the real room —

   | | convention charges | real room |
   |---|---|---|
   | forward joint's engagement (into canard module) | 79.40 mm | **50.729 mm** |
   | aft joint's anchor (into canard module) | 79.40 mm | **48.291 mm** |
   | sum against the 142.92 mm tube | 158.80 mm | **99.02 mm, 43.9 mm spare** |

   `design/joints.py`'s `for_rocket()`/`budgets()`/`tube_capacity()`/`check_joints()` all
   take the two figures as optional floats (`canard_forward_room`, `canard_aft_room`,
   `None` falling back to convention) — the same shape as `nav_bay_length` above, and kept
   dependency-light on purpose: building the printed bay needs a servo choice
   (`hinge.selected`, `hinge.canard_hinge_station`), and `design/configure.py`'s
   `evaluate()` — called on every optimizer/sweep iteration — never reads the canard
   module's own budget, only the recovery bay's, so it must not pay for that build. Only
   `scripts/baseline.py` and `scripts/port_report.py`, the two places a human reads
   `check_joints()`'s verdict, needed threading. **Both joints are still below the 1.0 cal
   convention** — that does not change, and nothing in this project sizes a coupler in
   bending, so it stays an explicit open note. What changed is that the tube is not
   physically over-subscribed: it was only ever under-served by a convention it could not
   have met in 142.92 mm either way. `check_joints()` now reports `OK` with three "below
   convention, open" notes instead of a violation.

   **THE PORTS: 3 × ⌀3.2 mm at station 420.82 mm, clocked 15/135/255°, 4.60 mm deep**,
   through the airframe tube **and the bonded aft coupler together**. That band is the only
   drillable wall in the bay — the forward band is the nose shoulder, and that joint comes
   apart, so a hole through both walls would have to re-align on every assembly and the
   annulus between them would be a leak path the altimeter senses through. Drilling through
   tube + coupler is not a workaround: the classic high-power av-bay **is** a coupler with
   its ports drilled through it, and it only looked like one here because this vehicle's
   av-bay is a full-diameter tube, so the doubled wall arrives from the joint instead.
   `design/ports.py`, `scripts/port_report.py`, verdict in `baseline.py`.

   Three more things came out of it, and the first two are the ones worth carrying:

   - **NEITHER CONVENTIONAL PLACEMENT RULE CAN BE MET, AND IT COSTS ABOUT A METRE.** "At
     least 2 cal aft of the nose shoulder" and "at least 1 cal forward of the next
     disturbance" are both unreachable — the nav bay is 1.6 cal long and it is sandwiched
     between the nose junction and the canards, so the best available is **1.30 cal and
     0.78 cal**. So the violation was priced instead of avoided. A validated slender-body
     solution (it is run against the exact answer for a 4:1 prolate spheroid, where it
     under-reads |Cp| by 17%, and that factor is applied) gives **Cp −0.0176** at the chosen
     station. And the answer is that **it does not matter, because position error scales with
     q and the altimeter is only ever read where q is small**: 28.7 m at max q, **0.69 m at
     the main's 200 m under drogue**, zero at apogee. The station is therefore set by edge
     distance in the bonded band, not by aerodynamics — the ring is centred, 23.82 mm each
     side against a 4.80 mm floor, and moving it to the aft end would buy 0.12 m and spend
     all of that. Same shape as `venting.py`'s own result on port SIZE.
   - **THE PORT COUNT ARGUMENT CAME OUT BACKWARDS FROM THE FIRST GUESS, AND THE FIRST GUESS
     IS THE INSTRUCTIVE PART.** A ring of N ports feeds one plenum, so the altimeter reads
     the mean, and the mean over N equally spaced samples kills every circumferential
     harmonic that is not a multiple of N. "Three and four are coprime, so a 3-port ring
     averages the canards' 4-fold field and a 4-port ring cannot" is *true* and points at the
     wrong answer, because **the 4-fold roll field is the small one**. A lateral command is
     odd-harmonic and 170× larger, and four ports reject all of it while three pass its
     k = 3. Worst case over every lateral command azimuth, at max q: one port 4.216 m,
     **three ports 0.265 m at any phasing**, four ports 0.000 m on the canard planes or their
     bisectors and 0.024 m anywhere else. **On the aerodynamics four ports is the better
     ring.** What the sweep actually settles is the clocking: **a 4-port ring's clocking is
     load-bearing and a 3-port ring's is not** — with a 4-fold field every port on a 4-port
     ring sits at the same phase of it, so the ring does not average it, it reads it. Three
     is the *forgiving* choice rather than the accurate one, which is a better reason for it
     than the one `venting.py` had written down, and it is the same thing every other number
     in that file is chosen for. **The count did not change.** With one port taped over —
     the failure the 3.2 mm diameter is really sized against — three degrade to 2.315 m and
     four to 1.522 m at max q, and both are under 0.07 m at deployment.
   - **THE ORIFICE EQUATION IN `venting.py` IS THE WRONG MODEL, AND THE CONCLUSION IS
     UNCHANGED.** `VentedBay.lag()` puts the bay behind a sharp-edged orifice at Cd 0.62,
     which is an inertial model valid above about Re 10⁴. The real port runs at **Re = 67**
     at the worst flow in the whole flight: laminar, linear in velocity, and 4.60 mm deep
     through a 3.2 mm hole, which is a short pipe and not a thin plate. Both are computed —
     0.153 Pa against 0.081 Pa, into a 35.1 Pa budget — so nothing moves, by a factor of 230.
     Recorded because "the model is invalid and the conclusion is unchanged" is a result, and
     because the next marginal vent needs to know which equation to reach for.

   Also asked for the first time, and it is correction 10's shape applied to a void instead
   of to a shaft: **can air actually reach the hole from inside.** An interference check
   cannot answer it — a mouth 0.2 mm off the face of a board is not an interference, it is a
   bay that does not breathe. `ports.port_mouth_clearances()` measures each port's inner
   mouth against everything the sled puts in that cross-section: **7.89 mm at worst**, to the
   −Y rod.

   Four stale strings fixed on the way past, all in `venting.py`'s own header and all the
   same cause — a free volume typed once while the component list under it kept moving:
   303 cm³ → **359**, "4 holes of 0.65" → **0.71**, "eighteen times the area" → **fifteen**,
   "three hundred times the margin" → **230**. None of them changed a conclusion, which is
   exactly why nobody caught them.

   **THE CAD IS BUILT AND VERIFIED.** `scripts/make_sled_fusion.py` now emits the aft coupler
   and cuts the three ports through both walls; the Fusion document `CanardControlModule` holds
   **15 bodies**, **Check interference reports none across all 105 pairs**, and the port mouths
   measure **9.29 / 11.02 / 7.89 mm** to the nearest sled solid — the same three numbers, to
   the hundredth, and the same three nearest parts, that `ports.port_mouth_clearances()`
   predicts analytically. It also fixes a regression this same correction introduced: the
   generator drew the nose shoulder from `bay.narrow_span`, which now sums both halves, so it
   would have drawn a 127 mm shoulder in a 127 mm bay.

   **AND BUILDING IT FOUND THAT THE CHECK ITSELF HAS A RESOLUTION NOBODY HAD MEASURED.** The
   expected volumes come from `ports.drilled_volume()` — the exact figure for a radial hole
   through a curved wall, +0.02% on πr²t, and 0.0040 mm³ per hole is forty times what the
   four-decimal check resolves. It is right: it agrees with a Monte Carlo integration to
   0.002 mm³. **Fusion's own volume of that hole is not, and it is wrong by clocking.** Asked
   for the same removed material by the two routes that must agree exactly — (body − cut body)
   and (body ∩ drill) — Fusion returns **+0.037/−0.017 mm³ at 15°, +0.000/+0.001 at 135°, and
   +0.048/+0.000 at 255°**. A hole on a 45° diagonal is exact and one at 15° is not; cutting
   three in sequence compounds it to 0.12 mm³ on the tube and 0.36 on the coupler. A flat
   plate with eleven holes and a plain annulus both still come back exact to five decimals, so
   this is specific to a *radial* hole through a *curved* wall. The volume tolerance on those
   two bodies is loosened to a **measured** 0.15 mm³ per port, and **the ports are now checked
   by FACE instead** — count the cylindrical faces at the port radius and read their axes back,
   which is exact and which tests what was actually asked for (right number, right size, right
   clocking) where a volume never did. Both bodies report 3 faces at ⌀3.2 on axes 15/75/135°
   (255° is 75° mod 180). This project has been trusting four-decimal volume agreement since
   correction 34; it is worth knowing where that stops working.

   **STILL OPEN, stated rather than solved:** all three of the canard module's coupled
   joints are below the 1.0 cal convention (0.600 cal nav-bay-side anchor, 0.639 cal
   forward engagement, 0.608 cal aft anchor) and **nothing in this project sizes a coupler
   in bending** — the capacity fits (43.9 mm spare), only the convention does not; the same
   joint's **retaining screws want the same 47.64 mm band the ports are in**, and no script
   here has ever placed one; the boundary layer, which is a position error of the same order
   as the one that was modelled and the wrong sign to guess at; and the ejection transient,
   which is the one flow case where this port really is inertial.

43. **Asked to keep going, the honest next step was not Step 4 — it was checking whether
   Step 3 was actually done.** It was not: only the nav bay and canard module have ever had
   real CAD, and Step 3's own deliverable is "a dimensioned drawing" of the whole airframe.
   Picked the nose cone to close next, and closing it found three things.

   **The hinge mechanism now articulates in Fusion, not just in Onshape.** Correction 39
   closed the mates in Onshape; nothing equivalent existed in the Fusion document, where the
   canard panels and shafts (imported from Onshape's own STEP export, correction 40) were
   just floating, unconnected bodies. Four AS-BUILT joints per canard — a rigid one bonding
   panel to shaft, a revolute one hinging shaft to tube, axis read directly off the shaft's
   own cylindrical face — fix that. AS-BUILT rather than a regular joint on purpose: a
   regular joint snaps the second occurrence to align with the picked geometry, which risks
   displacing a part whose only claim to being correctly placed is the STEP import's own
   accuracy; an as-built joint freezes the current position and adds only the requested
   motion. Driven to 8° and screenshotted before being trusted, then reset to 0 — correction
   39's own rule, applied a second time: a joint that "added successfully" and one that
   turns are different claims. Confirmed with a full interference re-check across every
   real, visible body (53 bodies, 1378 pairs) — zero real overlap, the same bearing-seat
   tolerance slivers as before.

   **The nose cone is a real part, and drawing it found the mass model was wrong by more
   than rounding.** The ogive shell (piecewise-frustum revolve, 150 segments, agreeing with
   an independent 20000-step numerical integration to 0.0007%) plus its integral shoulder —
   the same material `design/joints.py`'s nose/nav-bay joint already priced from the nav
   bay's side (correction 42), drawn now from the nose's own side instead of left as an
   anonymous placeholder annulus inside `NavBay`. `design/mass.py` had priced the whole nose
   cone as `wetted_area * wall_thickness * material_density` since before this file's own
   history — a thin-shell approximation that is reasonable for the ogive alone (~180 g
   estimate against ~216 g real, the wetted-area correction factor not quite matching a true
   ogive) but **never charged for the shoulder at all** (~77 g). Same shape of gap as every
   other allowance this project has found by finally drawing the part, one joint further
   forward. `design/mass.py` now prices the nose cone from the real integrated volume.

   **The adjustable ballast provision got real hardware, and the hardware itself was
   another uncounted mass.** D10 closed with "an adjustable threaded rod and washer stack in
   the nose shoulder" (docs/00 §7.1) but no rod diameter or washer size existed anywhere.
   `design/nose_module.py` picks M6 — the smallest metric size with a common 25 mm OD
   washer, chosen because the room available (31.2 mm inner radius at the ballast station)
   doesn't bind, so there is no reason to pick a bigger rod than the smallest normal one —
   and derives the washer stack's length from its target mass rather than asserting one,
   the same shape as `seal.stack_length()`. The **rod's own mass, 33.6 g, had never been
   counted** — `nose_ballast_kg` has always priced only the adjustable washer stack, which
   `design/nose_module.py` deliberately leaves alone (changing what "100 g of ballast" means
   would ripple into every static-margin figure that already assumes it), so the rod is a
   new, separate mass line rather than a redefinition of the old one.

   **Net effect: +156 g, nearly all of it forward of the CG, and the vehicle got MORE
   stable, not less.** Static margin **2.11–2.60 → 2.27–2.76 cal**, P(SM<1.0) **0.2% →
   0.1%** (`scripts/robustness.py`), at the cost of apogee (1369 → 1326 m) and crossrange
   (400 → 340 m, `scripts/baseline.py`). Nothing was retuned to get this — it is what the
   mass model produces once it is honest, the same kind of result correction 41's sled
   width fix was.

   **One performance regression was caught before it shipped.** The first version of
   `design/nose_module.py`'s volume integration used 4000 steps and lives inside
   `build_mass()`, which `evaluate()` calls once and which every optimizer in this project
   (`robustness.py`, `sweep.py`, `motor_trade.py`) calls thousands of times. Measured rather
   than assumed: `evaluate()` costs ~300 ms with or without this file, at 200 steps or 4000
   — the cost is the flight simulation, not this integration, and this function was never
   the thing slowing anything down. The step count was still cut to 200 (agreeing with 4000
   to 0.00003%) on the general principle that a value read from a hot loop should not carry
   weight it does not need, not because 4000 was proven to matter. Full regression sweep —
   every report script plus `sweep.py`, `robustness.py`, `motor_trade.py` — run clean.

   **STILL OPEN as of this session:** the recovery bay (no tube modelled; the internal
   bulkhead is drawn as a part by `make_bulkhead_cad.py` but not assembled anywhere, and
   still missing its U-bolt, backing plate, and charge well) and the booster + aft fins
   (nothing drawn at all — no planform, no root attachment, no motor mount) are the rest of
   Step 3's own deliverable. Neither is this session's. **[Update, correction 51: the
   recovery bay now has a native Fusion tube and its bulkhead is assembled — the U-bolt/
   backing-plate/charge-well and the booster+aft-fins are what remains.]**

   **ALSO FLAGGED, DELIBERATELY DEFERRED:** the 8 hinge joints above live on
   `Onshape_reference` — the STEP file imported from Onshape — not on the native Fusion
   rebuild (the 28 loose bodies at the document root, hidden, geometrically identical per
   correction 40's own comparison). That is a real dependency on Onshape for the one thing
   in this Fusion document that moves, and it was raised and consciously left as-is rather
   than fixed. Two ways to close it, from cheapest to most complete:
     1. Split the native rebuild's existing bodies into components (Fusion's own "Create
        Components from Bodies") and re-point the same 8 joints at them. Removes the
        Onshape-import dependency for today's geometry; still a static snapshot, not
        regeneratable if the Onshape design changes again.
     2. Write Fusion-native generator scripts for the whole canard module (servo, bearing,
        hinge stack, printed bay, root tang, spline socket), driven directly from
        `design/*.py`, the same approach `scripts/make_sled_fusion.py` and the nose cone
        generator already use — full regeneratable parity with Onshape, no import ever
        needed. A large undertaking: it re-does most of the canard module's CAD history
        (`make_servo_cad.py`, `make_bearing_cad.py`, `make_bay_cad.py`, `make_root_tang.py`,
        `make_spline_socket.py`) on the Fusion side.
   Neither is done. Do this before trusting the mechanism against anything but a visual
   check, and before assuming Onshape can be dropped for this module.

44. **Correction 43's option 2 was chosen — full migration off Onshape for this module —
   and its two biggest unknowns are now retired.** Asked directly, rather than deferred
   again: yes, migrate fully, and yes, also regenerate the tube/4 panels/4 shafts from
   scratch rather than keep them as the hand-built snapshot in the hidden 28-body rebuild
   (its planform math already exists, `scripts/make_cad_profiles.py`'s `fin_profile()`/
   `mac()`, so this is a port, not new design). That makes the real undertaking **six**
   generator scripts, not five: `make_hinge_stack_fusion.py` (tube + 4 panels + 4 shafts,
   each its own Fusion component, tang-cut and spline-socket folded into the same
   per-quadrant pass since the generator already holds direct body references and doesn't
   need Onshape's `classifyCanardBodies()` workaround), `make_servo_cad_fusion.py`,
   `make_bearing_cad_fusion.py`, `make_bay_cad_fusion.py`, and — new, no precedent anywhere
   in this repo — `make_canard_joints_fusion.py`. A new `scripts/fusion_common.py` is also
   planned, since `make_sled_fusion.py` is currently the only Fusion-side code in the repo
   and duplicating its temp-BRep/BaseFeature/verify boilerplate six times would be exactly
   the kind of second source of truth this project's conventions exist to prevent.

   This is a multi-session build (a 7-milestone plan, M0–M6). **Only M0, a plumbing spike,
   is done this session** — no real canard geometry has been generated yet. It existed to
   answer two open questions before committing to writing any generator against them:

   - **How does a generated script actually run inside Fusion?** Confirmed:
     `mcp__fusion360__fusion_mcp_execute` (`featureType: "script"`) runs a Python
     `run(_context)` function directly against the ACTIVE document via the real Fusion API
     — it is not "print text and paste it into Fusion's script editor by hand," which is
     what `make_sled_fusion.py`'s `--write`-to-`out/` pattern would otherwise imply and
     which nothing in the repo had actually proven. A generator can call this tool with its
     emitted script text directly.
   - **Does Fusion's `AsBuiltJoint` API work the way correction 43 assumed?** Confirmed, on
     the first attempt, both joint types this module needs:
     `root.asBuiltJoints.createInput(occA, occB, geometry)` then either
     `.setAsRigidJointMotion()` (geometry=`None`) or
     `.setAsRevoluteJointMotion(adsk.fusion.JointDirections.ZAxisJointDirection)` with
     geometry = `adsk.fusion.JointGeometry.createByCylinderOrConeFace(cylFace,
     JointQuadrantAngleTypes.StartJointQuadrantAngleType, JointKeyPointTypes.MiddleKeyPoint)`
     — axis read directly off the shaft's own cylindrical face, exactly the technique
     correction 43 used by hand for the current joints — then `root.asBuiltJoints.add(input)`.
     Driving motion: `adsk.fusion.RevoluteJointMotion.cast(joint.jointMotion).rotationValue
     = math.radians(8.0)`, read back exact. Screenshotted at 8° (visible near the document's
     origin, next to the nose), then both joints and their four throwaway test components
     deleted (`joint.deleteMe()`, `occurrence.deleteMe()`) — `CanardControlModule` is left
     exactly as it was before this session, nothing real added or changed.

   **Next up is M1 — the bay shell, standalone-verified** (the largest of the six ports,
   currently a custom Onshape FeatureScript purely because of two Onshape-only
   limitations — boolean scope can't name bodies by bare ID, radial extrude needs a
   sketch-plane query — that don't exist against Fusion's temp-BRep API). Full milestone
   list (M1 bay, M2 servo+bearing, M3 tube+panels+shafts, M4 placement+interference sweep,
   M5 joints wired for real, M6 cutover deleting `Onshape_reference` and the old hidden
   rebuild) and the full architecture/verification plan were written to a Claude Code plan
   file that does **not** live in this repo and will not survive a new machine or a cleared
   plan directory — this entry is the durable record of the decision and of what's proven;
   rebuilding the milestone-by-milestone detail from scratch next session is expected and
   fine, the risk retirement above is the part worth not re-deriving.

45. **M1 is done, same session as correction 44: the printed canard bay now has a native
   Fusion generator, verified against `design/bay.py` in the live `CanardControlModule`
   document.** Two new files, `scripts/fusion_common.py` (the shared temp-BRep primitive
   builders, BaseFeature injection loop and volume/face verify helpers every later
   generator will reuse -- written once so six generators don't retype it, per correction
   44's own stated plan) and `scripts/make_bay_cad_fusion.py`, which ports
   `cad/canard_bay.fs`'s geometric logic (not its FeatureScript mechanics -- Fusion's
   temp-BRep API needs neither of the two Onshape limitations that forced a custom feature
   there) into Python that emits a standalone Fusion script, run via
   `fusion_mcp_execute` exactly as correction 44 hoped.

   Built and verified live: one "canard bay" body (shell, 4 collar bosses, 4 servo trays,
   8 webs, 8 clamp bosses, all unioned, then 4 collar bores + 4 windows + 4 flange reliefs
   + 16 insert holes subtracted) plus 8 retainer bars -- drawn directly per
   (quadrant, screw row) rather than modelled once and instanced, since a from-scratch
   generator has no Onshape-style part-instancing step to exploit and the quadrant-frame
   helpers make eight independent bodies exactly as cheap as one. Volume checks
   (VeryHighCalculationAccuracy) pass to the fourth decimal on every retainer bar and
   within the same 6% band `scripts/make_bay_cad.py`'s own Onshape-side verify() uses on
   the shell (28,257.58 mm³ built vs 28,889.05 mm³ analytic -- the estimate is a sum of
   prisms and cylinders that doesn't model web embedment or boss/tray overlap, so the CAD
   is the more correct number here, same as the Onshape side always argued). A face check
   (exact where volume on a radial hole through a curved wall is not, same reasoning as
   `make_sled_fusion.py`'s ports) confirms all 4 collar bores at dia 8.00 mm, clocked
   exactly 0°/0°/90°/90°. Screenshotted with everything else in the document hidden — shell,
   collar bosses and bores, tray windows, webs and the dog-bone retainer bars with their
   screw holes are all visibly correct, not just numerically.

   **Found along the way, not assumed:** `design/bay.py`'s `retainer_volume` (a bridge plus
   two pads) never subtracts the two M2 screw holes `cad/canard_bay.fs` actually cuts
   through every bar ("retholes") -- 2 × π × (INSERT_DIA×0.7/2)² × RETAINER_THICKNESS =
   11.8224 mm³ per bar, about 11.5% of one bar's volume. The Onshape-side `verify()`
   (`scripts/make_bay_cad.py`) never caught this because it only checks the SHELL's volume
   against `b.volume - b.retainer_volume`, never a bar's own -- this generator's own
   per-body verify does, and its own expected figure now corrects for the holes with the
   computation shown (measured, not assumed, same discipline as
   `PORT_VOLUME_TOLERANCE_PER_PORT`). `design/bay.py` itself is UNCHANGED: `retainer_volume`
   still overstates each bar's true material by that ~11.5%, which flows into
   `BayGeometry.mass`/`.volume` and the "as flown" mass line
   `scripts/make_bay_cad.py --assemble` prints. Small (eight bars, printed PETG-CF, a
   fraction of a gram each) and not this migration's job to fix, but worth a line here so
   nobody mistakes the Fusion generator's corrected constant for a discovered CAD error --
   the CAD is right, `design/bay.py`'s analytic formula is what's loose.

46. **M2 is done, same session as corrections 44-45: the servo and the hinge bearing are
   now native Fusion geometry, both verified in the live `CanardControlModule` document.**
   Two new files, `scripts/make_servo_cad_fusion.py` (3 bodies: case+flange with its six
   lug/dowel holes, the output spline as a separate body since it turns and the case does
   not, and the lower boss keep-out as a third) and `scripts/make_bearing_cad_fusion.py`
   (1 body, OD cylinder less its bore, at journal diameter plus running clearance rather
   than the journal diameter itself -- design/hinge.py's own header explains why that
   distinction is the entire reason this file exists). Both port
   `scripts/make_servo_cad.py`/`scripts/make_bearing_cad.py`'s geometry directly: every
   feature in both parts is a plain box or cylinder along a single axis, so unlike the bay
   neither needed FeatureScript-specific workarounds to begin with.

   Both built in their own independent local frame (origin on the hinge axis, on the part's
   own outboard-facing reference face, +Z radially outward), matching the Onshape
   originals' own separation -- each is its own Part Studio there, with no defined relative
   position between them. Placing four of each at their real quadrant/hinge-station
   position in the module frame (mirroring `scripts/place_bearings.py`'s reach-along-shared-
   axis technique) is explicitly a later milestone (M4), not this one; the two components
   sit at the document's shared root origin for now, which is why a screenshot of both
   together shows the bearing's cylinder buried inside the servo's case box -- an artifact
   of two independently-drawn parts both defaulting to an identity transform, not a
   modelling error. Isolating each confirmed both are correct on their own.

   Verified: the bearing's volume matches the analytic annulus to the fourth decimal
   (130.2462 mm³, tolerance 0.01) and its bore reads back as exactly one cylindrical face at
   the right diameter. The servo has no natural analytic volume to check against (a real
   servo isn't a simple density model) -- `scripts/make_servo_cad.py` itself only ever
   PRINTED a bounding box for a human to eyeball, never asserted one; this generator's own
   `verify()` makes that a real, automated check instead, an improvement on the Onshape
   original rather than just a port of it.

   **Two bugs found in this generator, both self-inflicted and both fixed before the parts
   were trusted, not defects in the design itself:** (1) the lower boss's box height was
   computed as `BOSS_Z0 - BOSS_Z1` where BOSS_Z1 > BOSS_Z0, handing Fusion a negative height
   and a hard `RuntimeError: invalid argument height` -- fixed to `BOSS_Z1 - BOSS_Z0`.
   (2) the servo body's own verify() first asserted its low-Z extent against the FLANGE's
   depth (6.25 mm) when the CASE is actually deeper (16.8 mm) and is what really sets the
   bounding box -- the geometry was right and the check's own expectation was wrong; fixed
   to assert against `CASE_Z0`. Both were caught by the verify step itself doing its job
   (a hard Fusion exception in the first case, a failed assertion in the second), not by
   inspection -- exactly the point of writing the check before trusting the part.

   **Next up is M3 — tube + panels + shafts**, each its own Fusion component (so a joint
   can bind to it later), tang-cut and spline-socket folded into the same per-quadrant pass.
   Needs the panel's sketch+extrude decision from correction 44's Architecture section
   settled first: `TemporaryBRepManager` cannot build a swept trapezoid from box/cylinder
   primitives alone, so the panel specifically needs Fusion's regular `Sketches`/`Extrudes`
   API, planform corners ported from `scripts/make_cad_profiles.py`'s `fin_profile()`.

47. **M3 is done, same session as corrections 44-46: the tube, all 4 canard panels and all
   4 shafts are now native Fusion geometry, nine separate components, all nine verified
   live in `CanardControlModule`.** One new file, `scripts/make_hinge_stack_fusion.py` --
   the only one of the six generators that touches Fusion's parametric `Sketches`/
   `ExtrudeFeatures` API at all, and only for one thing: the panel is a swept trapezoid,
   which `TemporaryBRepManager` cannot build from box/cylinder primitives. To keep that
   from becoming a second way this migration builds geometry, the panel is sketched and
   extruded in a disposable SCRATCH component, immediately lifted into a real temporary
   BRep body with `TemporaryBRepManager.copy()`, and the scratch component deleted -- from
   that point on the panel is cut and injected through the same `BaseFeature` pattern as
   every other body in the project. One deviation from what correction 46 said this
   milestone would do: the planform corners come from `design/hinge.py`'s own
   `RootJoint.leading_edge()`/`.trailing_edge()`, not from
   `scripts/make_cad_profiles.py`'s `fin_profile()` as planned -- `RootJoint`'s version is
   already expressed relative to the hinge axis and already carries the 0.500 mm standoff
   correction between the panel's real root face (R 40.200) and the theoretical planform
   root (R 39.700, the tube OD) that cost this project 0.36 mm once before, caught only by
   the CAD (`selected_root_joint()`'s own docstring). Using it directly means this
   generator cannot reintroduce that error; porting `fin_profile()` instead would have
   risked it a second time for no reason.

   Nine components: `Tube` (two concentric cylinders), `Panel0`-`Panel3` (the trapezoid
   above, less a tang slot), `Shaft0`-`Shaft3` (a dia-6 rod, a tang boss unioned onto its
   outboard end, a blind spline socket cut into its inboard end) -- not flat bodies in one
   component, because the tube-to-shaft revolute and shaft-to-panel rigid joints (M5) need
   distinct components to bind to, and building them separately from the start avoids the
   "Create Components from Bodies" post-process correction 44 already rejected as
   incomplete for the bay.

   Every one of the nine verified to the fourth decimal against an analytic figure derived
   from the SAME corners/dimensions the geometry is built from -- tube by the plain annulus
   formula; panel by a shoelace-polygon area on its four corners, times thickness, less the
   slot; shaft by a rod cylinder plus a tang box, less their overlap (a circular-zone
   formula -- the same style `scripts/make_root_tang.py`'s own `expected_mass_change_g()`
   used for this exact overlap on the Onshape side) and less the socket cylinder. All nine
   came back exact (0.0000 mm³ delta) once the bug below was fixed. Screenshotted: a
   correctly swept trapezoid panel sitting flush at the tube surface, and a top-down view
   showing all four panels/shafts at their right quadrants alongside the bay's own
   quadrant features.

   **One real bug, caught by the verify step on the first run, not by inspection:** the
   tang's THICKNESS and WIDTH axes were swapped in the actual geometry (though not in the
   analytic formula, which happened to be built the right way round regardless, since
   volume is a product and does not care which factor is which). `TANG_THICKNESS` (1.8 mm)
   has to run tangentially -- through the panel's own 3.2 mm thickness, which is the
   constraint that sets it -- and `TANG_WIDTH` (11.9 mm) has to run axially/chordwise,
   which is what `design/hinge.py`'s `leading_edge_clearance`/`trailing_edge_clearance`
   actually measure it against. Built the other way round, the tang slot cut only ~2 mm
   wide in the chordwise direction instead of ~12 mm, and the first run came back
   +455.68 mm³ over the analytic panel volume -- about a quarter of the intended material
   left uncut. Fixed by swapping which quadrant-box axis each constant feeds, in both
   `build_panel`'s slot cut and `build_shaft`'s tang boss; re-ran clean, exact match, on
   all four panels and all four shafts alike (so the bug was not quadrant-dependent -- it
   would have shipped identically wrong on every one of the eight bodies it touched had
   the volume check not been there to catch it before the first one was trusted).

   **Next up is M4 — the full placement pass and interference sweep**: everything built so
   far (bay, servo, bearing, tube, panels, shafts) sits at its OWN independent local or
   module-frame origin; servo and bearing in particular have never been positioned relative
   to the tube/shaft they actually belong on. M4 places all of it from `design/hinge.py`'s
   own radii/angles directly (no "copy an existing occurrence's transform" step, unlike the
   Onshape original), then runs the pairwise boolean-intersection interference sweep from
   correction 44's plan against both the new geometry itself and the existing hidden
   28-body rebuild as a second oracle.

48. **M4 is done, same session as corrections 44-47: the servo and bearing are placed on
   all four real hinge axes, and the whole new assembly (bay, servo, bearing, tube, panel,
   shaft, all four quadrants) checks clean for interference.** One new script,
   `scripts/place_hinge_hardware_fusion.py`, copies each of the three servo bodies and the
   one bearing body out of their M2 local hinge-axis frame and onto each of the four real
   axes via `Matrix3D.setToAlignCoordinateSystems` (local +X, the case-length "along" axis,
   maps to global +Z/axial; local +Y, "across", to tangential; local +Z, the shaft axis, to
   radial -- confirmed against `design/hinge.py`'s `ServoGeometry` docstring, which itself
   corrects an older, wrong assumption in `design/packaging.py`'s header that case WIDTH
   rather than the shaft axis consumes radius). All sixteen placed bodies (12 servo + 4
   bearing) land at their centre of mass exactly on the expected quadrant angle -- 0.000000°
   delta, at a 1e-6° tolerance, on every one.

   **The interference sweep**, `scripts/check_canard_interference_fusion.py`: 32 pairwise
   boolean-intersection checks (8 physically-adjacent pairs × 4 quadrants — servo/bay,
   bearing/bay, bearing/tube, shaft/tube, shaft/bearing, panel/shaft, panel/tube,
   servo/bearing), all read-only (every comparison runs on `TemporaryBRepManager.copy()`
   copies, nothing touches the real document). Every pair came back **exactly 0.0000 mm³**
   — not just under tolerance, no measurable overlap at all. **Scope note:** this checks
   the newly-generated geometry against itself only, not against the existing hidden
   28-body rebuild as a second oracle the way correction 44's original plan described —
   worth doing before M6's cutover, not done here.

   **A real Fusion API gotcha, found the hard way and worth any future session reading
   before touching body names:** renaming a `BRepBody` immediately after
   `comp.bRepBodies.add(body, baseFeature)`, in the SAME script execution that created it,
   does not reliably persist -- it reads back correctly off the live Python object
   reference for the rest of that run (which is what made the first two attempts at this
   script look like they worked), but a later, separate script run against the same
   document sees Fusion's own default name ("Body4", "Body5", ...) instead. True whether or
   not that same transaction also deletes an older `BaseFeature` first -- deletion isn't
   the trigger, injecting-then-renaming into an ALREADY-POPULATED component is. Renaming a
   body that was committed in an earlier, separate transaction always works. The generator
   works around this by never trying to name anything in the transaction that creates it:
   `_place_component` walks a PLACE → RENAME → CLEANUP → DONE state machine, driven by
   which bodies are named what in the live document, so each of up to three separate script
   runs does exactly one kind of mutation (create with default names; identify each
   default-named body by MEASURING it — volume against the still-present old bodies, which
   a rigid transform cannot change, and centre-of-mass angle against the four quadrants —
   then rename; delete the old `BaseFeature`). Confirmed by direct probes against this
   document before writing the fix, not by theory.

   **Next up is M5 — joints wired for real.** Correction 44's spike (M0) already confirmed
   the `AsBuiltJoint` API works; this milestone builds `scripts/make_canard_joints_fusion.py`
   for real against the now-fully-placed, now-interference-clean tube/shaft/panel
   components. The M6 cutover (deleting `Onshape_reference` and the old hidden rebuild) also
   still needs the against-the-hidden-rebuild interference cross-check this milestone
   skipped, folded in before or during M6.

49. **M5 is done, same session as corrections 44-48: the canard mechanism now articulates
   on entirely native Fusion geometry, with no dependency on `Onshape_reference` for the
   one thing in this document that moves.** Two new files:
   `scripts/make_canard_joints_fusion.py` (creates/verifies the 8 joints and drives the
   4 revolute ones to 8° for the motion check) and its paired
   `out/reset_canard_joints_fusion_generated.py` (resets them to 0°, kept as a separate
   script deliberately — see below). No new dimensions needed deriving from
   `design/hinge.py`; a joint is a relationship between already-built, already-placed,
   already-verified occurrences, not new geometry, and the call shape itself was already
   retired by M0's spike.

   Eight joints, mirroring the hand-built ones on `Onshape_reference` exactly (correction
   43): 4 **rigid** `Shaft{{q}}`↔`Panel{{q}}` (the tang bonded into its slot, zero DOF, no
   geometry argument) and 4 **revolute** `Shaft{{q}}`↔`Tube` (the hinge itself, axis read
   directly off the shaft's own cylindrical face via
   `JointGeometry.createByCylinderOrConeFace`). All eight `AsBuiltJoint`, not regular
   joints, for the same reason as the hand-built ones and more strongly: nothing here
   needs snapping into place, M4 already verified every occurrence sits exactly where the
   analytic model says it should.

   **One real wrinkle, worth its own line:** the shaft has THREE cylindrical faces at two
   different radii (the rod's own OD, and the narrower, shorter spline-socket bore) —
   `fusion-mcp-gotchas.md` already carried a warning about exactly this from the
   `Onshape_reference` joints, and this generator picks the LARGEST-area face
   (`max(faces, key=lambda f: f.area)`) rather than the first one found, specifically
   because of that warning. Worth restating: a warning written for one CAD source
   (a STEP import) turned out to matter just as much for geometry built from scratch in
   the same document — the shaft shape itself is what has two cylinders, independent of
   how it was authored.

   Idempotency is by INSPECTION, not by a name this generator sets itself: an existing
   joint is found again by checking which two occurrences (by component NAME) it connects
   and which `JointMotion` subtype it carries — after correction 48's body-naming discovery
   a few corrections up, nothing here assumes a name assigned in the same transaction that
   creates an object will survive to a later script run, and joints were never separately
   spiked for that failure mode. Checking real state costs nothing and doesn't depend on
   the assumption being true.

   **Verified three ways.** (1) Existence, correct `JointMotion` type, and correct
   occurrence pair for all 8 — passed clean, 8 new joints, first try. (2) The motion check
   correction 43 itself insists on — "a joint that added successfully and one that turns
   are different claims" — driving all 4 revolute joints to 8°, reading `rotationValue`
   back exact, and screenshotting: all 4 panels visibly deflected, joint indicators
   showing 8° at each hinge. Resetting to 0° is a **separate script**, on purpose, so a
   screenshot can be taken from OUTSIDE either script's own transaction, in between them —
   the same discipline M4's naming fix needed, applied here because it is the same class
   of problem (state has to actually commit and be re-observed, not just read back off a
   live reference before the script ends). (3) An INTERFERENCE SWEEP AT THE DRIVEN
   POSITION, not just at rest — the earlier M4 sweep (correction 48) read bodies through
   `component.bRepBodies`, which is local geometry and does NOT reflect a joint's
   occurrence-level transform, so it could only ever have shown the static, undriven
   shape no matter what any joint was doing. Reading through `occurrence.bRepBodies`
   instead (proxies, not native bodies — same distinction `fusion-mcp-gotchas.md` already
   flagged for `measureMinimumDistance`) at the driven 8° position, shaft-vs-bay,
   panel-vs-bay and panel-vs-tube all came back **0.0000 mm³** on all four quadrants — the
   mechanism has real clearance through its swing, not just when parked at zero.

   **Still open before M6's cutover:** the against-the-hidden-28-body-rebuild interference
   cross-check correction 48 also deferred, and now also: this session's 8°-driven
   interference sweep covered three pairs (shaft/panel vs. bay/tube) by hand, ad hoc, not
   as a checked-in, re-runnable script the way the at-rest sweep is
   (`scripts/check_canard_interference_fusion.py`) — worth promoting to a real script,
   parameterised by drive angle, before trusting this at any angle other than the two
   points actually checked (0° and 8°).

   **M6 — THE CUTOVER — is DONE (Sep 2026, correction 50).** Checklist, all six items
   closed:
     1. **DONE.** Cross-checked the new geometry against the old hidden 28-body rebuild
        as a second interference oracle. 26 pairs (tube, bay, 4× panel/shaft/bearing/
        servo-unioned, 8× retainer bar), matched by MEASURED centroid position rather
        than the rebuild's ambiguous Onshape pattern-copy names — all **exactly
        0.0000 mm³**, not just under tolerance.
     2. **DONE.** Promoted the ad hoc 8°-driven interference sweep to
        `scripts/check_canard_interference_driven_fusion.py`, checked in and re-runnable,
        parameterised by drive angle: 0°/+4°/+8°/−4°/−8°/0° (correction 49's own "a few
        more angles" ask), reading bodies through OCCURRENCE proxies so it actually
        reflects the joints' driven position. 144 pairs (6 per quadrant × 4 quadrants ×
        6 angles) — all **exactly 0.0000 mm³**. Joints verified reset to 0° afterward.
     3. **DONE.** `Onshape_reference` and all 28 hidden rebuild bodies deleted from the
        live `CanardControlModule` document, only after 1 and 2 passed clean — see
        correction 50 for what else this step found and fixed first.
     4. **DONE (Sep 2026, ahead of 1–3, while Fusion's MCP add-in was down; updated again
        in correction 50 now that the deletion is real).** `docs/05-canard-module-build.md`'s
        files table points at the eight `scripts/*_fusion.py` generators (the original six
        plus correction 50's seal/access-bulkhead pair) instead of the Onshape scripts/
        elements, and no longer carries `Onshape_reference` or the old 28-body rebuild as
        rows at all — both are gone from the document, not just pending.
     5. **DONE (Sep 2026, same session as 4).** Grepped the repo for remaining Onshape
        document-ID references tied to this module and confirmed each is either updated
        or intentionally left as historical record (e.g. `scripts/make_bay_cad.py`'s own
        `DOC`/`WS` constants — they document what WAS built, not what IS current).
        **Result: nothing needed changing.** All 16 files carrying
        `DOC = "a8abe36ef209825f56ac7a88"` / `WS = "30c982b22d7f0010281e2c54"` point at
        the Onshape `canard-control module` document, which "State of play" already says
        stays untouched as the historical record for corrections 1–43 — intentionally
        left alone. No `docs/*.md` file carries either raw ID directly.
     6. **DONE — this entry (correction 50) is that closing summary.**

50. **M6 is closed, and closing it found two more parts nobody had ported.** Asked to
   delete `Onshape_reference` and the old hidden 28-body rebuild once checklist items 1
   and 2 passed clean, the honest answer was "not yet" — 26 of those 28 bodies were the
   six parts M1–M5 already migrated, but the other two, `pass_through_plate` and
   `aft_gas_seal` (the access-bulkhead pair from correction 38 and the recovery-bulkhead
   pair from correction 34), had never been touched by any of the six generators. Deleting
   the rebuild as originally planned would have removed real geometry — a plate and a
   seal this module's own interference checks depend on — with nothing standing in for it.
   Caught by re-reading the checklist against the actual body list before deleting,
   not by the checklist itself, which described "the 28-body rebuild" as one thing.

   **Migrated both, the same way as the original six:** two new generators,
   `scripts/make_seal_cad_fusion.py` (aft gas seal + internal bulkhead, from
   `design/seal.py`) and `scripts/make_access_bulkhead_cad_fusion.py` (pass-through plate
   + nose aft face, from `design/access_bulkhead.py`), each a disc cut by its own
   overshooting hole cylinders — the simplest geometry in this whole migration, and
   verified the same way: volume against the analytic disc-less-holes figure, to the
   fourth decimal, matching the Onshape originals' own numbers exactly (20744.0871 mm³
   for the seal, 10425.7648 mm³ for the pass-through plate — SAME figures the Onshape
   `verify()` reported when these were first built in correction 34/38, confirming the
   hole layout and disc dimensions ported without drift). The aft gas seal and
   pass-through plate are built DIRECTLY in the module's global frame (Z 138.12→142.92
   and Z 0→2.4, read off the live `Tube` body's own bounding box rather than assumed —
   confirmed to the fourth decimal against the module-frame Z figures this document has
   quoted since correction 19), the `CanardBay` precedent (correction 45) applied to a
   flat part; the internal bulkhead and nose plate are built as parts only, unplaced, same
   reasoning as the Onshape originals (no recovery bay or nose cavity modelled here to
   place them in). Both placed parts cross-checked against their old-rebuild counterparts
   before anything was deleted: **0.0000 mm³ symmetric difference on both**, and **0.0000
   mm³ overlap against Tube and CanardBay** — clean geometry, not just a volume match.

   **Then the cutover itself, done live against `CanardControlModule`:** `Onshape_reference`
   (36 child occurrences) and the 28-body rebuild (58 root-level features spanning the
   whole hand-built parametric tree, `Tube` through two `BaseFeature` "Onshape diff" cut-tool
   blocks, deleted in reverse chronological order — the whole chain came out clean, zero
   root bodies remaining afterward) are gone from the document. The at-rest interference
   sweep (32 pairs, all eight generators' own adjacent-pair check) was re-run immediately
   after deletion, against nothing but native geometry for the first time in this project's
   history: **still exactly 0.0000 mm³ on every pair.** Document saved.

   **One thing worth naming rather than quietly accepting:** `RecoveryInternalBulkhead`,
   `NoseAftFace`, `AftGasSeal` and `PassThroughPlate` all default to identity transform in
   components of their own, and the two unplaced ones (`RecoveryInternalBulkhead`,
   `NoseAftFace`) sit at local-frame Z [0, thickness] — the SAME global coordinates the two
   PLACED parts' own real positions partially overlap (`PassThroughPlate` spans that exact
   Z range for real). Correction 46 already normalised this class of overlap for M2's
   servo/bearing ("two independently-drawn parts both defaulting to identity transform, not
   a modelling error") when NEITHER part was at its real position; here it is slightly
   worse, because one of the four bodies sharing that coordinate range genuinely IS at its
   real position and the other three are visually sitting on top of it. Left as-is,
   matching the established precedent and because nothing currently checks interference
   against either unplaced part — but the next person driving a full-document interference
   sweep should know these two are not really there.

   **The module has zero Onshape dependency now.** Every body in `CanardControlModule` is
   native, generatable, checked-in Fusion geometry, deriving every dimension from
   `design/*.py` the same way the Onshape-era scripts did. Onshape's `canard-control
   module` document is untouched and remains the historical record for corrections 1–43;
   nothing in the live Fusion document reads from it, or from the STEP export, any more.

51. **The recovery bay's tube exists now, and its internal bulkhead is finally assembled
   rather than just drawn.** Asked what Step 3's dimensioned drawing still owed after M6
   closed, the honest answer (correction 43, restated) was two things: the recovery bay
   (no tube, an unplaced bulkhead) and the booster + aft fins (nothing at all). Picked the
   smaller of the two — sizing already existed (`design/recovery.py`, `design/seal.py`,
   `design/joints.py`) and the bulkhead itself was already built (correction 50), just not
   placed anywhere real.

   **One new generator**, `scripts/make_recovery_bay_cad_fusion.py`: `RecoveryBayTube`, a
   plain annulus (no wall bores, no ports — nothing in this project charges the recovery
   bay with either), OD 79.4 / ID 74.8 mm matching the canard module's own tube, length
   357.3 mm (`recovery_bay_cal = 4.5`, `design/configure.py`), built directly in the shared
   document frame at Z 142.92 → 500.22 — continuing from the aft gas seal's own aft face,
   which is also the canard module's own aft face (`design/joints.py`'s "canard module /
   recovery bay" joint is exactly this interface). Volume verified to the fourth decimal
   against the plain annulus formula (199051.3388 mm³, exact) — no radial holes here to
   loosen the tolerance for, unlike the canard module's own `Tube`.

   **The bulkhead's station is read off the packing model, not assumed.** Main compartment
   is forward (`design/recovery.py`'s own conduit note and `design/joints.py`'s per-joint
   notes both say so — "MAIN ejection separates here" is the forward joint, "DROGUE
   ejection separates here" is the aft one), so: aft gas seal's aft face (142.92 mm) + main
   compartment's packed length (`evaluate().packing`, 229.5003 mm) + 3 mm epoxy fillet
   clearance = the bulkhead disc's forward face at 375.4203 mm, running 4.8 mm to
   380.2203 mm, centred in the 10.8 mm `INTERNAL_BULKHEAD_STACK` allowance
   (`design/configure.py`) rather than flush against either compartment. The occurrence was
   TRANSLATED, not rebuilt — the disc geometry from correction 50 is unchanged, only its
   position — and the placement was verified by reading the body's own bounding box back
   through the occurrence proxy (not by trusting the transform matrix that was set), landing
   exactly on the computed station. 27.3 mm of slack remains at the tube's own aft face,
   which is where the recovery-bay/booster joint's anchored coupler half bonds in
   (`design/joints.py`'s own budget for that joint). Interference-clean: tube vs bulkhead,
   tube vs aft gas seal, tube vs the canard module's own tube — all exactly 0.0000 mm³.

   **Still open, and stated rather than worked around:** the U-bolt, backing plate and
   charge well this bulkhead needs are not drawn. Not an oversight — none of the three has
   ever been SIZED by anything in this project. `scripts/make_bulkhead_cad.py`'s own
   docstring said as much when the Onshape-era part was first built: "The backing plate is
   the one that matters ... and it is not here." The U-bolt HOLES through the bulkhead
   are cut (correction 50, from `design/seal.py`'s own hole layout) — what is missing is
   the hardware standing proud of them, which needs a dimension chosen before it can be
   drawn, the same discipline this project applied to the coupling (correction 21) and the
   hinge collar material (correction 19) rather than inventing a number to fill the gap.
   **Still entirely undrawn: the booster and aft fins** — checked rather than assumed
   (correction 52 corrects the record here: the planform and root attachment turned out to
   already be sized, just never built in 3D). Only the motor mount is a genuine sizing gap.

52. **The booster tube and all four aft fins are drawn, and two of "no planform, no root
   attachment, no motor mount" turned out to already be decided.** Correction 51 claimed
   the booster + aft fins had zero design-side sizing at all. Checking before drawing found
   that was wrong: `design/configure.py` has carried a frozen `FinSet` for the aft fins
   since before this project's Fusion migration (`aft_root_cal`/`aft_semispan_cal`/
   `aft_sweep_cal`/`aft_taper`, the same numbers `scripts/make_cad_profiles.py` has emitted
   as a 2D DXF fin pattern all along), and that DXF generator's own `fin_profile(aft,
   tab=TAB_DEPTH)` already encodes a root attachment scheme — a 12 mm through-wall tab —
   that had simply never been built as real geometry, in Onshape or Fusion. Only the motor
   mount (`design/mass.py`'s `motor_mount_centering_rings` budget line, no ring diameter,
   count or station behind it anywhere) is a genuine, unsized gap, and it is NOT attempted
   here for the same reason the U-bolt/backing-plate/charge-well were not in correction 51
   — inventing centering-ring geometry with nothing sizing it would be the exact mistake
   this project keeps finding and fixing elsewhere.

   **One new generator**, `scripts/make_aft_fin_cad_fusion.py`: `BoosterTube` (plain
   annulus, same OD/ID as every tube in this document, built continuing directly from
   `RecoveryBayTube`'s own aft face — the two share the same station, confirmed by
   `design/configure.py`'s own arithmetic, not assumed) with four rectangular slots cut
   through its wall for the fin tabs, and `AftFin0`-`AftFin3`, each the full flat pattern
   `fin_profile()` already describes (trapezoid plus tab, six points, one body) extruded
   into 3D and clocked at 45/135/225/315 degrees.

   **Clocking is the one number nothing in `design/*.py` encodes.** `FinSet` has no
   clocking field; "interdigitated 45 degrees" has only ever been prose, in
   `docs/00-requirements.md`, this file's own "Current vehicle" line, and `docs/05`'s own
   canard-panel section. Recorded here as `AFT_FIN_CLOCK_DEG = 45.0` rather than left
   implicit a second time.

   **Building at 45 degrees broke the canard-panel generator's own quadrant trick**, and
   fixing it found the session's one real bug. `make_hinge_stack_fusion.py` picks Fusion's
   `xZConstructionPlane`/`yZConstructionPlane` by quadrant parity, which only works because
   0/90/180/270 land exactly on an axis-aligned plane — 45 does not. Fixed by always
   sketching on `xZConstructionPlane` (as if clocked at 0) and rotating the finished temp
   body into its real clocking afterward with `TemporaryBRepManager.transform()` and a
   `Matrix3D.setToRotation()` about Z — one technique, works at any angle, so a later
   generator never needs a third way to place geometry.

   **THE REAL BUG: renaming a body sourced from Sketch/Extrude does not persist within the
   same script transaction, even into a component that was completely empty going in** —
   a stronger and different failure than the already-documented "already-populated
   component" gotcha. `b = comp.bRepBodies.add(body, bf); b.name = "aft fin"` read back
   correctly on `b` itself but a fresh `comp.bRepBodies` query, one line later, in the same
   run, still showed Fusion's own default name — `verify_fin()` reported "aft fin is
   missing" against a component that, by every appearance, had just been built successfully.
   Isolated by direct test: a body from `TemporaryBRepManager.createSphere()` renames fine
   through the identical pattern; a body copied off an `ExtrudeFeature`'s own result does
   not. The canard panels (M3) used this exact same rename pattern and are correctly named
   in the live document today, so this is not "always broken" — it is unreliable, which is
   worse, because a check that sometimes passes on a real bug is not a check. Fixed once, in
   `scripts/fusion_common.py`'s shared `_inject()`: rename AFTER `bf.finishEdit()`, via a
   fresh `comp.bRepBodies.item(i)` query, never via the object `.add()` itself returned.
   Confirmed this persists for both extrude-sourced and primitive-sourced bodies alike, so
   every generator now goes through one rename path rather than two that quietly disagree.

   **A second, smaller bug in the same session: an unsubtracted slot volume.** The first
   verify attempt on `BoosterTube` failed by exactly 4089.21 mm³ — four slots' worth, almost
   to the decimal, because the analytic `TUBE_VOLUME_MM3` constant was computed from the
   plain annulus and the slot volume was calculated but never actually subtracted from it
   before being embedded in the emitted script. Fixed; the real per-slot residual once the
   subtraction was correct is ~0.29 mm³ (a box cut through a curved wall has the same
   flat-face-meets-curved-surface residual `fusion-mcp-gotchas.md` already documents for
   the canard module's own radial wall bores), loosened tolerance set from that measurement,
   not guessed.

   **Verified**: `BoosterTube` volume against the analytic annulus-less-four-slots figure
   (227819.8017 mm³, −1.1757 mm³ against a 2.0 mm³ loosened tolerance); each `AftFin{q}`
   against the same six-point shoelace polygon its own sketch is built from, exact to
   0.0000 mm³ on all four; centroid angle exactly 45/135/225/315 degrees on all four, 1e-4
   deg tolerance; zero interference — `BoosterTube` vs `RecoveryBayTube`, each fin vs
   `BoosterTube`, and every fin pair against every other — all exactly 0.0000 mm³.
   Screenshotted at a fit view: nose, canard module, recovery bay, booster and all four aft
   fins, visibly clocked 45 degrees off the canards, in one continuous vehicle for the first
   time in this project's history.

   **Still open**: the motor mount (unsized, stated rather than invented) and the U-bolt/
   backing-plate/charge-well from correction 51. Between them, that is what is left of Step
   3's "a dimensioned drawing" deliverable.

53. **The motor mount is sized, and sizing it moved a frozen number and found a live
   ejection charge pointed at a sealed volume.** `design/motor_mount.py`,
   `scripts/motor_mount_report.py`, verdict in `baseline.py`, geometry in
   `scripts/make_motor_mount_cad_fusion.py`, write-up in `docs/09-motor-mount.md`. It is the
   fifth allowance in this project to be paid for without existing -- `mass.py`'s
   `motor_mount_centering_rings = 0.250`, with no ring count, ring diameter, ring station,
   mount tube or retainer behind it anywhere. **231.1 g against that 250.** The part
   `design/seal.py` explicitly handed over -- the booster's forward bulkhead -- is sized here
   too, and the handover turned out to be right for a reason `seal.py` could not have known.

   **THE HEADLINE IS THAT THE CENTERING RINGS ARE NOT THRUST STRUCTURE.** Thrust enters the
   airframe at the booster's forward bulkhead: the motor's forward closure bears on that disc
   through the mount tube's bore, and the load travels forward into the vehicle it is
   pushing. The rings align the motor, tie the fin tabs in, and carry its mass laterally.
   Sizing them as though 587 N ran through them would have produced a heavier, wronger part
   and hidden all three findings. They are checked against the full thrust anyway, as the
   redundant path, because a load path with one member is not a load path.

   **FINDING 1: THE FROZEN 12 mm FIN TAB AND A 54 mm MOUNT TUBE CANNOT BOTH EXIST.**
   `make_cad_profiles.py`'s `TAB_DEPTH = 0.012` is measured inward from the booster's OUTER
   radius, so the tab tip sat at R 27.70 -- **0.85 mm inside any mount tube a 54 mm motor can
   have, and 0.70 mm off the bare motor case, which is what the round number was really drawn
   against.** Meanwhile `design/flutter.py` and `baseline.py` both quote the 1.97x aft-fin
   flutter margin for a tab "bonded through the wall to the MOTOR MOUNT". Four `AftFin` bodies
   already occupied R 27.70 in the Fusion document; this was never going to survive an
   interference check, and it survived because there was nothing yet to check it against.
   Depth is **derived** now -- booster OR less mount tube OR, **11.15 mm** -- and
   `make_cad_profiles.py` and `make_aft_fin_cad_fusion.py` import
   `motor_mount.fin_tab_depth_for()` rather than each carrying the literal. **The four fin
   panels and the four booster tab slots must be rebuilt in Fusion.**

   **FINDING 2: THE FORWARD BULKHEAD AND THE THRUST FACE ARE THE SAME PART.** The booster's
   1.2 cal margin is 95.28 mm; the coupler takes 79.40 and `joints.BULKHEAD_ALLOWANCE` budgets
   12.00 more, leaving **3.88 mm**. There is no room for a separate thrust plate and there
   does not need to be -- one disc closes the drogue compartment, anchors the drogue harness's
   aft U-bolt, and presents its aft face to the motor.

   **FINDING 3, AND IT IS A FLIGHT SAFETY ONE.** The disc as sized is 4.80 mm rather than the
   12.00 the allowance charges, so the real clear gap is 11.08 mm -- and that gap is a
   **sealed 25.85 cm3 directly in front of the Pro54's own forward-closure ejection charge.**
   This vehicle deploys on an independent altimeter and nothing in this project had ever said
   what happens to the motor's charge. `seal.ejection_pressure()` puts 1.2 g in there at
   **10.17 MPa against a disc whose capacity is 6.69** -- and it fails at every charge mass
   from 0.8 g up, so the conclusion does not turn on the assumed figure. **The forward closure
   must be PLUGGED** (Cesaroni sells one; a purchase, not a modification), recorded as
   `FORWARD_CLOSURE_PLUGGED` so the check fails loudly if anyone ever sets it False.

   **Settled on the way past:** the mount tube is **332.08 mm**, which reconciles
   `make_ork.py`'s 331 against `docs/04`'s 416 -- the latter was the booster's own length
   copied by mistake. **Still open and stated rather than solved:** the fin ROOT MOMENT that
   tab bond carries has never been computed by anything here, and `flutter.py` says the same
   about its own ideal-rigid-root assumption.

54. **The U-bolt, backing plate and charge well are sized -- and the U-bolt this project
   assumed does not carry its own load.** `design/recovery_hardware.py`,
   `scripts/recovery_hardware_report.py`, verdict in `baseline.py`, geometry in
   `scripts/make_recovery_hardware_cad_fusion.py`, write-up in `docs/10-recovery-hardware.md`.

   **`seal.py` had carried this since it was written, and it read as a calculation:** *"An M5
   U-bolt on a 25 mm leg spacing is the ordinary size for this load -- 1.3 kN through two 5 mm
   legs is 33 MPa of shear in stainless, which is nothing."* Two errors, compounding. **The
   legs are not in shear** -- the harness pulls along the bolt's axis and they are in tension.
   **And the legs are not what breaks** -- the CROWN is, in bending at the two bends, which is
   where a U-bolt used as an anchor is actually observed to straighten. A published U-bolt
   rating is for CLAMPING A PIPE, which is a different structure. Sized against the mode that
   governs: **M8, 2.01x**, and the dia 5.5 holes already placed in both bulkheads become
   dia 8.5. They are not drilled yet, so the finding costs nothing but the drill. **The
   straight-beam idealisation gives 1.28x and is left visible rather than argued away** -- the
   arch model is the right one, but this is the most safety-critical joint in the vehicle and
   a destructive pull test on the bought bolt is what settles it.

   **THE BACKING PLATE IS WHAT `make_bulkhead_cad.py` SAID IT WAS.**
   `Bulkhead.point_load_stress()` goes as log(disc radius / footprint radius) and `seal.py`
   passed a hardcoded 6.0 mm -- a bare nut face -- with a comment saying a real plate would
   replace it. Replaced: **4.95x becomes 7.98x.** A result of the part existing, not a retune;
   `seal.py`'s default is unchanged, so every previously reported number still reproduces.

   **FINDING: THE HARNESS DOES NOT FIT THROUGH THE U-BOLT.** `recovery.size_harness()` picks
   3/4" tubular nylon, 19.1 mm; an M8 U-bolt on a 25 mm spacing leaves 17.0 mm. Two sized
   parts of this vehicle, and nothing had ever put them next to each other. Opening it up
   drives the rod to M10 and ~310 g across four anchors, which is not the answer -- **the
   webbing was never meant to pass through it.** `HARNESS_HARDWARE_KG` has priced links and
   swivels since it was written. Recorded as a requirement rather than left as the thing
   everybody happens to do: the harness attaches through a **quick link**, and the link goes
   through the U-bolt.

   **FINDING: THE INTERNAL BULKHEAD'S FACE IS THE MOST CROWDED SURFACE IN THE ROCKET.** It
   anchors a harness both ways, so it carries a U-bolt on each face -- and two U-bolts cannot
   share two holes. They clock **90 degrees apart**, which puts a backing plate along each
   axis and leaves only the diagonal clear. Each plate is then **relieved** with 9.5 x 3.50 mm
   edge notches where the opposing legs reach under it, and the conduit hole -- at 45 degrees
   "so it is equidistant from both legs", which was right for as long as that face held only
   holes -- has to move **out to R 27.5 mm** so the drogue charge well sitting on it clears
   both plates. Moving out reduces the bending field, so the hole margin *improves*, 2.17x ->
   2.41x. `seal.INTERNAL_CONDUIT_RADIUS` is the only hole radius in this vehicle set by a part
   rather than by the stress field, and the check re-derives the window it must lie in.

   **THE MASS LINE THAT DID NOT EXIST.** `mass.py` had no line for the anchors at all;
   `recovery.py`'s own `SoftGood("2 x U-bolt", 0.030, ...)` is dead code (`measured_volume`
   overrides it and nothing sums `Compartment.hardware` masses); `docs/04` independently said
   120 g for four. Three numbers for one part, none reconciled, and the real one is **191 g**
   because the bolt is M8. Sixth allowance-shaped hole found by drawing the part -- and the
   first that was not even an allowance. It was nothing at all. **The anchor is also
   SELF-LOADING**, which nothing else here is: its mass raises the descent mass and therefore
   the opening shock it carries. One pass settles it because the rod size is discrete and M8
   survives at 2.01x; the next thing to gain mass anywhere in this vehicle may push it to M10.

   **What it costs.** One anchor displaces 5.95 cm3 against `UBOLT_ENVELOPE_VOLUME`'s
   estimated 3.00, and the charge wells are rigid too -- `default_soft_goods()` said in as
   many words that they "do not consume packing volume", and a dia 12 tube standing 19 mm off
   the face is directly in the canopy's way. Both are priced now, and the well envelope is a
   **converged** figure rather than a typed one: the well displaces packing, the packing sets
   the compartment volume, the volume sets the charge, and the charge sizes the well -- two
   passes, the same fixed point `add_conduit()` already runs. Recovery bay margin **+8.35 ->
   +4.63 mm**, and nothing was resized to keep it there. Vehicle level, from 191 g the budget
   did not have: dry **5.68 -> 5.89 kg**, apogee **1326 -> 1271 m**, one-sided crossrange at
   8 deg **340 -> 297 m**, lateral authority **1.59 -> 1.41 g** against R8's 0.5, static margin
   **2.27-2.76 -> 2.30-2.77 cal**. No requirement moves out of bounds, and R6's 1600 m apogee
   cap has more room rather than less.

55. **Asked whether the vehicle could manoeuvre aggressively rather than lean through one
   slow curve, three alternative control architectures were evaluated and all three lost to
   the one already built -- and the winning change is a sensor line item, not an airframe
   change.** The question was whether this vehicle can fly a sequence of sharp,
   precomputed direction changes rather than the single one-sided bias `achievable_crossrange()`
   models. Nothing was changed by this correction. **`design/configure.py` is untouched and
   the frozen geometry still stands** -- what follows is a trade study and one open decision.

   **THE ANSWER IS A WIDER-RANGE GYRO, AND IT HAS A DEADLINE.**
   **>> SUPERSEDED BY CORRECTION 58 -- THIS SECTION'S CONCLUSION IS WRONG. <<** The
   saturation arithmetic below is correct; what does not follow is that a wider part lets
   the cap lift. Uncapping multiplies the DOMINANT attitude-error term (gyro scale factor
   at roll rate) by 4x from the rate and ~2x from the wider part's looser tolerance:
   `attitude_error_budget()` gives **7.94 deg capped against 62.89 deg uncapped**, and L1
   is "hold roll angle". The reversal times below are real; the estimate that would have to
   fly them is not. Read correction 58 before acting on anything in this section.

   `ROLL_COMMAND_CAP_DEG = 2.0`
   exists because a +/-2000 dps part saturates at the 8 deg deflection limit (2378 deg/s,
   correction 36 and `docs/06`). That cap is currently costing a factor of four in roll rate,
   and roll rate is what sets how fast the lateral-g vector can be re-aimed. Time for a
   180 deg bank reversal, from `roll_authority()` at the interdigitated interference model:

   | t (s) | V (m/s) | at the 2 deg cap | at 8 deg, wider gyro |
   |---|---|---|---|
   | 3.4 | 157 | 528 deg/s -> 0.40 s | 2110 deg/s -> **0.15 s** |
   | 9.0 | 79 | 268 deg/s -> 0.81 s | 1070 deg/s -> **0.31 s** |
   | 14.6 | 24 | 80 deg/s -> 2.74 s | 320 deg/s -> **1.05 s** |

   `docs/06` already records the option in one line -- *"Some IMUs reach +/-4000 deg/s. It is
   a line in a datasheet and costs nothing at design time, if you check before layout"*.
   **Correction 58 revises what to do with it**: specify a part with SELECTABLE full scale to
   +/-4000 and RUN IT AT +/-2000, because what is free before the schematic is the option,
   not the capability. The lever that actually moves the dominant term is scale-factor
   CALIBRATION (a 0.5% spec limit measures nearer 0.05-0.1%), which is a procedure and not a
   purchase.

   **REJECTED 1: CANTED AFT FINS + SPIN-AND-PULSE.** Cant the aft fins, let the vehicle spin,
   and pulse a canard pair phase-locked to the rotation (reversing every half revolution, so
   the force integrates in one ground direction). Two things kill it, and the first is
   geometric:

   | cant | t=3.4 s | t=9.0 s | t=14.6 s |
   |---|---|---|---|
   | 0.25 deg | 1.00 Hz | 0.51 Hz | 0.15 Hz |
   | 0.50 deg | 2.00 Hz | 1.02 Hz | 0.31 Hz |
   | 1.00 deg | **4.01 Hz** | 2.04 Hz | 0.61 Hz |
   | 2.00 deg | 8.02 Hz | **4.07 Hz** | 1.22 Hz |

   **Pitch mode is 4.1 Hz**, so 1 deg of cant starts the flight AT roll-pitch resonance and
   2 deg sweeps down THROUGH it mid-coast. Only cant <= 0.5 deg stays clear for the whole
   flight, because **spin rate is not a design number -- it is a decaying schedule**, falling
   with velocity by 6.5x across the coast. Second, and this corrects a claim made earlier in
   the same session: **a direction change under spin-and-pulse is not free, it costs half a
   revolution**, and that latency grows as the vehicle slows -- 0.25 s at burnout, 0.49 s at
   mid-coast, 1.64 s at the q=300 cutoff. Against the wider-gyro column above it loses at
   every point in the flight, *and* it pays a flat **2/pi = 63.7%** force penalty (the average
   of |cos| over a revolution) that bank-to-turn does not. It would also add permanent induced
   drag, put the magnetometer -- by then the PRIMARY phase reference -- next to servo current
   spikes synchronised to the spin, and introduce gyroscopic pitch/roll coupling that nothing
   in this project models. **The servos are NOT the obstacle**: at 0.5 deg cant the half-period
   is 250 ms against a 24 ms full +/-8 deg traverse at the X08 Plus's 667 deg/s, so half-rev
   square-wave reversal is comfortable. That was the one part of the idea that held up.

   **REJECTED 2: FREEWHEELING / ROLL-DECOUPLED TAIL.** Put the aft fin unit on a bearing so
   it cannot transmit roll torque into the body. It does cleanly remove the canard/aft-fin
   roll cancellation -- and it removes **86% of the vehicle's roll damping** with it, which is
   the same fins doing the same job seen from the other side. Split of `roll_damping_cl_p()`
   at the baseline: canards **-9.6**, aft fins **-59.7**, total **-69.3 /rad**. Damping is what
   lets a commanded bank angle be *arrived at* rather than overshot, so the technique makes
   pointing less precise, not snappier -- it adds no force and no torque, because it is not an
   actuator. It also wants a rotating bearing joint in the primary thrust path, which
   `design/joints.py` has no model for. **Worth recording why the technique exists at all**,
   since it is real and widely used: it is a passive substitute for an active roll loop, for
   vehicles that cannot afford a gyro + magnetometer + control law (unit cost at scale, gun-launch
   shock survival, sub-second flight times, seeker isolation). This vehicle already pays for
   the active version, so it would be buying the cheap fallback on top of the good answer.

   **REJECTED 3: COLD-GAS RCS / JET VANES.** Solves low-q roll authority off the rail --
   a problem nothing in this project has ever found. Jet vanes also mean hardware in the
   exhaust of a **certified** Pro54 reload, which voids the motor certification and the club's
   waiver with it. Not a cost trade; not available.

   **THE "SLOW CURVE" DIAGNOSIS WAS WRONG, AND THAT MATTERS FOR WHICH KNOB TO TURN.** The
   suspicion was that the vehicle responds sluggishly. It does not: quarter-period of the
   pitch mode is **60-68 ms across every geometry in the menu below**, and it barely moves
   with fin size. What makes a manoeuvre read as a slow lean is not response lag, it is
   **lateral-g magnitude** -- 1.41 g needs seconds of integration before displacement is
   visible. So the lever is authority, not bandwidth, and the pitch dynamics are not the
   thing to change.

   **OPEN DECISION, NOT TAKEN HERE: the authority/altitude menu.** From
   `robustness.optimise()` and `evaluate()`, all at the 8 deg limit:

   | | canard/aft (cal) | lat g | xrange | apogee | P(SM<1.0) | flutter | torque |
   |---|---|---|---|---|---|---|---|
   | baseline today | 0.85 / 1.55 | 1.41 | 297 m | 1271 m | 0.1% | 2.12x | 3.3x |
   | A shrink aft fin | 0.85 / 1.40 | 1.51 | 323 m | **1295 m (+24)** | 0.7% | 2.39x | 3.2x |
   | B balanced | 1.00 / 1.70 | 1.67 | 346 m | 1238 m (-33) | 0.1% | 1.91x | 2.8x |
   | C optimiser max | 1.30 / 1.85 | 2.27 | 456 m | 1196 m (-75) | 0.5% | 1.75x | 2.0x |

   **A is the odd one: it buys authority AND altitude**, because a smaller aft fin is less
   mass, less drag, and fights the canards less. **C is where to stop** -- it is the
   optimiser's own pick, it passes every constraint, and it lands on torque margin **exactly**
   at the 2.0x floor with flutter at 1.75x against a 1.5x floor. Two constraints at their
   limits simultaneously, with an airframe mass model still +/-30% until parts are swung, is
   not a design point. **Nothing here is adopted; `configure.py` still carries 0.85/1.55.**

   **STATED RATHER THAN SOLVED.** Every figure in this correction came from a throwaway probe,
   not from a checked-in script -- **none of it is regenerable by anything in `scripts/`**,
   which is this project's own standard and this correction does not meet it. The one
   cross-check that was run: the jink simulator reproduces the documented one-sided crossrange
   at **296.7 m against `evaluate()`'s 297 m**, which is why its jink numbers (an 8-segment
   profile spends **9.2 of 11.2 s** slewing rather than accelerating) are quoted at all. If any
   of this is acted on, `design/spin.py` and a jink-capable crossrange model have to exist
   first. **And the deeper caveat applies to the whole study: every roll number above is
   downstream of `Cl_delta`, which this document already calls the weakest figure in the
   analysis, and which GV-2's open-loop deflection sweep exists to measure.** This was
   precision arithmetic on an unmeasured coefficient.

56. **Step 3's CAD was executed, and running it found six defects the models could not see
   -- five of them in parts this document already called finished.** The three queued
   generators were run against `CanardControlModule` for the first time. Everything that was
   only ever "written and verified offline" is now built: the booster tube and four aft fins
   at the derived **11.15 mm** tab, the **motor mount** (forward bulkhead, mount tube, two
   centering rings, motor envelope), and the **recovery hardware** (4 U-bolts, 4 backing
   plates, 2 charge wells). Every body verifies against its analytic volume, most at
   **delta +0.0000**. Interference went **12 pairs -> 5**, and the five that remain are
   itemised at the end.

   **ONE GEOMETRIC FACT CAUSED THREE OF THE SIX, AND IT IS THAT THE TAB IS NOT A RECTANGLE.**
   `make_cad_profiles.fin_profile()` builds the through-wall tab as a TRAPEZOID --
   `[(0,0), (sw,s), (sw+t,s), (r,0), (r-6.0,-d), (6.0,-d)]` -- so its forward edge RAMPS from
   the root leading edge down to full depth over 6 mm, and there is tab material at every
   station of the root chord. Two separate consumers each modelled it as a rectangle
   starting at the 6 mm station:
   - **The forward centering ring landed in the ramp**, 22.59 mm3 into each of the four fins.
     `motor_mount.py` placed it against `tab_forward = x_root_le + 0.006`. The tab crosses the
     ring's own outer radius at x = 2.3 x 6/11.15 = **1.2377 mm**, i.e. Z 766.878 -- which is
     the observed overlap start **to three decimals**.
   - **The tube's tab slots were cut only across the full-depth band**, so both ramps ran
     through solid wall: **79.15 mm3 per fin, four fins**, sitting in this document since the
     fins were first drawn. Correction 52 claims *"fin-to-tube ... all exactly 0.0000 mm3"*;
     the document disagreed, and had done all along.
   - **The check that existed to catch the first one shared its datum.** `gap_fwd` measured
     to the full-depth station and printed *"clears the tab LE by 2.00 mm"* over a 2.76 mm
     overlap. **A check whose datum is wrong is worse than no check** -- correction 14's
     lesson, recurring.

   Fixed by naming the two datums apart rather than by moving a number: `TAB_RAMP_LENGTH`,
   `fin_tab_forward` (full depth -- the BOND datum, since only the full-depth run lands on
   the mount tube) and `fin_tab_material_forward` (ramp start -- the CLEARANCE datum), plus
   `SLOT_INSET_MM = 0.0` so the slot spans the full root chord. Forward ring moves to
   Z 760.44..763.64; tube volume drops **353.28 mm3 = 4 x 12 x 3.2 x 2.3**, exactly the extra
   slot. The check now reads *"clears the tab's ramp start by 2.00 mm (8.00 mm to full
   depth)"*. **No vehicle number moves**: feasible, no violations, apogee 1270.8 m, dry
   5.886 kg.

   **A DECISION RECORDED IN A COMMENT AND IMPLEMENTED ON ONE SIDE ONLY.**
   `INTERNAL_CONDUIT_RADIUS`'s own comment has said since correction 54 that the internal
   bulkhead carries a U-bolt on each face and *"they clock 90 degrees apart"*, and
   `recovery_hardware.py` duly gives the aft anchor `clocking_deg = 90` -- but
   `seal.hole_layout()` appended **one** pair at 0 deg for every bulkhead, so the 90 deg
   bolt's legs landed on undrilled G-10. The CAD priced it exactly: **482.55 mm3 =
   2 x pi x 4^2 x 4.8**, two full legs, no holes at all. Two more holes added;
   `check_hole_layout()` re-run and still OK.

   **THE STALE-CAD ONE.** `AftGasSeal` and `RecoveryInternalBulkhead` were still carrying
   the **5.5 mm** U-bolt holes they were built with before correction 54 took them to 8.5.
   `seal.UBOLT_HOLE_DIAMETER` was already 8.5 -- the DESIGN was right and the geometry was
   old, which is the reverse of this project's usual failure. Rebuilt: each disc lost
   **316.67 mm3 = 2 x pi (4.25^2 - 2.75^2) x 4.8**, to the last decimal.

   **A LATENT CHECK BUG, FOUND ONLY BECAUSE NAVBAY HAD TO BE REBUILT.**
   `make_sled_fusion.py`'s bore check excludes airframe bodies from "must pass the 70.20 mm
   shoulder bore" by name, and its list was `("nav bay tube", "nose shoulder", "nose
   plate")`. **Correction 42 added an `aft coupler` body to that component** -- so the ports
   could be drilled through tube and bonded coupler together -- and did not extend the list.
   The check therefore demanded that a coupler bonded at R 37.400 pass a 35.100 mm bore and
   failed by 2.3 mm, on a body that never moves. Latent since correction 42 because the
   generator was not re-run until now. `"aft coupler"` added; the check reports its real
   answer again, **34.80 mm against 35.10**, correction 41's own 0.3 mm.

   **AN ORPHAN DUPLICATE FIN.** `DiagFin/Body1` -- byte-identical to `AftFin0` (same volume,
   same bounding box, same centre of mass to three decimals) and sitting at the same
   coordinates, i.e. **100% overlap**. Nothing in the repo creates or references it, and its
   body carried Fusion's default name, which is the signature of correction 52's own
   rename-persistence bug. A diagnostic article from that session, never cleaned up.
   Deleted. It was ~90 g of phantom G-10 to anything that reads mass off this document.

   **TWO PROCESS FAILURES OF MINE, RECORDED BECAUSE BOTH WILL RECUR.**
   - **Catching a generator's exception defeats Fusion's rollback.** The wrapper used to run
     these scripts caught and printed the traceback, so nothing propagated, so Fusion
     committed the work of two scripts that had FAILED their own verify -- 15 unverified
     components left in the document. `fusion-mcp-gotchas.md` says a raising script is rolled
     back; that is true only if you let it raise. Deleted and re-verified; later runs let it
     propagate.
   - **`body.deleteMe()` on ONE body of a shared BaseFeature destroys ALL of them.** The
     existing note says the SECOND deletion in a loop raises. It is worse than that: NavBay's
     15 bodies are one BaseFeature, and deleting `nose shoulder` alone took the component to
     **0 bodies**. Restored by re-running the generator -- which is only possible because
     every part in this document is generated. **Do not delete individual bodies from a
     multi-body BaseFeature; change the generator and rebuild.**

   **THE FIVE REMAINING INTERFERENCES, and only two are defects.**
   | pair | mm3 | what it is |
   |---|---|---|
   | nose shoulder <-> nose shell | 41594.53 | **duplicate representation.** The sled generator draws the shoulder as context; correction 43 gave the nose an INTEGRAL shoulder. One part, two bodies. Not used by any check (the bore check compares against a number, not this body). Remove it from `make_sled_fusion.py` -- not by deleting the body, see above. |
   | pass-through plate <-> nose aft face | 10425.76 | **known and documented.** Both discs sit at Z 0 because `NoseAftFace` is deliberately unplaced -- correction 38, "a part only, its cavity is unmodelled". |
   | **motor envelope <-> u-bolt 3** | **414.19** | **REAL, and needs a decision.** UBolt3's legs run to Z 599.62; the motor's forward face is at 595.50, so they protrude **4.12 mm** into it. `UBOLT_LEG_STANDOUT = 20 mm` is not padding -- backing plate 3.2 + bulkhead 4.8 + washer 1.6 + M8 nyloc ~8 + two threads ~2.5 = 20.1. There is 11.08 mm aft of the bulkhead and the stack needs 15.2. Options: move the forward bulkhead forward (costs 4.12 of a **+4.63 mm** recovery-bay margin -- nearly all of it), a jam nut plus flush thread (~5.5 mm, loses the nyloc), counterbore the bulkhead for the nuts, or a different anchor at that station. **Not chosen here.** |
   | **nose plate <-> ballast rod** | **90.48** | **REAL.** `pi x 3^2 x 3.2` exactly: the M6 ballast rod passes through the full 3.2 mm of plate and **neither** the context plate nor the real `NoseAftFace` has a central hole -- `NOSE_HOLES` carries one dia 8 feed-through at R 22.598 and nothing on the axis. Same class as the U-bolt holes above. |
   | nose plate <-> nose shell | 1.19 | small, at the context plate's edge against the shell. |

   **WHAT THIS SAYS ABOUT THE PROJECT'S OWN RULE.** Every one of the six was invisible to a
   model that agreed with itself, and five were in parts already written up as finished. The
   two that only appeared after `RecoveryInternalBulkhead` was moved to its real station had
   been reporting a clean **0.0000 mm3** while the part sat at the origin -- *a zero between
   two things that are nowhere near each other is not a pass*, which is the interference-check
   version of correction 40's "volume and mass agreement is not model agreement".

57. **The two real defects correction 56 left open are closed, and the CAD is interference-free
   -- 5 pairs to 1, and the one left is 1.6 microns.** Both were the same shape of problem:
   a part passing through another part that had no hole for it, and a stack of hardware
   nobody had compared to the space behind it.

   **THE NOSE PLATE HAD NO HOLE FOR THE BALLAST ROD.** `design/nose_module.py` says in as
   many words that it "does not size the rod in tension or the nose plate's tapped hole that
   anchors it" -- and nothing else drilled that hole either, so the M6 rod ran through
   3.2 mm of solid G-10. The CAD priced it exactly: **90.48 mm3 = pi x 3^2 x 3.2**, a
   full-diameter rod through a full-thickness plate. `access_bulkhead.hole_layout()` adds it
   now, at NOMINAL rod diameter because the joint is THREADED -- at nominal the rod and the
   tapped hole share a surface, which is what a thread is, and it is the only diameter that
   neither overstates clearance nor reports a false interference. **STATED, NOT SOLVED: the
   hole is ON THE AXIS**, which for a pressure-loaded disc is the point of MAXIMUM bending --
   the opposite of `quiet_radius()`, where every other hole in this vehicle is deliberately
   put. It has to be on the axis, because ballast off the axis moves the CG laterally, which
   is the one thing ballast must not do. `size_access_bulkhead()` never sees this hole, so
   the margin reported for this plate is still the un-holed one.

   **THE U-BOLT STACK WAS A GLOBAL THAT NOTHING COMPARED TO THE SPACE BEHIND IT.**
   `UBOLT_LEG_STANDOUT = 20 mm` -- "through the backing plate, through the bulkhead, a
   washer, a nyloc nut and two threads of stand-out" -- was applied to all four anchors.
   Three have a whole compartment behind them. The fourth stands on the booster's forward
   bulkhead, and what is behind THAT is the motor: `motor_mount.forward_gap` is **11.08 mm**
   against a stack needing **15.20 mm**, so the legs ran **4.12 mm** into it. The U-bolt is
   sized in `recovery_hardware.py`, the gap is computed in `motor_mount.py`, and **no check
   imported one into the other** -- the same shape as correction 42's "two 1.0 cal joints do
   not fit in a 1.60 cal tube".
   Neither part could move: `bulkhead_station = coupler` puts the bulkhead as far forward as
   the recovery-bay joint allows, and the motor is aft-flush against its retainer. So the
   stack had to shrink, and two changes buy 4.7 mm without giving anything up:
   - **NO SEPARATE WASHER.** It exists to spread the nut load into the G-10 backing plate,
     and the plate is nowhere near bearing-limited: **107x with the washer, 24x with the nut
     bearing straight on the plate**, against a 2.0x requirement. It was costing 1.6 mm of
     stack for margin nobody needs.
   - **AN ALL-METAL NUT, NOT A NYLOC.** This nut sits in the sealed gap directly against the
     motor's forward closure, and **a nylon insert is the wrong part there on temperature
     alone** -- so the low-profile all-metal nut is correct here independently of the 2.0 mm
     it saves. One thread of stand-out instead of two, still inspectable.
   `UBOLT_LEG_STANDOUT` is now a derived `leg_standout()` and `UBolt` carries it per anchor;
   the booster's is **15.30 mm**, leaving **0.58 mm** spare. **And the missing check exists**:
   `check_recovery_hardware()` compares the stack against `booster_forward_gap`, which is
   carried ON THE RESULT rather than recomputed -- the first version reached for it through
   `r.evaluation`, which does not exist, inside a `try/except` that swallowed the
   `AttributeError` and reported a clean pass. **A check that silently skips itself is the
   exact failure this correction is about**, written accidentally while fixing it. Verified
   the other way too: restoring the 20 mm stack makes it fail with the right number.

   **TWO SUPERSEDED CONTEXT BODIES REMOVED, AND ONE REAL PART FINALLY PLACED.**
   `make_sled_fusion.py` drew a `nose shoulder` and a `nose plate` as simplified stand-ins so
   the sled could be checked against the bore it has to pass. Both have since become real
   parts drawn from their own models, and the document was carrying each twice: the shoulder
   is INTEGRAL to the nose shell as of correction 43 and that copy sat **100% inside it**
   (41594.53 mm3, ~77 g of phantom G-10), and the plate is `NoseAftFace` -- whose copy was a
   plain disc with **no holes at all**, which is why the ballast rod hit it while the real
   part sat unplaced at the origin. Both removed at the generator. `NoseAftFace` is placed
   now, aft face at **Z -127.04**, derived from the same bulkhead-allowance-plus-sled-assembly
   arithmetic `make_sled_fusion.py` uses for the tube rather than typed.

   **WHAT IS LEFT IS 1.1936 mm3, AND IT IS 1.6 MICRONS.** One pair: the nose plate's OD
   against the nose shell's shoulder bore, a full ring at R 37.400 spanning the plate's whole
   thickness. `1.1936 / (2 pi x 37.4 x 3.2)` = **0.0016 mm of radial overlap** between two
   parts that are SUPPOSED to touch, built from two different nominal chains to the same
   37.400. Correction 40 called this class "parity and the right bar"; the volume is larger
   than that session's slivers but the dimension that means anything is radial, and it is
   under two microns.

   **A CAVEAT WORTH CARRYING: the internal bulkhead's placement did not survive a rebuild
   elsewhere in the document.** `RecoveryInternalBulkhead` is built at a local origin by
   `make_seal_cad_fusion.py` and translated to its station by
   `make_recovery_bay_cad_fusion.py`; its occurrence transform came back as identity after an
   unrelated batch and had to be re-applied. It survives a save once re-applied. **Re-run the
   recovery-bay placement, and re-check the interference, after any batch that rebuilds
   components** -- an unplaced part reports clean zeros against everything it should be
   touching, which is how correction 56's two worst findings hid in the first place.

58. **CORRECTION 55'S HEADLINE ANSWER IS WRONG, AND THIS FILE'S OWN MODEL SAID SO BEFORE IT
   WAS WRITTEN.** Correction 55 concluded that a wider-range gyro was "the single
   highest-leverage decision left" because `ROLL_COMMAND_CAP_DEG = 2.0` exists only to keep a
   +/-2000 dps part out of saturation, so a +/-4000 dps part would buy back a factor of four
   in roll rate. **The saturation arithmetic is right and the conclusion does not follow.**
   Run `estimation.attitude_error_budget()` at both operating points:

   | | roll rate | RSS attitude error at apogee |
   |---|---|---|
   | ICM-42688-P at the 2 deg cap (as designed) | 558 deg/s | **7.94 deg** |
   | +/-4000 dps part at the 8 deg limit | 2232 deg/s | **62.89 deg** |

   Both are dominated by the SAME term -- **gyro scale factor at roll rate**, 7.86 deg
   against 62.84 deg -- and uncapping multiplies it by 4x from the rate and about 2x again
   from the wider part's looser scale-factor tolerance. **L1 is "hold roll angle", and a
   62.9 deg roll-angle error makes L1 meaningless.** The roll rate that saturates the gyro is
   the same roll rate that drives the dominant error term, so buying range does not buy the
   ability to use it. Uncapped, the wide part is **8x worse** than the capped narrow one.

   **THIS WAS ALREADY WRITTEN DOWN.** `docs/07` finding 4 says scale factor at roll rate
   "leads by an order of magnitude, and it leads because of the same roll rate that made D7's
   gyro line tight -- one root cause, and capping the roll rate is what" fixes it. And
   `GYRO_WIDE`'s own note in `design/estimation.py` says it exists **"to price the 'just buy
   more range' answer to the saturation problem"**. Correction 55 anchored on `docs/06`'s
   saturation table and never ran the budget that was written to answer exactly this. Same
   failure as correction 14's: **a datum was right and the question asked of it was wrong.**

   **WHAT TO DO AT LAYOUT INSTEAD.** Specify a gyro with **SELECTABLE full scale up to
   +/-4000 dps and run it at +/-2000.** What is free before the schematic is the OPTION, not
   the capability: the register write costs nothing, today's resolution and scale-factor
   behaviour are unchanged, and the range is there if the estimator ever earns it. Buying the
   range and USING it is what the table above forbids.

   **AND THE LEVER THAT ACTUALLY MOVES THE DOMINANT TERM IS NOT A PART.** Scale-factor error
   is `tolerance x rate x time`, and the tolerance in the budget is a **datasheet spec
   limit** (0.5%). Measured per unit against a rate table it is nearer 0.05-0.1% -- **5 to 10x
   off the term that is 99% of the budget**, for a calibration procedure and no hardware.
   That, not a part number, is what would let the roll cap lift.

   **THE REAL GAP, AND IT IS THE ONE WORTH CLOSING: `attitude_error_budget()` IS GYRO-ONLY.**
   Every term in it is a gyro mechanism propagating open-loop; there is **no magnetometer
   term at all**. But bounding roll angle is the entire reason D8 put a magnetometer on the
   board -- "roll angle is observed by the magnetometer or by nothing" (`docs/07` finding 3).
   So **62.89 deg is the UNAIDED number, and the aided number does not exist anywhere in this
   project.** Scale-factor error is a DRIFT between absolute references, and a magnetometer
   correcting roll phase bounds it rather than letting it integrate to apogee -- but nothing
   here models that, so how much of the 62.89 survives aiding is unknown. **No gyro decision
   should be taken on the strength of a budget that omits the sensor added specifically to
   fix the axis in question.** Closing that is firmware-adjacent work, not a purchase, and it
   is what actually decides whether `ROLL_COMMAND_CAP_DEG` can move.

   Three claims introduced by correction 55 are corrected in place rather than left to be
   found: its own "THE ANSWER IS A WIDER-RANGE GYRO" section, the State of play bullet above
   it, and the open item this finding put at the top of `docs/06`.

59. **CORRECTION 58'S GAP IS CLOSED -- `design/estimation.py` NOW HAS THE AIDED NUMBER, AND
   CLOSING IT MOVED THE OPEN ITEM RATHER THAN RETIRING IT.** `mag_aided_roll_error()` models
   the mechanism correction 58 described but did not compute: the dominant unaided term,
   gyro scale factor at roll rate, is a RATE error, and an absolute reference (the
   magnetometer) turns a rate error into a bounded lag instead of an open-loop integral, via
   a complementary filter whose time constant `_optimal_tau()` picks to minimise RSS(gyro
   lag, filtered mag noise).

   | | roll rate | UNAIDED (apogee) | AIDED |
   |---|---|---|---|
   | at the 2 deg cap | 558 deg/s | 7.94 deg | **0.08 deg** |
   | at the 8 deg deflection limit | 2232 deg/s | 31.45 deg | **0.12 deg** |

   **The magnetometer does not refine the roll estimate, it IS the roll estimate** -- so
   correction 55's uncapped-gyro comparison, and correction 58's own reversal of it, were
   both run on the wrong instrument for what happens once the sensor everyone agrees is
   load-bearing is actually in the loop. Neither aided total above is sensor noise: the
   MMC5983MA's 0.4 mgauss RMS is worth about 0.1 deg against the roll-resolving field
   component (`B cos(inclination)`, the HORIZONTAL part, 0.21 of 0.50 gauss at 65 deg -- the
   smaller half of the field). Checked, not assumed: `mag_aided_roll_error()` also reports
   `samples_per_rev`, and at the deflection limit it is 16.1 against a 10/rev floor this
   model treats as the aliasing point -- tracked, but only 1.6x margin, now a live
   `check_estimation()` note instead of a computed-and-ignored field.

   **WHAT ACTUALLY LIMITS ROLL ANGLE IS NOT THE SENSOR -- IT IS THE AIRFRAME, AND THIS IS
   THE PART A DATASHEET COMPARISON WOULD MISS.** A disturbance fixed in the body frame
   rotates WITH the vehicle, so it is coherent with the very signal being measured and no
   filter averages it away -- it ADDS to the total instead of RSS'ing into it.
   `required_magnetic_cleanliness()` inverts the budget to the number that actually matters:
   at the deflection limit the airframe may carry **18.0 mgauss** of body-fixed disturbance
   and still meet the 5 deg budget. `wire_field_gauss()` gives that a scale: one servo lead
   at 1 A, 50 mm from the magnetometer, is **40 mgauss** -- over the WHOLE allowance by
   itself, before the battery or the other three servos are counted. A twisted pair cancels
   to first order; an untwisted single-ended run past the sensor does not.

   **So the roll cap no longer waits on a gyro decision or an estimator design -- it waits
   on HARNESS ROUTING, a number nobody has measured.** `docs/07`'s "Still open" bullet --
   "four servos and a battery next to a magnetometer, in an airframe nobody has swung" --
   now has a threshold to swing it against instead of just a warning. `check_estimation()`
   carries all of this as notes (and would carry it as a violation if the budget were
   unreachable even magnetically clean, or if phase tracking fell below the floor); the full
   walkthrough is `scripts/estimation_trade.py`'s "THE GAP CORRECTION 58 FOUND" section.
   Nothing in the vehicle's numbers moved -- this closes an unknown, not a defect.

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

## Step 3 — Freeze the airframe — **CLOSED (Sep 2026), pending the CAD rebuild**

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
