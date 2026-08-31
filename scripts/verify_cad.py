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

from design import bay, hinge, seal as seal_mod
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
SEAL = "ba0ba9346b807b5930c70563"
# Where scripts/place_bulkhead.py puts the seal: the module's aft face, in the module frame.
SEAL_STATION = 0.1429  # m
INTERNAL_BULKHEAD = "ae46611f27f5c1d87d47922c"
MM = 1000.0

# 35 since the aft gas seal went in (scripts/place_bulkhead.py). The module assembly is the
# one place this project runs Onshape's own interference check, which is why the seal is
# instanced here and the recovery bay's internal bulkhead -- 240 mm further aft, in a bay
# that has never been modelled -- deliberately is not.
EXPECTED_INSTANCES = 35
EXPECTED_ASM_FEATURES = 9


def seal_analytic_volume(r) -> float:
    """A bulkhead's volume from design/seal.py: the disc, less every hole in the layout."""
    v = math.pi * r.bulkhead.radius**2 * r.bulkhead.thickness
    for h in seal_mod.hole_layout(r):
        v -= math.pi * (h.diameter / 2.0) ** 2 * r.bulkhead.thickness
    return v


def assembly_less_seal(mp: dict) -> dict:
    """The assembly's mass properties with the aft gas seal's contribution removed.

    Mass and centroid are exact. The two inertias are removed by parallel axis about the
    seal's own centroid, using the seal Part Studio's OWN measured tensor -- read back
    rather than modelled, which is how correction 22's stainless shafts were found.

    Roll is a straight subtraction because both parts sit on the same axis. Transverse has
    to move the reference point, since taking mass out of one end shifts the centroid of
    what is left: each part's transverse inertia is referred to the COMBINED centroid, the
    seal's is subtracted there, and the remainder is referred back to its own.
    """
    pid = get(f"/parts/d/{DOC}/w/{WS}/e/{SEAL}")[0]["partId"]
    sp = get(f"/parts/d/{DOC}/w/{WS}/e/{SEAL}/partid/{pid}/massproperties")["bodies"][pid]

    m_all, m_seal = mp["mass"][0], sp["mass"][0]
    m = m_all - m_seal
    z_all, z_seal = mp["centroid"][2], SEAL_STATION + sp["centroid"][2]
    z = (m_all * z_all - m_seal * z_seal) / m

    # Onshape returns the inertia tensor about the part's own centroid, row-major 3x3.
    ix_all, iz_all = mp["inertia"][0], mp["inertia"][8]
    ix_seal, iz_seal = sp["inertia"][0], sp["inertia"][8]

    i_roll = iz_all - iz_seal
    ix_all_c = ix_all + m_all * (z_all - z) ** 2
    ix_seal_c = ix_seal + m_seal * (z_seal - z) ** 2
    i_trans = (ix_all_c - ix_seal_c) - m * 0.0  # already about the remainder's own centroid
    return {"mass": m, "station": z, "i_transverse": i_trans, "i_roll": i_roll}


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

    from design.configure import evaluate as _evaluate
    _ev = _evaluate(p)
    sl = seal_mod.from_evaluation(_ev)
    ib = seal_mod.internal_bulkhead_from_evaluation(_ev)

    # Shaft: sleeve + tang box, less the part of the tang box that is already inside the
    # round sleeve, less the spline socket. Exact, so it must agree exactly.
    sleeve = math.pi * (s.journal_dia / 2) ** 2 * s.sleeve_length
    tang_box = j.tang_thickness * j.tang_width * (j.engagement + hinge.TANG_MODEL_OVERSHOOT)
    a, rr = j.tang_thickness / 2.0, s.journal_dia / 2.0
    strip = 2.0 * (a * math.sqrt(rr ** 2 - a ** 2) + rr ** 2 * math.asin(a / rr))
    socket = math.pi * (c.socket_dia / 2) ** 2 * c.socket_depth

    mp = get(f"/assemblies/d/{DOC}/w/{WS}/e/{ASSEMBLY}/massproperties")
    t = CANARD_MODULE_CAD
    less_seal = assembly_less_seal(mp)

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
        # The two bulkheads, against the disc-less-holes analytic figure. Compared TIGHT
        # for the same reason as the bearing: a solid disc and a drilled one differ by 1.7%
        # of mass, which no tolerance-based check would notice, and the holes not cutting is
        # exactly the failure mode (Part Studio 1's `Extrude 4` cut nothing at all).
        ("aft gas seal, mm^3",
         seal_analytic_volume(sl) * 1e9,
         part_volume(SEAL, "Aft gas seal") * 1e9, 1e-2),
        ("internal bulkhead, mm^3",
         seal_analytic_volume(ib) * 1e9,
         part_volume(INTERNAL_BULKHEAD, "Recovery internal bulkhead") * 1e9, 1e-2),
        # THE ASSEMBLY IS NO LONGER THE MODULE. The aft gas seal was instanced in Aug 2026,
        # so `/massproperties` now returns module + seal while `CANARD_MODULE_CAD` is the
        # module alone. The seal is NOT folded into that tensor on purpose: it is a
        # structure part, budgeted in `mass.DEFAULT_STRUCTURE_BUDGET["couplers_bulkheads"]`
        # with every other bulkhead, and moving it into the canard module's tensor without
        # taking it out of that line would count 38 g twice. `estimate_inertia` removes a
        # measured component's mass from the bulk and adds it back, so a double count there
        # is not visible as a mass error -- only as an inertia one.
        #
        # So the seal is SUBTRACTED from the assembly before comparing, using its own
        # measured properties rather than an analytic disc. That keeps the check exact and
        # keeps it a check: it still fails if anything else in the assembly moves.
        ("module mass, g", t.mass * 1000.0, less_seal["mass"] * 1000.0, 1e-3),
        ("module station, mm", t.station_from_module_face * MM,
         less_seal["station"] * MM, 1e-3),
        ("module I_transverse, e-6", t.i_transverse * 1e6,
         less_seal["i_transverse"] * 1e6, 1e-2),
        ("module I_roll, e-6", t.i_roll * 1e6, less_seal["i_roll"] * 1e6, 1e-2),
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
