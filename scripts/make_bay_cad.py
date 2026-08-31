"""Build the printed canard bay in Onshape, from design/bay.py.

    python scripts/make_bay_cad.py --check     # read the model, change nothing
    python scripts/make_bay_cad.py --apply     # create the studios and build

Two new elements, both created fresh so that nothing existing is at risk:

  * Feature Studio  "Canard bay"           <- cad/canard_bay.fs
  * Part Studio     "Canard bay (printed)" <- one instance of the `Canard bay` feature

The bay is drawn in the MODULE's frame -- origin on the rocket axis, Z 0 at the canard
module tube's forward face -- so it drops into Assembly 1 at identity. No transform to
compute and none to get wrong. scripts/place_bearings.py had to derive a placement from a
servo's transform; this one needs nothing.

VERIFICATION, and it is the point of the script rather than a postscript. A custom feature
that fails to compile can leave a Part Studio EMPTY while reporting `featureStatus: OK`,
and this project has had that happen. So:

  1. the Feature Studio's `featurespecs` must come back naming `Canard bay` -- that is the
     only compile check the API offers, and an empty list means it did not compile;
  2. the Part Studio must hold exactly the expected number of parts;
  3. the printed part's VOLUME must agree with design/bay.py's own analytic figure.

(3) is the one that matters. Part count and bounding box would both pass on a shell with no
servo windows, no collar bores and no insert holes. Volume is the number that only comes
out right if the cuts actually cut -- the same argument as the bearing's annulus.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import bay, hinge
from design.configure import baseline, build_vehicle
from design.materials import BAY_MATERIAL
from design.onshape import call, get, post
from design.packaging import SERVO_GEOMETRY

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"

FS_NAME = "Canard bay"
PS_NAME = "Canard bay (printed)"
FEATURE_TYPE = "canardBay"
PART_NAME = "Canard bay (printed, PETG-CF)"
RETAINER_NAME = "Servo retainer bar (8 off)"
SOURCE = Path(__file__).resolve().parents[1] / "cad" / "canard_bay.fs"

MM = 1000.0
# The shell, plus the retainer bar modelled once. The four quadrants' trays, collars,
# webs and bosses are all UNIONED into the shell, so they are not separate parts.
EXPECTED_PARTS = 2
VOLUME_TOLERANCE = 0.06   # fraction; design/bay.py's volume is a sum of prisms and
                          # cylinders and does not model the webs' embedment in the shell
                          # wall or the boss/tray overlap, so it is an ESTIMATE and the
                          # CAD is the truth. A 6% band catches "a cut did not cut" --
                          # which is worth tens of percent -- without pretending the
                          # analytic figure is exact.

PROP_NAME = "57f3fb8efa3416c06701d60d"
PROP_MATERIAL = "57f3fb8efa3416c06701d615"


def geometry() -> bay.BayGeometry:
    p = baseline()
    r = build_vehicle(p)
    g = SERVO_GEOMETRY[p.servo]
    s = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, g)
    return bay.build_bay(s, g, hinge.canard_hinge_station(r) - r.tube_station(1))


def find(name: str):
    for e in get(f"/documents/d/{DOC}/w/{WS}/elements"):
        if e["name"] == name:
            return e
    return None


def deploy_feature_studio() -> str:
    el = find(FS_NAME)
    if el is None:
        el = post(f"/featurestudios/d/{DOC}/w/{WS}", {"name": FS_NAME})
        print(f"  created Feature Studio '{FS_NAME}' -> {el['id']}")
    eid = el["id"]
    post(f"/featurestudios/d/{DOC}/w/{WS}/e/{eid}", {"contents": SOURCE.read_text()})

    specs = get(f"/featurestudios/d/{DOC}/w/{WS}/e/{eid}/featurespecs")
    names = [s.get("featureName") or s.get("featureTypeName")
             for s in (specs.get("featureSpecs", specs) if isinstance(specs, dict) else specs)]
    if not names:
        raise SystemExit(
            f"'{FS_NAME}' did not compile. An empty featurespecs is the ONLY symptom the "
            f"API gives -- there is no error message. Open the tab in the browser and look "
            f"for the red squiggle; `box` being a reserved word has caused this twice.")
    print(f"  compiles, exports: {names}")
    if FEATURE_TYPE not in [n for n in names] and FS_NAME not in names:
        raise SystemExit(f"compiled, but does not export '{FEATURE_TYPE}': {names}")
    return eid


def parameters(b: bay.BayGeometry) -> list[dict]:
    def q(pid: str, metres: float) -> dict:
        return {"btType": "BTMParameterQuantity-147", "parameterId": pid,
                "expression": f"{metres * MM:.4f} mm"}

    s = b.stack
    return [
        q("shellOd", 2.0 * b.shell_outer_radius),
        q("shellId", 2.0 * b.shell_inner_radius),
        q("zFwd", b.forward_face),
        q("zAft", b.aft_face),
        q("zHinge", b.hinge_station),
        q("collarOd", bay.COLLAR_OD),
        # AS REAMED, not as printed. The assembly is the vehicle that flies.
        q("collarBore", b.collar_bore),
        q("collarOverlap", bay.COLLAR_BOSS_OVERLAP),
        q("collarInnerR", s.bearing_inboard),
        q("trayFlangeR", b.tray_flange_face),
        q("trayBackR", b.tray_back_face),
        q("trayWidth", b.tray_width),
        q("trayFwdZ", b.servo_forward),
        q("trayAftZ", b.servo_aft),
        q("windowLen", b.window_length),
        q("windowWid", b.window_width),
        q("windowFwdZ", b.window_forward),
        q("webThk", bay.MIN_WALL),
        q("bossFaceR", b.boss_face),
        q("insertDia", bay.INSERT_DIA),
        q("insertDepth", bay.INSERT_DEPTH),
        q("clampY", bay.RETAINER_SCREW_ACROSS),
        q("screwZ1", b.screw_stations[0]),
        q("screwZ2", b.screw_stations[1]),
        q("retThk", bay.RETAINER_THICKNESS),
        q("retBridgeHalfZ", bay.RETAINER_BRIDGE_HALF_Z),
        q("retPadHalfZ", bay.RETAINER_PAD_HALF_Z),
        {"btType": "BTMParameterBoolean-144", "parameterId": "buildRetainer", "value": True},
    ]


def build(fs_id: str, b: bay.BayGeometry, rebuild: bool = False) -> str:
    el = find(PS_NAME)
    if el is not None:
        ps = el["id"]
        feats = get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/features").get("features", [])
        if feats and rebuild:
            # DELETE AND RE-ADD, because there is no alternative.
            #
            # A feature's Feature Studio namespace is IMMUTABLE. POSTing the feature back
            # with a bumped namespace microversion is refused with "Feature does not
            # match" -- tried with and without serializationVersion, with
            # rejectMicroversionSkew both ways, and with no microversion at all. So new
            # FeatureScript can only reach an existing feature by replacing it.
            #
            # And a HALF-DONE rebuild is worse than none. When the edit-in-place attempt
            # above failed, it had already pushed the new source, and Onshape filled the
            # newly-declared `collarOverlap` on the OLD feature with the spec default of
            # 25 mm. The Part Studio regenerated as OK, kept its part count, kept its part
            # names, and grew four dia 12 spikes 22 mm long straight out through the
            # airframe. Nothing except a volume check would have said so. That is why
            # verify() compares volume against design/bay.py and not just part count.
            asm = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}")["rootAssembly"]
            referencing = [i for i in asm["instances"] if i.get("elementId") == ps]
            if referencing:
                raise SystemExit(
                    f"REFUSING to rebuild: Assembly 1 holds {len(referencing)} instance(s) "
                    f"of '{PS_NAME}'. Deleting the feature destroys the bodies they point "
                    f"at, and Onshape heals an orphaned instance to an EMPTY partId -- it "
                    f"keeps its name and its transform, weighs nothing, and puts the "
                    f"airframe rigid group into ERROR.\n\n"
                    f"There is no instance-delete route on the API. Delete those "
                    f"{len(referencing)} instances in the browser first, then --rebuild, "
                    f"then --assemble.\n\n"
                    f"The lesson, which is cheap to follow: FINISH THE PART STUDIO BEFORE "
                    f"PUTTING IT IN AN ASSEMBLY.")
            for fdef in feats:
                call("DELETE", f"/partstudios/d/{DOC}/w/{WS}/e/{ps}"
                               f"/features/featureid/{quote(fdef['featureId'], safe='')}")
            print(f"  deleted {len(feats)} feature(s) to pick up new FeatureScript")
            feats = []
        if feats:
            print(f"  Part Studio '{PS_NAME}' already built ({ps}), "
                  f"{len(feats)} feature(s)")
            return ps
        # Exists but EMPTY, which is what a failed first attempt leaves behind: the
        # element cannot be deleted with this API key, and the bad feature was rolled
        # back. Carry on and populate it rather than reporting success on nothing.
        print(f"  Part Studio '{PS_NAME}' exists but is empty ({ps}) -- building into it")
    else:
        ps = post(f"/partstudios/d/{DOC}/w/{WS}", {"name": PS_NAME})["id"]
        print(f"  created Part Studio '{PS_NAME}' -> {ps}")

    mv = get(f"/documents/d/{DOC}/w/{WS}/currentmicroversion")["microversion"]
    fid = post(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/features", {"feature": {
        "btType": "BTMFeature-134", "featureType": FEATURE_TYPE, "name": "Canard bay",
        "namespace": f"e{fs_id}::m{mv}",
        "parameters": parameters(b),
    }})["feature"]["featureId"]

    status = get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/features") \
        ["featureStates"].get(fid, {}).get("featureStatus")
    print(f"  feature status: {status}")
    if status != "OK":
        call("DELETE", f"/partstudios/d/{DOC}/w/{WS}/e/{ps}"
                       f"/features/featureid/{quote(fid, safe='')}")
        raise SystemExit(f"'Canard bay' regenerated as {status}; feature deleted.")
    return ps


def name_and_material(ps: str, part_id: str, name: str, density: float) -> None:
    r = post(f"/metadata/d/{DOC}/w/{WS}/e/{ps}/p/{part_id}", {
        "jsonType": "metadata-part",
        "properties": [
            {"propertyId": PROP_NAME, "value": name},
            {"propertyId": PROP_MATERIAL, "value": {
                "id": "CustomMaterial", "displayName": BAY_MATERIAL, "libraryName": "",
                "properties": [{"name": "DENS", "value": f"{density:.0f}", "type": "",
                                "displayName": "Density", "units": "kg/m^3",
                                "category": "", "description": ""}]}},
        ]})
    ok = {"SUCCEEDED", "NOTHING_TO_UPDATE"}
    bad = [q for q in r.get("properties", []) if q.get("status") not in ok]
    if r.get("status") not in ok or bad:
        raise SystemExit(f"metadata write did not take: {r}")


def verify(ps: str, b: bay.BayGeometry) -> None:
    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{ps}")
    print(f"\n  {len(parts)} part(s):")
    for p in parts:
        print(f"    {p['partId']:5s} {p['name']}")
    if len(parts) != EXPECTED_PARTS:
        raise SystemExit(f"expected {EXPECTED_PARTS} parts, found {len(parts)}")

    # Volume is the check that a shell with no windows and no bores would fail.
    vols = {}
    for p in parts:
        mp = get(f"/parts/d/{DOC}/w/{WS}/e/{ps}/partid/{p['partId']}/massproperties")
        body = mp["bodies"][p["partId"]]
        vols[p["partId"]] = body["volume"][0]
    biggest = max(vols, key=lambda k: vols[k])
    v_cad = vols[biggest]
    v_est = b.volume - b.retainer_volume
    err = abs(v_cad - v_est) / v_est
    print(f"\n  bay volume    CAD {v_cad * 1e9:9.1f} mm^3 against design/bay.py's "
          f"{v_est * 1e9:.1f} mm^3  ({err * 100:+.1f}%)")
    if err > VOLUME_TOLERANCE:
        raise SystemExit(
            f"volume disagrees by {err * 100:.1f}%, over the {VOLUME_TOLERANCE * 100:.0f}% "
            f"band. Either a cut did not cut or the analytic estimate is wrong; find out "
            f"which before trusting this part.")

    bb = get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/boundingboxes")
    print(f"  bounding box  X {bb['lowX'] * MM:8.3f}..{bb['highX'] * MM:8.3f}   "
          f"Z {bb['lowZ'] * MM:8.3f}..{bb['highZ'] * MM:8.3f}")
    print(f"  expected      X +/-{b.shell_outer_radius * MM:.3f}, "
          f"Z {b.forward_face * MM:.3f}..{b.aft_face * MM:.3f}")

    density = b.density
    for p in parts:
        is_bay = p["partId"] == biggest
        name_and_material(ps, p["partId"], PART_NAME if is_bay else RETAINER_NAME, density)
    print(f"  named, {BAY_MATERIAL} at {density:.0f} kg/m^3")
    # The Part Studio endpoint nests everything under bodies["-all-"]; only the per-PART
    # endpoint puts mass at the top level. Reading the wrong one is a KeyError rather than
    # a wrong number, which is the good kind of mistake.
    mp = get(f"/partstudios/d/{DOC}/w/{WS}/e/{ps}/massproperties")["bodies"]["-all-"]
    print(f"  studio mass   {mp['mass'][0] * 1000:.3f} g for one bay + ONE retainer bar")
    print(f"  as flown      {(v_cad * density + 8.0 * (mp['volume'][0] - v_cad) * density) * 1000:.3f} g"
          f"  (the bay plus EIGHT bars -- the studio models the bar once)")


ASM = "ff7e2e472d6694342f892f9c"
AIRFRAME_GROUP = "Airframe (tube + servo bodies)"


def assemble(ps: str, b: bay.BayGeometry) -> None:
    """Put the bay and its eight retainer bars into Assembly 1.

    The bay needs NO transform: it was drawn in the module Part Studio's frame, so its
    identity placement is its real one. That is the whole reason for choosing that frame,
    and it is worth contrasting with scripts/place_bearings.py, which had to derive a
    placement by copying a servo's rotation.

    The bars do need transforms, because the Part Studio models the bar ONCE and eight are
    flown: rotate by quadrant, translate by the lug pitch for the aft row.
    """
    a = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}")["rootAssembly"]

    # REBUILDING A PART STUDIO BREAKS THE ASSEMBLY INSTANCES THAT REFERENCE IT.
    # Deleting the feature destroys the bodies, and Onshape heals the orphaned instance to
    # an EMPTY partId rather than leaving it visibly dangling. The instance keeps its name
    # and its transform, still lists, still shows in the tree -- and contributes no mass and
    # no geometry, while any rigid group holding it regenerates as ERROR. That is a silent
    # 38.5 g hole in the module tensor: the exact failure mode this project keeps meeting.
    # Detect it by the empty partId and replace those instances rather than adding more.
    ours = [i for i in a["instances"] if i.get("elementId") == ps]
    broken = [i for i in ours if not i.get("partId")]
    if broken:
        # And the API cannot clear them: there is no instance-delete route on v10.
        # /instance/{id} and /instances/{id} both 404, encoded or not. So this has to be
        # said plainly rather than papered over -- inserting nine more on top of nine dead
        # ones would leave a tree full of ghosts that weigh nothing.
        raise SystemExit(
            f"{len(broken)} of {len(ours)} instance(s) of '{PS_NAME}' in Assembly 1 have "
            f"lost their part reference. They still list, still hold a transform, and "
            f"contribute NO mass and NO geometry, and any rigid group holding them "
            f"regenerates as ERROR.\n\n"
            f"This is what rebuilding a Part Studio does to an assembly that already "
            f"references it. The API has no way to delete an assembly instance, so:\n"
            f"  1. open Assembly 1 in the browser\n"
            f"  2. delete the {len(broken)} '{PS_NAME}' instances from the instance list\n"
            f"  3. re-run this script with --assemble\n")
    if len(ours) == 9:
        print(f"  the bay and its 8 bars are already in Assembly 1, all resolving")
        return
    if ours:
        raise SystemExit(f"{len(ours)} instance(s) of this element in the assembly, "
                         f"expected 0 or 9. Sort that out by hand rather than adding more.")

    parts = {p["name"]: p["partId"] for p in get(f"/parts/d/{DOC}/w/{WS}/e/{ps}")}
    before = {i["id"] for i in a["instances"]}

    def insert(part_id: str) -> None:
        post(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}/instances", {
            "documentId": DOC, "workspaceId": WS, "elementId": ps, "partId": part_id,
            "isAssembly": False, "isWholePartStudio": False,
            "includePartTypes": ["PARTS"]})

    insert(parts[PART_NAME])
    for _ in range(8):
        insert(parts[RETAINER_NAME])

    a = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}")["rootAssembly"]
    names = {i["id"]: i["name"] for i in a["instances"]}
    new = [i["id"] for i in a["instances"] if i["id"] not in before]
    bays = [i for i in new if names[i].startswith(PART_NAME)]
    bars = [i for i in new if names[i].startswith(RETAINER_NAME)]
    if len(bays) != 1 or len(bars) != 8:
        raise SystemExit(f"inserted {len(bays)} bay(s) and {len(bars)} bar(s), wanted 1 and 8")
    print(f"  inserted the bay (identity -- no transform) and {len(bars)} retainer bars")

    dz = b.screw_stations[1] - b.screw_stations[0]
    for n, iid in enumerate(bars):
        q, row = divmod(n, 2)
        c, s_ = math.cos(math.radians(90 * q)), math.sin(math.radians(90 * q))
        post(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}/occurrencetransforms", {
            "occurrences": [{"path": [iid]}],
            "transform": [c, -s_, 0.0, 0.0,
                          s_, c, 0.0, 0.0,
                          0.0, 0.0, 1.0, dz * row,
                          0.0, 0.0, 0.0, 1.0],
            "isRelative": False})
    print(f"  bars placed on 4 quadrants x 2 rows, aft row {dz * MM:.3f} mm aft")

    # Everything here is bonded or bolted to the airframe and none of it rotates.
    fl = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}/features")
    g = next(f for f in fl["features"] if f.get("name") == AIRFRAME_GROUP)
    qy = next(x for x in g["parameters"] if x["parameterId"] == "occurrencesQuery")
    for iid in new:
        qy["queries"].append({"btType": "BTMIndividualOccurrenceQuery-626", "path": [iid]})
    call("POST", f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}"
                 f"/features/featureid/{quote(g['featureId'], safe='')}",
         {"feature": g, "serializationVersion": fl.get("serializationVersion"),
          "sourceMicroversion": fl.get("sourceMicroversion"),
          "rejectMicroversionSkew": False})
    st = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}/features")["featureStates"] \
        .get(g["featureId"], {}).get("featureStatus")
    print(f"  '{AIRFRAME_GROUP}' now holds {len(qy['queries'])} occurrences: {st}")
    if st != "OK":
        raise SystemExit("the airframe group did not regenerate cleanly")

    a = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}")["rootAssembly"]
    mp = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}/massproperties")
    bad = {k: v.get("featureStatus")
           for k, v in get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASM}/features")
           ["featureStates"].items() if v.get("featureStatus") not in ("OK", "WARNING")}
    print(f"\n  Assembly 1: {len(a['instances'])} instances, "
          f"{mp['mass'][0] * 1000:.4f} g, CoM Z {mp['centroid'][2] * MM:.3f} mm")
    print(f"  feature states not OK: {bad or 'none'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--assemble", action="store_true",
                    help="insert the bay and its eight bars into Assembly 1")
    ap.add_argument("--rebuild", action="store_true",
                    help="delete the bay feature and re-add it (the ELEMENT stays; a "
                         "read-only-flagged API key cannot delete elements)")
    a = ap.parse_args()
    b = geometry()

    print(f"design/bay.py says: {b.material.name}, {b.mass * 1000:.1f} g, "
          f"{b.length * MM:.1f} mm long, shell OD {2 * b.shell_outer_radius * MM:.3f}")
    if not (a.apply or a.rebuild or a.assemble):
        for e in get(f"/documents/d/{DOC}/w/{WS}/elements"):
            if e["name"] in (FS_NAME, PS_NAME):
                print(f"  present: {e['elementType']:13s} {e['name']}")
        print("\n--apply not given; nothing written")
        return

    print("\nfeature studio")
    fs_id = deploy_feature_studio()
    print("\npart studio")
    ps = build(fs_id, b, rebuild=a.rebuild)
    verify(ps, b)
    if a.assemble:
        print("\nassembly")
        assemble(ps, b)


if __name__ == "__main__":
    main()
