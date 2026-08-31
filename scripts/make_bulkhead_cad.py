"""Build the two recovery bulkheads as real geometry in Onshape, from design/seal.py.

Run:  python scripts/make_bulkhead_cad.py

WHY THIS EXISTS. `design/seal.py` sized both of them in August 2026 and neither was ever
drawn. This project's own history says what that costs: the servo was a mass-tuned block
for months and hid a hard clash at zero deflection (correction 11), and the bearing existed
only as a dimension until correction 18 -- *"a part that is not modelled cannot collide with
anything"*. The aft gas seal bolts to the canard module's aft face, which is inside the one
assembly this project actually runs an interference check on, so it is the piece with a
reason to exist in CAD today.

WHAT GETS BUILT, and it is deliberately only what the model specifies:

    Aft gas seal            dia 74.8 x 4.8 G-10, 2 x dia 4.0 feed-through, 2 x dia 5.5 U-bolt
    Internal bulkhead       dia 74.8 x 4.8 G-10, 1 x dia 6.0 conduit,      2 x dia 5.5 U-bolt

WHAT DOES NOT GET BUILT, listed so that nobody reads the absence as a decision: the charge
well and its terminal block, the U-bolt itself and its backing plate, the epoxy fillet, and
the RTV in the feed-throughs. The backing plate is the one that matters -- it is STRUCTURE
(`seal.point_load_stress` goes as the log of the plate-to-footprint radius ratio) and it is
not here, so this part is not yet the whole harness anchor.

FRAME. Origin on the disc's AFT face, +Z aft, so the seal's origin lands at Z = 142.900 in
the module assembly -- the module's aft face, a number you can read off the status bar and
check rather than an offset you have to compute. That is the bearing Part Studio's
convention (origin on the outboard face so it lands at R 39.700) applied to a flat part.

ONLY THE SEAL IS ASSEMBLED. The internal bulkhead sits 240 mm further aft, in a recovery bay
that is not modelled, so putting it in `Assembly 1` would place it somewhere it is not.
It is built and left as a part, which is the honest state.

CAUTION, inherited from make_bearing_cad.py: this script does not delete anything. DELETE
/elements returns 403 on a read-only-flagged key even though POST creates happily, so a
rebuild means deleting the Part Studio in the browser first. And per correction 24, FINISH
A PART STUDIO BEFORE PUTTING IT IN AN ASSEMBLY -- rebuilding one orphans every instance,
and Onshape heals an orphan to an empty partId that keeps its name and weighs nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import onshape_build as ob
from design import seal
from design.configure import baseline, evaluate
from design.onshape import get, post

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
ASSEMBLY = "ff7e2e472d6694342f892f9c"
MM = 1000.0

# The one material fact this project has ever committed to (configure.py).
G10_DENSITY = 1850.0

PROP_NAME = "57f3fb8efa3416c06701d60d"
PROP_MATERIAL = "57f3fb8efa3416c06701d615"

# The canard module's aft face, in the module Part Studio's own frame. Read off the Part
# Studio's bounding box rather than typed: lowZ 0.000 is the forward face and highZ is the
# aft one. Verified against design/configure.py's 142.92 mm module length.
MODULE_AFT_FACE_M = 0.1429

SPECS = [
    ("Aft gas seal (G-10 4.8)", "Aft gas seal (G-10, dia 74.8 x 4.8)", "seal"),
    ("Recovery internal bulkhead (G-10 4.8)",
     "Recovery internal bulkhead (G-10, dia 74.8 x 4.8)", "internal"),
]


def find_element(name: str):
    for e in get(f"/documents/d/{DOC}/w/{WS}/elements"):
        if e["name"] == name:
            return e
    return None


def add(feature: dict, element: str) -> str:
    r = post(f"/partstudios/d/{DOC}/w/{WS}/e/{element}/features", {"feature": feature})
    return r["feature"]["featureId"]


def build(element: str, r: seal.SealResult) -> None:
    """The disc, then every hole as its own cut."""
    t = r.bulkhead.thickness * MM
    od = r.bulkhead.bore_diameter * MM

    # 1. The disc, growing FORWARD from the origin, so +Z is aft and the origin sits on the
    #    aft face.
    sk = add(ob.sketch("Disc OD", "Top",
                       [ob.circle(0.0, 0.0, od / 2000.0, "od")]), element)
    add(ob.extrude("Bulkhead disc", [ob.sketch_regions(sk)],
                   depth_mm=t, opposite=True), element)

    # 2. Every hole as a SEPARATE cut, each overshooting both faces by 1 mm.
    #    Separate, because concentric or multiple regions in one sketch make which region an
    #    extrude takes depend on a filter flag that is easy to get wrong and impossible to
    #    see afterwards. Overshooting, because a REMOVE landing exactly on a face is
    #    degenerate -- Part Studio 1's `Extrude 4` cut nothing at all for that reason
    #    (docs/01 correction 7).
    over = 1.0
    for h in seal.hole_layout(r):
        sk = add(ob.sketch(h.name, "Top",
                           [ob.circle(h.x, h.y, h.diameter / 2.0, "hole")]), element)
        add(ob.extrude(h.name, [ob.sketch_regions(sk)],
                       depth_mm=t + 2 * over, opposite=True,
                       start_offset_mm=over, start_offset_opposite=False,
                       operation="REMOVE"), element)


def name_and_material(element: str, part_name: str) -> None:
    """Name it and give it a density, as part of the BUILD.

    Not an instruction to go and do it later. A part with no material weighs 0.0000 g and
    still answers every mass query with a number, which is how this document once reported
    175 g for a 260 g module. Correction 22 is the same lesson from the other end: a LIBRARY
    material returns density 0 through the metadata API, so an audit reading part metadata
    sees nothing wrong. Custom material, every time.
    """
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


def verify(element: str, r: seal.SealResult) -> None:
    """Volume against the analytic disc-less-holes, to the micron.

    THE ONLY PROOF THE HOLES ACTUALLY CUT. A solid disc and a drilled one differ by 0.6% of
    mass here, which no mass check would ever notice -- the bearing's bore was caught the
    same way and only because the figure was compared against an exact annulus rather than
    against a tolerance. If this disagrees, the holes did not cut; do not adjust the
    tolerance.
    """
    import math
    want = math.pi * r.bulkhead.radius**2 * r.bulkhead.thickness
    for h in seal.hole_layout(r):
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
    print(f"    solid would be {solid:8.3f} mm^3 -- the holes are {solid - want:.1f} mm^3, "
          f"{(solid - want) / solid * 100:.1f}%")
    if abs(have - want) > 0.01:
        raise SystemExit("VOLUME MISMATCH -- the holes did not cut as drawn")
    mass = mp["bodies"][pid]["mass"][0] * 1000.0
    print(f"    mass         {mass:10.3f} g at {G10_DENSITY:.0f} kg/m^3")
    if mass < 1e-6:
        raise SystemExit("mass is zero -- the material did not take")


def main() -> None:
    ev = evaluate(baseline())
    results = {
        "seal": seal.from_evaluation(ev),
        "internal": seal.internal_bulkhead_from_evaluation(ev),
    }

    for element_name, part_name, key in SPECS:
        r = results[key]
        chk = seal.check_hole_layout(r)
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

    print("\nOnly the aft gas seal belongs in Assembly 1 -- the internal bulkhead sits")
    print("240 mm further aft in a recovery bay that is not modelled. Place with")
    print("  python scripts/place_bulkhead.py")


if __name__ == "__main__":
    main()
