"""Horizontal (and near-horizontal) launch: fly the manoeuvre, then score the turn.

WHY THIS EXISTS, AND WHY `control.heading_change` COULD NOT BE REUSED.

`heading_change` integrates a turn rate against `trajectory.simulate`'s speed history --
a vertical-plane flight with no manoeuvre in it. On a near-vertical launch that is a
defensible approximation and it cross-checks against `scripts/virtual_flight.py` to three
digits (docs/11 section 7). On a HORIZONTAL launch it is not an approximation, it is a
different flight:

  * Gravity stops being an axial decelerator. A vertical J401FJ flight loses ~27 m/s of
    speed to gravity during the burn and everything after burnout is a deceleration at
    1 g plus drag. Flown flat, gravity is PERPENDICULAR to the velocity and does not
    slow the vehicle at all -- it curves it. Burnout speed is higher and stays higher.
  * The vehicle no longer climbs out of its own air. A vertical flight spends its control
    window between 200 m and 1000 m, where rho falls 2%/100 m. A flat flight stays in the
    densest air there is.
  * The window does not end at apogee. It ends at the GROUND, and how long that takes is
    set by the launch elevation, which is now a design parameter rather than a fixed 5 deg
    off the rail.
  * The turn is in the HORIZONTAL plane, so azimuth (`atan2(vy, vx)`) is well conditioned
    -- which is exactly the number that is ill-conditioned on a vertical flight and which
    docs/11 warns against quoting. Flown flat, it is the right number.

THE ONE EQUATION THAT ORGANISES ALL OF THIS. Turn rate is

    psi_dot = n g0 / V   and   n g0 = q S CN / m = 0.5 rho V^2 S CN / m

so

    psi_dot = 0.5 rho V S CN / m           -- LINEAR in speed, linear in density
    R = V / psi_dot = 2 m / (rho S CN)     -- INDEPENDENT of speed entirely

Turn radius does not contain V. It never did; docs/11 section 4 makes the same point from
the other direction. So the only ways to tighten the circle are more density (fly low),
more CN (less static margin, more canard, more throw) or less mass. A horizontal launch
buys the first one outright and buys turn RATE through the speed it does not lose.

And the total heading change over a window is

    delta_psi = integral(psi_dot dt) = (1/R) * integral(V dt) = path_length / R

which is the result worth carrying away: **total heading change is path length divided by
turn radius**. Not time. A flat flight turns further than a vertical one because it covers
more ground before it runs out of air, not because it turns faster at any instant.

BANK POLICY. A stable rocket cannot lean; it weathercocks. All of its lateral force comes
from canard-trimmed alpha, and which way that force points is set by the ROLL angle. Two
policies bracket the design:

  max_rate   Bank 90 deg. All of the available force goes into the horizontal plane, none
             of it holds altitude, and the vehicle descends ballistically at 1 g while it
             turns. This is the highest instantaneous heading rate the airframe can make,
             and it is what a peak-deg/s number should be quoted against.
  sustain    Bank to phi = arccos(1/n), so the vertical component of the force exactly
             cancels weight and the vehicle holds altitude while turning with the rest.
             Costs rate (n_horizontal = sqrt(n^2 - 1) instead of n) and buys window: the
             flight does not fall out of its own control authority.

`sustain` is only available while n > 1. Below that the vehicle cannot hold level at any
bank and the policy degrades to max_rate, which is the honest thing for it to do -- there
is no altitude-holding trim to be had, so spending the force sideways at least turns.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import aero, atmosphere, control
from .geometry import Rocket
from .mass import cg_at_time
from .motors import Motor
from .trajectory import FlightPoint

G0 = atmosphere.G0

# Below this dynamic pressure the canards are decoration. Matches
# `control.heading_change` / `achievable_crossrange` so the two can be quoted side by side.
Q_MIN = 300.0

# Stop manoeuvring this far above the ground. A horizontal launch's window ends at the
# dirt, not at apogee, and a control law that is still pulling at 10 m AGL has no recovery
# event left. 50 m is the drogue-out-and-swing floor; see docs/00 R12 and section 9.
ALTITUDE_FLOOR_M = 50.0


@dataclass
class HorizontalFlight:
    """One flown manoeuvre. Everything here is measured, not assumed."""

    elevation_deg: float
    deflection_deg: float
    policy: str
    duty_cycle: float

    # -- the turn (the deliverable) --------------------------------------------------
    peak_rate_deg_s: float = 0.0
    mean_rate_deg_s: float = 0.0
    heading_deg: float = 0.0          # azimuth change of the horizontal velocity
    min_radius_m: float = float("inf")
    control_seconds: float = 0.0
    peak_lateral_g: float = 0.0
    stalled_anywhere: bool = False

    # Rotation of the FULL velocity vector under canard force, regardless of which plane
    # it happens in. This is the apples-to-apples number against `control.heading_change`
    # -- which cannot measure azimuth, because on the vertical flight it integrates,
    # azimuth is ill-conditioned (docs/11 section 7). On a flat, 90-deg-banked flight the
    # two agree by construction; on a `sustain` flight they do not, because part of the
    # force is being spent holding altitude and rotates the vector out of the ground plane.
    peak_vec_rate_deg_s: float = 0.0
    vec_turn_deg: float = 0.0
    min_vec_radius_m: float = float("inf")
    # Flight path angle (deg, + is climbing) at the instant `peak_rate_deg_s` was set.
    # THE GUARD ON THE AZIMUTH NUMBER. psi_dot = a_h / v_horiz, and v_horiz -> 0 as the
    # flight path goes vertical, so azimuth rate diverges on a steep flight while nothing
    # physical is happening. Quote `peak_rate_deg_s` only when this is shallow; quote
    # `peak_vec_rate_deg_s`, which has no such singularity, otherwise.
    fpa_at_peak_deg: float = 0.0
    steep_azimuth: bool = False

    # -- the flight it happened on ---------------------------------------------------
    rail_exit_v: float = 0.0
    burnout_speed: float = 0.0
    burnout_alt_m: float = 0.0
    burnout_fpa_deg: float = 0.0
    max_speed: float = 0.0
    max_mach: float = 0.0
    max_q: float = 0.0
    max_altitude_m: float = 0.0
    apogee_speed: float = 0.0
    max_axial_g: float = 0.0
    downrange_m: float = 0.0
    crossrange_m: float = 0.0
    flight_seconds: float = 0.0
    terminated: str = ""              # why the window closed
    path_length_m: float = 0.0
    samples: list = field(default_factory=list)

    @property
    def quarter_turn_seconds(self) -> float:
        """Seconds to swing the velocity vector 90 deg at the mean rate achieved."""
        return 90.0 / self.mean_rate_deg_s if self.mean_rate_deg_s > 0 else float("inf")


def fly(
    rocket: Rocket,
    motor: Motor,
    masses,
    elevation_deg: float = 10.0,
    deflection_deg: float = 8.0,
    policy: str = "max_rate",
    duty_cycle: float = 1.0,
    start_after_burnout: float = 0.5,
    rail_length: float = 3.66,
    rail_height_m: float = 2.0,
    dt: float = 0.01,
    max_time: float = 60.0,
    altitude_floor: float = ALTITUDE_FLOOR_M,
    q_min: float = Q_MIN,
    stop_at_apogee: bool = False,
    keep_samples: bool = False,
) -> HorizontalFlight:
    """Integrate a launch at `elevation_deg` above HORIZONTAL and turn it in azimuth.

    `start_after_burnout` may be negative to price boost-phase steering: -1.0 starts the
    manoeuvre 1.0 s BEFORE burnout. It is never allowed to start before rail exit.

    3-DOF point mass, weathercocking (the body axis is the velocity vector), which is the
    same assumption `trajectory.py` and `scripts/virtual_flight.py` already make. The
    lateral force comes from `control.pitch_authority` -- the project's one model of what
    a deflected canard does -- so this shares its aerodynamics with everything else here
    and cannot silently disagree with `baseline.py`.
    """
    if rocket.canards is None:
        raise ValueError("rocket has no canards")

    out = HorizontalFlight(
        elevation_deg=elevation_deg, deflection_deg=deflection_deg,
        policy=policy, duty_cycle=duty_cycle,
    )

    el = math.radians(elevation_deg)
    rail_dir = np.array([math.cos(el), 0.0, math.sin(el)])

    t = 0.0
    pos = np.array([0.0, 0.0, rail_height_m])
    vel = np.zeros(3)
    on_rail = True
    heading_unwrapped = 0.0
    prev_heading = 0.0
    steer_start = motor.burn_time + start_after_burnout

    while t < max_time:
        speed = float(np.linalg.norm(vel))
        z = float(pos[2])
        rho = atmosphere.density(max(z, 0.0))
        sound = atmosphere.speed_of_sound(max(z, 0.0))
        mass = masses.dry_mass + max(motor.mass_at(t) - motor.dry_mass, 0.0)
        thrust = motor.thrust(t)
        cg = cg_at_time(masses, motor, t, rocket)
        q = 0.5 * rho * speed * speed
        mach = speed / sound if sound > 1.0 else 0.0

        body = rail_dir.copy() if (on_rail or speed <= 0.1) else vel / speed

        # -- is the control law allowed to pull right now? ---------------------------
        # `stop_at_apogee` reproduces the VERTICAL convention -- `control.heading_change`
        # and `achievable_crossrange` both end their window at apogee, because that is
        # where the drogue comes out. It is set for the near-vertical cross-check below and
        # left off for flat flights, where apogee arrives seconds after burnout and the
        # useful window is the long descending arc after it.
        past_apogee = (not on_rail) and t > motor.burn_time and vel[2] <= 0.0
        steering = (
            (not on_rail)
            and t >= steer_start
            and q >= q_min
            and z >= altitude_floor
            and not (stop_at_apogee and past_apogee)
        )

        a_lat = 0.0
        lat_g = 0.0
        stalled = False
        cd = aero.drag_coefficient(rocket, speed, max(z, 0.0))
        if steering:
            pt = FlightPoint(t=t, x=float(pos[0]), z=z, vx=speed, vz=0.0, mass=mass,
                             thrust=thrust, mach=mach, q=q, cg=cg, static_margin=0.0)
            auth = control.pitch_authority(rocket, pt, mass, deflection_deg)
            stalled = auth.stalled
            lat_g = auth.lateral_accel_g * duty_cycle * (0.6 if stalled else 1.0)
            a_lat = lat_g * G0
            cn_alpha = aero.stability(rocket, cg, mach).cn_alpha
            cd += aero.induced_drag_coefficient(cn_alpha, math.radians(auth.alpha_trim_deg))
            out.stalled_anywhere = out.stalled_anywhere or stalled

        drag = 0.5 * rho * speed * speed * cd * rocket.reference_area
        force = thrust * body - drag * body + np.array([0.0, 0.0, -mass * G0])

        # -- put the lateral force somewhere -----------------------------------------
        # Two unit vectors perpendicular to the velocity: `horiz` turns azimuth (positive
        # to the left looking along the flight path), `vert` is the pull-up direction.
        rate = 0.0
        if a_lat > 1e-9 and speed > 1.0:
            horiz = np.array([-body[1], body[0], 0.0])
            nh = float(np.linalg.norm(horiz))
            if nh > 1e-9:
                horiz = horiz / nh
                vert = np.cross(body, horiz)
                vert = vert / (float(np.linalg.norm(vert)) + 1e-12)
                if vert[2] < 0:
                    vert = -vert

                n = lat_g  # load factor available, in g
                if policy == "sustain" and n > 1.0:
                    # cos(bank) * n = 1 holds altitude; the rest turns.
                    a_h = math.sqrt(max(n * n - 1.0, 0.0)) * G0
                    a_v = 1.0 * G0
                else:
                    a_h, a_v = a_lat, 0.0
                force = force + mass * (a_h * horiz + a_v * vert)
                # Only the horizontal component rotates the ground track.
                v_horiz = max(math.hypot(float(vel[0]), float(vel[1])), 1.0)
                rate = a_h / v_horiz  # rad/s of azimuth
                vec_rate = math.hypot(a_h, a_v) / max(speed, 1.0)
                if math.degrees(vec_rate) > out.peak_vec_rate_deg_s:
                    out.peak_vec_rate_deg_s = math.degrees(vec_rate)
                out.vec_turn_deg += math.degrees(vec_rate) * dt
                out.min_vec_radius_m = min(out.min_vec_radius_m,
                                           speed / vec_rate if vec_rate > 0 else float("inf"))
                fpa = math.degrees(math.asin(max(-1.0, min(1.0, float(vel[2]) / max(speed, 1e-6)))))
                if math.degrees(rate) > out.peak_rate_deg_s:
                    out.peak_rate_deg_s = math.degrees(rate)
                    out.fpa_at_peak_deg = fpa
                    out.steep_azimuth = abs(fpa) > 45.0
                out.peak_lateral_g = max(out.peak_lateral_g, n)
                out.min_radius_m = min(out.min_radius_m, v_horiz / rate if rate > 0
                                       else float("inf"))
                out.control_seconds += dt

        acc = force / mass
        if on_rail:
            along = max(float(np.dot(acc, rail_dir)), 0.0)
            acc = along * rail_dir

        out.max_axial_g = max(out.max_axial_g, float(np.linalg.norm(acc)) / G0)
        out.max_speed = max(out.max_speed, speed)
        out.max_mach = max(out.max_mach, mach)
        out.max_q = max(out.max_q, q)
        if z > out.max_altitude_m:
            out.max_altitude_m = z
            # THE SPEED AT APOGEE, and on a flat flight it is not small. Vertically the
            # vehicle arrives at the top doing about 1 m/s and every recovery event is
            # sized for that; flown flat the horizontal component never goes away, so
            # apogee is the minimum-speed point of the arc rather than a stop. It is still
            # the right deployment trigger; it is no longer a free one.
            out.apogee_speed = speed
        out.path_length_m += speed * dt

        if speed > 1.0:
            h = math.atan2(float(vel[1]), float(vel[0]))
            if not on_rail:
                d = h - prev_heading
                while d > math.pi:
                    d -= 2 * math.pi
                while d < -math.pi:
                    d += 2 * math.pi
                heading_unwrapped += d
            prev_heading = h

        if keep_samples:
            out.samples.append({
                "t": t, "x": float(pos[0]), "y": float(pos[1]), "z": z,
                "speed": speed, "q": q, "mach": mach, "lat_g": lat_g,
                "rate_dps": math.degrees(rate), "heading_deg": math.degrees(heading_unwrapped),
                "steering": steering,
            })

        vel = vel + acc * dt
        pos = pos + vel * dt
        t += dt

        if on_rail and float(np.linalg.norm(pos - np.array([0.0, 0.0, rail_height_m]))) >= rail_length:
            on_rail = False
            out.rail_exit_v = float(np.linalg.norm(vel))
            prev_heading = math.atan2(float(vel[1]), float(vel[0]))

        if out.burnout_speed == 0.0 and t >= motor.burn_time:
            out.burnout_speed = float(np.linalg.norm(vel))
            out.burnout_alt_m = float(pos[2])
            out.burnout_fpa_deg = math.degrees(math.asin(max(-1.0, min(
                1.0, float(vel[2]) / max(out.burnout_speed, 1e-6)))))

        if pos[2] <= 0.0:
            out.terminated = "ground"
            break
    else:
        out.terminated = "max_time"

    out.flight_seconds = t
    out.heading_deg = abs(math.degrees(heading_unwrapped))
    out.downrange_m = float(pos[0])
    out.crossrange_m = float(pos[1])
    out.mean_rate_deg_s = (out.heading_deg / out.control_seconds
                           if out.control_seconds > 0 else 0.0)
    return out


def turn_radius_closed_form(rocket: Rocket, cn_total: float, mass: float,
                            altitude_m: float = 0.0) -> float:
    """R = 2 m / (rho S CN). Speed does not appear. Used to sanity-check `fly`."""
    rho = atmosphere.density(altitude_m)
    return 2.0 * mass / (rho * rocket.reference_area * cn_total)
