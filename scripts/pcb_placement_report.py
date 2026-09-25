"""Placement and impedance report for the Stage 2 flight computer board.

Run:  python scripts/pcb_placement_report.py

Reads pcb/flight_computer/flight_computer.kicad_pcb directly (no pcbnew, no KiCad) and
prints the two things ERC and DRC structurally cannot see:

  1. Every two-terminal passive that is far from the pin it serves, and the three nets that
     must be short end to end.  See design/pcb_placement.py for why the check is scoped that
     way -- run over every pad it fires on the intended zoning and is worthless.
  2. The microstrip solve behind the RF netclass width, so 0.36 mm is a derived number rather
     than a magic constant in layout.py.

`scripts/baseline.py` carries the pass/fail so it cannot regress quietly.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import pcb_placement

# Stackup from flight_computer.kicad_pcb: F.Cu (35 um) over 0.2104 mm prepreg over In1.Cu.
# er 4.5 is the board file's own value for that prepreg.
PREPREG_MM = 0.2104
EPSILON_R = 4.5
COPPER_MM = 0.035
TARGET_OHM = 50.0          # MAX-M10S RF_IN, u-blox UBX-20035208 R08 Table 13
GNSS_MHZ = 1575.42


def microstrip(w_mm: float, h_mm: float = PREPREG_MM, er: float = EPSILON_R,
               t_mm: float = COPPER_MM) -> tuple[float, float]:
    """Hammerstad single-ended microstrip: (Z0 ohm, effective permittivity).

    Thickness-corrected effective width, which matters here: 35 um of copper against
    210 um of prepreg is not a thin trace, and ignoring it reads ~3 ohm high.
    """
    we = w_mm + (t_mm / math.pi) * (1.0 + math.log(2.0 * h_mm / t_mm))
    u = we / h_mm
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 12 / u) ** -0.5
    if u <= 1.0:
        z = 60 / math.sqrt(eeff) * math.log(8 / u + u / 4)
    else:
        z = 120 * math.pi / (math.sqrt(eeff) * (u + 1.393 + 0.667 * math.log(u + 1.444)))
    return z, eeff


def edge_coupled_diff(w_mm: float, s_mm: float, h_mm: float = PREPREG_MM) -> float:
    """Differential impedance of an edge-coupled microstrip pair (IPC-2141 coupling term).

    Zdiff = 2 Z0 (1 - 0.48 exp(-0.96 s/h)).  A first-order formula, good to a few ohm at
    these proportions -- which is plenty: USB full speed does not care (see main()).
    """
    z0, _ = microstrip(w_mm, h_mm)
    return 2 * z0 * (1 - 0.48 * math.exp(-0.96 * s_mm / h_mm))


def width_for(z_target: float = TARGET_OHM) -> float:
    lo, hi = 0.05, 2.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if microstrip(mid)[0] > z_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def rule(title: str = "", width: int = 92) -> None:
    if title:
        print("\n" + "=" * width)
        print(title)
        print("=" * width)
    else:
        print("-" * width)


def main() -> None:
    pcb_placement.self_check()

    rule("PLACEMENT -- nearest same-net pad, for passives and the must-be-short nets")
    check = pcb_placement.check_placement()
    print(f"  evaluated           {check.n_pads} pads")
    print(f"  median              {check.median_mm:.2f} mm")
    print(f"  general limit       {pcb_placement.GENERAL_LIMIT_MM:.1f} mm")
    print(f"  failures            {len(check.failures)}")
    print()
    print(f"  {'mm':>6}  {'limit':>5}  {'pad':<10} {'net':<12} {'nearest':<10} state")
    rule()
    for link in check.worst(20):
        state = "FAIL" if link.over else ("exempt" if link.exempt_reason else "ok")
        print(f"  {link.mm:6.2f}  {link.limit:5.1f}  "
              f"{link.ref + '.' + link.number:<10} {link.net:<12} "
              f"{link.to_ref + '.' + link.to_number:<10} {state}")
    if check.failures:
        print()
        print("  FAILING:")
        for link in check.failures:
            print(f"    {link.ref}.{link.number} [{link.net}] is {link.mm:.2f} mm from "
                  f"{link.to_ref}.{link.to_number}, limit {link.limit:.1f} mm")
    else:
        print("\n  All passives are local to the pin they serve.")

    rule("RF -- why the RF netclass is 0.36 mm")
    z_default, _ = microstrip(0.25)
    w50 = width_for()
    z50, eeff = microstrip(w50)
    lam_mm = 300.0 / (GNSS_MHZ / 1000.0) / math.sqrt(eeff)
    print(f"  stackup             F.Cu {COPPER_MM * 1000:.0f} um over {PREPREG_MM:.4f} mm "
          f"prepreg, er {EPSILON_R}")
    print(f"  target              {TARGET_OHM:.0f} ohm (MAX-M10S RF_IN Zin, UBX-20035208 R08)")
    print(f"  Default 0.25 mm     {z_default:.1f} ohm   <- what GNSS_RF used to be")
    print(f"  RF {w50:.3f} mm        {z50:.1f} ohm")
    print(f"  wavelength          {lam_mm:.1f} mm in this dielectric at {GNSS_MHZ:.2f} MHz")
    gnss = [l for l in check.links if l.net == "GNSS_RF"]
    if gnss:
        run = max(l.mm for l in gnss)
        print(f"  GNSS_RF run         {run:.2f} mm = {run / lam_mm:.3f} lambda")

    rule("USB -- why the USB netclass is 0.25 mm / 0.15 mm gap")
    for w, g, what in ((0.4, 0.2, "the old netclass"), (0.25, 0.15, "the netclass now")):
        print(f"  w {w:.2f} / s {g:.2f} mm   {edge_coupled_diff(w, g):5.1f} ohm diff   <- {what}")
    print("  target              90 ohm diff (USB 2.0).  The STM32F405's OTG_FS is 12 Mbit/s:")
    print("                      edges >= 4 ns are ~600 mm long in this dielectric, so the")
    print("                      ~25 mm run is electrically short.  Bookkeeping, not SI.")

    rule("VERDICT")
    print(f"  placement           {'PASS' if check.ok else 'FAIL'}")
    if not check.ok:
        print("\n  Fix placement in pcb/flight_computer/scaffold/ (PLACE in gen_pcb.py for a")
        print("  major part, OVERRIDE_ANCHOR in layout.py for a passive), then regenerate.")
        print("  Do NOT nudge parts in the GUI -- the next regen puts them back.")
    sys.exit(0 if check.ok else 1)


if __name__ == "__main__":
    main()
