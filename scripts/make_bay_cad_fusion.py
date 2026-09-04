"""Generate the Fusion 360 script that builds the printed canard bay, from design/bay.py.

    python scripts/make_bay_cad_fusion.py            # print the script
    python scripts/make_bay_cad_fusion.py --write    # and into out/make_bay_cad_fusion_generated.py

MILESTONE M1 of the canard-module Onshape -> Fusion migration (docs/01-next-steps.md
correction 44). The bay is the biggest of the six ports and the first one attempted,
because it is the part `cad/canard_bay.fs`'s own header says was forced into a custom
FeatureScript feature by two Onshape-only limitations that do not exist against Fusion's
temp-BRep API: a boolean scope cannot name bodies by bare ID, and a radial extrude in plain
feature JSON needs a sketch on a plane that has to be named by a query. Neither constraint
applies here -- every body below is a `TemporaryBRepManager` primitive held as a direct
Python object reference, and `fusion_common._quadrant_box`/`_radial_cyl` take absolute 3D
points, no sketch plane required.

THIS FILE PORTS `cad/canard_bay.fs`'s GEOMETRIC LOGIC, not its FeatureScript mechanics. The
per-quadrant loop structure, the union-before-cut ordering (shell must gain its trays,
webs, collars and bosses BEFORE the collar bores and windows are subtracted, or the cuts
have nothing to remove material from at those radii), and every coordinate expression are
read directly off that file and `scripts/make_bay_cad.py`'s `parameters()` (which is itself
just design/bay.py's `BayGeometry` re-expressed as Onshape parameters) -- see both for the
"why" behind each dimension; this file only carries the "what".

THE FRAME. Same as `make_sled_fusion.py`'s: origin on the rocket axis, Z = 0 at the canard
module tube's forward face, +Z aft. The bay needs NO placement transform, the same reason
`scripts/make_bay_cad.py`'s own docstring gives for skipping one in Onshape: it is drawn
directly in this frame, so it drops in at its real position by construction.

EIGHT RETAINER BARS, DRAWN DIRECTLY RATHER THAN INSTANCED. The Onshape side models the bar
ONCE and flies it eight times via assembly-instance transforms, because that is how Onshape
reuses a Part Studio body across an assembly. A from-scratch Fusion generator has no
instancing step to exploit -- every body here is freshly built geometry regardless -- so
this file just runs the same quadrant/row loop eight times with `fusion_common`'s
quadrant-frame helpers, once per (quadrant, screw row), rather than building one bar and
then deriving seven more transforms for it.

GEOMETRY IS BUILT AS TEMPORARY BREP BODIES INJECTED THROUGH A BaseFeature, via
`scripts/fusion_common.py`'s shared helpers -- see that file's header for why.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import bay, hinge
from design.configure import baseline, build_vehicle
from design.packaging import SERVO_GEOMETRY
from scripts.fusion_common import FUSION_PRELUDE

MM = 1000.0
OUT = Path(__file__).resolve().parents[1] / "out" / "make_bay_cad_fusion_generated.py"

COMPONENT = "CanardBay"

# design/bay.py's own tolerance on this part's volume, carried forward unchanged: the
# analytic figure is a sum of prisms and cylinders that does not model the webs'
# embedment in the shell wall or the boss/tray overlap, so it is an ESTIMATE and the CAD
# is the truth -- see scripts/make_bay_cad.py's VOLUME_TOLERANCE for the same reasoning.
# A relative band, not an absolute one, because "canard bay" is one ~29 g body.
BAY_VOLUME_TOLERANCE_FRACTION = 0.06
BAR_VOLUME_TOLERANCE_MM3 = 0.01   # a box with round holes -- exact, like the sled's plate


def geometry() -> bay.BayGeometry:
    p = baseline()
    r = build_vehicle(p)
    g = SERVO_GEOMETRY[p.servo]
    s = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, g)
    return bay.build_bay(s, g, hinge.canard_hinge_station(r) - r.tube_station(1))


def emit() -> str:
    b = geometry()

    bay_volume_mm3 = (b.volume - b.retainer_volume) * 1e9
    # design/bay.py's `retainer_volume` is a bridge plus two pads and does not subtract
    # the two screw holes `cad/canard_bay.fs` cuts through every bar ("retholes") -- the
    # Onshape-side verify() never caught this because it only checks the SHELL's volume
    # against `b.volume - b.retainer_volume`, never the bar's own. This generator's own
    # verify() DOES check the bar individually, so the expected figure has to be honest
    # about the holes actually cut: measured (a plain cylinder through a flat plate needs
    # no Fusion-precision correction, unlike a radial hole through a curved wall -- see
    # PORT_VOLUME_TOLERANCE_PER_PORT in make_sled_fusion.py), not assumed.
    hole_dia_mm = bay.INSERT_DIA * MM * 0.7
    hole_volume_mm3 = 2.0 * math.pi * (hole_dia_mm / 2.0) ** 2 * (bay.RETAINER_THICKNESS * MM)
    bar_volume_mm3 = b.retainer_volume / 8.0 * 1e9 - hole_volume_mm3
    bay_tol_mm3 = BAY_VOLUME_TOLERANCE_FRACTION * bay_volume_mm3

    return f'''"""GENERATED by scripts/make_bay_cad_fusion.py -- do not edit this file.

Every number below comes from design/bay.py. Regenerate rather than patch.

Bay      shell OD {2 * b.shell_outer_radius * MM:.3f} mm, ID {2 * b.shell_inner_radius * MM:.3f} mm, Z {b.forward_face * MM:.2f} -> {b.aft_face * MM:.2f}
Collars  4 x dia {bay.COLLAR_OD * MM:.1f} boss, dia {b.collar_bore * MM:.2f} bore (as reamed), at Z {b.hinge_station * MM:.2f}
Trays    4 x servo window {b.window_length * MM:.2f} x {b.window_width * MM:.2f} mm, R {b.tray_flange_face * MM:.2f} -> {b.tray_back_face * MM:.2f}
Screws   Z {b.screw_stations[0] * MM:.2f} / {b.screw_stations[1] * MM:.2f}, insert dia {bay.INSERT_DIA * MM:.1f} at Y +/-{bay.RETAINER_SCREW_ACROSS * MM:.1f}
Retainer 8 x dog-bone bar, {bay.RETAINER_THICKNESS * MM:.1f} mm thick, R {b.boss_face * MM - bay.RETAINER_THICKNESS * MM:.3f} -> {b.boss_face * MM:.3f}
Volume   canard bay {bay_volume_mm3:.1f} mm3 (+/-{BAY_VOLUME_TOLERANCE_FRACTION * 100:.0f}%), one retainer bar {bar_volume_mm3:.4f} mm3
"""

{FUSION_PRELUDE}

COMPONENT = {COMPONENT!r}
OVER = 1.0   # mm, overshoot on every cut/join -- see fusion_common.py's header

SHELL_OD = {2 * b.shell_outer_radius * MM:.4f}
SHELL_ID = {2 * b.shell_inner_radius * MM:.4f}
Z_FWD = {b.forward_face * MM:.4f}
Z_AFT = {b.aft_face * MM:.4f}
Z_HINGE = {b.hinge_station * MM:.4f}

COLLAR_OD = {bay.COLLAR_OD * MM:.4f}
COLLAR_BORE = {b.collar_bore * MM:.4f}
COLLAR_OVERLAP = {bay.COLLAR_BOSS_OVERLAP * MM:.4f}
COLLAR_INNER_R = {b.stack.bearing_inboard * MM:.4f}

TRAY_FLANGE_R = {b.tray_flange_face * MM:.4f}
TRAY_BACK_R = {b.tray_back_face * MM:.4f}
TRAY_WIDTH = {b.tray_width * MM:.4f}
TRAY_FWD_Z = {b.servo_forward * MM:.4f}
TRAY_AFT_Z = {b.servo_aft * MM:.4f}

WINDOW_LEN = {b.window_length * MM:.4f}
WINDOW_WID = {b.window_width * MM:.4f}
WINDOW_FWD_Z = {b.window_forward * MM:.4f}

WEB_THK = {bay.MIN_WALL * MM:.4f}
BOSS_FACE_R = {b.boss_face * MM:.4f}
INSERT_DIA = {bay.INSERT_DIA * MM:.4f}
INSERT_DEPTH = {bay.INSERT_DEPTH * MM:.4f}
CLAMP_Y = {bay.RETAINER_SCREW_ACROSS * MM:.4f}
SCREW_Z1 = {b.screw_stations[0] * MM:.4f}
SCREW_Z2 = {b.screw_stations[1] * MM:.4f}

RET_THK = {bay.RETAINER_THICKNESS * MM:.4f}
RET_BRIDGE_HALF_Z = {bay.RETAINER_BRIDGE_HALF_Z * MM:.4f}
RET_PAD_HALF_Z = {bay.RETAINER_PAD_HALF_Z * MM:.4f}

BAY_VOLUME_MM3 = {bay_volume_mm3:.4f}
BAR_VOLUME_MM3 = {bar_volume_mm3:.4f}
BAY_VOLUME_TOLERANCE = {bay_tol_mm3:.4f}
BAR_VOLUME_TOLERANCE = {BAR_VOLUME_TOLERANCE_MM3:.4f}


def run(_context: str):
    app = adsk.core.Application.get()
    des = adsk.fusion.Design.cast(app.activeProduct)
    root = des.rootComponent
    tbm = adsk.fusion.TemporaryBRepManager.get()

    occ, has_bodies = _get_or_create_component(root, COMPONENT)
    if has_bodies:
        print("%s already holds %d bodies -- verifying rather than rebuilding"
              % (COMPONENT, occ.component.bRepBodies.count))
        verify(occ.component)
        return
    comp = occ.component

    made = []

    # ---- 1. the shell, hollowed ----
    shell = _cyl(tbm, 0.0, 0.0, Z_FWD, Z_AFT, SHELL_OD / 2.0)
    _cut(tbm, shell, _cyl(tbm, 0.0, 0.0, Z_FWD - OVER, Z_AFT + OVER, SHELL_ID / 2.0), "hollow")

    # ---- 2. additive bodies, four quadrants -- shell must gain these BEFORE section 3
    #         cuts, or the cuts have nothing to remove material from at those radii ----
    for q in range(4):
        collar = _radial_cyl(tbm, q, 0.0, Z_HINGE, COLLAR_INNER_R,
                              SHELL_ID / 2.0 + COLLAR_OVERLAP, COLLAR_OD / 2.0)
        _union(tbm, shell, collar, "collar %d" % q)

        tray = _quadrant_box(tbm, q, TRAY_FLANGE_R, TRAY_BACK_R,
                              -TRAY_WIDTH / 2.0, TRAY_WIDTH / 2.0, TRAY_FWD_Z, TRAY_AFT_Z)
        _union(tbm, shell, tray, "tray %d" % q)

        for sgn in (1.0, -1.0):
            y_outer = sgn * TRAY_WIDTH / 2.0
            y_inner = y_outer - sgn * WEB_THK
            web = _quadrant_box(tbm, q, TRAY_BACK_R, SHELL_ID / 2.0 + OVER,
                                 y_inner, y_outer, TRAY_FWD_Z, TRAY_AFT_Z)
            _union(tbm, shell, web, "web %d %s" % (q, "p" if sgn > 0 else "m"))

        for k, z_row in enumerate((SCREW_Z1, SCREW_Z2)):
            z_lo = max(z_row - INSERT_DIA, TRAY_FWD_Z)
            z_hi = min(z_row + INSERT_DIA, TRAY_AFT_Z)
            boss = _quadrant_box(tbm, q, BOSS_FACE_R, TRAY_FLANGE_R,
                                  -TRAY_WIDTH / 2.0, TRAY_WIDTH / 2.0, z_lo, z_hi)
            _union(tbm, shell, boss, "boss %d row%d" % (q, k))

    # ---- 3. subtractive bodies, four quadrants ----
    for q in range(4):
        bore = _radial_cyl(tbm, q, 0.0, Z_HINGE, COLLAR_INNER_R - OVER,
                            SHELL_OD / 2.0 + OVER, COLLAR_BORE / 2.0)
        _cut(tbm, shell, bore, "collar bore %d" % q)

        window = _quadrant_box(tbm, q, BOSS_FACE_R - OVER, TRAY_BACK_R + OVER,
                                -WINDOW_WID / 2.0, WINDOW_WID / 2.0,
                                WINDOW_FWD_Z, WINDOW_FWD_Z + WINDOW_LEN)
        _cut(tbm, shell, window, "window %d" % q)

        flange = _quadrant_box(tbm, q, BOSS_FACE_R - OVER, TRAY_FLANGE_R,
                                -WINDOW_WID / 2.0, WINDOW_WID / 2.0,
                                TRAY_FWD_Z - OVER, TRAY_AFT_Z + OVER)
        _cut(tbm, shell, flange, "flange relief %d" % q)

        for k, z_row in enumerate((SCREW_Z1, SCREW_Z2)):
            for sgn in (1.0, -1.0):
                ins = _radial_cyl(tbm, q, sgn * CLAMP_Y, z_row,
                                   BOSS_FACE_R - OVER, BOSS_FACE_R + INSERT_DEPTH,
                                   INSERT_DIA / 2.0)
                _cut(tbm, shell, ins, "insert %d row%d %s" % (q, k, "p" if sgn > 0 else "m"))

    made.append(("canard bay", shell))

    # ---- 4. eight retainer bars, drawn directly per (quadrant, screw row) -- see the
    #         module docstring for why this isn't one bar instanced eight times ----
    r_in = BOSS_FACE_R - RET_THK
    r_out = BOSS_FACE_R
    y_flange = WINDOW_WID / 2.0
    y_outer = TRAY_WIDTH / 2.0
    for q in range(4):
        for k, z_row in enumerate((SCREW_Z1, SCREW_Z2)):
            bar = _quadrant_box(tbm, q, r_in, r_out, -y_flange, y_flange,
                                 z_row - RET_BRIDGE_HALF_Z, z_row + RET_BRIDGE_HALF_Z)
            for sgn in (1.0, -1.0):
                pad = _quadrant_box(tbm, q, r_in, r_out, sgn * y_flange, sgn * y_outer,
                                     z_row - RET_PAD_HALF_Z, z_row + RET_PAD_HALF_Z)
                _union(tbm, bar, pad, "retainer pad q%dr%d" % (q, k))
            for sgn in (1.0, -1.0):
                hole = _radial_cyl(tbm, q, sgn * CLAMP_Y, z_row, r_in - OVER, r_out + OVER,
                                    INSERT_DIA * 0.7 / 2.0)
                _cut(tbm, bar, hole, "retainer hole q%dr%d" % (q, k))
            made.append(("retainer bar q%dr%d" % (q, k), bar))

    _inject(comp, made)
    print("built %d bodies in %s" % (len(made), COMPONENT))
    verify(comp)


def verify(comp):
    """Volume against design/bay.py's analytic figure, plus a face check on the collar
    bores that a volume check cannot make exact -- see fusion_common.py's header and
    make_sled_fusion.py's for why a radial hole through a curved wall needs one.
    """
    want = {{"canard bay": BAY_VOLUME_MM3}}
    for q in range(4):
        for k in range(2):
            want["retainer bar q%dr%d" % (q, k)] = BAR_VOLUME_MM3
    bad = _verify_volume(comp, want, BAR_VOLUME_TOLERANCE,
                         loose=("canard bay",), loose_tol=BAY_VOLUME_TOLERANCE)

    bay_body = None
    for b in comp.bRepBodies:
        if b.name == "canard bay":
            bay_body = b
    if bay_body is None:
        bad.append("canard bay body is missing, so its collar bores cannot be checked")
    else:
        found = _verify_cyl_faces(bay_body, COLLAR_BORE / 2.0, axis_is_radial=True)
        print("  %-28s %d collar-bore faces at dia %.2f, axes %s deg"
              % ("canard bay", len(found), COLLAR_BORE, ["%.2f" % v for v in found]))
        if len(found) != 4:
            bad.append("canard bay has %d collar-bore faces, wanted 4" % len(found))
        else:
            for a in found:
                if min(abs(a - 0.0), abs(a - 90.0)) > 1e-6:
                    bad.append("a collar bore is clocked %.4f deg, wanted 0 or 90" % a)

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
