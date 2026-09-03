"""Build the two access bulkheads as real geometry in Onshape, from design/access_bulkhead.py.

Run:  python scripts/make_access_bulkhead_cad.py

WHY THIS EXISTS. `design/access_bulkhead.py` sized both plates in August 2026 (correction
38) and neither has ever been drawn -- which is the whole reason the forward wiring
pass-through has never appeared on the Step 3 drawing (correction 37). Same lesson this
project keeps relearning: a part that is not modelled cannot collide with anything, and
cannot be dimensioned either.

WHAT GETS BUILT:

    Pass-through plate      dia 74.8 x 2.4 G-10, 1 x dia 8.0 wire bundle feed-through
    Nose aft face            dia 74.8 x 3.2 G-10, 1 x dia 8.0 connector feed-through

FRAME -- and it is the MIRROR of make_bulkhead_cad.py's, not a copy of it. The aft gas seal
sits at the module's AFT face (Z 142.900) with its origin on the disc's aft face and the
disc body growing FORWARD (opposite=True) into the module's own modelled tube. This plate
sits at the module's FORWARD face (Z 0.000) and closes the NAV BAY's aft end
(`design/joints.py`: "charged to the nav bay because it closes the nav bay's aft end") --
so putting its origin on the disc's aft face and growing forward would place the whole disc
in NEGATIVE Z, outside the one tube this project actually models. Instead: origin on the
disc's FORWARD face, body growing AFT (opposite=False) into the module's own Z 0 -> 142.9
span, so the geometry that gets interference-checked is inside the geometry that exists.
The nose plate is built as a part only -- it is not assembled, for the same reason the
internal bulkhead is not: the nose cavity has never been modelled, so instancing it would
place it in a bay that does not exist here.

CAUTION, inherited from make_bulkhead_cad.py and make_bearing_cad.py before it: this script
does not delete anything. DELETE /elements returns 403 on a read-only-flagged key even
though POST creates happily, so a rebuild means deleting the Part Studio in the browser
first. And FINISH A PART STUDIO BEFORE PUTTING IT IN AN ASSEMBLY (correction 24) --
rebuilding one orphans every instance.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import access_bulkhead as ab
from design import onshape_build as ob
from design.configure import baseline, evaluate
from design.onshape import get, post

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
MM = 1000.0

G10_DENSITY = 1850.0
PROP_NAME = "57f3fb8efa3416c06701d60d"
PROP_MATERIAL = "57f3fb8efa3416c06701d615"

SPECS = [
    ("Pass-through plate (G-10 2.4)", "Pass-through plate (G-10, dia 74.8 x 2.4)",
     "pass_through"),
    ("Nose aft face (G-10 3.2)", "Nose aft face (G-10, dia 74.8 x 3.2)", "nose"),
]


def find_element(name: str):
    for e in get(f"/documents/d/{DOC}/w/{WS}/elements"):
        if e["name"] == name:
            return e
    return None


def add(feature: dict, element: str) -> str:
    r = post(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/features", {"feature": feature})
    return r["feature"]["featureId"]


def build(element: str, r: ab.AccessBulkheadResult) -> None:
    """The disc, origin on its FORWARD face, growing AFT -- see the module docstring's
    FRAME note for why this is the mirror of `make_bulkhead_cad.py`'s convention."""
    t = r.bulkhead.thickness * MM
    od = r.bulkhead.bore_diameter * MM

    sk = add(ob.sketch("Disc OD", "Top",
                       [ob.circle(0.0, 0.0, od / 2000.0, "od")]), element)
    add(ob.extrude("Bulkhead disc", [ob.sketch_regions(sk)],
                   depth_mm=t, opposite=False), element)

    # The one feed-through, overshooting both faces by 1 mm -- same degenerate-cut caution
    # as make_bulkhead_cad.py (correction 7), mirrored: the disc spans local Z [0, t], so the
    # cut starts `over` BEFORE the forward face and runs the same direction as the disc.
    over = 1.0
    for h in ab.hole_layout(r):
        sk = add(ob.sketch(h.name, "Top",
                           [ob.circle(h.x, h.y, h.diameter / 2.0, "hole")]), element)
        add(ob.extrude(h.name, [ob.sketch_regions(sk)],
                       depth_mm=t + 2 * over, opposite=False,
                       start_offset_mm=over, start_offset_opposite=True,
                       operation="REMOVE"), element)


def name_and_material(element: str, part_name: str) -> None:
    """Name it and give it a density as part of the build -- an unmaterialled part weighs
    0.0000 g and still answers every mass query, which is correction 22's trap."""
    part_id = get(f"/parts/d/{DOC}/w/{WS}/e/{element}")[0]["partId"]
    r = post(f"/metadata/d/{DOC}/w/{WS}/e/{element}/p/{part_id}", {
        "jsonType": "metadata-part",
        "properties": [
            {"propertyId": PROP_NAME, "value": part_name},
            {"propertyId": PROP_MATERIAL, "value": {
                "id": "CustomMaterial", "displayName": "G-10/FR-4", "libraryName": "",
                "properties": [{
                    "name": "DENS", "value": f"{G10_DENSITY:.0f}", "type": "",
                    "displayName": "Density", "units": "kg/m^3",
                    "category": "", "description": ""}]}},
        ]})
    ok = {"SUCCEEDED", "NOTHING_TO_UPDATE"}
    failed = [q for q in r.get("properties", []) if q.get("status") not in ok]
    if r.get("status") not in ok or failed:
        raise SystemExit(f"metadata write did not take: {r}")


def verify(element: str, r: ab.AccessBulkheadResult) -> None:
    """Volume against the analytic disc-less-hole, to the micron -- the only proof the hole
    actually cut rather than landing off the material (correction 7's trap, and the reason
    the extrude direction is mirrored so carefully above)."""
    import math
    want = math.pi * r.bulkhead.radius**2 * r.bulkhead.thickness
    for h in ab.hole_layout(r):
        want -= math.pi * (h.diameter / 2.0) ** 2 * r.bulkhead.thickness
    want *= 1e9  # mm^3

    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{element}")
    if len(parts) != 1:
        raise SystemExit(f"expected one part, found {len(parts)}")
    pid = parts[0]["partId"]
    mp = get(f"/parts/d/{DOC}/w/{WS}/e/{element}/partid/{pid}/massproperties")
    have = mp["bodies"][pid]["volume"][0] * 1e9
    solid = math.pi * r.bulkhead.radius**2 * r.bulkhead.thickness * 1e9

    print(f"    volume       {have:10.3f} mm^3 against {want:10.3f} analytic "
          f"({have - want:+.3f})")
    print(f"    solid would be {solid:8.3f} mm^3 -- the hole is {solid - want:.1f} mm^3, "
          f"{(solid - want) / solid * 100:.1f}%")
    if abs(have - want) > 0.01:
        raise SystemExit("VOLUME MISMATCH -- the hole did not cut as drawn")
    mass = mp["bodies"][pid]["mass"][0] * 1000.0
    print(f"    mass         {mass:10.3f} g at {G10_DENSITY:.0f} kg/m^3 "
          f"(design/access_bulkhead.py says {r.bulkhead.mass * 1e3:.3f} g solid)")
    if mass < 1e-6:
        raise SystemExit("mass is zero -- the material did not take")


def main() -> None:
    ev = evaluate(baseline())
    results = {
        "pass_through": ab.pass_through_from_evaluation(ev),
        "nose": ab.nose_plate_from_evaluation(ev),
    }

    for element_name, part_name, key in SPECS:
        r = results[key]
        chk = ab.check_hole_layout(r)
        print(f"\n{element_name}")
        print(f"  layout       {'OK' if chk.ok else 'VIOLATIONS: ' + '; '.join(chk.violations)}")
        if not chk.ok:
            raise SystemExit("refusing to build a layout that does not pass its own check")

        el = find_element(element_name)
        if el is not None:
            print(f"  exists       {el['id']} -- verifying rather than rebuilding")
            verify(el["id"], r)
            continue

        el = post(f"/partstudios/d/{DOC}/w/{WS}", {"name": element_name})
        print(f"  created      {el['id']}")
        build(el["id"], r)
        name_and_material(el["id"], part_name)
        verify(el["id"], r)

    print("\nOnly the pass-through plate belongs in Assembly 1 -- the nose plate closes a")
    print("cavity that has never been modelled, same reasoning as the internal bulkhead.")
    print("Place with  python scripts/place_access_bulkhead.py")


if __name__ == "__main__":
    main()
