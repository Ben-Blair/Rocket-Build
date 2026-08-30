"""Put the selected canard hinge stack into the Onshape model.

    python scripts/make_hinge_stack.py --check      # read the model, change nothing
    python scripts/make_hinge_stack.py --shaft      # shaft: dia 6, and out of the servo
    python scripts/make_hinge_stack.py --bore       # wall bore: a bearing seat, not a copy
    python scripts/make_hinge_stack.py --servos     # move the four servos 4 mm inboard
    python scripts/make_hinge_stack.py --all

The design is in design/hinge.py and the argument for it is in out/hinge_report.txt. This
script only applies it. Three things change in the CAD:

  1. `Extrude 3` starts at R 33.485 instead of R 29.400 and is 6.715 long instead of 10.8,
     so the shaft stops at the servo's output face instead of running 7.785 mm into the
     servo case and 3.015 mm into its output spline. That overlap was real, solid-on-solid,
     and present at zero deflection -- the swept interference check did not see it because
     the sweep asked whether ROTATION caused a collision.

  2. `Sketch 3`'s circle goes from dia 5 to dia 6, and a NEW sketch and cut open the wall
     pass-through to dia 7.975 -- a seat for a dia 6 / dia 8 plain bearing. The old cut
     reused the shaft's own sketch, which is why the hole and the shaft were the same size
     to three decimal places. The new cut has its own dimension so they cannot track each
     other again.

  3. The four servo instances in `Assembly 1` move from R 37.185 to R 33.185.

SAFETY, and it is not decoration. docs/05 records that this Part Studio's circular pattern
silently drops material assignments from its copies, which once made the module read
0.175 kg instead of 0.260, and that a bad feature can regenerate to an EMPTY Part Studio
while still reporting featureStatus OK. So every write here is followed by a part count, a
feature-status sweep AND a mass comparison against a recorded expectation, and anything
unexpected restores the feature parameters that were there before.
"""

from __future__ import annotations

import argparse
import copy
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
ASSEMBLY = "ff7e2e472d6694342f892f9c"

EXPECTED_PARTS = 13
# Part Studio 1 total, measured before any of this ran. The pattern's dropped-material bug
# takes this to about 175 g, so a large fall means the materials went, not the geometry.
MASS_BEFORE_G = 259.85646
MASS_TOLERANCE_G = 3.0

MM = 1000.0
PS = f"/partstudios/d/{DOC}/w/{WS}/e/{PART_STUDIO}"


# ------------------------------------------------------------------------------------
# reading
# ------------------------------------------------------------------------------------

def feature_list() -> dict:
    return get(f"{PS}/features")


def by_name(fl: dict, name: str) -> dict:
    for f in fl["features"]:
        if f.get("name") == name:
            return f
    raise SystemExit(f"no feature named {name!r} in the Part Studio")


def param(feature: dict, pid: str) -> dict:
    for p in feature["parameters"]:
        if p.get("parameterId") == pid:
            return p
    raise SystemExit(f"{feature.get('name')} has no parameter {pid!r}")


def parts() -> list[dict]:
    return get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}")


def part_mass_g(part_id: str) -> float:
    mp = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}/partid/{part_id}/massproperties")
    return mp["bodies"][part_id]["mass"][0] * 1000.0


def total_mass_g() -> float:
    return sum(part_mass_g(p["partId"]) for p in parts())


def bbox_mm(part_id: str) -> dict:
    b = get(f"/parts/d/{DOC}/w/{WS}/e/{PART_STUDIO}/partid/{part_id}/boundingboxes")
    return {k: v * MM for k, v in b.items() if k[:3] in ("low", "hig")}


def verify(what: str) -> None:
    """Part count, every feature's status, and the mass. In that order, because an empty
    Part Studio still answers the mass question with a number."""
    fl = feature_list()
    bad = {fid: st.get("featureStatus")
           for fid, st in fl["featureStates"].items()
           if st.get("featureStatus") not in ("OK", "WARNING")}
    p = parts()
    if bad:
        raise RuntimeError(f"{what}: features not OK: {bad}")
    if len(p) != EXPECTED_PARTS:
        raise RuntimeError(f"{what}: {len(p)} parts, expected {EXPECTED_PARTS}")
    m = total_mass_g()
    if abs(m - MASS_BEFORE_G) > MASS_TOLERANCE_G:
        raise RuntimeError(
            f"{what}: Part Studio mass {m:.3f} g against {MASS_BEFORE_G:.3f} g before "
            f"(tolerance {MASS_TOLERANCE_G} g). If it fell a long way, the circular "
            f"pattern dropped the material assignments again -- see docs/05.")
    print(f"    verified after {what}: {len(p)} parts, all features OK, {m:.3f} g")


# ------------------------------------------------------------------------------------
# writing
# ------------------------------------------------------------------------------------

def update_feature(fl: dict, feature: dict) -> None:
    fid = feature["featureId"]
    call("POST", f"{PS}/features/featureid/{quote(fid, safe='')}",
         {"feature": feature,
          "serializationVersion": fl.get("serializationVersion"),
          "sourceMicroversion": fl.get("sourceMicroversion"),
          "rejectMicroversionSkew": False})


def set_quantity(feature_name: str, pid: str, expression: str) -> tuple[str, str]:
    """Set one quantity parameter. Returns (pid, old expression) so it can be put back."""
    fl = feature_list()
    f = copy.deepcopy(by_name(fl, feature_name))
    p = param(f, pid)
    old = p["expression"]
    if old == expression:
        print(f"    {feature_name}.{pid} already {expression}")
        return pid, old
    p["expression"] = expression
    print(f"    {feature_name}.{pid}  {old} -> {expression}")
    update_feature(fl, f)
    return pid, old


def set_sketch_diameter(feature_name: str, dia_m: float) -> float:
    """Set the DIAMETER constraint and the circle's own radius together.

    Both, because the sketch carries the geometry and the constraint separately and a
    solve that disagrees with its own geometry is exactly the kind of quiet wrongness this
    model has already produced twice.
    """
    fl = feature_list()
    f = copy.deepcopy(by_name(fl, feature_name))
    old = None
    for c in f.get("constraints", []):
        if c.get("constraintType") != "DIAMETER":
            continue
        for p in c["parameters"]:
            if p.get("parameterId") == "length":
                old = p["expression"]
                p["expression"] = f"{dia_m * MM:g} mm"
    for e in f.get("entities", []):
        g = e.get("geometry", {})
        if g.get("btType") == "BTCurveGeometryCircle-115":
            g["radius"] = dia_m / 2.0
    if old is None:
        raise SystemExit(f"{feature_name}: no DIAMETER constraint found")
    print(f"    {feature_name} diameter  {old} -> {dia_m * MM:g} mm")
    update_feature(fl, f)
    return old


# ------------------------------------------------------------------------------------
# steps
# ------------------------------------------------------------------------------------

def step_shaft(stack: hinge.HingeStack) -> None:
    """The shaft becomes a dia 6 sleeve that stops at the servo's output face."""
    print("\nshaft")
    before = [p for p in parts() if p["name"].startswith("Canard shaft 0")]
    undo = []
    try:
        undo.append(("Extrude 3", *set_quantity(
            "Extrude 3", "startOffsetDistance",
            f"{stack.sleeve_inboard * MM:.3f} mm")))
        undo.append(("Extrude 3", *set_quantity(
            "Extrude 3", "depth", f"{stack.sleeve_length * MM:.3f} mm")))
        old_dia = set_sketch_diameter("Sketch 3", stack.journal_dia)
        undo.append(("Sketch 3", "DIAMETER", old_dia))
        verify("shaft")
    except Exception:
        print("    FAILED -- restoring")
        for name, pid, old in reversed(undo):
            if pid == "DIAMETER":
                set_sketch_diameter(name, float(old.split()[0]) / MM)
            else:
                set_quantity(name, pid, old)
        raise
    b = bbox_mm([p for p in parts() if p["name"].startswith("Canard shaft 0")][0]["partId"])
    print(f"    shaft 0 now X[{b['lowX']:.3f},{b['highX']:.3f}] "
          f"Y[{b['lowY']:.3f},{b['highY']:.3f}]  (was "
          f"X[{29.4:.3f},{40.2:.3f}] Y[-2.500,2.500])")


def create_feature(feature: dict, label: str) -> str:
    fl = feature_list()
    f = copy.deepcopy(feature)
    f.pop("featureId", None)
    r = post(f"{PS}/features",
             {"feature": f,
              "serializationVersion": fl.get("serializationVersion"),
              "sourceMicroversion": fl.get("sourceMicroversion"),
              "rejectMicroversionSkew": False})
    fid = r["feature"]["featureId"]
    print(f"    created {label}  ({fid})")
    return fid


def delete_feature(fid: str) -> None:
    call("DELETE", f"{PS}/features/featureid/{quote(fid, safe='')}")


def model_bore_dia(fl: dict) -> float:
    for f in fl["features"]:
        if not f.get("name", "").startswith("Wall bore sketch"):
            continue
        for c in f.get("constraints", []):
            if c.get("constraintType") == "DIAMETER":
                for q in c["parameters"]:
                    if q.get("parameterId") == "length":
                        return float(q["expression"].split()[0])
    raise SystemExit("no wall bore sketch found")


def step_bore(stack: hinge.HingeStack) -> None:
    """The wall pass-through becomes a bearing seat with its OWN dimension.

    The old cut reused `Sketch 3` -- the shaft's own sketch -- which is why the hole and
    the shaft were dia 5.000 and dia 5.000. Position was right and fit was impossible, and
    nothing could ever report it: zero clearance is not an interference. The fix is not a
    bigger number in the same place, it is a SEPARATE dimension, so that the next person to
    change the shaft diameter does not silently change the bearing seat with it.

    Three new features at the end of the tree rather than an edit to `Extrude 4`, because
    a new sketch has to sit BEFORE the cut that uses it and the API appends. `Extrude 4`
    stays, now cutting dia 6 coincident with the shaft; this cut opens it to the seat.
    """
    print("\nwall bore")
    dia = stack.wall_bore_dia
    fl = feature_list()
    # Idempotent, because this script has to be safe to re-run: a second identical cut
    # removes nothing, regenerates as INFO, and leaves a duplicate in the tree that the
    # next person has to work out the meaning of.
    existing = [f for f in fl["features"]
                if f.get("name", "").startswith("Wall bore")]
    if existing:
        print(f"    already present: {', '.join(f['name'] for f in existing)}")
        print(f"    wall bore is dia {model_bore_dia(fl):.3f}; leaving it alone")
        return
    sk = copy.deepcopy(by_name(fl, "Sketch 3"))
    sk["name"] = f"Wall bore sketch (dia {dia * MM:.3f} bearing seat)"
    for c in sk.get("constraints", []):
        if c.get("constraintType") == "DIAMETER":
            for q in c["parameters"]:
                if q.get("parameterId") == "length":
                    q["expression"] = f"{dia * MM:.4f} mm"
    for e in sk.get("entities", []):
        g = e.get("geometry", {})
        if g.get("btType") == "BTCurveGeometryCircle-115":
            g["radius"] = dia / 2.0

    made: list[str] = []
    try:
        sk_id = create_feature(sk, sk["name"])
        made.append(sk_id)

        cut = copy.deepcopy(by_name(fl, "Extrude 4"))
        cut["name"] = "Wall bore (bearing seat)"
        ent = param(cut, "entities")
        ent["queries"] = [{
            "btType": "BTMIndividualSketchRegionQuery-140",
            "featureId": sk_id,
            "queryString": f'query = qSketchRegion(id + "{sk_id}", true);',
            "filterInnerLoops": True,
            "queryStatement": None,
        }]
        cut_id = create_feature(cut, cut["name"])
        made.append(cut_id)

        pat = copy.deepcopy(by_name(fl, "Circular pattern 1"))
        pat["name"] = "Wall bore pattern"
        param(pat, "instanceFunction")["featureIds"] = [cut_id]
        param(pat, "entities")["queries"] = []
        pat_id = create_feature(pat, pat["name"])
        made.append(pat_id)

        verify("wall bore")
    except Exception:
        print("    FAILED -- deleting what was created")
        for fid in reversed(made):
            try:
                delete_feature(fid)
            except Exception as e:  # noqa: BLE001
                print(f"    could not delete {fid}: {e}")
        raise

    tube = [p for p in parts() if p["name"] == "Canard module tube"][0]
    print(f"    tube now {part_mass_g(tube['partId']):.4f} g "
          f"(dia {dia * MM:.3f} seat, {stack.seat_fit * MM:+.3f} mm on a "
          f"dia {stack.bearing_od * MM:.3f} bearing)")


ASM = f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}"
EXPECTED_INSTANCES = 21
EXPECTED_ASM_FEATURES = 5


def occurrences() -> tuple[dict[str, str], list[dict]]:
    a = get(ASM)["rootAssembly"]
    names = {i["id"]: i["name"] for i in a["instances"]}
    return names, [o for o in a["occurrences"] if len(o["path"]) == 1]


def servo_radius() -> dict[str, float]:
    """Radial station of every servo occurrence, keyed by name."""
    names, occ = occurrences()
    out = {}
    for o in occ:
        n = names[o["path"][0]]
        if not n.startswith("Servo"):
            continue
        t = o["transform"]
        out[n] = (t[3] ** 2 + t[7] ** 2) ** 0.5
    return out


def step_servos(stack: hinge.HingeStack) -> None:
    """Move the four servos inboard so there is somewhere to put the bearing.

    This is the change that actually costs something, and it is worth being explicit about
    why it is the cheap one. Between the servo output face and the panel root there were
    3.015 mm. A plain bearing that can carry a 25 N panel load on a 29 mm overhang needs
    about 4.5 mm of length, because the peak pressure under an overhung load goes as
    1/L^2. Something had to move. Moving the panel outboard would change frozen
    aerodynamics -- planform area, exposed span, and every study downstream of them.
    Moving the servo spends central void, which is a budget line. So the servo moves.

    The four rigid groups have to come out first: the servo cases are grouped WITH the
    tube and the splines are grouped with the panels, so transforming an occurrence in
    place would drag the airframe. They are saved verbatim and put back afterwards, which
    also preserves the membership that the mates will eventually need.
    """
    print("\nservos")
    target = stack.servo_output_face
    before = servo_radius()
    if not before:
        raise SystemExit("no servo instances in the assembly")
    # Measure where the servos ARE, do not assume where they started. A relative move
    # computed from a constant is a step that silently doubles when the script is run
    # twice, and this script is meant to be safe to re-run.
    seat = before["Servo case + flange (KST X08 Plus) <1>"]
    move = round(seat - target, 6)
    if abs(move) < 1e-6:
        print(f"    servo output face already at R {target * MM:.3f}; nothing to move")
        return
    print(f"    moving 4 servos {move * MM:.3f} mm inboard, output face R "
          f"{seat * MM:.3f} -> {target * MM:.3f}")

    saved = get(f"{ASM}/features")
    feats = saved.get("features", [])
    if len(feats) != EXPECTED_ASM_FEATURES:
        raise SystemExit(f"expected {EXPECTED_ASM_FEATURES} assembly features, "
                         f"found {len(feats)}; refusing to touch the assembly")

    print(f"    removing {len(feats)} rigid groups so the occurrences are free to move")
    for f in feats:
        call("DELETE", f"{ASM}/features/featureid/{quote(f['featureId'], safe='')}")

    try:
        names, occ = occurrences()
        moved = 0
        for o in occ:
            n = names[o["path"][0]]
            if not n.startswith("Servo"):
                continue
            t = o["transform"]
            r = (t[3] ** 2 + t[7] ** 2) ** 0.5
            if r < 1e-9:
                raise RuntimeError(f"{n} sits on the rocket axis; no radial direction")
            ux, uy = t[3] / r, t[7] / r
            dx, dy = -ux * move, -uy * move
            post(f"{ASM}/occurrencetransforms", {
                "occurrences": [{"path": o["path"]}],
                "transform": [1.0, 0.0, 0.0, dx,
                              0.0, 1.0, 0.0, dy,
                              0.0, 0.0, 1.0, 0.0,
                              0.0, 0.0, 0.0, 1.0],
                "isRelative": True,
            })
            moved += 1
        if moved != 12:
            raise RuntimeError(f"moved {moved} servo occurrences, expected 12")

        after = servo_radius()
        for n, r in sorted(after.items()):
            delta = r - before[n]
            if abs(delta + move) > 1e-6:
                raise RuntimeError(
                    f"{n} moved {delta * MM:+.4f} mm, expected {-move * MM:+.4f}")
        print(f"    all 12 servo occurrences moved {-move * MM:+.3f} mm radially")
    finally:
        print(f"    restoring {len(feats)} rigid groups")
        for f in feats:
            g = copy.deepcopy(f)
            g.pop("featureId", None)
            post(f"{ASM}/features", {"feature": g})

    a = get(ASM)["rootAssembly"]
    nf = len(get(f"{ASM}/features").get("features", []))
    if len(a["instances"]) != EXPECTED_INSTANCES or nf != EXPECTED_ASM_FEATURES:
        raise RuntimeError(f"assembly ended with {len(a['instances'])} instances and "
                           f"{nf} features")
    mp = get(f"{ASM}/massproperties")
    print(f"    assembly: {len(a['instances'])} instances, {nf} groups, "
          f"{mp['mass'][0] * 1000:.3f} g, CoM Z {mp['centroid'][2] * MM:.3f} mm")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--shaft", action="store_true")
    ap.add_argument("--bore", action="store_true")
    ap.add_argument("--servos", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not any((a.check, a.shaft, a.bore, a.servos, a.all)):
        print(__doc__)
        return

    p = baseline()
    r = build_vehicle(p)
    stack = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness,
                           SERVO_GEOMETRY[p.servo])

    print(f"target stack: sleeve R {stack.sleeve_inboard * MM:.3f} -> "
          f"{stack.panel_root * MM:.3f}, dia {stack.journal_dia * MM:.3f}; "
          f"wall bore dia {stack.wall_bore_dia * MM:.3f}; "
          f"servo output face R {stack.servo_output_face * MM:.3f}")

    if a.check:
        verify("read-only check")
        return
    if a.shaft or a.all:
        step_shaft(stack)
    if a.bore or a.all:
        step_bore(stack)
    if a.servos or a.all:
        step_servos(stack)


if __name__ == "__main__":
    main()
