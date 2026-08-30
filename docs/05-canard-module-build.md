# Canard module — CAD build sheet

Regenerate the profiles with `python scripts/make_cad_profiles.py`. They are written from
`design/configure.py`, so the CAD cannot drift from the analysis. If a dimension here
disagrees with something you remember, regenerate; do not retype.

## State of play — August 2026

Read this first if you are picking the CAD back up. Progress lives in the Onshape document
(`canard-control module`, Part Studio 1), not in this file — this is just a pointer to where
the feature tree stands so a fresh session doesn't have to re-derive it.

**CURRENT as of Aug 2026**, rebuilt for the 35.4° sweep / 0.40 taper. 15 features, 13 parts.

**Done**, in feature-tree order: tube (`Extrude 1`, G10/FR4 1850 kg/m³) → `Hinge Plane`, an
offset from Top, now **68.27 mm** → one canard panel, root LE at **37.71 mm**, root 67.49 /
tip 27.0 / sweep 47.90 (`Sketch 2` / `Extrude 2`) → shaft, ⌀5 mm on the hinge axis
(`Sketch 3` / `Extrude 3`) → wall pass-through cut, reusing the shaft's own sketch so
position matches exactly — this is a **clearance/pass-through hole, not a structural
pocket**; the bearing that carries panel bending lives in the servo frame, not this hole
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

**Two known loose ends on what's built:**
- The servo block's radial (Y) centering is off by ~0.09 mm — not fully constrained, just
  dragged close. Fine for a mass/envelope placeholder; tighten with a real constraint before
  this matters for anything precision-sensitive.
- The block assumes the KST output shaft is centered on its 23.5 mm body. Unconfirmed — check
  the real datasheet before this assumption feeds into anything downstream.

**Not started**: printed bay (step 6 below) — blocked on picking real bracket hardware,
since a placeholder shell wouldn't tell you anything the mass/interference checks need.
Forward wiring pass-through and aft gas seal (mentioned under "what to check," not
originally in the modelling order) are still open. The **interference sweep** (rotate one
panel through ±8° and check the horn, shaft, bay and neighbouring servo clear) has NOT been
run — the mass check has.

**Module mass properties, measured Aug 2026** (all 13 parts, materials assigned):

| | |
|---|---|
| Mass | **0.2599 kg** |
| Volume | 130,889.802 mm³ |
| CoM | X 0, Y 0, **Z 74.138 mm** aft of the module forward face |
| Inertia about CoM | Ixx = Iyy = **593.524** kg·mm², Izz = **626.268** kg·mm² |
| Off-diagonals | zero — the four-fold symmetry check passing |

That 0.2599 kg is against roughly 0.565 kg in the mass budget, and the gap is real, not an
error: the servo frames, outboard bearings and printed bay are not modelled yet. Re-measure
once they exist.

## Drawing 1 — the Step 3 dimensioned drawing

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

### Servos — KST X08 Plus V6.0, 4 off

| | |
|---|---|
| Body | 23.5 × 8.0 × 16.8 mm ±0.2 |
| Orientation | **8.0 mm radial**, 16.8 mm circumferential, 23.5 mm **along the rocket axis** |
| Mount | Body bonded or clamped flat against the inner wall. **Stock lugs trimmed** — they extend the 23.5 mm axis and are not used |
| Output shaft | Radial, through the wall, into the canard root |
| Bearing | Outboard ball bearing in the wall carries the panel bending moment; the servo spline takes torque only |

Four servos need 79.2 mm of arc against 140.7 mm available at the mounting radius. Packaging
is not tight — see `00-requirements.md` §4.2.

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
5. **Servo, as a simple block** — 23.5 × 8.0 × 16.8 mm with the shaft axis located. Do not
   model the real servo; you only need the envelope and the mass. Assign 9 g directly as a
   mass override rather than modelling internals.
6. **Printed bay.** Build it around the servo blocks. PETG/ASA/CF-nylon, **not PLA**.
   Heat-set inserts, not printed threads. Layer lines perpendicular to the load path.
7. **Circular pattern** the panel/shaft/servo/bay set 4× about the tube axis.

## What to check when you are done

- **Mass properties.** Compare the module's mass against the model: 0.147 kg tube +
  0.142 kg canards + 0.036 kg servos + 0.240 kg shafts/bearings/sled. Then take the
  **moments of inertia** and feed them back — that is the number worth having.
- **Interference.** Rotate a panel through ±8° (the deflection limit) and check the horn,
  shaft and bay clear each other and the neighbouring servo through the full sweep.
- **Lug clearance.** Confirm the trimmed-body mounting actually assembles. This is the
  assumption the packaging conclusion rests on.

## Feeding results back

Weighed or CAD-derived masses go into `design/mass.py`; rerun `scripts/robustness.py` and
adjust the nose ballast in response. Measured inertia goes into `design/control.py` — it
will change the pitch mode frequency and therefore the loop rate requirement.

CAD mass properties are much better than the current analytical estimate but they are not a
substitute for weighing the built parts, or for a bifilar pendulum swing test on the
finished vehicle. They shrink the ±30%; they do not close it.
