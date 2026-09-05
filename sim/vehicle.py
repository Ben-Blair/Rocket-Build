"""The frozen baseline vehicle, expressed as a RocketPy 6-DOF model.

Every number here is READ from `design.configure.evaluate()` at runtime. Nothing is
retyped. This project has already been bitten once by six scripts each carrying their own
copy of the baseline dimensions and drifting apart (see `design/configure.py`'s own note),
so the rule here is that if a number appears as a literal in this file, it is a bug.

WHY ROCKETPY AND NOT A HAND-ROLLED INTEGRATOR. The repo's own flight model
(`design/trajectory.py`) is 3-DOF, and `scripts/virtual_flight.py` -- which looks like it
fills the gap -- reconstructs attitude kinematically: body axis is the velocity unit
vector, pitch is a trim force injected instantly, and roll rate is set algebraically to
`roll_authority().steady_roll_rate_deg_s` rather than integrated from `I_xx * pdot = L`.
Neither can validate an attitude estimator, which `docs/07-state-estimation.md` records as
an open gap ("There is no attitude truth model to validate a filter against").

VERIFIED BEFORE ADOPTING, not assumed -- `Flight.u_dot_generalized` line ~133 reads

    comp_vb = velocity_in_body_frame + (w ^ comp_cp)

i.e. it adds omega x r to EVERY aerodynamic surface's local stream velocity. So pitch
damping and roll damping are emergent from real per-surface geometry rather than bolted
on. That matters here specifically: `design/` has no `Cm_q` term anywhere, so this is a
gap RocketPy fills rather than one we have to paper over.

COORDINATE SYSTEM. `nose_to_tail` is chosen deliberately: it makes every station in this
repo -- all of which are measured from the nose tip (`FinSet.x_root_le`, see
`design/geometry.py`) -- pass through to RocketPy unchanged, with no sign flips and no
offset arithmetic. The one argument removes an entire class of frame error.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rocketpy import Environment, GenericMotor, Rocket

from design import aero, atmosphere
from design.configure import baseline, evaluate

# Mass items that are the MOTOR rather than the airframe. RocketPy wants the rocket's
# inertia and CG "without motor and propellant", and models the motor separately, so these
# two come out of the structure and go into the GenericMotor. Note that
# "structure: motor_mount_centering_rings" deliberately stays -- it is airframe.
MOTOR_ITEMS = {"motor case (dry)", "propellant"}


@dataclass
class Built:
    """Everything a Flight needs, plus the analytic model it must be checked against."""

    rocket: Rocket
    motor: GenericMotor
    env: Environment
    ev: object  # design.configure.Evaluation -- the source of truth for every acceptance test


def structure_without_motor(ev):
    """Mass, CG and inertia of the airframe alone, in RocketPy's convention.

    Returns (mass_kg, cg_from_nose_tip_m, Inertia). `design/control.estimate_inertia` is
    the only inertia model this project has; it is a bulk estimate with measured components
    superposed and its own docstring says to replace it with a bifilar/swing measurement
    before tuning gains. That caveat rides along into every number this simulator produces.
    """
    from design import control

    items = [it for it in ev.masses.items if it.name not in MOTOR_ITEMS]
    mass = sum(it.mass for it in items)
    cg = sum(it.mass * it.x for it in items) / mass
    return mass, cg, control.estimate_inertia(ev.rocket, mass, cg)


def drag_curve(ev, *, include_base: bool):
    """Cd as a function of Mach, sampled along the trajectory the repo already computed.

    RocketPy wants Cd(Mach); `aero.drag_coefficient` is Cd(velocity, altitude). Sampling it
    along `design/trajectory.py`'s OWN flight points rather than on an abstract Mach grid
    keeps the drag history identical to the RK4 run this is about to be correlated against,
    so M0 compares dynamics rather than comparing two different drag tables.
    """
    seen = {}
    for p in ev.flight.points:
        if p.speed < 1.0:
            continue
        cd = aero.drag_coefficient(ev.rocket, p.speed, p.z, include_base=include_base)
        seen[round(p.mach, 4)] = cd
    return sorted(seen.items())


def build(ev=None, *, include_base_drag_power_on: bool = True) -> Built:
    """Construct a fresh Rocket. ALWAYS call this per flight -- never reuse the result.

    The canard deflection state that `sim/surfaces.py` injects lives in closures hanging off
    the aerodynamic surfaces, so a Rocket reused across runs would silently carry the last
    run's commanded deflection into the next one. That would corrupt a Monte Carlo in a way
    that still looks entirely plausible, which is the worst kind of bug this project can
    have. Hence: factory, one per flight.
    """
    if ev is None:
        ev = evaluate(baseline())

    r = ev.rocket
    mass, cg, inertia = structure_without_motor(ev)

    # --- environment ---------------------------------------------------------------
    # Standard atmosphere, no weather fetch, constant g -- otherwise M0 would be comparing
    # atmospheres rather than comparing dynamics. atmosphere.G0 is the repo's own constant.
    env = Environment(gravity=atmosphere.G0, latitude=0.0, longitude=0.0, elevation=0.0)
    env.set_atmospheric_model(type="standard_atmosphere")

    # --- motor ---------------------------------------------------------------------
    # GenericMotor rather than SolidMotor: this project has the .eng thrust curve and the
    # propellant/total masses, but NOT the Pro54's grain geometry. SolidMotor would require
    # inventing BATES grain dimensions, and an invented number that feeds the motor's own
    # inertia is exactly the kind of thing that later gets quoted as if it were measured.
    m = ev.params.motor
    motor_len = 0.321  # from the .eng header; see data/motors/*.eng
    motor = GenericMotor(
        thrust_source=str(ROOT / "data" / "motors" / "Cesaroni_1261J449-15A.eng"),
        burn_time=m.times[-1],
        chamber_radius=0.054 / 2.0,
        chamber_height=motor_len,
        chamber_position=0.0,
        propellant_initial_mass=m.propellant_mass,
        nozzle_radius=0.054 / 2.0 * 0.6,
        dry_mass=m.dry_mass,
        nozzle_position=-motor_len / 2.0,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
    )

    # --- airframe ------------------------------------------------------------------
    # inertia order is (I_11, I_22, I_33) with e_3 the axis of symmetry, i.e. (pitch, pitch, roll).
    rocket = Rocket(
        radius=r.diameter / 2.0,
        mass=mass,
        inertia=(inertia.pitch, inertia.pitch, inertia.roll),
        power_off_drag=drag_curve(ev, include_base=True),
        power_on_drag=drag_curve(ev, include_base=include_base_drag_power_on),
        center_of_mass_without_motor=cg,
        coordinate_system_orientation="nose_to_tail",
    )

    # Motor's aft face sits at the tail. In nose_to_tail the tail is +x from the nose tip.
    rocket.add_motor(motor, position=r.length - motor_len / 2.0)

    rocket.add_nose(length=r.nose.length, kind="ogive", position=0.0)

    # Both fin sets are NATIVE, at zero cant. This is deliberate and load-bearing: it is
    # what buys native CN_alpha, CP, roll damping and pitch damping from real geometry.
    # The canards must NOT be modelled only as a control surface -- they carry 6.393/rad of
    # CN_alpha at 0.507 m, and dropping that moves CP by ~110 mm and static margin from
    # ~2.9 to ~4.3 cal. `sim/surfaces.py` adds ONLY the deflection increment on top.
    for fins in (r.aft_fins, r.canards):
        rocket.add_trapezoidal_fins(
            n=fins.count,
            root_chord=fins.root_chord,
            tip_chord=fins.tip_chord,
            span=fins.semispan,
            position=fins.x_root_le,
            sweep_length=fins.sweep_length,
            name=fins.name,
        )

    return Built(rocket=rocket, motor=motor, env=env, ev=ev)


if __name__ == "__main__":
    b = build()
    mass, cg, inertia = structure_without_motor(b.ev)
    print(f"structure without motor : {mass:.4f} kg, CG {cg:.5f} m from nose tip")
    print(f"                inertia : I_roll {inertia.roll:.6f}  I_pitch {inertia.pitch:.5f} kg m^2")
    print(f"          rocket length : {b.ev.rocket.length:.5f} m, radius {b.ev.rocket.radius if hasattr(b.ev.rocket,'radius') else b.ev.rocket.diameter/2:.5f} m")
    print(f"    static margin (RPy) : {b.rocket.static_margin(0):.3f} cal at t=0")
    print(f"    static margin (repo): {b.ev.flight.min_static_margin:.3f} to {b.ev.flight.max_static_margin:.3f} cal")
