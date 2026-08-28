"""3-DOF point-mass ascent trajectory (2-D plane, RK4).

Assumptions: rocket flies along its velocity vector once off the rail (perfect
weathercocking), no wind unless supplied, constant gravity, no thrust misalignment.
Good enough to size an airframe; not good enough to design a controller against. The
controller needs the 6-DOF model that comes later, seeded with the aero derivatives from
`aero.py` and `control.py`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import aero, atmosphere
from .geometry import Rocket
from .mass import MassResult, cg_at_time
from .motors import Motor


@dataclass
class FlightPoint:
    t: float
    x: float
    z: float
    vx: float
    vz: float
    mass: float
    thrust: float
    mach: float
    q: float  # dynamic pressure, Pa
    cg: float
    static_margin: float

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vz)


@dataclass
class Flight:
    points: list[FlightPoint] = field(default_factory=list)
    rail_exit_velocity: float = 0.0
    burnout_time: float = 0.0
    burnout_velocity: float = 0.0
    burnout_altitude: float = 0.0
    apogee: float = 0.0
    apogee_time: float = 0.0
    max_mach: float = 0.0
    max_q: float = 0.0
    max_acceleration_g: float = 0.0
    thrust_to_weight: float = 0.0
    min_static_margin: float = 0.0
    max_static_margin: float = 0.0

    def summary(self) -> str:
        return (
            f"  T/W at ignition       {self.thrust_to_weight:7.2f}\n"
            f"  rail exit velocity    {self.rail_exit_velocity:7.1f} m/s\n"
            f"  max acceleration      {self.max_acceleration_g:7.1f} g\n"
            f"  burnout               {self.burnout_time:7.2f} s at "
            f"{self.burnout_altitude:6.0f} m, {self.burnout_velocity:5.1f} m/s\n"
            f"  max Mach              {self.max_mach:7.3f}\n"
            f"  max dynamic pressure  {self.max_q / 1000.0:7.2f} kPa\n"
            f"  apogee                {self.apogee:7.0f} m ({self.apogee * 3.28084:.0f} ft) "
            f"at {self.apogee_time:.1f} s\n"
            f"  static margin range   {self.min_static_margin:7.2f} to "
            f"{self.max_static_margin:.2f} cal"
        )


def simulate(
    rocket: Rocket,
    motor: Motor,
    masses: MassResult,
    rail_length: float = 3.66,  # 12 ft
    rail_angle_deg: float = 5.0,  # from vertical
    dt: float = 0.01,
    max_time: float = 120.0,
) -> Flight:
    """Integrate from ignition to apogee."""
    flight = Flight()
    angle = math.radians(rail_angle_deg)
    rail_dir = (math.sin(angle), math.cos(angle))

    t = 0.0
    x, z = 0.0, 0.0
    vx, vz = 0.0, 0.0
    on_rail = True

    # T/W uses average thrust, matching the usual high power convention. Sampling thrust
    # at t=0 would land inside the ignition transient and read absurdly low.
    w0 = masses.wet_mass * atmosphere.G0
    flight.thrust_to_weight = motor.average_thrust / w0 if w0 > 0 else 0.0

    def acceleration(t: float, x: float, z: float, vx: float, vz: float, on_rail: bool):
        speed = math.hypot(vx, vz)
        rho = atmosphere.density(z)
        mass = masses.dry_mass + max(motor.mass_at(t) - motor.dry_mass, 0.0)
        thrust = motor.thrust(t)

        if on_rail:
            dirx, dirz = rail_dir
        elif speed > 0.1:
            dirx, dirz = vx / speed, vz / speed
        else:
            dirx, dirz = rail_dir

        cd = aero.drag_coefficient(rocket, speed, z)
        drag = 0.5 * rho * speed**2 * cd * rocket.reference_area

        fx = thrust * dirx - drag * dirx
        fz = thrust * dirz - drag * dirz - mass * atmosphere.G0
        if on_rail:
            # Rail carries any transverse component.
            along = fx * rail_dir[0] + fz * rail_dir[1]
            along = max(along, 0.0)
            fx, fz = along * rail_dir[0], along * rail_dir[1]
        return fx / mass, fz / mass, mass, thrust, speed, rho, cd

    while t < max_time:
        ax, az, mass, thrust, speed, rho, _ = acceleration(t, x, z, vx, vz, on_rail)
        sound = atmosphere.speed_of_sound(z)
        mach = speed / sound
        q = 0.5 * rho * speed**2
        cg = cg_at_time(masses, motor, t, rocket)
        stab = aero.stability(rocket, cg, mach)

        flight.points.append(
            FlightPoint(t, x, z, vx, vz, mass, thrust, mach, q, cg, stab.static_margin_cal)
        )

        flight.max_mach = max(flight.max_mach, mach)
        flight.max_q = max(flight.max_q, q)
        flight.max_acceleration_g = max(flight.max_acceleration_g, math.hypot(ax, az) / atmosphere.G0)

        # RK4 on [x, z, vx, vz].
        def deriv(tt, s, on_rail_local):
            a = acceleration(tt, s[0], s[1], s[2], s[3], on_rail_local)
            return [s[2], s[3], a[0], a[1]]

        s0 = [x, z, vx, vz]
        k1 = deriv(t, s0, on_rail)
        k2 = deriv(t + dt / 2, [s0[i] + dt / 2 * k1[i] for i in range(4)], on_rail)
        k3 = deriv(t + dt / 2, [s0[i] + dt / 2 * k2[i] for i in range(4)], on_rail)
        k4 = deriv(t + dt, [s0[i] + dt * k3[i] for i in range(4)], on_rail)
        x, z, vx, vz = [
            s0[i] + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(4)
        ]
        t += dt

        if on_rail and math.hypot(x, z) >= rail_length:
            on_rail = False
            flight.rail_exit_velocity = math.hypot(vx, vz)

        if flight.burnout_time == 0.0 and t >= motor.burn_time:
            flight.burnout_time = t
            flight.burnout_velocity = math.hypot(vx, vz)
            flight.burnout_altitude = z

        if vz <= 0.0 and t > motor.burn_time:
            flight.apogee = z
            flight.apogee_time = t
            break

    margins = [p.static_margin for p in flight.points if p.speed > 10.0]
    if margins:
        flight.min_static_margin = min(margins)
        flight.max_static_margin = max(margins)
    if flight.apogee == 0.0 and flight.points:
        flight.apogee = max(p.z for p in flight.points)
    return flight


def coast_window(flight: Flight, q_min: float = 500.0) -> tuple[float, float]:
    """Time interval after burnout during which dynamic pressure still exceeds `q_min`,
    i.e. the window in which the canards can actually do something."""
    coasting = [p for p in flight.points if p.t >= flight.burnout_time and p.q >= q_min]
    if not coasting:
        return (flight.burnout_time, flight.burnout_time)
    return (coasting[0].t, coasting[-1].t)
