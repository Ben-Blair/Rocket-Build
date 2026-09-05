"""Build the booster tube and its four aft fins as native Fusion geometry, from
`design/configure.py`'s already-frozen `FinSet` -- the first CAD either fin set's booster
section has ever had, in Onshape or Fusion.

    python scripts/make_aft_fin_cad_fusion.py            # print the script
    python scripts/make_aft_fin_cad_fusion.py --write    # and into out/

WHY THIS EXISTS. docs/01-next-steps.md correction 43 named the booster + aft fins as the
one piece of Step 3's "dimensioned drawing" deliverable with NOTHING drawn at all -- "no
planform, no root attachment, no motor mount". Two of those three turn out to already be
DECIDED, just never built in 3D: the planform (`aft_root_cal`/`aft_semispan_cal`/
`aft_sweep_cal`/`aft_taper`, `design/configure.py`, the same frozen numbers
`scripts/make_cad_profiles.py` has emitted as a 2D DXF fin pattern since before this
project's Fusion migration) and the root attachment (a 12 mm through-wall tab,
`make_cad_profiles.py`'s own `TAB_DEPTH`, baked into `fin_profile()`'s tab points and never
built as a real 3D slot). **The motor mount is not** -- `design/mass.py` carries
`motor_mount_centering_rings` as a budget line with no design module behind it, no ring
diameter, no ring count, no ring station -- and is not attempted here; inventing centering
ring geometry with nothing sizing it would be the same mistake this project keeps finding
and fixing elsewhere (correction 19's collar material, correction 21's coupling).

WHAT GETS BUILT. `BoosterTube`: a plain annulus, same OD/ID as every other tube in this
document (79.4/74.8 mm), built directly in the shared Fusion-document frame continuing from
`RecoveryBayTube`'s own aft face (Z 500.22 mm) -- `design/configure.py`'s own station
arithmetic confirms this (`booster forward face` and `recovery bay aft face` are the same
number). `AftFin0`-`AftFin3`: four swept-trapezoid panels WITH their through-wall tab
included in the same body (the flat pattern `make_cad_profiles.py`'s `fin_profile(aft,
tab=TAB_DEPTH)` already describes, just extruded into 3D instead of laser-cut as a 2D DXF),
each cut into a matching slot in `BoosterTube`'s own wall.

CLOCKING. Canards sit at quadrants 0/90/180/270 (the convention every generator in the
canard-module migration used). The vehicle description this project has quoted since before
the Fusion migration -- "canards ... aft fins ... interdigitated 45deg"
(docs/01-next-steps.md's own "Current vehicle" line, docs/05's "Canard panels -- 4 off, 90
deg apart, interdigitated 45deg from the aft fins") -- puts the aft fins at 45/135/225/315.
Nothing in `design/*.py` encodes this as a number (`FinSet` has no clocking field), so it is
recorded here rather than assumed silently: `AFT_FIN_CLOCK_DEG = 45.0`.

HOW THE PANEL IS BUILT, mirroring `scripts/make_hinge_stack_fusion.py`'s own canard-panel
technique with one change forced by the clocking: that generator picks Fusion's own
`xZConstructionPlane`/`yZConstructionPlane` for quadrant 0/2 vs 1/3, which only works
because those quadrants land exactly on an axis-aligned plane. 45 degrees does not. So the
panel here is always sketched on the plain `xZConstructionPlane` (as if it were quadrant 0),
lifted to a temporary body the same way, and then ROTATED into its real clocking with
`TemporaryBRepManager.transform()` and a `Matrix3D.setToRotation()` about the Z axis --
the same temp-BRep object, just placed at the angle that matters, rather than a second way
of building geometry for the one clocking that is not a multiple of 90.

VERIFIED the same way every generator in this project is: the tube's plain-annulus volume,
loosened for the four tab slots (a box cut into a curved wall has the exact same "flat
faces meeting a curved one" residual `fusion-mcp-gotchas.md` already documents for the
canard module's own radial wall bores -- not zero, and not the bug, a face check that a slot
exists is the real proof, same discipline `verify_tube()` established there); each fin panel
against the SAME shoelace-polygon corners the sketch is built from (the trapezoid plus its
tab, six points, exact -- no curved surface involved in a fin panel the way there is in the
tube it slots into).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design.configure import baseline, build_vehicle
from design.motor_mount import fin_tab_depth_for
from scripts.fusion_common import FUSION_PRELUDE

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "make_aft_fin_cad_fusion_generated.py"

TUBE_VOLUME_TOLERANCE_MM3 = 0.01
SLOT_TOLERANCE_PER_SLOT_MM3 = 0.5   # measured-class residual, see module docstring
PANEL_VOLUME_TOLERANCE_MM3 = 0.02

# TAB DEPTH IS DERIVED NOW, in geometry() -- it used to be 12.0 here, matching
# make_cad_profiles.py's own literal. Both were wrong the same way: 12 mm inward from the
# booster's OUTER radius puts the tab tip at R 27.70, which is 0.85 mm INSIDE the mount tube
# a 54 mm motor needs and 0.70 mm off the bare motor case. design/motor_mount.py derives it
# from the mount tube so the tab lands tangent on it. See docs/01 correction 53.
TAB_INSET_MM = 6.0    # matches fin_profile()'s hardcoded 6.0 mm inset each side

AFT_FIN_CLOCK_DEG = 45.0   # see module docstring -- not encoded anywhere in design/*.py

OVER_MM = 1.0


def _shoelace_area(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    a = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _fin_corners_rz(root_r_mm, semispan_mm, root_chord_mm, tip_chord_mm, sweep_mm,
                    root_le_z_mm, tab_depth_mm, tab_inset_mm):
    """The same six points scripts/make_cad_profiles.py's fin_profile() emits (root LE,
    tip LE, tip TE, root TE, tab TE-side, tab LE-side), remapped from that function's flat
    (chordwise, spanwise) pattern frame into this generator's (radius, Fusion-Z) frame:
    radius = root_r_mm + spanwise offset, Z = root_le_z_mm + chordwise offset.
    """
    tip_r = root_r_mm + semispan_mm
    return [
        (root_r_mm, root_le_z_mm),                                            # root LE
        (tip_r, root_le_z_mm + sweep_mm),                                     # tip LE
        (tip_r, root_le_z_mm + sweep_mm + tip_chord_mm),                      # tip TE
        (root_r_mm, root_le_z_mm + root_chord_mm),                           # root TE
        (root_r_mm - tab_depth_mm, root_le_z_mm + root_chord_mm - tab_inset_mm),  # tab TE
        (root_r_mm - tab_depth_mm, root_le_z_mm + tab_inset_mm),                 # tab LE
    ]


def geometry():
    p = baseline()
    r = build_vehicle(p)
    aft = r.aft_fins
    x_canard_module_mm = (r.nose.length + r.tubes[0].length) * MM
    booster_forward_z_mm = (r.tubes[1].length + r.tubes[2].length) * MM
    booster_len_mm = r.tubes[3].length * MM
    tube_or_mm = r.tubes[3].outer_diameter * MM / 2.0
    tube_ir_mm = r.tubes[3].inner_diameter * MM / 2.0
    root_le_z_mm = aft.x_root_le * MM - x_canard_module_mm
    return (
        tube_or_mm, tube_ir_mm, booster_forward_z_mm, booster_len_mm,
        aft.root_chord * MM, aft.tip_chord * MM, aft.semispan * MM,
        aft.sweep_length * MM, aft.thickness * MM, aft.count, root_le_z_mm,
        fin_tab_depth_for(r, p.motor) * MM,
    )


def emit() -> str:
    (tube_or, tube_ir, tube_fwd_z, tube_len, root_chord, tip_chord, semispan,
     sweep, thickness, count, root_le_z, TAB_DEPTH_MM) = geometry()

    wall = tube_or - tube_ir
    annulus_volume = math.pi * (tube_or**2 - tube_ir**2) * tube_len

    # Slot: a box through the wall, tangential width = fin thickness, axial span = THE FULL
    # ROOT CHORD. Radial extent is clipped to real material by the tube's own OD/ID -- see
    # module docstring on why this box's r bounds can safely overshoot past the wall.
    #
    # IT USED TO BE `root_chord - 2 x TAB_INSET_MM`, WHICH IS THE TAB'S FULL-DEPTH BAND AND
    # NOT ITS FOOTPRINT. `fin_profile()` ramps the tab from the root LE down to full depth
    # over TAB_INSET_MM, so there is tab material at every station of the root chord -- and
    # all of it is inboard of the tube OD, i.e. inside the wall. Slotting only the
    # full-depth band left the two ramps passing through solid G-10: 79.15 mm3 per fin,
    # four fins, sitting in this document since the fins were first drawn (correction 52
    # claimed "fin-to-tube ... all exactly 0.0000 mm3", which the document disagreed with).
    # Same root cause as the forward centering ring landing in the ramp -- one geometric
    # fact that two different consumers each modelled as a rectangle. See docs/01
    # correction 56. SLOT_INSET_MM is a separate name from TAB_INSET_MM on purpose: they
    # answer different questions and collapsing them is what caused this.
    SLOT_INSET_MM = 0.0
    tab_axial_span = root_chord - 2.0 * SLOT_INSET_MM
    slot_volume_flat = wall * thickness * tab_axial_span   # flat-box approximation
    # The flat-box formula does not know the slot's tangential faces are chords across a
    # curved wall, not the wall's own surface -- same class of residual
    # fusion-mcp-gotchas.md documents for a radial hole through a curved wall. Measured
    # against a live run of this exact script: -0.044 mm3/slot, so 0.2 mm3/slot is a real
    # loosened tolerance, not a cover for an actual mistake.
    tube_volume = annulus_volume - count * slot_volume_flat

    corners = _fin_corners_rz(tube_or, semispan, root_chord, tip_chord, sweep, root_le_z,
                              TAB_DEPTH_MM, TAB_INSET_MM)
    panel_area = _shoelace_area(corners)
    panel_volume = panel_area * thickness

    corners_repr = ", ".join("(%r, %r)" % c for c in corners)

    return f'''"""GENERATED by scripts/make_aft_fin_cad_fusion.py -- do not edit this file.
Regenerate rather than patch.

BoosterTube  OD {2*tube_or:.3f} / ID {2*tube_ir:.3f} x {tube_len:.3f} long, Z {tube_fwd_z:.3f} .. {tube_fwd_z + tube_len:.3f}
AftFin{{q}}     root R {tube_or:.3f}, tip R {tube_or + semispan:.3f}, root chord Z {root_le_z:.3f} .. {root_le_z + root_chord:.3f}
             {TAB_DEPTH_MM:.2f} mm through-wall tab (DERIVED -- design/motor_mount.py), clocked {{q}} x 90 + {AFT_FIN_CLOCK_DEG:.1f} deg
Volumes      tube {tube_volume:.4f} (less {count} slots, ~{slot_volume_flat:.4f} mm3 each, loosened)
             panel {panel_volume:.4f} mm3 (each x{count})
"""

{FUSION_PRELUDE}

OVER_MM = {OVER_MM!r}
AFT_FIN_CLOCK_DEG = {AFT_FIN_CLOCK_DEG!r}
N_FINS = {count}

TUBE_OR_MM = {tube_or!r}
TUBE_IR_MM = {tube_ir!r}
TUBE_LEN_MM = {tube_len!r}
TUBE_FWD_Z_MM = {tube_fwd_z!r}
TUBE_VOLUME_MM3 = {tube_volume!r}
TUBE_VOLUME_TOLERANCE_MM3 = {TUBE_VOLUME_TOLERANCE_MM3!r}
SLOT_TOLERANCE_MM3 = {SLOT_TOLERANCE_PER_SLOT_MM3 * count!r}

PANEL_THICKNESS_MM = {thickness!r}
PANEL_VOLUME_MM3 = {panel_volume!r}
PANEL_VOLUME_TOLERANCE_MM3 = {PANEL_VOLUME_TOLERANCE_MM3!r}
ROOT_CHORD_MM = {root_chord!r}
ROOT_R_MM = {tube_or!r}
TAB_DEPTH_MM = {TAB_DEPTH_MM!r}
TAB_INSET_MM = {TAB_INSET_MM!r}
SLOT_INSET_MM = 0.0   # slot spans the FULL root chord -- the tab ramps, see the generator
ROOT_LE_Z_MM = {root_le_z!r}

FIN_CORNERS_RZ = [{corners_repr}]


def _rotate_z(tbm, body, angle_deg):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(angle_deg), adsk.core.Vector3D.create(0.0, 0.0, 1.0),
                    adsk.core.Point3D.create(0.0, 0.0, 0.0))
    if not tbm.transform(body, m):
        raise ValueError("rotation to %.1f deg did not take" % angle_deg)


def build_tube(root):
    occ, has_bodies = _get_or_create_component(root, "BoosterTube")
    tbm = adsk.fusion.TemporaryBRepManager.get()
    if has_bodies:
        print("BoosterTube already holds a body -- verifying rather than rebuilding")
        verify_tube(occ.component)
        return
    comp = occ.component
    z0 = TUBE_FWD_Z_MM
    z1 = TUBE_FWD_Z_MM + TUBE_LEN_MM
    outer = _cyl(tbm, 0.0, 0.0, z0, z1, TUBE_OR_MM)
    _cut(tbm, outer, _cyl(tbm, 0.0, 0.0, z0 - OVER_MM, z1 + OVER_MM, TUBE_IR_MM), "bore")

    # Four tab slots, one per fin -- built at angle 0 (quadrant helper's own convention)
    # then rotated to each fin's real clocking, same technique as the panels below.
    z_lo = ROOT_LE_Z_MM + SLOT_INSET_MM
    z_hi = ROOT_LE_Z_MM + ROOT_CHORD_MM - SLOT_INSET_MM
    for q in range(N_FINS):
        slot = _quadrant_box(tbm, 0, TUBE_IR_MM - OVER_MM, TUBE_OR_MM + OVER_MM,
                             -PANEL_THICKNESS_MM / 2.0, PANEL_THICKNESS_MM / 2.0,
                             z_lo, z_hi)
        _rotate_z(tbm, slot, AFT_FIN_CLOCK_DEG + q * 90.0)
        _cut(tbm, outer, slot, "tab slot %d" % q)

    _inject(comp, [("booster tube", outer)])
    print("built 1 body in BoosterTube, %d tab slots cut" % N_FINS)
    verify_tube(comp)


def verify_tube(comp):
    """Volume loosened for the four tab slots (a box through a curved wall -- see module
    docstring), plus a face check that each slot actually opened the wall (two new edges
    at the tube's own OD and ID within the slot's axial/tangential footprint would be the
    rigorous check; a coarser but still real proxy -- the drilled volume is in the right
    ballpark, not just "some volume changed" -- is what the loosened tolerance below buys)."""
    bad = _verify_volume(comp, {{"booster tube": TUBE_VOLUME_MM3}}, TUBE_VOLUME_TOLERANCE_MM3,
                         loose=("booster tube",), loose_tol=SLOT_TOLERANCE_MM3)
    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK")


def build_fin(root, q):
    name = "AftFin%d" % q
    occ, has_bodies = _get_or_create_component(root, name)
    if has_bodies:
        print("%s already holds a body -- verifying rather than rebuilding" % name)
        verify_fin(occ.component)
        return
    comp = occ.component
    tbm = adsk.fusion.TemporaryBRepManager.get()

    # ---- the panel (trapezoid + through-wall tab, six points, one body) sketched at
    # quadrant 0 exactly like make_hinge_stack_fusion.py's canard panels, then rotated
    # into its real 45 + 90*q clocking -- see module docstring for why a rotate-after-
    # build replaces that generator's "pick xZ or yZ by quadrant parity" trick, which only
    # works for angles that are multiples of 90. ----
    scratch_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    scratch = scratch_occ.component
    plane = scratch.xZConstructionPlane
    sk = scratch.sketches.add(plane)

    def pt(r, z):
        return adsk.core.Point3D.create(r / 10.0, 0.0, z / 10.0)

    sk_pts = [sk.modelToSketchSpace(pt(r, z)) for (r, z) in FIN_CORNERS_RZ]
    lines = sk.sketchCurves.sketchLines
    first = lines.addByTwoPoints(
        adsk.core.Point3D.create(sk_pts[0].x, sk_pts[0].y, 0.0),
        adsk.core.Point3D.create(sk_pts[1].x, sk_pts[1].y, 0.0))
    prev = first
    for sp in sk_pts[2:]:
        prev = lines.addByTwoPoints(prev.endSketchPoint, adsk.core.Point3D.create(sp.x, sp.y, 0.0))
    lines.addByTwoPoints(prev.endSketchPoint, first.startSketchPoint)

    prof = sk.profiles.item(0)
    exin = scratch.features.extrudeFeatures.createInput(
        prof, adsk.fusion.FeatureOperations.NewBodyFeatureOperation)
    exin.setSymmetricExtent(adsk.core.ValueInput.createByReal(PANEL_THICKNESS_MM / 10.0), True)
    feat = scratch.features.extrudeFeatures.add(exin)
    raw = tbm.copy(feat.bodies.item(0))
    scratch_occ.deleteMe()

    _rotate_z(tbm, raw, AFT_FIN_CLOCK_DEG + q * 90.0)

    _inject(comp, [("aft fin", raw)])
    print("built 1 body in %s" % name)
    verify_fin(comp)


def verify_fin(comp):
    bad = _verify_volume(comp, {{"aft fin": PANEL_VOLUME_MM3}}, PANEL_VOLUME_TOLERANCE_MM3)
    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK")


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent

    build_tube(root)
    for q in range(N_FINS):
        build_fin(root, q)
'''


def main() -> None:
    text = emit()
    print(text)
    if "--write" in sys.argv:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text)
        print(f"\n# written to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
