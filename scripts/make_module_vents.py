"""Drill the canard module's two overboard vents in Onshape.

    python scripts/make_module_vents.py --check    # read the model, change nothing
    python scripts/make_module_vents.py --build    # create the plane, sketch and cut

The design is in `design/venting.py` (MODULE_VENT_STATION, MODULE_VENT_DIAMETER,
MODULE_VENT_CLOCKING_DEG) and the argument for it is in docs/05 "The vent path". This
script only applies it, and it types no dimension of its own -- every number comes from
that module, so the CAD cannot drift from the analysis that justified it.

WHY A MID-PLANE AND NOT AN ANGLED ONE. The two vents are radial holes at 45 and 225
degrees, which needs a sketch plane that CONTAINS the rocket axis and is rotated 45
degrees from Right. The obvious route -- a `cPlane` of type OFFSET with `angle` set -- does
not work and does not complain: the plane regenerates with featureStatus OK and its normal
comes back unchanged at (1, 0, 0). That was established by creating one and reading its
normal back through `/featurescript` rather than by looking at it, which is the only reason
it was caught before a hole went in at the wrong clocking.

What does work needs no angle at all. The MID_PLANE of the Front and Right default planes
is their bisector, so it contains their intersection line -- which IS the rocket axis --
and its normal comes back (-0.707, -0.707, 0). One feature, two default planes, no
construction line and no custom FeatureScript.

AND ONE CUT MAKES BOTH HOLES. The cut is SYMMETRIC and THROUGH_ALL, so it opens the wall on
both sides of that plane at once: 45 and 225 degrees, opposed by construction rather than
by a pattern that could be given the wrong count. The wall bore next door needs its
four-instance circular pattern because 0/90/180/270 is not two opposed holes; this does
not.

SAFETY. Same rules as `make_hinge_stack.py`, and for the same reason -- docs/05 records a
circular pattern in this Part Studio that silently dropped material assignments, and a
feature that regenerated to an EMPTY Part Studio while still reporting OK. Every write is
followed by a part count, a feature-status sweep and a mass check, and anything unexpected
deletes what this script created.

The mass check is WEAK here and that is stated rather than relied on: two dia 2 mm holes
through a 2.3 mm wall remove about 0.05 g, which is well inside the 3 g guard that protects
against the dropped-material failure. So the real verification is geometric --
`verify_holes()` reads the cylindrical faces back out of the model and checks the count,
the diameter, the station and the clocking. A mass delta this small proves nothing except
that the model did not fall over.
"""

from __future__ import annotations

import argparse
import copy
import math
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import venting
from design.onshape import call, get, post

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
PART_STUDIO = "dfb730308a9933e911684b5c"

PS = f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}"
MM = 1000.0

EXPECTED_PARTS = 13
# Part Studio 1 total before the vents. See make_hinge_stack.py for the history of this
# number and for why a FALL of any size is the thing to be suspicious of.
MASS_BEFORE_G = 260.3850
MASS_TOLERANCE_G = 3.0

# Deterministic ids of the two default planes, read off the sketches that already use them:
# Sketch 2 sits on Front, Sketch 3 and Sketch 4 sit on Right.
FRONT_PLANE = "JCC"
RIGHT_PLANE = "JEC"

PLANE_NAME = "Module vent plane (45 deg)"
SKETCH_NAME = f"Module vent sketch (2 x dia {venting.MODULE_VENT_DIAMETER * MM:.1f})"
CUT_NAME = "Module vents"

TUBE = "Canard module tube"


# ------------------------------------------------------------------------------------
# reading
# ------------------------------------------------------------------------------------

def feature_list() -> dict:
    return get(f"{PS}/features")


def by_name(fl: dict, name: str) -> dict:
    for f in fl["features"]:
        if f.get("name") == name:
            return f
    raise SystemExit(f"no feature named {name!r} in the Part Studio")


def param(feature: dict, pid: str) -> dict:
    for p in feature["parameters"]:
        if p.get("parameterId") == pid:
            return p
    raise SystemExit(f"{feature.get('name')} has no parameter {pid!r}")


def parts() -> list[dict]:
    return get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}")


def part_mass_g(part_id: str) -> float:
    mp = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}/partid/{part_id}/massproperties")
    return mp["bodies"][part_id]["mass"][0] * 1000.0


def total_mass_g() -> float:
    return sum(part_mass_g(p["partId"]) for p in parts())


def tube_part() -> dict:
    return [p for p in parts() if p["name"] == TUBE][0]


# The vent holes are the only dia 2 mm cylindrical faces in the Part Studio. Read their
# axis back out rather than trusting that the sketch landed where it was told to: the
# sketch's own coordinate frame on a derived plane is exactly the kind of thing that agrees
# with itself and disagrees with the model.
_HOLE_SCRIPT = """
function(context is Context, queries) {
    var out = [];
    for (var f in evaluateQuery(context, qEverything(EntityType.FACE))) {
        var surf = evSurfaceDefinition(context, {"face": f});
        if (surf is Cylinder) {
            var r = surf.radius / millimeter;
            if (abs(r - RADIUS_MM) < 0.001) {
                var o = surf.coordSystem.origin;
                var d = surf.coordSystem.zAxis;
                out = append(out, toString(round(o[2] / millimeter * 1000) / 1000) ~ "|"
                                ~ toString(round(d[0] * 10000) / 10000) ~ "|"
                                ~ toString(round(d[1] * 10000) / 10000) ~ "|"
                                ~ toString(round(d[2] * 10000) / 10000));
            }
        }
    }
    return out;
}
"""


def hole_faces() -> list[tuple[float, float, float, float]]:
    """(z_mm, dx, dy, dz) for every cylindrical face at the vent radius."""
    script = _HOLE_SCRIPT.replace(
        "RADIUS_MM", f"{venting.MODULE_VENT_DIAMETER / 2.0 * MM:.4f}")
    r = post(f"{PS}/featurescript", {"script": script})
    out = []
    for v in r["result"]["value"]:
        s = v["value"] if isinstance(v, dict) else str(v)
        z, dx, dy, dz = (float(x) for x in s.split("|"))
        out.append((z, dx, dy, dz))
    return out


def verify(what: str) -> None:
    """Part count, every feature's status, and the mass. In that order, because an empty
    Part Studio still answers the mass question with a number."""
    fl = feature_list()
    bad = {fid: st.get("featureStatus")
           for fid, st in fl["featureStates"].items()
           if st.get("featureStatus") not in ("OK", "WARNING")}
    p = parts()
    if bad:
        raise RuntimeError(f"{what}: features not OK: {bad}")
    if len(p) != EXPECTED_PARTS:
        raise RuntimeError(f"{what}: {len(p)} parts, expected {EXPECTED_PARTS}")
    m = total_mass_g()
    if abs(m - MASS_BEFORE_G) > MASS_TOLERANCE_G:
        raise RuntimeError(
            f"{what}: Part Studio mass {m:.3f} g against {MASS_BEFORE_G:.3f} g before "
            f"(tolerance {MASS_TOLERANCE_G} g). A large FALL means the circular pattern "
            f"dropped its material assignments again -- see docs/05.")
    print(f"    verified after {what}: {len(p)} parts, all features OK, {m:.3f} g")


def verify_holes() -> None:
    """The check that actually proves the vents are where the design says.

    Diameter, count, station and clocking, all read back from the model. The clocking is
    the one a person cannot eyeball on a round tube and the one that matters -- a vent at
    0 degrees sits directly behind a canard panel.
    """
    want_z = venting.MODULE_VENT_STATION * MM
    want_clock = sorted(venting.MODULE_VENT_CLOCKING_DEG)
    faces = hole_faces()
    if len(faces) != venting.MODULE_VENT_COUNT:
        raise RuntimeError(
            f"found {len(faces)} vent-diameter cylindrical faces, expected "
            f"{venting.MODULE_VENT_COUNT}. A symmetric through-all cut makes exactly two")

    got_clock = []
    for z, dx, dy, dz in faces:
        if abs(z - want_z) > 0.001:
            raise RuntimeError(f"vent at Z {z:.3f} mm, design says {want_z:.3f}")
        if abs(dz) > 1e-6:
            raise RuntimeError(
                f"vent axis has a Z component ({dz:.4f}) -- it is not radial, so the "
                f"sketch plane is not the one this script thinks it is")
        got_clock.append(math.degrees(math.atan2(dy, dx)) % 180.0)

    # Both faces share one axis, so both report the same line mod 180 degrees. Compare on
    # that rather than pretending the two holes have distinguishable directions.
    want_mod = sorted({c % 180.0 for c in want_clock})
    got_mod = sorted(set(round(c, 3) for c in got_clock))
    if len(got_mod) != 1 or abs(got_mod[0] - want_mod[0]) > 0.01:
        raise RuntimeError(
            f"vent clocking reads {got_mod} deg (mod 180), design says {want_mod}")
    print(f"    holes verified: {len(faces)} x dia "
          f"{venting.MODULE_VENT_DIAMETER * MM:.1f} mm at Z {want_z:.1f} mm, "
          f"{'/'.join(f'{a:.0f}' for a in want_clock)} deg, axes radial")


# ------------------------------------------------------------------------------------
# writing
# ------------------------------------------------------------------------------------

def create_feature(feature: dict, label: str) -> str:
    fl = feature_list()
    f = copy.deepcopy(feature)
    f.pop("featureId", None)
    r = post(f"{PS}/features",
             {"feature": f,
              "serializationVersion": fl.get("serializationVersion"),
              "sourceMicroversion": fl.get("sourceMicroversion"),
              "rejectMicroversionSkew": False})
    fid = r["feature"]["featureId"]
    print(f"    created {label}  ({fid})")
    return fid


def delete_feature(fid: str) -> None:
    call("DELETE", f"{PS}/features/featureid/{quote(fid, safe='')}")


def plane_query(did: str) -> list[dict]:
    return [{"btType": "BTMIndividualQuery-138", "queryStatement": None,
             "queryString": f'query=qCreatedBy(makeId("{did}"), EntityType.FACE);',
             "deterministicIds": [did]}]


def existing(fl: dict) -> list[dict]:
    names = (PLANE_NAME, SKETCH_NAME, CUT_NAME)
    return [f for f in fl["features"] if f.get("name") in names]


def report() -> None:
    fl = feature_list()
    have = existing(fl)
    print("\ncanard module vents")
    print(f"  design              {venting.MODULE_VENT_COUNT} x dia "
          f"{venting.MODULE_VENT_DIAMETER * MM:.1f} mm at Z "
          f"{venting.MODULE_VENT_STATION * MM:.1f} mm, "
          f"{'/'.join(f'{a:.0f}' for a in venting.MODULE_VENT_CLOCKING_DEG)} deg")
    if not have:
        print("  in the CAD          NOT PRESENT -- run with --build")
        return
    print(f"  in the CAD          {', '.join(f['name'] for f in have)}")
    verify_holes()
    print(f"  tube                {part_mass_g(tube_part()['partId']):.4f} g")


def build() -> None:
    fl = feature_list()
    if existing(fl):
        print("\ncanard module vents: already present, nothing to do")
        report()
        return

    print("\ncanard module vents")
    before_tube = part_mass_g(tube_part()["partId"])
    made: list[str] = []
    try:
        # 1. the 45 degree plane, as the bisector of Front and Right
        pl = copy.deepcopy(by_name(fl, "Hinge Plane"))
        pl["name"] = PLANE_NAME
        param(pl, "cplaneType")["value"] = "MID_PLANE"
        param(pl, "entities")["queries"] = (plane_query(FRONT_PLANE)
                                            + plane_query(RIGHT_PLANE))
        made.append(create_feature(pl, PLANE_NAME))

        # 2. one circle, on that plane, at the vent station
        sk = copy.deepcopy(by_name(fl, "Sketch 3"))
        sk["name"] = SKETCH_NAME
        param(sk, "sketchPlane")["queries"] = [{
            "btType": "BTMIndividualQuery-138", "queryStatement": None,
            "queryString": f'query = qCreatedBy(id + "{made[0]}", EntityType.FACE);',
            "deterministicIds": [],
        }]
        radius = venting.MODULE_VENT_DIAMETER / 2.0
        # BOTH the constraints and the geometry, and the station one is the trap. Sketch 3
        # pins its circle with a DISTANCE constraint (68.27 mm, the hinge station) and a
        # VERTICAL constraint holding the centre on the plane's vertical axis. Setting only
        # `yCenter` produced a hole that regenerated OK, passed the part count and passed
        # the mass guard, and sat at Z 68.270 -- the constraint simply solved the geometry
        # back. It was verify_holes() that caught it. The VERTICAL constraint is left alone
        # on purpose: it is what keeps the hole radial.
        for c in sk.get("constraints", []):
            kind = c.get("constraintType")
            if kind not in ("DIAMETER", "DISTANCE"):
                continue
            want = (venting.MODULE_VENT_DIAMETER if kind == "DIAMETER"
                    else venting.MODULE_VENT_STATION)
            for q in c["parameters"]:
                if q.get("parameterId") == "length":
                    q["expression"] = f"{want * MM:.4f} mm"
        for e in sk.get("entities", []):
            g = e.get("geometry", {})
            if g.get("btType") == "BTCurveGeometryCircle-115":
                g["radius"] = radius
                g["xCenter"] = 0.0
                g["yCenter"] = venting.MODULE_VENT_STATION
        made.append(create_feature(sk, SKETCH_NAME))

        # 3. one cut, symmetric and through all, which opens both sides at once
        cut = copy.deepcopy(by_name(fl, "Wall bore (bearing seat)"))
        cut["name"] = CUT_NAME
        param(cut, "entities")["queries"] = [{
            "btType": "BTMIndividualSketchRegionQuery-140",
            "featureId": made[1],
            "queryString": f'query = qSketchRegion(id + "{made[1]}", true);',
            "filterInnerLoops": True,
            "queryStatement": None,
        }]
        param(cut, "endBound")["value"] = "THROUGH_ALL"
        param(cut, "symmetric")["value"] = True
        param(cut, "startOffset")["value"] = False
        made.append(create_feature(cut, CUT_NAME))

        verify("module vents")
        verify_holes()
    except Exception:
        print("    FAILED -- deleting what was created")
        for fid in reversed(made):
            try:
                delete_feature(fid)
            except Exception as e:  # noqa: BLE001
                print(f"    could not delete {fid}: {e}")
        raise

    after_tube = part_mass_g(tube_part()["partId"])
    print(f"    tube {before_tube:.4f} -> {after_tube:.4f} g "
          f"({(after_tube - before_tube) * 1000:+.1f} mg for two vents)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="read the model, change nothing")
    ap.add_argument("--build", action="store_true", help="create the plane, sketch and cut")
    a = ap.parse_args()
    if a.build:
        build()
    else:
        report()


if __name__ == "__main__":
    main()
