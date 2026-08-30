# Canard module — CAD build sheet

Regenerate the profiles with `python scripts/make_cad_profiles.py`. They are written from
`design/configure.py`, so the CAD cannot drift from the analysis. If a dimension here
disagrees with something you remember, regenerate; do not retype.

## State of play — August 2026

Read this first if you are picking the CAD back up. Progress lives in the Onshape document
(`canard-control module`), not in this file — this is just a pointer to where things stand
so a fresh session doesn't have to re-derive it.

The document now holds **four** elements that matter:

| element | what it is |
|---|---|
| `Part Studio 1` | the module: tube, four canard panels, four shafts. 13 parts |
| `KST X08 Plus` | the **real servo**, built from the datasheet. 3 parts |
| `Canard articulation` (Feature Studio) | `canardDeflection` and `canardHingeConnectors`, source of truth in `cad/canard_articulation.fs` |
| `Assembly 1` | 21 instances: module + four real servos, positioned, grouped |

**THE SERVO IS NO LONGER A BLOCK.** The 23.5 × 8 × 16.8 envelope that stood in for it is
still in Part Studio 1, renamed `OBSOLETE servo envelope …`, and is superseded by real
geometry. Getting the real part in exposed two errors the block could not have shown,
because a bounding box has no output shaft:

- **The output shaft is 6.14 mm from one case end, not centred at 11.75 mm** — 5.61 mm off.
  This file previously flagged the centred assumption as "unconfirmed". It was wrong. The
  drawing dimensions the shaft three times from three datums (6.14 from the case end, 7.64
  from the lug-hole line, 9.14 from the envelope end) and those datums are 1.5 mm apart
  exactly as the 23.50 / 26.50 / 29.50 stack requires, so the reading checks itself.
- **The shaft runs along the 16.8 mm axis**, so a RADIAL output shaft spends 16.8 mm of
  tube radius and stacks only 8 mm around the circumference. Every document here said the
  opposite — "8.0 mm radial, 16.8 mm circumferential" — which points the output shaft
  tangentially and cannot drive a radial hinge. Both orientations fit, so no conclusion
  moved, but the **central void is 21 mm, not the 58 mm the block implied**, and the wiring
  and any pass-through structure have to live in that void. (It is ⌀12.17 now: the servos
  moved 4 mm inboard to make room for the hinge bearing. See "The hinge stack".)

Both numbers now live in `design/packaging.SERVO_GEOMETRY`, read off the manufacturer's
dimensioned drawing, and `check_flat_mount()` takes the orientation from there instead of
guessing it.

**CURRENT as of Aug 2026**, rebuilt for the 35.4° sweep / 0.40 taper. Part Studio 1 has 13
features and 13 parts — the original 11, plus `Canard hinge mate connectors` and
`Canard deflection`, both from the Feature Studio.

**Done**, in feature-tree order: tube (`Extrude 1`, G10/FR4 1850 kg/m³) → `Hinge Plane`, an
offset from Top, now **68.27 mm** → one canard panel, root LE at **37.71 mm**, root 67.49 /
tip 27.0 / sweep 47.90 (`Sketch 2` / `Extrude 2`) → shaft sleeve, **⌀6 mm, R 33.485 →
40.200** on the hinge axis (`Sketch 3` / `Extrude 3`) → the old ⌀ = shaft wall cut, which
still reuses the shaft's own sketch and is now superseded
(`Extrude 4`) → servo envelope block, 23.5×8.0×16.8 mm, mass-tuned to 9 g via a custom
material "Servo mass override (9 g)" at 2849 kg/m³ rather than a direct mass override, since
no such field was found in this Onshape UI (`Sketch 4` / `Extrude 5`) → `Circular pattern 1`,
a FEATURE pattern of `Extrude 2/3/4/5`, 4 instances at 90°, axis on the tube's own circular
edge, **Reapply features ON**.

**Four bugs have been found and fixed in this model. Read them before touching it:**
- `Extrude 4` was cutting **nothing**. It ran blind 2.3 mm from a 37.4 mm offset, which is
  exactly R37.4→R39.7 — precisely coincident with both wall surfaces, so the boolean was
  degenerate ("would result in non-manifold body"), and in its original direction it cut
  *inward into the bore*, through air. It is now **Opposite direction, offset 36 mm, depth
  5 mm**, so it overshoots both faces cleanly. Never let a cut land exactly on a face.
- The circular pattern does **not** carry material assignments to its copies. All nine
  patterned parts had no material and contributed zero mass, so the module read 0.175 kg
  instead of 0.260. Assign material to the copies after every pattern, and check the total.
- **`Sketch 3`'s hinge dimension measured to the circle's TANGENT, not its centre.** It read
  `57.2 mm` while the shaft axis actually sat at 59.700 — off by exactly the 2.5 mm shaft
  radius. The dimension now references `tt9bc77TUdvp.center` and reads the true station.
- **The `Hinge Plane` drove nothing.** `Sketch 3` and `Sketch 4` are built on plane `JEC`,
  not on it, so the datum was decorative — editing its offset moved the plane and no
  geometry. Combined with the bug above, the physical hinge sat at **0.029 of MAC instead
  of 0.200**, which is a 4.4× hinge moment and a **0.82× servo torque margin against a 2.0×
  requirement**. Both sketches are now dimensioned to Z 68.27 directly. The Hinge Plane is
  still not a driving reference — treat it as annotation until someone wires it in.

**Orientation, since it looks wrong and is not:** Top plane is the module's FORWARD face and
+Z runs AFT. Because Onshape draws +Z up, the module renders nose-DOWN. It is correct — the
panel CoM measures Z = 83.307 mm against an analytical 83.310, where a flipped model would
read 59.61 — but it is worth knowing before you mate this into an assembly.

**Loose ends on what's built:**
- The obsolete servo block's radial centering was off by ~0.09 mm. It no longer matters —
  the block is superseded — but the same trap applies to anything else dragged into place
  instead of constrained.
- **Both open fits are CLOSED.** See "The hinge stack" below. They turned out to be one
  problem counted twice, plus a third that neither of them mentioned.

**The hinge is now a mechanism, not a hole.** Both fits that this file carried as open —
the ⌀5.000-on-⌀5.000 wall pass-through and the spline's 0.185 mm of reach — are closed, and
closing them exposed a solid-on-solid clash the sweep had not been asked about: the ⌀5
shaft ran 7.785 mm into the servo case and 3.015 mm into its spline. The servo has moved
4.000 mm inboard, the shaft is a ⌀6 sleeve that stops at its output face, and the wall bore
is a ⌀7.975 bearing seat carrying its own dimension. Full argument and margins under "The
hinge stack" below; model in `design/hinge.py`. **The two items that left open — how the
sleeve meets the panel, and what four bores do to the tube — are closed too**; see "The
root joint" and "The tube at the hinge station".

**The four revolute hinge mates are IN** (Aug 2026), so `Assembly 1` is a mechanism and not
just a pose. `Canard 0 (+X) hinge` … `Canard 3 (-Y) hinge`, each pairing `tube{n}` with
`shaft{n}` from `canardHingeConnectors`, REVOLUTE, limited to ±8°. Mass and CoM did not
move (258.650 g, Z 75.122 mm), which is the check that the connectors really were
coincident — mating two connectors that are not coincident drags the geometry.

They were added **in the browser**, because the assembly-feature API still will not create
them. The useful discovery is that the restriction is on CREATION only: once the mates
existed, `POST /assemblies/.../features/featureid/{fid}` renamed all four from
`Revolute 1..4` without complaint. So the API can maintain a mate whose connector query
already resolves; it just cannot author that query. If these ever need rebuilding, expect
to place them by hand and script everything after.

In the UI the recipe is: expand `Canard module tube` in the instance list (its four mate
connectors are in quadrant order 0,1,2,3 — the status bar confirms it, the first reads
X 34.800 / Y 0.000 / Z 68.270), click the tube connector, ctrl/cmd-click the matching
`Canard shaft n` connector, check that the status bar reads **Min dist 0.000 mm**, then hit
Revolute. Tick Limits and enter −8 deg, **Tab**, 8 deg — clicking between the two limit
fields lands on the units autocomplete instead, and `Ctrl/Cmd+A` in that dialog clears the
mate connector selection rather than the text.

**Not started**: printed bay (step 6 below) — blocked on picking real bracket hardware,
since a placeholder shell wouldn't tell you anything the mass/interference checks need.
**It is now the only open item in the hinge load path, and it has a number on it**: the
housing collar carries 3.700 mm of the 6.0 mm bearing, and building it takes the bearing
seat from 3.2× to 21.3×. See "The tube at the hinge station" below.
Forward wiring pass-through and aft gas seal are still open. **The four revolute hinge
mates in `Assembly 1` are not in.** The mate connectors they need exist, in pairs on each
hinge axis (`canardHingeConnectors`), and the rigid groups either side of each hinge exist;
and **the mates are now in too** — see above. `scripts/make_module_assembly.py` still
builds everything up to that point; its `revolute()` remains the record of what the API
would not do.

**The interference sweep is RUN.** `python scripts/canard_sweep.py` drives the deflection
through ±8° and reports clearances; images land in `out/cad/`. The answer is that nothing
fouls, and the reason is structural rather than numerical, which is why the check kept
feeling harder than it was:

- the hinge axis is radial and the shaft is coaxial with it, so the shaft sweeps nothing;
- rotation about the hinge preserves each panel point's distance from the ROCKET axis,
  because that distance is measured **along** the hinge axis. The panel starts outboard of
  the tube and therefore stays outboard at every deflection — worst case 40.228 mm against
  a 39.700 mm tube;
- the servos are entirely inboard of the wall and the panels entirely outboard, so the two
  sets never share a radius. Servo-to-servo gap is 44.1 mm at the seat radius (50.4 before
  the servos moved inboard).

**Read that last bullet again, because it is where the third defect hid.** Servos and
panels never share a radius — true, and irrelevant, because **the SHAFT shares a radius
with both**, and the shaft is what was overlapping the servo. A correct argument about the
wrong two parts. See "The hinge stack" below.

The 0.5 mm root standoff is therefore an assembly allowance, not the swept-clearance
allowance this file described.

## The hinge stack

The two "loose ends" above were closed in August 2026, and closing them turned up a third
defect that neither of them named. All three are the same problem: **between the servo's
output face and the canard panel root there were 3.015 mm of radius, and the airframe wall
took 2.300 of them.** No tolerance callout creates space that is not there.

The third defect. `Canard shaft 0` was a **solid** ⌀5 rod from R 29.400 to R 40.200 — the
API returns 212.058 mm³ against 212.058 for a solid cylinder, so nothing had ever been cut
away for the servo — while the servo's output face sat at R 37.185 with its case running
inboard from there. The shaft and the servo occupied the same space: 3.015 mm of it inside
the output spline, 7.785 mm inside the case. That is a hard clash, not a fit subtlety, and
**the swept interference check did not see it because the sweep asked whether ROTATION
caused a collision and this collision was already there at zero deflection.** The R 29.400
was a leftover: it is the inboard face of the obsolete servo *block*, which the real part
superseded without anything re-examining what had been dimensioned to it.

The decision, and it is one decision rather than three:

| | |
|---|---|
| Servo | moves **4.000 mm inboard**, output face R 37.185 → **R 33.185** |
| Canard shaft | ⌀5 solid rod → **⌀6 sleeve, R 33.485 → 40.200**, with a ⌀4.4 × 3.2 deep 15T spline socket at its inboard end |
| Wall bore | ⌀5.000 → **⌀7.975**, on its own dimension, seating a ⌀6/⌀8 × 6.0 plain bearing |
| Bearing | new. 6.000 long, 2.300 of it in the wall, **3.700 needing a housing collar off the printed bay** |

Why the servo and not the panel. Something had to move: a plain bearing that can carry a
25 N panel load on a 29 mm overhang needs about 4.5 mm of length, because the peak pressure
under an overhung load goes as **1/L²** — a 2.3 mm bushing in the wall is not a slightly
worse answer than a 6 mm one, it is 7× worse, and it fails at 175 MPa against an 80 MPa
allowable. Moving the panel outboard would work and would change frozen aerodynamics.
Moving the servo spends **central void**, which is a budget line. Every band loses the same
8 mm, because the whole servo moves: ⌀20.17 → **⌀12.17** over the 8.2 mm where the cable
bosses sit, and ⌀40.77 → **⌀32.77** over the 29.5 mm alongside the cases. The wiring has to
fit the smaller. 4.000 mm is the largest move the four bosses allow with a millimetre to
spare before they meet on the axis.

**The number that was missing was the panel normal force.** The hinge moment is 0.0599 N·m,
which is why a 9 g servo is enough — the hinge sits 2.4 mm from the panel CP. The same
panel makes **25.4 N** at a bearing 29 mm away, which is **0.734 N·m** of bending where the
shaft leaves the tube. Reading only the hinge moment is how a hinge ends up with no bearing
in it.

Margins on the selected stack, at q = 19.42 kPa and 9.19° of panel local alpha:

| | |
|---|---|
| Bearing peak pressure | 23.2 MPa, **3.4×** against an 80 MPa polymer plain bearing (iglidur G class) |
| Sleeve bending | 34.6 MPa, 8.0× in 6061-T6, 18.9× in steel |
| Spline engagement | 2.900 mm, **91%** of the 3.2 mm spline; sized by the servo's 0.52 N·m **stall** torque, not by the aero moment |
| Socket wall | 0.800 mm — this, not strength, is why the shaft went to ⌀6 |
| Running clearance | +0.030 mm, against **+0.000 before** |

`design/hinge.py` holds the model, `scripts/hinge_report.py` prints it to
`out/hinge_report.txt`, and `scripts/make_hinge_stack.py` applies it to Onshape (idempotent;
every write is followed by a part count, a feature-status sweep and a mass comparison).
Two API facts that cost time and are not in Onshape's documentation, so they are written
down: **there is no assembly interference-check endpoint** (`/interferencecheck` 404s on
v10), which is why the clash had to be found from part bounding boxes and a volume that
matched the analytic solid figure exactly; and **a `mateGroup` freezes its members**, so
the four servos could not be transformed until the five rigid groups were deleted, saved
verbatim, and posted back afterwards. **And the API throttle is PER-ENDPOINT, with a long window.** This is worth knowing before
you plan a CAD session. Onshape's 429 is not only a burst limit: `/partstudios/.../features`
carries its own multi-hour quota, and when it is spent the server answers with a
`Retry-After` measured in hours — **49699 s, just under fourteen**, on 2026-08-30 — while
`/parts/...`, `/assemblies/...`, `/massproperties` and `/shadedviews` all keep working
normally. So a session can lose the ability to read or write the feature tree while still
being able to measure and render everything.

`/features` is the expensive one because it returns the whole tree (161 KB here) and forces
a regeneration, and the scripts call it far more than they need to: `set_quantity()` fetches
it to read a parameter and `verify()` fetches it again to check status, so a single
dimension change costs two full trees. `canard_sweep.py` costs about eight per sweep.
**Caching the tree within a run, and trusting the POST response's own feature state instead
of re-reading, is the fix and has not been done yet.**

`design/onshape.call()` retries 429 and transient 5xx with exponential backoff — safe,
because a 429 means the request was rejected rather than applied, so a retried POST cannot
double-apply — but it **caps `Retry-After` at 300 s** and otherwise fails immediately with
the time the quota returns. A script that honours a fourteen-hour `Retry-After` literally
is indistinguishable from one that is working.

`scripts/baseline.py` now carries a one-line hinge-stack verdict so the fit cannot silently
regress, and the check is exercised against the **as-built** layout as well as the selected
one — it fails the as-built on five counts, which is the only evidence that it checks
anything.

**Two things the model still does not carry, deliberately:**

- The ⌀4.4 spline socket is **not cut** in the Part Studio; the shaft is modelled as its
  ⌀6 envelope. Cutting it needs a boolean scope that reaches the four patterned shaft
  bodies without also drilling the four obsolete servo blocks, which is not worth the
  risk to a working tree for a feature that changes no mass and no clearance. The socket
  is a manufacturing dimension, carried here and in `out/hinge_report.txt`.
- **The tang and its slot are not modelled either.** Same reasoning as the spline socket
  above: they are manufacturing dimensions, they change no mass and no clearance, and
  cutting them needs a boolean scope that reaches four patterned bodies without touching
  the four obsolete servo blocks. They are carried in "The root joint" below and in
  `out/hinge_report.txt`. **The panel becoming a laminate is not a CAD change either** —
  the solid is identical — but it *is* a build-sheet change, so it is written up rather
  than left in a script.

**Module mass properties, measured Aug 2026 — from `Assembly 1`, with real servos:**

| | |
|---|---|
| Mass | **0.25865 kg** |
| Volume | 133,510.6 mm³ |
| CoM | X 0, Y 0, **Z 75.122 mm** aft of the module forward face |
| Inertia about CoM | Ixx = Iyy = **581.280** kg·mm², Izz = **604.584** kg·mm² |
| Off-diagonals | zero — the four-fold symmetry check passing |

Measure this on the ASSEMBLY, not Part Studio 1: the servos are no longer in the Part
Studio, so a Part Studio measurement now double-counts the obsolete blocks and misses the
real parts. Against the envelope-block figures the CoM moved 0.95 mm aft and roll inertia
fell 2.2% (626.268 → 612.442), because the real servo's mass sits off its own body centre
and hangs 16.8 mm inboard rather than 8. `design/control.py` carries the new tensor.

Re-measured after the hinge rebuild below: the ⌀6 sleeve, the ⌀7.975 bearing seat and
the 4 mm servo move together cost 1.21 g and took roll inertia down 1.3% (612.442 →
604.584). Neither moved a control conclusion, which is the point of measuring rather than
assuming. The previous figures — 0.259864 kg, Z 75.090, 585.266 / 612.442 — are kept in
`design/control.py` as a comment for exactly that comparison.

That 0.25865 kg is against roughly 0.565 kg in the mass budget, and the gap is real, not an
error: the servo frames, outboard bearings and printed bay are not modelled yet. Re-measure
once they exist.

## The root joint — how the shaft meets the panel

Closed August 2026. This is the item the hinge stack left as "the next real design
decision, in the place the spline coupling used to occupy", and it is the **hard** end of
the load path, not the easy one: every number in the stack gets smaller going inboard,
because the bearing takes the couple out. Going outboard the moment is at its maximum —
**0.721 N·m at the panel root** — and it has to be handed into 3.0 mm of G10.

Four ways to make the joint. Three lose, and it is worth recording why, because two of them
look better than the winner until you price them:

| | |
|---|---|
| **Root boss** — thicken the panel root into a hub, bore it ⌀6 | Needs ~9 mm of local thickness. Panel is 3.0 and its thickness is **frozen aerodynamics**: t/c drives the flutter margin, which the 0.40 taper already spent from 5.42× to 4.46×. Rejected — it moves a frozen number to solve a joint problem |
| **External clevis** — a fork straddling the panel, cross-bolted | Structurally the best of the four and the easiest to build. It also stands proud of the panel surface, at the root, in the fastest flow the panel sees, on all four panels. Rejected on drag, and it invalidates the swept interference check |
| **One piece** — machine shaft and panel from one aluminium billet | The honest structural answer: no joint at all. +38 g per panel, **+154 g on the vehicle**, all of it aft of the CG, on a design that already needs 100 g of nose ballast to satisfy R1. Rejected on mass and CG, not on structure. Revisit if the ballast budget ever grows |
| **Tang in a slot** — the sleeve's end milled to a flat blade, bonded into the panel root | **SELECTED.** Spends no aerodynamics, no mass and no CG. It moves the problem into the one place with room: the *plane* of the panel, 67.5 mm of root chord, rather than its 3.0 mm thickness |

**The selected tang: 1.8 × 11.5 mm, 25.0 mm into the root.** The three numbers are coupled
and none is free:

- **Thickness 1.8** sets the skins at 0.6 mm each. Thicker tang, stronger tang, weaker
  skin — and the skin's stress goes as 1/t², so the trade is sharp. This is the one number
  that did *not* move when the leading-edge constraint turned up, which is why the panel is
  still a 0.6/1.8/0.6 laminate.
- **Width 11.5** is paid for twice. Wider carries more (σ goes as 1/w) but its skin spans
  further, so skin stress *rises* with width — and it pushes the tang's forward corner
  towards the leading edge.
- **Engagement 25.0**, and **this is the one that was wrong twice.** See below.

| | |
|---|---|
| Tang bending | 116.1 MPa — **2.4×** in 6061-T6, 2.1× in 303 stainless, 5.6× in 4140 |
| Skin over the slot | 190.2 MPa — **2.5×** against a 480 MPa flexural allowable |
| **Leading-edge clearance** | **6.71 mm** at the tang tip, against a 5.0 mm minimum |
| Slot bearing | 0.69 MPa from bending, 0.94 MPa from **stall** torque — 392× |
| Bond shear | 0.044 MPa — 793×. The couple is carried in bearing, not in the bond |

### The depth was the expensive axis, not the free one

The first version of this section put the tang at **30 mm** and justified it like this:
*"depth is bought cheaply — slot pressure goes as 1/L², so it improves everything at once
and is paid for nowhere."* Both halves of that are true and it is still the wrong answer,
because it priced the tang against stress and the binding constraint is **geometry**.

**The panel is swept 35.4°.** Its leading edge runs aft **0.71 mm for every mm of span**,
while the tang stays in a fixed axial band about the hinge axis — it has to, being the end
of a shaft that turns about that axis. So every millimetre of depth spends better than half
a millimetre of leading-edge material:

| engagement | material ahead of the tang tip | |
|---|---|---|
| 25.0 mm | **+6.71 mm** | selected |
| 30.0 mm | +1.91 mm | previously selected, on strength alone |
| 32.7 mm | 0.00 mm | the tang reaches the leading edge |
| 40.5 mm | **−5.53 mm** | *what the old 60%-of-chord rule allowed* |

That last row is the point. The depth rule that was supposed to bound this **passed a tang
standing 5.18 mm proud of the panel's leading edge** — not a part with a thin margin, a part
that cannot be made. A rule that admits an unbuildable geometry is worse than no rule,
because it reads like a check.

Both failing cases are kept and exercised by `scripts/hinge_report.py`, which exits
non-zero if either passes: the ⌀6 sleeve butted into a 3 mm panel (fails on *there is no
panel left*), and the 1.8 × 14 × 30 tang — **whose every stress margin is better than the
selected joint's, 2.9× against 2.4×, and which is still not buildable.** That is the only
case in this project that fails on geometry while passing on strength, which is exactly why
it is worth keeping.

### And a datum error under that, which only the CAD caught

The first fix set the tang at 26.5 mm and read **5.50 mm** of leading edge. The real number
was **5.14 mm**, and the difference is a datum:

- `engagement` is measured from the **panel root face**, R 40.200.
- The planform's sweep and semispan are measured from the **theoretical root** — the tube
  surface, R 39.700.

Those differ by the 0.500 mm assembly standoff, and feeding one into the other over-read
the clearance by 0.500 × 0.71. The analysis agreed with itself perfectly; it disagreed with
Onshape, where **panel 0 runs R 40.20 → 107.19, and 107.19 is 39.700 + 67.490, not
40.200 + 67.490.** Reading the real model is what surfaced it.

Everything on the joint is now indexed by **radius**, which is what `HingeStack`'s own
docstring already said to do — *"radius, not distance from the wall, because radius is the
coordinate every one of these parts is actually positioned in"* — and which `RootJoint` had
not been doing. `body_radius` is now a field, and `leading_edge()`, `chord()` and
`trailing_edge()` all take a radius.

The selected 25.0 mm delivers **6.71 mm**, so the joint is no longer sitting 0.14 mm above
its own requirement.

**A second bug fell out of writing the check.** `slot_chord_fraction` divided the engagement
by the **root chord**. The tang reaches along the **span**; the chord is what its *width*
lies along. It returned the right number anyway — `canard_root_cal` and
`canard_semispan_cal` are both 0.85, so both lengths are 67.490 mm — and would have
silently read the wrong dimension the moment either parameter moved. Same class of error as
the sketch that measured to a circle's tangent instead of its centre. Now
`slot_span_fraction`, and the panel planform is passed to `RootJoint` whole so the joint
cannot drift from the aerodynamics.

Two things to carry into the build, both of which fall out of the model rather than out of
anyone's judgement:

- **The round-to-flat transition steps the stress up 3.4×, at the maximum-moment station.**
  Blend it. Do not shoulder it.
- **THE PANEL STOPS BEING A PLATE.** A 1.8 mm slot 25 mm deep into the edge of a 3.0 mm
  plate is a **14:1 blind cut**, which is not a thing you machine. The panel is built as a
  **0.6 / 1.8 / 0.6 mm bonded G10 laminate** with the core cut away where the tang goes.
  Same thickness, same planform, same mass, same aerodynamics — a manufacturing change, not
  a design one, and the real answer to "how does the shaft meet the panel" turned out to be
  "the panel is made differently."

The check is exercised against the obvious joint too — the ⌀6 sleeve simply entering the
panel — where it fails on *there is no panel left*. Same principle as `as_built`: a check
that has never failed is not evidence of anything.

Model in `design/hinge.py` (`RootJoint`, `root_joint_loads`, `check_root_joint`);
`scripts/hinge_report.py` prints it; `scripts/baseline.py` carries the verdict.

## The tube at the hinge station — four bores at one station

`check_hinge_stack()` has emitted *"the wall bore is ⌀7.97 mm in a 2.3 mm wall — check the
tube, not just the hinge"* since the hinge stack went in, and until August 2026 nothing had.
It is the same shape of gap the hinge stack itself was written for: **the bore was sized
against the bearing, and nobody asked what four of them do to the tube.**

Four ⌀7.975 bores at one station take **13.2% of the circumference** of a 79.4 × 2.3 tube —
557.1 mm² gross down to 483.7 mm² net, 52.6 mm of ligament between adjacent bores.

Loads, from three different flight conditions and deliberately **not** combined — the
vehicle is not doing all three at once, and the margins are wide enough that the question
does not arise:

| | |
|---|---|
| Axial | **143.6 N** at t = 2.47 s: 1.229 kg forward of the station at 7.24 g, plus 56 N of drag |
| Bending | **0.999 N·m** at max q, free body forward of the station **with inertial relief** |
| Torsion | **6.965 N·m** at a full roll command: four panels × 25.4 N at R 68.6 mm |

| margin | |
|---|---|
| **bearing seat crush** | **3.2×** |
| press-fit hoop | 29.9× |
| net section (compression + bending, Kt = 3.0) | 255.8× |
| torsional shear | 348.0× |
| shell buckling | 434.1× |

**The tube is fine, and it is not close** — by two to three orders of magnitude on every
margin except one. The interesting result is the exception.

**The bearing seat is the tightest thing at this station, and only because the housing
collar does not exist.** The bearing hands its couple to whatever holds it, and 3.700 mm of
its 6.0 mm sits inboard of the tube ID. With no collar, the 2.3 mm wall holds it alone:
**116.2 MPa, 3.2×**. With the collar, the full 6.0 mm carries it: **17.4 MPa, 21.3×**. The
peak pressure goes as 1/L², so the two answers are a factor of **6.7×** apart, and that gap
is the whole argument for building the collar. It is still blocked on bracket hardware
(step 6) — but it is now blocked on something with a number attached.

Two honest caveats, both stated in `design/materials.py` rather than buried:

- **The allowables are NEMA G-10 / FR-4 *sheet* properties, and a filament-wound airframe
  tube is not sheet.** A ±45° wind is stiffer in torsion and weaker in axial; a rolled or
  pultruded tube is different again. The project has only ever committed to one material
  fact, the 1850 kg/m³ density in `configure.py`. The convention adopted: **if a margin
  lands under 4×, stop and get the real tube datasheet.** The bearing seat at 3.2× is under
  that line, and the report says so.
- **Global airframe beam bending under a gust is not modelled** — here or anywhere in the
  project; this is the first structural model it has. The free body runs at the **trim**
  condition the trajectory actually flies, not at a certification gust case.
  `check_cut_station()` takes a `gust_factor` so a reviewer can scale it without editing
  the load path.

Model in `design/tube_section.py`, allowables in `design/materials.py`,
printed by `scripts/hinge_report.py`, verdict carried in `scripts/baseline.py`.

## Drawing 1 — the Step 3 dimensioned drawing

**THE DRAWING IS NOW STALE, AND IT WILL NOT TELL YOU SO.** Its axial view shows the servo
blocks against the inner wall in the OLD orientation — 8 mm radial, 16.8 mm circumferential
— which is the arrangement the datasheet says cannot drive a radial hinge. Press
*Update from this workspace* (ctrl+q) before reading anything off it, and redraw the axial
view against the real servo before the drawing is issued.

It is staler than that now. Since the hinge stack went in, the axial view is also wrong
about the shaft (⌀5 → **⌀6**, and it starts at R 33.485 rather than R 29.400), the wall
bore (⌀5.000 → **⌀7.975**) and the servo seat (R 37.185 → **R 33.185**). The three
dimensions actually placed on the drawing — 142.9, 37.71 and ⌀79.4 — are all panel and
tube geometry and have not moved, so nothing already dimensioned is wrong; it is the views
that lie. Redraw the axial view, then dimension the hinge stack off the table above.

**Where it stands.** ISO A3, first-angle, 1:2, metric title block. Two orthographic views:
a front view carrying the planform and every axial dimension, and a projected axial view
showing the 4x pattern at 90 degrees with the servo blocks against the inner wall. Three
dimensions placed and verified against the model: **142.9** (module length), **37.71**
(root LE from the forward face) and **diameter 79.4**.

**Two things about Onshape drawings that cost time here, so they are written down:**

- **Drawings do NOT auto-update.** After the model was corrected the drawing kept showing
  the old geometry and the old numbers, with no banner. The tell is the circular-arrow
  button in the toolbar turning orange — *"Update from this workspace (ctrl+q)"*. Press it
  after every model change, or every dimension you read is a lie.
- **Where you click to place a dimension decides its type.** Click *between* the two picked
  points and you get the distance along the view; click outside them and you get the
  perpendicular one, which is usually 0. And the placement click must land OUTSIDE the
  view's bounding box or Onshape reads it as selecting the view and silently cancels.

**Dimensions still to place.** The values are regenerated from `design/configure.py`, so
they cannot drift from the analysis. Each is a two-pick plus a placement:

| dimension | mm | view |
|---|---|---|
| tube OD | 79.40 | axial — DONE |
| tube ID | 74.80 | axial |
| canard spacing | 90.00 deg x 4 | axial |
| overall span across canards | 214.38 | axial |
| module length | 142.92 | front — DONE |
| root LE, from fwd face | 37.71 | front — DONE |
| **hinge axis, from fwd face** | **68.27** | front |
| root TE, from fwd face | 105.20 | front |
| root chord | 67.49 | front |
| tip chord | 27.00 | front |
| LE sweep, axial offset | 47.90 | front |
| panel height, as cut | 66.99 | front |
| panel root face radius | 40.20 | front |
| panel thickness | 3.00 | front |

Two notes for whoever finishes it. Label which end is the **forward face** — the model runs
nose-down, because Top is the forward face and +Z runs aft. And mark the panel CP as
**reference only**: it is an aerodynamic station, not a machining feature, and the whole
point of the geometry is that the hinge sits 2.5 mm forward of it.

The remaining dimensions need picks on geometry that is 0.5 mm apart — the panel root now
stands 0.5 mm proud of the tube — which is under a pixel at the working zoom. That is a
job for a mouse, not for automation.

## Why model this before the rest of the rocket

Three reasons, in order of value:

1. **Mass properties — DONE, Aug 2026.** The module's tensor is now measured and wired
   into `design/control.py` as `CANARD_MODULE_CAD`: 0.2599 kg, CoM 74.138 mm aft of the
   module forward face, Ixx = Iyy = 593.524 and Izz = 626.268 kg·mm² about that CoM, all
   off-diagonals zero. It raised the vehicle **roll** inertia 6.5% and dropped pitch 1.4%,
   moving the pitch mode 4.21 → 4.26 Hz and the roll acceleration down about 7%. Roll is
   the axis GV-3 flies, so that 6.5% is the one that matters. The rest of the airframe is
   still the crude estimate below.

   `README.md` flags the inertias as **±30%, "crude analytical
   estimate, measure before tuning gains."** Inertia sets your control bandwidth directly —
   pitch mode is 4.3 Hz and drives the ≥85 Hz loop rate requirement. Onshape computes CG
   and moments of inertia from real geometry with real densities. That is a genuine
   accuracy upgrade to the model, not documentation.
2. **Interference.** `check_flat_mount()` is a 2D arc calculation. It does not know whether
   four servo horns clear each other, or whether a horn sweeps into a bushing boss.
3. **The dimensioned drawing**, which is the last Step 3 deliverable.

The canard module is where all the unverified geometry lives. Model it first; a mistake
here costs an airframe.

## Files

| File | Contents |
|---|---|
| `out/cad/canard_planform.dxf` | Canard panel outline, with the hinge axis and panel CP marked on separate layers |
| `out/cad/aft_fin_planform.dxf` | Aft fin outline including a 12 mm through-wall tab |
| `out/cad/canard_bay_section.dxf` | Bay cross-section: tube OD/ID, four servo footprints, shaft locations |

DXF R12, millimetres. In Onshape: **Insert → DXF/DWG** into a sketch, or import the file to
the document and derive it. Layers come through, so you can delete `HINGE` and `PANEL_CP`
once you have used them for reference.

## Dimensions

### Module

| | |
|---|---|
| Station | 444.6 → 587.6 mm from the nose tip |
| Length | 142.9 mm |
| Outside diameter | 79.4 mm |
| Inside diameter | 74.8 mm |
| Wall | 2.3 mm |

### Canard panels — 4 off, 90° apart, interdigitated 45° from the aft fins

| | |
|---|---|
| Root chord | 67.5 mm |
| Tip chord | 27.0 mm |
| Exposed semispan | 67.5 mm (aerodynamic, from the tube surface R 39.7) |
| Panel root face | **R 40.2** — 0.5 mm proud of the tube, for rotation clearance |
| Panel height, as cut | **66.99 mm** (R 40.2 → R 107.19) |
| Sweep, LE | 47.9 mm (35.4°, matching the aft fins) |
| Thickness | 3.0 mm |
| Root LE position | 37.7 mm aft of the module's forward end |
| Root chord spans | 37.7 → 105.2 mm within the module |
| **Hinge axis** | **68.3 mm from the module forward end**, i.e. 30.6 mm aft of the root LE |
| Panel CP (reference) | 33.1 mm aft of the root LE |

The hinge sits **forward** of the panel CP. That is what makes the panel weakly
self-centring rather than divergent, and getting it the wrong way round is a real failure
mode — see `00-requirements.md` §4.4. The hinge is a straight radial axis at a fixed
station, not a constant-percentage line.

### Canard hinge stack — 4 off, on the hinge axis

Derived in `design/hinge.py`; regenerate with `python scripts/hinge_report.py`, do not
retype. Radii from the rocket axis.

| | |
|---|---|
| Servo output face | R 33.185 |
| Spline | R 33.185 → 36.385 (⌀4, 15T) |
| Shaft sleeve | R 33.485 → 40.200, **⌀6** OD, 6.715 long |
| Spline socket in the sleeve | ⌀4.4 × 3.2 deep from the inboard end; 2.900 mm engaged, 91% |
| Bearing | R 33.700 → 39.700, ⌀6 ID / ⌀8 OD, 6.000 long, plain, polymer |
| Housing collar (printed bay) | R 33.700 → 37.400, ⌀12 OD × 3.700 — **a requirement, not a detail** |
| Wall bore | **⌀7.975 H7** through the 2.3 mm wall, −0.025 mm on the bearing OD |
| Running clearance | +0.030 mm diametral, journal in bearing |
| Panel root face | R 40.200 |


### Servos — KST X08 Plus V6.0, 4 off

Datasheet KST_0012 rev 2025-04. Everything here is off the dimensioned drawing and lives in
`design/packaging.SERVO_GEOMETRY`; do not retype it.

| | |
|---|---|
| Case | 23.5 × 8.0 × 16.8 mm ±0.2 |
| Envelope with lugs | 29.5 mm long; lug holes 4 × ⌀1.5 on 26.5 × 5.0, plus 2 × ⌀2 |
| Lug plane | 5.25 mm below the case top face; flange ~1 mm |
| **Output shaft axis** | along the **16.8 mm** dimension, out of the 23.5 × 8 face |
| **Shaft position** | **6.14 mm from one case end** — 5.61 mm off the body centre |
| Spline | 15T, ⌀4 mm, standing 3.20 mm proud of the case top face (8.45 above the lug plane); horn retained by M2 |
| Below the top face | 27.10 mm overall including the cable boss |
| Travel | ±60° (±8° of canard uses 13% of it at 1:1) |
| Orientation in the bay | **16.8 mm radial** (the shaft axis), 8.0 mm circumferential, 23.5 mm **along the rocket axis** |
| Mount | Flange against a frame bonded to the inner wall, output face seated at **R 33.185** |
| Bearing | ⌀6/⌀8 × 6.0 plain bearing in the wall carries the panel bending moment; the servo spline takes torque only |

Four servos need 44.0 mm of arc against 144.4 mm available. Packaging is not tight — but
the **central void is ⌀12.17**, over the 8.2 mm axial band where the cable bosses sit, and
⌀32.77 over the 29.5 mm alongside the cases. Those were ⌀20.17 and ⌀40.77 before the servo
moved 4 mm inboard to make room for the hinge bearing, and ⌀58 when the servo was a block
on the wrong axis. That void is what the wiring has to fit through. `design/packaging.check_flat_mount()` reports 17 mm for
the same band because it also budgets a 4 mm frame and 3 mm of clearance — two different
questions, not a disagreement.

The orientation row used to read "8.0 mm radial, 16.8 mm circumferential", which points the
output shaft tangentially and cannot drive a radial hinge. See the state of play above.

## Modelling order

1. **Tube.** Sketch two concentric circles, ⌀79.4 and ⌀74.8, extrude 142.9 mm. Material:
   G10/FR4 fiberglass, 1850 kg/m³ — set this, or mass properties are meaningless.
2. **Datum planes.** One plane at 68.3 mm from the forward face for the hinge axes, and
   four planes at 0°/90°/180°/270° for the panels. Build the first panel and pattern it;
   do not model four panels by hand.
3. **Canard panel.** Import `canard_planform.dxf` onto a plane offset to the tube surface,
   extrude 3.0 mm symmetric. Add the shaft boss on the `HINGE` layer axis.
4. **Shaft and bearing.** Shaft through the wall on the hinge axis. Pocket the wall for the
   bearing seat.
5. ~~**Servo, as a simple block**~~ — **SUPERSEDED, and it is worth knowing why.** This
   step said "do not model the real servo; you only need the envelope and the mass." The
   envelope and the mass were exactly what a servo has in common with a brick, and every
   error in this module came out of the difference. Build the real part
   (`scripts/make_servo_cad.py`, from the manufacturer's dimensioned drawing) in its own
   Part Studio and instance it. A bounding box has no output shaft, so nothing about the
   output shaft can be checked, and three things about it were wrong.
6. **Printed bay.** Build it around the servo blocks. PETG/ASA/CF-nylon, **not PLA**.
   Heat-set inserts, not printed threads. Layer lines perpendicular to the load path.
7. **Circular pattern** the panel/shaft/servo/bay set 4× about the tube axis.

## What to check when you are done

- **Mass properties.** Compare the module's mass against the model: 0.147 kg tube +
  0.142 kg canards + 0.036 kg servos + 0.240 kg shafts/bearings/sled. Then take the
  **moments of inertia** and feed them back — that is the number worth having.
- **Interference. DONE** — `python scripts/canard_sweep.py`. Nothing fouls, and the reason
  is the arrangement rather than the numbers; see the state of play. Note that this design
  has no horn: the drive is direct onto a radial shaft, so the "horn sweep" this line used
  to ask about does not exist. The two FITS a static model could not express — the shaft
  in its ⌀5.000 hole and the spline's 0.185 mm of reach into the panel root — are closed;
  see "The hinge stack". The sweep now reads those stations off the model and compares
  them against `design/hinge.py` instead of printing them, so it can disagree with the CAD.
- **Lug clearance.** Confirm the trimmed-body mounting actually assembles. This is the
  assumption the packaging conclusion rests on.

## Feeding results back

Weighed or CAD-derived masses go into `design/mass.py`; rerun `scripts/robustness.py` and
adjust the nose ballast in response. Measured inertia goes into `design/control.py` — it
will change the pitch mode frequency and therefore the loop rate requirement.

CAD mass properties are much better than the current analytical estimate but they are not a
substitute for weighing the built parts, or for a bifilar pendulum swing test on the
finished vehicle. They shrink the ±30%; they do not close it.
