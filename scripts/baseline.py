"""Full analysis of the baseline vehicle, and the numbers to type into OpenRocket.

Run:  python scripts/baseline.py
      python scripts/baseline.py --plot
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from design import aero, control, flutter, trajectory
from design.configure import DesignParams, build_vehicle, evaluate
from design.motors import GENERIC, load_eng
from design.packaging import SERVOS, check_direct_drive, torque_margin

ROOT = Path(__file__).resolve().parents[1]

# Motor selected by scripts/motor_trade.py against the real ThrustCurve.org catalogue, and
# confirmed against scripts/recovery_study.py now that the field has no altitude ceiling.
# Cesaroni Pro54 J449 Blue Streak: roughly triples crossrange over the J430 while staying
# at Mach 0.55 and 8.6 g, and keeps the recovery walk near 1 km rather than 1.5 km.
MOTOR_FILE = ROOT / "data" / "motors" / "Cesaroni_1261J449-15A.eng"
MOTOR = load_eng(MOTOR_FILE) if MOTOR_FILE.exists() else GENERIC["J-54"]

# Airframe from scripts/sweep.py, with both fin sets resized by the constrained search in
# scripts/robustness.py (canard 0.70 -> 0.85 cal, aft 1.05 -> 1.55 cal).
#
# Sizing the two fin sets independently was the original mistake. They pull in opposite
# directions: canard area buys control authority but costs static margin, aft area buys
# margin but costs authority. Searched jointly under a probabilistic margin constraint, the
# answer is to grow *both* -- which beats the original airframe on crossrange and on safety
# at the same time, rather than trading one against the other.
BASELINE = DesignParams(
    outer_diameter=0.0794,  # 3.0 in fiberglass, 79.4 mm OD
    wall_thickness=0.0023,
    motor=MOTOR,
    aft_semispan_cal=1.55,
    canard_semispan_cal=0.85,
)

SERVO_CHOICE = "mini_ht"
DEFLECTION_LIMIT_DEG = 8.0
# Roll control needs far less deflection than pitch/yaw, because roll inertia is tiny.
ROLL_DEFLECTION_DEG = 2.0
GEAR_RATIO = 1.0


def rule(title: str = "", width: int = 92) -> None:
    if title:
        print("\n" + "=" * width)
        print(title)
        print("=" * width)
    else:
        print("-" * width)


def main() -> None:
    ev = evaluate(BASELINE, deflection_deg=DEFLECTION_LIMIT_DEG)
    r, f, m = ev.rocket, ev.flight, ev.masses
    d = r.diameter

    rule("BASELINE VEHICLE")
    print(f"  airframe            {d * 1000:.1f} mm OD fiberglass, {r.length * 1000:.0f} mm long, "
          f"L/D {r.fineness:.1f}")
    print(f"  motor               {BASELINE.motor.name}  "
          f"({BASELINE.motor.total_impulse:.0f} N s, class {BASELINE.motor.impulse_class}, "
          f"needs L{BASELINE.motor.requires_level})")
    if BASELINE.motor.approximate:
        print("                      ^ PLACEHOLDER motor. Replace with a real .eng curve.")
    print(f"  wet / dry mass      {m.wet_mass:.2f} / {m.dry_mass:.2f} kg")
    print(f"  feasible            {'YES' if ev.feasible else 'NO: ' + '; '.join(ev.violations)}")

    rule("GEOMETRY  (stations measured from nose tip)")
    print(f"  nose cone           {r.nose.shape}, {r.nose.length * 1000:.0f} mm "
          f"(fineness {r.nose.fineness:.1f}), CP at {r.nose.cp_station * 1000:.0f} mm")
    x = r.nose.length
    for t in r.tubes:
        print(f"  {t.name:19s} {t.length * 1000:6.0f} mm   station "
              f"{x * 1000:6.0f} -> {(x + t.length) * 1000:6.0f} mm   ID {t.inner_diameter * 1000:.1f} mm")
        x += t.length
    for fins, label in ((r.canards, "canards"), (r.aft_fins, "aft fins")):
        print(f"  {label:19s} {fins.count} panels, root {fins.root_chord * 1000:.1f} / "
              f"tip {fins.tip_chord * 1000:.1f} / semispan {fins.semispan * 1000:.1f} mm, "
              f"sweep {fins.sweep_length * 1000:.1f} mm")
        print(f"  {'':19s} root LE at {fins.x_root_le * 1000:.0f} mm, "
              f"CP at {fins.cp_station * 1000:.0f} mm")

    rule("MASS BUDGET")
    print(m.report())

    rule("FLIGHT")
    print(f.summary())
    t0, t1 = trajectory.coast_window(f)
    print(f"  usable control window {t1 - t0:7.1f} s (q > 500 Pa after burnout)")

    rule("STATIC STABILITY at max coast dynamic pressure")
    pt = max((p for p in f.points if p.t >= f.burnout_time), key=lambda p: p.q)
    stab = aero.stability(r, pt.cg, pt.mach)
    print(f"  {'component':16s} {'CNa (/rad)':>12s} {'CP (mm)':>10s} {'share':>8s}")
    for name, (cna, cp) in sorted(stab.contributions.items(), key=lambda kv: -kv[1][0]):
        print(f"  {name:16s} {cna:12.2f} {cp * 1000:10.0f} {cna / stab.cn_alpha * 100:7.1f}%")
    print(f"  {'TOTAL':16s} {stab.cn_alpha:12.2f} {stab.cp_station * 1000:10.0f}")
    print(f"\n  CG {pt.cg * 1000:.0f} mm, CP {stab.cp_station * 1000:.0f} mm, "
          f"static margin {stab.static_margin_cal:.2f} cal")
    print(f"  Cm_alpha {stab.cm_alpha:.1f} /rad")
    print(f"  same airframe with canards removed: {ev.sm_without_canards:.2f} cal")
    print(f"  --> the canards cost {ev.sm_without_canards - stab.static_margin_cal:.2f} cal of "
          f"static margin. That is the price of control authority,\n"
          f"      and it is why you cannot simply make the canards bigger.")

    rule("PITCH AUTHORITY vs DEFLECTION")
    print(f"  {'delta':>6s} {'a_trim':>8s} {'lat accel':>10s} {'canard a':>9s} "
          f"{'hinge Nm':>9s} {'wn (Hz)':>8s}  stall")
    for delta in (2.0, 4.0, 6.0, 8.0, 10.0, 12.0):
        a = control.pitch_authority(r, pt, pt.mass, delta)
        print(f"  {delta:5.0f}d {a.alpha_trim_deg:7.2f}d {a.lateral_accel_g:9.2f}g "
              f"{a.canard_local_alpha_deg:8.2f}d {a.hinge_moment_per_panel:9.4f} "
              f"{a.pitch_natural_freq_hz:8.2f}  {'STALL' if a.stalled else 'ok'}")
    print(f"\n  Cm_delta {control.pitch_authority(r, pt, pt.mass, 8.0).cm_delta:.2f} /rad")
    print(f"  one-sided manoeuvre crossrange at {DEFLECTION_LIMIT_DEG:.0f} deg: "
          f"{ev.crossrange:.0f} m over {ev.control_seconds:.1f} s")

    rule("ROLL AUTHORITY  --  the canard / aft-fin interference problem")
    for label, interf in (("aligned (0 deg offset)", control.InterferenceModel.aligned()),
                          ("interdigitated (45 deg)", control.InterferenceModel.interdigitated())):
        roll = control.roll_authority(r, pt, pt.mass, ROLL_DEFLECTION_DEG, interf)
        print(f"\n  {label}")
        print(f"    canard-to-fin spacing      {roll.spacing_cal:8.2f} cal")
        print(f"    interference strength      {roll.interference_strength:8.3f}")
        print(f"    Cl_delta from canards      {roll.cl_delta_canard:+8.3f} /rad")
        print(f"    Cl_delta from aft fins     {roll.cl_delta_aftfin:+8.3f} /rad  (opposing)")
        print(f"    Cl_delta NET               {roll.cl_delta_net:+8.3f} /rad")
        cancel = abs(roll.cl_delta_aftfin) / abs(roll.cl_delta_canard) * 100.0
        print(f"    cancellation               {cancel:8.1f}% of canard authority lost")
        print(f"    SIGN {'REVERSED -- commanded roll produces opposite roll!' if roll.reversed_sign else 'correct'}")
        print(f"    Cl_p (roll damping)        {roll.cl_p:+8.2f} /rad")
        print(f"    roll accel at {ROLL_DEFLECTION_DEG:.0f} deg      "
              f"{roll.roll_accel_deg_s2:8.0f} deg/s^2")
        print(f"    steady roll rate           {roll.steady_roll_rate_deg_s:8.0f} deg/s")

    print("\n  Sensitivity: where does the net roll moment change sign?")
    print("  Sweeping aft fin semispan (which sets how much fin area sits in the canard")
    print("  wake) against interference strength, aligned canards:\n")
    print(f"    {'aft span':>9s} {'SM':>6s} {'Cl_d can':>9s} {'Cl_d fin':>9s} "
          f"{'net':>8s} {'lost':>7s}  verdict")
    for aft_span in (0.85, 1.05, 1.25, 1.45, 1.65, 1.85):
        from dataclasses import replace as _replace

        probe = build_vehicle(_replace(BASELINE, aft_semispan_cal=aft_span))
        stab_p = aero.stability(probe, pt.cg, pt.mach)
        roll_p = control.roll_authority(
            probe, pt, pt.mass, ROLL_DEFLECTION_DEG, control.InterferenceModel.aligned()
        )
        lost = abs(roll_p.cl_delta_aftfin) / abs(roll_p.cl_delta_canard) * 100.0
        verdict = "REVERSED" if roll_p.reversed_sign else ("fragile" if lost > 70 else "ok")
        print(f"    {aft_span:9.2f} {stab_p.static_margin_cal:6.2f} "
              f"{roll_p.cl_delta_canard:+9.3f} {roll_p.cl_delta_aftfin:+9.3f} "
              f"{roll_p.cl_delta_net:+8.3f} {lost:6.1f}%  {verdict}")
    print("""
  Read this table carefully -- it is the core engineering argument of the project. Growing
  the aft fins raises static margin (good for a safe flight) while simultaneously feeding
  more fin area into the canard wake (bad for roll control). Push far enough and the net
  roll moment reverses: you command right roll and the vehicle rolls left. Any controller
  tuned on the assumed sign then saturates and diverges.

  Two things follow:
    1. Interdigitating the canards at 45 deg is not a cosmetic choice. It cuts the
       opposing term by roughly a factor of four in this model and moves the design well
       away from the reversal boundary.
    2. Because the interference factors are the least trustworthy numbers in this whole
       analysis, the first powered flight must measure them. Fly an open-loop deflection
       sweep, log commanded deflection against measured roll rate, and fit the sign and
       magnitude of Cl_delta before you ever close the loop.""")

    rule("ACTUATOR CHECK")
    servo = SERVOS[SERVO_CHOICE]
    bay = check_direct_drive(r.tubes[1].inner_diameter, servo, BASELINE.n_canards)
    print(f"  servo               {servo.name}")
    print(f"  packaging           {bay}")
    worst = max(
        (control.pitch_authority(r, p, p.mass, DEFLECTION_LIMIT_DEG) for p in f.points if p.q > 100),
        key=lambda a: a.hinge_moment_per_panel,
    )
    margin = torque_margin(worst.hinge_moment_per_panel, servo, GEAR_RATIO)
    print(f"  peak hinge moment   {worst.hinge_moment_per_panel:.4f} N m per panel "
          f"at q = {worst.dynamic_pressure / 1000:.1f} kPa")
    print(f"  usable servo torque {servo.stall_torque * 0.4 * GEAR_RATIO:.4f} N m "
          f"(stall x 0.4 derate, gear {GEAR_RATIO:.1f}:1)")
    print(f"  torque margin       {margin:.1f}x  {'OK' if margin > 2.0 else 'MARGINAL'}")
    print(f"  servo speed         {servo.speed_60deg:.2f} s/60deg "
          f"--> {60.0 / servo.speed_60deg:.0f} deg/s slew rate")
    print(f"  pitch mode          {worst.pitch_natural_freq_hz:.1f} Hz; loop rate should be "
          f">= {worst.pitch_natural_freq_hz * 20:.0f} Hz")

    rule("FIN FLUTTER")
    fast = max(f.points, key=lambda p: p.speed)
    print(f"  worst case {fast.speed:.0f} m/s at {fast.z:.0f} m altitude. Flutter speed scales as")
    print("  1/sqrt(ambient pressure), so the danger is speed low down, not Mach at apogee.\n")
    print(f"    {'fin set':10s} {'semispan':>9s} {'thick':>7s} {'AR':>5s} {'t/c':>7s} "
          f"{'V_flutter':>10s} {'margin':>7s}")
    for fins, label in ((r.aft_fins, "aft fins"), (r.canards, "canards")):
        res = flutter.evaluate(fins, fast.speed, fast.z)
        need = flutter.required_thickness(fins, fast.speed, fast.z)
        print(f"    {label:10s} {fins.semispan * 1000:8.1f}mm {fins.thickness * 1000:6.1f}mm "
              f"{res.aspect_ratio:5.2f} {res.thickness_ratio:7.4f} {res.flutter_speed:9.0f} "
              f"{res.margin:6.2f}x  {'OK' if res.ok else 'REDESIGN'}"
              f"   (>=1.5x needs {need * 1000:.1f} mm)")
    print("""
  Built from G10 at the stated thickness with the tab bonded through to the motor mount.
  Shear modulus is the weak input here -- published G10 spans 3 to 7 GPa and the result
  goes as sqrt(G), so read these as +/-25%. Surface-mounting the fins instead of
  through-the-wall invalidates the estimate entirely.""")

    rule("OPENROCKET ENTRY VALUES")
    print(f"""  Nose cone
    shape                 {r.nose.shape}  (parameter 1.0 for tangent ogive)
    length                {r.nose.length * 1000:.0f} mm
    base diameter         {d * 1000:.1f} mm
    wall thickness        {r.nose.wall_thickness * 1000:.1f} mm
    shoulder length       {d * 1000 * 1.0:.0f} mm (1 caliber, typical)

  Body tubes ({d * 1000:.1f} mm OD, {r.tubes[0].wall_thickness * 1000:.1f} mm wall, fiberglass)""")
    for t in r.tubes:
        print(f"    {t.name:18s}  {t.length * 1000:.0f} mm")
    print(f"""
  Canards (add as a FREEFORM or TRAPEZOIDAL fin set on the canard module)
    count                 {r.canards.count}
    root chord            {r.canards.root_chord * 1000:.1f} mm
    tip chord             {r.canards.tip_chord * 1000:.1f} mm
    height (semispan)     {r.canards.semispan * 1000:.1f} mm
    sweep length          {r.canards.sweep_length * 1000:.1f} mm
    thickness             {r.canards.thickness * 1000:.1f} mm
    position              {(r.canards.x_root_le - r.nose.length - r.tubes[0].length) * 1000:.1f} mm
                          from the front of the canard module
    fin rotation          45 deg relative to the aft fins  (interdigitated)

  Aft fins
    count                 {r.aft_fins.count}
    root chord            {r.aft_fins.root_chord * 1000:.1f} mm
    tip chord             {r.aft_fins.tip_chord * 1000:.1f} mm
    height (semispan)     {r.aft_fins.semispan * 1000:.1f} mm
    sweep length          {r.aft_fins.sweep_length * 1000:.1f} mm
    thickness             {r.aft_fins.thickness * 1000:.1f} mm
    position              bottom of booster tube, trailing edge flush with aft end

  Mass overrides -- OpenRocket cannot know about your avionics, so override these
    canard module         add {sum(p.mass for p in m.items if 'servo' in p.name or 'shaft' in p.name):.3f} kg
                          (servos, shafts, bearings, sled)
    avionics bay          add {sum(p.mass for p in m.items if 'avionics' in p.name):.3f} kg
    recovery              add {sum(p.mass for p in m.items if 'recovery' in p.name):.3f} kg

  Simulation settings
    launch rod / rail     3.66 m (12 ft), 5 deg from vertical
    motor                 {BASELINE.motor.name}

  Cross-check against this tool:
    expected CG           {pt.cg * 1000:.0f} mm from nose tip (dry-ish, mid coast)
    expected CP           {stab.cp_station * 1000:.0f} mm
    expected margin       {stab.static_margin_cal:.2f} cal
    expected apogee       {f.apogee:.0f} m ({f.apogee * 3.28084:.0f} ft)
    expected max Mach     {f.max_mach:.2f}

  If OpenRocket disagrees by more than about 15% on CP or apogee, find out why before
  trusting either result. Disagreement is information, not an inconvenience.""")

    if "--plot" in sys.argv:
        plot(ev)


def plot(ev) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f, r = ev.flight, ev.rocket
    t = [p.t for p in f.points]
    fig, ax = plt.subplots(2, 2, figsize=(12, 8))

    ax[0][0].plot(t, [p.z for p in f.points])
    ax[0][0].set(xlabel="t (s)", ylabel="altitude (m)", title="Altitude")

    ax[0][1].plot(t, [p.q / 1000.0 for p in f.points], label="q (kPa)")
    ax[0][1].plot(t, [p.mach * 10 for p in f.points], label="Mach x10")
    ax[0][1].axvline(f.burnout_time, ls="--", c="k", lw=0.8)
    ax[0][1].legend()
    ax[0][1].set(xlabel="t (s)", title="Dynamic pressure and Mach")

    ax[1][0].plot(t, [p.static_margin for p in f.points])
    ax[1][0].axhline(1.4, ls="--", c="r", lw=0.8)
    ax[1][0].axhline(3.0, ls="--", c="r", lw=0.8)
    ax[1][0].set(xlabel="t (s)", ylabel="calibers", title="Static margin")

    coast = [p for p in f.points if p.t >= f.burnout_time and p.q > 300]
    for delta in (4.0, 8.0, 12.0):
        g = [control.pitch_authority(r, p, p.mass, delta).lateral_accel_g for p in coast]
        ax[1][1].plot([p.t for p in coast], g, label=f"{delta:.0f} deg")
    ax[1][1].legend(title="canard deflection")
    ax[1][1].set(xlabel="t (s)", ylabel="lateral accel (g)", title="Control authority in coast")

    for a in ax.ravel():
        a.grid(alpha=0.3)
    fig.tight_layout()
    out = Path(__file__).resolve().parents[1] / "out" / "baseline.png"
    fig.savefig(out, dpi=130)
    print(f"\n  wrote {out}")


if __name__ == "__main__":
    main()
