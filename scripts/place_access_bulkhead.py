"""Put the pass-through plate into Assembly 1, on the canard module's forward face.

Run:  python scripts/place_access_bulkhead.py [--place]

WHY. `make_access_bulkhead_cad.py` built it as a part, and a part that is not instanced
still cannot clash with anything -- the argument every bulkhead in this project has made.
This disc sits inside the airframe tube at the module's forward end, 2.4 mm of G-10 across a
74.8 mm bore, and `Assembly 1` is the one place this project runs an interference check.

ONLY THE PASS-THROUGH PLATE. The nose aft face closes a cavity that has never been
modelled; instancing it here would place it somewhere it is not, the same reasoning
`place_bulkhead.py` gives for leaving the internal bulkhead unassembled.

THE PLACEMENT IS ONE NUMBER AND IT IS ZERO. `make_access_bulkhead_cad.py`'s FRAME note is
the reason: this disc's origin is on its FORWARD face and it grows AFT into the module, the
mirror of the aft gas seal's convention -- so it needs no offset at all. Its origin coincides
with the module Part Studio's own Z = 0.000, read from the bounding box rather than typed,
exactly as `place_bulkhead.py` reads Z = 142.900 for the seal.

AFTER RUNNING THIS, CHECK INTERFERENCE IN THE BROWSER. Volume proves nothing about overlap;
`/interferencecheck` 404s on v10. This is the plate closest to the forward hinge bore and the
forwardmost servo -- if anything in this module clashes with a part built from a pure
dimension rather than measured clearance, this is where it would show up.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import access_bulkhead as ab
from design.configure import baseline, evaluate
from design.onshape import call, get, post

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ASM = f"/assemblies/d/{DOC}/w/{WS}/e/ff7e2e472d6694342f892f9c"
PART_STUDIO = "dfb730308a9933e911684b5c"
PLATE_ELEMENT_NAME = "Pass-through plate (G-10 2.4)"
AIRFRAME_GROUP = "Airframe (tube + servo bodies)"

# The assembly as place_bulkhead.py left it: 34 instances before it ran, +1 for the seal.
EXPECTED_INSTANCES_BEFORE = 35
EXPECTED_FEATURES = 9
MM = 1000.0


def root() -> dict:
    return get(f"{ASM}?includeMateFeatures=true")["rootAssembly"]


def module_forward_face() -> float:
    """Z of the canard module's forward face, in metres -- read, not typed."""
    bb = get(f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}/boundingboxes")
    if abs(bb["lowZ"]) > 1e-9:
        raise SystemExit(
            f"the module Part Studio no longer starts at Z=0 (lowZ {bb['lowZ'] * MM:.3f} mm) "
            f"-- the frame this placement assumes has moved; re-read make_access_bulkhead_cad.py")
    return bb["lowZ"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", action="store_true",
                    help="actually insert and transform (otherwise report only)")
    args = ap.parse_args()

    r = ab.pass_through_from_evaluation(evaluate(baseline()))
    fwd = module_forward_face()

    el = next((e for e in get(f"/documents/d/{DOC}/w/{WS}/elements")
               if e["name"] == PLATE_ELEMENT_NAME), None)
    if el is None:
        raise SystemExit(f"no '{PLATE_ELEMENT_NAME}' -- run make_access_bulkhead_cad.py first")
    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{el['id']}")
    if len(parts) != 1:
        raise SystemExit(f"expected one part in the plate studio, found {len(parts)}")
    part_id = parts[0]["partId"]

    print(f"pass-through plate  dia {r.bulkhead.bore_diameter * MM:.1f} x "
          f"{r.bulkhead.thickness * MM:.1f} mm G-10, {len(ab.hole_layout(r))} hole")
    print(f"module              forward face at Z = {fwd * MM:.3f} mm (read from the Part Studio)")

    a = root()
    already = [i for i in a["instances"] if i.get("elementId") == el["id"]]
    if already:
        print(f"\nalready placed: {len(already)} instance(s)")
        report(a, el["id"])
        return

    if len(a["instances"]) != EXPECTED_INSTANCES_BEFORE:
        raise SystemExit(f"{len(a['instances'])} instances, expected "
                         f"{EXPECTED_INSTANCES_BEFORE}; refusing to touch the assembly")

    if not args.place:
        print("\n--place not given; nothing written")
        return

    print("\ninserting 1 instance")
    before = {i["id"] for i in a["instances"]}
    post(f"{ASM}/instances", {
        "documentId": DOC, "workspaceId": WS, "elementId": el["id"],
        "partId": part_id, "isAssembly": False, "isWholePartStudio": False,
        "includePartTypes": ["PARTS"],
    })
    a = root()
    new = [i["id"] for i in a["instances"] if i["id"] not in before]
    if len(new) != 1:
        raise SystemExit(f"{len(new)} new instances appeared, expected 1")

    # Identity -- the disc's own origin already sits on the module's forward face.
    t = [1.0, 0.0, 0.0, 0.0,
         0.0, 1.0, 0.0, 0.0,
         0.0, 0.0, 1.0, fwd,
         0.0, 0.0, 0.0, 1.0]
    post(f"{ASM}/occurrencetransforms",
         {"occurrences": [{"path": [new[0]]}], "transform": t, "isRelative": False})
    print(f"  placed at Z = {fwd * MM:.3f} mm")

    add_to_airframe_group(new)
    report(root(), el["id"])


def add_to_airframe_group(ids: list[str]) -> None:
    fl = get(f"{ASM}/features")
    feats = fl.get("features", [])
    if len(feats) != EXPECTED_FEATURES:
        raise SystemExit(f"{len(feats)} assembly features, expected {EXPECTED_FEATURES}")
    g = next((f for f in feats if f.get("name") == AIRFRAME_GROUP), None)
    if g is None:
        raise SystemExit(f"no '{AIRFRAME_GROUP}' feature to extend")
    q = next(p for p in g["parameters"] if p["parameterId"] == "occurrencesQuery")
    for i in ids:
        q["queries"].append({"btType": "BTMIndividualOccurrenceQuery-626", "path": [i]})
    call("POST", f"{ASM}/features/featureid/{quote(g['featureId'], safe='')}",
         {"feature": g, "serializationVersion": fl.get("serializationVersion"),
          "sourceMicroversion": fl.get("sourceMicroversion"),
          "rejectMicroversionSkew": False})
    st = get(f"{ASM}/features")["featureStates"].get(g["featureId"], {}).get("featureStatus")
    print(f"  '{AIRFRAME_GROUP}' now holds {len(q['queries'])} occurrences: {st}")
    if st != "OK":
        raise SystemExit("the airframe group did not regenerate cleanly")


def report(a: dict, element: str) -> None:
    print(f"\n  instances now {len(a['instances'])}")
    inst = {i["id"]: i for i in a["instances"]}
    for o in a["occurrences"]:
        i = inst.get(o["path"][-1])
        if i and i.get("elementId") == element:
            t = o["transform"]
            print(f"  plate at X {t[3] * MM:+.3f}  Y {t[7] * MM:+.3f}  Z {t[11] * MM:+.3f} mm")
    print("\n  NOW RUN CHECK INTERFERENCE IN THE BROWSER. Volume proves nothing about")
    print("  overlap; /interferencecheck 404s on v10.")


if __name__ == "__main__":
    main()
