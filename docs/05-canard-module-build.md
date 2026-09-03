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
| `KST X08 Plus` | the **real servo**, bu1ilt from the datasheet. 3 parts |
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
is a bearing seat carrying its own dimension (⌀7.975 as first built, **⌀8 H7** in the CAD
since Aug 2026 — `make_hinge_stack.py --bore` corrects it in place rather than skipping it,
because a step that silently declines to apply a design change is how the CAD and the
analysis drift apart). Full argument and margins under "The
hinge stack" below; model in `design/hinge.py`. **The two items that left open — how the
sleeve meets the panel, and what four bores do to the tube — are closed too**; see "The
root joint" and "The tube at the hinge station".

**The four revolute hinge mates are IN** (Aug 2026), so `Assembly 1` is a mechanism and not
just a pose. `Canard 0 (+X) hinge` … `Canard 3 (-Y) hinge`, each pairing `tube{n}` with
`shaft{n}` from `canardHingeConnectors`, REVOLUTE. Mass and CoM did not
move (258.650 g, Z 75.122 mm), which is the check that the connectors really were
coincident — mating two connectors that are not coincident drags the geometry.

**They were in and they did not turn, and the mate limits were why** (Sep 2026 — correction
39 in `docs/01`). The four mates carried the ±8° deflection limit, and every attempt to
animate one came back *"Unable to compute any steps for this animation. Unable to apply
transform. Instance(s) may be constrained."* Nothing in the assembly explained it: all 36
instances sit in exactly one rigid group each and the groups do not overlap, only the tube
is fixed (correctly — it is ground), every feature regenerates OK, and both mate connectors
resolve to the right parts. **On these mates a limit does not clamp the rotation, it
abolishes it.** Measured by driving the mate through `POST /matevalues` after each edit and
confirmed against the animation itself:

| `limitsEnabled` | rotation limit | asked | got |
|---|---|---|---|
| false | — | +5° | **+5.000°**, and the animation plays |
| true | −8 … 8° | +5° | 0.000°, frozen — the error above |
| true | −60 … 60° | +5° | 0.000°, frozen |
| true | −360 … 360° | +90° | 0.000°, frozen |
| true | 80 … 100° | +90° | 0.000°, frozen |

So it is **not the width of the limit** and not a pose sitting outside one: a limit generous
enough to allow a full revolution freezes the hinge exactly as hard as ±8° does. It is not
the rigid groups either — suppressing `Canard 0 (+X) rotating group` and retrying changes
nothing. The trigger is `limitsEnabled` itself, on mates whose connectors come from a Part
Studio (`BTMPartStudioMateConnectorQuery`), and it applies to all four identically.

Onshape's own Edit-mate dialog reads and writes `limitAxialZMin/Max` for a revolute's
rotation limits — open the dialog and those are the numbers it shows — so **the browser did
nothing wrong when these were authored**. The other Z pair, `limitZMin/Max`, *is* drivable
with limits enabled but enforces nothing (driven to +12° against a ±8° limit without
complaint), so putting the deflection limit there would leave the Limits box ticked over a
limit that does not exist. This project has enough of those.

**Fixed by turning the mate limits off**, with `scripts/fix_hinge_mate_limits.py` (safe to
re-run; `--verify` drives all four and parks them at zero). The limit was never load
bearing: no script has ever read it, `scripts/canard_sweep.py` drives the Part Studio's
`deflection` parameter rather than the assembly mates, and the number that every analysis
actually reads is `DEFLECTION_LIMIT_DEG` in `design/configure.py`. What is lost is a
hand-drag guard in the browser; what is gained is the mechanism the assembly exists to
demonstrate. Mass 356.393 g and CoM Z 78.183 mm across the write, unchanged to the microgram
— a limit is not a pose.

**If you re-author these mates by hand, leave Limits unticked**, or the assembly goes back
to being a pose.

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

**Printed bay**: BUILT (Aug 2026) — see "The printed bay" below. It was previously recorded
as blocked, then as unblocked; it is now geometry. What follows is the note from when it was
unblocked, kept because the collar argument in it is still the reason the part exists.

 It was held on "picking real bracket
hardware"; the bracket turned out not to be needed — see docs/04 on why the commercial servo
frames were dropped — and the bay is printable now. **It is the last open item in the hinge
load path and it has a number on it**: the housing collar carries 3.700 mm of the 6.0 mm
bearing, worth **3.4× → 14.5×** on the bearing seat. See "How this actually gets built"
and "The printed bay".
The aft gas seal is SIZED as of Aug 2026 (see "The aft gas seal" below); the forward wiring
pass-through is still open as geometry, and it is the module's vent. The mate connectors the hinges
need exist in pairs on each hinge axis (`canardHingeConnectors`), the rigid groups either
side of each hinge exist, and **the mates are in** — see above.
`scripts/make_module_assembly.py` still
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
| Canard shaft | ⌀5 solid rod → **⌀6 sleeve, R 33.485 → 40.200**, with a ⌀4.4 × 3.2 deep 15T spline socket at its inboard end. **The socket is superseded** — buy a splined servo horn instead, see "How this actually gets built" |
| Wall bore | ⌀5.000 → **⌀7.975**, on its own dimension, seating a ⌀6/⌀8 × 6.0 plain bearing. **⌀7.975 is superseded by ⌀8 H7**, same reason: it is not a reamer that exists |
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
panel makes **25.3 N** at a bearing 29 mm away, which is **0.718 N·m** of bending where the
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
Four API facts that cost time and are not in Onshape's documentation, so they are written
down. **An assembly feature id can contain a `/`** — `MwVg60P6xoYjGb/Tu` is one of the
rigid groups — so it must be percent-encoded into the `/features/featureid/{fid}` path or
the call 404s while looking exactly like a feature that is not there. **A limit parameter
that is UNSET reads back from `GET /features` as a non-null zero**, so the obvious round
trip — read a mate, change one thing, post it back — rewrites every unset limit as a hard
value; anything editing a mate should set what it means and null the rest. Then:
**there is no assembly interference-check endpoint** (`/interferencecheck` 404s on
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

- The ⌀4.4 spline socket is **not cut** in the Part Studio, and is now superseded by a
  bought servo horn anyway; the shaft is modelled as its
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

Re-measured after the hinge rebuild below: the ⌀6 sleeve, the bearing seat and
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

**The selected tang: 1.8 × 11.9 mm, 25.5 mm into the root.** The three numbers are coupled
and none is free:

- **Thickness 1.8** sets the skins at 0.6 mm each. Thicker tang, stronger tang, weaker
  skin — and the skin's stress goes as 1/t², so the trade is sharp. This is the one number
  that did *not* move when the leading-edge constraint turned up, which is why the panel is
  still a laminate.
- **Width 11.9** is paid for twice. Wider carries more (σ goes as 1/w) but its skin spans
  further, so skin stress *rises* with width — and it pushes the tang's forward corner
  towards the leading edge.
- **Engagement 25.5**, and **this is the one that was wrong twice.** See below.

| | |
|---|---|
| Tang bending | 111.7 MPa — **2.5×** in 6061-T6, 2.1× in 303 stainless, 5.9× in 4140 |
| Skin over the slot | 195.1 MPa — **2.5×** against a 480 MPa flexural allowable |
| **Leading-edge clearance** | **6.15 mm** at the tang tip, against a 5.0 mm minimum |
| Slot bearing | 0.64 MPa from bending, 0.86 MPa from **stall** torque — 428× |
| Bond shear | 0.042 MPa — 841×. The couple is carried in bearing, not in the bond |

### The skin is what survives over the SLOT, not over the tang — and that was a bug

Worth stating on its own, because it was a **failing joint reporting a pass.**
`skin_thickness` was `(panel - tang) / 2`. The slot is the tang plus a 0.1 mm bond line on
each face, so the real skin is `(panel - tang - 2·bond) / 2` — 0.5 mm where the model said
0.6. Skin stress goes as 1/t², so the joint was actually at **1.69× against a 2.0×
requirement** while reporting 2.5×. `RootJoint` now carries `bond_line`, and the skin spans
`slot_width`, not `tang_width`.

It surfaced only because a buyability question forced the stack to be expressed in sheet
thicknesses you can order. Asking "which sheets do I buy" is a different question from
"what dimensions are optimal", and it found something the second question could not.

### The panel is a laminate of two stocked sheets

**0.6 / 2.0 / 0.6 mm bonded G10, 3.2 mm total**, the middle sheet cut away over
12.1 × 25.5 mm at the root. That gap **is** the slot — it never gets machined.

The earlier spec, 0.6 / 1.8 / 0.6, is dead twice over: **1.8 mm G10 is not stocked
anywhere**, and it was the thickness that produced the 1.69× above. Every thickness in the
new stack is a sheet you can order. Check that before changing any of them.

This moved `canard_thickness` **3.0 → 3.2 mm**, which is a frozen parameter changed for a
manufacturing reason, so it is worth being explicit about what it did:

| | |
|---|---|
| canard flutter margin | 4.46× → **4.92×** — thicker t/c, so this improves |
| panel mass | +9 g, at station 0.507 m, which is **forward** of the 0.800 m CG |
| static margin | 2.03–2.52 → **2.04–2.53 cal** — up, because that mass is forward |
| crossrange | 424 → **419 m**, about 1%. This is the honest cost |
| `evaluate()` | still feasible, no violations |

**The alternative was a solid 3.0 mm plate with the slot cut by a slitting saw on a mill.**
It keeps the frozen thickness and needs no bonding, but it lands at 2.1× rather than 2.5×,
and its 0.55 mm skins depend on centring a slot in a 3.0 mm plate to ±0.05 mm — a *setup*
tolerance rather than a *stock* one. The laminate was chosen because a 3D printer makes its
one weakness — holding three layers and a tang in alignment while epoxy cures — into a
printed jig, and because a thickness guaranteed by the sheet beats one guaranteed by a
fixture.

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
| 25.5 mm | **+6.15 mm** | selected |
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
selected joint's and which is still not buildable.** That is the only
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
- **THE PANEL STOPS BEING A PLATE.** A 1.8 mm slot 25.5 mm deep into the edge of a solid
  plate is a **13:1 blind cut**, which is not a thing you machine without a slitting saw. The panel is built as a
  **0.6 / 2.0 / 0.6 mm bonded G10 laminate** with the core cut away where the tang goes.
  Same planform and the same aerodynamics; the thickness goes 3.0 → 3.2 because a laminate
  can only be a sum of sheets that are sold, and that is priced in "The panel is a laminate
  of two stocked sheets" above. The real answer to "how does the shaft meet the panel"
  turned out to be "the panel is made differently."

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

## How this actually gets built

Added August 2026, once it was established that parts get **bought** and the shop is a 3D
printer rather than a machine shop. Every dimension above is reachable that way, but only
in a particular order, and the order is the part that is easy to get wrong.

**One custom-machined part in the whole module.** The canard shaft: a ⌀6 6061-T6 rod,
32.2 mm long, with a 1.8 × 11.9 × 25.5 mm blade milled on one end. Everything else is
bought or printed. If that goes to a shop, it is one drawing and four identical parts.

**Do not cut the servo spline — cast it.** The shaft's inboard end carries a **⌀4.100 ×
3.20 mm plain drilled socket**, not a broached one. Fill it with anaerobic retaining
compound and push it onto the servo spline: the compound cures in the tooth valleys and
*becomes* the female spline. Fifteen keys, formed by the part they mate with.

An earlier revision of this file said to buy a ⌀4 mm 15T horn instead. **That does not
fit** — there is 0.515 mm between the servo's output face and the bearing, and outboard of
that everything passes down the ⌀6 journal; every female-spline part sold is ⌀7 or larger.
See docs/04 "The coupling" and docs/01 correction 21.

Either way the reasoning that made broaching avoidable still holds: **the coupling carries
torque only**, 0.520 N·m at servo stall, because the bearing sits outboard of it and takes
every bit of the bending. Prime the bore — 6061 is passive and anaerobics need an activator
on it, while the steel spline cures on its own.

**Ream the bearing seat AFTER the printed bay is bonded in.** This is the one that will bite
if it is done in the obvious order. The bearing is 6.0 mm long, the tube wall is 2.3 mm of
it, and a collar on the printed bay carries the other **3.700 mm**. Those two bores must be
concentric — if they are not, the bearing is pinched and the hinge binds, which is a
mechanism failure rather than a stress one and no margin in this document protects against
it. So:

1. Print the bay with the collar bore **undersize**, about ⌀7.5. FDM holes come out
   undersize and rough anyway; do not fight it.
2. Bond the bay into the tube.
3. Run a **⌀8 H7 chucking reamer** through the wall and the collar **in one pass**.

Concentricity is then a property of the operation instead of a tolerance held across two
parts made by different processes. This is also why the seat is ⌀8 H7 and not the ⌀7.975 it
was first specified as: ⌀7.975 is not a reamer that exists, and the interference a pressed
bushing needs comes from the bushing being supplied oversize, not from undersizing the hole.

**That collar is the best-value part in the module.** It is worth **3.2× → 21.3×** on the
bearing seat, because peak pressure under an overhung load goes as 1/L² and the collar more
than doubles L. The printed bay was previously recorded as "blocked on picking real bracket
hardware"; it is not blocked any more, and this is the reason to build it.

**Bond the panels in a printed jig.** The laminate's whole advantage is that skin thickness
is set by the sheet rather than by a machine setup — but only if the three layers and the
tang stay put while the epoxy cures. A printed fixture that clamps the stack flat and
locates the tang on the hinge axis at the correct chordwise station costs an hour of print
time and removes the only real risk in the approach. Keep epoxy off the ⌀6 journal; that
surface has to turn in the bearing.

**Still unmodelled, deliberately:** the panel bonding jig. The aft gas seal was on this list
until Aug 2026 and is now sized -- geometry still to draw. The bay and
its collar were on this list until Aug 2026 and are now real geometry — see "The printed
bay" below. The bought servo horn is off the list for a different reason: it does not fit.

That last paragraph used to end "when the bay is drawn, the collar has to be checked against
the bearing". It was drawn, the check was run, and it found a **servo-flange clash** that no
amount of reading the numbers would have shown. Modelling the bearing as a solid rather than
a dimension is what made that check possible.

## The printed bay

Added August 2026. Model in `design/bay.py`, argument in `out/bay_report.txt` (regenerate
with `python scripts/bay_report.py`), geometry in `cad/canard_bay.fs`, built by
`python scripts/make_bay_cad.py --apply --assemble`. **One printed part, PETG-CF, 39 g**,
plus eight small retainer bars.

It does two jobs. It puts each servo's output spline on its hinge axis, and it carries the
inboard **3.700 mm** of each bearing — the half of the seat the 2.3 mm airframe wall cannot
reach.

### The collar is worth 3.4× → 14.5×, and the number it replaces was 21.3×

The bearing seat is **two materials**: 2.300 mm of G10 wall outboard, 3.700 mm of printed
polymer inboard. Every document in this project priced the collar by putting the whole
6.0 mm into `p = 6M/(dL²) + N/(dL)`, which is the formula for one material.

A rigid pin in an elastic housing shares its couple out **by stiffness, not by length**. G10
is 18 GPa; PETG is 1.7. Make the collar soft and it moves aside — the load walks back into
the G10 and the effective seat shortens toward the bare wall. Length is necessary and it is
not sufficient.

| collar | E, GPa | peak in the collar | peak in the wall | wall margin | effective seat |
|---|---|---|---|---|---|
| none | — | — | 109.0 MPa | 3.4× | 2.37 mm |
| PETG | 1.7 | 9.7 MPa | 37.1 MPa | 10.0× | 4.08 mm |
| ASA | 2.0 | 10.1 MPa | 34.6 MPa | 10.7× | 4.22 mm |
| **PETG-CF** | **4.5** | **11.9 MPa** | **25.5 MPa** | **14.5×** | **4.93 mm** |
| PA6-CF | 6.0 | 12.6 MPa | 23.3 MPa | 15.9× | 5.17 mm |
| *as stiff as G10* | *18.0* | *16.3 MPa* | *17.3 MPa* | *21.4×* | *6.00 mm* |

`design/bay.py` models this as a Winkler foundation with a piecewise modulus and asserts
that it reduces to the single-material formula when both materials match. **Build the
collar** — 3.4× → 14.5× is still the largest margin improvement anywhere in this hinge — but
choose the filament on **stiffness**. Every candidate is strong enough; they differ in how
much of the collar's benefit they deliver. Plain PETG passes if there is no hardened nozzle.

### Layout

| | |
|---|---|
| Shell | ⌀74.500 × 2.400 wall, Z 53.129 → 94.629 (41.5 long). 0.150 mm radial epoxy gap to the ⌀74.8 tube ID |
| Collars, 4 off | ⌀12 boss on each hinge axis, standing 1.150 mm proud of the shell bore, bore printed **⌀7.5** |
| Servo trays, 4 off | flange face R 27.935, back face R 31.935, 15.0 wide, Z 59.129 → 88.629 |
| Servo window | 24.100 × 8.600 through the tray — clears the **case** |
| Flange relief | 8.600 wide over the full 29.5 lug envelope, R 26.935 → 27.935 — clears the **flange** |
| Clamp inserts | 8 × M2 heat-set, ⌀3.2 × 4.0, at Y ±6.0 on two rows per servo |
| Retainer bars | dog bone: 2.6 mm bridge × 8.6 wide across the flange, 4.7 mm pads out to 18.4 wide at the screws, 1.5 thick. Two per servo, 2× M2 each |
| Collar bore, in the CAD | **⌀8.000 as reamed** — the assembly is the vehicle that flies, and it has been reamed. ⌀7.500 is the print size |

The frame is the module Part Studio's own — origin on the rocket axis, Z 0 at the tube's
forward face — so the bay drops into `Assembly 1` at **identity**. No transform to compute
and none to get wrong.

### The servo is clamped, not screwed through its flange

The obvious mounting is the servo's own four M1.4 screws. The geometry rules it out: the lug
holes sit 1.5 mm beyond the ends of the case, the window has to clear the case, and what is
left between a lug screw and the window edge is a **0.62 mm ligament** — a perimeter and a
half, which a slicer may simply not fill. The servo's reaction torque does not go through
that ligament (it pushes along Y, into 5 mm of tray), so this is a printability problem, not
a strength one. But "there may or may not be material there" is not a thing to build on.

So the flange is clamped by a printed bar at each end, 2× M2 into heat-set inserts at
Y ±6.0, well clear of the 8 mm case. Three things come free: the marginal feature stops
existing, the fastener becomes a size that is buyable and takes an insert, and **a servo can
be changed after the bay is bonded in** — which matters, because the bay never comes out.

The servo's two ⌀2.0 flange holes are left empty. Their function is not labelled on the KST
drawing (see `design/packaging.py`), so nothing here depends on a guess about them.

### The clash the CAD found

The clamp bosses and the servo's own flange both wanted R 26.935 → 27.935. Invisible in an
end-on view, because the tray hides it. Fixed by relieving the flange over the full lug
envelope; `design/bay.py` now prints a clearance table on every run so it cannot come back:

| | |
|---|---|
| servo case vs window | +0.300 each side, +0.300 each end |
| retainer bridge vs case, in Z | +0.200 each end — the bar is a **dog bone**: 2.6 mm across the flange, 4.7 mm at the screws |
| collar boss rim vs tube bore | +1.544 radial — checked on **radius**, `hypot(reach, OD/2)`, not on the bounding box |
| servo flange vs relief | +0.300 each side |
| servo top face vs collar | +0.515 radial |
| servo top face vs shell bore | +1.665 radial |
| spline tip vs shell OD | +0.865 radial, inside the collar bore |
| shaft vs printed collar bore | +0.750 radial, before reaming |

### What is still open

**The coupling — CLOSED, Aug 2026.** This section carried it as open on the strength of
correction 19: there is 0.515 mm between the servo's output face and the bearing, and no
bought 15T ⌀4 horn hub is under ⌀7.4 × 4 mm. The way out was neither cutting a spline nor
buying one — **cast it**, in anaerobic retaining compound, in a plain ⌀4.100 × 3.20 drilled
socket. See docs/01 correction 21 and `design/hinge.py`. Cut in the CAD.

**The aft gas seal — SIZED AND BUILT, Aug 2026.** `design/seal.py`, `scripts/seal_report.py`,
verdict in `scripts/baseline.py`. See "The aft gas seal" below. It is a **G-10 disc, 4.8 mm,
38.4 g**, and it is not the part this heading described. Now real geometry:
`scripts/make_bulkhead_cad.py` builds it, `scripts/place_bulkhead.py` instances it in
`Assembly 1` at Z = 142.900, and **Check interference reports none across all 35 instances**
— with the caveat in docs/01 correction 34, because a ⌀74.8 disc in a ⌀74.8 bore could not
have reported one.

**The forward wiring pass-through — DECIDED, Aug 2026.** Still open as *geometry* (no hole
is drawn) but no longer an open decision: it is a wire route and is **potted solid**. It is
not the module's vent — the module vents through its own wall, 2 × ⌀2 mm. See "The vent path"
below, which corrects what this document said first.

## The aft gas seal

Added August 2026. Model in `design/seal.py`, argument in `out/seal_report.txt`
(regenerate with `python scripts/seal_report.py --write`), verdict carried by
`scripts/baseline.py` so it cannot silently regress.

**It is not a gasket, and calling it one for six months is why it was never sized.** The
heading above described a part whose job is to be gas-tight. Its actual job is to be the
**piston the ejection charge pushes on to separate the airframe**, and then the **anchor the
main parachute pulls on when it opens**. Gas tightness is its third requirement. This is
correction 2 and correction 11 again — a part named after its smallest load, sized against
the number in its name.

### What it carries

| | |
|---|---|
| bore, and so the piston area | ⌀74.8 mm, **4394 mm²** |
| forward compartment (holds the main) | 1041.5 cm³ geometric, **156.2 cm³ free** — 15%, the rest is canopy |
| shear pins | 3 × 2-56 nylon, 441 N, + 100 N of friction allowance |
| joint releases at | **123 kPa** (17.9 psi) |
| black powder charge | **1.17 g**, sized on the geometric volume at a 2.0× separation factor |
| design case — joint releases | 246 kPa, **1082 N** on the disc |
| **stuck case — same charge, free volume** | **1642 kPa, 7213 N** |
| main opening shock, through the U-bolt | 768 N at a 1.0 shock factor, **1306 N** at 1.7 |

**The stuck case is what sizes the disc, and the reason is not caution.** The shear pins are
the intended fuse. A bulkhead sized for the pressure that opens the joint is sized for the
day everything works; size it for the whole charge with nothing moving and the pins are
guaranteed to be the first thing that gives. That is the failure you want, and it costs two
sheet sizes and about 23 g.

### The part

**G-10 sheet, 4.8 mm, 39 g**, bonded into the aft end of the module with a fillet either
side. On its aft face: the charge well, a two-pole terminal block, and the harness U-bolt
**with a backing plate**. Feed-through: **2 × ⌀4.0 mm at R 22.6 mm**, potted.

| | |
|---|---|
| plate bending, simply supported | 118 MPa, **4.1×** |
| same, edge clamped | 75 MPa — reported, deliberately **not** used |
| feed-through, Kt 2.0 | 196 MPa, **2.45×** |
| U-bolt point load | 84 MPa, 5.7× |
| glue line | 2.84 MPa, 12.3× |
| centre deflection, stuck case | 1.32 mm (0.20 mm at design pressure) |

**The hole is what sets the thickness.** Size the plate alone and the answer is 4.0 mm,
where the feed-through then runs at **1.70×** against a 2.0× requirement. The feature the
part is *named for* is the one that governs it, and a bulkhead sized as though it were a
bulkhead is not a sized feed-through.

Three modelling choices are worth carrying forward because each one was nearly made the
comfortable way:

- **Simply supported, not clamped.** A disc bonded in with a fillet is between the two and
  they differ by 1.6×. Assuming the fillet into the answer is exactly how correction 15's
  joint reported 2.5× while sitting at 1.69×.
- **Kt 2.0, not 3.0.** 3.0 is the circular hole in a plate under *in-plane tension*. This
  plate is in *bending*, where the classical thin-plate value is about 1.8. Being wrongly
  conservative is not free: at Kt 3.0 the hole sizes the disc at 6.4 mm and the extra sheet
  buys nothing that exists.
- **The hole is placed on one model and checked against the other.** R 22.6 mm is where a
  *clamped* plate's radial stress passes through zero. A *simply supported* plate has no
  such radius, so the placement is free but buys almost nothing — and the margin is quoted
  from the simply supported field. The first version of this report used the clamped field
  for both and printed 15×.
- **Pot the feed-through on the FORWARD face.** RTV is good to about 315 °C and the gas
  leaves the charge at 1837 K. The disc is the heat shield, so the sealant belongs behind
  it. Potting the exposed face gives you a part that passes on the bench and sooties the
  nav bay in flight.

### The vent path — and the first version of this section was wrong

This section used to argue that the module has two faces it could breathe through, that the
aft one is disqualified because the ejection charge fires on the other side of it, and that
the module therefore vents **forward** through the wiring pass-through into the nav bay —
which would put the module inside the altimeter's static volume and make a leak past this
seal a pressure-sensor fault.

Every step of that follows from its premise, and **the premise is false. A bay is a
cylinder, and the third surface is the wall** — which on this module already has four ⌀8 mm
bores through it.

**The module vents overboard: 2 × ⌀2 mm through its own wall.** Then none of the rest
follows. The altimeter's sense volume is the nav bay alone; the wiring pass-through is
**potted solid** around the wires, which is a better seal than one that has to pass air; and
a leak past this disc goes outside instead of into the sensor that fires the charges.

See `design/venting.py` and docs/01 correction 28. The framing failed, not any number, and
"it has two faces and one is disqualified" is the kind of complete-sounding argument nothing
inside it will ever catch.

### Three things this opened — all closed, Aug 2026

1. **The drogue's firing circuit.** This disc closes the *forward* compartment, so the
   main's charge terminates on its aft face, millimetres from where the wires come through.
   The drogue's charge is on the far side of the internal bulkhead, and the only path to it
   is through a compartment packed with the main. The standard high-power answer — an av-bay
   between the two compartments — needs ~60 mm of tube and two more bulkheads against 13.0 mm
   of recovery-bay margin, so it does not fit, which is *why* the altimeter is in the nav bay
   and why this hole is not optional. **Answer: a ⌀5 mm thin-wall conduit bonded along the
   tube wall**, sealed where it crosses both bulkheads. `recovery.add_conduit()` prices it.

   Counting it turned up something bigger. A conduit and a U-bolt are **rigid** — the canopy
   packs *around* them, it does not compress with them — so they take their own volume out of
   the compartment rather than going through the fill limit. `Compartment.hardware` is that
   distinction, and once the conduit and the four U-bolts are in it the recovery bay's margin
   goes **+13.0 → +6.8 mm**. The U-bolts cost more than the conduit: 24 cm³ of envelope
   against 4.7. Still fits.
2. **The internal bulkhead** is now the same model applied a second time —
   `seal.internal_bulkhead_from_evaluation()`. **G-10 4.8 mm, 39 g**, 1 × ⌀6 mm feed-through
   for the conduit, plate 4.0× and feed-through 2.2×. Two things it is worth knowing: it is
   the **only pressure boundary in the vehicle with no fuse** (the aft seal has shear pins
   that go first; this one is bonded at both ends of its load path, so a stuck joint simply
   hands it the whole charge), and both bulkheads see the **same** pressure for a reason that
   has nothing to do with either — docs/01 correction 29.
3. **The nav bay has a packing check now** (`design/avionics.py`) and it does **not** pass:
   152 mm of sled wanted against 103 mm available, 117 mm with the tracker and radio moved to
   the nose. On estimated envelopes, so it is an `evaluate()` warning and not a violation —
   read docs/01 correction 27 and correction 5 before touching geometry.

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

**The Drawings API was tried, and it is not the way — Aug 2026.** Worth recording so
nobody spends the afternoon twice. `POST /drawings/.../modify` with
`onshapeCreateAnnotations` IS enabled on this account and DOES create dimensions; the
schema is in the Onshape memory notes. It fails on three things together. The edge id has
to be the `jsongeometry` **`uniqueId`** and not the `deterministicId` — and even with one
that resolves, plus `snapPointType`, the dimension attaches to the **wrong geometry**
(asked for the 27.00 tip chord, got the 67.49 root chord, from two very different
coordinate inputs). There is **no read-back** — `/annotations`, `/dimensions` and
`/sheets` all 404 — and **no working delete**, so every wrong dimension has to be picked
off by hand in the browser. Nothing in the API says where a view sits on the sheet either.
**Creating without reading back or deleting is iterating blind on the one document the
part gets made from**, so these stay a mouse job, exactly as the note below says.

What the API IS good for here: `GET /drawings/.../views/{viewId}/jsongeometry` returns
every edge with its `uniqueId` and its start/end in metres in the view's own frame. That
is how the table below was checked against the model — the front view really does carry
root LE at 37.71, root TE at 105.20, tip chord 27.00, LE sweep 47.90 and semispan 66.99.

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
| panel thickness | 3.20 | front |

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

Onshape elements, and which script owns each:

| Element | Built by |
|---|---|
| `Part Studio 1` — tube, 4 panels, 4 shafts | `scripts/make_hinge_stack.py`, `cad/canard_articulation.fs` |
| `KST X08 Plus` — case, spline, cable boss | `scripts/make_servo_cad.py` |
| `Hinge bearing (⌀6/8 × 6 plain)` | `scripts/make_bearing_cad.py` |
| `Canard bay (printed)` — bay + retainer bar | `scripts/make_bay_cad.py`, `cad/canard_bay.fs` |
| `Assembly 1` — 34 instances, 5 rigid groups, 4 revolute hinges | `scripts/make_module_assembly.py`, `scripts/place_bearings.py`, `scripts/make_bay_cad.py --assemble`; **the 4 mates were placed by hand** |

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
| Shaft sleeve | R 33.485 → 40.200, **⌀6** OD, 6.715 long, **6061-T6** |
| Spline socket in the sleeve | **⌀4.100 × 3.20 deep** from the inboard end, plain drilled; 2.900 mm engaged, 0.30 mm adhesive reservoir; 0.950 mm wall |
| Bearing | R 33.700 → 39.700, ⌀6 ID / ⌀8 OD, 6.000 long, plain, polymer |
| Housing collar (printed bay) | R 33.700 → 37.400, ⌀12 OD × 3.700 — **a requirement, not a detail** |
| Wall bore | **⌀8.000 H7** through the 2.3 mm wall — a standard reamer. The 0.030 mm press interference comes from the bushing being supplied oversize, not from undersizing the hole |
| Running clearance | +0.030 mm diametral, journal in bearing |
| Panel root face | R 40.200 |

The bearing and the wall bore are both **⌀8 nominal in the CAD**. The supplied oversize is a
fit allowance, not geometry — model it and the bearing reads as an interference against its
own seat in every clash check. Ream the wall and the printed collar **in one pass after the
bay is bonded in**, so concentricity is a property of the operation rather than a tolerance
held across two parts.


### Servos — KST X08 Plus V6.0, 4 off

Datasheet KST_0012 rev 2025-04. Everything here is off the dimensioned drawing and lives in
`design/packaging.SERVO_GEOMETRY`; do not retype it.

| | |
|---|---|
| Case | 23.5 × 8.0 × 16.8 mm ±0.2 |
| Envelope with lugs | 29.5 mm long; lug holes 4 × ⌀1.5 on 26.5 × 5.0, plus 2 × ⌀2 (both confirmed against the datasheet drawing's own callouts, "⌀1.50-4" and "⌀2-2") |
| — 4 × ⌀1.5 holes | at the 4 corners of the 26.5 × 5.0 rectangle. **Read as mounting screws** — KST lists 4 screws as supplied with the servo, and 4 corner holes on a rectangular flange is the ordinary pattern on this class of servo — but the datasheet dimensions the holes and does not caption their function, so this is inference, not a labelled fact |
| — 2 × ⌀2 holes | **on the flange centreline**, one per lug position, between the two rows of small holes rather than beside them. Larger than a screw needs and only two of them: consistent with locating dowels for repeatable placement in a tray. **Purpose unconfirmed** — nothing in this project uses them yet, and no callout on the drawing names them. Check before building a tray that assumes they take a pin |
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

## Verifying the model

`python scripts/verify_cad.py` cross-checks every design number against what the Onshape
model actually contains — volumes against exact analytic figures, and the measured mass
tensor against `design/control.py` — plus instance count, feature status, the four
hand-placed mates, and whether any assembly instance has lost its part reference.

**It cannot catch an interference.** Two solids in the same space change no volume and no
mass. There is exactly one tool for that and it is not in the API
(`/assemblies/.../interferencecheck` 404s on v10): open `Assembly 1` in the browser, select
every instance, right-click → **Check interference…**. Run it after any assembly change. It
is the only check that found the tang buried in the tube wall, the collar boss rim outside
the shell, and the retainer bar inside the servo — none of which moved a gram.

There is now a **second route, and it does not need the browser**: export the assembly to
STEP, open it in Fusion, and boolean every pair of bodies against each other with
`TemporaryBRepManager` — which works on copies and never touches the design. It is
scriptable, it reports the overlap volume rather than just a yes/no, and it can be pointed
at a rebuilt model as easily as at the import. See "The Fusion 360 transfer" below, where
it found 21 clashes in a rebuild that had passed every mass and volume check.

## The Fusion 360 transfer — what the rebuild lost

Sep 2026. The module was re-created natively in Fusion 360 (`CanardControlModule`), with
`cad/onshape_export/Assembly_1.step` imported alongside it as the component
`Onshape_reference`. Both live in the same file at the same coordinates, so the two can be
booleaned against each other body-for-body. That is the check, and it is worth knowing it
is available: **a native rebuild and its source in one document is a diffable pair**, which
is a stronger check than eyeballing dimensions, because it catches the things that are not
dimensions at all.

Volumes below are Fusion's `VeryHighCalculationAccuracy`. The default accuracy is not good
enough for this — it reported the tube 27 mm³ off its own analytic value and sent the first
pass of this check chasing a hole that was not there.

**Four parts transferred exactly**, to 0.0000 mm³: the four canard shafts (698.1377 mm³),
the eight servo retainer bars (90.8076), the pass-through plate (10425.7648) and the aft
gas seal (20744.0871). Every Z station in the module matches. So does the tube OD/ID, the
bay's shell OD ⌀74.500 and bore ⌀69.700, and all four hinge axes at Z 68.270.

Four things did not, and two of them are load path.

### 1. Every radial hole in the tube is blind

The tube reads 79142.6901 mm³ against the Onshape 79131.8242 — the rebuild has 10.87 mm³
**more** material, in a part whose only features are holes. All six radial holes — four ⌀8
hinge bores at Z 68.270 and both ⌀2.0 vents at Z 120.0 — stop on a flat plane at R 37.400,
tangent to the ⌀74.8 bore, instead of cutting through it. The bore is curved and the hole
bottom is flat, so each hole breaks through along a single tangent line and leaves a
crescent web everywhere else:

| hole | leftover web | thickest at hole edge |
|---|---|---|
| ⌀8 hinge bore, ×4 | 2.692 mm³ each | 0.2145 mm |
| ⌀2 vent, ×2 | 0.011 mm³ each | 0.0134 mm |

4 × 2.692 + 2 × 0.011 = 10.788 mm³ against the 10.866 measured. That is the whole
discrepancy, and it is the signature of a cut whose depth was typed as a number rather than
taken through the far face.

It is not cosmetic. The crescent sits exactly where the bearing and the shaft pass, so it
interferes with both: 1.85 mm³ against each bearing, 0.85 mm³ against each shaft, eight
clashes in total. And **the two vents do not vent** — they are blind pockets, which undoes
correction 37 entirely.

### 2. The bay's four bearing bores are plugged by the shell

The bay reads 29949.1849 against 28257.5795 — 1691.55 mm³ extra. The difference is purely
additive: the Onshape bay has only 0.41 mm³ the rebuild lacks, so nothing was left out,
things were left *in*. Splitting the extra by radius from the rocket axis says where:

| band | extra | what it is |
|---|---|---|
| R 26.000 – 34.850 | 1127.0 mm³ | a second pair of tray webs |
| R 34.850 – 37.250 | 482.9 mm³ | the bearing bores, not cut through the shell |
| R 37.250 – 40.000 | 81.6 mm³ | collar bosses run out too far |

The middle row is the one that matters. 482.9 mm³ is 4 × π/4 · 8² · 2.400 = 482.5 — a
2.400 mm **plug of shell wall left in each of the four ⌀8 collar bores**. The ⌀12 boss and
its ⌀8 bore are both present and both correctly sized; the bore simply was never cut
through the shell it passes into, which is what happens when the boss is unioned to the
shell and the bore is cut only in the boss. The bearing cannot be pressed in, and the model
says so: 52.95 mm³ against each bearing, 43.42 mm³ against each shaft, 19.47 mm³ against
each servo spline, twelve clashes.

The third row is the failure this build sheet already records Check interference finding
once. The collar bosses end at **R 37.400** — the tube ID — instead of **R 36.500**, which
is the shell bore at 34.850 plus `COLLAR_BOSS_OVERLAP` 1.650. They are 0.900 mm too long.
A flat-ended ⌀12 boss on a radial axis at R 37.400 has a rim at
hypot(37.400, 6.000) = **37.878**, against a shell OD of 37.250 and a tube ID of 37.400, so
the boss stands proud of its own shell and buries itself in the airframe wall — 43.85 mm³
of it. `design/bay.py` carries a comment warning about precisely this and a check
(`collar_rim_radius`) that would have caught it.

The first row is extra print, not a defect: the rebuild carries a second pair of tray webs
at a circumferential offset of 5.900–7.500 mm, where the Onshape bay has webs only at
7.600–9.200 mm. Nothing fouls them and they clear the servo's 8.0 mm width easily. They are
about 1.5 g of PETG-CF nobody asked for. Decide whether they were deliberate.

### 3. The servos are right — including the thing that was suspected

The servos were the first suspect and they are the one assembly that is provably correct.
Each rebuilt servo is one merged body where Onshape carries three (case + flange, lower
boss, spline), which is fine, and the merged volume is 3918.9964 against
3193.0482 + 672.3840 + 40.2124 = 3905.6446. The difference is **13.3518 mm³**, and

    4 × π/4 · 1.5² · 1.000  +  2 × π/4 · 2.0² · 1.000  =  13.3518

to four decimals — the four ⌀1.5 and two ⌀2.0 flange holes through the 1.000 mm flange,
not cut. Nothing else about the part differs. Every dimension `SERVO_GEOMETRY` carries
survived the transfer: 23.5 mm case and 29.5 mm lug envelope running axially, 8.0 mm
across the circumference, 16.8 mm of radius for the case, output face at R 33.185, spline
⌀4.0 × 3.2 reaching R 36.385, and the lower boss inboard to R 6.085 — which is
33.185 − 27.100, the `depth_from_top` the datasheet gives. The shaft is 6.14 mm off the
case centre in the rebuild too.

So the 23.5 × 8 × 16.8 numbers are not the problem, and neither is the flat-mount
orientation. Cut the six flange holes and the part is exact.

### 4. The bearing chamfers are undocumented, and the disagreement is the other way round

The rebuilt bearing is 131.9469 mm³ — exactly π/4 (8² − 6²) · 6, which is the analytic
annulus `scripts/make_bearing_cad.py` says it built and verified to 0.001 mm³. The
**Onshape** part is 130.2462, 1.7007 mm³ lighter, consistent with a 45° lead-in chamfer of
about 0.3 mm at both ends. Nothing in this repo mentions a chamfer, and the part has also
been renamed since that docstring was written (`dia 6/8 x 6 plain` →
`iglidur G, 6/8 x 6 plain`). Harmless either way — a chamfer only removes material and a
lead-in on a pressed bushing is good practice — but **the source of truth and the model
disagree and neither knows it**. Reconcile it: either put the chamfer in
`make_bearing_cad.py` or take it out of Onshape.

The canard panels differ by 1.991 mm³ (0.021%) and 0.008 mm of axial extent at the tip.
That is below anything that matters and below what a STEP round trip of a swept surface
guarantees. Leave it.

### The check that actually found all of this

Pairwise boolean intersection over every body, via `TemporaryBRepManager` — which does not
touch the design, so it is safe to run on a model you have not saved:

- **Onshape reference, 36 bodies: 6 pairs touching, all ≤ 0.028 mm³.** Those are tolerance
  slivers on coincident press-fit faces from the STEP round trip. This is what clean looks
  like, and it agrees with Onshape's own Check interference.
- **Fusion rebuild, 28 bodies: 21 pairs clashing, 0.85 – 52.95 mm³.** Three to four orders
  of magnitude larger. All 21 trace to findings 1 and 2.

None of the four findings moves a gram in any direction that a mass check would notice, and
two of them make the module unbuildable. This is the same lesson as the API rewrite and the
servo bounding box, one tool further out: **volume and mass agreement is not model
agreement.** Boolean the rebuild against its source.

### Fixed, Sep 2026 — and the fix is the same trick as the check

All four findings are closed in the Fusion file, which is saved. The repair did not involve
re-typing a single dimension, and that is the point worth keeping: **the reference solid is
also the cutting tool.** For any body where the rebuild is a superset of its source,

    tool  =  rebuild  −  reference
    fixed =  rebuild  −  tool      ( ≡ rebuild ∩ reference )

which lands the rebuild exactly on the reference without anyone deciding what the number
ought to be. Six such tools were built with `TemporaryBRepManager`, dropped into a
`BaseFeature`, and applied with `CombineFeature` cuts — a parametric design will not accept
a temporary body as a tool any other way. They sit at the end of the timeline and can be
deleted.

The bay was the only one needing judgement, because there the extra material was not all
unwanted: the bore plugs and the proud boss had to go, the extra webs were a separate
question. They split cleanly at the shell bore, so the tool was masked with a cylinder —
`tool = (rebuild − reference) − cylinder(R 34.850)` — which takes the plugs and the boss
and leaves the webs. The webs were then removed in a second, separate cut once they were
confirmed unintentional, so the two decisions stayed separable in the timeline.

| body | was | now | reference | note |
|---|---|---|---|---|
| tube | 79142.6901 | 79132.2721 | 79131.8242 | difference solid is **empty** |
| bay | 29949.1849 | 28257.1924 | 28257.5795 | difference solid is **empty** |
| servo ×4 | 3918.9964 | 3905.5375 | 3905.6446 | −0.0027% |
| canard panel ×4 | 9510.2874 | — | 9508.2962 | +0.021%, untouched |
| bearing ×4 | 131.9469 | — | 130.2462 | +1.31%, see below |

All mm³, `VeryHighCalculationAccuracy`. The tube and the bay now boolean to a **zero-face
empty body** against their Onshape counterparts, which is a stronger statement than the
volumes: the residual ±0.4 mm³ is the kernel valuing a natively-cut solid slightly
differently from a STEP-imported one, not geometry. The tube also matches face-for-face —
10 faces, no flat bottoms, hole walls 231.6304 mm² and 28.8834 mm² against 231.6304 and
28.8836.

Interference, same pairwise boolean as before:

| | pairs | worst |
|---|---|---|
| rebuild, before | 21 | 52.95 mm³ |
| rebuild, after | 4 | 0.0192 mm³ |
| Onshape reference | 6 | 0.0278 mm³ |

The four survivors are bearing-against-bay slivers on the press-fit seat, smaller than the
reference's own. That is parity, not a clean sheet, and a clean sheet is not available: a
STEP round trip does not reproduce coincident faces to zero. **Judge a rebuild against its
reference's interference number, not against zero.**

Two things are deliberately still open, and neither is a rebuild defect:

- **The bearing chamfer.** The rebuild is the exact analytic annulus
  `scripts/make_bearing_cad.py` claims. Onshape has ~0.3 mm lead-in chamfers nobody wrote
  down. Fixing this in Fusion would be encoding an undocumented change; the fix belongs in
  Onshape or in the script. Until then the rebuild is the one that agrees with this repo.
- **The canard panel's 0.021%.** Below what a STEP round trip of a swept surface promises.

The extra tray webs were removed at the same time — 1127.05 mm³, ~1.5 g — because they were
not intentional. Had they been, the fix would have been the other direction: `design/bay.py`
would have had to learn about them, since its 38.6 g is what reaches `design/control.py`
as the mass tensor. Worth stating as a rule: **when the CAD and the model disagree, decide
which one is wrong before deciding what to edit.** Three of the four findings here were the
CAD; the bearing chamfer probably is not.

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
