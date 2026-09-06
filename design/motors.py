"""Motor models.

Two sources:
  1. `load_eng()` parses RASP `.eng` files. **This is the one you should use.** Download
     the real curve for your exact motor from thrustcurve.org into `data/motors/`.
  2. `GENERIC` holds placeholder motors whose numbers are representative of the class but
     are NOT any real product. They exist only so the sizing sweep can run before you
     have picked a motor. Every value is APPROX.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Motor:
    name: str
    diameter: float  # m
    length: float  # m
    total_impulse: float  # N*s
    burn_time: float  # s
    propellant_mass: float  # kg
    total_mass: float  # kg
    times: list[float] = field(default_factory=list)
    thrusts: list[float] = field(default_factory=list)
    approximate: bool = False
    # Last field of the RASP header. Carried because scripts/make_ork.py has to hand
    # OpenRocket a manufacturer AND a designation to resolve the motor from its own
    # database, and it used to hardcode "Cesaroni Technology" / "1261J449-15A". That was
    # invisible while the baseline WAS the J449; the moment the frozen motor changed, the
    # generated .ork described an AeroTech vehicle carrying a Cesaroni motor. A constant
    # that happens to be right is not the same as a derived one.
    manufacturer: str = ""

    @property
    def dry_mass(self) -> float:
        return self.total_mass - self.propellant_mass

    @property
    def average_thrust(self) -> float:
        return self.total_impulse / self.burn_time

    @property
    def impulse_class(self) -> str:
        i = self.total_impulse
        bounds = [
            (2.5, "A"), (5, "B"), (10, "C"), (20, "D"), (40, "E"), (80, "F"),
            (160, "G"), (320, "H"), (640, "I"), (1280, "J"), (2560, "K"),
            (5120, "L"), (10240, "M"), (20480, "N"), (40960, "O"),
        ]
        for limit, letter in bounds:
            if i <= limit:
                return letter
        return "O+"

    @property
    def requires_level(self) -> int:
        """Minimum NAR/TRA certification level. Verify against current rules."""
        cls = self.impulse_class
        if cls in ("A", "B", "C", "D", "E", "F", "G"):
            return 0
        if cls in ("H", "I"):
            return 1
        if cls in ("J", "K", "L"):
            return 2
        return 3

    def thrust(self, t: float) -> float:
        """Thrust at time `t` seconds after ignition."""
        if t < 0.0 or t > self.burn_time:
            return 0.0
        if self.times:
            if t <= self.times[0]:
                return self.thrusts[0]
            for i in range(1, len(self.times)):
                if t <= self.times[i]:
                    span = self.times[i] - self.times[i - 1]
                    if span <= 0:
                        return self.thrusts[i]
                    frac = (t - self.times[i - 1]) / span
                    return self.thrusts[i - 1] + frac * (self.thrusts[i] - self.thrusts[i - 1])
            return 0.0
        # No curve: mildly regressive trapezoid normalised to the total impulse.
        rise = min(0.15 * self.burn_time, 0.15)
        if t < rise:
            shape = t / rise
        else:
            shape = 1.0 - 0.35 * (t - rise) / max(self.burn_time - rise, 1e-6)
        integral = 0.5 * rise + (self.burn_time - rise) * (1.0 - 0.175)
        return shape * self.total_impulse / integral

    def mass_at(self, t: float) -> float:
        """Total motor mass at time `t`, assuming mass depletes with delivered impulse."""
        if t <= 0.0:
            return self.total_mass
        if t >= self.burn_time:
            return self.dry_mass
        burned_fraction = self.impulse_delivered(t) / self.total_impulse
        return self.total_mass - self.propellant_mass * burned_fraction

    def impulse_delivered(self, t: float, steps: int = 200) -> float:
        upper = min(t, self.burn_time)
        if upper <= 0:
            return 0.0
        dt = upper / steps
        total = 0.0
        for i in range(steps):
            total += 0.5 * (self.thrust(i * dt) + self.thrust((i + 1) * dt)) * dt
        return total


def load_eng(path: str | Path) -> Motor:
    """Parse a RASP format `.eng` thrust curve file."""
    path = Path(path)
    header = None
    points: list[tuple[float, float]] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        parts = line.split()
        if header is None:
            # name diameter_mm length_mm delays prop_mass_kg total_mass_kg manufacturer
            header = parts
            continue
        if len(parts) >= 2:
            points.append((float(parts[0]), float(parts[1])))

    if header is None or not points:
        raise ValueError(f"{path} does not look like a RASP .eng file")

    times = [p[0] for p in points]
    thrusts = [p[1] for p in points]
    impulse = sum(
        0.5 * (thrusts[i] + thrusts[i - 1]) * (times[i] - times[i - 1])
        for i in range(1, len(times))
    )
    return Motor(
        name=header[0],
        diameter=float(header[1]) / 1000.0,
        length=float(header[2]) / 1000.0,
        total_impulse=impulse,
        burn_time=times[-1],
        propellant_mass=float(header[4]),
        total_mass=float(header[5]),
        times=times,
        thrusts=thrusts,
        manufacturer=header[6] if len(header) > 6 else "",
    )


def _generic(name, dia_mm, len_mm, impulse, burn, prop, total) -> Motor:
    return Motor(
        name=name,
        diameter=dia_mm / 1000.0,
        length=len_mm / 1000.0,
        total_impulse=impulse,
        burn_time=burn,
        propellant_mass=prop,
        total_mass=total,
        approximate=True,
    )


# Placeholders only. Replace with real .eng files before you trust any number.
GENERIC: dict[str, Motor] = {
    "H-38": _generic("GENERIC H, 38mm", 38, 152, 250, 1.4, 0.13, 0.30),
    "I-38": _generic("GENERIC I, 38mm", 38, 240, 480, 1.7, 0.24, 0.50),
    "I-54-long": _generic("GENERIC I long burn, 54mm", 54, 260, 600, 4.0, 0.30, 0.70),
    "J-54": _generic("GENERIC J, 54mm", 54, 330, 900, 2.0, 0.45, 0.95),
    "J-54-long": _generic("GENERIC J long burn, 54mm", 54, 400, 1100, 4.5, 0.55, 1.15),
    "K-54": _generic("GENERIC K, 54mm", 54, 490, 1600, 2.3, 0.80, 1.50),
    "K-54-long": _generic("GENERIC K long burn, 54mm", 54, 570, 1900, 5.0, 0.95, 1.75),
    "K-75": _generic("GENERIC K, 75mm", 75, 460, 2400, 2.7, 1.20, 2.20),
    "L-75": _generic("GENERIC L, 75mm", 75, 660, 3600, 3.2, 1.80, 3.20),
}


def catalogue(directory: str | Path = "data/motors") -> dict[str, Motor]:
    """All real `.eng` motors in `directory`, falling back to GENERIC if empty."""
    directory = Path(directory)
    found: dict[str, Motor] = {}
    if directory.is_dir():
        for f in sorted(directory.glob("*.eng")):
            try:
                m = load_eng(f)
                found[m.name] = m
            except (ValueError, IndexError) as exc:  # pragma: no cover
                print(f"  skipped {f.name}: {exc}")
    return found or dict(GENERIC)
