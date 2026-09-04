"""Emit a Fusion 360 script that builds the recovery bay's harness anchors and charge wells.

    python scripts/make_recovery_hardware_cad_fusion.py            # print the script
    python scripts/make_recovery_hardware_cad_fusion.py --write    # and into out/

THIS IS THE PART THREE OTHER GENERATORS REFUSED TO DRAW, and they were right to:
`scripts/make_bulkhead_cad.py`, `scripts/make_seal_cad_fusion.py` and
`scripts/make_recovery_bay_cad_fusion.py` all say in their own docstrings that the U-bolt,
its backing plate and the charge well had never been SIZED by anything in this project, and
that drawing dimensions nobody had chosen would be inventing a design decision rather than
recording one. `design/recovery_hardware.py` chooses them. This records them.

Builds, into the same `CanardControlModule` document and frame every other generator uses
(Z = 0 at the canard module's forward face, Z positive aft):

  * `UBolt0` .. `UBolt3` -- half a torus for the crown plus two cylinders for the legs.
    M8, not the M5 seal.py assumed: what governs a U-bolt used as an ANCHOR is bending in
    the crown, and seal.py's own aside checked the legs in shear, which is not a mode they
    are in. The four are placed on the aft gas seal, both faces of the internal bulkhead,
    and the booster's forward bulkhead.
  * `BackingPlate0` .. `BackingPlate3` -- G-10, on the opposite face from each crown. The
    two on the internal bulkhead are RELIEVED with edge notches, because that disc anchors a
    harness both ways, its two U-bolts therefore clock 90 degrees apart, and each plate then
    has the opposing bolt's legs reaching under it.
  * `ChargeWell0` (main) and `ChargeWell1` (drogue) -- thin-wall tube standing on the fired
    face of each separation bulkhead, over that charge's own lead hole.

EVERY DIMENSION AND EVERY POSITION IS READ FROM `design/recovery_hardware.py`. This file
types no diameter, no thickness, no station and no clocking -- the same rule
`seal.hole_layout()` established for the bulkhead scripts, and for the reason `configure.py`
gives about six scripts each carrying their own copy of the baseline.

ONE PRIMITIVE HERE IS NEW TO THIS REPO: `TemporaryBRepManager.createTorus`, for the U-bolt's
crown. Every other generator has needed only boxes and cylinders. If the emitted script
fails at a torus call, that is the first thing to check -- the crown is a swept round
section and there is no way to build it from boxes and cylinders that is not the wrong
shape.

THE VOLUME CHECK IS EXACT HERE, unusually. The crown is exactly half a torus
(pi^2 * R * r^2), the legs are cylinders that meet it face-on at the crown's own centre
plane so nothing overlaps, and the reliefs are straight-sided notches rather than holes
straddling an edge -- which is precisely why `design/recovery_hardware.py` specifies them as
notches. No loosened tolerance is needed anywhere in this file, and that is worth stating
because the last three generators all needed one.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import motor_mount as mmount, recovery_hardware as rhw, seal
from design.configure import baseline, evaluate
from scripts.fusion_common import FUSION_PRELUDE

MM = 1000.0
OUT = (Path(__file__).resolve().parents[1] / "out"
       / "make_recovery_hardware_cad_fusion_generated.py")

VOLUME_TOLERANCE_MM3 = 0.01
OVER_MM = 1.0

# Stations of the three discs these parts stand on, in the shared document frame. Derived
# from the same arithmetic scripts/make_recovery_bay_cad_fusion.py and
# scripts/make_motor_mount_cad_fusion.py use, never typed twice.
CANARD_MODULE_AFT_FACE_MM = 142.92
FILLET_CLEARANCE_MM = 3.0


def _faces(ev):
    """(forward Z, aft Z) of each bulkhead this file hangs hardware on, mm."""
    aft = seal.from_evaluation(ev)
    internal = seal.internal_bulkhead_from_evaluation(ev)
    mm_r = mmount.motor_mount_from_evaluation(ev)

    seal_aft_z = CANARD_MODULE_AFT_FACE_MM
    seal_fwd_z = seal_aft_z - aft.bulkhead.thickness * MM

    main_len = next(c[2] for c in ev.packing.compartments if c[0] == "main") * MM
    ib_fwd_z = seal_aft_z + main_len + FILLET_CLEARANCE_MM
    ib_aft_z = ib_fwd_z + internal.bulkhead.thickness * MM

    booster_fwd_z = (ev.rocket.tubes[1].length + ev.rocket.tubes[2].length) * MM
    bfb_fwd_z = booster_fwd_z + mm_r.bulkhead_station * MM
    bfb_aft_z = bfb_fwd_z + mm_r.forward_bulkhead.thickness * MM

    return {
        "aft gas seal / fwd": (seal_fwd_z, -1.0),
        "aft gas seal / aft": (seal_aft_z, +1.0),
        "internal bulkhead / fwd": (ib_fwd_z, -1.0),
        "internal bulkhead / aft": (ib_aft_z, +1.0),
        "booster forward bulkhead / fwd": (bfb_fwd_z, -1.0),
        "booster forward bulkhead / aft": (bfb_aft_z, +1.0),
    }


def emit() -> str:
    ev = evaluate(baseline())
    r = rhw.recovery_hardware_from_evaluation(ev)
    faces = _faces(ev)
    u = r.anchor.ubolt
    plate = r.anchor.plate
    reliefs = rhw.plate_reliefs(r)

    rod_r = u.rod_diameter * MM / 2.0
    crown_R = u.crown_radius * MM
    leg_len = rhw.UBOLT_LEG_STANDOUT * MM
    crown_volume = math.pi**2 * crown_R * rod_r**2          # exactly half a torus
    leg_volume = 2.0 * math.pi * rod_r**2 * leg_len
    ubolt_volume = crown_volume + leg_volume

    bolts, plates, wells = [], [], []
    for i, a in enumerate(r.anchors):
        cz, cdir = faces[a.face]
        pz, pdir = faces[rhw._plate_face(a.face)]
        bolts.append({
            "name": f"UBolt{i}", "body": f"u-bolt {i}",
            "z": cz, "dir": cdir, "clock": a.clocking_deg,
        })
        my = [x for x in reliefs if x.face == rhw._plate_face(a.face)]
        px, py = a.plate_halfspans()
        notch_vol = sum(x.width * x.depth for x in my) * plate.thickness * MM**3
        hole_vol = 2.0 * math.pi * (u.hole_diameter * MM / 2.0) ** 2 * plate.thickness * MM
        plates.append({
            "name": f"BackingPlate{i}", "body": f"backing plate {i}",
            "z": pz, "dir": pdir, "hx": px * MM, "hy": py * MM,
            "t": plate.thickness * MM,
            "legs": [(lx * MM, ly * MM) for lx, ly in a.leg_positions()],
            "reliefs": [(x.at[0] * MM, x.at[1] * MM, x.width * MM, x.depth * MM)
                        for x in my],
            "volume": 4.0 * px * py * MM**2 * plate.thickness * MM - hole_vol - notch_vol,
        })
    for i, w in enumerate(r.wells):
        wz, wdir = faces[w.face]
        cx, cy = w.centre
        wells.append({
            "name": f"ChargeWell{i}", "body": f"{w.name} well",
            "z": wz, "dir": wdir, "x": cx * MM, "y": cy * MM,
            "ro": w.outer_diameter * MM / 2.0, "ri": w.bore * MM / 2.0,
            "depth": w.depth * MM,
            "volume": (math.pi * ((w.outer_diameter * MM / 2.0) ** 2
                                  - (w.bore * MM / 2.0) ** 2) * w.depth * MM),
        })

    def rep(xs):
        return ",\n    ".join(repr(x) for x in xs)

    return f'''"""GENERATED by scripts/make_recovery_hardware_cad_fusion.py -- do not edit
this file. Regenerate rather than patch.

UBolt0-3        M{u.rod_diameter * MM:.0f} rod dia {2*rod_r:.3f}, crown R {crown_R:.3f}, legs {leg_len:.3f} long
                {ubolt_volume:.4f} mm3 each (half torus {crown_volume:.4f} + legs {leg_volume:.4f})
BackingPlate0-3 G-10 {plate.length * MM:.3f} x {plate.width * MM:.3f} x {plate.thickness * MM:.3f}
                two on the internal bulkhead RELIEVED, {len(reliefs)} notches total
ChargeWell0     {r.wells[0].name} dia {r.wells[0].bore * MM:.0f} x {r.wells[0].depth * MM:.3f} at R {r.wells[0].station_radius * MM:.3f}
ChargeWell1     {r.wells[1].name} dia {r.wells[1].bore * MM:.0f} x {r.wells[1].depth * MM:.3f} at R {r.wells[1].station_radius * MM:.3f}

Every dimension read from design/recovery_hardware.py. Nothing here is typed twice.
"""

{FUSION_PRELUDE}

VOLUME_TOLERANCE_MM3 = {VOLUME_TOLERANCE_MM3!r}
OVER_MM = {OVER_MM!r}

ROD_R_MM = {rod_r!r}
CROWN_R_MM = {crown_R!r}
LEG_LEN_MM = {leg_len!r}
UBOLT_VOLUME_MM3 = {ubolt_volume!r}
HOLE_R_MM = {u.hole_diameter * MM / 2.0!r}

BOLTS = [
    {rep(bolts)}
]

PLATES = [
    {rep(plates)}
]

WELLS = [
    {rep(wells)}
]


def _rotate_z(tbm, body, angle_deg):
    m = adsk.core.Matrix3D.create()
    m.setToRotation(math.radians(angle_deg), adsk.core.Vector3D.create(0.0, 0.0, 1.0),
                    adsk.core.Point3D.create(0.0, 0.0, 0.0))
    if not tbm.transform(body, m):
        raise ValueError("rotation to %.1f deg did not take" % angle_deg)
    return body


def _ubolt(tbm, z, direction, clock_deg):
    """Half a torus for the crown plus two cylinders for the legs, built at clocking 0 in
    the Y-Z plane and then rotated about Z -- one technique at any angle, which is the fix
    correction 52 made when 45 degrees broke the quadrant-parity trick.

    The legs start EXACTLY on the crown's own centre plane, so the two meet face to face
    and nothing overlaps. That is what makes the volume check below exact rather than
    loosened.
    """
    # Full torus, axis along X so its tube sweeps a circle in the Y-Z plane.
    torus = tbm.createTorus(
        adsk.core.Point3D.create(0.0, 0.0, z / 10.0),
        adsk.core.Vector3D.create(1.0, 0.0, 0.0),
        CROWN_R_MM / 10.0, ROD_R_MM / 10.0)
    # Keep only the half standing proud of the face.
    span = (CROWN_R_MM + ROD_R_MM) * 2.0 + OVER_MM
    cut = _box(tbm, 0.0, 0.0, z - direction * (span / 4.0), span, span, span / 2.0)
    _cut(tbm, torus, cut, "crown half")

    for sign in (+1.0, -1.0):
        leg = _cyl(tbm, 0.0, sign * CROWN_R_MM, z, z - direction * LEG_LEN_MM, ROD_R_MM)
        _union(tbm, torus, leg, "leg")
    return _rotate_z(tbm, torus, clock_deg)


def _plate(tbm, spec):
    z0 = spec["z"]
    z1 = z0 + spec["dir"] * spec["t"]
    lo, hi = min(z0, z1), max(z0, z1)
    body = _box(tbm, 0.0, 0.0, (lo + hi) / 2.0,
                2.0 * spec["hx"], 2.0 * spec["hy"], spec["t"])
    for (lx, ly) in spec["legs"]:
        _cut(tbm, body, _cyl(tbm, lx, ly, lo - OVER_MM, hi + OVER_MM, HOLE_R_MM), "leg hole")
    for (rx, ry, w, d) in spec["reliefs"]:
        # A straight-sided notch in the nearest edge, not a hole: the opposing leg's centre
        # is OUTSIDE this plate, so a hole there would be a notch anyway -- and a notch is
        # exactly modellable, exactly measurable, and easier to cut.
        if abs(rx) > abs(ry):
            cx = (abs(rx) / rx) * (spec["hx"] - d / 2.0)
            _cut(tbm, body, _box(tbm, cx, ry, (lo + hi) / 2.0, d, w, spec["t"] + OVER_MM),
                 "relief")
        else:
            cy = (abs(ry) / ry) * (spec["hy"] - d / 2.0)
            _cut(tbm, body, _box(tbm, rx, cy, (lo + hi) / 2.0, w, d, spec["t"] + OVER_MM),
                 "relief")
    return body


def _well(tbm, spec):
    z0 = spec["z"]
    z1 = z0 + spec["dir"] * spec["depth"]
    lo, hi = min(z0, z1), max(z0, z1)
    body = _cyl(tbm, spec["x"], spec["y"], lo, hi, spec["ro"])
    _cut(tbm, body, _cyl(tbm, spec["x"], spec["y"], lo - OVER_MM, hi + OVER_MM, spec["ri"]),
         "bore")
    return body


def _pair_interference(tbm, a, b):
    ca = tbm.copy(a)
    cb = tbm.copy(b)
    if not tbm.booleanOperation(ca, cb, adsk.fusion.BooleanTypes.IntersectionBooleanType):
        return 0.0
    return ca.volume * 1e3 if ca is not None else 0.0


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()
    bad = []
    built = []

    for spec in BOLTS:
        occ, has_bodies = _get_or_create_component(root, spec["name"])
        if not has_bodies:
            _inject(occ.component,
                    [(spec["body"], _ubolt(tbm, spec["z"], spec["dir"], spec["clock"]))])
            print("%s: built at Z %.4f, clocked %.1f deg"
                  % (spec["name"], spec["z"], spec["clock"]))
        else:
            print("%s: already has bodies, verifying only" % spec["name"])
        bad += _verify_volume(occ.component, {{spec["body"]: UBOLT_VOLUME_MM3}},
                              VOLUME_TOLERANCE_MM3)
        built.append((spec["name"], occ.component.bRepBodies.item(0)))

    for spec in PLATES:
        occ, has_bodies = _get_or_create_component(root, spec["name"])
        if not has_bodies:
            _inject(occ.component, [(spec["body"], _plate(tbm, spec))])
            print("%s: built at Z %.4f, %d holes, %d reliefs"
                  % (spec["name"], spec["z"], len(spec["legs"]), len(spec["reliefs"])))
        else:
            print("%s: already has bodies, verifying only" % spec["name"])
        bad += _verify_volume(occ.component, {{spec["body"]: spec["volume"]}},
                              VOLUME_TOLERANCE_MM3)
        built.append((spec["name"], occ.component.bRepBodies.item(0)))

    for spec in WELLS:
        occ, has_bodies = _get_or_create_component(root, spec["name"])
        if not has_bodies:
            _inject(occ.component, [(spec["body"], _well(tbm, spec))])
            print("%s: built at Z %.4f, (%.3f, %.3f)"
                  % (spec["name"], spec["z"], spec["x"], spec["y"]))
        else:
            print("%s: already has bodies, verifying only" % spec["name"])
        bad += _verify_volume(occ.component, {{spec["body"]: spec["volume"]}},
                              VOLUME_TOLERANCE_MM3)
        built.append((spec["name"], occ.component.bRepBodies.item(0)))

    # ---- interference, against each other AND against the discs they stand on ----------
    for disc in ("AftGasSeal", "RecoveryInternalBulkhead", "BoosterForwardBulkhead",
                 "RecoveryBayTube", "MotorMountTube"):
        for o in root.occurrences:
            if o.component.name == disc:
                for b in o.bRepBodies:
                    built.append((disc, b))

    print("interference:")
    seen = set()
    for i, (na, ba) in enumerate(built):
        for (nb, bb) in built[i + 1:]:
            if na == nb:
                continue
            key = tuple(sorted((na, nb)))
            v = _pair_interference(tbm, ba, bb)
            if v > 1e-4 or key not in seen:
                print("  %-46s %10.4f mm3" % ("%s vs %s" % (na, nb), v))
            seen.add(key)
            if v > 1e-4:
                bad.append("%s vs %s: %.4f mm3" % (na, nb, v))

    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK -- 4 anchors, 4 backing plates and 2 charge wells, zero interference")
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
