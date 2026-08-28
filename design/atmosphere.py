"""US Standard Atmosphere 1976, troposphere only (valid to 11 km)."""

from __future__ import annotations

import math

G0 = 9.80665  # m/s^2
R_AIR = 287.0528  # J/(kg K)
GAMMA = 1.4
T0 = 288.15  # K
P0 = 101325.0  # Pa
LAPSE = -0.0065  # K/m


def properties(altitude_m: float) -> tuple[float, float, float, float]:
    """Return (temperature_K, pressure_Pa, density_kg_m3, speed_of_sound_m_s)."""
    h = max(0.0, min(altitude_m, 11000.0))
    t = T0 + LAPSE * h
    p = P0 * (t / T0) ** (-G0 / (LAPSE * R_AIR))
    rho = p / (R_AIR * t)
    a = math.sqrt(GAMMA * R_AIR * t)
    return t, p, rho, a


def density(altitude_m: float) -> float:
    return properties(altitude_m)[2]


def speed_of_sound(altitude_m: float) -> float:
    return properties(altitude_m)[3]


def dynamic_viscosity(temperature_k: float) -> float:
    """Sutherland's law for air."""
    return 1.458e-6 * temperature_k**1.5 / (temperature_k + 110.4)
