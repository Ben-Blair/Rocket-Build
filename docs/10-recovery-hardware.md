# Recovery hardware — the U-bolt, its backing plate and the charge well

Added September 2026. Model in `design/recovery_hardware.py`, argument in
`out/recovery_hardware_report.txt` (regenerate with
`python scripts/recovery_hardware_report.py --write`), verdict carried by
`scripts/baseline.py`, geometry by `scripts/make_recovery_hardware_cad_fusion.py`. Full
history in `docs/01-next-steps.md` correction 54.

The U-bolt **holes** have been in the CAD since correction 50, drilled from
`seal.hole_layout()`'s own positions. The hardware standing proud of them had never been
sized. Three scripts said so in their own docstrings and one was blunt about which one
mattered — `scripts/make_bulkhead_cad.py`: *"The backing plate is the one that matters — it
is STRUCTURE — and it is not here, so this part is not yet the whole harness anchor."*

## The headline: a U-bolt used as an anchor is not loaded the way a U-bolt is rated

**`design/seal.py` had carried this sentence since it was written, and it read as a
calculation:**

> "An M5 U-bolt on a 25 mm leg spacing is the ordinary size for this load — 1.3 kN through
> two 5 mm legs is 33 MPa of shear in stainless, which is nothing."

Two errors, and they compound.

1. **The legs are not in shear.** The harness pulls along the bolt's axis, away from the
   plate. The legs are in **tension** and the nuts react it. Shear never enters.
2. **The legs are not what breaks.** The **crown** is, in bending, at the two bends where it
   meets the legs — which is exactly where a U-bolt used as an anchor is observed to
   straighten. A published U-bolt load rating is for **clamping a pipe**, where the crown
   bears on the pipe and the legs really are in tension and nothing bends. That rating
   describes a different structure.

## What it carries

One load, four anchors: **1506 N**, the main's infinite-mass opening shock, which
`design/configure.py` already uses for the harness. One load, three parts, no chance of them
disagreeing.

| Mode | Stress | Margin |
|---|---|---|
| Crown, fixed-arch model (**design case**) | 119 MPa | **2.01×** |
| Crown, straight-beam idealisation | 187 MPa | 1.28× |
| Legs, **tension** (not shear) | 21 MPa | 11.7× |
| Backing plate, own bending | 53.9 MPa | 9× |
| Backing plate, bearing under the nut washers | 3.5 MPa | 107× |

**The straight-beam row does not clear 2.0× and that is left visible.** The arch model is the
right one — a curved crown carries most of the pull in direct tension along the rod, which is
why U-bolts work at all — and a straight beam is a different structure rather than a bound on
this one. But this is the single most safety-critical joint in the vehicle, and what settles
it is a destructive pull test on the actual bolt. That has not been done.

Sized against the mode that governs: **M10, not M5.** The holes already placed in both
bulkheads go from ⌀5.5 to ⌀10.5. They are not drilled yet, so the finding costs nothing but
the drill.

> **M8 → M10 at the Sep 2026 agility freeze.** This file predicted it in as many words —
> *"the next thing to gain mass anywhere in this vehicle may push it to M10"* — and the
> next thing was the canards going to 1.30 cal. More fin → more mass → more descent weight
> → more opening shock (1587.6 N now), and the crown-in-bending margin went under 2.0× at
> M8. The four anchors go 191 → 302 g. See `docs/00-requirements.md` §7.2.

## The part

| Part | Dimensions | Mass |
|---|---|---|
| U-bolt, ×4 | M10 stainless, 25.0 mm leg spacing, crown R 12.5, legs 20.0, rod 79.3 long | 70.87 g |
| Backing plate, ×4 | G-10 39.0 × 24.5 × 3.2, ⌀10.5 holes; two of them relieved | 4.63 g |
| Charge well, main | ⌀12 × 19.00 deep, at R 22.60 on the aft gas seal's aft face | 6.44 g |
| Charge well, drogue | ⌀8 × 20.50 deep, at R 29.40 / 45° on the internal bulkhead's aft face | 6.07 g |
| **Total** | 4 anchors + 2 wells + charges | **205.3 g** |

Both wells sit **on their own charge's lead hole** — the main over a feed-through, the drogue
over the conduit hole — so neither needs a new hole through a pressure boundary. Bore is the
smallest whose well stands no more than 21 mm proud: a deep narrow well is a worse part than
a short fat one, harder to fill, harder to see into, and a lever the canopy can catch on.

**The drogue charge is 0.4515 g and this is the first place it has been printed.**
`seal.internal_bulkhead_from_evaluation()` has computed it since it was written and no report
in this project had ever shown it; `docs/04` lists only the main's.

## Why the backing plate is the one that matters

Its own bending asks for 1.2 mm. What sets it is that it must not **dish** under the nuts,
because if it dishes the footprint the log term assumes is not there.

`seal.Bulkhead.point_load_stress()` goes as log(disc radius / footprint radius). `seal.py`
passed a hardcoded **6.0 mm** there — a bare nut face — and said in a comment that a real
plate would replace it:

| Footprint | Disc stress | Margin |
|---|---|---|
| R 6.00 mm (bare nut) | 96.9 MPa | 4.95× |
| **R 16.71 mm (this plate)** | **60.1 MPa** | **7.98×** |

That is a **result** of the part existing, not a retune. Nothing was softened to get it, and
`seal.py`'s default is unchanged — `SealResult.shock_footprint_radius` is a field a caller
passes — so every previously reported number still reproduces.

## The second finding — the harness does not fit through the U-bolt

`recovery.size_harness()` selects 3/4" tubular nylon: **19.1 mm of webbing.** An M10 U-bolt on
a 25 mm spacing leaves a **17.0 mm clear opening.** Two sized parts of this vehicle, and
nothing had ever put them next to each other.

Opening the U up until the webbing passes needs 21 mm of clear opening, which drives the rod
to M10 and about 310 g of stainless across four anchors — more than the whole motor mount.
That is not the answer.

**The webbing was never meant to pass through it.** `recovery.HARNESS_HARDWARE_KG` has priced
50 g of "links and swivels" since it was written. **Requirement, recorded rather than left as
the thing everybody happens to do: the harness attaches through a quick link, and the link
goes through the U-bolt.** A 6 mm link needs 8 mm of opening, not 21, and there is 9.0 mm to
spare.

## The third finding — the internal bulkhead's face is the most crowded surface in the rocket

That disc anchors a harness **both ways**, so it carries a U-bolt on each face. Two U-bolts
cannot share two holes, so **they clock 90° apart** — which puts a backing plate along each
axis and leaves only the diagonal clear.

Two consequences, neither of which anything had run:

* **Each backing plate must be relieved** where the opposing bolt's legs reach under it:
  9.5 × 3.50 mm notches in its edge, not holes, because the leg centres are *outside* the
  plate. Four notches on that disc, two per face.
* **The conduit hole moves.** `seal.hole_layout()` put it at 45° "so it is equidistant from
  both U-bolt legs" — right for as long as the only things on that face were holes, and right
  again now for a better reason: the diagonal is the only clear ground. But it has to move
  **out to R 27.5 mm** so the drogue charge well sitting on it clears both plates by 3.2 mm
  and the disc's own edge by 4.9 mm. Moving out *reduces* the bending field, so the stress
  argument is unharmed — the hole margin goes 2.17× → **2.41×**.

`seal.INTERNAL_CONDUIT_RADIUS` is the only hole radius in this vehicle set by a part rather
than by the stress field, and `check_recovery_hardware()` re-derives the window it must lie
in (27.2 … 29.4 mm) and fails if it drifts out.

Backing-plate edge distance is **7.0 mm**, not the comfortable 8.5 (one hole diameter) it
started at. On every other face 8.5 fits; on this one it leaves the well 0.34 mm of ligament,
which is not a clearance, it is a coincidence. 7.0 buys 3.2 mm and costs 5.7% of the
footprint radius, which the disc absorbs without noticing.

## What it costs — and the mass line that did not exist

`design/mass.py` had **no line** for any of the anchors. `recovery.py`'s own
`SoftGood("2 x U-bolt", 0.030, …)` entries are dead code — `measured_volume` overrides the
mass and nothing sums `Compartment.hardware` masses — and `docs/04` independently lists
120 g for four. Three numbers for one part, none reconciled, and the real one is **302 g**
because the U-bolt is M10. `mass.DEFAULT_RECOVERY_BUDGET["harness_anchors"] = 0.302` carries
it now.

**The anchor is self-loading**, which nothing else in this project is: its mass is in the
recovery budget, so it raises the descent mass and therefore the opening shock it carries.
One pass settles it because the rod size is discrete, and M10 survives the round trip at
**3.89×**.

> **This paragraph used to end "it is thin — the next thing to gain mass anywhere in this
> vehicle may push it to M10", at M8 and 2.01×.** That is exactly what happened: the Sep
> 2026 freeze took the canards to 1.30 cal, the vehicle gained mass, and the round trip
> landed on M10. The prediction is left standing above because a warning that came true is
> worth more than a warning that was quietly edited out. At 3.89× there is now real room —
> but the mechanism has not changed, and neither has the lesson.

**Packing.** One anchor displaces **5.95 cm³** against the 3.00 cm³ `recovery.py` estimated —
low by 2.0×, because the U-bolt it described was M5. And the wells are rigid too:
`default_soft_goods()` said in as many words that charge wells "mount on the bulkhead face
and do not consume packing volume", and a ⌀12 tube standing 19 mm off the face is directly in
the canopy's way. Both are priced now, and the well envelope is a **converged** figure, not a
typed one — the well displaces packing, the packing sets the compartment volume, the volume
sets the charge and the charge sizes the well. Two passes settle it, the same fixed point
`add_conduit()` already runs.

Recovery bay margin: **+8.35 mm → +4.63 mm.** Still fits, and nothing was resized to keep it
there.

**Vehicle level**, from the 191 g the budget did not have: dry mass 5.68 → **5.89 kg**,
apogee 1326 → **1271 m**, one-sided crossrange at 8° 340 → **297 m**, lateral authority
1.59 → **1.41 g** (R8 asks for 0.5), static margin 2.27–2.76 → **2.30–2.77 cal**. No
requirement moves out of bounds; R6's 1600 m cap has more room, not less.

## What is still open

* **The crown model.** The straight-beam idealisation gives 1.28×. A destructive pull test on
  the bought bolt settles it and has not been done.
* ~~**The drogue harness's own opening shock** has never been computed by anything here.~~
  **CLOSED by correction 61, and it stopped being the conservative case.** The number now
  exists: `horizontal_agility_sweep.Candidate._deployment` computes it, and on a VERTICAL
  flight it is nearly zero — the vehicle arrives at apogee doing about 1 m/s, which is
  exactly why sizing all four anchors against the main's shock was conservative and why
  nobody needed the number.
  **On a horizontal launch it inverts.** A flat flight reaches apogee at ~94 m/s, because
  the horizontal velocity component never goes away, and an 18 in drogue opening there makes
  **2193 N against the 1604 N** the M10 anchors, the 3/4" harness and the quick links were
  all sized for. Apogee is still the right trigger — it is the minimum-speed point of a flat
  arc — so the fix is the canopy, not the trigger: **the drogue is sized by its own opening
  shock rather than by descent rate, and horizontal mode flies a 15.4 in drogue** (R11).
  That holds the shock to the existing design load, reaches the main's 200 m at 23.5 m/s,
  and **changes nothing else in this document** — same anchors, same backing plates, same
  harness, same quick links, same charge wells.
* **`point_load_stress()` is a central-patch formula** and the U-bolt's load arrives at two
  patches at R 12.5 mm. The centre is the worst case, so using it is conservative — but it is
  not the actual load case, and nothing here models the real one.
* **`BP_BULK_DENSITY` is 900 kg/m³** against a real 900–1100 band. The well is sized on the
  low end deliberately: a well too big is a nuisance, a well too small cannot hold the charge.
* **No e-match or terminal block part number is chosen.**
