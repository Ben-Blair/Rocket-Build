"""Emit DXF profiles and a build sheet for the canard module, from the frozen design.

Run:  python scripts/make_cad_profiles.py

Writes importable 2D geometry to out/cad/. Import each DXF into an Onshape sketch, then
extrude. Everything derives from design/configure.py, so the CAD cannot drift from the
analysis -- regenerate rather than editing dimensions by hand.

DXF R12 with LINE and CIRCLE entities only. No CAD kernel needed and every tool reads it.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design.configure import baseline, build_vehicle
from design.packaging import SERVOS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "cad"

HINGE_FRAC = 0.20   # of MAC, forward of the 0.25c panel CP -> restoring. See packaging.py
TAB_DEPTH = 0.012   # through-wall fin tab, m


class Dxf:
    """Minimal DXF R12 writer. Millimetres."""

    def __init__(self) -> None:
        self.body: list[str] = []

    def line(self, x1, y1, x2, y2, layer="0") -> None:
        self.body += ["0", "LINE", "8", layer,
                      "10", f"{x1:.4f}", "20", f"{y1:.4f}", "30", "0.0",
                      "11", f"{x2:.4f}", "21", f"{y2:.4f}", "31", "0.0"]

    def circle(self, cx, cy, r, layer="0") -> None:
        self.body += ["0", "CIRCLE", "8", layer,
                      "10", f"{cx:.4f}", "20", f"{cy:.4f}", "30", "0.0",
                      "40", f"{r:.4f}"]

    def poly(self, pts, layer="0", close=True) -> None:
        seq = list(pts) + ([pts[0]] if close else [])
        for (x1, y1), (x2, y2) in zip(seq, seq[1:]):
            self.line(x1, y1, x2, y2, layer)

    def write(self, path: Path) -> None:
        text = "\n".join(["0", "SECTION", "2", "ENTITIES"] + self.body +
                         ["0", "ENDSEC", "0", "EOF", ""])
        path.write_text(text)


def mac(root_c: float, tip_c: float, span: float, sweep: float):
    """Mean aerodynamic chord, its spanwise station, and its LE offset from the root LE."""
    lam = tip_c / root_c
    m = (2.0 / 3.0) * root_c * (1.0 + lam + lam * lam) / (1.0 + lam)
    y = (span / 3.0) * (1.0 + 2.0 * lam) / (1.0 + lam)
    x_le = sweep * y / span
    return m, y, x_le


def fin_profile(fins, tab: float = 0.0):
    """Planform corners in mm, root at y=0, tip at y=+semispan. Optional tab below y=0."""
    r, t = fins.root_chord * 1000, fins.tip_chord * 1000
    s, sw = fins.semispan * 1000, fins.sweep_length * 1000
    pts = [(0.0, 0.0), (sw, s), (sw + t, s), (r, 0.0)]
    if tab > 0:
        d = tab * 1000
        pts = [(0.0, 0.0), (sw, s), (sw + t, s), (r, 0.0), (r - 6.0, -d), (6.0, -d)]
    return pts


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = baseline()
    r = build_vehicle(p)
    servo = SERVOS[p.servo]
    can, aft = r.canards, r.aft_fins
    id_mm = r.tubes[1].inner_diameter * 1000
    od_mm = p.outer_diameter * 1000

    # ---- canard planform, with the hinge axis marked -----------------------------------
    d = Dxf()
    d.poly(fin_profile(can), layer="PROFILE")
    m, y_mac, x_le = mac(can.root_chord, can.tip_chord, can.semispan, can.sweep_length)
    x_hinge = (x_le + HINGE_FRAC * m) * 1000
    x_cp = (x_le + 0.25 * m) * 1000
    d.line(x_hinge, -8.0, x_hinge, can.semispan * 1000 + 8.0, layer="HINGE")
    d.line(x_cp, -4.0, x_cp, can.semispan * 1000 + 4.0, layer="PANEL_CP")
    d.write(OUT / "canard_planform.dxf")

    # ---- aft fin planform, with through-wall tab ---------------------------------------
    d = Dxf()
    d.poly(fin_profile(aft, tab=TAB_DEPTH), layer="PROFILE")
    d.write(OUT / "aft_fin_planform.dxf")

    # ---- canard bay cross-section, looking down the tube axis --------------------------
    d = Dxf()
    d.circle(0, 0, od_mm / 2, layer="TUBE_OD")
    d.circle(0, 0, id_mm / 2, layer="TUBE_ID")
    sw_mm, sh_mm = servo.width * 1000, servo.height * 1000   # radial, circumferential
    for i in range(p.n_canards):
        a = math.radians(90.0 * i)
        ca, sa = math.cos(a), math.sin(a)
        r_out, r_in = id_mm / 2, id_mm / 2 - sw_mm
        h = sh_mm / 2
        corners = [(r_in, -h), (r_out, -h), (r_out, h), (r_in, h)]
        d.poly([(x * ca - y * sa, x * sa + y * ca) for x, y in corners], layer="SERVO")
        d.circle((od_mm / 2 + 3) * ca, (od_mm / 2 + 3) * sa, 2.5, layer="SHAFT")
    d.write(OUT / "canard_bay_section.dxf")

    print(f"wrote 3 DXF profiles to {OUT}")
    print(f"  canard_planform.dxf     root {can.root_chord*1000:.1f} tip {can.tip_chord*1000:.1f} "
          f"span {can.semispan*1000:.1f} sweep {can.sweep_length*1000:.1f} mm")
    print(f"                          hinge axis {x_hinge:.1f} mm aft of root LE "
          f"(MAC {m*1000:.1f} mm, panel CP {x_cp:.1f} mm)")
    print(f"  aft_fin_planform.dxf    root {aft.root_chord*1000:.1f} tip {aft.tip_chord*1000:.1f} "
          f"span {aft.semispan*1000:.1f} sweep {aft.sweep_length*1000:.1f} mm, "
          f"{TAB_DEPTH*1000:.0f} mm tab")
    print(f"  canard_bay_section.dxf  OD {od_mm:.1f} ID {id_mm:.1f}, {p.n_canards} servo "
          f"footprints {sw_mm:.1f} radial x {sh_mm:.1f} circumferential")


if __name__ == "__main__":
    main()
