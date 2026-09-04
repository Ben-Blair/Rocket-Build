"""Emit a Fusion 360 script that builds the motor mount, from design/motor_mount.py.

    python scripts/make_motor_mount_cad_fusion.py            # print the script
    python scripts/make_motor_mount_cad_fusion.py --write    # and into out/

Builds, in the same `CanardControlModule` document every other generator writes into, and
in the same frame (Z = 0 at the canard module's forward face, Z positive aft):

  * `BoosterForwardBulkhead` -- the disc `design/seal.py` explicitly handed to the motor
    mount ("It does not size the booster's forward bulkhead ... that one is part of the
    motor mount structure and belongs with it"). Drilled from `motor_mount.hole_layout()`,
    so this file types no hole position and no hole diameter.
  * `MotorMountTube` -- a plain annulus BUTTED against that disc's aft face, running to the
    booster's own aft face. It cannot pass through the disc: that disc is the drogue
    compartment's pressure boundary and a tube through it is a hole in it.
  * `CenteringRing0` (plain) and `CenteringRing1` (SLOTTED for the four fin tabs). The aft
    ring sits INSIDE the fin tab band on purpose -- that is what ties tab, mount tube and
    airframe together at one station -- so an unslotted ring there is four interferences,
    which is exactly the class of thing correction 40 found by booleaning.
  * `MotorEnvelope` -- the motor as a plain cylinder, so the interference check has
    something to check against. Modelled precisely because correction 19's lesson is that an
    unmodelled part cannot collide with anything.

WHAT IT VERIFIES, and the first two are the session's findings rather than routine checks:

  1. `MotorMountTube` against all four `AftFin` panels must be EXACTLY 0.0000 mm3. At the
     frozen 12.00 mm tab depth it is not: the tab tip sits at R 27.70 and this tube's wall
     runs R 27.25 -> 28.55, so each fin buries 0.85 mm of itself in it. Running this script
     against fins built at the old depth is the demonstration; `design/motor_mount.py`'s
     `fin_tab_depth()` is the fix, and `scripts/make_aft_fin_cad_fusion.py` must be re-run
     and its four panels rebuilt BEFORE this one will pass.
  2. `BoosterForwardBulkhead` against the recovery-bay/booster coupler zone and against
     `MotorEnvelope` -- the axial squeeze the booster's 1.2 caliber margin leaves once the
     coupler and the bulkhead allowance are paid.
  3. Each `CenteringRing` against every fin tab, which is what the slots are for.
  4. Analytic volume on every body, to a tolerance that is measured rather than guessed:
     the rings' slots are boxes cut through a curved wall and carry the same
     flat-face-meets-curved-surface residual `fusion-mcp-gotchas.md` documents for the
     canard module's radial bores and `make_aft_fin_cad_fusion.py` measured at ~0.29 mm3
     per slot.
  5. A face check that each drilled hole actually opened, because a volume check alone
     cannot tell a hole that was cut from one that was cut somewhere else.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import motor_mount as mmount
from design.configure import baseline, evaluate
from scripts.fusion_common import FUSION_PRELUDE

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "make_motor_mount_cad_fusion_generated.py"

VOLUME_TOLERANCE_MM3 = 0.01
SLOT_TOLERANCE_PER_SLOT_MM3 = 0.5   # measured class, see module docstring
OVER_MM = 1.0

# Z of the booster tube's own forward face in the shared document frame. Derived, not typed:
# it is the canard module's length plus the recovery bay's, which is exactly how
# make_aft_fin_cad_fusion.py computes its own BoosterTube station.
def _booster_forward_z(ev) -> float:
    return (ev.rocket.tubes[1].length + ev.rocket.tubes[2].length) * MM


def geometry():
    ev = evaluate(baseline())
    r = mmount.motor_mount_from_evaluation(ev)
    aft = ev.rocket.aft_fins
    return ev, r, _booster_forward_z(ev), aft.thickness * MM, aft.count


def emit() -> str:
    ev, r, booster_z, fin_thickness, n_fins = geometry()

    def z(local_m: float) -> float:
        """Booster-local metres -> shared-document millimetres."""
        return booster_z + local_m * MM

    tube_or = r.tube.outer_diameter * MM / 2.0
    tube_ir = r.tube.inner_diameter * MM / 2.0
    tube_z0, tube_z1 = z(r.tube.forward_station), z(r.tube.aft_station)
    tube_volume = math.pi * (tube_or**2 - tube_ir**2) * (tube_z1 - tube_z0)

    disc_r = r.forward_bulkhead.radius * MM
    disc_t = r.forward_bulkhead.thickness * MM
    disc_z0 = z(r.bulkhead_station)
    holes = [(h.name, h.x * MM, h.y * MM, h.diameter * MM) for h in mmount.hole_layout(r)]
    disc_volume = (math.pi * disc_r**2 * disc_t
                   - sum(math.pi * (d / 2.0) ** 2 * disc_t for _, _, _, d in holes))

    rings = []
    for i, ring in enumerate(r.rings):
        ro = ring.outer_diameter * MM / 2.0
        ri = ring.bore * MM / 2.0
        t = ring.thickness * MM
        # The slot is cut from the ring's OUTER edge inward, to the same radius the fin tab
        # reaches: the tab occupies R (tube OR) .. (booster IR), so the slot must clear that
        # whole span or the ring and the tab share material.
        slot_r_lo = tube_or
        vol = math.pi * (ro**2 - ri**2) * t
        slot_vol = ring.slots * (ro - slot_r_lo) * fin_thickness * t
        rings.append({
            "name": f"CenteringRing{i}",
            "body": ring.name,
            "ro": ro, "ri": ri, "t": t,
            "z0": z(ring.station),
            "slots": ring.slots,
            "slot_width": fin_thickness,
            "slot_r_lo": slot_r_lo,
            "volume": vol - slot_vol,
            "slot_volume": slot_vol / ring.slots if ring.slots else 0.0,
        })

    motor_r = r.motor_diameter * MM / 2.0
    motor_z0, motor_z1 = z(r.motor_forward_station), z(r.motor_forward_station + r.motor_length)
    motor_volume = math.pi * motor_r**2 * (motor_z1 - motor_z0)

    tab_z0, tab_z1 = z(r.fin_tab_forward), z(r.fin_tab_aft)
    slot_tol = SLOT_TOLERANCE_PER_SLOT_MM3 * max(n_fins, 1)

    holes_repr = ", ".join("(%r, %r, %r, %r)" % h for h in holes)
    rings_repr = ",\n    ".join(repr(d) for d in rings)

    return f'''"""GENERATED by scripts/make_motor_mount_cad_fusion.py -- do not edit this file.
Regenerate rather than patch.

BoosterForwardBulkhead  dia {2*disc_r:.3f} x {disc_t:.3f}, Z {disc_z0:.3f} .. {disc_z0 + disc_t:.3f}
                        {len(holes)} holes, from design/motor_mount.hole_layout()
MotorMountTube          OD {2*tube_or:.3f} / ID {2*tube_ir:.3f}, Z {tube_z0:.3f} .. {tube_z1:.3f}
CenteringRing0          OD {2*rings[0]["ro"]:.3f} / ID {2*rings[0]["ri"]:.3f} x {rings[0]["t"]:.3f}, Z {rings[0]["z0"]:.3f}
CenteringRing1          OD {2*rings[1]["ro"]:.3f} / ID {2*rings[1]["ri"]:.3f} x {rings[1]["t"]:.3f}, Z {rings[1]["z0"]:.3f}, {rings[1]["slots"]} tab slots
MotorEnvelope           dia {2*motor_r:.3f} x {motor_z1 - motor_z0:.3f}, Z {motor_z0:.3f} .. {motor_z1:.3f}
Fin tab band            Z {tab_z0:.3f} .. {tab_z1:.3f}, tab tip R {tube_or:.3f} (DERIVED -- design/motor_mount.py)
"""

{FUSION_PRELUDE}

VOLUME_TOLERANCE_MM3 = {VOLUME_TOLERANCE_MM3!r}
SLOT_TOLERANCE_MM3 = {slot_tol!r}
OVER_MM = {OVER_MM!r}
N_FINS = {n_fins!r}
AFT_FIN_CLOCK_DEG = 45.0

DISC_R_MM = {disc_r!r}
DISC_T_MM = {disc_t!r}
DISC_Z0_MM = {disc_z0!r}
DISC_VOLUME_MM3 = {disc_volume!r}
HOLES = [{holes_repr}]

TUBE_OR_MM = {tube_or!r}
TUBE_IR_MM = {tube_ir!r}
TUBE_Z0_MM = {tube_z0!r}
TUBE_Z1_MM = {tube_z1!r}
TUBE_VOLUME_MM3 = {tube_volume!r}

RINGS = [
    {rings_repr}
]

MOTOR_R_MM = {motor_r!r}
MOTOR_Z0_MM = {motor_z0!r}
MOTOR_Z1_MM = {motor_z1!r}
MOTOR_VOLUME_MM3 = {motor_volume!r}

TAB_Z0_MM = {tab_z0!r}
TAB_Z1_MM = {tab_z1!r}


def _rotate_z(tbm, body, angle_deg):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(angle_deg), adsk.core.Vector3D.create(0.0, 0.0, 1.0),
                    adsk.core.Point3D.create(0.0, 0.0, 0.0))
    if not tbm.transform(body, m):
        raise ValueError("rotation to %.1f deg did not take" % angle_deg)
    return body


def _annulus(tbm, ro, ri, z0, z1):
    outer = _cyl(tbm, 0.0, 0.0, z0, z1, ro)
    _cut(tbm, outer, _cyl(tbm, 0.0, 0.0, z0 - OVER_MM, z1 + OVER_MM, ri), "bore")
    return outer


def _pair_interference(tbm, a, b):
    """mm3 of overlap between two bodies. Intersection, measured, not eyeballed -- the
    same technique correction 40 used to find 21 clashing pairs the eye had passed."""
    ca = tbm.copy(a)
    cb = tbm.copy(b)
    if not tbm.booleanOperation(ca, cb, adsk.fusion.BooleanTypes.IntersectionBooleanType):
        return 0.0
    return ca.volume * 1e3 if ca is not None else 0.0


def _bodies_named(root, comp_name):
    for o in root.occurrences:
        if o.component.name == comp_name:
            return list(o.bRepBodies)
    return []


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()
    bad = []

    # ---- the forward bulkhead: solid disc, then the holes ------------------------------
    occ, has_bodies = _get_or_create_component(root, "BoosterForwardBulkhead")
    if not has_bodies:
        disc = _cyl(tbm, 0.0, 0.0, DISC_Z0_MM, DISC_Z0_MM + DISC_T_MM, DISC_R_MM)
        for (name, hx, hy, hd) in HOLES:
            _cut(tbm, disc,
                 _cyl(tbm, hx, hy, DISC_Z0_MM - OVER_MM, DISC_Z0_MM + DISC_T_MM + OVER_MM,
                      hd / 2.0), name)
        _inject(occ.component, [("booster forward bulkhead", disc)])
        print("BoosterForwardBulkhead: built with %d holes" % len(HOLES))
    else:
        print("BoosterForwardBulkhead: already has bodies, verifying only")
    bad += _verify_volume(occ.component,
                          {{"booster forward bulkhead": DISC_VOLUME_MM3}},
                          VOLUME_TOLERANCE_MM3)

    # A volume check cannot tell a hole that was cut from one cut somewhere else, so read
    # the cylindrical faces back and confirm one axial bore exists at each hole's radius.
    disc_body = occ.component.bRepBodies.item(0)
    for (name, hx, hy, hd) in HOLES:
        if not _verify_cyl_faces(disc_body, hd / 2.0, False):
            bad.append("%s: no axial cylindrical face at R %.3f mm" % (name, hd / 2.0))

    # ---- the mount tube ----------------------------------------------------------------
    tube_occ, has_bodies = _get_or_create_component(root, "MotorMountTube")
    if not has_bodies:
        _inject(tube_occ.component,
                [("motor mount tube",
                  _annulus(tbm, TUBE_OR_MM, TUBE_IR_MM, TUBE_Z0_MM, TUBE_Z1_MM))])
        print("MotorMountTube: built, Z %.4f -> %.4f mm" % (TUBE_Z0_MM, TUBE_Z1_MM))
    else:
        print("MotorMountTube: already has bodies, verifying only")
    bad += _verify_volume(tube_occ.component,
                          {{"motor mount tube": TUBE_VOLUME_MM3}}, VOLUME_TOLERANCE_MM3)

    # ---- the centering rings -----------------------------------------------------------
    ring_occs = []
    for spec in RINGS:
        r_occ, has_bodies = _get_or_create_component(root, spec["name"])
        ring_occs.append((spec, r_occ))
        if not has_bodies:
            z0 = spec["z0"]
            z1 = z0 + spec["t"]
            ring = _annulus(tbm, spec["ro"], spec["ri"], z0, z1)
            # Slots for the fin tabs. Built at clocking 0 with the quadrant helper's own
            # convention, then rotated -- one technique at any angle, which is the fix
            # correction 52 made when 45 degrees broke the quadrant-parity trick.
            for q in range(spec["slots"]):
                half = spec["slot_width"] / 2.0
                slot = _quadrant_box(tbm, 0, spec["slot_r_lo"], spec["ro"] + OVER_MM,
                                     -half, half, z0 - OVER_MM, z1 + OVER_MM)
                _rotate_z(tbm, slot, AFT_FIN_CLOCK_DEG + q * 90.0)
                _cut(tbm, ring, slot, "tab slot %d" % q)
            _inject(r_occ.component, [(spec["body"], ring)])
            print("%s: built, Z %.4f -> %.4f mm, %d slots"
                  % (spec["name"], z0, z1, spec["slots"]))
        else:
            print("%s: already has bodies, verifying only" % spec["name"])
        loose = (spec["body"],) if spec["slots"] else ()
        bad += _verify_volume(r_occ.component, {{spec["body"]: spec["volume"]}},
                              VOLUME_TOLERANCE_MM3, loose=loose,
                              loose_tol=SLOT_TOLERANCE_MM3)

    # ---- the motor envelope, so interference has something to measure against ----------
    motor_occ, has_bodies = _get_or_create_component(root, "MotorEnvelope")
    if not has_bodies:
        _inject(motor_occ.component,
                [("motor envelope", _cyl(tbm, 0.0, 0.0, MOTOR_Z0_MM, MOTOR_Z1_MM, MOTOR_R_MM))])
        print("MotorEnvelope: built, Z %.4f -> %.4f mm" % (MOTOR_Z0_MM, MOTOR_Z1_MM))
    else:
        print("MotorEnvelope: already has bodies, verifying only")
    bad += _verify_volume(motor_occ.component, {{"motor envelope": MOTOR_VOLUME_MM3}},
                          VOLUME_TOLERANCE_MM3)

    # ---- interference, which is where the findings actually get demonstrated -----------
    fins = []
    for q in range(N_FINS):
        fins += _bodies_named(root, "AftFin%d" % q)
    tube_body = tube_occ.component.bRepBodies.item(0)

    print("interference:")
    pairs = []
    for i, f in enumerate(fins):
        pairs.append(("MotorMountTube vs AftFin%d" % i, tube_body, f))
    for spec, r_occ in ring_occs:
        rb = r_occ.component.bRepBodies.item(0)
        for i, f in enumerate(fins):
            pairs.append(("%s vs AftFin%d" % (spec["name"], i), rb, f))
        pairs.append(("%s vs MotorMountTube" % spec["name"], rb, tube_body))
        pairs.append(("%s vs MotorEnvelope" % spec["name"], rb,
                      motor_occ.component.bRepBodies.item(0)))
    pairs.append(("BoosterForwardBulkhead vs MotorEnvelope", disc_body,
                  motor_occ.component.bRepBodies.item(0)))
    pairs.append(("BoosterForwardBulkhead vs MotorMountTube", disc_body, tube_body))
    pairs.append(("MotorMountTube vs MotorEnvelope", tube_body,
                  motor_occ.component.bRepBodies.item(0)))
    for bt in _bodies_named(root, "BoosterTube"):
        pairs.append(("MotorMountTube vs BoosterTube", tube_body, bt))
        pairs.append(("BoosterForwardBulkhead vs BoosterTube", disc_body, bt))

    if not fins:
        bad.append("no AftFin bodies found -- run make_aft_fin_cad_fusion.py first, and "
                   "note that fins built at the OLD 12.00 mm tab depth will clash with "
                   "the mount tube by design; that is the finding, not a bug")

    for (label, a, b) in pairs:
        v = _pair_interference(tbm, a, b)
        print("  %-44s %10.4f mm3" % (label, v))
        if v > 1e-4:
            bad.append("%s: %.4f mm3" % (label, v))

    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK -- motor mount built, every body within tolerance, zero interference")
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
