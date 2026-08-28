"""Which airframe diameters can actually house a direct-drive canard actuator set?

Run:  python scripts/packaging_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design.packaging import SERVOS, check_bellcrank, check_direct_drive

# Commercially available high power airframe sizes: (label, OD mm, wall mm)
AIRFRAMES = [
    ("54 mm  (2.14in) fiberglass", 57.2, 2.0),
    ("66 mm  (2.6in)  fiberglass", 66.0, 2.0),
    ("75 mm  (3.0in)  fiberglass", 79.4, 2.3),
    ("98 mm  (3.9in)  fiberglass", 101.6, 2.4),
    ("129 mm (5.15in) fiberglass", 130.8, 2.5),
]

N_CANARDS = 4


def main() -> None:
    print("=" * 96)
    print("CANARD ACTUATOR PACKAGING  --  4 canards, direct radial drive")
    print("=" * 96)
    print("Servo dimensions are APPROXIMATE class representatives. Verify before ordering.\n")

    for label, od_mm, wall_mm in AIRFRAMES:
        inner_d = (od_mm - 2 * wall_mm) / 1000.0
        print(f"{label}   OD {od_mm:.1f} mm, ID {inner_d * 1000:.1f} mm")
        for key in ("submicro", "micro", "mini_ht", "standard_ht"):
            servo = SERVOS[key]
            direct = check_direct_drive(inner_d, servo, N_CANARDS)
            print(f"    {key:12s} ({servo.length * 1000:.0f}x{servo.width * 1000:.0f}mm, "
                  f"{servo.stall_torque:.2f} Nm)  {direct}")
        bell = check_bellcrank(inner_d, SERVOS["standard_ht"], N_CANARDS)
        print(f"    {'standard_ht':12s} via linkage                    {bell}")
        print()

    print("-" * 96)
    print("""Reading this table:

* 54 mm is dead for direct drive. Even a sub-micro servo cannot fit radially, and the
  circumference will not take four of anything plus a flight computer, battery and
  recovery hardware. Do not design around it.
* 75 mm is the smallest size that works with micro/mini servos on direct drive, and it is
  the sweet spot: 54 mm motor mount, huge motor selection, affordable, and light enough to
  reach a sane altitude on a J motor.
* 98 mm buys comfort -- standard-size servos, easy wiring, room to iterate -- at the cost
  of mass, drag area and a more expensive motor for the same altitude.
* The bellcrank column shows that linkages let a small tube carry a big servo. It is a
  real option, but backlash in a linkage becomes deadband in your control loop, which is
  a genuinely hard problem to tune around. Prefer direct drive if the diameter allows it.

Torque is checked separately against the aerodynamic hinge moment -- see
scripts/baseline.py, which reports required hinge moment at max dynamic pressure.""")


if __name__ == "__main__":
    main()
