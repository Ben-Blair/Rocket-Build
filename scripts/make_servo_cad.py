"""Build the KST X08 Plus as real geometry in Onshape, from the datasheet numbers held
in design/packaging.py.

Run:  python scripts/make_servo_cad.py [--rebuild]

This replaces the 23.5 x 8 x 16.8 envelope block that stood in for the servo. A bounding
box was enough to carry 9 g of mass and nothing else: it has no output shaft, so it could
not show that the shaft is 5.61 mm off the case centre, and no shaft axis, so it could not
show that a radial output points along the 16.8 mm dimension rather than the 8 mm one.
Both of those were wrong in the model and both are corrected here.

FRAME, and it is chosen to make mating trivial: the origin is ON THE OUTPUT AXIS, on the
case face the spline emerges from. +Z is the direction the spline points, +X runs along
the 23.5 mm case axis away from the near end, +Y across the 8 mm width. So in the module
assembly, +Z is radially outward and the origin lands on the hinge axis at the wall --
which means the servo mates to the canard hinge with no offset arithmetic at all.

The spline is a separate part from the case, because it rotates and the case does not.
That is the whole point: it is what makes the assembly articulate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from design import onshape_build as ob
from design.onshape import get, post
from design.packaging import SERVO_GEOMETRY, SERVOS

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ELEMENT_NAME = "KST X08 Plus"

SERVO_KEY = "kst_x08_plus"

# The lower boss is drawn on the datasheet's side view but not dimensioned in plan, so its
# extent along the case is scaled off that view. It is modelled as a separate part and
# treated as a KEEP-OUT, not as structure: it is the radial depth that matters, and that
# IS dimensioned (27.10 from the top face). Confirm against a physical part before
# anything load-bearing depends on where it starts.
BOSS_START_FROM_SHAFT_MM = 9.2


def mm(metres: float) -> float:
    return metres * 1000.0


def find_element(name: str):
    for e in get(f"/documents/d/{DOC}/w/{WS}/elements"):
        if e["name"] == name:
            return e
    return None


def add(feature: dict, element: str) -> str:
    r = post(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/features", {"feature": feature})
    return r["feature"]["featureId"]


def build(element: str) -> None:
    g = SERVO_GEOMETRY[SERVO_KEY]

    x_near = -mm(g.shaft_from_end)                       # near case end
    x_far = x_near + mm(g.case_length)                   # far case end
    half_w = mm(g.case_width) / 2.0
    env_near = x_near - (mm(g.envelope_length) - mm(g.case_length)) / 2.0
    env_far = env_near + mm(g.envelope_length)
    lug_x = [env_near + 1.5, env_far - 1.5]              # lug hole line, 1.5 in from tips
    lug_y = mm(g.lug_hole_pitch_across) / 2.0

    # Self-check: the datasheet dimensions the shaft 7.64 mm from the lug-hole line. If
    # this assertion ever fires, the envelope/case/shaft numbers have stopped agreeing.
    assert abs(abs(lug_x[0]) - 7.64) < 0.01, f"lug line at {lug_x[0]}, expected -7.64"

    # 1. Case.
    s = add(ob.sketch("Case outline", "Top",
                      ob.rect(x_near / 1000, -half_w / 1000, x_far / 1000, half_w / 1000,
                              "case")), element)
    add(ob.extrude("Case", [ob.sketch_regions(s)], depth_mm=mm(g.case_height),
                   opposite=True), element)

    # 2. Mounting flange, merged into the case. Modelled as a full plate; the part of it
    #    inside the case footprint is already solid, so the union is a no-op there.
    s = add(ob.sketch("Flange outline", "Top",
                      ob.rect(env_near / 1000, -half_w / 1000, env_far / 1000,
                              half_w / 1000, "flange")), element)
    add(ob.extrude("Mounting flange", [ob.sketch_regions(s)],
                   depth_mm=mm(g.flange_thickness), opposite=True,
                   start_offset_mm=mm(g.flange_from_top), start_offset_opposite=True,
                   operation="ADD"), element)

    # 3. Lug holes. Cut from well above the flange to well below it -- a REMOVE that lands
    #    exactly on a face is degenerate and silently cuts nothing. That bug has already
    #    cost this project once; see docs/05.
    holes = []
    for i, x in enumerate(lug_x):
        for y in (-lug_y, lug_y):
            holes.append(ob.circle(x / 1000, y / 1000, mm(g.lug_hole_dia) / 2000,
                                   f"h{i}{'p' if y > 0 else 'n'}"))
        holes.append(ob.circle(x / 1000, 0.0, mm(g.lug_hole_2_dia) / 2000, f"H{i}"))
    s = add(ob.sketch("Lug holes", "Top", holes), element)
    over = 1.0
    add(ob.extrude("Lug holes", [ob.sketch_regions(s)],
                   depth_mm=mm(g.flange_thickness) + 2 * over, opposite=True,
                   start_offset_mm=mm(g.flange_from_top) - over,
                   start_offset_opposite=True, operation="REMOVE"), element)

    # 4. Output spline -- ITS OWN PART, because it turns and the case does not.
    #    Modelled as a plain cylinder at the spline's outside diameter. The 15 teeth are
    #    a coupling detail, not an interference one; nothing downstream reads them.
    s = add(ob.sketch("Spline", "Top",
                      [ob.circle(0.0, 0.0, mm(g.spline_dia) / 2000, "spline")]), element)
    add(ob.extrude("Output spline", [ob.sketch_regions(s)],
                   depth_mm=mm(g.shaft_proud_of_top)), element)

    # 5. Lower boss, as a keep-out part.
    s = add(ob.sketch("Lower boss outline", "Top",
                      ob.rect(BOSS_START_FROM_SHAFT_MM / 1000, -half_w / 1000,
                              x_far / 1000, half_w / 1000, "boss")), element)
    add(ob.extrude("Lower boss (keep-out)", [ob.sketch_regions(s)],
                   depth_mm=mm(g.depth_from_top) - mm(g.case_height), opposite=True,
                   start_offset_mm=mm(g.case_height), start_offset_opposite=True),
        element)


def main() -> None:
    rebuild = "--rebuild" in sys.argv
    existing = find_element(ELEMENT_NAME)
    if existing and not rebuild:
        print(f"'{ELEMENT_NAME}' already exists ({existing['id']}). "
              f"Pass --rebuild to delete and regenerate it.")
        return
    if existing:
        from design.onshape import call
        call("DELETE", f"/elements/d/{DOC}/w/{WS}/e/{existing['id']}")
        print(f"deleted existing '{ELEMENT_NAME}'")

    el = post(f"/partstudios/d/{DOC}/w/{WS}", {"name": ELEMENT_NAME})
    element = el["id"]
    print(f"created part studio '{ELEMENT_NAME}' -> {element}")
    build(element)

    g = SERVO_GEOMETRY[SERVO_KEY]
    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{element}")
    print(f"\n{len(parts)} parts:")
    for p in parts:
        print(f"  {p['partId']:4s} {p['name']}")
    bb = get(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/boundingboxes")
    print("\nbounding box, mm:")
    for k in ("lowX", "highX", "lowY", "highY", "lowZ", "highZ"):
        print(f"  {k:6s} {bb[k] * 1000:8.2f}")
    print(f"\nexpected: X {-mm(g.shaft_from_end) - 3:.2f} .. "
          f"{-mm(g.shaft_from_end) + mm(g.case_length) + 3:.2f}  "
          f"Y +/-{mm(g.case_width) / 2:.2f}  "
          f"Z {-mm(g.depth_from_top):.2f} .. {mm(g.shaft_proud_of_top):.2f}")
    print(f"\nservo mass to assign: {SERVOS[SERVO_KEY].mass * 1000:.1f} g")


if __name__ == "__main__":
    main()
