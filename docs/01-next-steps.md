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
  carries `Canard 0 (+X) hinge` … `Canard 3 (-Y) hinge`, REVOLUTE, ±8°, each pairing
  `tube{n}` with `shaft{n}`. Mass and CoM did not move, which is how you know the paired
  connectors really were coincident.
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

Seventeen corrections are worth knowing about. The first four changed the design; two of the
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
