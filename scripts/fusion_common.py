"""Shared boilerplate for every scripts/make_*_fusion.py generator.

WHY THIS EXISTS. `make_sled_fusion.py` was the first Fusion generator in this repo and had
no precedent to share code with, so it duplicated its own temp-BRep primitive builders, its
BaseFeature injection loop and its verify() scaffolding inline. The canard module migration
(docs/01-next-steps.md correction 44) adds several more generators; typing that boilerplate
again in each one would be exactly the kind of second source of truth this project's own
`design/*.py` convention exists to prevent (see `make_sled_fusion.py`'s own header).

HOW IT IS USED. This is NOT imported at runtime by the emitted Fusion script -- Fusion's
embedded Python cannot import this repository (same constraint `make_sled_fusion.py`
documents). Instead, `FUSION_PRELUDE` is a literal block of real Python that every
generator's `emit()` copies verbatim into the text of its own emitted, standalone script,
by simple string concatenation. Every function here should therefore be written as it will
actually run INSIDE Fusion: `adsk.core`/`adsk.fusion` in scope, coordinates in millimetres
in, converted to Fusion's native centimetres internally (the `/ 10.0` throughout).

THE QUADRANT FRAME. `_quadrant_axes`, `_quadrant_box` and `_radial_cyl` port
`cad/canard_bay.fs`'s `quadrantCuboid`/`radialCylinder` helpers from FeatureScript to the
Fusion temp-BRep API. Quadrant 0 has +X radial ("length"/u), +Y tangential ("width"/v,
called `across` below to match the FeatureScript name), +Z axial -- the same convention
`cad/canard_bay.fs`'s own docstring states. `OrientedBoundingBox3D.create`'s height
direction is `lengthDirection` crossed into `widthDirection` by the right-hand rule, which
stays +Z at every quadrant since rotating u and v together about Z preserves their cross
product -- so a plain box built from (u, v, +Z) needs no separate rotation step the way
`cad/canard_bay.fs`'s `opTransform` rotation does; the box is built directly in its final
orientation.
"""

FUSION_PRELUDE = '''
import math

import adsk.core
import adsk.fusion


def _box(tbm, cx, cy, cz, lx, ly, lz):
    """An axis-aligned box in the GLOBAL X/Y/Z frame. mm in, cm internally."""
    obb = adsk.core.OrientedBoundingBox3D.create(
        adsk.core.Point3D.create(cx / 10.0, cy / 10.0, cz / 10.0),
        adsk.core.Vector3D.create(1.0, 0.0, 0.0),
        adsk.core.Vector3D.create(0.0, 1.0, 0.0),
        lx / 10.0, ly / 10.0, lz / 10.0)
    return tbm.createBox(obb)


def _cyl(tbm, x, y, z0, z1, r):
    """A cylinder on an axis PARALLEL TO Z, from z0 to z1. mm in, cm internally."""
    return tbm.createCylinderOrCone(
        adsk.core.Point3D.create(x / 10.0, y / 10.0, z0 / 10.0), r / 10.0,
        adsk.core.Point3D.create(x / 10.0, y / 10.0, z1 / 10.0), r / 10.0)


def _quadrant_axes(quadrant):
    """u = radial direction, v = tangential direction, at 90 deg * quadrant about Z."""
    a = math.radians(quadrant * 90.0)
    u = adsk.core.Vector3D.create(math.cos(a), math.sin(a), 0.0)
    v = adsk.core.Vector3D.create(-math.sin(a), math.cos(a), 0.0)
    return u, v


def _quadrant_box(tbm, quadrant, r_lo, r_hi, y_lo, y_hi, z_lo, z_hi):
    """A box whose length runs radially and width tangentially, at a given quadrant
    (0/1/2/3 = 0/90/180/270 deg about the rocket Z axis) -- ports
    `cad/canard_bay.fs`'s `quadrantCuboid`. mm in, cm internally.
    """
    u, v = _quadrant_axes(quadrant)
    r_lo, r_hi = min(r_lo, r_hi), max(r_lo, r_hi)
    y_lo, y_hi = min(y_lo, y_hi), max(y_lo, y_hi)
    z_lo, z_hi = min(z_lo, z_hi), max(z_lo, z_hi)
    rc, yc, zc = (r_lo + r_hi) / 2.0, (y_lo + y_hi) / 2.0, (z_lo + z_hi) / 2.0
    center = adsk.core.Point3D.create(
        (u.x * rc + v.x * yc) / 10.0, (u.y * rc + v.y * yc) / 10.0, zc / 10.0)
    obb = adsk.core.OrientedBoundingBox3D.create(
        center, u, v, (r_hi - r_lo) / 10.0, (y_hi - y_lo) / 10.0, (z_hi - z_lo) / 10.0)
    return tbm.createBox(obb)


def _radial_cyl(tbm, quadrant, across, z, r0, r1, r):
    """A cylinder on a RADIAL axis at the given quadrant, spanning radius r0 -> r1, offset
    `across` tangentially -- ports `cad/canard_bay.fs`'s `radialCylinder`. mm in, cm
    internally.
    """
    u, v = _quadrant_axes(quadrant)
    bx, by = v.x * across, v.y * across
    p0 = adsk.core.Point3D.create((bx + u.x * r0) / 10.0, (by + u.y * r0) / 10.0, z / 10.0)
    p1 = adsk.core.Point3D.create((bx + u.x * r1) / 10.0, (by + u.y * r1) / 10.0, z / 10.0)
    return tbm.createCylinderOrCone(p0, r / 10.0, p1, r / 10.0)


def _cut(tbm, target, tool, what):
    """Boolean subtract. NOTE: booleanOperation returns a BOOL and mutates `target` in
    place -- never assign its result back, per make_sled_fusion.py's own warning.
    """
    if not tbm.booleanOperation(target, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType):
        raise ValueError("cut %s did not take" % what)


def _union(tbm, target, tool, what):
    if not tbm.booleanOperation(target, tool, adsk.fusion.BooleanTypes.UnionBooleanType):
        raise ValueError("union %s did not take" % what)


def _get_or_create_component(root, name):
    """Find an existing occurrence by component name, else create a new empty one.

    Returns (occurrence, already_has_bodies). A caller that finds `already_has_bodies`
    True should verify rather than rebuild -- the same idempotency rule
    `make_sled_fusion.py` uses.
    """
    for o in root.occurrences:
        if o.component.name == name:
            return o, o.component.bRepBodies.count > 0
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return occ, False


def _inject(comp, made):
    """Inject a list of (name, body) temporary BRep bodies through one BaseFeature.

    Mandatory for a parametric document: a temp body only "takes" via
    `BRepBodies.add(body, baseFeature)`, per make_sled_fusion.py's own header.
    """
    bf = comp.features.baseFeatures.add()
    bf.startEdit()
    for (name, body) in made:
        b = comp.bRepBodies.add(body, bf)
        b.name = name
    bf.finishEdit()


def _verify_volume(comp, want, tol, loose=(), loose_tol=None):
    """Compare each named body's volume (mm3) against an analytic expectation.

    `loose` names bodies (radial holes through curved walls, or a part whose analytic
    figure is itself an estimate) that get `loose_tol` instead of `tol` -- measured, not
    guessed, the same discipline make_sled_fusion.py's PORT_VOLUME_TOLERANCE_PER_PORT uses.
    Returns a list of violation strings (empty if everything is within tolerance).
    """
    acc = adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy
    got = {}
    for b in comp.bRepBodies:
        got[b.name] = b.getPhysicalProperties(acc).volume * 1e3
    bad = []
    for name, wv in want.items():
        if name not in got:
            bad.append("%s is missing" % name)
            continue
        t = loose_tol if (name in loose and loose_tol is not None) else tol
        d = got[name] - wv
        print("  %-28s %14.4f mm3  want %14.4f  delta %+9.4f  (tol %.3f)"
              % (name, got[name], wv, d, t))
        if abs(d) > t:
            bad.append("%s is %+.4f mm3 out" % (name, d))
    return bad


def _verify_cyl_faces(body, radius, axis_is_radial):
    """Count cylindrical faces at `radius` (mm) and read back their clocking, in degrees
    mod 180. `axis_is_radial` True keeps only faces whose axis has no Z component (a
    radial hole); False keeps only faces whose axis IS parallel to Z (an axial hole).
    Exact where a volume check on a radial hole through a curved wall is not -- see
    make_sled_fusion.py's header for why that matters.
    """
    found = []
    for f in body.faces:
        g = f.geometry
        if not g.objectType.endswith("Cylinder"):
            continue
        if abs(g.radius * 10.0 - radius) > 1e-6:
            continue
        ax = g.axis
        is_radial = abs(ax.z) < 1e-9
        if is_radial != axis_is_radial:
            continue
        found.append(math.degrees(math.atan2(ax.y, ax.x)) % 180.0)
    return sorted(found)
'''
