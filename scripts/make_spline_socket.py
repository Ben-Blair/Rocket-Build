"""Cut the spline socket into the four canard shafts.

    python scripts/make_spline_socket.py --check
    python scripts/make_spline_socket.py --apply

A plain dia 4.100 x 3.20 blind hole in the inboard end of each sleeve. It is not a
broached spline: it is filled with anaerobic retaining compound and pushed onto the servo
spline, and the compound cures in the tooth valleys and becomes the female spline. The
argument is in design/hinge.py under "THE COUPLING" and the numbers print from
scripts/hinge_report.py.

docs/05 has carried this as "the socket could be cut the same way now; it has not been,
because nothing depends on it" since the hinge stack went in. The coupling depends on it.

SAFETY. This edits `Canard articulation`, the Feature Studio that Part Studio 1 depends on
for its deflection, its mate connectors and its root tang. A custom feature that fails to
compile can regenerate that Part Studio to EMPTY while reporting `featureStatus: OK`, and
this document has had that happen. So the deploy is:

    save the old contents -> POST the new -> read featurespecs (the ONLY compile check the
    API offers; an empty list means it did not compile) -> assert the Part Studio still has
    13 parts and the expected mass -> put the old contents back if anything moved.

The mass check is the one with teeth. Four dia 4.1 x 3.2 blind holes remove
4 * pi/4 * 4.1^2 * 3.2 = 169.0 mm^3 of aluminium, which is 0.457 g. If the studio does not
lose that, the sockets did not cut -- and a cut that silently cuts nothing is exactly how
the wall bore spent months at dia 5.000 on a dia 5.000 shaft.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import hinge
from design.configure import baseline, build_vehicle
from design.onshape import call, get, post
from design.packaging import SERVO_GEOMETRY, SERVOS

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
PART_STUDIO = "dfb730308a9933e911684b5c"
FEATURE_STUDIO = "8fa6ee54161173d35b56d1c8"
PS = f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}"
FS = f"/featurestudios/d/{DOC}/w/{WS}/e/{FEATURE_STUDIO}"
SOURCE = Path(__file__).resolve().parents[1] / "cad" / "canard_articulation.fs"

FEATURE_TYPE = "canardSplineSocket"
FEATURE_NAME = "Canard spline socket"
EXPECTED_PARTS = 13
MASS_TOLERANCE_G = 0.05
MM = 1000.0


def model() -> tuple[hinge.HingeStack, hinge.BondedCoupling, float]:
    p = baseline()
    r = build_vehicle(p)
    g = SERVO_GEOMETRY[p.servo]
    s = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, g)
    c = hinge.bonded_coupling(s, SERVOS[p.servo].stall_torque, g.spline_teeth)
    station = hinge.canard_hinge_station(r) - r.tube_station(1)
    return s, c, station


def parts() -> list[dict]:
    return get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}")


def total_mass_g() -> float:
    total = 0.0
    for p in parts():
        mp = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}/partid/{p['partId']}/massproperties")
        total += mp["bodies"][p["partId"]]["mass"][0]
    return total * 1000.0


def shaft_density() -> float:
    """Read the density the MODEL actually uses rather than assuming 2700.

    The predicted mass change is the whole safety check, so it has to be computed from the
    same numbers the studio is using. If someone changes the shaft material this check
    follows them instead of quietly going wrong."""
    for p in parts():
        if not p["name"].startswith("Canard shaft"):
            continue
        mp = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}/partid/{p['partId']}/massproperties")
        b = mp["bodies"][p["partId"]]
        return b["mass"][0] / b["volume"][0]
    raise SystemExit("no canard shaft found to read a density from")


def expected_loss_g(c: hinge.BondedCoupling, density: float) -> float:
    v = 4.0 * math.pi * (c.socket_dia / 2.0) ** 2 * c.socket_depth
    return v * density * 1000.0


def existing() -> list[dict]:
    return [f for f in get(f"{PS}/features").get("features", [])
            if f.get("featureType") == FEATURE_TYPE]


def deploy_source() -> None:
    """Push the Feature Studio and prove it compiled, keeping the old text to fall back to."""
    old = get(FS)["contents"]
    post(FS, {"contents": SOURCE.read_text()})
    specs = get(f"{FS}/featurespecs")
    got = specs.get("featureSpecs", specs) if isinstance(specs, dict) else specs
    names = [x.get("featureName") or x.get("featureTypeName") for x in got]
    if not names or FEATURE_NAME not in names:
        post(FS, {"contents": old})
        raise SystemExit(
            f"'{FEATURE_NAME}' is not in the compiled exports {names}. Old contents "
            f"restored. An empty list means it did not compile at all, and the API gives "
            f"no reason -- open the Feature Studio in the browser and look for the "
            f"red squiggle.")
    print(f"  Feature Studio compiles, exports: {names}")


def apply(s: hinge.HingeStack, c: hinge.BondedCoupling, station: float) -> None:
    if existing():
        print(f"  '{FEATURE_NAME}' is already in the tree -- leaving it alone")
        return

    density = shaft_density()
    expect = expected_loss_g(c, density)
    before = total_mass_g()
    print(f"  before          {len(parts())} parts, {before:.4f} g "
          f"(shaft density {density:.0f} kg/m^3)")
    print(f"  expect to lose  {expect:.4f} g of aluminium")

    deploy_source()

    mv = get(f"/documents/d/{DOC}/w/{WS}/currentmicroversion")["microversion"]
    q = lambda pid, m: {"btType": "BTMParameterQuantity-147", "parameterId": pid,
                        "expression": f"{m * MM:.4f} mm"}
    fid = post(f"{PS}/features", {"feature": {
        "btType": "BTMFeature-134", "featureType": FEATURE_TYPE, "name": FEATURE_NAME,
        "namespace": f"e{FEATURE_STUDIO}::m{mv}",
        "parameters": [
            q("hingeStation", station),
            q("sleeveInboard", s.sleeve_inboard),
            q("socketDia", c.socket_dia),
            q("socketDepth", c.socket_depth),
        ]}})["feature"]["featureId"]

    status = get(f"{PS}/features")["featureStates"].get(fid, {}).get("featureStatus")
    n, after = len(parts()), total_mass_g()
    moved = before - after
    ok = (status == "OK" and n == EXPECTED_PARTS
          and abs(moved - expect) < MASS_TOLERANCE_G)

    print(f"  after           {n} parts, {after:.4f} g  (lost {moved:.4f} g)")
    print(f"  feature status  {status}")
    if not ok:
        call("DELETE", f"{PS}/features/featureid/{quote(fid, safe='')}")
        raise SystemExit(
            f"REFUSING to leave this: status={status}, {n} parts (expected "
            f"{EXPECTED_PARTS}), mass fell {moved:.4f} g against an expected {expect:.4f}. "
            f"Feature deleted. A zero loss means the cut did not cut.")
    print("  OK -- four sockets cut, part count held, mass fell by the predicted amount")


def report(s: hinge.HingeStack, c: hinge.BondedCoupling, station: float) -> None:
    chk = hinge.check_coupling(c)
    print(f"  socket        dia {c.socket_dia * MM:.3f} x {c.socket_depth * MM:.2f} deep, "
          f"from R {s.sleeve_inboard * MM:.3f} to {(s.sleeve_inboard + c.socket_depth) * MM:.3f}")
    print(f"  wall          {c.socket_wall * MM:.3f} mm around it")
    print(f"  adhesive      {c.bond_shear / 1e6:.2f} MPa, margin {c.bond_margin:.2f}x")
    print(f"  hinge station Z {station * MM:.3f} from the module forward face")
    print(f"  design says   {'buildable' if chk.ok else 'NOT BUILDABLE'}")
    for x in chk.violations:
        print(f"    FAIL  {x}")
    have = existing()
    print(f"  in the CAD    {'yes -- ' + have[0]['name'] if have else 'NO, not cut yet'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    s, c, station = model()
    report(s, c, station)
    if a.apply:
        print()
        apply(s, c, station)


if __name__ == "__main__":
    main()
