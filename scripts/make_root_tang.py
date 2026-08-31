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
                             #
                             # APPLIED 2026-08-30, in the browser, because the /features
                             # quota was spent. Measured afterwards through /parts and
                             # /massproperties: every shaft 746.856 mm^3 against 746.856
                             # predicted, every panel down by exactly the 619.520 mm^3 slot,
                             # module 263.3267 -> 276.2319 g. This script is kept for
                             # rebuilds and is still the readable statement of what was
                             # applied.
BOND_LINE_MM = hinge.BOND_LINE * 1000.0   # imported, not typed -- the FeatureScript takes
                                          # it as a parameter from here
# The tang solid's overshoot inboard of the panel root. Imported, NOT typed: it moved
# 1.0 -> 0.4 mm when Onshape's interference check found the blade modelled inside the
# airframe wall, and a second copy of it here would have made this mass prediction wrong
# by exactly the volume of the bug it was supposed to catch.
OVERSHOOT_MM = hinge.TANG_MODEL_OVERSHOOT * 1000.0
MASS_TOLERANCE_G = 0.05

PS = f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}"
PARTS = f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}"
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


def check_panel_thickness(j: hinge.RootJoint) -> None:
    """The CAD panel must be the thickness the joint was sized against.

    Not a formality. The slot is cut to a fixed 2.000 mm centred in the panel, so the skins
    that survive are whatever the panel has left over -- 0.6 mm in a 3.2 mm panel, 0.5 mm in
    a 3.0 mm one. Skin stress goes as 1/t^2, so building this tang into a panel that is
    0.2 mm thin drops the margin from 2.5x to 1.7x, and NOTHING downstream would notice: the
    tang fits, the boolean succeeds, the part count holds and the mass is within grams. It
    would simply be weaker than every document says it is.

    That is exactly the failure this joint has already had once, in the analysis rather than
    the CAD (docs/01, correction 15). Checking it here is cheap.
    """
    want = j.panel_thickness * MM
    panel = [p for p in parts() if p["name"].startswith("Canard panel 0")][0]
    bb = get(f"{PARTS}/partid/{quote(panel['partId'], safe='')}/boundingboxes")
    got = (bb["highY"] - bb["lowY"]) * MM
    print(f"  panel in CAD    {got:.3f} mm thick, design wants {want:.3f}")
    if abs(got - want) > 0.01:
        raise SystemExit(
            f"REFUSING to cut the tang: the Onshape panel is {got:.3f} mm thick and "
            f"design/configure.py says {want:.3f}. The slot is a fixed "
            f"{j.slot_thickness * MM:.3f} mm, so this would leave "
            f"{(got - j.slot_thickness * MM) / 2:.3f} mm skins instead of "
            f"{j.skin_thickness * MM:.3f}, and the skin margin would be "
            f"{((got - j.slot_thickness * MM) / 2 / (j.skin_thickness * MM)) ** 2:.2f}x of "
            f"what the report claims. Run make_hinge_stack.py --panel first.")


def apply(j: hinge.RootJoint, station_mm: float, redeploy: bool = False) -> None:
    check_panel_thickness(j)
    have = existing()
    if have and not redeploy:
        print(f"  already present: {', '.join(f['name'] for f in have)} -- leaving it alone")
        return
    if have:
        # REDEPLOY exists because a feature's Feature Studio namespace is IMMUTABLE.
        # POSTing an existing feature back with a bumped namespace microversion is refused
        # with "Feature does not match" -- tried with and without serializationVersion,
        # with rejectMicroversionSkew both ways, and with no microversion at all. So the
        # only way to pick up edited FeatureScript is to delete the feature and add it
        # again, and that is safe HERE only because this feature creates no parts: it cuts
        # the panels and unions the tang into shafts that already exist, so every part id
        # survives and the assembly's four hand-placed mates never notice. It would not be
        # safe on a feature that creates bodies.
        before_ids = {p["partId"] for p in parts()}
        for f in have:
            call("DELETE", f"{PS}/features/featureid/{quote(f['featureId'], safe='')}")
        after_ids = {p["partId"] for p in parts()}
        if before_ids != after_ids:
            raise SystemExit(f"deleting the tang changed the part ids "
                             f"({before_ids ^ after_ids}); STOP -- the assembly references "
                             f"these and its mates cannot be rebuilt from the API")
        print(f"  deleted {len(have)} feature(s) to pick up new FeatureScript; "
              f"all {len(after_ids)} part ids survived")

    before = total_mass_g()
    _, _, expect = expected_mass_change_g(j)
    print(f"  before          {len(parts())} parts, {before:.4f} g")

    # Push the Feature Studio first, and prove it compiled: an empty featurespecs is the
    # only symptom the API gives for a parse error, and a custom feature that fails to
    # compile can regenerate this Part Studio to EMPTY while reporting featureStatus OK.
    src = (Path(__file__).resolve().parents[1] / "cad" / "canard_articulation.fs").read_text()
    old_src = get(f"/featurestudios/d/{DOC}/w/{WS}/e/{FEATURE_STUDIO}")["contents"]
    post(f"/featurestudios/d/{DOC}/w/{WS}/e/{FEATURE_STUDIO}", {"contents": src})
    specs = get(f"/featurestudios/d/{DOC}/w/{WS}/e/{FEATURE_STUDIO}/featurespecs")
    got = specs.get("featureSpecs", specs) if isinstance(specs, dict) else specs
    names = [x.get("featureName") or x.get("featureTypeName") for x in got]
    if FEATURE_NAME not in names:
        post(f"/featurestudios/d/{DOC}/w/{WS}/e/{FEATURE_STUDIO}", {"contents": old_src})
        raise SystemExit(f"'{FEATURE_NAME}' missing from compiled exports {names}; "
                         f"old source restored")
    print(f"  Feature Studio compiles, exports: {names}")

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
            q("tangOvershoot", hinge.TANG_MODEL_OVERSHOOT * 1000.0),
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
    ap.add_argument("--redeploy", action="store_true",
                    help="delete and re-add the feature so it picks up edited FeatureScript")
    args = ap.parse_args()
    j, station_mm = joint()
    print(f"\ncanard root tang -- {'APPLY' if args.apply else 'check only'}\n")
    report(j, station_mm)
    print()
    if args.apply or args.redeploy:
        apply(j, station_mm, redeploy=args.redeploy)
    else:
        have = existing()
        print(f"  in the model    {'yes: ' + have[0]['name'] if have else 'NOT PRESENT'}")


if __name__ == "__main__":
    main()
