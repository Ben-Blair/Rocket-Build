"""Make the four canard hinge mates in `Assembly 1` actually turn.

WHY THIS EXISTS
---------------
`Assembly 1` is supposed to be a mechanism: four REVOLUTE mates, `Canard 0 (+X) hinge` ...
`Canard 3 (-Y) hinge`, each pairing `tube{n}` with `shaft{n}`, each limited to the +-8 deg
deflection limit.  They were authored in the browser, because the assembly-feature API will
not create a mate (docs/05).

They did not turn.  Onshape's DOF animation refused every one of them with

    Unable to compute any steps for this animation.
    Unable to apply transform.  Instance(s) may be constrained.

and nothing in the assembly explained it.  All 36 instances are in exactly one rigid group
each and the groups do not overlap; only `Canard module tube <1>` is fixed, which is correct
-- it is ground; every feature regenerates OK; the mate connectors resolve to the right two
parts (`FNZEnKHRI9Yncer_5.tube0` and `.shaft0`, from `canardHingeConnectors`).  The mate was
not over-constrained and the mechanism was not wrong.

THE CAUSE: `limitsEnabled`.  On these mates, a limit does not clamp the rotation, it
abolishes it.  Measured on `Canard 0 (+X) hinge` by driving the mate through
`POST /matevalues` after each edit, and confirmed in the browser with the animation itself:

    limits OFF                        -> asked +5 deg, got +5.000   turns; animation plays
    limits ON, limitAxialZ  -8 ..   8 -> asked +5 deg, got  0.000   FROZEN; the error above
    limits ON, limitAxialZ -60 ..  60 -> asked +5 deg, got  0.000   FROZEN
    limits ON, limitAxialZ -179 .. 179-> asked +5 deg, got  0.000   FROZEN
    limits ON, limitAxialZ -360 .. 360-> asked +90 deg, got 0.000   FROZEN
    limits ON, limitAxialZ  80 .. 100 -> asked +90 deg, got 0.000   FROZEN

So it is not the WIDTH of the limit and not a pose sitting outside it: a limit generous
enough to allow a full revolution freezes the hinge exactly as hard as +-8 deg does.  It is
not the rigid groups either -- suppressing `Canard 0 (+X) rotating group` and retrying
changes nothing.  It is the presence of `limitsEnabled = true` on a mate whose connectors
come from a Part Studio (`BTMPartStudioMateConnectorQuery`), and it applies to all four.

`limitAxialZMin/Max` is what Onshape's own Edit-mate dialog reads and writes for a
revolute's rotation limits -- open the dialog and the numbers it shows are that pair -- so
the browser did nothing wrong when the mates were authored.  The other Z pair,
`limitZMin/Max`, is drivable with limits enabled but enforces NOTHING (driven to +12 deg
against a +-8 deg limit without complaint), so writing the deflection limit there would
leave the dialog's Limits box ticked over a limit that does not exist.  This project has
enough of those already.  We do not do that.

THE FIX, therefore: turn the mate limits OFF and keep the deflection limit where it is
actually enforced -- `DEFLECTION_LIMIT_DEG` in `design/configure.py`, which is what every
analysis reads, and `scripts/canard_sweep.py`, which drives the Part Studio's own
`deflection` parameter and checks clearances at the limit.  The mate limits were never load
bearing: no script has ever read them, and the sweep does not go through the assembly mates
at all.  What is lost is a hand-drag guard in the browser.  What is gained is a mechanism
that moves, which is the thing the assembly exists to demonstrate.

    python scripts/fix_hinge_mate_limits.py            # report only
    python scripts/fix_hinge_mate_limits.py --apply    # disable the mate limits
    python scripts/fix_hinge_mate_limits.py --verify   # drive every hinge, park it at zero

TWO API FACTS WORTH THE LINE THEY TAKE
--------------------------------------
* An assembly feature id can contain a `/` (`MwVg60P6xoYjGb/Tu` here), so it MUST be
  percent-encoded into the `/features/featureid/{fid}` path or the call 404s while looking
  exactly like a missing feature.
* A limit parameter that is UNSET reads back from `GET /features` as a non-null zero, so the
  obvious round trip -- read a mate, change one thing, post it back -- rewrites every unset
  limit as a hard value.  Anything that edits a mate through the API should set the
  parameters it means and null the rest, which is what `without_limits()` does.
"""

from __future__ import annotations

import argparse
import copy
import math
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design.configure import DEFLECTION_LIMIT_DEG
from design.onshape import call, get

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ASM = f"/assemblies/d/{DOC}/w/{WS}/e/ff7e2e472d6694342f892f9c"

HINGES = ("Canard 0 (+X) hinge", "Canard 1 (+Y) hinge",
          "Canard 2 (-X) hinge", "Canard 3 (-Y) hinge")


def features() -> dict:
    return get(ASM + "/features")


def mate_values() -> dict[str, float]:
    return {m["mateName"]: math.degrees(m.get("rotationZ", 0.0))
            for m in get(ASM + "/matevalues")["mateValues"]}


def drive(feature_id: str, name: str, deg: float) -> float:
    call("POST", ASM + "/matevalues", body={"mateValues": [{
        "jsonType": "Revolute", "rotationZ": math.radians(deg),
        "featureId": feature_id, "mateName": name, "ownerOccurrencePath": [],
    }]})
    return mate_values()[name]


def mass_and_com() -> tuple[float, float]:
    m = get(ASM + "/massproperties")
    return m["mass"][0] * 1000.0, m["centroid"][2] * 1000.0


def limits_of(feature: dict) -> str:
    enabled = next(p["value"] for p in feature["parameters"]
                   if p["parameterId"] == "limitsEnabled")
    axial = [p.get("expression") for p in feature["parameters"]
             if p["parameterId"] in ("limitAxialZMin", "limitAxialZMax")]
    return f"limitsEnabled={enabled}, rotation limit {axial[0]} .. {axial[1]}"


def without_limits(feature: dict) -> dict:
    """Limits off, and every limit parameter left unset rather than passed through."""
    mod = copy.deepcopy(feature)
    for p in mod["parameters"]:
        pid = p["parameterId"]
        if pid == "limitsEnabled":
            p["value"] = False
        elif pid.startswith("limit"):
            p.update(isNull=True)
    return mod


def write(feature: dict, doc: dict) -> None:
    fid = urllib.parse.quote(feature["featureId"], safe="")   # ids can contain '/'
    call("POST", ASM + "/features/featureid/" + fid,
         body={"btType": "BTMFeatureDefinitionCall-1406", "feature": feature,
               "serializationVersion": doc["serializationVersion"],
               "sourceMicroversion": doc["sourceMicroversion"],
               "rejectMicroversionSkew": False})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="disable the mate limits")
    ap.add_argument("--verify", action="store_true",
                    help="drive every hinge to +-the deflection limit, then park it at zero")
    args = ap.parse_args()

    limit = DEFLECTION_LIMIT_DEG
    doc = features()
    by_name = {f["name"]: f for f in doc["features"] if f["btType"] == "BTMMate-64"}
    missing = [n for n in HINGES if n not in by_name]
    if missing:
        raise SystemExit(f"hinge mates not found in Assembly 1: {missing}")

    print("as found:")
    for name in HINGES:
        print(f"  {name}: {limits_of(by_name[name])}")

    if args.apply:
        before = mass_and_com()
        for name in HINGES:
            doc = features()          # the microversion moves with every write
            feature = next(f for f in doc["features"] if f["name"] == name)
            write(without_limits(feature), doc)
            print(f"  limits off: {name}")

        doc = features()
        for fid, state in doc["featureStates"].items():
            if state.get("featureStatus") != "OK":
                raise SystemExit(f"feature {fid} is {state.get('featureStatus')} after the write")
        print("  all features OK")

        after = mass_and_com()
        print(f"\nmass {before[0]:.3f} -> {after[0]:.3f} g, "
              f"CoM Z {before[1]:.3f} -> {after[1]:.3f} mm")
        if abs(after[0] - before[0]) > 1e-6 or abs(after[1] - before[1]) > 1e-6:
            raise SystemExit("mass or CoM moved: this edit should touch nothing but limits")

    if args.verify:
        doc = features()
        print(f"\ndriving each hinge to +-{limit:g} deg "
              "(a mate that regenerates OK is not a mate that moves):")
        frozen = []
        for name in HINGES:
            fid = next(f["featureId"] for f in doc["features"] if f["name"] == name)
            got = [drive(fid, name, limit), drive(fid, name, -limit)]
            drive(fid, name, 0.0)
            turns = all(abs(g - want) < 1e-6 for g, want in zip(got, (limit, -limit)))
            frozen += [] if turns else [name]
            print(f"  {name}: +{limit:g} -> {got[0]:+7.3f}, -{limit:g} -> {got[1]:+7.3f}"
                  f"   {'TURNS' if turns else 'FROZEN'}")
        print("\nparked at:", {k: round(v, 6) for k, v in mate_values().items()})
        if frozen:
            raise SystemExit(f"still frozen: {frozen}")


if __name__ == "__main__":
    main()
