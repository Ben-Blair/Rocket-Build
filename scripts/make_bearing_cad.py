"""Build the canard hinge bearing as real geometry in Onshape, from design/hinge.py.

Run:  python scripts/make_bearing_cad.py [--rebuild]

WHY THIS EXISTS. The hinge stack put a bearing SEAT in the airframe wall in August 2026
and stopped there, so the model held a correctly-sized hole with nothing in it. (That seat
was first cut dia 7.975 and corrected to dia 8.000 H7 when this part was built, because
7.975 is not a reamer anyone sells -- the press interference comes from the bushing being
supplied 0.030 mm oversize, not from undersizing the hole. See design/hinge.py.)

An unmodelled bearing is not a cosmetic gap. This is the part that keeps the
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

Every dimension is imported from design.hinge.selected(). None is typed here. The part is
modelled at NOMINAL dia 8.000 OD -- the 0.030 mm supplied oversize is a fit allowance, not
geometry, and modelling it would make the bearing read as an interference against its own
seat in every clash check.

STATUS, Aug 2026: built. Part Studio "Hinge bearing (dia 6/8 x 6 plain)", one part, volume
131.947 mm^3 against the analytic annulus to within 0.001 mm^3 -- which is the proof the
bore actually cut, since a solid slug would read 301.593. Name and iglidur G material were
set through POST /metadata/.../p/{partId}, not by hand.

CAUTION: --rebuild CANNOT WORK with a read-only-flagged API key. It DELETEs the element
first, and DELETE /elements returns 403 "Invalid API key state" even though POST creates
elements happily. To rebuild, delete the Part Studio in the browser and re-run without the
flag.
"""

from __future__ import annotations

import math
import sys
from urllib.parse import quote
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
PART_NAME = "Hinge bearing (iglidur G, 6/8 x 6 plain)"

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


def bore_dia(s: hinge.HingeStack) -> float:
    """The bearing's BORE, which is the journal plus its running clearance -- not the
    journal diameter.

    Modelled at dia 6.000 originally, exactly equal to the shaft, which is the same defect
    this whole hinge exists to correct: the wall pass-through was dia 5.000 on dia 5.000
    for months and no interference check could ever report it, because zero clearance is
    not an interference. Onshape's assembly interference check DID flag this one, as four
    coincident cylinders -- but only because the surfaces were exactly coincident, which is
    luck, not a check. Carry the design's clearance.
    """
    return s.journal_dia + hinge.BEARING_RUNNING_CLEARANCE


def build(element: str, s: hinge.HingeStack) -> None:
    od, idia, length = s.bearing_od * MM, bore_dia(s) * MM, s.bearing_length * MM

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

    name_and_material(element)


# Onshape part metadata property ids. These are global constants, identical in every
# document -- they are not ids allocated to this part -- so they can be hard-coded.
PROP_NAME = "57f3fb8efa3416c06701d60d"
PROP_MATERIAL = "57f3fb8efa3416c06701d615"


def name_and_material(element: str) -> None:
    """Name the part and give it a density, as part of the BUILD.

    Not a printed instruction to go and do it by hand. A part with no material weighs
    0.0000 g and still answers every mass query with a number, which is how this document
    once reported 175 g for a 260 g module. Anything that has to be remembered after the
    script finishes will eventually not be.
    """
    part_id = get(f"/parts/d/{DOC}/w/{WS}/e/{element}")[0]["partId"]
    r = post(f"/metadata/d/{DOC}/w/{WS}/e/{element}/p/{part_id}", {
        "jsonType": "metadata-part",
        "properties": [
            {"propertyId": PROP_NAME, "value": PART_NAME},
            {"propertyId": PROP_MATERIAL, "value": {
                "id": "CustomMaterial", "displayName": "iglidur G", "libraryName": "",
                "properties": [{
                    "name": "DENS", "value": f"{IGLIDUR_G_DENSITY:.0f}", "type": "",
                    "displayName": "Density", "units": "kg/m^3",
                    "category": "", "description": ""}]}},
        ]})
    # NOTHING_TO_UPDATE is a SUCCESS, not a failure: it means the property already held
    # this exact value. Re-running the script must not look like a broken write. (Only the
    # name dedupes this way -- re-writing an identical material still reports SUCCEEDED,
    # so you cannot use the status to tell whether anything actually changed.)
    ok = {"SUCCEEDED", "NOTHING_TO_UPDATE"}
    failed = [q for q in r.get("properties", []) if q.get("status") not in ok]
    if r.get("status") not in ok or failed:
        raise SystemExit(f"metadata write did not take: {r}")
    print(f"  named '{PART_NAME}', iglidur G at {IGLIDUR_G_DENSITY:.0f} kg/m^3")


def correct_bore(element: str, s: hinge.HingeStack) -> bool:
    """Bring an already-built bearing's bore to the design size, in place.

    In place, because the element is referenced by four assembly instances and a rebuild
    would orphan every one of them -- Onshape heals an orphaned instance to an empty
    partId, so it keeps its name and transform and quietly weighs nothing. The bore is
    plain feature JSON (a sketch and an extrude), so it can simply be edited; only CUSTOM
    features are stuck, because a feature's Feature Studio namespace is immutable.
    """
    want = bore_dia(s)
    fl = get(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/features")
    sk = next(f for f in fl["features"]
              if f["name"] == "Bearing bore" and f["featureType"] == "newSketch")
    have = None
    for e in sk.get("entities", []):
        g = e.get("geometry", {})
        if g.get("btType") == "BTCurveGeometryCircle-115":
            have = g["radius"] * 2.0
    if have is not None and abs(have - want) < 1e-9:
        print(f"  bore is dia {have * MM:.3f}, which is what the design wants")
        return False
    print(f"  bore is dia {have * MM:.3f}, design wants dia {want * MM:.3f} -- CORRECTING")
    for e in sk.get("entities", []):
        g = e.get("geometry", {})
        if g.get("btType") == "BTCurveGeometryCircle-115":
            g["radius"] = want / 2.0
    for c in sk.get("constraints", []):
        if c.get("constraintType") == "DIAMETER":
            for q in c["parameters"]:
                if q.get("parameterId") == "length":
                    q["expression"] = f"{want * MM:.4f} mm"
    call("POST", f"/partstudios/d/{DOC}/w/{WS}/e/{element}"
                 f"/features/featureid/{quote(sk['featureId'], safe='')}",
         {"feature": sk, "serializationVersion": fl.get("serializationVersion"),
          "sourceMicroversion": fl.get("sourceMicroversion"),
          "rejectMicroversionSkew": False})
    st = get(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/features")["featureStates"] \
        .get(sk["featureId"], {}).get("featureStatus")
    if st != "OK":
        raise SystemExit(f"the bore sketch regenerated as {st}")
    return True


def main() -> None:
    s = stack()
    rebuild = "--rebuild" in sys.argv
    existing = find_element(ELEMENT_NAME)
    if existing and not rebuild:
        print(f"'{ELEMENT_NAME}' already exists ({existing['id']}).")
        if correct_bore(existing["id"], s):
            mp = get(f"/partstudios/d/{DOC}/w/{WS}/e/{existing['id']}/massproperties") \
                ["bodies"]["-all-"]
            want = math.pi * ((s.bearing_od / 2) ** 2 - (bore_dia(s) / 2) ** 2) \
                * s.bearing_length
            print(f"  volume now {mp['volume'][0] * 1e9:.3f} mm^3 against "
                  f"{want * 1e9:.3f} analytic")
            if abs(mp["volume"][0] - want) > 1e-12:
                raise SystemExit("volume does not match the annulus after the correction")
            print(f"  mass {mp['mass'][0] * 1000:.4f} g each")
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

    v = math.pi * ((s.bearing_od / 2) ** 2 - (bore_dia(s) / 2) ** 2) * s.bearing_length
    mp = get(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/massproperties")["bodies"]["-all-"]
    solid = math.pi * (s.bearing_od / 2) ** 2 * s.bearing_length
    print(f"\nvolume {mp['volume'][0] * 1e9:.3f} mm^3 against analytic {v * 1e9:.3f}; "
          f"a solid slug would be {solid * 1e9:.3f}")
    if abs(mp["volume"][0] - v) > 1e-12:
        raise SystemExit("volume does not match the annulus -- the bore did not cut.")
    print(f"mass {mp['mass'][0] * 1000:.4f} g each, "
          f"{mp['mass'][0] * 4000:.4f} g for four")
    print(f"\nIn the module assembly, place four of these with the origin on each hinge")
    print(f"axis at R {s.bearing_outboard * MM:.3f} mm, +Z radially outward. The bearing")
    print(f"then spans R {s.bearing_inboard * MM:.3f} -> {s.bearing_outboard * MM:.3f}, of which")
    print(f"{s.bearing_in_wall * MM:.3f} mm is inside the airframe wall and "
          f"{s.housing_collar_height * MM:.3f} mm needs the")
    print("housing collar off the printed bay, which is not built.")


if __name__ == "__main__":
    main()
