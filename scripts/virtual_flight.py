"""3-D virtual flight of the frozen baseline: ballistic, skid-to-turn, bank-to-turn.

Uses the same vehicle, motor curve, mass, drag, and canard derivatives as
`scripts/baseline.py`. Translation is the project's 3-DOF force model with the
lateral force from `control.pitch_authority` applied in 3-D. Roll uses the
project's steady-rate formula (the analytic panel-interference model — weakest
assumption, not flight-validated). Attitude is reconstructed from the velocity
vector plus bank, matching the weathercocking assumption in `trajectory.py`.

Run:  python scripts/virtual_flight.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import aero, atmosphere, control, trajectory
from design.configure import (
    DEFLECTION_LIMIT_DEG,
    ROLL_COMMAND_CAP_DEG,
    baseline,
    evaluate,
)
from design.packaging import SERVOS
from design.trajectory import FlightPoint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
HTML_PATH = OUT / "virtual_flight.html"
JSON_PATH = OUT / "virtual_flight.json"
PLOT_PATH = OUT / "virtual_flight.png"

G0 = atmosphere.G0
SLEW_DEG_S = 60.0 / SERVOS["kst_x08_plus"].speed_60deg  # 667 deg/s
STT_START = 0.5  # seconds after burnout, same as control.achievable_crossrange
Q_MIN = 300.0


def _point(t, pos, vel, mass, thrust, cg) -> FlightPoint:
    speed = float(np.linalg.norm(vel))
    z = float(pos[2])
    rho = atmosphere.density(z)
    sound = atmosphere.speed_of_sound(z)
    q = 0.5 * rho * speed * speed
    return FlightPoint(
        t=t,
        x=float(pos[0]),
        z=z,
        vx=speed,
        vz=0.0,
        mass=mass,
        thrust=thrust,
        mach=speed / sound if sound > 1.0 else 0.0,
        q=q,
        cg=cg,
        static_margin=0.0,
    )


def _mass_state(masses, motor, rocket, t):
    from design.mass import cg_at_time

    mass = masses.dry_mass + max(motor.mass_at(t) - motor.dry_mass, 0.0)
    thrust = motor.thrust(t)
    cg = cg_at_time(masses, motor, t, rocket)
    return mass, thrust, cg


def _rodrigues(v, axis, angle):
    axis = axis / (np.linalg.norm(axis) + 1e-12)
    c, s = math.cos(angle), math.sin(angle)
    return v * c + np.cross(axis, v) * s + axis * np.dot(axis, v) * (1.0 - c)


def _commands(mode, t, burnout, q, roll_deg, heading_deg):
    idle = (0.0, 0.0, 0.0)
    if mode == "ballistic":
        return idle
    if t < burnout + STT_START or q < Q_MIN:
        return idle
    if mode == "stt":
        return (0.0, DEFLECTION_LIMIT_DEG, 0.0)
    if mode == "btt":
        # Hold the 2° roll cap until 90° bank, then pull 8° in the banked plane.
        # Keep a trickle of roll command to hold bank against damping.
        roll_cmd = ROLL_COMMAND_CAP_DEG if roll_deg < 90.0 else 0.35
        pitch_cmd = DEFLECTION_LIMIT_DEG if roll_deg >= 80.0 else 0.0
        return (pitch_cmd, 0.0, roll_cmd)
    return idle


def simulate_3d(rocket, motor, masses, mode: str, dt: float = 0.005, max_time: float = 18.0):
    rail_len = 3.66
    rail_angle = math.radians(5.0)
    rail_dir = np.array([math.sin(rail_angle), 0.0, math.cos(rail_angle)])

    t = 0.0
    pos = np.zeros(3)
    vel = np.zeros(3)
    on_rail = True
    roll = 0.0
    delta_e = delta_r = delta_a = 0.0
    burnout_t = motor.burn_time

    rec = []
    rail_exit_v = 0.0
    apogee = 0.0
    apogee_t = 0.0
    max_mach = 0.0
    max_q = 0.0
    max_az_g = 0.0
    max_turn_dps = 0.0
    max_roll_dps = 0.0
    heading_45_t = None

    slew = math.radians(SLEW_DEG_S)

    def step_actuator(cur, cmd):
        err = math.radians(cmd) - cur
        return cur + float(np.clip(err, -slew * dt, slew * dt))

    while t <= max_time:
        mass, thrust, cg = _mass_state(masses, motor, rocket, t)
        pt = _point(t, pos, vel, mass, thrust, cg)
        speed = pt.vx
        rho = atmosphere.density(pos[2])

        cmd_e, cmd_r, cmd_a = _commands(mode, t, burnout_t, pt.q, math.degrees(roll), 0.0)
        delta_e = step_actuator(delta_e, cmd_e)
        delta_r = step_actuator(delta_r, cmd_r)
        delta_a = step_actuator(delta_a, cmd_a)

        if on_rail:
            body = rail_dir.copy()
        elif speed > 0.1:
            body = vel / speed
        else:
            body = rail_dir.copy()

        cd0 = aero.drag_coefficient(rocket, speed, float(pos[2]))
        delta_mag = math.degrees(math.hypot(delta_e, delta_r))
        a_lat = 0.0
        alpha_deg = 0.0
        stalled = False
        lat_g = 0.0
        if delta_mag > 0.05 and not on_rail and pt.q > 50.0:
            auth = control.pitch_authority(rocket, pt, mass, delta_mag)
            alpha_deg = auth.alpha_trim_deg
            stalled = auth.stalled
            lat_g = auth.lateral_accel_g * (0.6 if stalled else 1.0)
            a_lat = lat_g * G0
            cn_alpha = aero.stability(rocket, cg, pt.mach).cn_alpha
            cd0 += aero.induced_drag_coefficient(cn_alpha, math.radians(alpha_deg))

        drag = 0.5 * rho * speed * speed * cd0 * rocket.reference_area
        force = thrust * body - drag * body + np.array([0.0, 0.0, -mass * G0])

        lift_dir = np.zeros(3)
        if a_lat > 1e-6 and speed > 1.0:
            if mode == "stt":
                desired = np.array([0.0, 1.0, 0.0])
                lift_dir = desired - body * np.dot(desired, body)
            else:
                # Banked lift: roll the launch-plane pitch lift about the velocity.
                lift0 = np.array([body[2], 0.0, -body[0]])
                lift_dir = _rodrigues(lift0, body, roll)
            nrm = np.linalg.norm(lift_dir)
            if nrm > 1e-9:
                lift_dir = lift_dir / nrm
                force = force + mass * a_lat * lift_dir

        # Roll: first-order toward the project's steady-state rate at current δa.
        p = 0.0
        if abs(delta_a) > 1e-4 and not on_rail and pt.q > 50.0 and speed > 1.0:
            roll_res = control.roll_authority(
                rocket,
                pt,
                mass,
                math.degrees(abs(delta_a)),
                control.InterferenceModel.interdigitated(),
            )
            p = math.radians(roll_res.steady_roll_rate_deg_s) * math.copysign(1.0, delta_a)
            # Don't overshoot the 90° target in BTT.
            if mode == "btt" and roll >= math.radians(90.0) and p > 0.0:
                p = 0.0
                roll = math.radians(90.0)
        roll = float(np.clip(roll + p * dt, 0.0, math.radians(90.0)))

        acc = force / mass
        if on_rail:
            along = float(np.dot(acc, rail_dir))
            along = max(along, 0.0)
            acc = along * rail_dir

        vel = vel + acc * dt
        pos = pos + vel * dt
        t += dt

        if on_rail and float(np.linalg.norm(pos)) >= rail_len:
            on_rail = False
            rail_exit_v = float(np.linalg.norm(vel))

        # WHAT THIS IS, AND WHAT IT IS NOT. This is the compass AZIMUTH of the
        # horizontal velocity component, and on a near-vertical trajectory it is
        # ill-conditioned: vx is small (a 5 deg rail leaves little downrange against a lot
        # of climb), so a modest vy swings it a long way. On the frozen J401FJ vehicle the
        # stt run ends at vx 8.7, vy 40.7, vz ~0 -- azimuth 78.0 deg, on a velocity vector
        # whose magnitude has fallen to 42 m/s.
        #
        # It is NOT "the vehicle turned 78 degrees". The canard-induced rotation of the
        # velocity vector over the same window, integrated as a_lat/V, is 34.6 deg -- and
        # `design.control.heading_change` independently gets 32.0 deg on the same vehicle,
        # with peak rates matching to 6.49 vs 6.47 deg/s. Quote that number against a
        # missile, not this one. See docs/11-agility-comparison.md section 7.
        #
        # (Pre-freeze, on the J449, the same three numbers were 71.1 / 25.0 / 23.4 deg.
        # The artefact is structural, not a property of one vehicle.)
        heading = math.degrees(math.atan2(vel[1], vel[0])) if speed > 1.0 else 0.0
        flight_path = math.degrees(math.asin(np.clip(vel[2] / max(speed, 1e-6), -1.0, 1.0)))
        turn_dps = math.degrees(a_lat / max(speed, 1.0))
        az_g = float(np.linalg.norm(acc)) / G0

        max_mach = max(max_mach, pt.mach)
        max_q = max(max_q, pt.q)
        max_az_g = max(max_az_g, az_g)
        max_turn_dps = max(max_turn_dps, turn_dps)
        max_roll_dps = max(max_roll_dps, abs(math.degrees(p)))
        if heading_45_t is None and heading >= 45.0:
            heading_45_t = t
        if pos[2] > apogee:
            apogee = float(pos[2])
            apogee_t = t

        # Canard mix for the viewer: 45/135/225/315 deg, interdigitated.
        de, dr, da = math.degrees(delta_e), math.degrees(delta_r), math.degrees(delta_a)
        canards = [
            de * math.cos(math.radians(phi)) + dr * math.sin(math.radians(phi)) + da
            for phi in (45.0, 135.0, 225.0, 315.0)
        ]

        rec.append(
            {
                "t": round(t, 4),
                "x": float(pos[0]),
                "y": float(pos[1]),
                "z": float(pos[2]),
                "vx": float(vel[0]),
                "vy": float(vel[1]),
                "vz": float(vel[2]),
                "speed": speed,
                "mach": pt.mach,
                "q": pt.q,
                "thrust": thrust,
                "mass": mass,
                "roll": math.degrees(roll),
                "p": math.degrees(p),
                "heading": heading,
                "fpa": flight_path,
                "alpha": alpha_deg,
                "lat_g": lat_g,
                "az_g": az_g,
                "turn_dps": turn_dps,
                "delta_e": de,
                "delta_r": dr,
                "delta_a": da,
                "canards": canards,
                "body": body.tolist(),
                "lift": lift_dir.tolist(),
            }
        )

        if (not on_rail) and vel[2] <= 0.0 and t > burnout_t:
            break

    # Downsample for the viewer (~50 Hz is enough).
    stride = max(1, int(0.02 / dt))
    slim = rec[::stride]
    if rec and slim[-1] is not rec[-1]:
        slim.append(rec[-1])

    burnout_idx = min(range(len(rec)), key=lambda i: abs(rec[i]["t"] - burnout_t))
    bp = rec[burnout_idx]
    return {
        "mode": mode,
        "samples": slim,
        "summary": {
            "rail_exit_m_s": rail_exit_v,
            "burnout_s": burnout_t,
            "burnout_alt_m": bp["z"],
            "burnout_v_m_s": bp["speed"],
            "apogee_m": apogee,
            "apogee_s": apogee_t,
            "max_mach": max_mach,
            "max_q_kpa": max_q / 1000.0,
            "max_accel_g": max_az_g,
            "max_turn_dps": max_turn_dps,
            "max_roll_dps": max_roll_dps,
            "heading_45_s": heading_45_t,
            "final_heading_deg": rec[-1]["heading"],
            "final_x_m": rec[-1]["x"],
            "final_y_m": rec[-1]["y"],
            "peak_lat_g": max(s["lat_g"] for s in rec),
        },
    }


def _write_plots(flights: dict):
    fig = plt.figure(figsize=(15, 10))
    fig.suptitle(
        "GV-3  ·  Cesaroni J449BS  ·  live baseline derivatives",
        fontsize=14,
        fontweight="bold",
        color="#2A2420",
    )

    ax3 = fig.add_subplot(2, 2, (1, 3), projection="3d")
    colors = {"ballistic": "#7A7268", "stt": "#C46A3A", "btt": "#2E5A8C"}
    labels = {
        "ballistic": "Ballistic (canards faired)",
        "stt": "Skid-to-turn  8° yaw",
        "btt": "Bank-to-turn  2° roll → 8° pitch",
    }
    for key, fl in flights.items():
        s = fl["samples"]
        ax3.plot(
            [p["x"] / 1000 for p in s],
            [p["y"] / 1000 for p in s],
            [p["z"] for p in s],
            color=colors[key],
            lw=2.2 if key != "ballistic" else 1.6,
            label=labels[key],
        )
    ax3.scatter([0], [0], [0], color="#3A7A3A", s=40, label="Rail")
    ax3.set_xlabel("Downrange (km)")
    ax3.set_ylabel("Crossrange (km)")
    ax3.set_zlabel("Altitude (m)")
    ax3.set_title("Ascent to apogee")
    ax3.legend(loc="upper left", fontsize=8)
    ax3.grid(True, alpha=0.3)

    ax2 = fig.add_subplot(2, 2, 2)
    for key, fl in flights.items():
        s = fl["samples"]
        ax2.plot([p["t"] for p in s], [p["heading"] for p in s], color=colors[key], lw=2, label=labels[key])
    ax2.axhline(45, color="#888", ls="--", lw=1, alpha=0.7)
    ax2.set_ylabel("Velocity heading (deg)")
    ax2.set_title("Turn: heading of the velocity vector")
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=7)

    ax4 = fig.add_subplot(2, 2, 4)
    for key, fl in flights.items():
        s = fl["samples"]
        ax4.plot([p["t"] for p in s], [p["lat_g"] for p in s], color=colors[key], lw=2)
        ax4.plot([p["t"] for p in s], [p["turn_dps"] for p in s], color=colors[key], lw=1.2, ls=":")
    ax4.set_xlabel("Time (s)")
    ax4.set_ylabel("Lateral g   /   turn rate (deg/s, dotted)")
    ax4.set_title("Turning authority after burnout")
    ax4.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(PLOT_PATH, dpi=140, bbox_inches="tight", facecolor="#F3EFE6")
    plt.close(fig)


def main():
    ev = evaluate(baseline(), deflection_deg=DEFLECTION_LIMIT_DEG)
    rocket, motor, masses, flight = ev.rocket, ev.params.motor, ev.masses, ev.flight
    t0, t1 = trajectory.coast_window(flight)
    pt = max((p for p in flight.points if p.t >= flight.burnout_time), key=lambda p: p.q)
    pitch = control.pitch_authority(rocket, pt, pt.mass, DEFLECTION_LIMIT_DEG)
    roll2 = control.roll_authority(
        rocket, pt, pt.mass, ROLL_COMMAND_CAP_DEG, control.InterferenceModel.interdigitated()
    )
    roll8 = control.roll_authority(
        rocket, pt, pt.mass, DEFLECTION_LIMIT_DEG, control.InterferenceModel.interdigitated()
    )
    v = pt.speed
    a = pitch.lateral_accel_g * G0
    turn_dps = math.degrees(a / v)
    radius = v * v / a if a > 0 else float("inf")
    t_45 = 45.0 / turn_dps if turn_dps > 0 else float("inf")

    print("=== LIVE BASELINE (configure.evaluate) ===")
    print(flight.summary())
    print(f"  usable control window {t1 - t0:7.1f} s")
    print(f"  wet/dry mass          {masses.wet_mass:.3f} / {masses.dry_mass:.3f} kg")
    print()
    print("=== TURNING SPEED at max-Q coast (the number you asked for) ===")
    print(f"  condition             t={pt.t:.2f}s  V={v:.1f} m/s  q={pt.q/1000:.2f} kPa  M={pt.mach:.3f}")
    print(f"  pitch at {DEFLECTION_LIMIT_DEG:.0f}°           {pitch.lateral_accel_g:.3f} g   "
          f"α_trim {pitch.alpha_trim_deg:.2f}°   wn {pitch.pitch_natural_freq_hz:.2f} Hz")
    print(f"  turn rate             {turn_dps:.2f} deg/s")
    print(f"  turn radius           {radius:.0f} m  ({radius/1000:.2f} km)")
    print(f"  time for 45° heading  {t_45:.1f} s   (control window {t1-t0:.1f} s)")
    print(f"  roll at {ROLL_COMMAND_CAP_DEG:.0f}° cap        {roll2.steady_roll_rate_deg_s:.0f} deg/s   "
          f"(90° snap {90/roll2.steady_roll_rate_deg_s:.3f} s)")
    print(f"  roll at {DEFLECTION_LIMIT_DEG:.0f}° aero limit  {roll8.steady_roll_rate_deg_s:.0f} deg/s")
    print(f"  Cl_δ net / Cl_p       {roll2.cl_delta_net:.3f} / {roll2.cl_p:.2f}   "
          f"(interference model — not flight-validated)")
    print()

    flights = {}
    for mode in ("ballistic", "stt", "btt"):
        print(f"integrating {mode}...")
        flights[mode] = simulate_3d(rocket, motor, masses, mode)
        s = flights[mode]["summary"]
        print(
            f"  apogee {s['apogee_m']:.0f} m @ {s['apogee_s']:.1f}s   "
            f"crossrange {s['final_y_m']:.0f} m   heading {s['final_heading_deg']:.1f}°   "
            f"peak {s['peak_lat_g']:.2f} g / {s['max_turn_dps']:.2f} deg/s"
        )

    OUT.mkdir(exist_ok=True)
    payload = {
        "vehicle": {
            "name": "GV-3",
            "motor": motor.name,
            "length_m": rocket.length,
            "diameter_m": rocket.diameter,
            "nose_length_m": rocket.nose.length,
            "canard": {
                "root": rocket.canards.root_chord,
                "tip": rocket.canards.tip_chord,
                "semispan": rocket.canards.semispan,
                "sweep": rocket.canards.sweep_length,
                "x_le": rocket.canards.x_root_le,
            },
            "aft": {
                "root": rocket.aft_fins.root_chord,
                "tip": rocket.aft_fins.tip_chord,
                "semispan": rocket.aft_fins.semispan,
                "sweep": rocket.aft_fins.sweep_length,
                "x_le": rocket.aft_fins.x_root_le,
            },
            "wet_kg": masses.wet_mass,
            "dry_kg": masses.dry_mass,
        },
        "authority": {
            "lat_g_per_deg": pitch.lateral_accel_g / DEFLECTION_LIMIT_DEG,
            "lat_g_at_8": pitch.lateral_accel_g,
            "turn_dps": turn_dps,
            "turn_radius_m": radius,
            "t_45_s": t_45,
            "roll_2deg_dps": roll2.steady_roll_rate_deg_s,
            "roll_8deg_dps": roll8.steady_roll_rate_deg_s,
            "control_window_s": t1 - t0,
            "pitch_wn_hz": pitch.pitch_natural_freq_hz,
        },
        "reference_3dof": {
            "apogee_m": flight.apogee,
            "apogee_s": flight.apogee_time,
            "burnout_s": flight.burnout_time,
            "burnout_alt_m": flight.burnout_altitude,
            "burnout_v_m_s": flight.burnout_velocity,
            "max_mach": flight.max_mach,
            "max_q_kpa": flight.max_q / 1000.0,
            "max_accel_g": flight.max_acceleration_g,
            "rail_exit_m_s": flight.rail_exit_velocity,
            "twr": flight.thrust_to_weight,
        },
        "flights": {k: {"mode": v["mode"], "summary": v["summary"], "samples": v["samples"]} for k, v in flights.items()},
    }
    JSON_PATH.write_text(json.dumps(payload))
    _write_html(payload)
    _write_plots(flights)
    print(f"\nviewer: {HTML_PATH}")
    print(f"plot:   {PLOT_PATH}")


def _write_html(payload: dict):
    data = json.dumps(payload)
    HTML_PATH.write_text(HTML_TEMPLATE.replace("__DATA__", data))


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GV-3  range replay</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500&display=swap" rel="stylesheet"/>
<style>
  :root {
    --dust: #C9B896;
    --playa: #B7A484;
    --shade: #1C1814;
    --panel: rgba(28, 24, 20, 0.82);
    --ink: #F4EDE0;
    --mute: #B4A894;
    --copper: #C46A3A;
    --streak: #3D6B9A;
    --g10: #6B5A3E;
    --ok: #7A9A62;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; background: #6f8794; color: var(--ink); font-family: "IBM Plex Sans", sans-serif; overflow: hidden; }
  #stage {
    position: absolute;
    top: 70px;
    left: 262px;
    right: 296px;
    bottom: 124px;
  }
  #view {
    position: absolute;
    inset: 0;
    width: 100% !important;
    height: 100% !important;
    display: block;
  }
  .hud { position: absolute; z-index: 2; pointer-events: none; }
  .hud button, .hud select, .hud input { pointer-events: auto; }
  header.hud {
    top: 0; left: 0; right: 0; padding: 18px 22px 0;
    display: flex; justify-content: space-between; align-items: flex-start;
    text-shadow: 0 1px 0 rgba(0,0,0,.35);
  }
  h1 { font-family: "Barlow Condensed", sans-serif; font-weight: 700; font-size: 34px; letter-spacing: 0.04em; line-height: 0.9; }
  h1 span { display: block; font-size: 13px; font-weight: 500; letter-spacing: 0.18em; color: var(--dust); margin-bottom: 4px; }
  .modes { display: flex; gap: 6px; pointer-events: auto; }
  .modes button {
    background: var(--panel); color: var(--ink); border: 1px solid rgba(244,237,224,.18);
    padding: 8px 12px; font: 500 13px "IBM Plex Sans", sans-serif; cursor: pointer;
  }
  .modes button.on { background: var(--copper); border-color: var(--copper); color: #1C1814; }
  aside.hud {
    top: 92px; left: 22px; width: 228px;
    background: rgba(28, 24, 20, 0.92); padding: 14px 14px 10px;
    border-left: 3px solid var(--copper);
  }
  aside h2 { font-family: "Barlow Condensed", sans-serif; font-size: 18px; letter-spacing: 0.08em; margin-bottom: 8px; }
  .evt { display: grid; grid-template-columns: 52px 1fr; gap: 2px 10px; font-family: "IBM Plex Mono", monospace; font-size: 11px; line-height: 1.55; color: var(--mute); }
  .evt b { color: var(--ink); font-weight: 500; }
  .evt .now { color: var(--copper); }
  footer.hud {
    left: 0; right: 0; bottom: 0; padding: 0 22px 16px;
    display: grid; grid-template-columns: 1fr auto; gap: 16px; align-items: end;
  }
  .gauges { display: grid; grid-template-columns: repeat(6, minmax(90px, 1fr)); gap: 8px; }
  .g { background: var(--panel); padding: 8px 10px 7px; min-width: 0; }
  .g em { display: block; font-style: normal; font-family: "IBM Plex Mono", monospace; font-size: 10px; color: var(--mute); }
  .g strong { font-family: "Barlow Condensed", sans-serif; font-size: 28px; font-weight: 700; letter-spacing: 0.02em; line-height: 1; }
  .g strong small { font-size: 14px; color: var(--mute); margin-left: 3px; }
  .transport { display: flex; align-items: center; gap: 10px; pointer-events: auto; background: var(--panel); padding: 10px 12px; }
  .transport button {
    background: transparent; color: var(--ink); border: 1px solid rgba(244,237,224,.25);
    min-width: 36px; height: 32px; padding: 0 8px; cursor: pointer; font-size: 14px;
  }
  .transport button.on { background: var(--copper); border-color: var(--copper); color: #1C1814; }
  .transport input[type=range] { width: 180px; accent-color: var(--copper); }
  .transport .t { font-family: "IBM Plex Mono", monospace; font-size: 13px; min-width: 70px; }
  .hint { font-family: "IBM Plex Mono", monospace; font-size: 10px; color: var(--mute); line-height: 1.3; max-width: 160px; }
  .note {
    position: absolute; top: 92px; right: 22px; width: 260px;
    background: var(--panel); padding: 12px 14px; font-size: 12px; line-height: 1.45; color: var(--mute);
  }
  .note b { color: var(--ink); font-weight: 500; }
  @media (max-width: 900px) {
    .gauges { grid-template-columns: repeat(3, 1fr); }
    .note, aside.hud { display: none; }
    h1 { font-size: 26px; }
    #stage { left: 12px; right: 12px; }
  }
</style>
</head>
<body>
<div id="stage"><canvas id="view"></canvas></div>
<header class="hud">
  <h1><span>RANGE REPLAY</span>GV-3  /  J449BS</h1>
  <div class="modes">
    <button data-mode="ballistic">Ballistic</button>
    <button data-mode="stt" class="on">Skid-to-turn</button>
    <button data-mode="btt">Bank-to-turn</button>
  </div>
</header>
<aside class="hud">
  <h2>FLIGHT CARD</h2>
  <div class="evt" id="events"></div>
</aside>
<div class="note hud" id="note"></div>
<footer class="hud">
  <div class="gauges">
    <div class="g"><em>altitude</em><strong id="g-z">0<small>m</small></strong></div>
    <div class="g"><em>speed</em><strong id="g-v">0<small>m/s</small></strong></div>
    <div class="g"><em>heading</em><strong id="g-hdg">0<small>°</small></strong></div>
    <div class="g"><em>turn rate</em><strong id="g-turn">0<small>°/s</small></strong></div>
    <div class="g"><em>lateral</em><strong id="g-lat">0<small>g</small></strong></div>
    <div class="g"><em>roll rate</em><strong id="g-roll">0<small>°/s</small></strong></div>
  </div>
  <div class="transport">
    <button id="play" title="play/pause">❚❚</button>
    <button id="rate" title="speed">0.25×</button>
    <input id="scrub" type="range" min="0" max="1000" value="0"/>
    <div class="t" id="clock">0.00 s</div>
    <button id="zoom-out" title="zoom out">−</button>
    <button id="zoom-in" title="zoom in">+</button>
    <button id="frame" title="frame the rocket">frame</button>
    <button id="follow" class="on" title="keep the camera on the rocket">follow</button>
    <div class="hint">scroll zoom · drag orbit · right-drag pan</div>
  </div>
</footer>
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const DATA = __DATA__;
const $ = (id) => document.getElementById(id);

let mode = "stt";
let playing = true;
let rate = 0.25;
let clock = 3.2;
const rates = [0.25, 1, 4];

const canvas = $("view");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x7f9aab);
scene.fog = new THREE.Fog(0x7f9aab, 4000, 16000);
const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 20000);
camera.position.set(3.2, 1.6, 3.8);

scene.add(new THREE.HemisphereLight(0xdde8ee, 0x6b5a3e, 1.1));
const sun = new THREE.DirectionalLight(0xfff1d6, 1.35);
sun.position.set(400, 900, 600);
sun.castShadow = true;
scene.add(sun);

const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(8000, 8000),
  new THREE.MeshLambertMaterial({ color: 0x8f7f62 })
);
ground.rotation.x = -Math.PI / 2;
ground.receiveShadow = true;
scene.add(ground);
const grid = new THREE.GridHelper(4000, 40, 0x8a7a5e, 0xb0a07e);
grid.position.y = 0.04;
scene.add(grid);

const railLen = 3.66;
const railTilt = 5 * Math.PI / 180;
const rail = new THREE.Mesh(
  new THREE.CylinderGeometry(0.025, 0.025, railLen, 8),
  new THREE.MeshStandardMaterial({ color: 0x3a3530, metalness: 0.55, roughness: 0.45 })
);
rail.position.set(Math.sin(railTilt) * railLen / 2, Math.cos(railTilt) * railLen / 2, 0);
rail.rotation.z = -railTilt;
scene.add(rail);

function trapFin(root, tip, span, sweep, thick) {
  const s = new THREE.Shape();
  s.moveTo(0, 0);
  s.lineTo(root, 0);
  s.lineTo(sweep + tip, span);
  s.lineTo(sweep, span);
  s.closePath();
  const geo = new THREE.ExtrudeGeometry(s, { depth: thick, bevelEnabled: false });
  geo.translate(0, 0, -thick / 2);
  return geo;
}

function addFinSet(parent, spec, count, clock0, mat, R, hinged) {
  const hinges = [];
  for (let i = 0; i < count; i++) {
    const panel = new THREE.Mesh(trapFin(spec.root, spec.tip, spec.semispan, spec.sweep, 0.0032), mat);
    panel.rotation.z = -Math.PI / 2;
    panel.position.x = R;
    const hinge = new THREE.Group();
    hinge.add(panel);
    hinge.position.y = spec.x_le + (hinged ? spec.root * 0.20 : 0);
    hinge.rotation.y = clock0 + i * (Math.PI * 2 / count);
    parent.add(hinge);
    hinges.push(hinge);
  }
  return hinges;
}

function buildRocket(v) {
  const g = new THREE.Group();
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0xefe6d4, roughness: 0.45, metalness: 0.08 });
  const noseMat = new THREE.MeshStandardMaterial({ color: 0x2b2722, roughness: 0.55 });
  const finMat = new THREE.MeshStandardMaterial({ color: 0x1e1a16, roughness: 0.7 });
  const canMat = new THREE.MeshStandardMaterial({ color: 0xe39a3a, roughness: 0.4, emissive: 0x5a2a00, emissiveIntensity: 0.25 });

  const pts = [];
  const Ln = v.nose_length_m, R = v.diameter_m / 2, L = v.length_m;
  for (let i = 0; i <= 16; i++) {
    const x = (i / 16) * Ln;
    const rho = (R*R + Ln*Ln) / (2*R);
    const r = Math.sqrt(Math.max(rho*rho - (Ln - x)*(Ln - x), 0)) + R - rho;
    pts.push(new THREE.Vector2(r, x));
  }
  g.add(new THREE.Mesh(new THREE.LatheGeometry(pts, 28), noseMat));

  const tube = new THREE.Mesh(new THREE.CylinderGeometry(R, R, L - Ln, 28), bodyMat);
  tube.position.y = Ln + (L - Ln) / 2;
  g.add(tube);
  const bandMat = new THREE.MeshStandardMaterial({ color: 0xc46a3a, roughness: 0.35 });
  const inkMat = new THREE.MeshStandardMaterial({ color: 0x1c1814, roughness: 0.5 });
  for (const [y, mat] of [
    [v.canard.x_le + v.canard.root * 0.5, bandMat],
    [v.aft.x_le + 0.04, inkMat],
  ]) {
    const band = new THREE.Mesh(new THREE.CylinderGeometry(R + 0.0012, R + 0.0012, 0.045, 24), mat);
    band.position.y = y;
    g.add(band);
  }

  addFinSet(g, v.aft, 4, 0, finMat, R, false);
  const canards = addFinSet(g, v.canard, 4, Math.PI / 4, canMat, R, true);

  const flame = new THREE.Mesh(
    new THREE.ConeGeometry(R * 0.7, 0.55, 12),
    new THREE.MeshBasicMaterial({ color: 0x4a7ab5, transparent: true, opacity: 0.88 })
  );
  flame.position.y = L + 0.22;
  flame.rotation.x = Math.PI;
  g.add(flame);

  // Origin at mid-body so orbit/zoom aim at the airframe, not the nose tip.
  for (const child of g.children) child.position.y -= L * 0.5;
  // Visual scale only. Positions stay in real metres; 79 mm at 5 m is a thread.
  g.scale.setScalar(10);
  g.userData = { canards, flame, length: L };
  return g;
}

const rocket = buildRocket(DATA.vehicle);
scene.add(rocket);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.12;
controls.enablePan = true;
controls.enableZoom = true;
controls.zoomSpeed = 1.15;
controls.rotateSpeed = 0.85;
controls.panSpeed = 0.8;
controls.minDistance = 2;
controls.maxDistance = 4000;
controls.target.set(0, 1, 0);
controls.update();

let follow = true;

const trails = {};
const grounds = {};
const trailCols = { ballistic: 0x7a7268, stt: 0xc46a3a, btt: 0x2e5a8c };
for (const key of Object.keys(DATA.flights)) {
  const line = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: trailCols[key], transparent: true, opacity: key === mode ? 1 : 0.28 }));
  const gnd = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: trailCols[key], transparent: true, opacity: 0.45 }));
  scene.add(line);
  scene.add(gnd);
  trails[key] = line;
  grounds[key] = gnd;
}

function samples() { return DATA.flights[mode].samples; }
function tMax() { return samples()[samples().length - 1].t; }

function atTime(t) {
  const s = samples();
  if (t <= s[0].t) return s[0];
  if (t >= s[s.length - 1].t) return s[s.length - 1];
  let lo = 0, hi = s.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (s[mid].t <= t) lo = mid; else hi = mid;
  }
  const a = s[lo], b = s[hi];
  const u = (t - a.t) / Math.max(b.t - a.t, 1e-9);
  const lerp = (k) => a[k] + (b[k] - a[k]) * u;
  const out = { ...a };
  for (const k of ["x","y","z","vx","vy","vz","speed","mach","q","thrust","mass","roll","p","heading","fpa","alpha","lat_g","az_g","turn_dps","delta_e","delta_r","delta_a"]) out[k] = lerp(k);
  out.canards = a.canards.map((v, i) => v + (b.canards[i] - v) * u);
  out.body = a.body.map((v, i) => v + (b.body[i] - v) * u);
  return out;
}

function updateTrails() {
  for (const [key, line] of Object.entries(trails)) {
    const s = DATA.flights[key].samples.filter(p => p.t <= clock + 0.0001);
    const pts = s.map(p => new THREE.Vector3(p.x, p.z, p.y));
    line.geometry.setFromPoints(pts.length ? pts : [new THREE.Vector3()]);
    line.material.opacity = key === mode ? 1 : 0.22;
    grounds[key].geometry.setFromPoints(pts.length ? pts.map(v => new THREE.Vector3(v.x, 0.3, v.z)) : [new THREE.Vector3()]);
    grounds[key].material.opacity = key === mode ? 0.7 : 0.2;
  }
}

const _box = new THREE.Box3();
function rocketCenter() {
  rocket.updateWorldMatrix(true, true);
  _box.setFromObject(rocket);
  return _box.getCenter(new THREE.Vector3());
}

function zoomBy(factor) {
  const offset = camera.position.clone().sub(controls.target);
  offset.multiplyScalar(factor);
  const len = Math.min(controls.maxDistance, Math.max(controls.minDistance, offset.length()));
  offset.setLength(len);
  camera.position.copy(controls.target).add(offset);
  controls.update();
}

function frameRocket() {
  const mid = rocketCenter();
  const size = Math.max(6, _box.getSize(new THREE.Vector3()).length());
  const dist = size * 1.05;
  controls.target.copy(mid);
  camera.position.copy(mid).add(new THREE.Vector3(dist * 0.62, dist * 0.18, dist * 0.78));
  controls.update();
}

function placeVehicle(p) {
  const body = new THREE.Vector3(p.body[0], p.body[2], p.body[1]);
  if (body.lengthSq() < 1e-8) body.set(0, 1, 0);
  body.normalize();
  const pos = new THREE.Vector3(p.x, p.z, p.y);
  rocket.position.copy(pos);
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), body);
  const bank = new THREE.Quaternion().setFromAxisAngle(body, p.roll * Math.PI / 180);
  rocket.quaternion.copy(q).multiply(bank);
  rocket.userData.canards.forEach((h, i) => {
    h.children[0].rotation.x = (p.canards[i] || 0) * Math.PI / 180;
  });
  rocket.userData.flame.visible = p.thrust > 20;
  rocket.userData.flame.scale.setScalar(0.7 + Math.min(p.thrust / 450, 1.4));

  const mid = rocketCenter();
  if (follow) {
    const delta = mid.clone().sub(controls.target);
    controls.target.copy(mid);
    camera.position.add(delta);
  }
}

function stepTo(t) {
  clock = t;
  const p = atTime(clock);
  placeVehicle(p);
  updateTrails();
  setText();
  controls.update();
  renderer.render(scene, camera);
  return p;
}
window.replay = {
  get clock() { return clock; }, set clock(v) { clock = v; },
  get playing() { return playing; }, set playing(v) { playing = !!v; },
  camera, rocket, controls, frameRocket, zoomBy, stepTo,
};

function setText() {
  const p = atTime(clock);
  $("g-z").innerHTML = p.z.toFixed(0) + "<small>m</small>";
  $("g-v").innerHTML = p.speed.toFixed(0) + "<small>m/s</small>";
  $("g-hdg").innerHTML = p.heading.toFixed(1) + "<small>°</small>";
  $("g-turn").innerHTML = p.turn_dps.toFixed(2) + "<small>°/s</small>";
  $("g-lat").innerHTML = p.lat_g.toFixed(2) + "<small>g</small>";
  $("g-roll").innerHTML = Math.abs(p.p).toFixed(0) + "<small>°/s</small>";
  $("clock").textContent = clock.toFixed(2) + " s";
  $("scrub").max = 1000;
  $("scrub").value = (clock / tMax()) * 1000;

  const ref = DATA.reference_3dof;
  const auth = DATA.authority;
  const sm = DATA.flights[mode].summary;
  const ev = [
    ["0.00", "ignition"],
    [ref.rail_exit_m_s ? "rail" : "—", `rail exit ${ref.rail_exit_m_s.toFixed(1)} m/s`],
    [ref.burnout_s.toFixed(2), `burnout  ${ref.burnout_alt_m.toFixed(0)} m`],
    [(ref.burnout_s + 0.5).toFixed(2), mode === "ballistic" ? "canards faired" : "canards commanded"],
    [sm.apogee_s.toFixed(1), `apogee  ${sm.apogee_m.toFixed(0)} m`],
  ];
  $("events").innerHTML = ev.map(([t, lab]) => {
    const raw = parseFloat(t);
    const cls = (!Number.isNaN(raw) && clock >= raw - 0.05) ? "now" : "";
    return `<b class="${cls}">${typeof t === "string" && t === "rail" ? ref.rail_exit_m_s.toFixed(1) : (Number.isNaN(raw) ? t : raw.toFixed(2))}</b><span class="${cls}">${lab}</span>`;
  }).join("");

  $("note").innerHTML = `
    <b>At max-Q coast this vehicle turns at ${auth.turn_dps.toFixed(2)} deg/s.</b>
    That is ${auth.lat_g_at_8.toFixed(2)} g from 8° canard, radius ${ (auth.turn_radius_m/1000).toFixed(2) } km.
    A 45° heading change wants ${auth.t_45_s.toFixed(1)} s of pull; the usable window is ${auth.control_window_s.toFixed(1)} s.
    Roll snaps 90° in ${(90/auth.roll_2deg_dps).toFixed(2)} s at the 2° gyro cap (${auth.roll_2deg_dps.toFixed(0)} deg/s).
    Crossrange this run: <b>${sm.final_y_m.toFixed(0)} m</b>, heading <b>${sm.final_heading_deg.toFixed(1)}°</b>.
    Roll derivatives are the analytic interference model — not flight-validated.
  `;
}

document.querySelectorAll(".modes button").forEach(btn => {
  btn.onclick = () => {
    mode = btn.dataset.mode;
    document.querySelectorAll(".modes button").forEach(b => b.classList.toggle("on", b === btn));
    clock = 0;
    follow = true;
    $("follow").classList.add("on");
    frameRocket();
  };
});
$("play").onclick = () => { playing = !playing; $("play").textContent = playing ? "❚❚" : "▶"; };
$("rate").onclick = () => {
  rate = rates[(rates.indexOf(rate) + 1) % rates.length];
  $("rate").textContent = rate + "×";
};
$("scrub").oninput = (e) => { clock = (e.target.value / 1000) * tMax(); playing = false; $("play").textContent = "▶"; };
$("zoom-in").onclick = () => zoomBy(0.72);
$("zoom-out").onclick = () => zoomBy(1.38);
$("frame").onclick = () => { follow = true; $("follow").classList.add("on"); frameRocket(); };
$("follow").onclick = () => {
  follow = !follow;
  $("follow").classList.toggle("on", follow);
  if (follow) frameRocket();
};
addEventListener("keydown", (e) => {
  if (e.target.matches("input, textarea")) return;
  if (e.key === "=" || e.key === "+") zoomBy(0.72);
  if (e.key === "-" || e.key === "_") zoomBy(1.38);
  if (e.key === "f" || e.key === "F") { follow = true; $("follow").classList.add("on"); frameRocket(); }
});
canvas.addEventListener("pointerdown", (e) => {
  canvas.focus();
  if (e.button === 2) {
    follow = false;
    $("follow").classList.remove("on");
  }
});
canvas.tabIndex = 0;

function resize() {
  const stage = $("stage").getBoundingClientRect();
  const w = Math.max(1, Math.round(stage.width));
  const h = Math.max(1, Math.round(stage.height));
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(w, h, false);
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener("resize", resize);
resize();
stepTo(clock);
frameRocket();

let last = performance.now();
function tick(now) {
  try {
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    if (playing) {
      clock += dt * rate;
      if (clock > tMax()) clock = 0;
    }
    stepTo(clock);
  } catch (err) {
    window.replay.err = String(err);
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
