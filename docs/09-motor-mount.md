# Motor mount — the last unsized structure in the vehicle

Added September 2026. Model in `design/motor_mount.py`, argument in
`out/motor_mount_report.txt` (regenerate with `python scripts/motor_mount_report.py --write`),
verdict carried by `scripts/baseline.py` so it cannot silently regress, geometry by
`scripts/make_motor_mount_cad_fusion.py`. Full history in `docs/01-next-steps.md`
correction 53.

**`design/mass.py` has charged 250 g for this assembly since that dict was written, and
there was nothing behind it — no mount tube, no ring count, no ring diameter, no ring
station, no retainer, no thrust path.** It is the fifth allowance in this project to be paid
for without existing, after correction 20's bulkhead, correction 33's harness, correction
38's access plates and correction 41's sled. Two CAD generators refused to draw it on
purpose, on exactly the right grounds: inventing centering-ring geometry with nothing sizing
it would have been the mistake this project keeps finding and fixing elsewhere.

`design/seal.py` handed one more part over explicitly — *"It does not size the booster's
forward bulkhead, which closes the drogue compartment's aft end. That one is part of the
motor mount structure and belongs with it."* It is sized here, and the handover turned out to
be right for a reason `seal.py` could not have known.

## The headline: the centering rings are not thrust structure

**Thrust enters the airframe at the BOOSTER'S FORWARD BULKHEAD.** The motor's forward
closure bears on that disc through the mount tube's bore, and the load travels forward from
there into the vehicle it is pushing. The rings aft of it align the motor, tie the fin tabs
in, and carry the motor's mass laterally. Sizing them as though 587 N ran through them would
have produced a heavier, wronger part — and it would have hidden all three findings below.

The rings are checked against the full thrust anyway, as the redundant path, because a load
path with one member is not a load path.

## What it carries

| | |
|---|---|
| Peak thrust | **488.10 N**, AeroTech `J401FJ` at t = 0.022 s (was 586.87 N on the Cesaroni `1261J449-15A` — the Sep 2026 freeze changed the motor, and every margin in this file got *better*, so nothing here was resized) |
| Thrust into the forward bulkhead | 6.60 MPa in the 10.15 mm annular land, **73×** |
| Drogue stuck-joint pressure | 1673 kPa → 121.8 MPa, **3.94×** |
| Drogue harness U-bolt | 1506 N → 96.9 MPa bare, **4.95×** (7.98× once `docs/10`'s backing plate lands) |
| Ring glue lines, redundant path | 293 N each → 0.51 MPa, **12×** |
| Retainer base bond | 147 N (498 g dry at 30 g) → 0.054 MPa, **115×** |
| Mount tube, full thrust | 2.58 MPa, **186×**; local buckling **39×** |

**Nothing here is sized by stress.** The mount tube's wall is set by the fact that two rings
and a retainer base bond to its outside; the ring thickness by the fact that a thinner ring
tips in its own fillet and cannot be bonded square. Same shape of result as
`design/access_bulkhead.py`'s two plates and `design/venting.py`'s port sizing: the model
gives the floor, practice gives the design point.

## The part

Stations are local to the booster tube's forward face, positive aft. In the shared Fusion
frame add 500.22 mm.

| Part | Dimensions | Station | Mass |
|---|---|---|---|
| Forward bulkhead / thrust face | G-10 ⌀74.80 × 4.80, 3 holes | 79.40 → 84.20 | 39.0 g |
| Mount tube | ⌀57.10 / 54.50 × 332.08 | 84.20 → 416.28 | 140.0 g |
| Forward centering ring | G-10 ⌀74.80 / 57.10 × 3.20 | 266.22 → 269.42 | 10.9 g |
| Aft centering ring, **slotted** | same, 4 × 3.2 × 8.85 mm slots | 398.08 → 401.28 | 10.2 g |
| Retainer, Aeropack class | bonded 15 mm on the tube OD | 401.28 → 416.28 | 31.0 g |
| *(motor, aft-flush)* | ⌀54.00 × 321.00 | 95.28 → 416.28 | — |
| *(aft fin tab band)* | tab depth 11.15 mm | 271.42 → 410.28 | — |

**231.1 g against the 250 g allowance — +18.9 g.** Mount tube length **332.08 mm** settles a
discrepancy nothing had reconciled: `scripts/make_ork.py` typed 331 mm into itself to have
something to hand OpenRocket, and `docs/04` says 416 mm, which is the booster's own length
copied by mistake.

Holes in the forward bulkhead, from `motor_mount.hole_layout()` so the CAD types nothing:
drogue charge feed-through ⌀4.0 at (22.60, 0), U-bolt legs ⌀8.5 at (0, ±12.50). Tightest
ligament 12.8 mm.

**The aft ring sits inside the fin tab band and is slotted for the four tabs.** That is not a
compromise — it is the arrangement that makes "through-the-wall fins bonded to the motor
mount" mean something structurally, because it ties tab, mount tube and airframe together at
one station. An unslotted ring there is four interferences.

## The first finding — the frozen 12 mm fin tab and a 54 mm mount tube cannot both exist

`scripts/make_cad_profiles.py`'s `TAB_DEPTH = 0.012` is measured inward from the booster
tube's **outer** radius, so the tab tip sat at R 27.70 mm.

```
  booster OD                        R 39.70
  booster ID                        R 37.40
  tab tip at the frozen 12.00 mm    R 27.70
  mount tube OD (this file)         R 28.55   <- the tab was 0.85 mm INSIDE it
  mount tube ID                     R 27.25
  bare 54 mm motor case             R 27.00   <- 0.70 mm clear
```

**The 12 mm tab describes a fin bonded to the bare motor case**, while `design/flutter.py`
and `scripts/baseline.py` both quote the 1.97× aft-fin flutter margin for a tab "bonded
through the wall to the **motor mount**". Four `AftFin` bodies already occupied R 27.70 in
the Fusion document. This was never going to survive an interference check; it survived
because there was nothing yet to check it against.

**Derived, not chosen:** tab depth = booster OR − mount tube OR = **11.15 mm**. The tab then
stands 8.85 mm proud of the airframe bore and lands tangent on the mount tube, giving
1777 mm² of tab-to-tube bond across four fins with no fillet credited.
`scripts/make_cad_profiles.py` and `scripts/make_aft_fin_cad_fusion.py` import
`motor_mount.fin_tab_depth_for()` now instead of each carrying the literal — the same
de-duplication `venting.CANARD_MODULE_FREE_VOLUME` got in correction 38.

## The second finding — the forward bulkhead and the thrust face are the same part

```
booster tube                        416.28 mm
motor, aft-flush                    321.00
forward margin                       95.28
  less coupler engagement          - 79.40
  less joints.BULKHEAD_ALLOWANCE   - 12.00
  = what the BUDGET leaves            3.88 mm
```

There is no room for a separate thrust plate and there does not need to be. One disc closes
the drogue compartment on its forward face, anchors the drogue harness's aft U-bolt there,
and presents its aft face to the motor. That is exactly why `seal.py` handed this part to the
motor mount rather than sizing it as a third bulkhead — a reason `seal.py` stated without
knowing.

The disc as sized is 4.80 mm, not the 12.00 mm the allowance charges, so the real clear gap
is **11.08 mm**. That is not slack to spend. It is the third finding.

## The third finding — that gap is a closed volume in front of a live ejection charge

The Cesaroni Pro54 ships with an ejection charge in its forward closure. This vehicle deploys
on an independent altimeter, and **nothing in this project had ever said what happens to the
motor's own charge.**

The volume it would fire into is bounded by the mount tube's bore, the motor's forward
closure and this bulkhead: **25.85 cm³, sealed on every side.** `seal.ejection_pressure()` —
the project's own model, not a new one — gives:

| Charge | Pressure | Against the disc's 6.69 MPa capacity |
|---|---|---|
| 0.8 g | 6.78 MPa | 1.01× over |
| 1.0 g | 8.48 MPa | 1.27× over |
| **1.2 g** | **10.17 MPa** | **1.52× over** |
| 1.4 g | 11.87 MPa | 1.77× over |
| 1.6 g | 13.56 MPa | 2.03× over |

It fails at every plausible charge mass, so the conclusion does not turn on the assumed
figure — which is just as well, because Cesaroni does not publish one.

**Design answer: a plugged forward closure.** Cesaroni sells one; it is a purchase, not a
modification. Recorded as `motor_mount.FORWARD_CLOSURE_PLUGGED` so the check fails loudly if
anyone ever sets it `False`. Venting the gap is the alternative and it is worse: a hole
through a pressure boundary to solve what a different part number solves for nothing.

## What is still open

* **The fin root moment.** The tab-to-mount-tube bond is checked here for area and for
  clearance. The moment it carries has never been computed by anything in this project, and
  `design/flutter.py` says the same about its own ideal-rigid-root assumption. Swinging the
  finished fin is what settles it.
* **The mount tube's material.** Every margin above uses G-10 **sheet** properties for a
  filament-wound tube, because `design/materials.py` has nothing else. The margins that
  matter are all well clear, which is the only reason that is tolerable.
* **The motor's ejection charge mass** is assumed, not obtained.
* **`MOUNT_TUBE_WALL_OPTIONS`** is the band the common 54 mm offerings fall in, not a quoted
  catalogue. Confirm the vendor's own list before ordering.
* **The motor's aft closure geometry is not modelled.** The thrust face is taken to be the
  forward closure, which is what an aft-flush motor and a screw-on retainer force. A case
  with a proud aft flange would react thrust at the other end of the tube and every ring
  load above would be a different number.
