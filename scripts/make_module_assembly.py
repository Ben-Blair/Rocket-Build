"""Wire up Assembly 1 so the canard module actually articulates.

    python scripts/make_module_assembly.py --mates

Assembly 1 held the four real servos and the module parts in the right places, but nothing
was connected, so nothing could move. This adds:

  * a rigid group per canard -- panel + shaft + that servo's output spline, so the spline
    turns with the surface it drives, which is what a direct drive means;
  * a rigid group for everything that does not move -- tube, four servo cases, four cable
    bosses;
  * a REVOLUTE mate per canard on its own hinge axis, limited to the deflection limit.

The mate connectors come from the `Canard hinge mate connectors` feature in the Part
Studio (cad/canard_articulation.fs). They are built in PAIRS at identical coordinate
systems, differing only in which body owns them, so mating moves nothing: the assembly
stays exactly where the Part Studio put it and gains one degree of freedom per canard.

That pairing is the whole trick. Mate connectors placed by picking geometry land on the
centroids of whatever was picked, which for a shaft and the hole it passes through are
3.75 mm apart along the axis -- and a revolute mate closes that gap by MOVING the part.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from urllib.parse import quote

from design.onshape import call, get, post

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ASSEMBLY = "ff7e2e472d6694342f892f9c"

DEFLECTION_LIMIT_DEG = 8.0
QUADRANT_LABEL = {0: "0 (+X)", 1: "1 (+Y)", 2: "2 (-X)", 3: "3 (-Y)"}


def instances() -> dict[str, list[str]]:
    a = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}")
    out: dict[str, list[str]] = {}
    for i in a["rootAssembly"]["instances"]:
        out.setdefault(i["name"].rsplit("<", 1)[0].strip(), []).append(i["id"])
    return out


def hinge_connector_ids() -> dict[str, str]:
    """Map 'tube0'/'shaft0'/... to the full mate connector feature id."""
    a = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}", includeMateFeatures="true",
            includeMateConnectors="true", includeNonSolids="false")
    found = {}
    for part in a.get("parts", []):
        for mc in part.get("mateConnectors") or []:
            fid = mc["featureId"]
            if "." in fid:
                found[fid.split(".", 1)[1]] = fid
    return found


def clear_features() -> None:
    for f in get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/features").get("features", []):
        call("DELETE", f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}"
                       f"/features/featureid/{quote(f['featureId'], safe='')}")


def add(feature: dict, label: str) -> str:
    fid = post(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/features",
               {"feature": feature})["feature"]["featureId"]
    status = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/features") \
        ["featureStates"].get(fid, {}).get("featureStatus")
    print(f"  {label:38s} {status}")
    if status != "OK":
        raise SystemExit(f"'{label}' regenerated as {status} -- stopping before the "
                         f"assembly is left half-mated.")
    return fid


def group(name: str, ids: list[str]) -> str:
    return add({
        "btType": "BTMMateGroup-65", "featureType": "mateGroup", "name": name,
        "parameters": [{
            "btType": "BTMParameterQueryWithOccurrenceList-67",
            "parameterId": "occurrencesQuery",
            "queries": [{"btType": "BTMIndividualOccurrenceQuery-626", "path": [i]}
                        for i in ids]}],
    }, name)


def revolute(name: str, a_path: list[str], a_fid: str,
             b_path: list[str], b_fid: str, limit_deg: float) -> str:
    return add({
        "btType": "BTMMate-64", "featureType": "mate", "name": name,
        "parameters": [
            {"btType": "BTMParameterEnum-145", "enumName": "Mate type",
             "value": "REVOLUTE", "parameterId": "mateType"},
            {"btType": "BTMParameterQueryWithOccurrenceList-67",
             "parameterId": "mateConnectorsQuery",
             "queries": [
                 {"btType": "BTMFeatureQueryWithOccurrence-157",
                  "path": a_path, "featureId": a_fid, "queryData": ""},
                 {"btType": "BTMFeatureQueryWithOccurrence-157",
                  "path": b_path, "featureId": b_fid, "queryData": ""}]},
            {"btType": "BTMParameterBoolean-144", "parameterId": "limitsEnabled",
             "value": True},
            {"btType": "BTMParameterNullableQuantity-807", "parameterId": "limitAxialZMin",
             "isNull": False, "expression": f"-{limit_deg} deg"},
            {"btType": "BTMParameterNullableQuantity-807", "parameterId": "limitAxialZMax",
             "isNull": False, "expression": f"{limit_deg} deg"},
        ],
    }, name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mates", action="store_true",
                    help="rebuild the groups and hinge mates")
    ap.add_argument("--limit", type=float, default=DEFLECTION_LIMIT_DEG)
    args = ap.parse_args()
    if not args.mates:
        print(__doc__)
        return

    inst = instances()
    mcs = hinge_connector_ids()
    missing = [k for k in
               [f"{w}{q}" for q in range(4) for w in ("tube", "shaft")] if k not in mcs]
    if missing:
        raise SystemExit(f"Missing hinge mate connectors: {missing}. Add the "
                         f"'Canard hinge mate connectors' feature to the Part Studio first.")

    tube = inst["Canard module tube"][0]
    cases = inst["Servo case + flange (KST X08 Plus)"]
    bosses = inst["Servo lower boss (keep-out)"]
    splines = inst["Servo output spline (15T, 4 mm)"]

    print("clearing existing assembly features")
    clear_features()

    print("\ngroups")
    group("Airframe (tube + servo bodies)", [tube] + cases + bosses)
    for q in range(4):
        label = QUADRANT_LABEL[q]
        group(f"Canard {label} rotating group",
              [inst[f"Canard panel {label}"][0],
               inst[f"Canard shaft {label}"][0],
               splines[q]])

    print(f"\nhinges, limited to +/-{args.limit:g} deg")
    for q in range(4):
        shaft = inst[f"Canard shaft {QUADRANT_LABEL[q]}"][0]
        revolute(f"Canard {QUADRANT_LABEL[q]} hinge",
                 [tube], mcs[f"tube{q}"], [shaft], mcs[f"shaft{q}"], args.limit)

    a = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}")
    moved = [o for o in a["rootAssembly"]["occurrences"]
             if abs(o["transform"][11]) > 1e-9 and o["transform"][:3] == [1.0, 0.0, 0.0]]
    print(f"\ndone. {len(a['rootAssembly']['instances'])} instances, "
          f"{len(get(f'/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/features')['features'])} "
          f"assembly features.")


if __name__ == "__main__":
    main()
