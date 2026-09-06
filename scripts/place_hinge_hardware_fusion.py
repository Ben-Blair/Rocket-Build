"""Generate the Fusion 360 script that places four servos and four bearings onto their
real hinge axes, from design/hinge.py.

    python scripts/place_hinge_hardware_fusion.py            # print the script
    python scripts/place_hinge_hardware_fusion.py --write    # and into out/place_hinge_hardware_fusion_generated.py

MILESTONE M4 (placement half) of the canard-module Onshape -> Fusion migration
(docs/01-next-steps.md correction 44). M2 built one servo and one bearing, each in its own
local hinge-axis frame, and left them exactly there -- both `Servo` and `Bearing` sat at
the document's shared root origin, overlapping, because correction 46 explicitly deferred
placement to this milestone. This is the file that does it.

THE TECHNIQUE, and why it is not a re-derivation of scripts/make_servo_cad_fusion.py's or
scripts/make_bearing_cad_fusion.py's geometry: `place_bearings.py`'s own insight on the
Onshape side was that the servo and bearing were DELIBERATELY built in the same local
frame (origin on the hinge axis, +Z radially outward) precisely so a bearing's placement
could be derived from a servo's, never independently re-typed. A from-scratch Fusion
generator has no "existing occurrence's transform" to copy the way the Onshape assembly
script did, but it does not need one either: `design/hinge.py` already gives both parts'
origin radius directly (`servo_output_face`, `bearing_outboard`), so each is placed
straight from that number, not from the other's transform.

MECHANICALLY: `TemporaryBRepManager.copy()` lifts each of the three servo bodies (and the
one bearing body) out of their already-built, already-verified M2 component; a
`Matrix3D.setToAlignCoordinateSystems` maps the part's own local frame --
    local +X (case_length / "along")   -> global +Z (axial, the rocket's own long axis)
    local +Y (case_width / "across")   -> the quadrant's TANGENTIAL direction
    local +Z (shaft axis / radial)     -> the quadrant's RADIAL direction
    local origin                       -> (that quadrant's radial direction) * origin_r,
                                           at module Z = HINGE_Z
onto each of the four hinge axes in turn; `TemporaryBRepManager.transform()` applies it in
place to the copy. Servo and bearing stay flat bodies in their existing `Servo`/`Bearing`
components -- neither participates in a joint (only the tube/shafts/panels do, M5), so
neither needs the nine-separate-components treatment M3's parts got.

TWO PHASES, ACROSS TWO SEPARATE SCRIPT RUNS, NOT ONE -- a real Fusion API constraint found
the hard way. The first attempt at this file deleted the M2 BaseFeature and created the
new, named, placed one in the SAME script execution: the new bodies' names read back
correctly off the live object reference for the rest of that same run (which is what let
that version pass its own verify() and looked completely fine), but a later, separate
script run against the same document saw plain Fusion defaults ("Body4", "Body5", ...)
instead -- the rename never actually committed. Renaming a batch of bodies added moments
earlier persists fine on its own (confirmed by a standalone probe against this exact
document); it is specifically deleting the OLD BaseFeature and creating+naming the NEW one
inside one transaction that does not survive. The SECOND attempt split that into PLACE
(inject, no delete) and CLEANUP (delete, no inject) as two separate runs -- and naming
STILL did not survive PLACE's own transaction, even with nothing deleted in it. The
distinguishing factor turned out to be simpler and less forgiving than "don't delete and
create in the same transaction": naming a body added moments earlier, in the SAME
transaction, DOES NOT SURVIVE if that component already held other bodies from an earlier,
separate transaction. Renaming ALREADY-COMMITTED bodies in their own, later, standalone
transaction always works, confirmed three times over against this exact document. So this
generator does not try to name anything in the same transaction it creates it in, ever.
`run()` inspects which of four phases the document is in and does only that one --
    PLACE   (old M2 bodies present, no placed copies yet): inject the twelve/four placed
            copies into a NEW BaseFeature with whatever default names Fusion gives them.
            The old M2 bodies are left exactly alone.
    RENAME  (old M2 bodies present, AND more bodies than that with default names): match
            each default-named body to its (part, quadrant) identity by MEASURING it --
            volume against the still-present, still-correctly-named old bodies (a rigid
            transform cannot change volume) and centre-of-mass angle against the four
            quadrants -- then rename it. Not by trusting insertion order.
    CLEANUP (old M2 bodies present, AND the placed copies are already correctly named):
            delete the OLD BaseFeature only, leaving the twelve/four placed bodies.
    DONE    (only placed copies present): verify and stop.
Run this generator's script THREE times in a row against a freshly-rebuilt Servo/Bearing
to place, rename and then clean up; a fourth run (or any run once DONE) just verifies.

WHY LOCAL +X MAPS TO GLOBAL +Z, NOT THE OTHER WAY AROUND: `design/packaging.py`'s own
header states the confirmed arrangement plainly -- "its LENGTH runs fore-and-aft along the
rocket axis" -- and `design/hinge.py`'s `ServoGeometry` docstring is explicit that the
SHAFT axis (`case_height`, local Z here) is what consumes radius, correcting an earlier,
wrong assumption in that same packaging header that WIDTH did. Case width is what is left,
and it is what stacks around the circumference -- tangentially.

VERIFICATION does not re-derive the parts' own volumes (a rigid transform cannot change
them -- these bodies already passed scripts/make_servo_cad_fusion.py's and
scripts/make_bearing_cad_fusion.py's own checks in M2). Instead it checks (1) each
placed copy's volume against the ORIGINAL body's own measured volume, catching a copy that
silently lost geometry, and (2) each copy's centre of mass lands at the expected quadrant
angle -- exact, not approximate, because every body here is symmetric about its own local
Y = 0 plane, so a correct placement puts the centre of mass exactly on the quadrant's
radial line with no tangential offset to round.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import hinge
from design.configure import baseline, build_vehicle
from design.packaging import SERVO_GEOMETRY
from scripts.fusion_common import FUSION_PRELUDE

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "place_hinge_hardware_fusion_generated.py"

ANGLE_TOLERANCE_DEG = 1e-6
# Used only to CLASSIFY a placed body into one of four quadrants, which are 90 deg apart.
# Nothing about placement accuracy rides on it -- ANGLE_TOLERANCE_DEG above is what checks
# that. See _do_rename for why an exact match on a rounded angle was the wrong tool.
IDENTIFY_TOLERANCE_DEG = 1.0


def geometry() -> hinge.HingeStack:
    p = baseline()
    r = build_vehicle(p)
    g = SERVO_GEOMETRY[p.servo]
    return hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, g)


def emit() -> str:
    s = geometry()
    p = baseline()
    r = build_vehicle(p)
    hinge_z = (hinge.canard_hinge_station(r) - r.tube_station(1)) * MM

    servo_r = s.servo_output_face * MM
    bearing_r = s.bearing_outboard * MM

    return f'''"""GENERATED by scripts/place_hinge_hardware_fusion.py -- do not edit this file.

Every number below comes from design/hinge.py. Regenerate rather than patch.

Servo origin radius   {servo_r:.4f} mm (servo_output_face)
Bearing origin radius {bearing_r:.4f} mm (bearing_outboard = tube_outer_radius)
Hinge Z               {hinge_z:.4f} mm (module frame)
"""

{FUSION_PRELUDE}

HINGE_Z = {hinge_z:.4f}
SERVO_ORIGIN_R = {servo_r:.4f}
BEARING_ORIGIN_R = {bearing_r:.4f}
ANGLE_TOLERANCE_DEG = {ANGLE_TOLERANCE_DEG}
IDENTIFY_TOLERANCE_DEG = {IDENTIFY_TOLERANCE_DEG}


def _find(root, name):
    for o in root.occurrences:
        if o.component.name == name:
            return o
    raise ValueError("no occurrence named %r -- run the M2 generators first" % name)


def _place_hinge_frame(tbm, body, quadrant, origin_r):
    """Copy `body` out of its local hinge-axis frame and place it on hinge axis
    `quadrant` (0/1/2/3 = 0/90/180/270 deg) at radius `origin_r`, HINGE_Z axially.
    Local +X (along) -> global +Z (axial); local +Y (across) -> tangential;
    local +Z (shaft/radial) -> radial. See the module docstring for why.
    """
    a = math.radians(quadrant * 90.0)
    u = adsk.core.Vector3D.create(math.cos(a), math.sin(a), 0.0)
    v = adsk.core.Vector3D.create(-math.sin(a), math.cos(a), 0.0)
    z_axis = adsk.core.Vector3D.create(0.0, 0.0, 1.0)
    origin = adsk.core.Point3D.create(
        u.x * origin_r / 10.0, u.y * origin_r / 10.0, HINGE_Z / 10.0)

    m = adsk.core.Matrix3D.create()
    m.setToAlignCoordinateSystems(
        adsk.core.Point3D.create(0.0, 0.0, 0.0),
        adsk.core.Vector3D.create(1.0, 0.0, 0.0),
        adsk.core.Vector3D.create(0.0, 1.0, 0.0),
        adsk.core.Vector3D.create(0.0, 0.0, 1.0),
        origin, z_axis, v, u)

    copy = tbm.copy(body)
    if not tbm.transform(copy, m):
        raise ValueError("transform did not take")
    return copy


def _placed_name(base, q):
    return "%s q%d" % (base, q)


def _place_component(comp, body_names, origin_r, expected_count):
    """Shared PLACE/RENAME/CLEANUP/DONE logic for Servo (3 body names) and Bearing (1).

    See the module docstring for why this is four states across up to three script runs,
    not one build-and-rename pass.
    """
    placed_names = set(_placed_name(n, q) for n in body_names for q in range(4))
    old_bodies = [b for b in comp.bRepBodies if b.name in body_names]
    new_named = [b for b in comp.bRepBodies if b.name in placed_names]
    unnamed = [b for b in comp.bRepBodies
              if b.name not in body_names and b.name not in placed_names]

    if old_bodies and not unnamed and not new_named:
        _do_place(comp, body_names, origin_r)
    elif old_bodies and unnamed:
        _do_rename(comp, body_names, unnamed)
    elif old_bodies and new_named and not unnamed:
        _do_cleanup(comp, body_names)
    elif new_named and not old_bodies and not unnamed:
        print("%s already placed and cleaned up -- verifying" % comp.name)
        _verify_placed(comp, body_names, expected_count)
    else:
        raise ValueError("%s is in an unrecognised state (%d old, %d named, %d unnamed)"
                         % (comp.name, len(old_bodies), len(new_named), len(unnamed)))


def _do_place(comp, body_names, origin_r):
    """PLACE phase: add the twelve/four placed copies into a NEW BaseFeature, whatever
    default names Fusion gives them. Does not touch the old M2 bodies at all -- nothing
    is deleted or renamed in this phase.
    """
    tbm = adsk.fusion.TemporaryBRepManager.get()
    originals = {{b.name: b for b in comp.bRepBodies if b.name in body_names}}
    missing = [n for n in body_names if n not in originals]
    if missing:
        raise ValueError("%s is missing expected bodies: %s" % (comp.name, missing))

    made = []
    for q in range(4):
        for name in body_names:
            copy = _place_hinge_frame(tbm, originals[name], q, origin_r)
            made.append(copy)

    bf = comp.features.baseFeatures.add()
    bf.startEdit()
    for body in made:
        comp.bRepBodies.add(body, bf)
    bf.finishEdit()

    print("PLACE: added %d bodies to %s with default names -- run again to identify and "
          "rename them" % (len(made), comp.name))


def _do_rename(comp, body_names, unnamed):
    """RENAME phase: identify each default-named body by MEASURING it -- volume against
    the still-present, still-correctly-named old bodies (a rigid transform cannot change
    volume) and centre-of-mass angle against the four quadrants -- then rename it. Not by
    trusting insertion order or anything set during PLACE's own transaction.
    """
    acc = adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy
    vol_to_name = {{}}
    for b in comp.bRepBodies:
        if b.name in body_names:
            vol_to_name[round(b.getPhysicalProperties(acc).volume * 1e3, 4)] = b.name
    renamed = []
    for b in unnamed:
        props = b.getPhysicalProperties(acc)
        v = round(props.volume * 1e3, 4)
        angle = math.degrees(math.atan2(props.centerOfMass.y,
                                        props.centerOfMass.x)) % 360.0
        base = vol_to_name.get(v)
        # NEAREST QUADRANT ON A CIRCLE, not a dict lookup on a rounded angle.
        #
        # This was `angle_to_q = {{0.0: 0, 90.0: 1, ...}}` with the angle rounded to one
        # decimal, and it failed the first time the canard module was rebuilt at 1.30 cal:
        # a q0 bearing whose centre of mass landed a hair BELOW the +X axis came back as
        # 359.99.. deg, which `% 360.0` leaves at 359.99, `round(..., 1)` turns into
        # 360.0, and no such key exists. The body was placed perfectly; the identifier
        # simply could not see it, and the script raised and rolled the whole rebuild back.
        #
        # 0 and 360 are the same direction. `_verify_placed` below already knew that --
        # it measures a circular distance -- so the two halves of this file disagreed
        # about how to compare angles and only the strict half was on the failure path.
        # IDENTIFY_TOLERANCE_DEG is deliberately loose: these bodies sit on exact
        # quadrants 90 deg apart, so classifying them needs nothing tighter, and
        # ANGLE_TOLERANCE_DEG stays at 1e-6 for the VERIFY that actually checks placement.
        q = None
        best = IDENTIFY_TOLERANCE_DEG
        for cand in range(4):
            want = cand * 90.0
            d = min(abs(angle - want), 360.0 - abs(angle - want))
            if d <= best:
                best, q = d, cand
        if base is None or q is None:
            raise ValueError("%s: cannot identify body %r (volume %.4f mm3, angle %.1f deg)"
                             % (comp.name, b.name, v, angle))
        b.name = _placed_name(base, q)
        renamed.append(b.name)

    print("RENAME: identified and renamed %d bodies in %s by volume+angle -- run again "
          "to remove the old bodies" % (len(renamed), comp.name))


def _do_cleanup(comp, body_names):
    """CLEANUP phase: delete the OLD BaseFeature (the M2 originals) now that the placed
    copies are correctly named in their own, separate BaseFeature. A single-purpose
    transaction that only deletes -- nothing is created or renamed in it.
    """
    # Identify the OLD BaseFeature by the bodies it PRODUCED -- `bf.bodies` -- not by
    # `bf.sourceBodies`.
    #
    # THIS WAS `sourceBodies` AND IT SILENTLY DELETED NOTHING. sourceBodies are the
    # TEMPORARY bodies handed to `BRepBodies.add()`, and they keep Fusion's own default
    # names forever: ['Body1', 'Body2', 'Body3'], never 'servo body'. So the subset test
    # could not match, the loop deleted no feature, and the function still printed
    # "removed the old BaseFeature" and returned success. The prototypes survived into
    # the mass properties, which is the one place a silent no-op does real damage --
    # a Servo carrying 15 bodies instead of 12 overstates the module by three servos.
    #
    # It is the same wrong assumption as the rename bug this file's header documents:
    # a name set after `.add()` lives on the RESULT body, and the source body never
    # hears about it. `bf.bodies` is the result side, so that is what to match on.
    removed = 0
    for bf_old in list(comp.features.baseFeatures):
        names = set(b.name for b in bf_old.bodies)
        if names and names.issubset(set(body_names)):
            bf_old.deleteMe()
            removed += 1

    # A CLEANUP THAT CLEANED NOTHING IS A FAILURE, not a no-op. Reporting success here is
    # what let the defect above go unnoticed.
    if removed == 0:
        raise ValueError(
            "CLEANUP FAILED: %s has no BaseFeature whose bodies are all in %s -- nothing "
            "was removed. Bodies present: %s"
            % (comp.name, sorted(body_names), sorted(b.name for b in comp.bRepBodies)))

    print("CLEANUP: removed %d old BaseFeature(s) from %s -- %d bodies remain"
          % (removed, comp.name, comp.bRepBodies.count))


def _verify_placed(comp, body_names, expected_count):
    acc = adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy
    if comp.bRepBodies.count != expected_count:
        raise ValueError("VERIFY FAILED: %s has %d bodies, wanted %d"
                         % (comp.name, comp.bRepBodies.count, expected_count))
    bad = []
    for q in range(4):
        want_angle = (q * 90.0) % 360.0
        for name in body_names:
            full_name = _placed_name(name, q)
            body = None
            for b in comp.bRepBodies:
                if b.name == full_name:
                    body = b
            if body is None:
                bad.append("%s is missing" % full_name)
                continue
            props = body.getPhysicalProperties(acc)
            com = props.centerOfMass
            got_angle = math.degrees(math.atan2(com.y, com.x)) % 360.0
            d = min(abs(got_angle - want_angle), 360.0 - abs(got_angle - want_angle))
            print("  %-20s angle %8.4f deg (want %6.1f, delta %.6f)"
                  % (full_name, got_angle, want_angle, d))
            if d > ANGLE_TOLERANCE_DEG:
                bad.append("%s is at %.6f deg, wanted %.1f" % (full_name, got_angle, want_angle))
    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK")


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent

    servo_occ = _find(root, "Servo")
    _place_component(servo_occ.component, ["servo body", "servo spline", "servo boss"],
                     SERVO_ORIGIN_R, 12)

    bearing_occ = _find(root, "Bearing")
    _place_component(bearing_occ.component, ["bearing"], BEARING_ORIGIN_R, 4)
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
