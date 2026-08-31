"""Cross-check every design number against what the Onshape model actually contains.

    python scripts/verify_cad.py

Each build script verifies its own piece as it writes it. This checks the WHOLE thing
afterwards, from the other direction, and it exists because a session that fixed six real
defects found five of them only by looking somewhere nothing had looked before.

WHAT IT WILL AND WILL NOT CATCH. It compares volumes and the mass tensor -- it will catch a
cut that did not cut, a bore at the wrong diameter, a material that is secretly steel, and
a Part Studio rebuilt out from under its assembly. It will NOT catch two solids occupying
the same space: an interference changes no volume and no mass. For that there is exactly
one tool, and it is not in the API -- open Assembly 1 in the browser, select every
instance, right-click, "Check interference...". `/assemblies/.../interferencecheck` 404s on
v10. Run it after any assembly change; it is the only check that found the tang buried in
the tube wall, the collar boss rim outside the shell, and the retainer bar inside the servo.

The volume tolerances differ on purpose. The bearing, the shaft and the tensor are compared
against EXACT analytic figures and must agree to the micron. The bay and its retainer are
compared against a sum of prisms that does not model where its own webs and bosses overlap,
so those are estimates and the CAD is the truth -- a few percent is expected there, and a
few tens of percent is not.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import bay, hinge
from design.configure import baseline, build_vehicle
from design.control import CANARD_MODULE_CAD
from design.onshape import get
from design.packaging import SERVO_GEOMETRY, SERVOS

DOC = "a8abe36ef209825f56ac7a88"
WS = "30c982b22d7f0010281e2c54"
PART_STUDIO = "dfb730308a9933e911684b5c"
BAY = "7baeb0969c14bbb9352a946f"
BEARING = "0483e6c18e364a5b057b4134"
ASSEMBLY = "ff7e2e472d6694342f892f9c"
MM = 1000.0

EXPECTED_INSTANCES = 34
EXPECTED_ASM_FEATURES = 9


def part_volume(element: str, name_prefix: str) -> float:
    for p in get(f"/parts/d/{DOC}/w/{WS}/e/{element}"):
        if p["name"].startswith(name_prefix):
            mp = get(f"/parts/d/{DOC}/w/{WS}/e/{element}/partid/{p['partId']}/massproperties")
            return mp["bodies"][p["partId"]]["volume"][0]
    raise SystemExit(f"no part starting '{name_prefix}' in element {element}")


def main() -> None:
    p = baseline()
    r = build_vehicle(p)
    g = SERVO_GEOMETRY[p.servo]
    s = hinge.selected(r.diameter / 2.0, r.tubes[1].wall_thickness, g)
    c = hinge.bonded_coupling(s, SERVOS[p.servo].stall_torque, g.spline_teeth)
    j = hinge.selected_root_joint(s, r.canards)
    b = bay.build_bay(s, g, hinge.canard_hinge_station(r) - r.tube_station(1))

    # Shaft: sleeve + tang box, less the part of the tang box that is already inside the
    # round sleeve, less the spline socket. Exact, so it must agree exactly.
    sleeve = math.pi * (s.journal_dia / 2) ** 2 * s.sleeve_length
    tang_box = j.tang_thickness * j.tang_width * (j.engagement + hinge.TANG_MODEL_OVERSHOOT)
    a, rr = j.tang_thickness / 2.0, s.journal_dia / 2.0
    strip = 2.0 * (a * math.sqrt(rr ** 2 - a ** 2) + rr ** 2 * math.asin(a / rr))
    socket = math.pi * (c.socket_dia / 2) ** 2 * c.socket_depth

    mp = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/massproperties")
    t = CANARD_MODULE_CAD

    checks = [
        ("bearing volume, mm^3",
         math.pi * ((s.bearing_od / 2) ** 2
                    - ((s.journal_dia + hinge.BEARING_RUNNING_CLEARANCE) / 2) ** 2)
         * s.bearing_length * 1e9,
         part_volume(BEARING, "Hinge bearing") * 1e9, 1e-3),
        ("shaft volume, mm^3",
         (sleeve + tang_box - hinge.TANG_MODEL_OVERSHOOT * strip - socket) * 1e9,
         part_volume(PART_STUDIO, "Canard shaft 0") * 1e9, 0.5),
        ("bay volume, mm^3",
         (b.volume - b.retainer_volume) * 1e9,
         part_volume(BAY, "Canard bay") * 1e9, 900.0),
        ("one retainer, mm^3",
         b.retainer_volume / 8.0 * 1e9,
         part_volume(BAY, "Servo retainer") * 1e9, 30.0),
        ("module mass, g", t.mass * 1000.0, mp["mass"][0] * 1000.0, 1e-3),
        ("module station, mm", t.station_from_module_face * MM,
         mp["centroid"][2] * MM, 1e-3),
        ("module I_transverse, e-6", t.i_transverse * 1e6, mp["inertia"][0] * 1e6, 1e-2),
        ("module I_roll, e-6", t.i_roll * 1e6, mp["inertia"][8] * 1e6, 1e-2),
    ]

    print(f"  {'quantity':24s} {'design':>12s} {'CAD':>12s} {'delta':>10s} {'':>8s}")
    ok = True
    for name, design, cad, tol in checks:
        d = cad - design
        good = abs(d) <= tol
        ok &= good
        print(f"  {name:24s} {design:12.3f} {cad:12.3f} {d:+10.3f} "
              f"{d / design * 100:+7.2f}%  {'ok' if good else 'MISMATCH'}")

    # Structural facts that a volume cannot express.
    asm = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}")["rootAssembly"]
    orphans = [i["name"] for i in asm["instances"] if not i.get("partId")]
    fl = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/features")
    bad = {f["name"]: fl["featureStates"][f["featureId"]]["featureStatus"]
           for f in fl["features"]
           if fl["featureStates"][f["featureId"]]["featureStatus"] not in ("OK", "WARNING")}
    mates = [f["name"] for f in fl["features"] if f["btType"] == "BTMMate-64"]

    print()
    for label, got, want in (
            ("assembly instances", len(asm["instances"]), EXPECTED_INSTANCES),
            ("assembly features", len(fl["features"]), EXPECTED_ASM_FEATURES),
            ("hand-placed revolute mates", len(mates), 4),
    ):
        good = got == want
        ok &= good
        print(f"  {label:34s} {got:3d}  (want {want}) {'ok' if good else 'MISMATCH'}")
    print(f"  {'instances with no part reference':34s} {len(orphans):3d}  "
          f"{'ok' if not orphans else 'ORPHANED: ' + ', '.join(orphans)}")
    print(f"  {'features not OK':34s} {len(bad):3d}  {bad or 'ok'}")
    ok &= not orphans and not bad

    # The collar rim check, restated against the model's own tube.
    print(f"\n  collar boss rim R {b.collar_rim_radius * MM:.3f} against a tube bored to "
          f"R {s.tube_inner_radius * MM:.3f} -- checked on RADIUS, which is the thing an "
          f"axis-aligned\n  bounding box cannot tell you.")

    print("\n  ALL CONSISTENT" if ok else "\n  SOMETHING DISAGREES")
    print("\n  This does NOT prove there are no interferences -- an interference moves no")
    print("  volume and no mass. Run 'Check interference...' in the browser for that.")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
