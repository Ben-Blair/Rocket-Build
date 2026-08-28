"""Dual-deploy recovery sizing, descent time, and wind drift.

Once an altitude waiver stops being the binding constraint, the constraint that replaces
it is the size of the recovery area. Drift under canopy scales with descent time, which
scales with apogee, so "we can fly as high as we want" quietly becomes "we can walk as far
as we want, and we can lose the vehicle and all its data."

For a project that needs five or six repeatable flights on an academic calendar, recovery
footprint is a first-class design constraint, not an afterthought.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import atmosphere

# Landing kinetic energy guidance. NAR/TRA range safety commonly looks for each
# independently-descending section to land below roughly 75 ft-lbf. Confirm the current
# figure with your prefect; treat this as a design target, not a quoted rule.
LANDING_KE_LIMIT_J = 75.0 * 1.35582


@dataclass
class Canopy:
    name: str
    diameter: float  # m
    drag_coefficient: float

    @property
    def area(self) -> float:
        return math.pi * self.diameter**2 / 4.0

    @property
    def cd_a(self) -> float:
        return self.drag_coefficient * self.area

    def descent_rate(self, mass: float, altitude: float = 0.0) -> float:
        rho = atmosphere.density(altitude)
        return math.sqrt(2.0 * mass * atmosphere.G0 / (rho * self.cd_a))


def size_for_descent_rate(
    mass: float, target_rate: float, drag_coefficient: float = 2.2, altitude: float = 0.0
) -> float:
    """Canopy diameter, in metres, giving `target_rate` m/s at sea level."""
    rho = atmosphere.density(altitude)
    cd_a = 2.0 * mass * atmosphere.G0 / (rho * target_rate**2)
    return math.sqrt(4.0 * cd_a / (drag_coefficient * math.pi))


@dataclass
class DescentResult:
    drogue_rate: float
    main_rate: float
    drogue_time: float
    main_time: float
    total_time: float
    landing_energy: float
    drift_by_wind: dict[float, float]  # wind m/s -> total drift m

    def report(self, apogee: float, downrange_at_apogee: float = 0.0) -> str:
        lines = [
            f"  apogee                {apogee:7.0f} m ({apogee * 3.28084:.0f} ft)",
            f"  drogue descent rate   {self.drogue_rate:7.1f} m/s",
            f"  main descent rate     {self.main_rate:7.1f} m/s",
            f"  descent time          {self.total_time:7.0f} s "
            f"({self.drogue_time:.0f} s drogue + {self.main_time:.0f} s main)",
            f"  landing energy        {self.landing_energy:7.0f} J "
            f"({self.landing_energy / 1.35582:.0f} ft-lbf) "
            f"{'OK' if self.landing_energy <= LANDING_KE_LIMIT_J else 'TOO HIGH'}",
            "  drift and minimum field radius:",
        ]
        for wind, drift in sorted(self.drift_by_wind.items()):
            total = drift + downrange_at_apogee
            lines.append(
                f"    {wind * 2.23694:4.0f} mph wind  ->  {drift:6.0f} m drift, "
                f"{total:6.0f} m from the pad ({total * 0.000621371:.2f} miles)"
            )
        return "\n".join(lines)


def simulate_descent(
    apogee: float,
    mass: float,
    drogue: Canopy,
    main: Canopy,
    main_deploy_altitude: float = 200.0,
    winds: tuple[float, ...] = (2.24, 4.47, 6.71, 8.94),  # 5, 10, 15, 20 mph
    steps: int = 200,
) -> DescentResult:
    """Descent time and drift, integrating density variation with altitude."""

    def leg_time(top: float, bottom: float, canopy: Canopy) -> float:
        if top <= bottom:
            return 0.0
        dh = (top - bottom) / steps
        t = 0.0
        for i in range(steps):
            h = top - (i + 0.5) * dh
            t += dh / canopy.descent_rate(mass, h)
        return t

    main_alt = min(main_deploy_altitude, apogee)
    t_drogue = leg_time(apogee, main_alt, drogue)
    t_main = leg_time(main_alt, 0.0, main)
    total = t_drogue + t_main

    landing_rate = main.descent_rate(mass, 0.0)
    energy = 0.5 * mass * landing_rate**2

    # Drift assumes the canopy moves with the airmass, which is the standard
    # approximation and is close enough for field sizing.
    drift = {w: w * total for w in winds}

    return DescentResult(
        drogue_rate=drogue.descent_rate(mass, apogee),
        main_rate=landing_rate,
        drogue_time=t_drogue,
        main_time=t_main,
        total_time=total,
        landing_energy=energy,
        drift_by_wind=drift,
    )
