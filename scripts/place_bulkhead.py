"""Put the aft gas seal into Assembly 1, on the canard module's aft face.

Run:  python scripts/place_bulkhead.py [--place]

WHY. `make_bulkhead_cad.py` built it as a part, and a part that is not instanced still
cannot clash with anything -- which was the whole argument for modelling it. This disc sits
inside the airframe tube at the module's aft end, 4.8 mm of G-10 across a 74.8 mm bore, and
`Assembly 1` is the one place in this project where Onshape's own interference check runs.

ONLY THE SEAL. The internal bulkhead is 240 mm further aft, in a recovery bay that has never
been modelled; instancing it here would place it somewhere it is not, and a part in the
wrong place is worse than a part that is missing because it looks finished.

THE PLACEMENT IS ONE NUMBER AND IT IS NOT TYPED. The disc was built with its origin on its
own aft face and +Z aft (see make_bulkhead_cad.py, FRAME), and Part Studio 1 runs from
Z = 0.000 at the module's forward face to Z = 142.900 at its aft face. So the seal's origin
goes to Z = 142.900 with no rotation at all -- identity plus a translation, and the number
is read from the Part Studio's bounding box rather than restated. `make_bay_cad.py` earns
its identity transform the same way.

IT JOINS THE AIRFRAME GROUP. The seal is bonded into the tube and does not rotate with any
panel. Putting it in a canard rotating group would still articulate and would still look
right, which is exactly why it is worth saying out loud.

AFTER RUNNING THIS, CHECK INTERFERENCE IN THE BROWSER. `/interferencecheck` 404s on v10 and
volume proves nothing about overlap -- an interference moves no volume and no mass. It is
the check that found the tang buried in the tube wall, the collar rim outside the shell and
the retainer bar inside the servo (correction 23).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import seal
from design.configure import baseline, evaluate
from design.onshape import call, get, post

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ASM = f"/assemblies/d/{DOC}/w/{WS}/e/ff7e2e472d6694342f892f9c"
PART_STUDIO = "dfb730308a9933e911684b5c"
SEAL_ELEMENT_NAME = "Aft gas seal (G-10 4.8)"
AIRFRAME_GROUP = "Airframe (tube + servo bodies)"

# The assembly as correction 23 left it. Refuse to touch anything else -- this assembly
# holds four hand-placed revolute mates the API cannot author, and every wholesale edit is
# one slip from taking them with it.
EXPECTED_INSTANCES_BEFORE = 34
EXPECTED_FEATURES = 9
MM = 1000.0


def root() -> dict:
    """The rootAssembly node. `instances` and `occurrences` both live inside it, not at the
    top level -- the top level carries rootAssembly / subAssemblies / parts."""
    return get(f"{ASM}?includeMateFeatures=true")["rootAssembly"]


def module_aft_face() -> float:
    """Z of the canard module's aft face, in metres, from the Part Studio's own bounds."""
    bb = get(f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}/boundingboxes")
    if abs(bb["lowZ"]) > 1e-9:
        raise SystemExit(
            f"the module Part Studio no longer starts at Z=0 (lowZ {bb['lowZ'] * MM:.3f} mm) "
            f"-- the frame this placement assumes has moved; re-read make_bulkhead_cad.py")
    return bb["highZ"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", action="store_true",
                    help="actually insert and transform (otherwise report only)")
    args = ap.parse_args()

    r = seal.from_evaluation(evaluate(baseline()))
    aft = module_aft_face()

    el = next((e for e in get(f"/documents/d/{DOC}/w/{WS}/elements")
               if e["name"] == SEAL_ELEMENT_NAME), None)
    if el is None:
        raise SystemExit(f"no '{SEAL_ELEMENT_NAME}' -- run make_bulkhead_cad.py first")
    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{el['id']}")
    if len(parts) != 1:
        raise SystemExit(f"expected one part in the seal studio, found {len(parts)}")
    part_id = parts[0]["partId"]

    print(f"seal        dia {r.bulkhead.bore_diameter * MM:.1f} x "
          f"{r.bulkhead.thickness * MM:.1f} mm G-10, "
          f"{len(seal.hole_layout(r))} holes")
    print(f"module      aft face at Z = {aft * MM:.3f} mm (read from the Part Studio)")

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

    # Identity rotation, translated to the aft face. Row-major 4x4, as Onshape wants it.
    t = [1.0, 0.0, 0.0, 0.0,
         0.0, 1.0, 0.0, 0.0,
         0.0, 0.0, 1.0, aft,
         0.0, 0.0, 0.0, 1.0]
    post(f"{ASM}/occurrencetransforms",
         {"occurrences": [{"path": [new[0]]}], "transform": t, "isRelative": False})
    print(f"  placed at Z = {aft * MM:.3f} mm")

    add_to_airframe_group(new)
    report(root(), el["id"])


def add_to_airframe_group(ids: list[str]) -> None:
    """Extend the airframe rigid group in place, never delete and recreate it."""
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
            print(f"  seal at X {t[3] * MM:+.3f}  Y {t[7] * MM:+.3f}  Z {t[11] * MM:+.3f} mm")
    print("\n  NOW RUN CHECK INTERFERENCE IN THE BROWSER. Volume proves nothing about")
    print("  overlap; /interferencecheck 404s on v10.")


if __name__ == "__main__":
    main()
