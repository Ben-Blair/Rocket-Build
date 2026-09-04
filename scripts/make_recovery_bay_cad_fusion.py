"""Build the recovery bay tube as native Fusion geometry, and place the already-built
`RecoveryInternalBulkhead` (scripts/make_seal_cad_fusion.py) at its real station inside it.

    python scripts/make_recovery_bay_cad_fusion.py            # print the script
    python scripts/make_recovery_bay_cad_fusion.py --write    # and into out/

WHY THIS EXISTS. docs/01-next-steps.md's own account of what Step 3's dimensioned-drawing
deliverable still owes (correction 43, restated after the canard module's Fusion migration
closed in correction 50): "the recovery bay (no tube modelled, an internal bulkhead drawn
but not assembled...)". The bulkhead stopped being true the session `RecoveryInternalBulkhead`
was built (correction 50) -- but it was built UNPLACED, at its own local origin, same
precedent as M2's servo/bearing before M4 placed them. This closes "no tube modelled" and
"not assembled" together, in the SAME shared Fusion-document frame the canard module and
`NavBay` already use (Z = 0 at the canard module's forward face), because the recovery bay
is physically the next section aft of it: `design/joints.py`'s "canard module / recovery
bay" joint is exactly that interface, and its bulkhead -- the aft gas seal -- already sits
at Z 138.12 -> 142.92 in this document (scripts/make_seal_cad_fusion.py).

WHAT GETS BUILT. `RecoveryBayTube`: a plain tube, OD 79.4 / ID 74.8 mm (the same wall as the
canard module's own `Tube`), length 357.3 mm (`recovery_bay_cal = 4.5` in
`design/configure.py`), running Z 142.92 -> 500.22 -- continuing directly from the aft gas
seal's own aft face, which is also the canard module's own aft face. No wall bores, no
ports: `design/ports.py` puts the nav bay's static ports where they are precisely because
the recovery bay has no equivalent need drawn anywhere in this project.

WHERE THE BULKHEAD GOES, and it is READ OFF THE PACKING MODEL, not assumed: main
compartment is FORWARD (`design/recovery.py`'s own conduit note -- "starts at the aft gas
seal and ends at the internal bulkhead, where the drogue's charge is" -- and
`design/joints.py`'s own per-joint notes -- "MAIN ejection separates here" at the forward
joint, "DROGUE ejection separates here" at the aft one), so:

    aft gas seal aft face (tube forward face)              Z 142.9200 mm
    + main compartment packed length (evaluate().packing)  + 229.5003 mm
    = bulkhead allowance band starts here                  Z 372.4203 mm
    + 3 mm epoxy fillet clearance (INTERNAL_BULKHEAD_STACK  + 3.0000 mm
      is disc 4.8 + fillet 3 + fillet 3 = 10.8 mm, configure.py)
    = bulkhead DISC forward face                            Z 375.4203 mm
    + bulkhead disc thickness                                + 4.8000 mm
    = bulkhead disc aft face / drogue compartment starts     Z 380.2203 mm
    + drogue compartment packed length                       + 89.7152 mm
    = drogue compartment ends                                Z 469.9355 mm
      (27.28 mm of slack remains to the tube's own aft face, Z 500.22 -- where the
      "recovery bay / booster" joint's anchored coupler half bonds in, per
      design/joints.py's own budget for that joint)

The bulkhead is centred in its 10.8 mm allowance band (3 mm clearance each face) rather
than placed flush against either compartment, mirroring the "3 mm epoxy fillet on each
face" `INTERNAL_BULKHEAD_STACK` is itself built from (`design/configure.py`).

WHAT THIS DOES NOT DRAW, and it is a real gap rather than an oversight: the U-bolt HOLES
through the bulkhead are already cut (`scripts/make_seal_cad_fusion.py`, from
`design/seal.py`'s own hole layout), but the U-bolt hardware itself, its backing plate, and
the charge well are not drawn here because none of them has ever been SIZED anywhere in
this project -- `scripts/make_bulkhead_cad.py`'s own docstring says so plainly ("The
backing plate is the one that matters ... and it is not here"). Drawing dimensions that
have never been chosen would be inventing a design decision, not recording one; see the
docs/01-next-steps.md correction this generator ships with for the open item stated
explicitly rather than quietly worked around.

VERIFIED the same way every generator in this migration is: the tube's volume against the
plain annulus formula, to the fourth decimal (no wall bores here, so this one gets the
tight tolerance the canard module's own `Tube` could not use); the bulkhead's placement by
reading its OWN occurrence transform back and confirming the translated bounding box lands
where the station arithmetic above says it should, not by trusting the matrix that was set.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import recovery
from design.configure import INTERNAL_BULKHEAD_STACK, baseline, evaluate
from scripts.fusion_common import FUSION_PRELUDE

OUT = Path(__file__).resolve().parents[1] / "out" / "make_recovery_bay_cad_fusion_generated.py"

VOLUME_TOLERANCE_MM3 = 0.01

# The canard module's own aft face -- confirmed live off the Tube body's bounding box in
# the session that built AftGasSeal (scripts/make_seal_cad_fusion.py), not re-derived here.
CANARD_MODULE_AFT_FACE_MM = 142.92

# Epoxy fillet clearance either side of the bulkhead disc, half of
# (INTERNAL_BULKHEAD_STACK - disc thickness) -- see this file's own docstring.
FILLET_CLEARANCE_MM = 3.0


def _geometry():
    ev = evaluate(baseline())
    rec_tube = next(t for t in ev.rocket.tubes if t.name == "recovery bay")
    p = ev.packing
    lengths = {name: length for name, _vol, length in p.compartments}
    return (
        rec_tube.outer_diameter * 1000.0 / 2.0,
        rec_tube.inner_diameter * 1000.0 / 2.0,
        rec_tube.length * 1000.0,
        lengths["main"] * 1000.0,
        lengths["drogue"] * 1000.0,
        INTERNAL_BULKHEAD_STACK * 1000.0,
    )


def emit() -> str:
    tube_or, tube_ir, tube_len, main_len, drogue_len, bulkhead_stack_mm = _geometry()
    tube_vol = 3.141592653589793 * (tube_or**2 - tube_ir**2) * tube_len
    bulkhead_disc_mm = bulkhead_stack_mm - 2.0 * FILLET_CLEARANCE_MM

    return f'''"""GENERATED by scripts/make_recovery_bay_cad_fusion.py -- do not edit this
file. Regenerate rather than patch.

Builds RecoveryBayTube (Z {CANARD_MODULE_AFT_FACE_MM:.4f} -> {CANARD_MODULE_AFT_FACE_MM + tube_len:.4f} mm)
and translates the existing RecoveryInternalBulkhead occurrence to its real station.
Idempotent: verifies rather than rebuilds/re-translates if the tube already has a body or
the bulkhead is already away from local Z 0.
"""

{FUSION_PRELUDE}

VOLUME_TOLERANCE_MM3 = {VOLUME_TOLERANCE_MM3!r}
OVER_MM = 1.0

TUBE_OR_MM = {tube_or!r}
TUBE_IR_MM = {tube_ir!r}
TUBE_LEN_MM = {tube_len!r}
TUBE_FORWARD_Z_MM = {CANARD_MODULE_AFT_FACE_MM!r}
TUBE_VOLUME_MM3 = {tube_vol!r}

MAIN_LEN_MM = {main_len!r}
BULKHEAD_STACK_MM = {bulkhead_stack_mm!r}
FILLET_CLEARANCE_MM = {FILLET_CLEARANCE_MM!r}
BULKHEAD_DISC_MM = {bulkhead_disc_mm!r}
DROGUE_LEN_MM = {drogue_len!r}

# Where the bulkhead DISC's own forward face lands, in the shared document frame.
BULKHEAD_FORWARD_Z_MM = TUBE_FORWARD_Z_MM + MAIN_LEN_MM + FILLET_CLEARANCE_MM


def _occ(root, name):
    for o in root.occurrences:
        if o.component.name == name:
            return o
    raise ValueError("no occurrence named %r" % name)


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()

    # -- Recovery bay tube: plain annulus, no wall bores or ports --
    tube_occ, tube_has_bodies = _get_or_create_component(root, "RecoveryBayTube")
    if not tube_has_bodies:
        z0 = TUBE_FORWARD_Z_MM
        z1 = TUBE_FORWARD_Z_MM + TUBE_LEN_MM
        outer = _cyl(tbm, 0.0, 0.0, z0, z1, TUBE_OR_MM)
        _cut(tbm, outer, _cyl(tbm, 0.0, 0.0, z0 - OVER_MM, z1 + OVER_MM, TUBE_IR_MM), "bore")
        _inject(tube_occ.component, [("recovery bay tube", outer)])
        print("RecoveryBayTube: built, Z %.4f -> %.4f mm" % (z0, z1))
    else:
        print("RecoveryBayTube: already has bodies, verifying only")
    bad = _verify_volume(tube_occ.component, {{"recovery bay tube": TUBE_VOLUME_MM3}},
                         VOLUME_TOLERANCE_MM3)

    # -- Place the already-built internal bulkhead: translate its occurrence from local
    # Z [0, disc thickness] to the real station computed above. Idempotent by reading the
    # occurrence's own current transform back, not by a flag this script sets itself. --
    bulk_occ = _occ(root, "RecoveryInternalBulkhead")
    cur = bulk_occ.transform
    already_placed = abs(cur.translation.z * 10.0 - BULKHEAD_FORWARD_Z_MM) < 1e-6
    if not already_placed:
        m = adsk.core.Matrix3D.create()
        m.translation = adsk.core.Vector3D.create(0.0, 0.0, BULKHEAD_FORWARD_Z_MM / 10.0)
        bulk_occ.transform = m
        print("RecoveryInternalBulkhead: translated to Z %.4f mm forward face"
              % BULKHEAD_FORWARD_Z_MM)
    else:
        print("RecoveryInternalBulkhead: already at its real station")

    # Read the transform back and confirm the body's own bounding box landed where the
    # station arithmetic says -- not just that the matrix was accepted.
    body = None
    for b in bulk_occ.bRepBodies:
        if b.name == "recovery internal bulkhead":
            body = b
    if body is None:
        bad.append("RecoveryInternalBulkhead has no 'recovery internal bulkhead' body")
    else:
        bb = body.boundingBox
        got_z0 = bb.minPoint.z * 10.0
        got_z1 = bb.maxPoint.z * 10.0
        want_z1 = BULKHEAD_FORWARD_Z_MM + BULKHEAD_DISC_MM
        print("  bulkhead (occurrence proxy) Z %.4f -> %.4f mm  (want %.4f -> %.4f)"
              % (got_z0, got_z1, BULKHEAD_FORWARD_Z_MM, want_z1))
        if abs(got_z0 - BULKHEAD_FORWARD_Z_MM) > 1e-4 or abs(got_z1 - want_z1) > 1e-4:
            bad.append("bulkhead landed at Z %.4f -> %.4f mm, wanted %.4f -> %.4f"
                       % (got_z0, got_z1, BULKHEAD_FORWARD_Z_MM, want_z1))

    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK -- recovery bay tube built and internal bulkhead placed at its real station")
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
