# The nav bay sled

**Status, Sep 2026: built, verified, and it found something.** `design/sled.py` models it,
`scripts/sled_report.py` prints the argument, `scripts/make_sled_fusion.py` generates the
Fusion build, and `scripts/baseline.py` carries the verdict. The part is in the Fusion
document `CanardControlModule` as the component `NavBay`.

Read `design/sled.py`'s header before acting on anything here. This file is the narrative;
that file is the argument, and it is the one that will still be right when these numbers
move.

## Why this part did not exist

The nav bay has had a packing check since Aug 2026 — `design/avionics.py` — and it is a
good one. It exists to make a single point, which it makes correctly: **a flat sled in a
round tube can only use the rectangle inscribed in the circle**, so the bay is not half
empty the way a volume comparison suggests, and the binding quantity is footprint on two
faces. It computes:

```
sled_width    = 0.80 * min_bore     = 56.16 mm
usable_height = 2*sqrt(r^2-(w/2)^2) = 42.12 mm      (not 74.8)
per_mm        = 2 faces * width * 0.70 efficiency = 78.62 mm^2/mm
required      = 8682 mm^2 / 78.62   = 110.42 mm     against 115.04 available
```

**+4.6 mm, and it FITS.** That verdict is correct for the question it answers.

But it is an **areal** model. It sums footprint and divides. It never places a component,
never checks two parts against each other, and never draws the sled. So the sled itself
existed as exactly two numbers: `SLED_WIDTH_FRACTION = 0.80`, and
`design/mass.py`'s `"sled_and_hardware": 0.150`. A width allowance and a mass allowance,
priced into every budget in the vehicle, for a part that had never been drawn.

That is the fourth time in this project. Correction 33 was the harness — its volume came
from a budget line divided by an assumed density and its strength came from nowhere.
Correction 37 was the pass-through plate. Correction 38 was both access bulkheads. **The
tell is identical every time: the thing is charged for in a budget, so no check ever reports
it missing.** A missing part shows up as a violation; an allowance shows up as nothing at
all.

## What placing it actually found

`design/sled.py` places every component as a real rectangle on one of two real faces. The
search is exhaustive over face assignment and 0/90 orientation, and exact within a face —
backtracking over corner points, which loses no solutions, because in any feasible packing
every rectangle can be slid down and left until it touches something. **That is what makes
a negative result here mean "no packing exists" rather than "the heuristic gave up",** and
it is the only reason a negative result is worth reporting at all.

**The four boards fit.** On the 56.16 mm plate, at 1.0 mm of clearance all round, with
room left over. The boards were never the question.

**The wiring is the question.** `avionics.WIRING_FOOTPRINT` charges the 80 g loom
70 × 20 mm of sled *face* — an areal model has no way to say "along one edge" other than by
charging the area. Asked as a rectangle, on the 56.16 mm plate:

| clearance | boards only | boards + loom |
|---|---|---|
| 0.0 mm | places | places |
| 0.5 mm | places | **NO PLACEMENT** |
| 1.0 mm | places | **NO PLACEMENT** |
| 2.0 mm | places | **NO PLACEMENT** |

And no single part is at fault — removing any one of the STM32 board, the battery or the
loom lets the rest place. It is the total.

### The corners do not rescue it

The obvious objection is that a loom is flexible and the two corner crescents outboard of
the sled are exactly the volume a flat plate cannot reach. That is `avionics.py`'s own
argument, so it deserves a number rather than an opinion:

| plate | free crescent volume | density needed to hold 80 g |
|---|---|---|
| 56.16 mm (0.80 of bore) | 43.9 cm³ | **1.82 g/cm³** |
| 59.41 mm (as built) | 29.8 cm³ | **2.68 g/cm³** |

*(These are the crescents with the rods **out of them** — moving the rods above and below
the plate handed the side crescents back. It still is not enough.)*

Copper is 8.96 g/cm³ and PVC insulation about 1.4. A bundle with air in it does not reach
either figure. **And it gets worse as the plate widens, so the two candidate fixes work
against each other.**

### The fix is width

| plate | fraction | half-height | tallest part | boards + loom |
|---|---|---|---|---|
| 56.16 mm | 0.800 | 21.06 mm | 15.70 mm | NO PLACEMENT |
| 58.00 mm | 0.826 | 19.77 mm | 15.70 mm | NO PLACEMENT |
| **59.41 mm** | **0.846** | 18.70 mm | 15.70 mm | **places** ← selected |
| 62.50 mm | 0.890 | 15.99 mm | 15.70 mm | places, but 0.29 mm of headroom |

**`SLED_WIDTH_FRACTION = 0.80` is 2.84 mm too narrow to carry the wiring the same file
charges for.** Nothing could have seen that, because an areal model only ever sees the
product `width × length × efficiency` — it cannot distinguish a plate that is 2.84 mm too
narrow from one that is wide enough.

The plate is **59.41 mm**, and what sets it is **not the rods** — see the next section, that
turned out to be a red herring — but the fact that **width is bought with height**. A wider
plate sits on a longer chord, so the inscribed rectangle gets shorter, and the tallest
component pays. 59.41 mm is what keeps **3.0 mm of headroom** over the 15.70 mm
StratoLoggerCF-plus-standoff stack.

`design/configure.py` now passes that real width into `avionics.check_packing()` instead of
the 0.80 fallback, so the vehicle's own warning describes the sled that exists. **The areal
margin goes +4.6 → +10.7 mm as a result.** That is not the model being retuned until it
fits — correction 5's failure mode — it is the part getting better and the constant
following. The constant stays in `avionics.py` as the figure to use when no sled has been
designed, which is the situation that module was written for.

## The mount, and the thing that had to be got wrong first

**Two threaded rods between the two end plates, clocked perpendicular to the sled** — one
above it, one below — **not out at its edges.** The edges is where a side-view sketch puts
them, and it is where this was first built.

**Rods beside the plate do not work**, and the reason only shows up in three dimensions. A
nut on a rod running along the rocket axis clamps *along that axis*, and a plate lying in
the rod's own plane presents nothing to that direction but its **1.6 mm edge**. There is no
face for a washer to bear on. Widening the plate into ears around each rod does not rescue
it either: the rod runs the whole length of the bay, so clearing it means removing every
scrap of ear at that radius *at every station*, and the ear then captures nothing.

The Fusion model said so in one line: **47.31 mm³ of plate inside each rod.** That is what a
pairwise interference check is for, and it is why it is worth running against your own new
part and not only against the old ones.

So the capture has to be **perpendicular to the rod**: a small end bracket in the
cross-section plane, which is a bulkhead in miniature and is what a real avionics bay has
always used. Once it is a bracket, the rod is free to leave the plate's plane, and that buys
two things at once:

| rod position | ligament in a bracket | ligament in the two end plates |
|---|---|---|
| R 32.60 mm | **−0.05 mm** | 2.55 mm |
| R 31.00 mm | 1.55 mm | 4.15 mm |
| **R 30.00 mm** | **2.55 mm** | **5.15 mm** ← selected |

- **The rod stops constraining the plate width.** Beside the plate they compete for the same
  millimetres. Above it they do not compete at all — the rod sits at Y 28.0–32.0 mm and the
  tallest component reaches 16.50 mm.
- **The rod can come inboard, so its hole is a real hole.** At R 32.60 a ⌀4.5 hole leaves
  −0.05 mm of ligament, which is not a part. At R 30.00 it leaves 2.55 mm. It also takes the
  hole in each **end plate** from 2.55 to 5.15 mm of edge ligament, and that matters more:
  those two plates are pressure boundaries.

The plate **butts** the brackets and is bonded to them; it does not run through them. It
cannot — the plate is 59.41 mm wide and a bracket only 36.0 mm, so a slot for it would run
the bracket's full width and cut it into two unconnected halves. The butt bond is 95.1 mm²
at 25 MPa: **166×**.

### The rods also had the wrong length

They were first drawn 115.04 mm — the length of the *sled*. They have to be **127.04 mm**,
the length of the *bay*, because they are anchored in the pass-through plate at the aft end
and take a nut against the nose plate at the forward end. As built they were 12 mm short of
anything to hold them: a "simply supported" sled supported at one end by nothing.

## THE SECOND READING — read this before acting

The loom-does-not-fit result has two readings and **the model cannot distinguish them**:

1. The loom really is 70 × 20 × 12 mm of solid keep-out, in which case the plate must go to
   59 mm and the width comes out of the tallest component's headroom.
2. **The 80 g is a whole-avionics allowance in the wrong place.** `design/mass.py` calls the
   line `wiring_connectors`, and connectors are not loom. The servo leads run *aft* through
   the pass-through plate into the canard module; the pyro leads run *aft* to the recovery
   bay. Neither stays in this bay. Charging all 80 g to nav bay sled *face* would then be
   the wrong place for most of it, and the whole squeeze dissolves.

**Nothing was resized and `avionics.py`'s model was not edited.** Correction 5 is the
precedent and it is exact: the recovery bay was declared 11 mm short on a figure built from
multiplied estimates, the airframe was lengthened on the strength of it, and the shortfall
turned out not to exist. What settles this one is **weighing the loom and counting the
conductors** — an afternoon's work that has never been done.

The wider plate is cheap insurance meanwhile: it costs nothing, it stays inside the bore,
and it is right under either reading.

## The part

|  |  |
|---|---|
| plate | G-10, **109.04 × 59.41 × 1.6 mm**, 19.0 g, 11 mounting holes |
| end brackets | 2 × G-10, R 34.80 cropped to ±18.0 mm in X, 3.0 mm thick, 26.2 g |
| rods | **2 × M4** at (0, ±30.00), perpendicular to the plate, 127.04 mm long, 25.2 g |
| standoffs | 12 × ⌀6 nylon, 3 mm — 1.2 g |
| hardware | 30 g — nuts, washers, screws. **A guess.** |
| **total** | **101.6 g** against the **150 g** `mass.py` has budgeted since before the part existed |
| assembly length | 115.04 mm against 115.04 mm usable |
| widest point | R 34.80 mm in an R 35.10 mm shoulder bore |
| station | 317.60 → 432.64 mm from the tip; Fusion Z **−127.04 → −12.00** |

Mounting holes are **merged where they collide**. The BEC's and the StratoLoggerCF's screws
landed exactly on top of each other at one corner and 1.30 mm apart at another — two holes
1.30 mm apart are one ragged slot with no material between them. Boards on opposite faces
can legitimately share a screw with a standoff on each side, so a cluster merges rather than
being rejected; 12 screw positions become 11 holes. **Nothing found this until the CAD
volume came back 10.7519 mm³ heavy and the two overlaps accounted for it to the last
hundredth** — which is the whole argument for checking volume against an analytic figure
instead of looking at the model.

### The surrounding structure

Drawn so the sled is checked against something rather than against nothing. No new design
decisions — every dimension is read off `joints.py` and `design/access_bulkhead.py`:

| body | |
|---|---|
| nav bay tube | ⌀79.40 / ⌀74.80 × 127.04 mm, Z −127.04 → 0 |
| nose shoulder | ⌀74.80 / ⌀70.20 × 79.40 mm, reaching aft into this bay |
| nose plate | ⌀74.80 × 3.2 mm G-10, Z −130.24 → −127.04 |

### The frame, and the trap in it

The Fusion document has Z = 0 on the canard module's **forward** face (station 444.64 mm),
+Z aft, and `pass_through_plate` already occupies Z 0.000 → 2.400 there.

```
station 317.60 mm  =  Z -127.04   nav bay forward end
station 432.64 mm  =  Z  -12.00   aft limit of the sled
station 444.64 mm  =  Z    0.00   module forward face
```

**The 12 mm is `joints.BULKHEAD_ALLOWANCE`, and it is charged to the NAV BAY even though the
plate itself sits 2.4 mm inside the canard module.** Reading it the other way puts the sled
12 mm too far aft and straight through the plate. That was worth deriving rather than
inheriting — the alternative reading was worth ±8.8 mm on a margin quoted as +4.6 mm.

## Verification

- **Volume**, at `VeryHighCalculationAccuracy`: plate 10278.1112 mm³ (**−0.0076**), each
  bracket 7071.2677 (**−0.0000**), each rod 1596.4317 (**+0.0000**). That accuracy is not
  optional — the default read the Onshape tube 27 mm³ heavy last session — and it earned its
  keep again here by finding the colliding mounting holes.
- **Interference**: pairwise boolean over all 42 bodies, 861 pairs. **Zero clashes involving
  any sled body**, including against the tube, the shoulder and the nose plate. The only
  four in the document are the pre-existing 0.0192 mm³ bearing-against-bay slivers from
  correction 40, unchanged. This is what caught the rods running through the plate.
- **The bore**: every sled body booleaned against a ⌀70.20 cylinder swept the length of the
  bay leaves **0.0000 mm³ outside it**, and the widest vertex is a bracket at 34.8000 mm
  radius against 35.1000 — **0.30 mm clear**. No script in this repo had ever performed the
  "does it slide past the nose shoulder" check, and it is the one question a sled has that a
  bulkhead does not.

## Why the build script is a generator

`scripts/make_sled_fusion.py` does not build anything. It **emits** the Python that Fusion
runs, with every number derived from `design/sled.py`.

Fusion's embedded interpreter cannot import this repository, so a script that runs inside
Fusion has to carry its dimensions as literals. Typing them would put a second source of
truth next to the model — exactly what every Onshape script in `scripts/` refuses to do.
`place_bearings.py` will not even type a quadrant angle, on the grounds that a hand-written
number goes stale silently while a derived one does not. Generating the script keeps one
source of truth and makes the build re-runnable when the envelopes change.

Geometry goes in as **temporary BRep bodies through a `BaseFeature`**, not as sketches and
extrudes. That is the pattern proven in this document in correction 40: the design is
PARAMETRIC, so a temp body has to go in through `BRepBodies.add(body, baseFeature)` or it
does not go in at all.

## What is still open

- **Three of the four envelopes are guesses** (`measured=False`): the STM32 board, the
  battery, the BEC. The board's 70 × 45 × 12 is called *a layout target, not a measurement*
  in `avionics.py`, and it is the only line a design decision can shrink. Everything here is
  parametric on them — rerun `python scripts/sled_report.py` when a part is chosen.
- **The loom's mass and conductor count.** See "the second reading" above. This is the one
  that decides whether any of this matters.
- **The 30 g of hardware** is a guess of the same character as `SLED_PACKING_EFFICIENCY`.
- **BATTERY AND LOOM RETENTION IS NOT SOLVED.** There is **1.00 mm** of clear plate beside
  the battery and **1.41 mm** beside the loom, against the ~3 mm a cable-tie slot needs. So
  the two heaviest items on the sled are held by nothing that is drawn. Adhesive, foam, or a
  strap anchored to the board standoffs will do it — 90 g at 8.3 g is only 7.3 N — but none
  of those is designed, and a battery coming loose in a guided vehicle is not a small
  failure. The check reports the gaps rather than drawing slots that do not fit.
- **Six of the eleven mounting screws land under a component on the other face.** They have
  to be countersunk flush or the part above needs relief.
- **Sled stiffness is not modelled.** A 1.6 mm G-10 plate spanning 115 mm with 400 g on it
  is a deflection question, and this project has no vibration model to answer it. The
  thickness is a producibility floor, in the sense `design/access_bulkhead.py` uses the
  phrase, not a stress result.
- **Connector overhang and cable bend radius.** An envelope is a rectangle and a plugged
  connector is not. This is the next thing that will bite, and it eats directly into the
  1.0 mm of placement clearance and the 3.0 mm of headroom.
- ~~**The nav bay's static ports still have no station and no clocking anywhere in this
  repo.**~~ **CLOSED, Sep 2026 — docs/01 correction 42.** 3 × ⌀3.2 mm at station 420.82 mm,
  clocked 15/135/255°, 4.60 mm deep, in the CAD and interference-checked. `design/ports.py`,
  `scripts/port_report.py`.

  This paragraph said it "needs a decision rather than a script". **It needed a script**, and
  the reason is worth keeping: the first question a hole asks is not where the pressure is
  right, it is **what is behind the wall** — and the answer here was that there is no bare
  wall in this bay at all. Two 1.0 cal joints do not fit in a 1.60 cal tube, and nothing
  could see it because `design/joints.py` described a joint only by the half that protrudes.
  Getting to three holes went through a new field on `Joint`, a new check, and 9.4 mm of the
  recovery bay's packing margin.

  It also validated this document's own sled model against CAD for the first time in a way
  nothing else had: the ports' inner mouths measure **9.29 / 11.02 / 7.89 mm** to the nearest
  sled solid in Fusion, against the same three numbers to the hundredth from
  `sled.solids_at()` — which is the function that had to exist before anyone could ask
  whether air can actually reach a hole from inside.
