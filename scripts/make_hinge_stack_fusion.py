"""Generate the Fusion 360 script that builds the canard module tube, its four panels and
their four shafts, from design/hinge.py.

    python scripts/make_hinge_stack_fusion.py            # print the script
    python scripts/make_hinge_stack_fusion.py --write    # and into out/make_hinge_stack_fusion_generated.py

MILESTONE M3 of the canard-module Onshape -> Fusion migration (docs/01-next-steps.md
correction 44). None of the five Onshape scripts port directly here -- they all assume the
tube/panels/shafts already exist and only place bearings, cut sockets, or add tangs to
them. This is the file that draws those three parts from scratch, so the module has zero
Onshape dependency and no hand-built snapshot anywhere in its history. The tang cut/boss
(`scripts/make_root_tang.py`) and the spline socket cut (`scripts/make_spline_socket.py`)
are folded directly into the panel/shaft build here rather than kept as separate files,
because this generator already holds direct Python references to "this quadrant's panel
body" and "this quadrant's shaft body" as it builds them -- Onshape's `classifyCanardBodies`
workaround (needed only because a boolean scope there can't name a body by bare ID) simply
does not apply.

NINE COMPONENTS, not flat bodies: `Tube`, `Panel0`..`Panel3`, `Shaft0`..`Shaft3`. Every
other generator in this migration (bay, servo, bearing) dumps its bodies into ONE flat
component the way `make_sled_fusion.py`'s `NavBay` does, because nothing needs to bind a
Fusion Joint to them. These nine do -- the tube-to-shaft revolute joints and the
shaft-to-panel rigid joints (a later milestone) need distinct components to attach to, so
each of these nine gets its own occurrence here, built at build time rather than split out
by a post-process "Create Components from Bodies" step.

THE ONE REAL ARCHITECTURAL EXCEPTION IN THIS MIGRATION: the panel is a swept trapezoid,
which `TemporaryBRepManager` cannot build from box/cylinder primitives (there is no
`createWedge`). Building it needs Fusion's regular `Sketches`/`ExtrudeFeatures` API. To
keep it from becoming a SECOND way this migration builds geometry, the panel is built in a
disposable SCRATCH component (sketch + symmetric extrude there, a real parametric
feature), then `TemporaryBRepManager.copy()` lifts the resulting body into a genuine
temporary BRep body, the scratch component is deleted, and from that point on the panel is
cut and injected exactly like every other body in this migration -- one, and only one,
place in the whole pipeline touches the parametric Sketch/Extrude API, and everything
downstream of it is back on the same temp-BRep pattern as the rest of the project.

PANEL PLANFORM COORDINATES COME FROM `design/hinge.py`'s OWN `RootJoint.leading_edge()`/
`.trailing_edge()`, not from `scripts/make_cad_profiles.py`'s `fin_profile()`. Both encode
the same sweep, but `RootJoint`'s version is already expressed relative to the hinge axis
and already carries the 0.500 mm standoff correction between the panel's real root face (R
40.200) and the planform's theoretical root (R 39.700, the tube OD) that
`selected_root_joint()`'s own docstring says cost this project 0.36 mm once, found only by
the CAD. Using it directly means this generator cannot reintroduce that error.

THE TUBE ALSO CARRIES FOUR WALL BORES, one per hinge axis, at `HingeStack.wall_bore_dia`
(the bearing seat) -- added in the M4 pass after the placement step tried to seat a bearing
into a tube with no hole for it and found M3's first version of this function had never cut
one. A radial hole through a curved wall is the same Fusion volume-precision case
`make_sled_fusion.py`'s own header documents for its ports, so the tube's volume check is
loosened for it and the real check is the face count/diameter/clocking in `verify_tube()`.

THE TANG/SOCKET GEOMETRY, ported from `cad/canard_articulation.fs`'s two custom features:
the shaft is a round dia-6 rod (`sleeve_inboard` -> `panel_root`) with a flat tang boss
unioned onto its outboard end (R `panel_root - TANG_MODEL_OVERSHOOT` -> `panel_root +
engagement`, oversized on purpose so the union has 0.400 mm to bite into), and a blind
spline socket cut into its inboard end. The panel gets a matching slot cut -- the tang's
footprint plus a bond line on every face -- at the same station. Neither body is unioned to
the other: in the real assembly they are bonded, not merged, matching the Onshape original.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import hinge
from design.configure import baseline, build_vehicle
from design.packaging import SERVO_GEOMETRY, SERVOS
from scripts.fusion_common import FUSION_PRELUDE

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "make_hinge_stack_fusion_generated.py"

VOLUME_TOLERANCE_MM3 = 0.02


def geometry():
    p = baseline()
    r = build_vehicle(p)
    g = SERVO_GEOMETRY[p.servo]
    s = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, g)
    hinge_z_m = hinge.canard_hinge_station(r) - r.tube_station(1)
    joint = hinge.selected_root_joint(s, r.canards)
    coupling = hinge.bonded_coupling(s, SERVOS[p.servo].stall_torque)
    return s, hinge_z_m, joint, coupling, r.tubes[1].length


def _shoelace_area(pts: list[tuple[float, float]]) -> float:
    """Area of a simple polygon from its corners -- used here instead of the trapezoid
    formula so the analytic figure makes no assumption about the panel actually being a
    perfect trapezoid; it just measures the same four corners the sketch is built from."""
    n = len(pts)
    a = 0.0
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0



def _radial_bore_volume(a: float, tube_ir: float, tube_or: float) -> float:
    """Volume a RADIAL cylindrical hole of radius `a` removes from a cylindrical shell.

    NOT pi*a^2*t. The hole's axis is radial and the surfaces it breaks through are curved
    about a different axis, so the material actually removed is

        V = integral(-a..a) 2*sqrt(a^2 - y^2) * [sqrt(Ro^2 - y^2) - sqrt(Ri^2 - y^2)] dy

    -- for each chordwise offset y inside the hole, the wall is
    sqrt(Ro^2-y^2) - sqrt(Ri^2-y^2) thick along the hole's own axis, not (Ro - Ri). The
    two agree only as a -> 0.

    Substituting y = a*sin(theta) removes the endpoint singularities and leaves a smooth
    integrand, so composite Simpson over theta converges to well under a thousandth of a
    mm^3 at this size. Kept dependency-free on purpose: this module is imported by an
    emitter, and the emitted script runs inside Fusion's embedded Python where the repo's
    numpy/scipy are not importable.
    """
    n = 2000  # even; Simpson
    lo, hi = -math.pi / 2.0, math.pi / 2.0
    h = (hi - lo) / n

    def f(theta: float) -> float:
        y = a * math.sin(theta)
        wall = math.sqrt(max(tube_or * tube_or - y * y, 0.0)) - math.sqrt(
            max(tube_ir * tube_ir - y * y, 0.0))
        return 2.0 * (a * math.cos(theta)) * wall * a * math.cos(theta)

    total = f(lo) + f(hi)
    for i in range(1, n):
        total += f(lo + i * h) * (4.0 if i % 2 else 2.0)
    return total * h / 3.0


def emit() -> str:
    s, hinge_z_m, joint, coupling, tube_length_m = geometry()

    hinge_z = hinge_z_m * MM
    tube_or = s.tube_outer_radius * MM
    tube_ir = s.tube_inner_radius * MM
    tube_len = tube_length_m * MM
    wall_bore_dia = s.wall_bore_dia * MM

    journal_r = s.journal_dia * MM / 2.0
    sleeve_inboard = s.sleeve_inboard * MM
    panel_root = s.panel_root * MM
    sleeve_length = s.sleeve_length * MM

    tang_thickness = joint.tang_thickness * MM
    tang_width = joint.tang_width * MM
    engagement = joint.engagement * MM
    bond_line = joint.bond_line * MM
    tang_overshoot = hinge.TANG_MODEL_OVERSHOOT * MM
    slot_thickness = joint.slot_thickness * MM
    slot_width = joint.slot_width * MM

    socket_dia = coupling.socket_dia * MM
    socket_depth = coupling.socket_depth * MM

    tip_r_m = joint.body_radius + joint.panel_semispan
    tip_r = tip_r_m * MM
    root_le = hinge_z + joint.leading_edge(s.panel_root) * MM
    root_te = hinge_z + joint.trailing_edge(s.panel_root) * MM
    tip_le = hinge_z + joint.leading_edge(tip_r_m) * MM
    tip_te = hinge_z + joint.trailing_edge(tip_r_m) * MM
    panel_thickness = joint.panel_thickness * MM

    # ---- analytic volumes, all measured against the SAME corners/dimensions the emitted
    # script builds from, not a separate simplified model -----------------------------
    # The tube needs FOUR wall bores, one per hinge axis (HingeStack.wall_bore_dia, the
    # bearing seat) -- missed in the first pass of this generator (M3), since nothing
    # forced the omission to surface until M4 tried to place a bearing into a tube with no
    # hole for it. pi*r^2*wall_thickness is not exact for a RADIAL hole through a CURVED
    # wall -- the same Fusion-precision issue make_sled_fusion.py's own header documents at
    # length for its ports -- so the tube's own tolerance is loosened below, measured, and
    # the real check on the bores is the face check in verify(), not their volume.
    wall_thickness = tube_or - tube_ir
    bore_volume_each = _radial_bore_volume(wall_bore_dia / 2.0, tube_ir, tube_or)
    tube_volume = math.pi * (tube_or ** 2 - tube_ir ** 2) * tube_len - 4.0 * bore_volume_each
    # 0.05 mm3 per hole. It was 0.2, "measured", against a pi*r^2*t bore model -- and the
    # 0.2 was not a Fusion precision limit at all, it was that model's own error, which is
    # 0.156 mm3 at the dia 8 bore it was measured on. It scales hard: dia 12 makes it
    # 0.796 mm3 per hole, four of which blew straight through a 0.8 mm3 budget the first
    # time the journal grew (correction 62). `_radial_bore_volume` integrates the hole
    # exactly instead, which lands within 0.04 mm3 per hole of Fusion -- so the tolerance
    # tightens by 4x rather than loosening, and it no longer moves when the bore does.
    TUBE_BORE_TOLERANCE_MM3 = 0.05

    rod_volume = math.pi * journal_r ** 2 * sleeve_length
    tang_box_volume = tang_thickness * tang_width * (engagement + tang_overshoot)
    # The tang boss overlaps the round rod over the TANG_MODEL_OVERSHOOT band -- the
    # intersection of a rectangle (tang cross-section) and a circle (rod cross-section),
    # a "circular zone" between two chords equidistant from the centre. Same style of
    # formula scripts/make_root_tang.py's own expected_mass_change_g() used for this exact
    # overlap on the Onshape side.
    zone_h = tang_thickness / 2.0
    zone_area = (2.0 * journal_r ** 2 * math.asin(zone_h / journal_r)
                + 2.0 * zone_h * math.sqrt(journal_r ** 2 - zone_h ** 2))
    overlap_volume = zone_area * tang_overshoot
    socket_volume = math.pi * (socket_dia / 2.0) ** 2 * socket_depth
    shaft_volume = rod_volume + tang_box_volume - overlap_volume - socket_volume

    panel_corners = [(panel_root, root_le), (tip_r, tip_le), (tip_r, tip_te), (panel_root, root_te)]
    trapezoid_area = _shoelace_area(panel_corners)
    slot_volume = slot_thickness * slot_width * (engagement + bond_line)
    panel_volume = trapezoid_area * panel_thickness - slot_volume

    return f'''"""GENERATED by scripts/make_hinge_stack_fusion.py -- do not edit this file.

Every number below comes from design/hinge.py. Regenerate rather than patch.

Tube     OD {2 * tube_or:.3f} / ID {2 * tube_ir:.3f} x {tube_len:.3f} long, Z 0.000 .. {tube_len:.3f}
Panel    R {panel_root:.3f} .. {tip_r:.3f}, root chord Z {root_le:.3f} .. {root_te:.3f}, tip chord Z {tip_le:.3f} .. {tip_te:.3f}
         thickness {panel_thickness:.3f}, tang slot {slot_thickness:.3f} x {slot_width:.3f} x {engagement + bond_line:.3f} deep
Shaft    dia {2 * journal_r:.3f} rod R {sleeve_inboard:.3f} .. {panel_root:.3f}, tang boss to R {panel_root + engagement:.3f}
         spline socket dia {socket_dia:.3f} x {socket_depth:.3f} deep from R {sleeve_inboard:.3f}
Volumes  tube {tube_volume:.4f}  panel {panel_volume:.4f}  shaft {shaft_volume:.4f}  mm3 (each x4 for panel/shaft)
"""

{FUSION_PRELUDE}

OVER = 1.0   # mm, overshoot on every open-face cut/join -- see fusion_common.py's header

TUBE_OR = {tube_or:.4f}
TUBE_IR = {tube_ir:.4f}
TUBE_LEN = {tube_len:.4f}
TUBE_VOLUME = {tube_volume:.4f}
TUBE_BORE_TOLERANCE = {TUBE_BORE_TOLERANCE_MM3 * 4.0:.4f}
WALL_BORE_DIA = {wall_bore_dia:.4f}

HINGE_Z = {hinge_z:.4f}
JOURNAL_R = {journal_r:.4f}
SLEEVE_INBOARD = {sleeve_inboard:.4f}
PANEL_ROOT = {panel_root:.4f}
SLEEVE_LENGTH = {sleeve_length:.4f}

TANG_THICKNESS = {tang_thickness:.4f}
TANG_WIDTH = {tang_width:.4f}
ENGAGEMENT = {engagement:.4f}
BOND_LINE = {bond_line:.4f}
TANG_OVERSHOOT = {tang_overshoot:.4f}
SLOT_THICKNESS = {slot_thickness:.4f}
SLOT_WIDTH = {slot_width:.4f}

SOCKET_DIA = {socket_dia:.4f}
SOCKET_DEPTH = {socket_depth:.4f}

TIP_R = {tip_r:.4f}
ROOT_LE = {root_le:.4f}
ROOT_TE = {root_te:.4f}
TIP_LE = {tip_le:.4f}
TIP_TE = {tip_te:.4f}
PANEL_THICKNESS = {panel_thickness:.4f}

SHAFT_VOLUME = {shaft_volume:.4f}
PANEL_VOLUME = {panel_volume:.4f}
VOLUME_TOLERANCE = {VOLUME_TOLERANCE_MM3:.4f}


def build_tube(root):
    occ, has_bodies = _get_or_create_component(root, "Tube")
    if has_bodies:
        print("Tube already holds a body -- verifying rather than rebuilding")
        verify_tube(occ.component)
        return
    comp = occ.component
    tbm = adsk.fusion.TemporaryBRepManager.get()
    outer = _cyl(tbm, 0.0, 0.0, 0.0, TUBE_LEN, TUBE_OR)
    _cut(tbm, outer, _cyl(tbm, 0.0, 0.0, -OVER, TUBE_LEN + OVER, TUBE_IR), "bore")
    # Four wall bores, one per hinge axis -- the bearing seat (HingeStack.wall_bore_dia).
    # Missing from M3's first pass; see the emit()-side comment on TUBE_BORE_TOLERANCE.
    for q in range(4):
        wall_bore = _radial_cyl(tbm, q, 0.0, HINGE_Z, TUBE_IR - OVER, TUBE_OR + OVER,
                                WALL_BORE_DIA / 2.0)
        _cut(tbm, outer, wall_bore, "wall bore %d" % q)
    _inject(comp, [("tube", outer)])
    print("built 1 body in Tube")
    verify_tube(comp)


def verify_tube(comp):
    """Volume loosened for the four wall bores (radial holes through a curved wall --
    see emit()'s comment), plus an exact face check on them: right count, right
    diameter, right clocking, where the volume figure is not exact."""
    bad = _verify_volume(comp, {{"tube": TUBE_VOLUME}}, VOLUME_TOLERANCE,
                         loose=("tube",), loose_tol=TUBE_BORE_TOLERANCE)

    body = None
    for b in comp.bRepBodies:
        if b.name == "tube":
            body = b
    if body is None:
        bad.append("tube body is missing, so its wall bores cannot be checked")
    else:
        found = _verify_cyl_faces(body, WALL_BORE_DIA / 2.0, axis_is_radial=True)
        print("  %-28s %d wall-bore faces at dia %.2f, axes %s deg"
              % ("tube", len(found), WALL_BORE_DIA, ["%.2f" % v for v in found]))
        if len(found) != 4:
            bad.append("tube has %d wall-bore faces, wanted 4" % len(found))
        else:
            for a in found:
                if min(abs(a - 0.0), abs(a - 90.0)) > 1e-6:
                    bad.append("a wall bore is clocked %.4f deg, wanted 0 or 90" % a)

    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK")


def build_panel(root, q):
    name = "Panel%d" % q
    occ, has_bodies = _get_or_create_component(root, name)
    if has_bodies:
        print("%s already holds a body -- verifying rather than rebuilding" % name)
        verify_one(occ.component, "panel", PANEL_VOLUME)
        return
    comp = occ.component
    tbm = adsk.fusion.TemporaryBRepManager.get()

    # ---- the trapezoid, built as a real parametric feature in a disposable scratch
    #      component, then lifted into a temp body so everything past this point stays
    #      on the same pattern as the rest of the migration -- see the module docstring.
    a = math.radians(q * 90.0)
    ux, uy = math.cos(a), math.sin(a)

    def pt(r, z):
        return adsk.core.Point3D.create(ux * r / 10.0, uy * r / 10.0, z / 10.0)

    scratch_occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    scratch = scratch_occ.component
    plane = scratch.xZConstructionPlane if q in (0, 2) else scratch.yZConstructionPlane
    sk = scratch.sketches.add(plane)
    corners = [pt(PANEL_ROOT, ROOT_LE), pt(TIP_R, TIP_LE), pt(TIP_R, TIP_TE), pt(PANEL_ROOT, ROOT_TE)]
    sk_pts = [sk.modelToSketchSpace(c) for c in corners]
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
    exin.setSymmetricExtent(adsk.core.ValueInput.createByReal(PANEL_THICKNESS / 10.0), True)
    feat = scratch.features.extrudeFeatures.add(exin)
    raw = tbm.copy(feat.bodies.item(0))
    scratch_occ.deleteMe()

    # ---- the tang slot, cut from the lifted temp body exactly like every other cut
    #      in this migration. SLOT_THICKNESS runs tangentially (Y, through the panel's
    #      own thickness -- it has to fit inside PANEL_THICKNESS) and SLOT_WIDTH runs
    #      axially (Z, chordwise -- it is what leading_edge_clearance/trailing_edge_
    #      clearance in design/hinge.py measure against the swept LE/TE). Swapping these
    #      is the bug this generator's own verify() caught on the first run: a slot cut
    #      only ~2 mm wide in Z instead of ~12 mm removed a quarter of the material it
    #      should have. ----
    slot = _quadrant_box(tbm, q, PANEL_ROOT - OVER, PANEL_ROOT + ENGAGEMENT + BOND_LINE,
                         -SLOT_THICKNESS / 2.0, SLOT_THICKNESS / 2.0,
                         HINGE_Z - SLOT_WIDTH / 2.0, HINGE_Z + SLOT_WIDTH / 2.0)
    _cut(tbm, raw, slot, "tang slot")

    _inject(comp, [("panel", raw)])
    print("built 1 body in %s" % name)
    verify_one(comp, "panel", PANEL_VOLUME)


def build_shaft(root, q):
    name = "Shaft%d" % q
    occ, has_bodies = _get_or_create_component(root, name)
    if has_bodies:
        print("%s already holds a body -- verifying rather than rebuilding" % name)
        verify_one(occ.component, "shaft", SHAFT_VOLUME)
        return
    comp = occ.component
    tbm = adsk.fusion.TemporaryBRepManager.get()

    rod = _radial_cyl(tbm, q, 0.0, HINGE_Z, SLEEVE_INBOARD, PANEL_ROOT, JOURNAL_R)
    # TANG_THICKNESS runs tangentially (Y), TANG_WIDTH runs axially (Z, chordwise) --
    # see build_panel's own comment on the matching slot cut for why.
    tang = _quadrant_box(tbm, q, PANEL_ROOT - TANG_OVERSHOOT, PANEL_ROOT + ENGAGEMENT,
                         -TANG_THICKNESS / 2.0, TANG_THICKNESS / 2.0,
                         HINGE_Z - TANG_WIDTH / 2.0, HINGE_Z + TANG_WIDTH / 2.0)
    _union(tbm, rod, tang, "tang boss")

    socket = _radial_cyl(tbm, q, 0.0, HINGE_Z, SLEEVE_INBOARD - OVER,
                         SLEEVE_INBOARD + SOCKET_DEPTH, SOCKET_DIA / 2.0)
    _cut(tbm, rod, socket, "spline socket")

    _inject(comp, [("shaft", rod)])
    print("built 1 body in %s" % name)
    verify_one(comp, "shaft", SHAFT_VOLUME)


def verify_one(comp, expected_name, want_volume):
    bad = _verify_volume(comp, {{expected_name: want_volume}}, VOLUME_TOLERANCE)
    if bad:
        raise ValueError("VERIFY FAILED: " + "; ".join(bad))
    print("  OK")


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent

    build_tube(root)
    for q in range(4):
        build_panel(root, q)
    for q in range(4):
        build_shaft(root, q)
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
