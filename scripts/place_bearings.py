"""Put the four hinge bearings into Assembly 1, on the hinge axes, in the airframe group.

Run:  python scripts/place_bearings.py [--place]

WHY. scripts/make_bearing_cad.py built the bearing as a part; until it is INSTANCED it
still cannot clash with anything, which was the entire argument for modelling it. 3.700 mm
of its 6.000 mm length stands proud of the tube ID and has to be caught by a housing collar
off the printed bay. That collar gets drawn next, and it has to be drawn against geometry
that is actually there.

HOW THE PLACEMENT IS DERIVED, and this is the part worth understanding: nothing here is a
typed coordinate. The servo part and the bearing part were deliberately built in the SAME
frame -- origin on the hinge axis, +Z radially outward (see the FRAME paragraph in
make_servo_cad.py and make_bearing_cad.py). So each bearing's placement is its servo's
placement, translated along that servo's own +Z by the radial gap between the two faces:

    servo output face   R 33.185   (hinge.servo_output_face)
    bearing outboard    R 39.700   (hinge.bearing_outboard, flush with the tube OD)
    -------------------------------------------------------
    translate                       +6.515 mm along local +Z

Both radii come from design/hinge.py, and the rotation is COPIED from the servo rather
than rebuilt from a quadrant angle. That matters: a quadrant angle is a second source of
truth for where the hinge axes are, and if the module is ever clocked, hand-written angles
go stale silently while a copied rotation does not.

The bearing is pressed into the tube wall and does NOT rotate with the panel, so it joins
the "Airframe (tube + servo bodies)" rigid group, not a canard rotating group. Adding it
to a rotating group would be a real error and not an obvious one -- the assembly would
still articulate, and the bearing would spin with the surface it is supposed to support.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import hinge
from design.configure import baseline, build_vehicle
from design.onshape import call, get, post
from design.packaging import SERVO_GEOMETRY

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ASM = f"/assemblies/d/{DOC}/w/{WS}/e/ff7e2e472d6694342f892f9c"

BEARING_ELEMENT = "Hinge bearing (dia 6/8 x 6 plain)"
AIRFRAME_GROUP = "Airframe (tube + servo bodies)"
SERVO_CASE = "Servo case + flange (KST X08 Plus)"
MM = 1000.0

# Guards. The assembly is hand-mated in one respect that cannot be scripted back (the four
# revolute hinges), so anything that finds it in an unexpected shape must stop rather than
# improvise. 21 instances and 9 features is the state after the servos and hinges went in.
EXPECTED_INSTANCES_BEFORE = 21
EXPECTED_FEATURES = 9


def stack() -> hinge.HingeStack:
    p = baseline()
    r = build_vehicle(p)
    return hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness,
                          SERVO_GEOMETRY[p.servo])


def bearing_part() -> tuple[str, str]:
    el = next((e for e in get(f"/documents/d/{DOC}/w/{WS}/elements")
               if e["name"] == BEARING_ELEMENT), None)
    if el is None:
        raise SystemExit(f"no '{BEARING_ELEMENT}' element; run make_bearing_cad.py first")
    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{el['id']}")
    if len(parts) != 1:
        raise SystemExit(f"expected exactly 1 part in '{BEARING_ELEMENT}', "
                         f"found {len(parts)}")
    return el["id"], parts[0]["partId"]


def root() -> dict:
    return get(ASM)["rootAssembly"]


def named_occurrences(a: dict, prefix: str) -> dict[str, dict]:
    """Top-level occurrences whose instance name starts with `prefix`, keyed by name."""
    names = {i["id"]: i["name"] for i in a["instances"]}
    out = {}
    for o in a["occurrences"]:
        if len(o["path"]) != 1:
            continue
        n = names.get(o["path"][0], "")
        if n.startswith(prefix):
            out[n] = o
    return out


def radial(t: list[float]) -> tuple[float, float, float]:
    """The local +Z axis of a 4x4 row-major transform, in assembly coordinates."""
    return t[2], t[6], t[10]


def place(dry: bool) -> None:
    s = stack()
    element, part_id = bearing_part()
    reach = s.bearing_outboard - s.servo_output_face
    print(f"bearing element {element}, part {part_id}")
    print(f"servo output face R {s.servo_output_face * MM:.3f} -> bearing outboard face "
          f"R {s.bearing_outboard * MM:.3f}: translate {reach * MM:+.3f} mm along local +Z")

    a = root()
    servos = named_occurrences(a, SERVO_CASE)
    if len(servos) != 4:
        raise SystemExit(f"found {len(servos)} servo cases, expected 4")

    existing = named_occurrences(a, "Hinge bearing")
    if existing:
        print(f"\n{len(existing)} bearing(s) already placed:")
        report(s)
        return

    if len(a["instances"]) != EXPECTED_INSTANCES_BEFORE:
        raise SystemExit(f"{len(a['instances'])} instances, expected "
                         f"{EXPECTED_INSTANCES_BEFORE}; refusing to touch the assembly")
    if dry:
        print("\n--place not given; nothing written")
        return

    print("\ninserting 4 instances")
    before = {i["id"] for i in a["instances"]}
    for _ in range(4):
        post(f"{ASM}/instances", {
            "documentId": DOC, "workspaceId": WS, "elementId": element,
            "partId": part_id, "isAssembly": False, "isWholePartStudio": False,
            "includePartTypes": ["PARTS"],
        })
    a = root()
    new = [i["id"] for i in a["instances"] if i["id"] not in before]
    if len(new) != 4:
        raise SystemExit(f"{len(new)} new instances appeared, expected 4")

    print("transforming each onto its servo's axis")
    for iid, (name, servo) in zip(new, sorted(servos.items())):
        t = list(servo["transform"])
        ux, uy, uz = radial(t)
        t[3] += ux * reach
        t[7] += uy * reach
        t[11] += uz * reach
        post(f"{ASM}/occurrencetransforms",
             {"occurrences": [{"path": [iid]}], "transform": t, "isRelative": False})
        print(f"  {name:44s} -> R {(t[3]**2 + t[7]**2) ** 0.5 * MM:.3f}")

    print(f"\nadding all four to '{AIRFRAME_GROUP}' (they are pressed in the wall and do "
          f"not rotate)")
    add_to_airframe_group(new)
    report(s)


def add_to_airframe_group(ids: list[str]) -> None:
    """Extend the airframe rigid group in place.

    Edited, not deleted and recreated. The assembly holds four hand-placed revolute mates
    that the API cannot author, and every wholesale 'clear and rebuild' of this assembly is
    one slip away from taking them with it.
    """
    fl = get(f"{ASM}/features")
    feats = fl.get("features", [])
    if len(feats) != EXPECTED_FEATURES:
        raise SystemExit(f"{len(feats)} assembly features, expected {EXPECTED_FEATURES}")
    g = next((f for f in feats if f.get("name") == AIRFRAME_GROUP), None)
    if g is None:
        raise SystemExit(f"no '{AIRFRAME_GROUP}' feature to extend")
    q = next(p for p in g["parameters"] if p["parameterId"] == "occurrencesQuery")
    have = {tuple(x["path"]) for x in q["queries"]}
    for i in ids:
        if (i,) not in have:
            q["queries"].append({"btType": "BTMIndividualOccurrenceQuery-626", "path": [i]})
    call("POST", f"{ASM}/features/featureid/{quote(g['featureId'], safe='')}",
         {"feature": g, "serializationVersion": fl.get("serializationVersion"),
          "sourceMicroversion": fl.get("sourceMicroversion"),
          "rejectMicroversionSkew": False})
    st = get(f"{ASM}/features")["featureStates"].get(g["featureId"], {}) \
        .get("featureStatus")
    print(f"  '{AIRFRAME_GROUP}' now holds {len(q['queries'])} occurrences: {st}")
    if st != "OK":
        raise SystemExit("the airframe group did not regenerate cleanly")


def report(s: hinge.HingeStack) -> None:
    a = root()
    bearings = named_occurrences(a, "Hinge bearing")
    print()
    ok = True
    for name, o in sorted(bearings.items()):
        t = o["transform"]
        r = (t[3] ** 2 + t[7] ** 2) ** 0.5
        ux, uy, _ = radial(t)
        # The +Z axis must point straight out along the radius, or the bearing is cocked
        # in its seat: a bore that is 0.020 mm off centre over 6 mm is 0.2 deg, and no
        # bounding box will ever show it.
        radial_err = abs(ux * t[7] - uy * t[3]) * MM
        bad = abs(r - s.bearing_outboard) * MM > 1e-3 or radial_err > 1e-3
        ok &= not bad
        print(f"  {name:34s} R {r * MM:8.3f}  Z {t[11] * MM:8.3f}  "
              f"axis offset {radial_err:6.4f} mm  {'FAIL' if bad else 'ok'}")
    # R alone cannot tell four bearings on four axes from four bearings stacked on one:
    # every one of them would read R 39.700. Check the quadrants are actually distinct.
    seen = {(round(o["transform"][3] * MM, 3), round(o["transform"][7] * MM, 3))
            for o in bearings.values()}
    print(f"  {len(seen)} distinct axis position(s): "
          f"{sorted(f'({x:+.1f},{y:+.1f})' for x, y in seen)}")
    if bearings and len(seen) != len(bearings):
        ok = False
        print("  FAIL: two or more bearings share an axis")

    fs = get(f"{ASM}/features")["featureStates"]
    bad_f = {k: v.get("featureStatus") for k, v in fs.items()
             if v.get("featureStatus") not in ("OK", "WARNING")}
    mp = get(f"{ASM}/massproperties")
    print(f"\n{len(a['instances'])} instances, "
          f"{len(get(f'{ASM}/features')['features'])} features, "
          f"{mp['mass'][0] * MM:.4f} g, CoM Z {mp['centroid'][2] * MM:.3f} mm")
    print(f"feature states not OK: {bad_f or 'none'}")
    print(f"\nexpected R {s.bearing_outboard * MM:.3f} (outboard face, flush with the tube "
          f"OD at {s.bearing_outboard * MM:.3f})")
    print(f"each bearing spans R {s.bearing_inboard * MM:.3f} -> "
          f"{s.bearing_outboard * MM:.3f}; {s.housing_collar_height * MM:.3f} mm of that "
          f"is inboard of the tube ID")
    print("and still needs the housing collar off the printed bay, which is not built.")
    if not ok:
        raise SystemExit("a bearing is not on its hinge axis")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", action="store_true",
                    help="actually insert and transform (otherwise report only)")
    place(dry=not ap.parse_args().place)


if __name__ == "__main__":
    main()
