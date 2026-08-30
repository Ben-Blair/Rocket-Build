"""Build the canard hinge bearing as real geometry in Onshape, from design/hinge.py.

Run:  python scripts/make_bearing_cad.py [--rebuild]

WHY THIS EXISTS. The hinge stack put a dia 7.975 bearing SEAT in the airframe wall in
August 2026 and stopped there, so the model has held a correctly-sized hole with nothing
in it ever since. That is not a cosmetic gap. The bearing is the part that keeps the
panel's 0.734 N m of bending out of the servo's output shaft -- it is the whole reason the
servo moved 4 mm inboard and the shaft became a sleeve -- and a part that is not modelled
cannot collide with anything. This Part Studio has already hidden one hard clash for weeks
because the servo was a bounding box (docs/01, correction 11); a bearing that exists only
as a dimension is the same trap one part further out.

It matters right now for a specific reason: 3.700 mm of this bearing's 6.000 mm length
sits INBOARD of the tube ID and has to be carried by a housing collar off the printed bay,
which does not exist yet. When that bay is drawn, the collar has to be checked against the
bearing -- and that check needs both of them to be geometry.

FRAME, chosen to make mating trivial and to match scripts/make_servo_cad.py: the origin is
ON THE HINGE AXIS, on the bearing's OUTBOARD face, and +Z points radially outward. That
face is flush with the tube OD, so in the module assembly the bearing's origin lands at
R 39.700 exactly -- a number that can be read off the status bar and checked, rather than
an offset that has to be computed.

Every dimension is imported from design.hinge.selected(). None is typed here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import hinge
from design import onshape_build as ob
from design.configure import baseline, build_vehicle
from design.onshape import call, get, post
from design.packaging import SERVO_GEOMETRY

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ELEMENT_NAME = "Hinge bearing (dia 6/8 x 6 plain)"

# igus iglidur G, the class the 80 MPa allowable in design/materials.py is taken from.
# Quoted 1.45 g/cm^3. The bearing is 0.19 g, so this changes nothing in the mass budget --
# it is here so the part carries a material rather than the zero-density default, which is
# how this Part Studio once read 0.175 kg instead of 0.260.
IGLIDUR_G_DENSITY = 1450.0

MM = 1000.0


def stack() -> hinge.HingeStack:
    p = baseline()
    r = build_vehicle(p)
    return hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness,
                          SERVO_GEOMETRY[p.servo])


def find_element(name: str):
    for e in get(f"/documents/d/{DOC}/w/{WS}/elements"):
        if e["name"] == name:
            return e
    return None


def add(feature: dict, element: str) -> str:
    r = post(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/features", {"feature": feature})
    return r["feature"]["featureId"]


def build(element: str, s: hinge.HingeStack) -> None:
    od, idia, length = s.bearing_od * MM, s.journal_dia * MM, s.bearing_length * MM

    # 1. The outer cylinder, growing INBOARD from the origin, so +Z is outward radial.
    sk = add(ob.sketch("Bearing OD", "Top",
                       [ob.circle(0.0, 0.0, od / 2000.0, "od")]), element)
    add(ob.extrude("Bearing body", [ob.sketch_regions(sk)],
                   depth_mm=length, opposite=True), element)

    # 2. The bore, as a SEPARATE cut rather than a second region in the same sketch.
    #    Two concentric circles in one sketch give two regions -- the disc and the annulus
    #    -- and which of them an extrude takes depends on a filter flag that is easy to get
    #    wrong and impossible to see afterwards. A cut is unambiguous. It overshoots both
    #    faces by 1 mm, because a REMOVE that lands exactly on a face is degenerate: this
    #    Part Studio's `Extrude 4` cut nothing at all for precisely that reason.
    over = 1.0
    sk = add(ob.sketch("Bearing bore", "Top",
                       [ob.circle(0.0, 0.0, idia / 2000.0, "bore")]), element)
    add(ob.extrude("Bearing bore", [ob.sketch_regions(sk)],
                   depth_mm=length + 2 * over, opposite=True,
                   start_offset_mm=over, start_offset_opposite=False,
                   operation="REMOVE"), element)


def main() -> None:
    s = stack()
    rebuild = "--rebuild" in sys.argv
    existing = find_element(ELEMENT_NAME)
    if existing and not rebuild:
        print(f"'{ELEMENT_NAME}' already exists ({existing['id']}). "
              f"Pass --rebuild to delete and regenerate it.")
        return
    if existing:
        call("DELETE", f"/elements/d/{DOC}/w/{WS}/e/{existing['id']}")
        print(f"deleted existing '{ELEMENT_NAME}'")

    el = post(f"/partstudios/d/{DOC}/w/{WS}", {"name": ELEMENT_NAME})
    element = el["id"]
    print(f"created part studio '{ELEMENT_NAME}' -> {element}")
    build(element, s)

    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{element}")
    print(f"\n{len(parts)} part(s):")
    for p in parts:
        print(f"  {p['partId']:4s} {p['name']}")
    bb = get(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/boundingboxes")
    print("\nbounding box, mm:")
    for k in ("lowX", "highX", "lowY", "highY", "lowZ", "highZ"):
        print(f"  {k:6s} {bb[k] * MM:8.3f}")
    print(f"\nexpected: X and Y +/-{s.bearing_od * MM / 2:.3f}, "
          f"Z {-s.bearing_length * MM:.3f} .. 0.000")

    import math
    v = math.pi * ((s.bearing_od / 2) ** 2 - (s.journal_dia / 2) ** 2) * s.bearing_length
    print(f"\nvolume should be {v * 1e9:.3f} mm^3; assign iglidur G at "
          f"{IGLIDUR_G_DENSITY:.0f} kg/m^3 -> {v * IGLIDUR_G_DENSITY * 1000:.3f} g each")
    print(f"\nIn the module assembly, place four of these with the origin on each hinge")
    print(f"axis at R {s.bearing_outboard * MM:.3f} mm, +Z radially outward. The bearing")
    print(f"then spans R {s.bearing_inboard * MM:.3f} -> {s.bearing_outboard * MM:.3f}, of which")
    print(f"{s.bearing_in_wall * MM:.3f} mm is inside the airframe wall and "
          f"{s.housing_collar_height * MM:.3f} mm needs the")
    print("housing collar off the printed bay, which is not built.")


if __name__ == "__main__":
    main()
