"""Put the canard root tang into the Onshape model.

    python scripts/make_root_tang.py --check    # read the model, change nothing
    python scripts/make_root_tang.py --apply    # add the feature, verify, roll back on doubt

The design is in design/hinge.py and the argument for it is in out/hinge_report.txt. This
script only applies it, and the FeatureScript that does the work is `canardRootTang` in
cad/canard_articulation.fs.

WHY A CUSTOM FEATURE rather than a sketch, an extrude and a copy of the circular pattern,
which is how scripts/make_hinge_stack.py works. Because this operation needs a BOOLEAN
SCOPE: the slot must cut the four panels and nothing else, and the tang must join the four
shafts and nothing else -- in a Part Studio that also holds four obsolete servo blocks and
a tube. A boolean scope in feature JSON has to name bodies, and **bodies cannot be named by
bare deterministic id** -- such a query POSTs fine and then regenerates as ERROR. That is
the same wall docs/05 hit when it left the spline socket uncut: "cutting it needs a boolean
scope that reaches the four patterned shaft bodies without also drilling the four obsolete
servo blocks". FeatureScript resolves its queries at regeneration time instead, so it can
simply classify the bodies and pick the right ones. The socket could be cut the same way
now; it has not been, because nothing depends on it.

SAFETY, and it is not decoration. This Part Studio has already been emptied once by a
custom feature that reported `featureStatus: OK`, and its circular pattern silently drops
material assignments from its copies. So the feature is added, then part count, feature
status and mass are all checked against an expectation computed from the model's OWN
measured densities -- and anything unexpected deletes the feature again.
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
from design.packaging import SERVO_GEOMETRY

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
PART_STUDIO = "dfb730308a9933e911684b5c"
FEATURE_STUDIO = "8fa6ee54161173d35b56d1c8"

FEATURE_TYPE = "canardRootTang"
FEATURE_NAME = "Canard root tang"
EXPECTED_PARTS = 13          # the tang joins a shaft and the slot cuts a panel, so the
                             # part COUNT must not move. If it does, a boolean missed.
BOND_LINE_MM = 0.100
OVERSHOOT_MM = 1.000         # must match OVERSHOOT in the FeatureScript
MASS_TOLERANCE_G = 0.05

PS = f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}"
MM = 1000.0


def parts() -> list[dict]:
    return get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}")


def total_mass_g() -> float:
    return get(f"{PS}/massproperties")["bodies"]["-all-"]["mass"][0] * 1000.0


def part_mass_and_volume(pid: str) -> tuple[float, float]:
    b = get(f"{PS}/massproperties", partId=pid)["bodies"]["-all-"]
    return b["mass"][0] * 1000.0, b["volume"][0] * 1e9


def density(pid: str) -> float:
    """kg/m^3, measured off the model rather than assumed. The circular pattern in this
    Part Studio has dropped material assignments before, which made the module read
    0.175 kg instead of 0.260 -- so the density a body actually has is a fact worth
    reading, not one worth trusting."""
    m_g, v_mm3 = part_mass_and_volume(pid)
    return (m_g / 1000.0) / (v_mm3 * 1e-9)


def joint() -> tuple[hinge.RootJoint, float]:
    """The selected joint, and the hinge station in the Part Studio's own Z, in mm.

    The station is DERIVED -- `canard_hinge_station` less the module's forward face -- and
    not typed. It comes out at 68.269, which is the number docs/05 carries for the Hinge
    Plane and the number `Sketch 3` is dimensioned to, so this doubles as the check that
    the CAD and the analysis still agree about where the hinge is. That has been wrong
    once already, by 4.4x in hinge moment.
    """
    p = baseline()
    r = build_vehicle(p)
    stack = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness,
                           SERVO_GEOMETRY[p.servo])
    station_mm = (hinge.canard_hinge_station(r) - r.tube_station(1)) * MM
    return hinge.selected_root_joint(stack, r.canards), station_mm


def expected_mass_change_g(j: hinge.RootJoint) -> tuple[float, float, float]:
    """What the tang and the slot are worth, from the model's own densities.

    Computed rather than recorded, so it tracks design/hinge.py instead of going stale the
    first time a dimension moves.
    """
    shaft = [p for p in parts() if p["name"].startswith("Canard shaft 0")][0]
    panel = [p for p in parts() if p["name"].startswith("Canard panel 0")][0]
    rho_shaft, rho_panel = density(shaft["partId"]), density(panel["partId"])

    t, w, L = j.tang_thickness * MM, j.tang_width * MM, j.engagement * MM
    r_shaft = j.sleeve_dia * MM / 2.0

    # Tang: the box runs from OVERSHOOT inboard of the panel root out to the engagement.
    # The overshoot overlaps the round shaft, so that much is not NEW material.
    tang_box = (L + OVERSHOOT_MM) * t * w
    a = t / 2.0
    strip = 2.0 * (a * math.sqrt(r_shaft ** 2 - a ** 2)
                   + r_shaft ** 2 * math.asin(a / r_shaft))   # circle ∩ |y| <= t/2
    tang_new = tang_box - OVERSHOOT_MM * strip
    d_shaft = 4.0 * tang_new * 1e-9 * rho_shaft * 1000.0

    # Slot: only the part INSIDE the panel counts, i.e. from the panel root face outward.
    slot = ((L + BOND_LINE_MM) * (t + 2 * BOND_LINE_MM) * (w + 2 * BOND_LINE_MM))
    d_panel = -4.0 * slot * 1e-9 * rho_panel * 1000.0
    return d_shaft, d_panel, d_shaft + d_panel


def existing() -> list[dict]:
    return [f for f in get(f"{PS}/features")["features"]
            if f.get("featureType") == FEATURE_TYPE]


def report(j: hinge.RootJoint, station_mm: float) -> None:
    print(f"  tang            {j.tang_thickness * MM:.2f} x {j.tang_width * MM:.2f} mm, "
          f"{j.engagement * MM:.2f} mm engaged")
    print(f"  radially        R {j.panel_root * MM:.3f} -> {j.tang_tip_radius * MM:.3f}")
    print(f"  hinge station   Z {station_mm:.3f} mm from the module forward face "
          f"({j.root_le_to_hinge * MM:.3f} aft of the root LE)")
    print(f"  leading edge    {j.leading_edge_clearance * MM:.3f} mm clear at the tang tip")
    print(f"  skins           {j.skin_thickness * MM:.2f} mm each side")
    d_shaft, d_panel, net = expected_mass_change_g(j)
    print(f"  expected mass   shafts {d_shaft:+.4f} g, panels {d_panel:+.4f} g, "
          f"net {net:+.4f} g")


def apply(j: hinge.RootJoint, station_mm: float) -> None:
    have = existing()
    if have:
        print(f"  already present: {', '.join(f['name'] for f in have)} -- leaving it alone")
        return

    before = total_mass_g()
    _, _, expect = expected_mass_change_g(j)
    print(f"  before          {len(parts())} parts, {before:.4f} g")

    mv = get(f"/documents/d/{DOC}/w/{WS}/currentmicroversion")["microversion"]
    q = lambda pid, mm_val: {"btType": "BTMParameterQuantity-147",
                             "parameterId": pid, "expression": f"{mm_val:.4f} mm"}
    feature = {"feature": {
        "btType": "BTMFeature-134", "featureType": FEATURE_TYPE, "name": FEATURE_NAME,
        "namespace": f"e{FEATURE_STUDIO}::m{mv}",
        "parameters": [
            q("hingeStation", station_mm),
            q("panelRootRadius", j.panel_root * MM),
            q("tangThickness", j.tang_thickness * MM),
            q("tangWidth", j.tang_width * MM),
            q("tangEngagement", j.engagement * MM),
            q("bondLine", BOND_LINE_MM),
        ]}}
    fid = post(f"{PS}/features", feature)["feature"]["featureId"]

    state = get(f"{PS}/features")
    status = state["featureStates"].get(fid, {}).get("featureStatus")
    n, after = len(parts()), total_mass_g()
    moved = after - before
    ok = (status == "OK" and n == EXPECTED_PARTS
          and abs(moved - expect) < MASS_TOLERANCE_G)

    print(f"  after           {n} parts, {after:.4f} g  ({moved:+.4f} g, "
          f"expected {expect:+.4f})")
    print(f"  feature status  {status}")
    if not ok:
        call("DELETE", f"{PS}/features/featureid/{quote(fid, safe='')}")
        raise SystemExit(
            f"REFUSING to leave the model in this state: status={status}, {n} parts "
            f"(expected {EXPECTED_PARTS}), mass moved {moved:+.4f} g against an expected "
            f"{expect:+.4f}. Feature deleted; the Part Studio is back as it was.")
    print("  OK -- tang applied, part count held, mass moved by the predicted amount")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    j, station_mm = joint()
    print(f"\ncanard root tang -- {'APPLY' if args.apply else 'check only'}\n")
    report(j, station_mm)
    print()
    if args.apply:
        apply(j, station_mm)
    else:
        have = existing()
        print(f"  in the model    {'yes: ' + have[0]['name'] if have else 'NOT PRESENT'}")


if __name__ == "__main__":
    main()
