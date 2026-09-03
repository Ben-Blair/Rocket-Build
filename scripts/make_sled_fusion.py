"""Generate the Fusion 360 script that builds the nav bay sled.

    python scripts/make_sled_fusion.py            # print the script
    python scripts/make_sled_fusion.py --write    # and into out/make_sled_fusion_generated.py

WHY THIS IS A GENERATOR AND NOT A SCRIPT. Fusion's embedded Python cannot import this
repository, so a script that runs inside Fusion has to carry its dimensions as literals.
Typing them would put a second source of truth next to `design/sled.py`, which is precisely
what every Onshape script in `scripts/` refuses to do -- `place_bearings.py` will not even
type a quadrant angle, on the grounds that a hand-written number goes stale silently while
a derived one does not. So this file derives every number from `design/sled.py` and emits
the script; nothing is typed into Fusion by hand.

THE FRAME. The Fusion document `CanardControlModule` has Z = 0 on the canard module's
FORWARD face, which is station 444.64 mm, and +Z runs aft. The nav bay is the bay forward
of it, so it lives in negative Z:

    station 317.60 mm  =  Z -127.04    nav bay forward end, the nose plate's aft face
    station 432.64 mm  =  Z  -12.00    aft limit of the sled -- joints.py's 12 mm
                                       BULKHEAD_ALLOWANCE for the pass-through plate
    station 444.64 mm  =  Z    0.00    the module's forward face; `pass_through_plate`
                                       already occupies Z 0.000 -> 2.400 there

So the sled spans Z -127.04 -> -12.00, which is 115.04 mm, which is `usable_length`. That
the two agree is worth stating: the 12 mm allowance is charged to the NAV BAY even though
the plate itself sits 2.4 mm into the canard module, and reading it the other way would put
the sled 12 mm too far aft and straight through the plate.

Plate width runs along X, thickness along Y, length along Z. Components mount on the two
+/-Y faces. The rods run along Z at X = +/- rod_pitch/2, Y = 0 -- outboard of the plate in
the corner crescents. See `design/sled.py` for why they are outboard and not through it.

GEOMETRY IS BUILT AS TEMPORARY BREP BODIES INJECTED THROUGH A BaseFeature, not as sketches
and extrudes. That is the pattern that was proven to work in this document last session
(docs/05, "The Fusion 360 transfer"): the design is PARAMETRIC, so a temp body has to go in
through `BRepBodies.add(body, baseFeature)` or it does not go in at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import math

from design import joints, sled
from design.configure import baseline, evaluate

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "make_sled_fusion_generated.py"

COMPONENT = "NavBay"
NOSE_PLATE_THICKNESS_MM = 3.2   # design/access_bulkhead.MODULE_INTERFACE_THICKNESS_FLOOR
ROD_COUNT_TXT = f"{sled.ROD_COUNT} x M{sled.ROD_DIAMETER * MM:.0f} rods"


def ev_wall() -> float:
    """Airframe wall, m -- read from the frozen baseline, not typed."""
    return baseline().wall_thickness


def geometry():
    ev = evaluate(baseline())
    g = sled.sled_from_evaluation(ev)
    bay = joints.budgets(ev.rocket, ev.params.wall_thickness)["nav bay"]
    # Z of the sled ASSEMBLY's forward end, in the module's frame. The aft limit is
    # -BULKHEAD_ALLOWANCE, and the span is plate + both brackets -- not the plate alone,
    # which is 6 mm shorter and would put the whole sled 6 mm too far aft.
    z_aft = -joints.BULKHEAD_ALLOWANCE * MM
    z_fwd = z_aft - g.assembly_length * MM
    return g, bay, z_fwd, z_aft


def emit() -> str:
    g, bay, z_fwd, z_aft = geometry()
    chk = sled.check_sled(g)
    if not chk.ok:
        raise SystemExit(
            "refusing to generate a build for a sled that does not pass its own check:\n  "
            + "\n  ".join(chk.violations))

    w = g.plate_width * MM
    t = g.plate_thickness * MM
    bt = g.bracket_thickness * MM

    # The plate butts the two brackets, so it sits inboard of both.
    plate = (0.0, 0.0, (z_fwd + z_aft) / 2.0, w, t, g.plate_length * MM)

    holes = [(h.name, -w / 2.0 + h.y * MM, z_fwd + bt + h.x * MM,
              sled.MOUNT_HOLE_DIAMETER * MM / 2.0) for h in g.mount_holes]

    standoffs = []
    for (hx, hy, faces, _owners) in g.mount_sites():
        for face in faces:
            standoffs.append((-w / 2.0 + hy * MM, z_fwd + bt + hx * MM,
                              1.0 if face == 0 else -1.0))

    boxes = []
    for pl in g.placements:
        comp = next(c for c in g.components if c.name == pl.name)
        standoff = 0.0 if comp.name in sled.STRAPPED_DIRECTLY else sled.STANDOFF_HEIGHT * MM
        y0 = t / 2.0 + standoff
        cy = (y0 + pl.height * MM / 2.0) * (1.0 if pl.face == 0 else -1.0)
        cx = -w / 2.0 + (pl.y + pl.width / 2.0) * MM
        cz = z_fwd + bt + (pl.x + pl.length / 2.0) * MM
        boxes.append((pl.name, cx, cy, cz, pl.width * MM, pl.height * MM, pl.length * MM))

    od = bay.full_bore * MM + 2.0 * ev_wall() * MM
    tubes = [
        ("nav bay tube", od / 2.0, bay.full_bore * MM / 2.0,
         z_fwd, z_fwd + bay.tube_length * MM),
        ("nose shoulder", bay.full_bore * MM / 2.0, bay.narrow_bore * MM / 2.0,
         z_fwd, z_fwd + bay.narrow_span * MM),
        ("nose plate", bay.full_bore * MM / 2.0, 0.0,
         z_fwd - NOSE_PLATE_THICKNESS_MM, z_fwd),
    ]

    return f'''"""GENERATED by scripts/make_sled_fusion.py -- do not edit this file.

Every number below comes from design/sled.py. Regenerate rather than patch.

Plate   {g.plate_length * MM:.2f} x {w:.2f} x {t:.2f} mm G-10, {len(g.mount_holes)} mounting holes
Bracket 2 off, R {g.bracket_radius * MM:.2f} cropped to +/-{sled.BRACKET_HALF_WIDTH * MM:.1f} mm in X, {bt:.1f} mm thick
Rods    {sled.ROD_COUNT} x M{g.rod_diameter * MM:.0f} at (0, +/-{g.rod_radius * MM:.2f}) running Z {z_fwd:.2f} -> {z_fwd + g.rod_length * MM:.2f}
Stack   {len(g.placements)} components at {g.clearance * MM:.1f} mm clearance, {len(standoffs)} standoffs
"""

import adsk.core
import adsk.fusion

COMPONENT = {COMPONENT!r}
BORE_MM = {g.bore * MM:.4f}
Z_FWD = {z_fwd:.4f}
Z_AFT = {z_aft:.4f}
PLATE_T = {t:.4f}
STANDOFF_R = {sled.STANDOFF_OD * MM / 2.0:.4f}
STANDOFF_H = {sled.STANDOFF_HEIGHT * MM:.4f}

BRACKET_R = {g.bracket_radius * MM:.4f}
BRACKET_HALF_W = {sled.BRACKET_HALF_WIDTH * MM:.4f}
BRACKET_T = {bt:.4f}
BRACKET_Z = [{z_fwd + bt / 2.0:.4f}, {z_aft - bt / 2.0:.4f}]

ROD_R_POS = {g.rod_radius * MM:.4f}
ROD_R = {g.rod_diameter * MM / 2.0:.4f}
ROD_HOLE_R = {g.rod_hole_diameter * MM / 2.0:.4f}
ROD_Z0 = {z_fwd:.4f}
ROD_Z1 = {z_fwd + g.rod_length * MM:.4f}

PLATE_VOLUME_MM3 = {g.plate_volume * 1e9:.4f}
BRACKET_VOLUME_MM3 = {g.bracket_area * g.bracket_thickness * 1e9:.4f}
ROD_VOLUME_MM3 = {math.pi * (g.rod_diameter / 2.0) ** 2 * g.rod_length * 1e9:.4f}

PLATE = ({plate[0]:.4f}, {plate[1]:.4f}, {plate[2]:.4f}, {plate[3]:.4f}, {plate[4]:.4f}, {plate[5]:.4f})

MOUNT_HOLES = [
{chr(10).join(f"        ({h[0]!r}, {h[1]:.4f}, {h[2]:.4f}, {h[3]:.4f})," for h in holes).rstrip(",")}
]

STANDOFFS = [
{chr(10).join(f"        ({x:.4f}, {z:.4f}, {sg:+.1f})," for (x, z, sg) in standoffs).rstrip(",")}
]

BOXES = [
{chr(10).join(f"        ({r[0]!r}, {r[1]:.4f}, {r[2]:.4f}, {r[3]:.4f}, {r[4]:.4f}, {r[5]:.4f}, {r[6]:.4f})," for r in boxes).rstrip(",")}
]

TUBES = [
{chr(10).join(f"        ({r[0]!r}, {r[1]:.4f}, {r[2]:.4f}, {r[3]:.4f}, {r[4]:.4f})," for r in tubes).rstrip(",")}
]


def _box(tbm, cx, cy, cz, lx, ly, lz):
    obb = adsk.core.OrientedBoundingBox3D.create(
        adsk.core.Point3D.create(cx / 10.0, cy / 10.0, cz / 10.0),
        adsk.core.Vector3D.create(1.0, 0.0, 0.0),
        adsk.core.Vector3D.create(0.0, 1.0, 0.0),
        lx / 10.0, ly / 10.0, lz / 10.0)
    return tbm.createBox(obb)


def _cyl(tbm, x, y, z0, z1, r):
    return tbm.createCylinderOrCone(
        adsk.core.Point3D.create(x / 10.0, y / 10.0, z0 / 10.0), r / 10.0,
        adsk.core.Point3D.create(x / 10.0, y / 10.0, z1 / 10.0), r / 10.0)


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()
    DIFF = adsk.fusion.BooleanTypes.DifferenceBooleanType

    # NOTE: booleanOperation returns a BOOL and mutates the target in place. Never assign
    # its result back -- `body = tbm.booleanOperation(...) or body` rebinds body to True the
    # first time it succeeds, which is a bug that reads as correct.
    def cut(target, tool, what):
        if not tbm.booleanOperation(target, tool, DIFF):
            raise ValueError("cut %s did not take" % what)

    occ = None
    for o in root.occurrences:
        if o.component.name == COMPONENT:
            occ = o
            break
    if occ is not None and occ.component.bRepBodies.count:
        print("%s already holds %d bodies -- verifying rather than rebuilding"
              % (COMPONENT, occ.component.bRepBodies.count))
        verify(occ.component)
        return
    if occ is None:
        occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        occ.component.name = COMPONENT
    comp = occ.component

    made = []

    # --- the plate: a plain rectangle, less its mounting holes ---
    plate = _box(tbm, *PLATE)
    for (n, x, z, r) in MOUNT_HOLES:
        c0 = adsk.core.Point3D.create(x / 10.0, -(PLATE_T / 2.0 + 2.0) / 10.0, z / 10.0)
        c1 = adsk.core.Point3D.create(x / 10.0, (PLATE_T / 2.0 + 2.0) / 10.0, z / 10.0)
        cut(plate, tbm.createCylinderOrCone(c0, r / 10.0, c1, r / 10.0), n)
    made.append(("sled plate", plate))

    # --- the two end brackets: a disc cropped in X, less two rod holes ---
    for k, zc in enumerate(BRACKET_Z):
        br = _cyl(tbm, 0.0, 0.0, zc - BRACKET_T / 2.0, zc + BRACKET_T / 2.0, BRACKET_R)
        for sgn in (1.0, -1.0):
            cut(br, _box(tbm, sgn * (BRACKET_HALF_W + BRACKET_R), 0.0, zc,
                         2.0 * BRACKET_R, 4.0 * BRACKET_R, BRACKET_T + 4.0), "bracket crop")
        for sgn in (1.0, -1.0):
            cut(br, _cyl(tbm, 0.0, sgn * ROD_R_POS, zc - BRACKET_T, zc + BRACKET_T,
                         ROD_HOLE_R), "bracket rod hole")
        made.append(("end bracket %s" % ("fwd" if k == 0 else "aft"), br))

    # --- standoffs, unioned into one body ---
    so = None
    for (x, z, sg) in STANDOFFS:
        c0 = adsk.core.Point3D.create(x / 10.0, (sg * PLATE_T / 2.0) / 10.0, z / 10.0)
        c1 = adsk.core.Point3D.create(
            x / 10.0, (sg * (PLATE_T / 2.0 + STANDOFF_H)) / 10.0, z / 10.0)
        b = tbm.createCylinderOrCone(c0, STANDOFF_R / 10.0, c1, STANDOFF_R / 10.0)
        if so is None:
            so = b
        elif not tbm.booleanOperation(so, b, adsk.fusion.BooleanTypes.UnionBooleanType):
            raise ValueError("union of a standoff failed")
    made.append(("standoffs", so))

    for name, sgn in (("rod +Y", 1.0), ("rod -Y", -1.0)):
        made.append((name, _cyl(tbm, 0.0, sgn * ROD_R_POS, ROD_Z0, ROD_Z1, ROD_R)))

    for (name, cx, cy, cz, lx, ly, lz) in BOXES:
        made.append((name, _box(tbm, cx, cy, cz, lx, ly, lz)))

    for (name, r_out, r_in, z0, z1) in TUBES:
        outer = _cyl(tbm, 0.0, 0.0, z0, z1, r_out)
        if r_in > 0.0:
            cut(outer, _cyl(tbm, 0.0, 0.0, z0 - 1.0, z1 + 1.0, r_in), name)
        made.append((name, outer))

    bf = comp.features.baseFeatures.add()
    bf.startEdit()
    for (name, body) in made:
        b = comp.bRepBodies.add(body, bf)
        b.name = name
    bf.finishEdit()

    print("built %d bodies in %s" % (len(made), COMPONENT))
    verify(comp)


def verify(comp):
    """Volume against the analytic figure, and the bore check no other script performs.

    VeryHighCalculationAccuracy is not optional: the default read the Onshape tube 27 mm^3
    heavy last session and sent a whole pass chasing a hole that was not there. It earned
    its keep again here -- a +10.7519 mm^3 disagreement on the plate turned out to be two
    pairs of mounting holes overlapping each other, which nothing else had noticed.
    """
    acc = adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy
    got = {{}}
    for b in comp.bRepBodies:
        got[b.name] = b.getPhysicalProperties(acc).volume * 1e3

    want = {{"sled plate": PLATE_VOLUME_MM3,
            "end bracket fwd": BRACKET_VOLUME_MM3,
            "end bracket aft": BRACKET_VOLUME_MM3,
            "rod +Y": ROD_VOLUME_MM3, "rod -Y": ROD_VOLUME_MM3}}

    bad = []
    for name, wv in want.items():
        if name not in got:
            bad.append("%s is missing" % name)
            continue
        d = got[name] - wv
        print("  %-20s %12.4f mm3  want %12.4f  delta %+9.4f" % (name, got[name], wv, d))
        if abs(d) > 0.01:
            bad.append("%s is %+.4f mm3 out" % (name, d))

    STRUCTURE = ("nav bay tube", "nose shoulder", "nose plate")
    worst, who = 0.0, ""
    for b in comp.bRepBodies:
        if b.name in STRUCTURE:
            continue
        for vx in b.vertices:
            gg = vx.geometry
            rr = (gg.x * gg.x + gg.y * gg.y) ** 0.5 * 10.0
            if rr > worst:
                worst, who = rr, b.name
    print("  widest sled vertex %.4f mm (%s) against a %.4f mm bore radius"
          % (worst, who, BORE_MM / 2.0))
    if worst > BORE_MM / 2.0 + 1e-6:
        bad.append("the sled does not pass the %.2f mm shoulder bore" % BORE_MM)

    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK")
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
