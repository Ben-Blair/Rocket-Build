# Canard module — CAD build sheet

Regenerate the profiles with `python scripts/make_cad_profiles.py`. They are written from
`design/configure.py`, so the CAD cannot drift from the analysis. If a dimension here
disagrees with something you remember, regenerate; do not retype.

## State of play — August 2026

Read this first if you are picking the CAD back up. Progress lives in the Onshape document
(`canard-control module`, Part Studio 1), not in this file — this is just a pointer to where
the feature tree stands so a fresh session doesn't have to re-derive it.

**Done**, in feature-tree order: tube (`Extrude 1`, G10/FR4 1850 kg/m³) → hinge datum plane
→ one canard panel, correctly oriented and dimensioned, root LE at 43.67 mm, panel CP
forward-hinge relationship verified (`Sketch 2` / `Extrude 2`) → shaft, ⌀5 mm on the hinge
axis (`Sketch 3` / `Extrude 3`) → wall pass-through cut, reusing the shaft's own sketch so
position matches exactly — this is a **clearance/pass-through hole, not a structural
pocket**; the bearing that carries panel bending lives in the servo frame, not this hole
(`Extrude 4`) → servo envelope block, 23.5×8.0×16.8 mm, mass-tuned to 9 g via a custom
material density (2849 kg/m³) rather than a direct mass override, since no such field was
found in this Onshape UI (`Sketch 4` / `Extrude 5`, part renamed "Servo (envelope, KST X08
Plus)"). Parts (4): tube, panel, shaft, servo block.

**Two known loose ends on what's built:**
- The servo block's radial (Y) centering is off by ~0.09 mm — not fully constrained, just
  dragged close. Fine for a mass/envelope placeholder; tighten with a real constraint before
  this matters for anything precision-sensitive.
- The block assumes the KST output shaft is centered on its 23.5 mm body. Unconfirmed — check
  the real datasheet before this assumption feeds into anything downstream.

**Not started**: printed bay (step 6 below) — blocked on picking real bracket hardware, since
a placeholder shell wouldn't tell you anything the mass/interference checks need. Circular
pattern ×4 (step 7) is well-defined and doesn't depend on the bay; it's the natural next
step. Forward wiring pass-through and aft gas seal (mentioned under "what to check," not
originally in the modelling order) are still open. The mass and interference checks at the
end of this document haven't been run.

## Why model this before the rest of the rocket

Three reasons, in order of value:

1. **Mass properties.** `README.md` flags the inertias as **±30%, "crude analytical
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
| Root chord | 55.6 mm |
| Tip chord | 38.9 mm |
| Semispan | 67.5 mm (exposed, from the tube surface) |
| Sweep, LE | 8.3 mm |
| Thickness | 3.0 mm |
| Root LE position | 43.7 mm aft of the module's forward end |
| Root chord spans | 43.7 → 99.2 mm within the module |
| **Hinge axis** | **57.2 mm from the module forward end**, i.e. 13.5 mm aft of the root LE |
| Panel CP (reference) | 15.9 mm aft of the root LE |

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
2. **Datum planes.** One plane at 57.2 mm from the forward face for the hinge axes, and
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
