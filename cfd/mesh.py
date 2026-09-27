"""Build a 3-D CFD volume mesh of the frozen vehicle for SU2.

    .venv-cfd/bin/python cfd/mesh.py --case roll5 --level medium

EVERY DIMENSION COMES FROM `design/configure.py`, same discipline as the CAD generators:
`build_vehicle(baseline())` for the body, both fin sets and their stations, and
`hinge.canard_hinge_station` for the canard hinge axis. Nothing here is typed in, so the
mesh cannot drift away from the vehicle the rest of the repo analyses.

What is modelled, and what is deliberately not:

  * Body: tangent ogive + cylinder to the base, then a STING -- the same cylinder carried
    3 body lengths downstream. An inviscid solver has no way to settle a flat-base wake
    (it is a separated, unsteady flow Euler cannot represent), and a sting is the standard
    wind-tunnel and CFD answer. The sting is its own marker and is never integrated into
    any force, so it changes the aft-fin flow slightly and nothing else.
  * Panels: flat plates at the true laminate thickness (4.0 mm canard, 3.2 mm aft fin) with
    a 20%-chord symmetric bevel at each edge. The real parts are square-edged G10 sanded to
    a bevel; a square edge in an inviscid solver just produces a singular suction spike.
  * Canard deflection: each canard is rotated about ITS OWN radial hinge axis, at the
    derived hinge station -- the same axis the Fusion joints rotate about. The panel root
    is sunk 5 mm into the body so a deflected root still fuses cleanly; the real root gap
    (a few tenths of a mm around the shaft) is not modelled.
  * Frame: x aft from the nose tip (the repo's station convention), z up. SU2 puts the
    freestream along +x and rotates it toward +z by AOA, so a positive AOA is nose-up and
    produces +z normal force.

Clocking: canards at 0/90/180/270 deg, aft fins at 45/135/225/315 (interdigitated,
docs/01 correction 52). A panel at clock angle phi spans along (0, cos phi, sin phi).
Canards 0 and 180 are therefore the HORIZONTAL pair -- the pitch pair.

Sign of deflection: +delta rotates a panel about its outward span axis by the right-hand
rule. For the pitch pair that is chosen so +delta on both gives +z force (nose-up moment
about the CG, since they are forward of it); for a roll command every panel gets the same
+delta about its own outward axis, which is a pure rolling couple.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import gmsh

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from design import configure, hinge  # noqa: E402

OUT = ROOT / "out" / "cfd"

CANARD_CLOCK_DEG = (0.0, 90.0, 180.0, 270.0)
FIN_CLOCK_DEG = (45.0, 135.0, 225.0, 315.0)
ROOT_SINK = 0.005  # m, panel root buried inside the body so a deflected root still fuses
BEVEL_FRAC = 0.20

# Deflection sets, degrees, one entry per canard in CANARD_CLOCK_DEG order.
# Pitch uses the horizontal pair (0 and 180 deg). A panel at 180 deg spans along -y, so its
# outward axis is reversed and the SAME physical nose-up deflection is -delta about it.
CASES: dict[str, dict] = {
    "alpha0": dict(alpha=0.0, defl=(0, 0, 0, 0)),
    "alpha3": dict(alpha=3.0, defl=(0, 0, 0, 0)),
    "pitch6": dict(alpha=0.0, defl=(6.0, 0, -6.0, 0)),
    "roll5": dict(alpha=0.0, defl=(5.0, 5.0, 5.0, 5.0)),
    # the design point: full pitch/yaw deflection at roughly the trimmed AOA it produces
    "trim9": dict(alpha=2.0, defl=(9.2, 0, -9.2, 0)),
}

LEVELS = {
    #          canard  fin   body  far
    "coarse": (0.0024, 0.0032, 0.008, 0.60),
    "medium": (0.0016, 0.0022, 0.006, 0.45),
    "fine":   (0.0011, 0.0016, 0.004, 0.35),
}


@dataclass
class Geometry:
    d: float
    nose_len: float
    body_len: float
    hinge_x: float
    canard: dict
    fin: dict

    @classmethod
    def frozen(cls) -> "Geometry":
        rocket = configure.build_vehicle(configure.baseline())
        def fs(f):
            return dict(root=f.root_chord, tip=f.tip_chord, span=f.semispan,
                        sweep=f.sweep_length, x_le=f.x_root_le, t=f.thickness)
        return cls(d=rocket.diameter, nose_len=rocket.nose.length, body_len=rocket.length,
                   hinge_x=hinge.canard_hinge_station(rocket),
                   canard=fs(rocket.canards), fin=fs(rocket.aft_fins))


def _section(occ, x_le: float, chord: float, t: float, r: float) -> int:
    """Beveled flat-plate section as a closed wire in the local (x, n) plane at radius r.

    Built in the +y panel frame: span along +y, thickness along z. It is rotated to its
    clock angle afterwards."""
    b = BEVEL_FRAC * chord
    pts = [(x_le, 0.0), (x_le + b, t / 2), (x_le + chord - b, t / 2), (x_le + chord, 0.0),
           (x_le + chord - b, -t / 2), (x_le + b, -t / 2)]
    tags = [occ.addPoint(x, r, z) for x, z in pts]
    lines = [occ.addLine(tags[i], tags[(i + 1) % len(tags)]) for i in range(len(tags))]
    return occ.addCurveLoop(lines)


def _panel(occ, f: dict, r_body: float) -> int:
    """One trapezoidal panel spanning +y, root sunk ROOT_SINK into the body."""
    r_root = r_body - ROOT_SINK
    # extend the planform linearly inboard so the exposed part is exactly the design panel
    k = -ROOT_SINK / f["span"]
    root_c = f["root"] + (f["tip"] - f["root"]) * k
    root_le = f["x_le"] + f["sweep"] * k
    w_root = _section(occ, root_le, root_c, f["t"], r_root)
    w_tip = _section(occ, f["x_le"] + f["sweep"], f["tip"], f["t"], r_body + f["span"])
    out = occ.addThruSections([w_root, w_tip], makeSolid=True, makeRuled=True)
    return [t for dim, t in out if dim == 3][0]


def build(case: str, level: str, out_dir: Path) -> Path:
    g = Geometry.frozen()
    spec = CASES[case]
    h_can, h_fin, h_body, h_far = LEVELS[level]
    R = g.d / 2
    L = g.body_len

    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 1)
    gmsh.option.setNumber("General.NumThreads", 8)
    gmsh.model.add(f"{case}_{level}")
    occ = gmsh.model.occ

    # --- body: lofted ogive + cylindrical bands ---------------------------------------
    # The nose is a LOFT through circular sections, not a revolve. A surface of revolution
    # has a degenerate parametrisation at the point on its axis, and gmsh falls back to
    # MeshAdapt there -- which does not finish this model in an hour. The loft has no
    # degeneracy and meshes with Frontal-Delaunay in seconds.
    #
    # That costs a BLUNTED TIP: the loft starts at the station where the ogive radius is
    # TIP_RADIUS rather than at the mathematical point, leaving a flat disc of that radius.
    # At 0.4 mm on a 39.7 mm body that disc is 1e-4 of the reference area, and a real
    # fiberglass nose tip is blunter than this. It is also the one place this mesh is not
    # the frozen geometry, so it is stated rather than buried.
    Ln = g.nose_len
    rho = (R**2 + Ln**2) / (2 * R)

    def ogive_r(x: float) -> float:
        return math.sqrt(max(rho**2 - (Ln - x) ** 2, 0.0)) + R - rho

    TIP_RADIUS = 0.0004
    lo, hi = 0.0, Ln
    for _ in range(80):  # bisect for the station where the ogive reaches TIP_RADIUS
        mid = 0.5 * (lo + hi)
        if ogive_r(mid) < TIP_RADIUS:
            lo = mid
        else:
            hi = mid
    x_tip = hi
    sting_end = L + 3.0 * L
    gmsh.option.setNumber("Geometry.OCCUnionUnify", 0)

    n_sec = 26
    wires = []
    for i in range(n_sec + 1):
        # cosine clustering toward the tip, where curvature is highest
        f_ = (1 - math.cos(math.pi * i / n_sec)) / 2
        x = x_tip + (Ln - x_tip) * f_
        r = max(ogive_r(x), TIP_RADIUS)
        c = occ.addCircle(x, 0, 0, r, zAxis=[1, 0, 0])
        wires.append(occ.addCurveLoop([c]))
    nose_out = occ.addThruSections(wires, makeSolid=True, makeRuled=False)
    parts = [t for dim, t in nose_out if dim == 3]

    # Cylindrical bands, each rotated 22.5 deg so its seam is clear of every panel root.
    # One skin with eight panel holes cut in it is also a MeshAdapt case; bands are not.
    cut_x = [Ln, g.canard["x_le"] - 0.03,
             g.canard["x_le"] + g.canard["sweep"] + g.canard["tip"] + 0.03,
             g.fin["x_le"] - 0.03, L, sting_end]
    for x0, x1 in zip(cut_x[:-1], cut_x[1:]):
        cyl = occ.addCylinder(x0, 0, 0, x1 - x0, 0, 0, R)
        occ.rotate([(3, cyl)], 0, 0, 0, 1, 0, 0, math.radians(22.5))
        parts.append(cyl)
    body_parts, _ = occ.fuse([(3, parts[0])], [(3, t) for t in parts[1:]])
    body = body_parts[0][1]

    # --- panels ----------------------------------------------------------------------
    solids = []
    for i, clock in enumerate(CANARD_CLOCK_DEG):
        p = _panel(occ, g.canard, R)
        delta = math.radians(spec["defl"][i])
        if delta:
            # hinge axis is the panel's own span direction (+y before clocking)
            occ.rotate([(3, p)], g.hinge_x, 0, 0, 0, 1, 0, delta)
        occ.rotate([(3, p)], 0, 0, 0, 1, 0, 0, math.radians(clock))
        solids.append(("CANARD%d" % i, p))
    for i, clock in enumerate(FIN_CLOCK_DEG):
        p = _panel(occ, g.fin, R)
        occ.rotate([(3, p)], 0, 0, 0, 1, 0, 0, math.radians(clock))
        solids.append(("FIN%d" % i, p))

    vehicle, _ = occ.fuse([(3, body)], [(3, t) for _, t in solids])
    # farfield box: 3 L upstream and radially; the sting runs out through the outflow face
    X0, X1, H = -3 * L, sting_end, 3 * L
    far = occ.addBox(X0, -H, -H, X1 - X0, 2 * H, 2 * H)
    fluid, _ = occ.cut([(3, far)], vehicle)
    occ.synchronize()

    # --- classify boundary surfaces by where they are ---------------------------------
    vol = fluid[0][1]
    surfaces = [t for d_, t in gmsh.model.getBoundary(fluid, oriented=False) if d_ == 2]
    groups: dict[str, list[int]] = {k: [] for k in
                                     ["FARFIELD", "BODY", "STING"] + [n for n, _ in solids]}
    tol = 1e-6
    for s in surfaces:
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, s)
        on_box = (abs(xmin - xmax) < tol and (abs(xmin - X0) < tol or abs(xmax - X1) < tol)) \
            or (abs(ymin - ymax) < tol and abs(abs(ymin) - H) < tol) \
            or (abs(zmin - zmax) < tol and abs(abs(zmin) - H) < tol)
        if on_box:
            groups["FARFIELD"].append(s)
            continue
        cx, cy, cz = occ.getCenterOfMass(2, s)
        if math.hypot(cy, cz) > 1.02 * R:
            ang = math.degrees(math.atan2(cz, cy)) % 360.0
            is_canard = cx < 0.5 * L
            clocks = CANARD_CLOCK_DEG if is_canard else FIN_CLOCK_DEG
            k = min(range(4), key=lambda j: abs((ang - clocks[j] + 180) % 360 - 180))
            groups[("CANARD%d" if is_canard else "FIN%d") % k].append(s)
        elif cx > L:
            groups["STING"].append(s)
        else:
            groups["BODY"].append(s)
    for name, tags in groups.items():
        if not tags:
            raise RuntimeError(f"marker {name} is empty -- surface classification failed")
        pg = gmsh.model.addPhysicalGroup(2, tags)
        gmsh.model.setPhysicalName(2, pg, name)
    gmsh.model.addPhysicalGroup(3, [vol], name="FLUID")
    print({k: len(v) for k, v in groups.items()})

    # --- sizing fields -------------------------------------------------------------------
    f = gmsh.model.mesh.field
    def dist_thresh(tags, h_min, d_min, d_max):
        fd = f.add("Distance"); f.setNumbers(fd, "SurfacesList", tags)
        f.setNumber(fd, "Sampling", 60)
        ft = f.add("Threshold"); f.setNumber(ft, "InField", fd)
        f.setNumber(ft, "SizeMin", h_min); f.setNumber(ft, "SizeMax", h_far)
        f.setNumber(ft, "DistMin", d_min); f.setNumber(ft, "DistMax", d_max)
        return ft
    can = [s for n, t in groups.items() if n.startswith("CANARD") for s in t]
    fin = [s for n, t in groups.items() if n.startswith("FIN") for s in t]
    fields = [
        dist_thresh(can, h_can, 0.004, 0.6),
        dist_thresh(fin, h_fin, 0.004, 0.6),
        dist_thresh(groups["BODY"], h_body, 0.01, 0.8),
        dist_thresh(groups["STING"], 2.5 * h_body, 0.02, 0.8),
    ]
    # wake box from the canards back past the fins: the canard wake is the whole question
    fb = f.add("Box")
    f.setNumber(fb, "VIn", 2.2 * h_fin); f.setNumber(fb, "VOut", h_far)
    f.setNumber(fb, "XMin", g.canard["x_le"]); f.setNumber(fb, "XMax", L + 0.1)
    for a in ("Y", "Z"):
        f.setNumber(fb, a + "Min", -(R + g.fin["span"] + 0.02))
        f.setNumber(fb, a + "Max", R + g.fin["span"] + 0.02)
    f.setNumber(fb, "Thickness", 0.15)
    fields.append(fb)
    fmin = f.add("Min"); f.setNumbers(fmin, "FieldsList", fields)
    f.setAsBackgroundMesh(fmin)
    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 24)
    gmsh.option.setNumber("Mesh.MeshSizeMax", h_far)
    gmsh.option.setNumber("Mesh.Algorithm", 6)
    gmsh.option.setNumber("Mesh.Algorithm3D", 10)  # HXT, parallel
    gmsh.option.setNumber("Mesh.Optimize", 1)

    gmsh.model.mesh.generate(3)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "mesh.su2"
    gmsh.write(str(path))
    n_tet = sum(len(t) for t in gmsh.model.mesh.getElements(3)[1])
    gmsh.finalize()

    meta = dict(case=case, level=level, alpha=spec["alpha"], defl=list(spec["defl"]),
                n_cells=n_tet, geometry=asdict(g), canard_clock=CANARD_CLOCK_DEG,
                fin_clock=FIN_CLOCK_DEG)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"wrote {path}  ({n_tet:,} tets)")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", choices=sorted(CASES), required=True)
    ap.add_argument("--level", choices=sorted(LEVELS), default="medium")
    a = ap.parse_args()
    build(a.case, a.level, OUT / f"{a.case}_{a.level}")
