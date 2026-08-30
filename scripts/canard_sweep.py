"""Drive the canard deflection in the Onshape model, and check the sweep for interference.

    python scripts/canard_sweep.py                 # sweep the deflection limit, leave at 0
    python scripts/canard_sweep.py --set 8         # park the model at +8 deg
    python scripts/canard_sweep.py --render        # also save shaded views to out/cad/

docs/05 lists the interference check as NOT RUN, and it could not be run: a Part Studio is
static, so there was nothing to sweep. The `canardDeflection` custom feature in the
`Canard articulation` Feature Studio (source in cad/canard_articulation.fs) makes the
panels and shafts actually turn about their hinge axes, and this script drives it.

SAFETY. Every write is followed by a part count. A custom feature that fails to compile
can regenerate to an EMPTY Part Studio while still reporting featureStatus OK -- that
happened during development, and the model was recovered only because the failure was
noticed immediately. If the count is ever wrong, this script removes the feature and
restores the model before doing anything else.
"""

from __future__ import annotations

import argparse
import base64
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from urllib.parse import quote

from design.onshape import call, get, post

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
PART_STUDIO = "dfb730308a9933e911684b5c"
FEATURE_STUDIO = "8fa6ee54161173d35b56d1c8"
ASSEMBLY = "ff7e2e472d6694342f892f9c"

HINGE_STATION_MM = 68.27
EXPECTED_PARTS = 13
FEATURE_TYPE = "canardDeflection"

OUT = Path(__file__).resolve().parent.parent / "out" / "cad"


def clear() -> None:
    for f in get(f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}/features")["features"]:
        if f.get("featureType") == FEATURE_TYPE:
            call("DELETE", f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}"
                           f"/features/featureid/{quote(f['featureId'], safe='')}")


def set_deflection(deg: float) -> None:
    """Park the model at `deg`. Replaces the feature rather than editing it: editing a
    custom feature in place needs its namespace microversion to match exactly, and
    replacing is both simpler and idempotent."""
    clear()
    mv = get(f"/documents/d/{DOC}/w/{WS}/currentmicroversion")["microversion"]
    feature = {"feature": {
        "btType": "BTMFeature-134", "featureType": FEATURE_TYPE,
        "name": f"Canard deflection ({deg:+g} deg)",
        "namespace": f"e{FEATURE_STUDIO}::m{mv}",
        "parameters": [
            {"btType": "BTMParameterQuantity-147", "parameterId": "deflection",
             "expression": f"{deg} deg"},
            {"btType": "BTMParameterQuantity-147", "parameterId": "hingeStation",
             "expression": f"{HINGE_STATION_MM} mm"},
        ]}}
    fid = post(f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}/features",
               feature)["feature"]["featureId"]
    state = get(f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}/features")
    status = state["featureStates"].get(fid, {}).get("featureStatus")
    parts = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}")
    if status != "OK" or len(parts) != EXPECTED_PARTS:
        clear()
        raise SystemExit(
            f"REFUSING to leave the model in this state: status={status}, "
            f"{len(parts)} parts (expected {EXPECTED_PARTS}). Feature removed; "
            f"the Part Studio is back as it was.")


def panel_geometry() -> dict[str, tuple[float, float]]:
    """Y-extent of each canard panel -- the direct read-out of how far it has swung."""
    out = {}
    for p in get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}"):
        if not p["name"].startswith("Canard panel"):
            continue
        b = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}/partid/{p['partId']}/boundingboxes")
        out[p["name"]] = (b["lowY"] * 1000, b["highY"] * 1000)
    return out


def render(tag: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    r = call("GET", f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/shadedviews",
             query={"viewMatrix": "1,0,0,0,0,1,0,0,0,0,1,0", "outputHeight": 900,
                    "outputWidth": 1200, "pixelSize": 0, "useAntiAliasing": "true"})
    path = OUT / f"canard_sweep_{tag}.png"
    path.write_bytes(base64.b64decode(r["images"][0]))
    print(f"    wrote {path}")


def model_shaft() -> dict:
    """Diameter and inboard end of canard shaft 0, off the API."""
    for pt in get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}"):
        if pt["name"].startswith("Canard shaft 0"):
            b = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}"
                    f"/partid/{pt['partId']}/boundingboxes")
            return {"inboard": b["lowX"] * 1000, "outboard": b["highX"] * 1000,
                    "dia": (b["highY"] - b["lowY"]) * 1000}
    raise SystemExit("no 'Canard shaft 0' part in the Part Studio")


def model_wall_bore() -> float:
    """The wall bore diameter, off its own sketch -- which is the point: it HAS its own."""
    for f in get(f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}/features")["features"]:
        if not f.get("name", "").startswith("Wall bore sketch"):
            continue
        for c in f.get("constraints", []):
            if c.get("constraintType") == "DIAMETER":
                for q in c["parameters"]:
                    if q.get("parameterId") == "length":
                        return float(q["expression"].split()[0])
    raise SystemExit("no 'Wall bore sketch' feature -- run scripts/make_hinge_stack.py")


def model_servo_seat() -> float:
    """Radius the servo output face actually sits at, off the assembly."""
    a = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}")["rootAssembly"]
    names = {i["id"]: i["name"] for i in a["instances"]}
    for o in a["occurrences"]:
        if len(o["path"]) != 1:
            continue
        if names[o["path"][0]].startswith("Servo case"):
            t = o["transform"]
            return (t[3] ** 2 + t[7] ** 2) ** 0.5 * 1000
    raise SystemExit("no servo case instance in Assembly 1")


def clearance_report(limit_deg: float = 8.0) -> None:
    """What can touch what, through the full deflection.

    docs/05 poses this as a sweep: "rotate a panel through +/-8 deg and check the horn,
    shaft, bay and neighbouring servo clear." Having actually built the sweep, most of it
    turns out not to need one, and the reason is worth writing down because it is a
    property of the ARRANGEMENT rather than of the numbers:

      - The hinge axis is radial, and the shaft is coaxial with it. A body of revolution
        turning on its own axis sweeps nothing. The shaft cannot foul at any angle.
      - Every point of a canard panel keeps its distance from the ROCKET axis when the
        panel turns, because that distance is measured along the hinge axis and rotation
        about an axis preserves position along it. The panel starts entirely outboard of
        the tube and therefore stays there, at every deflection.
      - The servos live entirely inboard of the wall, the panels entirely outboard. The
        two sets never share a radius.

    So the interference question has a structural answer -- nothing can foul -- and the
    real risks are the two FITS that a bounding-box model could not express: the shaft in
    its pass-through hole, and the spline in the panel root. Both are checked below, and
    both want attention.

    The panel geometry comes from design/configure.py so it cannot drift from the model.
    """
    import math as _m

    from design import hinge
    from design.configure import baseline, build_vehicle
    from design.packaging import SERVO_GEOMETRY

    p = baseline()
    r = build_vehicle(p)
    can = r.canards
    g = SERVO_GEOMETRY[p.servo]

    od = p.outer_diameter * 1000
    bore = (p.outer_diameter - 2 * p.wall_thickness) * 1000
    root_face = 40.20                                  # 0.5 mm proud of the tube
    hinge_z = HINGE_STATION_MM
    d = _m.radians(limit_deg)

    print("  PANEL vs TUBE")
    # Sample the panel's four corners plus its root edge and swing them. x -- the distance
    # along the hinge axis -- is invariant under the rotation, so the closest any panel
    # point gets to the rocket axis is its own root radius, at any deflection.
    root_le = can.x_root_le * 1000 if hasattr(can, "x_root_le") else 37.71
    corners = [(root_face, s * can.thickness * 500, z)
               for s in (-1, 1)
               for z in (root_le, root_le + can.root_chord * 1000)]
    worst = min(
        _m.hypot(x, y * _m.cos(dd) - (z - hinge_z) * _m.sin(dd))
        for (x, y, z) in corners
        for dd in (0.0, d, -d)
    )
    print(f"    panel root face at R                        {root_face:7.3f} mm")
    print(f"    tube outside radius                         {od / 2:7.3f} mm")
    print(f"    closest panel point to the axis, swept      {worst:7.3f} mm")
    print(f"    -> clearance, worst case over +/-{limit_deg:.0f} deg      "
          f"{worst - od / 2:+7.3f} mm")
    print("    (rotation cannot reduce this: it preserves distance along the hinge axis,")
    print("     which is the radial coordinate. The 0.5 mm standoff is an assembly")
    print("     allowance, not a swept-clearance one.)")

    # The next three blocks used to print constants. They now READ THE MODEL and compare
    # it against design/hinge.py, because every one of those constants was wrong within a
    # month of being typed, and a script that restates a number cannot notice that.
    stack = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, g)

    print("\n  SHAFT vs BEARING SEAT")
    shaft = model_shaft()
    bore = model_wall_bore()
    print(f"    canard shaft diameter, from the model       {shaft['dia']:7.3f} mm")
    print(f"    wall bore diameter, from the model          {bore:7.3f} mm")
    print(f"    bearing OD it seats                         {stack.bearing_od * 1000:7.3f} mm")
    print(f"    -> seat fit                                 "
          f"{bore - stack.bearing_od * 1000:+7.3f} mm  (interference, as a press fit wants)")
    print(f"    -> running clearance, journal in bearing    "
          f"{stack.running_clearance * 1000:+7.3f} mm")
    print("    Until Aug 2026 both of the first two numbers were 5.000, because the cut")
    print("    reused the shaft's own sketch. Right for POSITION, wrong for FIT, and")
    print("    invisible to every interference check, since zero clearance is not an")
    print("    interference. The bore now carries its own dimension so the two cannot")
    print("    track each other again. See design/hinge.py.")

    print("\n  SPLINE vs SHAFT SLEEVE")
    seat = model_servo_seat()
    tip = seat + g.shaft_proud_of_top * 1000
    print(f"    servo output face seats at R                {seat:7.3f} mm")
    print(f"    spline stands proud of it                   "
          f"{g.shaft_proud_of_top * 1000:7.3f} mm")
    print(f"    -> spline tip reaches R                     {tip:7.3f} mm")
    print(f"    shaft sleeve inboard end at R               {shaft['inboard']:7.3f} mm")
    print(f"    -> engagement in the sleeve's spline socket "
          f"{tip - shaft['inboard']:+7.3f} mm "
          f"({(tip - shaft['inboard']) / (g.shaft_proud_of_top * 1000) * 100:.0f}% of the spline)")
    print(f"    panel root face at R                        {root_face:7.3f} mm")
    print(f"    -> spline relative to the panel root        {tip - root_face:+7.3f} mm")
    print("    That last number was +0.185 mm, and it was read as 'direct drive is not")
    print("    available', which was right. What it also meant was that the whole radial")
    print("    budget between the servo and the panel was 3.015 mm with 2.300 of wall in")
    print("    it -- no room for a bearing, so there was no bearing. The servo has since")
    print("    moved 4.000 mm inboard to make that room.")

    print("\n  SERVO vs SERVO, AND THE CENTRAL VOID")
    arc = 2 * _m.pi * seat / p.n_canards
    print(f"    arc between servo centres at the seat       {arc:7.2f} mm")
    print(f"    servo case width                            "
          f"{g.case_width * 1000:7.2f} mm")
    print(f"    -> circumferential gap                      {arc - g.case_width * 1000:+7.2f} mm")
    inner = seat - g.depth_from_top * 1000
    print(f"    cable boss inner end at R                   {inner:7.2f} mm")
    print(f"    clear bore down the middle, over that band  {2 * inner:7.2f} mm")
    print(f"    -> corner-to-corner between adjacent bosses "
          f"{inner - g.case_width * 500:+7.2f} mm")
    print(f"    clear bore alongside the cases              "
          f"{2 * (seat - g.case_height * 1000):7.2f} mm")
    print("    That void is what the wiring lives in, and it is the price of the 4 mm the")
    print("    servo moved: every band lost the same 8 mm, because the whole servo moved.")
    print("    It was 58 mm when the servo was a block on the wrong axis.")

    # The whole point of reading the model is to be able to disagree with it.
    want = {
        "shaft inboard end": (shaft["inboard"], stack.sleeve_inboard * 1000),
        "shaft diameter": (shaft["dia"], stack.journal_dia * 1000),
        "wall bore": (bore, stack.wall_bore_dia * 1000),
        "servo output face": (seat, stack.servo_output_face * 1000),
    }
    bad = {k: v for k, v in want.items() if abs(v[0] - v[1]) > 1e-3}
    print("")
    if bad:
        for k, (got, exp) in bad.items():
            print(f"    MODEL DISAGREES WITH design/hinge.py: {k} is {got:.3f}, "
                  f"should be {exp:.3f}")
    else:
        print("    model agrees with design/hinge.py on every station above.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=float, default=None,
                    help="park the model at this deflection, in degrees")
    ap.add_argument("--render", action="store_true", help="save a shaded view per station")
    ap.add_argument("--limit", type=float, default=8.0, help="deflection limit, degrees")
    args = ap.parse_args()

    if args.set is not None:
        set_deflection(args.set)
        print(f"model parked at {args.set:+g} deg")
        return

    print(f"SWEEPING THE CANARDS THROUGH +/-{args.limit:g} DEG\n")
    for deg in (0.0, args.limit, -args.limit, 0.0):
        set_deflection(deg)
        geo = panel_geometry()
        print(f"  delta = {deg:+6.1f} deg")
        for name in sorted(geo):
            lo, hi = geo[name]
            print(f"      {name:22s} Y {lo:8.2f} .. {hi:8.2f} mm")
        if args.render:
            render(f"{deg:+.0f}".replace("+", "p").replace("-", "m"))
    print("\nmodel left at 0 deg\n")

    print("CLEARANCES")
    clearance_report()


if __name__ == "__main__":
    main()
